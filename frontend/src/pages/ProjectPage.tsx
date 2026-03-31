import { useEffect, useState, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Button, Typography, Space, Divider, Tabs } from 'antd';
import {
    PlayCircleOutlined,
    StopOutlined,
    FileTextOutlined,
    ExperimentOutlined,
    ShareAltOutlined,
    SyncOutlined,
} from '@ant-design/icons';
import { useProjects } from '@/hooks/useProjects';
import { useWorkflow } from '@/hooks/useWorkflow';
import { useWorkflowStore } from '@/stores/workflowStore';
import { listOutputs } from '@/api/outputs';
import { ProjectStatus } from '@/types/enums';
import type { HitlFeedback, ReviewOutputResponse } from '@/types';
import ChatPanel from '@/components/Chat/ChatPanel';
import AgentStatus from '@/components/Workflow/AgentStatus';
import ProgressBar from '@/components/Workflow/ProgressBar';
import HitlCard from '@/components/Workflow/HitlCard';
import TokenUsage from '@/components/Workflow/TokenUsage';
import PaperList from '@/components/Paper/PaperList';
import ReviewPreview from '@/components/Review/ReviewPreview';
import OutlineTree from '@/components/Review/OutlineTree';
import CitationSummary from '@/components/Review/CitationSummary';
import ExportButton from '@/components/Review/ExportButton';
import ClusterView from '@/components/Analysis/ClusterView';
import ComparisonTable from '@/components/Analysis/ComparisonTable';
import TrendChart from '@/components/Analysis/TrendChart';
import GapList from '@/components/Analysis/GapList';
import ShareDialog from '@/components/Project/ShareDialog';
import KnowledgeGraph from '@/components/Visualization/KnowledgeGraph';
import GraphControls from '@/components/Visualization/GraphControls';
import PaperDetailDrawer from '@/components/Visualization/PaperDetailDrawer';
import Loading from '@/components/Common/Loading';
import type { GraphData } from '@/types/visualization';
import { getGraphData } from '@/api/visualizations';

const { Title, Text } = Typography;

/** 当前项目是否可以启动/恢复工作流 */
function canStart(status: string): boolean {
    return [ProjectStatus.CREATED, ProjectStatus.FAILED].includes(status as ProjectStatus);
}

