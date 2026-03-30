import apiClient from './client';
import type {
    HitlFeedback,
    WorkflowStartResponse,
    WorkflowStatusResponse,
} from '@/types';

/** 启动工作流 */
export function startWorkflow(projectId: string) {
    return apiClient.post<WorkflowStartResponse>(
        `/api/v1/projects/${encodeURIComponent(projectId)}/workflow/start`,
    );
}

/** 恢复工作流 (HITL 反馈) */
export function resumeWorkflow(projectId: string, feedback: HitlFeedback) {
    return apiClient.post<WorkflowStartResponse>(
        `/api/v1/projects/${encodeURIComponent(projectId)}/workflow/resume`,
        feedback,
    );
}

/** 查询工作流状态 */
export function getWorkflowStatus(projectId: string) {
    return apiClient.get<WorkflowStatusResponse>(
        `/api/v1/projects/${encodeURIComponent(projectId)}/workflow/status`,
    );
}

/** 取消工作流 */
export function cancelWorkflow(projectId: string) {
    return apiClient.post(
        `/api/v1/projects/${encodeURIComponent(projectId)}/workflow/cancel`,
    );
}

/**
 * 获取 SSE 事件流 URL
 *
 * SSE 使用浏览器原生 EventSource，不走 Axios，
 * 此函数仅返回 URL 供 SSEClient 使用。
 */
export function getEventsUrl(projectId: string): string {
    const base = import.meta.env.VITE_API_BASE_URL || '';
    return `${base}/api/v1/projects/${encodeURIComponent(projectId)}/events`;
}
