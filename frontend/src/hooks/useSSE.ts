import { useEffect, useRef, useCallback } from 'react';
import { SSEClient } from '@/api/sse';
import { getEventsUrl } from '@/api/workflow';
import { useWorkflowStore, createMessageId } from '@/stores/workflowStore';
import { TOKEN_COST_PER_1K } from '@/utils/constants';
import type { ProjectPaperResponse, AnalystOutput, CriticOutput } from '@/types';

/**
 * SSE 连接管理 Hook
 *
 * 监听项目的 SSE 事件流，将事件分发到 workflowStore。
 */
export function useSSE(projectId: string | undefined, enabled: boolean) {
    const clientRef = useRef<SSEClient | null>(null);

    const {
        addMessage,
        updateAgentProgress,
        setHitlState,
        setCandidatePapers,
        addCandidatePaper,
        updateTokenUsage,
        setPhase,
        setStatus,
        setAnalysisResult,
    } = useWorkflowStore();

    const handleEvent = useCallback(
        (event: string, data: Record<string, unknown>) => {
            const now = new Date().toISOString();

            switch (event) {
                case 'agent_start':
                    setPhase(data.agent as string);
                    setStatus('running');
                    updateAgentProgress({
                        name: data.agent as string,
                        current: 0,
                        total: (data.total as number) || 0,
                        percentage: 0,
                    });
                    addMessage({
                        id: createMessageId(),
                        role: 'agent',
                        content: `${data.agent} 开始工作...`,
                        timestamp: now,
                        agentName: data.agent as string,
                        collapsible: true,
                    });
                    break;

                case 'agent_complete':
                    updateAgentProgress({
                        name: data.agent as string,
                        current: (data.total as number) || 0,
                        total: (data.total as number) || 0,
                        percentage: 100,
                    });
                    addMessage({
                        id: createMessageId(),
                        role: 'agent',
                        content: `${data.agent} 已完成`,
                        timestamp: now,
                        agentName: data.agent as string,
                        collapsible: true,
                    });
                    break;

                case 'progress':
                    updateAgentProgress({
                        name: (data.agent as string) || '',
                        current: (data.current as number) || 0,
                        total: (data.total as number) || 0,
                        percentage:
                            (data.total as number) > 0
                                ? Math.round(
                                    ((data.current as number) / (data.total as number)) * 100,
                                )
                                : 0,
                    });
                    break;

                case 'paper_found': {
                    const papers = data.papers as ProjectPaperResponse[] | undefined;
                    if (papers) {
                        setCandidatePapers(papers);
                    } else if (data.paper) {
                        addCandidatePaper(data.paper as ProjectPaperResponse);
                    }
                    break;
                }

                case 'paper_read':
                    addMessage({
                        id: createMessageId(),
                        role: 'agent',
                        content: `已精读: ${data.title || '论文'}`,
                        timestamp: now,
                        agentName: 'Reader',
                        collapsible: true,
                    });
                    break;

                case 'hitl_pause':
                    setHitlState(
                        data.hitl_type as 'search_review' | 'outline_review' | 'draft_review',
                        data,
                    );
                    addMessage({
                        id: createMessageId(),
                        role: 'system',
                        content: '',
                        timestamp: now,
                        hitlType: data.hitl_type as 'search_review' | 'outline_review' | 'draft_review',
                        hitlData: data,
                    });
                    break;

                case 'token_update': {
                    const total = (data.total_tokens as number) || 0;
                    updateTokenUsage({
                        total,
                        cost: (total / 1000) * TOKEN_COST_PER_1K,
                    });
                    break;
                }

                case 'warning':
                    addMessage({
                        id: createMessageId(),
                        role: 'system',
                        content: (data.message as string) || '发生警告',
                        timestamp: now,
                    });
                    break;

                case 'error':
                    setStatus('error');
                    addMessage({
                        id: createMessageId(),
                        role: 'system',
                        content: (data.message as string) || '发生错误',
                        timestamp: now,
                    });
                    break;

                case 'complete':
                    setStatus('completed');
                    setPhase('completed');
                    addMessage({
                        id: createMessageId(),
                        role: 'system',
                        content: '工作流已完成！点击查看综述结果。',
                        timestamp: now,
                    });
                    break;

                case 'analyze_complete':
                    setAnalysisResult({
                        analyst: data as unknown as AnalystOutput,
                    });
                    addMessage({
                        id: createMessageId(),
                        role: 'agent',
                        content: '分析完成：主题聚类、方法对比、趋势分析已生成',
                        timestamp: now,
                        agentName: 'Analyst',
                        collapsible: true,
                    });
                    break;

                case 'critique_complete':
                    setAnalysisResult({
                        critic: data as unknown as CriticOutput,
                    });
                    addMessage({
                        id: createMessageId(),
                        role: 'agent',
                        content: '评审完成：质量评估、矛盾检测、研究空白已生成',
                        timestamp: now,
                        agentName: 'Critic',
                        collapsible: true,
                    });
                    break;
            }
        },
        [
            addMessage,
            updateAgentProgress,
            setHitlState,
            setCandidatePapers,
            addCandidatePaper,
            updateTokenUsage,
            setPhase,
            setStatus,
            setAnalysisResult,
        ],
    );

    useEffect(() => {
        if (!projectId || !enabled) return;

        const url = getEventsUrl(projectId);
        const client = new SSEClient(url, {
            onEvent: handleEvent,
            onOpen: () => setStatus('running'),
            onError: () => {
                // SSEClient handles retry internally
            },
            onClose: () => {
                // connection closed
            },
        });

        client.connect();
        clientRef.current = client;

        return () => {
            client.close();
            clientRef.current = null;
        };
    }, [projectId, enabled, handleEvent, setStatus]);

    return {
        close: () => clientRef.current?.close(),
        isConnected: clientRef.current?.isConnected ?? false,
    };
}
