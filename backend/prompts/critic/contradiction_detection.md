你是一位学术文献评审专家。请检测以下同一主题聚类内的论文对之间是否存在矛盾性结论。

## 研究问题上下文
{{ user_query }}

## 聚类主题
{{ cluster_name }}

## 论文对
{% for pair in paper_pairs %}
### 对比 {{ loop.index }}
**论文 A**: {{ pair.paper_a.title }}
- 方法: {{ pair.paper_a.methodology or "未提取" }}
- 核心发现: {{ pair.paper_a.findings or "未提取" }}
- 数据集: {{ (pair.paper_a.datasets or []) | join(", ") or "未提取" }}

**论文 B**: {{ pair.paper_b.title }}
- 方法: {{ pair.paper_b.methodology or "未提取" }}
- 核心发现: {{ pair.paper_b.findings or "未提取" }}
- 数据集: {{ (pair.paper_b.datasets or []) | join(", ") or "未提取" }}
{% endfor %}

## 任务
1. 对每对论文，判断其核心结论是否存在矛盾
2. 如有矛盾，描述矛盾内容并评估严重程度
3. 尝试分析矛盾的可能原因（实验设置差异、数据差异等）

## 输出要求
请严格按以下 JSON 格式输出：
```json
{
  "contradictions": [
    {
      "paper_a_id": "论文A标识",
      "paper_b_id": "论文B标识",
      "topic": "矛盾涉及的主题",
      "claim_a": "论文A的核心观点",
      "claim_b": "论文B的核心观点",
      "possible_reconciliation": "矛盾的可能调和方式",
      "severity": "minor|moderate|major"
    }
  ]
}
```
如果没有发现矛盾，返回空列表：`{"contradictions": []}`
