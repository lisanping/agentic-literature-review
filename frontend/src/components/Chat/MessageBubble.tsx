import { Typography, Tag, Collapse } from 'antd';
import {
    RobotOutlined,
    UserOutlined,
    InfoCircleOutlined,
    WarningOutlined,
} from '@ant-design/icons';
import type { ChatMessage } from '@/types';

const { Text, Paragraph } = Typography;

interface MessageBubbleProps {
    message: ChatMessage;
}

const roleConfig = {
    system: { icon: <InfoCircleOutlined />, color: '#faad14', label: '系统' },
    agent: { icon: <RobotOutlined />, color: '#1677ff', label: 'Agent' },
    user: { icon: <UserOutlined />, color: '#52c41a', label: '用户' },
};

export default function MessageBubble({ message }: MessageBubbleProps) {
    const config = roleConfig[message.role];

    // HITL 消息不在此渲染（由 HitlCard 处理）
    if (message.hitlType) return null;

    // 警告/错误样式
    const isWarning = message.role === 'system' && message.content.includes('警告');
    const isError = message.role === 'system' && message.content.includes('错误');

    const bgColor = isError
        ? '#fff2f0'
        : isWarning
            ? '#fffbe6'
            : message.role === 'user'
                ? '#e6f4ff'
                : '#fafafa';

    const content = (
        <div
            style={{
                padding: '8px 12px',
                background: bgColor,
                borderRadius: 8,
                marginBottom: 8,
                maxWidth: message.role === 'user' ? '70%' : '100%',
                marginLeft: message.role === 'user' ? 'auto' : 0,
            }}
        >
            <div style={{ marginBottom: 4, display: 'flex', alignItems: 'center', gap: 6 }}>
                {isWarning ? (
                    <WarningOutlined style={{ color: '#faad14' }} />
                ) : (
                    <span style={{ color: config.color }}>{config.icon}</span>
                )}
                <Tag
                    color={isError ? 'error' : isWarning ? 'warning' : undefined}
                    style={{ margin: 0, fontSize: 11 }}
                >
                    {message.agentName || config.label}
                </Tag>
                <Text type="secondary" style={{ fontSize: 11 }}>
                    {new Date(message.timestamp).toLocaleTimeString()}
                </Text>
            </div>
            <Paragraph style={{ margin: 0, fontSize: 13 }}>{message.content}</Paragraph>
        </div>
    );

    if (message.collapsible && message.role === 'agent') {
        return (
            <Collapse
                ghost
                size="small"
                items={[
                    {
                        key: message.id,
                        label: (
                            <Text type="secondary" style={{ fontSize: 12 }}>
                                {message.agentName}: {message.content}
                            </Text>
                        ),
                        children: content,
                    },
                ]}
            />
        );
    }

    return content;
}
