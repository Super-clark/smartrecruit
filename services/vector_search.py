"""
Vector Search Service — Qdrant + fastembed
"""

from __future__ import annotations

import logging
from typing import Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import Distance, PointStruct, ScoredPoint, VectorParams

from config import EMBEDDING_DIM, EMBEDDING_MODEL, QDRANT_COLLECTION, QDRANT_HOST, QDRANT_PORT

logger = logging.getLogger(__name__)

_qdrant_client: AsyncQdrantClient | None = None
_embed_model: Any | None = None


def _get_embed_model() -> Any:
    global _embed_model
    if _embed_model is None:
        try:
            from fastembed import TextEmbedding  # type: ignore
            _embed_model = TextEmbedding(model_name=EMBEDDING_MODEL)
            logger.info("fastembed model '%s' loaded.", EMBEDDING_MODEL)
        except Exception as exc:
            logger.error("Failed to load fastembed model: %s", exc)
            _embed_model = None
    return _embed_model


def get_qdrant_client() -> AsyncQdrantClient:
    global _qdrant_client
    if _qdrant_client is None:
        import os
        api_key = os.getenv("QDRANT_API_KEY")   # None in local dev, set in production
        _qdrant_client = AsyncQdrantClient(
            host=QDRANT_HOST,
            port=QDRANT_PORT,
            api_key=api_key,                     # ignored when None
        )
        logger.info("AsyncQdrantClient → %s:%s%s", QDRANT_HOST, QDRANT_PORT,
                    " (authenticated)" if api_key else "")
    return _qdrant_client


async def ensure_collection() -> None:
    client = get_qdrant_client()
    existing = await client.get_collections()
    names = [c.name for c in existing.collections]
    if QDRANT_COLLECTION not in names:
        await client.create_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
        )
        logger.info("Qdrant collection '%s' created.", QDRANT_COLLECTION)


def _embed_text(text: str) -> list[float]:
    model = _get_embed_model()
    if model is None:
        return [0.0] * EMBEDDING_DIM
    try:
        return list(model.embed([text]))[0].tolist()
    except Exception as exc:
        logger.error("Embedding failed: %s", exc)
        return [0.0] * EMBEDDING_DIM


async def upsert_candidate_vector(
    candidate_id: int, text: str, payload: dict[str, Any] | None = None,
) -> None:
    client = get_qdrant_client()
    vector = _embed_text(text)
    await client.upsert(
        collection_name=QDRANT_COLLECTION,
        points=[PointStruct(id=candidate_id, vector=vector, payload=payload or {})],
    )
    logger.debug("Upserted vector for candidate_id=%s", candidate_id)


async def search_candidates(query_text: str, limit: int = 10) -> list[ScoredPoint]:
    client = get_qdrant_client()
    query_vector = _embed_text(query_text)
    try:
        return await client.search(
            collection_name=QDRANT_COLLECTION,
            query_vector=query_vector,
            limit=limit,
            with_payload=True,
        )
    except Exception as exc:
        logger.error("search_candidates failed: %s", exc)
        return []


async def delete_candidate_vector(candidate_id: int) -> None:
    client = get_qdrant_client()
    await client.delete(
        collection_name=QDRANT_COLLECTION,
        points_selector=[candidate_id],
    )
