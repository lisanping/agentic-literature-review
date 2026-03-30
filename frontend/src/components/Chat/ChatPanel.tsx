import { useRef, useEffect } from 'react';
import { Input, Button, Space } from 'antd';
import { SendOutlined } from '@ant-design/icons';
import type { ChatMessage } from '@/types';
import MessageBubble from './MessageBubble';

const { TextArea } = Input;

interface ChatPanelProps {
    messages: ChatMessage[];
    /** 当前是否有 HITL 暂停 */
    paused: boolean;
    /** HITL 卡片渲染 (由外层注入) */
    hitlCard?: React.ReactNode;
    /** 用户发送消息 */
    onSend?: (text: string) => void;
    /** 是否禁用输入 */
    disabled?: boolean;
}

export default function ChatPanel({
    messages,
    paused,
    hitlCard,
    onSend,
    disabled,
}: ChatPanelProps) {
    const bottomRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<string>('');

    // 自动滚动到最新消息
    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages.length, paused]);

    const handleSend = () => {
        const text = inputRef.current.trim();
        if (!text) return;
        onSend?.(text);
        inputRef.current = '';
    };

    return (
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
            {/* 消息列表 */}
            <div style={{ flex: 1, overflow: 'auto', padding: '16px 16px 8px' }}>
                {messages.map((msg) => (
                    <MessageBubble key={msg.id} message={msg} />
                ))}

                {/* HITL 卡片 */}
                {paused && hitlCard && <div style={{ marginTop: 8 }}>{hitlCard}</div>}

                <div ref={bottomRef} />
            </div>

            {/* 输入框 */}
            <div style={{ padding: '8px 16px 16px', borderTop: '1px solid #f0f0f0' }}>
                <Space.Compact style={{ width: '100%' }}>
                    <TextArea
                        placeholder={paused ? '请先完成上方确认操作...' : '输入指令...'}
                        autoSize={{ minRows: 1, maxRows: 3 }}
                        disabled={disabled || paused}
                        onChange={(e) => {
                            inputRef.current = e.target.value;
                        }}
                        onPressEnter={(e) => {
                            if (!e.shiftKey) {
                                e.preventDefault();
                                handleSend();
                            }
                        }}
                    />
                    <Button
                        type="primary"
                        icon={<SendOutlined />}
                        onClick={handleSend}
                        disabled={disabled || paused}
                    />
                </Space.Compact>
            </div>
        </div>
    );
}
