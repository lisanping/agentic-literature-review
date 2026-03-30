# 变更日志 (Changelog)

本文件记录项目的所有重要变更，格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 规范。

> **版本规则**: 本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/) (SemVer)。
> **标记说明**: `[设计]` 设计文档变更 · `[后端]` 后端代码 · `[前端]` 前端代码 · `[基础设施]` 部署/CI/配置 · `[文档]` 其他文档

---

## [Unreleased]

### 新增

- `[后端]` 实施计划阶段 7 完成：集成测试、Docker 部署与文档
  - E2E 集成测试 (`tests/test_e2e.py`)：14 项测试覆盖完整生命周期
    - 项目 CRUD 全流程 (创建/获取/更新/列表/删除/404)
    - 工作流控制 (status/cancel/start-Celery-dispatch/conflict-409/resume-HITL-3种类型)
    - 完整 LangGraph 工作流 (mock agents, 3 次 HITL pause/resume, HITL 反馈环路, 修订循环)
    - 统一错误响应格式验证 (§8.3.7)
    - OpenAPI schema 可用性验证
  - Live E2E 测试 (`tests/test_e2e_live.py`)：3 项真实 LLM 测试，标记 `@pytest.mark.live`，CI 中 skip
  - Celery 优雅关停 (`tasks.py`)：`worker_shutting_down` 信号处理，in-flight 任务可感知 shutdown 标志
  - Docker 增强:
    - Dockerfile 添加非 root 用户 (appuser) 安全运行
    - docker-compose.yml 添加 `networks: app-net`、`restart: unless-stopped`、`redis-data` 持久卷、Celery worker 命令修正为 `celery -A app.celery_app:celery_app`
  - README.md：项目介绍、系统架构图、快速开始 (Docker / 本地 / CLI)、API 端点一览、环境变量、项目结构、技术栈
  - Swagger UI 文档验证：16 条 OpenAPI paths 全部完整生成
  - 全部 214 项测试通过，3 项 Live 测试正确 skip
- `[后端]` 实施计划阶段 6 完成：接口层
  - 项目管理 API (`api/routes/projects.py`)：POST/GET/PATCH/DELETE 5 个端点，含分页 PaginatedResponse、软删除
  - 工作流控制 API (`api/routes/workflow.py`)：start/resume/status/cancel 4 个端点，HitlFeedback → ReviewState 转换，Celery 任务调度
  - 论文管理 API (`api/routes/papers.py`)：列表(含分页+状态过滤)/更新状态/详情/上传 4 个端点
  - 输出与导出 API (`api/routes/outputs.py`)：列表/详情/导出(markdown/word/bibtex/ris) 3 个端点，文件流下载
  - SSE 事件流 (`api/routes/events.py`)：Redis Pub/Sub → SSE 推送，Last-Event-ID 重放，_format_sse 格式化
  - 统一错误处理 (`api/exceptions.py`)：AppError/NotFoundError/ConflictError/ServiceUnavailableError，register_exception_handlers 全局注册
  - 工作流 Schema (`schemas/workflow.py`)：HitlFeedback (search_review/outline_review/draft_review)、WorkflowStartResponse、WorkflowStatusResponse、ExportRequest
  - Celery 配置 (`celery_app.py`)：3 级队列 (high/default/low)、JSON 序列化、task_acks_late
  - Celery 任务 (`tasks.py`)：run_review_segment — checkpoint 分段执行，asyncio.run 桥接，HITL aupdate_state 恢复，EventPublisher 事件推送
  - CLI 客户端 (`cli.py`)：Click 命令行界面 — review 命令(交互式 HITL：论文选择/大纲审阅/初稿审阅)、status 命令、Token 用量展示、BibTeX 导出
  - 路由注册 (`main.py`)：6 个 router 全部挂载 — health/projects/workflow/papers/outputs/events
  - 全部 16 个业务端点 + 2 个健康检查 + Swagger 文档确认注册
  - requirements.txt 新增 click>=8.1
  - 30 项新增测试 (异常类 ×4 + Schema ×7 + 路由注册 ×2 + HITL 状态构建 ×5 + Celery ×2 + SSE ×1 + 导出 ×3 + httpx 集成 ×2 + 项目 Schema ×4)，全部 200 项测试通过