export default function ProjectPage() {
    const { projectId } = useParams<{ projectId: string }>();
    const navigate = useNavigate();
    const { fetchProject } = useProjects();
    const [projectLoading, setProjectLoading] = useState(true);
    const [hitlLoading, setHitlLoading] = useState(false);

    const {
        startWorkflow,
        resumeWorkflow,
        cancelWorkflow,
        resetWorkflow,
        enableSSE,
    } = useWorkflow(projectId);

    const {
        phase,
        status: wfStatus,
        messages,
        agentProgress,
        hitlType,
        hitlData,
        candidatePapers,
        tokenUsage,
        analysisResult,
    } = useWorkflowStore();

    const [project, setProject] = useState<Awaited<ReturnType<typeof fetchProject>> | null>(null);
    const [outputs, setOutputs] = useState<ReviewOutputResponse[]>([]);
    const [activeOutput, setActiveOutput] = useState<ReviewOutputResponse | null>(null);
    const [shareOpen, setShareOpen] = useState(false);
    const [graphData, setGraphData] = useState<GraphData | null>(null);
    const graphSvgRef = useRef<SVGSVGElement>(null);
    const reviewRef = useRef<HTMLDivElement>(null);

    // 加载项目详情 & 判断是否自动恢复 SSE
    useEffect(() => {
        if (!projectId) return;

        resetWorkflow();
        setProjectLoading(true);

        fetchProject(projectId)
            .then((p) => {
                setProject(p);
                // 如果项目正在执行中，自动建立 SSE
                const runningStatuses = [
                    ProjectStatus.SEARCHING,
                    ProjectStatus.READING,
                    ProjectStatus.ANALYZING,
                    ProjectStatus.OUTLINING,
                    ProjectStatus.WRITING,
                    ProjectStatus.REVISING,
                    ProjectStatus.EXPORTING,
                ];
                if (runningStatuses.includes(p.status as ProjectStatus)) {
                    enableSSE();
                }
            })
            .catch(() => {
                navigate('/');
            })
            .finally(() => setProjectLoading(false));

        return () => resetWorkflow();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [projectId]);

    // 加载输出 (项目完成时 或 工作流完成时)
    useEffect(() => {
        if (!projectId) return;
        const completed =
            project?.status === ProjectStatus.COMPLETED || wfStatus === 'completed';
        if (!completed) return;

        listOutputs(projectId).then((res) => {
            setOutputs(res.data);
            if (res.data.length > 0) {
                setActiveOutput(res.data[0]!);
            }
        });
    }, [projectId, project?.status, wfStatus]);

    // 加载知识图谱数据 (有分析结果时)
    useEffect(() => {
        if (!projectId) return;
        const hasAnalysis = analysisResult.analyst || analysisResult.critic;
        const completed =
            project?.status === ProjectStatus.COMPLETED || wfStatus === 'completed';
        if (!hasAnalysis && !completed) return;

        getGraphData(projectId)
            .then((res) => setGraphData(res.data))
            .catch(() => {
                // Graph data not available — not critical
            });
    }, [projectId, project?.status, wfStatus, analysisResult]);

    /** 大纲导航跳转 */
    const handleOutlineSelect = useCallback((headingId: string) => {
        const el = reviewRef.current?.querySelector(`#${CSS.escape(headingId)}`);
        el?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, []);

    /** 处理 HITL 提交 */
    const handleHitlSubmit = useCallback(
        async (feedback: HitlFeedback) => {
            setHitlLoading(true);
            try {
                await resumeWorkflow(feedback);
            } finally {
                setHitlLoading(false);
            }
        },
        [resumeWorkflow],
    );

    if (projectLoading) {
        return <Loading tip="加载项目..." />;
    }

    if (!project) return null;

    const isPaused = hitlType !== null;
    const isRunning = wfStatus === 'running';
    const isCompleted = wfStatus === 'completed' || project.status === ProjectStatus.COMPLETED;

    return (
        <div style={{ display: 'flex', height: '100%' }}>
            {/* ── 左侧: 对话流 ── */}
            <div
                style={{
                    flex: 1,
                    display: 'flex',
                    flexDirection: 'column',
                    borderRight: '1px solid #f0f0f0',
                    minWidth: 0,
                }}
            >
                {/* 顶部: 项目信息 + 控制按钮 */}
                <div style={{ padding: '12px 16px', borderBottom: '1px solid #f0f0f0' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div>
                            <Title level={5} style={{ margin: 0 }}>
                                {project.title || project.user_query}
                            </Title>
                            <AgentStatus progress={agentProgress} phase={phase} />
                        </div>
                        <Space>
                            {canStart(project.status) && !isRunning && (
                                <Button
                                    type="primary"
                                    icon={<PlayCircleOutlined />}
                                    onClick={startWorkflow}
                                >
                                    启动
                                </Button>
                            )}
                            {isRunning && (
                                <Button
                                    danger
                                    icon={<StopOutlined />}
                                    onClick={cancelWorkflow}
                                >
                                    取消
                                </Button>
                            )}
                            {isCompleted && activeOutput && (
                                <ExportButton
                                    projectId={project.id}
                                    outputId={activeOutput.id}
                                />
                            )}
                            {isCompleted && (
                                <Button
                                    icon={<SyncOutlined />}
                                    onClick={async () => {
                                        try {
                                            const { triggerUpdate } = await import('@/api/updates');
                                            await triggerUpdate(project.id);
                                            const { message } = await import('antd');
                                            message.success('已触发更新检查，请稍候...');
                                        } catch {
                                            const { message } = await import('antd');
                                            message.error('触发更新失败');
                                        }
                                    }}
                                >
                                    检查更新
                                </Button>
                            )}
                            <Button
                                icon={<ShareAltOutlined />}
                                onClick={() => setShareOpen(true)}
                            >
                                分享
                            </Button>
                        </Space>
                    </div>

                    {/* 进度条 */}
                    {(isRunning || isPaused || isCompleted) && <ProgressBar phase={phase} />}
                </div>

                {/* 主内容区: 完成时显示综述预览，否则显示对话面板 */}
                <div style={{ flex: 1, minHeight: 0 }}>
                    {isCompleted && activeOutput?.content ? (
                        <div ref={reviewRef} style={{ height: '100%', overflow: 'auto' }}>
                            <ReviewPreview
                                content={activeOutput.content}
                                title={activeOutput.title}
                                citationVerification={activeOutput.citation_verification}
                            />
                        </div>
                    ) : (
                        <ChatPanel
                            messages={messages}
                            paused={isPaused}
                            disabled={!isRunning}
                            hitlCard={
                                hitlType ? (
                                    <HitlCard
                                        type={hitlType}
                                        data={hitlData}
                                        candidatePapers={candidatePapers}
                                        onSubmit={handleHitlSubmit}
                                        loading={hitlLoading}
                                    />
                                ) : undefined
                            }
                        />
                    )}
                </div>
            </div>

            {/* ── 右侧: 数据面板 ── */}
            <div style={{ width: 380, flexShrink: 0, overflow: 'auto' }}>
                <Tabs
                    defaultActiveKey={isCompleted && activeOutput ? 'review' : 'papers'}
                    size="small"
                    style={{ padding: '0 12px' }}
                    items={[
                        // 综述 Tab (完成后显示)
                        ...(isCompleted && activeOutput
                            ? [
                                {
                                    key: 'review',
                                    label: (
                                        <span>
                                            <FileTextOutlined /> 综述
                                        </span>
                                    ),
                                    children: (
                                        <div>
                                            {/* 输出版本列表 */}
                                            {outputs.length > 1 && (
                                                <div style={{ padding: '8px 4px', borderBottom: '1px solid #f0f0f0' }}>
                                                    <Text type="secondary" style={{ fontSize: 12 }}>
                                                        版本:
                                                    </Text>
                                                    <Space size={4} style={{ marginLeft: 8 }}>
                                                        {outputs.map((o) => (
                                                            <Button
                                                                key={o.id}
                                                                size="small"
                                                                type={o.id === activeOutput.id ? 'primary' : 'default'}
                                                                onClick={() => setActiveOutput(o)}
                                                            >
                                                                v{o.version}
                                                            </Button>
                                                        ))}
                                                    </Space>
                                                </div>
                                            )}

                                            {/* 大纲导航 */}
                                            <OutlineTree
                                                outline={activeOutput.outline}
                                                onSelect={handleOutlineSelect}
                                            />

                                            {/* 引用验证汇总 */}
                                            <CitationSummary
                                                verifications={activeOutput.citation_verification}
                                            />
                                        </div>
                                    ),
                                },
                            ]
                            : []),
                        {
                            key: 'papers',
                            label: `论文 (${candidatePapers.length || project.paper_count})`,
                            children: (
                                <div style={{ padding: '0 4px' }}>
                                    {candidatePapers.length > 0 ? (
                                        <PaperList papers={candidatePapers} />
                                    ) : (
                                        <Text type="secondary" style={{ display: 'block', textAlign: 'center', padding: 24, fontSize: 13 }}>
                                            {isRunning ? '正在检索论文...' : '论文列表将在检索完成后显示'}
                                        </Text>
                                    )}
                                </div>
                            ),
                        },
                        // 分析 Tab (有分析数据时显示)
                        ...((analysisResult.analyst || analysisResult.critic)
                            ? [
                                {
                                    key: 'analysis',
                                    label: (
                                        <span>
                                            <ExperimentOutlined /> 分析
                                        </span>
                                    ),
                                    children: (
                                        <div style={{ padding: '8px 4px' }}>
                                            {analysisResult.analyst?.topic_clusters && (
                                                <div style={{ marginBottom: 16 }}>
                                                    <Text strong style={{ fontSize: 13, display: 'block', marginBottom: 8 }}>
                                                        主题聚类
                                                    </Text>
                                                    <ClusterView clusters={analysisResult.analyst.topic_clusters} />
                                                </div>
                                            )}

                                            {analysisResult.analyst?.comparison_matrix && (
                                                <div style={{ marginBottom: 16 }}>
                                                    <Text strong style={{ fontSize: 13, display: 'block', marginBottom: 8 }}>
                                                        方法对比
                                                    </Text>
                                                    <ComparisonTable matrix={analysisResult.analyst.comparison_matrix} />
                                                </div>
                                            )}

                                            {analysisResult.analyst?.research_trends && (
                                                <div style={{ marginBottom: 16 }}>
                                                    <Text strong style={{ fontSize: 13, display: 'block', marginBottom: 8 }}>
                                                        研究趋势
                                                    </Text>
                                                    <TrendChart trends={analysisResult.analyst.research_trends} />
                                                </div>
                                            )}

                                            {(analysisResult.critic?.research_gaps ||
                                                analysisResult.critic?.contradictions ||
                                                analysisResult.critic?.limitation_summary) && (
                                                    <div style={{ marginBottom: 16 }}>
                                                        <Text strong style={{ fontSize: 13, display: 'block', marginBottom: 8 }}>
                                                            研究空白与评审
                                                        </Text>
                                                        <GapList
                                                            gaps={analysisResult.critic?.research_gaps || []}
                                                            contradictions={analysisResult.critic?.contradictions}
                                                            limitationSummary={analysisResult.critic?.limitation_summary}
                                                        />
                                                    </div>
                                                )}
                                        </div>
                                    ),
                                },
                            ]
                            : []),
                        // 图谱 Tab (有图谱数据时显示)
                        ...(graphData && graphData.nodes.length > 0
                            ? [
                                {
                                    key: 'graph',
                                    label: '📊 图谱',
                                    children: (
                                        <div style={{ padding: '8px 4px' }}>
                                            <GraphControls
                                                clusters={graphData.clusters}
                                                svgRef={graphSvgRef}
                                            />
                                            <KnowledgeGraph
                                                data={graphData}
                                                width={460}
                                                height={400}
                                            />
                                            <PaperDetailDrawer nodes={graphData.nodes} />
                                        </div>
                                    ),
                                },
                            ]
                            : []),
                        {
                            key: 'token',
                            label: 'Token',
                            children: (
                                <div style={{ padding: '12px 4px' }}>
                                    <TokenUsage usage={tokenUsage} />
                                    <Divider />
                                    <Text type="secondary" style={{ fontSize: 12 }}>
                                        费用基于 GPT-4o 定价估算
                                    </Text>
                                </div>
                            ),
                        },
                    ]}
                />
            </div>

            {/* 分享对话框 */}
            <ShareDialog
                projectId={project.id}
                open={shareOpen}
                onClose={() => setShareOpen(false)}
            />
        </div>
    );
}
