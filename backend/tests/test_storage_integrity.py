import hashlib
from app.services.processing.background import ProcessingStatus, verify_download_integrity
from tests.test_extraction_pipeline_bounded import MemoryStorage, make_pdf, make_processor, run_batch, no_network  # noqa: F401
from app.services.extraction.extractor import ExtractionResult


def seed(storage, original, stored, sha=True):
    storage.upload_file("batch_i", "doc_i.pdf", stored)  # what download_file will return
    manifest = {"document_id": "doc_i", "storage_name": "doc_i.pdf", "size_bytes": len(original), "page_count": 1}
    if sha:
        manifest["sha256"] = hashlib.sha256(original).hexdigest()
    storage.save_batch("batch_i", {"batch_id": "batch_i", "status": "uploaded", "documents": [manifest],
                                   "test_records": [], "commitment_records": [], "errors": [], "demo_mode": False})


class Recorder:
    calls = 0

    def extract(self, image, document_id, page_index):
        Recorder.calls += 1
        fields = {"patient_first_name": "A", "patient_last_name": "B", "patient_id_number": "1", "sender": None,
                  "received_date": None, "central_numbers": [], "commitment_numbers": []}
        return ExtractionResult("1.0", fields, [], "m", "2.0", 1.0)


def test_altered_download_stops_extraction_with_storage_integrity_error(tmp_path):
    original = make_pdf(tmp_path / "o.pdf", [(1, 0, 0)]).read_bytes()
    altered = make_pdf(tmp_path / "a.pdf", [(1, 1, 1)]).read_bytes()
    storage = MemoryStorage()
    seed(storage, original, altered)
    Recorder.calls = 0
    job, _ = run_batch(make_processor(Recorder(), storage), "batch_i")
    saved = storage.load_batch("batch_i")
    assert Recorder.calls == 0  # never extract from bytes that are not the uploaded file
    assert job.status == ProcessingStatus.FAILED and saved["status"] == "failed"
    error = saved["errors"][0]
    assert error["error_code"] == "storage_integrity_error"
    assert error["diagnostics"]["actual_bytes"] == len(altered) and error["diagnostics"]["expected_bytes"] == len(original)
    assert error["diagnostics"]["expected_sha256_prefix"] == hashlib.sha256(original).hexdigest()[:8]
    record = saved["commitment_records"][0]  # page still represented; review/export stay blocked
    assert record["commitment_number"]["review_state"] == "needs_review"
    assert record["patient_first_name"]["raw_value"] is None


def test_matching_download_extracts_normally(tmp_path):
    original = make_pdf(tmp_path / "o.pdf", [(1, 0, 0)]).read_bytes()
    storage = MemoryStorage()
    seed(storage, original, original)
    Recorder.calls = 0
    job, _ = run_batch(make_processor(Recorder(), storage), "batch_i")
    assert Recorder.calls == 1 and job.status == ProcessingStatus.COMPLETED


def test_legacy_manifest_without_hash_is_not_blocked(tmp_path):
    original = make_pdf(tmp_path / "o.pdf", [(1, 0, 0)]).read_bytes()
    storage = MemoryStorage()
    seed(storage, original, original, sha=False)
    assert verify_download_integrity({"document_id": "d"}, b"anything") is None
    Recorder.calls = 0
    job, _ = run_batch(make_processor(Recorder(), storage), "batch_i")
    assert Recorder.calls == 1 and job.status == ProcessingStatus.COMPLETED
