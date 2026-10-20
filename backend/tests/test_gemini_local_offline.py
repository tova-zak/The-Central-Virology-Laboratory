"""Focused Gemini contract tests. Real SDK conversion, synthetic data, in-memory HTTP only."""
import json
import socket

import httpx
import pytest

from app.services.extraction import gemini_adapter as adapter
from app.services.extraction import gemini_key_manager as keys
from app.services.extraction.extractor import ExtractionError
from app.services.extraction.quota_manager import QuotaManager, parse_gemini_error


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def reject(*args, **kwargs):
        raise AssertionError("Network access is forbidden in this offline test")
    # Windows asyncio implements its internal socketpair via loopback connect.
    # Permit only that synchronous socketpair construction, never outbound sockets/HTTP.
    original_connect = socket.socket.connect
    original_pair = socket.socketpair
    making_pair = False

    def guarded_connect(sock, address):
        if making_pair and address[0] in ("127.0.0.1", "::1"):
            return original_connect(sock, address)
        return reject()

    def internal_pair(*args, **kwargs):
        nonlocal making_pair
        making_pair = True
        try:
            return original_pair(*args, **kwargs)
        finally:
            making_pair = False

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket, "socketpair", internal_pair)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", reject)
    for name in keys.GeminiKeyManager.KEY_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(keys, "dotenv_values", lambda path: {"GEMINI_API_1": "unit-test-not-a-real-credential"})
    monkeypatch.setattr(keys, "_key_manager", None)
    from app.core.config import settings
    monkeypatch.setattr(settings, "demo_mode", False)
    monkeypatch.setattr(settings, "deployment_mode", "local")
    monkeypatch.setattr(settings, "supabase_url", "")
    monkeypatch.setattr(settings, "supabase_service_key", "")


def payload():
    return {"patient_first_name": "Synthetic", "patient_last_name": "Example",
            "patient_id_number": "SYNTHETIC-ID", "sender": None, "received_date": "2026-10-20",
            "central_numbers": ["SYN-LAB"], "commitment_numbers": ["SYN-COMMITMENT"],
            "commitment_types": [], "warnings": []}


def extractor_with_transport(monkeypatch, handler):
    from google import genai
    from google.genai import types
    original = genai.Client

    def create_client(**kwargs):
        # Dispose unused real-network client; replace it with the in-memory transport.
        kwargs["http_options"].httpx_client.close()
        kwargs["http_options"] = types.HttpOptions(
            httpx_client=httpx.Client(transport=httpx.MockTransport(handler)),
            retry_options=types.HttpRetryOptions(attempts=1),
        )
        return original(**kwargs)

    monkeypatch.setattr(adapter.genai, "Client", create_client)
    extractor = adapter.GeminiExtractor(model="gemini-3.8-flash")
    extractor.quota_manager = QuotaManager()
    return extractor


def test_sdk_schema_and_patient_fields_without_network(monkeypatch, caplog):
    seen = []

    def respond(request):
        body = json.loads(request.content)
        seen.append(body)
        config = body["generationConfig"]
        assert "additionalProperties" not in json.dumps(config)
        assert "temperature" not in config
        return httpx.Response(200, json={"candidates": [{"content": {
            "parts": [{"text": json.dumps(payload())}], "role": "model"}, "finishReason": "STOP"}]})

    extractor = extractor_with_transport(monkeypatch, respond)
    result = extractor.extract(b"\x89PNG\r\n\x1a\nsynthetic-image", "synthetic_doc", 0)
    assert len(seen) == 1
    assert result.fields["patient_first_name"] == "Synthetic"
    assert result.fields["patient_id_number"] == "SYNTHETIC-ID"
    assert result.fields["central_numbers"] == ["SYN-LAB"]
    assert result.fields["commitment_numbers"] == ["SYN-COMMITMENT"]
    assert "unit-test-not-a-real-credential" not in caplog.text


