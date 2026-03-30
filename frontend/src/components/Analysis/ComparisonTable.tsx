import { Table, Typography, Tooltip } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { ComparisonMatrix, ComparisonMethod } from '@/types';

const { Text, Paragraph } = Typography;

interface ComparisonTableProps {
    matrix: ComparisonMatrix;
}

/** 方法对比矩阵表格 */
export default function ComparisonTable({ matrix }: ComparisonTableProps) {
    if (!matrix.dimensions.length || !matrix.methods.length) {
        return <Text type="secondary">暂无对比矩阵数据</Text>;
    }

    const columns: ColumnsType<ComparisonMethod> = [
        {
            title: '方法',
            dataIndex: 'name',
            key: 'name',
            width: 120,
            fixed: 'left',
            render: (name: string, record) => (
                <Tooltip title={record.category}>
                    <Text strong style={{ fontSize: 12 }}>{name}</Text>
                </Tooltip>
            ),
        },
        ...matrix.dimensions.map((dim) => ({
            title: (
                <Tooltip title={dim.unit ? `单位: ${dim.unit}` : undefined}>
                    <span style={{ fontSize: 12 }}>{dim.label}</span>
                </Tooltip>
            ),
            dataIndex: ['values', dim.key],
            key: dim.key,
            width: 100,
            render: (val: number | string | null) => {
                if (val === null || val === undefined) return <Text type="secondary">—</Text>;
                return <Text style={{ fontSize: 12 }}>{String(val)}</Text>;
            },
        })),
    ];

    return (
        <div>
            <Table
                columns={columns}
                dataSource={matrix.methods}
                rowKey="name"
                size="small"
                scroll={{ x: 'max-content' }}
                pagination={false}
                bordered
            />
            {matrix.narrative && (
                <Paragraph
                    type="secondary"
                    style={{ fontSize: 12, marginTop: 8 }}
                    ellipsis={{ rows: 3, expandable: true, symbol: '展开' }}
                >
                    {matrix.narrative}
                </Paragraph>
            )}
        </div>
    );
}
