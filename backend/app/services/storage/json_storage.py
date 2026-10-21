"""Simple JSON file-based storage for MVP.

Integration Package 3: Persistence
- Survives server restarts
- Works locally and on Render free tier
- No database dependency
- Files stored in temp_storage_path/batches/
"""
import json
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime


class JSONStorage:
    """File-based JSON storage for batch data."""
    
    def __init__(self, base_path: Path):
        """Initialize storage.
        
        Args:
            base_path: Base directory for storage files
        """
        self.base_path = Path(base_path)
        self.batches_dir = self.base_path / "batches"
        self.batches_dir.mkdir(parents=True, exist_ok=True)
    
    def save_batch(self, batch_id: str, batch_data: Dict[str, Any]) -> None:
        """Save batch data to JSON file.
        
        Args:
            batch_id: Batch identifier
            batch_data: Batch data dictionary
        """
        batch_file = self.batches_dir / f"{batch_id}.json"
        
        # Add metadata
        if "saved_at" not in batch_data:
            batch_data["saved_at"] = datetime.utcnow().isoformat()
        
        # Write atomically (write to temp, then rename)
        temp_file = batch_file.with_suffix('.tmp')
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(batch_data, f, ensure_ascii=False, indent=2)
        
        # Atomic rename
        temp_file.replace(batch_file)

    def upload_file(self, batch_id: str, file_name: str, file_bytes: bytes) -> str:
        from .storage_adapter import validate_storage_name
        validate_storage_name(batch_id)
        validate_storage_name(file_name)
        directory = self.base_path / batch_id
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / file_name
        with target.open("xb") as handle:
            handle.write(file_bytes)
        return f"{batch_id}/{file_name}"

    def download_file(self, batch_id: str, file_name: str) -> bytes:
        from .storage_adapter import validate_storage_name
        validate_storage_name(batch_id)
        validate_storage_name(file_name)
        return (self.base_path / batch_id / file_name).read_bytes()

    def check_ready(self):
        if not self.batches_dir.is_dir():
            raise RuntimeError("Local storage unavailable")
    
    def load_batch(self, batch_id: str) -> Optional[Dict[str, Any]]:
        """Load batch data from JSON file.
        
        Args:
            batch_id: Batch identifier
            
        Returns:
            Batch data dictionary or None if not found
        """
        batch_file = self.batches_dir / f"{batch_id}.json"
        
        if not batch_file.exists():
            return None
        
        try:
            with open(batch_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading batch {batch_id}: {e}")
            return None
    
    def batch_exists(self, batch_id: str) -> bool:
        """Check if batch exists in storage.
        
        Args:
            batch_id: Batch identifier
            
        Returns:
            True if batch exists
        """
        batch_file = self.batches_dir / f"{batch_id}.json"
        return batch_file.exists()
    
    def list_batches(self) -> list[str]:
        """List all batch IDs in storage.
        
        Returns:
            List of batch IDs
        """
        return [f.stem for f in self.batches_dir.glob("*.json")]
    
    def iter_batch_rows(self, chunk_size: int = 50):
        """Read-only: yield (batch_id, created_at, batch_data) newest first (local dev storage)."""
        rows = []
        for batch_file in self.batches_dir.glob("*.json"):
            data = self.load_batch(batch_file.stem)
            if isinstance(data, dict):
                rows.append((batch_file.stem, str(data.get("saved_at") or ""), data))
        rows.sort(key=lambda r: (r[1], r[0]), reverse=True)
        yield from rows

    def delete_batch(self, batch_id: str) -> bool:
        """Delete batch data.
        
        Args:
            batch_id: Batch identifier
            
        Returns:
            True if deleted, False if not found
        """
        batch_file = self.batches_dir / f"{batch_id}.json"
        
        if batch_file.exists():
            batch_file.unlink()
            return True
        
        return False
