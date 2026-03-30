# 前端 MVP v0.2 实施计划

> **文档版本**: v1.0
> **创建日期**: 2026-03-30
> **前置文档**: [产品 UX 设计](../design/product-delivery-and-ux.md) · [系统架构](../design/system-architecture.md) · [后端实施计划](implementation-plan.md)
> **目标**: 基于 UX 设计文档和已完成的后端 API，将前端 MVP v0.2 分解为可执行的实施阶段与任务清单

---

## 一、MVP v0.2 前端范围

### 1.1 功能范围

根据 UX 设计文档 §9.2 (MVP v0.2 — 简易 Web 界面)，前端需实现：

| 功能           | 说明                                                  | 对接后端 API                                 |
| -------------- | ----------------------------------------------------- | -------------------------------------------- |
| 对话式输入     | Web 端对话框输入研究问题                              | `POST /api/v1/projects`                      |
| 文件上传       | 支持上传 PDF / .bib / .ris 文件                       | `POST /api/v1/projects/{id}/papers/upload`   |
| 输出类型选择   | Quick Brief / Annotated Bib / Full Review             | `ProjectCreate.output_types`                 |
| Agent 状态面板 | 实时显示各 Agent 工作状态、进度和 Token 消耗          | `GET /api/v1/projects/{id}/events` (SSE)     |
| 论文列表       | 可勾选的候选论文列表，含全文状态和相关度              | `GET /api/v1/projects/{id}/papers`           |
| 渐进式精读结果 | 每完成一篇即展示，无需等待全部完成                    | SSE `paper_read` 事件                        |
| 引用验证标识   | 综述预览中展示引用验证状态                            | `ReviewOutputResponse.citation_verification` |
| 综述预览       | Markdown 渲染预览，支持导出（含 BibTeX/RIS）          | `GET /api/v1/projects/{id}/outputs/{oid}`    |
| 项目管理       | 新建 / 列表 / 删除 / 中断恢复                         | 项目 CRUD API                                |
| 异常状态提示   | 数据源异常、空结果、预算超限等状态的友好提示          | SSE `error`/`warning` 事件                   |
| HITL 交互      | 检索确认 / 大纲审阅 / 初稿审阅 3 个 Human-in-the-loop | `POST /api/v1/projects/{id}/workflow/resume` |

### 1.2 不包含 (完整版延期)

| 不包含                 | 延期到 |
| ---------------------- | ------ |
| 分析看板（图表可视化） | v0.3+  |
| 综述富文本编辑器       | v0.3+  |
| 版本历史 / 撤销重做    | v0.3+  |
| 知识图谱可交互视图     | v0.4+  |
| 文献订阅与推送通知     | v0.5+  |
| 多用户 / 团队协作      | v0.4+  |
| 移动端响应式适配       | v0.4+  |
| 新手引导 (Onboarding)  | v0.3+  |
| 快速开始模板           | v0.3+  |

### 1.3 技术栈

| 层次        | 技术                           | 说明                          |
| ----------- | ------------------------------ | ----------------------------- |
| 构建工具    | Vite                           | 快速开发/构建，React 社区主流 |
| UI 框架     | React 18+                      | 设计文档指定                  |
| 组件库      | Ant Design 5.x                 | 设计文档指定，企业级组件丰富  |
| 路由        | React Router v6                | SPA 路由                      |
| 状态管理    | Zustand                        | 轻量，适合中小型应用          |
| HTTP 客户端 | Axios                          | 拦截器、错误处理              |
| SSE 客户端  | EventSource API                | 浏览器原生 SSE 支持           |
| Markdown    | react-markdown + remark-gfm    | Markdown 渲染                 |
| 语言        | TypeScript                     | 类型安全                      |
| CSS 方案    | Ant Design Token + CSS Modules | 主题定制 + 局部样式隔离       |
| 代码检查    | ESLint + Prettier              | 代码规范                      |

---

## 二、实施阶段总览

前端实施分为 **6 个阶段**：

```
阶段 1: 项目脚手架与基础设施    ── 工程初始化
阶段 2: 布局与路由              ── 页面骨架
阶段 3: 项目管理                ── 首页 + 项目 CRUD
阶段 4: 工作流核心交互          ── SSE + HITL + Agent 状态
阶段 5: 综述预览与导出          ── 结果呈现 + 文件下载
阶段 6: 集成测试与 Docker 部署  ── 前后端联调 + 容器化
```

### 阶段依赖关系

```
阶段 1 (脚手架)
  └──▶ 阶段 2 (布局与路由)
         └──▶ 阶段 3 (项目管理)
                └──▶ 阶段 4 (工作流核心交互)
                       └──▶ 阶段 5 (综述预览与导出)
                              └──▶ 阶段 6 (集成测试 + 部署)
```

---

## 三、阶段 1：项目脚手架与基础设施

**目标**: 初始化 React 项目、配置构建工具、安装依赖、搭建基础设施层。

### 1.1 任务清单

