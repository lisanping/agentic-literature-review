# v0.5 实施计划：OpenAlex/PubMed 适配器 + Update Agent

> **文档版本**: v1.0
> **创建日期**: 2026-03-31
> **前置文档**: [v0.1 实施计划](implementation-plan.md) · [v0.4 实施计划](v04-implementation-plan.md) · [需求与功能设计](../design/requirements-and-functional-design.md) · [系统架构](../design/system-architecture.md)
> **目标**: 新增 OpenAlex/PubMed 数据源适配器，实现 Update Agent（新文献监控 + 增量更新）

---

## 一、v0.5 范围

### 1.1 本次实施内容

| 维度   | v0.5 新增                                                  |
| ------ | ---------------------------------------------------------- |
| 数据源 | OpenAlex 适配器 + PubMed 适配器（实现 `PaperSource` 接口） |
| Agent  | Update Agent — 新文献监控、差异对比、增量更新报告          |
| 配置   | 新数据源配置项、Update Agent 配置                          |
| API    | 更新触发端点、更新历史查询端点                             |
| 前端   | 项目页"检查更新"按钮（复用 SSE 事件流）                    |

### 1.2 不包含

| 维度       | 状态                                       |
| ---------- | ------------------------------------------ |
| 数据库迁移 | PostgreSQL 切换推迟（保持 SQLite）         |
| 定时任务   | Celery Beat 自动周期触发推迟（仅手动触发） |
| 邮件通知   | 更新完成后的邮件/推送通知推迟              |
| 其他数据源 | Crossref / DBLP / CORE / Unpaywall 推迟    |

---

## 二、关键设计决策

### 2.1 OpenAlex API 方案

**API**: OpenAlex REST API (`https://api.openalex.org`)
- **无需 API Key**，但建议设置 `mailto` 参数进入 polite pool（速率更高）
- 速率限制: polite pool 10 req/s，无 mailto 则 1 req/s
- 返回 JSON，字段丰富（DOI、作者、机构、概念、引用等）
- 支持 filter 语法（年份、类型、开放获取等）

**映射到 `PaperMetadata`**:
| OpenAlex 字段                          | PaperMetadata 字段 |
| -------------------------------------- | ------------------ |
| `id` (URL 尾部)                        | — (内部索引)       |
| `doi`                                  | `doi`              |
| `title`                                | `title`            |
| `authorships[].author.display_name`    | `authors`          |
| `publication_year`                     | `year`             |
| `primary_location.source.display_name` | `venue`            |
| `abstract_inverted_index` → 重建文本   | `abstract`         |
| `cited_by_count`                       | `citation_count`   |
| `referenced_works_count`               | `reference_count`  |
| `open_access.is_oa`                    | `open_access`      |
| `primary_location.pdf_url`             | `pdf_url`          |
| `id`                                   | `source_url`       |

**注意**: OpenAlex 的 `abstract_inverted_index` 是倒排索引格式，需要重建为连续文本。

### 2.2 PubMed API 方案

**API**: NCBI Entrez E-utilities
- `esearch.fcgi` — 关键词检索，返回 PMID 列表
- `efetch.fcgi` — 按 PMID 获取详情（XML 格式）
- `elink.fcgi` — 获取引用/被引关系
- **速率限制**: 无 API Key 3 req/s，有 Key 10 req/s
- **API Key**: 通过 `NCBI_API_KEY` 环境变量配置（可选）

**映射到 `PaperMetadata`**:
| PubMed XML 字段                       | PaperMetadata 字段        |
| ------------------------------------- | ------------------------- |
| `PMID`                                | — (通过 `s2_id` 或新字段) |
| `ArticleTitle`                        | `title`                   |
| `AuthorList/Author`                   | `authors`                 |
| `PubDate/Year`                        | `year`                    |
| `Journal/Title`                       | `venue`                   |
| `AbstractText`                        | `abstract`                |
| `ArticleIdList/ArticleId[IdType=doi]` | `doi`                     |
| `ArticleIdList/ArticleId[IdType=pmc]` | —                         |

