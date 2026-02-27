

from abc import ABC, abstractmethod

from super_rag.graphiti.graphiti_core.driver.query_executor import QueryExecutor, Transaction
from super_rag.graphiti.graphiti_core.edges import CommunityEdge


class CommunityEdgeOperations(ABC):
    @abstractmethod
    async def save(
        self,
        executor: QueryExecutor,
        edge: CommunityEdge,
        tx: Transaction | None = None,
    ) -> None: ...

    @abstractmethod
    async def delete(
        self,
        executor: QueryExecutor,
        edge: CommunityEdge,
        tx: Transaction | None = None,
    ) -> None: ...

    @abstractmethod
    async def delete_by_uuids(
        self,
        executor: QueryExecutor,
        uuids: list[str],
        tx: Transaction | None = None,
    ) -> None: ...

    @abstractmethod
    async def get_by_uuid(
        self,
        executor: QueryExecutor,
        uuid: str,
    ) -> CommunityEdge: ...

    @abstractmethod
    async def get_by_uuids(
        self,
        executor: QueryExecutor,
        uuids: list[str],
    ) -> list[CommunityEdge]: ...

    @abstractmethod
    async def get_by_group_ids(
        self,
        executor: QueryExecutor,
        group_ids: list[str],
        limit: int | None = None,
        uuid_cursor: str | None = None,
    ) -> list[CommunityEdge]: ...
