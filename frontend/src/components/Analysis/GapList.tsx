import { List, Tag, Typography, Space, Collapse } from 'antd';
import { WarningOutlined, ExperimentOutlined } from '@ant-design/icons';
import type { ResearchGap, Contradiction } from '@/types';

const { Text, Paragraph } = Typography;

const PRIORITY_CONFIG = {
    high: { color: 'red', label: '高' },
    medium: { color: 'orange', label: '中' },
    low: { color: 'green', label: '低' },
} as const;

interface GapListProps {
    gaps: ResearchGap[];
    contradictions?: Contradiction[];
    limitationSummary?: string;
}

/** 研究空白 + 矛盾 + 局限性列表 */
export default function GapList({ gaps, contradictions, limitationSummary }: GapListProps) {
    const hasData = gaps.length > 0 || (contradictions && contradictions.length > 0) || limitationSummary;

    if (!hasData) {
        return <Text type="secondary">暂无研究空白数据</Text>;
    }

    return (
        <div>
            {/* 研究空白 */}
            {gaps.length > 0 && (
                <div style={{ marginBottom: 16 }}>
                    <Text strong style={{ fontSize: 12, display: 'block', marginBottom: 8 }}>
                        <ExperimentOutlined /> 研究空白 ({gaps.length})
                    </Text>
                    <List
                        size="small"
                        dataSource={gaps}
                        renderItem={(gap) => {
                            const prio = PRIORITY_CONFIG[gap.priority] || PRIORITY_CONFIG.medium;
                            return (
                                <List.Item style={{ padding: '8px 0', alignItems: 'flex-start' }}>
                                    <div style={{ width: '100%' }}>
                                        <Space style={{ marginBottom: 4 }}>
                                            <Tag color={prio.color}>{prio.label}</Tag>
                                            <Text style={{ fontSize: 12 }}>{gap.description}</Text>
                                        </Space>
                                        {gap.suggested_direction && (
                                            <div style={{ marginTop: 4 }}>
                                                <Text type="secondary" style={{ fontSize: 11 }}>
                                                    💡 {gap.suggested_direction}
                                                </Text>
                                            </div>
                                        )}
                                    </div>
                                </List.Item>
                            );
                        }}
                    />
                </div>
            )}

            {/* 矛盾 */}
            {contradictions && contradictions.length > 0 && (
                <div style={{ marginBottom: 16 }}>
                    <Text strong style={{ fontSize: 12, display: 'block', marginBottom: 8 }}>
                        <WarningOutlined /> 矛盾 ({contradictions.length})
                    </Text>
                    <Collapse
                        size="small"
                        items={contradictions.map((c) => {
                            const severityColor = { minor: 'default', moderate: 'warning', major: 'error' }[c.severity] || 'default';
                            return {
                                key: c.id,
                                label: (
                                    <Space>
                                        <Tag color={severityColor as string}>{c.severity}</Tag>
                                        <Text style={{ fontSize: 12 }}>{c.topic}</Text>
                                    </Space>
                                ),
                                children: (
                                    <div style={{ fontSize: 12 }}>
                                        <div style={{ marginBottom: 4 }}>
                                            <Text type="secondary">观点 A: </Text>{c.claim_a}
                                        </div>
                                        <div style={{ marginBottom: 4 }}>
                                            <Text type="secondary">观点 B: </Text>{c.claim_b}
                                        </div>
                                        {c.possible_reconciliation && (
                                            <div>
                                                <Text type="secondary">调和: </Text>{c.possible_reconciliation}
                                            </div>
                                        )}
                                    </div>
                                ),
                            };
                        })}
                    />
                </div>
            )}

            {/* 局限性汇总 */}
            {limitationSummary && (
                <div>
                    <Text strong style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
                        📋 局限性汇总
                    </Text>
                    <Paragraph
                        type="secondary"
                        style={{ fontSize: 12 }}
                        ellipsis={{ rows: 4, expandable: true, symbol: '展开' }}
                    >
                        {limitationSummary}
                    </Paragraph>
                </div>
            )}
        </div>
    );
}
