from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM
    llm_provider: str = "openai"  # openai | gemini
    openai_api_key: str = "sk-your-openai-api-key-here"
    openai_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    gemini_api_key: str = "your-gemini-api-key-here"
    gemini_model: str = "gemini-2.0-flash"

    # Supabase
    supabase_url: str = "https://your-project-ref.supabase.co"
    supabase_anon_key: str = "your-supabase-anon-key-here"
    supabase_service_role_key: str = "your-supabase-service-role-key-here"
    database_url: str = ""

    # Server
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    cors_origins: str = "http://localhost:3000"

    # Diagnostics
    max_clarifying_questions: int = 4
    use_mock_llm: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def openai_configured(self) -> bool:
        key = self.openai_api_key
        return bool(key) and not key.startswith("sk-your-") and "placeholder" not in key.lower()

    @property
    def gemini_configured(self) -> bool:
        key = self.gemini_api_key
        return bool(key) and not key.startswith("your-") and "placeholder" not in key.lower()

    @property
    def supabase_configured(self) -> bool:
        return (
            "your-project-ref" not in self.supabase_url
            and not self.supabase_service_role_key.startswith("your-")
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