| #    | 任务                         | 输出文件                                   | 说明                                                      |
| ---- | ---------------------------- | ------------------------------------------ | --------------------------------------------------------- |
| 1.1  | Vite + React + TS 项目初始化 | `frontend/`                                | `npm create vite@latest frontend -- --template react-ts`  |
| 1.2  | 依赖安装                     | `frontend/package.json`                    | antd, react-router-dom, zustand, axios, react-markdown 等 |
| 1.3  | ESLint + Prettier 配置       | `frontend/eslint.config.js`, `.prettierrc` | TypeScript 规则、Ant Design 兼容                          |
| 1.4  | 目录结构规划                 | `frontend/src/`                            | 按功能模块分层 (见 §1.2)                                  |
| 1.5  | Ant Design 主题配置          | `frontend/src/theme/`                      | ConfigProvider 全局主题 Token、暗色模式预留               |
| 1.6  | API 客户端封装               | `frontend/src/api/client.ts`               | Axios 实例、baseURL、拦截器 (错误统一处理)、请求/响应类型 |
| 1.7  | API 接口定义                 | `frontend/src/api/*.ts`                    | 对齐后端 16 个 API 端点的 TypeScript 类型和请求函数       |
| 1.8  | SSE 客户端封装               | `frontend/src/api/sse.ts`                  | EventSource 封装、自动重连、Last-Event-ID 续传、事件解析  |
| 1.9  | TypeScript 类型定义          | `frontend/src/types/`                      | 对齐后端 Pydantic Schema 的 TS interface/type             |
| 1.10 | 环境变量配置                 | `frontend/.env.example`                    | `VITE_API_BASE_URL=http://localhost:8000`                 |
| 1.11 | Vite 代理配置                | `frontend/vite.config.ts`                  | 开发模式代理 `/api` → 后端，避免 CORS                     |

### 1.2 目录结构

```
frontend/src/
├── api/                    # API 客户端与接口定义
│   ├── client.ts           # Axios 实例、拦截器
│   ├── sse.ts              # SSE 客户端封装
│   ├── projects.ts         # 项目 API
│   ├── workflow.ts         # 工作流 API
│   ├── papers.ts           # 论文 API
│   └── outputs.ts          # 输出与导出 API
├── components/             # 可复用组件
│   ├── Layout/             # 布局组件
│   │   ├── AppLayout.tsx
│   │   ├── Sidebar.tsx
│   │   └── StatusBar.tsx
│   ├── Chat/               # 对话组件
│   │   ├── ChatPanel.tsx
│   │   └── MessageBubble.tsx
│   ├── Paper/              # 论文相关组件
│   │   ├── PaperList.tsx
│   │   ├── PaperCard.tsx
│   │   └── PaperFilter.tsx
│   ├── Workflow/           # 工作流组件
│   │   ├── AgentStatus.tsx
│   │   ├── HitlCard.tsx
│   │   └── ProgressBar.tsx
│   ├── Review/             # 综述组件
│   │   ├── ReviewPreview.tsx
│   │   ├── OutlineTree.tsx
│   │   └── CitationBadge.tsx
│   └── Common/             # 通用组件
│       ├── ErrorBoundary.tsx
│       ├── Loading.tsx
│       └── EmptyState.tsx
├── pages/                  # 页面组件
│   ├── HomePage.tsx        # 首页 / 新建项目
│   ├── ProjectPage.tsx     # 项目工作区 (对话+数据面板)
│   └── NotFoundPage.tsx    # 404
├── stores/                 # Zustand 状态管理
│   ├── projectStore.ts     # 项目列表与当前项目
│   ├── workflowStore.ts    # 工作流状态、Agent 进度
│   └── uiStore.ts          # UI 状态 (侧栏展开/折叠等)
├── hooks/                  # 自定义 Hooks
│   ├── useSSE.ts           # SSE 连接管理
│   ├── useProjects.ts      # 项目 CRUD
│   └── useWorkflow.ts      # 工作流控制
├── types/                  # TypeScript 类型
│   ├── project.ts
│   ├── paper.ts
│   ├── workflow.ts
│   └── output.ts
├── utils/                  # 工具函数
│   ├── format.ts           # 日期/数字格式化
│   └── constants.ts        # 常量
├── theme/                  # Ant Design 主题
│   └── index.ts
├── App.tsx                 # 根组件
├── main.tsx                # 入口
└── vite-env.d.ts
```

### 1.3 依赖清单 (package.json)

```json
{
  "dependencies": {
    "react": "^18.3",
    "react-dom": "^18.3",
    "react-router-dom": "^6.28",
    "antd": "^5.22",
    "@ant-design/icons": "^5.5",
    "zustand": "^5.0",
    "axios": "^1.7",
    "react-markdown": "^9.0",
    "remark-gfm": "^4.0",
    "dayjs": "^1.11"
  },
  "devDependencies": {
    "@types/react": "^18.3",
    "@types/react-dom": "^18.3",
    "@vitejs/plugin-react": "^4.3",
    "typescript": "^5.6",
    "vite": "^6.0",
    "eslint": "^9.15",
    "@eslint/js": "^9.15",
    "eslint-plugin-react-hooks": "^5.0",
    "globals": "^15.12",
    "typescript-eslint": "^8.15",
    "prettier": "^3.4"
  }
}
```

### 1.4 验收标准

- [ ] `npm run dev` 可启动，浏览器访问 `http://localhost:5173` 显示空白 React 页面
- [ ] Ant Design 组件可正常渲染（全局 ConfigProvider 生效）
- [ ] `apiClient.get('/healthz')` 通过 Vite 代理成功返回 `{"status": "ok"}`
- [ ] TypeScript 类型编译无错误
- [ ] ESLint + Prettier 检查通过

