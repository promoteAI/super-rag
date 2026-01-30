from typing import Any, Optional

from sqlalchemy import desc, func, select

from super_rag.db.models import WorkflowStatus, WorkflowTable, WorkflowVersionTable
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
