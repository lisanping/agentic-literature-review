"""Enumeration types for the application.

This is the single source of truth for all enums. Definitions are aligned with
the data model design document (docs/design/data-model.md §2).
"""

from enum import StrEnum


class OutputType(StrEnum):
    """综述输出类型"""

    # ── 文本类 ──
    QUICK_BRIEF = "quick_brief"
    ANNOTATED_BIBLIOGRAPHY = "annotated_bib"
    FULL_REVIEW = "full_review"
    METHODOLOGY_REVIEW = "methodology_review"
    RESEARCH_ROADMAP = "research_roadmap"

    # ── 结构化数据类 ──
    COMPARISON_MATRIX = "comparison_matrix"
    GAP_REPORT = "gap_report"
    TREND_REPORT = "trend_report"

    # ── 可视化类 ──
    KNOWLEDGE_MAP = "knowledge_map"
    TIMELINE = "timeline"


class ProjectStatus(StrEnum):
    """项目生命周期状态"""

    CREATED = "created"
    SEARCHING = "searching"
    SEARCH_REVIEW = "search_review"
    READING = "reading"
    ANALYZING = "analyzing"
    CRITIQUING = "critiquing"
    OUTLINING = "outlining"
    OUTLINE_REVIEW = "outline_review"
    WRITING = "writing"
    DRAFT_REVIEW = "draft_review"
    REVISING = "revising"
    EXPORTING = "exporting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PaperSourceType(StrEnum):
    """论文数据来源"""

    SEMANTIC_SCHOLAR = "semantic_scholar"
    ARXIV = "arxiv"
    OPENALEX = "openalex"
    PUBMED = "pubmed"
    CROSSREF = "crossref"
    DBLP = "dblp"
    CORE = "core"
    UNPAYWALL = "unpaywall"
    USER_UPLOAD = "user_upload"


class PaperRelationType(StrEnum):
    """论文间的学术关系"""

    CITES = "cites"
    EXTENDS = "extends"
    REFUTES = "refutes"
    REPRODUCES = "reproduces"
    REVIEWS = "reviews"
    COMPARES = "compares"
    APPLIES = "applies"


class CitationStyle(StrEnum):
    """引用格式"""

    APA = "apa"
    IEEE = "ieee"
    GBT7714 = "gbt7714"
    CHICAGO = "chicago"
    MLA = "mla"


class ExportFormat(StrEnum):
    """导出格式"""

    MARKDOWN = "markdown"
    WORD = "word"
    LATEX = "latex"
    PDF = "pdf"
    HTML = "html"
    EXCEL = "excel"
    CSV = "csv"
    BIBTEX = "bibtex"
    RIS = "ris"
    SVG = "svg"
    PNG = "png"
