import { OutputType, ProjectStatus, CitationStyle, ExportFormat } from '@/types/enums';

/** 输出类型标签映射 */
export const OUTPUT_TYPE_LABELS: Record<string, string> = {
    [OutputType.QUICK_BRIEF]: '快速摘要',
    [OutputType.ANNOTATED_BIB]: '注释文献列表',
    [OutputType.FULL_REVIEW]: '完整综述',
    [OutputType.METHODOLOGY_REVIEW]: '方法论综述',
    [OutputType.RESEARCH_ROADMAP]: '研究路线图',
    [OutputType.COMPARISON_MATRIX]: '对比矩阵',
    [OutputType.GAP_REPORT]: '研究空白报告',
    [OutputType.TREND_REPORT]: '趋势报告',
    [OutputType.KNOWLEDGE_MAP]: '知识图谱',
    [OutputType.TIMELINE]: '时间线',
};

/** 项目状态标签映射 */
export const PROJECT_STATUS_LABELS: Record<string, string> = {
    [ProjectStatus.CREATED]: '已创建',
    [ProjectStatus.SEARCHING]: '检索中',
    [ProjectStatus.SEARCH_REVIEW]: '等待检索确认',
    [ProjectStatus.READING]: '精读中',
    [ProjectStatus.ANALYZING]: '分析中',
    [ProjectStatus.CRITIQUING]: '评审中',
    [ProjectStatus.OUTLINING]: '生成大纲',
    [ProjectStatus.OUTLINE_REVIEW]: '等待大纲审阅',
    [ProjectStatus.WRITING]: '撰写中',
    [ProjectStatus.DRAFT_REVIEW]: '等待初稿审阅',
    [ProjectStatus.REVISING]: '修订中',
    [ProjectStatus.EXPORTING]: '导出中',
    [ProjectStatus.COMPLETED]: '已完成',
    [ProjectStatus.FAILED]: '失败',
    [ProjectStatus.CANCELLED]: '已取消',
};

/** 项目状态颜色映射 (Ant Design Badge 颜色) */
export const PROJECT_STATUS_COLORS: Record<string, string> = {
    [ProjectStatus.CREATED]: 'default',
    [ProjectStatus.SEARCHING]: 'processing',
    [ProjectStatus.SEARCH_REVIEW]: 'warning',
    [ProjectStatus.READING]: 'processing',
    [ProjectStatus.ANALYZING]: 'processing',
    [ProjectStatus.CRITIQUING]: 'processing',
    [ProjectStatus.OUTLINING]: 'processing',
    [ProjectStatus.OUTLINE_REVIEW]: 'warning',
    [ProjectStatus.WRITING]: 'processing',
    [ProjectStatus.DRAFT_REVIEW]: 'warning',
    [ProjectStatus.REVISING]: 'processing',
    [ProjectStatus.EXPORTING]: 'processing',
    [ProjectStatus.COMPLETED]: 'success',
    [ProjectStatus.FAILED]: 'error',
    [ProjectStatus.CANCELLED]: 'default',
};

/** 引用格式标签映射 */
export const CITATION_STYLE_LABELS: Record<string, string> = {
    [CitationStyle.APA]: 'APA',
    [CitationStyle.IEEE]: 'IEEE',
    [CitationStyle.GBT7714]: 'GB/T 7714',
    [CitationStyle.CHICAGO]: 'Chicago',
    [CitationStyle.MLA]: 'MLA',
};

/** 导出格式标签映射 */
export const EXPORT_FORMAT_LABELS: Record<string, string> = {
    [ExportFormat.MARKDOWN]: 'Markdown (.md)',
    [ExportFormat.WORD]: 'Word (.docx)',
    [ExportFormat.BIBTEX]: 'BibTeX (.bib)',
    [ExportFormat.RIS]: 'RIS (.ris)',
};

/** MVP 支持的输出类型 */
export const MVP_OUTPUT_TYPES = [
    OutputType.QUICK_BRIEF,
    OutputType.ANNOTATED_BIB,
    OutputType.FULL_REVIEW,
    OutputType.METHODOLOGY_REVIEW,
    OutputType.GAP_REPORT,
    OutputType.TREND_REPORT,
    OutputType.RESEARCH_ROADMAP,
] as const;

/** GPT-4o 每千 Token 价格 (美元) — 用于前端费用估算 */
export const TOKEN_COST_PER_1K = 0.0025;
