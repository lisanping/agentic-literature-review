你是一位学术文献分析专家。请根据以下按年份排列的论文列表，识别研究领域的关键里程碑事件。

## 研究问题上下文
{{ user_query }}

## 按年份排列的论文
{% for entry in yearly_papers %}
### {{ entry.year }} 年（{{ entry.papers | length }} 篇）
{% for paper in entry.papers %}
- {{ paper.title }}
  - 方法: {{ paper.methodology or "未提取" }}
  - 贡献: {{ paper.findings or "未提取" }}
  - 被引数: {{ paper.citation_count or "未知" }}
{% endfor %}
{% endfor %}

## 任务
1. 识别每个年份中的里程碑事件（能代表该领域重要转折或突破的论文/发现）
2. 对于没有特别突破的年份，milestone 可设为 null
3. 标注每个年份的关键事件描述

## 输出要求
请严格按以下 JSON 格式输出：
```json
{
  "milestones": [
    {
      "year": 2020,
      "milestone": "里程碑描述（无则为 null）",
      "paper_ids": ["相关论文标识"],
      "key_event": "该年份的关键事件描述（无则为 null）"
    }
  ]
}
```
