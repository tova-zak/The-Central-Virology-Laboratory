import ssl
import pytest
from app.services.extraction import gemini_adapter as adapter
from app.services.extraction.extractor import ExtractionError
from tests.test_gemini_local_offline import no_network  # noqa: F401  (autouse: blocks all outbound sockets)


def run_until_client_creation(monkeypatch, force):
    import app.core.config as config_module  # run-time lookup (another test rebinds settings)
    monkeypatch.setattr(config_module.settings, "gemini_force_ipv4", force)
    transports, seen = [], {}
    real_transport = adapter.httpx.HTTPTransport

    def spy_transport(*args, **kwargs):
        transports.append(kwargs)
        return real_transport(*args, **kwargs)

    def stop_at_sdk(**kwargs):
        seen["httpx_client"] = kwargs["http_options"].httpx_client
        seen["retry_attempts"] = kwargs["http_options"].retry_options.attempts
        raise RuntimeError("stop before any request")

    monkeypatch.setattr(adapter.httpx, "HTTPTransport", spy_transport)
    monkeypatch.setattr(adapter.genai, "Client", stop_at_sdk)
    extractor = adapter.GeminiExtractor()
    extractor.quota_manager = adapter.get_quota_manager().__class__()
    with pytest.raises(ExtractionError):
        extractor.extract(b"\x89PNGsynthetic", "synthetic_doc", 0)
    return extractor, transports, seen


def test_force_ipv4_binds_transport_keeps_tls_and_is_what_the_sdk_receives(monkeypatch):
    extractor, transports, seen = run_until_client_creation(monkeypatch, True)
    assert len(transports) == 1
    assert transports[0]["local_address"] == "0.0.0.0"
    assert transports[0]["verify"] is extractor.ssl_context  # TLS verification preserved
    assert extractor.ssl_context.verify_mode == ssl.CERT_REQUIRED and extractor.ssl_context.check_hostname is True
    assert seen["httpx_client"].timeout.read == 60.0 and seen["retry_attempts"] == 1  # timeouts/retries unchanged


def test_default_keeps_the_standard_transport(monkeypatch):
    extractor, transports, seen = run_until_client_creation(monkeypatch, False)
    assert transports == []  # no custom transport: automatic proxy discovery untouched
    assert seen["httpx_client"].timeout.read == 60.0 and seen["retry_attempts"] == 1


def test_setting_defaults_to_false():
    from app.core.config import Settings
    assert Settings(_env_file=None).gemini_force_ipv4 is False
