"""Offline regression tests for the real-Gemini extraction pipeline (synthetic data only).

Proves: page count -> one request per page, bounded payload, Gemini JSON -> seven fields -> persisted record,
HTTP 504 -> bounded retries + circuit breaker + terminal failure, batch deadline, interrupted-batch reporting.
The real GeminiExtractor (real SDK conversion) is used with an in-memory HTTP transport; no network,
no credentials, and MockExtractor is never substituted for the Gemini adapter.
"""
import asyncio
import base64
import copy
import hashlib
import io
import json
import time
from types import SimpleNamespace

import httpx
import pytest

from app.core.config import Settings
from app.services.documents.renderer import DocumentRenderer
from app.services.extraction import gemini_adapter as adapter
from app.services.extraction.extractor import ExtractionError, ExtractionResult
from app.services.processing.background import BackgroundProcessor, ProcessingJob, ProcessingStatus
# Re-use the offline guard (autouse: blocks every outbound socket) and the in-memory transport helper.
from tests.test_gemini_local_offline import no_network, payload, extractor_with_transport  # noqa: F401

CLALIT = "\u05db\u05dc\u05dc\u05d9\u05ea"
TERMINAL = {"completed", "completed_with_errors", "failed", "quota_exhausted"}


class MemoryStorage:
    """Minimal in-memory stand-in for the Supabase/JSON storage backend."""

    def __init__(self):
        self.batches = {}
        self.files = {}

    def upload_file(self, batch_id, name, content):
        self.files[(batch_id, name)] = content
        return f"{batch_id}/{name}"

    def download_file(self, batch_id, name):
        return self.files[(batch_id, name)]

    def save_batch(self, batch_id, data):
        stored = copy.deepcopy(data)
        stored["saved_at"] = "2026-10-20T00:00:00+00:00"
        self.batches[batch_id] = stored

    def load_batch(self, batch_id):
        data = self.batches.get(batch_id)
        return copy.deepcopy(data) if data is not None else None


def make_pdf(path, colors):
    """Synthetic PDF: one 540x768pt page per colour, each with a large filled rectangle."""
    import pymupdf
    doc = pymupdf.open()
    for color in colors:
        page = doc.new_page(width=540, height=768)
        page.draw_rect(pymupdf.Rect(40, 40, 500, 700), color=color, fill=color)
        page.insert_text((60, 80), "SYNTHETIC", fontsize=24)
    doc.save(str(path))
    doc.close()
    return path


def seed_batch(storage, pdf_bytes, page_count, batch_id="batch_synthetic01", doc_id="doc_synthetic01"):
    name = f"{doc_id}.pdf"
    storage.upload_file(batch_id, name, pdf_bytes)
    storage.save_batch(batch_id, {
        "batch_id": batch_id, "status": "uploaded", "test_records": [], "commitment_records": [],
        "errors": [], "demo_mode": False,
        "documents": [{"document_id": doc_id, "storage_name": name, "size_bytes": len(pdf_bytes),
                       "page_count": page_count}]})
    return batch_id


def make_processor(extractor, storage, *, max_retries=1, consecutive=2, batch_deadline=1800, timeout=30):
    processor = object.__new__(BackgroundProcessor)
    processor._jobs = {}
    processor._storage = storage
    processor._renderer = DocumentRenderer(dpi=300, max_dimension=3000)
    processor._extractor = extractor
    processor._gemini_timeout_seconds = timeout
    processor._max_retries = max_retries
    processor._retry_delay = 0
    processor._max_consecutive_failures = consecutive
    processor._batch_deadline_seconds = batch_deadline
    return processor


def run_batch(processor, batch_id):
    job = ProcessingJob(batch_id)
    processor._jobs[batch_id] = job

    async def scenario():
        started = time.monotonic()
        await processor._process_batch(job)
        return time.monotonic() - started

    elapsed = asyncio.run(scenario())
    return job, elapsed


def gemini_ok(data):
    return httpx.Response(200, json={"candidates": [{"content": {
        "parts": [{"text": json.dumps(data)}], "role": "model"}, "finishReason": "STOP"}]})


def inline_image(body):
    for part in body["contents"][0]["parts"]:
        if "inlineData" in part:
            blob = part["inlineData"]
            data = blob["data"]
            return blob["mimeType"], base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))
    raise AssertionError("request carried no inline image")


def dominant(image_bytes):
    from PIL import Image
    with Image.open(io.BytesIO(image_bytes)) as image:
        return image.convert("RGB").resize((8, 8)).getpixel((4, 4))


