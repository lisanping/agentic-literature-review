import { useState, useMemo } from 'react';
import { Checkbox, Button, Typography, Space, Divider } from 'antd';
import type { ProjectPaperResponse } from '@/types';
import PaperCard from './PaperCard';
import PaperFilter, { type PaperFilters } from './PaperFilter';

const { Text } = Typography;

interface PaperListProps {
    papers: ProjectPaperResponse[];
    /** 是否显示勾选框 (HITL 检索确认时启用) */
    selectable?: boolean;
    /** 已选论文 ID 列表 */
    selectedIds?: string[];
    /** 选择变更回调 */
    onSelectionChange?: (ids: string[]) => void;
    /** 是否显示过滤器 */
    showFilter?: boolean;
}

export default function PaperList({
    papers,
    selectable = false,
    selectedIds = [],
    onSelectionChange,
    showFilter = false,
}: PaperListProps) {
    const [filters, setFilters] = useState<PaperFilters>({});

    // 过滤论文
    const filteredPapers = useMemo(() => {
        return papers.filter((item) => {
            const p = item.paper;
            if (filters.yearMin && p.year && p.year < filters.yearMin) return false;
            if (filters.yearMax && p.year && p.year > filters.yearMax) return false;
            if (filters.minCitations && p.citation_count < filters.minCitations) return false;
            if (filters.fullTextOnly && !p.pdf_available) return false;
            return true;
        });
    }, [papers, filters]);

    const allFilteredIds = filteredPapers.map((p) => p.paper.id);
    const allSelected =
        allFilteredIds.length > 0 && allFilteredIds.every((id) => selectedIds.includes(id));

    const handleToggle = (paperId: string) => {
        if (!onSelectionChange) return;
        if (selectedIds.includes(paperId)) {
            onSelectionChange(selectedIds.filter((id) => id !== paperId));
        } else {
            onSelectionChange([...selectedIds, paperId]);
        }
    };

    const handleSelectAll = () => {
        if (!onSelectionChange) return;
        if (allSelected) {
            onSelectionChange(selectedIds.filter((id) => !allFilteredIds.includes(id)));
        } else {
            const merged = new Set([...selectedIds, ...allFilteredIds]);
            onSelectionChange(Array.from(merged));
        }
    };

    return (
        <div>
            {/* 过滤器 */}
            {showFilter && <PaperFilter filters={filters} onChange={setFilters} />}

            {/* 汇总行 */}
            <div
                style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: '4px 0',
                }}
            >
                <Text type="secondary" style={{ fontSize: 12 }}>
                    共 {filteredPapers.length} 篇
                    {selectable && ` · 已选 ${selectedIds.length} 篇`}
                </Text>
                {selectable && (
                    <Space>
                        <Button size="small" type="link" onClick={handleSelectAll}>
                            {allSelected ? '取消全选' : '全选'}
                        </Button>
                    </Space>
                )}
            </div>

            <Divider style={{ margin: '4px 0 8px' }} />

            {/* 论文列表 */}
            {filteredPapers.map((item) => (
                <div key={item.paper.id} style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                    {selectable && (
                        <Checkbox
                            checked={selectedIds.includes(item.paper.id)}
                            onChange={() => handleToggle(item.paper.id)}
                            style={{ marginTop: 12 }}
                        />
                    )}
                    <div style={{ flex: 1 }}>
                        <PaperCard
                            item={item}
                            selected={selectedIds.includes(item.paper.id)}
                            onClick={selectable ? () => handleToggle(item.paper.id) : undefined}
                        />
                    </div>
                </div>
            ))}

            {filteredPapers.length === 0 && (
                <Text type="secondary" style={{ display: 'block', textAlign: 'center', padding: 24 }}>
                    没有匹配的论文
                </Text>
            )}
        </div>
    );
}
