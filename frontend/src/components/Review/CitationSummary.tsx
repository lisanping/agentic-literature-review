import { Space, Typography, Tag } from 'antd';
import { CheckCircleOutlined, ExclamationCircleOutlined } from '@ant-design/icons';
import type { CitationVerification } from '@/types';

const { Text } = Typography;

interface CitationSummaryProps {
    verifications: CitationVerification[] | null;
}

export default function CitationSummary({ verifications }: CitationSummaryProps) {
    if (!verifications || verifications.length === 0) return null;

    const verified = verifications.filter((v) => v.status === 'verified').length;
    const unverified = verifications.length - verified;

    return (
        <div
            style={{
                padding: '8px 12px',
                borderTop: '1px solid #f0f0f0',
                background: '#fafafa',
            }}
        >
            <Text strong style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
                引用验证
            </Text>
            <Space size="small">
                <Tag icon={<CheckCircleOutlined />} color="success">
                    已验证 {verified}
                </Tag>
                {unverified > 0 && (
                    <Tag icon={<ExclamationCircleOutlined />} color="warning">
                        待确认 {unverified}
                    </Tag>
                )}
            </Space>
        </div>
    );
}
