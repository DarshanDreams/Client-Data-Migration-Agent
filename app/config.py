from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Client Data Migration Agent"
    app_env: str = "development"
    log_level: str = "INFO"

    auto_approval_threshold: float = 0.85
    escalation_threshold: float = 0.60

    max_validation_attempts: int = 2
    max_api_retries: int = 3

    target_api_url: str = "http://localhost:8000"

    database_url: str = "sqlite:///./migration.db"

    # Open-source AI mapping
    ai_mapping_enabled: bool = True
    ai_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    ai_similarity_weight: float = 0.60
    rule_similarity_weight: float = 0.40

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()