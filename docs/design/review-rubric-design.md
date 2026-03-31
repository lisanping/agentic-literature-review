# 综述级评分标准设计 (Review-Level Rubric)

> **文档版本**: v1.0
> **创建日期**: 2026-03-31
> **前置文档**: [系统架构](system-architecture.md) · [v0.5 实施计划](../dev/v05-implementation-plan.md)
> **目标**: 设计一套共享的综述级评分标准 (Rubric)，同时指导 Writer Agent 的生成行为和 Critic Agent 的评估判断，实现"生成-评估对齐"

---

## 一、动机与问题

### 1.1 当前现状

| 环节                 | 现有机制                                                              | 不足                                                                       |
| -------------------- | --------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| **Writer 写作**      | Prompt 中包含写作要求（"使用学术风格"、"逻辑连贯"），但无量化标准     | Writer 不知道下游评估的具体维度和阈值，写作方向靠 Prompt 经验              |
| **Critic 评估**      | `quality_assessment.md` 评估单篇论文的方法学严谨性 (rigor_score 0-10) | 仅评估输入论文质量，**不评估 Writer 生成的综述本身**                       |
| **Coherence Review** | `coherence_review.md` 做连贯性审查 (overall_quality 0-1)              | 维度模糊，仅 Writer 内部自查，评估结果不回传给反馈环路                     |
| **反馈环路**         | `route_after_draft_review` 仅依赖用户手动 `revision_instructions`     | 无自动化质量门控——即使综述质量低，不设 revision_instructions 就直接 export |

### 1.2 核心洞察

参考 UI 设计领域的实践：**同一套评分标准同时提供给生成器和评估器**，可以消除"生成器不知道评估器在意什么"的错位。这一模式适用于文献综述场景：

- **Writer（生成器）**：写作时以 Rubric 为目标进行自检
- **Critic（评估器）**：用同一套 Rubric 对综述评分，输出结构化反馈
- **路由决策**：基于 Rubric 分数自动决定是否触发修订，减少对人工审阅的依赖

---

## 二、Rubric 四维度定义

### 2.1 维度设计

从 UI 设计的四维度（设计质量 / 原创性 / 工艺 / 功能性）映射到学术综述领域：

| #   | 维度           | 英文标识    | 定义                                                                                     | 评分范围 |
| --- | -------------- | ----------- | ---------------------------------------------------------------------------------------- | -------- |
| 1   | **综合连贯性** | `coherence` | 综述是否形成统一叙事？章节之间是否有自然过渡和逻辑递进？还是各论文摘要的简单拼接？       | 1-10     |
| 2   | **分析深度**   | `depth`     | 是否有跨论文的模式识别、矛盾讨论、趋势归纳、研究空白推断？还是仅复述各论文结论？         | 1-10     |
| 3   | **学术严谨性** | `rigor`     | 引用是否准确完整？论证逻辑是否严密？术语使用是否一致？方法描述是否完整？覆盖面是否均衡？ | 1-10     |
| 4   | **实用价值**   | `utility`   | 读者能否从综述中理解领域现状？能否找到关键文献和方法对比？能否明确未来研究方向？         | 1-10     |

### 2.2 详细评分量表

#### 维度 1: 综合连贯性 (Coherence)

| 分数 | 水平 | 典型表现                                                                                     |
| ---- | ---- | -------------------------------------------------------------------------------------------- |
| 9-10 | 优秀 | 全文围绕核心研究问题展开统一叙事，章节之间有清晰的逻辑递进和过渡段落，结论自然地从论述中产生 |
| 7-8  | 良好 | 有明确的叙事主线，大多数章节衔接自然，偶尔过渡稍显生硬                                       |
| 5-6  | 及格 | 章节主题清晰但各自独立，缺乏跨章节的叙事线索，读起来像分节报告                               |
| 3-4  | 不足 | 章节之间逻辑跳跃明显，缺少过渡，像是逐篇论文的摘要集合                                       |
| 1-2  | 很差 | 文本碎片化，没有统一结构，段落之间无逻辑关联                                                 |

#### 维度 2: 分析深度 (Depth)

| 分数 | 水平 | 典型表现                                                                               |
| ---- | ---- | -------------------------------------------------------------------------------------- |
| 9-10 | 优秀 | 提出原创性的分类框架或研究趋势归纳，有深刻的矛盾分析和研究空白推断，超越文献本身的洞察 |
| 7-8  | 良好 | 有跨论文的对比分析，识别出主要趋势和分歧，对研究空白有合理讨论                         |
| 5-6  | 及格 | 按主题归类组织了论文，有基本的比较，但缺乏深入的交叉分析                               |
| 3-4  | 不足 | 以复述各论文结论为主，缺少跨论文综合分析                                               |
| 1-2  | 很差 | 纯粹罗列论文摘要，无任何分析或综合                                                     |

