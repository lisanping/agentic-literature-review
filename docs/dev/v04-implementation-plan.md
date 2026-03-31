# v0.4 实施计划：多用户认证 + 交互式可视化

> **文档版本**: v1.0
> **创建日期**: 2026-03-30
> **前置文档**: [需求与功能设计](../design/requirements-and-functional-design.md) · [系统架构](../design/system-architecture.md) · [数据模型](../design/data-model.md) · [v0.1 实施计划](implementation-plan.md) · [v0.3 实施计划](v03-implementation-plan.md)
> **目标**: 在 v0.3 基础上，实现多用户 JWT 认证与权限控制、交互式知识图谱与时间线可视化

---

## 一、v0.4 范围

### 1.1 新增能力

| 维度     | v0.4 新增                                                                   |
| -------- | --------------------------------------------------------------------------- |
| 认证     | JWT 用户注册/登录/刷新、Bearer Token 鉴权中间件                             |
| 权限     | 项目按 user_id 隔离、RBAC 角色模型 (admin/user)、项目分享 API               |
| 用户管理 | User ORM 模型、用户个人资料与设置                                           |
| 可视化   | 交互式知识图谱 (D3.js force-directed)、交互式时间线、趋势折线图             |
| 输出类型 | 解锁 `knowledge_map` + `timeline` 输出类型（前端可视化渲染 + SVG/PNG 导出） |
| 前端     | 登录/注册页面、用户菜单、项目分享 UI、图谱/时间线交互组件                   |

### 1.2 不变 / 保留

| 维度       | 状态                                                              |
| ---------- | ----------------------------------------------------------------- |
| 基础设施   | SQLite + Chroma + Redis，Docker Compose 保持不变                  |
| Agent 链路 | 6-Agent 完整工作流 (Search→Read→Analyze→Critique→Write→Export)    |
| 工作流配置 | workflow.yaml 无结构变更                                          |
| State 字段 | ReviewState 无修改，可视化数据已有 citation_network / timeline 等 |
| 后端框架   | FastAPI + Celery + LangGraph 不变                                 |

### 1.3 功能边界

```
v0.4 包含:
  ✅ 单机多用户 (注册/登录，项目隔离)
  ✅ JWT Token 认证 (access + refresh)
  ✅ 基于角色的权限控制 (admin / user)
  ✅ 项目分享 (只读/协作)
  ✅ 交互式知识图谱 (D3.js force-directed graph)
  ✅ 交互式时间线 (年份轴 + 里程碑)
  ✅ 趋势折线图 (替代 v0.3 的 CSS 柱状图)
  ✅ 可视化导出 (SVG / PNG)

v0.4 不包含:
  ❌ OAuth / SSO 第三方登录 (v0.5+)
  ❌ 团队/组织管理 (v0.5+)
  ❌ PostgreSQL 迁移 (v0.5)
  ❌ 实时协作编辑 (v1.0)
  ❌ K8s / HTTPS 部署 (v1.0)
```

---

## 二、关键设计决策

### 2.1 认证方案：内建 JWT

**决策**: 采用 **内建 JWT 认证** 而非外部身份服务 (Keycloak/Auth0)。

| 方案                | 优点                       | 缺点                         | 适用场景    |
| ------------------- | -------------------------- | ---------------------------- | ----------- |
| 内建 JWT            | 零外部依赖、部署简单、可控 | 需自行实现密码安全/Token轮转 | 单机/小团队 |
| Keycloak            | 功能完备、支持 SSO/LDAP    | 部署重、配置复杂             | 企业级      |
| Auth0/Firebase Auth | 托管服务、开箱即用         | 依赖外部服务、成本增加       | SaaS 产品   |

**选型理由**:
- v0.4 目标为单机/小团队私有部署，无需 SSO/LDAP
- 避免在 Docker Compose 中引入额外重量级服务
- 后续 v0.5+ 可平滑迁移至外部身份服务（抽象认证接口）

**Token 策略**:
- **Access Token**: JWT, HS256 签名, 有效期 1 小时
- **Refresh Token**: 随机 UUID, 存入 Redis, 有效期 7 天
- **Token 刷新**: `/auth/refresh` 接口，签发新 access_token，refresh_token 一次性使用（旋转）
- **密码存储**: bcrypt hash (cost factor 12), 不可逆

### 2.2 权限模型：RBAC 简化版

**决策**: 两级角色 + 项目级共享，不引入通用权限框架。

```
角色层次:
  admin — 管理所有用户和项目、系统设置
  user  — 管理自己的项目

项目级权限:
  owner      — 项目创建者，完全控制
  collaborator — 可启动/恢复工作流、导出
  viewer     — 只读访问项目和输出
```

**权限矩阵**:

| 操作               | owner | collaborator | viewer | admin |
| ------------------ | ----- | ------------ | ------ | ----- |
| 查看项目/论文/输出 | ✅     | ✅            | ✅      | ✅     |
| 启动/恢复工作流    | ✅     | ✅            | ❌      | ✅     |
| HITL 决策          | ✅     | ✅            | ❌      | ✅     |
| 导出               | ✅     | ✅            | ✅      | ✅     |
| 编辑项目设置       | ✅     | ❌            | ❌      | ✅     |
| 删除项目           | ✅     | ❌            | ❌      | ✅     |
| 分享项目           | ✅     | ❌            | ❌      | ✅     |
| 管理用户           | ❌     | ❌            | ❌      | ✅     |

### 2.3 可视化技术选型：D3.js

**决策**: 前端使用 **D3.js** 实现交互式知识图谱和时间线。

| 方案               | 优点                           | 缺点                          |
| ------------------ | ------------------------------ | ----------------------------- |
| D3.js              | 灵活性极高、社区成熟、SVG 原生 | 学习曲线陡、需封装 React 集成 |
| @ant-design/charts | 与 Ant Design 风格一致         | 图谱类型支持弱、定制化受限    |
| react-force-graph  | React 封装好、上手快           | 包体积大、功能偏向通用网络图  |
| Cytoscape.js       | 专业图谱库、性能好             | 样式定制与 Ant Design 对齐难  |
| ECharts            | 中文生态好、图表类型丰富       | 力导向图交互不如 D3 灵活      |

