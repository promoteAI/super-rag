## super-rag 工作流 / 节点编排设计（对标并超越 nodetool）

### 1. 目标与原则

- **目标**：在借鉴 `nodetool` DAG + 画布的基础上，做一套更适合 RAG / 多 Agent 开发场景的工作流系统，既好用又工程化。
- **核心原则**：
  - **RAG 领域专用**：为 RAG / 检索 / Agent 设计专门的数据类型与节点，而不是 all-in-one 通用节点。
  - **高可观测性**：任意边、任意节点都能便捷查看中间数据，支持回放与局部重跑。
  - **工程易集成**：每个工作流都能以 SDK / HTTP API / CLI 的形式直接被业务调用。
  - **模板优先**：常见场景（ingest / index / query / eval）有开箱即用的工作流模板。

---

### 2. 核心概念模型

#### 2.1 基础对象

- **Workflow（工作流）**
  - 有向无环图（DAG），由若干 `Node` 与 `Edge` 组成。
  - 元数据：`id`、`version`、`name`、`tags`（如 `ingest` / `query` / `eval`）、`status`（draft/published）。

- **Node（节点）**
  - 属性：`id`、`type`、`impl`（后端实现标识）、`config`（配置）、`ui_meta`（画布位置、颜色等）。
  - 类别：`Source` / `Transform` / `Retrieval` / `LLM` / `Tool` / `Control` / `Eval` 等。

- **Port（端口）**
  - 输入端口 / 输出端口，每个端口有**强类型**。
  - RAG 领域关键类型：
    - `DocumentBatch`
    - `ChunkBatch`
    - `EmbeddingBatch`
    - `Query`（text + filters + user_id 等）
    - `RetrievedItems`
    - `ChatMessages`
    - `ToolCall` / `ToolResult`
    - `EvalMetric` / `EvalSample`

- **Edge（边）**
  - `from: (node_id, out_port)` → `to: (node_id, in_port)`。
  - 仅允许类型兼容的连接（前后端双重校验）。
  - 支持多播（一个输出连接多个输入）和通过 `Merge` 节点做聚合。

- **Run（运行实例）**
  - 某次 workflow 执行的记录：
    - `run_id`、`workflow_id`、`workflow_version`、`input`、`output`、`status`、`created_at`、`finished_at`。
    - 每个节点对应 `NodeRun`：
      - 入参 / 出参（可裁剪存储）、耗时、错误、日志。

- **Artifact（工件）**
  - 对任意节点输出可选择持久化为 Artifact：
    - 支持 debug：点击边即可查看最近/历史数据样本。
    - 支持复现：以该 Artifact 作为输入，重跑后半段子图。
    - 支持评估与训练数据沉淀。

---

### 3. 为 RAG 定制的节点分层

#### 3.1 Ingest / 索引流水线节点

- **Source 节点**
  - `FileUploader`：上传本地文件、目录。
  - `WebCrawler`：爬取网页，并产出 `DocumentBatch`。
  - `GitRepoReader`：扫描代码仓库，适配 code-aware chunking。
  - `DBReader`：读取数据库表记录、视图。

- **Preprocess 节点**
  - `TextCleaner`：清洗文本（去 HTML、去噪音）。
  - `LanguageDetector`：识别语种。
  - `MetadataExtractor`：提取标题、作者、时间、标签等。

- **Chunk 节点**
  - `FixedSizeChunker`：规则分段（按字数/句数）。
  - `SemanticChunker`：基于 embedding/LLM 的语义分段。
  - `CodeAwareChunker`：识别函数、类、文件结构。

- **Embed 节点**
  - `TextEmbedder`：针对文本的向量化，配置 embedding 模型。
  - `MultiModalEmbedder`：图文 / 附件的多模态向量化。

- **Index 节点**
  - `VectorIndexer`：入库到 Faiss / Pgvector / Chroma / 内置向量库。
  - `KeywordIndexer`：BM25 等关键字索引。
  - `HybridIndexer`：混合索引（向量 + 关键词）。

#### 3.2 查询 / 检索 / 生成流水线节点

- **Query 节点**
  - `QueryNormalizer`：标准化用户查询，填充默认过滤条件等。
  - `QueryRewriter`：扩写、多路 Query 生成（如 multi-query RAG）。

- **Retrieve 节点**
  - `VectorRetriever`：向量召回。
  - `HybridRetriever`：结合向量和关键词检索。
  - `SQLRetriever`：对结构化数据库进行查询。

- **Rank / Filter 节点**
  - `CrossEncoderReranker`：交叉编码重排，提高相关性。
  - `MetadataFilter`：按标签、时间、权限等过滤。

