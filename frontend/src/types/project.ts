import type { OutputType, ProjectStatus, CitationStyle } from './enums';

/** 创建项目请求体 — 对齐后端 ProjectCreate */
export interface ProjectCreate {
    user_query: string;
    output_types?: OutputType[];
    output_language?: string;
    citation_style?: CitationStyle;
    search_config?: Record<string, unknown>;
    token_budget?: number;
}

/** 更新项目请求体 — 对齐后端 ProjectUpdate */
export interface ProjectUpdate {
    title?: string;
    output_types?: OutputType[];
    output_language?: string;
    citation_style?: CitationStyle;
    search_config?: Record<string, unknown>;
    token_budget?: number;
}

/** 项目响应 — 对齐后端 ProjectResponse */
export interface ProjectResponse {
    id: string;
    user_id: string | null;
    title: string;
    user_query: string;
    status: ProjectStatus;
    output_types: OutputType[];
    output_language: string;
    citation_style: CitationStyle;
    paper_count: number;
    token_usage: Record<string, number> | null;
    token_budget: number | null;
    created_at: string;
    updated_at: string;
}
