# 多智能体文献综述应用 — 数据模型设计

> **文档版本**: v1.2
> **创建日期**: 2026-03-28
> **最后更新**: 2026-03-30
> **文档状态**: 迭代修订
> **前置文档**: [需求与功能设计](requirements-and-functional-design.md) · [系统架构](system-architecture.md)
> **文档说明**: 本文档定义系统核心实体、关系、数据库 Schema 及枚举类型，为后端编码实现提供直接的数据层指导。

---

## 目录

- [一、实体关系总览](#一实体关系总览)
- [二、核心枚举类型](#二核心枚举类型)
- [三、项目实体 (Project)](#三项目实体-project)
- [四、论文实体 (Paper)](#四论文实体-paper)
- [五、论文分析实体 (PaperAnalysis)](#五论文分析实体-paperanalysis)
- [六、综述输出实体 (ReviewOutput)](#六综述输出实体-reviewoutput)
- [七、项目-论文关联 (ProjectPaper)](#七项目-论文关联-projectpaper)
- [八、工作流状态与 Agent 数据结构](#八工作流状态与-agent-数据结构)
- [九、向量数据库 Schema](#九向量数据库-schema)
- [十、缓存 Key 设计](#十缓存-key-设计)
- [十一、MVP 实现范围](#十一mvp-实现范围)

---

## 一、实体关系总览

### 1.1 ER 图

```
┌──────────────┐       1:N        ┌──────────────────┐
│              │─────────────────▶│                  │
│   Project    │                  │  ReviewOutput    │
│              │◀─────────────────│                  │
└──────┬───────┘                  └──────────────────┘
       │
       │ M:N (通过 ProjectPaper)
       │
┌──────┴───────┐       1:1        ┌──────────────────┐
│              │─────────────────▶│                  │
│   Paper      │                  │  PaperAnalysis   │
│  (全局去重)   │◀─────────────────│  (项目内分析结果)  │
└──────────────┘                  └──────────────────┘

关键关系:
  Project  ──1:N──▶  ReviewOutput   (一个项目可生成多种类型的输出)
  Project  ──M:N──▶  Paper          (通过 ProjectPaper 关联表)
  Paper    ──1:N──▶  PaperAnalysis  (同一论文在不同项目中有不同分析上下文)
  ProjectPaper     ──1:1──▶  PaperAnalysis  (每个项目-论文对应一次分析)
```

### 1.2 设计原则

| 原则             | 说明                                                                                                                                                                               |
| ---------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **论文全局去重** | 同一篇论文（按 DOI / S2 ID）只存一份，多个项目共享                                                                                                                                 |
| **分析项目隔离** | 论文的分析结果按项目隔离，同一篇论文在不同研究问题下有不同分析角度                                                                                                                 |
| **输出可扩展**   | 输出类型通过枚举定义，新增类型只需扩展枚举值                                                                                                                                       |
| **软删除**       | 项目级实体（`projects`、`project_papers`、`paper_analyses`、`review_outputs`）使用 `deleted_at` 字段软删除，保留审计轨迹。全局共享实体（`papers`）不做软删除，因可能被多个项目引用 |

---

## 二、核心枚举类型

### 2.1 输出类型 (OutputType)

```python
from enum import StrEnum

class OutputType(StrEnum):
    """综述输出类型"""
    # ── 文本类 ──
    QUICK_BRIEF = "quick_brief"                 # 快速摘要 (1-2页领域速览)
    ANNOTATED_BIBLIOGRAPHY = "annotated_bib"    # 注释文献列表
    FULL_REVIEW = "full_review"                 # 完整文献综述
    METHODOLOGY_REVIEW = "methodology_review"   # 方法论综合报告 (方法/技术路线对比、适用场景、优劣势)
    RESEARCH_ROADMAP = "research_roadmap"       # 研究脉络报告 (研究思路演进、方法迭代、关键转折点)

    # ── 结构化数据类 ──
    COMPARISON_MATRIX = "comparison_matrix"     # 对比矩阵 (方法×指标)
    GAP_REPORT = "gap_report"                   # 研究空白报告
    TREND_REPORT = "trend_report"               # 趋势分析报告

    # ── 可视化类 ──
    KNOWLEDGE_MAP = "knowledge_map"             # 知识图谱
    TIMELINE = "timeline"                       # 时间线
```

**输出类型分类说明**:

| 分类       | 类型                                                                          | 特点                                 |
| ---------- | ----------------------------------------------------------------------------- | ------------------------------------ |
| **文本类** | Quick Brief, Annotated Bib, Full Review, Methodology Review, Research Roadmap | 以长文本为主体，可导出 Word/LaTeX/MD |
| **数据类** | Comparison Matrix, Gap Report, Trend Report                                   | 结构化数据 + 文字解读，可导出表格    |
| **可视化** | Knowledge Map, Timeline                                                       | 图形为主，可导出 SVG/PNG/HTML        |

### 2.2 项目状态 (ProjectStatus)

```python
class ProjectStatus(StrEnum):
    """项目生命周期状态"""
    CREATED = "created"             # 已创建，未开始
    SEARCHING = "searching"         # Search Agent 检索中
    SEARCH_REVIEW = "search_review" # 等待用户确认论文列表 (HITL)
    READING = "reading"             # Reader Agent 精读中
    ANALYZING = "analyzing"         # Analyst Agent 分析中
    CRITIQUING = "critiquing"       # Critic Agent 评审中
    OUTLINING = "outlining"         # Writer Agent 生成大纲中
    OUTLINE_REVIEW = "outline_review" # 等待用户确认大纲 (HITL)
    WRITING = "writing"             # Writer Agent 生成全文中
    DRAFT_REVIEW = "draft_review"   # 等待用户审阅初稿 (HITL)
    REVISING = "revising"           # 修改中
    EXPORTING = "exporting"         # 导出中
    COMPLETED = "completed"         # 已完成
    FAILED = "failed"               # 失败
    CANCELLED = "cancelled"         # 用户取消
```

### 2.3 论文来源 (PaperSourceType)

```python
class PaperSourceType(StrEnum):
    """论文数据来源"""
    SEMANTIC_SCHOLAR = "semantic_scholar"
    ARXIV = "arxiv"
    OPENALEX = "openalex"
    PUBMED = "pubmed"
    CROSSREF = "crossref"
    DBLP = "dblp"
    CORE = "core"                   # CORE 开放获取聚合 (非 MVP)
    UNPAYWALL = "unpaywall"         # Unpaywall OA 查找 (非 MVP)
    USER_UPLOAD = "user_upload"     # 用户手动上传
```

### 2.4 论文关系类型 (PaperRelationType)

```python
class PaperRelationType(StrEnum):
    """论文间的学术关系"""
    CITES = "cites"                 # A 引用了 B
    EXTENDS = "extends"             # A 扩展了 B 的工作
    REFUTES = "refutes"             # A 反驳了 B 的结论
    REPRODUCES = "reproduces"       # A 复现了 B 的实验
    REVIEWS = "reviews"             # A 综述了 B
    COMPARES = "compares"           # A 与 B 做了对比
    APPLIES = "applies"             # A 将 B 的方法应用到新领域
```

### 2.5 引用格式 (CitationStyle)

```python
class CitationStyle(StrEnum):
    APA = "apa"
    IEEE = "ieee"
    GBT7714 = "gbt7714"            # GB/T 7714
    CHICAGO = "chicago"
    MLA = "mla"
```

### 2.6 导出格式 (ExportFormat)

```python
class ExportFormat(StrEnum):
    MARKDOWN = "markdown"
    WORD = "word"                   # .docx
    LATEX = "latex"                 # .tex
    PDF = "pdf"
    HTML = "html"
    EXCEL = "excel"                 # .xlsx
    CSV = "csv"
    BIBTEX = "bibtex"              # .bib
    RIS = "ris"                    # .ris (Zotero / Mendeley / EndNote 互操作)
    SVG = "svg"
    PNG = "png"
```

---

## 三、项目实体 (Project)

一个"项目"对应用户发起的一次文献综述任务。

> **权威定义声明**: 本文档是系统数据结构的权威定义。当其他文档（如系统架构中的 ORM 示例）与本文档存在差异时，以本文档为准。

### 3.1 数据库表

```sql
CREATE TABLE projects (
    id              TEXT PRIMARY KEY,           -- UUID
    user_id         TEXT,                       -- 用户标识 (MVP 单用户可为空，多用户版必填)
    title           TEXT NOT NULL,              -- 项目标题 (可由 LLM 自动生成)
    user_query      TEXT NOT NULL,              -- 用户原始研究问题
    status          TEXT NOT NULL DEFAULT 'created',  -- ProjectStatus
    output_types    TEXT NOT NULL DEFAULT '["full_review"]',  -- JSON array of OutputType
    output_language TEXT NOT NULL DEFAULT 'zh', -- "zh" | "en" | "bilingual"
    citation_style  TEXT NOT NULL DEFAULT 'apa', -- CitationStyle

    -- 检索配置
    search_config   TEXT,                       -- JSON: {sources, filters, max_papers, ...}

    -- 统计
    paper_count     INTEGER NOT NULL DEFAULT 0,

    -- 成本追踪
    token_usage     TEXT,                       -- JSON: {total_input, total_output, by_agent: {search: {input, output}, ...}}
    token_budget    INTEGER,                    -- 用户设置的 Token 预算上限 (NULL 表示不限制)

    -- LangGraph 关联
    thread_id       TEXT,                       -- LangGraph Checkpointer thread ID

    -- 时间戳
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    deleted_at      TEXT                        -- 软删除
);

CREATE INDEX idx_projects_status ON projects(status) WHERE deleted_at IS NULL;
CREATE INDEX idx_projects_created ON projects(created_at);
CREATE INDEX idx_projects_user ON projects(user_id) WHERE user_id IS NOT NULL AND deleted_at IS NULL;
```

### 3.2 Pydantic Model

```python
from pydantic import BaseModel, Field
from datetime import datetime

class ProjectCreate(BaseModel):
    """创建项目请求"""
    user_query: str = Field(..., min_length=2, max_length=2000)
    output_types: list[OutputType] = Field(default=[OutputType.FULL_REVIEW])
    output_language: str = Field(default="zh", pattern="^(zh|en|bilingual)$")
    citation_style: CitationStyle = Field(default=CitationStyle.APA)
    search_config: dict | None = None

class ProjectResponse(BaseModel):
    """项目详情响应"""
    id: str
    user_id: str | None
    title: str
    user_query: str
    status: ProjectStatus
    output_types: list[OutputType]
    output_language: str
    citation_style: CitationStyle
    paper_count: int
    token_usage: dict | None
    token_budget: int | None
    created_at: datetime
    updated_at: datetime
```

### 3.3 search_config 结构

```json
{
  "sources": ["semantic_scholar", "arxiv"],
  "max_papers": 50,
  "year_range": {"min": 2020, "max": null},
  "min_citations": 0,
  "include_preprints": true,
  "keywords_override": null,
  "seed_paper_ids": []
}
```

### 3.4 数据访问层约定

业务代码通过 **SQLAlchemy ORM** 访问数据库，Schema 迁移使用 **Alembic**（详见[系统架构 7.3~7.4 节](system-architecture.md#七状态管理与持久化)）。

| 约定                   | 说明                                                                                 |
| ---------------------- | ------------------------------------------------------------------------------------ |
| **ORM 优先**           | 业务层只通过 SQLAlchemy ORM 操作数据库，不直接拼写 SQL                               |
| **方言无关**           | ORM 模型避免 SQLite/PostgreSQL 特有语法；UUID 存为 `String`；JSON 字段用 `JSON` 类型 |
| **Schema 迁移**        | 所有表结构变更通过 Alembic 迁移脚本管理，`alembic upgrade head` 创建/更新 Schema     |
| **本文档 Schema 定位** | 本文档的 SQL `CREATE TABLE` 为逻辑参考设计，实际 Schema 由 ORM 模型 + Alembic 生成   |
| **迁移路径**           | MVP 使用 SQLite，v0.5 迁移到 PostgreSQL 时仅需修改 `DATABASE_URL` 并重新 migrate     |

---

## 四、论文实体 (Paper)

论文在系统中全局去重存储，多个项目可引用同一篇论文。

### 4.1 数据库表

```sql
CREATE TABLE papers (
    id              TEXT PRIMARY KEY,           -- 内部 UUID

    -- 外部标识 (用于去重)
    doi             TEXT UNIQUE,                -- DOI (可能为空，如 arXiv 预印本)
    s2_id           TEXT UNIQUE,                -- Semantic Scholar Paper ID
    arxiv_id        TEXT UNIQUE,                -- arXiv ID (e.g., "2301.00001")

    -- 基本元数据
    title           TEXT NOT NULL,
    authors         TEXT NOT NULL,              -- JSON array: ["Author A", "Author B"]
    year            INTEGER,
    venue           TEXT,                       -- 发表期刊/会议
    abstract        TEXT,

    -- 引用统计
    citation_count  INTEGER DEFAULT 0,
    reference_count INTEGER DEFAULT 0,

    -- 来源
    source          TEXT NOT NULL,              -- PaperSourceType: 首次发现该论文的来源
    source_url      TEXT,                       -- 来源页面 URL
    pdf_url         TEXT,                       -- PDF 下载链接
    open_access     BOOLEAN DEFAULT FALSE,

    -- 文件存储
    pdf_path        TEXT,                       -- 已下载的 PDF 本地路径

    -- 时间戳
    fetched_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 论文全文文本独立存储，避免 papers 主表膨胀
-- 论文全文可达数万字，与高频查询的元数据分离后不影响主表性能
CREATE TABLE paper_fulltext (
    paper_id        TEXT PRIMARY KEY REFERENCES papers(id),
    content         TEXT NOT NULL,              -- 解析后的全文文本
    parser_used     TEXT,                       -- 解析器: "pymupdf" | "grobid"
    parsed_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_papers_doi ON papers(doi) WHERE doi IS NOT NULL;
CREATE INDEX idx_papers_s2_id ON papers(s2_id) WHERE s2_id IS NOT NULL;
CREATE INDEX idx_papers_arxiv ON papers(arxiv_id) WHERE arxiv_id IS NOT NULL;
CREATE INDEX idx_papers_year ON papers(year);
CREATE INDEX idx_papers_title ON papers(title);
```

### 4.2 去重策略

论文去重按以下优先级匹配：

```
1. DOI 完全匹配           (最可靠)
2. Semantic Scholar ID 匹配
3. arXiv ID 匹配
4. 标题模糊匹配 (归一化后相似度 > 0.95)
```

```python
async def find_or_create_paper(metadata: PaperMetadata) -> Paper:
    """查找已有论文或创建新记录，确保去重"""
    # 优先按 DOI 查找
    if metadata.doi:
        existing = await db.query(Paper).filter_by(doi=metadata.doi).first()
        if existing:
            return merge_metadata(existing, metadata)

    # 按 S2 ID 查找
    if metadata.s2_id:
        existing = await db.query(Paper).filter_by(s2_id=metadata.s2_id).first()
        if existing:
            return merge_metadata(existing, metadata)

    # 按 arXiv ID 查找
    if metadata.arxiv_id:
        existing = await db.query(Paper).filter_by(arxiv_id=metadata.arxiv_id).first()
        if existing:
            return merge_metadata(existing, metadata)

    # 标题模糊匹配 (最后手段)
    normalized = normalize_title(metadata.title)
    candidates = await db.query(Paper).filter(
        func.lower(Paper.title).contains(normalized[:50])
    ).all()
    for c in candidates:
        if title_similarity(c.title, metadata.title) > 0.95:
            return merge_metadata(c, metadata)

    # 创建新记录
    return await create_paper(metadata)
```

### 4.3 Pydantic Model

```python
class PaperMetadata(BaseModel):
    """论文元数据标准格式 — 所有数据源适配器的统一输出"""
    title: str
    authors: list[str]
    year: int | None = None
    venue: str | None = None
    abstract: str | None = None
    doi: str | None = None
    s2_id: str | None = None
    arxiv_id: str | None = None
    citation_count: int = 0
    reference_count: int = 0
    source: PaperSourceType
    source_url: str | None = None
    pdf_url: str | None = None
    url: str | None = None          # 论文来源页面 URL (详情页/landing page)
    open_access: bool = False

class PaperResponse(BaseModel):
    """论文详情响应"""
    id: str
    title: str
    authors: list[str]
    year: int | None
    venue: str | None
    abstract: str | None
    doi: str | None
    citation_count: int
    source: PaperSourceType
    pdf_available: bool
    analysis: "PaperAnalysisResponse | None" = None
```

---

## 五、论文分析实体 (PaperAnalysis)

每篇论文在特定项目上下文中的分析结果，由 Reader Agent 生成。

### 5.1 数据库表

```sql
CREATE TABLE paper_analyses (
    id              TEXT PRIMARY KEY,           -- UUID
    project_id      TEXT NOT NULL REFERENCES projects(id),
    paper_id        TEXT NOT NULL REFERENCES papers(id),

    -- 结构化摘要
    objective       TEXT,                       -- 研究目的
    methodology     TEXT,                       -- 研究方法
    datasets        TEXT,                       -- JSON array: 使用的数据集
    findings        TEXT,                       -- 主要发现
    limitations     TEXT,                       -- 局限性

    -- 方法论细节 (用于 Methodology Review 输出)
    method_category TEXT,                       -- 方法分类标签
    method_details  TEXT,                       -- JSON: {algorithm, architecture, hyperparams, ...}

    -- 关键概念
    key_concepts    TEXT,                       -- JSON array: ["concept A", "concept B"]

    -- 论文关系
    relations       TEXT,                       -- JSON array: [{target_paper_id, relation_type, evidence}]

    -- 质量评估 (Critic Agent 填充)
    quality_score   REAL,                       -- 0.0 - 1.0
    quality_notes   TEXT,                       -- 质量评估说明

    -- 在综述中的使用
    relevance_score REAL,                       -- 与研究问题的相关性 0.0 - 1.0

    -- 分析深度
    analysis_depth  TEXT NOT NULL DEFAULT 'abstract_only',
                                                -- "fulltext": 基于全文精读 | "abstract_only": 仅基于摘要

    -- 元信息
    analyzed_at     TEXT NOT NULL DEFAULT (datetime('now')),
    model_used      TEXT,                       -- 分析使用的 LLM 模型

    -- 软删除 (随项目级联)
    deleted_at      TEXT
);

-- 部分唯一索引：仅对未软删除的记录生效，避免软删除后无法重新分析同一论文
CREATE UNIQUE INDEX idx_analysis_unique_active
    ON paper_analyses(project_id, paper_id)
    WHERE deleted_at IS NULL;

CREATE INDEX idx_analysis_project ON paper_analyses(project_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_analysis_paper ON paper_analyses(paper_id) WHERE deleted_at IS NULL;
```

### 5.2 Pydantic Model

```python
class PaperAnalysisResponse(BaseModel):
    """论文分析结果"""
    paper_id: str
    objective: str | None
    methodology: str | None
    datasets: list[str]
    findings: str | None
    limitations: str | None
    method_category: str | None
    method_details: dict | None
    key_concepts: list[str]
    relations: list[PaperRelation]
    quality_score: float | None
    relevance_score: float | None
    analysis_depth: str             # "fulltext" | "abstract_only"

class PaperRelation(BaseModel):
    """论文间关系"""
    target_paper_id: str
    relation_type: PaperRelationType
    evidence: str | None = None     # 支撑该关系判断的文本证据
```

### 5.3 method_details 结构

供 Methodology Review 输出类型使用的方法论细节：

```json
{
  "algorithm": "Transformer-based seq2seq",
  "architecture": "Encoder-Decoder with cross-attention",
  "training_strategy": "Supervised fine-tuning + RLHF",
  "key_innovation": "Introduced retrieval-augmented generation",
  "evaluation_metrics": ["BLEU", "ROUGE-L", "Human evaluation"],
  "performance": {
    "BLEU": 42.3,
    "ROUGE-L": 38.7
  },
  "computational_cost": "8x A100 GPUs, 72h training",
  "applicable_scenarios": ["Code generation", "Text summarization"],
  "limitations_of_method": "Struggles with long-context dependencies"
}
```

---

## 六、综述输出实体 (ReviewOutput)

一个项目可生成多种类型的输出，每种独立存储。

### 6.1 数据库表

```sql
CREATE TABLE review_outputs (
    id              TEXT PRIMARY KEY,           -- UUID
    project_id      TEXT NOT NULL REFERENCES projects(id),
    output_type     TEXT NOT NULL,              -- OutputType

    -- 内容
    title           TEXT,                       -- 输出标题
    outline         TEXT,                       -- JSON: 大纲结构
    content         TEXT,                       -- 主体内容 (Markdown 格式)
    structured_data TEXT,                       -- JSON: 结构化数据 (对比矩阵、Gap 列表等)
    references      TEXT,                       -- JSON array: 参考文献列表

    -- 版本管理
    version         INTEGER NOT NULL DEFAULT 1,
    parent_id       TEXT REFERENCES review_outputs(id), -- 上一版本
    revision_notes  TEXT,                       -- 本次修改说明

    -- 配置
    language        TEXT NOT NULL DEFAULT 'zh',
    citation_style  TEXT NOT NULL DEFAULT 'apa',
    writing_style   TEXT,                       -- "narrative" | "systematic" | "critical"

    -- 引用验证 (verify_citations 节点填充)
    citation_verification TEXT,                 -- JSON array: [{ref_index, paper_id, status, source, verified_at}]
                                                -- status: "verified" | "unverified" | "pending"

    -- 导出记录
    export_formats  TEXT,                       -- JSON array: 已导出的格式

    -- 时间戳
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    deleted_at      TEXT                        -- 软删除 (随项目级联)
);

CREATE INDEX idx_outputs_project ON review_outputs(project_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_outputs_type ON review_outputs(output_type) WHERE deleted_at IS NULL;
CREATE INDEX idx_outputs_project_type ON review_outputs(project_id, output_type) WHERE deleted_at IS NULL;
```

### 6.2 各输出类型的 content 与 structured_data 用法

| OutputType           | content (Markdown) | structured_data (JSON)                                |
| -------------------- | ------------------ | ----------------------------------------------------- |
| `quick_brief`        | 1-2 页综述文本     | `null`                                                |
| `annotated_bib`      | 分组说明文字       | `{groups: [{name, papers: [{id, annotation}]}]}`      |
| `full_review`        | 完整综述正文       | `null`                                                |
| `methodology_review` | 方法论分析正文     | `{methods: [{name, pros, cons, scenarios, papers}]}`  |
| `research_roadmap`   | 研究脉络叙述性文字 | `{milestones: [{year, event, papers, significance}]}` |
| `comparison_matrix`  | 对比分析讨论文字   | `{dimensions: [...], rows: [{method, values}]}`       |
| `gap_report`         | Gap 分析讨论文字   | `{gaps: [{description, evidence, severity}]}`         |
| `trend_report`       | 趋势解读文字       | `{trends: [{keyword, yearly_counts, direction}]}`     |
| `knowledge_map`      | （通常为空）       | `{nodes: [...], edges: [...]}`                        |
| `timeline`           | （通常为空）       | `{events: [{year, title, description, paper_ids}]}`   |

### 6.3 citation_verification 结构

`verify_citations` 工作流节点（见[系统架构 4.1 节](system-architecture.md#四orchestrator-编排引擎设计)）生成的引用验证结果，内嵌于 `review_outputs` 中：

```json
[
  {
    "ref_index": 1,
    "paper_id": "uuid-xxx",
    "cited_as": "Chen et al., 2021",
    "status": "verified",
    "source": "semantic_scholar",
    "verified_at": "2026-03-30T12:00:00Z"
  },
  {
    "ref_index": 5,
    "cited_as": "Li & Wang, 2024",
    "status": "unverified",
    "source": null,
    "verified_at": "2026-03-30T12:00:02Z"
  }
]
```

| 字段          | 说明                                                                 |
| ------------- | -------------------------------------------------------------------- |
| `ref_index`   | 引用在 `references` 列表中的索引位置                                 |
| `paper_id`    | 关联的 papers 表 ID（unverified 时可能为空）                         |
| `cited_as`    | 正文中的引用标记文本                                                 |
| `status`      | `"verified"` 已确认存在 · `"unverified"` 未找到 · `"pending"` 待验证 |
| `source`      | 验证所用数据源（Semantic Scholar / CrossRef / DOI 等）               |
| `verified_at` | 验证时间 (ISO 8601)                                                  |

> **设计说明**: 引用验证结果内嵌在 `review_outputs` 而非独立建表，因为验证结果与具体的综述版本强绑定——每次重新生成或修订综述时，引用列表和验证状态需要同步更新。内嵌 JSON 避免了跨表级联更新的复杂性。

### 6.4 Pydantic Model

```python
class ReviewOutputCreate(BaseModel):
    """创建/更新综述输出"""
    output_type: OutputType
    title: str | None = None
    outline: dict | None = None
    content: str | None = None
    structured_data: dict | None = None
    references: list[dict] | None = None
    writing_style: str | None = None

class ReviewOutputResponse(BaseModel):
    """综述输出响应"""
    id: str
    project_id: str
    output_type: OutputType
    title: str | None
    outline: dict | None
    content: str | None
    structured_data: dict | None
    references: list[dict] | None
    version: int
    language: str
    citation_style: CitationStyle
    writing_style: str | None
    citation_verification: list[dict] | None
    created_at: datetime
    updated_at: datetime
```

### 6.5 Methodology Review 的 structured_data 示例

```json
{
  "overview": "本报告对比分析了医学影像分割领域的 5 种主要方法论路线。",
  "methods": [
    {
      "name": "U-Net 系列",
      "category": "CNN-based",
      "description": "基于编码器-解码器结构的卷积网络方法",
      "representative_papers": ["paper_id_1", "paper_id_2"],
      "pros": ["训练效率高", "小数据集表现好", "结构简洁"],
      "cons": ["感受野有限", "长程依赖建模差"],
      "applicable_scenarios": ["小规模数据集", "实时推理需求"],
      "performance_summary": {"Dice": "85-90%", "典型数据集": "ISIC, BraTS"}
    },
    {
      "name": "Vision Transformer 系列",
      "category": "Transformer-based",
      "description": "基于自注意力机制的全局建模方法",
      "representative_papers": ["paper_id_3", "paper_id_4"],
      "pros": ["全局上下文建模", "可扩展性强"],
      "cons": ["需要大量训练数据", "计算成本高"],
      "applicable_scenarios": ["大规模数据集", "精度优先场景"],
      "performance_summary": {"Dice": "88-93%", "典型数据集": "Synapse, ACDC"}
    }
  ],
  "comparison_dimensions": [
    {"dimension": "计算效率", "ranking": ["U-Net", "TransUNet", "nnFormer"]},
    {"dimension": "精度", "ranking": ["nnFormer", "TransUNet", "U-Net"]},
    {"dimension": "数据效率", "ranking": ["U-Net", "nnFormer", "TransUNet"]}
  ],
  "recommendation": "对于临床部署场景，推荐 U-Net 变体；对于研究探索，推荐 Transformer 混合架构。"
}
```

### 6.6 Research Roadmap 的 structured_data 示例

```json
{
  "research_question": "深度学习在医学影像分割中的演进",
  "timeline_summary": "从传统方法到 CNN 再到 Transformer 的三阶段演进",
  "phases": [
    {
      "name": "传统方法阶段",
      "period": "2012-2015",
      "key_insight": "基于手工特征的分割方法主导",
      "papers": ["paper_id_1"],
      "transition_trigger": "深度学习在 ImageNet 上的突破"
    },
    {
      "name": "CNN 主导阶段",
      "period": "2015-2020",
      "key_insight": "U-Net 系列成为医学影像分割的事实标准",
      "papers": ["paper_id_2", "paper_id_3"],
      "transition_trigger": "Vision Transformer 的提出"
    },
    {
      "name": "Transformer 融合阶段",
      "period": "2020-至今",
      "key_insight": "CNN+Transformer 混合架构兼顾局部与全局特征",
      "papers": ["paper_id_4", "paper_id_5"],
      "transition_trigger": "进行中"
    }
  ],
  "milestones": [
    {"year": 2015, "event": "U-Net 提出", "paper_id": "paper_id_2", "significance": "奠定医学影像分割基线架构"},
    {"year": 2020, "event": "ViT 提出", "paper_id": "paper_id_4", "significance": "引入自注意力到视觉任务"},
    {"year": 2021, "event": "TransUNet", "paper_id": "paper_id_5", "significance": "首次在医学影像分割中融合 Transformer"}
  ],
  "open_questions": [
    "如何在保持 Transformer 精度的同时降低计算成本？",
    "自监督预训练在医学影像分割中的潜力尚未充分挖掘"
  ]
}
```

---

## 七、项目-论文关联 (ProjectPaper)

### 7.1 数据库表

```sql
CREATE TABLE project_papers (
    id              TEXT PRIMARY KEY,           -- UUID
    project_id      TEXT NOT NULL REFERENCES projects(id),
    paper_id        TEXT NOT NULL REFERENCES papers(id),

    -- 状态
    status          TEXT NOT NULL DEFAULT 'candidate',
                    -- "candidate": 候选 | "selected": 用户确认 | "excluded": 用户排除

    -- 来源信息
    found_by        TEXT,                       -- "search" | "snowball" | "user_upload" | "recommendation"
    search_query    TEXT,                       -- 发现该论文时使用的查询词

    -- 排序
    relevance_rank  INTEGER,                    -- 在检索结果中的排名

    -- 时间戳
    added_at        TEXT NOT NULL DEFAULT (datetime('now')),
    deleted_at      TEXT,                       -- 软删除 (随项目级联)

    UNIQUE(project_id, paper_id)
);

CREATE INDEX idx_pp_project ON project_papers(project_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_pp_paper ON project_papers(paper_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_pp_status ON project_papers(project_id, status) WHERE deleted_at IS NULL;
```

### 7.2 Pydantic Model

```python
class ProjectPaperResponse(BaseModel):
    """项目中的论文"""
    paper: PaperResponse
    status: str                     # "candidate" | "selected" | "excluded"
    found_by: str | None
    relevance_rank: int | None
    added_at: datetime
```

---

## 八、工作流状态与 Agent 数据结构

### 8.1 ReviewState 与数据库的映射关系

`ReviewState` 是 LangGraph 工作流中的内存状态，通过 Checkpointer 持久化。与业务数据库的映射关系：

```
ReviewState (in-memory, LangGraph)          Database Tables
────────────────────────────────           ──────────────
user_query                         ◀──▶    projects.user_query
output_types                       ◀──▶    projects.output_types
candidate_papers                   ◀──▶    project_papers (status=candidate)
selected_papers                    ◀──▶    project_papers (status=selected)
uploaded_papers                    ◀──▶    project_papers (found_by='user_upload')
paper_analyses                     ◀──▶    paper_analyses
outline                            ◀──▶    review_outputs.outline
full_draft                         ◀──▶    review_outputs.content
references                         ◀──▶    review_outputs.references
citation_verification              ◀──▶    review_outputs.citation_verification
current_phase                      ◀──▶    projects.status
token_usage                        ◀──▶    projects.token_usage
token_budget                       ◀──▶    projects.token_budget
fulltext_coverage                  ──▶     从 paper_analyses.analysis_depth 聚合计算
feedback_search_queries            ──      仅 Checkpointer 持久化 (工作流运行时临时状态)
feedback_iteration_count           ──      仅 Checkpointer 持久化 (工作流运行时临时状态)
```

**设计决策**: ReviewState 是工作流运行时的完整快照。工作流完成后，最终结果回写到业务数据库。工作流运行期间，LangGraph Checkpointer 负责状态持久化和断点恢复。

### 8.2 Analyst / Critic Agent 中间数据结构

> **MVP 范围说明**: 以下数据结构供 Analyst Agent 和 Critic Agent 使用（v0.3 启用），MVP 阶段不实现。预先定义以确保数据模型的前向兼容性，后续启用时无需修改已有表结构。

这些结构存在于 ReviewState 中，按需回写到 `review_outputs.structured_data`：

```python
class TopicCluster(TypedDict):
    """主题聚类"""
    cluster_id: str
    name: str                       # LLM 命名的主题
    description: str
    paper_ids: list[str]
    keywords: list[str]
    paper_count: int

class ComparisonEntry(TypedDict):
    """对比矩阵条目"""
    method_name: str
    paper_id: str
    metrics: dict[str, str | float] # {"accuracy": 94.2, "speed": "fast"}
    datasets: list[str]
    year: int

class ResearchGap(TypedDict):
    """研究空白"""
    description: str
    severity: str                   # "high" | "medium" | "low"
    evidence_paper_ids: list[str]   # 支撑该判断的论文
    suggested_direction: str | None

class TrendDataPoint(TypedDict):
    """趋势数据点"""
    keyword: str
    yearly_counts: dict[int, int]   # {2020: 5, 2021: 12, 2022: 18}
    direction: str                  # "rising" | "stable" | "declining"
```

---

## 九、向量数据库 Schema

使用 Chroma 存储论文 embedding，用于语义检索和相似论文推荐。

### 9.1 Collection 设计

```python
# Collection: paper_embeddings
# 每篇论文的摘要/段落 embedding

{
    "collection_name": "paper_embeddings",
    "metadata_schema": {
        "paper_id": "string",       # 关联 papers.id
        "chunk_type": "string",     # "abstract" | "section" | "full"
        "section_name": "string",   # 段落所属章节名
        "year": "integer",
        "source": "string",        # PaperSourceType
    },
    "embedding_model": "text-embedding-3-small",  # OpenAI embedding
    "distance_metric": "cosine"
}
```

### 9.2 典型查询场景

| 场景             | 查询方式                                         |
| ---------------- | ------------------------------------------------ |
| **相似论文推荐** | 用论文 A 的 abstract embedding 查找最近邻        |
| **语义检索**     | 用用户查询的 embedding 搜索相关论文段落          |
| **主题聚类辅助** | 获取所有论文的 embedding 向量，执行 k-means 聚类 |

---

## 十、缓存 Key 设计

### 10.1 Redis Key 命名规范

```
{namespace}:{resource_type}:{identifier}:{sub_key}
```

### 10.2 Key 清单

| Key Pattern                   | TTL  | 用途                          |
| ----------------------------- | ---- | ----------------------------- |
| `search:s2:{query_hash}`      | 24h  | Semantic Scholar 检索结果缓存 |
| `search:arxiv:{query_hash}`   | 24h  | arXiv 检索结果缓存            |
| `paper:meta:{doi_or_id}`      | 7d   | 论文元数据缓存                |
| `paper:citations:{paper_id}`  | 7d   | 引用列表缓存                  |
| `paper:references:{paper_id}` | 7d   | 参考文献列表缓存              |
| `project:events:{project_id}` | 1h   | SSE 事件流缓存                |
| `ratelimit:{source}:{window}` | 动态 | API 速率限制计数器            |

---

## 十一、MVP 实现范围

### 11.1 MVP 包含的数据表

| 表名             | MVP | 说明                     |
| ---------------- | --- | ------------------------ |
| `projects`       | ✅   | 项目管理                 |
| `papers`         | ✅   | 论文存储（全局去重）     |
| `paper_fulltext` | ✅   | 论文全文文本（独立存储） |
| `project_papers` | ✅   | 项目-论文关联            |
| `paper_analyses` | ✅   | 论文分析结果             |
| `review_outputs` | ✅   | 综述输出                 |

### 11.2 MVP 包含的输出类型

| OutputType           | MVP | 说明                                                |
| -------------------- | --- | --------------------------------------------------- |
| `quick_brief`        | ✅   | 快速摘要                                            |
| `annotated_bib`      | ✅   | 注释文献列表                                        |
| `full_review`        | ✅   | 完整综述                                            |
| `methodology_review` | —   | 依赖 Analyst/Critic Agent 的方法对比能力，v0.3 开放 |
| `research_roadmap`   | —   | 依赖 Analyst/Critic Agent 的脉络分析能力，v0.3 开放 |
| `comparison_matrix`  | —   | 需要 Analyst Agent                                  |
| `gap_report`         | —   | 需要 Critic Agent                                   |
| `trend_report`       | —   | 需要 Analyst Agent                                  |
| `knowledge_map`      | —   | 需要前端可视化                                      |
| `timeline`           | —   | 需要前端可视化                                      |

### 11.3 MVP 数据库文件

```
data/
├── app.db              # SQLite 业务数据库 (projects, papers, ...)
├── checkpoints.db      # LangGraph Checkpointer
├── chroma/             # Chroma 向量数据库
└── uploads/            # 用户上传的 PDF 文件
```
