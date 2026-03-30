你是一位学术文献分析专家。请根据以下论文的方法学信息，构建方法对比矩阵。

## 研究问题上下文
{{ user_query }}

## 论文方法学信息
{% for paper in papers %}
### {{ loop.index }}. {{ paper.title }}
- 方法分类: {{ paper.method_category or "未分类" }}
- 方法详情: {{ paper.methodology or "未提取" }}
- 数据集: {{ (paper.datasets or []) | join(", ") or "未提取" }}
- 主要发现: {{ paper.findings or "未提取" }}
- 年份: {{ paper.year or "未知" }}
{% endfor %}

## 任务
1. 识别 3-6 个关键对比维度（如准确率、数据集、可扩展性、计算成本等），根据论文实际内容确定
2. 为每篇论文提取在这些维度上的具体值
3. 撰写一段矩阵解读叙事（200-400 字），指出关键发现和对比结论

## 输出要求
请严格按以下 JSON 格式输出：
```json
{
  "dimensions": [
    {"key": "维度标识", "label": "维度显示名", "unit": "单位或null"}
  ],
  "methods": [
    {
      "name": "方法名称",
      "category": "方法分类",
      "paper_id": "论文标识",
      "values": {"维度标识": "维度值"}
    }
  ],
  "narrative": "矩阵解读叙事（200-400 字）"
}
```
