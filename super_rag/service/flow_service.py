

import asyncio
import json
import logging
from datetime import datetime
from platform import node

from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from super_rag.db.ops import AsyncDatabaseOps, async_db_ops
from super_rag.exceptions import ResourceNotFoundException
from super_rag.nodeflow.engine import NodeflowEngine
from super_rag.nodeflow.parser import nodeflowParser
from super_rag.schema import view_models
from super_rag.service.workflow_run_recorder import WorkflowRunRecorder

logger = logging.getLogger(__name__)


class FlowService:
    """Flow service that handles business logic for bot flows"""

    def __init__(self, session: AsyncSession = None):
        # Use global db_ops instance by default, or create custom one with provided session
        if session is None:
            self.db_ops = async_db_ops  # Use global instance
        else:
            self.db_ops = AsyncDatabaseOps(session)  # Create custom instance for transaction control

    def _convert_to_serializable(self, obj):
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        elif isinstance(obj, dict):
            return {k: self._convert_to_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_to_serializable(item) for item in obj]
        elif hasattr(obj, "__dict__"):
            return self._convert_to_serializable(obj.__dict__)
        return obj

    async def run_workflow_once(
        self,
        user: str,
        data: view_models.WorkflowRunRequest,
    ) -> view_models.WorkflowRunResponse:
        """
        直接使用 WorkflowDefinition 运行一次工作流（不做持久化），返回节点输出。

        - 用于前端 Workflow Editor 的「运行」按钮；
        - 输入会被放入 ExecutionContext.global_variables，并参与表达式解析。
        """
        # 将 Pydantic WorkflowDefinition 转成 dict，再交给 nodeflowParser 解析为 NodeflowInstance
        workflow_dict = data.workflow.model_dump(by_alias=True, exclude_none=True)
        flow = nodeflowParser.parse(workflow_dict)

        recorder = None
        if data.persist:
            recorder = WorkflowRunRecorder(
                db_ops=self.db_ops,
                user=user,
                workflow_id=data.workflow_id,
                workflow_version=data.workflow_version,
                input_payload=data.input,
            )
        engine = NodeflowEngine(recorder=recorder)

        # initial_data 里至少带上 user，方便节点侧取用
        initial_data = {"user": user}
        if data.input:
            initial_data.update(data.input)

        outputs, system_outputs = await engine.execute_nodeflow(flow, initial_data)

        # 转成可 JSON 序列化形式再返回
        return view_models.WorkflowRunResponse(
            outputs=self._convert_to_serializable(outputs),
            system_outputs=self._convert_to_serializable(system_outputs),
        )

    async def stream_flow_events(self, flow_generator, flow_task, engine, flow):
        # event stream
        async for event in flow_generator:
            serializable_event = self._convert_to_serializable(event)
            yield f"data: {json.dumps(serializable_event)}\n\n"
            event_type = event.get("event_type")
            # Align with NodeflowEngine event types: nodeflow_start / nodeflow_end / nodeflow_error
            if event_type == "nodeflow_end":
                break
            if event_type == "nodeflow_error":
                return

        # Flow execution finished, now stream LLM chunks from the end node (if any)
        _, system_outputs = await flow_task
        node_id = ""
        nodes = engine.find_end_nodes(flow)
        async_generator = None
        for node in nodes:
            async_generator = system_outputs[node].get("async_generator")
            if async_generator:
                node_id = node
                break
        if not async_generator:
            yield "data: {'event_type': 'flow_error', 'error': 'No generator found on the end node'}\n\n"
            return

        # llm message chunk stream
        async for chunk in async_generator():
            data = {
                "event_type": "output_chunk",
                "node_id": node_id,
                "execution_id": engine.execution_id,
                "timestamp": datetime.now().isoformat(),
                "data": {"chunk": self._convert_to_serializable(chunk)},
            }
            yield f"data: {json.dumps(data)}\n\n"

    async def debug_flow_stream(self, user: str, agent_id: str, debug: view_models.DebugFlowRequest):
        """Stream debug flow events as SSE using FastAPI StreamingResponse."""
        agent = await self.db_ops.query_agent(user, agent_id)
        if not agent:
            raise ResourceNotFoundException("Agent", agent_id)

        agent_config = json.loads(agent.config)
        flow_config = agent_config.get("flow")
        if not flow_config:
            raise ValueError("Agent flow config not found")

        flow = nodeflowParser.parse(flow_config)
        engine = NodeflowEngine()
        initial_data = {"query": debug.query, "user": user}
        # Use NodeflowEngine.execute_nodeflow which is the canonical execution entrypoint
        task = asyncio.create_task(engine.execute_nodeflow(flow, initial_data))

        return StreamingResponse(
            self.stream_flow_events(engine.get_events(), task, engine, flow),
            media_type="text/event-stream",
        )

    async def get_flow(self, user: str, agent_id: str) -> dict:
        """Get flow config for an agent (deprecated, flow is removed)."""
        agent = await self.db_ops.query_agent(user, agent_id)
        if not agent:
            raise ResourceNotFoundException("Agent", agent_id)

        return {}

    async def update_flow(self, user: str, agent_id: str, data: view_models.WorkflowDefinition) -> dict:
        """Update flow config for an agent (deprecated, flow is removed)."""
        agent = await self.db_ops.query_agent(user, agent_id)
        if not agent:
            raise ResourceNotFoundException("Agent", agent_id)

        config = json.loads(agent.config or "{}")
        config.pop("flow", None)

        updated_agent = await self.db_ops.update_agent_config_by_id(
            user=user,
            agent_id=agent_id,
            config=json.dumps(config, ensure_ascii=False),
        )

        if not updated_agent:
            raise ResourceNotFoundException("Agent", agent_id)

        return {}


# Create a global service instance for easy access
# This uses the global db_ops instance and doesn't require session management in views
flow_service_global = FlowService()
