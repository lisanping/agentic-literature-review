# MVP v0.1 实施计划

> **文档版本**: v1.0
> **创建日期**: 2026-03-30
> **前置文档**: [需求与功能设计](../design/requirements-and-functional-design.md) · [系统架构](../design/system-architecture.md) · [数据模型](../design/data-model.md) · [产品UX](../design/product-delivery-and-ux.md)
> **目标**: 基于设计文档，将 MVP v0.1 分解为可执行的实施阶段与任务清单

---

## 一、MVP 范围回顾

| 维度     | MVP v0.1 包含                                                |
| -------- | ------------------------------------------------------------ |
| Agent    | Search Agent + Reader Agent + Writer Agent                   |
| 编排     | LangGraph 工作流 + Reader→Search 反馈环路 + 3 个 HITL 中断点 |
| 输出类型 | Quick Brief · Annotated Bibliography · Full Review           |
| 数据源   | Semantic Scholar + arXiv                                     |
| 存储     | SQLite + Chroma + Redis                                      |
| LLM      | OpenAI GPT-4o (可配置)                                       |
| 接口     | FastAPI REST + SSE，CLI 客户端                               |
| 部署     | Docker Compose 单机                                          |
| 导出格式 | Markdown · Word (.docx) · BibTeX (.bib) · RIS (.ris)         |

---

## 二、实施阶段总览

整个 MVP 实施分为 **7 个阶段**，每个阶段有明确的交付物和验收标准。阶段之间存在依赖关系，需按顺序执行；阶段内的任务可适度并行。

```
阶段 1: 项目脚手架与基础设施        ──┐
阶段 2: 数据层 (ORM + 迁移 + 向量库)  ──┤── 基础层 (无业务逻辑)
阶段 3: 能力层 (LLM/数据源/PDF解析)  ──┘
阶段 4: Agent 实现 (Search/Reader/Writer) ──┐
阶段 5: 编排层 (LangGraph 工作流)          ──┤── 核心业务
阶段 6: 接口层 (REST API + SSE + CLI)      ──┘
阶段 7: 集成测试 + Docker 部署 + 文档      ── 交付准备
```

---

## 三、阶段 1：项目脚手架与基础设施

**目标**: 搭建后端项目骨架、配置管理、日志、依赖和 Docker 基础镜像。

### 1.1 任务清单

| #    | 任务                          | 输出文件                                       | 说明                                                                                 |
| ---- | ----------------------------- | ---------------------------------------------- | ------------------------------------------------------------------------------------ |
| 1.1  | 初始化 Python 项目            | `backend/pyproject.toml` 或 `requirements.txt` | Python 3.12，pinning 核心依赖版本                                                    |
| 1.2  | FastAPI 应用入口              | `backend/app/main.py`                          | CORS、全局异常处理器、路由注册、lifespan 事件                                        |
| 1.3  | 配置管理 (Pydantic Settings)  | `backend/app/config.py`                        | 从 `.env` 加载所有配置项 (见 CLAUDE.md 环境变量清单)                                 |
| 1.4  | 结构化日志                    | `backend/app/logging.py`                       | `structlog` 配置，JSON 格式，按环境控制级别                                          |
| 1.5  | 健康检查端点                  | `backend/app/api/routes/health.py`             | `/healthz` 存活检查 + `/readyz` 就绪检查 (DB + Redis)                                |
| 1.6  | `.env.example` + `.gitignore` | 项目根目录                                     | 环境变量模板、Python/Docker 忽略规则                                                 |
| 1.7  | Backend Dockerfile            | `backend/Dockerfile`                           | 多阶段构建，生产用 slim 镜像                                                         |
| 1.8  | docker-compose.yml 骨架       | `docker-compose.yml`                           | backend + worker + redis 三服务，healthcheck，volumes                                |
| 1.9  | pytest 测试基础设施           | `backend/tests/conftest.py`                    | fixture: test client、test db、mock redis                                            |
| 1.10 | 枚举类型定义                  | `backend/app/models/enums.py`                  | `OutputType`, `ProjectStatus`, `PaperSourceType`, `CitationStyle`, `ExportFormat` 等 |