**注意**: PubMed 不直接提供引用计数，需通过 elink 获取 cited-by 列表计数。PubMed 原生不支持 `get_citations` / `get_references`，改用 elink PMC 引用链接或降级返回空列表。

### 2.3 PaperMetadata 扩展

需要新增字段以支持 OpenAlex 和 PubMed 的 ID：

```python
class PaperMetadata(BaseModel):
    # ... 现有字段 ...
    openalex_id: str | None = None   # OpenAlex Work ID (e.g. "W2741809807")
    pmid: str | None = None          # PubMed ID (e.g. "12345678")
    pmcid: str | None = None         # PubMed Central ID (e.g. "PMC1234567")
```

同步修改 Paper ORM 模型，新增 `openalex_id` / `pmid` 列（可选，nullable），并加入去重优先级链：
```
DOI > S2 ID > arXiv ID > OpenAlex ID > PMID > 标题模糊匹配
```

### 2.4 Update Agent 设计

**定位**: 复用现有 Search Agent 检索能力 + Reader Agent 分析能力，独立工作流。

**触发方式**: v0.5 仅支持手动触发（API 调用），不含定时任务。

**工作流程**:
```
触发更新 (project_id)
    │
    ▼
1. 加载原项目的 search_strategy + 已有论文集
    │
    ▼
2. 增量检索 — 复用 SourceRegistry，加 date_range 过滤 (since last_search_at)
    │
    ▼
3. 差异对比 — 新论文集 vs 已有论文集去重，筛出真正新增的
    │
    ▼
4. 相关性评估 — LLM 判断新论文与原研究问题的相关性 (批量评分)
    │
    ▼
5. 精读新论文 — 对高相关论文调用 Reader Agent 分析
    │
    ▼
6. 生成更新报告 — LLM 总结新发现、对原综述的影响评估
    │
    ▼
7. 持久化 — 新论文写入 project_papers，报告写入 review_outputs
```

**不修改原综述**: v0.5 的 Update Agent 只生成增量更新报告，不自动修订原综述。自动修订为 v1.0 能力。

---

## 三、阶段划分

```
阶段 1: OpenAlex 适配器 ──┐
                           ├── 互相独立，可并行
阶段 2: PubMed 适配器   ──┘
                           │
                           ▼
阶段 3: PaperMetadata 扩展 + 去重链扩展 ── 数据层改动
                           │
                           ▼
阶段 4: Update Agent 实现 ── Agent 节点 + Prompt
                           │
                           ▼
阶段 5: API 端点 + 前端集成
                           │
                           ▼
阶段 6: 测试 + 文档
```

---

## 四、阶段 1：OpenAlex 适配器

**目标**: 实现 `OpenAlexSource(PaperSource)` 适配器。

### 4.1 任务清单

| #   | 任务                  | 输出文件                         | 说明                                                 |
| --- | --------------------- | -------------------------------- | ---------------------------------------------------- |
| 1.1 | OpenAlex 适配器       | `app/sources/openalex.py`        | 实现 search/get_paper/get_citations/get_references   |
| 1.2 | 倒排索引重建函数      | (同上)                           | `_reconstruct_abstract(inverted_index)` 重建摘要文本 |
| 1.3 | 配置项                | `app/config.py` (修改)           | 新增 `OPENALEX_EMAIL` 配置（polite pool mailto）     |
| 1.4 | 注册到 SourceRegistry | `app/sources/__init__.py` (修改) | `create_source_registry()` 中注册 `openalex`         |
| 1.5 | 单元测试              | `tests/test_openalex.py`         | Mock HTTP 响应测试解析逻辑 + 倒排索引重建            |

### 4.2 API 细节

```
搜索: GET https://api.openalex.org/works?search={query}&per_page={limit}&mailto={email}
      filter 支持: publication_year, type, open_access.is_oa, cited_by_count
详情: GET https://api.openalex.org/works/{openalex_id}?mailto={email}
引用: GET https://api.openalex.org/works?filter=cites:{openalex_id}&per_page=100
被引: GET https://api.openalex.org/works?filter=cited_by:{openalex_id}&per_page=100
```

