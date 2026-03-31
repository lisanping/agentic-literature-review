# v0.6 实施计划：Celery Beat 定时调度 + PostgreSQL 生产数据库

> **文档版本**: v1.0
> **创建日期**: 2026-03-31
> **前置文档**: [v0.1 实施计划](implementation-plan.md) · [v0.5 实施计划](v05-implementation-plan.md) · [系统架构](../design/system-architecture.md)
> **目标**: 实现 Celery Beat 定时任务调度（自动增量更新 + 数据清理），支持 PostgreSQL 生产数据库部署

---

## 一、v0.6 范围

### 1.1 本次实施内容

| 维度     | v0.6 新增                                                       |
| -------- | --------------------------------------------------------------- |
| 定时调度 | Celery Beat 周期任务框架 + 自动增量更新调度 + 数据清理任务      |
| 数据库   | PostgreSQL 16 生产支持（ORM 方言兼容 + 迁移 + checkpoint 切换） |
| 配置     | 调度策略配置项、PostgreSQL 连接配置、数据库选择开关             |
| 部署     | Docker Compose 新增 `postgres` + `beat` 服务                    |
| 前端     | 项目调度配置 UI（更新频率/启停开关）                            |
| 文档     | SQLite → PostgreSQL 迁移指南                                    |

### 1.2 不包含

| 维度         | 状态                                      |
| ------------ | ----------------------------------------- |
| OAuth / SSO  | 第三方登录推迟（v0.7+）                   |
| 更多数据源   | Crossref / DBLP 推迟（v0.7+）             |
| 邮件通知     | 更新完成后的邮件/推送通知推迟（v0.7+）    |
| K8s 部署     | 推迟至 v1.0                               |
| 自动修订综述 | Update Agent 仅生成报告，不自动修改原综述 |

---

## 二、关键设计决策

### 2.1 Celery Beat 调度方案

**决策**: 使用 **Celery Beat + Redis 后端** 调度周期任务。

| 方案             | 优点                           | 缺点                       | 适用场景       |
| ---------------- | ------------------------------ | -------------------------- | -------------- |
| Celery Beat      | 原生集成、零额外依赖、成熟稳定 | 单点调度器（非 HA）        | 单机/小规模    |
| APScheduler      | 灵活、支持数据库存储           | 需额外引入、与 Celery 重叠 | 独立应用       |
| Cron + HTTP 触发 | 系统级、简单                   | 不感知任务状态、缺少重试   | 纯 DevOps 场景 |

**选型理由**:
- 项目已使用 Celery Worker，Beat 为原生附加组件，零额外依赖
- 周期任务通过 `celery_app.conf.beat_schedule` 声明式配置
- Beat 进程独立运行，不影响 Worker 性能
- 后续如需 HA，可切换到 `django-celery-beat` 或 `celery-redbeat` 等数据库后端

**调度策略**:

| 任务                    | 频率             | 队列  | 说明                                   |
| ----------------------- | ---------------- | ----- | -------------------------------------- |
| 自动增量更新检查        | 每日 02:00 UTC   | `low` | 扫描符合条件的项目，触发 Update Agent  |
| 过期 Checkpoint 清理    | 每周日 03:00 UTC | `low` | 清理超过 30 天的孤立 checkpoint 记录   |
| 过期 Refresh Token 清理 | 每日 04:00 UTC   | `low` | 清理已过期/已撤销的 refresh_token 记录 |

**自动更新触发条件**:
```
项目满足以下全部条件时触发增量更新:
1. status = 'completed'（已完成至少一次综述）
2. auto_update_enabled = true（用户启用自动更新）
3. last_search_at < now() - update_interval（超过用户设定的更新间隔）
4. deleted_at IS NULL（未被软删除）
```

### 2.2 PostgreSQL 迁移方案

**决策**: 采用 **双数据库并行支持** 方案，通过环境变量切换。

| 方案            | 优点                             | 缺点                    |
| --------------- | -------------------------------- | ----------------------- |
| 强制替换 SQLite | 简单、无分支代码                 | 开发环境也需 PostgreSQL |
| 双数据库并行    | 开发用 SQLite、生产用 PostgreSQL | 需处理方言差异          |
| 仅新部署用 PG   | 无迁移负担                       | 既有用户无法升级        |

**选型理由**:
- 本地开发 / CI 仍可使用 SQLite 零配置启动
- Docker Compose 生产部署切换到 PostgreSQL，仅需修改环境变量
- 提供 SQLite → PostgreSQL 数据迁移脚本

