"""Application configuration management using Pydantic Settings."""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # API Configuration
    app_name: str = "Virology Lab Commitment Extraction API"
    app_version: str = "0.1.0"
    debug: bool = False
    
    # Gemini API Configuration
    gemini_api_key: str = ""  # Primary key (optional if using numbered keys)
    gemini_model: str = "gemini-3.8-flash"  # Updated to latest stable free-tier model
    
    # Demo Mode (for testing without Gemini API calls)
    demo_mode: bool = False  # Set to true to use mock extractor
    
    # Hybrid Engine Configuration
    hybrid_engine_enabled: bool = False  # Master switch for hybrid extraction
    enable_preprocessing: bool = True
    enable_ocr: bool = True
    enable_hybrid_verification: bool = True
    enable_focused_retry: bool = False  # DISABLED by default per user requirement
    
    # File Processing Limits (D-14 provisional)
    max_file_size_mb: int = 20
    max_pages_per_document: int = 30
    max_files_per_batch: int = 10
    
    # CORS Configuration
    cors_origins: list[str] = ["http://localhost:5173"]
    
    # Temporary Storage
    temp_storage_ttl_hours: int = 24
    temp_storage_path: str = "temp"
    
    model_config = SettingsConfigDict(
        env_file=Path(__file__).parent.parent.parent.parent / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra='ignore',  # Allow extra env vars (e.g., GEMINI_API_1-8 for key manager)
    )


# Global settings instance
settings = Settings()