# ---------------------------------------------------------------- 1. one page in -> one request out

def test_one_page_pdf_renders_one_page_and_makes_exactly_one_gemini_request(tmp_path, monkeypatch):
    pdf = make_pdf(tmp_path / "one.pdf", [(1, 0, 0)])
    assert len(DocumentRenderer(dpi=300, max_dimension=3000).pdf_to_images(pdf)) == 1

    bodies = []

    def respond(request):
        bodies.append(json.loads(request.content))
        return gemini_ok(payload())

    storage = MemoryStorage()
    batch_id = seed_batch(storage, pdf.read_bytes(), 1)
    job, _ = run_batch(make_processor(extractor_with_transport(monkeypatch, respond), storage), batch_id)

    assert job.status == ProcessingStatus.COMPLETED
    assert len(bodies) == 1
    mime, sent = inline_image(bodies[0])
    from PIL import Image
    assert mime == "image/jpeg"
    assert max(Image.open(io.BytesIO(sent)).size) <= 2048
    red, green, blue = dominant(sent)
    assert red > 200 and green < 60 and blue < 60  # the red page itself, not another/blank page
    assert len(storage.load_batch(batch_id)["commitment_records"]) == 1


def test_each_page_is_sent_once_in_order_without_duplicates(tmp_path, monkeypatch):
    pdf = make_pdf(tmp_path / "three.pdf", [(1, 0, 0), (0, 1, 0), (0, 0, 1)])
    seen = []

    def respond(request):
        seen.append(dominant(inline_image(json.loads(request.content))[1]))
        return gemini_ok(payload())

    storage = MemoryStorage()
    batch_id = seed_batch(storage, pdf.read_bytes(), 3)
    job, _ = run_batch(make_processor(extractor_with_transport(monkeypatch, respond), storage), batch_id)

    assert job.status == ProcessingStatus.COMPLETED
    assert len(seen) == 3
    assert seen[0][0] > 200 and seen[1][1] > 200 and seen[2][2] > 200  # red, green, blue in page order
    records = storage.load_batch(batch_id)["commitment_records"]
    assert sorted(r["form_id"] for r in records) == [f"doc_synthetic01_page_{i}" for i in range(3)]


# ---------------------------------------------------------------- 2. response -> seven fields -> saved -> visible

def test_gemini_json_maps_to_all_seven_fields_is_persisted_and_served(tmp_path, monkeypatch):
    from app.api import process
    data = {"patient_first_name": "Synthetic", "patient_last_name": "Example", "patient_id_number": "012345678",
            "sender": CLALIT, "received_date": "20/10/2026", "central_numbers": ["SYN-LAB-1", "SYN-LAB-2"],
            "commitment_numbers": ["SYN-COMMITMENT"], "commitment_types": [], "warnings": []}
    pdf = make_pdf(tmp_path / "one.pdf", [(1, 1, 1)])
    storage = MemoryStorage()
    batch_id = seed_batch(storage, pdf.read_bytes(), 1)
    processor = make_processor(extractor_with_transport(monkeypatch, lambda request: gemini_ok(data)), storage)
    job, _ = run_batch(processor, batch_id)
    assert job.status == ProcessingStatus.COMPLETED

    record = storage.load_batch(batch_id)["commitment_records"][0]
    assert record["patient_first_name"]["raw_value"] == "Synthetic"
    assert record["patient_last_name"]["raw_value"] == "Example"
    assert record["patient_id_number"]["raw_value"] == "012345678"  # leading zero preserved
    assert record["sender"]["raw_value"] == CLALIT
    assert record["received_date"]["raw_value"] == "20/10/2026"
    assert record["central_numbers"]["raw_value"] == ["SYN-LAB-1", "SYN-LAB-2"]
    assert record["commitment_number"]["raw_value"] == "SYN-COMMITMENT"

    # The same values are what the frontend polls (GET /api/batches/{id}).
    monkeypatch.setattr(process, "_storage", storage)
    monkeypatch.setattr(process, "get_processor", lambda: processor)
    served = asyncio.run(process.get_batch_status(batch_id))
    assert served["status"] == "completed"
    assert served["commitment_records"][0]["patient_first_name"]["raw_value"] == "Synthetic"


# ---------------------------------------------------------------- 3. HTTP 504 -> bounded -> terminal