**当前 SQLite 特有代码清点**:

| 文件            | SQLite 特有代码                                            | 影响                                     |
| --------------- | ---------------------------------------------------------- | ---------------------------------------- |
| ORM 模型 (6 个) | `from sqlalchemy.dialects.sqlite import JSON`              | 需改为 `sqlalchemy.JSON`                 |
| ORM 索引定义    | `sqlite_where=...` 参数                                    | 需改为通用 `postgresql_where` / 条件索引 |
| Alembic 迁移    | `from sqlalchemy.dialects import sqlite` + `sqlite.JSON()` | 新迁移使用通用类型                       |
| Checkpointer    | `sqlite3.connect()` 硬编码                                 | 已有 `postgres` 分支                     |

### 2.3 Project 模型扩展

新增调度相关字段以支持 per-project 自动更新配置：

```python
class Project(Base):
    # ... 现有字段 ...
    auto_update_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    update_interval_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=30  # 默认 30 天
    )
```

---

## 三、阶段划分

```
阶段 1: ORM 方言兼容改造   ──┐
                              ├── 可并行
阶段 2: PostgreSQL 部署集成 ──┘
                              │
                              ▼
阶段 3: Celery Beat 定时任务 ── 调度框架 + 3 个周期任务
                              │
                              ▼
阶段 4: 前端调度配置 UI
                              │
                              ▼
阶段 5: 数据迁移脚本 + 测试 + 文档
```

---

## 四、阶段 1：ORM 方言兼容改造

**目标**: 消除代码中所有 SQLite-specific 依赖，使 ORM 模型和索引定义同时兼容 SQLite 和 PostgreSQL。

### 4.1 任务清单

| #    | 任务                          | 输出文件                              | 说明                                                                          |
| ---- | ----------------------------- | ------------------------------------- | ----------------------------------------------------------------------------- |
| 1.1  | JSON 类型统一                 | `app/models/project.py` (修改)        | `from sqlalchemy.dialects.sqlite import JSON` → `from sqlalchemy import JSON` |
| 1.2  | JSON 类型统一                 | `app/models/paper.py` (修改)          | 同上                                                                          |
| 1.3  | JSON 类型统一                 | `app/models/paper_analysis.py` (修改) | 同上                                                                          |
| 1.4  | JSON 类型统一                 | `app/models/review_output.py` (修改)  | 同上                                                                          |
| 1.5  | JSON 类型统一                 | `app/models/audit_log.py` (修改)      | 同上                                                                          |
| 1.6  | 部分索引兼容                  | `app/models/project.py` (修改)        | `sqlite_where=` → 通用条件索引辅助函数                                        |
| 1.7  | 部分索引兼容                  | `app/models/paper.py` (修改)          | 同上                                                                          |
| 1.8  | 部分索引兼容                  | `app/models/paper_analysis.py` (修改) | 同上                                                                          |
| 1.9  | 部分索引兼容                  | `app/models/project_paper.py` (修改)  | 同上                                                                          |
| 1.10 | 部分索引兼容                  | `app/models/project_share.py` (修改)  | 同上                                                                          |
| 1.11 | 条件索引辅助函数              | `app/models/database.py` (修改)       | 封装 `partial_index()` 适配不同方言                                           |
| 1.12 | Project 新增调度字段          | `app/models/project.py` (修改)        | `auto_update_enabled` + `update_interval_days`                                |
| 1.13 | ProjectUpdate Schema 新增字段 | `app/schemas/project.py` (修改)       | 请求/响应 Schema 新增调度字段                                                 |
| 1.14 | 单元测试验证                  | `tests/test_models.py` (扩展)         | 确认现有测试在 SQLite 下无回归                                                |

### 4.2 索引兼容方案

SQLAlchemy `Index` 的 `sqlite_where` 和 `postgresql_where` 参数可以同时指定：

```python
# 兼容写法：两个方言参数同时指定，SQLAlchemy 自动按实际方言选择
Index(
    "idx_projects_status",
    "status",
    sqlite_where=deleted_at.is_(None),
    postgresql_where=deleted_at.is_(None),
)
```

为减少重复代码，提供辅助函数：

```python
# app/models/database.py
def partial_index(name: str, *columns, where):
    """Create a partial/filtered index compatible with both SQLite and PostgreSQL."""
    return Index(name, *columns, sqlite_where=where, postgresql_where=where)
```