#### 维度 3: 学术严谨性 (Rigor)

| 分数 | 水平 | 典型表现                                                         |
| ---- | ---- | ---------------------------------------------------------------- |
| 9-10 | 优秀 | 引用准确完整，论证逻辑严密，术语一致，覆盖面均衡，无遗漏关键文献 |
| 7-8  | 良好 | 引用基本准确，逻辑清晰，极少数术语不一致或引用遗漏               |
| 5-6  | 及格 | 引用存在少量问题（格式不一、遗漏），逻辑整体通顺但有薄弱环节     |
| 3-4  | 不足 | 引用问题较多，论证有漏洞，对某些方法的描述不够准确               |
| 1-2  | 很差 | 引用严重缺失或错误，论证混乱，术语使用不当                       |

#### 维度 4: 实用价值 (Utility)

| 分数 | 水平 | 典型表现                                                             |
| ---- | ---- | -------------------------------------------------------------------- |
| 9-10 | 优秀 | 读者可以快速建立领域全景认知，理解方法优缺点，获得清晰的研究方向建议 |
| 7-8  | 良好 | 提供了有价值的领域概览和方法比较，研究方向有参考价值                 |
| 5-6  | 及格 | 覆盖了主要文献，但对方法比较和未来方向的指导性不足                   |
| 3-4  | 不足 | 信息密度低，读者难以从中获得超越单篇论文阅读的价值                   |
| 1-2  | 很差 | 几乎没有实用价值，不如直接阅读原始论文                               |

### 2.3 输出类型加权

不同输出类型对四个维度的权重不同：

| 输出类型             | coherence | depth | rigor | utility | 说明                   |
| -------------------- | --------- | ----- | ----- | ------- | ---------------------- |
| `full_review`        | 0.30      | 0.25  | 0.25  | 0.20    | 均衡，连贯性最重要     |
| `methodology_review` | 0.20      | 0.30  | 0.30  | 0.20    | 深度和严谨性优先       |
| `gap_report`         | 0.15      | 0.35  | 0.20  | 0.30    | 深度分析和实用价值优先 |
| `trend_report`       | 0.25      | 0.30  | 0.20  | 0.25    | 深度和连贯性优先       |
| `research_roadmap`   | 0.15      | 0.25  | 0.15  | 0.45    | 实用价值最重要         |

加权总分计算：
$$\text{weighted\_score} = \sum_{i=1}^{4} w_i \times s_i$$

其中 $w_i$ 为维度权重，$s_i$ 为维度分数 (1-10)。

---

## 三、架构设计

### 3.1 核心原则

**一份 Rubric，两处使用**：

```
                    ┌──────────────────┐
                    │  review_rubric   │
                    │  (共享模板)       │
                    └────────┬─────────┘
                  ┌──────────┼──────────┐
                  ▼                     ▼
        ┌─────────────────┐   ┌─────────────────┐
        │  Writer Agent   │   │  Critic Agent   │
        │  ─────────────  │   │  ─────────────  │
        │  在写作时以     │   │  在评估时用     │
        │  Rubric 为目标  │   │  同一 Rubric    │
        │  进行自检       │   │  打分 + 反馈    │
        └────────┬────────┘   └────────┬────────┘
                 │                     │
                 ▼                     ▼
        ┌─────────────────┐   ┌─────────────────┐
        │  生成综述草稿   │   │  综述级评估报告 │
        │  (quality-aware │   │  (4 维度分数 +  │
        │   writing)      │   │   修改建议)     │
        └─────────────────┘   └────────┬────────┘
                                       │
                                       ▼
                              ┌─────────────────┐
                              │  路由决策       │
                              │  score < 6 →    │
                              │  auto-revise    │
                              └─────────────────┘
```

### 3.2 Prompt 模板结构

```
prompts/
├── shared/                          # [新增] 共享模板
│   └── review_rubric.md             # Rubric 定义模板
├── writer/
│   ├── section_writing.md           # [修改] 注入 Rubric 引用
│   ├── coherence_review.md          # [修改] 采用 Rubric 维度
│   └── ... (其他不变)
└── critic/
    ├── review_assessment.md         # [新增] 综述级评估 Prompt
    └── ... (其他不变)
```

### 3.3 与现有 Prompt 管理的兼容

当前 `PromptManager` 使用 `FileSystemLoader`，已原生支持 Jinja2 的 `{% include %}` 指令：

```python
# PromptManager 使用 FileSystemLoader，天然支持 include
self.env = Environment(
    loader=FileSystemLoader(str(self.prompts_dir)),
    autoescape=False,
)
```

因此 Writer 和 Critic 的 Prompt 模板可以通过 `{% include "shared/review_rubric.md" %}` 引用共享 Rubric，无需修改 `PromptManager` 代码。

### 3.4 ReviewState 扩展

