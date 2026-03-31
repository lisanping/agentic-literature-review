import { Input, Button, Space, Tag, Tooltip, message } from 'antd';
import {
    DownloadOutlined,
    FileImageOutlined,
    SearchOutlined,
} from '@ant-design/icons';
import type { ClusterInfo } from '@/types/visualization';
import { CLUSTER_COLORS } from '@/types/visualization';
import { useVisualizationStore } from '@/stores/visualizationStore';
import { downloadSvg, downloadPng } from '@/utils/export-svg';

interface GraphControlsProps {
    clusters: ClusterInfo[];
    svgRef: React.RefObject<SVGSVGElement | null>;
}

/** Controls panel for the Knowledge Graph — zoom, search, legend, export */
export default function GraphControls({ clusters, svgRef }: GraphControlsProps) {
    const {
        searchQuery,
        setSearchQuery,
        highlightedClusters,
        toggleCluster,
        setHighlightedClusters,
    } = useVisualizationStore();

    const handleExportSvg = () => {
        if (!svgRef.current) return;
        downloadSvg(svgRef.current, 'knowledge-graph.svg');
        message.success('SVG 已导出');
    };

    const handleExportPng = async () => {
        if (!svgRef.current) return;
        try {
            await downloadPng(svgRef.current, 'knowledge-graph.png');
            message.success('PNG 已导出');
        } catch {
            message.error('PNG 导出失败');
        }
    };

    return (
        <div style={{ marginBottom: 12 }}>
            {/* Search + Export */}
            <div style={{ display: 'flex', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
                <Input
                    placeholder="搜索论文..."
                    prefix={<SearchOutlined />}
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    allowClear
                    style={{ flex: 1, minWidth: 160 }}
                    size="small"
                />
                <Space size={4}>
                    <Tooltip title="导出 SVG">
                        <Button
                            size="small"
                            icon={<DownloadOutlined />}
                            onClick={handleExportSvg}
                        />
                    </Tooltip>
                    <Tooltip title="导出 PNG">
                        <Button
                            size="small"
                            icon={<FileImageOutlined />}
                            onClick={handleExportPng}
                        />
                    </Tooltip>
                </Space>
            </div>

            {/* Cluster legend */}
            {clusters.length > 0 && (
                <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                    {clusters.map((cluster, idx) => {
                        const color = CLUSTER_COLORS[idx % CLUSTER_COLORS.length]!;
                        const active =
                            highlightedClusters.size === 0 || highlightedClusters.has(cluster.id);
                        return (
                            <Tag
                                key={cluster.id}
                                color={active ? color : undefined}
                                style={{
                                    cursor: 'pointer',
                                    opacity: active ? 1 : 0.4,
                                    fontSize: 11,
                                }}
                                onClick={() => toggleCluster(cluster.id)}
                            >
                                {cluster.name} ({cluster.paper_count})
                            </Tag>
                        );
                    })}
                    {highlightedClusters.size > 0 && (
                        <Tag
                            style={{ cursor: 'pointer', fontSize: 11 }}
                            onClick={() => setHighlightedClusters(new Set<string>())}
                        >
                            显示全部
                        </Tag>
                    )}
                </div>
            )}
        </div>
    );
}