### 4.3 速率限制

- `RateLimiter(rate=10, per_seconds=1)` — polite pool（有 mailto）
- `RateLimiter(rate=1, per_seconds=1)` — 无 mailto 降级

### 4.4 验收标准

- [ ] `OpenAlexSource.search("transformer attention")` 返回 `PaperMetadata` 列表
- [ ] 倒排索引正确重建为连续英文摘要
- [ ] DOI / OpenAlex ID 正确提取
- [ ] `get_citations` / `get_references` 返回相关论文
- [ ] 无 API Key 场景正常降级（低速率限制）

---

## 五、阶段 2：PubMed 适配器

**目标**: 实现 `PubMedSource(PaperSource)` 适配器。

### 5.1 任务清单

| #   | 任务                  | 输出文件                         | 说明                                                         |
| --- | --------------------- | -------------------------------- | ------------------------------------------------------------ |
| 2.1 | PubMed 适配器         | `app/sources/pubmed.py`          | 实现 search/get_paper/get_citations/get_references           |
| 2.2 | XML 解析函数          | (同上)                           | `_parse_pubmed_article(xml_element)` 解析 PubmedArticle 节点 |
| 2.3 | 配置项                | `app/config.py` (修改)           | 新增 `NCBI_API_KEY` 配置（可选，提高速率限制）               |
| 2.4 | 注册到 SourceRegistry | `app/sources/__init__.py` (修改) | `create_source_registry()` 中注册 `pubmed`                   |
| 2.5 | 单元测试              | `tests/test_pubmed.py`           | Mock HTTP 响应测试 XML 解析                                  |

### 5.2 API 细节

```
检索: GET https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi
      ?db=pubmed&term={query}&retmax={limit}&retmode=json&api_key={key}
      → 返回 PMID 列表

详情: GET https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi
      ?db=pubmed&id={pmid_list}&retmode=xml&api_key={key}
      → 返回 PubmedArticleSet XML

引用: GET https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi
      ?dbfrom=pubmed&db=pubmed&id={pmid}&linkname=pubmed_pubmed_citedin&api_key={key}
      → 返回 cited-by PMID 列表 → 再 efetch 获取详情
```

### 5.3 实现要点

- 检索分两步：`esearch` 获取 PMID 列表 → `efetch` 批量获取详情（每批最多 200 个 PMID）
- PubMed 没有引用计数字段，`citation_count` 通过 `elink` cited-by 列表长度填充（可选，默认 0）
- `get_citations` 通过 `elink pubmed_pubmed_citedin` 实现
- `get_references` 通过 `elink pubmed_pubmed_refs` 实现
- XML 解析使用 `xml.etree.ElementTree`（与 arXiv 适配器一致）

### 5.4 速率限制

- 有 API Key: `RateLimiter(rate=10, per_seconds=1)`
- 无 API Key: `RateLimiter(rate=3, per_seconds=1)`

### 5.5 验收标准

- [ ] `PubMedSource.search("CRISPR gene editing")` 返回生物医学论文列表
- [ ] XML 正确解析标题、作者、摘要、DOI、年份
- [ ] PMID 正确提取并填充到 `PaperMetadata.pmid`
- [ ] `get_citations` / `get_references` 通过 elink 正常工作
- [ ] 无 API Key 场景正常降级

---

## 六、阶段 3：PaperMetadata 扩展 + 去重链扩展

**目标**: 扩展数据模型以支持 OpenAlex ID 和 PMID，扩展去重优先级链。

### 6.1 任务清单

