import { useCallback, useState } from 'react';
import { useWorkflowStore, createMessageId } from '@/stores/workflowStore';
import * as workflowApi from '@/api/workflow';
import type { HitlFeedback } from '@/types';
import { useSSE } from './useSSE';

/**
 * 工作流控制 Hook
 *
 * 封装 start / resume / cancel 操作，
 * 自动管理 SSE 连接生命周期。
 */
export function useWorkflow(projectId: string | undefined) {
    const {
        status,
        taskId,
        setTaskId,
        setStatus,
        addMessage,
        clearHitlState,
        reset,
    } = useWorkflowStore();

    const [sseEnabled, setSseEnabled] = useState(false);

    // SSE 连接（仅在 sseEnabled 为 true 时建立）
    useSSE(projectId, sseEnabled);

    /** 启动工作流 */
    const startWorkflow = useCallback(async () => {
        if (!projectId) return;
        try {
            const res = await workflowApi.startWorkflow(projectId);
            setTaskId(res.data.task_id);
            setStatus('running');
            setSseEnabled(true);
            addMessage({
                id: createMessageId(),
                role: 'system',
                content: '工作流已启动，正在检索文献...',
                timestamp: new Date().toISOString(),
            });
        } catch {
            setStatus('error');
        }
    }, [projectId, setTaskId, setStatus, setSseEnabled, addMessage]);

    /** 恢复工作流（HITL 反馈） */
    const resumeWorkflow = useCallback(
        async (feedback: HitlFeedback) => {
            if (!projectId) return;
            try {
                clearHitlState();
                const res = await workflowApi.resumeWorkflow(projectId, feedback);
                setTaskId(res.data.task_id);
                setStatus('running');
                setSseEnabled(true);
            } catch {
                setStatus('error');
            }
        },
        [projectId, clearHitlState, setTaskId, setStatus, setSseEnabled],
    );

    /** 取消工作流 */
    const cancelWorkflow = useCallback(async () => {
        if (!projectId) return;
        try {
            await workflowApi.cancelWorkflow(projectId);
            setStatus('cancelled');
            setSseEnabled(false);
            addMessage({
                id: createMessageId(),
                role: 'system',
                content: '工作流已取消',
                timestamp: new Date().toISOString(),
            });
        } catch {
            // error handled by interceptor
        }
    }, [projectId, setStatus, setSseEnabled, addMessage]);

    /** 查询工作流状态 */
    const fetchStatus = useCallback(async () => {
        if (!projectId) return null;
        const res = await workflowApi.getWorkflowStatus(projectId);
        return res.data;
    }, [projectId]);

    /** 重置 (切换项目时) */
    const resetWorkflow = useCallback(() => {
        setSseEnabled(false);
        reset();
    }, [setSseEnabled, reset]);

    return {
        status,
        taskId,
        startWorkflow,
        resumeWorkflow,
        cancelWorkflow,
        fetchStatus,
        resetWorkflow,
        enableSSE: () => setSseEnabled(true),
    };
}