@pytest.mark.parametrize("status,message,code", [
    (400, "API_KEY_INVALID DO_NOT_LOG_PROVIDER_CONTENT", "invalid_credentials"),
    (403, "PERMISSION_DENIED DO_NOT_LOG_PROVIDER_CONTENT", "invalid_credentials"),
    (404, "Model not found DO_NOT_LOG_PROVIDER_CONTENT", "model_incompatible"),
    (400, "Model does not support generateContent DO_NOT_LOG_PROVIDER_CONTENT", "model_incompatible"),
    (400, "additionalProperties is not supported DO_NOT_LOG_PROVIDER_CONTENT", "schema_incompatible"),
    (429, "RESOURCE_EXHAUSTED requests per minute retry after 60s DO_NOT_LOG_PROVIDER_CONTENT", "rate_limit"),
    (429, "RESOURCE_EXHAUSTED requests per day DO_NOT_LOG_PROVIDER_CONTENT", "daily_quota"),
    (503, "UNAVAILABLE DO_NOT_LOG_PROVIDER_CONTENT", "provider_unavailable"),
])
def test_controlled_provider_errors(monkeypatch, caplog, status, message, code):
    calls = []

    def respond(request):
        calls.append(1)
        return httpx.Response(status, json={"error": {"code": status, "message": message}})

    extractor = extractor_with_transport(monkeypatch, respond)
    with pytest.raises(ExtractionError) as caught:
        extractor.extract(b"\x89PNGsynthetic", "synthetic_doc", 0)
    assert caught.value.code == code
    assert len(calls) == 1
    assert "DO_NOT_LOG_PROVIDER_CONTENT" not in str(caught.value)
    assert "DO_NOT_LOG_PROVIDER_CONTENT" not in caplog.text
    assert "unit-test-not-a-real-credential" not in caplog.text
    if code in ("rate_limit", "daily_quota"):
        blocked = extractor.quota_manager.get_all_exhausted_quotas()[extractor.model]
        assert "DO_NOT_LOG_PROVIDER_CONTENT" not in blocked.error_message
        assert blocked.quota_type == code


@pytest.mark.parametrize("text", ["not JSON", "[]", '{"patient_id_number": 123}'])
def test_invalid_output_never_becomes_synthetic_success(monkeypatch, text):
    def respond(request):
        return httpx.Response(200, json={"candidates": [{"content": {
            "parts": [{"text": text}], "role": "model"}, "finishReason": "STOP"}]})
    extractor = extractor_with_transport(monkeypatch, respond)
    with pytest.raises(ExtractionError) as caught:
        extractor.extract(b"\x89PNGsynthetic", "synthetic_doc", 0)
    assert caught.value.code == "invalid_response"


def test_timeout_is_sanitized(monkeypatch):
    def respond(request):
        raise httpx.ReadTimeout("DO_NOT_LOG_PROVIDER_CONTENT", request=request)
    extractor = extractor_with_transport(monkeypatch, respond)
    with pytest.raises(ExtractionError) as caught:
        extractor.extract(b"\x89PNGsynthetic", "synthetic_doc", 0)
    assert caught.value.code == "provider_timeout"
    assert "DO_NOT_LOG_PROVIDER_CONTENT" not in str(caught.value)


def test_keys_use_selected_file_with_process_precedence(monkeypatch, caplog):
    monkeypatch.setattr(keys, "dotenv_values", lambda path: {
        "GEMINI_API_KEY": "file-primary", "GEMINI_API_1": "duplicate-secret-sentinel",
        "GEMINI_API_2": "duplicate-secret-sentinel"})
    monkeypatch.setenv("GEMINI_API_KEY", "process-primary")
    manager = keys.GeminiKeyManager()
    assert manager.get_total_key_count() == 2
    assert manager.get_next_key()[1] == "process-primary"
    assert manager.get_next_key()[1] == "duplicate-secret-sentinel"
    assert "duplicate-secret-sentinel" not in caplog.text
    assert "duplicate-secret-sentinel" not in repr(manager._keys)
    assert "process-primary" not in repr(manager._keys)


def test_generic_429_is_not_daily_quota():
    assert parse_gemini_error(Exception("429 RESOURCE_EXHAUSTED quota exceeded per minute"))[0] is False
    assert parse_gemini_error(Exception("429 quota exceeded per day"))[0] is True


def test_hosted_security_guards_stay_closed():
    from app.core.config import Settings
    with pytest.raises(ValueError, match="PRODUCTION BLOCKED"):
        Settings(_env_file=None, deployment_mode="production").validate_deployment()
    with pytest.raises(ValueError, match="DEMO_MODE"):
        Settings(_env_file=None, deployment_mode="staging", demo_mode=False).validate_deployment()


