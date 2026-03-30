# v0.3 实施计划：Analyst Agent + Critic Agent

> **文档版本**: v1.0
> **创建日期**: 2026-03-30
> **前置文档**: [需求与功能设计](../design/requirements-and-functional-design.md) · [系统架构](../design/system-architecture.md) · [数据模型](../design/data-model.md) · [v0.1 实施计划](implementation-plan.md)
> **目标**: 在 v0.1/v0.2 基础上，实现 Analyst Agent 和 Critic Agent，完成完整 6-Agent 链路

---

## 一、v0.3 范围

### 1.1 新增能力

| 维度     | v0.3 新增                                                         |
| -------- | ----------------------------------------------------------------- |
| Agent    | Analyst Agent + Critic Agent                                      |
| 输出类型 | Methodology Review · Research Roadmap · Gap Report · Trend Report |
| 编排     | Analyst→Critic 链路、Critic→Search 反馈环路                       |
| Prompt   | 8 个新 Prompt 模板 (analyst 4 + critic 4)                         |
| 前端     | 分析结果可视化 Tab (聚类/对比矩阵/趋势图)                         |

### 1.2 不变 / 保留

| 维度       | 状态                                                                                   |
| ---------- | -------------------------------------------------------------------------------------- |
| 基础设施   | SQLite + Chroma + Redis，Docker Compose 不变                                           |
| 工作流配置 | 仅需将 `workflow.yaml` 中 `analyze` + `critique` 设为 `enabled: true`                  |
| State 字段 | `ReviewState` 已有 v0.3 字段骨架，无需修改 TypedDict                                   |
| DB Schema  | `paper_analyses` 表已含 `quality_score` / `relevance_score` / `method_category` 等字段 |
| 前端框架   | React + Ant Design + Zustand，复用现有架构                                             |

### 1.3 架构定位

```
v0.1 MVP 工作流:
  parse_intent → search → [HITL] → read → check_read_feedback
    → generate_outline → [HITL] → write → verify → [HITL] → revise → export

v0.3 完整工作流:
  parse_intent → search → [HITL] → read → check_read_feedback
    → **analyze** → **critique** → **check_critic_feedback**
    → generate_outline → [HITL] → write → verify → [HITL] → revise → export
         ↑                                    |
         └────── feedback_search_queries ─────┘ (max 2 iterations)
```

---

## 二、关键设计决策

### 2.1 Analyst Agent: 混合分析策略

**决策**: 采用 **Embedding + LLM 混合策略**，而非纯 LLM 分析。

| 分析任务     | 策略                                                                    | 理由                                     |
| ------------ | ----------------------------------------------------------------------- | ---------------------------------------- |
| 主题聚类     | Chroma embedding 向量聚类 + LLM 命名/总结                               | 向量聚类高效且成本低，LLM 仅用于语义解释 |
| 方法对比矩阵 | 从 Reader 的 `method_category` + `method_details` 结构化提取 + LLM 补充 | Reader 已做结构化提取，Analyst 聚合即可  |
| 引文网络     | 算法构建 (论文间关系图) + LLM 识别关键节点/桥梁论文                     | 图结构纯算法，影响力解读用 LLM           |
| 趋势分析     | 按年份统计分布 + LLM 趋势解读                                           | 统计数据算法生成，趋势叙事用 LLM         |
| 时间线       | 按年份排列 + LLM 识别里程碑事件                                         | 排序算法化，里程碑判断用 LLM             |

**论文数量阈值**:

| 论文数 | 行为                                                         |
| ------ | ------------------------------------------------------------ |
| < 5    | 跳过 Analyst，直接进入 Writer (数据不足以做有意义的聚类分析) |
| 5–50   | 完整分析                                                     |
| 50–200 | 分批处理 (每批 20 篇)，合并结果                              |
| > 200  | 按相关度取 Top 100 进行分析，警告用户                        |

### 2.2 Critic Agent: LLM-Driven 质量评估

**决策**: Critic Agent 以 **LLM 判断为主** + **Bibliometric 信号为辅**。

