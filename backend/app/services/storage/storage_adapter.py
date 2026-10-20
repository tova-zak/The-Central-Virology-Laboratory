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
import os
import json


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
        from datetime import datetime
        
        # Add metadata
        if "saved_at" not in batch_data:
            batch_data["saved_at"] = datetime.utcnow().isoformat()
        
        # Upsert to batches table
        result = self.client.table("batches").upsert({
            "batch_id": batch_id,
            "batch_data": batch_data,
            "updated_at": datetime.utcnow().isoformat()
        }).execute()
        
        if not result.data:
            raise RuntimeError(f"Failed to save batch {batch_id} to Supabase")
    
    def load_batch(self, batch_id: str) -> Optional[Dict[str, Any]]:
        """Load batch data from Supabase Postgres."""
        result = self.client.table("batches").select("batch_data").eq("batch_id", batch_id).execute()
        
        if not result.data:
            return None
        
        return result.data[0]["batch_data"]
    
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
        
        Returns: Public URL or path to the uploaded file.
        """
        file_path = f"{batch_id}/{file_name}"
        
        result = self.client.storage.from_(self.bucket_name).upload(
            path=file_path,
            file=file_bytes,
            file_options={"content-type": "application/octet-stream"}
        )
        
        return file_path
    
    def download_file(self, batch_id: str, file_name: str) -> bytes:
        """Download file from Supabase Storage bucket."""
        file_path = f"{batch_id}/{file_name}"
        
        result = self.client.storage.from_(self.bucket_name).download(file_path)
        
        return result


def get_storage_backend() -> StorageBackend:
    """Get appropriate storage backend based on environment.
    
    Returns:
        SupabaseStorageAdapter if SUPABASE_URL set (cloud/production)
        JSONStorage otherwise (local dev/test)
    """
    from app.core.config import settings
    
    if settings.supabase_url:
        # Cloud mode: use Supabase
        return SupabaseStorageAdapter()
    else:
        # Local mode: use JSON files
        from app.services.storage.json_storage import JSONStorage
        return JSONStorage(base_path=Path(settings.temp_storage_path))
