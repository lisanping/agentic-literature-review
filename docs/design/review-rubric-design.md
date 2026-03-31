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
```

### 3.5 工作流集成点

在现有 DAG 中，综述级评估发生在 **`write_review` 之后、`human_review_draft` 之前**：

```
... → write_review → verify_citations → [review_assessment] → human_review_draft → ...
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

### 4.6 路由增强

**当前**: `route_after_draft_review` 仅依赖用户 `revision_instructions`。

**增强**: 结合 `review_scores` 辅助提示，但不强制覆盖用户决策。

```python
def route_after_draft_review(state: ReviewState) -> str:
    """Route after user reviews the draft.

    - If user provided revision instructions → revise_review
    - Otherwise → export

    Enhancement: review_scores 作为辅助信息展示给用户（HITL 暂停时），
    帮助用户判断是否需要修订。评分低于阈值时在前端显示"建议修订"提示，
    但最终决策权仍在用户。
    """
    if state.get("revision_instructions"):
        return "revise_review"
    return "export"
```

> **设计决策**: 不采用自动阻断模式（score < 6 自动触发修订）。原因：
> 1. LLM 自评分数可能不准确，自动阻断可能造成无限循环
> 2. 保持 HITL 原则——用户始终是最终决策者
> 3. 评分作为**辅助信息**呈现在 HITL 暂停界面，帮助用户做出更知情的决策

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
阶段 4: State 扩展 + 前端展示            ── ReviewState 新字段 + HITL UI
                 │
                 ▼
阶段 5: 测试                             ── 单元测试 + 集成验证
```

### 5.2 任务清单

| #   | 任务                          | 输出文件                                        | 说明                                                   |
| --- | ----------------------------- | ----------------------------------------------- | ------------------------------------------------------ |
| 1.1 | 创建共享 Rubric 模板          | `prompts/shared/review_rubric.md`               | 4 维度定义 + 评分量表，含可变权重                      |
| 2.1 | 升级 coherence_review Prompt  | `prompts/writer/coherence_review.md`            | 引入 `{% include %}` Rubric，输出格式改为 4 维度       |
| 2.2 | 修改 section_writing Prompt   | `prompts/writer/section_writing.md`             | 末尾追加 Rubric 摘要提示，提醒 Writer 写作目标         |
| 2.3 | 适配 writer_agent.py          | `app/agents/writer_agent.py`                    | `coherence_review()` 解析新格式，传入 output_type 权重 |
| 3.1 | 新增 review_assessment Prompt | `prompts/critic/review_assessment.md`           | 包含 `{% include %}` Rubric + 审稿人视角指令           |
| 3.2 | 新增 assess_review() 函数     | `app/agents/critic_agent.py`                    | 综述级评估逻辑 + 权重计算                              |
| 3.3 | 修改 critique_node()          | `app/agents/critic_agent.py`                    | 根据 full_draft 是否存在条件调用 assess_review()       |
| 3.4 | 新增 RUBRIC_WEIGHTS 常量      | `app/agents/critic_agent.py`                    | 5 种输出类型的权重映射                                 |
| 4.1 | ReviewState 新增字段          | `app/agents/state.py`                           | `review_scores` + `review_feedback`                    |
| 4.2 | 前端类型定义                  | `frontend/src/types/`                           | 新增 ReviewScores 类型                                 |
| 4.3 | HitlCard 展示评分             | `frontend/src/components/Workflow/HitlCard.tsx` | 在草稿审阅卡片中展示评分                               |
| 5.1 | Writer 测试                   | `tests/test_writer_agent.py`                    | coherence_review 新格式解析测试                        |
| 5.2 | Critic 测试                   | `tests/test_critic_agent.py`                    | assess_review + 权重计算测试                           |
| 5.3 | 集成测试                      | `tests/test_e2e_v03.py`                         | 端到端验证 review_scores 传递                          |

### 5.3 文件变更汇总

```
新增: 3 个文件
  prompts/shared/review_rubric.md
  prompts/critic/review_assessment.md
  (前端类型文件可能新增)

修改: ~8 个文件
  prompts/writer/coherence_review.md
  prompts/writer/section_writing.md
  app/agents/writer_agent.py
  app/agents/critic_agent.py
  app/agents/state.py
  frontend/src/components/Workflow/HitlCard.tsx
  tests/test_writer_agent.py
  tests/test_critic_agent.py
```

### 5.4 验收标准

- [ ] `prompts/shared/review_rubric.md` 被 Writer 和 Critic 的 Prompt 通过 `{% include %}` 共享
- [ ] Writer `coherence_review` 输出 4 维度分数 + 逐维度问题列表
- [ ] Critic `assess_review` 独立评估综述并输出相同格式的分数
- [ ] `review_scores` 和 `review_feedback` 正确写入 ReviewState
- [ ] HITL `human_review_draft` 暂停界面展示评分和改进建议
- [ ] 不同 output_type 使用正确的权重配置
- [ ] 全部现有测试无回归

---

## 六、Token 消耗预估

| 步骤                                 | 输入 Token                       | 输出 Token | 预估成本      |
| ------------------------------------ | -------------------------------- | ---------- | ------------- |
| Writer coherence_review (含 Rubric)  | ~3000 (综述全文) + ~500 (Rubric) | ~500       | ~$0.02        |
| Critic review_assessment (含 Rubric) | ~3000 (综述全文) + ~500 (Rubric) | ~500       | ~$0.02        |
| **总增量**                           |                                  |            | **~$0.04/次** |

相比现有工作流总成本 (~$0.20-0.25/次)，增加约 16-20%，属于可接受范围。

---

## 七、未来扩展

| 方向              | 版本  | 说明                                                           |
| ----------------- | ----- | -------------------------------------------------------------- |
| 自动修订触发      | v0.7+ | 当 weighted_score < 阈值时自动触发 revise_review，无需用户干预 |
| 多轮评估收敛      | v0.7+ | 修订后重新评分，直到分数达标或达到最大修订次数                 |
| 用户自定义 Rubric | v0.8+ | 允许用户调整维度权重或新增自定义评估维度                       |
| 评分历史追踪      | v0.8+ | 记录每轮修订的评分变化，可视化改进趋势                         |
| 跨项目评分对比    | v1.0  | 比较不同项目综述的质量分布                                     |
