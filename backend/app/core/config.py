"""Application configuration management using Pydantic Settings."""
from pathlib import Path
import os
from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# Explicit selection only: never search other worktrees or copy credential files.
ENV_FILE_PATH = Path(os.environ.get(
    "APP_ENV_FILE", str(Path(__file__).resolve().parents[3] / ".env")
)).expanduser().resolve()
if os.environ.get("APP_ENV_FILE") and not ENV_FILE_PATH.is_file():
    raise ValueError("APP_ENV_FILE must identify an existing environment file")


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # API Configuration
    app_name: str = "Virology Lab Commitment Extraction API"
    app_version: str = "0.1.0"
    debug: bool = False
    
    # Gemini API Configuration
    gemini_api_key: str = ""  # Primary key (optional if using numbered keys)
    gemini_model: str = "gemini-3.5-flash-lite"  # Free tier model (verified working)
    
    # Demo Mode (for testing without Gemini API calls)
    demo_mode: bool = False  # Set to true to use mock extractor
    
    # Hybrid Engine Configuration
    hybrid_engine_enabled: bool = False  # Master switch for hybrid extraction
    enable_preprocessing: bool = True
    enable_ocr: bool = True
    enable_hybrid_verification: bool = True
    enable_focused_retry: bool = False  # DISABLED by default per user requirement
    
    # File Processing Limits (D-14 provisional)
    max_file_size_mb: int = Field(default=20, ge=1, le=100)
    max_pages_per_document: int = Field(default=30, ge=1, le=100)
    max_files_per_batch: int = Field(default=10, ge=1, le=20)
    
    # CORS Configuration
    cors_origins: list[str] = ["http://localhost:5173"]
    
    # Temporary Storage
    temp_storage_ttl_hours: int = 24
    temp_storage_path: str = "temp"
    
    # Supabase Configuration (optional - for cloud persistence)
    supabase_url: str = ""
    supabase_service_key: str = ""
    supabase_bucket_name: str = "virology-lab-uploads"
    # "cloud" remains a compatibility alias for the protected staging demo.
    deployment_mode: Literal["local", "cloud", "staging", "staging-real", "production"] = "local"
    api_username: str = ""
    api_password: str = ""
    max_request_size_mb: int = Field(default=210, ge=1, le=512)
    upload_requests_per_minute: int = Field(default=6, ge=1, le=60)
    concurrent_processing_batches: int = Field(default=1, ge=1, le=4)
    # Overall per-page attempt deadline; separate from HTTPX operation timeouts.
    extraction_timeout_seconds: int = Field(default=300, ge=30, le=600)
    # Bounded, observable extraction. Total attempts per page (SDK retries are disabled: attempts=1).
    extraction_max_attempts: int = Field(default=2, ge=1, le=3)
    # Stop the batch after this many consecutive provider-wide failures (503/504/timeout/network).
    extraction_max_consecutive_failures: int = Field(default=2, ge=1, le=10)
    # Hard wall-clock ceiling for one batch; remaining pages are recorded as not processed.
    extraction_batch_deadline_seconds: int = Field(default=1800, ge=60, le=7200)
    # Gemini HTTP request timeout (also sent to the server as its processing deadline).
    gemini_request_timeout_seconds: int = Field(default=180, ge=10, le=300)
    # Page image sent to Gemini: longest side in pixels (0 = send the rendered PNG unchanged) and JPEG quality.
    gemini_image_max_dimension: int = Field(default=2048, ge=0, le=4096)
    gemini_image_jpeg_quality: int = Field(default=90, ge=50, le=100)
    # Optional thinking level for latency tuning ("" = model default; gemini-3.8-flash rejects "minimal").
    gemini_thinking_level: Literal["", "low", "medium", "high"] = ""
    # Bind the Gemini HTTP client to IPv4 (local_address=0.0.0.0). For networks where IPv6 is advertised in DNS
    # but black-holed. NOTE: a custom transport bypasses httpx automatic proxy discovery (HTTP(S)_PROXY / system proxy).
    gemini_force_ipv4: bool = False
    # Local safety budget for Gemini requests (each attempt counts). Set these to your project real provider limits,
    # never above them; raising them does not increase the provider quota.
    local_quota_requests_per_minute: int = Field(default=5, ge=1, le=1000)
    local_quota_requests_per_day: int = Field(default=20, ge=1, le=100000)
    max_image_pixels: int = Field(default=20_000_000, ge=1, le=80_000_000)

    @property
    def is_cloud(self) -> bool:
        return self.deployment_mode != "local"

    def validate_deployment(self) -> None:
        # Deliberately not an env-var bypass: clinical controls are not implemented.
        if self.deployment_mode == "production":
            raise ValueError(
                "PRODUCTION BLOCKED: institutional identity/RBAC, tenant authorization, "
                "durable processing, audit ledger and institutional approvals are required"
            )
        if self.is_cloud:
            if self.deployment_mode == "staging-real":
                if self.demo_mode:
                    raise ValueError("staging-real requires DEMO_MODE=false; mock extraction is prohibited")
                key_names = ["GEMINI_API_KEY", *(f"GEMINI_API_{i}" for i in range(1, 9))]
                if not any(os.environ.get(name, "").strip() for name in key_names):
                    raise ValueError("staging-real requires Gemini credentials in backend environment variables")
                if not self.gemini_model.strip():
                    raise ValueError("staging-real requires GEMINI_MODEL")
            elif not self.demo_mode:
                raise ValueError("Staging requires DEMO_MODE synthetic extraction")
            if not (self.supabase_url and self.supabase_service_key):
                raise ValueError("Cloud requires SUPABASE_URL and SUPABASE_SERVICE_KEY")
            if not self.api_username or len(self.api_password) < 16:
                raise ValueError("Staging requires API_USERNAME and a strong API_PASSWORD")
            from urllib.parse import urlsplit
            project = urlsplit(self.supabase_url)
            if (project.scheme != "https" or not project.hostname or project.username
                    or project.password or project.query or project.fragment or project.path not in ("", "/")):
                raise ValueError("Cloud requires an exact HTTPS Supabase project endpoint")
            for origin in self.cors_origins:
                parsed = urlsplit(origin)
                if (parsed.scheme != "https" or not parsed.hostname or parsed.username
                        or parsed.password or parsed.path or parsed.query or parsed.fragment
                        or "*" in origin):
                    raise ValueError("Cloud requires exact HTTPS frontend CORS origins")
            if not self.cors_origins:
                raise ValueError("Cloud requires explicit frontend CORS origins")
    
    model_config = SettingsConfigDict(
        env_file=ENV_FILE_PATH,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra='ignore',  # Allow extra env vars (e.g., GEMINI_API_1-8 for key manager)
    )


# Global settings instance
settings = Settings()