- **Augment 节点**
  - `PromptAugmenter`：将 query + context 拼装成 prompt。
  - `ContextCompressor`：对长 context 做压缩、聚合。

- **LLM 节点**
  - `ChatModel`：对话模型节点，支持多家 provider / 本地模型。
  - `ToolCallingModel`：专门用于工具调用、Agent。

- **Tool / Action 节点**
  - `HTTPTool`：通用 HTTP 调用。
  - `CodeExecutionTool`：执行代码片段（沙箱）。
  - `DBWriteTool`：写数据库，更新业务状态。

- **Control 节点**
  - `If`：条件分支，根据布尔值选择路径。
  - `Switch`：多路分支，根据枚举值选择一路。
  - `Map`：对一个集合并行执行子工作流。
  - `Merge`：合并多个分支结果。

#### 3.3 评估 / 监控节点（超越 nodetool 的差异点）

- **Eval 节点**
  - `LLMJudge`：使用 LLM 评估回答质量（相关性、完整性等）。
  - `StringMatchEval`：基于字符串或正则的简单匹配评估。
  - `VectorRecallEval`：评估向量检索的召回质量。
  - `CostEstimator`：估算 token 使用量与费用。

- **Logging / Metrics 节点**
  - `TraceExporter`：导出 trace 至 OpenTelemetry / 自建链路追踪系统。
  - `MetricsAggregator`：聚合 QPS、latency、hit-rate 等指标。

---

### 4. 运行时架构（后端）

#### 4.1 Workflow 定义与存储

- 使用 Pydantic / JSON Schema 定义：
  - `WorkflowDefinition`
  - `NodeDefinition`
  - `PortDefinition`
  - `EdgeDefinition`
- 持久化：
  - 数据库表 `workflows`：
    - 字段：`id`、`version`、`name`、`definition_json`、`status`、`created_at`、`updated_at`。
  - 支持：
    - `draft` / `published` 状态。
    - 从已有版本 `clone_from` 形成新版本。

#### 4.2 执行引擎（Executor）

- **图分析**
  - 加载并解析 `WorkflowDefinition`。
  - 校验 DAG 无环、端口类型匹配。
  - 拓扑排序生成执行计划。

- **执行模型**
  - 推荐采用异步 + 任务队列（如 `asyncio` / Celery / RQ）：
    - 支持节点并行执行。
    - 支持子图执行（Workflow 作为一个 Node 被复用）。

- **上下文管理**
  - `ExecutionContext`：
    - 全局变量：`user_id`、`tenant_id`、`env`、`feature_flag` 等。
    - 运行配置：是否开启 debug snapshot、日志等级等。

- **持久化与观测**
  - 每个 `NodeRun` 记录：
    - 入参 / 出参（带采样与红线控制）。
    - 开始/结束时间、耗时、错误堆栈、日志。
  - 对接现有日志/监控系统（如 OpenTelemetry / Prometheus）。

#### 4.3 集成接口

- **SDK 层**（以 Python 为例）
  - `run_workflow(workflow_id, input, version=None, **options)`
  - `resume_from_node(run_id, node_id, override_input=None)`

- **API 层**
  - `POST /api/workflows/{id}/run`：触发执行。
  - `GET /api/workflows/{id}/runs`：查询运行历史。
  - `GET /api/workflows/{id}/graph`：获取 workflow 定义。

- **CLI 层**
  - `rag wf run <workflow_id> --input examples/query.json`
  - `rag wf inspect <run_id>`

---

### 5. 前端编排体验（canvas 设计）

#### 5.1 画布基础能力

- 基于 React + React Flow（或类似库）实现：
  - 节点拖拽、连线、缩放、框选。
  - 端口类型校验：不兼容类型不能连线。
- 左侧 `Node Palette`：
  - 按「Ingest / Index / Query / Eval / Tool / Control」分组展示节点。
  - 支持搜索节点（按名称、描述、标签）。

#### 5.2 RAG 特化的 UX 设计

- **向导式新建工作流**
  - 新建时先选择模板：
    - `RAG-基础问答`
    - `RAG-混合检索`
    - `RAG-多路 Query + 重排`
    - `RAG-离线评估 pipeline`
  - 生成一张预配置的 workflow 图，用户只需补充数据源、模型配置等。

- **智能补线 / 推荐节点**
  - 用户在已有 ingest 流中拖入一个 `VectorIndexer` 节点：
    - 系统自动推荐并可一键创建：
      - `FileUploader -> Chunker -> TextEmbedder -> VectorIndexer`。
  - 基于端口类型和上下文自动推荐「下一个常见节点」。

