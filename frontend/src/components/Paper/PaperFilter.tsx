import { Space, Select, InputNumber, Switch, Typography } from 'antd';

const { Text } = Typography;

export interface PaperFilters {
    yearMin?: number;
    yearMax?: number;
    minCitations?: number;
    fullTextOnly?: boolean;
}

interface PaperFilterProps {
    filters: PaperFilters;
    onChange: (filters: PaperFilters) => void;
}

export default function PaperFilter({ filters, onChange }: PaperFilterProps) {
    const currentYear = new Date().getFullYear();
    const yearOptions = Array.from({ length: 30 }, (_, i) => ({
        value: currentYear - i,
        label: String(currentYear - i),
    }));

    return (
        <Space wrap size="middle" style={{ padding: '8px 0' }}>
            <Space size={4}>
                <Text type="secondary" style={{ fontSize: 12 }}>
                    年份:
                </Text>
                <Select
                    size="small"
                    placeholder="起始"
                    allowClear
                    style={{ width: 80 }}
                    options={yearOptions}
                    value={filters.yearMin}
                    onChange={(v) => onChange({ ...filters, yearMin: v })}
                />
                <Text type="secondary">-</Text>
                <Select
                    size="small"
                    placeholder="结束"
                    allowClear
                    style={{ width: 80 }}
                    options={yearOptions}
                    value={filters.yearMax}
                    onChange={(v) => onChange({ ...filters, yearMax: v })}
                />
            </Space>

            <Space size={4}>
                <Text type="secondary" style={{ fontSize: 12 }}>
                    最低被引:
                </Text>
                <InputNumber
                    size="small"
                    min={0}
                    style={{ width: 70 }}
                    value={filters.minCitations}
                    onChange={(v) => onChange({ ...filters, minCitations: v ?? undefined })}
                />
            </Space>

            <Space size={4}>
                <Text type="secondary" style={{ fontSize: 12 }}>
                    仅全文:
                </Text>
                <Switch
                    size="small"
                    checked={filters.fullTextOnly}
                    onChange={(v) => onChange({ ...filters, fullTextOnly: v })}
                />
            </Space>
        </Space>
    );
}