### 4.3 JSON 类型兼容

SQLAlchemy 通用 `JSON` 类型同时支持 SQLite（存储为 TEXT）和 PostgreSQL（原生 JSONB）。直接使用 `from sqlalchemy import JSON` 替换 `from sqlalchemy.dialects.sqlite import JSON`，无功能差异。

### 4.4 验收标准

- [ ] 所有 ORM 模型不再 import `sqlalchemy.dialects.sqlite`
- [ ] 全部现有测试在 SQLite 下通过（零回归）
- [ ] `partial_index()` 辅助函数有单元测试
- [ ] Project 模型新增 `auto_update_enabled` / `update_interval_days` 字段

---

## 五、阶段 2：PostgreSQL 部署集成

**目标**: Docker Compose 新增 PostgreSQL 服务，支持通过环境变量切换数据库。

### 5.1 任务清单

| #    | 任务                                 | 输出文件                                         | 说明                                                          |
| ---- | ------------------------------------ | ------------------------------------------------ | ------------------------------------------------------------- |
| 2.1  | 新增 `asyncpg` 依赖                  | `requirements.txt` (修改)                        | `asyncpg>=0.29,<1.0`                                          |
| 2.2  | 新增 `langgraph-checkpoint-postgres` | `requirements.txt` (修改)                        | `langgraph-checkpoint-postgres>=2.0,<3.0`                     |
| 2.3  | 新增 `psycopg[binary]` 依赖          | `requirements.txt` (修改)                        | Checkpointer 同步驱动（LangGraph PostgresSaver 使用 psycopg） |
| 2.4  | Docker Compose 新增 postgres 服务    | `docker-compose.yml` (修改)                      | `postgres:16-alpine`，健康检查，持久化卷                      |
| 2.5  | Docker Compose 新增 postgres profile | `docker-compose.yml` (修改)                      | 使用 `profiles` 区分 SQLite（默认）和 PostgreSQL 部署模式     |
| 2.6  | backend/worker 环境变量更新          | `docker-compose.yml` (修改)                      | PostgreSQL 模式下 `DATABASE_URL` 指向 postgres 容器           |
| 2.7  | Alembic 迁移脚本                     | `alembic/versions/v06_schedule_fields.py` (新增) | `auto_update_enabled` + `update_interval_days` 字段迁移       |
| 2.8  | `.env.example` 更新                  | `.env.example` (修改)                            | 新增 PostgreSQL 连接字符串示例和调度配置项                    |
| 2.9  | Checkpointer 工厂增强                | `app/agents/checkpointer.py` (修改)              | PostgresSaver 使用 `psycopg` 连接池，自动创建表               |
| 2.10 | 数据库引擎连接池配置                 | `app/models/database.py` (修改)                  | PostgreSQL 模式下配置连接池参数 (`pool_size`/`max_overflow`)  |
| 2.11 | PostgreSQL 端到端验证                | —                                                | `docker compose --profile postgres up` 全流程验证             |

### 5.2 Docker Compose 设计

使用 Docker Compose `profiles` 实现两种部署模式：

```yaml
# 默认模式 (SQLite): docker compose up
# PostgreSQL 模式: docker compose --profile postgres up

services:
  postgres:
    image: postgres:16-alpine
    profiles: ["postgres"]
    environment:
      POSTGRES_DB: review_db
      POSTGRES_USER: review_user
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-changeme}
    volumes:
      - pg-data:/var/lib/postgresql/data
    networks:
      - app-net
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "review_user", "-d", "review_db"]
      interval: 10s
      timeout: 3s
      retries: 5
    restart: unless-stopped
```

环境变量覆盖：

```yaml
  # backend / worker 中增加 PostgreSQL 模式的环境变量覆盖
  # 用户通过 .env 文件设置:
  # DATABASE_URL=postgresql+asyncpg://review_user:changeme@postgres:5432/review_db
  # CHECKPOINT_DB_URL=postgresql://review_user:changeme@postgres:5432/review_db
  # CHECKPOINTER_BACKEND=postgres
```

### 5.3 连接池配置

```python
# app/models/database.py
if settings.DATABASE_URL.startswith("postgresql"):
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,       # 连接健康检查
        pool_recycle=3600,         # 每小时回收连接
    )
else:
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
```

### 5.4 验收标准

