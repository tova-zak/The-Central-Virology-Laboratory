"""Metadata-only OCR startup probe: no images, providers, or persistence."""
import logging
import re
import shutil
import subprocess


def _probe(command, argument):
    try:
        result = subprocess.run(
            [command, argument], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=2, check=False,
        )
        return ("ok", result.stdout) if result.returncode == 0 else ("failed", "")
    except subprocess.TimeoutExpired:
        return "timeout", ""
    except Exception:
        # Never log exception text, paths, environment, or raw subprocess output.
        return "unavailable", ""


def log_ocr_startup(settings):
    """Best effort, bounded probe. A missing dependency must not prevent startup."""
    logger = logging.getLogger("uvicorn.error")
    try:
        from app.core.hybrid_config import get_hybrid_config

        config = get_hybrid_config()
        path_command = shutil.which("tesseract")
        command = config.tesseract_cmd or path_command
        logger.info(
            "OCR startup: binary_in_path=%s custom_command_configured=%s "
            "ocr_enabled=%s hybrid_engine_enabled=%s hybrid_verification_enabled=%s",
            bool(path_command), bool(config.tesseract_cmd),
            bool(settings.enable_ocr and config.enable_ocr),
            bool(settings.hybrid_engine_enabled),
            bool(settings.enable_hybrid_verification and config.enable_hybrid_verification),
        )
        if not command:
            logger.info("OCR startup: runtime_ready=false missing=tesseract version=unavailable languages=unavailable")
            return
        version_status, output = _probe(command, "--version")
        # Emit only a parsed numeric version; never emit raw output or stderr.
        match = re.match(r"tesseract\s+(\d+(?:\.\d+){1,3})(?:\s|$)", output)
        version = match.group(1) if match else "unknown"
        language_status, output = _probe(command, "--list-langs")
        languages = sorted({line.strip() for line in output.splitlines()[1:]
                            if re.fullmatch(r"[a-z][a-z0-9_]{1,19}", line.strip())})[:128]
        missing = sorted({"heb", "eng"} - set(languages))
        ready = version_status == language_status == "ok" and bool(match) and not missing
        logger.info(
            "OCR startup: version=%s version_probe=%s languages=%s language_probe=%s "
            "missing_required_languages=%s runtime_ready=%s",
            version, version_status, ",".join(languages) or "none", language_status,
            ",".join(missing) or "none", ready,
        )
    except Exception:
        logger.warning("OCR startup: diagnostic_unavailable")
