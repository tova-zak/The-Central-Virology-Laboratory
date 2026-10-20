"""Storage adapter for cloud persistence.

This adapter provides the same save_batch/load_batch interface as JSONStorage,
but backed by Supabase Postgres (JSONB) + Storage bucket for durability on
Render Free tier (which has ephemeral filesystem).

Architecture:
- Batch metadata and small data: Supabase Postgres JSONB column (one row per batch)
- Uploaded PDF/image files: Supabase Storage private bucket
- Local JSON: Retained for dev/test mode (when SUPABASE_URL not set)

Usage:
    # Same interface as JSONStorage
    storage = get_storage_backend()  # Returns SupabaseAdapter or JSONStorage
    storage.save_batch(batch_id, batch_data)
    batch_data = storage.load_batch(batch_id)
"""
from pathlib import Path
from typing import Dict, Any, Optional, Protocol
from datetime import datetime, timezone
import re


class StorageConflict(RuntimeError):
    """A concurrent writer changed this batch; reload before retrying."""


def validate_storage_name(value: str):
    if not re.fullmatch(r"[A-Za-z0-9_-]+(?:\.[A-Za-z0-9]+)?", value):
        raise ValueError("Invalid storage identifier")


class StorageBackend(Protocol):
    """Storage backend interface (duck typing)."""
    
    def save_batch(self, batch_id: str, batch_data: Dict[str, Any]) -> None:
        """Save batch data."""
        ...
    
    def load_batch(self, batch_id: str) -> Optional[Dict[str, Any]]:
        """Load batch data."""
        ...
    
    def batch_exists(self, batch_id: str) -> bool:
        """Check if batch exists."""
        ...
    
    def list_batches(self) -> list[str]:
        """List all batch IDs."""
        ...
    
    def delete_batch(self, batch_id: str) -> bool:
        """Delete batch."""
        ...

    def upload_file(self, batch_id: str, file_name: str, file_bytes: bytes) -> str:
        ...

    def download_file(self, batch_id: str, file_name: str) -> bytes:
        ...

    def check_ready(self) -> None:
        ...


