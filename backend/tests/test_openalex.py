"""Tests for OpenAlex data source adapter."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.sources.openalex import (
    OpenAlexSource,
    _parse_work,
    _reconstruct_abstract,
    _extract_openalex_id,
)


# ── Abstract reconstruction tests ──


class TestReconstructAbstract:
    def test_basic(self):
        inverted = {"hello": [0], "world": [1], "foo": [2]}
        assert _reconstruct_abstract(inverted) == "hello world foo"

    def test_word_at_multiple_positions(self):
        inverted = {"the": [0, 4], "cat": [1], "sat": [2], "on": [3], "mat": [5]}
        assert _reconstruct_abstract(inverted) == "the cat sat on the mat"

    def test_none_input(self):
        assert _reconstruct_abstract(None) is None

    def test_empty_dict(self):
        assert _reconstruct_abstract({}) is None

    def test_complex_abstract(self):
        inverted = {
            "We": [0],
            "propose": [1],
            "a": [2, 8],
            "novel": [3],
            "method": [4],
            "for": [5],
            "text": [6],
            "classification": [7],
            "using": [9],
            "transformers.": [10],
        }
        result = _reconstruct_abstract(inverted)
        assert result is not None
        assert result.startswith("We propose")
        assert "transformers." in result


class TestExtractOpenAlexId:
    def test_full_url(self):
        assert _extract_openalex_id("https://openalex.org/W2741809807") == "W2741809807"

    def test_just_id(self):
        assert _extract_openalex_id("W2741809807") == "W2741809807"


# ── Work parsing tests ──


SAMPLE_WORK = {
    "id": "https://openalex.org/W2741809807",
    "doi": "https://doi.org/10.1234/test.2024",
    "title": "Attention Is All You Need",
    "publication_year": 2017,
    "authorships": [
        {"author": {"display_name": "Ashish Vaswani"}},
        {"author": {"display_name": "Noam Shazeer"}},
    ],
    "primary_location": {
        "source": {"display_name": "NeurIPS 2017"},
        "pdf_url": "https://example.com/paper.pdf",
        "is_oa": True,
    },
    "abstract_inverted_index": {
        "The": [0],
        "dominant": [1],
        "sequence": [2],
        "models.": [3],
    },
    "cited_by_count": 90000,
    "referenced_works_count": 42,
    "open_access": {"is_oa": True},
}


class TestParseWork:
    def test_full_work(self):
        paper = _parse_work(SAMPLE_WORK)
        assert paper is not None
        assert paper.title == "Attention Is All You Need"
        assert paper.year == 2017
        assert len(paper.authors) == 2
        assert paper.authors[0] == "Ashish Vaswani"
        assert paper.doi == "10.1234/test.2024"
        assert paper.openalex_id == "W2741809807"
        assert paper.citation_count == 90000
        assert paper.reference_count == 42
        assert paper.open_access is True
        assert paper.pdf_url == "https://example.com/paper.pdf"
        assert paper.venue == "NeurIPS 2017"
        assert paper.source == "openalex"
        assert paper.abstract is not None
        assert "dominant sequence" in paper.abstract

    def test_none_data(self):
        assert _parse_work(None) is None
        assert _parse_work({}) is None
        assert _parse_work({"title": None}) is None

    def test_minimal_work(self):
        paper = _parse_work({"id": "https://openalex.org/W123", "title": "Test"})
        assert paper is not None
        assert paper.title == "Test"
        assert paper.authors == ["Unknown"]
        assert paper.citation_count == 0

    def test_doi_without_prefix(self):
        data = {**SAMPLE_WORK, "doi": "10.5555/plain-doi"}
        paper = _parse_work(data)
        assert paper is not None
        assert paper.doi == "10.5555/plain-doi"


# ── Search mock test ──


class TestOpenAlexSourceSearch:
    @pytest.mark.asyncio
    async def test_search_parses_results(self):
        """Test that search correctly parses API response."""
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"results": [SAMPLE_WORK], "meta": {"count": 1}}
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.sources.openalex.httpx.AsyncClient", return_value=mock_client):
            source = OpenAlexSource(email="test@example.com")
            results = await source.search("attention transformer")

        assert len(results) == 1
        assert results[0].title == "Attention Is All You Need"
        assert results[0].source == "openalex"

    @pytest.mark.asyncio
    async def test_get_paper_not_found(self):
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 404

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.sources.openalex.httpx.AsyncClient", return_value=mock_client):
            source = OpenAlexSource()
            result = await source.get_paper("W999999")
            assert result is None

    @pytest.mark.asyncio
    async def test_search_with_year_filter(self):
        """Verify year range translates to filter param."""
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"results": []}
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.sources.openalex.httpx.AsyncClient", return_value=mock_client):
            source = OpenAlexSource(email="test@example.com")
            await source.search("test", filters={"year_range": {"min": 2020, "max": 2024}})

        # Verify the filter param was passed
        call_kwargs = mock_client.get.call_args
        params = call_kwargs.kwargs.get("params", call_kwargs[1].get("params", {}))
        assert "filter" in params
        assert "publication_year:2020-2024" in params["filter"]


# ── Live integration test (skipped in CI) ──


class TestOpenAlexLive:
    @pytest.mark.live
    @pytest.mark.asyncio
    async def test_live_search(self):
        source = OpenAlexSource()
        results = await source.search("transformer attention mechanism", filters={"max_papers": 5})
        assert len(results) > 0
        assert all(r.title for r in results)
        assert all(r.source == "openalex" for r in results)