- [ ] `docker compose up` (默认) 仍使用 SQLite，行为不变
- [ ] `docker compose --profile postgres up` 启动含 PostgreSQL 的全栈
- [ ] `alembic upgrade head` 在 PostgreSQL 上成功创建全部表 + 索引
- [ ] 完整工作流 (创建项目 → 检索 → HITL → 写作 → 导出) 在 PostgreSQL 下通过
- [ ] LangGraph Checkpointer 在 PostgreSQL 下正常读写

---

## 六、阶段 3：Celery Beat 定时任务

**目标**: 实现 Celery Beat 调度框架，注册 3 个周期任务。

### 6.1 任务清单

| #   | 任务                          | 输出文件                           | 说明                                                                   |
| --- | ----------------------------- | ---------------------------------- | ---------------------------------------------------------------------- |
| 3.1 | Beat Schedule 配置            | `app/celery_app.py` (修改)         | 注册 3 个周期任务到 `beat_schedule`                                    |
| 3.2 | 自动更新扫描任务              | `app/tasks.py` (修改)              | `scan_projects_for_updates()` — 扫描符合条件的项目并触发 `run_update`  |
| 3.3 | Checkpoint 清理任务           | `app/tasks.py` (修改)              | `cleanup_old_checkpoints()` — 清理超过 30 天的孤立 checkpoint          |
| 3.4 | Refresh Token 清理任务        | `app/tasks.py` (修改)              | `cleanup_expired_tokens()` — 清理已过期/已撤销的 refresh_token         |
| 3.5 | 调度配置项                    | `app/config.py` (修改)             | `UPDATE_SCAN_HOUR`、`CHECKPOINT_RETENTION_DAYS`、`ENABLE_AUTO_UPDATES` |
| 3.6 | Docker Compose 新增 beat 服务 | `docker-compose.yml` (修改)        | Celery Beat 独立容器                                                   |
| 3.7 | 更新 API — 调度配置端点       | `app/api/routes/updates.py` (修改) | `PATCH /projects/{id}/updates/schedule` 启停自动更新 + 设置间隔        |
| 3.8 | 更新 API — Schema             | `app/schemas/project.py` (修改)    | `UpdateScheduleRequest` / `UpdateScheduleResponse`                     |
| 3.9 | 单元测试                      | `tests/test_tasks.py` (新增)       | 扫描逻辑、清理逻辑单元测试                                             |

### 6.2 Celery Beat 配置

```python
# app/celery_app.py
from celery.schedules import crontab
from app.config import settings

celery_app.conf.beat_schedule = {
    "scan-projects-for-updates": {
        "task": "app.tasks.scan_projects_for_updates",
        "schedule": crontab(hour=settings.UPDATE_SCAN_HOUR, minute=0),
        "options": {"queue": "low"},
    },
    "cleanup-old-checkpoints": {
        "task": "app.tasks.cleanup_old_checkpoints",
        "schedule": crontab(day_of_week=0, hour=3, minute=0),
        "options": {"queue": "low"},
    },
    "cleanup-expired-tokens": {
        "task": "app.tasks.cleanup_expired_tokens",
        "schedule": crontab(hour=4, minute=0),
        "options": {"queue": "low"},
    },
}
```

### 6.3 自动更新扫描任务设计

```python
@celery_app.task(name="app.tasks.scan_projects_for_updates", queue="low")
def scan_projects_for_updates():
    """扫描所有符合自动更新条件的项目，逐个触发 run_update。

    触发条件:
    1. status = 'completed'
    2. auto_update_enabled = True
    3. last_search_at < now() - update_interval_days
    4. deleted_at IS NULL
    5. 当前没有正在执行的更新 (status != 'updating')

    安全措施:
    - 每次最多触发 10 个项目更新，避免资源耗尽
    - 每个 run_update 任务分配到 default 队列
    - 项目间随机延迟 (0~60s)，避免 API 限速集中触发
    """
```

### 6.4 Checkpoint 清理任务设计

```python
@celery_app.task(name="app.tasks.cleanup_old_checkpoints", queue="low")
def cleanup_old_checkpoints():
    """清理超过 retention_days 天的孤立 checkpoint。

    清理范围:
    - SQLite 模式: 操作 checkpoints.db 中的旧记录
    - PostgreSQL 模式: DELETE FROM checkpoints WHERE created_at < cutoff

    安全措施:
    - 不清理状态为 'in_progress' / 'updating' 项目的 checkpoint
    - 每次最多清理 1000 条，避免长事务
    """
```

