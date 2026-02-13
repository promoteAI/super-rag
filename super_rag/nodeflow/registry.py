"""
Nodeflow 节点注册表：加载外部 node pack（entry point），并提供节点类型元数据 API。

参考 nodetool-registry：节点以 Python 包形式发布到 Git，通过 entry point 注册到运行时，
便于工作流编辑时发现并安装更多节点。
"""

import json
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from importlib.metadata import entry_points

from super_rag.nodeflow.base.models import NODE_RUNNER_REGISTRY

logger = logging.getLogger(__name__)

ENTRY_POINT_GROUP = "super_rag.nodeflow.packs"

# 内置节点类型的展示名与分类（与 docs/design/nodeflow 对齐）
BUILTIN_NODE_METADATA: Dict[str, Dict[str, str]] = {
    "start": {"label": "开始", "category": "Source"},
    "vector_search": {"label": "向量检索", "category": "Retrieval"},
    "graph_search": {"label": "图检索", "category": "Retrieval"},
    "rerank": {"label": "重排", "category": "Retrieval"},
    "merge": {"label": "合并", "category": "Control"},
    "llm": {"label": "大模型", "category": "LLM"},
}


def _model_json_schema(model: Any) -> Dict[str, Any]:
    """从 Pydantic 模型生成 JSON Schema，兼容 Pydantic v1/v2。"""
    try:
        if hasattr(model, "model_json_schema"):
            return model.model_json_schema()
        if hasattr(model, "schema"):
            return model.schema()
    except Exception as e:
        logger.debug("Failed to get schema for %s: %s", model, e)
    return {}


def load_nodeflow_packs() -> None:
    """
    加载所有通过 entry point 注册的 node pack。
    在应用启动时调用一次，之后 NODE_RUNNER_REGISTRY 中会包含内置 + 外部节点。
    """
    try:
        eps = entry_points(group=ENTRY_POINT_GROUP)
    except Exception as e:
        logger.debug("No entry points for %s: %s", ENTRY_POINT_GROUP, e)
        return
    for ep in eps:
        try:
            fn: Callable[[], None] = ep.load()
            fn()
            logger.info("Loaded nodeflow pack: %s", ep.name)
        except Exception as e:
            logger.warning("Failed to load nodeflow pack %s: %s", ep.name, e, exc_info=True)


def get_registered_node_types() -> List[Dict[str, Any]]:
    """
    返回当前已注册的节点类型列表，用于画布节点面板与 API。
    包含 type、label、category、input_schema、output_schema。
    """
    load_nodeflow_packs()
    result: List[Dict[str, Any]] = []
    for node_type, info in NODE_RUNNER_REGISTRY.items():
        runner = info.get("runner")
        input_model = info.get("input_model")
        output_model = info.get("output_model")
        meta = BUILTIN_NODE_METADATA.get(node_type, {"label": node_type, "category": "Other"})
        result.append({
            "type": node_type,
            "label": meta.get("label", node_type),
            "category": meta.get("category", "Other"),
            "input_schema": _model_json_schema(input_model) if input_model else {},
            "output_schema": _model_json_schema(output_model) if output_model else {},
            "description": getattr(runner, "__doc__", None) or "",
        })
    return result


def get_registry_index_path() -> Path:
    """返回仓库内 nodeflow_registry/index.json 的路径（与 pyproject 同目录）。"""
    # 从 super_rag/nodeflow/registry.py 向上到项目根
    return Path(__file__).resolve().parents[2] / "nodeflow_registry" / "index.json"


def get_registry_packages() -> List[Dict[str, Any]]:
    """
    读取 nodeflow_registry/index.json，返回可安装的 pack 列表。
    用于 UI 展示「可安装节点包」及安装说明（如 pip install git+https://...）。
    """
    path = get_registry_index_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("packages") or []
    except Exception as e:
        logger.warning("Failed to read registry index %s: %s", path, e)
        return []


# 外部 pack 在应用 lifespan 中加载（见 app.py），get_registered_node_types() 内也会惰性加载
