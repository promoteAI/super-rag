

from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from super_rag.nodeflow.base.exceptions import CycleError
from super_rag.utils.history import BaseChatMessageHistory


@dataclass
class NodeInstance:
    """Instance of a node in the nodeflow"""

    id: str
    type: str  # NodeDefinition.type
    input_schema: dict = field(default_factory=dict)
    input_values: dict = field(default_factory=dict)
    output_schema: dict = field(default_factory=dict)
    title: Optional[str] = None
    # 节点原始配置（与参考 JSON 的 data 对齐：start_page, model, prompt 等）
    data: Optional[Dict[str, Any]] = None


@dataclass
class Edge:
    """Connection between nodes in the nodeflow"""

    source: str
    target: str
    # 端口级连接：source 的哪个输出 -> target 的哪个输入（便于与前端 graph 对齐）
    source_handle: Optional[str] = None  # 默认 "output"
    target_handle: Optional[str] = None  # 目标节点的输入端口名
    edge_id: Optional[str] = None
    ui_properties: Optional[Dict[str, Any]] = None


@dataclass
class NodeflowInstance:
    """Instance of a nodeflow with nodes and edges"""

    name: str
    title: str
    nodes: Dict[str, NodeInstance]
    edges: List[Edge]
    # 工作流级元数据（与参考 JSON 对齐，便于 API/前端）
    workflow_id: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    input_schema: Optional[Dict[str, Any]] = None  # JSON Schema，工作流入参
    output_schema: Optional[Dict[str, Any]] = None  # JSON Schema，工作流出参

    def validate(self) -> None:
        """Validate the nodeflow configuration"""
        self._topological_sort()

    def _topological_sort(self) -> List[str]:
        """Perform topological sort to detect cycles"""
        # Build dependency graph
        in_degree = {node_id: 0 for node_id in self.nodes}
        for edge in self.edges:
            in_degree[edge.target] += 1

        # Topological sort
        queue = deque([node_id for node_id, degree in in_degree.items() if degree == 0])
        if len(queue) == 0:
            raise CycleError("nodeflow contains cycles")

        sorted_nodes = []

        while queue:
            node_id = queue.popleft()
            sorted_nodes.append(node_id)

            # Update in-degree of successor nodes
            for edge in self.edges:
                if edge.source == node_id:
                    in_degree[edge.target] -= 1
                    if in_degree[edge.target] == 0:
                        queue.append(edge.target)

        if len(sorted_nodes) != len(self.nodes):
            raise CycleError("nodeflow contains cycles")

        return sorted_nodes


@dataclass
class ExecutionContext:
    """Context for nodeflow execution, storing outputs and global state"""

    outputs: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    system_outputs: Dict[str, Any] = field(default_factory=dict)
    global_variables: Dict[str, Any] = field(default_factory=dict)

    def get_input(self, node_id: str, field: str) -> Any:
        """Get input value for a node field"""
        return self.outputs.get(node_id, {}).get(field)

    def set_output(self, node_id: str, outputs: Dict[str, Any]) -> None:
        """Set output values for a node"""
        self.outputs[node_id] = outputs

    def get_global(self, name: str) -> Any:
        """Get global variable value"""
        return self.global_variables.get(name)

    def set_global(self, name: str, value: Any) -> None:
        """Set global variable value"""
        self.global_variables[name] = value

    def set_system_output(self, node_id: str, system_output: Any) -> None:
        """Set system output for a node"""
        self.system_outputs[node_id] = system_output

    def get_system_output(self, node_id: str) -> Any:
        """Get system output for a node"""
        return self.system_outputs.get(node_id)


NODE_RUNNER_REGISTRY = {}


class BaseNodeRunner(ABC):
    @abstractmethod
    async def run(self, ui: Any, si: Dict[str, Any]) -> Tuple[Any, Dict[str, Any]]:
        raise NotImplementedError


def register_node_runner(
    node_type: str,
    input_model,
    output_model,
):
    def decorator(cls):
        NODE_RUNNER_REGISTRY[node_type] = {
            "runner": cls(),
            "input_model": input_model,
            "output_model": output_model,
        }
        return cls

    return decorator


class SystemInput:
    query: str
    user: str
    chat_id: Optional[str] = None
    history: Optional[BaseChatMessageHistory] = None
    message_id: Optional[str] = None

    def __init__(
        self,
        query: str,
        user: str,
        history: Optional[BaseChatMessageHistory] = None,
        message_id: Optional[str] = None,
        **kwargs,
    ):
        self.query = query
        self.user = user
        self.history = history
        self.message_id = message_id
        # Set additional attributes from kwargs
        for key, value in kwargs.items():
            setattr(self, key, value)