| 评估任务   | 策略                                                                     |
| ---------- | ------------------------------------------------------------------------ |
| 质量评分   | LLM 对每篇论文的方法学严谨性评分 (0-10)，结合被引数/影响因子归一化为 0-1 |
| 矛盾检测   | 同一聚类内的论文对，LLM 逐对比较核心结论 (仅评估同聚类，降低 O(N²) 成本) |
| 研究空白   | 基于聚类覆盖和趋势分析，LLM 推断未覆盖方向                               |
| 局限性汇总 | 从 Reader 的 `limitations` 字段聚合 + LLM 叙事化                         |

**质量评分 Rubric**:

```
quality_score = 0.6 × llm_rigor_score + 0.3 × normalized_citations + 0.1 × venue_tier
```

- `llm_rigor_score` (0–1): LLM 评估方法学严谨性、实验设计、统计显著性
- `normalized_citations` (0–1): `min(citation_count / max_citations_in_set, 1.0)`
- `venue_tier` (0–1): 已知顶会/期刊 → 1.0, 中档 → 0.5, 未知 → 0.2

### 2.3 Writer 如何使用 Analyst/Critic 数据

**决策**: Writer 的大纲生成器基于 Analyst 的聚类结构组织章节，Critic 的质量评分指导引用密度。

| Writer 行为            | 数据来源                                                   |
| ---------------------- | ---------------------------------------------------------- |
| 大纲结构参考聚类分组   | `topic_clusters`                                           |
| 方法论章节嵌入对比矩阵 | `comparison_matrix`                                        |
| 引言章节嵌入研究趋势   | `research_trends`                                          |
| 标注研究空白未来方向   | `research_gaps`, `limitation_summary`                      |
| 高质量论文优先引用     | `quality_assessments` (score ≥ 0.7 优先, < 0.3 降级为脚注) |
| 矛盾之处做平衡讨论     | `contradictions`                                           |

### 2.4 反馈环路触发条件

Critic Agent 在以下条件下触发 `feedback_search_queries`:

1. **覆盖空白**: 某个聚类少于 3 篇论文，且该主题被判断为核心方向
2. **时间空白**: 最近 2 年无该方向的新论文，但趋势显示应有增长
3. **方法空白**: 对比矩阵中某个方法维度值全部缺失

触发后将具体搜索词写入 `feedback_search_queries`，由 `check_critic_feedback` 路由回 Search Agent。

受 `max_feedback_iterations = 2` 控制，最多回溯 2 次。

---

## 三、数据结构详细设计

### 3.1 Analyst 输出结构

#### `topic_clusters: list[dict]`

```python
[
    {
        "id": "cluster_0",
        "name": "基于 Transformer 的方法",     # LLM 生成的聚类名称
        "summary": "该类方法使用...",           # LLM 生成的聚类描述 (100-200 字)
        "paper_ids": ["paper_id_1", "paper_id_2", ...],
        "paper_count": 8,
        "avg_year": 2023.5,
        "key_terms": ["transformer", "attention", "pre-training"],
    },
    ...
]
```

#### `comparison_matrix: dict`

```python
{
    "title": "方法对比矩阵",
    "dimensions": [
        {"key": "accuracy", "label": "准确率", "unit": "%"},
        {"key": "dataset", "label": "数据集", "unit": null},
        {"key": "year", "label": "年份", "unit": null},
        {"key": "scalability", "label": "可扩展性", "unit": null},
    ],
    "methods": [
        {
            "name": "MethodA",
            "category": "supervised",
            "paper_id": "paper_id_1",
            "values": {"accuracy": 94.2, "dataset": "ImageNet", "year": 2023, "scalability": "中"},
        },
        ...
    ],
    "narrative": "从表中可以看出...",  # LLM 生成的矩阵解读 (200-400 字)
}
```

#### `timeline: list[dict]`

```python
[
    {
        "year": 2018,
        "milestone": "BERT 提出预训练范式",          # LLM 判断的里程碑 (可为 null)
        "paper_ids": ["paper_id_1"],
        "paper_count": 3,
        "key_event": "预训练语言模型首次在 NLP 任务上大幅超越传统方法",
    },
    {
        "year": 2020,
        "milestone": "Vision Transformer 首次成功",
        "paper_ids": ["paper_id_5", "paper_id_6"],
        "paper_count": 7,
        "key_event": null,  # 无特别里程碑
    },
    ...
]
```

