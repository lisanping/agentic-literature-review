import { Card, Typography, Space } from 'antd';
import { ThunderboltOutlined } from '@ant-design/icons';
import { formatTokens, tokensToCost } from '@/utils/format';

const { Text } = Typography;

interface CostEstimateProps {
    /** 预估 Token 数 */
    estimatedTokens: number;
    /** 论文数量 */
    paperCount: number;
}

export default function CostEstimate({ estimatedTokens, paperCount }: CostEstimateProps) {
    return (
        <Card size="small" style={{ marginBottom: 12, background: '#f6ffed', borderColor: '#b7eb8f' }}>
            <Space direction="vertical" size={2}>
                <Space>
                    <ThunderboltOutlined style={{ color: '#52c41a' }} />
                    <Text strong style={{ fontSize: 13 }}>
                        预估消耗
                    </Text>
                </Space>
                <Text type="secondary" style={{ fontSize: 12 }}>
                    精读 {paperCount} 篇 ≈ {formatTokens(estimatedTokens)} tokens (
                    {tokensToCost(estimatedTokens)})
                </Text>
            </Space>
        </Card>
    );
}