class SupabaseStorageAdapter:
    """Supabase-backed storage adapter for cloud persistence.
    
    Requires environment variables:
        SUPABASE_URL: Supabase project URL
        SUPABASE_SERVICE_KEY: Service role key (server-side only, never exposed)
        SUPABASE_BUCKET_NAME: Private storage bucket name (default: virology-lab-uploads)
    
    Database schema (must be created manually):
        CREATE TABLE batches (
            batch_id TEXT PRIMARY KEY,
            batch_data JSONB NOT NULL,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );
        
        CREATE INDEX idx_batches_created ON batches(created_at DESC);
    """
    
    def __init__(self):
        """Initialize Supabase connection."""
        # Load from app config (pydantic-settings reads .env)
        from app.core.config import settings
        
        self.supabase_url = settings.supabase_url
        self.supabase_key = settings.supabase_service_key
        self.bucket_name = settings.supabase_bucket_name
        
        if not self.supabase_url or not self.supabase_key:
            raise ValueError(
                "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set for SupabaseStorageAdapter. "
                "For local dev, unset these to use JSONStorage."
            )
        
        # Lazy import to avoid dependency in local dev
        try:
            from supabase import create_client, Client
            self.client: Client = create_client(self.supabase_url, self.supabase_key)
        except ImportError:
            raise ImportError(
                "supabase-py not installed. Run: pip install supabase"
            )
    
    def save_batch(self, batch_id: str, batch_data: Dict[str, Any]) -> None:
        """Save batch data to Supabase Postgres JSONB."""
        validate_storage_name(batch_id)
        version = batch_data.get("_storage_version")
        now = datetime.now(timezone.utc).isoformat()
        payload = {k: v for k, v in batch_data.items() if k != "_storage_version"}
        payload.setdefault("saved_at", now)
        row = {
            "batch_id": batch_id,
            "batch_data": payload,
            "updated_at": now,
        }
        table = self.client.table("batches")
        # Never upsert stale data over human corrections.
        if version is None:
            result = table.insert(row).execute()
        else:
            result = table.update(row).eq("batch_id", batch_id).eq("updated_at", version).execute()
        if not result.data:
            raise StorageConflict("Batch changed during save; reload and retry")
        batch_data["_storage_version"] = result.data[0]["updated_at"]
    
    def load_batch(self, batch_id: str) -> Optional[Dict[str, Any]]:
        """Load batch data from Supabase Postgres."""
        validate_storage_name(batch_id)
        result = self.client.table("batches").select("batch_data,updated_at").eq("batch_id", batch_id).execute()
        
        if not result.data:
            return None
        
        return {**result.data[0]["batch_data"], "_storage_version": result.data[0]["updated_at"]}
    
    def batch_exists(self, batch_id: str) -> bool:
        """Check if batch exists in Supabase."""
        result = self.client.table("batches").select("batch_id").eq("batch_id", batch_id).execute()
        return bool(result.data)
    
    def list_batches(self) -> list[str]:
        """List all batch IDs in Supabase."""
        result = self.client.table("batches").select("batch_id").execute()
        return [row["batch_id"] for row in result.data]
    
    def delete_batch(self, batch_id: str) -> bool:
        """Delete batch from Supabase."""
        result = self.client.table("batches").delete().eq("batch_id", batch_id).execute()
        return bool(result.data)
    
    def upload_file(self, batch_id: str, file_name: str, file_bytes: bytes) -> str:
        """Upload file to Supabase Storage bucket.
        
        Returns: Private object path; never a public URL.
        """
        validate_storage_name(batch_id)
        validate_storage_name(file_name)
        file_path = f"{batch_id}/{file_name}"
        
        result = self.client.storage.from_(self.bucket_name).upload(
            path=file_path,
            file=file_bytes,
            file_options={"content-type": "application/octet-stream"}
        )
        if not result:
            raise RuntimeError("Original document upload failed")
        
        return file_path
    
    def download_file(self, batch_id: str, file_name: str) -> bytes:
        """Download file from Supabase Storage bucket."""
        validate_storage_name(batch_id)
        validate_storage_name(file_name)
        file_path = f"{batch_id}/{file_name}"
        
        result = self.client.storage.from_(self.bucket_name).download(file_path)
        if not isinstance(result, bytes) or not result:
            raise RuntimeError("Original document download failed")
        return result

    def check_ready(self):
        """Read-only schema access and private-bucket check; no patient rows read."""
        self.client.table("batches").select("batch_id,batch_data,updated_at").limit(0).execute()
        bucket = self.client.storage.get_bucket(self.bucket_name)
        public = bucket.get("public") if isinstance(bucket, dict) else getattr(bucket, "public", None)
        if public is not False:
            raise RuntimeError("Configured Supabase bucket must be private")


def get_storage_backend() -> StorageBackend:
    """Get appropriate storage backend based on environment.
    
    Returns:
        SupabaseStorageAdapter if SUPABASE_URL set (cloud/production)
        JSONStorage otherwise (local dev/test)
    """
    from app.core.config import settings
    settings.validate_deployment()
    if settings.deployment_mode == "cloud" and not (settings.supabase_url and settings.supabase_service_key):
        raise ValueError("Cloud mode requires SUPABASE_URL and SUPABASE_SERVICE_KEY")
    if bool(settings.supabase_url) != bool(settings.supabase_service_key):
        raise ValueError("Set both SUPABASE_URL and SUPABASE_SERVICE_KEY")
    if settings.supabase_url:
        # Cloud mode: use Supabase
        return SupabaseStorageAdapter()
    else:
        # Local mode: use JSON files
        from app.services.storage.json_storage import JSONStorage
        return JSONStorage(base_path=Path(settings.temp_storage_path))