- `[后端]` 实施计划阶段 5 完成：编排层
  - workflow.yaml 配置文件 (`config/workflow.yaml`)：MVP 节点配置，analyze/critique `enabled: false`，3 个 HITL `interrupt: true` 节点，4 条条件路由边，revise_review `sequential: false` 仅通过条件路由触达
  - 条件路由函数 (`agents/routing.py`)：route_after_search_review / route_after_read / route_after_critique / route_after_draft_review / check_token_budget，ROUTER_REGISTRY 查找表
  - Orchestrator (`agents/orchestrator.py`)：
    - `load_workflow_config()` 加载 YAML (UTF-8)
    - `build_review_graph()` 配置驱动动态构建 LangGraph StateGraph (12 节点 MVP)，自动过滤禁用节点、区分 sequential/non-sequential 节点、条件路由边自动关联 ROUTER_REGISTRY
    - `compile_review_graph()` 编译含 checkpointer + `interrupt_before` 的完整工作流图
    - HITL passthrough 节点：human_review_search / human_review_outline / human_review_draft (interrupt 前暂停)
    - check_read_feedback 节点：Reader 反馈检查 + feedback_iteration_count 递增
    - revise_review → human_review_draft 循环边
    - `_ensure_agents_imported()` 确保所有 Agent 模块自注册
  - Checkpointer 工厂 (`agents/checkpointer.py`)：`create_checkpointer()` 配置驱动切换 sqlite/postgres
  - requirements.txt 新增 `langgraph-checkpoint-sqlite>=3.0`
  - 31 项新增集成测试 (routing ×15 + HITL 节点 ×5 + config ×2 + graph build ×4 + 端到端 flow ×4 + 反馈环路 ×1)，全部 170 项测试通过
  - 验收标准全部满足：端到端工作流执行 (mock Agent)、HITL 暂停/恢复 (update_state + ainvoke(None))、反馈环路 max_iteration 自动退出、禁用节点跳过、修订循环 (revise → re-review → export)、Token 预算超限检测
- `[后端]` 实施计划阶段 4 完成：Agent 实现
  - ReviewState TypedDict (`agents/state.py`)：全部字段对齐 §4.2，含 HITL 信号、反馈环路控制、Token 预算追踪
  - AgentRegistry (`agents/registry.py`)：全局单例注册中心，Agent 自注册模式
  - parse_intent 节点 (`agents/intent_parser.py`)：LLM 解析用户意图 → search_strategy (queries + key_concepts + filters)，JSON 解析失败有 fallback
  - Search Agent (`agents/search_agent.py`)：
    - Multi-Source Fetcher：asyncio.gather 并行调用 SourceRegistry 所有已启用数据源
    - Deduplicator：DOI → S2 ID → arXiv ID → title 四级去重，高引优先保留
    - Snowball Crawler：S2 引用/被引链展开，深度 2、单次 50、总量 200 约束
    - Ranker：keyword 相关性 × 0.5 + log(citations) × 0.3 + recency × 0.2
  - Reader Agent (`agents/reader_agent.py`)：
    - PDF Processor：httpx 下载 + PyMuPDF 解析，失败降级摘要模式
    - Info Extractor：LLM 结构化提取 (objective/methodology/datasets/findings/limitations/key_concepts)
    - 并行处理：asyncio.Semaphore(5) 并发读取，部分失败不阻塞
    - fulltext_coverage 统计 (全文/仅摘要/失败)
  - Writer Agent (`agents/writer_agent.py`)：
    - generate_outline_node：LLM 生成大纲 (title + sections with relevant_paper_indices)
    - write_review_node：逐章节 LLM 写作 + citation 标记 + 参考文献列表 (APA/IEEE/GB-T)
    - revise_review_node：基于用户修改意见重写
    - build_references_list：从 analyses 构建格式化引用
  - verify_citations 节点 (`agents/verify_citations.py`)：回溯 S2 验证每条引用 (DOI + paper_id)，标记 verified/unverified
  - export 节点 (`agents/export_node.py`)：生成最终 Markdown 输出
  - 全部 8 个 Agent Node 自注册到 agent_registry (parse_intent / search / read / generate_outline / write_review / revise_review / verify_citations / export)
  - 43 项新增单元测试 (mock LLM)，全部 139 项测试通过
