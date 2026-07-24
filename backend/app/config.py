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
    openai_api_key: str = "your_openai_api_key_here"
    openai_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    gemini_api_key: str = "your_gemini_api_key_here"
    gemini_model: str = "gemini-2.0-flash"

    # Supabase
    supabase_url: str = "your_supabase_project_url_here"
    supabase_anon_key: str = "your_supabase_anon_key_here"
    supabase_service_role_key: str = "your_supabase_service_role_key_here"
    database_url: str = ""

    # Server
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    cors_origins: str = "http://localhost:3000"

    # Diagnostics
    max_clarifying_questions: int = 4
    use_mock_llm: bool = False

    # RAG: cosine similarity floor for "strong" vector matches.
    # Below this → treat as no grounded knowledge (general GPT only).
    # Exact OBD code matches always count as strong regardless of this value.
    # 0.55 keeps JP battery (~0.56) as strong; weak/tangential hits stay out.
    rag_min_similarity: float = 0.55

    # PostHog (same project token as NEXT_PUBLIC_POSTHOG_KEY; server-only env name)
    posthog_key: str = ""

    @staticmethod
    def _is_placeholder(value: str) -> bool:
        """True for empty/template secrets that must never be treated as live keys."""
        if not value or not str(value).strip():
            return True
        v = str(value).strip().lower()
        if v.startswith("sk-your"):
            return True
        if v.startswith("your_") or v.startswith("your-") or v.startswith("your "):
            return True
        if "placeholder" in v or "example" in v or "changeme" in v:
            return True
        if "your_project" in v or "project-ref" in v or "project_ref" in v:
            return True
        if v.endswith("_here") or v.endswith("-here"):
            return True
        return False

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def openai_configured(self) -> bool:
        return not self._is_placeholder(self.openai_api_key)

    @property
    def gemini_configured(self) -> bool:
        return not self._is_placeholder(self.gemini_api_key)

    @property
    def supabase_configured(self) -> bool:
        return not (
            self._is_placeholder(self.supabase_url)
            or self._is_placeholder(self.supabase_service_role_key)
        )

    @property
    def database_configured(self) -> bool:
        return (
            bool(self.database_url)
            and self.database_url.startswith("postgres")
            and not self._is_placeholder(self.database_url)
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
