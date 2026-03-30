import apiClient from './client';
import type { PaperResponse, ProjectPaperResponse, PaginatedResponse } from '@/types';

/** 获取项目论文列表 */
export function listProjectPapers(
    projectId: string,
    params?: { status?: string; page?: number; size?: number },
) {
    return apiClient.get<PaginatedResponse<ProjectPaperResponse>>(
        `/api/v1/projects/${encodeURIComponent(projectId)}/papers`,
        { params },
    );
}

/** 更新项目内论文状态 */
export function updatePaperStatus(projectId: string, paperId: string, status: string) {
    return apiClient.patch<ProjectPaperResponse>(
        `/api/v1/projects/${encodeURIComponent(projectId)}/papers/${encodeURIComponent(paperId)}`,
        { status },
    );
}

/** 获取论文详情 */
export function getPaper(paperId: string) {
    return apiClient.get<PaperResponse>(`/api/v1/papers/${encodeURIComponent(paperId)}`);
}

/** 上传文件 (PDF / BibTeX / RIS) */
export function uploadPaperFile(projectId: string, file: File) {
    const formData = new FormData();
    formData.append('file', file);
    return apiClient.post<PaperResponse[]>(
        `/api/v1/projects/${encodeURIComponent(projectId)}/papers/upload`,
        formData,
        { headers: { 'Content-Type': 'multipart/form-data' } },
    );
}
