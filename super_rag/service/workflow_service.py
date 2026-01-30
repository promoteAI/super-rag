from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from super_rag.db import models as db_models
from super_rag.db.models import WorkflowStatus
from super_rag.db.ops import AsyncDatabaseOps, async_db_ops
from super_rag.exceptions import ResourceNotFoundException
from super_rag.schema import view_models


class WorkflowService:
    """Workflow service that handles business logic for workflow storage and versions."""

    def __init__(self, session: AsyncSession = None):
        if session is None:
            self.db_ops = async_db_ops
        else:
            self.db_ops = AsyncDatabaseOps(session)

    def _build_workflow_response(self, workflow: db_models.WorkflowTable) -> view_models.WorkflowRecord:
        return view_models.WorkflowRecord(
            id=workflow.id,
            name=workflow.name,
            title=workflow.title,
            description=workflow.description,
            tags=workflow.tags or [],
            status=workflow.status,
            graph=workflow.graph,
            input_schema=workflow.input_schema,
            output_schema=workflow.output_schema,
            created=workflow.gmt_created.isoformat(),
            updated=workflow.gmt_updated.isoformat(),
        )

    def _build_version_response(
        self, version: db_models.WorkflowVersionTable
    ) -> view_models.WorkflowVersionRecord:
        return view_models.WorkflowVersionRecord(
            id=version.id,
            workflow_id=version.workflow_id,
            version=version.version,
            name=version.name,
            title=version.title,
            description=version.description,
            graph=version.graph,
            input_schema=version.input_schema,
            output_schema=version.output_schema,
            save_type=version.save_type,
            autosave_metadata=version.autosave_metadata or {},
            created=version.gmt_created.isoformat(),
        )

    async def create_workflow(
        self, user: str, data: view_models.WorkflowCreate
    ) -> view_models.WorkflowRecord:
        status = WorkflowStatus(data.status) if data.status else WorkflowStatus.DRAFT
        workflow = await self.db_ops.create_workflow(
            user=user,
            name=data.name,
            title=data.title,
            description=data.description,
            tags=data.tags,
            graph=data.graph.model_dump(by_alias=True, exclude_none=True),
            input_schema=data.input_schema,
            output_schema=data.output_schema,
            status=status,
        )
        return self._build_workflow_response(workflow)

    async def list_workflows(self, user: str, limit: int = 100, offset: int = 0) -> view_models.WorkflowList:
        workflows = await self.db_ops.query_workflows(user, limit=limit, offset=offset)
        return view_models.WorkflowList(items=[self._build_workflow_response(wf) for wf in workflows])

    async def get_workflow(self, user: str, workflow_id: str) -> view_models.WorkflowRecord:
        workflow = await self.db_ops.query_workflow(user, workflow_id)
        if not workflow:
            raise ResourceNotFoundException("Workflow", workflow_id)
        return self._build_workflow_response(workflow)

    async def update_workflow(
        self, user: str, workflow_id: str, data: view_models.WorkflowUpdate
    ) -> view_models.WorkflowRecord:
        updates: dict[str, Any] = {}
        if data.name is not None:
            updates["name"] = data.name
        if data.title is not None:
            updates["title"] = data.title
        if data.description is not None:
            updates["description"] = data.description
        if data.tags is not None:
            updates["tags"] = data.tags
        if data.graph is not None:
            updates["graph"] = data.graph.model_dump(by_alias=True, exclude_none=True)
        if data.input_schema is not None:
            updates["input_schema"] = data.input_schema
        if data.output_schema is not None:
            updates["output_schema"] = data.output_schema
        if data.status is not None:
            updates["status"] = WorkflowStatus(data.status)

        workflow = await self.db_ops.update_workflow_by_id(user, workflow_id, updates)
        if not workflow:
            raise ResourceNotFoundException("Workflow", workflow_id)
        return self._build_workflow_response(workflow)

    async def delete_workflow(self, user: str, workflow_id: str) -> None:
        workflow = await self.db_ops.delete_workflow_by_id(user, workflow_id)
        if not workflow:
            raise ResourceNotFoundException("Workflow", workflow_id)

    async def create_workflow_version(
        self, user: str, workflow_id: str, data: view_models.WorkflowVersionCreate
    ) -> view_models.WorkflowVersionRecord:
        workflow = await self.db_ops.query_workflow(user, workflow_id)
        if not workflow:
            raise ResourceNotFoundException("Workflow", workflow_id)

        graph = workflow.graph
        input_schema = workflow.input_schema
        output_schema = workflow.output_schema

        version = await self.db_ops.create_workflow_version(
            user=user,
            workflow_id=workflow_id,
            name=data.name or workflow.name,
            title=data.title or workflow.title,
            description=data.description or workflow.description,
            graph=graph,
            input_schema=input_schema,
            output_schema=output_schema,
            save_type=data.save_type or "manual",
            autosave_metadata=data.autosave_metadata,
        )
        return self._build_version_response(version)

    async def list_workflow_versions(
        self, user: str, workflow_id: str, limit: int = 100, offset: int = 0
    ) -> view_models.WorkflowVersionList:
        workflow = await self.db_ops.query_workflow(user, workflow_id)
        if not workflow:
            raise ResourceNotFoundException("Workflow", workflow_id)
        versions = await self.db_ops.query_workflow_versions(workflow_id, limit=limit, offset=offset)
        return view_models.WorkflowVersionList(
            items=[self._build_version_response(v) for v in versions]
        )

    async def get_workflow_version(
        self, user: str, workflow_id: str, version: int
    ) -> view_models.WorkflowVersionRecord:
        workflow = await self.db_ops.query_workflow(user, workflow_id)
        if not workflow:
            raise ResourceNotFoundException("Workflow", workflow_id)
        version_obj = await self.db_ops.query_workflow_version(workflow_id, version)
        if not version_obj:
            raise ResourceNotFoundException("WorkflowVersion", f"{workflow_id}@{version}")
        return self._build_version_response(version_obj)


workflow_service = WorkflowService()
