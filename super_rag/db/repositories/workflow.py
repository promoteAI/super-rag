from typing import Any, Optional

from sqlalchemy import desc, func, select

from super_rag.db.models import (
    NodeRunStatus,
    NodeRunTable,
    WorkflowRunStatus,
    WorkflowRunTable,
    WorkflowStatus,
    WorkflowTable,
    WorkflowVersionTable,
)
from super_rag.db.repositories.base import AsyncRepositoryProtocol
from super_rag.utils.utils import utc_now


class AsyncWorkflowRepositoryMixin(AsyncRepositoryProtocol):
    async def query_workflow(self, user: str, workflow_id: str) -> Optional[WorkflowTable]:
        async def _query(session):
            stmt = select(WorkflowTable).where(
                WorkflowTable.id == workflow_id,
                WorkflowTable.user == user,
                WorkflowTable.status != WorkflowStatus.DELETED,
            )
            result = await session.execute(stmt)
            return result.scalars().first()

        return await self._execute_query(_query)

    async def query_workflows(self, user: str, limit: int = 100, offset: int = 0) -> list[WorkflowTable]:
        async def _query(session):
            stmt = (
                select(WorkflowTable)
                .where(WorkflowTable.user == user, WorkflowTable.status != WorkflowStatus.DELETED)
                .order_by(desc(WorkflowTable.gmt_created))
                .limit(limit)
                .offset(offset)
            )
            result = await session.execute(stmt)
            return result.scalars().all()

        return await self._execute_query(_query)

    async def create_workflow(
        self,
        user: str,
        name: str,
        title: Optional[str],
        description: Optional[str],
        tags: Optional[list[str]],
        graph: dict[str, Any],
        input_schema: Optional[dict[str, Any]],
        output_schema: Optional[dict[str, Any]],
        status: WorkflowStatus,
    ) -> WorkflowTable:
        async def _operation(session):
            instance = WorkflowTable(
                user=user,
                name=name,
                title=title,
                description=description,
                tags=tags or [],
                graph=graph,
                input_schema=input_schema,
                output_schema=output_schema,
                status=status,
            )
            session.add(instance)
            await session.flush()
            await session.refresh(instance)
            return instance

        return await self.execute_with_transaction(_operation)

    async def update_workflow_by_id(
        self,
        user: str,
        workflow_id: str,
        updates: dict[str, Any],
    ) -> Optional[WorkflowTable]:
        async def _operation(session):
            stmt = select(WorkflowTable).where(
                WorkflowTable.id == workflow_id,
                WorkflowTable.user == user,
                WorkflowTable.status != WorkflowStatus.DELETED,
            )
            result = await session.execute(stmt)
            instance = result.scalars().first()
            if not instance:
                return None

            for key, value in updates.items():
                setattr(instance, key, value)
            instance.gmt_updated = utc_now()
            session.add(instance)
            await session.flush()
            await session.refresh(instance)
            return instance

        return await self.execute_with_transaction(_operation)

    async def delete_workflow_by_id(self, user: str, workflow_id: str) -> Optional[WorkflowTable]:
        async def _operation(session):
            stmt = select(WorkflowTable).where(
                WorkflowTable.id == workflow_id,
                WorkflowTable.user == user,
                WorkflowTable.status != WorkflowStatus.DELETED,
            )
            result = await session.execute(stmt)
            instance = result.scalars().first()
            if not instance:
                return None

            instance.status = WorkflowStatus.DELETED
            instance.gmt_deleted = utc_now()
            instance.gmt_updated = utc_now()
            session.add(instance)
            await session.flush()
            await session.refresh(instance)
            return instance

        return await self.execute_with_transaction(_operation)

    async def create_workflow_version(
        self,
        user: str,
        workflow_id: str,
        name: Optional[str],
        title: Optional[str],
        description: Optional[str],
        graph: dict[str, Any],
        input_schema: Optional[dict[str, Any]],
        output_schema: Optional[dict[str, Any]],
        save_type: str,
        autosave_metadata: Optional[dict[str, Any]],
    ) -> WorkflowVersionTable:
        async def _operation(session):
            stmt = select(func.max(WorkflowVersionTable.version)).where(WorkflowVersionTable.workflow_id == workflow_id)
            result = await session.execute(stmt)
            latest_version = result.scalar() or 0
            next_version = latest_version + 1

            instance = WorkflowVersionTable(
                user=user,
                workflow_id=workflow_id,
                version=next_version,
                name=name,
                title=title,
                description=description,
                graph=graph,
                input_schema=input_schema,
                output_schema=output_schema,
                save_type=save_type,
                autosave_metadata=autosave_metadata or {},
            )
            session.add(instance)
            await session.flush()
            await session.refresh(instance)
            return instance

        return await self.execute_with_transaction(_operation)

    async def query_workflow_versions(
        self,
        workflow_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[WorkflowVersionTable]:
        async def _query(session):
            stmt = (
                select(WorkflowVersionTable)
                .where(WorkflowVersionTable.workflow_id == workflow_id)
                .order_by(desc(WorkflowVersionTable.version))
                .limit(limit)
                .offset(offset)
            )
            result = await session.execute(stmt)
            return result.scalars().all()

        return await self._execute_query(_query)

    async def query_workflow_version(
        self,
        workflow_id: str,
        version: int,
    ) -> Optional[WorkflowVersionTable]:
        async def _query(session):
            stmt = select(WorkflowVersionTable).where(
                WorkflowVersionTable.workflow_id == workflow_id,
                WorkflowVersionTable.version == version,
            )
            result = await session.execute(stmt)
            return result.scalars().first()

        return await self._execute_query(_query)

    async def create_workflow_run(
        self,
        user: str,
        workflow_id: Optional[str],
        workflow_version: Optional[int],
        execution_id: Optional[str],
        input_payload: Optional[dict[str, Any]],
    ) -> WorkflowRunTable:
        async def _operation(session):
            instance = WorkflowRunTable(
                user=user,
                workflow_id=workflow_id,
                workflow_version=workflow_version,
                execution_id=execution_id,
                status=WorkflowRunStatus.RUNNING,
                input=input_payload,
            )
            session.add(instance)
            await session.flush()
            await session.refresh(instance)
            return instance

        return await self.execute_with_transaction(_operation)

    async def update_workflow_run(
        self,
        run_id: str,
        status: WorkflowRunStatus,
        output_payload: Optional[dict[str, Any]],
        error: Optional[str],
        finished_at,
    ) -> Optional[WorkflowRunTable]:
        async def _operation(session):
            stmt = select(WorkflowRunTable).where(WorkflowRunTable.id == run_id)
            result = await session.execute(stmt)
            instance = result.scalars().first()
            if not instance:
                return None
            instance.status = status
            instance.output = output_payload
            instance.error = error
            instance.finished_at = finished_at
            instance.gmt_updated = utc_now()
            session.add(instance)
            await session.flush()
            await session.refresh(instance)
            return instance

        return await self.execute_with_transaction(_operation)

    async def create_node_run(
        self,
        run_id: str,
        node_id: str,
        node_type: Optional[str],
        input_snapshot: Optional[dict[str, Any]],
        started_at,
    ) -> NodeRunTable:
        async def _operation(session):
            instance = NodeRunTable(
                run_id=run_id,
                node_id=node_id,
                node_type=node_type,
                status=NodeRunStatus.RUNNING,
                input_snapshot=input_snapshot,
                started_at=started_at,
            )
            session.add(instance)
            await session.flush()
            await session.refresh(instance)
            return instance

        return await self.execute_with_transaction(_operation)

    async def update_node_run(
        self,
        node_run_id: str,
        status: NodeRunStatus,
        output_snapshot: Optional[dict[str, Any]],
        error: Optional[str],
        duration_ms: Optional[int],
        finished_at,
    ) -> Optional[NodeRunTable]:
        async def _operation(session):
            stmt = select(NodeRunTable).where(NodeRunTable.id == node_run_id)
            result = await session.execute(stmt)
            instance = result.scalars().first()
            if not instance:
                return None
            instance.status = status
            instance.output_snapshot = output_snapshot
            instance.error = error
            instance.duration_ms = duration_ms
            instance.finished_at = finished_at
            instance.gmt_updated = utc_now()
            session.add(instance)
            await session.flush()
            await session.refresh(instance)
            return instance

        return await self.execute_with_transaction(_operation)

    async def query_workflow_runs(
        self,
        user: str,
        workflow_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[WorkflowRunTable]:
        async def _query(session):
            stmt = (
                select(WorkflowRunTable)
                .where(WorkflowRunTable.user == user, WorkflowRunTable.workflow_id == workflow_id)
                .order_by(desc(WorkflowRunTable.started_at))
                .limit(limit)
                .offset(offset)
            )
            result = await session.execute(stmt)
            return result.scalars().all()

        return await self._execute_query(_query)

    async def query_workflow_run(
        self,
        user: str,
        workflow_id: str,
        run_id: str,
    ) -> Optional[WorkflowRunTable]:
        async def _query(session):
            stmt = select(WorkflowRunTable).where(
                WorkflowRunTable.user == user,
                WorkflowRunTable.workflow_id == workflow_id,
                WorkflowRunTable.id == run_id,
            )
            result = await session.execute(stmt)
            return result.scalars().first()

        return await self._execute_query(_query)

    async def query_node_runs(self, run_id: str) -> list[NodeRunTable]:
        async def _query(session):
            stmt = select(NodeRunTable).where(NodeRunTable.run_id == run_id).order_by(NodeRunTable.started_at)
            result = await session.execute(stmt)
            return result.scalars().all()

        return await self._execute_query(_query)
