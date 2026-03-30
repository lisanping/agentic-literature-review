# Agentic Literature Review

AI 驱动的多智能体文献综述助手。输入研究问题，系统通过多个专业智能体协作，自动完成文献检索、精读、分析、写作全流程，交付可直接使用的学术综述。

## 功能特性

- **多源文献检索**: Semantic Scholar + arXiv 并行检索，自动查询扩展与去重
- **智能精读**: PDF 下载 + LLM 结构化信息提取（目标、方法、发现、局限）
- **主题聚类分析**: Embedding 聚类 + LLM 语义解读，生成主题聚类、方法对比矩阵、研究趋势
- **质量评估与空白识别**: LLM 质量评分 + 矛盾检测 + 研究空白发现 + 局限性汇总
- **自动写作**: 大纲生成 → 逐章写作 → 引用格式化（APA/IEEE/GB/T 7714）
- **引用验证**: 每条引用回溯验证存在性，标注 ✅ verified / ⚠️ unconfirmed
- **多种输出类型**: 完整综述 / 方法论综述 / 研究空白报告 / 趋势报告 / 研究路线图
- **Human-in-the-loop**: 3 个关键节点等待用户确认（论文列表、大纲、初稿）
- **断点恢复**: LangGraph Checkpointer 自动持久化，随时可从断点继续
- **多格式导出**: Markdown / Word / BibTeX / RIS
- **前端可视化**: 聚类视图、对比矩阵表格、趋势图、研究空白列表、质量评分标识

## 系统架构

```
┌──────────────────────────────────────────────────────────┐
│                      FastAPI + SSE                       │
├──────────────────────────────────────────────────────────┤
│                   Celery Worker (async)                   │
├──────────────────────────────────────────────────────────┤
│  LangGraph StateGraph (15 nodes)                          │
│  ┌──────┐  ┌──────┐  ┌──────┐  ┌───────┐  ┌──────┐       │
│  │Search│→ │ Read │→ │Analyst│→ │Critic │→ │Writer│→Export│
│  │Agent │  │Agent │  │Agent  │  │Agent  │  │Agent │       │
│  └──────┘  └──────┘  └───┬───┘  └───┬───┘  └──────┘       │
│                          │ 聚类/    │ 质量/                │
│                          │ 对比/    │ 空白/                │
│                          │ 趋势     │ 反馈环路             │
├──────────────────────────────────────────────────────────┤
│  SQLite │ ChromaDB │ Redis │ LangGraph Checkpointer      │
└──────────────────────────────────────────────────────────┘
```

## 快速开始

### 前置条件

- Docker + Docker Compose
- OpenAI API Key

### Docker 部署（推荐）

```bash
# 1. 克隆项目
git clone <repo-url>
cd agentic-literature-review

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填入 OPENAI_API_KEY

# 3. 一键启动
docker compose up -d

# 4. 验证服务
curl http://localhost:8000/healthz
# {"status": "ok"}

curl http://localhost:8000/readyz
# {"status": "ready", "checks": {"database": "ok", "redis": "ok"}}
```

服务启动后：
- **API 文档**: http://localhost:8000/docs (Swagger UI)
- **ReDoc**: http://localhost:8000/redoc

### 本地开发

```bash
# 1. 启动 Redis
docker run -d --name redis -p 6379:6379 redis:7-alpine

# 2. 安装依赖
cd backend
pip install -r requirements.txt

# 3. 启动 API 服务
uvicorn app.main:app --reload --port 8000

# 4. 启动 Celery Worker（新终端）
celery -A app.celery_app:celery_app worker -l info -Q high,default,low

# 5. 运行测试
pytest
```

### CLI 使用

```bash
cd backend

# 运行文献综述
python -m app.cli review "What are the recent advances in LLM for code generation?"

# 指定语言和引用格式
python -m app.cli review "深度学习在医学影像中的应用" -l zh -s gbt7714

# 设置 token 预算
python -m app.cli review "few-shot learning" -b 50000
```

## API 端点