### 1.2 依赖清单 (requirements.txt)

```
# Web 框架
fastapi>=0.115
uvicorn[standard]>=0.30
pydantic>=2.0
pydantic-settings>=2.0

# LangGraph
langgraph>=0.4
langchain-openai>=0.3

# 数据库
sqlalchemy[asyncio]>=2.0
aiosqlite>=0.20
alembic>=1.14

# 向量数据库
chromadb>=0.5

# 任务队列
celery[redis]>=5.4
redis>=5.0

# LLM
openai>=1.60

# PDF 解析
pymupdf>=1.25

# 日志
structlog>=24.0

# 重试
tenacity>=9.0

# Prompt 模板
jinja2>=3.1

# 导出
python-docx>=1.1       # Word 导出

# 测试
pytest>=8.0
pytest-asyncio>=0.24
httpx>=0.27             # FastAPI TestClient
```

### 1.3 验收标准

- [ ] `uvicorn app.main:app --reload` 可启动，`/healthz` 返回 `{"status": "ok"}`
- [ ] `pytest` 可运行，空测试通过
- [ ] `docker compose up` 可启动 backend + redis
- [ ] `.env.example` 含所有配置项，`config.py` 可加载

---

## 四、阶段 2：数据层

**目标**: 实现 ORM 模型、数据库迁移、向量库初始化和 Redis 连接。

### 2.1 任务清单

| #    | 任务                        | 输出文件                                                   | 说明                                                            |
| ---- | --------------------------- | ---------------------------------------------------------- | --------------------------------------------------------------- |
| 2.1  | SQLAlchemy Base + 引擎      | `backend/app/models/database.py`                           | `create_async_engine`、`async_sessionmaker`、`Base`             |
| 2.2  | Project ORM 模型            | `backend/app/models/project.py`                            | 对齐数据模型 §3.1，含 `deleted_at` 软删除                       |
| 2.3  | Paper ORM 模型              | `backend/app/models/paper.py`                              | 对齐 §4.1，含 `paper_fulltext` 表                               |
| 2.4  | PaperAnalysis ORM 模型      | `backend/app/models/paper_analysis.py`                     | 对齐 §5.1，部分唯一索引                                         |
| 2.5  | ProjectPaper ORM 模型       | `backend/app/models/project_paper.py`                      | 对齐 §7.1，含 `status` / `found_by`                             |
| 2.6  | ReviewOutput ORM 模型       | `backend/app/models/review_output.py`                      | 对齐 §6.1，含 `citation_verification` JSON                      |
| 2.7  | Alembic 初始化              | `backend/alembic/`                                         | `alembic init`、`env.py` 配置 `target_metadata = Base.metadata` |
| 2.8  | 初始迁移脚本                | `backend/alembic/versions/001_initial.py`                  | 创建全部 5 张表 + 索引                                          |
| 2.9  | 数据库依赖注入              | `backend/app/api/deps.py`                                  | `get_db()` session 生成器，`get_redis()` 连接                   |
| 2.10 | Chroma 向量库初始化         | `backend/app/services/embedding.py`                        | `paper_embeddings` Collection 创建，`text-embedding-3-small`    |
| 2.11 | 论文去重工具函数            | `backend/app/models/paper.py` (或 `services/paper_ops.py`) | `find_or_create_paper()` —— DOI / S2ID / arXiv ID / 标题相似度  |
| 2.12 | Pydantic Schema (请求/响应) | `backend/app/schemas/`                                     | `ProjectCreate`, `ProjectResponse`, `PaperResponse` 等          |

### 2.2 验收标准

- [ ] `alembic upgrade head` 成功创建 5 张表 + 所有索引
- [ ] ORM CRUD 单元测试通过 (projects, papers 的增删查改)
- [ ] 论文去重逻辑单元测试通过 (4 种匹配策略)
- [ ] Chroma collection 创建成功

---

## 五、阶段 3：能力层

**目标**: 实现 LLM 抽象层、Prompt 管理、外部数据源适配器、PDF 解析、缓存装饰器。

### 3.1 任务清单

