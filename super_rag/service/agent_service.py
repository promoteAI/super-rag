import json
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from super_rag.db import models as db_models
from super_rag.db.ops import AsyncDatabaseOps, async_db_ops
from super_rag.exceptions import ResourceNotFoundException
from super_rag.schema import view_models
from super_rag.schema.utils import normalize_schema_fields


class AgentService:
    """Agent service that handles business logic for agents (backed by Agent table)."""

    def __init__(self, session: AsyncSession = None):
        if session is None:
            self.db_ops = async_db_ops
        else:
            self.db_ops = AsyncDatabaseOps(session)

    async def _strip_flow_config(self, user: str, agent_id: str, config_dict: dict) -> dict:
        if "flow" not in config_dict:
            return config_dict
        config_dict.pop("flow", None)
        await self.db_ops.update_agent_config_by_id(
            user=user,
            agent_id=agent_id,
            config=json.dumps(config_dict, ensure_ascii=False),
        )
        return config_dict

    async def build_agent_response(self, bot: db_models.Agent) -> view_models.AgentRecord:
        agent_config = None
        if bot.config:
            config_dict = json.loads(bot.config)
            config_dict = normalize_schema_fields(config_dict)
            config_dict = await self._strip_flow_config(bot.user, bot.id, config_dict)
            agent_config = view_models.AgentConfig(**config_dict)

        return view_models.AgentRecord(
            id=bot.id,
            title=bot.title,
            description=bot.description,
            type=bot.type,
            config=agent_config,
            created=bot.gmt_created.isoformat(),
            updated=bot.gmt_updated.isoformat(),
        )

    async def validate_collections(self, user: str, agent_config: view_models.AgentConfig):
        if agent_config and agent_config.agent and agent_config.agent.collections:
            collection_ids = [collection.id for collection in agent_config.agent.collections]
            collections = await self.db_ops.query_collections_by_ids(user, collection_ids)
            if not collections or len(collections) != len(collection_ids):
                raise ResourceNotFoundException("Collection", collection_ids)

    async def create_agent(self, user: str, agent_in: view_models.AgentCreate) -> view_models.AgentRecord:
        async def _create_agent_atomically(session):
            from super_rag.db.models import Agent, AgentStatus

            await self.validate_collections(user, agent_in.config)

            config_str = "{}"
            if agent_in.config:
                config_str = json.dumps(agent_in.config.model_dump(exclude_none=True, by_alias=True))

            bot = Agent(
                user=user,
                title=agent_in.title,
                type=agent_in.type,
                status=AgentStatus.ACTIVE,
                description=agent_in.description,
                config=config_str,
            )
            session.add(bot)
            await session.flush()
            await session.refresh(bot)
            return bot

        bot = await self.db_ops.execute_with_transaction(_create_agent_atomically)
        return await self.build_agent_response(bot)

    async def list_agents(self, user: str) -> view_models.AgentList:
        agents = await self.db_ops.query_agents([user])
        return view_models.AgentList(items=[await self.build_agent_response(agent) for agent in agents])

    async def get_agent(self, user: str, agent_id: str) -> view_models.AgentRecord:
        agent = await self.db_ops.query_agent(user, agent_id)
        if agent is None:
            raise ResourceNotFoundException("Agent", agent_id)
        return await self.build_agent_response(agent)

    async def update_agent(
        self, user: str, agent_id: str, agent_in: view_models.AgentUpdate
    ) -> view_models.AgentRecord:
        agent = await self.db_ops.query_agent(user, agent_id)
        if agent is None:
            raise ResourceNotFoundException("Agent", agent_id)

        new_config_str = None
        if agent_in.config:
            new_config_str = json.dumps(agent_in.config.model_dump(exclude_none=True, by_alias=True))

        await self.validate_collections(user, agent_in.config)

        async def _update_agent_atomically(session):
            from sqlalchemy import select

            from super_rag.db.models import Agent, AgentStatus

            stmt = select(Agent).where(Agent.id == agent_id, Agent.user == user, Agent.status != AgentStatus.DELETED)
            result = await session.execute(stmt)
            agent_to_update = result.scalars().first()

            if not agent_to_update:
                raise ResourceNotFoundException("Agent", agent_id)

            if agent_in.title is not None:
                agent_to_update.title = agent_in.title
            if agent_in.description is not None:
                agent_to_update.description = agent_in.description
            if agent_in.type is not None:
                agent_to_update.type = agent_in.type
            if new_config_str is not None:
                agent_to_update.config = new_config_str
            session.add(agent_to_update)
            await session.flush()
            await session.refresh(agent_to_update)
            return agent_to_update

        updated_agent = await self.db_ops.execute_with_transaction(_update_agent_atomically)
        return await self.build_agent_response(updated_agent)

    async def delete_agent(self, user: str, agent_id: str) -> Optional[view_models.AgentRecord]:
        agent = await self.db_ops.query_agent(user, agent_id)
        if agent is None:
            return None

        async def _delete_agent_atomically(session):
            from sqlalchemy import select

            from super_rag.db.models import Agent, AgentStatus, utc_now

            stmt = select(Agent).where(Agent.id == agent_id, Agent.user == user, Agent.status != AgentStatus.DELETED)
            result = await session.execute(stmt)
            agent_to_delete = result.scalars().first()

            if not agent_to_delete:
                return None

            agent_to_delete.status = AgentStatus.DELETED
            agent_to_delete.gmt_deleted = utc_now()
            session.add(agent_to_delete)
            await session.flush()
            await session.refresh(agent_to_delete)
            return agent_to_delete

        deleted_agent = await self.db_ops.execute_with_transaction(_delete_agent_atomically)
        if deleted_agent:
            return await self.build_agent_response(deleted_agent)
        return None


agent_service = AgentService()
