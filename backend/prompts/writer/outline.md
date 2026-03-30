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
