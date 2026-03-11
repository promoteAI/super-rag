

import logging
from typing import List, Optional, Tuple

from pydantic import BaseModel, Field

from super_rag.db.models import Collection
from super_rag.db.ops import async_db_ops
from super_rag.nodeflow.base.models import BaseNodeRunner, SystemInput, register_node_runner
from super_rag.models import DocumentWithScore
from super_rag.schema.utils import parseCollectionConfig

logger = logging.getLogger(__name__)


# User input model for graph search node
class GraphSearchInput(BaseModel):
    top_k: int = Field(5, description="Number of top results to return")
    collection_ids: Optional[list[str]] = Field(default_factory=list, description="Collection IDs")


# User output model for graph search node
class GraphSearchOutput(BaseModel):
    docs: List[DocumentWithScore]


# Database operations interface
class GraphSearchRepository:
    """Repository interface for graph search database operations"""

    async def get_collection(self, user, collection_id: str) -> Optional[Collection]:
        """Get collection by ID for the user"""
        return await async_db_ops.query_collection(user, collection_id)


# Business logic service
class GraphSearchService:
    """Service class containing graph search business logic"""

    def __init__(self, repository: GraphSearchRepository):
        self.repository = repository

    async def execute_graph_search(
        self, user, query: str, top_k: int, collection_ids: List[str]
    ) -> List[DocumentWithScore]:
        """Execute graph search with given parameters"""
        collection = None
        if collection_ids:
            collection = await self.repository.get_collection(user, collection_ids[0])

        if not collection:
            return []

        config = parseCollectionConfig(collection.config)
        if not config.enable_knowledge_graph:
            logger.warning(f"Collection {collection.id} does not have knowledge graph enabled")
            return []

        # Use Graphiti for graph search (same backend as graph indexing)
        from super_rag.graphiti.graphiti_manager import _create_graphiti_instance
        from super_rag.graphiti.graphiti_core.search.search_config_recipes import COMBINED_HYBRID_SEARCH_RRF
        from super_rag.graphiti.graphiti_core.search.search_helpers import search_results_to_context_string

        graphiti = _create_graphiti_instance(collection)
        try:
            search_config = COMBINED_HYBRID_SEARCH_RRF.model_copy(update={"limit": top_k})
            # Get all document IDs in this collection
            documents = await async_db_ops.query_documents([collection.user], collection.id)
            group_ids = [doc.id for doc in documents]
            results = await graphiti.search_(
                query,
                config=search_config,
                group_ids=group_ids,
            )
            context = search_results_to_context_string(results)
            if not context or not context.strip():
                return []
            return [DocumentWithScore(text=context, metadata={"recall_type": "graph_search"})]
        finally:
            try:
                await graphiti.close()
            except Exception as e:
                logger.warning(f"Failed to close Graphiti driver after graph search: {e}")


@register_node_runner(
    "graph_search",
    input_model=GraphSearchInput,
    output_model=GraphSearchOutput,
)
class GraphSearchNodeRunner(BaseNodeRunner):
    def __init__(self):
        self.repository = GraphSearchRepository()
        self.service = GraphSearchService(self.repository)

    async def run(self, ui: GraphSearchInput, si: SystemInput) -> Tuple[GraphSearchOutput, dict]:
        """
        Run graph search node. ui: user configurable params; si: system injected params (SystemInput).
        Returns (uo, so)
        """
        docs = await self.service.execute_graph_search(
            user=si.user, query=si.query, top_k=ui.top_k, collection_ids=ui.collection_ids or []
        )

        return GraphSearchOutput(docs=docs), {}
