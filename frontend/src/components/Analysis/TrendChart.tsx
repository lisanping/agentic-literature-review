import { Typography } from 'antd';
import type { ResearchTrends } from '@/types';

const { Text, Paragraph } = Typography;

interface TrendChartProps {
    trends: ResearchTrends;
}

/** 趋势可视化 — 纯 CSS 柱状图 + 主题趋势标签 */
export default function TrendChart({ trends }: TrendChartProps) {
    const { by_year, by_topic, emerging_topics, narrative } = trends;

    if (!by_year.length && !by_topic.length) {
        return <Text type="secondary">暂无趋势数据</Text>;
    }

    const maxCount = Math.max(...by_year.map((y) => y.count), 1);

    return (
        <div>
            {/* 年度论文数量柱状图 */}
            {by_year.length > 0 && (
                <div style={{ marginBottom: 16 }}>
                    <Text strong style={{ fontSize: 12, display: 'block', marginBottom: 8 }}>
                        年度论文数量
                    </Text>
                    <div style={{ display: 'flex', alignItems: 'flex-end', gap: 4, height: 100 }}>
                        {by_year.map((item) => {
                            const height = Math.max((item.count / maxCount) * 80, 4);
                            return (
                                <div
                                    key={item.year}
                                    style={{
                                        display: 'flex',
                                        flexDirection: 'column',
                                        alignItems: 'center',
                                        flex: 1,
                                    }}
                                >
                                    <Text style={{ fontSize: 10, color: '#666' }}>
                                        {item.count}
                                    </Text>
                                    <div
                                        style={{
                                            width: '100%',
                                            maxWidth: 32,
                                            height,
                                            background: '#1677ff',
                                            borderRadius: '4px 4px 0 0',
                                            transition: 'height 0.3s',
                                        }}
                                    />
                                    <Text style={{ fontSize: 10, color: '#999', marginTop: 2 }}>
                                        {item.year}
                                    </Text>
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}

            {/* 主题趋势 */}
            {by_topic.length > 0 && (
                <div style={{ marginBottom: 12 }}>
                    <Text strong style={{ fontSize: 12, display: 'block', marginBottom: 6 }}>
                        主题趋势
                    </Text>
                    {by_topic.map((t) => {
                        const icon = t.trend === 'rising' ? '📈' : t.trend === 'declining' ? '📉' : '➡️';
                        const color = t.trend === 'rising' ? '#52c41a' : t.trend === 'declining' ? '#ff4d4f' : '#666';
                        return (
                            <div
                                key={t.topic}
                                style={{
                                    display: 'flex',
                                    justifyContent: 'space-between',
                                    alignItems: 'center',
                                    padding: '4px 0',
                                    borderBottom: '1px solid #f5f5f5',
                                }}
                            >
                                <Text style={{ fontSize: 12 }}>{t.topic}</Text>
                                <Text style={{ fontSize: 12, color }}>
                                    {icon} {t.trend}
                                </Text>
                            </div>
                        );
                    })}
                </div>
            )}

            {/* 新兴主题 */}
            {emerging_topics.length > 0 && (
                <div style={{ marginBottom: 12 }}>
                    <Text strong style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
                        🌟 新兴主题
                    </Text>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                        {emerging_topics.join('、')}
                    </Text>
                </div>
            )}

            {/* 叙事摘要 */}
            {narrative && (
                <Paragraph
                    type="secondary"
                    style={{ fontSize: 12, marginTop: 4 }}
                    ellipsis={{ rows: 3, expandable: true, symbol: '展开' }}
                >
                    {narrative}
                </Paragraph>
            )}
        </div>
    );
}
