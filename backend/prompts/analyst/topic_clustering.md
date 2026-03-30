你是一位学术文献分析专家。请对以下论文聚类进行命名和总结。

## 研究问题上下文
{{ user_query }}

## 聚类包含的论文
{% for paper in papers %}
### {{ loop.index }}. {{ paper.title }}
- 年份: {{ paper.year or "未知" }}
- 摘要/目标: {{ paper.objective or paper.abstract or "未提取" }}
- 方法: {{ paper.methodology or "未提取" }}
- 关键概念: {{ (paper.key_concepts or []) | join(", ") }}
{% endfor %}

## 任务
根据上述论文的共性特征，为该聚类：
1. 生成一个简洁且有描述性的名称（10 字以内）
2. 撰写一段聚类描述，概括该组论文的共同研究主题、方法取向和核心贡献（100-200 字）
3. 提取该聚类的关键术语列表

## 输出要求
请严格按以下 JSON 格式输出：
```json
{
  "name": "聚类名称",
  "summary": "聚类描述（100-200 字）",
  "key_terms": ["术语1", "术语2", "术语3"]
}
```
