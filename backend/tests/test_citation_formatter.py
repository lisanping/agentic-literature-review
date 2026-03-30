"""Tests for citation formatter — APA, IEEE, GB/T 7714, BibTeX, RIS."""

from app.parsers.citation_formatter import (
    CitationInfo,
    format_apa,
    format_citation,
    format_gbt7714,
    format_ieee,
    parse_bibtex_entry,
    to_bibtex,
    to_ris,
)


_SAMPLE = CitationInfo(
    title="Attention Is All You Need",
    authors=["Vaswani, Ashish", "Shazeer, Noam"],
    year=2017,
    venue="NeurIPS",
    doi="10.5555/3295222.3295349",
)


def test_format_apa():
    result = format_apa(_SAMPLE)
    assert "Vaswani" in result
    assert "(2017)" in result
    assert "Attention Is All You Need" in result
    assert "NeurIPS" in result
    assert "10.5555" in result


def test_format_ieee():
    result = format_ieee(_SAMPLE)
    assert "Vaswani" in result
    assert '"Attention Is All You Need,"' in result
    assert "2017" in result


def test_format_gbt7714():
    result = format_gbt7714(_SAMPLE)
    assert "Vaswani" in result
    assert "2017" in result
    assert "Attention Is All You Need" in result


def test_format_citation_dispatches():
    assert "Vaswani" in format_citation(_SAMPLE, "apa")
    assert "Vaswani" in format_citation(_SAMPLE, "ieee")
    assert "Vaswani" in format_citation(_SAMPLE, "gbt7714")
    # Unknown style falls back to APA
    assert "(2017)" in format_citation(_SAMPLE, "unknown_style")


def test_format_apa_no_year():
    info = CitationInfo(title="No Year Paper", authors=["Smith, John"])
    result = format_apa(info)
    assert "(n.d.)" in result


def test_format_apa_many_authors():
    info = CitationInfo(
        title="Many Authors",
        authors=[f"Author{i}, A." for i in range(10)],
        year=2024,
    )
    result = format_apa(info)
    assert "..." in result


def test_to_bibtex():
    result = to_bibtex(_SAMPLE)
    assert "@article{" in result
    assert "Attention Is All You Need" in result
    assert "Vaswani" in result
    assert "doi = {10.5555" in result
    assert "year = {2017}" in result


def test_to_ris():
    result = to_ris(_SAMPLE)
    assert "TY  - JOUR" in result
    assert "TI  - Attention Is All You Need" in result
    assert "AU  - Vaswani, Ashish" in result
    assert "PY  - 2017" in result
    assert "ER  - " in result


def test_parse_bibtex_entry():
    bib = """@article{vaswani2017,
      title = {Attention Is All You Need},
      author = {Vaswani, Ashish and Shazeer, Noam},
      year = {2017},
      journal = {NeurIPS},
    }"""
    info = parse_bibtex_entry(bib)
    assert info is not None
    assert info.title == "Attention Is All You Need"
    assert len(info.authors) == 2
    assert info.year == 2017
    assert info.venue == "NeurIPS"


def test_parse_bibtex_entry_no_title():
    bib = "@article{test, author = {A}}"
    assert parse_bibtex_entry(bib) is None