| #   | 任务                   | 输出文件                                 | 说明                                                                       |
| --- | ---------------------- | ---------------------------------------- | -------------------------------------------------------------------------- |
| 3.1 | PaperMetadata 新增字段 | `app/schemas/paper.py` (修改)            | 新增 `openalex_id` / `pmid` / `pmcid` 可选字段                             |
| 3.2 | Paper ORM 新增列       | `app/models/paper.py` (修改)             | 新增 `openalex_id` / `pmid` 列 (nullable, unique 部分索引)                 |
| 3.3 | Alembic 迁移           | `alembic/versions/v05_new_source_ids.py` | ALTER TABLE papers ADD COLUMN openalex_id / pmid                           |
| 3.4 | 去重链扩展             | `app/services/paper_ops.py` (修改)       | `find_or_create_paper()` 优先级: DOI > S2 > arXiv > OpenAlex > PMID > 标题 |
| 3.5 | PaperResponse 更新     | `app/schemas/paper.py` (修改)            | 响应 schema 新增 `openalex_id` / `pmid`                                    |
| 3.6 | 前端类型更新           | `frontend/src/types/paper.ts` (修改)     | PaperResponse 新增字段                                                     |

### 6.2 验收标准

- [ ] Alembic 迁移正常执行
- [ ] 去重逻辑测试: 同一篇论文通过 OpenAlex ID / PMID 正确去重
- [ ] 现有测试无回归

---

## 七、阶段 4：Update Agent 实现

**目标**: 实现 Update Agent 节点函数，独立于主工作流运行。

### 7.1 任务清单

| #    | 任务                       | 输出文件                             | 说明                                                                         |
| ---- | -------------------------- | ------------------------------------ | ---------------------------------------------------------------------------- |
| 4.1  | ReviewState 新增字段       | `app/agents/state.py` (修改)         | 新增 `update_mode` / `new_papers_found` / `update_report` / `last_search_at` |
| 4.2  | Update Agent Prompt 模板   | `prompts/update/relevance_filter.md` | LLM 判断新论文与原研究问题的相关性 (批量评分 JSON)                           |
| 4.3  | Update Agent Prompt 模板   | `prompts/update/update_report.md`    | LLM 基于新论文分析生成增量更新报告                                           |
| 4.4  | Update Agent — 增量检索    | `app/agents/update_agent.py`         | 加载原 search_strategy + date_range 过滤检索新论文                           |
| 4.5  | Update Agent — 差异对比    | (同上)                               | 新论文集 vs 已有论文集 去重，筛出真正新增                                    |
| 4.6  | Update Agent — 相关性评估  | (同上)                               | LLM 批量评分新论文相关性，过滤低相关                                         |
| 4.7  | Update Agent — 调用 Reader | (同上)                               | 对高相关新论文复用 Reader Agent 精读逻辑                                     |
| 4.8  | Update Agent — 生成报告    | (同上)                               | LLM 生成增量更新报告 (新发现 / 影响评估 / 建议)                              |
| 4.9  | Update Agent — Node 函数   | (同上)                               | `update_node(state) -> dict` 整合上述步骤                                    |
| 4.10 | ProjectStatus 扩展         | `app/models/enums.py` (修改)         | 新增 `UPDATING` 状态                                                         |
| 4.11 | Project 模型新增字段       | `app/models/project.py` (修改)       | 新增 `last_search_at` 时间戳                                                 |
| 4.12 | 单元测试                   | `tests/test_update_agent.py`         | Mock LLM + Mock SourceRegistry，验证增量检索+报告生成                        |

### 7.2 Update Agent 节点函数签名

```python
async def update_node(state: ReviewState) -> dict:
    """
    输入 (从 state 读取):
        - project_id: 要更新的项目 ID
        - search_strategy: 原始检索策略
        - selected_papers: 已有论文列表 (用于去重)
        - last_search_at: 上次检索时间 (用于 date_range 过滤)
        - user_query: 原始研究问题

    输出 (返回更新字段):
        - new_papers_found: 新发现论文列表
        - paper_analyses: 新论文的精读结果 (追加)
        - update_report: 增量更新报告文本
        - last_search_at: 更新为当前时间
    """
```

### 7.3 Prompt 设计