```python
# app/agents/state.py 新增字段
class ReviewState(TypedDict):
    # ... 现有字段 ...

    # ── Review Rubric Assessment (v0.5+) ──
    review_scores: dict | None          # {"coherence": 7, "depth": 6, "rigor": 8, "utility": 7, "weighted": 7.1}
    review_feedback: list[dict] | None  # [{"dimension": "coherence", "issue": "...", "suggestion": "..."}]

    # ── Auto-revision loop (迭代合同) ──
    revision_iteration_count: int       # 当前自动修订轮次 (0 = 初稿，最大 MAX_REVISION_ITERATIONS)
    revision_contract: dict | None      # 本轮迭代合同：{"focus_dimensions": ["depth", "coherence"],
                                        #   "targets": {"depth": 7, "coherence": 7},
                                        #   "instructions": "具体修改指令"}
    revision_score_history: list[dict]  # 每轮评分快照 [{"iteration": 0, "scores": {...}}, ...]
```

### 3.5 工作流集成点

在现有 DAG 中，综述级评估发生在 **`write_review` 之后、`human_review_draft` 之前**，新增自动修订环路：

```
... → write_review → verify_citations → [review_assessment] → route ──┐
                                                          │           │
                                         weighted ≥ 6.0 或│           │ weighted < 6.0 且
                                         迭代上限/收敛停滞│           │ iteration < MAX
                                                          ▼           │
                                                 human_review_draft   │
                                                          │           │
                                             ┌────────────┤           │
                                 user 给出    │    无修改指令           │
                             revision_instr  │            │           │
                                             ▼            ▼           │
                                        revise_review   export       │
                                        (用户指令修订)                │
                                             │                        │
                                             ▼                        │
                                           export                     │
                                                                      │
                     ┌────────────────────────────────────────────────┘
                     ▼
                auto_revise (按迭代合同修订)
                     │
                     ▼
              verify_citations (重新验证)
                     │
                     ▼
             [review_assessment] (重新评分)
                     │
                     ▼
                 route ... (循环判断)
```

#### 方案 A: 新增独立节点 `review_assessment`

- 在 `verify_citations` 和 `human_review_draft` 之间插入新节点
- 需要修改 `workflow.yaml` 添加节点和路由
- 优点：职责清晰、可独立禁用
- 缺点：增加 DAG 节点数量、增加一次 LLM 调用

#### 方案 B: 嵌入 Critic 现有流程 ✅ (推荐)

- 在 `critique_node` 中新增一个步骤 `assess_review()`
- 该步骤在综述初稿生成后才执行（通过 `state.get("full_draft")` 判断）
- 首次走 critique（无 full_draft）时执行原有论文级评估
- 用户确认大纲后走 Writer → 生成 full_draft → 再次 critique 时执行综述级评估
- 优点：复用现有节点、无需改 DAG
- 缺点：Critic 节点职责略有扩展

#### 方案 C: 嵌入 Writer coherence_review ✅ (推荐)

- 将现有的 `coherence_review` 升级为 Rubric-based 评估
- `write_review_node` 内部已调用 `coherence_review()`，可直接改造
- 评估结果写入 `state["review_scores"]` 和 `state["review_feedback"]`
- 优点：零 DAG 变更、复用现有调用点
- 缺点：评估者与生成者是同一个 Agent（自評）

#### 推荐方案：C + B 组合

1. **Writer 侧（方案 C）**：升级 `coherence_review` 为 Rubric 自检，写作时意识到评分标准
2. **Critic 侧（方案 B）**：在 `critique_node` 中增加综述级评估步骤，作为独立的第三方评估
3. **路由增强**：`route_after_draft_review` 可参考 `review_scores` 辅助决策

这样实现了"生成器自检 + 评估器独立评分"的双重机制。

---

## 四、详细设计

### 4.1 共享 Rubric 模板

**文件**: `prompts/shared/review_rubric.md`

此模板被 Writer 和 Critic 的 Prompt 通过 `{% include %}` 引入，确保两者使用完全相同的评分标准。