#### `citation_network: dict`

```python
{
    "nodes": [
        {
            "id": "paper_id_1",
            "title": "Paper Title",
            "year": 2023,
            "cluster_id": "cluster_0",
            "citation_count": 150,
            "role": "foundational",  # foundational | bridge | recent | peripheral
        },
        ...
    ],
    "edges": [
        {
            "source": "paper_id_1",
            "target": "paper_id_3",
            "relation": "cites",     # cites | extends | refutes | applies
        },
        ...
    ],
    "key_papers": ["paper_id_1", "paper_id_5"],    # LLM 判断的关键论文
    "bridge_papers": ["paper_id_3"],                # 连接不同聚类的桥梁论文
}
```

#### `research_trends: dict`

```python
{
    "by_year": [
        {"year": 2018, "count": 3, "citations_sum": 450},
        {"year": 2019, "count": 5, "citations_sum": 320},
        ...
    ],
    "by_topic": [
        {
            "topic": "Transformer-based",
            "trend": "rising",        # rising | stable | declining
            "yearly_counts": [{"year": 2020, "count": 2}, {"year": 2023, "count": 8}],
        },
        ...
    ],
    "emerging_topics": ["多模态学习", "高效微调"],   # LLM 识别的新兴方向
    "narrative": "从趋势分析来看...",                # LLM 趋势解读 (200-400 字)
}
```

### 3.2 Critic 输出结构

#### `quality_assessments: list[dict]`

```python
[
    {
        "paper_id": "paper_id_1",
        "quality_score": 0.85,         # 综合评分 0-1
        "llm_rigor_score": 0.9,        # LLM 方法学严谨性评分
        "normalized_citations": 0.75,  # 归一化被引数
        "venue_tier": 1.0,             # 期刊/会议等级
        "justification": "该论文采用了严格的实验设计...",  # 评分理由 (100 字)
        "strengths": ["大规模数据集", "消融实验完整"],
        "weaknesses": ["缺乏理论分析"],
    },
    ...
]
```

#### `contradictions: list[dict]`

```python
[
    {
        "id": "contradiction_1",
        "paper_a_id": "paper_id_1",
        "paper_b_id": "paper_id_3",
        "topic": "注意力机制的效率",
        "claim_a": "论文 A 认为稀疏注意力可以达到同等性能",
        "claim_b": "论文 B 的实验表明稀疏注意力在长序列上性能下降 15%",
        "possible_reconciliation": "差异可能源于实验设置 (数据集规模不同)",
        "severity": "moderate",  # minor | moderate | major
    },
    ...
]
```

#### `research_gaps: list[dict]`

```python
[
    {
        "id": "gap_1",
        "description": "缺乏在低资源语言上的系统评估",
        "evidence": [
            "大多数论文仅在英文/中文数据上评估",
            "cluster_2 中无论文涉及低资源语言场景"
        ],
        "priority": "high",            # high | medium | low
        "related_cluster_ids": ["cluster_2"],
        "suggested_direction": "将现有方法迁移到低资源语言场景，评估跨语言迁移能力",
    },
    ...
]
```

#### `limitation_summary: str`

LLM 生成的结构化叙事文本 (300-500 字)，包含：
- 方法学层面的共性局限
- 数据层面的共性局限
- 评估层面的共性局限
- 外部有效性层面的局限

---

## 四、Prompt 模板设计

### 4.1 Analyst Agent Prompts

| Prompt 文件                              | 用途                    | 输入                                            | 输出                         |
| ---------------------------------------- | ----------------------- | ----------------------------------------------- | ---------------------------- |
| `prompts/analyst/topic_clustering.md`    | 对聚类结果命名和总结    | 聚类内论文标题+摘要                             | 聚类名称 + 聚类描述          |
| `prompts/analyst/comparison_matrix.md`   | 生成/补充方法对比矩阵   | 论文分析列表 (method_category + method_details) | 矩阵维度 + 方法值 + 叙事解读 |
| `prompts/analyst/timeline_milestones.md` | 识别研究里程碑          | 按年份排列的论文列表                            | 里程碑事件 + 关键转折点      |
| `prompts/analyst/trend_analysis.md`      | 趋势解读 + 新兴方向识别 | 年度统计 + 主题分布                             | 趋势叙事 + 新兴主题列表      |

