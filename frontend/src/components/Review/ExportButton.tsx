import { useState } from 'react';
import { Dropdown, Button, message } from 'antd';
import { DownloadOutlined } from '@ant-design/icons';
import { exportOutput, downloadBlob } from '@/api/outputs';
import { EXPORT_FORMAT_LABELS } from '@/utils/constants';
import { ExportFormat } from '@/types/enums';

interface ExportButtonProps {
    projectId: string;
    outputId: string;
}

const FORMATS = [
    ExportFormat.MARKDOWN,
    ExportFormat.WORD,
    ExportFormat.BIBTEX,
    ExportFormat.RIS,
] as const;

export default function ExportButton({ projectId, outputId }: ExportButtonProps) {
    const [loading, setLoading] = useState(false);

    const handleExport = async (format: ExportFormat) => {
        setLoading(true);
        try {
            const { blob, filename } = await exportOutput(projectId, outputId, { format });
            downloadBlob(blob, filename);
            message.success(`已下载: ${filename}`);
        } catch {
            // error handled by axios interceptor
        } finally {
            setLoading(false);
        }
    };

    const menuItems = FORMATS.map((format) => ({
        key: format,
        label: EXPORT_FORMAT_LABELS[format],
        onClick: () => handleExport(format),
    }));

    return (
        <Dropdown menu={{ items: menuItems }} trigger={['click']}>
            <Button icon={<DownloadOutlined />} loading={loading}>
                导出
            </Button>
        </Dropdown>
    );
}
