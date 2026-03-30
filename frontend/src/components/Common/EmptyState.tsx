import { Result, Button, Space, Typography } from 'antd';
import {
    ExclamationCircleOutlined,
    SearchOutlined,
    WarningOutlined,
    DollarOutlined,
} from '@ant-design/icons';

const { Text } = Typography;

type EmptyStateType = 'source_error' | 'no_results' | 'budget_exceeded' | 'generic_error';

interface EmptyStateProps {
    type: EmptyStateType;
    message?: string;
    onRetry?: () => void;
    onModifyQuery?: () => void;
}

const CONFIG: Record<
    EmptyStateType,
    {
        icon: React.ReactNode;
        title: string;
        defaultMessage: string;
    }
> = {
    source_error: {
        icon: <WarningOutlined style={{ color: '#faad14' }} />,
        title: '数据源异常',
        defaultMessage: '部分数据源响应超时，结果可能不完整',
    },
    no_results: {
        icon: <SearchOutlined style={{ color: '#999' }} />,
        title: '未找到匹配的论文',
        defaultMessage: '尝试更宽泛的描述或换用英文关键词',
    },
    budget_exceeded: {
        icon: <DollarOutlined style={{ color: '#ff4d4f' }} />,
        title: 'Token 预算超限',
        defaultMessage: '当前消耗已接近或超过预算上限',
    },
    generic_error: {
        icon: <ExclamationCircleOutlined style={{ color: '#ff4d4f' }} />,
        title: '操作失败',
        defaultMessage: '发生了未知错误',
    },
};

export default function EmptyState({
    type,
    message,
    onRetry,
    onModifyQuery,
}: EmptyStateProps) {
    const config = CONFIG[type];

    return (
        <Result
            icon={config.icon}
            title={config.title}
            subTitle={
                <Text type="secondary">{message || config.defaultMessage}</Text>
            }
            extra={
                <Space>
                    {onRetry && (
                        <Button type="primary" onClick={onRetry}>
                            重试
                        </Button>
                    )}
                    {onModifyQuery && (
                        <Button onClick={onModifyQuery}>
                            修改查询
                        </Button>
                    )}
                </Space>
            }
        />
    );
}