| #    | 任务                       | 输出文件                                    | 说明                                                                                                                        |
| ---- | -------------------------- | ------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| 3.1  | LLMRouter + ModelConfig    | `backend/app/services/llm.py`               | 多模型路由 (§10.5)、Token 追踪、降级逻辑                                                                                    |
| 3.2  | PromptManager              | `backend/app/services/prompt_manager.py`    | Jinja2 模板加载器 (§10.6)                                                                                                   |
| 3.3  | PaperSource 抽象接口       | `backend/app/sources/base.py`               | `search`, `get_paper`, `get_citations`, `get_references` 四个抽象方法                                                       |
| 3.4  | SourceRegistry             | `backend/app/sources/registry.py`           | 数据源注册/启用/禁用 (§9.2)                                                                                                 |
| 3.5  | Semantic Scholar 适配器    | `backend/app/sources/semantic_scholar.py`   | 实现 `PaperSource` 接口，解析 S2 API 响应映射到 `PaperMetadata`                                                             |
| 3.6  | arXiv 适配器               | `backend/app/sources/arxiv.py`              | 实现 `PaperSource` 接口，解析 Atom XML                                                                                      |
| 3.7  | RateLimiter                | `backend/app/sources/rate_limiter.py`       | 令牌桶限速器 (S2: 100req/5min, arXiv: 3req/s)                                                                               |
| 3.8  | CachedSource               | `backend/app/sources/cache.py`              | Redis 缓存装饰器 (§9.4)，TTL 24h                                                                                            |
| 3.9  | 数据源注册启动入口         | `backend/app/sources/__init__.py`           | `create_source_registry()` 组装已注册数据源                                                                                 |
| 3.10 | PDF 解析器                 | `backend/app/parsers/pdf_parser.py`         | PyMuPDF 解析全文文本、章节划分；解析失败降级为摘要模式                                                                      |
| 3.11 | 引用格式化                 | `backend/app/parsers/citation_formatter.py` | APA / IEEE / GB/T 7714 格式化、BibTeX + RIS 导入/导出                                                                       |
| 3.12 | 导出服务                   | `backend/app/services/export.py`            | Markdown 原文输出 + python-docx 导出 Word                                                                                   |
| 3.13 | MVP Prompt 模板文件        | `backend/prompts/`                          | Search (query_planning, relevance_ranking) + Reader (info_extraction) + Writer (outline, section_writing, coherence_review) |
| 3.14 | EventPublisher (Worker 端) | `backend/app/services/event_publisher.py`   | Redis Pub/Sub 发布事件 (§6.4.1)                                                                                             |
| 3.15 | EventBus (Backend 端)      | `backend/app/services/event_bus.py`         | Redis Pub/Sub 订阅 + ReplayBuffer (§6.4.2)                                                                                  |

### 3.2 验收标准

- [ ] LLMRouter 单元测试：根据 agent_name + task_type 正确路由模型
- [ ] Semantic Scholar 适配器集成测试：真实 API 检索返回 `PaperMetadata` 列表
- [ ] arXiv 适配器集成测试：XML 解析正确
- [ ] CachedSource 测试：首次请求走 API，二次请求命中缓存
- [ ] PDF 解析测试：解析示例 PDF 提取文本
- [ ] PromptManager 测试：模板变量渲染正确
- [ ] 引用格式化测试：APA/IEEE/GB/T 7714 输出正确

---

## 六、阶段 4：Agent 实现

**目标**: 实现 3 个核心 Agent 的业务逻辑，每个 Agent 作为 LangGraph Node 函数。

### 4.1 任务清单