---

## 四、阶段 2：布局与路由

**目标**: 实现整体页面布局（侧栏 + 主工作区 + 状态栏）和 SPA 路由。

### 2.1 任务清单

| #   | 任务                   | 输出文件                              | 说明                                                                |
| --- | ---------------------- | ------------------------------------- | ------------------------------------------------------------------- |
| 2.1 | React Router 路由配置  | `frontend/src/App.tsx`                | `/` 首页、`/projects/:id` 项目工作区、`*` 404                       |
| 2.2 | AppLayout 布局组件     | `components/Layout/AppLayout.tsx`     | Ant Design Layout: Sider + Content + Footer，响应 UX 设计 §3.2 布局 |
| 2.3 | Sidebar 侧栏           | `components/Layout/Sidebar.tsx`       | 项目列表 + 新建项目按钮 + 项目状态标识，可折叠                      |
| 2.4 | StatusBar 状态栏       | `components/Layout/StatusBar.tsx`     | Agent 工作状态 + Token 消耗展示，隐藏/显示根据是否有活跃项目        |
| 2.5 | ErrorBoundary 全局错误 | `components/Common/ErrorBoundary.tsx` | React Error Boundary，防止组件崩溃导致白屏                          |
| 2.6 | Loading 组件           | `components/Common/Loading.tsx`       | 通用加载态（Skeleton / Spin）                                       |
| 2.7 | NotFoundPage 404       | `pages/NotFoundPage.tsx`              | Ant Design Result 组件                                              |
| 2.8 | UI Store               | `stores/uiStore.ts`                   | 侧栏折叠状态、当前活跃面板                                          |

### 2.2 路由结构

```
/                       → HomePage        (首页 / 新建项目)
/projects/:projectId    → ProjectPage     (项目工作区: 对话 + 数据面板)
*                       → NotFoundPage    (404)
```

### 2.3 验收标准

- [ ] 整体布局渲染正确：左侧栏 + 主内容区 + 底部状态栏
- [ ] 侧栏可折叠/展开
- [ ] 路由切换正常，URL 与页面内容对应
- [ ] 404 页面正常显示

---

## 五、阶段 3：项目管理

**目标**: 实现首页 / 新建项目、项目列表、项目 CRUD 完整流程。

### 3.1 任务清单

| #   | 任务                    | 输出文件                        | 说明                                                               |
| --- | ----------------------- | ------------------------------- | ------------------------------------------------------------------ |
| 3.1 | Project Store           | `stores/projectStore.ts`        | Zustand: 项目列表、当前项目、CRUD actions，分页状态                |
| 3.2 | 首页 — 研究问题输入     | `pages/HomePage.tsx`            | 大文本输入框 + 输出类型选择 (Radio Group) + 开始按钮，对应 UX §4.1 |
| 3.3 | 首页 — 文件上传         | `pages/HomePage.tsx`            | Ant Design Upload，支持 PDF / .bib / .ris，拖拽上传                |
| 3.4 | 首页 — 最近项目列表     | `pages/HomePage.tsx`            | 显示最近项目（状态标识、论文数、时间），点击进入项目工作区         |
| 3.5 | 侧栏 — 项目列表对接 API | `components/Layout/Sidebar.tsx` | 调用 `GET /api/v1/projects` 渲染项目列表，进行中项目显示状态 Badge |
| 3.6 | 项目删除                | 侧栏或首页                      | 确认弹窗 → 调用 `DELETE /api/v1/projects/{id}` → 刷新列表          |
| 3.7 | 中断恢复入口            | `pages/HomePage.tsx`            | 检测到未完成项目时显示恢复提示卡片 (UX §5.4)                       |
| 3.8 | useProjects Hook        | `hooks/useProjects.ts`          | 封装项目 CRUD 操作，加载状态管理                                   |

### 3.2 验收标准

- [ ] 首页可输入研究问题、选择输出类型、点击开始创建项目
- [ ] 创建成功后自动跳转到项目工作区 `/projects/:id`
- [ ] 文件上传功能正常（选择文件后显示文件名）
- [ ] 侧栏项目列表与后端同步，点击可切换项目
- [ ] 可删除项目（软删除）
- [ ] 未完成项目显示恢复提示

---

## 六、阶段 4：工作流核心交互

**目标**: 实现项目工作区的核心交互逻辑 — SSE 实时事件、Agent 状态显示、对话式 HITL 交互、论文列表。

这是前端最核心、最复杂的阶段。

### 4.1 任务清单

