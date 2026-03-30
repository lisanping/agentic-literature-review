你是一位学术综述写作专家。请根据以下论文分析结果，生成综述大纲。

## 研究问题
{{ user_query }}

## 输出类型
{{ output_type }}

## 论文分析摘要
{% for analysis in analyses %}
### {{ loop.index }}. {{ analysis.title }}
- 目标: {{ analysis.objective or "未提取" }}
- 方法: {{ analysis.methodology or "未提取" }}
- 发现: {{ analysis.findings or "未提取" }}
- 关键概念: {{ (analysis.key_concepts or []) | join(", ") }}
{% endfor %}

{% if topic_clusters %}
## 主题聚类（来自 Analyst Agent）
请参考以下聚类结果组织章节结构，每个聚类可映射为一个主要章节：
{% for cluster in topic_clusters %}
### 聚类: {{ cluster.name }} ({{ cluster.paper_count }} 篇)
- 关键术语: {{ (cluster.key_terms or []) | join(", ") }}
- 摘要: {{ cluster.summary or "无" }}
- 包含论文: {{ (cluster.paper_ids or []) | join(", ") }}
{% endfor %}
{% endif %}

## 输出语言
{{ output_language }}

## 输出要求
请严格按以下 JSON 格式输出大纲结构：
```json
{
  "title": "综述标题",
  "sections": [
    {
      "heading": "章节标题",
      "description": "本章节将涵盖的内容简述",
      "subsections": [
        {"heading": "子章节标题", "description": "子章节内容简述"}
      ],
      "relevant_paper_indices": [1, 3, 5]
    }
  ]
}
```
