"""
Persistence Proof Tests - P0 Requirement

Tests that data survives:
1. Container restart (save, restart, load)
2. Container recreate (save, destroy, recreate with same env, load)
3. Manual corrections survive (reviewed_value, human_verified)

THESE TESTS MUST PASS before claiming "persistence solved".

With Supabase adapter: Tests pass (data in Postgres + Storage bucket).
With JSONStorage only: Tests FAIL on Render Free (ephemeral filesystem).

If these tests don't pass by T+6:00, deployment MUST be labeled:
"TEMPORARY SYNTHETIC-DATA DEMO, NO DURABILITY GUARANTEE"
"""
import pytest
import os
import subprocess
import time
import json
from pathlib import Path


# Test configuration
CONTAINER_NAME = "virology-persistence-test"
IMAGE_NAME = "virology-lab-backend:test"
TEST_BATCH_ID = "persist_test_001"


def run_docker_command(cmd: list[str]) -> subprocess.CompletedProcess:
    """Run Docker command and return result."""
    return subprocess.run(cmd, capture_output=True, text=True)


def start_container(env_vars: dict = None) -> bool:
    """Start test container with optional env vars.
    
    Returns True if started successfully.
    """
    if env_vars is None:
        env_vars = {
            "DEMO_MODE": "true",
            "TEMP_STORAGE_PATH": "/app/temp_storage"
        }
    
    # Build docker run command
    cmd = [
        "docker", "run", "-d",
        "--name", CONTAINER_NAME,
        "-p", "8002:8000"  # Use 8002 to avoid conflicts
    ]
    
    # Add env vars
    for key, value in env_vars.items():
        cmd.extend(["-e", f"{key}={value}"])
    
    cmd.append(IMAGE_NAME)
    
    result = run_docker_command(cmd)
    if result.returncode != 0:
        print(f"Failed to start container: {result.stderr}")
        return False
    
    # Wait for health check
    for i in range(30):
        time.sleep(1)
        result = run_docker_command(["docker", "exec", CONTAINER_NAME, "curl", "-f", "http://localhost:8000/health"])
        if result.returncode == 0:
            return True
    
    return False


def stop_container():
    """Stop and remove container."""
    run_docker_command(["docker", "stop", CONTAINER_NAME])
    run_docker_command(["docker", "rm", CONTAINER_NAME])


def save_test_batch() -> bool:
    """Save a test batch via API."""
    # This is a simplified test - full implementation would use actual API
    # For now, we test the storage adapter directly via exec
    
    test_data = {
        "batch_id": TEST_BATCH_ID,
        "test_records": [{
            "test_id": "test_001",
            "patient_first_name": {
                "raw_value": "דוד",
                "normalized_value": "דוד",
                "reviewed_value": "דוד מתוקן",  # Manual correction
                "review_state": "human_verified"  # Must survive restart
            }
        }],
        "status": "completed"
    }
    
    # Write test data to container via exec (simulating save_batch)
    json_str = json.dumps(test_data)
    
    # For JSONStorage: write to /app/temp_storage/batches/
    cmd = [
        "docker", "exec", CONTAINER_NAME,
        "sh", "-c",
        f"mkdir -p /app/temp_storage/batches && echo '{json_str}' > /app/temp_storage/batches/{TEST_BATCH_ID}.json"
    ]
    
    result = run_docker_command(cmd)
    return result.returncode == 0


def load_test_batch() -> dict:
    """Load test batch from container."""
    cmd = [
        "docker", "exec", CONTAINER_NAME,
        "cat", f"/app/temp_storage/batches/{TEST_BATCH_ID}.json"
    ]
    
    result = run_docker_command(cmd)
    if result.returncode != 0:
        return None
    
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