| #    | 任务                   | 输出文件                               | 说明                                                                  |
| ---- | ---------------------- | -------------------------------------- | --------------------------------------------------------------------- |
| 4.1  | Workflow Store         | `stores/workflowStore.ts`              | 工作流状态、Agent 进度、消息列表、HITL 状态、Token 用量               |
| 4.2  | useSSE Hook            | `hooks/useSSE.ts`                      | 管理 EventSource 生命周期、自动重连、Last-Event-ID、事件分发到 Store  |
| 4.3  | useWorkflow Hook       | `hooks/useWorkflow.ts`                 | 封装工作流操作 (start/resume/cancel/status)，SSE 连接控制             |
| 4.4  | ProjectPage 双栏布局   | `pages/ProjectPage.tsx`                | 左侧对话流 + 右侧数据面板，对应 UX §4.2                               |
| 4.5  | ChatPanel 对话面板     | `components/Chat/ChatPanel.tsx`        | 消息列表 + 底部输入框，支持系统消息和用户消息                         |
| 4.6  | MessageBubble 消息气泡 | `components/Chat/MessageBubble.tsx`    | 区分 system/user/agent 消息类型，Agent 消息可折叠                     |
| 4.7  | AgentStatus 状态组件   | `components/Workflow/AgentStatus.tsx`  | 显示当前 Agent 名称、状态图标、进度百分比 (如 "Reader 12/30")         |
| 4.8  | ProgressBar 进度条     | `components/Workflow/ProgressBar.tsx`  | 多步骤进度 (Search → Read → Write → Export)，当前步高亮               |
| 4.9  | HitlCard — 检索确认    | `components/Workflow/HitlCard.tsx`     | 候选论文列表 (可勾选) + 过滤/排序 + 确认按钮，对应 UX §4.2 HITL #1    |
| 4.10 | HitlCard — 大纲审阅    | (同上)                                 | 大纲树形展示 + 修改指令输入 + 确认/要求重新生成，对应 HITL #2         |
| 4.11 | HitlCard — 初稿审阅    | (同上)                                 | 综述预览 + 修改指令 + 通过/修改按钮，对应 HITL #3                     |
| 4.12 | PaperList 论文列表组件 | `components/Paper/PaperList.tsx`       | 可勾选表格/卡片列表，Checkbox 批量选择                                |
| 4.13 | PaperCard 论文卡片     | `components/Paper/PaperCard.tsx`       | 标题、作者、年份、会议、被引数、全文状态 (📄/📋)、相关度评分            |
| 4.14 | PaperFilter 过滤器     | `components/Paper/PaperFilter.tsx`     | 年份范围、被引数阈值、全文可获取状态过滤                              |
| 4.15 | Token 消耗展示         | `components/Workflow/TokenUsage.tsx`   | 已消耗 / 预算展示 + 费用估算 + 预算超限警告                           |
| 4.16 | 成本预估卡片           | `components/Workflow/CostEstimate.tsx` | HITL 确认前显示后续步骤预估 Token 消耗和费用                          |
| 4.17 | 工作流启动             | `pages/ProjectPage.tsx`                | 创建项目后自动调用 `POST /workflow/start`，建立 SSE 连接              |
| 4.18 | 异常状态组件           | `components/Common/EmptyState.tsx`     | 数据源异常、空结果、预算超限等状态 (UX §5.1–5.5) 的友好提示与恢复操作 |

### 4.2 SSE 事件处理映射

| SSE 事件类型     | 前端响应                                                  |
| ---------------- | --------------------------------------------------------- |
| `agent_start`    | 更新 AgentStatus 组件，对话流添加 "Agent X 开始工作" 消息 |
| `agent_complete` | 更新 AgentStatus 为完成，进度步骤前进                     |
| `progress`       | 更新进度百分比 (如 Reader 12/30)                          |
| `paper_found`    | 候选论文列表增量更新                                      |
| `paper_read`     | 渐进式精读结果展示                                        |
| `hitl_pause`     | 对话流插入 HITL 卡片 (检索确认/大纲审阅/初稿审阅)         |
| `token_update`   | 更新 Token 消耗显示                                       |
| `warning`        | 对话流插入警告消息 (数据源超时等)                         |
| `error`          | 对话流插入错误消息 + 恢复操作按钮                         |
| `complete`       | 工作流完成，关闭 SSE，引导查看结果                        |

### 4.3 HITL 交互流程

```
SSE 'hitl_pause' 事件
  └─▶ workflowStore.setHitlState(type, data)
        └─▶ ChatPanel 渲染 HitlCard (根据 type 切换内容)
              └─▶ 用户交互 (勾选论文/修改大纲/审阅初稿)
                    └─▶ POST /api/v1/projects/{id}/workflow/resume (HitlFeedback)
                          └─▶ SSE 恢复推送事件
```

### 4.4 验收标准

- [ ] SSE 连接建立后可实时接收 Agent 事件
- [ ] Agent 状态面板实时更新 (Search → Reader → Writer 进度)
- [ ] 检索确认 HITL：候选论文列表渲染、勾选/取消、过滤、确认后工作流恢复
- [ ] 大纲审阅 HITL：大纲树形展示、可输入修改指令、确认后恢复
- [ ] 初稿审阅 HITL：综述预览、修改指令输入、通过/修改后恢复
- [ ] 论文卡片展示完整信息 (标题、作者、年份、被引、全文状态、相关度)
- [ ] Token 消耗实时更新
- [ ] 异常状态有友好提示和恢复引导
- [ ] SSE 断线后自动重连，Last-Event-ID 续传

---

## 七、阶段 5：综述预览与导出

**目标**: 实现综述结果的 Markdown 渲染预览、引用验证标识展示和多格式导出下载。

### 5.1 任务清单