```markdown
## 综述评分标准 (Review Rubric)

请从以下 4 个维度评估综述质量，每个维度 1-10 分：

### 1. 综合连贯性 (Coherence) — 权重 {{ weights.coherence }}
综述是否形成统一叙事？章节之间是否有自然过渡和逻辑递进？
- 9-10: 全文统一叙事，章节逻辑递进，过渡自然
- 7-8: 叙事主线明确，偶尔过渡生硬
- 5-6: 章节独立，缺乏跨章节叙事线索
- 3-4: 逻辑跳跃明显，像摘要集合
- 1-2: 碎片化，无统一结构

### 2. 分析深度 (Depth) — 权重 {{ weights.depth }}
是否有跨论文的模式识别、矛盾讨论、趋势归纳、研究空白推断？
- 9-10: 原创性分析框架或趋势归纳，超越文献本身的洞察
- 7-8: 有跨论文对比，识别趋势和分歧
- 5-6: 按主题归类，有基本比较
- 3-4: 以复述结论为主
- 1-2: 纯粹罗列摘要

### 3. 学术严谨性 (Rigor) — 权重 {{ weights.rigor }}
引用准确性、论证逻辑、术语一致性、方法描述完整度、覆盖面均衡性。
- 9-10: 引用准确完整，逻辑严密，术语一致
- 7-8: 基本准确，极少数不一致
- 5-6: 少量引用问题，逻辑整体通顺
- 3-4: 引用问题较多，论证有漏洞
- 1-2: 引用严重缺失，论证混乱

### 4. 实用价值 (Utility) — 权重 {{ weights.utility }}
读者能否理解领域现状、找到关键文献和方法对比、明确未来研究方向？
- 9-10: 快速建立领域全景认知，获得清晰研究方向建议
- 7-8: 有价值的概览和比较
- 5-6: 覆盖主要文献，指导性不足
- 3-4: 信息密度低
- 1-2: 几乎没有超越单篇论文的价值
```

### 4.2 Writer 集成 — 升级 `coherence_review.md`

**修改**: `prompts/writer/coherence_review.md`

在现有连贯性审查 Prompt 中注入 Rubric，使 Writer 的自检从模糊的 5 维度变为量化的 4 维度评分。

修改后 Prompt 将通过 `{% include "shared/review_rubric.md" %}` 引入标准，并要求 LLM 输出结构化的 4 维度分数和逐维度改进建议。

**输出格式变更**：

```json
{
  "scores": {
    "coherence": 7,
    "depth": 6,
    "rigor": 8,
    "utility": 7
  },
  "weighted_score": 7.05,
  "issues": [
    {
      "dimension": "depth",
      "location": "第 3 节",
      "description": "缺少跨论文的方法对比分析",
      "suggestion": "增加 [2] 和 [5] 的方法对比段落"
    }
  ],
  "summary": "总体评价"
}
```

### 4.3 Critic 集成 — 新增 `review_assessment.md`

**新增**: `prompts/critic/review_assessment.md`

独立于 Writer 的第三方评估 Prompt，使用相同 Rubric 但从评审视角出发。

与 Writer 自评的区别：
- Writer 自评是"我写完了，自查一下"
- Critic 评估是"作为独立审稿人，评估这篇综述"

Critic 评估结果写入 `state["review_scores"]` 和 `state["review_feedback"]`，供路由和前端使用。

### 4.4 Critic Agent 代码变更

在 `critique_node()` 中新增综述级评估步骤：

```python
async def critique_node(state: ReviewState) -> dict:
    # ... 现有论文级评估逻辑 ...

    # ── 综述级评估 (仅当 full_draft 存在时执行) ──
    full_draft = state.get("full_draft")
    if full_draft:
        review_scores, review_feedback = await assess_review(
            full_draft=full_draft,
            user_query=state.get("user_query", ""),
            output_type=output_type,
            llm=llm,
            prompt_manager=prompt_manager,
            token_usage=token_usage,
        )
        updates["review_scores"] = review_scores
        updates["review_feedback"] = review_feedback

    return updates
```

新增 `assess_review()` 函数：

```python
# 输出类型权重映射
RUBRIC_WEIGHTS = {
    "full_review":        {"coherence": 0.30, "depth": 0.25, "rigor": 0.25, "utility": 0.20},
    "methodology_review": {"coherence": 0.20, "depth": 0.30, "rigor": 0.30, "utility": 0.20},
    "gap_report":         {"coherence": 0.15, "depth": 0.35, "rigor": 0.20, "utility": 0.30},
    "trend_report":       {"coherence": 0.25, "depth": 0.30, "rigor": 0.20, "utility": 0.25},
    "research_roadmap":   {"coherence": 0.15, "depth": 0.25, "rigor": 0.15, "utility": 0.45},
}

async def assess_review(
    full_draft: str,
    user_query: str,
    output_type: str,
    llm: LLMRouter,
    prompt_manager: PromptManager,
    token_usage: dict | None = None,
) -> tuple[dict, list[dict]]:
    """Assess the generated review using the shared rubric.

    Returns:
        (scores_dict, feedback_list)
    """
    weights = RUBRIC_WEIGHTS.get(output_type, RUBRIC_WEIGHTS["full_review"])

    prompt = prompt_manager.render(
        "critic", "review_assessment",
        user_query=user_query,
        full_draft=full_draft,
        weights=weights,
    )

    response_text, token_usage = await llm.call(
        prompt=prompt,
        agent_name="critic",
        task_type="review_assessment",
        token_usage=token_usage,
    )

    parsed = _parse_json_response(response_text)
    if not parsed:
        return {"coherence": 5, "depth": 5, "rigor": 5, "utility": 5, "weighted": 5.0}, []

    scores = parsed.get("scores", {})
    weighted = sum(scores.get(d, 5) * weights.get(d, 0.25) for d in weights)
    scores["weighted"] = round(weighted, 2)

    return scores, parsed.get("issues", [])
```