### 6.5 Docker Compose Beat 服务

```yaml
  beat:
    build: ./backend
    command: >
      celery -A app.celery_app:celery_app beat
      --loglevel=info
      --pidfile=/tmp/celerybeat.pid
      --schedule=/tmp/celerybeat-schedule
    environment:
      # 与 worker 相同的环境变量
    volumes:
      - app-data:/data
    networks:
      - app-net
    depends_on:
      redis:
        condition: service_healthy
    restart: unless-stopped
```

> **注意**: Celery Beat 必须确保单实例运行（单个 `beat` 容器），防止重复调度。Docker Compose 天然保证每个服务只有一个实例。

### 6.6 配置项

```python
# app/config.py 新增
ENABLE_AUTO_UPDATES: bool = True        # 全局开关：是否启用自动更新调度
UPDATE_SCAN_HOUR: int = 2               # 每日扫描时间（UTC 小时，0-23）
CHECKPOINT_RETENTION_DAYS: int = 30     # Checkpoint 保留天数
MAX_AUTO_UPDATE_BATCH: int = 10         # 单次扫描最多触发的项目数
```

### 6.7 新增 API 端点

```
PATCH /api/v1/projects/{project_id}/updates/schedule
  请求体:
    {
      "auto_update_enabled": true,
      "update_interval_days": 14
    }
  响应:
    {
      "auto_update_enabled": true,
      "update_interval_days": 14,
      "next_check_at": "2026-04-14T02:00:00Z"
    }
  权限: collaborator

GET /api/v1/projects/{project_id}/updates/schedule
  响应:
    {
      "auto_update_enabled": false,
      "update_interval_days": 30,
      "last_search_at": "2026-03-20T10:30:00Z",
      "next_check_at": null
    }
  权限: viewer
```

### 6.8 验收标准

- [ ] Celery Beat 容器启动后按 crontab 调度触发任务
- [ ] `scan_projects_for_updates` 正确筛选符合条件的项目
- [ ] 已禁用自动更新的项目不会被触发
- [ ] `cleanup_old_checkpoints` 正确清理过期记录，不删除活跃项目 checkpoint
- [ ] `cleanup_expired_tokens` 正确清理过期 token
- [ ] API 端点可启停项目自动更新 + 设置间隔

---

## 七、阶段 4：前端调度配置 UI

**目标**: 在项目页面提供自动更新调度的配置界面。

### 7.1 任务清单

| #   | 任务                     | 输出文件                                           | 说明                                                |
| --- | ------------------------ | -------------------------------------------------- | --------------------------------------------------- |
| 4.1 | 前端 API 层 — 调度接口   | `src/api/updates.ts` (修改)                        | `getSchedule` / `updateSchedule` 函数               |
| 4.2 | 类型定义                 | `src/types/project.ts` (修改)                      | 新增 `UpdateSchedule` 类型                          |
| 4.3 | ProjectResponse 类型更新 | `src/types/project.ts` (修改)                      | 新增 `auto_update_enabled` / `update_interval_days` |
| 4.4 | 调度配置组件             | `src/components/Project/UpdateSchedule.tsx` (新增) | Switch 开关 + 间隔选择 + 下次检查时间展示           |
| 4.5 | ProjectPage 集成         | `src/pages/ProjectPage.tsx` (修改)                 | 在更新 Tab 中嵌入调度配置组件                       |

### 7.2 UI 设计

```
┌────────────────────────────────────────────┐
│ 📅 自动更新调度                            │
├────────────────────────────────────────────┤
│                                            │
│ 自动检查新文献   [======●] 已启用          │
│                                            │
│ 检查间隔         [  14 天  ▼]              │
│                  (7 天 / 14 天 / 30 天 / 90 天) │
│                                            │
│ 上次检索         2026-03-20 10:30          │
│ 下次检查         2026-04-03 02:00 (UTC)    │
│                                            │
└────────────────────────────────────────────┘
```

### 7.3 验收标准

- [ ] Switch 开关可启停自动更新
- [ ] 间隔选择器可修改更新频率
- [ ] 显示上次检索和预估下次检查时间
- [ ] 未启用时显示「自动更新已关闭」状态

---

## 八、阶段 5：数据迁移脚本 + 测试 + 文档

**目标**: 提供 SQLite → PostgreSQL 数据迁移工具，完整测试覆盖，撰写迁移指南。

### 8.1 任务清单