| #   | 任务                       | 输出文件                                | 说明                                                                      |
| --- | -------------------------- | --------------------------------------- | ------------------------------------------------------------------------- |
| 5.1 | ReviewPreview 综述预览组件 | `components/Review/ReviewPreview.tsx`   | react-markdown 渲染综述内容，支持 GFM 表格/列表                           |
| 5.2 | OutlineTree 大纲导航组件   | `components/Review/OutlineTree.tsx`     | Ant Design Tree 组件，从 outline JSON 生成树形导航，点击跳转到对应章节    |
| 5.3 | CitationBadge 引用验证标识 | `components/Review/CitationBadge.tsx`   | 引用旁显示 ✅ 已验证 / ⚠️ 待确认 图标，Tooltip 显示详情                     |
| 5.4 | 引用验证汇总面板           | `components/Review/CitationSummary.tsx` | 左侧面板底部：已验证 N 条 / 待确认 M 条 汇总                              |
| 5.5 | 导出功能                   | `pages/ProjectPage.tsx`                 | 导出按钮菜单 (Markdown / Word / BibTeX / RIS)，调用导出 API 下载文件      |
| 5.6 | ExportButton 导出按钮组件  | `components/Review/ExportButton.tsx`    | Ant Design Dropdown 按钮，选择格式后调用 `POST /outputs/{id}/export` 下载 |
| 5.7 | 输出列表                   | `pages/ProjectPage.tsx`                 | 项目工作区显示该项目所有输出版本列表                                      |

### 5.2 导出文件下载流程

```
用户点击导出按钮
  └─▶ 选择格式 (markdown / word / bibtex / ris)
        └─▶ POST /api/v1/projects/{id}/outputs/{oid}/export { format: "word" }
              └─▶ 后端返回二进制文件流 + Content-Disposition header
                    └─▶ 前端创建 Blob URL → 触发浏览器下载
```

### 5.3 验收标准

- [ ] 综述 Markdown 内容正确渲染（标题、段落、列表、表格、引用）
- [ ] 大纲导航可点击跳转到对应章节位置
- [ ] 引用验证标识正确显示（已验证/待确认）
- [ ] 4 种格式 (Markdown/Word/BibTeX/RIS) 导出均可正常下载文件
- [ ] 导出的文件名包含项目标题和格式后缀

---

## 八、阶段 6：集成测试与 Docker 部署

**目标**: 前后端联调验证，前端 Docker 容器化，接入 docker-compose 统一部署。

### 6.1 任务清单

| #   | 任务                | 输出文件                    | 说明                                                              |
| --- | ------------------- | --------------------------- | ----------------------------------------------------------------- |
| 6.1 | 前端 Dockerfile     | `frontend/Dockerfile`       | 多阶段构建: Node 构建 → Nginx 静态服务                            |
| 6.2 | Nginx 配置          | `frontend/nginx.conf`       | SPA fallback (`try_files`)、反向代理 `/api` → backend:8000、gzip  |
| 6.3 | docker-compose 集成 | `docker-compose.yml` (更新) | 新增 frontend 服务，端口 3000，depends_on backend                 |
| 6.4 | 前后端联调测试      | —                           | 完整流程验证: 创建项目 → 启动工作流 → SSE 事件 → HITL 交互 → 导出 |
| 6.5 | CORS / 代理验证     | —                           | 确认 Docker 环境下前后端通信正常 (Nginx 反向代理)                 |
| 6.6 | 构建优化            | `frontend/vite.config.ts`   | 代码分割、gzip 压缩、生产构建体积检查                             |

### 6.2 Nginx 配置要点

```nginx
server {
    listen 3000;

    # 静态文件服务
    location / {
        root /usr/share/nginx/html;
        index index.html;
        try_files $uri $uri/ /index.html;    # SPA fallback
    }

    # API 反向代理
    location /api/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # SSE 代理（禁用缓冲）
    location /api/v1/projects/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_buffering off;               # SSE 必须禁用缓冲
        proxy_cache off;
        proxy_read_timeout 3600s;          # 长连接超时
    }

    # 健康检查代理
    location /healthz {
        proxy_pass http://backend:8000;
    }
}
```

### 6.3 Docker 多阶段构建

```dockerfile
# 阶段 1: 构建
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# 阶段 2: 生产镜像
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 3000
```

### 6.4 验收标准

- [ ] `docker compose up` 一键启动前端 + 后端 + Redis
- [ ] 浏览器访问 `http://localhost:3000` 显示首页
- [ ] 前端通过 Nginx 反向代理正确访问后端 API
- [ ] SSE 事件流通过 Nginx 代理正常工作 (无缓冲)
- [ ] 完整流程可走通: 创建项目 → 工作流 → HITL → 综述预览 → 导出
- [ ] 生产构建体积合理 (gzip 后 < 500KB JS)

---

## 九、API 对接清单

前端需对接的全部后端 API 汇总：

### 9.1 项目管理

| 前端操作 | HTTP 方法 | 路径                    | 请求体                     | 响应                    |
| -------- | --------- | ----------------------- | -------------------------- | ----------------------- |
| 创建项目 | POST      | `/api/v1/projects`      | `ProjectCreate`            | `ProjectResponse` (201) |
| 项目列表 | GET       | `/api/v1/projects`      | 查询参数: status/page/size | `PaginatedResponse`     |
| 项目详情 | GET       | `/api/v1/projects/{id}` | —                          | `ProjectResponse`       |
| 更新项目 | PATCH     | `/api/v1/projects/{id}` | `ProjectUpdate`            | `ProjectResponse`       |
| 删除项目 | DELETE    | `/api/v1/projects/{id}` | —                          | 204                     |

### 9.2 工作流控制