### 4.5 Writer coherence_review 变更

升级 `coherence_review()` 函数，解析新的 4 维度输出格式：

```python
async def coherence_review(
    full_draft: str,
    user_query: str,
    output_type: str,
    llm: LLMRouter,
    prompt_manager: PromptManager,
    token_usage: dict | None = None,
) -> tuple[float, list[dict], dict]:
    """Perform rubric-based self-assessment of the draft.

    Returns:
        (weighted_score, issues, scores_dict)
    """
    weights = RUBRIC_WEIGHTS.get(output_type, RUBRIC_WEIGHTS["full_review"])

    prompt = prompt_manager.render(
        "writer", "coherence_review",
        user_query=user_query,
        full_draft=full_draft,
        weights=weights,
    )
    # ... LLM call + parse ...
```

### 4.6 路由增强 — 迭代合同与自动修订

#### 4.6.1 问题回顾

**当前**: `route_after_draft_review` 仅依赖用户 `revision_instructions`，无自动化质量门控。

**目标**: 在 Writer-Critic 之间引入**迭代合同 (Iteration Contract)** 驱动的自动修订环路，同时保留 HITL 作为最终兜底。

#### 4.6.2 迭代合同机制

在每轮自动修订开始前，系统基于上一轮评分结果生成一份**迭代合同**——明确本轮修订的聚焦维度、目标分数和具体修改指令：

```python
# 迭代合同示例
{
    "focus_dimensions": ["depth", "coherence"],   # 聚焦得分最低的 1-2 个维度
    "targets": {"depth": 7, "coherence": 7},        # 本轮目标分数（当前分 +1~2）
    "instructions": "1. 在第3节增加 [2] 和 [5] 方法的对比分析段落；"
                    "2. 在第2→3节之间补充过渡段落，串联聚类分析与方法对比的逻辑",
    "previous_scores": {"coherence": 5, "depth": 4, "rigor": 8, "utility": 7, "weighted": 5.65}
}
```

核心原则：
- **聚焦而非泛化**：每轮合同最多关注 2 个最低分维度，避免 Writer 大改引入新问题
- **目标递增**：target = min(current_score + 2, 10)，设定可达成的增量目标
- **具体可执行**：instructions 从 `review_feedback` 中提取最相关的 issue，转化为修改指令

#### 4.6.3 生成合同的函数

```python
MAX_REVISION_ITERATIONS = 2        # 自动修订最多 2 轮
AUTO_REVISE_THRESHOLD = 6.0        # weighted_score < 6.0 触发自动修订
MAX_CONTRACT_DIMENSIONS = 2        # 每轮合同最多聚焦 2 个维度

def generate_revision_contract(
    review_scores: dict,
    review_feedback: list[dict],
) -> dict:
    """Generate an iteration contract from the latest review assessment.

    Selects the lowest-scoring dimensions (up to MAX_CONTRACT_DIMENSIONS),
    sets incremental targets, and extracts actionable instructions from feedback.
    """
    dimensions = ["coherence", "depth", "rigor", "utility"]
    scored = [(d, review_scores.get(d, 5)) for d in dimensions]
    scored.sort(key=lambda x: x[1])  # ascending by score

    focus = scored[:MAX_CONTRACT_DIMENSIONS]
    targets = {d: min(s + 2, 10) for d, s in focus}
    focus_dims = [d for d, _ in focus]

    # Extract relevant feedback items for focused dimensions
    relevant_feedback = [
        fb for fb in review_feedback
        if fb.get("dimension") in focus_dims
    ]
    instructions = "\n".join(
        f"- [{fb['dimension']}] {fb.get('location', '')}: {fb.get('suggestion', fb.get('description', ''))}"
        for fb in relevant_feedback[:6]  # cap at 6 items to control prompt length
    )

    return {
        "focus_dimensions": focus_dims,
        "targets": targets,
        "instructions": instructions or "请改进上述低分维度的整体质量",
        "previous_scores": review_scores,
    }
```

#### 4.6.4 路由函数重构

将原有的单一路由拆为两级路由：

**路由 1**: `route_after_review_assessment` — 在 Critic 综述级评估之后，决定是自动修订还是进入 HITL