- `[后端]` 实施计划阶段 3 完成：能力层
  - LLM 抽象层 (`services/llm.py`)：LLMRouter 多模型路由 (agent×task_type → model)、ModelConfig、Token 用量追踪、失败自动降级 (gpt-4o → gpt-4o-mini)、tenacity 重试 (指数退避 ×3)
  - Prompt 管理 (`services/prompt_manager.py`)：Jinja2 模板加载器，支持变量渲染、热重载、A/B 测试 (PROMPTS_DIR 切换)
  - 7 个 MVP 级 Prompt 模板：search/query_planning + relevance_ranking、reader/info_extraction + relation_detection、writer/outline + section_writing + coherence_review
  - PaperSource 抽象接口 (`sources/base.py`)：search / get_paper / get_citations / get_references 四方法
  - SourceRegistry (`sources/registry.py`)：注册/启用/禁用数据源，运行时动态查询
  - Semantic Scholar 适配器 (`sources/semantic_scholar.py`)：Graph API v1 全字段映射，year 过滤，引用/参考链获取
  - arXiv 适配器 (`sources/arxiv.py`)：Atom XML 解析，arXiv ID 版本号剥离，全字段映射
  - RateLimiter (`sources/rate_limiter.py`)：异步令牌桶限速器 (S2: 100req/5min, arXiv: 3req/s)
  - CachedSource (`sources/cache.py`)：Redis 缓存装饰器，TTL 24h，SHA-256 key 生成
  - 数据源注册入口 (`sources/__init__.py`)：`create_source_registry()` 组装 S2 + arXiv（含缓存）
  - PDF 解析器 (`parsers/pdf_parser.py`)：PyMuPDF 全文提取 + 基于字号/粗体的章节检测，解析失败降级
  - 引用格式化 (`parsers/citation_formatter.py`)：APA / IEEE / GB/T 7714 格式化 + BibTeX/RIS 导入导出
  - 导出服务 (`services/export.py`)：Markdown 全文输出 + python-docx Word 导出 + BibTeX/RIS 导出
  - 事件发布 (`services/event_publisher.py`)：Redis Pub/Sub 异步事件发布 (Worker → Backend)
  - 事件总线 (`services/event_bus.py`)：Redis Pub/Sub 订阅 + ReplayBuffer 断线重放
  - 52 项新增单元测试，全部 96 项测试通过
- `[后端]` 实施计划阶段 2 完成：数据层
  - 5 个 ORM 模型 (Project / Paper+PaperFulltext / PaperAnalysis / ProjectPaper / ReviewOutput)，对齐数据模型设计文档所有字段和索引
  - 所有项目级实体支持 `deleted_at` 软删除，条件唯一索引 `WHERE deleted_at IS NULL`
  - Alembic 异步迁移环境 (async engine)，初始迁移脚本自动生成 6 张表 + 全部索引
  - Pydantic Schema (ProjectCreate/Update/Response, PaperMetadata/Response, ReviewOutputResponse, PaginatedResponse)
  - 论文去重服务 (`paper_ops.py`)：DOI → S2 ID → arXiv ID → 标题模糊匹配四级去重 + 元数据合并
  - Chroma 向量库初始化 (`embedding.py`)：`paper_embeddings` collection，cosine 距离
  - `deps.py` 使用 `database.py` 集中管理的引擎和会话工厂
  - 34 项新增单元测试 (ORM CRUD 11 项 + 去重逻辑 11 项 + Schema 校验 8 项 + Chroma 初始化验证)，全部 44 项测试通过
