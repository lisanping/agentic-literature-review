"""Tests for PubMed data source adapter."""

import xml.etree.ElementTree as ET
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.sources.pubmed import PubMedSource, _parse_pubmed_article


# ── Sample PubMed XML ──

SAMPLE_ARTICLE_XML = """
<PubmedArticle>
  <MedlineCitation>
    <PMID>12345678</PMID>
    <Article>
      <ArticleTitle>CRISPR-Cas9 Gene Editing in Human Cells</ArticleTitle>
      <AuthorList>
        <Author>
          <LastName>Zhang</LastName>
          <ForeName>Feng</ForeName>
        </Author>
        <Author>
          <LastName>Doudna</LastName>
          <ForeName>Jennifer</ForeName>
        </Author>
      </AuthorList>
      <Abstract>
        <AbstractText Label="BACKGROUND">CRISPR-Cas9 enables precise genome editing.</AbstractText>
        <AbstractText Label="METHODS">We developed an improved guide RNA design.</AbstractText>
        <AbstractText Label="RESULTS">Editing efficiency increased by 50 percent.</AbstractText>
      </Abstract>
      <Journal>
        <Title>Nature Methods</Title>
        <JournalIssue>
          <PubDate>
            <Year>2023</Year>
          </PubDate>
        </JournalIssue>
      </Journal>
    </Article>
  </MedlineCitation>
  <PubmedData>
    <ArticleIdList>
      <ArticleId IdType="doi">10.1038/nmeth.2023</ArticleId>
      <ArticleId IdType="pmc">PMC7654321</ArticleId>
      <ArticleId IdType="pubmed">12345678</ArticleId>
    </ArticleIdList>
  </PubmedData>
</PubmedArticle>
"""

MINIMAL_ARTICLE_XML = """
<PubmedArticle>
  <MedlineCitation>
    <PMID>99999999</PMID>
    <Article>
      <ArticleTitle>Minimal Article</ArticleTitle>
      <Journal>
        <JournalIssue>
          <PubDate>
            <MedlineDate>2022 Jan-Feb</MedlineDate>
          </PubDate>
        </JournalIssue>
      </Journal>
    </Article>
  </MedlineCitation>
</PubmedArticle>
"""


# ── XML parsing tests ──


class TestParsePubmedArticle:
    def test_full_article(self):
        el = ET.fromstring(SAMPLE_ARTICLE_XML)
        paper = _parse_pubmed_article(el)

        assert paper is not None
        assert paper.title == "CRISPR-Cas9 Gene Editing in Human Cells"
        assert len(paper.authors) == 2
        assert paper.authors[0] == "Feng Zhang"
        assert paper.authors[1] == "Jennifer Doudna"
        assert paper.year == 2023
        assert paper.venue == "Nature Methods"
        assert paper.doi == "10.1038/nmeth.2023"
        assert paper.pmid == "12345678"
        assert paper.pmcid == "PMC7654321"
        assert paper.source == "pubmed"
        assert paper.open_access is True  # PMC article
        assert paper.abstract is not None
        assert "CRISPR-Cas9" in paper.abstract
        assert "BACKGROUND:" in paper.abstract
        assert "RESULTS:" in paper.abstract
        assert paper.source_url == "https://pubmed.ncbi.nlm.nih.gov/12345678/"
        assert "PMC7654321" in (paper.pdf_url or "")

    def test_minimal_article(self):
        el = ET.fromstring(MINIMAL_ARTICLE_XML)
        paper = _parse_pubmed_article(el)

        assert paper is not None
        assert paper.title == "Minimal Article"
        assert paper.authors == ["Unknown"]
        assert paper.year == 2022  # From MedlineDate
        assert paper.doi is None
        assert paper.pmid == "99999999"
        assert paper.pmcid is None
        assert paper.abstract is None

    def test_no_medline_citation(self):
        el = ET.fromstring("<PubmedArticle></PubmedArticle>")
        assert _parse_pubmed_article(el) is None

    def test_no_article(self):
        el = ET.fromstring(
            "<PubmedArticle><MedlineCitation><PMID>1</PMID></MedlineCitation></PubmedArticle>"
        )
        assert _parse_pubmed_article(el) is None

    def test_no_title(self):
        el = ET.fromstring("""
        <PubmedArticle>
          <MedlineCitation>
            <PMID>1</PMID>
            <Article>
              <Journal><JournalIssue><PubDate><Year>2020</Year></PubDate></JournalIssue></Journal>
            </Article>
          </MedlineCitation>
        </PubmedArticle>""")
        assert _parse_pubmed_article(el) is None


