import apiClient from './client';

export interface UpdateSummary {
    id: string;
    created_at: string | null;
    new_papers_count: number;
    checked_at: string | null;
}

export interface UpdateDetail {
    id: string;
    project_id: string;
    created_at: string | null;
    report: string;
    new_papers: Record<string, unknown>[];
    new_papers_count: number;
    checked_at: string | null;
}

/** Trigger an update check for new literature */
export function triggerUpdate(projectId: string) {
    return apiClient.post<{ task_id: string; status: string }>(
        `/api/v1/projects/${encodeURIComponent(projectId)}/updates`,
    );
}

/** List update history for a project */
export function listUpdates(projectId: string) {
    return apiClient.get<UpdateSummary[]>(
        `/api/v1/projects/${encodeURIComponent(projectId)}/updates`,
    );
}

/** Get detailed update report */
export function getUpdateReport(projectId: string, updateId: string) {
    return apiClient.get<UpdateDetail>(
        `/api/v1/projects/${encodeURIComponent(projectId)}/updates/${encodeURIComponent(updateId)}`,
    );
}