**relevance_filter.md**:
```
你是一位学术文献筛选专家。

研究问题: {{ user_query }}

以下是新检索到的论文列表。请评估每篇论文与研究问题的相关性。
对每篇论文返回 JSON 格式的评分 (0-10) 和简短理由。

论文列表:
{% for paper in papers %}
- [{{ loop.index }}] {{ paper.title }} ({{ paper.year }})
  摘要: {{ paper.abstract[:300] }}
{% endfor %}

返回 JSON 数组:
[{"index": 1, "score": 8, "reason": "..."}, ...]
```

**update_report.md**:
```
你是一位资深学术综述专家。

研究问题: {{ user_query }}
原综述包含 {{ existing_count }} 篇论文。
本次检查发现 {{ new_count }} 篇新相关论文。

新论文分析摘要:
{% for analysis in new_analyses %}
## {{ analysis.title }} ({{ analysis.year }})
- 主要发现: {{ analysis.findings }}
- 方法: {{ analysis.methodology }}
{% endfor %}

请生成一份增量更新报告，包含:
1. **新发现摘要**: 这些新论文带来了哪些新知识
2. **对原综述的影响**: 是否改变了原有结论或增加了新维度
3. **建议**: 是否需要修订综述，如需修订建议修改哪些章节
```

### 7.4 验收标准

- [ ] 给定已完成项目，`update_node` 可检索到新论文
- [ ] 新论文与已有论文正确去重（不重复添加）
- [ ] 相关性评估过滤掉低相关论文
- [ ] 高相关论文经过 Reader 精读
- [ ] 生成的更新报告包含新发现摘要 + 影响评估
- [ ] 结果正确持久化到 project_papers + review_outputs

---

## 八、阶段 5：API 端点 + 前端集成

**目标**: 提供触发更新和查看更新历史的 API，前端集成。

### 8.1 任务清单

| #   | 任务             | 输出文件                                    | 说明                                                |
| --- | ---------------- | ------------------------------------------- | --------------------------------------------------- |
| 5.1 | 更新 API 路由    | `app/api/routes/updates.py` (新增)          | POST 触发更新 / GET 更新历史 / GET 更新报告详情     |
| 5.2 | Celery 任务      | `app/tasks.py` (修改)                       | `run_update(project_id)` 异步执行 Update Agent      |
| 5.3 | 路由注册         | `app/main.py` (修改)                        | 注册 updates 路由                                   |
| 5.4 | 前端 API 层      | `frontend/src/api/updates.ts` (新增)        | `triggerUpdate` / `listUpdates` / `getUpdateReport` |
| 5.5 | 前端 ProjectPage | `frontend/src/pages/ProjectPage.tsx` (修改) | "检查更新"按钮 + 更新报告展示                       |

### 8.2 API 端点

```
POST /api/v1/projects/{project_id}/updates
  → 触发异步更新检查，返回 task_id
  → 需要 collaborator 权限

GET /api/v1/projects/{project_id}/updates
  → 返回更新历史列表 [{id, created_at, new_papers_count, status}]
  → 需要 viewer 权限

GET /api/v1/projects/{project_id}/updates/{update_id}
  → 返回更新报告详情 (new_papers + report_text)
  → 需要 viewer 权限
```

### 8.3 验收标准

- [ ] API 手动触发更新 → Celery 执行 → SSE 推送进度
- [ ] 更新完成后可查看更新报告
- [ ] 前端"检查更新"按钮可触发并显示结果
- [ ] 权限控制正确（viewer 可查看，collaborator 可触发）

---

## 九、阶段 6：测试 + 文档

### 9.1 任务清单

| #   | 任务                  | 输出文件                            | 说明                              |
| --- | --------------------- | ----------------------------------- | --------------------------------- |
| 6.1 | OpenAlex 集成测试     | `tests/test_openalex.py` (扩展)     | `@pytest.mark.live` 真实 API 测试 |
| 6.2 | PubMed 集成测试       | `tests/test_pubmed.py` (扩展)       | `@pytest.mark.live` 真实 API 测试 |
| 6.3 | Update Agent 集成测试 | `tests/test_update_agent.py` (扩展) | Mock 完整更新流程                 |
| 6.4 | 数据源回归测试        | `tests/test_sources.py` (扩展)      | 确认 4 源注册正确                 |
| 6.5 | 前端构建验证          | —                                   | TypeScript 零错误 + Vite 构建通过 |
| 6.6 | CHANGELOG 更新        | `docs/dev/CHANGELOG.md` (修改)      | v0.5 变更记录                     |

