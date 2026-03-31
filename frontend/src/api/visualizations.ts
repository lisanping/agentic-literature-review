import apiClient from './client';
import type { GraphData } from '@/types/visualization';

/** 获取项目的知识图谱数据 (从 analysis result 构建) */
export function getGraphData(projectId: string) {
    return apiClient.get<GraphData>(
        `/api/v1/projects/${encodeURIComponent(projectId)}/visualizations/graph`,
    );
}

/** 获取项目的时间线数据 */
export function getTimelineData(projectId: string) {
    return apiClient.get(
        `/api/v1/projects/${encodeURIComponent(projectId)}/visualizations/timeline`,
    );
}

/** 获取项目的趋势数据 */
export function getTrendsData(projectId: string) {
    return apiClient.get(
        `/api/v1/projects/${encodeURIComponent(projectId)}/visualizations/trends`,
    );
}