- **统一配置面板**
  - 点击节点，右侧打开配置表单：
    - 字段带校验（必填、范围、枚举等）。
    - 支持「预设」：如 embedding 模型预设、向量库连接预设。

- **数据预览 & 回放**
  - 点任意边 / 节点：
    - 显示最近一次 run 的输入/输出样本（支持切换不同 run）。
    - 支持「从该节点输出重新执行后半段子图」：
      - 用于 debug downstream 逻辑。

- **运行可视化**
  - 正在执行的节点高亮（如绿色运行中、黄色排队、红色失败）。
  - hover 节点显示：
    - 最近一次执行耗时、错误摘要、调用次数等。

---

### 6. 相比 nodetool 的关键增强点

1. **RAG 领域专用类型系统**
   - 引入 `DocumentBatch` / `ChunkBatch` / `EmbeddingBatch` / `RetrievedItems` / `ChatMessages` 等类型。
   - 带来更强的连线校验与节点推荐能力。

2. **模板化 RAG 工作流**
   - 内置 ingest / index / query / eval 的完整模板：
     - 让大部分用户不必从空白画布开始搭建。

3. **评估与观测为一等公民**
   - Eval 节点与 Metrics 节点让「构建工作流」与「评估效果」统一在一张图里。
   - 支持在生产流量旁路构建评估 pipeline。

4. **工程化集成体验**
   - 每个 workflow 天然映射为：
     - 一个 SDK 函数；
     - 一个 HTTP API；
     - 一个 CLI 命令。
   - 大幅缩短从「画图试验」到「服务上线」的距离。

5. **更强的调试 / 复现能力**
   - 任意边可查看样本数据，支持回放、局部重跑。
   - 每个 run 都有完整的 trace 与 artifact，方便问题定位与效果分析。

---

### 7. 后续落地建议

- **后端优先**：
  - 在后端实现 `WorkflowDefinition` / `NodeDefinition` / `Executor` 的核心模型与接口。
  - 定义最小可用节点集合（如：FileUploader、Chunker、TextEmbedder、VectorIndexer、VectorRetriever、ChatModel）。
- **前端渐进增强**：
  - 先用 React Flow 打通一个最小 demo（简单 ingest + query 流）。
  - 然后逐步增加节点类型、模板、数据预览等高级功能。

---

### 8. 参考 JSON 格式与解析（易用性对齐）

为与前端/画布及 nodetool 类 workflow JSON 对齐，nodeflow 支持**参考 JSON 结构**，便于导入导出与 API 一致。

#### 8.1 顶层结构

- **工作流元数据**：`id`、`name`、`description`、`tags`、`input_schema`、`output_schema`。
- **图**：`graph.nodes`、`graph.edges`（端口级连接）。

```json
{
  "id": "workflow-id",
  "name": "Summarize Paper",
  "description": "...",
  "tags": ["audio", "example"],
  "graph": {
    "nodes": [...],
    "edges": [...]
  },
  "input_schema": { "type": "object", "properties": { "url": { "type": "string" } }, "required": ["url"] },
  "output_schema": { "type": "object", "properties": {} }
}
```

#### 8.2 节点（graph.nodes）

- `id`、`type`、`data`（扁平配置：`value`、`name`、`start_page`、`end_page`、`prompt`、`model` 等）。
- 可选 `ui_properties`（画布位置、宽高等）。

#### 8.3 边（graph.edges）

- `source`、`target`、`sourceHandle`（默认 `"output"`）、`targetHandle`（目标输入端口名）。
- 解析时自动将「目标节点的 `targetHandle`」绑定为 `{{ nodes.<source>.output.<sourceHandle> }}`。

#### 8.4 工作流入参

- `input_schema` 定义工作流级入参（如 `url`）。
- 若某节点 `data.name` 与 `input_schema.properties` 的 key 一致，该节点的 `value` 端口会绑定为 `{{ globals.<key> }}`，运行时由 `initial_data` 覆盖。

#### 8.5 解析与兼容

- **Parser**：`nodeflowParser.parse(data)` 自动识别格式：
  - 存在 `graph` → 按参考格式解析（边驱动 input_values、data 补默认值、input_schema 映射）。
  - 否则 → 按原有 YAML 格式解析（顶层 `nodes`/`edges`，`node.data.input.values`）。
- **Engine**：执行时 `initial_data` 写入 `global_variables`，端口引用 `nodes.X.output.Y` 与 `globals.Z` 行为不变；单端口输出时 `output` 键可省略（整段输出视为 output 端口）。

示例见 `super_rag/nodeflow/examples/new_flow_structure.json`。

