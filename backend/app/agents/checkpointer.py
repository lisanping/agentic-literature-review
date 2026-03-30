"""Checkpointer factory — create the checkpoint persistence backend."""

from app.config import settings


def create_checkpointer():
    """Create a LangGraph checkpointer based on configuration.

    Supports:
    - ``sqlite``: file-based, good for MVP / single-server
    - ``postgres``: for production multi-worker setups

    Returns:
        A LangGraph BaseCheckpointSaver instance.
    """
    backend = settings.CHECKPOINTER_BACKEND.lower()

    if backend == "sqlite":
        from langgraph.checkpoint.sqlite import SqliteSaver
        import sqlite3

        conn = sqlite3.connect(settings.CHECKPOINT_DB_URL.replace("sqlite:///", ""), check_same_thread=False)
        return SqliteSaver(conn)

    elif backend == "postgres":
        from langgraph.checkpoint.postgres import PostgresSaver

        return PostgresSaver.from_conn_string(settings.CHECKPOINT_DB_URL)

    raise ValueError(
        f"Unknown checkpointer backend: {backend!r}. "
        "Supported: 'sqlite', 'postgres'."
    )
