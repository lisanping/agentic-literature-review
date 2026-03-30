"""Tests for arXiv adapter — XML parsing."""

import pytest
from app.sources.arxiv import _parse_entry, ArxivSource
import xml.etree.ElementTree as ET


SAMPLE_ENTRY = """
<entry xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <id>http://arxiv.org/abs/2301.00001v2</id>
  <published>2023-01-01T00:00:00Z</published>
  <title>  A Sample Paper on
     Large Language Models  </title>
  <summary>This paper studies large language models and their applications.</summary>
  <author><name>Alice Smith</name></author>
  <author><name>Bob Jones</name></author>
  <link title="pdf" href="http://arxiv.org/pdf/2301.00001v2" rel="related" type="application/pdf"/>
  <link href="http://arxiv.org/abs/2301.00001v2" rel="alternate" type="text/html"/>
  <arxiv:doi>10.1234/test</arxiv:doi>
  <arxiv:primary_category term="cs.CL"/>
</entry>
"""


def test_parse_entry():
    entry = ET.fromstring(SAMPLE_ENTRY)
    result = _parse_entry(entry)
    assert result is not None
    assert result.title == "A Sample Paper on Large Language Models"
    assert result.authors == ["Alice Smith", "Bob Jones"]
    assert result.year == 2023
    assert result.arxiv_id == "2301.00001"
    assert result.doi == "10.1234/test"
    assert result.pdf_url == "http://arxiv.org/pdf/2301.00001v2"
    assert result.source == "arxiv"
    assert result.open_access is True
    assert result.venue == "cs.CL"


def test_parse_entry_no_title():
    entry_xml = """
    <entry xmlns="http://www.w3.org/2005/Atom">
      <id>http://arxiv.org/abs/2301.00001</id>
    </entry>
    """
    entry = ET.fromstring(entry_xml)
    result = _parse_entry(entry)
    assert result is None


SAMPLE_RESPONSE = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <title>ArXiv Query</title>
  {entry}
</feed>""".format(entry=SAMPLE_ENTRY)


def test_parse_full_response():
    root = ET.fromstring(SAMPLE_RESPONSE)
    ns = "{http://www.w3.org/2005/Atom}"
    entries = root.findall(f"{ns}entry")
    assert len(entries) == 1
    result = _parse_entry(entries[0])
    assert result is not None
    assert result.title == "A Sample Paper on Large Language Models"
