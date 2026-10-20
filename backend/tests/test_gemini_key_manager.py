"""Tests for GeminiKeyManager - multi-key management and round-robin."""
import pytest
import os
from datetime import datetime, timezone
from unittest.mock import patch

from app.services.extraction.gemini_key_manager import GeminiKeyManager, ApiKeyInfo


class TestGeminiKeyManager:
    """Test suite for API key management."""
    
    @patch.dict(os.environ, {
        "GEMINI_API_KEY": "test-key-primary",
        "GEMINI_API_1": "test-key-1",
        "GEMINI_API_2": "test-key-2",
    }, clear=True)
    def test_load_multiple_keys(self):
        """Test loading multiple valid keys from environment."""
        manager = GeminiKeyManager()
        
        assert manager.get_total_key_count() == 3
        assert manager.get_active_key_count() == 3
        
        status = manager.get_status()
        assert len(status) == 3
        assert status[0]["key_id"] == "key_1"
        assert status[0]["env_var"] == "GEMINI_API_KEY"
        assert status[0]["is_active"] is True
    
    @patch.dict(os.environ, {
        "GEMINI_API_KEY": "test-key-primary",
        "GEMINI_API_1": "",  # Empty
        "GEMINI_API_2": "  ",  # Whitespace only
    }, clear=True)
    def test_skip_empty_keys(self):
        """Test that empty and whitespace-only keys are skipped."""
        manager = GeminiKeyManager()
        
        assert manager.get_total_key_count() == 1
        assert manager.get_active_key_count() == 1
    
    @patch.dict(os.environ, {
        "GEMINI_API_KEY": "test-key-duplicate",
        "GEMINI_API_1": "test-key-duplicate",  # Duplicate
        "GEMINI_API_2": "test-key-unique",
    }, clear=True)
    def test_detect_duplicates(self):
        """Test that duplicate keys are detected and skipped."""
        manager = GeminiKeyManager()
        
        # Only 2 unique keys should be loaded
        assert manager.get_total_key_count() == 2
        
        status = manager.get_status()
        assert status[0]["env_var"] == "GEMINI_API_KEY"
        assert status[1]["env_var"] == "GEMINI_API_2"
    
    @patch.dict(os.environ, {
        "GEMINI_API_KEY": "key-a",
        "GEMINI_API_1": "key-b",
        "GEMINI_API_2": "key-c",
    }, clear=True)
    def test_round_robin_selection(self):
        """Test round-robin key selection."""
        manager = GeminiKeyManager()
        
        # First round
        key_id_1, key_val_1 = manager.get_next_key()
        key_id_2, key_val_2 = manager.get_next_key()
        key_id_3, key_val_3 = manager.get_next_key()
        
        assert key_id_1 == "key_1"
        assert key_id_2 == "key_2"
        assert key_id_3 == "key_3"
        
        assert key_val_1 == "key-a"
        assert key_val_2 == "key-b"
        assert key_val_3 == "key-c"
        
        # Second round - should cycle back
        key_id_4, key_val_4 = manager.get_next_key()
        assert key_id_4 == "key_1"
        assert key_val_4 == "key-a"
    
    @patch.dict(os.environ, {
        "GEMINI_API_KEY": "key-a",
        "GEMINI_API_1": "key-b",
    }, clear=True)
    def test_failure_tracking(self):
        """Test that failures are tracked and keys disabled after threshold."""
        manager = GeminiKeyManager()
        
        key_id, _ = manager.get_next_key()
        assert key_id == "key_1"
        
        # Mark as failed 3 times (MAX_FAILURES_BEFORE_DISABLE = 3)
        manager.mark_key_failed("key_1", "Test error 1")
        manager.mark_key_failed("key_1", "Test error 2")
        
        # Still active after 2 failures
        assert manager.get_active_key_count() == 2
        
        manager.mark_key_failed("key_1", "Test error 3")
        
        # Now disabled
        assert manager.get_active_key_count() == 1
        
        # Next key should skip disabled key_1
        key_id_next, _ = manager.get_next_key()
        assert key_id_next == "key_2"
    
    @patch.dict(os.environ, {
        "GEMINI_API_KEY": "key-a",
        "GEMINI_API_1": "key-b",
    }, clear=True)
    def test_success_resets_failures(self):
        """Test that successful API call resets failure count."""
        manager = GeminiKeyManager()
        
        key_id, _ = manager.get_next_key()
        
        # Mark as failed twice
        manager.mark_key_failed(key_id, "Error 1")
        manager.mark_key_failed(key_id, "Error 2")
        
        status = manager.get_status()
        key_status = next(k for k in status if k["key_id"] == key_id)
        assert key_status["failure_count"] == 2
        
        # Mark as success
        manager.mark_key_success(key_id)
        
        status = manager.get_status()
        key_status = next(k for k in status if k["key_id"] == key_id)
        assert key_status["failure_count"] == 0
    
    @patch.dict(os.environ, {
        "GEMINI_API_KEY": "key-a",
    }, clear=True)
    def test_all_keys_disabled(self):
        """Test error when all keys are disabled."""
        manager = GeminiKeyManager()
        
        # Disable the only key
        for _ in range(3):
            manager.mark_key_failed("key_1", "Test error")
        
        # Should raise error
        with pytest.raises(RuntimeError, match="All API keys are disabled"):
            manager.get_next_key()
    
    @patch.dict(os.environ, {
        "GEMINI_API_KEY": "key-a",
    }, clear=True)
    def test_reactivate_key(self):
        """Test manual key reactivation."""
        manager = GeminiKeyManager()
        
        # Disable key
        for _ in range(3):
            manager.mark_key_failed("key_1", "Test error")
        
        assert manager.get_active_key_count() == 0
        
        # Reactivate
        manager.reactivate_key("key_1")
        
        assert manager.get_active_key_count() == 1
        
        status = manager.get_status()
        assert status[0]["is_active"] is True
        assert status[0]["failure_count"] == 0
    
    @patch.dict(os.environ, {}, clear=True)
    def test_no_keys_configured(self):
        """Test error when no keys are configured."""
        with pytest.raises(ValueError, match="No Gemini API keys configured"):
            GeminiKeyManager()
    
    @patch.dict(os.environ, {
        "GEMINI_API_KEY": "  key-with-spaces  ",
        "GEMINI_API_1": "	key-with-tabs	",
    }, clear=True)
    def test_strip_whitespace(self):
        """Test that leading/trailing whitespace is stripped from keys."""
        manager = GeminiKeyManager()
        
        _, key_val_1 = manager.get_next_key()
        _, key_val_2 = manager.get_next_key()
        
        assert key_val_1 == "key-with-spaces"
        assert key_val_2 == "key-with-tabs"
    
    @patch.dict(os.environ, {
        "GEMINI_API_KEY": "key-a",
        "GEMINI_API_1": "key-b",
    }, clear=True)
    def test_status_includes_last_used(self):
        """Test that status includes last_used timestamp."""
        manager = GeminiKeyManager()
        
        before = datetime.now(timezone.utc)
        key_id, _ = manager.get_next_key()
        after = datetime.now(timezone.utc)
        
        status = manager.get_status()
        key_status = next(k for k in status if k["key_id"] == key_id)
        
        assert key_status["last_used"] is not None
        # Parse ISO timestamp
        last_used = datetime.fromisoformat(key_status["last_used"].replace("Z", ""))
        assert before <= last_used <= after
    
    @patch.dict(os.environ, {
        "GEMINI_API_KEY": "key-a",
        "GEMINI_API_1": "key-b",
        "GEMINI_API_2": "key-c",
    }, clear=True)
    def test_concurrent_access_safety(self):
        """Test thread-safety of key manager (basic smoke test)."""
        import threading
        
        manager = GeminiKeyManager()
        results = []
        errors = []
        
        def get_keys():
            try:
                for _ in range(10):
                    key_id, key_val = manager.get_next_key()
                    results.append((key_id, key_val))
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=get_keys) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # No errors should occur
        assert len(errors) == 0
        
        # Should have 50 results (10 per thread × 5 threads)
        assert len(results) == 50
        
        # All results should be valid keys
        for key_id, key_val in results:
            assert key_id in ["key_1", "key_2", "key_3"]
            assert key_val in ["key-a", "key-b", "key-c"]
