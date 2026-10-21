"""Verified LOCAL temporary copies of stored originals (MVP workaround; NOT durable storage).

Why: remote retrieval of stored documents was observed to fail or return different bytes on this network
(altered PNG delivery, HTTP 418 for generated PDFs). The system of record stays Supabase; this spool only lets the
local MVP process and preview the exact bytes it just received.

Rules
- Location: <TEMP_STORAGE_PATH>/_verified_spool/<batch_id>/<storage_name> (private temp dir, never mounted as static files;
  reachable only through authenticated API routes that look the document up in the batch manifest).
- Names must pass validate_storage_name (no separators, no traversal) and the resolved path must stay inside the spool.
- Every local read is verified against the manifest SHA-256; a mismatch deletes the copy and falls back to the
  (separately verified) remote copy. Remote bytes are never trusted without the caller verifying the same SHA-256.
- Missing copy (server restart, retention cleanup) is NOT an error by itself: remote is tried; if that also fails the caller
  gets OriginalUnavailable with an explicit code instead of a crash.
- Retention: copies older than TEMP_STORAGE_TTL_HOURS (default 24 h, by batch-folder modification time) are deleted
  whenever a new copy is saved (cleanup_expired can also be called explicitly). Nothing is logged except ids and sizes.
"""
import hashlib
import logging
import os
import shutil
import time
from pathlib import Path
from typing import Optional

from app.core.config import settings
from app.services.storage.storage_adapter import validate_storage_name

logger = logging.getLogger(__name__)
SPOOL_DIRNAME = "_verified_spool"


class SpoolMissing(Exception):
    pass


class SpoolIntegrityError(Exception):
    pass


class OriginalUnavailable(Exception):
    """The original could not be obtained from any source (explicit, per-document, no document content)."""

    def __init__(self, code: str, message: str, diagnostics: Optional[dict] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.diagnostics = diagnostics or {}

    def as_error(self, document_id) -> dict:
        return {"document_id": document_id, "error": self.message, "error_code": self.code, "diagnostics": self.diagnostics}


class LocalSpool:
    def __init__(self, base_dir: Path):
        self.base = Path(base_dir).resolve()

    def _path(self, batch_id: str, name: str) -> Path:
        validate_storage_name(batch_id)
        validate_storage_name(name)
        path = (self.base / batch_id / name).resolve()
        if not path.is_relative_to(self.base):
            raise ValueError("Invalid storage identifier")
        return path

    def save(self, batch_id: str, name: str, content: bytes) -> None:
        path = self._path(batch_id, name)
        self.cleanup_expired(settings.temp_storage_ttl_hours)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(path.parent, 0o700)  # best effort; Windows relies on the user profile ACL of the temp directory
        except OSError:
            pass
        temporary = path.with_name(path.name + ".tmp-%d" % os.getpid())
        temporary.write_bytes(content)
        os.replace(temporary, path)

    def read_verified(self, batch_id: str, name: str, expected_sha256: str) -> bytes:
        path = self._path(batch_id, name)
        if not path.is_file():
            raise SpoolMissing()
        try:
            content = path.read_bytes()
        except OSError:
            raise SpoolMissing() from None
        if hashlib.sha256(content).hexdigest() != expected_sha256:
            try:
                path.unlink()
            except OSError:
                pass
            raise SpoolIntegrityError()
        return content

    def cleanup_expired(self, ttl_hours: float) -> int:
        if not self.base.is_dir():
            return 0
        removed, cutoff = 0, time.time() - ttl_hours * 3600
        for batch_dir in self.base.iterdir():
            try:
                if batch_dir.is_dir() and batch_dir.stat().st_mtime < cutoff:
                    shutil.rmtree(batch_dir)
                    removed += 1
            except OSError:
                logger.warning("Spool cleanup could not remove one expired batch folder")
        return removed


def get_spool() -> LocalSpool:
    return LocalSpool(Path(settings.temp_storage_path) / SPOOL_DIRNAME)


def fetch_original(storage, batch_id: str, document: dict, spool: Optional[LocalSpool] = None):
    """Return (bytes, source) where source is "local_spool" (verified here) or "remote" (caller must still verify)."""
    spool = spool or get_spool()
    expected, name = document.get("sha256"), document["storage_name"]
    spool_state = "not_applicable"
    if expected:
        try:
            return spool.read_verified(batch_id, name, expected), "local_spool"
        except SpoolMissing:
            spool_state = "missing"
        except SpoolIntegrityError:
            spool_state = "corrupt_removed"
            logger.warning("[%s] local copy of document=%s failed SHA-256 verification and was removed", batch_id, document.get("document_id"))
    try:
        return storage.download_file(batch_id, name), "remote"
    except Exception as error:
        raise OriginalUnavailable(
            "storage_unavailable",
            "Original document could not be retrieved (no verified local copy; remote storage request failed). Upload it again.",
            {"exception_type": type(error).__name__, "local_copy": spool_state}) from None