| #   | 任务                | 输出文件                                         | 说明                                      |
| --- | ------------------- | ------------------------------------------------ | ----------------------------------------- |
| 5.1 | 数据迁移脚本        | `backend/scripts/migrate_sqlite_to_pg.py` (新增) | 从 SQLite 读取数据 → 批量写入 PostgreSQL  |
| 5.2 | PostgreSQL E2E 测试 | `tests/test_e2e_postgres.py` (新增)              | `@pytest.mark.postgres` 标记，CI 可选运行 |
| 5.3 | Beat 调度测试       | `tests/test_tasks.py` (新增)                     | 扫描逻辑 + 清理逻辑单元测试               |
| 5.4 | 调度 API 测试       | `tests/test_api.py` (扩展)                       | 调度配置 CRUD 测试                        |
| 5.5 | 现有测试回归        | —                                                | 全量测试在 SQLite 模式下通过              |
| 5.6 | 迁移指南文档        | `docs/MIGRATION_SQLITE_TO_PG.md` (新增)          | 步骤化迁移操作指南                        |
| 5.7 | CHANGELOG 更新      | `docs/dev/CHANGELOG.md` (修改)                   | v0.6 变更记录                             |

### 8.2 数据迁移脚本设计

```python
"""
用法: python scripts/migrate_sqlite_to_pg.py \
        --sqlite data/app.db \
        --postgres postgresql://user:pass@host/db

步骤:
1. 连接 SQLite 源库，读取所有表数据
2. 连接 PostgreSQL 目标库，确认 alembic upgrade head 已执行
3. 按外键依赖顺序批量插入:
   users → projects → papers → project_papers →
   paper_analyses → review_outputs → project_shares →
   refresh_tokens → audit_log
4. 校验:行数对比、主键完整性
5. 输出迁移报告 (成功/失败/跳过行数)
"""
```

表迁移顺序（按外键依赖）:
1. `users` — 无外键
2. `projects` — FK: `user_id` → `users`
3. `papers` + `paper_fulltext` — 无外键
4. `project_papers` — FK: `project_id` + `paper_id`
5. `paper_analyses` — FK: `project_id` + `paper_id`
6. `review_outputs` — FK: `project_id`
7. `project_shares` — FK: `project_id` + `user_id`
8. `refresh_tokens` — FK: `user_id`
9. `audit_log` — FK: `user_id`

### 8.3 迁移指南大纲

```markdown
# SQLite → PostgreSQL 迁移指南

## 前置条件
- Docker Compose 已配置 PostgreSQL 服务
- 已备份现有 SQLite 数据库

## 迁移步骤
1. 停止所有服务: `docker compose down`
2. 备份数据: `cp data/app.db data/app.db.bak`
3. 启动 PostgreSQL: `docker compose --profile postgres up postgres -d`
4. 初始化 Schema: `alembic upgrade head`
5. 执行迁移: `python scripts/migrate_sqlite_to_pg.py --sqlite ... --postgres ...`
6. 验证: `python scripts/migrate_sqlite_to_pg.py --verify ...`
7. 更新 .env: DATABASE_URL / CHECKPOINT_DB_URL / CHECKPOINTER_BACKEND
8. 重启全栈: `docker compose --profile postgres up -d`
9. 验证服务: curl /readyz

## 回滚
- 恢复 .env 为 SQLite 配置
- `docker compose up -d` (无 --profile postgres)
```

### 8.4 验收标准

- [ ] 迁移脚本可将 SQLite 数据完整导入 PostgreSQL
- [ ] 迁移后全部 API 功能正常
- [ ] Beat 调度任务测试通过
- [ ] 全量现有测试在 SQLite 下无回归
- [ ] 迁移指南可指导用户完成升级

---

## 九、文件产出清单

