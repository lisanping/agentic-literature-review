import { Space, Typography, Progress, Tooltip } from 'antd';
import { DollarOutlined, WarningOutlined } from '@ant-design/icons';
import type { TokenUsage as TokenUsageType } from '@/types';
import { formatTokens, tokensToCost } from '@/utils/format';

const { Text } = Typography;

interface TokenUsageProps {
    usage: TokenUsageType;
}

export default function TokenUsage({ usage }: TokenUsageProps) {
    const overBudget = usage.budget !== null && usage.total > usage.budget;
    const percent =
        usage.budget !== null && usage.budget > 0
            ? Math.min(Math.round((usage.total / usage.budget) * 100), 100)
            : undefined;

    return (
        <Space direction="vertical" size={4} style={{ width: '100%' }}>
            <Space>
                <DollarOutlined style={{ color: overBudget ? '#ff4d4f' : '#999' }} />
                <Text type={overBudget ? 'danger' : 'secondary'} style={{ fontSize: 13 }}>
                    已消耗: {formatTokens(usage.total)} tokens ({tokensToCost(usage.total)})
                </Text>
                {overBudget && (
                    <Tooltip title="Token 消耗已超过预算">
                        <WarningOutlined style={{ color: '#ff4d4f' }} />
                    </Tooltip>
                )}
            </Space>
            {usage.budget !== null && (
                <>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                        预算: {formatTokens(usage.budget)} tokens
                    </Text>
                    <Progress
                        percent={percent}
                        size="small"
                        status={overBudget ? 'exception' : 'active'}
                        showInfo={false}
                    />
                </>
            )}
        </Space>
    );
}
