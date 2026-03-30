# CLAUDE.md

本文件为 AI 编程助手提供项目上下文和编码规范，确保生成的代码与项目架构保持一致。

## 项目概述

**多智能体文献综述应用 (Agentic Literature Review)** — 面向科研人员的 AI 驱动文献综述助手。用户输入研究问题，系统通过多个专业智能体协作，自动完成文献检索、精读、分析、评审、写作全流程，交付可直接使用的学术综述。

## 设计文档

所有设计文档位于 `docs/design/`：

- `requirements-and-functional-design.md` — 需求与功能设计（用户画像、Agent 定义、功能模块、数据源、技术栈）
- `product-delivery-and-ux.md` — 产品交付形态与用户体验（部署模式、UI 设计、使用流程）
- `system-architecture.md` — 系统架构详细设计（分层架构、Agent 通信、状态管理、错误恢复、部署）
- `data-model.md` — 数据模型设计（实体关系、数据库 Schema、枚举类型、输出类型定义）

实现前请先阅读相关设计文档以了解上下文。

## 技术栈

| 层次       | 技术                      |
| ---------- | ------------------------- |
| 智能体框架 | LangGraph                 |
| LLM        | OpenAI GPT-4o（可配置）   |
| 后端       | Python 3.12 + FastAPI     |
| 前端       | React + Ant Design        |
| 任务队列   | Celery + Redis            |
| 数据库     | SQLite（MVP）/ PostgreSQL |
| 向量数据库 | Chroma（MVP）/ Milvus     |
| 缓存       | Redis                     |
| PDF 解析   | PyMuPDF / GROBID          |
| 部署       | Docker Compose            |

## 项目结构

```
agentic-literature-review/
├── docs/design/                    # 设计文档
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI 入口
│   │   ├── config.py               # 配置管理
│   │   ├── api/routes/             # API 路由（projects, workflow, events）
│   │   ├── agents/                 # 智能体实现
│   │   │   ├── orchestrator.py     # LangGraph 工作流定义
│   │   │   ├── state.py            # ReviewState 状态定义
│   │   │   ├── search_agent.py
│   │   │   ├── reader_agent.py
│   │   │   ├── analyst_agent.py
│   │   │   ├── critic_agent.py
│   │   │   └── writer_agent.py
│   │   ├── sources/                # 外部数据源适配器
│   │   │   ├── base.py             # PaperSource 抽象接口
│   │   │   ├── semantic_scholar.py
│   │   │   └── arxiv.py
│   │   ├── parsers/                # PDF 解析、引用格式化
│   │   ├── models/                 # 数据库模型
│   │   ├── services/               # LLM、Embedding、导出等服务
│   │   └── tasks.py                # Celery 任务
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                       # React 前端（MVP v0.2）
├── docker-compose.yml
├── .env.example
└── CLAUDE.md
```

## 核心架构概念

### Agent 架构

系统采用 LangGraph StateGraph 编排 6 个专业 Agent：

1. **Search Agent** — 多源文献检索、查询扩展、去重
2. **Reader Agent** — PDF 精读、结构化信息提取
3. **Analyst Agent** — 主题聚类、方法对比、趋势分析
4. **Critic Agent** — 质量评估、矛盾检测、Research Gap 发现
5. **Writer Agent** — 综述生成、多格式导出
6. **Update Agent** — 新文献监控、增量更新

MVP 阶段只实现 Search + Reader + Writer。

### 共享状态模型

所有 Agent 通过读写 `ReviewState`（TypedDict）通信。每个 Agent 是一个 LangGraph Node，接收完整状态，返回需要更新的字段子集。

### Human-in-the-loop

工作流在 3 个关键节点使用 LangGraph `interrupt` 暂停等待用户确认：
1. 检索后确认论文列表
2. 综述大纲审阅
3. 初稿审阅

### 断点恢复

使用 LangGraph `SqliteSaver` Checkpointer，每个 Node 执行后自动持久化状态，支持从断点恢复。

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
def agent_node(state: ReviewState) -> dict:
    """从 state 读取输入 → 执行逻辑 → 返回需更新的字段"""
    ...
```

- Agent 内部组件拆分为独立函数/类，便于单元测试
- LLM 调用通过 `services/llm.py` 抽象层，不直接调用 OpenAI SDK
- 每个 Agent 文件内包含对应的 prompt 模板

### 外部数据源

所有数据源实现 `PaperSource` 抽象接口（`sources/base.py`），统一返回 `PaperMetadata` 格式。添加新数据源只需实现该接口。

### 测试

- 单元测试：`pytest`，每个 Agent 和数据源适配器都有对应测试
- LLM 调用测试：使用 mock 或录制响应，不在 CI 中实际调用 LLM
- 集成测试：完整工作流端到端测试

## MVP 范围

当前处于 MVP v0.1 阶段：

| 包含                                      | 不包含                          |
| ----------------------------------------- | ------------------------------- |
| Search + Reader + Writer Agent            | Analyst / Critic / Update Agent |
| Semantic Scholar + arXiv                  | OpenAlex / PubMed 等            |
| CLI 界面                                  | Web 前端                        |
| SQLite + Chroma + Redis                   | PostgreSQL / Neo4j              |
| Docker Compose 单机                       | K8s 部署                        |
| Quick Brief + Annotated Bib + Full Review | 知识图谱 / 时间线可视化         |

## 常用命令

```bash
# 启动开发环境
docker compose up -d

# 后端开发（本地）
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 运行测试
cd backend
pytest

# Celery Worker
celery -A app.tasks worker -l info

# 前端开发（v0.2 后）
cd frontend
npm install
npm run dev
```

## 环境变量

```bash
# .env.example
OPENAI_API_KEY=sk-...                    # 必需
OPENAI_MODEL=gpt-4o                     # 默认 gpt-4o
DATABASE_URL=sqlite:///data/app.db       # MVP 用 SQLite
CHROMA_PATH=/data/chroma                 # 向量数据库路径
REDIS_URL=redis://localhost:6379/0       # Redis 连接
S2_API_KEY=                              # Semantic Scholar API Key（可选，提高速率限制）
LOG_LEVEL=INFO
```

## 变更日志

`docs/dev/CHANGELOG.md` 记录所有重要变更。**每次对项目进行实质性修改后，必须同步更新 `docs/dev/CHANGELOG.md`**，包括但不限于：

- 设计文档的新增或修改
- 代码功能的新增、变更或修复
- 依赖项或配置的变更
- 基础设施 / 部署相关变更

格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 规范，使用 `新增` / `变更` / `修复` / `移除` 等分类，并标注模块标签（`[设计]` `[后端]` `[前端]` `[基础设施]` `[文档]`）。