**选型理由**:
- 知识图谱需要高度定制的力导向布局、节点大小/颜色映射、边交互
- 时间线需要自定义轴刻度、里程碑标记、论文气泡
- D3.js 是可视化领域的事实标准，可生成纯 SVG（方便导出）
- 项目已有 React 基础，封装 `useD3` Hook 即可优雅集成

### 2.4 知识图谱数据来源

**决策**: 复用 v0.3 已有的 `citation_network` + `topic_clusters` 数据结构，**不引入 Neo4j**。

| 数据维度   | 数据来源 (v0.3 已有)                                | 图谱映射                                     |
| ---------- | --------------------------------------------------- | -------------------------------------------- |
| 论文节点   | `citation_network.nodes`                            | 节点大小 ∝ citation_count, 颜色 = cluster_id |
| 引用关系边 | `citation_network.edges`                            | 有向边, 宽度 ∝ 关系强度                      |
| 聚类分组   | `topic_clusters`                                    | 凸包分组着色、图例标签                       |
| 论文角色   | `node.role` (foundational/bridge/recent/peripheral) | 节点形状差异                                 |
| 关键论文   | `citation_network.key_papers`                       | 星形标记/描边加粗                            |
| 桥梁论文   | `citation_network.bridge_papers`                    | 菱形标记                                     |

**理由**: Analyst Agent 已生成完整的 `citation_network` 图数据，无需额外后端计算。前端仅需将 JSON 映射到 D3.js 力导向布局即可。

### 2.5 项目数据隔离策略

**决策**: 基于 `user_id` 字段的 **逻辑隔离**，而非物理隔离。

- `Project.user_id` 从 nullable 改为 **NOT NULL**（Alembic 迁移时为存量数据分配默认用户）
- 所有项目查询 API 强制附加 `WHERE user_id = current_user.id` 条件
- 论文 (Paper) 表保持全局共享（去重需求），但 `ProjectPaper` 关联隔离
- 共享项目通过 `project_shares` 表实现跨用户访问

---

## 三、数据模型扩展

### 3.1 新增表：users

```sql
CREATE TABLE users (
    id              TEXT PRIMARY KEY,                      -- UUID
    email           TEXT NOT NULL UNIQUE,                  -- 登录邮箱
    username        TEXT NOT NULL,                         -- 显示名称
    hashed_password TEXT NOT NULL,                         -- bcrypt hash
    role            TEXT NOT NULL DEFAULT 'user',          -- 'admin' | 'user'
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,         -- 账号是否激活
    avatar_url      TEXT,                                  -- 头像 URL (可选)
    preferences     JSON DEFAULT '{}',                     -- 用户偏好设置 JSON
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login_at   DATETIME                               -- 最近登录时间
);

CREATE UNIQUE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role) WHERE is_active = TRUE;
```

**`preferences` JSON 结构**:

```json
{
    "default_language": "zh",
    "default_citation_style": "apa",
    "default_output_types": ["full_review"],
    "token_budget_default": null,
    "theme": "light"
}
```

### 3.2 新增表：refresh_tokens

```sql
CREATE TABLE refresh_tokens (
    id              TEXT PRIMARY KEY,                      -- UUID
    user_id         TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash      TEXT NOT NULL UNIQUE,                  -- SHA-256 hash of refresh token
    expires_at      DATETIME NOT NULL,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    revoked_at      DATETIME                               -- 被撤销时间 (NULL = 有效)
);

CREATE INDEX idx_refresh_tokens_user ON refresh_tokens(user_id);
CREATE INDEX idx_refresh_tokens_expires ON refresh_tokens(expires_at);
```

### 3.3 新增表：project_shares

```sql
CREATE TABLE project_shares (
    id              TEXT PRIMARY KEY,                      -- UUID
    project_id      TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id         TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    permission      TEXT NOT NULL DEFAULT 'viewer',        -- 'viewer' | 'collaborator'
    shared_by       TEXT NOT NULL REFERENCES users(id),    -- 分享发起人
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    revoked_at      DATETIME                               -- 撤销时间 (NULL = 有效)
);

CREATE UNIQUE INDEX idx_project_shares_unique ON project_shares(project_id, user_id)
    WHERE revoked_at IS NULL;
CREATE INDEX idx_project_shares_user ON project_shares(user_id) WHERE revoked_at IS NULL;
```

### 3.4 新增表：audit_log

```sql
CREATE TABLE audit_log (
    id              TEXT PRIMARY KEY,                      -- UUID
    user_id         TEXT REFERENCES users(id),             -- 操作者 (系统操作可为 NULL)
    action          TEXT NOT NULL,                         -- 'login' | 'create_project' | 'share_project' | ...
    resource_type   TEXT,                                  -- 'project' | 'user' | 'output' | ...
    resource_id     TEXT,                                  -- 被操作资源的 ID
    details         JSON,                                  -- 操作详情
    ip_address      TEXT,                                  -- 请求 IP
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_log_user ON audit_log(user_id, created_at);
CREATE INDEX idx_audit_log_action ON audit_log(action, created_at);
```

### 3.5 projects 表变更

```sql
-- user_id 从 nullable 改为 NOT NULL
ALTER TABLE projects ADD CONSTRAINT fk_projects_user FOREIGN KEY (user_id) REFERENCES users(id);
-- Alembic 迁移: 存量 project 的 user_id 分配给系统默认用户
```

### 3.6 Pydantic Schema 新增

```python
# schemas/user.py
class UserRegister(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=2, max_length=50)
    password: str = Field(..., min_length=8, max_length=128)

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: str
    email: str
    username: str
    role: str
    is_active: bool
    avatar_url: str | None
    preferences: dict
    created_at: datetime
    last_login_at: datetime | None

class UserUpdate(BaseModel):
    username: str | None = None
    avatar_url: str | None = None
    preferences: dict | None = None

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds

class TokenRefresh(BaseModel):
    refresh_token: str

# schemas/share.py
class ProjectShareCreate(BaseModel):
    email: str  # 被分享用户的邮箱
    permission: Literal["viewer", "collaborator"] = "viewer"

class ProjectShareResponse(BaseModel):
    id: str
    project_id: str
    user_id: str
    username: str
    email: str
    permission: str
    created_at: datetime
```

