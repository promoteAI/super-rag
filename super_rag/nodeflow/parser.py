"""解析工作流配置：仅支持 graph + input_schema 格式（如 rag_flow3.json / new_flow_structure.json）。"""

from typing import Any, Dict, List, Optional, Set

import json
import jsonref
import yaml

from super_rag.nodeflow.base.models import (
    Edge,
    NODE_RUNNER_REGISTRY,
    NodeflowInstance,
    NodeInstance,
)

from .base.exceptions import ValidationError


# 从 node.data 合并到 input_values 的默认值键
_DATA_INPUT_KEYS = frozenset({
    "value", "name", "start_page", "end_page", "prompt", "top_k", "temperature",
    "merge_strategy", "deduplicate", "model", "model_service_provider", "custom_llm_provider",
    "model_name", "prompt_template", "similarity_threshold", "collection_ids",
})


class nodeflowParser:
    """Parser for nodeflow configuration. Only supports graph format (graph.nodes / graph.edges)."""

    @staticmethod
    def parse(data: str | dict[str, Any]) -> NodeflowInstance:
        """Parse YAML/JSON into a NodeflowInstance. Only accepts workflow with top-level "graph"
        (graph.nodes, graph.edges, optional input_schema/output_schema). See rag_flow3.json.
        """
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                try:
                    data = yaml.safe_load(data)
                except yaml.YAMLError as e:
                    raise ValidationError(f"Invalid JSON/YAML format: {e}") from e
        if not isinstance(data, dict):
            raise ValidationError("nodeflow data must be a dict")

        if "graph" not in data:
            raise ValidationError(
                'nodeflow must have top-level "graph" with "nodes" and "edges". '
                "Use format like rag_flow3.json / new_flow_structure.json."
            )

        data = jsonref.replace_refs(data)
        return nodeflowParser._parse_graph_format(data)

    @staticmethod
    def _parse_graph_format(data: Dict[str, Any]) -> NodeflowInstance:
        """参考 JSON 格式：graph.nodes / graph.edges，端口级边，工作流 input_schema."""
        graph = data.get("graph") or {}
        nodes_list: List[Dict[str, Any]] = graph.get("nodes") or []
        edges_list: List[Dict[str, Any]] = graph.get("edges") or []

        # 1) 先建节点（仅 id/type/data），input_values 稍后由边 + data 填充
        nodes: Dict[str, NodeInstance] = {}
        for nd in nodes_list:
            node = nodeflowParser._parse_node_from_graph(nd)
            nodes[node.id] = node

        # 2) 解析边（含 sourceHandle/targetHandle）
        edges: List[Edge] = []
        for ed in edges_list:
            edges.append(nodeflowParser._parse_edge_from_graph(ed))

        # 3) 按边填充目标节点的 input_values：targetHandle <- nodes.source.output.sourceHandle
        # sourceHandle 须与上游节点实际输出键一致（如 start 输出为 query，用 sourceHandle: "query"）
        for edge in edges:
            target_id = edge.target
            target_handle = edge.target_handle or "value"
            source_id = edge.source
            source_handle = edge.source_handle or "output"
            if target_id not in nodes:
                continue
            ref = f"{{{{ nodes.{source_id}.output.{source_handle} }}}}"
            nodes[target_id].input_values[target_handle] = ref

        # 4) 用 node.data 中的常见输入键补默认值（未被边覆盖的）
        for node in nodes.values():
            if not node.data:
                continue
            for k, v in node.data.items():
                if k in _DATA_INPUT_KEYS and k not in node.input_values and v is not None:
                    node.input_values[k] = v

        # 5) 工作流 input_schema 映射到输入节点：data.name == schema key -> 端口用 globals.key
        input_schema = data.get("input_schema") or {}
        props = input_schema.get("properties") or {}
        for schema_key in props:
            ref = f"{{{{ globals.{schema_key} }}}}"
            for node in nodes.values():
                if not node.data or node.data.get("name") != schema_key:
                    continue
                node.input_values[schema_key] = ref
                node.input_values["value"] = ref  # 兼容单端口输入节点（如 StringInput 的 value）
                break

        nodeflow = NodeflowInstance(
            name=data.get("name", "Unnamed nodeflow"),
            title=data.get("title", data.get("name", "Unnamed nodeflow")),
            nodes=nodes,
            edges=edges,
            workflow_id=data.get("id"),
            description=data.get("description"),
            tags=data.get("tags"),
            input_schema=data.get("input_schema"),
            output_schema=data.get("output_schema"),
        )
        nodeflow.validate()
        nodeflowParser._validate_edge_types(nodeflow)
        return nodeflow

    @staticmethod
    def _parse_node_from_graph(node_data: Dict[str, Any]) -> NodeInstance:
        """Graph-format node: id, type, data (flat config)."""
        data = node_data.get("data") or {}
        title = data.get("name") or node_data.get("id", "")
        return NodeInstance(
            id=node_data["id"],
            type=node_data["type"],
            input_schema={},
            input_values={},
            output_schema={},
            title=title,
            data=data,
        )

    @staticmethod
    def _parse_edge_from_graph(edge_data: Dict[str, Any]) -> Edge:
        """Graph-format edge: source, sourceHandle, target, targetHandle, id, ui_properties."""
        return Edge(
            source=edge_data["source"],
            target=edge_data["target"],
            source_handle=edge_data.get("sourceHandle"),
            target_handle=edge_data.get("targetHandle"),
            edge_id=edge_data.get("id"),
            ui_properties=edge_data.get("ui_properties"),
        )

    @staticmethod
    def _get_model_field_schema(model, field_name: str) -> Optional[dict[str, Any]]:
        try:
            schema = model.model_json_schema()
        except Exception:
            return None
        properties = schema.get("properties") or {}
        return properties.get(field_name)

    @staticmethod
    def _extract_schema_types(schema: Optional[dict[str, Any]]) -> Set[str]:
        if not schema:
            return set()
        if "anyOf" in schema:
            types: Set[str] = set()
            for item in schema.get("anyOf") or []:
                types.update(nodeflowParser._extract_schema_types(item))
            return types
        if "oneOf" in schema:
            types = set()
            for item in schema.get("oneOf") or []:
                types.update(nodeflowParser._extract_schema_types(item))
            return types
        if "allOf" in schema:
            types = set()
            for item in schema.get("allOf") or []:
                types.update(nodeflowParser._extract_schema_types(item))
            return types
        typ = schema.get("type")
        if isinstance(typ, list):
            return set(typ)
        if isinstance(typ, str):
            return {typ}
        return set()

    @staticmethod
    def _types_compatible(source_types: Set[str], target_types: Set[str]) -> bool:
        if not source_types or not target_types:
            return True
        if "any" in source_types or "any" in target_types:
            return True
        if source_types & target_types:
            return True
        if "integer" in source_types and "number" in target_types:
            return True
        return False

    @staticmethod
    def _validate_edge_types(nodeflow: NodeflowInstance) -> None:
        for edge in nodeflow.edges:
            source_node = nodeflow.nodes.get(edge.source)
            target_node = nodeflow.nodes.get(edge.target)
            if not source_node or not target_node:
                continue
            source_runner = NODE_RUNNER_REGISTRY.get(source_node.type)
            target_runner = NODE_RUNNER_REGISTRY.get(target_node.type)
            if not source_runner or not target_runner:
                continue

            source_handle = edge.source_handle
            target_handle = edge.target_handle
            if not source_handle or not target_handle:
                continue

            source_schema = nodeflowParser._get_model_field_schema(
                source_runner.get("output_model"),
                source_handle,
            )
            target_schema = nodeflowParser._get_model_field_schema(
                target_runner.get("input_model"),
                target_handle,
            )

            source_types = nodeflowParser._extract_schema_types(source_schema)
            target_types = nodeflowParser._extract_schema_types(target_schema)
            if not nodeflowParser._types_compatible(source_types, target_types):
                raise ValidationError(
                    f"Edge type mismatch: {edge.source}.{source_handle} ({sorted(source_types)}) "
                    f"-> {edge.target}.{target_handle} ({sorted(target_types)})"
                )

    @staticmethod
    def load_from_file(file_path: str) -> NodeflowInstance:
        """Load nodeflow configuration from a file (YAML or JSON)."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                raw = f.read()
            if file_path.lower().endswith(".json"):
                data = json.loads(raw)
            else:
                data = yaml.safe_load(raw)
            return nodeflowParser.parse(data)
        except FileNotFoundError:
            raise ValidationError(f"nodeflow configuration file not found: {file_path}")
        except Exception as e:
            raise ValidationError(f"Error loading nodeflow configuration: {str(e)}") from e
