# Nodeflow 节点注册表与 Node Pack 开发指南

参考 [nodetool-registry](https://github.com/nodetool-ai/nodetool-registry)：将 Nodeflow 节点以 **Node Pack**（Python 包）形式打包、发布到 Git，并可通过注册表发现与安装，便于为工作流提供更多节点。

## 1. 整体架构

- **内置节点**：`super_rag/nodeflow/runners/` 中的节点随项目一起提供（start、vector_search、graph_search、rerank、merge、llm）。
- **Node Pack**：独立 Python 包，通过 **entry point** 在安装后向 `NODE_RUNNER_REGISTRY` 注册自定义节点。
- **注册表（Registry）**：仓库内 `nodeflow_registry/index.json` 维护「可安装包」列表（名称、描述、repo_id、节点类型等），供 UI 或文档展示。
- **安装方式**：用户通过 `pip install super-rag-nodes-xxx` 或 `pip install git+https://github.com/xxx/super-rag-nodes-xxx.git` 安装 pack，重启服务后节点自动可用。

## 2. 创建 Node Pack

### 2.1 包名与结构约定

- **包名建议**：`super-rag-nodes-<功能>`（如 `super-rag-nodes-eval`、`super-rag-nodes-tools`），与 nodetool 的 `nodetool-` 前缀类似，便于在 PyPI 或 Git 上识别。
- **目录结构示例**：

```
super-rag-nodes-example/
├── pyproject.toml
├── README.md
└── src/
    └── super_rag_nodes_example/
        ├── __init__.py
        └── nodes.py
```

### 2.2 pyproject.toml

必须声明 entry point，组名为 `super_rag.nodeflow.packs`，值为「无参可调用对象」（如模块中的 `register` 函数），在加载时会被执行一次，用于注册节点。

```toml
[project]
name = "super-rag-nodes-example"
version = "0.1.0"
description = "示例 Nodeflow 节点包"
requires-python = ">=3.11"
dependencies = [
    "super-rag>=0.1.0",
]

[project.entry-points."super_rag.nodeflow.packs"]
example = "super_rag_nodes_example:register"
```

### 2.3 节点实现与注册

在 `register()` 中导入所有使用 `@register_node_runner` 的类，从而触发它们向 `NODE_RUNNER_REGISTRY` 注册。节点实现需依赖 `super_rag` 的 `BaseNodeRunner` 与 `register_node_runner`。

示例 `src/super_rag_nodes_example/nodes.py`：

```python
from typing import Any, Dict, Tuple

from pydantic import BaseModel, Field

from super_rag.nodeflow.base.models import BaseNodeRunner, SystemInput, register_node_runner


class EchoInput(BaseModel):
    message: str = Field("", description="Echo message")


class EchoOutput(BaseModel):
    text: str


@register_node_runner("echo", input_model=EchoInput, output_model=EchoOutput)
class EchoNodeRunner(BaseNodeRunner):
    """示例：回显节点"""

    async def run(self, ui: EchoInput, si: SystemInput) -> Tuple[EchoOutput, Dict[str, Any]]:
        return EchoOutput(text=ui.message or si.query), {}
```

`src/super_rag_nodes_example/__init__.py`：

```python
def register() -> None:
    from . import nodes  # noqa: F401  # 导入即完成注册
```

### 2.4 依赖

- 必须依赖 `super-rag`（版本与当前运行环境兼容），以便使用 `BaseNodeRunner`、`SystemInput`、`register_node_runner` 及 `NODE_RUNNER_REGISTRY`。
- 若节点依赖其他库，在 `pyproject.toml` 的 `dependencies` 中声明即可。

## 3. 发布到 Git 并加入注册表

### 3.1 发布到 Git

1. 在 GitHub/GitLab 等创建仓库（如 `your-org/super-rag-nodes-example`）。
2. 推送代码并打 tag（如 `v0.1.0`），便于用户按版本安装。

### 3.2 注册到 index.json

在本仓库的 **nodeflow_registry/index.json** 中增加一条 pack 描述，便于前端或文档展示「可安装的节点包」：

```json
{
  "packages": [
    {
      "name": "Super-RAG 内置节点",
      "description": "内置 RAG 工作流节点。",
      "repo_id": "super-rag/super-rag",
      "builtin": true,
      "node_types": ["start", "vector_search", "graph_search", "rerank", "merge", "llm"]
    },
    {
      "name": "Example Nodes",
      "description": "示例回显节点，用于开发与演示。",
      "repo_id": "your-org/super-rag-nodes-example",
      "install": "pip install git+https://github.com/your-org/super-rag-nodes-example.git",
      "node_types": ["echo"]
    }
  ]
}
```

- **repo_id**：Git 仓库标识（如 `owner/repo`）。
- **install**：可选，给用户的安装命令。
- **node_types**：该包提供的节点 type 列表，与 `@register_node_runner("echo", ...)` 中的名称一致。

修改 index.json 后提 PR 到本仓库即可完成「注册」。

## 4. 在项目中安装 Node Pack

### 4.1 从 Git 安装

在 super-rag 项目虚拟环境中执行：

```bash
# 从默认分支安装
pip install "git+https://github.com/your-org/super-rag-nodes-example.git"

# 指定 tag
pip install "git+https://github.com/your-org/super-rag-nodes-example.git@v0.1.0"
```

若使用 uv：

```bash
uv pip install "git+https://github.com/your-org/super-rag-nodes-example.git"
```

### 4.2 本地开发安装

在 pack 目录下：

```bash
pip install -e .
```

### 4.3 生效方式

- 应用启动时（FastAPI lifespan）会执行 `load_nodeflow_packs()`，扫描所有 `super_rag.nodeflow.packs` entry point 并调用其 `register()`。
- 安装新 pack 后需**重启 super-rag 服务**，新节点才会出现在 `GET /api/v1/nodeflow/node-types` 并可用于工作流执行。

## 5. API 与前端

- **GET /api/v1/nodeflow/node-types**：返回当前已注册的节点类型（内置 + 已安装的 pack），包含 `type`、`label`、`category`、`input_schema`、`output_schema` 等，供工作流画布节点面板使用。
- **GET /api/v1/nodeflow/packs**：返回 `nodeflow_registry/index.json` 中的可安装包列表，供「节点管理」或设置页展示及生成安装说明。

前端可基于 node-types 动态渲染可拖拽节点，基于 packs 展示「可安装更多节点」的入口与安装命令。

## 6. 小结

| 步骤       | 说明 |
|------------|------|
| 开发 Pack | 新建 Python 包，使用 `register_node_runner` 注册节点，并在 pyproject.toml 中声明 `super_rag.nodeflow.packs` entry point。 |
| 发布到 Git| 推送仓库并打 tag。 |
| 注册       | 在 `nodeflow_registry/index.json` 中新增一条 pack 记录（可选，用于发现与文档）。 |
| 安装       | 用户执行 `pip install git+https://...` 或 `uv pip install ...`，重启服务后节点即可用。 |

这样即可像 nodetool-registry 一样，将 Nodeflow 节点打包、发布到 Git，并支持在项目中注册与安装，便于后续提供更多节点供工作流编辑与运行。