| 前端操作   | HTTP 方法 | 路径                                    | 请求体         | 响应                     |
| ---------- | --------- | --------------------------------------- | -------------- | ------------------------ |
| 启动工作流 | POST      | `/api/v1/projects/{id}/workflow/start`  | —              | `WorkflowStartResponse`  |
| 恢复工作流 | POST      | `/api/v1/projects/{id}/workflow/resume` | `HitlFeedback` | `WorkflowStartResponse`  |
| 查询状态   | GET       | `/api/v1/projects/{id}/workflow/status` | —              | `WorkflowStatusResponse` |
| 取消工作流 | POST      | `/api/v1/projects/{id}/workflow/cancel` | —              | 204                      |

### 9.3 论文管理

| 前端操作     | HTTP 方法 | 路径                                     | 请求体                     | 响应                   |
| ------------ | --------- | ---------------------------------------- | -------------------------- | ---------------------- |
| 论文列表     | GET       | `/api/v1/projects/{id}/papers`           | 查询参数: status/page/size | `PaginatedResponse`    |
| 更新论文状态 | PATCH     | `/api/v1/projects/{id}/papers/{paperId}` | `{status: "..."}`          | `ProjectPaperResponse` |
| 论文详情     | GET       | `/api/v1/papers/{paperId}`               | —                          | `PaperResponse`        |
| 上传文件     | POST      | `/api/v1/projects/{id}/papers/upload`    | `FormData (file)`          | `PaperResponse[]`      |

### 9.4 输出与导出

| 前端操作 | HTTP 方法 | 路径                                         | 请求体          | 响应                     |
| -------- | --------- | -------------------------------------------- | --------------- | ------------------------ |
| 输出列表 | GET       | `/api/v1/projects/{id}/outputs`              | —               | `ReviewOutputResponse[]` |
| 输出详情 | GET       | `/api/v1/projects/{id}/outputs/{oid}`        | —               | `ReviewOutputResponse`   |
| 导出文件 | POST      | `/api/v1/projects/{id}/outputs/{oid}/export` | `ExportRequest` | 二进制文件流             |

### 9.5 实时事件

| 前端操作   | 协议 | 路径                           | 说明                        |
| ---------- | ---- | ------------------------------ | --------------------------- |
| SSE 事件流 | SSE  | `/api/v1/projects/{id}/events` | 支持 Last-Event-ID 断线续传 |

### 9.6 系统

| 前端操作 | HTTP 方法 | 路径       | 响应                                   |
| -------- | --------- | ---------- | -------------------------------------- |
| 存活检查 | GET       | `/healthz` | `{"status": "ok"}`                     |
| 就绪检查 | GET       | `/readyz`  | `{"status": "ready", "checks": {...}}` |

---

## 十、TypeScript 类型定义

对齐后端 Pydantic Schema，前端 TypeScript 类型如下（需实现于 `frontend/src/types/`）：

### 10.1 枚举类型

```typescript
// types/enums.ts
export enum OutputType {
  QUICK_BRIEF = 'quick_brief',
  ANNOTATED_BIB = 'annotated_bibliography',
  FULL_REVIEW = 'full_review',
}

export enum ProjectStatus {
  CREATED = 'created',
  SEARCHING = 'searching',
  READING = 'reading',
  ANALYZING = 'analyzing',
  WRITING = 'writing',
  COMPLETED = 'completed',
  FAILED = 'failed',
  CANCELLED = 'cancelled',
}

export enum CitationStyle {
  APA = 'apa',
  IEEE = 'ieee',
  GB_T_7714 = 'gb_t_7714',
}

export enum PaperSourceType {
  SEMANTIC_SCHOLAR = 'semantic_scholar',
  ARXIV = 'arxiv',
}

export enum ExportFormat {
  MARKDOWN = 'markdown',
  WORD = 'word',
  BIBTEX = 'bibtex',
  RIS = 'ris',
}
```

### 10.2 核心类型

```typescript
// types/project.ts
export interface ProjectCreate {
  user_query: string;
  output_types?: OutputType[];
  output_language?: string;
  citation_style?: CitationStyle;
  search_config?: Record<string, unknown>;
  token_budget?: number;
}

export interface ProjectResponse {
  id: string;
  user_id: string | null;
  title: string;
  user_query: string;
  status: ProjectStatus;
  output_types: OutputType[];
  output_language: string;
  citation_style: CitationStyle;
  paper_count: number;
  token_usage: Record<string, number> | null;
  token_budget: number | null;
  created_at: string;
  updated_at: string;
}

// types/paper.ts
export interface PaperResponse {
  id: string;
  title: string;
  authors: string[];
  year: number | null;
  venue: string | null;
  abstract: string | null;
  doi: string | null;
  s2_id: string | null;
  arxiv_id: string | null;
  citation_count: number;
  source: PaperSourceType;
  pdf_url: string | null;
  pdf_available: boolean;
  open_access: boolean;
  analysis: PaperAnalysisResponse | null;
}

export interface PaperAnalysisResponse {
  paper_id: string;
  objective: string | null;
  methodology: string | null;
  datasets: string[] | null;
  findings: string | null;
  limitations: string | null;
  key_concepts: string[] | null;
  quality_score: number | null;
  relevance_score: number | null;
  analysis_depth: string;
}

export interface ProjectPaperResponse {
  paper: PaperResponse;
  status: string;
  found_by: string | null;
  relevance_rank: number | null;
  added_at: string;
}

// types/workflow.ts
export interface HitlFeedback {
  hitl_type: 'search_review' | 'outline_review' | 'draft_review';
  selected_paper_ids?: string[];
  additional_query?: string;
  approved_outline?: Record<string, unknown>;
  revision_instructions?: string;
  approved?: boolean;
}

export interface WorkflowStartResponse {
  task_id: string;
  status: string;
}

export interface WorkflowStatusResponse {
  project_id: string;
  phase: string | null;
  status: string;
  progress: Record<string, unknown> | null;
  token_usage: Record<string, number> | null;
}

// types/output.ts
export interface ReviewOutputResponse {
  id: string;
  project_id: string;
  output_type: OutputType;
  title: string | null;
  outline: Record<string, unknown> | null;
  content: string | null;
  structured_data: Record<string, unknown> | null;
  references: Record<string, unknown>[] | null;
  version: number;
  language: string;
  citation_style: CitationStyle;
  citation_verification: CitationVerification[] | null;
  created_at: string;
  updated_at: string;
}

export interface CitationVerification {
  reference_index: number;
  status: 'verified' | 'unverified';
  title: string;
  doi: string | null;
}

// types/common.ts
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

// SSE 事件类型
export interface SSEEvent {
  id: string;
  event: string;
  data: Record<string, unknown>;
}
```

