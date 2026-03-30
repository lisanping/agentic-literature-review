你是一位学术论文关系分析专家。请分析以下两篇论文之间的学术关系。

## 当前论文
- 标题: {{ paper_title }}
- 摘要: {{ paper_abstract }}

## 候选相关论文列表
{% for other in other_papers %}
### 论文 {{ loop.index }}
- ID: {{ other.id }}
- 标题: {{ other.title }}
- 摘要: {{ other.abstract or "无摘要" }}
{% endfor %}

## 关系类型定义
- cites: 当前论文引用了目标论文
- extends: 当前论文扩展了目标论文的工作
- refutes: 当前论文反驳了目标论文的结论
- reproduces: 当前论文复现了目标论文的实验
- reviews: 当前论文综述了目标论文
- compares: 当前论文与目标论文做了对比
- applies: 当前论文将目标论文的方法应用到新领域

## 输出要求
请严格按以下 JSON 格式输出：
```json
{
  "relations": [
    {
      "target_paper_id": "论文ID",
      "relation_type": "关系类型",
      "evidence": "支撑该关系判断的文本证据"
    }
  ]
}
```