---

## 四、后端认证架构

### 4.1 认证流程

```
用户注册:
  POST /api/v1/auth/register
    → 校验 email 唯一性
    → bcrypt hash 密码
    → 创建 User 记录
    → 签发 access_token + refresh_token
    → 返回 TokenResponse

用户登录:
  POST /api/v1/auth/login
    → 校验 email + password
    → 更新 last_login_at
    → 签发 access_token + refresh_token
    → 记录 audit_log (action='login')
    → 返回 TokenResponse

Token 刷新:
  POST /api/v1/auth/refresh
    → 校验 refresh_token 有效性 (未过期/未撤销)
    → 撤销旧 refresh_token (一次性使用)
    → 签发新 access_token + refresh_token
    → 返回 TokenResponse

登出:
  POST /api/v1/auth/logout
    → 撤销当前 refresh_token
    → 返回 204
```

### 4.2 JWT Payload 结构

```json
{
    "sub": "user-uuid",
    "email": "user@example.com",
    "role": "user",
    "iat": 1711800000,
    "exp": 1711803600
}
```

### 4.3 认证中间件

```python
# app/api/deps.py 扩展

async def get_current_user(
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db),
) -> User:
    """从 Bearer Token 提取并验证当前用户"""
    # 1. 解析 Bearer Token
    # 2. 验证 JWT 签名和有效期
    # 3. 从 DB 查询 user (is_active=True)
    # 4. 返回 User 对象 或 抛出 401

async def get_current_user_optional(
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """可选认证 — 兼容 v0.3 无 Token 的调用"""

def require_role(role: str):
    """角色检查装饰器"""
    async def check(user: User = Depends(get_current_user)) -> User:
        if user.role != role and user.role != "admin":
            raise HTTPException(403, "权限不足")
        return user
    return check

async def check_project_access(
    project_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    min_permission: str = "viewer",
) -> Project:
    """项目级权限检查 — owner / shared / admin"""
    # 1. 查询项目
    # 2. 检查: user_id == project.user_id (owner)
    #    或 project_shares 表中有记录且 permission >= min_permission
    #    或 user.role == 'admin'
    # 3. 返回 Project 或抛出 403/404
```

### 4.4 现有 API 改造

所有现有 API 路由需注入 `current_user` 依赖:

| 路由文件      | 改造内容                                              |
| ------------- | ----------------------------------------------------- |
| `projects.py` | 列表接口过滤 `user_id`; 详情/修改/删除检查 owner 权限 |
| `workflow.py` | start/resume/cancel 检查 collaborator 权限            |
| `papers.py`   | 通过 project_id 间接检查权限; 上传需 collaborator     |
| `outputs.py`  | 通过 project_id 间接检查权限; 导出需 viewer 权限      |
| `events.py`   | SSE 连接需验证项目访问权限                            |

**向后兼容策略**: 初期支持 `get_current_user_optional`，配置项 `AUTH_REQUIRED=false` 时不强制认证（方便开发/CLI 场景）。正式启用后改为 `AUTH_REQUIRED=true`。

---

## 五、可视化设计

### 5.1 知识图谱交互设计

#### 数据映射

| 视觉属性 | 数据字段          | 映射规则                                         |
| -------- | ----------------- | ------------------------------------------------ |
| 节点大小 | `citation_count`  | `r = 5 + log2(citations + 1) * 4` (5-25px)       |
| 节点颜色 | `cluster_id`      | 聚类调色板 (categorical10)                       |
| 节点形状 | `role`            | foundational=⭐, bridge=◆, recent=●, peripheral=○ |
| 节点标签 | `title` (截断)    | 鼠标悬停显示完整标题                             |
| 边方向   | `source → target` | 箭头标识引用方向                                 |
| 边粗细   | `relation`        | cites=1px, extends/applies=2px, refutes=2px虚线  |
| 边颜色   | `relation`        | cites=灰, extends=蓝, refutes=红, applies=绿     |
| 聚类分组 | `topic_clusters`  | 半透明凸包背景色                                 |

#### 交互行为

| 交互         | 行为                                                    |
| ------------ | ------------------------------------------------------- |
| 缩放         | 鼠标滚轮 / 双指缩放 (0.1x - 4x)                         |
| 平移         | 鼠标拖拽空白区域                                        |
| 节点悬停     | Tooltip: 论文标题、年份、被引数、所属聚类、角色         |
| 节点点击     | 右侧弹出论文详情面板 (Paper Detail Drawer)              |
| 节点拖拽     | 力导向布局中可拖拽固定节点位置                          |
| 聚类图例点击 | 高亮/灰化对应聚类的节点和边                             |
| 右键菜单     | "聚焦此节点" (仅显示 1-hop 邻居)、"查看原文" (跳转外链) |
| 搜索         | 输入框模糊搜索论文标题，匹配节点高亮并居中              |
| 导出         | "导出为 SVG" / "导出为 PNG" 按钮                        |

#### 布局算法

```
D3 Force Simulation 参数:
  forceLink:    distance = 80, strength = 0.3
  forceManyBody: strength = -200 (斥力)
  forceCenter:  x = width/2, y = height/2
  forceCollide: radius = node_size + 5 (防重叠)
  alphaDecay:   0.02 (收敛速度)
  velocityDecay: 0.4 (阻尼)
```

### 5.2 时间线交互设计

#### 数据映射

复用 v0.3 已有的 `timeline` + `research_trends.by_year` 数据。

```
时间轴结构:
  ┌──────────────────────────────────────────────────────────┐
  │  2018    2019    2020    2021    2022    2023    2024    │  ← 年份刻度
  │   │       │      │★      │       │      │★★     │       │  ← 里程碑标记
  │   ●       ●●     ●●●●    ●●●●●   ●●●●●● ●●●●●●●●●      │  ← 论文气泡
  │   3       5      12      15      18     25      8       │  ← 年度论文数
  └──────────────────────────────────────────────────────────┘
```

