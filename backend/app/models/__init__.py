"""ORM models — import all models here so Alembic can discover them."""

from app.models.database import Base
from app.models.enums import (
    CitationStyle,
    ExportFormat,
    OutputType,
    PaperRelationType,
    PaperSourceType,
    ProjectStatus,
)
from app.models.paper import Paper, PaperFulltext
from app.models.paper_analysis import PaperAnalysis
from app.models.project import Project
from app.models.project_paper import ProjectPaper
from app.models.review_output import ReviewOutput

__all__ = [
    "Base",
    "CitationStyle",
    "ExportFormat",
    "OutputType",
    "Paper",
    "PaperAnalysis",
    "PaperFulltext",
    "PaperRelationType",
    "PaperSourceType",
    "Project",
    "ProjectPaper",
    "ProjectStatus",
    "ReviewOutput",
]