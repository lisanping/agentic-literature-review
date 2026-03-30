"""Citation formatting (APA / IEEE / GB/T 7714) and BibTeX / RIS export."""

from dataclasses import dataclass


@dataclass
class CitationInfo:
    """Minimal citation data needed for formatting."""

    title: str
    authors: list[str]
    year: int | None = None
    venue: str | None = None
    doi: str | None = None
    url: str | None = None
    volume: str | None = None
    pages: str | None = None


def _first_author_last_name(authors: list[str]) -> str:
    """Extract the last name of the first author."""
    if not authors:
        return "Unknown"
    first = authors[0]
    parts = first.split(",")
    if len(parts) >= 2:
        return parts[0].strip()
    parts = first.split()
    return parts[-1] if parts else "Unknown"


def _format_author_apa(name: str) -> str:
    """Format a single author name in APA style: Last, F. M."""
    parts = name.split(",")
    if len(parts) >= 2:
        last = parts[0].strip()
        firsts = parts[1].strip().split()
        initials = " ".join(f"{f[0]}." for f in firsts if f)
        return f"{last}, {initials}"
    parts = name.split()
    if len(parts) >= 2:
        last = parts[-1]
        initials = " ".join(f"{p[0]}." for p in parts[:-1] if p)
        return f"{last}, {initials}"
    return name


def format_apa(info: CitationInfo) -> str:
    """Format a citation in APA (7th edition) style."""
    authors_str = ", ".join(_format_author_apa(a) for a in info.authors[:7])
    if len(info.authors) > 7:
        authors_str += ", ... "
    year_str = f"({info.year})" if info.year else "(n.d.)"
    parts = [f"{authors_str} {year_str}. {info.title}."]
    if info.venue:
        venue_part = f"*{info.venue}*"
        if info.volume:
            venue_part += f", *{info.volume}*"
        if info.pages:
            venue_part += f", {info.pages}"
        parts.append(venue_part + ".")
    if info.doi:
        parts.append(f"https://doi.org/{info.doi}")
    return " ".join(parts)


def format_ieee(info: CitationInfo) -> str:
    """Format a citation in IEEE style."""
    # IEEE: F. M. Last, ...
    author_parts = []
    for name in info.authors[:6]:
        parts = name.split(",")
        if len(parts) >= 2:
            last = parts[0].strip()
            firsts = parts[1].strip().split()
            initials = " ".join(f"{f[0]}." for f in firsts if f)
            author_parts.append(f"{initials} {last}")
        else:
            p = name.split()
            if len(p) >= 2:
                initials = " ".join(f"{x[0]}." for x in p[:-1])
                author_parts.append(f"{initials} {p[-1]}")
            else:
                author_parts.append(name)
    if len(info.authors) > 6:
        author_parts.append("et al.")

    authors_str = ", ".join(author_parts)
    parts = [f'{authors_str}, "{info.title},"']
    if info.venue:
        venue_part = f"*{info.venue}*"
        if info.volume:
            venue_part += f", vol. {info.volume}"
        if info.pages:
            venue_part += f", pp. {info.pages}"
        parts.append(venue_part + ",")
    if info.year:
        parts.append(f"{info.year}.")
    if info.doi:
        parts.append(f"doi: {info.doi}.")
    return " ".join(parts)


def format_gbt7714(info: CitationInfo) -> str:
    """Format a citation in GB/T 7714-2015 style (Chinese standard)."""
    authors_str = ", ".join(info.authors[:3])
    if len(info.authors) > 3:
        authors_str += ", 等"
    year_str = str(info.year) if info.year else ""
    parts = [f"{authors_str}. {info.title}[J]."]
    if info.venue:
        parts.append(f"{info.venue},")
    if year_str:
        parts.append(f"{year_str}")
    if info.volume:
        parts.append(f", {info.volume}")
    if info.pages:
        parts.append(f": {info.pages}")
    parts.append(".")
    return " ".join(parts)


def format_citation(info: CitationInfo, style: str = "apa") -> str:
    """Format a citation in the given style.

    Args:
        info: Citation data.
        style: One of "apa", "ieee", "gbt7714".

    Returns:
        Formatted citation string.
    """
    formatters = {
        "apa": format_apa,
        "ieee": format_ieee,
        "gbt7714": format_gbt7714,
    }
    formatter = formatters.get(style, format_apa)
    return formatter(info)


# ── BibTeX / RIS export ──


def to_bibtex(info: CitationInfo, cite_key: str | None = None) -> str:
    """Generate a BibTeX entry from citation info."""
    if not cite_key:
        last = _first_author_last_name(info.authors)
        cite_key = f"{last}{info.year or 'nd'}"

    lines = [f"@article{{{cite_key},"]
    lines.append(f"  title = {{{info.title}}},")
    lines.append(f"  author = {{{' and '.join(info.authors)}}},")
    if info.year:
        lines.append(f"  year = {{{info.year}}},")
    if info.venue:
        lines.append(f"  journal = {{{info.venue}}},")
    if info.volume:
        lines.append(f"  volume = {{{info.volume}}},")
    if info.pages:
        lines.append(f"  pages = {{{info.pages}}},")
    if info.doi:
        lines.append(f"  doi = {{{info.doi}}},")
    if info.url:
        lines.append(f"  url = {{{info.url}}},")
    lines.append("}")
    return "\n".join(lines)


def to_ris(info: CitationInfo) -> str:
    """Generate a RIS entry from citation info."""
    lines = ["TY  - JOUR"]
    lines.append(f"TI  - {info.title}")
    for author in info.authors:
        lines.append(f"AU  - {author}")
    if info.year:
        lines.append(f"PY  - {info.year}")
    if info.venue:
        lines.append(f"JO  - {info.venue}")
    if info.volume:
        lines.append(f"VL  - {info.volume}")
    if info.pages:
        lines.append(f"SP  - {info.pages}")
    if info.doi:
        lines.append(f"DO  - {info.doi}")
    if info.url:
        lines.append(f"UR  - {info.url}")
    lines.append("ER  - ")
    return "\n".join(lines)


def parse_bibtex_entry(bibtex_str: str) -> CitationInfo | None:
    """Parse a single BibTeX entry into CitationInfo (simple parser)."""
    import re

    fields: dict[str, str] = {}
    for match in re.finditer(r"(\w+)\s*=\s*\{([^}]*)\}", bibtex_str):
        fields[match.group(1).lower()] = match.group(2)

    title = fields.get("title")
    if not title:
        return None

    author_str = fields.get("author", "Unknown")
    authors = [a.strip() for a in author_str.split(" and ")]
    year = int(fields["year"]) if "year" in fields and fields["year"].isdigit() else None

    return CitationInfo(
        title=title,
        authors=authors,
        year=year,
        venue=fields.get("journal") or fields.get("booktitle"),
        doi=fields.get("doi"),
        url=fields.get("url"),
        volume=fields.get("volume"),
        pages=fields.get("pages"),
    )
