

from abc import ABC, abstractmethod
from typing import Any

from super_rag.graphiti.graphiti_core.driver.query_executor import QueryExecutor
from super_rag.graphiti.graphiti_core.nodes import CommunityNode, EntityNode, EpisodicNode


class GraphMaintenanceOperations(ABC):
    @abstractmethod
    async def clear_data(
        self,
        executor: QueryExecutor,
        group_ids: list[str] | None = None,
    ) -> None: ...

    @abstractmethod
    async def build_indices_and_constraints(
        self,
        executor: QueryExecutor,
        delete_existing: bool = False,
    ) -> None: ...

    @abstractmethod
    async def delete_all_indexes(
        self,
        executor: QueryExecutor,
    ) -> None: ...

    @abstractmethod
    async def get_community_clusters(
        self,
        executor: QueryExecutor,
        group_ids: list[str] | None = None,
    ) -> list[Any]: ...

    @abstractmethod
    async def remove_communities(
        self,
        executor: QueryExecutor,
    ) -> None: ...

    @abstractmethod
    async def determine_entity_community(
        self,
        executor: QueryExecutor,
        entity: EntityNode,
    ) -> None: ...

    @abstractmethod
    async def get_mentioned_nodes(
        self,
        executor: QueryExecutor,
        episodes: list[EpisodicNode],
    ) -> list[EntityNode]: ...

    @abstractmethod
    async def get_communities_by_nodes(
        self,
        executor: QueryExecutor,
        nodes: list[EntityNode],
    ) -> list[CommunityNode]: ...
