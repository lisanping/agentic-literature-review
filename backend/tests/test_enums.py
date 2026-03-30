"""Tests for enum definitions."""

from app.models.enums import (
    CitationStyle,
    ExportFormat,
    OutputType,
    PaperRelationType,
    PaperSourceType,
    ProjectStatus,
)


def test_output_type_values():
    assert OutputType.QUICK_BRIEF == "quick_brief"
    assert OutputType.FULL_REVIEW == "full_review"
    assert OutputType.ANNOTATED_BIBLIOGRAPHY == "annotated_bib"
    assert len(OutputType) == 10


def test_project_status_values():
    assert ProjectStatus.CREATED == "created"
    assert ProjectStatus.COMPLETED == "completed"
    assert ProjectStatus.FAILED == "failed"
    assert len(ProjectStatus) == 15


def test_paper_source_type_values():
    assert PaperSourceType.SEMANTIC_SCHOLAR == "semantic_scholar"
    assert PaperSourceType.ARXIV == "arxiv"
    assert PaperSourceType.USER_UPLOAD == "user_upload"
    assert len(PaperSourceType) == 9


def test_paper_relation_type_values():
    assert PaperRelationType.CITES == "cites"
    assert PaperRelationType.EXTENDS == "extends"
    assert len(PaperRelationType) == 7


def test_citation_style_values():
    assert CitationStyle.APA == "apa"
    assert CitationStyle.GBT7714 == "gbt7714"
    assert len(CitationStyle) == 5


def test_export_format_values():
    assert ExportFormat.MARKDOWN == "markdown"
    assert ExportFormat.BIBTEX == "bibtex"
    assert ExportFormat.RIS == "ris"
    assert len(ExportFormat) == 11
