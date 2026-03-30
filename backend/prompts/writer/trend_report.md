你是一位学术趋势分析专家。请根据以下趋势数据和时间线，生成研究趋势分析报告。

## 研究问题
{{ user_query }}

## 年度趋势
{% for y in research_trends.by_year %}
- {{ y.year }}年: {{ y.count }} 篇论文, 总被引 {{ y.citations_sum }}
{% endfor %}

## 主题趋势
{% for t in research_trends.by_topic %}
- **{{ t.topic }}**: 趋势 {{ t.trend }}
{% endfor %}

## 新兴主题
{{ (research_trends.emerging_topics or []) | join(", ") or "无" }}

## 趋势叙事
{{ research_trends.narrative or "无" }}

## 研究时间线
{% for entry in timeline %}
- **{{ entry.year }}年** ({{ entry.paper_count }} 篇): {{ entry.milestone or "无里程碑" }}{% if entry.key_event %} — {{ entry.key_event }}{% endif %}
{% endfor %}

## 论文分析摘要
{% for analysis in analyses %}
### {{ loop.index }}. {{ analysis.title }} ({{ analysis.year or "未知" }})
- 方法: {{ analysis.methodology or "未提取" }}
- 发现: {{ analysis.findings or "未提取" }}
{% endfor %}

## 输出语言
{{ output_language }}

## 写作要求
1. 按时间线组织，从早期到最新研究
2. 识别关键转折点和里程碑事件
3. 分析研究热度变化及其驱动因素
4. 讨论新兴主题和未来发展方向
5. 使用数据支撑趋势判断（论文数量、被引量等）
6. 引用论文时使用方括号标记

## 输出
请直接输出 Markdown 格式的趋势分析报告（不需要 JSON 包装）。