- `[后端]` 实施计划阶段 1 完成：项目脚手架与基础设施
  - 初始化 Python 项目，`requirements.txt` 锁定全部核心依赖版本
  - FastAPI 应用入口 (`app/main.py`)：CORS、全局异常处理器、lifespan 事件
  - 配置管理 (`app/config.py`)：Pydantic Settings，11 项环境变量从 `.env` 加载
  - 结构化日志 (`app/logging.py`)：structlog JSON 格式，按环境控制级别
  - 健康检查端点 (`app/api/routes/health.py`)：`/healthz` 存活 + `/readyz` 就绪 (DB + Redis)
  - 依赖注入 (`app/api/deps.py`)：异步 DB session 生成器 + Redis 客户端
  - 枚举类型 (`app/models/enums.py`)：6 个 StrEnum (OutputType / ProjectStatus / PaperSourceType / PaperRelationType / CitationStyle / ExportFormat)
  - SQLAlchemy Base 声明 (`app/models/database.py`)
  - `.env.example`、`.gitignore`
  - Backend Dockerfile (多阶段构建)、`docker-compose.yml` 骨架 (backend + worker + redis)
  - pytest 测试基础设施 (`conftest.py`：async client / in-memory DB / mock Redis) + 10 项单元测试全部通过
- `[文档]` 新增 MVP v0.1 实施计划 (`docs/dev/implementation-plan.md`)
  - 基于四份设计文档，将 MVP 分解为 7 个实施阶段：项目脚手架 → 数据层 → 能力层 → Agent 实现 → 编排层 → 接口层 → 集成部署
  - 每个阶段含详细任务清单、输出文件、验收标准
  - 明确阶段间依赖关系（阶段 2/3 可并行，阶段 4 依赖 2+3）
  - 包含完整文件产出清单（约 60 个文件）、技术风险分析、后续迭代规划 (v0.2~v1.0)

### 修复

- `[设计]` P0 级架构缺陷修复（系统架构文档 + 数据模型文档）
  - **跨进程事件通信**: 系统架构 §6.4 `EventBus` 从进程内 `asyncio.Queue` 重构为 **Redis Pub/Sub** 跨进程事件通道。新增 `EventPublisher`（Worker 端发布）和 `EventBus`（Backend 端订阅）双组件设计，以及 `ReplayBuffer` 本地重放缓冲。解决 Docker Compose 中 Worker 与 Backend 独立容器无法通过内存队列通信的断链问题
  - **project_papers UNIQUE 约束与软删除冲突**: 数据模型 §7.1 `project_papers` 表将 `UNIQUE(project_id, paper_id)` 内联约束改为部分唯一索引 `CREATE UNIQUE INDEX idx_pp_unique_active ... WHERE deleted_at IS NULL`，与 `paper_analyses` 的软删除修复保持一致
  - **ReviewState 体积膨胀风险**: 系统架构 §4.2 `ReviewState` 定义后新增 State 体积管理约束表，明确 `candidate_papers`/`paper_analyses`/`full_draft`/`messages` 等大字段在实现时应存储引用 ID 而非完整对象，避免 Checkpointer 序列化/反序列化性能问题
  - **SSE vs WebSocket 不一致**: 系统架构 §1.1 系统上下文图 `HTTPS / WebSocket` 修正为 `HTTPS / SSE`；§二 分层架构表现层和接口层描述统一为 `SSE 实时推送` 和 `REST + SSE`
  - **Celery + asyncio 嵌套事件循环风险**: 系统架构 §10.2 新增嵌套事件循环风险说明和三种应对策略，推荐方案为 Celery 入口 `asyncio.run()` + LangGraph `graph.astream()` 异步 API + Agent Node 定义为 `async def`；任务代码示例从 `graph.stream()` 同步调用改为 `graph.astream()` 异步调用