---

## 十一、状态管理设计

### 11.1 Store 划分

| Store           | 职责                                                          | 持久化 |
| --------------- | ------------------------------------------------------------- | ------ |
| `projectStore`  | 项目列表、当前项目、CRUD actions                              | 否     |
| `workflowStore` | 工作流运行时状态: Agent 进度、消息列表、HITL 状态、Token 用量 | 否     |
| `uiStore`       | UI 状态: 侧栏折叠、当前活跃面板、通知                         | 否     |

### 11.2 workflowStore 核心结构

```typescript
interface WorkflowState {
  // 工作流状态
  phase: string | null;              // 当前阶段: searching / reading / writing
  status: string;                    // running / paused / completed / error
  taskId: string | null;             // Celery task ID

  // 消息列表 (对话流)
  messages: ChatMessage[];           // 系统消息、Agent 消息、用户消息、HITL 卡片

  // Agent 进度
  agentProgress: {
    name: string;                    // 当前 Agent 名称
    current: number;                 // 已完成数
    total: number;                   // 总数
    percentage: number;              // 百分比
  } | null;

  // HITL 状态
  hitlState: {
    type: 'search_review' | 'outline_review' | 'draft_review' | null;
    data: Record<string, unknown>;   // HITL 相关数据 (论文列表/大纲/初稿)
  };

  // 候选论文 (检索确认 HITL 期间)
  candidatePapers: ProjectPaperResponse[];

  // Token 消耗
  tokenUsage: {
    total: number;
    budget: number | null;
    cost: number;                    // 预估费用 (美元)
  };

  // Actions
  addMessage: (msg: ChatMessage) => void;
  updateAgentProgress: (progress: AgentProgress) => void;
  setHitlState: (type: string, data: unknown) => void;
  clearHitlState: () => void;
  updateTokenUsage: (usage: TokenUsage) => void;
  reset: () => void;
}
```

---

## 十二、关键交互状态机

### 12.1 项目工作区状态流转

```
                    ┌─────────────┐
                    │   CREATED   │  ← 项目刚创建，显示启动按钮
                    └──────┬──────┘
                           │ POST /workflow/start
                           ▼
                    ┌─────────────┐
              ┌────►│  SEARCHING  │  ← Search Agent 工作中，SSE 推送进度
              │     └──────┬──────┘
              │            │ SSE 'hitl_pause' (search_review)
              │            ▼
              │     ┌─────────────┐
              │     │HITL: 检索确认│  ← 用户勾选论文、点击确认
              │     └──────┬──────┘
              │            │ POST /workflow/resume
              │            ▼
              │     ┌─────────────┐
              │     │   READING   │  ← Reader Agent 工作中，渐进式精读结果
              │     └──────┬──────┘
              │            │ SSE 'hitl_pause' (outline_review)
              │            ▼
              │     ┌─────────────┐
              │     │HITL: 大纲审阅│  ← 用户审阅/修改大纲
              │     └──────┬──────┘
              │            │ POST /workflow/resume
              │            ▼
              │     ┌─────────────┐
              │     │   WRITING   │  ← Writer Agent 生成综述
              │     └──────┬──────┘
              │            │ SSE 'hitl_pause' (draft_review)
              │            ▼
              │     ┌─────────────┐
              ├─────│HITL: 初稿审阅│  ← 用户审阅/修改初稿 (可多次循环)
              │     └──────┬──────┘
              │            │ POST /workflow/resume (approved=true)
              │            ▼
              │     ┌─────────────┐
              │     │  COMPLETED  │  ← 显示综述预览 + 导出按钮
              │     └─────────────┘
              │
              └── revision_instructions 提交后回到 WRITING (修订循环)
```

---

## 十三、技术风险与缓解

