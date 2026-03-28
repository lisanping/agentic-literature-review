# 多智能体文献综述应用 — 系统架构详细设计

> **文档版本**: v1.0
> **创建日期**: 2026-03-28
> **文档状态**: 初稿
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
                           │ HTTPS / WebSocket
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

| 原则           | 说明                                                   |
| -------------- | ------------------------------------------------------ |
| **松耦合**     | Agent 之间通过标准消息协议通信，可独立开发、测试、替换 |
| **可恢复**     | 每个工作流步骤结束后持久化状态，系统重启后可从断点继续 |
| **可观测**     | 全链路 tracing，Agent 每一步推理均可审计               |
| **渐进式扩展** | MVP 最小集合可运行，后续 Agent/数据源可热插拔          |
| **LLM 无关**   | 通过抽象层对接不同 LLM Provider，避免供应商锁定        |

---

## 二、系统分层架构

```
┌─────────────────────────────────────────────────────────────┐
│                    表现层 (Presentation)                     │
│    React SPA · WebSocket 实时推送 · CLI Client              │
├─────────────────────────────────────────────────────────────┤
│                    接口层 (API Layer)                        │
│    FastAPI · REST + WebSocket · 认证鉴权 · 请求校验         │
├─────────────────────────────────────────────────────────────┤
│                    编排层 (Orchestration)                    │
│    LangGraph StateMachine · Workflow DAG · Human-in-loop    │
├─────────────────────────────────────────────────────────────┤
│                    智能体层 (Agent Layer)                    │
│    Search · Reader · Analyst · Critic · Writer · Update     │
├─────────────────────────────────────────────────────────────┤
│                    能力层 (Capability Layer)                 │
│    LLM 调用 · 文献检索 · PDF 解析 · 向量检索 · 图谱构建    │
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
| 接口层     | 请求路由、认证、参数校验、SSE/WS 推送       | FastAPI                 |
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
                ┌────────────────┐
                │  search        │  ← Search Agent 多库检索
                └────────┬───────┘
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
                │                  │
                ▼                  ▼
        ┌──────────────┐  ┌──────────────┐
        │ search (补充) │  │    read      │  ← Reader Agent 精读
        └──────┬───────┘  └──────┬───────┘
               │                 │
               └────────┐       │
                        ▼       ▼
                   ┌──────────────┐
                   │   analyze    │  ← Analyst Agent 分析
                   └──────┬───────┘
                          │
                          ▼
                   ┌──────────────┐
                   │   critique   │  ← Critic Agent 评审
                   └──────┬───────┘
                          │
                          ▼
                ┌──────────────────┐
                │  generate_outline│  ← Writer Agent 生成大纲
                └────────┬─────────┘
                         │
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

### 4.2 核心状态定义（ReviewState）

```python
from typing import TypedDict, Literal, Annotated
from langgraph.graph.message import add_messages

class PaperMetadata(TypedDict):
    paper_id: str           # 统一 ID (DOI / S2 ID / arXiv ID)
    title: str
    authors: list[str]
    year: int
    abstract: str
    source: str             # "semantic_scholar" | "arxiv" | ...
    citation_count: int
    url: str
    pdf_url: str | None

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
    output_type: str                        # 期望输出类型 (见 OutputType 枚举)
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

    # ── 流程控制 ──
    current_phase: str                      # 当前阶段
    messages: Annotated[list, add_messages] # 对话历史
    error_log: list[dict]                   # 错误记录
```

### 4.3 条件路由逻辑

```python
def route_after_search_review(state: ReviewState) -> str:
    """检索确认后的路由：若用户要求补充检索则回到 search，否则进入 read"""
    if state.get("needs_more_search"):
        return "search"
    if len(state["selected_papers"]) == 0:
        return "search"  # 无选中论文，重新检索
    return "read"

def route_after_draft_review(state: ReviewState) -> str:
    """初稿审阅后的路由：需修改则回到 revise，否则导出"""
    if state.get("revision_instructions"):
        return "revise_review"
    return "export"

def should_run_analyst(state: ReviewState) -> bool:
    """仅当论文数量 >= 5 时才运行 Analyst Agent"""
    return len(state.get("paper_analyses", [])) >= 5
```

---

## 五、各 Agent 详细设计

### 5.1 Search Agent

```
输入: user_query, search_strategy, uploaded_papers
输出: candidate_papers
```

| 组件                     | 说明                                                       |
| ------------------------ | ---------------------------------------------------------- |
| **Query Planner**        | 将自然语言转为结构化查询：提取关键词、同义词扩展、布尔组合 |
| **Multi-Source Fetcher** | 并行调用多个数据源 API，统一结果格式                       |
| **Deduplicator**         | 基于 DOI / 标题相似度去重                                  |
| **Snowball Crawler**     | 从种子论文的引用/被引列表获取相关论文                      |
| **Ranker**               | 按相关性 + 引用数 + 年份综合排序                           |

**内部流程**:
```
user_query
    │
    ▼