```python
def route_after_review_assessment(state: ReviewState) -> str:
    """Route after Critic's review-level assessment.

    Decision logic:
      1. weighted_score >= AUTO_REVISE_THRESHOLD → human_review_draft (质量达标)
      2. revision_iteration_count >= MAX_REVISION_ITERATIONS → human_review_draft (迭代上限)
      3. 本轮分数未提升（相比上轮） → human_review_draft (收敛停滞，避免死循环)
      4. Otherwise → auto_revise (按迭代合同自动修订)
    """
    scores = state.get("review_scores", {})
    weighted = scores.get("weighted", 10.0)
    iteration = state.get("revision_iteration_count", 0)
    history = state.get("revision_score_history", [])

    # 质量达标 → 进入人工审阅
    if weighted >= AUTO_REVISE_THRESHOLD:
        return "human_review_draft"

    # 迭代上限 → 强制进入人工审阅
    if iteration >= MAX_REVISION_ITERATIONS:
        return "human_review_draft"

    # 单调收敛检查：如果本轮分数没有比上轮提升，停止自动修订
    if len(history) >= 2:
        prev_weighted = history[-2].get("scores", {}).get("weighted", 0)
        if weighted <= prev_weighted:
            return "human_review_draft"

    return "auto_revise"
```

**路由 2**: `route_after_draft_review` — HITL 暂停后，用户最终决策（保持不变）

```python
def route_after_draft_review(state: ReviewState) -> str:
    """Route after user reviews the draft (HITL).

    保持现有行为：用户给出 revision_instructions → revise_review，否则 → export。
    此时用户可以看到 review_scores 和 review_feedback 辅助决策。
    """
    if state.get("revision_instructions"):
        return "revise_review"
    return "export"
```

#### 4.6.5 自动修订节点

```python
async def auto_revise_node(state: ReviewState) -> dict:
    """Auto-revise the draft based on the iteration contract.

    Unlike human-triggered revise_review (which uses user instructions),
    this node uses the Critic-generated revision_contract.
    """
    contract = generate_revision_contract(
        review_scores=state.get("review_scores", {}),
        review_feedback=state.get("review_feedback", []),
    )
    iteration = state.get("revision_iteration_count", 0)

    log.info(
        "auto_revise_start",
        iteration=iteration + 1,
        focus=contract["focus_dimensions"],
        targets=contract["targets"],
    )

    # 复用现有 revise_review 的核心逻辑，但用 contract.instructions 替代 user instructions
    revised_draft = await _revise_draft(
        full_draft=state["full_draft"],
        revision_instructions=contract["instructions"],
        user_query=state.get("user_query", ""),
        llm=llm,
        prompt_manager=prompt_manager,
        token_usage=state.get("token_usage"),
    )

    # 记录评分历史
    history = list(state.get("revision_score_history", []))
    history.append({"iteration": iteration, "scores": state.get("review_scores", {})})

    return {
        "full_draft": revised_draft,
        "revision_iteration_count": iteration + 1,
        "revision_contract": contract,
        "revision_score_history": history,
    }
```

#### 4.6.6 workflow.yaml 变更

```yaml
workflow:
  nodes:
    # ... 前面不变 ...
    - name: write_review
    - name: verify_citations
    - name: review_assessment          # [新增] Critic 综述级评估
    - name: auto_revise                # [新增] 自动修订（仅条件路由可达）
      sequential: false
    - name: human_review_draft
      interrupt: true
    - name: revise_review
      sequential: false
    - name: export

  edges:
    # ... 前面不变 ...
    - from: review_assessment
      router: route_after_review_assessment
      targets: [auto_revise, human_review_draft]   # [新增] 评估后路由
    - from: auto_revise
      to: verify_citations                          # [新增] 修订后重新验证→重新评估
    - from: human_review_draft
      router: route_after_draft_review
      targets: [revise_review, export]              # 保持不变
```

#### 4.6.7 完整路由流程图

```
write_review
    │
    ▼
verify_citations
    │
    ▼
┌─────────────────────────┐
│ review_assessment       │ ◄──────────────────────────┐
│ (Critic 综述级评估)     │                            │
└────────────┬────────────┘                            │
             │                                         │
    route_after_review_assessment                      │
      ┌──────┴──────┐                                  │
      │             │                                  │
   达标/上限/     不达标且                              │
   收敛停滞      可继续迭代                             │
      │             │                                  │
      ▼             ▼                                  │
human_review    auto_revise                            │
   _draft       (按迭代合同修订)                        │
      │             │                                  │
 route_after_   verify_citations ──► review_assessment ┘
 draft_review     (重新验证)
   ┌──┴──┐
   │     │
   ▼     ▼
revise  export
_review
(用户指令修订)
   │
   ▼
 export
```

#### 4.6.8 设计决策