# ── Search mock tests ──


ESEARCH_RESPONSE = {
    "esearchresult": {
        "count": "2",
        "idlist": ["12345678", "87654321"],
    }
}

EFETCH_RESPONSE_XML = f"""<?xml version="1.0"?>
<PubmedArticleSet>
{SAMPLE_ARTICLE_XML}
</PubmedArticleSet>"""


class TestPubMedSourceSearch:
    @pytest.mark.asyncio
    async def test_search_two_step(self):
        """Test esearch → efetch two-step workflow."""
        call_count = 0

        def make_response(url, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_resp = MagicMock(spec=httpx.Response)
            mock_resp.raise_for_status = MagicMock()
            if "esearch" in url:
                mock_resp.status_code = 200
                mock_resp.json.return_value = ESEARCH_RESPONSE
            elif "efetch" in url:
                mock_resp.status_code = 200
                mock_resp.text = EFETCH_RESPONSE_XML
            else:
                mock_resp.status_code = 404
            return mock_resp

        mock_client = AsyncMock()
        mock_client.get.side_effect = lambda url, **kwargs: make_response(url, **kwargs)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.sources.pubmed.httpx.AsyncClient", return_value=mock_client):
            source = PubMedSource()
            results = await source.search("CRISPR")

        assert call_count == 2  # esearch + efetch
        assert len(results) == 1
        assert results[0].title == "CRISPR-Cas9 Gene Editing in Human Cells"
        assert results[0].source == "pubmed"

    @pytest.mark.asyncio
    async def test_search_empty_results(self):
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"esearchresult": {"count": "0", "idlist": []}}
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.sources.pubmed.httpx.AsyncClient", return_value=mock_client):
            source = PubMedSource()
            results = await source.search("nonexistent query xyz")
            assert results == []

    @pytest.mark.asyncio
    async def test_get_paper(self):
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.text = EFETCH_RESPONSE_XML
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.sources.pubmed.httpx.AsyncClient", return_value=mock_client):
            source = PubMedSource(api_key="test-key")
            result = await source.get_paper("12345678")

        assert result is not None
        assert result.pmid == "12345678"

    @pytest.mark.asyncio
    async def test_get_citations_via_elink(self):
        def make_response(url, **kwargs):
            mock_resp = MagicMock(spec=httpx.Response)
            mock_resp.raise_for_status = MagicMock()
            if "elink" in url:
                mock_resp.status_code = 200
                mock_resp.json.return_value = {
                    "linksets": [
                        {
                            "linksetdbs": [
                                {
                                    "linkname": "pubmed_pubmed_citedin",
                                    "links": [12345678],
                                }
                            ]
                        }
                    ]
                }
            elif "efetch" in url:
                mock_resp.status_code = 200
                mock_resp.text = EFETCH_RESPONSE_XML
            else:
                mock_resp.status_code = 404
            return mock_resp

        mock_client = AsyncMock()
        mock_client.get.side_effect = lambda url, **kwargs: make_response(url, **kwargs)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.sources.pubmed.httpx.AsyncClient", return_value=mock_client):
            source = PubMedSource()
            results = await source.get_citations("99999999")

        assert len(results) == 1


# ── Live test ──


class TestPubMedLive:
    @pytest.mark.live
    @pytest.mark.asyncio
    async def test_live_search(self):
        source = PubMedSource()
        results = await source.search("CRISPR gene editing", filters={"max_papers": 5})
        assert len(results) > 0
        assert all(r.title for r in results)
        assert all(r.source == "pubmed" for r in results)