| 视觉属性   | 数据字段                        | 映射规则                       |
| ---------- | ------------------------------- | ------------------------------ |
| X 轴位置   | `year`                          | 线性映射到画布宽度             |
| 气泡大小   | `paper_count`                   | `r = sqrt(count) * 6` (6-30px) |
| 气泡颜色   | 主导聚类                        | 与图谱聚类色一致               |
| 里程碑标记 | `milestone` (非 null)           | ★ 星形标记 + 弹出说明          |
| 趋势线     | `research_trends.by_year.count` | 折线叠加在时间轴上方           |
| 主题线     | `research_trends.by_topic`      | 多条彩色折线，可按主题切换显隐 |

#### 交互行为

| 交互       | 行为                                          |
| ---------- | --------------------------------------------- |
| 年份悬停   | 展开该年论文列表气泡，每个气泡为一篇论文      |
| 年份点击   | 右侧面板过滤显示该年论文列表                  |
| 里程碑悬停 | Tooltip: 里程碑名称 + 关键事件描述            |
| 里程碑点击 | 高亮相关论文，知识图谱联动高亮对应节点        |
| 主题筛选   | 顶部主题复选框，选中/取消主题后时间线动态过滤 |
| 缩放       | 鼠标滚轮水平缩放，聚焦时间范围                |
| 导出       | "导出为 SVG" / "导出为 PNG" 按钮              |

### 5.3 趋势图增强

将 v0.3 的 CSS 柱状图 (`TrendChart.tsx`) 升级为 D3.js 交互式折线图:

| 功能     | 当前 (v0.3)              | 升级 (v0.4)                      |
| -------- | ------------------------ | -------------------------------- |
| 年度趋势 | CSS 柱状图 (无交互)      | D3 折线/柱状图，悬停显示精确数值 |
| 主题趋势 | 文字列表 (rising/stable) | 多系列折线图，点击切换显隐       |
| 新兴主题 | 标签列表                 | 气泡图 (大小=增长率, 颜色=主题)  |
| 导出     | 无                       | SVG/PNG 导出                     |

### 5.4 图谱-时间线联动

两个可视化组件之间支持联动交互:

| 触发组件 | 操作       | 联动响应                           |
| -------- | ---------- | ---------------------------------- |
| 知识图谱 | 选中节点   | 时间线高亮对应年份的气泡           |
| 知识图谱 | 筛选聚类   | 时间线仅显示该聚类论文的趋势       |
| 时间线   | 选中年份   | 知识图谱高亮该年论文节点，其余灰化 |
| 时间线   | 选中里程碑 | 知识图谱聚焦里程碑相关论文子图     |

联动通过 Zustand store 的 `visualizationStore` 共享选中状态实现。

---

## 六、API 新增端点

### 6.1 认证 API `/api/v1/auth/`

| 方法 | 路径             | 说明                | 认证 |
| ---- | ---------------- | ------------------- | ---- |
| POST | `/auth/register` | 注册新用户          | 无   |
| POST | `/auth/login`    | 用户登录            | 无   |
| POST | `/auth/refresh`  | 刷新 Token          | 无   |
| POST | `/auth/logout`   | 登出 (撤销 refresh) | 是   |

### 6.2 用户 API `/api/v1/users/`

| 方法   | 路径                 | 说明                  | 认证 |
| ------ | -------------------- | --------------------- | ---- |
| GET    | `/users/me`          | 获取当前用户信息      | 是   |
| PATCH  | `/users/me`          | 更新当前用户信息      | 是   |
| PUT    | `/users/me/password` | 修改密码              | 是   |
| GET    | `/users/`            | 用户列表 (admin only) | 是   |
| PATCH  | `/users/{id}`        | 修改用户 (admin only) | 是   |
| DELETE | `/users/{id}`        | 停用用户 (admin only) | 是   |

### 6.3 项目分享 API `/api/v1/projects/{id}/shares/`

| 方法   | 路径                          | 说明           | 认证 |
| ------ | ----------------------------- | -------------- | ---- |
| POST   | `/projects/{id}/shares`       | 分享项目给用户 | 是   |
| GET    | `/projects/{id}/shares`       | 列出项目的共享 | 是   |
| PATCH  | `/projects/{id}/shares/{sid}` | 修改共享权限   | 是   |
| DELETE | `/projects/{id}/shares/{sid}` | 撤销共享       | 是   |

### 6.4 可视化 API `/api/v1/projects/{id}/visualizations/`

| 方法 | 路径                                     | 说明             | 认证 |
| ---- | ---------------------------------------- | ---------------- | ---- |
| GET  | `/projects/{id}/visualizations/graph`    | 获取知识图谱数据 | 是   |
| GET  | `/projects/{id}/visualizations/timeline` | 获取时间线数据   | 是   |
| GET  | `/projects/{id}/visualizations/trends`   | 获取趋势数据     | 是   |

> 可视化 API 本质是从 `ReviewState` 中提取 `citation_network` / `timeline` / `research_trends` 字段，前端也可直接从现有 SSE 事件获取。独立 API 便于按需获取和缓存。

---

## 七、实施阶段分解

### 阶段 1: 后端认证基础

| #    | 任务                    | 输出文件                              | 说明                                                       |
| ---- | ----------------------- | ------------------------------------- | ---------------------------------------------------------- |
| 1.1  | 认证配置项              | `app/config.py`                       | JWT_SECRET_KEY, JWT_ALGORITHM, JWT_EXPIRY_*, AUTH_REQUIRED |
| 1.2  | User ORM 模型           | `app/models/user.py`                  | users 表 + password hash + preferences JSON                |
| 1.3  | RefreshToken ORM 模型   | `app/models/refresh_token.py`         | refresh_tokens 表 + token_hash + expires_at                |
| 1.4  | User Pydantic Schema    | `app/schemas/user.py`                 | Register / Login / Response / Update / Token 等            |
| 1.5  | Alembic 迁移脚本        | `alembic/versions/v04_auth_tables.py` | 创建 users + refresh_tokens + audit_log 表                 |
| 1.6  | 密码安全工具            | `app/services/auth.py`                | bcrypt hash/verify + JWT encode/decode + token 生成        |
| 1.7  | 认证依赖注入            | `app/api/deps.py` (修改)              | get_current_user / get_current_user_optional               |
| 1.8  | 认证 API 路由           | `app/api/routes/auth.py`              | register / login / refresh / logout 4 个端点               |
| 1.9  | models/__init__.py 更新 | `app/models/__init__.py` (修改)       | 导出新模型                                                 |
| 1.10 | 单元测试                | `tests/test_auth.py`                  | 密码 hash、JWT 编解码、注册/登录/刷新/登出流程             |

