import { Space, Tag, Typography } from 'antd';
import {
    CheckCircleOutlined,
    SyncOutlined,
    ClockCircleOutlined,
    DollarOutlined,
} from '@ant-design/icons';
import type { AgentProgress, TokenUsage } from '@/types';
import { formatTokens, tokensToCost } from '@/utils/format';

const { Text } = Typography;

interface StatusBarProps {
    /** 当前 Agent 进度 (工作流运行时显示) */
    agentProgress: AgentProgress | null;
    /** Token 使用情况 */
    tokenUsage: TokenUsage | null;
    /** 是否有活跃的工作流 */
    active: boolean;
}

function AgentStatusTag({ progress }: { progress: AgentProgress }) {
    const isComplete = progress.current >= progress.total && progress.total > 0;
    return (
        <Tag
            icon={isComplete ? <CheckCircleOutlined /> : <SyncOutlined spin />}
            color={isComplete ? 'success' : 'processing'}
        >
            {progress.name} {progress.current}/{progress.total}
        </Tag>
    );
}

export default function StatusBar({ agentProgress, tokenUsage, active }: StatusBarProps) {
    if (!active) return null;

    return (
        <div
            style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                padding: '4px 16px',
                borderTop: '1px solid #f0f0f0',
                background: '#fafafa',
                fontSize: 13,
            }}
        >
            {/* 左侧: Agent 状态 */}
            <Space size="small">
                <ClockCircleOutlined style={{ color: '#999' }} />
                {agentProgress ? (
                    <AgentStatusTag progress={agentProgress} />
                ) : (
                    <Text type="secondary">等待中...</Text>
                )}
            </Space>

            {/* 右侧: Token 消耗 */}
            {tokenUsage && (
                <Space size="small">
                    <DollarOutlined style={{ color: '#999' }} />
                    <Text type="secondary">
                        已消耗: {formatTokens(tokenUsage.total)} tokens
                        {' '}({tokensToCost(tokenUsage.total)})
                    </Text>
                    {tokenUsage.budget && (
                        <Text type="secondary">
                            / 预算: {formatTokens(tokenUsage.budget)}
                        </Text>
                    )}
                </Space>
            )}
        </div>
    );
}