| #    | 任务                                | 输出文件                                 | 说明                                                                 |
| ---- | ----------------------------------- | ---------------------------------------- | -------------------------------------------------------------------- |
| 4.1  | ReviewState 定义                    | `backend/app/agents/state.py`            | TypedDict (§4.2)，含 State 体积管理注释                              |
| 4.2  | AgentRegistry                       | `backend/app/agents/registry.py`         | Agent 注册中心 (§4.4)                                                |
| 4.3  | Search Agent — Query Planner        | `backend/app/agents/search_agent.py`     | 自然语言 → 结构化查询，1 次 LLM 调用                                 |
| 4.4  | Search Agent — Multi-Source Fetcher | (同上)                                   | 使用 SourceRegistry 并行调用已启用数据源                             |
| 4.5  | Search Agent — Deduplicator         | (同上)                                   | DOI / 标题相似度去重                                                 |
| 4.6  | Search Agent — Snowball Crawler     | (同上)                                   | 引用链展开 (深度 2, 单次 50, 总量 200)                               |
| 4.7  | Search Agent — Ranker               | (同上)                                   | 相关性 + 被引数 + 年份排序                                           |
| 4.8  | Search Agent — Node 函数整合        | (同上)                                   | `search_node(state) -> dict`，自注册 `agent_registry`                |
| 4.9  | Reader Agent — PDF Processor        | `backend/app/agents/reader_agent.py`     | 下载 PDF → 调用 pdf_parser → 结构化文本                              |
| 4.10 | Reader Agent — Abstract Analyzer    | (同上)                                   | 无全文时降级为摘要分析                                               |
| 4.11 | Reader Agent — Info Extractor       | (同上)                                   | LLM 结构化提取 (objective, method, dataset, findings, limitations)   |
| 4.12 | Reader Agent — Relation Detector    | (同上)                                   | 论文间关系识别 (cites, extends, refutes...)                          |
| 4.13 | Reader Agent — 并行处理 + 渐进推送  | (同上)                                   | `asyncio.Semaphore(5)` 并行精读，部分失败降级，SSE 推送进度          |
| 4.14 | Reader Agent — Node 函数整合        | (同上)                                   | `read_node(state) -> dict`                                           |
| 4.15 | Writer Agent — Outline Generator    | `backend/app/agents/writer_agent.py`     | 基于分析结果生成大纲 (LLM 调用)                                      |
| 4.16 | Writer Agent — Section Writer       | (同上)                                   | 逐章节生成综述文本 (LLM 调用)                                        |
| 4.17 | Writer Agent — Citation Formatter   | (同上)                                   | 自动引用标记插入 + 参考文献列表生成                                  |
| 4.18 | Writer Agent — Coherence Reviewer   | (同上)                                   | LLM 全文连贯性审查                                                   |
| 4.19 | Writer Agent — Node 函数整合        | (同上)                                   | `generate_outline_node` + `write_review_node` + `revise_review_node` |
| 4.20 | Verify Citations Node               | `backend/app/agents/verify_citations.py` | 每条引用回溯 S2/arXiv 确认存在性                                     |
| 4.21 | parse_intent Node                   | `backend/app/agents/intent_parser.py`    | LLM 解析用户意图，生成 search_strategy                               |
| 4.22 | Export Node                         | `backend/app/agents/export_node.py`      | 调用 export 服务，生成最终输出文件                                   |

### 4.2 验收标准

- [ ] 每个 Agent Node 函数有独立单元测试 (mock LLM 响应)
- [ ] Search Agent：给定查询词，返回去重排序后的 `candidate_papers`
- [ ] Reader Agent：给定论文列表，返回 `paper_analyses`（mock PDF + mock LLM）
- [ ] Writer Agent：给定分析结果，返回 `outline` → `full_draft` → `references`
- [ ] verify_citations：给定 references，返回 `citation_verification` 结果

---

## 七、阶段 5：编排层

**目标**: 用 LangGraph StateGraph 编排 Agent，实现工作流 DAG、条件路由、HITL 中断、Checkpoint 持久化。

### 5.1 任务清单

