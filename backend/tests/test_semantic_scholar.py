"""Tests for Semantic Scholar adapter — response parsing."""

from app.sources.semantic_scholar import _parse_paper


def test_parse_paper_full():
    data = {
        "paperId": "abc123",
        "title": "Attention Is All You Need",
        "authors": [{"name": "Vaswani"}, {"name": "Shazeer"}],
        "year": 2017,
        "venue": "NeurIPS",
        "abstract": "We propose the Transformer...",
        "citationCount": 80000,
        "referenceCount": 40,
        "isOpenAccess": True,
        "openAccessPdf": {"url": "https://example.com/paper.pdf"},
        "url": "https://www.semanticscholar.org/paper/abc123",
        "externalIds": {
            "DOI": "10.5555/3295222.3295349",
            "ArXiv": "1706.03762",
        },
    }
    result = _parse_paper(data)
    assert result is not None
    assert result.title == "Attention Is All You Need"
    assert result.authors == ["Vaswani", "Shazeer"]
    assert result.year == 2017
    assert result.s2_id == "abc123"
    assert result.doi == "10.5555/3295222.3295349"
    assert result.arxiv_id == "1706.03762"
    assert result.citation_count == 80000
    assert result.open_access is True
    assert result.pdf_url == "https://example.com/paper.pdf"
    assert result.source == "semantic_scholar"


def test_parse_paper_minimal():
    data = {
        "paperId": "xyz",
        "title": "Some Paper",
        "authors": [{"name": "Author A"}],
    }
    result = _parse_paper(data)
    assert result is not None
    assert result.title == "Some Paper"
    assert result.citation_count == 0
    assert result.doi is None


def test_parse_paper_no_title():
    data = {"paperId": "xyz"}
    assert _parse_paper(data) is None


def test_parse_paper_empty():
    assert _parse_paper({}) is None
    assert _parse_paper(None) is None


def test_parse_paper_no_open_access_pdf():
    data = {
        "paperId": "z",
        "title": "Test",
        "authors": [],
        "openAccessPdf": None,
    }
    result = _parse_paper(data)
    assert result is not None
    assert result.pdf_url is None
    assert result.authors == ["Unknown"]
