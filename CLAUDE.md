# CLAUDE.md

本文件为 AI 编程助手提供项目上下文和编码规范，确保生成的代码与项目架构保持一致。

## 项目概述

**多智能体文献综述应用 (Agentic Literature Review)** — 面向科研人员的 AI 驱动文献综述助手。用户输入研究问题，系统通过多个专业智能体协作，自动完成文献检索、精读、分析、评审、写作全流程，交付可直接使用的学术综述。

当前版本 **v0.5**，全部 7 个 Agent、4 个数据源、Web 前端（含认证/分享/可视化）均已实现。

## 设计文档

所有设计文档位于 `docs/design/`：

- `requirements-and-functional-design.md` — 需求与功能设计（用户画像、Agent 定义、功能模块、数据源、技术栈）
- `product-delivery-and-ux.md` — 产品交付形态与用户体验（部署模式、UI 设计、使用流程）
- `system-architecture.md` — 系统架构详细设计（分层架构、Agent 通信、状态管理、错误恢复、部署）
- `data-model.md` — 数据模型设计（实体关系、数据库 Schema、枚举类型、输出类型定义）

实现前请先阅读相关设计文档以了解上下文。

## 技术栈

| 层次       | 技术                                  |
| ---------- | ------------------------------------- |
| 智能体框架 | LangGraph                             |
| LLM        | OpenAI GPT-4o（可配置，支持路由降级） |
| 后端       | Python 3.12 + FastAPI                 |
| 前端       | React 18 + Ant Design 5 + D3.js       |
| 任务队列   | Celery + Redis                        |
| 数据库     | SQLite（MVP）/ PostgreSQL             |
| 向量数据库 | ChromaDB                              |
| 认证       | JWT (HS256) + bcrypt + RBAC           |
| 缓存       | Redis                                 |
| PDF 解析   | PyMuPDF                               |
| 部署       | Docker Compose                        |

## 项目结构

```
agentic-literature-review/
├── docs/
│   ├── design/                         # 设计文档
│   ├── QUICKSTART.md                   # 快速开始指南
│   └── dev/                            # 开发文档与实施计划
├── backend/
│   ├── app/
│   │   ├── main.py                     # FastAPI 入口
│   │   ├── config.py                   # 配置管理（23 项配置）
│   │   ├── cli.py                      # CLI 客户端
│   │   ├── celery_app.py               # Celery 配置
│   │   ├── tasks.py                    # Celery 任务
│   │   ├── api/
│   │   │   ├── deps.py                 # 依赖注入（认证、权限）
│   │   │   ├── exceptions.py           # 统一错误处理
│   │   │   └── routes/                 # API 路由（11 个路由模块）
│   │   │       ├── auth.py             # 认证（注册/登录/刷新/登出）
│   │   │       ├── projects.py         # 项目 CRUD
│   │   │       ├── workflow.py         # 工作流控制
│   │   │       ├── papers.py           # 论文管理
│   │   │       ├── outputs.py          # 输出与导出
│   │   │       ├── events.py           # SSE 事件流
│   │   │       ├── shares.py           # 项目分享
│   │   │       ├── users.py            # 用户管理
│   │   │       ├── visualizations.py   # 可视化数据
│   │   │       ├── updates.py          # 增量更新
│   │   │       └── health.py           # 健康检查
│   │   ├── agents/                     # 智能体实现
│   │   │   ├── orchestrator.py         # LangGraph 工作流编排（配置驱动）
│   │   │   ├── state.py                # ReviewState 状态定义
│   │   │   ├── registry.py             # Agent 注册中心
│   │   │   ├── routing.py              # 条件路由函数
│   │   │   ├── checkpointer.py         # LangGraph Checkpointer 工厂
│   │   │   ├── intent_parser.py        # 意图解析
│   │   │   ├── search_agent.py         # 检索智能体
│   │   │   ├── reader_agent.py         # 精读智能体
│   │   │   ├── analyst_agent.py        # 分析智能体
│   │   │   ├── critic_agent.py         # 评审智能体
│   │   │   ├── writer_agent.py         # 写作智能体
│   │   │   ├── update_agent.py         # 增量更新智能体
│   │   │   ├── verify_citations.py     # 引用验证
│   │   │   └── export_node.py          # 导出节点
│   │   ├── sources/                    # 外部数据源适配器
│   │   │   ├── base.py                 # PaperSource 抽象接口
│   │   │   ├── registry.py             # 数据源注册中心
│   │   │   ├── semantic_scholar.py     # Semantic Scholar
│   │   │   ├── arxiv.py                # arXiv
│   │   │   ├── openalex.py             # OpenAlex
│   │   │   ├── pubmed.py               # PubMed
│   │   │   ├── cache.py                # Redis 缓存装饰器
│   │   │   └── rate_limiter.py         # 异步令牌桶限速器
│   │   ├── parsers/                    # PDF 解析、引用格式化
│   │   ├── models/                     # ORM 模型（11 个）
│   │   │   ├── project.py              # 项目
│   │   │   ├── paper.py                # 论文 + 全文
│   │   │   ├── paper_analysis.py       # 论文分析
│   │   │   ├── project_paper.py        # 项目-论文关联
│   │   │   ├── review_output.py        # 综述输出
│   │   │   ├── user.py                 # 用户
│   │   │   ├── refresh_token.py        # 刷新令牌
│   │   │   ├── project_share.py        # 项目分享
│   │   │   └── audit_log.py            # 审计日志
│   │   ├── schemas/                    # Pydantic v2 请求/响应 Schema
│   │   └── services/                   # LLM、Embedding、导出、认证等服务
│   ├── config/workflow.yaml            # 工作流 DAG 配置
│   ├── prompts/                        # Jinja2 Prompt 模板
│   │   ├── search/                     # 检索 Prompt
│   │   ├── reader/                     # 精读 Prompt
│   │   ├── analyst/                    # 分析 Prompt（4 个）
│   │   ├── critic/                     # 评审 Prompt（4 个）
│   │   ├── writer/                     # 写作 Prompt（6 个）
│   │   └── update/                     # 更新 Prompt（2 个）
│   ├── alembic/                        # 数据库迁移（3 个版本）
│   ├── tests/                          # 测试
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                           # React 前端
│   ├── src/
│   │   ├── api/                        # API 客户端（10 个模块）
│   │   ├── components/                 # 组件
│   │   │   ├── Analysis/               # 分析结果展示
│   │   │   ├── Chat/                   # 对话流
│   │   │   ├── Common/                 # 通用组件
│   │   │   ├── Layout/                 # 布局（含 UserMenu）
│   │   │   ├── Paper/                  # 论文卡片/列表
│   │   │   ├── Project/                # 项目管理（含 ShareDialog）
│   │   │   ├── Review/                 # 综述预览与导出
│   │   │   ├── Visualization/          # D3.js 知识图谱/时间线
│   │   │   └── Workflow/               # 工作流交互
│   │   ├── hooks/                      # React Hooks
│   │   ├── pages/                      # 页面（Home/Login/Project/Settings/404）
│   │   ├── stores/                     # Zustand 状态管理（5 个 Store）
│   │   ├── types/                      # TypeScript 类型定义
│   │   └── utils/                      # 工具函数
│   ├── Dockerfile                      # 多阶段构建 + Nginx
│   └── nginx.conf                      # SPA + API 反代 + SSE 代理
├── docker-compose.yml
├── .env.example
└── CLAUDE.md
```

