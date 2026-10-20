"""Storage Adapter Persistence Tests

Tests for both JSONStorage and SupabaseStorageAdapter to verify:
- save_batch/load_batch cycle
- Reviewed values persist after reload
- CommitmentRecord data survives restart simulation

CRITICAL: These tests verify that manual corrections and extracted data
are NOT lost when the backend restarts or container is recreated.

NOTE: Container recreation testing requires actual Docker environment.
These tests simulate restart by creating new storage instances.
"""
import pytest
import tempfile
import json
import os
from pathlib import Path
from typing import Dict, Any


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def temp_storage_path():
    """Temporary storage directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_batch_data() -> Dict[str, Any]:
    """Sample batch data with test records and commitment records."""
    return {
        "batch_id": "batch_001",
        "status": "completed",
        "created_at": "2026-10-14T10:00:00",
        "test_records": [
            {
                "test_id": "test_001",
                "patient_first_name": {
                    "raw_value": "יוסי",
                    "reviewed_value": "יוסף",  # Manual correction
                    "extraction_state": "reviewed"
                },
                "patient_last_name": {
                    "raw_value": "כהן",
                    "reviewed_value": None,
                    "extraction_state": "extracted"
                },
                "identity_number": {
                    "raw_value": "123456789",
                    "reviewed_value": None,
                    "extraction_state": "extracted"
                }
            }
        ],
        "commitment_records": [
            {
                "commitment_record_id": "comm_001",
                "test_id": "test_001",
                "commitment_number": {
                    "raw_value": "AUTO123",
                    "reviewed_value": "MANUAL456",  # Manual correction
                    "extraction_state": "reviewed"
                },
                "central_number": {
                    "raw_value": "987654",
                    "reviewed_value": None,
                    "extraction_state": "extracted"
                },
                "relationship_status": "verified"
            },
            {
                "commitment_record_id": "comm_002",
                "test_id": "test_001",
                "commitment_number": {
                    "raw_value": "COMM67890",
                    "reviewed_value": None,
                    "extraction_state": "extracted"
                },
                "relationship_status": "unresolved_relationship"
            }
        ]
    }


# ============================================================================
# JSONStorage Tests
# ============================================================================

def test_json_storage_save_and_load(temp_storage_path, sample_batch_data):
    """Test JSONStorage save/load cycle preserves all data."""
    from app.services.storage.json_storage import JSONStorage
    
    storage = JSONStorage(base_path=temp_storage_path)
    batch_id = sample_batch_data["batch_id"]
    
    # Save batch
    storage.save_batch(batch_id, sample_batch_data)
    
    # Verify file created (JSONStorage saves to batches/ subdirectory)
    batch_file = temp_storage_path / "batches" / f"{batch_id}.json"
    assert batch_file.exists(), f"Expected batch file at {batch_file}"
    
    # Load batch
    loaded_data = storage.load_batch(batch_id)
    
    assert loaded_data is not None
    assert loaded_data["batch_id"] == batch_id
    assert loaded_data["status"] == "completed"
    assert len(loaded_data["test_records"]) == 1
    assert len(loaded_data["commitment_records"]) == 2


def test_json_storage_reviewed_values_persist(temp_storage_path, sample_batch_data):
    """Test that manual corrections (reviewed_value) survive save/load."""
    from app.services.storage.json_storage import JSONStorage
    
    storage = JSONStorage(base_path=temp_storage_path)
    batch_id = sample_batch_data["batch_id"]
    
    # Save batch with reviewed values
    storage.save_batch(batch_id, sample_batch_data)
    
    # Simulate restart: create new storage instance
    storage_after_restart = JSONStorage(base_path=temp_storage_path)
    loaded_data = storage_after_restart.load_batch(batch_id)
    
    # Verify reviewed values preserved
    assert loaded_data["test_records"][0]["patient_first_name"]["reviewed_value"] == "יוסף"
    assert loaded_data["test_records"][0]["patient_first_name"]["extraction_state"] == "reviewed"
    
    # Verify commitment record corrections preserved
    assert loaded_data["commitment_records"][0]["commitment_number"]["reviewed_value"] == "MANUAL456"
    assert loaded_data["commitment_records"][0]["relationship_status"] == "verified"
    assert loaded_data["commitment_records"][1]["relationship_status"] == "unresolved_relationship"


def test_json_storage_commitment_records_survive_restart(temp_storage_path):
    """Test that CommitmentRecords with multiple fields persist correctly."""
    from app.services.storage.json_storage import JSONStorage
    
    storage = JSONStorage(base_path=temp_storage_path)
    batch_id = "batch_multi_commitment"
    
    # Create batch with 3 commitments from same form
    batch_data = {
        "batch_id": batch_id,
        "status": "completed",
        "commitment_records": [
            {
                "commitment_record_id": f"comm_00{i}",
                "test_id": "test_001",
                "commitment_number": {
                    "raw_value": f"COMM{i}",
                    "reviewed_value": None,
                    "extraction_state": "extracted"
                },
                "central_number": {
                    "raw_value": "999888",
                    "reviewed_value": None,
                    "extraction_state": "extracted"
                },
                "relationship_status": "verified"
            }
            for i in range(1, 4)
        ]
    }
    
    storage.save_batch(batch_id, batch_data)
    
    # Simulate restart
    storage_restarted = JSONStorage(base_path=temp_storage_path)
    loaded = storage_restarted.load_batch(batch_id)
    
    assert len(loaded["commitment_records"]) == 3
    assert loaded["commitment_records"][0]["commitment_number"]["raw_value"] == "COMM1"
    assert loaded["commitment_records"][1]["commitment_number"]["raw_value"] == "COMM2"
    assert loaded["commitment_records"][2]["commitment_number"]["raw_value"] == "COMM3"


def test_json_storage_batch_exists(temp_storage_path, sample_batch_data):
    """Test batch_exists method."""
    from app.services.storage.json_storage import JSONStorage
    
    storage = JSONStorage(base_path=temp_storage_path)
    batch_id = sample_batch_data["batch_id"]
    
    # Before save
    assert not storage.batch_exists(batch_id)
    
    # After save
    storage.save_batch(batch_id, sample_batch_data)
    assert storage.batch_exists(batch_id)


def test_json_storage_list_batches(temp_storage_path):
    """Test listing all batches."""
    from app.services.storage.json_storage import JSONStorage
    
    storage = JSONStorage(base_path=temp_storage_path)
    
    # Save multiple batches
    for i in range(1, 4):
        batch_id = f"batch_00{i}"
        storage.save_batch(batch_id, {"batch_id": batch_id, "status": "completed"})
    
    batches = storage.list_batches()
    assert len(batches) == 3
    assert "batch_001" in batches
    assert "batch_002" in batches
    assert "batch_003" in batches


def test_json_storage_delete_batch(temp_storage_path, sample_batch_data):
    """Test deleting a batch."""
    from app.services.storage.json_storage import JSONStorage
    
    storage = JSONStorage(base_path=temp_storage_path)
    batch_id = sample_batch_data["batch_id"]
    
    # Save and verify exists
    storage.save_batch(batch_id, sample_batch_data)
    assert storage.batch_exists(batch_id)
    
    # Delete
    result = storage.delete_batch(batch_id)
    assert result is True
    assert not storage.batch_exists(batch_id)
    
    # Delete non-existent
    result = storage.delete_batch("nonexistent")
    assert result is False


# ============================================================================
# SupabaseStorageAdapter Tests
# ============================================================================

def test_supabase_adapter_requires_env_vars():
    """Test that SupabaseStorageAdapter raises clear error when env vars missing."""
    from app.services.storage.storage_adapter import SupabaseStorageAdapter
    
    # Temporarily unset env vars
    original_url = os.environ.get("SUPABASE_URL")
    original_key = os.environ.get("SUPABASE_SERVICE_KEY")
    
    try:
        if "SUPABASE_URL" in os.environ:
            del os.environ["SUPABASE_URL"]
        if "SUPABASE_SERVICE_KEY" in os.environ:
            del os.environ["SUPABASE_SERVICE_KEY"]
        
        with pytest.raises(ValueError) as exc_info:
            SupabaseStorageAdapter()
        
        assert "SUPABASE_URL" in str(exc_info.value)
        assert "SUPABASE_SERVICE_KEY" in str(exc_info.value)
        
    finally:
        # Restore original env vars
        if original_url:
            os.environ["SUPABASE_URL"] = original_url
        if original_key:
            os.environ["SUPABASE_SERVICE_KEY"] = original_key


def test_get_storage_backend_returns_json_storage_by_default(temp_storage_path):
    """Test that get_storage_backend returns JSONStorage when no Supabase env."""
    from app.services.storage.storage_adapter import get_storage_backend
    from app.services.storage.json_storage import JSONStorage
    
    # Ensure SUPABASE_URL not set
    original_url = os.environ.get("SUPABASE_URL")
    try:
        if "SUPABASE_URL" in os.environ:
            del os.environ["SUPABASE_URL"]
        
        storage = get_storage_backend()
        
        # Should return JSONStorage instance
        assert isinstance(storage, JSONStorage)
        
    finally:
        if original_url:
            os.environ["SUPABASE_URL"] = original_url


@pytest.mark.skipif(
    not (os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SERVICE_KEY")),
    reason="Supabase live tests require SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables"
)
def test_supabase_adapter_save_and_load():
    """Test SupabaseStorageAdapter save/load cycle (LIVE TEST - SKIPPED WITHOUT ENV).
    
    To run this test:
    1. Set up Supabase project
    2. Create batches table:
        CREATE TABLE batches (
            batch_id TEXT PRIMARY KEY,
            batch_data JSONB NOT NULL,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );
    3. Set environment variables:
        - SUPABASE_URL
        - SUPABASE_SERVICE_KEY
        - SUPABASE_BUCKET_NAME
    """
    from app.services.storage.storage_adapter import SupabaseStorageAdapter
    
    storage = SupabaseStorageAdapter()
    
    batch_id = "test_supabase_batch"
    batch_data = {
        "batch_id": batch_id,
        "status": "completed",
        "test_records": []
    }
    
    # Save
    storage.save_batch(batch_id, batch_data)
    
    # Load
    loaded = storage.load_batch(batch_id)
    assert loaded is not None
    assert loaded["batch_id"] == batch_id
    
    # Cleanup
    storage.delete_batch(batch_id)


# ============================================================================
# Integration Test: Persistence After Simulated Restart
# ============================================================================

def test_persistence_after_simulated_restart(temp_storage_path):
    """Full integration test: save → restart → load → verify all data intact.
    
    This simulates what happens when:
    1. User uploads PDF and extracts fields
    2. User reviews and corrects some values
    3. Backend saves to storage
    4. Backend restarts (new process/container)
    5. User refreshes browser and expects to see their corrections
    
    VALIDATES:
    - No data loss during restart
    - Manual corrections (reviewed_value) preserved
    - CommitmentRecord relationship_status preserved
    - Extraction state flags preserved
    """
    from app.services.storage.json_storage import JSONStorage
    
    # Phase 1: Initial processing and review
    storage_session_1 = JSONStorage(base_path=temp_storage_path)
    
    batch_id = "batch_restart_test"
    original_data = {
        "batch_id": batch_id,
        "status": "in_review",
        "test_records": [
            {
                "test_id": "test_001",
                "patient_first_name": {
                    "raw_value": "דויד",
                    "reviewed_value": "דוד",  # User corrected spelling
                    "extraction_state": "reviewed",
                    "confidence": 0.95
                }
            }
        ],
        "commitment_records": [
            {
                "commitment_record_id": "comm_001",
                "test_id": "test_001",
                "commitment_number": {
                    "raw_value": "AUTO123",
                    "reviewed_value": "MANUAL456",  # User corrected
                    "extraction_state": "reviewed"
                },
                "relationship_status": "verified"  # User verified mapping
            }
        ]
    }
    
    storage_session_1.save_batch(batch_id, original_data)
    
    # Phase 2: Simulate restart - new storage instance (new process)
    storage_session_2 = JSONStorage(base_path=temp_storage_path)
    
    # Phase 3: Load data after "restart"
    loaded_data = storage_session_2.load_batch(batch_id)
    
    # Phase 4: Verify ALL data intact
    assert loaded_data is not None, "Batch should exist after restart"
    assert loaded_data["batch_id"] == batch_id
    assert loaded_data["status"] == "in_review"
    
    # Verify test record corrections preserved
    test_record = loaded_data["test_records"][0]
    assert test_record["patient_first_name"]["raw_value"] == "דויד"
    assert test_record["patient_first_name"]["reviewed_value"] == "דוד", \
        "User's manual correction MUST survive restart"
    assert test_record["patient_first_name"]["extraction_state"] == "reviewed"
    assert test_record["patient_first_name"]["confidence"] == 0.95
    
    # Verify commitment record corrections preserved
    commitment = loaded_data["commitment_records"][0]
    assert commitment["commitment_number"]["raw_value"] == "AUTO123"
    assert commitment["commitment_number"]["reviewed_value"] == "MANUAL456", \
        "User's commitment number correction MUST survive restart"
    assert commitment["commitment_number"]["extraction_state"] == "reviewed"
    assert commitment["relationship_status"] == "verified", \
        "User's relationship verification MUST survive restart"


# ============================================================================
# Container Recreation Test (Requires Docker)
# ============================================================================

def test_container_recreation_documentation():
    """Document how to test container recreation in Docker.
    
    Container recreation testing CANNOT be fully automated in pytest because
    it requires actually stopping and starting Docker containers.
    
    To test container recreation manually:
    
    1. Build Docker image:
        cd backend
        docker build -t virology-lab-test .
    
    2. Start container with volume mount:
        docker run -d --name virology-test \
            -v $(pwd)/test_storage:/app/temp_storage \
            -p 8000:8000 \
            -e DEMO_MODE=true \
            virology-lab-test
    
    3. Process a batch and verify data saved:
        curl -X POST http://localhost:8000/api/batches -F "files=@test.pdf"
        # Get batch_id from response
        curl http://localhost:8000/api/batches/{batch_id}
    
    4. Stop and REMOVE container:
        docker stop virology-test
        docker rm virology-test
    
    5. Start NEW container with SAME volume:
        docker run -d --name virology-test-2 \
            -v $(pwd)/test_storage:/app/temp_storage \
            -p 8000:8000 \
            -e DEMO_MODE=true \
            virology-lab-test
    
    6. Verify data still exists:
        curl http://localhost:8000/api/batches/{batch_id}
        # Should return the same batch data
    
    Expected result: Data persists across container recreation because
    temp_storage is mounted as a volume (not ephemeral container filesystem).
    
    NOTE: On Render Free tier, storage is EPHEMERAL and data is lost on
    redeploy. This test works locally but NOT on Render without Supabase.
    """
    pass  # Documentation only


# ============================================================================
# SUMMARY
# ============================================================================

"""
Storage Adapter Test Summary
=============================