- `[设计]` 跨文档 P0 级一致性修复（系统架构文档 + 数据模型文档）
  - **PaperMetadata 双定义对齐**: 系统架构 §4.2 的 TypedDict `PaperMetadata` 新增 `doi`/`s2_id`/`arxiv_id`/`open_access` 字段，与数据模型 §4.3 Pydantic 版对齐；增加权威定义声明注释，明确 TypedDict 为 LangGraph State 内部简化视图，完整定义以数据模型文档为准
  - **Project ORM output_type→output_types**: 系统架构 §7.3 ORM 模型的 `output_type = Column(String)` 修正为 `output_types = Column(JSON)`，与数据模型 §3.1 的 JSON 数组定义对齐；同步补齐 `output_language`/`citation_style`/`search_config`/`token_usage`/`token_budget` 字段
  - **ReviewState output_type→output_types**: 系统架构 §4.2 `ReviewState` 中 `output_type: str` 修正为 `output_types: list[str]`；数据模型 §8.1 映射表同步修正
  - **paper_analyses UNIQUE 约束与软删除冲突**: 数据模型 §5.1 将 `UNIQUE(project_id, paper_id)` 内联约束改为部分唯一索引 `CREATE UNIQUE INDEX ... WHERE deleted_at IS NULL`，避免软删除后无法重新分析同一论文
  - **Celery + asyncio 兼容性**: 系统架构 §10.2 新增 Celery 与 asyncio 兼容方案对比表，明确 MVP 采用 `asyncio.run()` 桥接模式（Celery prefork + 任务内 asyncio.run() 驱动异步操作）

### 新增

- `[设计]` P1 级设计补全（四份文档）
  - **REST API 详细设计** (系统架构 §8.3): 新增接口层 REST API 设计，定义 6 组共 14 个 API 端点（项目管理 5 个、工作流控制 4 个、论文管理 4 个、输出导出 3 个、事件流 1 个、系统 2 个），含 `HitlFeedback` 请求体定义和统一错误响应格式
  - **非功能性需求** (需求文档 §七½): 新增性能目标（30 篇论文 ≤8 分钟、检索 ≤10 秒、单篇精读 ≤30 秒）、容量约束（最大并发 3 项目、单项目 200 篇上限、Token 预算 200 万）、可靠性要求（断点恢复、数据源容错、LLM 重试）
  - **论文全文大文本分离** (数据模型 §4.1): 将 `papers.parsed_text` 列移入独立 `paper_fulltext` 表（1:1 关系），避免主表膨胀影响查询性能；MVP 数据表清单同步新增 `paper_fulltext`
  - **CLI HITL 简化策略** (产品UX §9.1): 新增 CLI 模式下 3 个 HITL 节点的简化交互方案对比表（Web vs CLI），定义命令式操作语法（`exclude 3,7`/`add "query"`/`edit`/`revise "指令"`），附 CLI 示例交互
- `[设计]` P2 级质量改进（三份文档）
  - **workflow.yaml 补全 Critic 反馈边** (系统架构 §4.4): 工作流配置 `edges` 新增 `check_critic_feedback` 条件路由（`router: route_after_critique`，`targets: [search, generate_outline]`），带 `enabled: false` 随 critique 节点同步启用
  - **CachedSource hash() 修正** (系统架构 §9.4): 将 `hash(query, filters)`（Python 内置 hash 不支持多参数）修正为 `hashlib.sha256(json.dumps(...)).hexdigest()[:16]`，确保缓存 key 确定性可复现
  - **软删除部分索引优化** (数据模型 §3.1/§5.1/§6.1/§7.1): 四张支持软删除的表（`projects`/`paper_analyses`/`review_outputs`/`project_papers`）的查询索引统一加上 `WHERE deleted_at IS NULL` 条件，避免查询命中已删除记录
  - **移动端适配策略** (产品UX §9.4): 新增响应式设计策略表，定义 6 种场景在桌面端 vs 移动端的差异化呈现方式，明确 MVP 阶段优先桌面端、v0.4 补齐移动端

### 变更

