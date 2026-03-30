import type { PaperSourceType } from './enums';

/** 论文分析结果 — 对齐后端 PaperAnalysisResponse */
export interface PaperAnalysisResponse {
    paper_id: string;
    objective: string | null;
    methodology: string | null;
    datasets: string[] | null;
    findings: string | null;
    limitations: string | null;
    method_category: string | null;
    method_details: Record<string, unknown> | null;
    key_concepts: string[] | null;
    relations: Record<string, unknown>[] | null;
    quality_score: number | null;
    relevance_score: number | null;
    analysis_depth: string;
}

/** 论文详情 — 对齐后端 PaperResponse */
export interface PaperResponse {
    id: string;
    title: string;
    authors: string[];
    year: number | null;
    venue: string | null;
    abstract: string | null;
    doi: string | null;
    s2_id: string | null;
    arxiv_id: string | null;
    citation_count: number;
    source: PaperSourceType;
    pdf_url: string | null;
    pdf_available: boolean;
    open_access: boolean;
    analysis: PaperAnalysisResponse | null;
}

/** 项目内论文关系 — 对齐后端 ProjectPaperResponse */
export interface ProjectPaperResponse {
    paper: PaperResponse;
    status: string;
    found_by: string | null;
    relevance_rank: number | null;
    added_at: string;
}