def test_http_504_is_bounded_trips_breaker_and_ends_in_persisted_failure(tmp_path, monkeypatch):
    pdf = make_pdf(tmp_path / "six.pdf", [(1, 1, 1)] * 6)  # the incident shape: 6 pages
    http_calls = []

    def respond(request):
        http_calls.append(1)
        return httpx.Response(504, json={"error": {"code": 504, "message": "DO_NOT_LOG_PROVIDER_CONTENT",
                                                      "status": "DEADLINE_EXCEEDED"}})

    storage = MemoryStorage()
    batch_id = seed_batch(storage, pdf.read_bytes(), 6)
    job, elapsed = run_batch(make_processor(extractor_with_transport(monkeypatch, respond), storage), batch_id)

    assert len(http_calls) == 4  # 2 pages x 2 attempts; SDK adds no hidden retries; pages 3-6 never requested
    assert elapsed < 30
    assert job.status == ProcessingStatus.FAILED
    saved = storage.load_batch(batch_id)
    assert saved["status"] == "failed"  # terminal and persisted (never left as processing)
    codes = [e["error_code"] for e in saved["errors"]]
    assert codes[:2] == ["provider_unavailable", "provider_unavailable"]
    assert codes.count("provider_circuit_open") == 1
    assert codes.count("page_not_processed") == 4
    first = saved["errors"][0]
    assert first["diagnostics"]["http_status"] == 504
    assert first["diagnostics"]["api_status"] == "DEADLINE_EXCEEDED"
    assert first["diagnostics"]["payload_bytes"] > 0
    assert "DO_NOT_LOG_PROVIDER_CONTENT" not in json.dumps(saved["errors"])
    assert len(saved["commitment_records"]) == 6  # every page is represented for manual review
    assert job.progress["pages_failed"] == 2 and job.progress["pages_succeeded"] == 0


def test_transient_504_then_success_uses_the_single_allowed_retry(tmp_path, monkeypatch):
    pdf = make_pdf(tmp_path / "one.pdf", [(1, 1, 1)])
    answers = [httpx.Response(504, json={"error": {"code": 504, "message": "x"}}), gemini_ok(payload())]
    calls = []

    def respond(request):
        calls.append(1)
        return answers[len(calls) - 1]

    storage = MemoryStorage()
    batch_id = seed_batch(storage, pdf.read_bytes(), 1)
    job, _ = run_batch(make_processor(extractor_with_transport(monkeypatch, respond), storage), batch_id)
    assert len(calls) == 2
    assert job.status == ProcessingStatus.COMPLETED


@pytest.mark.parametrize("name,respond", [
    ("http_504", lambda request: httpx.Response(504, json={"error": {"code": 504, "message": "x"}})),
    ("http_503", lambda request: httpx.Response(503, json={"error": {"code": 503, "message": "x"}})),
    ("http_429", lambda request: httpx.Response(429, json={"error": {"code": 429, "message": "RESOURCE_EXHAUSTED per minute"}})),
    ("read_timeout", lambda request: (_ for _ in ()).throw(httpx.ReadTimeout("x", request=request))),
    ("connect_error", lambda request: (_ for _ in ()).throw(httpx.ConnectError("x", request=request))),
    ("bad_json", lambda request: gemini_ok.__call__({"patient_id_number": 5})),
])
def test_every_failure_mode_reaches_a_terminal_persisted_state(tmp_path, monkeypatch, name, respond):
    pdf = make_pdf(tmp_path / "two.pdf", [(1, 1, 1)] * 2)
    storage = MemoryStorage()
    batch_id = seed_batch(storage, pdf.read_bytes(), 2)
    job, elapsed = run_batch(make_processor(extractor_with_transport(monkeypatch, respond), storage), batch_id)
    saved = storage.load_batch(batch_id)
    assert job.status.value in TERMINAL and saved["status"] in TERMINAL, name
    assert job.completed_at is not None and elapsed < 30
    assert saved["errors"], name  # a meaningful error is persisted for the UI
    assert len(saved["commitment_records"]) == 2


def test_batch_deadline_cuts_a_stuck_provider_and_still_ends_terminal(tmp_path):
    pdf = make_pdf(tmp_path / "three.pdf", [(1, 1, 1)] * 3)

    class StuckProvider:
        calls = 0

        def extract(self, image, document_id, page_index):
            StuckProvider.calls += 1
            time.sleep(4)  # far longer than the 2.5 s batch budget
            raise AssertionError("must have been cut off by the deadline")

    storage = MemoryStorage()
    batch_id = seed_batch(storage, pdf.read_bytes(), 3)
    processor = make_processor(StuckProvider(), storage, batch_deadline=2.5, timeout=30)
    job, elapsed = run_batch(processor, batch_id)
    assert elapsed < 3.5  # the 30 s per-attempt limit was clamped to the remaining batch budget
    assert StuckProvider.calls == 1
    assert job.status == ProcessingStatus.FAILED
    codes = [e["error_code"] for e in storage.load_batch(batch_id)["errors"]]
    assert codes[0] == "provider_timeout" and "batch_deadline_exceeded" in codes
    assert codes.count("page_not_processed") == 2