### 4.2 Critic Agent Prompts

| Prompt 文件                                 | 用途             | 输入                                 | 输出                               |
| ------------------------------------------- | ---------------- | ------------------------------------ | ---------------------------------- |
| `prompts/critic/quality_assessment.md`      | 方法学严谨性评分 | 论文分析 (method, dataset, findings) | rigor_score (0-10) + 理由 + 优缺点 |
| `prompts/critic/contradiction_detection.md` | 矛盾检测         | 同聚类论文对的核心结论               | 矛盾描述 + 严重程度 + 调和可能性   |
| `prompts/critic/gap_identification.md`      | 研究空白识别     | 聚类覆盖 + 趋势 + 局限性             | 空白列表 + 优先级 + 建议方向       |
| `prompts/critic/limitation_summary.md`      | 局限性汇总       | 所有论文的 limitations 字段          | 结构化叙事 (300-500 字)            |

---

## 五、实施阶段分解

### 阶段 1: Analyst Agent 核心实现

| #   | 任务                | 输出文件                      | 说明                                                                            |
| --- | ------------------- | ----------------------------- | ------------------------------------------------------------------------------- |
| 1.1 | Analyst Prompt 模板 | `prompts/analyst/*.md`        | 4 个模板文件                                                                    |
| 1.2 | 向量聚类工具函数    | `app/agents/analyst_agent.py` | 从 Chroma 获取 embedding → K-means/层次聚类 → 返回聚类分组                      |
| 1.3 | LLM 聚类命名器      | 同上                          | 对每个聚类调用 LLM 生成名称和描述                                               |
| 1.4 | 方法对比矩阵构建器  | 同上                          | 从 `paper_analyses` 的 `method_category` + `method_details` 提取 → LLM 补充维度 |
| 1.5 | 引文网络构建器      | 同上                          | 从 Reader 的 `relations` 构建有向图 → LLM 标注关键/桥梁节点                     |
| 1.6 | 时间线与趋势分析    | 同上                          | 算法统计 + LLM 里程碑识别和趋势解读                                             |
| 1.7 | analyze_node 整合   | 同上                          | `analyze_node(state) -> dict`，注册到 `agent_registry`                          |
| 1.8 | 单元测试            | `tests/test_analyst_agent.py` | Mock LLM + Mock Chroma，验证各子模块输出结构                                    |

#### 验收标准

- [ ] 给定 10 篇 paper_analyses，聚类输出 2-5 个 topic_clusters，每个有名称和描述
- [ ] comparison_matrix 包含从论文中提取的方法和维度
- [ ] citation_network 节点数 = 论文数，边数 ≥ 0
- [ ] timeline 按年份排列，milestone 字段由 LLM 填充
- [ ] research_trends 包含 by_year + by_topic + emerging_topics
- [ ] 论文数 < 5 时跳过分析，直接返回空结果

### 阶段 2: Critic Agent 核心实现

| #   | 任务               | 输出文件                     | 说明                                                        |
| --- | ------------------ | ---------------------------- | ----------------------------------------------------------- |
| 2.1 | Critic Prompt 模板 | `prompts/critic/*.md`        | 4 个模板文件                                                |
| 2.2 | 质量评分器         | `app/agents/critic_agent.py` | LLM rigor_score + bibliometric 归一化 → 综合 quality_score  |
| 2.3 | 矛盾检测器         | 同上                         | 同聚类论文对 LLM 比较 → 矛盾列表 (限制: 聚类内前 10 对)     |
| 2.4 | 研究空白识别器     | 同上                         | 基于聚类覆盖 + 趋势 → LLM 推断空白                          |
| 2.5 | 局限性汇总器       | 同上                         | 聚合 limitations → LLM 叙事化                               |
| 2.6 | 反馈查询生成器     | 同上                         | 检查覆盖空白条件 → 生成 feedback_search_queries             |
| 2.7 | critique_node 整合 | 同上                         | `critique_node(state) -> dict`，注册到 `agent_registry`     |
| 2.8 | DB 回写            | 同上                         | 将 quality_score / relevance_score 写入 `paper_analyses` 表 |
| 2.9 | 单元测试           | `tests/test_critic_agent.py` | Mock LLM，验证评分/矛盾/空白输出结构                        |