| #   | 任务                        | 输出文件                             | 说明                                                                                                     |
| --- | --------------------------- | ------------------------------------ | -------------------------------------------------------------------------------------------------------- |
| 5.1 | workflow.yaml 配置文件      | `config/workflow.yaml`               | MVP 节点配置 (analyze/critique `enabled: false`)                                                         |
| 5.2 | 条件路由函数                | `backend/app/agents/routing.py`      | `route_after_search_review`, `route_after_read`, `route_after_draft_review`, `check_token_budget` (§4.3) |
| 5.3 | Orchestrator — 配置驱动构建 | `backend/app/agents/orchestrator.py` | `build_review_graph()` 动态读取 YAML 构建 DAG (§4.4)                                                     |
| 5.4 | Checkpointer 工厂函数       | `backend/app/agents/checkpointer.py` | `create_checkpointer()` 配置驱动切换 sqlite/postgres (§7.1)                                              |
| 5.5 | HITL 中断点实现             | (orchestrator 内)                    | 3 个 `interrupt` 节点: search_review, outline_review, draft_review                                       |
| 5.6 | 反馈环路流转                | (orchestrator 内)                    | `check_read_feedback` → 条件回到 search，`feedback_iteration_count` 上限 2                               |
| 5.7 | Token 预算检查节点          | (routing.py)                         | 关键转换前检查预算，超限触发 interrupt                                                                   |
| 5.8 | 完整工作流集成测试          | `backend/tests/test_workflow.py`     | Mock Agent Node，验证 DAG 流转顺序、HITL 暂停/恢复、反馈环路                                             |

### 5.2 验收标准

- [ ] 工作流可从头执行到结束 (mock Agent，所有 HITL 自动通过)
- [ ] HITL 暂停后可从 checkpoint 恢复
- [ ] 反馈环路在达到 max_iteration 后自动退出
- [ ] 禁用节点 (analyze/critique) 被正确跳过
- [ ] Token 预算超限时工作流暂停

---

## 八、阶段 6：接口层

**目标**: 实现 REST API、SSE 事件流、Celery 异步任务，以及 CLI 客户端。

### 6.1 任务清单

| #    | 任务                     | 输出文件                             | 说明                                                              |
| ---- | ------------------------ | ------------------------------------ | ----------------------------------------------------------------- |
| 6.1  | 项目管理 API             | `backend/app/api/routes/projects.py` | CRUD 5 个端点 (§8.3.1)，含分页                                    |
| 6.2  | 工作流控制 API           | `backend/app/api/routes/workflow.py` | start/resume/status/cancel 4 个端点 (§8.3.2)                      |
| 6.3  | 论文管理 API             | `backend/app/api/routes/papers.py`   | 列表/更新状态/详情/上传 4 个端点 (§8.3.3)                         |
| 6.4  | 输出与导出 API           | `backend/app/api/routes/outputs.py`  | 列表/详情/导出 3 个端点 (§8.3.4)                                  |
| 6.5  | SSE 事件流端点           | `backend/app/api/routes/events.py`   | Redis Pub/Sub 订阅 → SSE 推送，支持 `Last-Event-ID` 重放 (§8.3.5) |
| 6.6  | 统一错误响应             | `backend/app/api/exceptions.py`      | 全局异常处理器，统一 JSON 格式 (§8.3.7)                           |
| 6.7  | `HitlFeedback` Schema    | `backend/app/schemas/workflow.py`    | HITL 反馈请求体定义 (§8.3.2)                                      |
| 6.8  | Celery 任务 — run_review | `backend/app/tasks.py`               | `run_review_segment()` 分段执行 + checkpoint (§10.2)              |
| 6.9  | Celery 配置              | `backend/app/celery_app.py`          | Broker/Backend 配置、队列优先级 (high/default/low)                |
| 6.10 | CLI 客户端               | `backend/app/cli.py`                 | Click/Typer CLI，支持创建项目、HITL 交互、查看状态 (§9.1 UX)      |
| 6.11 | API 路由注册             | `backend/app/main.py` (更新)         | 注册所有路由 prefix `/api/v1/`                                    |

### 6.2 验收标准

- [ ] 所有 16 个 API 端点功能测试通过
- [ ] SSE 端点可接收实时事件 (mock 事件)
- [ ] Celery Worker 可消费任务并执行分段工作流
- [ ] HITL 反馈提交后可恢复工作流
- [ ] CLI 可完成一次完整文献综述流程 (端到端 mock)

---

## 九、阶段 7：集成测试、Docker 部署与文档

**目标**: 端到端集成验证、Docker Compose 部署就绪、README 和使用文档。

### 7.1 任务清单

