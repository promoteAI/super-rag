from __future__ import annotations

from typing import Any, Optional

from super_rag.db.models import NodeRunStatus, WorkflowRunStatus
from super_rag.db.ops import AsyncDatabaseOps
from super_rag.utils.utils import utc_now


class WorkflowRunRecorder:
    """Record workflow and node run metadata into the database."""

    def __init__(
        self,
        db_ops: AsyncDatabaseOps,
        user: str,
        workflow_id: Optional[str],
        workflow_version: Optional[int],
        input_payload: Optional[dict[str, Any]],
    ):
        self.db_ops = db_ops
        self.user = user
        self.workflow_id = workflow_id
        self.workflow_version = workflow_version
        self.input_payload = input_payload
        self.run_id: Optional[str] = None
        self._node_run_ids: dict[str, str] = {}

    async def on_flow_start(self, execution_id: str):
        run = await self.db_ops.create_workflow_run(
            user=self.user,
            workflow_id=self.workflow_id,
            workflow_version=self.workflow_version,
            execution_id=execution_id,
            input_payload=self.input_payload,
        )
        self.run_id = run.id

    async def on_flow_end(self, output_payload: dict[str, Any]):
        if not self.run_id:
            return
        await self.db_ops.update_workflow_run(
            run_id=self.run_id,
            status=WorkflowRunStatus.SUCCEEDED,
            output_payload=output_payload,
            error=None,
            finished_at=utc_now(),
        )

    async def on_flow_error(self, error: str):
        if not self.run_id:
            return
        await self.db_ops.update_workflow_run(
            run_id=self.run_id,
            status=WorkflowRunStatus.FAILED,
            output_payload=None,
            error=error,
            finished_at=utc_now(),
        )

    async def on_node_start(self, node_id: str, node_type: Optional[str], inputs: dict[str, Any]):
        if not self.run_id:
            return
        node_run = await self.db_ops.create_node_run(
            run_id=self.run_id,
            node_id=node_id,
            node_type=node_type,
            input_snapshot=inputs,
            started_at=utc_now(),
        )
        self._node_run_ids[node_id] = node_run.id

    async def on_node_end(self, node_id: str, outputs: dict[str, Any], duration_ms: Optional[int]):
        node_run_id = self._node_run_ids.get(node_id)
        if not node_run_id:
            return
        await self.db_ops.update_node_run(
            node_run_id=node_run_id,
            status=NodeRunStatus.SUCCEEDED,
            output_snapshot=outputs,
            error=None,
            duration_ms=duration_ms,
            finished_at=utc_now(),
        )

    async def on_node_error(self, node_id: str, error: str, duration_ms: Optional[int]):
        node_run_id = self._node_run_ids.get(node_id)
        if not node_run_id:
            return
        await self.db_ops.update_node_run(
            node_run_id=node_run_id,
            status=NodeRunStatus.FAILED,
            output_snapshot=None,
            error=error,
            duration_ms=duration_ms,
            finished_at=utc_now(),
        )