#### 验收标准

- [ ] 每篇论文产出 quality_score (0-1) 和 justification
- [ ] 同聚类矛盾检测至少能发现明显冲突 (mock 数据测试)
- [ ] research_gaps 列表含 priority 且有 suggested_direction
- [ ] limitation_summary 为 300-500 字叙事文本
- [ ] 覆盖空白条件触发时 feedback_search_queries 非空
- [ ] quality_score 正确写入 paper_analyses 表

### 阶段 3: 编排层集成

| #   | 任务                       | 输出文件                                          | 说明                                                                                    |
| --- | -------------------------- | ------------------------------------------------- | --------------------------------------------------------------------------------------- |
| 3.1 | 启用 workflow.yaml         | `config/workflow.yaml`                            | `analyze.enabled: true`, `critique.enabled: true`, `check_critic_feedback` 边启用       |
| 3.2 | Orchestrator 导入          | `app/agents/orchestrator.py`                      | 添加 `import app.agents.analyst_agent` / `critic_agent`                                 |
| 3.3 | check_critic_feedback 节点 | `app/agents/routing.py`                           | 已有 `route_after_critique`，验证路由逻辑                                               |
| 3.4 | SSE 事件扩展               | `app/services/event_publisher.py`                 | 新增 `analyze_start` / `analyze_complete` / `critique_start` / `critique_complete` 事件 |
| 3.5 | Token 用量追踪             | `app/agents/analyst_agent.py` / `critic_agent.py` | `token_usage.by_agent["analyze"]` / `by_agent["critique"]`                              |
| 3.6 | 集成测试                   | `tests/test_workflow_v03.py`                      | Mock Agent，验证 6-Agent 完整 DAG 流转 + 反馈环路                                       |

#### 验收标准

- [ ] `workflow.yaml` 启用后工作流包含 analyze + critique 节点
- [ ] 完整 DAG 流转: search → read → analyze → critique → generate_outline → write → export
- [ ] Critic 触发反馈时正确回溯到 Search (不超过 2 次)
- [ ] SSE 客户端收到 analyze/critique 进度事件
- [ ] Token 用量分 Agent 统计

### 阶段 4: Writer Agent 增强

| #   | 任务                | 输出文件                                  | 说明                                                                   |
| --- | ------------------- | ----------------------------------------- | ---------------------------------------------------------------------- |
| 4.1 | 大纲生成器增强      | `app/agents/writer_agent.py`              | 大纲结构参考 topic_clusters 组织章节                                   |
| 4.2 | 章节写作增强        | 同上                                      | 嵌入 comparison_matrix、research_trends、contradictions                |
| 4.3 | 研究空白章节        | 同上                                      | 自动生成 "Research Gaps & Future Directions" 章节                      |
| 4.4 | 引用权重策略        | 同上                                      | quality_score ≥ 0.7 优先引用, < 0.3 降级                               |
| 4.5 | 新增输出类型 Prompt | `prompts/writer/methodology_review.md` 等 | Methodology Review / Research Roadmap / Gap Report / Trend Report 模板 |
| 4.6 | 输出类型路由        | `app/agents/writer_agent.py`              | 根据 `output_types` 选择不同写作策略                                   |
| 4.7 | 测试更新            | `tests/test_writer_agent.py`              | 验证新输出类型生成                                                     |

#### 验收标准

- [ ] Full Review 大纲结构映射 topic_clusters
- [ ] Methodology Review 包含 comparison_matrix 表格
- [ ] Gap Report 包含 research_gaps 列表
- [ ] Trend Report 包含趋势分析叙事
- [ ] 高质量论文 (score ≥ 0.7) 引用频率高于低质量论文

### 阶段 5: 前端分析结果展示

