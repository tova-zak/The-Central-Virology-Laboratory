"""Small isolated metadata probes; never import the application or providers."""
import logging
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch

from app.core.ocr_diagnostics import log_ocr_startup


def run_probe(caplog, outputs=(), command="tesseract"):
    config = SimpleNamespace(tesseract_cmd=None, enable_ocr=False,
                             enable_hybrid_verification=False)
    settings = SimpleNamespace(enable_ocr=True, hybrid_engine_enabled=False,
                               enable_hybrid_verification=True)
    module = SimpleNamespace(get_hybrid_config=lambda: config)
    with patch.dict(sys.modules, {"app.core.hybrid_config": module}), \
            patch("app.core.ocr_diagnostics.shutil.which", return_value=command), \
            patch("app.core.ocr_diagnostics.subprocess.run", side_effect=outputs) as run, \
            caplog.at_level(logging.INFO, logger="uvicorn.error"):
        log_ocr_startup(settings)
    return run


def test_available_disabled_and_redacted(caplog):
    run = run_probe(caplog, [
        subprocess.CompletedProcess([], 0, "tesseract 5.5.0\nsecret", "secret"),
        subprocess.CompletedProcess([], 0, 'List of available languages in "secret" (2):\nheb\neng\n', ""),
    ])
    assert "version=5.5.0" in caplog.text
    assert "languages=eng,heb" in caplog.text
    assert "runtime_ready=True" in caplog.text
    assert "ocr_enabled=False hybrid_engine_enabled=False" in caplog.text
    assert "secret" not in caplog.text
    assert [call.args[0][1] for call in run.call_args_list] == ["--version", "--list-langs"]
    assert all(call.kwargs["timeout"] == 2 for call in run.call_args_list)


def test_missing_binary(caplog):
    run = run_probe(caplog, command=None)
    run.assert_not_called()
    assert "missing=tesseract" in caplog.text


def test_missing_hebrew(caplog):
    run_probe(caplog, [subprocess.CompletedProcess([], 0, "tesseract 5.5.0\n", ""),
                       subprocess.CompletedProcess([], 0, "Languages:\neng\n", "")])
    assert "missing_required_languages=heb runtime_ready=False" in caplog.text


def test_timeout_and_failure_are_safe(caplog):
    run_probe(caplog, [subprocess.TimeoutExpired("secret", 2),
                       OSError("secret")])
    assert "version_probe=timeout" in caplog.text
    assert "language_probe=unavailable" in caplog.text
    assert "runtime_ready=False" in caplog.text
    assert "secret" not in caplog.text
