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

## 引用格式
{{ citation_style }}

## 输出语言
{{ output_language }}

## 写作要求
1. 使用学术写作风格
2. 引用论文时使用方括号标记，如 [1]、[2, 3]
3. 需要对不同论文的观点进行分析和比较
4. 章节需有逻辑连贯的段落结构

## 输出
请直接输出 Markdown 格式的章节内容（不需要 JSON 包装）。
