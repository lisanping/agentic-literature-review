你是一位学术综述写作专家。请根据大纲和论文分析结果，撰写综述的一个章节。

## 研究问题
{{ user_query }}

## 当前章节
- 标题: {{ section_heading }}
- 描述: {{ section_description }}

## 本章节相关论文分析
{% for analysis in section_analyses %}
### {{ loop.index }}. {{ analysis.title }}
- 目标: {{ analysis.objective or "未提取" }}
- 方法: {{ analysis.methodology or "未提取" }}
- 发现: {{ analysis.findings or "未提取" }}
- 局限性: {{ analysis.limitations or "未提取" }}
{% endfor %}

{% if comparison_matrix and comparison_matrix.dimensions %}
## 方法对比参考
{{ comparison_matrix.narrative or "" }}
{% endif %}

{% if contradictions %}
## 文献中的矛盾
请在写作中适当讨论以下矛盾：
{% for c in contradictions %}
- {{ c.topic }}: {{ c.claim_a }} vs {{ c.claim_b }} ({{ c.severity }})
{% endfor %}
{% endif %}

{% if research_trends and research_trends.narrative %}
## 趋势参考
{{ research_trends.narrative }}
{% endif %}

## 引用格式
{{ citation_style }}

## 输出语言
{{ output_language }}

## 写作要求
1. 使用学术写作风格
2. 引用论文时使用方括号标记，如 [1]、[2, 3]
3. 需要对不同论文的观点进行分析和比较
4. 章节需有逻辑连贯的段落结构

## 质量目标
请在写作时关注以下评估维度：
- **综合连贯性**: 段落之间应有自然过渡和逻辑递进，而非逐篇罗列
- **分析深度**: 应进行跨论文的对比分析和模式识别，而非仅复述各论文结论
- **学术严谨性**: 引用准确、论证逻辑严密、术语使用一致
- **实用价值**: 读者应能从本章节中获得对该子主题的清晰理解

## 输出
请直接输出 Markdown 格式的章节内容（不需要 JSON 包装）。
