from typing import Dict, Any
from super_rag.db.ops import async_db_ops
from super_rag.exceptions import CollectionNotFoundException
from super_rag.graphiti.graphiti_manager import (
    get_graph_labels_for_collection,
    get_knowledge_graph_for_collection,
)


class GraphService:
    """Service for knowledge graph operations"""

    def __init__(self):
        from super_rag.service.collection_service import collection_service

        self.collection_service = collection_service
        self.db_ops = async_db_ops

    async def get_graph_labels(self, user_id: str, collection_id: str) -> list[str]:
        """Get the labels of the graph (entity node labels for filtering)."""
        db_collection = await self._get_and_validate_collection(user_id, collection_id)
        return await get_graph_labels_for_collection(db_collection)

    async def _get_and_validate_collection(self, user_id: str, collection_id: str):
        """Get collection and validate knowledge graph is enabled"""
        try:
            view_collection = await self.collection_service.get_collection(user_id, collection_id)
        except Exception:
            raise CollectionNotFoundException(collection_id)

        if not view_collection.config or not view_collection.config.enable_knowledge_graph:
            raise ValueError(f"Knowledge graph is not enabled for collection {collection_id}")

        db_collection = await self.collection_service.db_ops.query_collection(user_id, collection_id)
        if not db_collection:
            raise CollectionNotFoundException(collection_id)

        return db_collection

    async def get_knowledge_graph(
        self,
        user_id: str,
        collection_id: str,
        label: str = None,
        max_depth: int = 3,
        max_nodes: int = 1000,
    ) -> Dict[str, Any]:
        """Get knowledge graph with overview or subgraph mode.
        When label is None or '*', returns an overview (optionally truncated).
        When label is set, returns a subgraph from that entity label up to max_depth.
        """
        db_collection = await self._get_and_validate_collection(user_id, collection_id)
        return await get_knowledge_graph_for_collection(
            db_collection,
            label=label,
            max_depth=max_depth,
            max_nodes=max_nodes,
        )