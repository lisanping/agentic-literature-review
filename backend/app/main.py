"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.logging import setup_logging
from app.api.exceptions import register_exception_handlers
from app.api.routes import auth, health, projects, workflow, papers, outputs, events, shares, users, visualizations

logger = structlog.stdlib.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup and shutdown events."""
    setup_logging(settings.LOG_LEVEL)
    logger.info("app.startup", log_level=settings.LOG_LEVEL)
    yield
    logger.info("app.shutdown")


app = FastAPI(
    title="Agentic Literature Review",
    description="AI-driven multi-agent literature review assistant",
    version="0.1.0",
    lifespan=lifespan,
)

# ── CORS ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Exception handlers ──
register_exception_handlers(app)

# ── Routes ──
app.include_router(auth.router)
app.include_router(health.router)
app.include_router(projects.router)
app.include_router(workflow.router)
app.include_router(papers.router)
app.include_router(outputs.router)
app.include_router(events.router)
app.include_router(shares.router)
app.include_router(users.router)
app.include_router(visualizations.router)
