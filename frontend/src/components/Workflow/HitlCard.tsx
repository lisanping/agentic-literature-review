import { useState } from 'react';
import { Card, Button, Space, Input, Typography, Tree } from 'antd';
import {
    CheckOutlined,
    EditOutlined,
    ReloadOutlined,
} from '@ant-design/icons';
import type { HitlFeedback, ProjectPaperResponse } from '@/types';
import PaperList from '@/components/Paper/PaperList';
import CostEstimate from './CostEstimate';

const { TextArea } = Input;
const { Title, Text, Paragraph } = Typography;

interface HitlCardProps {
    type: 'search_review' | 'outline_review' | 'draft_review';
    data: Record<string, unknown>;
    /** 候选论文 (search_review 时使用) */
    candidatePapers?: ProjectPaperResponse[];
    /** 提交 HITL 反馈 */
    onSubmit: (feedback: HitlFeedback) => void;
    /** 提交中 */
    loading?: boolean;
}

/** 检索确认 HITL */
function SearchReview({
    candidatePapers = [],
    onSubmit,
    loading,
}: Omit<HitlCardProps, 'type'>) {
    const [selectedIds, setSelectedIds] = useState<string[]>(
        candidatePapers.map((p) => p.paper.id),
    );
    const [additionalQuery, setAdditionalQuery] = useState('');

    const estimatedTokens = selectedIds.length * 8000; // 粗略估算

    return (
        <Card
            title="🔍 检索结果确认"
            size="small"
            styles={{ header: { background: '#e6f4ff' } }}
        >
            <Text type="secondary" style={{ display: 'block', marginBottom: 8 }}>
                请确认以下候选论文，取消勾选不需要的论文：
            </Text>

            <PaperList
                papers={candidatePapers}
                selectable
                selectedIds={selectedIds}
                onSelectionChange={setSelectedIds}
                showFilter
            />

            <CostEstimate estimatedTokens={estimatedTokens} paperCount={selectedIds.length} />

            <Input
                placeholder="追加搜索词（可选）"
                value={additionalQuery}
                onChange={(e) => setAdditionalQuery(e.target.value)}
                style={{ marginBottom: 12 }}
            />

            <Button
                type="primary"
                icon={<CheckOutlined />}
                loading={loading}
                onClick={() =>
                    onSubmit({
                        hitl_type: 'search_review',
                        selected_paper_ids: selectedIds,
                        additional_query: additionalQuery || undefined,
                    })
                }
                disabled={selectedIds.length === 0}
                block
            >
                确认并继续 ({selectedIds.length} 篇)
            </Button>
        </Card>
    );
}

/** 将大纲 JSON 转为 Tree 数据 */
function outlineToTreeData(outline: Record<string, unknown>): { title: string; key: string; children?: { title: string; key: string }[] }[] {
    const sections = (outline.sections as { title: string; subsections?: { title: string }[] }[]) || [];
    return sections.map((section, i) => ({
        title: section.title,
        key: `${i}`,
        children: section.subsections?.map((sub, j) => ({
            title: sub.title,
            key: `${i}-${j}`,
        })),
    }));
}

/** 大纲审阅 HITL */
function OutlineReview({ data, onSubmit, loading }: Omit<HitlCardProps, 'type' | 'candidatePapers'>) {
    const [instructions, setInstructions] = useState('');
    const outline = (data.outline as Record<string, unknown>) || {};
    const treeData = outlineToTreeData(outline);

    return (
        <Card
            title="📝 大纲审阅"
            size="small"
            styles={{ header: { background: '#f6ffed' } }}
        >
            <Text type="secondary" style={{ display: 'block', marginBottom: 8 }}>
                请审阅综述大纲，确认或提出修改意见：
            </Text>

            {typeof outline.title === 'string' && (
                <Title level={5} style={{ marginBottom: 8 }}>
                    {outline.title}
                </Title>
            )}

            <Tree treeData={treeData} defaultExpandAll selectable={false} style={{ marginBottom: 12 }} />

            <TextArea
                placeholder="修改意见（可选，如：合并第 3、4 章，增加一节'临床应用案例'）"
                autoSize={{ minRows: 2, maxRows: 4 }}
                value={instructions}
                onChange={(e) => setInstructions(e.target.value)}
                style={{ marginBottom: 12 }}
            />

            <Space>
                <Button
                    type="primary"
                    icon={<CheckOutlined />}
                    loading={loading}
                    onClick={() =>
                        onSubmit({
                            hitl_type: 'outline_review',
                            approved_outline: outline,
                            revision_instructions: instructions || undefined,
                        })
                    }
                >
                    {instructions ? '提交修改并继续' : '确认大纲'}
                </Button>
                <Button
                    icon={<ReloadOutlined />}
                    loading={loading}
                    onClick={() =>
                        onSubmit({
                            hitl_type: 'outline_review',
                            revision_instructions: '请重新生成大纲',
                        })
                    }
                >
                    重新生成
                </Button>
            </Space>
        </Card>
    );
}

/** 初稿审阅 HITL */
function DraftReview({ data, onSubmit, loading }: Omit<HitlCardProps, 'type' | 'candidatePapers'>) {
    const [instructions, setInstructions] = useState('');
    const content = (data.content as string) || '';

    return (
        <Card
            title="📖 初稿审阅"
            size="small"
            styles={{ header: { background: '#fff7e6' } }}
        >
            <Text type="secondary" style={{ display: 'block', marginBottom: 8 }}>
                请审阅综述初稿，通过或提出修改意见：
            </Text>

            <div
                style={{
                    maxHeight: 300,
                    overflow: 'auto',
                    padding: 12,
                    background: '#fafafa',
                    borderRadius: 6,
                    marginBottom: 12,
                    fontSize: 13,
                    lineHeight: 1.8,
                }}
            >
                <Paragraph>{content || '（初稿内容加载中...）'}</Paragraph>
            </div>

            <TextArea
                placeholder="修改意见（可选，如：扩展方法A部分的细节、改为更批判性的写作风格）"
                autoSize={{ minRows: 2, maxRows: 4 }}
                value={instructions}
                onChange={(e) => setInstructions(e.target.value)}
                style={{ marginBottom: 12 }}
            />

            <Space>
                <Button
                    type="primary"
                    icon={<CheckOutlined />}
                    loading={loading}
                    onClick={() =>
                        onSubmit({
                            hitl_type: 'draft_review',
                            approved: true,
                            revision_instructions: instructions || undefined,
                        })
                    }
                >
                    {instructions ? '提交修改' : '通过初稿'}
                </Button>
                <Button
                    icon={<EditOutlined />}
                    loading={loading}
                    onClick={() =>
                        onSubmit({
                            hitl_type: 'draft_review',
                            approved: false,
                            revision_instructions: instructions || '请修改',
                        })
                    }
                    disabled={!instructions}
                >
                    要求修改
                </Button>
            </Space>
        </Card>
    );
}

export default function HitlCard(props: HitlCardProps) {
    const { type, ...rest } = props;

    switch (type) {
        case 'search_review':
            return <SearchReview {...rest} />;
        case 'outline_review':
            return <OutlineReview {...rest} />;
        case 'draft_review':
            return <DraftReview {...rest} />;
        default:
            return null;
    }
}