| 方法     | 路径                                         | 说明          |
| -------- | -------------------------------------------- | ------------- |
| `POST`   | `/api/v1/projects`                           | 创建项目      |
| `GET`    | `/api/v1/projects`                           | 列表（分页）  |
| `GET`    | `/api/v1/projects/{id}`                      | 项目详情      |
| `PATCH`  | `/api/v1/projects/{id}`                      | 更新配置      |
| `DELETE` | `/api/v1/projects/{id}`                      | 软删除        |
| `POST`   | `/api/v1/projects/{id}/workflow/start`       | 启动工作流    |
| `POST`   | `/api/v1/projects/{id}/workflow/resume`      | HITL 反馈恢复 |
| `GET`    | `/api/v1/projects/{id}/workflow/status`      | 工作流状态    |
| `POST`   | `/api/v1/projects/{id}/workflow/cancel`      | 取消工作流    |
| `GET`    | `/api/v1/projects/{id}/papers`               | 论文列表      |
| `PATCH`  | `/api/v1/projects/{id}/papers/{pid}`         | 更新论文状态  |
| `GET`    | `/api/v1/papers/{id}`                        | 论文详情      |
| `POST`   | `/api/v1/projects/{id}/papers/upload`        | 上传论文      |
| `GET`    | `/api/v1/projects/{id}/outputs`              | 输出列表      |
| `GET`    | `/api/v1/projects/{id}/outputs/{oid}`        | 输出详情      |
| `POST`   | `/api/v1/projects/{id}/outputs/{oid}/export` | 导出          |
| `GET`    | `/api/v1/projects/{id}/events`               | SSE 事件流    |

## 环境变量

| 变量                   | 必需 | 说明                     | 默认值                            |
| ---------------------- | ---- | ------------------------ | --------------------------------- |
| `OPENAI_API_KEY`       | ✅    | OpenAI API 密钥          | —                                 |
| `OPENAI_MODEL`         |      | LLM 模型                 | `gpt-4o`                          |
| `DATABASE_URL`         |      | 数据库连接               | `sqlite+aiosqlite:///data/app.db` |
| `REDIS_URL`            |      | Redis 连接               | `redis://localhost:6379/0`        |
| `S2_API_KEY`           |      | Semantic Scholar API Key | —                                 |
| `CHECKPOINTER_BACKEND` |      | 检查点后端               | `sqlite`                          |
| `CHECKPOINT_DB_URL`    |      | 检查点数据库             | `sqlite:///data/checkpoints.db`   |
| `LOG_LEVEL`            |      | 日志级别                 | `INFO`                            |

## 项目结构

```
agentic-literature-review/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 入口
│   │   ├── config.py            # 配置管理
│   │   ├── cli.py               # CLI 客户端
│   │   ├── celery_app.py        # Celery 配置
│   │   ├── tasks.py             # Celery 任务
│   │   ├── api/routes/          # REST API 路由
│   │   ├── agents/              # LangGraph 智能体
│   │   │   ├── orchestrator.py  # 工作流编排 (15 节点)
│   │   │   ├── state.py         # ReviewState
│   │   │   ├── routing.py       # 条件路由
│   │   │   ├── search_agent.py  # 检索智能体
│   │   │   ├── reader_agent.py  # 精读智能体
│   │   │   ├── analyst_agent.py # 分析智能体 (v0.3)
│   │   │   ├── critic_agent.py  # 评审智能体 (v0.3)
│   │   │   └── writer_agent.py  # 写作智能体
│   │   ├── sources/             # 数据源适配器
│   │   ├── services/            # LLM / 导出 / 事件等服务
│   │   └── models/              # ORM 模型
│   ├── config/workflow.yaml     # 工作流 DAG 配置
│   ├── tests/                   # 测试
│   ├── Dockerfile
│   └── requirements.txt
├── docker-compose.yml
├── .env.example
└── README.md
```

## 技术栈

| 层次       | 技术                  |
| ---------- | --------------------- |
| 智能体框架 | LangGraph             |
| LLM        | OpenAI GPT-4o         |
| 后端       | Python 3.12 + FastAPI |
| 任务队列   | Celery + Redis        |
| 数据库     | SQLite (MVP)          |
| 向量数据库 | ChromaDB              |
| 部署       | Docker Compose        |

## 许可证

MIT