| #   | 任务                      | 输出文件                         | 说明                                                |
| --- | ------------------------- | -------------------------------- | --------------------------------------------------- |
| 7.1 | 端到端集成测试 (mock LLM) | `backend/tests/test_e2e.py`      | 从创建项目 → 检索 → HITL → 精读 → 写作 → 导出全流程 |
| 7.2 | 端到端集成测试 (真实 LLM) | `backend/tests/test_e2e_live.py` | 标记 `@pytest.mark.live`，CI 中不运行               |
| 7.3 | Docker Compose 完善       | `docker-compose.yml`             | 完善 volumes / networks / 环境变量 / healthcheck    |
| 7.4 | Celery Worker Dockerfile  | (复用 `backend/Dockerfile`)      | 不同 CMD                                            |
| 7.5 | 优雅关停处理              | `backend/app/tasks.py` (更新)    | `worker_shutting_down` 信号处理 (§14.2)             |
| 7.6 | README.md                 | 项目根目录 `README.md`           | 项目介绍、快速开始、环境变量、Docker 部署步骤       |
| 7.7 | API 文档自动生成          | FastAPI 内置 `/docs`             | Swagger UI，确认所有端点文档完整                    |

### 7.2 验收标准

- [ ] `docker compose up` 一键启动所有服务
- [ ] 容器健康检查 `/healthz` 和 `/readyz` 全部通过
- [ ] CLI 端到端测试 (mock LLM) 通过
- [ ] `docker compose down` 后重新 `up`，已有项目可从 checkpoint 恢复
- [ ] README 可指导新用户从零部署并运行

---

## 十、技术依赖与风险

### 10.1 关键依赖关系

```
阶段 1 (脚手架)
  └──▶ 阶段 2 (数据层) ──▶ 阶段 4 (Agent，需要 ORM + Schema)
  └──▶ 阶段 3 (能力层) ──▶ 阶段 4 (Agent，需要 LLM + 数据源)
                             └──▶ 阶段 5 (编排层，需要 Agent Node)
                                   └──▶ 阶段 6 (接口层，需要编排层 + Celery)
                                         └──▶ 阶段 7 (集成)
```

- **阶段 2 和 3 可并行执行**，均仅依赖阶段 1
- **阶段 4 依赖 2 + 3 全部完成**
- **阶段 5 依赖阶段 4，阶段 6 依赖阶段 5**

### 10.2 技术风险

| 风险                          | 影响 | 缓解策略                                                     |
| ----------------------------- | ---- | ------------------------------------------------------------ |
| Semantic Scholar API 速率限制 | 中   | 申请 API Key 提高限额；CachedSource 缓存 24h；降级到仅 arXiv |
| LangGraph Checkpointer 兼容性 | 中   | 及早进行 checkpoint 保存/恢复测试；锁定 langgraph 版本       |
| Celery + asyncio 嵌套事件循环 | 高   | 采用 `asyncio.run()` 桥接方案；早期验证 PoC                  |
| PDF 解析质量参差              | 低   | 解析失败降级为摘要分析；后续可接入 GROBID                    |
| LLM 输出结构化解析失败        | 中   | Prompt 中强制 JSON 输出格式；tenacity 重试；fallback 兜底    |

---

