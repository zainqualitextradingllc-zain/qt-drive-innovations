"""Embedding helpers for RAG (OpenAI text-embedding-3-small = 1536 dims)."""

from __future__ import annotations

from typing import Sequence

from app.config import get_settings

# Must match knowledge_entries.embedding vector(1536)
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
EXPECTED_DIMS = 1536


def build_embed_text(row: dict) -> str:
    """
    Build bilingual embed text for a knowledge_entries row.
    Prefers stored embed_text; otherwise concatenates EN + JA fields.
    """
    existing = (row.get("embed_text") or "").strip()
    if existing:
        return existing

    parts: list[str] = []
    for key in (
        "obd_code",
        "title_en",
        "description_en",
        "severity_en",
        "recommended_action_en",
        "title_ja",
        "description_ja",
        "severity_ja",
        "recommended_action_ja",
    ):
        val = row.get(key)
        if val:
            parts.append(str(val))

    for key in ("likely_causes_en", "likely_causes_ja"):
        val = row.get(key)
        if isinstance(val, (list, tuple)):
            parts.append(" ".join(str(x) for x in val))
        elif val:
            parts.append(str(val))

    return " | ".join(parts).strip()


async def embed_texts(texts: Sequence[str], *, model: str | None = None) -> list[list[float]]:
    """Embed one or more texts. Returns list of float vectors (len = EXPECTED_DIMS)."""
    settings = get_settings()
    if not settings.openai_configured:
        raise RuntimeError(
            "OPENAI_API_KEY is not configured. Set a real key in backend/.env to run embeddings."
        )

    cleaned = [t.strip() if t and t.strip() else " " for t in texts]
    use_model = model or settings.openai_embedding_model or DEFAULT_EMBEDDING_MODEL

    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    resp = await client.embeddings.create(model=use_model, input=cleaned)
    # API returns data sorted by index
    vectors = [item.embedding for item in sorted(resp.data, key=lambda d: d.index)]
    for i, vec in enumerate(vectors):
        if len(vec) != EXPECTED_DIMS:
            raise RuntimeError(
                f"Unexpected embedding dims={len(vec)} for item {i}; "
                f"expected {EXPECTED_DIMS} (model={use_model}). "
                "Update knowledge_entries.embedding column if you change models."
            )
    return vectors


async def embed_query(text: str) -> list[float]:
    """Embed a single user query for match_knowledge_entries RPC."""
    vecs = await embed_texts([text])
    return vecs[0]


def embed_texts_sync(texts: Sequence[str], *, model: str | None = None) -> list[list[float]]:
    """Sync variant for CLI scripts."""
    settings = get_settings()
    if not settings.openai_configured:
        raise RuntimeError(
            "OPENAI_API_KEY is not configured. Set a real key in backend/.env to run embeddings."
        )

    cleaned = [t.strip() if t and t.strip() else " " for t in texts]
    use_model = model or settings.openai_embedding_model or DEFAULT_EMBEDDING_MODEL

    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    resp = client.embeddings.create(model=use_model, input=cleaned)
    vectors = [item.embedding for item in sorted(resp.data, key=lambda d: d.index)]
    for i, vec in enumerate(vectors):
        if len(vec) != EXPECTED_DIMS:
            raise RuntimeError(
                f"Unexpected embedding dims={len(vec)} for item {i}; expected {EXPECTED_DIMS}."
            )
    return vectors
