# 多智能体文献综述应用 — 系统架构详细设计

> **文档版本**: v1.3
> **创建日期**: 2026-03-28
> **最后更新**: 2026-03-30
> **文档状态**: 迭代修订
> **前置文档**: [需求与功能设计](requirements-and-functional-design.md) · [产品交付形态与用户体验](product-delivery-and-ux.md)
> **文档说明**: 本文档在需求设计基础上，定义系统的分层架构、Agent 通信协议、状态管理、数据流、错误恢复机制及关键技术决策，为编码实现提供直接指导。

---

## 目录

- [一、架构总览](#一架构总览)
- [二、系统分层架构](#二系统分层架构)
- [三、智能体框架选型与设计](#三智能体框架选型与设计)
- [四、Orchestrator 编排引擎设计](#四orchestrator-编排引擎设计)
- [五、各 Agent 详细设计](#五各-agent-详细设计)
- [六、Agent 间通信协议](#六agent-间通信协议)
- [七、状态管理与持久化](#七状态管理与持久化)
- [八、数据流架构](#八数据流架构)
  - [8.3 接口层 REST API 设计](#83-接口层-rest-api-设计)
- [九、外部数据源接入层](#九外部数据源接入层)
- [十、异步任务与队列设计](#十异步任务与队列设计)
- [十一、错误恢复与容错机制](#十一错误恢复与容错机制)
- [十二、安全设计](#十二安全设计)
- [十三、可观测性与监控](#十三可观测性与监控)
- [十四、部署架构](#十四部署架构)
- [十五、MVP 架构范围](#十五mvp-架构范围)

---

## 一、架构总览

### 1.1 系统上下文

```
                    ┌─────────────┐
                    │   用户       │
                    │ (浏览器/CLI) │
                    └──────┬──────┘
                           │ HTTPS / SSE
                           ▼
              ┌────────────────────────┐
              │     API Gateway        │
              │     (Nginx / Traefik)  │
              └────────┬───────────────┘
                       │
          ┌────────────┴────────────┐
          ▼                         ▼
┌──────────────────┐    ┌──────────────────┐
│   Web Frontend   │    │   Backend API    │
│   (React SPA)    │    │   (FastAPI)      │
│   :3000          │    │   :8000          │
└──────────────────┘    └────────┬─────────┘
                                 │
            ┌────────────────────┼────────────────────┐
            ▼                    ▼                    ▼
   ┌────────────────┐  ┌────────────────┐  ┌────────────────┐
   │  Agent Engine  │  │  Task Queue    │  │  Data Layer    │
   │  (LangGraph)   │  │  (Celery+Redis)│  │  (存储集群)     │
   └────────────────┘  └────────────────┘  └────────────────┘
            │                                        │
            ▼                                        ▼
   ┌────────────────┐                    ┌───────────────────┐
   │  LLM Provider  │                    │  External APIs    │
   │  (OpenAI/本地)  │                    │  (S2/arXiv/...)   │
   └────────────────┘                    └───────────────────┘
```

### 1.2 核心设计原则

| 原则           | 说明                                                                                      |
| -------------- | ----------------------------------------------------------------------------------------- |
| **松耦合**     | Agent 之间通过标准消息协议通信，可独立开发、测试、替换                                    |
| **可恢复**     | 每个工作流步骤结束后持久化状态，系统重启后可从断点继续                                    |
| **可观测**     | 全链路 tracing，Agent 每一步推理均可审计                                                  |
| **渐进式扩展** | MVP 最小集合可运行，后续 Agent/数据源可热插拔                                             |
| **LLM 无关**   | 通过抽象层对接不同 LLM Provider，按 Agent/任务类型路由最优模型（见 10.5），避免供应商锁定 |

---

## 二、系统分层架构

```
┌─────────────────────────────────────────────────────────────┐
│                    表现层 (Presentation)                     │
│    React SPA · SSE 实时推送 · CLI Client                  │
├─────────────────────────────────────────────────────────────┤
│                    接口层 (API Layer)                        │
│    FastAPI · REST + SSE · 认证鉴权 · 请求校验              │
├─────────────────────────────────────────────────────────────┤
│                    编排层 (Orchestration)                    │
│    LangGraph StateMachine · Workflow DAG · Human-in-loop    │
├─────────────────────────────────────────────────────────────┤
│                    智能体层 (Agent Layer)                    │
│    Search · Reader · Analyst · Critic · Writer · Update     │
├─────────────────────────────────────────────────────────────┤
│                    能力层 (Capability Layer)                 │
│    LLM 路由 · Prompt 管理 · 文献检索 · PDF 解析 · 向量检索  │
├─────────────────────────────────────────────────────────────┤
│                    数据层 (Data Layer)                       │
│    SQLite/PG · Chroma · Redis · 文件系统                    │
├─────────────────────────────────────────────────────────────┤
│                    基础设施层 (Infrastructure)               │
│    Docker Compose · 日志收集 · 健康检查 · 配置管理          │
└─────────────────────────────────────────────────────────────┘
```

各层职责：

| 层次       | 职责                                        | MVP 技术选型            |
| ---------- | ------------------------------------------- | ----------------------- |
| 表现层     | 用户交互、实时状态展示                      | React + Ant Design      |
| 接口层     | 请求路由、认证、参数校验、SSE 实时推送      | FastAPI                 |
| 编排层     | 工作流定义、Agent 调度、断点恢复、HITL 控制 | LangGraph               |
| 智能体层   | 各专业 Agent 的业务逻辑                     | LangGraph Nodes         |
| 能力层     | 底层工具函数，供 Agent 调用                 | Python 模块             |
| 数据层     | 数据持久化、缓存                            | SQLite + Chroma + Redis |
| 基础设施层 | 容器编排、配置、监控                        | Docker Compose          |

---

## 三、智能体框架选型与设计

### 3.1 框架选型：LangGraph

| 评估维度          | LangGraph                   | CrewAI         | AutoGen              |
| ----------------- | --------------------------- | -------------- | -------------------- |
| **状态管理**      | ✅ 原生 StateGraph，可持久化 | ⚠️ 有限         | ⚠️ 会话级别           |
| **工作流控制**    | ✅ 显式 DAG + 条件分支       | ⚠️ 隐式链式调用 | ⚠️ 对话驱动，控制力弱 |
| **Human-in-loop** | ✅ 原生 interrupt 支持       | ⚠️ 需手动实现   | ✅ 支持               |
| **断点恢复**      | ✅ Checkpointer 机制         | ❌              | ❌                    |
| **可观测性**      | ✅ LangSmith 集成            | ⚠️ 基础日志     | ⚠️ 基础日志           |
| **灵活性**        | ✅ 完全可控的执行流          | ⚠️ 框架约束较多 | ⚠️ 多轮对话模式限制   |
| **生态成熟度**    | ✅ LangChain 生态            | ✅ 社区活跃     | ✅ 微软支持           |

**选型结论**: 采用 **LangGraph** 作为智能体编排框架。其显式状态图模型最适合文献综述这种多阶段、需要人工干预、且要求断点恢复的长流程任务。

### 3.2 LangGraph 核心概念映射

| LangGraph 概念       | 在本系统中的映射                           |
| -------------------- | ------------------------------------------ |
| **StateGraph**       | 整个文献综述工作流                         |
| **State**            | `ReviewState` — 贯穿全流程的共享状态对象   |
| **Node**             | 各 Agent（Search / Reader / Writer 等）    |
| **Edge**             | Agent 间的数据流转与条件判断               |
| **Conditional Edge** | 基于检索结果数量/质量决定是否进入下一阶段  |
| **Interrupt**        | Human-in-loop 暂停点（检索确认、大纲审阅） |
| **Checkpointer**     | 每个 Node 执行后自动持久化状态到 SQLite    |

---

## 四、Orchestrator 编排引擎设计

### 4.1 工作流状态图（StateGraph）

工作流并非严格线性流水线，而是支持**条件反馈边**。当下游 Agent 发现信息不足时，可触发上游 Agent 定向补充，形成闭环迭代。每次反馈触发设有最大迭代次数限制（默认 2 次），防止无限循环。

```
                    ┌─────────┐
                    │  START  │
                    └────┬────┘
                         │
                         ▼
                ┌────────────────┐
                │  parse_intent  │  ← 解析用户意图，制定策略
                └────────┬───────┘
                         │
                         ▼
           ┌───────────────────────────┐
           │         search            │  ← Search Agent 多库检索
           └────────────┬──────────────┘
                        │
                        ▼
              ┌──────────────────────┐
              │  human_review_search │  ← HITL: 用户确认论文列表
              │  (interrupt)         │
              └──────────┬───────────┘
                         │
                    ┌────┴────┐
                    │ 需补充?  │
                    └────┬────┘
                   yes ┌─┘└─┐ no
                       │    │
                ┌──────┘    └──────┐
                ▼                  ▼
        ┌──────────────┐  ┌──────────────┐
        │ search (补充) │  │    read      │  ← Reader Agent 精读
        └──────┬───────┘  └──────┬───────┘
               │                 │
               └────────┐       │
                        ▼       ▼
              ┌─────────────────────┐
              │  check_read_feedback │  ← 检查 Reader 是否发现需补充检索的引用
              └─────────┬───────────┘
                        │
                   ┌────┴────┐
                   │需补充检索?│  ← feedback_iteration_count < max(2)
                   └────┬────┘
                  yes ┌─┘└─┐ no
                      │    │
               ┌──────┘    └──────┐
               ▼                  ▼
        ┌──────────────┐  ┌──────────────┐
        │search (反馈)  │  │   analyze    │  ← Analyst Agent 分析
        └──────┬───────┘  └──────┬───────┘
               │                 │
               └──▶ read ──▶     │
                                 ▼
                   ┌──────────────┐
                   │   critique   │  ← Critic Agent 评审
                   └──────┬───────┘
                          │
                          ▼
              ┌───────────────────────┐
              │ check_critic_feedback │  ← 检查 Critic 是否发现文献覆盖不足
              └───────────┬───────────┘
                          │
                     ┌────┴────┐
                     │覆盖不足? │  ← feedback_iteration_count < max(2)
                     └────┬────┘
                    yes ┌─┘└─┐ no
                        │    │
                 ┌──────┘    └──────┐
                 ▼                  ▼
        ┌───────────────┐  ┌──────────────────┐
        │search (Gap补充)│  │  generate_outline│  ← Writer Agent 生成大纲
        └───────┬───────┘  └────────┬─────────┘
                │                    │
                └──▶ read ──▶        │
                 analyze ──▶         │
                 critique ──▶        │
                                     ▼
              ┌──────────────────────┐
              │ human_review_outline │  ← HITL: 用户确认大纲
              │ (interrupt)          │
              └──────────┬───────────┘
                         │
                         ▼
                ┌────────────────┐
                │  write_review  │  ← Writer Agent 生成全文
                └────────┬───────┘
                         │
                         ▼
              ┌────────────────────┐
              │  verify_citations  │  ← 引用验证：回溯数据源确认每条引用存在性
              └────────┬───────────┘
                       │
                       ▼
              ┌──────────────────────┐
              │ human_review_draft   │  ← HITL: 用户审阅初稿
              │ (interrupt)          │
              └──────────┬───────────┘
                         │
                    ┌────┴────┐
                    │ 需修改?  │
                    └────┬────┘
                   yes ┌─┘└─┐ no
                       │    │
                ┌──────┘    └──────┐
                ▼                  ▼
        ┌──────────────┐    ┌──────────┐
        │ revise_review │    │  export  │  ← 格式化导出
        └──────┬───────┘    └──────┬───┘
               │                   │
               └───────────┐      │
                           ▼      ▼
                        ┌─────┐
                        │ END │
                        └─────┘
```

**反馈环路节点说明**:

| 节点                    | 触发条件                                        | 行为                                                                       |
| ----------------------- | ----------------------------------------------- | -------------------------------------------------------------------------- |
| `check_read_feedback`   | Reader 发现种子论文引用中有高相关但未收录的论文 | 将待补充论文 ID 写入 `feedback_search_queries`，触发 Search Agent 定向检索 |
| `check_critic_feedback` | Critic 发现某主题方向论文覆盖不足（<3 篇）      | 将不足方向写入 `feedback_search_queries`，触发 Search Agent 补充检索       |
| `verify_citations`      | Writer 生成全文后自动执行                       | 每条引用回溯 Semantic Scholar / CrossRef 确认存在性，标记验证结果          |

### 4.2 核心状态定义（ReviewState）

> **注意**: `PaperMetadata` 的权威字段定义见[数据模型文档 §4.3](data-model.md#四论文实体-paper)（Pydantic Model）。此处 TypedDict 为 LangGraph State 内部传递的简化视图，仅保留工作流运行时必需的字段；完整元数据在写入数据库时使用 Pydantic 版本。

```python
from typing import TypedDict, Literal, Annotated
from langgraph.graph.message import add_messages

class PaperMetadata(TypedDict):
    """LangGraph State 内部使用的论文元数据简化视图。
    完整字段定义见 data-model.md §4.3 PaperMetadata (Pydantic)。"""
    paper_id: str           # 统一 ID (DOI / S2 ID / arXiv ID)
    title: str
    authors: list[str]
    year: int | None
    abstract: str | None
    source: str             # "semantic_scholar" | "arxiv" | ...
    citation_count: int
    url: str | None
    pdf_url: str | None
    doi: str | None
    s2_id: str | None
    arxiv_id: str | None
    open_access: bool

class PaperAnalysis(TypedDict):
    paper_id: str
    structured_summary: dict    # {objective, method, dataset, findings, limitations}
    key_concepts: list[str]
    methodology_details: dict
    relations: list[dict]       # [{target_paper_id, relation_type}]

class ReviewState(TypedDict):
    # ── 用户输入 ──
    user_query: str                         # 原始研究问题
    uploaded_papers: list[str]              # 用户上传的论文文件路径
    output_types: list[str]                 # 期望输出类型列表 (见 OutputType 枚举)
    output_language: str                    # "zh" | "en" | "bilingual"
    citation_style: str                     # "apa" | "ieee" | "gbt7714"

    # ── 检索阶段 ──
    search_strategy: dict                   # 检索策略 (查询词、数据源、过滤条件)
    candidate_papers: list[PaperMetadata]   # 候选论文列表
    selected_papers: list[PaperMetadata]    # 用户确认后的论文列表

    # ── 阅读阶段 ──
    paper_analyses: list[PaperAnalysis]     # 各论文的结构化分析结果
    reading_progress: dict                  # {total, completed, current}

    # ── 分析阶段 ──
    topic_clusters: list[dict]              # 主题聚类结果
    comparison_matrix: dict                 # 方法对比矩阵
    timeline: list[dict]                    # 时间线数据
    citation_network: dict                  # 引文网络
    research_trends: dict                   # 研究趋势

    # ── 评审阶段 ──
    quality_assessments: list[dict]         # 论文质量评估
    contradictions: list[dict]              # 矛盾发现
    research_gaps: list[dict]               # 研究空白
    limitation_summary: str                 # 共性局限归纳

    # ── 写作阶段 ──
    outline: dict                           # 综述大纲
    draft_sections: list[dict]              # 各章节草稿
    full_draft: str                         # 完整初稿
    references: list[dict]                  # 参考文献列表
    final_output: str                       # 最终交付文本

    # ── 引用验证 ──
    citation_verification: list[dict]       # [{paper_id, status: "verified"|"unverified"|"pending", source}]

    # ── 成本追踪 ──
    token_usage: dict                       # {total_input, total_output, by_agent: {search: {input, output}, ...}}
    token_budget: int | None                # 用户设置的 Token 预算上限 (None 表示不限制)

    # ── 全文覆盖 ──
    fulltext_coverage: dict                 # {total, fulltext_count, abstract_only_count}

    # ── 反馈环路控制 ──
    feedback_search_queries: list[str]      # 下游 Agent 发现需要补充检索的查询词
    feedback_iteration_count: int           # 当前反馈迭代次数 (上限默认 2)

    # ── 流程控制 ──
    current_phase: str                      # 当前阶段
    messages: Annotated[list, add_messages] # 对话历史
    error_log: list[dict]                   # 错误记录
```

> **State 体积管理约束**: `ReviewState` 经 LangGraph Checkpointer 在每个 Node 执行后序列化到 SQLite/PostgreSQL。当论文数量较多时（100+），`candidate_papers`、`paper_analyses`、`full_draft` 等字段可能导致 State 达数 MB 级别，影响 checkpoint 写入性能。实现时应采用以下策略控制体积：
>
> | 字段 | 策略 | 说明 |
> |--------|--------|------|
> | `candidate_papers` / `selected_papers` | State 内仅存储 `paper_id` 列表 | 完整 `PaperMetadata` 已写入业务数据库 `papers` 表，Agent 按需查询 |
> | `paper_analyses` | State 内仅存储 `paper_id` 列表 | 完整分析结果已写入 `paper_analyses` 表，Writer Agent 按需加载 |
> | `full_draft` | State 内存储草稿摘要或引用 ID | 完整文本写入 `review_outputs` 表，避免长文本反复序列化 |
> | `messages` | 控制最大历史长度 | 仅保留最近 N 条消息，避免无限增长 |
>
> 具体实现时，上述“简化视图”字段（如 `candidate_papers: list[str]`）可替代当前的完整对象列表，但需确保 Agent 内部有便捷的数据库查询接口。本 TypedDict 保留完整对象以展示数据合约，实际编码时可按上表策略优化。

### 4.3 条件路由逻辑

```python
MAX_FEEDBACK_ITERATIONS = 2  # 反馈环路最大迭代次数

def route_after_search_review(state: ReviewState) -> str:
    """检索确认后的路由：若用户要求补充检索则回到 search，否则进入 read"""
    if state.get("needs_more_search"):
        return "search"
    if len(state["selected_papers"]) == 0:
        return "search"  # 无选中论文，重新检索
    return "read"

def route_after_read(state: ReviewState) -> str:
    """精读完成后的路由：检查是否有反馈触发的补充检索需求"""
    feedback_queries = state.get("feedback_search_queries", [])
    iteration_count = state.get("feedback_iteration_count", 0)
    if feedback_queries and iteration_count < MAX_FEEDBACK_ITERATIONS:
        return "search"  # 反馈环路：回到检索
    return "analyze"

def route_after_critique(state: ReviewState) -> str:
    """评审完成后的路由：Critic 发现覆盖不足则触发补充检索"""
    feedback_queries = state.get("feedback_search_queries", [])
    iteration_count = state.get("feedback_iteration_count", 0)
    if feedback_queries and iteration_count < MAX_FEEDBACK_ITERATIONS:
        return "search"  # 反馈环路：回到检索
    return "generate_outline"

def route_after_draft_review(state: ReviewState) -> str:
    """初稿审阅后的路由：需修改则回到 revise，否则导出"""
    if state.get("revision_instructions"):
        return "revise_review"
    return "export"

def should_run_analyst(state: ReviewState) -> bool:
    """仅当论文数量 >= 5 时才运行 Analyst Agent"""
    return len(state.get("paper_analyses", [])) >= 5

def check_token_budget(state: ReviewState) -> str:
    """检查 Token 预算：超限时暂停工作流等待用户确认"""
    budget = state.get("token_budget")
    usage = state.get("token_usage", {})
    if budget and usage.get("total_input", 0) + usage.get("total_output", 0) >= budget:
        return "budget_exceeded"  # 触发 interrupt 暂停
    return "continue"
```

### 4.4 Agent 注册与工作流配置驱动

设计原则要求"Agent 可热插拔"，但如果每次新增 Agent 都需要手动修改 `orchestrator.py` 中的 DAG 定义，可维护性差。通过 **AgentRegistry** + **配置文件驱动** 的方式，使工作流 DAG 可由声明式配置组装。

**AgentRegistry 实现**:

```python
from typing import Callable

# Agent Node 函数类型
AgentNodeFn = Callable[[ReviewState], dict]

class AgentRegistry:
    """Agent 注册中心，管理所有可用的 Agent Node 函数"""

    def __init__(self):
        self._agents: dict[str, AgentNodeFn] = {}

    def register(self, name: str, node_fn: AgentNodeFn):
        """注册一个 Agent Node 函数"""
        self._agents[name] = node_fn

    def get(self, name: str) -> AgentNodeFn:
        """获取已注册的 Agent Node 函数"""
        if name not in self._agents:
            raise ValueError(f"Agent '{name}' not registered")
        return self._agents[name]

    def list_agents(self) -> list[str]:
        """列出所有已注册的 Agent 名称"""
        return list(self._agents.keys())
```

**Agent 自注册**: 每个 Agent 模块在导入时自动注册到全局 Registry：

```python
# agents/search_agent.py
from app.agents.registry import agent_registry

def search_node(state: ReviewState) -> dict:
    """Search Agent 节点函数"""
    ...

agent_registry.register("search", search_node)
```

**工作流配置文件**: 工作流 DAG 的节点序列、边、条件路由通过 YAML 配置声明，`orchestrator.py` 读取配置动态组装 StateGraph：

```yaml
# config/workflow.yaml
workflow:
  name: "literature_review"

  # 启用的 Agent 节点（按执行顺序）
  nodes:
    - name: parse_intent
    - name: search
    - name: human_review_search
      interrupt: true           # HITL 中断点
    - name: read
    - name: check_read_feedback
    - name: analyze
      enabled: false            # MVP 阶段禁用（设为 true 即启用）
    - name: critique
      enabled: false            # MVP 阶段禁用
    - name: generate_outline
    - name: human_review_outline
      interrupt: true
    - name: write_review
    - name: verify_citations
    - name: human_review_draft
      interrupt: true
    - name: export

  # 边定义（条件路由）
  edges:
    - from: human_review_search
      router: route_after_search_review
      targets: [search, read]
    - from: check_read_feedback
      router: route_after_read
      targets: [search, analyze, generate_outline]  # analyze 禁用时自动跳过
    - from: check_critic_feedback
      router: route_after_critique
      targets: [search, generate_outline]            # Critic 发现覆盖不足时回到检索
      enabled: false                                 # 随 critique 节点同步启用
    - from: human_review_draft
      router: route_after_draft_review
      targets: [revise_review, export]

  # 全局配置
  max_feedback_iterations: 2
```

**配置驱动的 Orchestrator**: `orchestrator.py` 不再硬编码 DAG，而是读取配置动态构建：

```python
# agents/orchestrator.py
import yaml
from langgraph.graph import StateGraph

def build_review_graph(
    agent_registry: AgentRegistry,
    config_path: str = "config/workflow.yaml",
) -> StateGraph:
    """根据配置文件动态构建工作流 DAG"""
    with open(config_path) as f:
        config = yaml.safe_load(f)

    graph = StateGraph(ReviewState)

    # 动态添加启用的节点
    for node_cfg in config["workflow"]["nodes"]:
        if not node_cfg.get("enabled", True):
            continue
        name = node_cfg["name"]
        node_fn = agent_registry.get(name)
        graph.add_node(name, node_fn)

    # 动态添加边（含条件路由）
    for edge_cfg in config["workflow"]["edges"]:
        router_fn = ROUTER_REGISTRY[edge_cfg["router"]]
        graph.add_conditional_edges(
            edge_cfg["from"],
            router_fn,
            {t: t for t in edge_cfg["targets"]},
        )

    # 添加顺序边（相邻启用节点之间）
    enabled_nodes = [n["name"] for n in config["workflow"]["nodes"] if n.get("enabled", True)]
    for i in range(len(enabled_nodes) - 1):
        if not _has_conditional_edge(config, enabled_nodes[i]):
            graph.add_edge(enabled_nodes[i], enabled_nodes[i + 1])

    return graph
```

**扩展新 Agent 的步骤**:

1. 实现 Agent Node 函数（如 `agents/analyst_agent.py`），模块内调用 `agent_registry.register()`
2. 在 `config/workflow.yaml` 中将对应节点 `enabled` 设为 `true`
3. 无需修改 `orchestrator.py` 代码

**MVP 阶段**: 配置文件中 `analyze` 和 `critique` 节点 `enabled: false`，仅 Search + Reader + Writer 参与工作流。v0.3 启用 Analyst + Critic 只需修改配置。

---

## 五、各 Agent 详细设计

### 5.1 Search Agent

```
输入: user_query, search_strategy, uploaded_papers
输出: candidate_papers
```

| 组件                     | 说明                                                        |
| ------------------------ | ----------------------------------------------------------- |
| **Query Planner**        | 将自然语言转为结构化查询：提取关键词、同义词扩展、布尔组合  |
| **Multi-Source Fetcher** | 通过 `SourceRegistry` 获取已启用数据源，并行调用（见 9.2）  |
| **Deduplicator**         | 基于 DOI / 标题相似度去重                                   |
| **Snowball Crawler**     | 从种子论文的引用/被引列表获取相关论文（终止条件见下方约束） |
| **Ranker**               | 按相关性 + 引用数 + 年份综合排序                            |

**内部流程**:
```
user_query
    │
    ▼
[Query Planner] → 生成多组查询词
    │
    ▼
[SourceRegistry.get_enabled_sources()]
    │
    ├──▶ Source A (e.g. Semantic Scholar) ──┐
    ├──▶ Source B (e.g. arXiv) ─────────────┤
    ├──▶ Source N (动态注册) ───────────────┤
    │                                       ▼
    │                                [Deduplicator]
    │                           │
    │                           ▼
    │                    [Ranker] → 排序后的候选列表
    │
    └──▶ (如有种子论文) [Snowball Crawler]
              │
              └──▶ 追加到候选列表
```

**滚雪球检索终止条件**:

| 约束项           | 限制值 | 说明                                                   |
| ---------------- | ------ | ------------------------------------------------------ |
| **递归深度**     | 2 层   | 从种子论文出发，最多追溯 2 层引用/被引                 |
| **单次扩展上限** | 50 篇  | 每轮 Snowball Crawler 最多追加 50 篇候选论文           |
| **候选总量上限** | 200 篇 | 所有数据源 + 滚雪球结果合计不超过 200 篇（去重后）     |
| **相关性阈值**   | 可配置 | 仅纳入与研究问题相关性评分高于阈值的论文，防止主题漂移 |

**LLM 使用点**:
- Query Planner: 将自然语言转结构化查询（1 次 LLM 调用）
- Ranker: 评估论文与研究问题的相关性（可选，批量调用）

### 5.2 Reader Agent

```
输入: selected_papers
输出: paper_analyses
```

| 组件                  | 说明                                           |
| --------------------- | ---------------------------------------------- |
| **PDF Processor**     | 下载 PDF，解析为结构化文本（标题、章节、图表） |
| **Abstract Analyzer** | 无全文时基于摘要分析                           |
| **Info Extractor**    | LLM 提取：目的、方法、数据集、发现、局限性     |
| **Relation Detector** | 识别论文间的引用关系和学术关系类型             |

**并行策略**:

| 设计维度           | 策略                                                                   |
| ------------------ | ---------------------------------------------------------------------- |
| **并发度上限**     | 默认 5 篇并行，可配置。受 LLM API 速率限制约束（GPT-4o: ~500 RPM）     |
| **实现方式**       | `asyncio.Semaphore(max_concurrent)` 控制并发，每篇论文为独立 coroutine |
| **渐进式推送**     | 每完成 1 篇即通过 SSE 推送结果，前端实时展示已完成论文的分析卡片       |
| **部分失败处理**   | 单篇 PDF 下载/解析失败不阻塞整体流程，降级为仅摘要分析并标记 `partial` |
| **全文覆盖率追踪** | 每篇论文完成后更新 `fulltext_coverage`，区分全文精读 vs 仅摘要分析     |

```python
async def read_papers_parallel(papers: list[PaperMetadata], max_concurrent: int = 5):
    semaphore = asyncio.Semaphore(max_concurrent)
    results = []

    async def process_one(paper):
        async with semaphore:
            try:
                analysis = await extract_paper_info(paper)
                publish_event("progress", {"completed": len(results) + 1})
                return analysis
            except PDFParseError:
                return await fallback_abstract_analysis(paper)  # 降级

    results = await asyncio.gather(
        *[process_one(p) for p in papers],
        return_exceptions=False
    )
    return results
```

**LLM 使用点**:
- Info Extractor: 每篇论文 1 次 LLM 调用（主要消耗点）
- Relation Detector: 论文对之间关系判断（批量调用）

### 5.3 Analyst Agent

```
输入: paper_analyses
输出: topic_clusters, comparison_matrix, timeline, citation_network, research_trends
```

| 组件                   | 说明                                         |
| ---------------------- | -------------------------------------------- |
| **Topic Clusterer**    | 基于论文 embedding 聚类，LLM 命名各聚类主题  |
| **Comparison Builder** | 提取各论文的方法/指标，构建对比矩阵          |
| **Timeline Generator** | 按时间排列关键里程碑论文                     |
| **Network Analyzer**   | 基于引用关系构建图，计算 PageRank/中介中心性 |
| **Trend Analyzer**     | 统计发文量/关键词频率随时间的变化            |

**LLM 使用点**:
- Topic Clusterer: 聚类命名和描述（1 次调用）
- Comparison Builder: 统一对比维度提取（1 次调用）

### 5.4 Critic Agent

```
输入: paper_analyses, topic_clusters, comparison_matrix
输出: quality_assessments, contradictions, research_gaps, limitation_summary
```

| 组件                      | 说明                                         |
| ------------------------- | -------------------------------------------- |
| **Quality Assessor**      | 评估每篇论文的证据强度（样本量、方法严谨性） |
| **Contradiction Finder**  | 比对不同论文的结论，发现矛盾                 |
| **Gap Identifier**        | 根据现有研究版图推断未覆盖区域               |
| **Limitation Aggregator** | 归纳跨论文的共性局限                         |

**LLM 使用点**: 每个组件 1 次 LLM 调用，需要整合多篇论文的分析结果进行推理。

### 5.5 Writer Agent

```
输入: 全部分析结果 + outline (确认后)
输出: full_draft, references
```

| 组件                   | 说明                                         |
| ---------------------- | -------------------------------------------- |
| **Outline Generator**  | 基于分析结果生成综述大纲                     |
| **Section Writer**     | 按大纲逐章节生成文本                         |
| **Citation Formatter** | 自动插入引用标记，按指定格式生成参考文献列表 |
| **Style Adapter**      | 根据用户选择调整写作风格（叙述/系统/批判）   |
| **Exporter**           | 输出为 Markdown / Word / LaTeX / PDF         |

**写作策略**: 分章节生成，每章节独立 LLM 调用，最后由 LLM 做一次全文连贯性审查。

### 5.6 Update Agent（非 MVP）

```
输入: 已完成的综述项目配置
输出: 新发现论文列表 + 差异报告
```

以定时任务运行，复用 Search Agent 检索能力，对比已有论文集识别新增文献。

---

## 六、Agent 间通信协议

### 6.1 通信模型

采用 **共享状态 (Shared State)** 模型，所有 Agent 通过读写 `ReviewState` 进行通信：

```
┌──────────────────────────────────────────────────┐
│                 ReviewState                       │
│                 (共享状态对象)                     │
│                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │candidate │  │paper_    │  │topic_    │  ...   │
│  │_papers   │  │analyses  │  │clusters  │       │
│  └────▲─────┘  └────▲─────┘  └────▲─────┘       │
│       │             │             │              │
└───────┼─────────────┼─────────────┼──────────────┘
        │             │             │
   ┌────┴───┐   ┌────┴───┐   ┌────┴────┐
   │ Search │   │ Reader │   │ Analyst │
   │ Agent  │   │ Agent  │   │ Agent   │
   └────────┘   └────────┘   └─────────┘

   每个 Agent 读取上游输出 → 执行任务 → 写回结果到 State
```

### 6.2 Agent 输入输出契约

每个 Agent 实现统一的 Node 接口：

```python
def agent_node(state: ReviewState) -> dict:
    """
    Agent 节点函数签名。

    Args:
        state: 当前完整的工作流状态（只读取需要的字段）

    Returns:
        dict: 需要更新的状态字段（LangGraph 自动 merge 到 State）
    """
    # 读取输入
    papers = state["selected_papers"]

    # 执行业务逻辑
    analyses = do_analysis(papers)

    # 返回更新
    return {
        "paper_analyses": analyses,
        "current_phase": "read_complete",
    }
```

### 6.3 消息与事件

除了状态共享，系统还通过 **事件流** 向前端推送实时进度：

```python
class AgentEvent(TypedDict):
    event_type: str     # "progress" | "error" | "hitl_request" | "complete"
    agent_name: str     # "search" | "reader" | ...
    timestamp: str      # ISO 8601
    data: dict          # 事件特定数据

# 示例事件
{"event_type": "progress",     "agent_name": "reader", "data": {"completed": 12, "total": 30}}
{"event_type": "hitl_request", "agent_name": "search", "data": {"candidate_count": 47}}
{"event_type": "error",        "agent_name": "search", "data": {"source": "arxiv", "message": "Rate limited"}}
```

通过 **Server-Sent Events (SSE)** 从后端推送到前端，保持低延迟的实时反馈。

### 6.4 SSE 背压与消息缓冲

当 Reader Agent 并行精读多篇论文时，事件产出速率可能超过前端消费速率，导致 SSE 连接缓冲溢出或内存膨胀。系统通过 **跨进程事件通道 + 有界缓冲 + 消息合并 + 断线重连** 四层机制应对。

#### 6.4.1 跨进程事件通道：Redis Pub/Sub

> **架构约束**: Docker Compose 中 `backend`（FastAPI）和 `worker`（Celery）是独立容器/进程，不共享内存。Agent 执行产生的事件在 Worker 进程中，而 SSE 端点在 Backend 进程中。因此不能使用进程内内存队列（如 `asyncio.Queue`）作为事件总线，必须使用 **Redis Pub/Sub** 作为跨进程事件通道。

**事件流转示意图**:

```
[Celery Worker]                    [Redis]                    [FastAPI Backend]
     │                               │                              │
  Agent 执行产生事件              │                              │
     │                               │                              │
     │── PUBLISH                    │                              │
     │   events:{project_id} ───▶│                              │
     │                               │── fan-out ──────────────▶│
     │                               │                     SUBSCRIBE │
     │                               │                   events:{id} │
     │                               │                              │
     │                               │                         SSE 推送到前端
```

**Worker 端发布事件**:

```python
import redis.asyncio as aioredis
import json

class EventPublisher:
    """在 Celery Worker 中发布事件到 Redis"""

    def __init__(self, redis_url: str):
        self._redis = aioredis.from_url(redis_url)

    async def publish(self, project_id: str, event: AgentEvent):
        """发布事件到 Redis Pub/Sub 频道"""
        channel = f"events:{project_id}"
        await self._redis.publish(channel, json.dumps(event))

    def publish_sync(self, project_id: str, event: AgentEvent):
        """同步版发布，供 Celery 任务中调用"""
        r = redis.from_url(self._redis_url)
        channel = f"events:{project_id}"
        r.publish(channel, json.dumps(event))
```

**Backend 端订阅与转发**:

```python
class EventBus:
    """项目级事件总线，基于 Redis Pub/Sub 实现跨进程事件通道"""

    def __init__(self, redis_url: str, max_buffer_size: int = 500):
        self._redis = aioredis.from_url(redis_url)
        self._max_buffer_size = max_buffer_size

    async def subscribe(self, project_id: str):
        """SSE 端点消费事件的异步生成器，从 Redis 订阅事件"""
        pubsub = self._redis.pubsub()
        channel = f"events:{project_id}"
        await pubsub.subscribe(channel)
        try:
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                event = json.loads(message["data"])
                yield event
                if event["event_type"] == "complete":
                    break
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()
```

| 组件             | 职责                         | 依赖  |
| ---------------- | ---------------------------- | ----- |
| `EventPublisher` | Worker 端发布事件到 Redis    | Redis |
| `EventBus`       | Backend 端订阅事件并转发 SSE | Redis |

> **为何不用 Redis Stream**: Redis Pub/Sub 是即发即弃模式，足够满足实时事件推送场景。Redis Stream 支持持久化和消费组，但引入额外复杂度。当前事件仅用于 UI 实时展示，不需要持久化，丢失事件可通过断线重连重放机制补对。MVP 阶段使用 Pub/Sub，如后续需求升级可替换为 Stream。

#### 6.4.2 本地有界缓冲

Backend 端在 Redis 订阅与 SSE 推送之间保持一个本地有界缓冲，用于断线重放和背压控制：

```python
from collections import deque

class ReplayBuffer:
    """最近事件缓冲，支持断线重连重放"""

    def __init__(self, max_size: int = 100):
        self._buffer: dict[str, deque] = defaultdict(lambda: deque(maxlen=max_size))

    def append(self, project_id: str, event: AgentEvent):
        self._buffer[project_id].append(event)

    def replay_since(self, project_id: str, last_event_id: str) -> list[AgentEvent]:
        """Return events after the given event ID"""
        events = self._buffer.get(project_id, deque())
        result = []
        found = False
        for e in events:
            if found:
                result.append(e)
            elif e.get("event_id") == last_event_id:
                found = True
        return result
```

**消息合并（Debounce）**: 高频 `progress` 事件（如 Reader 每秒完成多篇论文）在推送前合并，降低前端渲染压力：

| 事件类型       | 合并策略                                                   | 最大延迟 |
| -------------- | ---------------------------------------------------------- | -------- |
| `progress`     | 相同 `agent_name` 的连续 progress 事件合并，只保留最新计数 | 500ms    |
| `error`        | 不合并，立即推送                                           | 0        |
| `hitl_request` | 不合并，立即推送                                           | 0        |
| `complete`     | 不合并，立即推送                                           | 0        |

**断线重连与消息重放**: SSE 规范原生支持 `Last-Event-ID`，客户端断线重连时携带最后收到的事件 ID，后端从缓冲中重放丢失事件：

```python
# api/routes/events.py
@router.get("/api/v1/projects/{project_id}/events")
async def sse_stream(project_id: str, last_event_id: str | None = Header(None)):
    async def event_generator():
        # 若客户端断线重连，从本地 ReplayBuffer 重放丢失事件
        if last_event_id:
            missed = replay_buffer.replay_since(project_id, last_event_id)
            for event in missed:
                yield format_sse(event)

        # 订阅 Redis Pub/Sub，接收 Worker 推送的事件
        async for event in event_bus.subscribe(project_id):
            replay_buffer.append(project_id, event)  # 存入重放缓冲
            yield format_sse(event)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

**设计约束**:

| 参数                   | 默认值 | 说明                                             |
| ---------------------- | ------ | ------------------------------------------------ |
| `progress_debounce_ms` | 500    | progress 事件合并窗口                            |
| `replay_buffer_size`   | 100    | 本地 ReplayBuffer 容量，断线重连时最多重放的事件 |

---

## 七、状态管理与持久化

### 7.1 LangGraph Checkpointer

Checkpointer 通过配置层切换，MVP 使用 `SqliteSaver`，远期迁移到 `PostgresSaver` 无需修改业务代码：

```python
from app.config import settings

def create_checkpointer():
    """根据配置创建 Checkpointer 实例"""
    if settings.CHECKPOINTER_BACKEND == "sqlite":
        from langgraph.checkpoint.sqlite import SqliteSaver
        return SqliteSaver.from_conn_string(settings.CHECKPOINT_DB_URL)
    elif settings.CHECKPOINTER_BACKEND == "postgres":
        from langgraph.checkpoint.postgres import PostgresSaver
        return PostgresSaver.from_conn_string(settings.CHECKPOINT_DB_URL)
    else:
        raise ValueError(f"Unknown checkpointer backend: {settings.CHECKPOINTER_BACKEND}")

checkpointer = create_checkpointer()
graph = workflow.compile(checkpointer=checkpointer)
```

**配置项**:

```bash
# .env
CHECKPOINTER_BACKEND=sqlite                    # "sqlite" (MVP) | "postgres" (远期)
CHECKPOINT_DB_URL=sqlite:///data/checkpoints.db # 或 postgresql://user:pass@host/dbname
```

**持久化时机**: 每个 Node 执行完成后自动保存 checkpoint。

**恢复策略**: 用户重新打开项目时，从最近的 checkpoint 恢复状态，继续执行未完成的步骤。

### 7.2 状态快照结构

```
checkpoints.db
├── thread_id (项目 ID)
│   ├── checkpoint_1  (parse_intent 完成后)
│   ├── checkpoint_2  (search 完成后)
│   ├── checkpoint_3  (human_review_search 完成后)
│   ├── checkpoint_4  (read 完成后)
│   └── ...
```

### 7.3 项目级持久化

除 LangGraph checkpoint 外，项目元数据存储在业务数据库中。业务层通过 **SQLAlchemy ORM** 访问数据库，避免直接 SQL，确保 SQLite → PostgreSQL 迁移时业务代码无需修改：

```python
# models/database.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

engine = create_async_engine(settings.DATABASE_URL)
async_session = async_sessionmaker(engine, expire_on_commit=False)
```

**项目模型（SQLAlchemy ORM）**:

```python
# models/project.py
from sqlalchemy import Column, String, Integer, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from app.models.database import Base
import uuid

class Project(Base):
    """项目 ORM 模型 — 字段定义对齐 data-model.md §3.1 (权威定义)"""
    __tablename__ = "projects"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=True)          # MVP 单用户暂为空
    title = Column(String, nullable=False)
    user_query = Column(String, nullable=False)
    status = Column(String, default="created")       # ProjectStatus 枚举值
    output_types = Column(JSON, default=["full_review"])  # OutputType 数组 (对齐数据模型)
    output_language = Column(String, default="zh")    # "zh" | "en" | "bilingual"
    citation_style = Column(String, default="apa")    # CitationStyle 枚举值
    search_config = Column(JSON, nullable=True)       # 检索配置
    thread_id = Column(String, unique=True)           # 对应 LangGraph thread
    paper_count = Column(Integer, default=0)
    token_usage = Column(JSON, nullable=True)         # Token 消耗追踪
    token_budget = Column(Integer, nullable=True)     # Token 预算上限
    created_at = Column(DateTime, server_default="now()")
    updated_at = Column(DateTime, onupdate="now()")
    config = Column(JSON, default=dict)               # 检索配置、写作偏好等
```

### 7.4 数据库迁移策略

采用 **Alembic** 管理数据库 Schema 迁移，确保 SQLite（MVP）→ PostgreSQL（远期）的平滑过渡：

**目录结构**:

```
backend/
├── alembic/
│   ├── alembic.ini              # Alembic 配置（DB URL 从环境变量读取）
│   ├── env.py                   # 迁移环境配置，引入 Base.metadata
│   └── versions/                # 迁移脚本目录
│       ├── 001_initial.py       # 初始 schema（projects, papers 表）
│       └── ...
```

**Alembic 配置要点**:

```python
# alembic/env.py
from app.models.database import Base
from app.models.project import Project   # 确保所有模型被导入
from app.models.paper import Paper

target_metadata = Base.metadata          # 自动检测 ORM 模型变更
```

**迁移工作流**:

```bash
# 生成迁移脚本（检测 ORM 模型变更）
alembic revision --autogenerate -m "add_token_tracking_fields"

# 执行迁移
alembic upgrade head

# 回滚
alembic downgrade -1
```

**MVP → PostgreSQL 迁移路径**:

| 阶段       | 数据库     | 迁移步骤                                                                                                                                                                  |
| ---------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| MVP (v0.1) | SQLite     | 初始 schema 通过 Alembic 创建，开发期间 `alembic upgrade head`                                                                                                            |
| v0.2~v0.4  | SQLite     | 增量迁移脚本管理 schema 变更                                                                                                                                              |
| v0.5       | PostgreSQL | 1. 修改 `DATABASE_URL` 环境变量 → 2. `alembic upgrade head` 在 PG 上重建 schema → 3. 数据迁移脚本（如需保留历史数据） → 4. 修改 `CHECKPOINTER_BACKEND=postgres`（见 7.1） |

**SQLAlchemy 方言兼容性约束**:

ORM 模型中避免使用 SQLite 特有语法，确保与 PostgreSQL 兼容：
- 使用 `Column(String)` 而非 `Column(Text)` + SQLite collation
- JSON 字段使用 `Column(JSON)`（SQLAlchemy 自动适配不同方言）
- UUID 字段使用 `Column(String)` 存储（而非 PostgreSQL 原生 UUID 类型），MVP 阶段兼容性优先

---

## 八、数据流架构

### 8.1 端到端数据流

```
用户请求
  │
  ▼
[API Layer] ────────────────────────────────────────────────────┐
  │ 创建项目, 启动工作流                                         │
  │                                                             │
  ▼                                                             │
[Orchestrator] ReviewState 初始化                                │
  │                                                             │
  ▼                                                             │
[Search Agent] ◀──────────── (反馈环路: 补充检索) ──────┐       │  SSE
  │ query → External APIs → PaperMetadata[]             │       │  推送
  │ 写入: candidate_papers                               │       │  │
  ▼                                                     │       │  │
[HITL: 用户确认] ← ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┤─ ─ ─ ┤  │
  │ 写入: selected_papers                                │       │  │
  ▼                                                     │       │  │
[Reader Agent]                                          │       │  │
  │ selected_papers → PDF下载 → LLM 分析                │       │  │
  │ 写入: paper_analyses, fulltext_coverage              │       │  │
  │ 副作用: 论文 embedding → Chroma                       │       │  │
  ▼                                                     │       │  │
[check_read_feedback] ─── 需补充? ── yes ───────────────┘       │  │
  │ no                                                          │  │
  ▼                                                             │  │
[Analyst Agent]                                                 │  │
  │ paper_analyses → 聚类/对比/趋势分析                          │  │
  │ 写入: topic_clusters, comparison_matrix, ...                 │  │
  ▼                                                             │  │
[Critic Agent]                                                  │  │
  │ analyses + clusters → 质量/矛盾/Gap 评估                    │  │
  │ 写入: research_gaps, contradictions, ...                     │  │
  ▼                                                             │  │
[check_critic_feedback] ── 覆盖不足? ── yes ── → Search ──┐    │  │
  │ no                                                     │    │  │
  ▼                                                        │    │  │
[Writer Agent - Outline]                                   │    │  │
  │ all_results → 综述大纲                                  │    │  │
  │ 写入: outline                                          │    │  │
  ▼                                                        │    │  │
[HITL: 大纲确认] ← ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┤─ ─ ┤  │
  │                                                             │  │
  ▼                                                             │  │
[Writer Agent - Draft]                                          │  │
  │ outline + all_results → 完整综述                              │  │
  │ 写入: full_draft, references                                  │  │
  │ 累计: token_usage                                            │  │
  ▼                                                             │  │
[verify_citations]                                              │  │
  │ 回溯数据源确认每条引用存在性                                    │  │
  │ 写入: citation_verification                                  │  │
  ▼                                                             │  │
[HITL: 初稿审阅] ← ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┤  │
  │                                                             │  │
  ▼                                                             │  │
[Export]                                                        │  │
  │ full_draft → Markdown / Word / BibTeX / RIS                 │  │
  │ 写入: final_output                                           │  ▼
  └──────────────────────────────────────────────────────────────┘
                                                                → 用户
```

> **反馈环路说明**: 数据流中标注的反馈环路受 `feedback_iteration_count` 限制（最大 2 次），防止无限循环。每次反馈触发时，仅针对 `feedback_search_queries` 中指定的论文/方向做定向补充检索，而非全量重检。

### 8.2 外部数据交互时序

```
[Search Agent]          [Semantic Scholar]    [arXiv]         [Redis Cache]
     │                        │                  │                │
     │── check cache ─────────────────────────────────────────▶│
     │◀─ cache miss ──────────────────────────────────────────│
     │                        │                  │                │
     │── search(query) ──────▶│                  │                │
     │                        │── HTTP GET ──▶   │                │
     │── search(query) ─────────────────────────▶│                │
     │                        │                  │── HTTP GET ──▶ │
     │◀─ results ────────────│                  │                │
     │◀─ results ───────────────────────────────│                │
     │                        │                  │                │
     │── cache results ──────────────────────────────────────▶│
     │                        │                  │                │
     │── deduplicate ──▶      │                  │                │
     │── rank ──▶             │                  │                │
     │                        │                  │                │
```

### 8.3 接口层 REST API 设计

后端 FastAPI 暴露以下 REST API，供前端 / CLI / 第三方集成调用。所有业务 API 统一使用 `/api/v1/` 前缀，为后续破坏性变更预留版本切换空间。MVP 阶段实现标注 ✅ 的接口。

#### 8.3.1 项目管理

| 方法   | 路径                    | 说明         | MVP | 请求体 / 参数                       | 响应                                 |
| ------ | ----------------------- | ------------ | --- | ----------------------------------- | ------------------------------------ |
| POST   | `/api/v1/projects`      | 创建综述项目 | ✅   | `ProjectCreate` (见数据模型 §3.2)   | `ProjectResponse`                    |
| GET    | `/api/v1/projects`      | 列出所有项目 | ✅   | `?status=` `?page=` `?size=`        | `PaginatedResponse[ProjectResponse]` |
| GET    | `/api/v1/projects/{id}` | 获取项目详情 | ✅   |                                     | `ProjectResponse`                    |
| DELETE | `/api/v1/projects/{id}` | 软删除项目   | ✅   |                                     | `204 No Content`                     |
| PATCH  | `/api/v1/projects/{id}` | 更新项目配置 | ✅   | `{token_budget, output_types, ...}` | `ProjectResponse`                    |

**分页响应格式**:

所有返回列表的 API 使用统一的分页包装：

```python
class PaginatedResponse(BaseModel, Generic[T]):
    """统一分页响应格式"""
    items: list[T]          # 当前页数据
    total: int              # 总记录数
    page: int               # 当前页码 (1-based)
    size: int               # 每页条数
    pages: int              # 总页数
```

#### 8.3.2 工作流控制

| 方法 | 路径                                    | 说明                        | MVP | 请求体 / 参数           | 响应                     |
| ---- | --------------------------------------- | --------------------------- | --- | ----------------------- | ------------------------ |
| POST | `/api/v1/projects/{id}/workflow/start`  | 启动工作流                  | ✅   | `{}`                    | `{task_id, status}`      |
| POST | `/api/v1/projects/{id}/workflow/resume` | 从 HITL 断点恢复 (提交反馈) | ✅   | `HitlFeedback` (见下方) | `{task_id, status}`      |
| GET  | `/api/v1/projects/{id}/workflow/status` | 查询工作流当前状态          | ✅   |                         | `{phase, progress, ...}` |
| POST | `/api/v1/projects/{id}/workflow/cancel` | 取消工作流                  | ✅   |                         | `204 No Content`         |

**HitlFeedback 请求体**:

```python
class HitlFeedback(BaseModel):
    """用户在 HITL 节点提交的反馈"""
    hitl_type: str                              # "search_review" | "outline_review" | "draft_review"
    # ── 检索确认 ──
    selected_paper_ids: list[str] | None = None  # 用户确认的论文 ID 列表
    additional_query: str | None = None          # 用户要求补充检索的查询词
    # ── 大纲审阅 ──
    approved_outline: dict | None = None         # 用户修改后的大纲 (None 表示直接通过)
    # ── 初稿审阅 ──
    revision_instructions: str | None = None     # 修改指令 (None 表示直接通过)
    approved: bool = True                        # False 表示需要修改
```

#### 8.3.3 论文管理

| 方法  | 路径                                      | 说明                     | MVP | 请求体 / 参数                           | 响应                                      |
| ----- | ----------------------------------------- | ------------------------ | --- | --------------------------------------- | ----------------------------------------- |
| GET   | `/api/v1/projects/{id}/papers`            | 获取项目论文列表         | ✅   | `?status=candidate\|selected\|excluded` | `PaginatedResponse[ProjectPaperResponse]` |
| PATCH | `/api/v1/projects/{id}/papers/{paper_id}` | 更新论文状态 (选中/排除) | ✅   | `{status: "selected"\|"excluded"}`      | `ProjectPaperResponse`                    |
| GET   | `/api/v1/papers/{id}`                     | 获取论文详情 (含分析)    | ✅   |                                         | `PaperResponse`                           |
| POST  | `/api/v1/projects/{id}/papers/upload`     | 上传 PDF / BibTeX / RIS  | ✅   | `multipart/form-data`                   | `list[PaperResponse]`                     |

#### 8.3.4 输出与导出

| 方法 | 路径                                               | 说明             | MVP | 请求体 / 参数                       | 响应                                |
| ---- | -------------------------------------------------- | ---------------- | --- | ----------------------------------- | ----------------------------------- |
| GET  | `/api/v1/projects/{id}/outputs`                    | 获取项目所有输出 | ✅   | `?type=full_review`                 | `list[ReviewOutputResponse]`        |
| GET  | `/api/v1/projects/{id}/outputs/{output_id}`        | 获取单个输出详情 | ✅   |                                     | `ReviewOutputResponse`              |
| POST | `/api/v1/projects/{id}/outputs/{output_id}/export` | 导出为指定格式   | ✅   | `{format: "markdown"\|"word"\|...}` | 文件流 (`application/octet-stream`) |

#### 8.3.5 事件流

| 方法 | 路径                           | 说明                  | MVP | 参数                   | 响应                |
| ---- | ------------------------------ | --------------------- | --- | ---------------------- | ------------------- |
| GET  | `/api/v1/projects/{id}/events` | SSE 事件流 (实时进度) | ✅   | `Last-Event-ID` header | `text/event-stream` |

SSE 事件格式见 §6.3 `AgentEvent` 定义，背压与断线重连机制见 §6.4。

#### 8.3.6 系统

| 方法 | 路径       | 说明     | MVP | 响应                                  |
| ---- | ---------- | -------- | --- | ------------------------------------- |
| GET  | `/healthz` | 存活检查 | ✅   | `{status: "ok"}`                      |
| GET  | `/readyz`  | 就绪检查 | ✅   | `{status, checks: {database, redis}}` |

#### 8.3.7 错误响应格式

所有 API 错误统一返回以下 JSON 格式：

```json
{
  "detail": {
    "code": "PROJECT_NOT_FOUND",
    "message": "Project with id 'xxx' not found",
    "params": {"project_id": "xxx"}
  }
}
```

| HTTP 状态码 | 使用场景                      |
| ----------- | ----------------------------- |
| 400         | 请求参数校验失败              |
| 404         | 资源不存在                    |
| 409         | 状态冲突 (如工作流已在运行中) |
| 422         | Pydantic 校验错误             |
| 429         | 请求过于频繁                  |
| 500         | 服务端内部错误                |
| 503         | 依赖服务不可用 (LLM / 数据源) |

---

## 九、外部数据源接入层

### 9.1 统一适配器架构

```python
from abc import ABC, abstractmethod

class PaperSource(ABC):
    """学术数据源统一抽象接口"""

    @abstractmethod
    async def search(self, query: str, filters: dict) -> list[PaperMetadata]:
        """关键词检索"""
        ...

    @abstractmethod
    async def get_paper(self, paper_id: str) -> PaperMetadata:
        """获取单篇论文详情"""
        ...

    @abstractmethod
    async def get_citations(self, paper_id: str) -> list[PaperMetadata]:
        """获取引用该论文的论文列表"""
        ...

    @abstractmethod
    async def get_references(self, paper_id: str) -> list[PaperMetadata]:
        """获取该论文引用的论文列表"""
        ...
```

### 9.2 数据源注册机制（SourceRegistry）

设计原则中提到"Agent/数据源可热插拔"，通过 `SourceRegistry` 实现数据源的自注册与自动发现，新增数据源只需实现 `PaperSource` 接口并注册，Search Agent 无需修改代码即可调用。

```python
class SourceRegistry:
    """数据源注册中心，管理所有可用的 PaperSource 实例"""

    def __init__(self):
        self._sources: dict[str, PaperSource] = {}
        self._enabled: set[str] = set()

    def register(self, name: str, source: PaperSource, enabled: bool = True):
        """注册一个数据源实例"""
        self._sources[name] = source
        if enabled:
            self._enabled.add(name)

    def unregister(self, name: str):
        """移除数据源"""
        self._sources.pop(name, None)
        self._enabled.discard(name)

    def enable(self, name: str):
        """启用已注册的数据源"""
        if name in self._sources:
            self._enabled.add(name)

    def disable(self, name: str):
        """禁用数据源（保留注册，不参与检索）"""
        self._enabled.discard(name)

    def get_enabled_sources(self) -> list[tuple[str, PaperSource]]:
        """返回所有已启用的数据源列表"""
        return [(name, self._sources[name]) for name in self._enabled if name in self._sources]

    def get_source(self, name: str) -> PaperSource | None:
        """按名称获取特定数据源"""
        return self._sources.get(name)
```

**启动时注册**:

```python
# app/sources/__init__.py
def create_source_registry(config: Settings) -> SourceRegistry:
    """根据配置创建并注册所有数据源"""
    registry = SourceRegistry()
    cache = Redis.from_url(config.redis_url)

    # MVP 数据源
    registry.register("semantic_scholar", CachedSource(
        SemanticScholarSource(api_key=config.s2_api_key),
        cache=cache,
    ))
    registry.register("arxiv", CachedSource(
        ArxivSource(),
        cache=cache,
    ))

    # 后续数据源按需注册（仅需实现 PaperSource 接口）
    # registry.register("openalex", CachedSource(OpenAlexSource(), cache=cache))
    # registry.register("pubmed", CachedSource(PubMedSource(api_key=...), cache=cache))

    return registry
```

**Search Agent 调用方式**:

Search Agent 的 `Multi-Source Fetcher` 不再硬编码数据源，而是从 `SourceRegistry` 动态获取所有已启用数据源并行检索：

```python
async def multi_source_fetch(registry: SourceRegistry, query: str, filters: dict) -> list[PaperMetadata]:
    """并行调用所有已启用数据源"""
    sources = registry.get_enabled_sources()
    tasks = [source.search(query, filters) for _, source in sources]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_papers = []
    for (name, _), result in zip(sources, results):
        if isinstance(result, Exception):
            logger.warning("source.search_failed", source=name, error=str(result))
            continue
        all_papers.extend(result)
    return all_papers
```

**扩展新数据源的步骤**:

1. 实现 `PaperSource` 接口（如 `sources/openalex.py`）
2. 在 `create_source_registry()` 中注册（或通过配置文件声明）
3. 无需修改 Search Agent 或 Orchestrator 代码

### 9.3 数据源实现清单

| 数据源           | 适配器类                | MVP | 速率限制                   | 备注               |
| ---------------- | ----------------------- | --- | -------------------------- | ------------------ |
| Semantic Scholar | `SemanticScholarSource` | ✅   | 100 req/5min (无 key)      | 主力检索源         |
| arXiv            | `ArxivSource`           | ✅   | 3 req/sec                  | 预印本，全文可下载 |
| OpenAlex         | `OpenAlexSource`        | —   | 100k req/day (polite pool) | 补充检索源         |
| PubMed           | `PubMedSource`          | —   | 10 req/sec (with API key)  | 生物医学领域       |
| CrossRef         | `CrossRefSource`        | —   | 50 req/sec (polite pool)   | DOI 元数据补全     |

### 9.4 速率限制与缓存策略

```python
class RateLimiter:
    """令牌桶限速器"""
    def __init__(self, rate: int, per_seconds: int):
        self.rate = rate
        self.per_seconds = per_seconds
        # ...

class CachedSource:
    """数据源缓存装饰器"""
    def __init__(self, source: PaperSource, cache: Redis, ttl: int = 86400):
        self.source = source
        self.cache = cache
        self.ttl = ttl  # 默认缓存 24 小时

    async def search(self, query: str, filters: dict) -> list[PaperMetadata]:
        import hashlib, json
        raw = json.dumps({"q": query, "f": filters}, sort_keys=True)
        query_hash = hashlib.sha256(raw.encode()).hexdigest()[:16]
        cache_key = f"search:{self.source.__class__.__name__}:{query_hash}"
        cached = await self.cache.get(cache_key)
        if cached:
            return cached
        results = await self.source.search(query, filters)
        await self.cache.set(cache_key, results, ex=self.ttl)
        return results
```

---

## 十、异步任务与队列设计

### 10.1 任务分类

| 任务类型          | 执行方式            | 说明                           |
| ----------------- | ------------------- | ------------------------------ |
| **工作流执行**    | Celery Worker       | 完整的综述生成流程，长时间运行 |
| **PDF 下载/解析** | Celery Worker       | 可并行，I/O 密集型             |
| **LLM 调用**      | asyncio (in Worker) | 异步 HTTP 调用，等待响应       |
| **外部 API 检索** | asyncio (in Worker) | 并行调用多个数据源             |
| **定时文献追踪**  | Celery Beat         | 周期性任务，非 MVP             |
| **导出生成**      | Celery Worker       | Word/LaTeX/PDF 格式转换        |

### 10.2 Celery 任务设计与 HITL 协作模式

LangGraph 工作流在 HITL 节点使用 `interrupt` 暂停执行。若在 Celery Worker 内直接 `graph.stream()`，`interrupt` 会导致 Worker 线程长时间挂起占用资源。

**采用方案：Checkpoint 分段执行**

工作流在每个 HITL `interrupt` 节点自动 checkpoint 保存并结束当前 Celery 任务。用户通过 API 提交 HITL 反馈后，启动新的 Celery 任务从 checkpoint 恢复执行，直到下一个 `interrupt` 或工作流结束。

**Celery 与 asyncio 兼容性**: Agent 内部大量使用 `asyncio`（`asyncio.Semaphore`、`asyncio.gather` 等异步并发），而 Celery Worker 默认使用 prefork 进程池（同步执行）。二者的兼容方案如下：

| 方案                         | 说明                                                           | 选型                    |
| ---------------------------- | -------------------------------------------------------------- | ----------------------- |
| `asyncio.run()` 桥接         | Celery 任务函数为同步函数，内部用 `asyncio.run()` 启动异步入口 | ✅ **MVP 采用**          |
| Celery + `gevent`/`eventlet` | 使用协程 Worker Pool                                           | ❌ 与 asyncio 生态不兼容 |
| 独立 asyncio Worker          | 不使用 Celery，自建 asyncio 消费者                             | ❌ 增加架构复杂度        |

MVP 采用 **`asyncio.run()` 桥接**模式：Celery 任务函数保持同步签名（prefork pool），在任务函数入口通过 `asyncio.run()` 创建新的事件循环驱动异步工作流。LangGraph 的 `graph.stream()` 本身为同步 API，其内部调用的 Agent Node 若需 async 操作（如并行 LLM 调用、并行数据源检索），由 Node 内部自行处理。此模式无需引入额外依赖，且与 Celery prefork 模型完全兼容。

> **嵌套事件循环风险与应对**: `asyncio.run()` 会创建新的事件循环，若当前线程已有运行中的事件循环（如 LangGraph 内部创建），嵌套调用会触发 `RuntimeError: This event loop is already running`。应对策略：
>
> 1. **Celery 任务入口统一管理事件循环**: 任务函数入口调用 `asyncio.run(main_async())` 创建唯一事件循环，所有 Agent Node 内部使用 `await` 而非 `asyncio.run()`
> 2. **LangGraph 异步模式**: 使用 `graph.ainvoke()` / `graph.astream()` 异步 API 替代 `graph.stream()` 同步 API，使整个工作流在同一事件循环内运行
> 3. **推荐方案**: 结合两者，Celery 任务入口用 `asyncio.run()` 启动循环，内部使用 `graph.astream()` 异步流式执行，Agent Node 定义为 `async def` 异步函数，避免任何嵌套事件循环

```python
# tasks.py
import asyncio
from celery import Celery

app = Celery("literature_review")

@app.task(bind=True, max_retries=3, default_retry_delay=60)
def run_review_segment(self, project_id: str, config: dict, resume: bool = False):
    """
    执行工作流的一个段落（两个 interrupt 之间的部分）。
    Celery 任务为同步函数，入口 asyncio.run() 启动事件循环，
    内部使用 graph.astream() 异步执行工作流，避免嵌套事件循环。
    """
    asyncio.run(self._run_async(project_id, config, resume))

async def _run_async(self, project_id: str, config: dict, resume: bool):
    try:
        graph = build_review_graph()  # 含 checkpointer
        event_publisher = EventPublisher(settings.REDIS_URL)

        if resume:
            async for event in graph.astream(None, thread_id=project_id):
                await event_publisher.publish(project_id, event)
        else:
            initial_state = build_initial_state(config)
            async for event in graph.astream(initial_state, thread_id=project_id):
                await event_publisher.publish(project_id, event)

        # graph.astream() 在 interrupt 时自动 checkpoint 并返回
        # Celery 任务自然结束，不占用 Worker 线程

    except Exception as exc:
        self.retry(exc=exc)

@app.task
def download_and_parse_pdf(paper_id: str, pdf_url: str):
    """下载并解析单篇论文 PDF"""
    # ...
```

**HITL 交互时序**:

```
[用户] ────▶ [API: 创建项目] ────▶ [Celery: run_review_segment(resume=False)]
                                         │
                                   graph.stream() 执行到 human_review_search
                                   interrupt → checkpoint 保存 → 任务结束
                                         │
[用户] ◀──── [SSE: hitl_request] ◀───────┘
  │
  │ 确认论文列表
  ▼
[API: 提交 HITL 反馈] ────▶ [Celery: run_review_segment(resume=True)]
                                         │
                                   从 checkpoint 恢复 → 继续执行...
                                   interrupt → checkpoint 保存 → 任务结束
                                         │
[用户] ◀──── [SSE: hitl_request] ◀───────┘
  │
  └── ... 循环直到工作流结束
```

### 10.3 任务优先级

```
Queue: high     ← 用户交互响应（HITL 回调、状态查询）
Queue: default  ← 工作流执行、LLM 调用
Queue: low      ← PDF 下载、缓存预热、定时任务
```

### 10.4 Token 预算管理

Token 预算管理贯穿整个工作流执行过程，在每次 LLM 调用后累加消耗，并在关键节点检查是否超限。

**架构集成点**:

| 集成位置                           | 行为                                                                                   |
| ---------------------------------- | -------------------------------------------------------------------------------------- |
| **LLM 调用层** (`services/llm.py`) | 每次调用后从 LLM 响应中提取 `usage` 字段，累加到 `ReviewState.token_usage`             |
| **Agent Node 出口**                | 每个 Agent 执行完毕后，返回更新后的 `token_usage` 字段                                 |
| **Conditional Edge**               | 在 `search → read`、`read → analyze`、`write_review → verify` 等关键转换前插入预算检查 |
| **预算超限处理**                   | 触发 `interrupt` 暂停工作流，通过 SSE 推送超限通知，用户可选择追加预算或终止           |

**LLM 调用层 Token 追踪伪代码**（完整实现见 10.5 节 `LLMRouter.call()`）:

```python
async def call_llm(prompt: str, agent_name: str, task_type: str, state: ReviewState) -> tuple[str, dict]:
    """LLM 调用封装，自动路由模型 + 追踪 Token 消耗"""
    config = llm_router.resolve_model(agent_name, task_type)  # 多模型路由（见 10.5）
    response = await openai_client.chat.completions.create(model=config.model_name, ...)

    # 提取 Token 用量
    usage = response.usage
    token_update = update_token_usage(
        current=state.get("token_usage", {}),
        agent=agent_name,
        input_tokens=usage.prompt_tokens,
        output_tokens=usage.completion_tokens,
    )

    return response.choices[0].message.content, {"token_usage": token_update}
```

**预算检查在工作流中的嵌入位置**:

```
parse_intent → [budget_check] → search → human_review → [budget_check] → read
→ [budget_check] → analyze → critique → [budget_check] → write → verify → export
```

每个 `[budget_check]` 调用 4.3 节中定义的 `check_token_budget()` 路由函数，超限时路由到 `budget_exceeded` interrupt 节点。

### 10.5 LLM 多模型路由

不同 Agent 的任务复杂度差异显著：Search Agent 的 Query Planner 仅需意图解析，而 Writer Agent 需要长文写作。为优化成本与质量平衡，系统在 `services/llm.py` 中实现 **LLM Router**，根据调用方 Agent 和任务类型自动选择最优模型。

**模型路由配置**:

```python
from dataclasses import dataclass

@dataclass
class ModelConfig:
    """单个模型的配置"""
    model_name: str             # e.g. "gpt-4o", "gpt-4o-mini"
    max_tokens: int             # 最大输出 Token
    temperature: float          # 默认温度
    cost_per_1k_input: float    # 输入成本 ($/1k tokens)
    cost_per_1k_output: float   # 输出成本 ($/1k tokens)

# Agent → 任务类型 → 模型的映射
DEFAULT_MODEL_ROUTING: dict[str, dict[str, str]] = {
    "search": {
        "query_planning":   "gpt-4o-mini",   # 意图解析，复杂度低
        "relevance_ranking": "gpt-4o-mini",  # 相关性评分，批量调用
    },
    "reader": {
        "info_extraction":  "gpt-4o",        # 论文精读，需要强推理
        "relation_detection": "gpt-4o-mini", # 关系判断，结构化任务
    },
    "analyst": {
        "topic_clustering": "gpt-4o",        # 聚类命名，需要领域理解
        "comparison":       "gpt-4o",        # 对比分析
    },
    "critic": {
        "quality_assessment": "gpt-4o",      # 质量评估，需要深度推理
        "gap_identification": "gpt-4o",      # Gap 发现
    },
    "writer": {
        "outline":          "gpt-4o",        # 大纲生成
        "section_writing":  "gpt-4o",        # 章节写作，需要长文能力
        "coherence_review": "gpt-4o",        # 全文连贯性审查
    },
}
```

**LLMRouter 实现**:

```python
class LLMRouter:
    """根据 Agent 和任务类型路由到最优 LLM 模型"""

    def __init__(
        self,
        model_configs: dict[str, ModelConfig],
        routing_table: dict[str, dict[str, str]] | None = None,
        default_model: str = "gpt-4o",
    ):
        self.model_configs = model_configs
        self.routing_table = routing_table or DEFAULT_MODEL_ROUTING
        self.default_model = default_model

    def resolve_model(self, agent_name: str, task_type: str) -> ModelConfig:
        """根据 Agent 名称和任务类型解析应使用的模型"""
        model_name = (
            self.routing_table
            .get(agent_name, {})
            .get(task_type, self.default_model)
        )
        return self.model_configs[model_name]

    async def call(
        self,
        prompt: str,
        agent_name: str,
        task_type: str,
        state: ReviewState,
        **kwargs,
    ) -> tuple[str, dict]:
        """统一 LLM 调用入口：自动路由模型 + Token 追踪"""
        config = self.resolve_model(agent_name, task_type)

        response = await openai_client.chat.completions.create(
            model=config.model_name,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=config.max_tokens,
            temperature=kwargs.get("temperature", config.temperature),
            **kwargs,
        )

        # Token 追踪（复用 10.4 节逻辑）
        usage = response.usage
        token_update = update_token_usage(
            current=state.get("token_usage", {}),
            agent=agent_name,
            input_tokens=usage.prompt_tokens,
            output_tokens=usage.completion_tokens,
        )

        return response.choices[0].message.content, {"token_usage": token_update}
```

**Agent 调用示例**:

```python
# 在 Search Agent 中
result, usage = await llm_router.call(
    prompt=query_prompt,
    agent_name="search",
    task_type="query_planning",   # → 自动路由到 gpt-4o-mini
    state=state,
)

# 在 Writer Agent 中
result, usage = await llm_router.call(
    prompt=section_prompt,
    agent_name="writer",
    task_type="section_writing",  # → 自动路由到 gpt-4o
    state=state,
)
```

**降级路由**: 当主模型不可用时（API 错误、速率限制），LLMRouter 自动降级到备选模型（见第十一节降级策略）：

| 主模型      | 降级模型    | 触发条件                       |
| ----------- | ----------- | ------------------------------ |
| gpt-4o      | gpt-4o-mini | gpt-4o 连续失败 3 次或返回 429 |
| gpt-4o-mini | —           | 最小模型，无降级，直接报错     |

**配置方式**: 路由表通过环境变量 `LLM_ROUTING_CONFIG` 或配置文件 `config/llm_routing.yaml` 覆盖默认值，支持运行时切换而无需修改代码。

### 10.6 Prompt 模板管理

各 Agent 的 LLM Prompt 从代码中剥离为独立模板文件，支持版本化管理和运行时切换，无需修改 Agent 代码即可调优 Prompt。

**模板目录结构**:

```
backend/
├── prompts/
│   ├── search/
│   │   ├── query_planning.md            # Search Agent: 查询规划 prompt
│   │   └── relevance_ranking.md         # Search Agent: 相关性评分 prompt
│   ├── reader/
│   │   ├── info_extraction.md           # Reader Agent: 信息提取 prompt
│   │   └── relation_detection.md        # Reader Agent: 关系检测 prompt
│   ├── analyst/
│   │   ├── topic_clustering.md          # Analyst Agent: 主题聚类 prompt
│   │   └── comparison.md               # Analyst Agent: 对比分析 prompt
│   ├── critic/
│   │   ├── quality_assessment.md        # Critic Agent: 质量评估 prompt
│   │   └── gap_identification.md        # Critic Agent: Gap 发现 prompt
│   └── writer/
│       ├── outline.md                   # Writer Agent: 大纲生成 prompt
│       ├── section_writing.md           # Writer Agent: 章节写作 prompt
│       └── coherence_review.md          # Writer Agent: 连贯性审查 prompt
```

**模板格式**: 使用 Markdown 文件存储 prompt，支持 Jinja2 变量插值：

```markdown
<!-- prompts/reader/info_extraction.md -->
你是一位学术论文分析专家。请对以下论文进行结构化信息提取。

## 论文信息
- 标题: {{ title }}
- 作者: {{ authors }}
- 年份: {{ year }}

## 待分析内容
{{ content }}

## 输出要求
请按以下 JSON 格式输出：
{
  "objective": "研究目标",
  "method": "研究方法",
  "dataset": "使用数据集",
  "findings": "主要发现",
  "limitations": "局限性"
}
```

**PromptManager 实现**:

```python
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape

class PromptManager:
    """Prompt 模板加载与渲染管理"""

    def __init__(self, prompts_dir: str = "prompts"):
        self.prompts_dir = Path(prompts_dir)
        self.env = Environment(
            loader=FileSystemLoader(self.prompts_dir),
            autoescape=select_autoescape([]),  # Prompt 不需要 HTML 转义
        )

    def render(self, agent_name: str, task_type: str, **kwargs) -> str:
        """
        加载并渲染 prompt 模板。

        Args:
            agent_name: Agent 名称（对应子目录）
            task_type: 任务类型（对应模板文件名）
            **kwargs: 模板变量

        Returns:
            渲染后的 prompt 文本
        """
        template_path = f"{agent_name}/{task_type}.md"
        template = self.env.get_template(template_path)
        return template.render(**kwargs)
```

**与 LLMRouter 的集成**: Agent 调用 LLM 时，先通过 `PromptManager` 渲染 prompt，再交给 `LLMRouter` 路由到对应模型：

```python
# Agent 中的调用方式
prompt = prompt_manager.render(
    agent_name="reader",
    task_type="info_extraction",
    title=paper.title,
    authors=", ".join(paper.authors),
    year=paper.year,
    content=paper_text,
)

result, usage = await llm_router.call(
    prompt=prompt,
    agent_name="reader",
    task_type="info_extraction",
    state=state,
)
```

**版本化与切换**:

| 需求                | 实现方式                                                           |
| ------------------- | ------------------------------------------------------------------ |
| Prompt 版本管理     | 模板文件纳入 Git 版本控制，变更可追溯、可回滚                      |
| A/B 测试不同 Prompt | 通过环境变量 `PROMPTS_DIR` 指向不同模板目录（如 `prompts_v2/`）    |
| 按 Agent 覆盖       | `PromptManager` 先查找自定义目录，未命中时 fallback 到默认模板     |
| 运行时热更新        | Jinja2 `FileSystemLoader` 默认不缓存，模板文件修改后下次调用即生效 |

---

## 十一、错误恢复与容错机制

### 11.1 错误分类与处理策略

| 错误类型              | 示例                         | 处理策略                                                      |
| --------------------- | ---------------------------- | ------------------------------------------------------------- |
| **外部 API 暂时失败** | 网络超时、速率限制 429       | 指数退避重试，最多 3 次                                       |
| **外部 API 永久失败** | API 关闭、认证失效           | 跳过该数据源，记录警告，使用其他源填补                        |
| **LLM 调用失败**      | Token 超限、服务不可用       | 重试 → 降级（换模型/缩减输入）→ 报错                          |
| **PDF 解析失败**      | 加密 PDF、图片 PDF、格式异常 | 降级为仅摘要分析，标记该论文为"部分分析"                      |
| **用户会话中断**      | 浏览器关闭、网络断开         | Checkpoint 保存，用户重连后从断点恢复                         |
| **Worker 崩溃**       | OOM、未捕获异常              | Celery 自动重启 Worker，从 checkpoint 恢复（优雅关停见 14.2） |

### 11.2 降级策略

```
完整能力                          降级模式
─────────                        ─────────
全文 PDF 精读                 →   仅摘要分析
多数据源检索 (S2+arXiv+...)  →   单数据源检索
GPT-4o 级别 LLM              →   更小模型 (GPT-4o-mini)
引文网络分析                  →   跳过，仅输出基础聚类
交互式知识图谱                →   静态图片
```

### 11.3 重试机制伪代码

```python
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type((TimeoutError, RateLimitError)),
)
async def call_external_api(source: PaperSource, query: str):
    return await source.search(query)
```

---

## 十二、安全设计

### 12.1 认证与授权

| 层次         | 机制                                                   |
| ------------ | ------------------------------------------------------ |
| **用户认证** | JWT Token，通过 `/auth/login` 获取                     |
| **API 认证** | Bearer Token in Header                                 |
| **CLI 认证** | API Key 存储在本地配置文件                             |
| **权限控制** | 用户只能访问自己的项目和数据（MVP 为单用户，暂不需要） |

### 12.2 数据安全

| 安全点           | 措施                                   |
| ---------------- | -------------------------------------- |
| **API Key 存储** | 环境变量或 `.env` 文件，不入代码仓库   |
| **用户上传文件** | 存储在隔离目录，文件名随机化防路径遍历 |
| **LLM 调用内容** | 不在 prompt 中包含用户认证信息         |
| **数据传输**     | HTTPS（生产环境）                      |
| **输入校验**     | FastAPI Pydantic 模型强制校验所有输入  |

### 12.3 MVP 安全范围

MVP 阶段为单机私有部署，安全优先级：
1. ✅ API Key 环境变量管理
2. ✅ 输入参数校验
3. ✅ 文件上传安全（类型检查、大小限制、路径隔离）
4. ⏳ JWT 认证（v0.2 Web 界面时加入）
5. ⏳ HTTPS（生产部署时加入）

---

## 十三、可观测性与监控

### 13.1 日志设计

```python
import structlog

logger = structlog.get_logger()

# Agent 执行日志
logger.info("agent.execute",
    agent="search",
    project_id="xxx",
    query="LLM code generation",
    source_count=2,
    result_count=47,
    duration_ms=3200)

# LLM 调用日志
logger.info("llm.call",
    agent="reader",
    model="gpt-4o",
    input_tokens=2800,
    output_tokens=1200,
    duration_ms=4500,
    paper_id="xxx")
```

### 13.2 指标监控

| 指标分类       | 关键指标                                   |
| -------------- | ------------------------------------------ |
| **业务指标**   | 项目创建数、完成率、平均论文数、平均耗时   |
| **Agent 指标** | 每个 Agent 执行时间、成功率、重试次数      |
| **LLM 指标**   | 调用次数、Token 消耗、延迟 P50/P95、错误率 |
| **API 指标**   | 外部数据源可用性、响应时间、缓存命中率     |
| **系统指标**   | CPU、内存、磁盘使用率、Worker 队列深度     |

### 13.3 追踪（Tracing）

集成 LangSmith 进行全链路追踪：

```
Project "LLM 综述"
└── Workflow Run #001
    ├── [Search Agent]  3.2s
    │   ├── LLM: query_planning  1.1s  (450 tokens)
    │   ├── API: semantic_scholar  1.5s  (32 results)
    │   └── API: arxiv  0.6s  (15 results)
    ├── [Reader Agent]  45.2s
    │   ├── PDF: download  5.3s  (12 files)
    │   ├── LLM: extract_info [x12]  38.1s  (28k tokens)
    │   └── LLM: detect_relations  1.8s  (2k tokens)
    ├── [Analyst Agent]  8.5s
    │   └── ...
    └── [Writer Agent]  22.3s
        └── ...
```

---

## 十四、部署架构

### 14.1 MVP 部署（Docker Compose）

```yaml
# docker-compose.yml 结构概览
services:
  frontend:
    build: ./frontend
    ports: ["3000:3000"]
    depends_on:
      backend:
        condition: service_healthy

  backend:
    build: ./backend
    ports: ["8000:8000"]
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - DATABASE_URL=sqlite:///data/app.db
      - CHROMA_PATH=/data/chroma
      - REDIS_URL=redis://redis:6379/0
    volumes:
      - app-data:/data
    depends_on:
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/healthz"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s
    stop_grace_period: 30s

  worker:
    build: ./backend
    command: celery -A app.tasks worker -l info -Q high,default,low
              --max-tasks-per-child=100
    environment: # 同 backend
    volumes:
      - app-data:/data
    depends_on:
      redis:
        condition: service_healthy
      backend:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "celery", "-A", "app.tasks", "inspect", "ping", "-t", "5"]
      interval: 60s
      timeout: 10s
      retries: 3
      start_period: 15s
    stop_grace_period: 60s  # Worker 需要更长时间完成当前任务并 checkpoint

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 3

volumes:
  app-data:
```

### 14.2 健康检查与优雅关停

**健康检查端点**:

后端暴露两个健康检查端点，供 Docker / 负载均衡器 / 监控系统调用：

```python
# api/routes/health.py

@router.get("/healthz")
async def healthz():
    """存活检查 (Liveness)：进程是否运行"""
    return {"status": "ok"}

@router.get("/readyz")
async def readyz(db=Depends(get_db), redis=Depends(get_redis)):
    """就绪检查 (Readiness)：依赖服务是否可用"""
    checks = {}
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"

    try:
        await redis.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "error"

    all_ok = all(v == "ok" for v in checks.values())
    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={"status": "ready" if all_ok else "degraded", "checks": checks},
    )
```

| 端点           | 用途                 | 检查内容        | 失败行为               |
| -------------- | -------------------- | --------------- | ---------------------- |
| `GET /healthz` | 存活检查 (Liveness)  | 进程存活        | Docker 重启容器        |
| `GET /readyz`  | 就绪检查 (Readiness) | DB + Redis 可达 | 停止路由流量，等待恢复 |

**优雅关停 (Graceful Shutdown)**:

容器收到 `SIGTERM` 时，各组件按以下顺序安全退出：

```
SIGTERM 信号
    │
    ├── [FastAPI Backend]
    │   1. 停止接受新请求
    │   2. 等待进行中的请求完成（默认 30s timeout）
    │   3. 关闭数据库连接池
    │   4. 退出
    │
    ├── [Celery Worker]
    │   1. 停止消费新任务（warm shutdown）
    │   2. 当前执行的 Agent 任务完成到下一个 checkpoint 保存点
    │   3. 保存 checkpoint → 任务状态标记为 "interrupted"
    │   4. 退出（stop_grace_period: 60s 留足时间）
    │
    └── [Redis]
        1. RDB 持久化 / AOF flush
        2. 退出
```

**Celery Worker 关停处理**:

```python
# tasks.py
from celery.signals import worker_shutting_down

@worker_shutting_down.connect
def on_worker_shutdown(sig, how, exitcode, **kwargs):
    """Worker 关停信号处理：标记当前任务需要在下一个安全点中断"""
    logger.info("worker.shutting_down", signal=sig)
    # 设置全局标志，Agent 执行循环中检查此标志
    # LangGraph checkpoint 机制确保状态已持久化
```

**Worker 防内存泄漏**:

Celery Worker 配置 `--max-tasks-per-child=100`，每个子进程执行 100 个任务后自动回收重启，防止长时间运行导致的内存泄漏。

### 14.3 目录结构

```
agentic-literature-review/
├── docs/
│   └── design/                          # 设计文档
├── backend/
│   ├── app/
│   │   ├── main.py                      # FastAPI 入口
│   │   ├── config.py                    # 配置管理
│   │   ├── api/
│   │   │   ├── routes/
│   │   │   │   ├── projects.py          # 项目 CRUD
│   │   │   │   ├── workflow.py          # 工作流控制
│   │   │   │   ├── events.py            # SSE 事件推送
│   │   │   │   └── health.py            # /healthz + /readyz 端点
│   │   │   └── deps.py                  # 依赖注入
│   │   ├── agents/
│   │   │   ├── orchestrator.py          # LangGraph 工作流动态构建（配置驱动）
│   │   │   ├── registry.py              # AgentRegistry 实现
│   │   │   ├── state.py                 # ReviewState 定义
│   │   │   ├── search_agent.py
│   │   │   ├── reader_agent.py
│   │   │   ├── analyst_agent.py
│   │   │   ├── critic_agent.py
│   │   │   └── writer_agent.py
│   │   ├── sources/
│   │   │   ├── __init__.py              # SourceRegistry 创建与注册
│   │   │   ├── base.py                  # PaperSource 抽象
│   │   │   ├── registry.py              # SourceRegistry 实现
│   │   │   ├── semantic_scholar.py
│   │   │   ├── arxiv.py
│   │   │   └── cache.py                 # 缓存装饰器
│   │   ├── parsers/
│   │   │   ├── pdf_parser.py            # PDF 解析
│   │   │   └── citation_formatter.py    # 引用格式化
│   │   ├── models/
│   │   │   ├── database.py              # SQLAlchemy 引擎 + Base 声明
│   │   │   ├── project.py               # 项目 ORM 模型
│   │   │   └── paper.py                 # 论文 ORM 模型
│   │   ├── services/
│   │   │   ├── llm.py                   # LLM 调用抽象 + LLMRouter 多模型路由
│   │   │   ├── prompt_manager.py        # PromptManager 模板加载与渲染
│   │   │   ├── embedding.py             # Embedding 服务
│   │   │   └── export.py                # 导出服务
│   │   └── tasks.py                     # Celery 任务定义
│   ├── prompts/                         # Prompt 模板（Jinja2 Markdown）
│   │   ├── search/                      # Search Agent prompts
│   │   ├── reader/                      # Reader Agent prompts
│   │   ├── analyst/                     # Analyst Agent prompts
│   │   ├── critic/                      # Critic Agent prompts
│   │   └── writer/                      # Writer Agent prompts
│   ├── alembic/
│   │   ├── alembic.ini                  # Alembic 配置
│   │   ├── env.py                       # 迁移环境（引入 Base.metadata）
│   │   └── versions/                    # 迁移脚本
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
├── config/
│   └── workflow.yaml                    # 工作流 DAG 配置（节点启用/边/路由）
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   ├── components/
│   │   └── services/
│   ├── Dockerfile
│   └── package.json
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## 十五、MVP 架构范围

### 15.1 MVP 包含

| 模块         | 范围                                                                                 |
| ------------ | ------------------------------------------------------------------------------------ |
| **Agent**    | Search + Reader + Writer（3 个核心 Agent）                                           |
| **编排**     | LangGraph 非线性工作流（含 Reader→Search 反馈环路）+ 3 个 HITL 中断点                |
| **输出类型** | Quick Brief（快速摘要）· Annotated Bibliography（注释文献目录）· Full Review（综述） |
| **引用验证** | `verify_citations` 节点：回溯数据源确认每条引用存在性，防止 LLM 幻觉                 |
| **文献互操** | BibTeX / RIS 格式导入导出                                                            |
| **数据源**   | Semantic Scholar + arXiv                                                             |
| **存储**     | SQLite (业务 + checkpoint) + Chroma (向量) + Redis (缓存)                            |
| **LLM**      | OpenAI GPT-4o（可配置切换）                                                          |
| **接口**     | FastAPI REST + SSE                                                                   |
| **部署**     | Docker Compose 单机                                                                  |

### 15.2 MVP 不包含（后续迭代）

| 模块               | 迭代阶段 |
| ------------------ | -------- |
| Analyst Agent      | v0.3     |
| Critic Agent       | v0.3     |
| Update Agent       | v0.5     |
| Web 前端           | v0.2     |
| 知识图谱可视化     | v0.4     |
| 多用户与权限       | v0.4     |
| PostgreSQL / Neo4j | v0.5     |
| K8s 部署           | v1.0     |

### 15.3 MVP 架构简图

```
┌────────────┐     ┌──────────────────────────────────────────┐
│   CLI      │────▶│  FastAPI Backend (:8000)                  │
│   Client   │◀────│                                          │
└────────────┘ SSE │  ┌──────────────────────────────────┐    │
                   │  │  LangGraph Workflow               │    │
                   │  │                                    │    │
                   │  │  Search → [HITL] → Read ──┐       │    │
                   │  │    ▲                       │       │    │
                   │  │    └── feedback ───────────┘       │    │
                   │  │                                    │    │
                   │  │  → Outline → [HITL] → Write       │    │
                   │  │  → verify_citations → [HITL]      │    │
                   │  │  → Export (.md/.docx/.bib/.ris)    │    │
                   │  └──────────────────────────────────┘    │
                   │         │           │                     │
                   │    ┌────┴───┐  ┌────┴──────┐             │
                   │    │ OpenAI │  │ S2 + arXiv│             │
                   │    └────────┘  └───────────┘             │
                   │         │                                 │
                   │  ┌──────┴───────────────────┐            │
                   │  │ SQLite + Chroma + Redis   │            │
                   │  └──────────────────────────┘            │
                   └──────────────────────────────────────────┘
```
