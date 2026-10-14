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
    gemini_api_key: str
    gemini_model: str = "gemini-3.5-flash-lite"
    
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
    )


# Global settings instance
settings = Settings()
