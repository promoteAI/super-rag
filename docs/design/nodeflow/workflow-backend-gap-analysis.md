# 后端工作流差距分析与改造方案（基于 references/flow）

## 目标与范围

- 参考实现：`references/flow` 的工作流系统能力
- 我们当前实现：`super_rag/nodeflow` + `super_rag/api/flow.py` + `super_rag/service/flow_service.py`
- 本文只覆盖后端改造设计，不涉及前端与运行环境变更

## 参考实现能力拆解（baseline）

### 1) 图结构与类型校验

参考实现将 workflow graph 抽象为 `Graph`，包含节点、边、拓扑排序与类型校验逻辑。  
（见 `Graph.from_dict()` 对节点解析与边合法性过滤，以及类型元数据校验的依赖）

```20:33:references/flow/workflows/graph.py
class Graph(BaseModel):
    """
    Represents a graph data structure for workflow management and analysis.
    ...
    - JSON schema generation for inputs and outputs
    - Topological sorting of nodes
    """
```

### 2) 节点基类与流式执行模型

`BaseNode` 统一了 buffered/streaming 的执行语义，并通过类型元数据做输入输出对齐。  
（强调“所有输出都是 stream”的执行模型）

```25:40:references/flow/workflows/base_node.py
Unified Input/Streaming Model
-----------------------------
- Everything is a stream; a scalar is a stream of length 1.
...
- Nodes either consume once (buffered `process`) or iteratively (`gen_process`)
```

### 3) 执行引擎与运行管理

`WorkflowRunner` 使用 NodeActor 驱动节点并发，支持 GPU 锁、缓存、日志等运行机制。  

```1:23:references/flow/workflows/workflow_runner.py
Workflow execution engine using per-node actors for DAG graphs.
...
- One lightweight async task (NodeActor) per node drives that node to completion.
- Nodes either consume once (buffered `process`) or iteratively (`gen_process`)
```

### 4) 工作流与版本模型

参考实现使用 `Workflow` 与 `WorkflowVersion` 模型存储工作流本体与版本快照。  

```31:60:references/flow/models/workflow.py
@DBIndex(columns=["user_id"])
class Workflow(DBModel):
    id: str = DBField(hash_key=True)
    user_id: str = DBField(default="")
    access: str = DBField(default="private")
    name: str = DBField(default="")
    ...
    graph: dict = DBField(default_factory=dict)
```

```28:47:references/flow/models/workflow_version.py
@DBIndex(columns=["workflow_id", "save_type", "created_at"])
class WorkflowVersion(DBModel):
    id: str = DBField(hash_key=True)
    workflow_id: str = DBField(default="")
    user_id: str = DBField(default="")
    version: int = DBField(default=1)
    graph: dict = DBField(default_factory=dict)
```

## 我们当前实现现状（nodeflow）

### 1) 运行引擎

`NodeflowEngine` 做了 DAG 拓扑排序与分组并行执行，并内置事件流。  

```52:133:super_rag/nodeflow/engine.py
class NodeflowEngine:
    """Engine for executing nodeflow instances"""
    ...
    async def execute_nodeflow(self, nodeflow: NodeflowInstance, initial_data: Dict[str, Any] = None):
        ...
        sorted_nodes = self._topological_sort(nodeflow)
        for node_group in self._find_parallel_groups(nodeflow, sorted_nodes):
            await self._execute_node_group(nodeflow, node_group)
```

### 2) 模型与图结构

`NodeflowInstance`/`NodeInstance`/`Edge` 是轻量 dataclass，输入输出仅用 JSON schema，缺少强类型 port 定义。  

```12:53:super_rag/nodeflow/base/models.py
@dataclass
class NodeInstance:
    id: str
    type: str
    input_schema: dict = field(default_factory=dict)
    input_values: dict = field(default_factory=dict)
    output_schema: dict = field(default_factory=dict)
```

### 3) API 与服务层

当前仅支持“一次性运行”，且 workflow 存储在 `Bot.config` 中。  

```16:26:super_rag/api/flow.py
@router.post("/workflows/run", response_model=view_models.WorkflowRunResponse)
async def run_workflow_once_view(...):
    return await flow_service_global.run_workflow_once(str(user.id), body)
```

```42:70:super_rag/service/flow_service.py
async def run_workflow_once(...):
    ...
    flow = nodeflowParser.parse(workflow_dict)
    engine = NodeflowEngine()
    outputs, system_outputs = await engine.execute_nodeflow(flow, initial_data)
```

