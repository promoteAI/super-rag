from typing import List, Optional

from sqlalchemy import desc, select

from super_rag.db.models import Agent, AgentStatus
from super_rag.db.repositories.base import AsyncRepositoryProtocol
from super_rag.utils.utils import utc_now


class AsyncAgentRepositoryMixin(AsyncRepositoryProtocol):
    async def query_agent(self, user: str, agent_id: str):
        async def _query(session):
            stmt = select(Agent).where(Agent.id == agent_id, Agent.user == user, Agent.status != AgentStatus.DELETED)
            result = await session.execute(stmt)
            return result.scalars().first()

        return await self._execute_query(_query)

    async def query_agents(self, users: List[str]):
        async def _query(session):
            stmt = (
                select(Agent).where(Agent.user.in_(users), Agent.status != AgentStatus.DELETED).order_by(desc(Agent.gmt_created))
            )
            result = await session.execute(stmt)
            return result.scalars().all()

        return await self._execute_query(_query)

    async def query_agents_count(self, user: str):
        async def _query(session):
            from sqlalchemy import func

            stmt = select(func.count()).select_from(Agent).where(Agent.user == user, Agent.status != AgentStatus.DELETED)
            return await session.scalar(stmt)

        return await self._execute_query(_query)

    async def update_agent_config_by_id(self, user: str, agent_id: str, config: str) -> Optional[Agent]:
        async def _operation(session):
            stmt = select(Agent).where(Agent.id == agent_id, Agent.user == user, Agent.status != AgentStatus.DELETED)
            result = await session.execute(stmt)
            instance = result.scalars().first()

            if instance:
                instance.config = config
                session.add(instance)
                await session.flush()
                await session.refresh(instance)

            return instance

        return await self.execute_with_transaction(_operation)

    async def delete_agent_by_id(self, user: str, agent_id: str) -> Optional[Agent]:
        async def _operation(session):
            stmt = select(Agent).where(Agent.id == agent_id, Agent.user == user, Agent.status != AgentStatus.DELETED)
            result = await session.execute(stmt)
            instance = result.scalars().first()

            if instance:
                instance.status = AgentStatus.DELETED
                instance.gmt_deleted = utc_now()
                session.add(instance)
                await session.flush()
                await session.refresh(instance)

            return instance

        return await self.execute_with_transaction(_operation)