## 核心架构概念

### Agent 架构

系统采用 LangGraph StateGraph 编排 7 个专业 Agent（14 个工作流节点）：

1. **Intent Parser** — 解析用户输入，提取研究问题、关键词、时间范围
2. **Search Agent** — 多源文献检索（4 个数据源）、查询扩展、去重
3. **Reader Agent** — PDF 精读、结构化信息提取（5 路并发）
4. **Analyst Agent** — 主题聚类、方法对比矩阵、引文网络、趋势分析
5. **Critic Agent** — 质量评估、矛盾检测、Research Gap 发现、反馈环路
6. **Writer Agent** — 大纲生成、逐章写作、引用格式化、专用输出类型路由
7. **Update Agent** — 增量检索、差异对比、相关性评估、更新报告

工作流由 `config/workflow.yaml` 配置驱动，支持启用/禁用节点、条件路由和反馈环路。

### 共享状态模型

所有 Agent 通过读写 `ReviewState`（TypedDict，25+ 字段）通信。每个 Agent 是一个 LangGraph Node，接收完整状态，返回需要更新的字段子集。

### Human-in-the-loop

工作流在 3 个关键节点使用 LangGraph `interrupt` 暂停等待用户确认：
1. 检索后确认论文列表
2. 综述大纲审阅
3. 初稿审阅

### 断点恢复

使用 LangGraph `SqliteSaver` Checkpointer，每个 Node 执行后自动持久化状态，支持从断点恢复。

### 认证与权限

- JWT 认证：access_token (1h) + refresh_token 旋转 (7d)，bcrypt 密码存储
- RBAC：admin/user 两级角色 + 项目级 owner/collaborator/viewer 权限
- 向后兼容：`AUTH_REQUIRED=false` 时不强制认证

## 编码规范

### Python 后端

- Python 3.12+，使用 type hints
- 异步优先：外部 API 调用和 I/O 操作使用 `async/await`
- FastAPI 路由使用 Pydantic v2 模型校验输入输出
- 结构化日志使用 `structlog`
- 错误处理：外部 API 调用使用 `tenacity` 重试（指数退避，最多 3 次）
- 配置管理：环境变量 + `.env` 文件，通过 Pydantic Settings 加载
- API Key 等敏感信息只通过环境变量传递，不硬编码

