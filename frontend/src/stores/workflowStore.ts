import { create } from 'zustand';
import type { ChatMessage, AgentProgress, TokenUsage, ProjectPaperResponse, AnalysisResult } from '@/types';

type HitlType = 'search_review' | 'outline_review' | 'draft_review' | null;

interface WorkflowState {
    /** 当前阶段: searching / reading / writing 等 */
    phase: string | null;
    /** 运行状态: idle / running / paused / completed / error */
    status: string;
    /** Celery task ID */
    taskId: string | null;

    /** 对话消息列表 */
    messages: ChatMessage[];

    /** Agent 进度 */
    agentProgress: AgentProgress | null;

    /** HITL 状态 */
    hitlType: HitlType;
    hitlData: Record<string, unknown>;

    /** 候选论文 (检索确认 HITL 期间) */
    candidatePapers: ProjectPaperResponse[];

    /** Token 消耗 */
    tokenUsage: TokenUsage;

    /** 分析结果 (v0.3 Analyst + Critic) */
    analysisResult: AnalysisResult;

    // ── Actions ──

    setPhase: (phase: string | null) => void;
    setStatus: (status: string) => void;
    setTaskId: (taskId: string | null) => void;

    addMessage: (msg: ChatMessage) => void;
    updateAgentProgress: (progress: AgentProgress | null) => void;

    setHitlState: (type: HitlType, data: Record<string, unknown>) => void;
    clearHitlState: () => void;

    setCandidatePapers: (papers: ProjectPaperResponse[]) => void;
    addCandidatePaper: (paper: ProjectPaperResponse) => void;

    updateTokenUsage: (usage: Partial<TokenUsage>) => void;

    setAnalysisResult: (result: Partial<AnalysisResult>) => void;

    /** 重置全部状态 (切换项目时) */
    reset: () => void;
}

const initialState = {
    phase: null,
    status: 'idle',
    taskId: null,
    messages: [],
    agentProgress: null,
    hitlType: null as HitlType,
    hitlData: {},
    candidatePapers: [],
    tokenUsage: { total: 0, budget: null, cost: 0 } as TokenUsage,
    analysisResult: {} as AnalysisResult,
};

let msgIdCounter = 0;

/** 生成消息 ID */
export function createMessageId(): string {
    return `msg-${Date.now()}-${++msgIdCounter}`;
}

export const useWorkflowStore = create<WorkflowState>((set) => ({
    ...initialState,

    setPhase: (phase) => set({ phase }),
    setStatus: (status) => set({ status }),
    setTaskId: (taskId) => set({ taskId }),

    addMessage: (msg) =>
        set((state) => ({ messages: [...state.messages, msg] })),

    updateAgentProgress: (agentProgress) => set({ agentProgress }),

    setHitlState: (type, data) =>
        set({ hitlType: type, hitlData: data, status: 'paused' }),
    clearHitlState: () =>
        set({ hitlType: null, hitlData: {}, status: 'running' }),

    setCandidatePapers: (candidatePapers) => set({ candidatePapers }),
    addCandidatePaper: (paper) =>
        set((state) => ({
            candidatePapers: [...state.candidatePapers, paper],
        })),

    updateTokenUsage: (usage) =>
        set((state) => ({
            tokenUsage: { ...state.tokenUsage, ...usage },
        })),

    setAnalysisResult: (result) =>
        set((state) => ({
            analysisResult: { ...state.analysisResult, ...result },
        })),

    reset: () => set(initialState),
}));