[Query Planner] → 生成多组查询词
    │
    ├──▶ Semantic Scholar API ──┐
    ├──▶ arXiv API ─────────────┤
    ├──▶ (其他数据源) ──────────┤
    │                           ▼
    │                    [Deduplicator]
    │                           │
    │                           ▼
    │                    [Ranker] → 排序后的候选列表
    │
    └──▶ (如有种子论文) [Snowball Crawler]
              │
              └──▶ 追加到候选列表
```

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

**并行策略**: 多篇论文可并行处理，通过 `asyncio.gather` 或 Celery 任务组实现。

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

---

## 七、状态管理与持久化

### 7.1 LangGraph Checkpointer

```python
from langgraph.checkpoint.sqlite import SqliteSaver

# MVP 阶段使用 SQLite 作为 checkpoint 存储
checkpointer = SqliteSaver.from_conn_string("data/checkpoints.db")

# 构建工作流时注入 checkpointer
graph = workflow.compile(checkpointer=checkpointer)
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

除 LangGraph checkpoint 外，项目元数据存储在业务数据库中：

```
projects 表
├── id                  UUID
├── user_id             UUID
├── title               TEXT
├── user_query          TEXT
├── status              TEXT (searching | reading | analyzing | writing | completed)
├── output_type         TEXT
├── thread_id           TEXT (对应 LangGraph thread)
├── paper_count         INT
├── created_at          TIMESTAMP
├── updated_at          TIMESTAMP
└── config              JSON (检索配置、写作偏好等)
```

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
[Search Agent]                                                  │  SSE
  │ query → External APIs → PaperMetadata[]                     │  推送
  │ 写入: candidate_papers                                       │  │
  ▼                                                             │  │
[HITL: 用户确认] ← ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┤  │
  │ 写入: selected_papers                                        │  │
  ▼                                                             │  │
[Reader Agent]                                                  │  │
  │ selected_papers → PDF下载 → LLM 分析 → PaperAnalysis[]     │  │
  │ 写入: paper_analyses                                         │  │
  │ 副作用: 论文 embedding → Chroma                               │  │
  ▼                                                             │  │
[Analyst Agent]                                                 │  │
  │ paper_analyses → 聚类/对比/趋势分析                          │  │
  │ 写入: topic_clusters, comparison_matrix, ...                 │  │
  ▼                                                             │  │
[Critic Agent]                                                  │  │
  │ analyses + clusters → 质量/矛盾/Gap 评估                    │  │
  │ 写入: research_gaps, contradictions, ...                     │  │
  ▼                                                             │  │
[Writer Agent - Outline]                                        │  │
  │ all_results → 综述大纲                                      │  │
  │ 写入: outline                                                │  │
  ▼                                                             │  │
[HITL: 大纲确认] ← ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┤  │
  │                                                             │  │
  ▼                                                             │  │
[Writer Agent - Draft]                                          │  │
  │ outline + all_results → 完整综述                              │  │
  │ 写入: full_draft, references                                  │  │
  ▼                                                             │  │
[Export]                                                        │  │
  │ full_draft → Word / LaTeX / Markdown / PDF                  │  │
  │ 写入: final_output                                           │  ▼
  └──────────────────────────────────────────────────────────────┘
                                                                → 用户
```

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

### 9.2 数据源实现清单

| 数据源           | 适配器类                | MVP | 速率限制                   | 备注               |
| ---------------- | ----------------------- | --- | -------------------------- | ------------------ |
| Semantic Scholar | `SemanticScholarSource` | ✅   | 100 req/5min (无 key)      | 主力检索源         |
| arXiv            | `ArxivSource`           | ✅   | 3 req/sec                  | 预印本，全文可下载 |
| OpenAlex         | `OpenAlexSource`        | —   | 100k req/day (polite pool) | 补充检索源         |
| PubMed           | `PubMedSource`          | —   | 10 req/sec (with API key)  | 生物医学领域       |
| CrossRef         | `CrossRefSource`        | —   | 50 req/sec (polite pool)   | DOI 元数据补全     |

### 9.3 速率限制与缓存策略

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
        cache_key = f"search:{self.source.__class__.__name__}:{hash(query, filters)}"
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

### 10.2 Celery 任务设计

```python
# tasks.py
from celery import Celery

app = Celery("literature_review")

@app.task(bind=True, max_retries=3, default_retry_delay=60)
def run_review_workflow(self, project_id: str, user_query: str, config: dict):
    """启动完整的文献综述工作流"""
    try:
        graph = build_review_graph()
        initial_state = build_initial_state(user_query, config)

        for event in graph.stream(initial_state, thread_id=project_id):
            # 通过 SSE 推送进度事件到前端
            publish_event(project_id, event)

    except Exception as exc:
        self.retry(exc=exc)

