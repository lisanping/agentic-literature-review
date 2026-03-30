import { Tag, Space, Typography } from 'antd';
import {
    SearchOutlined,
    ReadOutlined,
    EditOutlined,
    ExportOutlined,
    CheckCircleOutlined,
    SyncOutlined,
    ClockCircleOutlined,
} from '@ant-design/icons';
import type { AgentProgress } from '@/types';

const { Text } = Typography;

interface AgentStatusProps {
    progress: AgentProgress | null;
    phase: string | null;
}

const PHASE_CONFIG: Record<string, { icon: React.ReactNode; label: string }> = {
    searching: { icon: <SearchOutlined />, label: '检索中' },
    search_review: { icon: <ClockCircleOutlined />, label: '等待确认' },
    reading: { icon: <ReadOutlined />, label: '精读中' },
    outlining: { icon: <EditOutlined />, label: '生成大纲' },
    outline_review: { icon: <ClockCircleOutlined />, label: '等待审阅' },
    writing: { icon: <EditOutlined />, label: '撰写中' },
    draft_review: { icon: <ClockCircleOutlined />, label: '等待审阅' },
    revising: { icon: <EditOutlined />, label: '修订中' },
    exporting: { icon: <ExportOutlined />, label: '导出中' },
    completed: { icon: <CheckCircleOutlined />, label: '已完成' },
};

export default function AgentStatus({ progress, phase }: AgentStatusProps) {
    const config = phase ? PHASE_CONFIG[phase] : null;

    if (!config && !progress) return null;

    return (
        <Space size="middle" align="center">
            {config && (
                <Tag
                    icon={
                        phase === 'completed' ? (
                            <CheckCircleOutlined />
                        ) : phase?.includes('review') ? (
                            <ClockCircleOutlined />
                        ) : (
                            <SyncOutlined spin />
                        )
                    }
                    color={
                        phase === 'completed'
                            ? 'success'
                            : phase?.includes('review')
                                ? 'warning'
                                : 'processing'
                    }
                >
                    {config.label}
                </Tag>
            )}
            {progress && progress.total > 0 && (
                <Text type="secondary" style={{ fontSize: 13 }}>
                    {progress.name} {progress.current}/{progress.total} ({progress.percentage}%)
                </Text>
            )}
        </Space>
    );
}
