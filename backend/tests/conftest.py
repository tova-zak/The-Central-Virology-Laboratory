"""Shared offline-test isolation.

Some e2e modules (e.g. e2e_batch_processing_test.py) call load_dotenv() on the developer's
root .env at collection time, which can inject API_*/SUPABASE_* values into the process
before app settings are built. That turns the local-mode access guard on (and points storage at a
hosted backend) so unrelated API tests fail with 401 depending on collection order. Tests that
exercise the guard or hosted modes set their own values explicitly, so every test starts from the
credential-free local default.
"""
import pytest


@pytest.fixture(autouse=True)
def _local_mode_without_env_credentials(monkeypatch):
    from app.core import access
    for name in ("api_username", "api_password", "supabase_url", "supabase_service_key"):
        monkeypatch.setattr(access.settings, name, "")
