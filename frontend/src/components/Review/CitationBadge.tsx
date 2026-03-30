import { Tooltip, Tag } from 'antd';
import { CheckCircleOutlined, ExclamationCircleOutlined } from '@ant-design/icons';
import type { CitationVerification } from '@/types';

interface CitationBadgeProps {
    verification: CitationVerification;
}

export default function CitationBadge({ verification }: CitationBadgeProps) {
    const isVerified = verification.status === 'verified';

    return (
        <Tooltip
            title={
                <div>
                    <div>{verification.title}</div>
                    {verification.doi && (
                        <div style={{ fontSize: 11, marginTop: 4 }}>DOI: {verification.doi}</div>
                    )}
                    <div style={{ fontSize: 11, marginTop: 4 }}>
                        状态: {isVerified ? '已验证' : '待确认'}
                    </div>
                </div>
            }
        >
            <Tag
                color={isVerified ? 'success' : 'warning'}
                icon={isVerified ? <CheckCircleOutlined /> : <ExclamationCircleOutlined />}
                style={{
                    fontSize: 10,
                    lineHeight: '16px',
                    padding: '0 4px',
                    marginLeft: 2,
                    cursor: 'help',
                    verticalAlign: 'super',
                }}
            >
                {isVerified ? '✓' : '?'}
            </Tag>
        </Tooltip>
    );
}