@pytest.mark.parametrize("code,delay", [("invalid_credentials", None), ("daily_quota", None), ("rate_limit", 60)])
def test_background_does_not_retry_permanent_errors_or_long_cooldowns(code, delay):
    import asyncio
    from app.services.processing.background import BackgroundProcessor
    from unittest.mock import Mock
    processor = object.__new__(BackgroundProcessor)
    processor._extractor = Mock()
    processor._extractor.extract.side_effect = ExtractionError(
        "Controlled failure", code=code, retryable=code == "rate_limit", retry_after_seconds=delay)
    processor._max_retries = 2
    processor._retry_delay = 0
    processor._gemini_timeout_seconds = 5
    with pytest.raises(ExtractionError):
        asyncio.run(processor._extract_with_retry(b"synthetic", "synthetic_doc", 0))
    assert processor._extractor.extract.call_count == 1


def test_background_retries_transient_failure_without_mock_substitution():
    import asyncio
    from app.services.processing.background import BackgroundProcessor
    from unittest.mock import Mock
    processor = object.__new__(BackgroundProcessor)
    processor._extractor = Mock()
    expected = object()
    processor._extractor.extract.side_effect = [
        ExtractionError("Unavailable", code="provider_unavailable", retryable=True), expected]
    processor._max_retries = 1
    processor._retry_delay = 0
    processor._gemini_timeout_seconds = 5
    assert asyncio.run(processor._extract_with_retry(b"synthetic", "synthetic_doc", 0)) is expected
    assert processor._extractor.extract.call_count == 2


def test_real_adapter_results_keep_one_commitment_per_page(monkeypatch):
    from app.services.processing.background import BackgroundProcessor
    from app.domain.models import ReviewState
    def respond(request):
        data = payload()
        data["commitment_numbers"] = ["SYN-C1", "SYN-C2"]
        return httpx.Response(200, json={"candidates": [{"content": {
            "parts": [{"text": json.dumps(data)}], "role": "model"}, "finishReason": "STOP"}]})
    extractor = extractor_with_transport(monkeypatch, respond)
    processor = object.__new__(BackgroundProcessor)
    records = []
    for page in range(3):
        result = extractor.extract(b"\x89PNGsynthetic", "synthetic_doc", page)
        records.append(processor._create_commitment_from_page(result, "synthetic_doc", page))
    assert len(records) == 3
    assert len({record.form_id for record in records}) == 3
    for record in records:
        assert record.patient_first_name.raw_value == "Synthetic"
        assert record.patient_id_number.raw_value == "SYNTHETIC-ID"
        assert record.central_numbers.raw_value == ["SYN-LAB"]
        assert record.commitment_number.review_state == ReviewState.needs_review


@pytest.fixture
def staging_real(monkeypatch):
    from app.core.config import settings
    for name, value in {
        "deployment_mode": "staging-real", "demo_mode": False,
        "supabase_url": "https://synthetic-staging.invalid",
        "supabase_service_key": "offline-storage-sentinel",
        "api_username": "offline-operator", "api_password": "offline-password-sentinel",
        "cors_origins": ["https://synthetic-frontend.invalid"],
    }.items():
        monkeypatch.setattr(settings, name, value)
    monkeypatch.setenv("GEMINI_API_8", "offline-provider-sentinel")
    return settings


def test_staging_real_accepts_only_explicit_nonmock_mode(staging_real, monkeypatch):
    staging_real.validate_deployment()
    monkeypatch.setattr(staging_real, "demo_mode", True)
    with pytest.raises(ValueError, match="DEMO_MODE=false"):
        staging_real.validate_deployment()


def test_blueprint_settings_parse_as_restricted_real_staging(staging_real):
    from pathlib import Path
    import yaml
    from app.core.config import Settings
    blueprint = yaml.safe_load((Path(__file__).resolve().parents[2] / "render.yaml").read_text(encoding="utf-8"))
    backend = next(service for service in blueprint["services"] if service["runtime"] == "docker")
    values = {item["key"].lower(): item["value"] for item in backend["envVars"] if "value" in item}
    parsed = Settings(_env_file=None, **values, supabase_url=staging_real.supabase_url,
                      supabase_service_key=staging_real.supabase_service_key,
                      api_username=staging_real.api_username, api_password=staging_real.api_password,
                      cors_origins=staging_real.cors_origins)
    parsed.validate_deployment()
    assert parsed.deployment_mode == "staging-real" and parsed.demo_mode is False
    assert parsed.max_file_size_mb == 10 and parsed.max_pages_per_document == 10


