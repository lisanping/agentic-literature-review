"""Chroma vector database initialization and embedding service."""

import chromadb

from app.config import settings


def get_chroma_client() -> chromadb.ClientAPI:
    """Create a persistent Chroma client."""
    return chromadb.PersistentClient(path=settings.CHROMA_PATH)


def get_or_create_paper_collection(
    client: chromadb.ClientAPI | None = None,
) -> chromadb.Collection:
    """Get or create the paper_embeddings collection.

    Uses cosine distance for similarity search.
    """
    if client is None:
        client = get_chroma_client()
    return client.get_or_create_collection(
        name="paper_embeddings",
        metadata={"hnsw:space": "cosine"},
    )