#### 验收标准

- [ ] 注册新用户返回 JWT Token，密码以 bcrypt 存储
- [ ] 登录成功返回 access_token + refresh_token
- [ ] access_token 过期后通过 refresh 获取新 Token
- [ ] refresh_token 一次性使用（旋转）
- [ ] 无效/过期 Token 返回 401
- [ ] `AUTH_REQUIRED=false` 时现有 API 不受影响

### 阶段 2: 权限控制与项目隔离

| #    | 任务                    | 输出文件                                 | 说明                                               |
| ---- | ----------------------- | ---------------------------------------- | -------------------------------------------------- |
| 2.1  | ProjectShare ORM 模型   | `app/models/project_share.py`            | project_shares 表                                  |
| 2.2  | AuditLog ORM 模型       | `app/models/audit_log.py`                | audit_log 表                                       |
| 2.3  | 项目权限检查器          | `app/api/deps.py` (修改)                 | check_project_access() + require_role()            |
| 2.4  | ProjectShare Schema     | `app/schemas/share.py`                   | Create / Response                                  |
| 2.5  | Alembic 迁移 — 分享表   | `alembic/versions/v04_sharing_tables.py` | 创建 project_shares 表 + projects.user_id NOT NULL |
| 2.6  | 项目分享 API            | `app/api/routes/shares.py`               | 分享/列表/修改/撤销 4 个端点                       |
| 2.7  | 用户管理 API            | `app/api/routes/users.py`                | me/列表/修改/停用 6 个端点                         |
| 2.8  | 现有路由改造 — projects | `app/api/routes/projects.py` (修改)      | 注入 get_current_user，列表过滤 user_id            |
| 2.9  | 现有路由改造 — workflow | `app/api/routes/workflow.py` (修改)      | 注入项目权限检查 (collaborator)                    |
| 2.10 | 现有路由改造 — papers   | `app/api/routes/papers.py` (修改)        | 注入项目权限检查                                   |
| 2.11 | 现有路由改造 — outputs  | `app/api/routes/outputs.py` (修改)       | 注入项目权限检查 (viewer)                          |
| 2.12 | 现有路由改造 — events   | `app/api/routes/events.py` (修改)        | SSE 连接验证项目访问权限                           |
| 2.13 | 审计日志服务            | `app/services/audit.py`                  | log_action() 记录关键操作                          |
| 2.14 | 路由注册                | `app/main.py` (修改)                     | 添加 auth/users/shares 路由                        |
| 2.15 | 单元测试                | `tests/test_permissions.py`              | 权限矩阵测试、项目隔离测试                         |

#### 验收标准

- [ ] 用户 A 无法访问用户 B 的项目 (403)
- [ ] admin 可以访问任何用户的项目
- [ ] 分享后被分享用户可按权限级别操作
- [ ] 撤销分享后被分享用户即时失去访问权
- [ ] 现有 API 在 `AUTH_REQUIRED=true` 时均需要 Token
- [ ] 审计日志记录关键操作 (登录/创建项目/分享)

### 阶段 3: 前端认证 UI

| #    | 任务                 | 输出文件                                     | 说明                                                   |
| ---- | -------------------- | -------------------------------------------- | ------------------------------------------------------ |
| 3.1  | Auth API 层          | `src/api/auth.ts`                            | register / login / refresh / logout / getMe API 调用   |
| 3.2  | Auth Store           | `src/stores/authStore.ts`                    | Zustand: user / token / isAuthenticated / login/logout |
| 3.3  | Auth 类型定义        | `src/types/user.ts`                          | User / TokenResponse / LoginRequest / RegisterRequest  |
| 3.4  | Axios 拦截器         | `src/api/client.ts` (修改)                   | 请求拦截注入 Bearer Token, 401 响应拦截自动刷新        |
| 3.5  | 登录页面             | `src/pages/LoginPage.tsx`                    | 邮箱 + 密码表单，登录/注册切换                         |
| 3.6  | 路由守卫             | `src/components/Common/ProtectedRoute.tsx`   | 未登录重定向到 /login                                  |
| 3.7  | 用户菜单             | `src/components/Layout/UserMenu.tsx`         | 头像下拉: 个人信息、设置、登出                         |
| 3.8  | 个人设置页面         | `src/pages/SettingsPage.tsx`                 | 修改用户名/密码、偏好设置                              |
| 3.9  | App.tsx 路由更新     | `src/App.tsx` (修改)                         | 添加 /login, /settings 路由 + ProtectedRoute 包裹      |
| 3.10 | AppLayout 更新       | `src/components/Layout/AppLayout.tsx` (修改) | 顶部栏添加 UserMenu                                    |
| 3.11 | 项目分享 UI          | `src/components/Project/ShareDialog.tsx`     | 分享对话框: 邮箱输入 + 权限选择                        |
| 3.12 | Share API 层         | `src/api/shares.ts`                          | share / list / revoke API 调用                         |
| 3.13 | 分享类型定义         | `src/types/share.ts`                         | ShareCreate / ShareResponse 类型                       |
| 3.14 | ProjectPage 分享入口 | `src/pages/ProjectPage.tsx` (修改)           | 顶部工具栏添加「分享」按钮                             |
| 3.15 | 前端依赖             | `package.json` (修改)                        | 新增 `jwt-decode` 用于 Token 过期检测                  |

#### 验收标准

- [ ] 未登录用户自动跳转到 /login 页面
- [ ] 注册 → 登录 → 创建项目 → 退出登录流程完整
- [ ] Token 过期后页面自动刷新 Token 或跳转重新登录
- [ ] 用户菜单显示当前用户名和头像
- [ ] 项目分享对话框可添加/移除协作者
- [ ] 被分享的项目出现在首页项目列表中 (标记 "共享")

### 阶段 4: 交互式知识图谱

