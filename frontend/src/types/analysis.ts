/** Analysis types — Analyst + Critic output structures (v0.3) */

// ── Analyst Output Types ──

/** 主题聚类 */
export interface TopicCluster {
    id: string;
    name: string;
    paper_ids: string[];
    paper_count: number;
    key_terms: string[];
    summary?: string;
}

/** 对比矩阵维度 */
export interface ComparisonDimension {
    key: string;
    label: string;
    unit?: string;
}

/** 对比矩阵方法条目 */
export interface ComparisonMethod {
    name: string;
    category: string;
    paper_id?: string;
    values: Record<string, number | string | null>;
}

/** 对比矩阵 */
export interface ComparisonMatrix {
    title: string;
    dimensions: ComparisonDimension[];
    methods: ComparisonMethod[];
    narrative: string;
}

/** 时间线条目 */
export interface TimelineEntry {
    year: number;
    paper_count: number;
    paper_ids: string[];
    milestone: string | null;
    key_event: string | null;
}

/** 年度趋势 */
export interface YearTrend {
    year: number;
    count: number;
    citations_sum: number;
}

/** 主题趋势 */
export interface TopicTrend {
    topic: string;
    trend: 'rising' | 'stable' | 'declining';
    yearly_counts: { year: number; count: number }[];
}

/** 趋势分析 */
export interface ResearchTrends {
    by_year: YearTrend[];
    by_topic: TopicTrend[];
    emerging_topics: string[];
    narrative: string;
}

/** Analyst 完整输出 */
export interface AnalystOutput {
    topic_clusters: TopicCluster[];
    comparison_matrix: ComparisonMatrix;
    timeline: TimelineEntry[];
    research_trends: ResearchTrends;
}

// ── Critic Output Types ──

/** 质量评估 */
export interface QualityAssessment {
    paper_id: string;
    quality_score: number;
    justification: string;
    strengths: string[];
    weaknesses: string[];
}

/** 矛盾检测 */
export interface Contradiction {
    id: string;
    paper_a_id: string;
    paper_b_id: string;
    topic: string;
    claim_a: string;
    claim_b: string;
    possible_reconciliation: string;
    severity: 'minor' | 'moderate' | 'major';
}

/** 研究空白 */
export interface ResearchGap {
    id: string;
    description: string;
    evidence: string[];
    priority: 'high' | 'medium' | 'low';
    related_cluster_ids: string[];
    suggested_direction: string;
    search_query?: string;
}

/** Critic 完整输出 */
export interface CriticOutput {
    quality_assessments: QualityAssessment[];
    contradictions: Contradiction[];
    research_gaps: ResearchGap[];
    limitation_summary: string;
}

/** 分析结果聚合（存储在 store 中） */
export interface AnalysisResult {
    analyst?: AnalystOutput;
    critic?: CriticOutput;
}
