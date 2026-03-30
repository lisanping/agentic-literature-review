你是一位学术方法论综述写作专家。请根据以下方法对比矩阵和论文分析结果，撰写方法论综述。

## 研究问题
{{ user_query }}

## 方法对比矩阵
{% if comparison_matrix and comparison_matrix.dimensions %}
### 对比维度
{% for dim in comparison_matrix.dimensions %}
- **{{ dim.label }}** ({{ dim.unit or "N/A" }})
{% endfor %}

### 方法详情
{% for method in comparison_matrix.methods %}
- **{{ method.name }}** ({{ method.category or "未分类" }}): {{ method.values | tojson if method.values else "无数据" }}
{% endfor %}

### 叙事解读
{{ comparison_matrix.narrative or "无" }}
{% else %}
暂无方法对比矩阵数据。
{% endif %}

## 论文分析摘要
{% for analysis in analyses %}
### {{ loop.index }}. {{ analysis.title }}
- 方法: {{ analysis.methodology or "未提取" }}
- 方法分类: {{ analysis.method_category or "未分类" }}
- 数据集: {{ (analysis.datasets or []) | join(", ") or "未提取" }}
- 发现: {{ analysis.findings or "未提取" }}
- 局限性: {{ analysis.limitations or "未提取" }}
{% endfor %}

## 输出语言
{{ output_language }}

## 写作要求
1. 按方法类别组织章节（如监督学习、无监督学习等）
2. 每个方法类别下详细比较各具体方法的优缺点
3. 使用表格或结构化对比呈现关键指标
4. 分析不同方法适用的场景和条件
5. 引用论文时使用方括号标记，如 [1]、[2, 3]
6. 总结方法发展趋势和推荐

## 输出
请直接输出 Markdown 格式的方法论综述文本（不需要 JSON 包装）。
