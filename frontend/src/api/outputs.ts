import apiClient from './client';
import type { ReviewOutputResponse, ExportRequest } from '@/types';

/** 获取项目输出列表 */
export function listOutputs(projectId: string) {
    return apiClient.get<ReviewOutputResponse[]>(
        `/api/v1/projects/${encodeURIComponent(projectId)}/outputs`,
    );
}

/** 获取输出详情 */
export function getOutput(projectId: string, outputId: string) {
    return apiClient.get<ReviewOutputResponse>(
        `/api/v1/projects/${encodeURIComponent(projectId)}/outputs/${encodeURIComponent(outputId)}`,
    );
}

/** 导出文件 (返回 Blob) */
export async function exportOutput(
    projectId: string,
    outputId: string,
    request: ExportRequest,
): Promise<{ blob: Blob; filename: string }> {
    const response = await apiClient.post(
        `/api/v1/projects/${encodeURIComponent(projectId)}/outputs/${encodeURIComponent(outputId)}/export`,
        request,
        { responseType: 'blob' },
    );

    // 从 Content-Disposition header 提取文件名
    const disposition = response.headers['content-disposition'] as string | undefined;
    let filename = `export.${request.format}`;
    if (disposition) {
        const match = disposition.match(/filename[^;=\n]*=["']?([^"';\n]*)["']?/);
        if (match?.[1]) {
            filename = decodeURIComponent(match[1]);
        }
    }

    return { blob: response.data as Blob, filename };
}

/** 触发浏览器下载 */
export function downloadBlob(blob: Blob, filename: string): void {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}