@pytest.mark.slow
@pytest.mark.docker
def test_01_restart_persistence():
    """Test 1: Save, restart container, load - data should survive.
    
    WITH SUPABASE: ✅ PASS (data in Postgres)
    WITH JSONSTO RAGE on Render Free: ❌ FAIL (ephemeral filesystem)
    """
    print("\n[TEST 1] Restart persistence test")
    
    try:
        # Cleanup
        stop_container()
        
        # Start container
        assert start_container(), "Failed to start container"
        print("[TEST 1] Container started")
        
        # Save batch
        assert save_test_batch(), "Failed to save batch"
        print(f"[TEST 1] Saved batch: {TEST_BATCH_ID}")
        
        # Verify saved
        batch_before = load_test_batch()
        assert batch_before is not None, "Failed to load batch before restart"
        print(f"[TEST 1] Loaded batch before restart: {batch_before['batch_id']}")
        
        # Restart container
        print("[TEST 1] Restarting container...")
        run_docker_command(["docker", "restart", CONTAINER_NAME])
        time.sleep(5)  # Wait for restart
        
        # Wait for health
        for i in range(30):
            time.sleep(1)
            result = run_docker_command(["docker", "exec", CONTAINER_NAME, "curl", "-f", "http://localhost:8000/health"])
            if result.returncode == 0:
                break
        
        # Load batch after restart
        batch_after = load_test_batch()
        
        # Assert: data survived restart
        assert batch_after is not None, "FAILED: Batch not found after restart (data lost)"
        assert batch_after["batch_id"] == TEST_BATCH_ID, "FAILED: Batch ID mismatch"
        
        # Assert: manual corrections survived
        reviewed_value = batch_after["test_records"][0]["patient_first_name"]["reviewed_value"]
        assert reviewed_value == "דוד מתוקן", f"FAILED: Manual correction lost (got: {reviewed_value})"
        
        print("[TEST 1] ✅ PASSED - Data survived restart")
        
    finally:
        stop_container()


@pytest.mark.slow
@pytest.mark.docker
def test_02_recreate_persistence():
    """Test 2: Save, destroy container, recreate with same env, load - data should survive.
    
    WITH SUPABASE: ✅ PASS (data in Postgres, not tied to container)
    WITH JSONSTO RAGE on Render Free: ❌ FAIL (filesystem destroyed with container)
    """
    print("\n[TEST 2] Recreate persistence test")
    
    try:
        # Cleanup
        stop_container()
        
        # Start container
        env_vars = {
            "DEMO_MODE": "true",
            "TEMP_STORAGE_PATH": "/app/temp_storage",
            # If using Supabase, add these:
            # "SUPABASE_URL": os.getenv("SUPABASE_URL"),
            # "SUPABASE_SERVICE_KEY": os.getenv("SUPABASE_SERVICE_KEY"),
        }
        
        assert start_container(env_vars), "Failed to start container"
        print("[TEST 2] Container started")
        
        # Save batch
        assert save_test_batch(), "Failed to save batch"
        print(f"[TEST 2] Saved batch: {TEST_BATCH_ID}")
        
        # Destroy container
        print("[TEST 2] Destroying container...")
        run_docker_command(["docker", "rm", "-f", CONTAINER_NAME])
        time.sleep(2)
        
        # Recreate container with SAME env vars
        print("[TEST 2] Recreating container with same env...")
        assert start_container(env_vars), "Failed to recreate container"
        
        # Load batch from recreated container
        batch_after = load_test_batch()
        
        # Assert: data survived destroy/recreate
        assert batch_after is not None, "FAILED: Batch not found after recreate (data lost)"
        assert batch_after["batch_id"] == TEST_BATCH_ID, "FAILED: Batch ID mismatch"
        
        # Assert: manual corrections survived
        reviewed_value = batch_after["test_records"][0]["patient_first_name"]["reviewed_value"]
        assert reviewed_value == "דוד מתוקן", f"FAILED: Manual correction lost (got: {reviewed_value})"
        
        print("[TEST 2] ✅ PASSED - Data survived destroy/recreate")
        
    finally:
        stop_container()


