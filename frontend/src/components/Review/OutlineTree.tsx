import { Tree, Typography } from 'antd';
import { UnorderedListOutlined } from '@ant-design/icons';
import type { DataNode } from 'antd/es/tree';

const { Text } = Typography;

interface OutlineSection {
    title: string;
    subsections?: { title: string }[];
}

interface OutlineTreeProps {
    /** 大纲 JSON (包含 sections 字段) */
    outline: Record<string, unknown> | null;
    /** 点击章节回调 (传入 heading ID) */
    onSelect?: (headingId: string) => void;
}

/** 生成 heading ID (与 ReviewPreview 一致) */
function headingId(text: string): string {
    return text
        .toLowerCase()
        .replace(/\s+/g, '-')
        .replace(/[^\w-]/g, '');
}

/** 将 outline JSON 转为 Ant Design Tree 数据 */
function buildTreeData(outline: Record<string, unknown>): DataNode[] {
    const sections = (outline.sections as OutlineSection[]) || [];
    return sections.map((section, i) => ({
        title: section.title,
        key: headingId(section.title) || `section-${i}`,
        icon: <UnorderedListOutlined />,
        children: section.subsections?.map((sub, j) => ({
            title: sub.title,
            key: headingId(sub.title) || `section-${i}-${j}`,
        })),
    }));
}

export default function OutlineTree({ outline, onSelect }: OutlineTreeProps) {
    if (!outline) {
        return (
            <Text type="secondary" style={{ padding: 16, display: 'block' }}>
                暂无大纲
            </Text>
        );
    }

    const treeData = buildTreeData(outline);

    if (treeData.length === 0) {
        return (
            <Text type="secondary" style={{ padding: 16, display: 'block' }}>
                暂无大纲
            </Text>
        );
    }

    return (
        <div style={{ padding: '8px 0' }}>
            <Text strong style={{ display: 'block', padding: '0 12px 8px', fontSize: 13 }}>
                大纲导航
            </Text>
            <Tree
                treeData={treeData}
                defaultExpandAll
                showIcon
                blockNode
                onSelect={(selectedKeys) => {
                    if (selectedKeys.length > 0 && onSelect) {
                        onSelect(String(selectedKeys[0]));
                    }
                }}
                style={{ fontSize: 13 }}
            />
        </div>
    );
}
