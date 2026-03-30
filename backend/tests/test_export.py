"""Tests for export service — Markdown, Word, BibTeX, RIS."""

from app.services.export import export_bibtex, export_markdown, export_ris, export_word


_REFS = [
    {"title": "Paper A", "formatted": "Author A (2024). Paper A.", "authors": ["Author A"], "year": 2024},
    {"title": "Paper B", "formatted": "Author B (2023). Paper B.", "authors": ["Author B"], "year": 2023},
]


def test_export_markdown_basic():
    md = export_markdown("Hello world")
    assert "Hello world" in md


def test_export_markdown_with_title():
    md = export_markdown("Body text", title="My Review")
    assert "# My Review" in md
    assert "Body text" in md


def test_export_markdown_with_references():
    md = export_markdown("Body", references=_REFS, title="Review")
    assert "## References" in md
    assert "[1]" in md
    assert "[2]" in md
    assert "Paper A" in md


def test_export_word_returns_bytes():
    doc_bytes = export_word("# Introduction\n\nSome text.", title="Test")
    assert isinstance(doc_bytes, bytes)
    assert len(doc_bytes) > 100
    # .docx is actually a zip file — check magic bytes
    assert doc_bytes[:2] == b"PK"


def test_export_word_with_references():
    doc_bytes = export_word("Body", references=_REFS, title="Review")
    assert isinstance(doc_bytes, bytes)
    assert len(doc_bytes) > 100


def test_export_bibtex():
    bib = export_bibtex(_REFS)
    assert "@article{" in bib
    assert "Paper A" in bib
    assert "Paper B" in bib


def test_export_ris():
    ris = export_ris(_REFS)
    assert "TY  - JOUR" in ris
    assert "TI  - Paper A" in ris
    assert "TI  - Paper B" in ris
    assert "ER  - " in ris
