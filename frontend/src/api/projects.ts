import apiClient from './client';
import type { ProjectCreate, ProjectUpdate, ProjectResponse, PaginatedResponse } from '@/types';

/** 创建项目 */
export function createProject(data: ProjectCreate) {
    return apiClient.post<ProjectResponse>('/api/v1/projects', data);
}

/** 获取项目列表 */
export function listProjects(params?: { status?: string; page?: number; size?: number }) {
    return apiClient.get<PaginatedResponse<ProjectResponse>>('/api/v1/projects', { params });
}

/** 获取项目详情 */
export function getProject(projectId: string) {
    return apiClient.get<ProjectResponse>(`/api/v1/projects/${encodeURIComponent(projectId)}`);
}

/** 更新项目 */
export function updateProject(projectId: string, data: ProjectUpdate) {
    return apiClient.patch<ProjectResponse>(
        `/api/v1/projects/${encodeURIComponent(projectId)}`,
        data,
    );
}

/** 删除项目 (软删除) */
export function deleteProject(projectId: string) {
    return apiClient.delete(`/api/v1/projects/${encodeURIComponent(projectId)}`);
}
