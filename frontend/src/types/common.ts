/** 分页响应 — 对齐后端 PaginatedResponse */
export interface PaginatedResponse<T> {
    items: T[];
    total: number;
    page: number;
    size: number;
    pages: number;
}

/** 对话消息类型 */
export type MessageRole = 'system' | 'user' | 'agent';

/** 对话消息 */
export interface ChatMessage {
    id: string;
    role: MessageRole;
    content: string;
    timestamp: string;
    /** HITL 卡片类型 (仅 role=system 时可能有值) */
    hitlType?: 'search_review' | 'outline_review' | 'draft_review';
    /** HITL 关联数据 */
    hitlData?: Record<string, unknown>;
    /** agent 名称 (仅 role=agent 时有值) */
    agentName?: string;
    /** 是否可折叠 */
    collapsible?: boolean;
}

/** SSE 事件 */
export interface SSEEvent {
    id: string;
    event: string;
    data: Record<string, unknown>;
}

/** Agent 进度 */
export interface AgentProgress {
    name: string;
    current: number;
    total: number;
    percentage: number;
}

/** Token 使用情况 */
export interface TokenUsage {
    total: number;
    budget: number | null;
    cost: number;
}