| 决策                         | 选择                   | 原因                                                  |
| ---------------------------- | ---------------------- | ----------------------------------------------------- |
| 自动修订触发阈值             | weighted < 6.0         | 6.0 对应"及格"水平，低于此分可明确判定需改进          |
| 最大自动修订轮次             | 2 轮                   | 与现有 `max_feedback_iterations` 对齐，控制成本和延迟 |
| 单调收敛检查                 | 本轮 ≤ 上轮分数 → 停止 | 避免 LLM 评分噪声导致的无限循环                       |
| 合同聚焦维度数               | 最多 2 个              | 减少修订面，降低引入新问题的风险                      |
| HITL 仍为最终兜底            | 是                     | 用户始终是最终决策者，自动修订只处理明显低质          |
| 自动修订复用 `_revise_draft` | 是                     | 最小代码变更，Writer 已有修订能力                     |

> **与纯 HITL 方案的对比**: 原方案中即使综述质量明显低于及格线，仍需要用户手动提供修订指令，用户体验差且依赖用户的学术判断力。迭代合同模式让系统自行处理"明显的低质问题"，用户只需审阅已达标的综述。

### 4.7 前端展示

在 `human_review_draft` 暂停界面展示评分结果：

```
┌────────────────────────────────────────────────┐
│ 📊 综述质量评分                                 │
├────────────────────────────────────────────────┤
│ 综合连贯性  ████████░░  8/10                    │
│ 分析深度    ██████░░░░  6/10  ⚠️ 建议改进       │
│ 学术严谨性  ████████░░  8/10                    │
│ 实用价值    ███████░░░  7/10                    │
│ ──────────────────────────                     │
│ 加权总分    7.1/10                              │
├────────────────────────────────────────────────┤
│ 📋 改进建议                                     │
│ • [分析深度] 第3节缺少跨论文方法对比分析        │
│ • [分析深度] 趋势讨论可加入时间维度数据支撑     │
└────────────────────────────────────────────────┘
```

---

## 五、实施计划

### 5.1 阶段划分

```
阶段 1: 创建共享 Rubric 模板            ── prompts/shared/review_rubric.md
                 │
                 ▼
阶段 2: 升级 Writer coherence_review     ── Prompt 改造 + 代码适配
                 │
                 ▼
阶段 3: 新增 Critic review_assessment    ── 新 Prompt + assess_review() 函数
                 │
                 ▼
阶段 4: 迭代合同 + 自动修订环路          ── 路由重构 + auto_revise 节点 + workflow.yaml
                 │
                 ▼
阶段 5: State 扩展 + 前端展示            ── ReviewState 新字段 + HITL UI
                 │
                 ▼
阶段 6: 测试                             ── 单元测试 + 集成验证
```

### 5.2 任务清单

| #   | 任务                                 | 输出文件                                        | 说明                                                    |
| --- | ------------------------------------ | ----------------------------------------------- | ------------------------------------------------------- |
| 1.1 | 创建共享 Rubric 模板                 | `prompts/shared/review_rubric.md`               | 4 维度定义 + 评分量表，含可变权重                       |
| 2.1 | 升级 coherence_review Prompt         | `prompts/writer/coherence_review.md`            | 引入 `{% include %}` Rubric，输出格式改为 4 维度        |
| 2.2 | 修改 section_writing Prompt          | `prompts/writer/section_writing.md`             | 末尾追加 Rubric 摘要提示，提醒 Writer 写作目标          |
| 2.3 | 适配 writer_agent.py                 | `app/agents/writer_agent.py`                    | `coherence_review()` 解析新格式，传入 output_type 权重  |
| 3.1 | 新增 review_assessment Prompt        | `prompts/critic/review_assessment.md`           | 包含 `{% include %}` Rubric + 审稿人视角指令            |
| 3.2 | 新增 assess_review() 函数            | `app/agents/critic_agent.py`                    | 综述级评估逻辑 + 权重计算                               |
| 3.3 | 修改 critique_node()                 | `app/agents/critic_agent.py`                    | 根据 full_draft 是否存在条件调用 assess_review()        |
| 3.4 | 新增 RUBRIC_WEIGHTS 常量             | `app/agents/critic_agent.py`                    | 5 种输出类型的权重映射                                  |
| 4.1 | 新增 `generate_revision_contract`    | `app/agents/critic_agent.py`                    | 从评分结果生成迭代合同                                  |
| 4.2 | 新增 `auto_revise_node`              | `app/agents/writer_agent.py`                    | 按迭代合同自动修订，复用 `_revise_draft`                |
| 4.3 | 新增 `route_after_review_assessment` | `app/agents/routing.py`                         | 评估后路由：达标→HITL / 不达标→auto_revise              |
| 4.4 | 修改 workflow.yaml                   | `config/workflow.yaml`                          | 新增 `review_assessment`、`auto_revise` 节点和条件路由  |
| 5.1 | ReviewState 新增字段                 | `app/agents/state.py`                           | `review_scores` + `review_feedback` + `revision_*` 字段 |
| 5.2 | 前端类型定义                         | `frontend/src/types/`                           | 新增 ReviewScores + RevisionContract 类型               |
| 5.3 | HitlCard 展示评分                    | `frontend/src/components/Workflow/HitlCard.tsx` | 在草稿审阅卡片中展示评分、迭代历史                      |
| 6.1 | Writer 测试                          | `tests/test_writer_agent.py`                    | coherence_review 新格式 + auto_revise 测试              |
| 6.2 | Critic 测试                          | `tests/test_critic_agent.py`                    | assess_review + generate_revision_contract 测试         |
| 6.3 | 路由测试                             | `tests/test_workflow.py`                        | route_after_review_assessment 各分支覆盖                |
| 6.4 | 集成测试                             | `tests/test_e2e_v03.py`                         | 端到端验证自动修订环路、收敛停止、HITL 兜底             |

