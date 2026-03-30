import { Steps } from 'antd';
import {
    SearchOutlined,
    ReadOutlined,
    EditOutlined,
    ExportOutlined,
} from '@ant-design/icons';

interface ProgressBarProps {
    phase: string | null;
}

const STEPS = [
    { key: 'searching', title: '检索', icon: <SearchOutlined /> },
    { key: 'reading', title: '精读', icon: <ReadOutlined /> },
    { key: 'writing', title: '写作', icon: <EditOutlined /> },
    { key: 'exporting', title: '导出', icon: <ExportOutlined /> },
];

const PHASE_TO_STEP: Record<string, number> = {
    searching: 0,
    search_review: 0,
    reading: 1,
    outlining: 2,
    outline_review: 2,
    writing: 2,
    draft_review: 2,
    revising: 2,
    exporting: 3,
    completed: 4,
};

export default function ProgressBar({ phase }: ProgressBarProps) {
    const current = phase ? (PHASE_TO_STEP[phase] ?? 0) : 0;

    return (
        <Steps
            size="small"
            current={current}
            items={STEPS.map((step) => ({
                title: step.title,
                icon: step.icon,
            }))}
            style={{ padding: '12px 16px' }}
        />
    );
}
