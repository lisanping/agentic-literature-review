"""PDF parsing using PyMuPDF — extract full text with section detection."""

from dataclasses import dataclass, field
from pathlib import Path

import structlog

logger = structlog.stdlib.get_logger()


@dataclass
class ParsedPDF:
    """Result of parsing a PDF document."""

    text: str
    sections: list[dict] = field(default_factory=list)  # [{title, content}]
    page_count: int = 0
    parser_used: str = "pymupdf"
    success: bool = True
    error: str | None = None


def parse_pdf(pdf_path: str | Path) -> ParsedPDF:
    """Parse a PDF file and extract full text with section detection.

    Falls back gracefully: if parsing fails, returns an error result.
    The caller should degrade to abstract-only analysis.

    Args:
        pdf_path: Path to the PDF file on disk.

    Returns:
        ParsedPDF with extracted text, sections, and metadata.
    """
    try:
        import pymupdf
    except ImportError:
        return ParsedPDF(
            text="",
            success=False,
            error="pymupdf not installed",
        )

    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        return ParsedPDF(text="", success=False, error=f"File not found: {pdf_path}")

    try:
        doc = pymupdf.open(str(pdf_path))
    except Exception as exc:
        logger.warning("pdf.open_failed", path=str(pdf_path), error=str(exc))
        return ParsedPDF(text="", success=False, error=str(exc))

    try:
        full_text_parts: list[str] = []
        sections: list[dict] = []
        current_section_title = "Untitled"
        current_section_lines: list[str] = []

        for page in doc:
            blocks = page.get_text("dict", sort=True).get("blocks", [])
            for block in blocks:
                if block.get("type") != 0:  # text blocks only
                    continue
                for line_info in block.get("lines", []):
                    line_text_parts = []
                    max_font_size = 0.0
                    is_bold = False
                    for span in line_info.get("spans", []):
                        text = span.get("text", "").strip()
                        if text:
                            line_text_parts.append(text)
                            font_size = span.get("size", 0)
                            if font_size > max_font_size:
                                max_font_size = font_size
                            flags = span.get("flags", 0)
                            if flags & 2 ** 4:  # bold flag
                                is_bold = True

                    line_text = " ".join(line_text_parts).strip()
                    if not line_text:
                        continue

                    full_text_parts.append(line_text)

                    # Heuristic: larger or bold text likely a section heading
                    if max_font_size > 12 and is_bold and len(line_text) < 200:
                        # Save previous section
                        if current_section_lines:
                            sections.append(
                                {
                                    "title": current_section_title,
                                    "content": "\n".join(current_section_lines),
                                }
                            )
                        current_section_title = line_text
                        current_section_lines = []
                    else:
                        current_section_lines.append(line_text)

        # Flush the last section
        if current_section_lines:
            sections.append(
                {
                    "title": current_section_title,
                    "content": "\n".join(current_section_lines),
                }
            )

        full_text = "\n".join(full_text_parts)

        logger.info(
            "pdf.parsed",
            path=str(pdf_path),
            pages=len(doc),
            chars=len(full_text),
            sections=len(sections),
        )

        return ParsedPDF(
            text=full_text,
            sections=sections,
            page_count=len(doc),
            parser_used="pymupdf",
        )
    except Exception as exc:
        logger.warning("pdf.parse_failed", path=str(pdf_path), error=str(exc))
        return ParsedPDF(text="", success=False, error=str(exc))
    finally:
        doc.close()