### 5.3 文件变更汇总

```
新增: 3 个文件
  prompts/shared/review_rubric.md
  prompts/critic/review_assessment.md
  (前端类型文件可能新增)

修改: ~10 个文件
  prompts/writer/coherence_review.md
  prompts/writer/section_writing.md
  app/agents/writer_agent.py          # coherence_review 升级 + auto_revise_node
  app/agents/critic_agent.py          # assess_review + generate_revision_contract
  app/agents/routing.py               # 新增 route_after_review_assessment
  app/agents/state.py                 # 新增 revision_* 字段
  config/workflow.yaml                # 新增节点 + 条件路由
  frontend/src/components/Workflow/HitlCard.tsx
  tests/test_writer_agent.py
  tests/test_critic_agent.py
  tests/test_workflow.py              # 路由分支覆盖测试
```

### 5.4 验收标准

- [ ] `prompts/shared/review_rubric.md` 被 Writer 和 Critic 的 Prompt 通过 `{% include %}` 共享
- [ ] Writer `coherence_review` 输出 4 维度分数 + 逐维度问题列表
- [ ] Critic `assess_review` 独立评估综述并输出相同格式的分数
- [ ] `review_scores` 和 `review_feedback` 正确写入 ReviewState
- [ ] HITL `human_review_draft` 暂停界面展示评分、迭代历史和改进建议
- [ ] 不同 output_type 使用正确的权重配置
- [ ] weighted_score < 6.0 时自动触发修订，生成迭代合同并聚焦最低 1-2 维度
- [ ] 自动修订最多 2 轮，达到上限后强制进入 HITL
- [ ] 单调收敛检查：本轮分数未提升时停止自动修订
- [ ] `revision_score_history` 正确记录每轮评分快照
- [ ] 用户在 HITL 界面仍可提供 `revision_instructions` 触发额外修订
- [ ] 全部现有测试无回归

---

## 六、Token 消耗预估

| 步骤                                    | 输入 Token                       | 输出 Token | 预估成本      |
| --------------------------------------- | -------------------------------- | ---------- | ------------- |
| Writer coherence_review (含 Rubric)     | ~3000 (综述全文) + ~500 (Rubric) | ~500       | ~$0.02        |
| Critic review_assessment (含 Rubric)    | ~3000 (综述全文) + ~500 (Rubric) | ~500       | ~$0.02        |
| **基础增量（无自动修订）**              |                                  |            | **~$0.04/次** |
| 自动修订每轮 (revise + verify + assess) | ~3500 × 3 调用                   | ~1500      | ~$0.06/轮     |
| **最大增量（2 轮自动修订）**            |                                  |            | **~$0.16/次** |

- 无自动修订时（weighted ≥ 6.0）：增加 ~$0.04，相比基准 ~16-20%
- 1 轮自动修订：增加 ~$0.10，相比基准 ~40-50%
- 2 轮自动修订（最坏情况）：增加 ~$0.16，相比基准 ~64-80%

实际触发自动修订的比例预计较低（大多数综述初稿 weighted ≥ 6.0），平均增量估计 ~$0.06/次。

---

## 七、未来扩展

| 方向               | 版本  | 说明                                                             |
| ------------------ | ----- | ---------------------------------------------------------------- |
| 用户自定义 Rubric  | v0.8+ | 允许用户调整维度权重或新增自定义评估维度                         |
| 自适应阈值         | v0.8+ | 基于历史项目评分分布动态调整 `AUTO_REVISE_THRESHOLD`             |
| 评分趋势可视化     | v0.8+ | 前端展示 `revision_score_history` 的折线图，直观呈现迭代改进趋势 |
| 跨项目评分对比     | v1.0  | 比较不同项目综述的质量分布                                       |
| 用户可配置修订策略 | v1.0  | 允许用户选择自动修订/纯 HITL/混合模式                            |

> **已实现（本版本）**: 自动修订触发（迭代合同 + weighted < 6.0 阈值）、多轮评估收敛（单调检查 + 最多 2 轮）、评分历史追踪（`revision_score_history`）。