# ---------------------------------------------------------------- 4. polling can never wait forever

def test_orphaned_processing_batch_is_reported_as_failed_not_processing_forever():
    from app.api import process
    stale = {"batch_id": "b", "status": "processing", "errors": [], "saved_at": "2020-01-01T00:00:00+00:00"}
    reported = process._report_interrupted_if_stale(stale)
    assert reported["status"] == "failed"
    assert reported["errors"][-1]["error_code"] == "processing_interrupted"
    assert stale["status"] == "processing"  # stored record untouched (manual-recovery rules unchanged)

    from datetime import datetime, timezone
    fresh = dict(stale, saved_at=datetime.now(timezone.utc).isoformat())
    assert process._report_interrupted_if_stale(fresh)["status"] == "processing"
    done = dict(stale, status="completed")
    assert process._report_interrupted_if_stale(done)["status"] == "completed"
    assert process._report_interrupted_if_stale(dict(stale, saved_at="garbage"))["status"] == "processing"


def test_failed_job_response_carries_errors_and_page_progress_for_the_ui(monkeypatch):
    from app.api import process
    storage = MemoryStorage()
    storage.save_batch("batch_f", {"batch_id": "batch_f", "status": "failed", "commitment_records": [],
                                   "test_records": [], "errors": [{"error": "Gemini endpoint returned HTTP 504",
                                                                   "error_code": "provider_unavailable", "page_index": 0}]})
    job = SimpleNamespace(status=ProcessingStatus.FAILED, progress={"page_current": 2, "page_total": 6, "pages_failed": 2})
    processor = SimpleNamespace(get_job_status=lambda batch_id: job)
    monkeypatch.setattr(process, "_storage", storage)
    monkeypatch.setattr(process, "get_processor", lambda: processor)
    served = asyncio.run(process.get_batch_status("batch_f"))
    assert served["status"] == "failed"
    assert served["errors"][0]["error_code"] == "provider_unavailable"
    assert served["progress"]["page_total"] == 6


# ---------------------------------------------------------------- 5. retries / payload / config

def test_sdk_retry_layer_is_disabled_so_only_the_worker_retries():
    import tenacity
    from google.genai import _api_client, types
    stop = _api_client.retry_args(types.HttpRetryOptions(attempts=1))["stop"]
    assert isinstance(stop, tenacity.stop_after_attempt) and stop.max_attempt_number == 1


def test_adapter_passes_configured_timeout_and_single_attempt_to_the_sdk(monkeypatch):
    # Resolve settings at run time: tests/test_batch_lifecycle.py rebinds app.core.config.settings permanently.
    import app.core.config as config_module
    monkeypatch.setattr(config_module.settings, "gemini_request_timeout_seconds", 45)
    created = []

    def create_client(**kwargs):
        created.append(kwargs["http_options"])
        raise RuntimeError("stop before any request")

    monkeypatch.setattr(adapter.genai, "Client", create_client)
    extractor = adapter.GeminiExtractor()
    extractor.quota_manager = adapter.get_quota_manager().__class__()
    with pytest.raises(ExtractionError):
        extractor.extract(b"\x89PNGsynthetic", "synthetic_doc", 0)
    options = created[0]
    assert options.timeout == 45000 and options.retry_options.attempts == 1
    assert options.httpx_client.timeout.read == 45.0


@pytest.mark.parametrize("level,expected", [("", None), ("low", "LOW"), ("high", "HIGH")])
def test_thinking_level_is_only_sent_when_configured(monkeypatch, level, expected):
    import app.core.config as config_module  # run-time lookup, see note above
    monkeypatch.setattr(config_module.settings, "gemini_thinking_level", level)
    bodies = []

    def respond(request):
        bodies.append(json.loads(request.content))
        return gemini_ok(payload())

    extractor_with_transport(monkeypatch, respond).extract(b"\x89PNGsynthetic", "synthetic_doc", 0)
    config = bodies[0]["generationConfig"]
    thinking = config.get("thinkingConfig") or {}
    # SDK 2.10 serialises this nested key in snake_case; the API accepts both spellings.
    assert (thinking.get("thinkingLevel") or thinking.get("thinking_level")) == expected


