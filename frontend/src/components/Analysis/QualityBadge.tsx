import { Tooltip } from 'antd';

interface QualityBadgeProps {
    score: number | null | undefined;
}

/**
 * 质量评分圆点标识
 *
 * - ≥ 0.7  →  绿色 (高质量)
 * - 0.3–0.7 →  黄色 (中等)
 * - < 0.3   →  红色 (低质量)
 * - null   →  不显示
 */
export default function QualityBadge({ score }: QualityBadgeProps) {
    if (score === null || score === undefined) return null;

    const color = score >= 0.7 ? '#52c41a' : score >= 0.3 ? '#faad14' : '#ff4d4f';
    const label = score >= 0.7 ? '高' : score >= 0.3 ? '中' : '低';

    return (
        <Tooltip title={`质量评分: ${(score * 100).toFixed(0)}% (${label})`}>
            <span
                style={{
                    display: 'inline-block',
                    width: 8,
                    height: 8,
                    borderRadius: '50%',
                    background: color,
                    marginRight: 4,
                    verticalAlign: 'middle',
                }}
            />
        </Tooltip>
    );
}