### Agent 实现

每个 Agent 遵循统一的 Node 函数签名：

```python
async def agent_node(state: ReviewState) -> dict:
    """从 state 读取输入 → 执行逻辑 → 返回需更新的字段"""
    ...
```

- Agent 内部组件拆分为独立函数/类，便于单元测试
- LLM 调用通过 `services/llm.py` 抽象层，不直接调用 OpenAI SDK
- Prompt 模板外置到 `prompts/` 目录，通过 `services/prompt_manager.py`（Jinja2）加载
- 所有 Agent 通过 `agents/registry.py` 自注册

### 外部数据源

所有数据源实现 `PaperSource` 抽象接口（`sources/base.py`），统一返回 `PaperMetadata` 格式。添加新数据源只需实现该接口并在 `sources/__init__.py` 注册。

当前已实现 4 个数据源：Semantic Scholar、arXiv、OpenAlex、PubMed。

### 测试

- 单元测试：`pytest`，每个 Agent 和数据源适配器都有对应测试
- LLM 调用测试：使用 mock 或录制响应，不在 CI 中实际调用 LLM
- 集成测试：完整工作流端到端测试
- Live 测试：`@pytest.mark.live` 标记，仅手动运行

## 当前版本范围 (v0.5)

| 已实现                                                                        | 未实现 / 计划中                   |
| ----------------------------------------------------------------------------- | --------------------------------- |
| 全部 7 个 Agent（Search/Reader/Analyst/Critic/Writer/Update + Intent Parser） | 计划任务调度（Celery Beat, v0.6） |
| 4 个数据源（S2 + arXiv + OpenAlex + PubMed）                                  | 更多数据源（Crossref / DBLP 等）  |
| Web 前端（认证/分享/D3 可视化/综述预览/导出）                                 | OAuth / SSO 登录                  |
| CLI + REST API + SSE 实时推送                                                 | PostgreSQL 生产部署               |
| JWT 认证 + RBAC 权限 + 项目分享                                               | 邮件通知                          |
| 5 种输出类型 + 4 种导出格式                                                   | K8s 部署                          |
| SQLite + ChromaDB + Redis                                                     |                                   |
| Docker Compose 单机部署                                                       |                                   |

## 常用命令

```bash
# 启动开发环境
docker compose up -d

# 后端开发（本地）
cd backend
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# Celery Worker
celery -A app.celery_app:celery_app worker -l info -Q high,default,low

# 运行测试
cd backend
pytest
pytest -m "not live"    # 跳过真实 LLM 测试

# 前端开发
cd frontend
npm install
npm run dev
```

## 环境变量

```bash
# .env.example
OPENAI_API_KEY=sk-...                    # 必需
OPENAI_MODEL=gpt-4o                     # 默认 gpt-4o
DATABASE_URL=sqlite+aiosqlite:///data/app.db  # 数据库连接
CHROMA_PATH=/data/chroma                 # 向量数据库路径
REDIS_URL=redis://localhost:6379/0       # Redis 连接

# ── 数据源 API Key（均为可选）──
S2_API_KEY=                              # Semantic Scholar（提高速率限制）
OPENALEX_EMAIL=                          # OpenAlex polite pool（提升至 10 req/s）
NCBI_API_KEY=                            # PubMed NCBI（提升至 10 req/s）

# ── LangGraph ──
CHECKPOINTER_BACKEND=sqlite             # 检查点后端
CHECKPOINT_DB_URL=sqlite:///data/checkpoints.db

# ── 认证（AUTH_REQUIRED=false 时可忽略）──
AUTH_REQUIRED=false                      # 是否强制认证
JWT_SECRET_KEY=change-me-in-production   # JWT 签名密钥
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60       # Access Token 有效期
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7          # Refresh Token 有效期
FIRST_ADMIN_EMAIL=                       # 首次启动自动创建管理员
FIRST_ADMIN_PASSWORD=

# ── 其他 ──
PROMPTS_DIR=prompts                      # Prompt 模板目录
LOG_LEVEL=INFO
```

## 变更日志

`docs/dev/CHANGELOG.md` 记录所有重要变更。**每次对项目进行实质性修改后，必须同步更新 `docs/dev/CHANGELOG.md`**，包括但不限于：

- 设计文档的新增或修改
- 代码功能的新增、变更或修复
- 依赖项或配置的变更
- 基础设施 / 部署相关变更

格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 规范，使用 `新增` / `变更` / `修复` / `移除` 等分类，并标注模块标签（`[设计]` `[后端]` `[前端]` `[基础设施]` `[文档]`）。
