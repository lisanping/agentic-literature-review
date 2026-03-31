import { Drawer, Descriptions, Tag, Typography, Space, Divider } from 'antd';
import {
    CalendarOutlined,
    TeamOutlined,
    BookOutlined,
} from '@ant-design/icons';
import type { GraphNode } from '@/types/visualization';
import { useVisualizationStore } from '@/stores/visualizationStore';

const { Text } = Typography;

interface PaperDetailDrawerProps {
    nodes: GraphNode[];
}

/** Side drawer showing paper details when a node is clicked */
export default function PaperDetailDrawer({ nodes }: PaperDetailDrawerProps) {
    const { selectedNodeId, selectNode } = useVisualizationStore();

    const paper = nodes.find((n) => n.id === selectedNodeId);

    return (
        <Drawer
            title="论文详情"
            open={!!selectedNodeId}
            onClose={() => selectNode(null)}
            width={380}
            mask={false}
        >
            {paper && (
                <div>
                    <Typography.Title level={5} style={{ marginBottom: 12 }}>
                        {paper.title}
                    </Typography.Title>

                    <Descriptions column={1} size="small" style={{ marginBottom: 16 }}>
                        <Descriptions.Item
                            label={
                                <Space>
                                    <TeamOutlined />
                                    作者
                                </Space>
                            }
                        >
                            {paper.authors.length > 0 ? paper.authors.join(', ') : '—'}
                        </Descriptions.Item>
                        <Descriptions.Item
                            label={
                                <Space>
                                    <CalendarOutlined />
                                    年份
                                </Space>
                            }
                        >
                            {paper.year ?? '—'}
                        </Descriptions.Item>
                        <Descriptions.Item
                            label={
                                <Space>
                                    <BookOutlined />
                                    被引数
                                </Space>
                            }
                        >
                            {paper.citations_count}
                        </Descriptions.Item>
                    </Descriptions>

                    {paper.cluster_name && (
                        <>
                            <Divider style={{ margin: '12px 0' }} />
                            <div>
                                <Text type="secondary" style={{ fontSize: 12 }}>
                                    所属聚类
                                </Text>
                                <div style={{ marginTop: 4 }}>
                                    <Tag color="blue">{paper.cluster_name}</Tag>
                                </div>
                            </div>
                        </>
                    )}
                </div>
            )}
        </Drawer>
    );
}
