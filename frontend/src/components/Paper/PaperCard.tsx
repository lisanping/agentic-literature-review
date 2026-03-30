import { Tag, Typography, Space, Tooltip } from 'antd';
import { FileTextOutlined, FilePdfOutlined } from '@ant-design/icons';
import type { ProjectPaperResponse } from '@/types';
import QualityBadge from '@/components/Analysis/QualityBadge';

const { Text, Paragraph } = Typography;

interface PaperCardProps {
    item: ProjectPaperResponse;
    /** 是否选中 */
    selected?: boolean;
    /** 点击回调 */
    onClick?: () => void;
}

/** 相关度圆点 */
function RelevanceDots({ score }: { score: number | null }) {
    if (score === null) return null;
    const filled = Math.round((score / 100) * 5);
    return (
        <Tooltip title={`相关度: ${score}`}>
            <span style={{ letterSpacing: 1, fontSize: 10 }}>
                {'●'.repeat(filled)}
                {'○'.repeat(5 - filled)}
            </span>
        </Tooltip>
    );
}

export default function PaperCard({ item, selected, onClick }: PaperCardProps) {
    const { paper } = item;
    const authors =
        paper.authors.length > 3
            ? `${paper.authors.slice(0, 2).join(', ')} et al.`
            : paper.authors.join(', ');

    return (
        <div
            onClick={onClick}
            style={{
                padding: '10px 12px',
                borderRadius: 6,
                border: `1px solid ${selected ? '#1677ff' : '#f0f0f0'}`,
                background: selected ? '#e6f4ff' : '#fff',
                cursor: onClick ? 'pointer' : 'default',
                marginBottom: 6,
                transition: 'all 0.2s',
            }}
        >
            {/* 标题行 */}
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                {paper.pdf_available ? (
                    <FilePdfOutlined style={{ color: '#52c41a', marginTop: 3 }} />
                ) : (
                    <FileTextOutlined style={{ color: '#999', marginTop: 3 }} />
                )}
                <div style={{ flex: 1, minWidth: 0 }}>
                    <Text strong style={{ fontSize: 13, display: 'block' }}>
                        {paper.title}
                    </Text>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                        {authors}
                    </Text>
                </div>
            </div>

            {/* 元信息行 */}
            <Space size={[8, 4]} wrap style={{ marginTop: 6 }}>
                {paper.year && <Tag>{paper.year}</Tag>}
                {paper.venue && (
                    <Tag color="blue" style={{ maxWidth: 150, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {paper.venue}
                    </Tag>
                )}
                <Text type="secondary" style={{ fontSize: 12 }}>
                    被引: {paper.citation_count}
                </Text>
                <Tag color={paper.pdf_available ? 'green' : 'default'}>
                    {paper.pdf_available ? '📄 全文' : '📋 仅摘要'}
                </Tag>
                <RelevanceDots score={item.relevance_rank} />
                <QualityBadge score={item.paper.analysis?.quality_score ?? null} />
            </Space>

            {/* 摘要 (折叠) */}
            {paper.abstract && (
                <Paragraph
                    type="secondary"
                    style={{ fontSize: 12, marginTop: 6, marginBottom: 0 }}
                    ellipsis={{ rows: 2, expandable: true, symbol: '展开' }}
                >
                    {paper.abstract}
                </Paragraph>
            )}
        </div>
    );
}
