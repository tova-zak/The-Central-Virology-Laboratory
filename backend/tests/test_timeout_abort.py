import time, threading
from app.services.processing.background import ProcessingStatus
from app.services.extraction import gemini_adapter as adapter
from tests.test_extraction_pipeline_bounded import MemoryStorage, make_pdf, seed_batch, make_processor, run_batch, no_network  # noqa: F401


def test_late_provider_result_cannot_overwrite_failed_batch_and_call_is_aborted(tmp_path):
    aborted, finished = threading.Event(), threading.Event()

    class Slow:
        def extract(self, image, document_id, page_index):
            aborted.wait(5)  # blocked provider call; released only by abort_inflight
            finished.set()
            raise RuntimeError("late 503 after the deadline")

        def abort_inflight(self):
            aborted.set()

    storage = MemoryStorage()
    batch_id = seed_batch(storage, make_pdf(tmp_path / "one.pdf", [(1, 1, 1)]).read_bytes(), 1)
    job, elapsed = run_batch(make_processor(Slow(), storage, timeout=1), batch_id)
    assert job.status == ProcessingStatus.FAILED and elapsed < 3
    assert finished.wait(2), "orphaned call kept running after the deadline"
    saved = storage.load_batch(batch_id)
    assert saved["status"] == "failed" and saved["errors"][0]["error_code"] == "provider_timeout"
    time.sleep(0.2)
    assert storage.load_batch(batch_id) == saved  # the late failure changed nothing


def test_adapter_abort_closes_inflight_clients():
    closed = []

    class Closable:
        def close(self):
            closed.append(1)

    extractor = adapter.GeminiExtractor()
    extractor._inflight = [Closable(), Closable()]
    extractor.abort_inflight()
    assert len(closed) == 2