```
backend/
├── app/
│   ├── config.py                              # [阶段 3] 修改 (调度配置项)
│   ├── celery_app.py                          # [阶段 3] 修改 (beat_schedule)
│   ├── tasks.py                               # [阶段 3] 修改 (3 个周期任务)
│   ├── models/
│   │   ├── database.py                        # [阶段 1] 修改 (partial_index + 连接池)
│   │   ├── project.py                         # [阶段 1] 修改 (JSON + 索引 + 调度字段)
│   │   ├── paper.py                           # [阶段 1] 修改 (JSON + 索引)
│   │   ├── paper_analysis.py                  # [阶段 1] 修改 (JSON + 索引)
│   │   ├── project_paper.py                   # [阶段 1] 修改 (索引)
│   │   ├── project_share.py                   # [阶段 1] 修改 (索引)
│   │   ├── review_output.py                   # [阶段 1] 修改 (JSON)
│   │   └── audit_log.py                       # [阶段 1] 修改 (JSON)
│   ├── schemas/
│   │   └── project.py                         # [阶段 1+3] 修改 (调度字段 + Schema)
│   ├── agents/
│   │   └── checkpointer.py                    # [阶段 2] 修改 (PostgresSaver 增强)
│   └── api/routes/
│       └── updates.py                         # [阶段 3] 修改 (调度 API)
├── alembic/versions/
│   └── v06_schedule_fields.py                 # [阶段 2] 新增
├── scripts/
│   └── migrate_sqlite_to_pg.py                # [阶段 5] 新增
├── requirements.txt                           # [阶段 2] 修改 (asyncpg + pg checkpoint)
├── tests/
│   ├── test_tasks.py                          # [阶段 5] 新增
│   └── test_e2e_postgres.py                   # [阶段 5] 新增

frontend/src/
├── api/
│   └── updates.ts                             # [阶段 4] 修改
├── types/
│   └── project.ts                             # [阶段 4] 修改
├── components/Project/
│   └── UpdateSchedule.tsx                     # [阶段 4] 新增
└── pages/
    └── ProjectPage.tsx                        # [阶段 4] 修改

docs/
├── MIGRATION_SQLITE_TO_PG.md                  # [阶段 5] 新增
└── dev/
    ├── v06-implementation-plan.md             # 本文件
    └── CHANGELOG.md                           # [阶段 5] 修改

docker-compose.yml                             # [阶段 2+3] 修改
.env.example                                   # [阶段 2] 修改

# 新增文件: ~5 个
# 修改文件: ~20 个
```

---

## 十、依赖关系

```
阶段 1 (ORM 方言兼容) ──┐
                         ├── 可并行（阶段 2 不依赖代码改动，只需配置）
阶段 2 (PostgreSQL 部署) ─┘
          │
          ▼
阶段 3 (Celery Beat) ── 依赖 1 完成（新字段已就位）
          │
          ▼
阶段 4 (前端 UI) ── 依赖 3 的 API 就位
          │
          ▼
阶段 5 (迁移 + 测试 + 文档) ── 依赖全部阶段完成
```

**并行机会**:
- 阶段 1 和 2 可并行：ORM 修改 vs Docker/依赖配置互不干扰
- 阶段 4 的类型定义和组件骨架可在阶段 3 的 API 设计确定后提前开始

---

## 十一、技术风险

| 风险                               | 影响 | 缓解策略                                                       |
| ---------------------------------- | ---- | -------------------------------------------------------------- |
| SQLite → PostgreSQL 方言差异       | 中   | 统一使用 SQLAlchemy 通用类型；部分索引双方言参数同时指定       |
| Alembic 迁移脚本方言兼容           | 中   | 新迁移使用 `sa.JSON()` 而非 `sqlite.JSON()`；旧迁移保持不改    |
| Celery Beat 单点故障               | 低   | Docker Compose 天然单实例；`restart: unless-stopped` 自动恢复  |
| 数据迁移丢失/损坏                  | 高   | 迁移前强制备份；迁移后行数校验；支持回滚到 SQLite              |
| LangGraph Checkpoint PG 驱动兼容性 | 中   | 锁定 `langgraph-checkpoint-postgres` 版本；早期 PoC 验证       |
| 并发 Beat 调度导致重复更新         | 中   | 扫描任务获取项目后设置 `status=updating`，防止重复触发         |
| PostgreSQL 连接池耗尽              | 低   | `pool_size=5, max_overflow=10`；Worker + Beat 合计不超 20 连接 |

---

## 十二、后续迭代规划

| 版本 | 主要内容            | 关键新增                                      |
| ---- | ------------------- | --------------------------------------------- |
| v0.7 | 更多数据源 + OAuth  | Crossref / DBLP 适配器、OAuth SSO 登录        |
| v0.8 | 邮件通知 + 团队管理 | 更新完成通知、团队/组织、成员邀请             |
| v0.9 | 综述自动修订        | Update Agent 自动修改原综述章节               |
| v1.0 | 生产就绪            | K8s 部署、HTTPS、负载均衡、监控告警、完善日志 |
