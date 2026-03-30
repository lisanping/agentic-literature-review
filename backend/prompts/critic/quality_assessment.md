你是一位学术论文质量评估专家。请对以下论文进行方法学严谨性评估。

## 研究问题上下文
{{ user_query }}

## 待评估论文
{% for paper in papers %}
### {{ loop.index }}. {{ paper.title }}
- 年份: {{ paper.year or "未知" }}
- 方法: {{ paper.methodology or "未提取" }}
- 数据集: {{ (paper.datasets or []) | join(", ") or "未提取" }}
- 主要发现: {{ paper.findings or "未提取" }}
- 局限性: {{ paper.limitations or "未提取" }}
- 被引次数: {{ paper.citation_count or "未知" }}
- 论文标识: {{ paper.paper_id or "" }}
{% endfor %}

## 评估标准 (Rubric)
请从以下维度评估每篇论文的方法学严谨性（0-10 分）：
1. **研究设计** (0-3): 研究设计是否合理、实验是否可重现
2. **数据质量** (0-3): 数据集是否充分、采样是否合理
3. **统计分析** (0-2): 统计方法是否恰当、是否报告显著性
4. **结论可靠性** (0-2): 结论是否由数据支撑、是否存在过度推断

## 输出要求
请严格按以下 JSON 格式输出：
```json
{
  "assessments": [
    {
      "paper_id": "论文标识",
      "rigor_score": 8,
      "justification": "评分理由（100字以内）",
      "strengths": ["优点1", "优点2"],
      "weaknesses": ["不足1"]
    }
  ]
}
```
