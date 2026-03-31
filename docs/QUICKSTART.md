# 快速开始指南

本指南帮助你从零开始部署并使用 **Agentic Literature Review** — AI 多智能体文献综述助手。

---

## 目录

- [前置条件](#前置条件)
- [方式一：Docker Compose 部署（推荐）](#方式一docker-compose-部署推荐)
- [方式二：本地开发环境](#方式二本地开发环境)
- [使用方式](#使用方式)
  - [Web 界面](#web-界面)
  - [CLI 命令行](#cli-命令行)
  - [REST API](#rest-api)
- [工作流详解](#工作流详解)
- [配置说明](#配置说明)
- [常见问题](#常见问题)

---

## 前置条件

| 依赖                    | 版本要求               | 说明                    |
| ----------------------- | ---------------------- | ----------------------- |
| Docker + Docker Compose | Docker 24+, Compose v2 | Docker 部署方式必需     |
| Python                  | 3.12+                  | 本地开发方式必需        |
| Node.js                 | 20+                    | 本地前端开发必需        |
| OpenAI API Key          | —                      | **必需**，用于 LLM 调用 |

> **可选 API Key**（提升数据源请求频率）：
> - `S2_API_KEY`：Semantic Scholar，无 Key 100 次/5 分钟，有 Key 可提升
> - `OPENALEX_EMAIL`：OpenAlex polite pool，提升至 10 req/s
> - `NCBI_API_KEY`：PubMed NCBI，提升至 10 req/s

---

## 方式一：Docker Compose 部署（推荐）

最简单的部署方式，一键启动所有服务。

### 1. 克隆项目

```bash
git clone <repo-url>
cd agentic-literature-review
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入你的 OpenAI API Key：

```bash
# .env
OPENAI_API_KEY=sk-your-key-here        # 必需!
OPENAI_MODEL=gpt-4o                    # 可选，默认 gpt-4o
S2_API_KEY=                            # 可选，Semantic Scholar API Key
OPENALEX_EMAIL=                        # 可选，OpenAlex polite pool
NCBI_API_KEY=                          # 可选，PubMed NCBI API Key
AUTH_REQUIRED=false                    # 是否强制认证
LOG_LEVEL=INFO                         # 可选，日志级别
```

### 3. 启动服务

```bash
docker compose up -d
```

这会启动 4 个服务：

| 服务         | 端口   | 说明                |
| ------------ | ------ | ------------------- |
| **frontend** | `3000` | Web 界面 (Nginx)    |
| **backend**  | `8000` | FastAPI 后端 API    |
| **worker**   | —      | Celery 异步任务处理 |
| **redis**    | `6379` | 消息队列 + 缓存     |

### 4. 验证服务状态

```bash
# 查看服务状态
docker compose ps

# 健康检查
curl http://localhost:8000/healthz
# 返回: {"status": "ok"}

curl http://localhost:8000/readyz
# 返回: {"status": "ready", "checks": {"database": "ok", "redis": "ok"}}
```

### 5. 开始使用

- **Web 界面**: 打开浏览器访问 http://localhost:3000
- **API 文档**: http://localhost:8000/docs (Swagger UI)
- **ReDoc 文档**: http://localhost:8000/redoc

### 停止与清理

```bash
# 停止所有服务
docker compose down

# 停止并删除数据卷（会清空数据库和向量库）
docker compose down -v
```

---

## 方式二：本地开发环境

适合需要修改代码或调试的开发者。

### 1. 启动 Redis

Redis 用于 Celery 任务队列和 SSE 事件发布，是必需的基础服务：

```bash
docker run -d --name redis -p 6379:6379 redis:7-alpine
```

### 2. 配置环境变量

```bash
cd backend
cp ../.env.example .env
# 编辑 .env，填入 OPENAI_API_KEY
```

### 3. 安装后端依赖

```bash
cd backend
pip install -r requirements.txt
```

### 4. 初始化数据库

```bash
cd backend
alembic upgrade head
```

### 5. 启动后端 API

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

### 6. 启动 Celery Worker（新终端）

```bash
cd backend
celery -A app.celery_app:celery_app worker -l info -Q high,default,low
```

### 7. （可选）启动前端开发服务

```bash
cd frontend
npm install
npm run dev
# 访问 http://localhost:5173（开发模式自动代理 API 请求到 :8000）
```

### 运行测试

```bash
cd backend

# 运行所有单元/集成测试
pytest

# 跳过需要真实 LLM 调用的测试
pytest -m "not live"

# 运行特定测试文件
pytest tests/test_search_agent.py -v
```

---

## 使用方式

### Web 界面

1. 打开浏览器访问前端地址（Docker: `http://localhost:3000`，本地开发: `http://localhost:5173`）
2. 如启用认证（`AUTH_REQUIRED=true`），先注册账号并登录
3. 在首页输入研究问题，例如：*"What are recent advances in LLM for code generation?"*
4. 选择输出类型（完整综述 / 方法论综述 / 研究空白报告 / 趋势报告 / 研究路线图）
5. 点击开始，系统将自动执行文献综述工作流
6. 在 3 个关键节点会暂停等待你确认：
   - **论文列表确认**：审阅检索到的论文，可排除不相关的或追加检索
   - **大纲审阅**：确认综述结构是否合理
   - **初稿审阅**：审阅完整初稿，可要求修改
7. 完成后可导出为 Markdown / Word / BibTeX / RIS 格式
8. 可通过项目分享功能将项目共享给其他用户（owner/collaborator/viewer 权限）
9. 可通过「检查更新」按钮触发增量更新，检索最新文献并生成更新报告
10. 可在「图谱」Tab 中查看 D3.js 知识图谱、时间线和趋势可视化

### CLI 命令行

无需前端，直接在终端交互式完成文献综述：

```bash
cd backend

# 基本用法
python -m app.cli review "What are recent advances in LLM for code generation?"

# 指定中文输出 + GB/T 7714 引用格式
python -m app.cli review "深度学习在医学影像中的应用" -l zh -s gbt7714

# 指定英文输出 + IEEE 引用格式
python -m app.cli review "transformer architecture survey" -l en -s ieee

# 设置 token 预算上限
python -m app.cli review "few-shot learning" -b 50000
```

**CLI 参数说明：**

| 参数            | 缩写 | 选项                       | 默认值        | 说明           |
| --------------- | ---- | -------------------------- | ------------- | -------------- |
| `--language`    | `-l` | `zh` / `en` / `bilingual`  | `zh`          | 输出语言       |
| `--style`       | `-s` | `apa` / `ieee` / `gbt7714` | `apa`         | 引用格式       |
| `--output-type` | `-t` | `full_review` 等           | `full_review` | 输出类型       |
| `--budget`      | `-b` | 整数                       | 无限制        | Token 预算上限 |

CLI 运行过程中会在 3 个节点暂停等待输入：

```
Found 25 candidate papers:
  [1] (2024) Large Language Models for Code: A Survey...  [cited: 342]
  [2] (2023) Code Generation with LLMs...               [cited: 128]
  ...

Select papers (all / exclude 3,7 / add "query"): all

--- Phase 2: Reading 25 papers ---
Generated outline:
  1. Introduction — ...
  2. Methodology — ...

Approve outline? (yes / retry "instruction"): yes

--- Phase 3: Writing + Citation Verification ---
Generated draft (15234 chars)
  Citations: 22/25 verified ✅, 3 unconfirmed ⚠️

Approve draft? (yes / revise "instruction"): yes

--- Phase 4: Export ---
✅ Review saved to review_output.md
✅ References saved to references.bib
```

### REST API

通过 API 编程式调用：

```bash
# 0. 注册用户（AUTH_REQUIRED=true 时）
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "your-password"}'

# 0b. 登录获取 Token
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "your-password"}'
# 返回: {"access_token": "eyJ...", "refresh_token": "..."}

# 1. 创建项目（AUTH_REQUIRED=false 时无需 Authorization 头）
curl -X POST http://localhost:8000/api/v1/projects \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access_token>" \
  -d '{"query": "LLM for code generation", "output_types": ["full_review"]}'

# 2. 启动工作流
curl -X POST http://localhost:8000/api/v1/projects/{project_id}/workflow/start \
  -H "Authorization: Bearer <access_token>"

# 3. 查询工作流状态
curl http://localhost:8000/api/v1/projects/{project_id}/workflow/status \
  -H "Authorization: Bearer <access_token>"

# 4. 订阅实时事件流 (SSE)
curl -N http://localhost:8000/api/v1/projects/{project_id}/events \
  -H "Authorization: Bearer <access_token>"

# 5. HITL 反馈恢复（当工作流暂停时）
curl -X POST http://localhost:8000/api/v1/projects/{project_id}/workflow/resume \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access_token>" \
  -d '{"action": "approve"}'

# 6. 获取输出列表
curl http://localhost:8000/api/v1/projects/{project_id}/outputs \
  -H "Authorization: Bearer <access_token>"

# 7. 导出为 Word 格式
curl -X POST http://localhost:8000/api/v1/projects/{project_id}/outputs/{output_id}/export \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access_token>" \
  -d '{"format": "docx"}'

# 8. 触发增量更新检查
curl -X POST http://localhost:8000/api/v1/projects/{project_id}/updates \
  -H "Authorization: Bearer <access_token>"

# 9. 查看更新历史
curl http://localhost:8000/api/v1/projects/{project_id}/updates \
  -H "Authorization: Bearer <access_token>"
```

完整 API 端点列表见 http://localhost:8000/docs 。

---

## 工作流详解

系统采用 LangGraph 编排的 15 节点工作流 DAG：

```
parse_intent → search → [HITL: 确认论文列表]
    → read → check_read_feedback
    → analyze (主题聚类/对比矩阵/趋势分析)
    → critique (质量评分/矛盾检测/研究空白)
    → check_critic_feedback
    → generate_outline → [HITL: 审阅大纲]
    → write_review → verify_citations
    → [HITL: 审阅初稿] → revise_review (可选)
    → export
```

### 各 Agent 职责

| Agent             | 功能                                                                          |
| ----------------- | ----------------------------------------------------------------------------- |
| **Intent Parser** | 解析用户输入，提取研究问题、关键词、时间范围等                                |
| **Search Agent**  | Semantic Scholar + arXiv + OpenAlex + PubMed 四源并行检索，查询扩展，去重排序 |
| **Reader Agent**  | PDF 下载解析，LLM 提取目标/方法/发现/局限（5 路并发）                         |
| **Analyst Agent** | Embedding 主题聚类，方法对比矩阵，引用网络，趋势分析                          |
| **Critic Agent**  | 质量评分，矛盾检测，Research Gap 发现，局限性汇总                             |
| **Writer Agent**  | 集群感知大纲生成，分节写作，引用格式化（APA/IEEE/GB/T 7714）                  |
| **Update Agent**  | 增量检索新文献，差异对比（6 级 ID 去重），LLM 相关性评估，更新报告生成        |
| **Export Node**   | 导出 Markdown / Word / BibTeX / RIS                                           |

### 输出类型

| 类型                 | 说明         |
| -------------------- | ------------ |
| `full_review`        | 完整学术综述 |
| `methodology_review` | 方法论综述   |
| `gap_report`         | 研究空白报告 |
| `trend_report`       | 研究趋势报告 |
| `research_roadmap`   | 研究路线图   |

---

## 配置说明

### 环境变量

| 变量                              | 必需   | 默认值                            | 说明                                     |
| --------------------------------- | ------ | --------------------------------- | ---------------------------------------- |
| `OPENAI_API_KEY`                  | **是** | —                                 | OpenAI API 密钥                          |
| `OPENAI_MODEL`                    | 否     | `gpt-4o`                          | LLM 模型名称                             |
| `DATABASE_URL`                    | 否     | `sqlite+aiosqlite:///data/app.db` | 数据库连接字符串                         |
| `CHROMA_PATH`                     | 否     | `/data/chroma`                    | ChromaDB 向量数据库路径                  |
| `REDIS_URL`                       | 否     | `redis://localhost:6379/0`        | Redis 连接地址                           |
| `S2_API_KEY`                      | 否     | —                                 | Semantic Scholar API Key（提高请求频率） |
| `OPENALEX_EMAIL`                  | 否     | —                                 | OpenAlex polite pool（提升至 10 req/s）  |
| `NCBI_API_KEY`                    | 否     | —                                 | PubMed NCBI API Key（提升至 10 req/s）   |
| `CHECKPOINTER_BACKEND`            | 否     | `sqlite`                          | LangGraph 检查点后端                     |
| `CHECKPOINT_DB_URL`               | 否     | `sqlite:///data/checkpoints.db`   | 检查点数据库路径                         |
| `AUTH_REQUIRED`                   | 否     | `false`                           | 是否强制认证                             |
| `JWT_SECRET_KEY`                  | 否     | `change-me-in-production`         | JWT 签名密钥（生产环境必须修改）         |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | 否     | `60`                              | Access Token 有效期（分钟）              |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS`   | 否     | `7`                               | Refresh Token 有效期（天）               |
| `FIRST_ADMIN_EMAIL`               | 否     | —                                 | 首次启动自动创建管理员邮箱               |
| `FIRST_ADMIN_PASSWORD`            | 否     | —                                 | 首次启动自动创建管理员密码               |
| `PROMPTS_DIR`                     | 否     | `prompts`                         | Prompt 模板目录                          |
| `LOG_LEVEL`                       | 否     | `INFO`                            | 日志级别（DEBUG/INFO/WARNING/ERROR）     |

### 工作流配置

工作流 DAG 通过 `backend/config/workflow.yaml` 配置，支持：
- 启用/禁用特定 Agent 节点
- 调整条件路由逻辑
- 配置 HITL 中断点
- 设置反馈迭代次数上限（默认最多 2 次）

---

## 常见问题

### 服务启动失败

**Q: `docker compose up` 后 backend 容器不断重启？**

检查 `.env` 文件是否正确配置了 `OPENAI_API_KEY`。查看日志：

```bash
docker compose logs backend
```

**Q: Worker 连接 Redis 失败？**

确保 Redis 服务已启动且健康：

```bash
docker compose ps redis
docker compose logs redis
```

### 运行时问题

**Q: 检索到的论文数量很少？**

- 尝试使用更宽泛的英文关键词
- 配置 `S2_API_KEY`、`OPENALEX_EMAIL`、`NCBI_API_KEY` 以提高各数据源请求频率
- 系统默认并行检索 4 个数据源（S2 + arXiv + OpenAlex + PubMed）
- 在 HITL 论文确认环节输入 `add "supplementary query"` 追加检索

**Q: Token 消耗过多？**

- CLI 中使用 `-b` 参数限制 token 预算
- 使用 `OPENAI_MODEL=gpt-4o-mini` 降低成本（精度会有所下降）

**Q: 中文文献支持如何？**

系统支持中文查询和中文输出（`-l zh`），但数据源（Semantic Scholar、arXiv、OpenAlex、PubMed）以英文文献为主。PubMed 对中文生物医学文献有一定收录，其余数据源的中文文献覆盖率有限。

### 数据与导出

**Q: 数据存储在哪里？**

- Docker 部署：数据存储在 `app-data` 和 `redis-data` Docker 卷中
- 本地开发：SQLite 数据库位于 `backend/data/app.db`，ChromaDB 位于 `backend/data/chroma/`

**Q: 如何备份数据？**

```bash
# Docker 部署
docker compose cp backend:/data ./backup

# 本地开发
cp -r backend/data ./backup
```

**Q: 支持哪些导出格式？**

Markdown (`.md`)、Word (`.docx`)、BibTeX (`.bib`)、RIS (`.ris`)。

---

## 下一步

- 阅读 [系统架构设计](design/system-architecture.md) 了解技术细节
- 阅读 [数据模型设计](design/data-model.md) 了解数据库 Schema
- 查看 [API 文档](http://localhost:8000/docs) 了解完整 API 接口
- 查看 [更新日志](dev/CHANGELOG.md) 了解版本历史
