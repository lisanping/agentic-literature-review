/** 输出类型 — 对齐后端 OutputType */
export enum OutputType {
    QUICK_BRIEF = 'quick_brief',
    ANNOTATED_BIB = 'annotated_bib',
    FULL_REVIEW = 'full_review',
    METHODOLOGY_REVIEW = 'methodology_review',
    RESEARCH_ROADMAP = 'research_roadmap',
    COMPARISON_MATRIX = 'comparison_matrix',
    GAP_REPORT = 'gap_report',
    TREND_REPORT = 'trend_report',
    KNOWLEDGE_MAP = 'knowledge_map',
    TIMELINE = 'timeline',
}

/** 项目状态 — 对齐后端 ProjectStatus */
export enum ProjectStatus {
    CREATED = 'created',
    SEARCHING = 'searching',
    SEARCH_REVIEW = 'search_review',
    READING = 'reading',
    ANALYZING = 'analyzing',
    CRITIQUING = 'critiquing',
    OUTLINING = 'outlining',
    OUTLINE_REVIEW = 'outline_review',
    WRITING = 'writing',
    DRAFT_REVIEW = 'draft_review',
    REVISING = 'revising',
    EXPORTING = 'exporting',
    COMPLETED = 'completed',
    FAILED = 'failed',
    CANCELLED = 'cancelled',
}

/** 论文数据来源 — 对齐后端 PaperSourceType */
export enum PaperSourceType {
    SEMANTIC_SCHOLAR = 'semantic_scholar',
    ARXIV = 'arxiv',
    OPENALEX = 'openalex',
    PUBMED = 'pubmed',
    CROSSREF = 'crossref',
    DBLP = 'dblp',
    CORE = 'core',
    UNPAYWALL = 'unpaywall',
    USER_UPLOAD = 'user_upload',
}

/** 引用格式 — 对齐后端 CitationStyle */
export enum CitationStyle {
    APA = 'apa',
    IEEE = 'ieee',
    GBT7714 = 'gbt7714',
    CHICAGO = 'chicago',
    MLA = 'mla',
}

/** 导出格式 — MVP 仅支持 markdown/word/bibtex/ris */
export enum ExportFormat {
    MARKDOWN = 'markdown',
    WORD = 'word',
    BIBTEX = 'bibtex',
    RIS = 'ris',
}