- `[设计]` 系统架构文档 v1.2→v1.3 / 数据模型文档 v1.2→v1.3 / 产品UX文档 v1.0→v1.1：设计审核修复
  - **REST API 统一版本前缀** (系统架构 §8.3): 所有业务 API 路径从 `/api/xxx` 改为 `/api/v1/xxx`，为后续破坏性变更预留版本切换空间；健康检查端点 `/healthz`、`/readyz` 保持不变（基础设施端点不需要版本化）
  - **分页响应格式** (系统架构 §8.3.1): 新增 `PaginatedResponse[T]` 泛型分页响应模型（`items`/`total`/`page`/`size`/`pages`），GET `/api/v1/projects` 和 GET `/api/v1/projects/{id}/papers` 响应类型改为 `PaginatedResponse`
  - **产品UX文档版本更新**: 文档元信息从 v1.0「初稿」更新为 v1.1「迭代修订」，新增「最后更新」字段
- `[设计]` 系统架构文档：外部数据源接入层（第九章）新增 `SourceRegistry` 数据源注册机制
  - 新增 9.2 节 `SourceRegistry` 类设计，支持数据源自注册、启用/禁用、自动发现
  - 新增启动时注册示例（`create_source_registry`）和 Search Agent 调用方式（`multi_source_fetch`）
  - Search Agent 的 `Multi-Source Fetcher` 改为从 Registry 动态获取数据源，不再硬编码
  - 目录结构新增 `sources/registry.py` 和 `sources/__init__.py`
  - 原 9.2→9.3、9.3→9.4 章节号顺延
- `[设计]` 系统架构文档：新增 LLM 多模型路由设计（10.5 节）
  - 新增 `LLMRouter` 类，根据 Agent 名称和任务类型自动路由到最优模型
  - 新增 `ModelConfig` 数据类和 `DEFAULT_MODEL_ROUTING` 路由表（Search 用 mini、Writer 用强模型）
  - 10.4 节 `call_llm` 伪代码改为引用 `LLMRouter.resolve_model()`
  - 新增降级路由规则（gpt-4o → gpt-4o-mini）和配置覆盖方式
  - 能力层描述更新为"LLM 路由"，设计原则"LLM 无关"补充多模型路由引用
  - 目录结构 `services/llm.py` 注释更新
- `[设计]` 系统架构文档：部署架构（第十四章）增加健康检查与优雅关停设计
  - docker-compose.yml 全部服务增加 `healthcheck` 配置（backend/worker/redis）
  - `depends_on` 改为 `condition: service_healthy` 确保启动顺序
  - 新增 14.2 节：`/healthz`（存活）+ `/readyz`（就绪）端点设计及伪代码
  - 新增优雅关停流程（FastAPI 停止接受请求、Worker checkpoint 后退出、Redis 持久化）
  - Worker 增加 `--max-tasks-per-child=100` 防内存泄漏、`stop_grace_period: 60s`
  - 新增 `worker_shutting_down` 信号处理
  - 目录结构新增 `api/routes/health.py`，原 14.2→14.3 章节号顺延
- `[设计]` 系统架构文档：状态管理与持久化（第七章）增加数据库迁移与 Checkpointer 切换设计
  - 7.1 节 Checkpointer 改为配置驱动的工厂函数 `create_checkpointer()`，通过 `CHECKPOINTER_BACKEND` 环境变量切换 `SqliteSaver` / `PostgresSaver`
  - 7.3 节项目级持久化改为 SQLAlchemy ORM 模型定义（`Base` + `Project` 类），不再使用 schema 伪代码
  - 新增 7.4 节「数据库迁移策略」：Alembic 目录结构、`env.py` 配置要点、迁移工作流命令、MVP→PostgreSQL 迁移路径表、方言兼容性约束
  - 目录结构新增 `alembic/` 目录（`alembic.ini`、`env.py`、`versions/`），`models/database.py` 注释更新为"SQLAlchemy 引擎 + Base 声明"
