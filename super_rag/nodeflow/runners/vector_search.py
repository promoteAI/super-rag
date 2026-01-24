import json
import logging
from typing import List, Optional, Tuple

from pydantic import BaseModel, Field

from super_rag.config import settings
from super_rag.context.context import ContextManager
from super_rag.db.models import Collection
from super_rag.db.ops import async_db_ops
from super_rag.nodeflow.base.models import BaseNodeRunner, SystemInput, register_node_runner
from super_rag.llm.embed.base_embedding import get_collection_embedding_service_sync
from super_rag.llm.llm_error_types import (
    EmbeddingError,
    ProviderNotFoundError,
)
from super_rag.models import DocumentWithScore
from super_rag.utils.utils import generate_vector_db_collection_name

logger = logging.getLogger(__name__)


# User input model for vector search node
class VectorSearchInput(BaseModel):
    top_k: int = Field(5, description="Number of top results to return")
    similarity_threshold: float = Field(0.2, description="Similarity threshold for vector search")
    collection_ids: Optional[List[str]] = Field(default_factory=list, description="Collection IDs")
    chat_id: Optional[str] = Field(None, description="Chat ID to filter chat documents")


# User output model for vector search node
class VectorSearchOutput(BaseModel):
    docs: List[DocumentWithScore]


# Database operations interface
class VectorSearchRepository:
    """Repository interface for vector search database operations"""

    async def get_collection(self, user, collection_id: str) -> Optional[Collection]:
        """Get collection by ID for the user"""
        return await async_db_ops.query_collection(user, collection_id)


# Business logic service
class VectorSearchService:
    """Service class containing vector search business logic"""

    def __init__(self, repository: VectorSearchRepository):
        self.repository = repository

    async def execute_vector_search(
        self,
        user,
        query: str,
        top_k: int,
        similarity_threshold: float,
        collection_ids: List[str],
        chat_id: Optional[str] = None,
    ) -> List[DocumentWithScore]:
        """Execute vector search with given parameters"""
        collection = None
        if collection_ids:
            collection = await self.repository.get_collection(user, collection_ids[0])

        if not collection:
            return []

        try:
            collection_name = generate_vector_db_collection_name(collection.id)
            embedding_model, vector_size = get_collection_embedding_service_sync(collection)
            vectordb_ctx = json.loads(settings.vector_db_context)
            vectordb_ctx["collection"] = collection_name
            context_manager = ContextManager(collection_name, embedding_model, settings.vector_db_type, vectordb_ctx)

            vector = embedding_model.embed_query(query)

            # Query vector database for vector and vision indexes only (excluding summary)
            results = context_manager.query(
                query,
                score_threshold=similarity_threshold,
                topk=top_k,
                vector=vector,
                index_types=["vector"],
                chat_id=chat_id,
            )

            # Add recall type metadata
            for item in results:
                if item.metadata is None:
                    item.metadata = {}
                item.metadata["recall_type"] = "vector_search"

            return results
        except ProviderNotFoundError as e:
            # Configuration error - gracefully degrade by returning empty results
            logger.warning(f"Vector search skipped for collection {collection.id} due to provider not found: {str(e)}")
            return []
        except EmbeddingError as e:
            # Embedding error - gracefully degrade by returning empty results
            logger.warning(f"Vector search skipped for collection {collection.id} due to embedding error: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Vector search failed for collection {collection.id}: {str(e)}")
            return []


@register_node_runner(
    "vector_search",
    input_model=VectorSearchInput,
    output_model=VectorSearchOutput,
)
class VectorSearchNodeRunner(BaseNodeRunner):
    def __init__(self):
        self.repository = VectorSearchRepository()
        self.service = VectorSearchService(self.repository)

    async def run(self, ui: VectorSearchInput, si: SystemInput) -> Tuple[VectorSearchOutput, dict]:
        """
        Run vector search node. ui: user configurable params; si: system injected params (SystemInput).
        Returns (uo, so)
        """
        chat_id = ui.chat_id or getattr(si, "chat_id", None)

        collection_ids = ui.collection_ids or getattr(si, "collection_ids", [])

        docs = await self.service.execute_vector_search(
            user=si.user,
            query=si.query,
            top_k=ui.top_k,
            similarity_threshold=ui.similarity_threshold,
            collection_ids=collection_ids,
            chat_id=chat_id,
        )
        return VectorSearchOutput(docs=docs), {}


if __name__ == "__main__":
    import asyncio

    async def main():
        repository = VectorSearchRepository()
        service = VectorSearchService(repository)
        docs = await service.execute_vector_search(
            user="123",
            query="你好",
            top_k=3,
            similarity_threshold=0.2,
            collection_ids=["col835e91441e0c8457"],
            chat_id="",
        )
        print(docs)

    asyncio.run(main())