| #    | 任务                     | 输出文件                                               | 说明                                                                   |
| ---- | ------------------------ | ------------------------------------------------------ | ---------------------------------------------------------------------- |
| 5.1  | 分析结果类型定义         | `frontend/src/types/analysis.ts`                       | AnalystOutput / CriticOutput 类型                                      |
| 5.2  | 分析结果 API             | `frontend/src/api/analysis.ts`                         | 获取分析/评估结果接口                                                  |
| 5.3  | ClusterView 聚类视图     | `frontend/src/components/Analysis/ClusterView.tsx`     | 聚类列表 + 每个聚类的论文标签                                          |
| 5.4  | ComparisonTable 对比矩阵 | `frontend/src/components/Analysis/ComparisonTable.tsx` | Ant Design Table 渲染方法对比矩阵                                      |
| 5.5  | TrendChart 趋势图        | `frontend/src/components/Analysis/TrendChart.tsx`      | 简单柱状/折线图 (可选用 @ant-design/charts 或纯 CSS)                   |
| 5.6  | GapList 研究空白列表     | `frontend/src/components/Analysis/GapList.tsx`         | 空白列表 + 优先级标签 + 建议方向                                       |
| 5.7  | QualityBadge 质量标识    | `frontend/src/components/Analysis/QualityBadge.tsx`    | PaperCard 上显示质量评分 (绿/黄/红圆点)                                |
| 5.8  | ProjectPage 集成         | `frontend/src/pages/ProjectPage.tsx`                   | 右侧面板新增「分析」Tab                                                |
| 5.9  | 新输出类型支持           | `frontend/src/utils/constants.ts`                      | 解锁 Methodology Review / Gap Report / Trend Report / Research Roadmap |
| 5.10 | SSE 事件处理             | `frontend/src/hooks/useSSE.ts`                         | 处理 analyze/critique 事件                                             |

#### 验收标准

- [ ] 项目完成后右侧「分析」Tab 显示聚类视图 + 对比矩阵 + 趋势
- [ ] PaperCard 显示质量评分标识
- [ ] 研究空白列表在综述 Tab 或独立 Tab 中展示
- [ ] 首页可选择新增的 4 种输出类型
- [ ] SSE 正确推送 Analyst/Critic 进度事件

### 阶段 6: 端到端测试

| #   | 任务                | 输出文件                     | 说明                             |
| --- | ------------------- | ---------------------------- | -------------------------------- |
| 6.1 | E2E 测试 (Mock LLM) | `tests/test_e2e_v03.py`      | 完整 6-Agent 流程                |
| 6.2 | E2E 测试 (Live LLM) | `tests/test_e2e_live_v03.py` | `@pytest.mark.live`，CI 不运行   |
| 6.3 | 前端构建验证        | —                            | TypeScript 零错误 + 生产构建通过 |
| 6.4 | 文档更新            | `CHANGELOG.md`, `README.md`  | 更新功能说明和输出类型列表       |

#### 验收标准

- [ ] Mock E2E: 创建项目 → 检索 → 精读 → **分析 → 评估** → 写作 → 导出
- [ ] 反馈环路测试: Critic 触发补充检索 → 第二轮分析 → 终止
- [ ] 4 种新输出类型均可生成 Markdown 和 Word 导出
- [ ] Docker Compose 部署新版本正常运行

---

## 六、文件产出清单