- `[设计]` 系统架构文档：新增 Prompt 模板外置管理设计（10.6 节）
  - 新增 `PromptManager` 类，基于 Jinja2 `FileSystemLoader` 加载和渲染 Markdown 模板
  - 设计 `prompts/` 模板目录结构（按 Agent 分子目录，每个任务类型一个 `.md` 文件）
  - 模板格式示例（Jinja2 变量插值 + JSON 输出约束）
  - 与 `LLMRouter` 集成的调用示例
  - 版本化与切换策略（Git 版本控制、`PROMPTS_DIR` 环境变量、fallback、热更新）
  - 能力层描述更新为"LLM 路由 · Prompt 管理 · 文献检索 · PDF 解析 · 向量检索"
  - 目录结构新增 `services/prompt_manager.py` 和 `prompts/` 目录
- `[设计]` 系统架构文档：Orchestrator 编排引擎（第四章）新增 Agent 注册与工作流配置驱动设计（4.4 节）
  - 新增 `AgentRegistry` 类，支持 Agent Node 函数自注册/按名称查找/列出
  - 新增 Agent 自注册模式（模块导入时自动 `agent_registry.register()`）
  - 新增 `config/workflow.yaml` 工作流配置文件格式（节点启用/禁用、HITL 中断标记、条件路由声明）
  - `orchestrator.py` 改为配置驱动的 `build_review_graph()` 动态构建 DAG
  - MVP 阶段 `analyze` 和 `critique` 节点 `enabled: false`，v0.3 修改配置即可启用
  - 目录结构新增 `agents/registry.py` 和 `config/workflow.yaml`，`orchestrator.py` 注释更新
- `[设计]` 系统架构文档：Agent 间通信协议（第六章）新增 SSE 背压与消息缓冲设计（6.4 节）
  - 新增 `EventBus` 有界缓冲实现（`asyncio.Queue` + 溢出丢弃最旧事件 + 警告日志）
  - 新增消息合并（Debounce）策略表（progress 事件 500ms 合并窗口，error/hitl/complete 立即推送）
  - 新增断线重连与消息重放机制（`Last-Event-ID` + `replay_since`）
  - 新增设计约束参数表（`max_buffer_size`=500, `progress_debounce_ms`=500, `replay_buffer_size`=100）
- `[设计]` 数据模型文档 v1.0→v1.1：与已更新的需求/架构/UX 文档对齐
  - **MVP 输出类型修正**: `methodology_review` 和 `research_roadmap` 从 MVP ✅ 改为 `—`（依赖 Analyst/Critic Agent，v0.3 开放），与需求文档第九章和系统架构 15.1 节保持一致
  - **ExportFormat 枚举**: 新增 `RIS = "ris"` 导出格式，支持 Zotero / Mendeley / EndNote 互操作（需求文档 P0 项）
  - **Project 实体对齐**: `projects` 表新增 `user_id TEXT` 字段及条件索引、`token_usage TEXT` (JSON) 和 `token_budget INTEGER` 成本追踪字段；`ProjectResponse` 同步新增对应字段
  - **引用验证数据模型**: `review_outputs` 表新增 `citation_verification TEXT` (JSON) 字段；新增 §6.3 节定义 JSON 结构（`ref_index`/`paper_id`/`status`/`source`/`verified_at`）及设计说明
  - **全文覆盖率标记**: `paper_analyses` 表新增 `analysis_depth TEXT NOT NULL DEFAULT 'abstract_only'`（`"fulltext"` / `"abstract_only"`）；`PaperAnalysisResponse` 同步新增
  - **ReviewState 映射表更新**: 补全 7 个字段映射（`uploaded_papers`、`citation_verification`、`token_usage`/`token_budget`、`fulltext_coverage`、`feedback_*`），区分双向同步/单向聚合/仅 Checkpointer 三类持久化策略
  - **数据访问层约定**: 新增 §3.4 节声明 SQLAlchemy ORM + Alembic 迁移约定、方言无关性约束、文档 Schema 定位
  - **软删除一致性**: 修订 §1.2 设计原则，明确项目级实体（`projects`/`project_papers`/`paper_analyses`/`review_outputs`）使用 `deleted_at` 软删除，全局共享实体（`papers`）不做软删除；三张表新增 `deleted_at` 字段
  - **PaperSourceType 枚举**: 新增 `CORE` 和 `UNPAYWALL`（标注非 MVP），与需求文档 5.1 节数据源列表对齐
  - **PaperMetadata 对齐**: 新增 `url` 字段，与系统架构 ReviewState 中的 PaperMetadata TypedDict 保持一致
  - **§8.2 非 MVP 标注**: 标题改为"Analyst / Critic Agent 中间数据结构"，增加 MVP 范围说明框
  - **权威定义声明**: 在第三章增加声明，明确本文档为系统数据结构的权威定义
  - 文档元信息更新：版本 v1.0→v1.1、状态"初稿"→"迭代修订"、新增"最后更新"字段
  - 章节号顺延：§6.3→6.4, §6.4→6.5, §6.5→6.6