| 风险                                | 影响 | 缓解策略                                                       |
| ----------------------------------- | ---- | -------------------------------------------------------------- |
| SSE 长连接稳定性                    | 高   | 实现自动重连 + Last-Event-ID 续传；超时检测 + 心跳             |
| Nginx 代理 SSE 缓冲导致事件延迟     | 高   | Nginx 配置 `proxy_buffering off; proxy_cache off;`             |
| 大型论文列表 (200+ 篇) 前端渲染性能 | 中   | 虚拟滚动 (antd Table 内置)、分页加载                           |
| Markdown 渲染 XSS 安全              | 中   | react-markdown 默认 sanitize；不使用 `dangerouslySetInnerHTML` |
| 导出大文件下载超时                  | 低   | Axios responseType: 'blob'、进度提示                           |
| Ant Design 包体积过大               | 中   | Vite tree-shaking 自动按需加载；生产构建检查体积               |

---

## 十四、文件产出清单

```
frontend/
├── public/
│   └── favicon.svg
├── src/
│   ├── api/
│   │   ├── client.ts                   # [阶段 1]
│   │   ├── sse.ts                      # [阶段 1]
│   │   ├── projects.ts                 # [阶段 1]
│   │   ├── workflow.ts                 # [阶段 1]
│   │   ├── papers.ts                   # [阶段 1]
│   │   └── outputs.ts                  # [阶段 1]
│   ├── components/
│   │   ├── Layout/
│   │   │   ├── AppLayout.tsx           # [阶段 2]
│   │   │   ├── Sidebar.tsx             # [阶段 2]
│   │   │   └── StatusBar.tsx           # [阶段 2]
│   │   ├── Chat/
│   │   │   ├── ChatPanel.tsx           # [阶段 4]
│   │   │   └── MessageBubble.tsx       # [阶段 4]
│   │   ├── Paper/
│   │   │   ├── PaperList.tsx           # [阶段 4]
│   │   │   ├── PaperCard.tsx           # [阶段 4]
│   │   │   └── PaperFilter.tsx         # [阶段 4]
│   │   ├── Workflow/
│   │   │   ├── AgentStatus.tsx         # [阶段 4]
│   │   │   ├── HitlCard.tsx            # [阶段 4]
│   │   │   ├── ProgressBar.tsx         # [阶段 4]
│   │   │   ├── TokenUsage.tsx          # [阶段 4]
│   │   │   └── CostEstimate.tsx        # [阶段 4]
│   │   ├── Review/
│   │   │   ├── ReviewPreview.tsx       # [阶段 5]
│   │   │   ├── OutlineTree.tsx         # [阶段 5]
│   │   │   ├── CitationBadge.tsx       # [阶段 5]
│   │   │   ├── CitationSummary.tsx     # [阶段 5]
│   │   │   └── ExportButton.tsx        # [阶段 5]
│   │   └── Common/
│   │       ├── ErrorBoundary.tsx       # [阶段 2]
│   │       ├── Loading.tsx             # [阶段 2]
│   │       └── EmptyState.tsx          # [阶段 4]
│   ├── pages/
│   │   ├── HomePage.tsx                # [阶段 3]
│   │   ├── ProjectPage.tsx             # [阶段 4]
│   │   └── NotFoundPage.tsx            # [阶段 2]
│   ├── stores/
│   │   ├── projectStore.ts             # [阶段 3]
│   │   ├── workflowStore.ts            # [阶段 4]
│   │   └── uiStore.ts                  # [阶段 2]
│   ├── hooks/
│   │   ├── useSSE.ts                   # [阶段 4]
│   │   ├── useProjects.ts              # [阶段 3]
│   │   └── useWorkflow.ts              # [阶段 4]
│   ├── types/
│   │   ├── enums.ts                    # [阶段 1]
│   │   ├── project.ts                  # [阶段 1]
│   │   ├── paper.ts                    # [阶段 1]
│   │   ├── workflow.ts                 # [阶段 1]
│   │   ├── output.ts                   # [阶段 1]
│   │   └── common.ts                   # [阶段 1]
│   ├── utils/
│   │   ├── format.ts                   # [阶段 1]
│   │   └── constants.ts                # [阶段 1]
│   ├── theme/
│   │   └── index.ts                    # [阶段 1]
│   ├── App.tsx                         # [阶段 2]
│   ├── main.tsx                        # [阶段 1]
│   └── vite-env.d.ts                   # [阶段 1]
├── index.html                          # [阶段 1]
├── package.json                        # [阶段 1]
├── tsconfig.json                       # [阶段 1]
├── tsconfig.node.json                  # [阶段 1]
├── vite.config.ts                      # [阶段 1]
├── eslint.config.js                    # [阶段 1]
├── .prettierrc                         # [阶段 1]
├── .env.example                        # [阶段 1]
├── Dockerfile                          # [阶段 6]
└── nginx.conf                          # [阶段 6]
```

**文件总数**: 约 50 个文件

---

## 十五、后续迭代规划

前端 MVP v0.2 完成后，后续迭代方向：

| 版本 | 前端新增                                                                     |
| ---- | ---------------------------------------------------------------------------- |
| v0.3 | 综述富文本编辑器 (内联 AI 指令、版本历史、撤销重做)；分析看板 (ECharts 图表) |
| v0.4 | JWT 认证 + 用户系统；知识图谱可视化 (D3.js)；移动端响应式适配                |
| v0.5 | 文献订阅通知 UI；国际化 (i18n)；新手引导 Onboarding                          |
| v1.0 | 性能优化、PWA 支持、完善的 E2E 测试 (Cypress/Playwright)                     |