```
backend/
├── app/agents/
│   ├── analyst_agent.py              # [阶段 1] 新增
│   └── critic_agent.py               # [阶段 2] 新增
├── prompts/
│   ├── analyst/
│   │   ├── topic_clustering.md       # [阶段 1] 新增
│   │   ├── comparison_matrix.md      # [阶段 1] 新增
│   │   ├── timeline_milestones.md    # [阶段 1] 新增
│   │   └── trend_analysis.md         # [阶段 1] 新增
│   ├── critic/
│   │   ├── quality_assessment.md     # [阶段 2] 新增
│   │   ├── contradiction_detection.md# [阶段 2] 新增
│   │   ├── gap_identification.md     # [阶段 2] 新增
│   │   └── limitation_summary.md     # [阶段 2] 新增
│   └── writer/
│       ├── methodology_review.md     # [阶段 4] 新增
│       ├── gap_report.md             # [阶段 4] 新增
│       ├── trend_report.md           # [阶段 4] 新增
│       └── research_roadmap.md       # [阶段 4] 新增
├── tests/
│   ├── test_analyst_agent.py         # [阶段 1] 新增
│   ├── test_critic_agent.py          # [阶段 2] 新增
│   ├── test_workflow_v03.py          # [阶段 3] 新增
│   └── test_e2e_v03.py              # [阶段 6] 新增
├── config/
│   └── workflow.yaml                 # [阶段 3] 修改 (启用节点)
└── app/agents/
    ├── orchestrator.py               # [阶段 3] 修改 (添加 import)
    └── writer_agent.py               # [阶段 4] 修改 (增强)

frontend/src/
├── types/
│   └── analysis.ts                   # [阶段 5] 新增
├── api/
│   └── analysis.ts                   # [阶段 5] 新增
├── components/Analysis/
│   ├── ClusterView.tsx               # [阶段 5] 新增
│   ├── ComparisonTable.tsx           # [阶段 5] 新增
│   ├── TrendChart.tsx                # [阶段 5] 新增
│   ├── GapList.tsx                   # [阶段 5] 新增
│   └── QualityBadge.tsx              # [阶段 5] 新增
├── pages/
│   └── ProjectPage.tsx               # [阶段 5] 修改
├── hooks/
│   └── useSSE.ts                     # [阶段 5] 修改
└── utils/
    └── constants.ts                  # [阶段 5] 修改

# 新增文件: ~25 个
# 修改文件: ~8 个
```

---

## 七、依赖关系

```
阶段 1 (Analyst Agent)   ──┐
                            ├──▶ 阶段 3 (编排集成)
阶段 2 (Critic Agent)    ──┘        │
                                    ▼
                            阶段 4 (Writer 增强) ──▶ 阶段 6 (E2E 测试)
                                    │
                            阶段 5 (前端展示) ─────┘
```

- **阶段 1 和 2 可并行**，互不依赖
- **阶段 3 依赖 1 + 2**，需要两个 Agent 都就绪
- **阶段 4 和 5 可并行**，均依赖阶段 3
- **阶段 6 依赖 4 + 5**

---

## 八、技术风险

| 风险                                        | 影响 | 缓解策略                                                               |
| ------------------------------------------- | ---- | ---------------------------------------------------------------------- |
| Analyst 聚类质量不稳定                      | 中   | 提供聚类数量参数 (k=auto)，使用轮廓系数自动选 k; 结果可 HITL 调整      |
| Critic 矛盾检测 O(N²) 成本                  | 高   | 仅在同聚类内检测 (大幅减少对数); 限制每聚类最多检测 10 对              |
| LLM 质量评分不一致                          | 中   | 使用具体 Rubric Prompt; 批量评估降低变异; 结合 Bibliometric 信号稳定化 |
| Analyst + Critic 增加 Token 消耗            | 高   | 预估: 100 篇论文约增加 50K-100K tokens; 分批处理 + 预算检查节点        |
| 新输出类型 (Methodology Review 等) 写作质量 | 中   | 专用 Prompt 模板; 复用已有 HITL 审阅机制                               |

---

## 九、Token 消耗预估

基于 100 篇论文的典型场景:

| Agent                                | 子任务                     | 预估 Token (input + output) |
| ------------------------------------ | -------------------------- | --------------------------- |
| Analyst                              | 聚类命名 (5 个聚类)        | ~10K                        |
| Analyst                              | 对比矩阵                   | ~8K                         |
| Analyst                              | 趋势分析                   | ~5K                         |
| Analyst                              | 里程碑识别                 | ~5K                         |
| Critic                               | 质量评分 (100 篇, 批量 10) | ~30K                        |
| Critic                               | 矛盾检测 (~20 对)          | ~15K                        |
| Critic                               | 空白识别                   | ~8K                         |
| Critic                               | 局限性汇总                 | ~5K                         |
| **Analyst + Critic 总计**            |                            | **~86K tokens**             |
| **v0.1 现有** (Search+Reader+Writer) |                            | **~100K-150K tokens**       |
| **v0.3 总计**                        |                            | **~186K-236K tokens**       |

费用影响 (GPT-4o): 约增加 $0.20-$0.25/次综述。