| #    | 任务                   | 输出文件                                             | 说明                                                       |
| ---- | ---------------------- | ---------------------------------------------------- | ---------------------------------------------------------- |
| 4.1  | D3.js 依赖安装         | `package.json` (修改)                                | `d3` + `@types/d3`                                         |
| 4.2  | useD3 Hook             | `src/hooks/useD3.ts`                                 | D3.js + React ref 集成 Hook，管理 SVG 生命周期             |
| 4.3  | 可视化 Store           | `src/stores/visualizationStore.ts`                   | Zustand: 选中节点/高亮聚类/联动状态/时间范围               |
| 4.4  | 可视化类型定义         | `src/types/visualization.ts`                         | GraphNode / GraphEdge / TimelineEvent / VisualizationState |
| 4.5  | KnowledgeGraph 组件    | `src/components/Visualization/KnowledgeGraph.tsx`    | D3 力导向图: 节点渲染、边渲染、聚类凸包、Tooltip           |
| 4.6  | GraphControls 组件     | `src/components/Visualization/GraphControls.tsx`     | 缩放控制、聚类图例、搜索框、导出按钮                       |
| 4.7  | PaperDetailDrawer 组件 | `src/components/Visualization/PaperDetailDrawer.tsx` | 节点点击弹出的论文详情抽屉                                 |
| 4.8  | SVG 导出工具           | `src/utils/export-svg.ts`                            | SVG → PNG 转换、下载触发                                   |
| 4.9  | 可视化 API 层          | `src/api/visualizations.ts`                          | 获取 graph / timeline / trends 数据                        |
| 4.10 | ProjectPage 集成       | `src/pages/ProjectPage.tsx` (修改)                   | 右侧面板「图谱」Tab 集成 KnowledgeGraph                    |

#### 验收标准

- [ ] 力导向图正确渲染论文节点和引用关系边
- [ ] 节点大小映射被引数，颜色映射聚类
- [ ] 鼠标悬停显示 Tooltip (标题/年份/被引数)
- [ ] 节点点击弹出论文详情 Drawer
- [ ] 聚类图例点击可高亮/灰化对应聚类
- [ ] 支持缩放/平移/节点拖拽
- [ ] 搜索框可模糊匹配论文并高亮居中
- [ ] "导出 SVG" / "导出 PNG" 功能正常

### 阶段 5: 交互式时间线与趋势图

| #   | 任务                     | 输出文件                                               | 说明                                      |
| --- | ------------------------ | ------------------------------------------------------ | ----------------------------------------- |
| 5.1 | InteractiveTimeline 组件 | `src/components/Visualization/InteractiveTimeline.tsx` | D3 时间轴: 年份气泡、里程碑标记、论文展开 |
| 5.2 | TrendLineChart 组件      | `src/components/Visualization/TrendLineChart.tsx`      | D3 多系列折线图替代 CSS 柱状图            |
| 5.3 | TopicBubbleChart 组件    | `src/components/Visualization/TopicBubbleChart.tsx`    | 新兴主题气泡图                            |
| 5.4 | 图谱-时间线联动逻辑      | `src/stores/visualizationStore.ts` (修改)              | 选中状态同步: 图谱选中 ↔ 时间线高亮       |
| 5.5 | VisualizationPanel 容器  | `src/components/Visualization/VisualizationPanel.tsx`  | 标签页切换: 图谱 / 时间线 / 趋势          |
| 5.6 | ProjectPage 集成         | `src/pages/ProjectPage.tsx` (修改)                     | 右侧面板替换为 VisualizationPanel         |
| 5.7 | TrendChart 替换          | `src/components/Analysis/TrendChart.tsx` (修改)        | 内部改用 TrendLineChart 组件              |

#### 验收标准

- [ ] 时间线正确显示年度论文数量气泡和里程碑标记
- [ ] 年份悬停展开该年论文列表
- [ ] 里程碑点击联动知识图谱高亮关键论文
- [ ] 趋势折线图支持按主题筛选、悬停显示精确数值
- [ ] 新兴主题气泡图正确展示增长率
- [ ] 图谱与时间线联动: 选中图谱节点 → 时间线高亮对应年份
- [ ] 所有图表支持 SVG/PNG 导出

### 阶段 6: knowledge_map + timeline 输出类型

| #   | 任务                   | 输出文件                                         | 说明                                                    |
| --- | ---------------------- | ------------------------------------------------ | ------------------------------------------------------- |
| 6.1 | 可视化导出后端         | `app/services/export.py` (修改)                  | knowledge_map → SVG/HTML 导出; timeline → SVG/HTML 导出 |
| 6.2 | knowledge_map 生成节点 | `app/agents/export_node.py` (修改)               | output_types 含 knowledge_map 时生成 structured_data    |
| 6.3 | timeline 生成节点      | `app/agents/export_node.py` (修改)               | output_types 含 timeline 时生成 structured_data         |
| 6.4 | 输出类型前端解锁       | `src/utils/constants.ts` (修改)                  | ALL_OUTPUT_TYPES 新增 knowledge_map + timeline          |
| 6.5 | ReviewPreview 渲染     | `src/components/Review/ReviewPreview.tsx` (修改) | knowledge_map/timeline 输出渲染为交互组件               |
| 6.6 | 单元测试               | `tests/test_export_viz.py`                       | 可视化输出类型生成和导出测试                            |

#### 验收标准

- [ ] 用户可在创建项目时选择 knowledge_map / timeline 输出类型
- [ ] 工作流完成后 knowledge_map 输出的 structured_data 含完整图数据
- [ ] timeline 输出的 structured_data 含完整时间线数据
- [ ] 导出 API 支持 SVG 和 HTML 格式导出可视化
- [ ] ReviewPreview 页面正确渲染可视化输出

### 阶段 7: 端到端测试与文档