@app.task
def download_and_parse_pdf(paper_id: str, pdf_url: str):
    """下载并解析单篇论文 PDF"""
    # ...
```

### 10.3 任务优先级

```
Queue: high     ← 用户交互响应（HITL 回调、状态查询）
Queue: default  ← 工作流执行、LLM 调用
Queue: low      ← PDF 下载、缓存预热、定时任务
```

---

## 十一、错误恢复与容错机制

### 11.1 错误分类与处理策略

| 错误类型              | 示例                         | 处理策略                                   |
| --------------------- | ---------------------------- | ------------------------------------------ |
| **外部 API 暂时失败** | 网络超时、速率限制 429       | 指数退避重试，最多 3 次                    |
| **外部 API 永久失败** | API 关闭、认证失效           | 跳过该数据源，记录警告，使用其他源填补     |
| **LLM 调用失败**      | Token 超限、服务不可用       | 重试 → 降级（换模型/缩减输入）→ 报错       |
| **PDF 解析失败**      | 加密 PDF、图片 PDF、格式异常 | 降级为仅摘要分析，标记该论文为"部分分析"   |
| **用户会话中断**      | 浏览器关闭、网络断开         | Checkpoint 保存，用户重连后从断点恢复      |
| **Worker 崩溃**       | OOM、未捕获异常              | Celery 自动重启 Worker，从 checkpoint 恢复 |

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
    depends_on: [backend]

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
    depends_on: [redis]

  worker:
    build: ./backend
    command: celery -A app.tasks worker -l info -Q high,default,low
    environment: # 同 backend
    volumes:
      - app-data:/data
    depends_on: [redis, backend]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

volumes:
  app-data:
```

### 14.2 目录结构

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
│   │   │   │   └── events.py            # SSE 事件推送
│   │   │   └── deps.py                  # 依赖注入
│   │   ├── agents/
│   │   │   ├── orchestrator.py          # LangGraph 工作流定义
│   │   │   ├── state.py                 # ReviewState 定义
│   │   │   ├── search_agent.py
│   │   │   ├── reader_agent.py
│   │   │   ├── analyst_agent.py
│   │   │   ├── critic_agent.py
│   │   │   └── writer_agent.py
│   │   ├── sources/
│   │   │   ├── base.py                  # PaperSource 抽象
│   │   │   ├── semantic_scholar.py
│   │   │   ├── arxiv.py
│   │   │   └── cache.py                 # 缓存装饰器
│   │   ├── parsers/
│   │   │   ├── pdf_parser.py            # PDF 解析
│   │   │   └── citation_formatter.py    # 引用格式化
│   │   ├── models/
│   │   │   ├── database.py              # 数据库连接
│   │   │   ├── project.py               # 项目模型
│   │   │   └── paper.py                 # 论文模型
│   │   ├── services/
│   │   │   ├── llm.py                   # LLM 调用抽象
│   │   │   ├── embedding.py             # Embedding 服务
│   │   │   └── export.py                # 导出服务
│   │   └── tasks.py                     # Celery 任务定义
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
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

| 模块       | 范围                                                      |
| ---------- | --------------------------------------------------------- |
| **Agent**  | Search + Reader + Writer（3 个核心 Agent）                |
| **编排**   | LangGraph 线性工作流 + 2 个 HITL 中断点                   |
| **数据源** | Semantic Scholar + arXiv                                  |
| **存储**   | SQLite (业务 + checkpoint) + Chroma (向量) + Redis (缓存) |
| **LLM**    | OpenAI GPT-4o（可配置切换）                               |
| **接口**   | FastAPI REST + SSE                                        |
| **部署**   | Docker Compose 单机                                       |

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
┌────────────┐     ┌──────────────────────────────────────┐
│   CLI      │────▶│  FastAPI Backend (:8000)              │
│   Client   │◀────│                                      │
└────────────┘ SSE │  ┌──────────────────────────────┐    │
                   │  │  LangGraph Workflow           │    │
                   │  │  Search → [HITL] → Read →     │    │
                   │  │  Outline → [HITL] → Write →   │    │
                   │  │  Export                        │    │
                   │  └──────────────────────────────┘    │
                   │         │           │                 │
                   │    ┌────┴───┐  ┌────┴──────┐         │
                   │    │ OpenAI │  │ S2 + arXiv│         │
                   │    └────────┘  └───────────┘         │
                   │         │                             │
                   │  ┌──────┴───────────────────┐        │
                   │  │ SQLite + Chroma + Redis   │        │
                   │  └──────────────────────────┘        │
                   └──────────────────────────────────────┘
```