### 9.2 验收标准

- [ ] 全部现有测试无回归
- [ ] 新增测试全部通过
- [ ] 前端构建零错误

---

## 十、文件产出清单

```
backend/
├── app/
│   ├── config.py                              # [阶段 1+2] 修改 (OPENALEX_EMAIL, NCBI_API_KEY)
│   ├── main.py                                # [阶段 5] 修改 (注册 updates 路由)
│   ├── tasks.py                               # [阶段 5] 修改 (run_update 任务)
│   ├── models/
│   │   ├── enums.py                           # [阶段 4] 修改 (UPDATING 状态)
│   │   ├── paper.py                           # [阶段 3] 修改 (openalex_id, pmid 列)
│   │   └── project.py                         # [阶段 4] 修改 (last_search_at)
│   ├── schemas/
│   │   └── paper.py                           # [阶段 3] 修改 (新增 ID 字段)
│   ├── agents/
│   │   ├── state.py                           # [阶段 4] 修改 (update 字段)
│   │   └── update_agent.py                    # [阶段 4] 新增
│   ├── sources/
│   │   ├── __init__.py                        # [阶段 1+2] 修改 (注册新数据源)
│   │   ├── openalex.py                        # [阶段 1] 新增
│   │   └── pubmed.py                          # [阶段 2] 新增
│   ├── services/
│   │   └── paper_ops.py                       # [阶段 3] 修改 (去重链扩展)
│   └── api/routes/
│       └── updates.py                         # [阶段 5] 新增
├── alembic/versions/
│   └── v05_new_source_ids.py                  # [阶段 3] 新增
├── prompts/update/
│   ├── relevance_filter.md                    # [阶段 4] 新增
│   └── update_report.md                       # [阶段 4] 新增
├── tests/
│   ├── test_openalex.py                       # [阶段 1+6] 新增
│   ├── test_pubmed.py                         # [阶段 2+6] 新增
│   └── test_update_agent.py                   # [阶段 4+6] 新增

frontend/src/
├── api/
│   └── updates.ts                             # [阶段 5] 新增
├── types/
│   └── paper.ts                               # [阶段 3] 修改
└── pages/
    └── ProjectPage.tsx                        # [阶段 5] 修改

# 新增文件: ~8 个
# 修改文件: ~14 个
```

---

## 十一、依赖关系

```
阶段 1 (OpenAlex) ──┐
                     ├── 互不依赖，可并行
阶段 2 (PubMed)   ──┘
          │
          ▼
阶段 3 (PaperMetadata 扩展) ── 依赖 1+2 的 ID 字段定义
          │
          ▼
阶段 4 (Update Agent) ── 依赖 3 (新数据源可用)
          │
          ▼
阶段 5 (API + 前端) ── 依赖 4
          │
          ▼
阶段 6 (测试 + 文档)
```

**并行机会**:
- 阶段 1 和 2 完全并行
- 阶段 3 中 schema 修改可在 1/2 完成前准备好，仅迁移脚本需等待

---

## 十二、技术风险

| 风险                                       | 影响 | 缓解策略                                              |
| ------------------------------------------ | ---- | ----------------------------------------------------- |
| OpenAlex abstract_inverted_index 重建不准  | 低   | 单测覆盖多种 case；降级到 title-only 分析             |
| PubMed XML 格式跨版本变化                  | 低   | 防御性解析，缺失字段返回 None                         |
| PubMed elink 引用数据不完整                | 中   | citation_count 降级为 0；标注数据来源                 |
| Update Agent 新论文过多导致 LLM Token 爆炸 | 中   | 相关性评估先筛选，上限 30 篇新论文进入精读            |
| 4 数据源并发检索导致速率限制触发           | 中   | 每个数据源独立 RateLimiter；CachedSource 减少重复请求 |