### 待开发

- 后端项目初始化 (FastAPI + 项目结构搭建)
- Search Agent / Reader Agent / Writer Agent 实现
- Semantic Scholar / arXiv 数据源适配器
- LangGraph 工作流编排
- CLI 界面
- Docker Compose 部署配置

---

## [0.0.1] - 2026-03-30

### 新增

- `[设计]` 需求与功能设计文档 v1.0 (`docs/design/requirements-and-functional-design.md`)
- `[设计]` 产品交付形态与用户体验设计文档 (`docs/design/product-delivery-and-ux.md`)
- `[设计]` 系统架构详细设计文档 (`docs/design/system-architecture.md`)
- `[设计]` 数据模型设计文档 (`docs/design/data-model.md`)
- `[文档]` 项目 AI 编码规范 (`CLAUDE.md`)

### 变更

- `[设计]` 需求文档迭代优化：
  - 新增目标用户角色（本科生、企业研发人员）
  - 明确 Orchestrator 为「LLM 决策 + 确定性编排」混合模式
  - 新增滚雪球检索终止条件（深度 2 层、单次 50 篇、总量 200 篇）
  - 新增全文获取降级策略与用户论文上传功能
  - 新增引用验证机制（防止 LLM 幻觉编造虚假引用）
  - 新增文献工具互操作（BibTeX/RIS 导入导出）
  - 重新设计工作流为含反馈环路的非线性流程
  - 新增成本透明章节（Token 预算预估与实时展示）
  - 新增风险评估与应对章节（5 大风险）
  - 数据源表增加风险备注列与降级策略
  - MVP 输出类型从 5 种缩减为 3 种（Quick Brief + Annotated Bib + Full Review）
  - 新增引用验证与文献互操作为 MVP P0 项
- `[设计]` 产品交付与用户体验文档迭代优化：
  - 新增设计原则：渐进式呈现、容错友好、成本透明
  - 整体布局增加 Token 消耗实时展示至底部状态栏
  - 首页新增输出类型选择、快速开始模板、Onboarding 引导、.bib/.ris 导入入口
  - 对话面板全面增强：论文全文状态标注、相关度评分、成本预估卡片、渐进式精读结果、预估剩余时间
  - 综述编辑器增强：引用验证标识（✅已验证/⚠️待确认）、版本历史、撤销/重做、对比视图、BibTeX/RIS 导出
  - 新增「异常状态与容错体验」章节（数据源异常、空结果、预算超限、中断恢复、反馈环路通知共 5 种状态 UI）
  - 用户场景增强：场景一增加成本预估、全文覆盖率、渐进式精读、引用验证、BibTeX 导出细节
  - 新增场景三（从 .bib 文献库出发）和场景四（中断恢复）
  - 输出交付物表格增加 RIS 导出格式、Full Review 增加引用验证标识说明
  - MVP v0.1 CLI 新增引用验证、Token 消耗展示、全文覆盖率、BibTeX 导入/导出
  - MVP v0.2 Web 新增文件上传（.bib/.ris）、输出类型选择、渐进式精读、引用验证、中断恢复、异常状态提示
  - 完整版新增版本历史、撤销/重做、对比视图、Onboarding 模板
- `[文档]` CLAUDE.md 新增变更日志更新规则、MVP 输出类型同步修正
- `[文档]` 新增 CHANGELOG.md 文件 (`docs/dev/CHANGELOG.md`)