@pytest.mark.parametrize("mode", ["staging", "cloud", "production"])
def test_real_staging_does_not_unlock_other_hosted_modes(staging_real, monkeypatch, mode):
    monkeypatch.setattr(staging_real, "deployment_mode", mode)
    with pytest.raises(ValueError, match="PRODUCTION BLOCKED" if mode == "production" else "DEMO_MODE"):
        staging_real.validate_deployment()


@pytest.mark.parametrize("name,value", [
    ("supabase_url", ""), ("supabase_service_key", ""),
    ("api_username", ""), ("api_password", "short"),
    ("supabase_url", "http://synthetic-staging.invalid"),
    ("cors_origins", []), ("cors_origins", ["https://*.invalid"]),
    ("cors_origins", ["http://synthetic-frontend.invalid"]),
    ("gemini_model", ""),
])
def test_real_staging_retains_hosted_startup_guards(staging_real, monkeypatch, name, value):
    monkeypatch.setattr(staging_real, name, value)
    with pytest.raises(ValueError):
        staging_real.validate_deployment()


def test_real_staging_rejects_file_only_credentials(staging_real, monkeypatch):
    monkeypatch.delenv("GEMINI_API_8")
    monkeypatch.setattr(staging_real, "gemini_api_key", "file-only-sentinel")
    with pytest.raises(ValueError, match="backend environment variables"):
        staging_real.validate_deployment()


def test_hosted_key_manager_never_reads_dotenv(staging_real, monkeypatch):
    def forbidden_file(*args, **kwargs):
        raise AssertionError("Hosted Gemini keys must not come from dotenv files")
    monkeypatch.setattr(keys, "dotenv_values", forbidden_file)
    manager = keys.GeminiKeyManager()
    assert manager.get_total_key_count() == 1
    assert manager.get_next_key()[1] == "offline-provider-sentinel"


def test_real_staging_selects_gemini_and_supabase_without_network(staging_real, monkeypatch):
    from unittest.mock import Mock
    from app.services.storage import storage_adapter
    from app.services.processing.background import BackgroundProcessor
    persistent_store = Mock()
    factory = Mock(return_value=persistent_store)
    monkeypatch.setattr(storage_adapter, "SupabaseStorageAdapter", factory)
    monkeypatch.setattr(adapter.genai, "Client", Mock(side_effect=AssertionError("No live client permitted")))
    processor = BackgroundProcessor()
    assert processor._storage is persistent_store
    factory.assert_called_once_with()
    assert isinstance(processor._extractor, adapter.GeminiExtractor)
    assert processor.extractor_name == "GeminiExtractor"
    assert processor._extractor.client is None


def test_real_staging_still_requires_authentication(staging_real):
    from app.core.access import require_access
    from fastapi import HTTPException
    from fastapi.security import HTTPBasicCredentials
    with pytest.raises(HTTPException) as caught:
        require_access(None)
    assert caught.value.status_code == 401
    require_access(HTTPBasicCredentials(username=staging_real.api_username, password=staging_real.api_password))


def test_quota_terminal_status_includes_persisted_errors(staging_real, monkeypatch):
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import Mock
    from app.services.storage import storage_adapter
    monkeypatch.setattr(storage_adapter, "SupabaseStorageAdapter", Mock())
    from app.api import process
    job = SimpleNamespace(status=process.ProcessingStatus.QUOTA_EXHAUSTED, progress={})
    processor = Mock()
    processor.get_job_status.return_value = job
    monkeypatch.setattr(process, "get_processor", lambda: processor)
    store = Mock()
    store.load_batch.return_value = {
        "batch_id": "synthetic_batch", "status": "quota_exhausted",
        "commitment_records": [], "test_records": [],
        "errors": [{"error": "Gemini daily quota exhausted", "error_code": "daily_quota"}],
    }
    monkeypatch.setattr(process, "_storage", store)
    result = asyncio.run(process.get_batch_status("synthetic_batch"))
    assert result["status"] == "quota_exhausted"
    assert result["errors"][0]["error_code"] == "daily_quota"