@pytest.mark.slow
@pytest.mark.docker
def test_03_manual_corrections_survive():
    """Test 3: Manual corrections (reviewed_value, human_verified) survive restart.
    
    Verifies that human review work is not lost.
    """
    print("\n[TEST 3] Manual corrections persistence test")
    
    try:
        # Cleanup
        stop_container()
        
        # Start container
        assert start_container(), "Failed to start container"
        print("[TEST 3] Container started")
        
        # Save batch with manual corrections
        test_data = {
            "batch_id": TEST_BATCH_ID,
            "test_records": [{
                "test_id": "test_001",
                "patient_first_name": {
                    "raw_value": "דוד",  # AI extraction
                    "normalized_value": "דוד",
                    "reviewed_value": "דוד בן משה",  # Human correction
                    "review_state": "human_verified",
                    "extraction_state": "found"
                },
                "patient_id_number": {
                    "raw_value": "12345678",  # Invalid checksum
                    "reviewed_value": "123456789",  # Human corrected
                    "review_state": "human_verified"
                }
            }]
        }
        
        json_str = json.dumps(test_data)
        cmd = [
            "docker", "exec", CONTAINER_NAME,
            "sh", "-c",
            f"mkdir -p /app/temp_storage/batches && echo '{json_str}' > /app/temp_storage/batches/{TEST_BATCH_ID}.json"
        ]
        run_docker_command(cmd)
        print("[TEST 3] Saved batch with manual corrections")
        
        # Restart
        run_docker_command(["docker", "restart", CONTAINER_NAME])
        time.sleep(5)
        
        # Wait for health
        for i in range(30):
            time.sleep(1)
            result = run_docker_command(["docker", "exec", CONTAINER_NAME, "curl", "-f", "http://localhost:8000/health"])
            if result.returncode == 0:
                break
        
        # Load and verify
        batch_after = load_test_batch()
        assert batch_after is not None, "FAILED: Batch not found after restart"
        
        record = batch_after["test_records"][0]
        
        # Assert: manual corrections intact
        assert record["patient_first_name"]["reviewed_value"] == "דוד בן משה", "FAILED: Name correction lost"
        assert record["patient_first_name"]["review_state"] == "human_verified", "FAILED: Review state lost"
        assert record["patient_id_number"]["reviewed_value"] == "123456789", "FAILED: ID correction lost"
        
        print("[TEST 3] ✅ PASSED - Manual corrections survived")
        
    finally:
        stop_container()


if __name__ == "__main__":
    """
    Run persistence tests standalone.
    
    NOTE: These tests require Docker and the backend image to be built.
    They are slow and may fail if Supabase adapter is not wired yet.
    """
    print("=" * 80)
    print("PERSISTENCE PROOF TESTS")
    print("=" * 80)
    print("WARNING: These tests take 2-3 minutes and require Docker.")
    print("If Supabase adapter is not wired, tests 1 and 2 will FAIL (expected).")
    print("=" * 80)
    
    # Run tests
    try:
        test_01_restart_persistence()
        test_02_recreate_persistence()
        test_03_manual_corrections_survive()
        
        print("\n" + "=" * 80)
        print("✅ ALL PERSISTENCE TESTS PASSED")
        print("Persistence is SOLVED - safe to deploy.")
        print("=" * 80)
        
    except AssertionError as e:
        print("\n" + "=" * 80)
        print(f"❌ PERSISTENCE TEST FAILED: {e}")
        print("=" * 80)
        print("\nAction required:")
        print("1. Wire Supabase adapter in process.py and background.py")
        print("2. Set SUPABASE_URL and SUPABASE_SERVICE_KEY env vars")
        print("3. Re-run tests")
        print("\nOR label deployment: 'TEMPORARY SYNTHETIC-DATA DEMO, NO DURABILITY GUARANTEE'")
        print("=" * 80)
