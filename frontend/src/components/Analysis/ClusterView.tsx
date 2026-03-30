import { Tag, Typography, Collapse, Space, Badge } from 'antd';
import { ClusterOutlined } from '@ant-design/icons';
import type { TopicCluster } from '@/types';

const { Text } = Typography;

interface ClusterViewProps {
    clusters: TopicCluster[];
}

/** 主题聚类列表视图 */
export default function ClusterView({ clusters }: ClusterViewProps) {
    if (!clusters.length) {
        return <Text type="secondary">暂无聚类数据</Text>;
    }

    return (
        <Collapse
            size="small"
            items={clusters.map((cluster) => ({
                key: cluster.id,
                label: (
                    <Space>
                        <ClusterOutlined />
                        <Text strong>{cluster.name}</Text>
                        <Badge count={cluster.paper_count} color="#1677ff" />
                    </Space>
                ),
                children: (
                    <div>
                        {cluster.key_terms.length > 0 && (
                            <div style={{ marginBottom: 8 }}>
                                {cluster.key_terms.map((term) => (
                                    <Tag key={term} color="blue" style={{ marginBottom: 4 }}>
                                        {term}
                                    </Tag>
                                ))}
                            </div>
                        )}
                        {cluster.summary && (
                            <Text type="secondary" style={{ fontSize: 12 }}>
                                {cluster.summary}
                            </Text>
                        )}
                    </div>
                ),
            }))}
        />
    );
}