| #   | 任务                | 输出文件                        | 说明                                         |
| --- | ------------------- | ------------------------------- | -------------------------------------------- |
| 7.1 | 认证 E2E 测试       | `tests/test_e2e_auth.py`        | 注册→登录→创建项目→分享→协作者访问 全流程    |
| 7.2 | 权限 E2E 测试       | `tests/test_e2e_permissions.py` | 跨用户隔离、权限升级/降级、admin 特权        |
| 7.3 | 可视化 E2E 测试     | `tests/test_e2e_v04.py`         | 完整工作流 + knowledge_map/timeline 输出生成 |
| 7.4 | 前端构建验证        | —                               | TypeScript 零错误 + 生产构建通过             |
| 7.5 | Docker Compose 更新 | `docker-compose.yml` (修改)     | 新增 JWT_SECRET_KEY 环境变量                 |
| 7.6 | .env.example 更新   | `.env.example` (修改)           | 新增认证相关配置项                           |
| 7.7 | README 更新         | `README.md` (修改)              | 多用户使用说明、首次管理员账号创建           |
| 7.8 | CHANGELOG 更新      | `docs/dev/CHANGELOG.md` (修改)  | v0.4 变更记录                                |

#### 验收标准

- [ ] 多用户场景 E2E 测试通过: 用户注册 → 项目隔离 → 分享协作
- [ ] 可视化输出类型 E2E 测试通过
- [ ] `docker compose up` 首次启动自动创建 admin 用户
- [ ] 前端构建零错误，gzip < 600KB
- [ ] README 可指导用户完成多用户配置

---

## 八、文件产出清单

```
backend/
├── app/
│   ├── config.py                              # [阶段 1] 修改 (新增 JWT 配置项)
│   ├── main.py                                # [阶段 2] 修改 (注册新路由)
│   ├── models/
│   │   ├── __init__.py                        # [阶段 1] 修改 (导出新模型)
│   │   ├── user.py                            # [阶段 1] 新增
│   │   ├── refresh_token.py                   # [阶段 1] 新增
│   │   ├── project_share.py                   # [阶段 2] 新增
│   │   └── audit_log.py                       # [阶段 2] 新增
│   ├── schemas/
│   │   ├── user.py                            # [阶段 1] 新增
│   │   └── share.py                           # [阶段 2] 新增
│   ├── services/
│   │   ├── auth.py                            # [阶段 1] 新增
│   │   ├── audit.py                           # [阶段 2] 新增
│   │   └── export.py                          # [阶段 6] 修改 (可视化导出)
│   ├── api/
│   │   ├── deps.py                            # [阶段 1+2] 修改 (认证依赖)
│   │   └── routes/
│   │       ├── auth.py                        # [阶段 1] 新增
│   │       ├── users.py                       # [阶段 2] 新增
│   │       ├── shares.py                      # [阶段 2] 新增
│   │       ├── visualizations.py              # [阶段 6] 新增
│   │       ├── projects.py                    # [阶段 2] 修改 (注入认证)
│   │       ├── workflow.py                    # [阶段 2] 修改 (注入认证)
│   │       ├── papers.py                      # [阶段 2] 修改 (注入认证)
│   │       ├── outputs.py                     # [阶段 2] 修改 (注入认证)
│   │       └── events.py                      # [阶段 2] 修改 (注入认证)
│   └── agents/
│       └── export_node.py                     # [阶段 6] 修改 (可视化输出)
├── alembic/versions/
│   ├── v04_auth_tables.py                     # [阶段 1] 新增
│   └── v04_sharing_tables.py                  # [阶段 2] 新增
├── tests/
│   ├── test_auth.py                           # [阶段 1] 新增
│   ├── test_permissions.py                    # [阶段 2] 新增
│   ├── test_e2e_auth.py                       # [阶段 7] 新增
│   ├── test_e2e_permissions.py                # [阶段 7] 新增
│   ├── test_e2e_v04.py                        # [阶段 7] 新增
│   └── test_export_viz.py                     # [阶段 6] 新增

frontend/src/
├── api/
│   ├── client.ts                              # [阶段 3] 修改 (Token 拦截器)
│   ├── auth.ts                                # [阶段 3] 新增
│   ├── shares.ts                              # [阶段 3] 新增
│   └── visualizations.ts                      # [阶段 4] 新增
├── stores/
│   ├── authStore.ts                           # [阶段 3] 新增
│   └── visualizationStore.ts                  # [阶段 4] 新增
├── types/
│   ├── user.ts                                # [阶段 3] 新增
│   ├── share.ts                               # [阶段 3] 新增
│   └── visualization.ts                       # [阶段 4] 新增
├── pages/
│   ├── LoginPage.tsx                          # [阶段 3] 新增
│   ├── SettingsPage.tsx                       # [阶段 3] 新增
│   └── ProjectPage.tsx                        # [阶段 4+5] 修改
├── hooks/
│   └── useD3.ts                               # [阶段 4] 新增
├── components/
│   ├── Common/
│   │   └── ProtectedRoute.tsx                 # [阶段 3] 新增
│   ├── Layout/
│   │   ├── UserMenu.tsx                       # [阶段 3] 新增
│   │   └── AppLayout.tsx                      # [阶段 3] 修改
│   ├── Project/
│   │   └── ShareDialog.tsx                    # [阶段 3] 新增
│   ├── Visualization/
│   │   ├── KnowledgeGraph.tsx                 # [阶段 4] 新增
│   │   ├── GraphControls.tsx                  # [阶段 4] 新增
│   │   ├── PaperDetailDrawer.tsx              # [阶段 4] 新增
│   │   ├── InteractiveTimeline.tsx            # [阶段 5] 新增
│   │   ├── TrendLineChart.tsx                 # [阶段 5] 新增
│   │   ├── TopicBubbleChart.tsx               # [阶段 5] 新增
│   │   └── VisualizationPanel.tsx             # [阶段 5] 新增
│   ├── Analysis/
│   │   └── TrendChart.tsx                     # [阶段 5] 修改 (内部替换为 D3)
│   └── Review/
│       └── ReviewPreview.tsx                  # [阶段 6] 修改
├── utils/
│   ├── export-svg.ts                          # [阶段 4] 新增
│   └── constants.ts                           # [阶段 6] 修改
├── App.tsx                                    # [阶段 3] 修改 (新增路由)
└── package.json                               # [阶段 3+4] 修改 (新增依赖)

# 项目根目录
├── docker-compose.yml                         # [阶段 7] 修改
├── .env.example                               # [阶段 7] 修改
└── README.md                                  # [阶段 7] 修改

# 新增文件: ~35 个
# 修改文件: ~20 个
```

