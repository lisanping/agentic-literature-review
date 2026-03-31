import apiClient from './client';
import type { ShareCreate, ShareUpdate, ShareResponse } from '@/types/share';

/** 分享项目给用户 */
export function shareProject(projectId: string, data: ShareCreate) {
    return apiClient.post<ShareResponse>(
        `/api/v1/projects/${encodeURIComponent(projectId)}/shares`,
        data,
    );
}

/** 列出项目的所有分享 */
export function listShares(projectId: string) {
    return apiClient.get<ShareResponse[]>(
        `/api/v1/projects/${encodeURIComponent(projectId)}/shares`,
    );
}

/** 更新分享权限 */
export function updateShare(projectId: string, shareId: string, data: ShareUpdate) {
    return apiClient.patch<ShareResponse>(
        `/api/v1/projects/${encodeURIComponent(projectId)}/shares/${encodeURIComponent(shareId)}`,
        data,
    );
}

/** 撤销分享 */
export function revokeShare(projectId: string, shareId: string) {
    return apiClient.delete(
        `/api/v1/projects/${encodeURIComponent(projectId)}/shares/${encodeURIComponent(shareId)}`,
    );
}
