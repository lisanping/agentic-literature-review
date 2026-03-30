你是一位学术文献评审专家。请根据以下文献分析结果，识别当前研究领域中的研究空白。

## 研究问题上下文
{{ user_query }}

## 聚类覆盖情况
{% for cluster in clusters %}
### 聚类: {{ cluster.name }}（{{ cluster.paper_count }} 篇）
- 关键术语: {{ (cluster.key_terms or []) | join(", ") }}
- 描述: {{ cluster.summary or "无" }}
{% endfor %}

## 趋势信息
{% for topic in trends %}
- {{ topic.topic }}: 趋势 {{ topic.trend }}
{% endfor %}

## 论文局限性汇总
{% for lim in limitations %}
- {{ lim.title }}: {{ lim.limitations or "未提取" }}
{% endfor %}

## 任务
1. 基于聚类覆盖和趋势分析，识别未被充分研究的方向
2. 为每个研究空白评估优先级（high / medium / low）
3. 提出具体的研究建议方向
4. 如果某些空白可以通过补充检索弥补，生成针对性的搜索查询

## 输出要求
请严格按以下 JSON 格式输出：
```json
{
  "gaps": [
    {
      "description": "研究空白描述",
      "evidence": ["支持该判断的证据1", "证据2"],
      "priority": "high|medium|low",
      "related_cluster_ids": ["相关聚类ID"],
      "suggested_direction": "建议的研究方向",
      "search_query": "补充检索的查询词（如需要，否则为 null）"
    }
  ]
}
```