---

## 九、依赖关系

```
阶段 1 (后端认证基础) ──▶ 阶段 2 (权限控制 + 项目隔离) ──▶ 阶段 3 (前端认证 UI)
                                      │
                                      ▼
                              阶段 4 (知识图谱) ──▶ 阶段 5 (时间线 + 趋势图)
                                      │                        │
                                      └────────┬───────────────┘
                                               ▼
                                      阶段 6 (输出类型解锁)
                                               │
                                               ▼
                                      阶段 7 (E2E 测试 + 文档)
```

- **阶段 1 → 2 → 3 串行**: 认证基础 → 权限层 → 前端 UI，强依赖
- **阶段 3 完成后，阶段 4 可开始**: 前端认证就绪后开始可视化开发
- **阶段 4 → 5 弱依赖**: 时间线可与图谱并行, 但联动逻辑需阶段 4 先就绪
- **阶段 6 依赖 4 + 5**: 页面集成需组件就绪
- **阶段 7 依赖全部**: 端到端测试

```
并行机会:
  阶段 2 期间可提前开始阶段 4.1-4.4 (D3 依赖、类型定义、Hook)
  阶段 4 和 5 的组件开发可部分并行
```

---

## 十、配置变更

### 10.1 新增配置项

```python
# app/config.py 新增
class Settings(BaseSettings):
    # ── 认证 ──
    JWT_SECRET_KEY: str = ""               # 必需: JWT 签名密钥 (≥32 字符随机字符串)
    JWT_ALGORITHM: str = "HS256"           # JWT 签名算法
    JWT_ACCESS_EXPIRY_MINUTES: int = 60    # Access Token 有效期 (分钟)
    JWT_REFRESH_EXPIRY_DAYS: int = 7       # Refresh Token 有效期 (天)
    AUTH_REQUIRED: bool = False            # 是否强制认证 (False = 兼容 v0.3 无认证模式)
    ADMIN_EMAIL: str = ""                  # 首次启动自动创建管理员 (email)
    ADMIN_PASSWORD: str = ""               # 首次启动自动创建管理员 (密码)
    BCRYPT_ROUNDS: int = 12               # bcrypt cost factor
```

### 10.2 .env.example 更新

```bash
# ── 认证 (v0.4 新增) ──
JWT_SECRET_KEY=your-secret-key-at-least-32-chars  # 必需
AUTH_REQUIRED=false                                # true 启用多用户认证
ADMIN_EMAIL=admin@example.com                      # 首次启动创建管理员
ADMIN_PASSWORD=changeme                            # 首次管理员密码 (请修改)
```

### 10.3 前端新增依赖

```json
{
    "dependencies": {
        "d3": "^7.9.0",
        "jwt-decode": "^4.0.0"
    },
    "devDependencies": {
        "@types/d3": "^7.4.0"
    }
}
```

---

## 十一、技术风险

| 风险                               | 影响 | 缓解策略                                                                 |
| ---------------------------------- | ---- | ------------------------------------------------------------------------ |
| JWT 密钥泄露导致伪造 Token         | 高   | 密钥仅通过环境变量传递，不入代码仓库；生产环境使用 ≥256bit 随机密钥      |
| Refresh Token 被窃取导致持久访问   | 高   | 一次性旋转策略；检测异常刷新模式 (同一 refresh 多次使用时撤销所有 Token) |
| 密码暴力破解                       | 中   | bcrypt (cost 12) 减缓尝试速度；后续可加登录速率限制                      |
| D3.js + React 集成内存泄漏         | 中   | useD3 Hook 在 cleanup 中移除 SVG 元素和事件监听；StrictMode 双渲染测试   |
| 大规模图谱性能 (>200 节点)         | 中   | 超过 200 节点时启用 Canvas 渲染替代 SVG；分层聚类视图                    |
| 现有 API 向后兼容性                | 中   | AUTH_REQUIRED=false 默认值保持向后兼容；CLI 场景支持 API Key 认证        |
| Alembic 迁移 user_id NOT NULL 冲突 | 低   | 迁移脚本先创建默认用户，再将存量 project 的 user_id 指向默认用户         |
| 前端包体积增长 (D3.js ~30KB gzip)  | 低   | D3 模块化导入 (只引入 d3-force, d3-selection 等需要的子包)               |

---

## 十二、安全设计要点

### 12.1 密码安全

- 密码长度要求: 8-128 字符
- 存储: bcrypt hash (cost factor 12)
- 传输: HTTPS (生产环境)
- 登录响应不透露 "邮箱不存在" vs "密码错误" 差异（统一返回 "邮箱或密码错误"）

### 12.2 Token 安全

- Access Token: 短有效期 (1h)、不存储于后端
- Refresh Token: 一次性使用、SHA-256 hash 存储、支持跨设备撤销
- 检测 Token 重用: 同一 Refresh Token 被第二次使用时，撤销该用户的所有 Refresh Token（可能被窃取）
- 前端 Token 存储: `localStorage` (SPA 场景，非 cookie)

### 12.3 权限安全

- 所有 API 路由的权限检查在 FastAPI Depends 层面强制执行
- 禁止客户端传递 user_id 来伪造身份（从 JWT 中提取）
- 项目列表 API 始终附加 user_id 过滤条件
- admin 路由独立检查角色

### 12.4 输入校验

- 邮箱格式: Pydantic `EmailStr` 校验
- 用户名: 2-50 字符，禁止特殊字符
- 密码: 8-128 字符
- 分享邮箱: 校验用户存在性

---

## 十三、后续迭代规划 (v0.4 之后)

| 版本 | 主要内容                | 关键新增                                            |
| ---- | ----------------------- | --------------------------------------------------- |
| v0.5 | PostgreSQL + 更多数据源 | 数据库迁移、OpenAlex/PubMed 适配器、Update Agent    |
| v0.6 | OAuth + 团队管理        | Google/GitHub SSO、Team/Organization 模型、团队配额 |
| v0.7 | 性能优化                | Canvas 渲染大规模图谱、增量更新、批量操作、查询优化 |
| v1.0 | 生产就绪                | K8s 部署、HTTPS、负载均衡、完善监控、多语言 i18n    |
