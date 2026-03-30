/** HITL 反馈请求体 — 对齐后端 HitlFeedback */
export interface HitlFeedback {
    hitl_type: 'search_review' | 'outline_review' | 'draft_review';
    selected_paper_ids?: string[];
    additional_query?: string;
    approved_outline?: Record<string, unknown>;
    revision_instructions?: string;
    approved?: boolean;
}

/** 工作流启动响应 — 对齐后端 WorkflowStartResponse */
export interface WorkflowStartResponse {
    task_id: string;
    status: string;
}

/** 工作流状态响应 — 对齐后端 WorkflowStatusResponse */
export interface WorkflowStatusResponse {
    project_id: string;
    phase: string | null;
    status: string;
    progress: Record<string, unknown> | null;
    token_usage: Record<string, number> | null;
}

/** 导出请求体 — 对齐后端 ExportRequest */
export interface ExportRequest {
    format: 'markdown' | 'word' | 'bibtex' | 'ris';
}