IMPLEMENTED (10 tests):
✅ test_json_storage_save_and_load - Basic save/load cycle
✅ test_json_storage_reviewed_values_persist - Manual corrections survive restart
✅ test_json_storage_commitment_records_survive_restart - Multiple commitments preserved
✅ test_json_storage_batch_exists - Existence check
✅ test_json_storage_list_batches - List all batches
✅ test_json_storage_delete_batch - Delete batch
✅ test_supabase_adapter_requires_env_vars - Supabase config validation
✅ test_get_storage_backend_returns_json_storage_by_default - Storage backend selection
✅ test_persistence_after_simulated_restart - Full integration test
✅ test_container_recreation_documentation - Docker testing instructions

SKIPPED (1 test - requires env vars):
⏸️ test_supabase_adapter_save_and_load - Requires SUPABASE_URL and SUPABASE_SERVICE_KEY

CRITICAL VALIDATIONS:
✅ Reviewed values (manual corrections) survive restart
✅ CommitmentRecord data preserved
✅ Relationship_status flags preserved
✅ Multiple commitments per batch handled correctly
✅ Storage backend selection works (JSON vs Supabase)

LIMITATION:
⚠️ Container recreation requires actual Docker environment (documented)
⚠️ Supabase live tests require credentials (skipped when env vars not set)
⚠️ Render Free tier has ephemeral storage - data lost on redeploy
"""
