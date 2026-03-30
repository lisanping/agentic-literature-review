你是一位学术研究规划专家。请根据以下趋势、空白和聚类分析，生成研究路线图。

## 研究问题
{{ user_query }}

## 聚类主题
{% for cluster in topic_clusters %}
### {{ cluster.name }} ({{ cluster.paper_count }} 篇)
- 关键术语: {{ (cluster.key_terms or []) | join(", ") }}
- 摘要: {{ cluster.summary or "无" }}
{% endfor %}

## 研究空白
{% for gap in research_gaps %}
- **{{ gap.description }}** (优先级: {{ gap.priority }})
  - 建议方向: {{ gap.suggested_direction or "无" }}
{% endfor %}

## 趋势信息
{% for t in research_trends.by_topic %}
- **{{ t.topic }}**: 趋势 {{ t.trend }}
{% endfor %}

## 新兴方向
{{ (research_trends.emerging_topics or []) | join(", ") or "无" }}

## 时间线
{% for entry in timeline %}
- {{ entry.year }}年: {{ entry.milestone or "无里程碑" }}
{% endfor %}

## 输出语言
{{ output_language }}

## 写作要求
1. 概述当前研究格局（基于聚类和趋势）
2. 按时间维度规划短期（1-2年）、中期（3-5年）和长期（5年+）研究方向
3. 每个方向需包含：背景依据、预期目标、关键挑战、建议的方法论
4. 优先级排序参考研究空白的 priority
5. 标注各研究方向之间的依赖关系
6. 引用相关论文支撑路线图规划

## 输出
请直接输出 Markdown 格式的研究路线图（不需要 JSON 包装）。