```382:392:super_rag/db/models.py
class Bot(Base):
    __tablename__ = "bot"
    ...
    config = Column(Text, nullable=False)
```

## 差距清单（核心主题）

### A. 存储与版本化

- 参考实现：`Workflow` + `WorkflowVersion` 独立存储
- 当前实现：workflow 仅存于 `Bot.config`，无版本管理

### B. 运行记录与可观测性

- 参考实现：Job/Run/NodeRun 级别记录与日志
- 当前实现：只有执行期事件流，无持久化 run 记录

### C. 类型系统与图校验

- 参考实现：端口类型元数据与边连接类型校验
- 当前实现：仅 JSON schema，缺少 PortDefinition 与 edge 类型校验

### D. API/服务边界

- 参考实现：Workflow CRUD、版本、run、触发等完整接口
- 当前实现：仅 `/workflows/run` + bot 绑定的 `get/update flow`

## 改造方案（分阶段）

### 阶段一：数据模型与版本化设计

**目标：** 摆脱 `Bot.config` 作为唯一存储，建立工作流与版本管理基础。  

**建议新增模型（SQLAlchemy 草案）**

```python
class WorkflowTable(Base):
    __tablename__ = "workflow"
    id: str
    user: str
    name: str
    description: str | None
    tags: list[str] | None
    status: str  # draft/published
    graph: JSON
    created_at: datetime
    updated_at: datetime

class WorkflowVersionTable(Base):
    __tablename__ = "workflow_version"
    id: str
    workflow_id: str
    version: int
    graph: JSON
    save_type: str  # manual/autosave
    created_at: datetime
```

**关联策略**

- `Bot` 可引用 `workflow_id`（推荐）或保留快照字段（兼容）
- 保留 `config.flow` 作为旧数据迁移源

### 阶段二：执行与运行记录

**目标：** 持久化每次运行与节点输入输出，支持后续可观测与回放。  

**新增模型草案**

```python
class WorkflowRunTable(Base):
    __tablename__ = "workflow_run"
    id: str
    workflow_id: str
    workflow_version: int | None
    input: JSON
    output: JSON
    status: str  # running/succeeded/failed
    started_at: datetime
    finished_at: datetime | None

class NodeRunTable(Base):
    __tablename__ = "node_run"
    id: str
    run_id: str
    node_id: str
    input_snapshot: JSON | None
    output_snapshot: JSON | None
    duration_ms: int | None
    error: str | None
```

**引擎扩展接口**

- `NodeflowEngine` 增加可选 `RunRecorder`（事件钩子）用于记录 node run
- `FlowService.run_workflow_once` 可接受 `persist=True` 参数写入 run 记录

### 阶段三：端口类型与图校验

**目标：** 引入端口类型定义并做连接校验，减少运行期错误。  

**建议数据结构**

```python
class PortDefinition(BaseModel):
    name: str
    type: str  # Query, DocumentBatch, RetrievedItems 等
    is_list: bool = False

class NodeDefinition(BaseModel):
    id: str
    type: str
    input_ports: list[PortDefinition]
    output_ports: list[PortDefinition]
```

**校验点**

- 解析 workflow graph 时检查 edge 的 source/target 类型兼容
- 默认允许 `any` 类型，逐步替换为强类型

### 阶段四：API/服务边界重构

**目标：** 建立 workflow CRUD 与 run 的独立 API，降低对 Bot 的耦合。  

**建议接口**

```
POST   /api/workflows                 # 创建 workflow
GET    /api/workflows                 # 列表
GET    /api/workflows/{id}            # 详情
PUT    /api/workflows/{id}            # 更新
POST   /api/workflows/{id}/versions   # 保存版本
POST   /api/workflows/{id}/run        # 执行（可选 stream）
GET    /api/workflows/{id}/runs       # 运行记录
GET    /api/workflows/{id}/runs/{rid} # 单次 run 详情
```

## 风险与兼容策略

- **兼容旧 flow 数据**：保留 `Bot.config.flow` 读取逻辑，迁移前置校验
- **数据迁移压力**：可先双写（`Bot.config` + `workflow` 表）
- **类型系统落地节奏**：允许 `any` 过渡，优先覆盖关键节点

## 里程碑建议

1. **W1-W2：模型与表结构设计**  
   产出迁移脚本草案 + CRUD stub
2. **W3-W4：运行记录与引擎钩子**  
   接入 `WorkflowRun`/`NodeRun` 写入
3. **W5-W6：端口类型与校验**  
   完成核心节点类型定义与边校验
4. **W7+：API 解耦与 SDK/CLI 预留**  
   新 API 切换、旧接口兼容
