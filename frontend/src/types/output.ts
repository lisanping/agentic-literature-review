import type { OutputType, CitationStyle } from './enums';

/** 引用验证条目 */
export interface CitationVerification {
    reference_index: number;
    status: 'verified' | 'unverified';
    title: string;
    doi: string | null;
}

/** 综述输出详情 — 对齐后端 ReviewOutputResponse */
export interface ReviewOutputResponse {
    id: string;
    project_id: string;
    output_type: OutputType;
    title: string | null;
    outline: Record<string, unknown> | null;
    content: string | null;
    structured_data: Record<string, unknown> | null;
    references: Record<string, unknown>[] | null;
    version: number;
    language: string;
    citation_style: CitationStyle;
    writing_style: string | null;
    citation_verification: CitationVerification[] | null;
    export_formats: string[] | null;
    created_at: string;
    updated_at: string;
}