def test_rendered_scan_page_payload_shrinks_roughly_tenfold_and_keeps_text_legible():
    from PIL import Image, ImageDraw, ImageFilter
    # Scan-like page: 1499x2133 source upscaled to the renderer 2109x3000 plus mild sensor noise and dark text strokes.
    page = Image.effect_noise((1499, 2133), 6).convert("RGB").point(lambda v: 225 + (v - 128) // 8)
    draw = ImageDraw.Draw(page)
    for row in range(40):
        draw.rectangle((100, 120 + row * 48, 1400 - (row % 5) * 150, 140 + row * 48), fill=(25, 25, 25))
    page = page.resize((2109, 3000), Image.Resampling.BICUBIC)
    buffer = io.BytesIO()
    page.save(buffer, format="PNG")
    png = buffer.getvalue()

    sent, mime = adapter.prepare_image_payload(png, "image/png", 2048, 90)
    assert mime == "image/jpeg" and len(sent) < len(png) / 4
    out = Image.open(io.BytesIO(sent))
    assert max(out.size) == 2048 and abs(out.size[0] / out.size[1] - 2109 / 3000) < 0.01
    def dark_fraction(image):
        pixels = list(image.convert("L").getdata())
        return sum(1 for px in pixels if px < 90) / len(pixels)

    assert abs(dark_fraction(out) - dark_fraction(page)) < 0.02  # text strokes survive downscale + JPEG


def test_payload_preparation_never_blocks_extraction():
    assert adapter.prepare_image_payload(b"\x89PNGnot-really-a-png", "image/png", 2048, 90) == (
        b"\x89PNGnot-really-a-png", "image/png")
    assert adapter.prepare_image_payload(b"%PDF-1.7", "application/pdf", 2048, 90)[1] == "application/pdf"
    from PIL import Image
    buffer = io.BytesIO()
    Image.new("RGB", (600, 800), (250, 250, 250)).save(buffer, format="PNG")
    original = buffer.getvalue()
    assert adapter.prepare_image_payload(original, "image/png", 0, 90) == (original, "image/png")  # disabled
    small_jpeg = io.BytesIO()
    Image.new("RGB", (600, 800), (250, 250, 250)).save(small_jpeg, format="JPEG")
    assert adapter.prepare_image_payload(small_jpeg.getvalue(), "image/jpeg", 2048, 90)[0] == small_jpeg.getvalue()


def test_new_extraction_limits_have_safe_defaults_and_bounds():
    defaults = Settings(_env_file=None)
    assert (defaults.extraction_max_attempts, defaults.extraction_max_consecutive_failures) == (2, 2)
    assert defaults.extraction_batch_deadline_seconds == 1800 and defaults.gemini_request_timeout_seconds == 60
    assert defaults.gemini_image_max_dimension == 2048 and defaults.gemini_thinking_level == ""
    for bad in ({"extraction_max_attempts": 0}, {"extraction_max_attempts": 4},
                {"extraction_batch_deadline_seconds": 30}, {"gemini_thinking_level": "minimal"}):
        with pytest.raises(ValueError):
            Settings(_env_file=None, **bad)


# ---------------------------------------------------------------- 6. upload: what did the backend actually receive?

@pytest.mark.parametrize("colors", [[(1, 0, 0)], [(1, 0, 0), (0, 1, 0), (0, 0, 1)]])
def test_upload_reports_page_count_and_records_hash(tmp_path, monkeypatch, colors):
    from starlette.datastructures import Headers, UploadFile
    from app.api import upload
    storage = MemoryStorage()
    monkeypatch.setattr(upload, "get_storage_backend", lambda: storage)
    pdf = make_pdf(tmp_path / "upload.pdf", colors).read_bytes()
    file = UploadFile(file=io.BytesIO(pdf), filename="upload.pdf", headers=Headers({"content-type": "application/pdf"}))
    response = asyncio.run(upload.upload_files([file]))
    assert response.documents[0].page_count == len(colors)
    entry = storage.load_batch(response.batch_id)["documents"][0]
    assert entry["page_count"] == len(colors) and entry["size_bytes"] == len(pdf)
    assert entry["sha256"] == hashlib.sha256(pdf).hexdigest()
    assert storage.download_file(response.batch_id, entry["storage_name"]) == pdf