## 十一、各阶段文件产出清单汇总

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                              # [阶段 1]
│   ├── config.py                            # [阶段 1]
│   ├── logging.py                           # [阶段 1]
│   ├── celery_app.py                        # [阶段 6]
│   ├── tasks.py                             # [阶段 6]
│   ├── cli.py                               # [阶段 6]
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py                          # [阶段 2]
│   │   ├── exceptions.py                    # [阶段 6]
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── health.py                    # [阶段 1]
│   │       ├── projects.py                  # [阶段 6]
│   │       ├── workflow.py                  # [阶段 6]
│   │       ├── papers.py                    # [阶段 6]
│   │       ├── outputs.py                   # [阶段 6]
│   │       └── events.py                    # [阶段 6]
│   ├── models/
│   │   ├── __init__.py
│   │   ├── enums.py                         # [阶段 1]
│   │   ├── database.py                      # [阶段 2]
│   │   ├── project.py                       # [阶段 2]
│   │   ├── paper.py                         # [阶段 2]
│   │   ├── paper_analysis.py                # [阶段 2]
│   │   ├── project_paper.py                 # [阶段 2]
│   │   └── review_output.py                 # [阶段 2]
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── project.py                       # [阶段 2]
│   │   ├── paper.py                         # [阶段 2]
│   │   ├── output.py                        # [阶段 2]
│   │   └── workflow.py                      # [阶段 6]
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── state.py                         # [阶段 4]
│   │   ├── registry.py                      # [阶段 4]
│   │   ├── orchestrator.py                  # [阶段 5]
│   │   ├── checkpointer.py                  # [阶段 5]
│   │   ├── routing.py                       # [阶段 5]
│   │   ├── intent_parser.py                 # [阶段 4]
│   │   ├── search_agent.py                  # [阶段 4]
│   │   ├── reader_agent.py                  # [阶段 4]
│   │   ├── writer_agent.py                  # [阶段 4]
│   │   ├── verify_citations.py              # [阶段 4]
│   │   └── export_node.py                   # [阶段 4]
│   ├── sources/
│   │   ├── __init__.py                      # [阶段 3]
│   │   ├── base.py                          # [阶段 3]
│   │   ├── registry.py                      # [阶段 3]
│   │   ├── semantic_scholar.py              # [阶段 3]
│   │   ├── arxiv.py                         # [阶段 3]
│   │   ├── rate_limiter.py                  # [阶段 3]
│   │   └── cache.py                         # [阶段 3]
│   ├── parsers/
│   │   ├── __init__.py
│   │   ├── pdf_parser.py                    # [阶段 3]
│   │   └── citation_formatter.py            # [阶段 3]
│   └── services/
│       ├── __init__.py
│       ├── llm.py                           # [阶段 3]
│       ├── prompt_manager.py                # [阶段 3]
│       ├── embedding.py                     # [阶段 3]
│       ├── export.py                        # [阶段 3]
│       ├── event_publisher.py               # [阶段 3]
│       └── event_bus.py                     # [阶段 3]
├── prompts/                                 # [阶段 3]
│   ├── search/
│   │   ├── query_planning.md
│   │   └── relevance_ranking.md
│   ├── reader/
│   │   ├── info_extraction.md
│   │   └── relation_detection.md
│   └── writer/
│       ├── outline.md
│       ├── section_writing.md
│       └── coherence_review.md
├── alembic/                                 # [阶段 2]
│   ├── alembic.ini
│   ├── env.py
│   └── versions/
│       └── 001_initial.py
├── tests/                                   # [各阶段]
│   ├── conftest.py
│   ├── test_models.py
│   ├── test_sources.py
│   ├── test_agents.py
│   ├── test_workflow.py
│   ├── test_api.py
│   └── test_e2e.py
├── Dockerfile                               # [阶段 1]
└── requirements.txt                         # [阶段 1]

config/
└── workflow.yaml                            # [阶段 5]

docker-compose.yml                           # [阶段 1 骨架, 阶段 7 完善]
.env.example                                 # [阶段 1]
README.md                                    # [阶段 7]
```

---

## 十二、后续迭代规划 (MVP 之后)

| 版本 | 主要内容              | 关键新增                                         | 状态   |
| ---- | --------------------- | ------------------------------------------------ | ------ |
| v0.2 | Web 前端              | React + Ant Design SPA，对话式交互，实时进度面板 | ✅ 完成 |
| v0.3 | 完整 Agent 链路       | Analyst Agent + Critic Agent，配置文件中启用即可 | ✅ 完成 |
| v0.4 | 多用户 + 可视化       | JWT 认证、权限控制；D3.js 知识图谱/时间线可视化  | ✅ 完成 |
| v0.5 | 更多数据源 + 增量更新 | OpenAlex/PubMed 适配器、Update Agent             | ✅ 完成 |
| v0.6 | 定时调度 + PostgreSQL | Celery Beat 自动更新调度、PostgreSQL 生产数据库  | 📋 计划 |
| v0.7 | 更多数据源 + OAuth    | Crossref/DBLP 适配器、OAuth SSO 登录             | 📋 计划 |
| v1.0 | 生产就绪              | K8s 部署、HTTPS、负载均衡、完善监控              | 📋 计划 |
