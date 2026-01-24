from abc import ABC
from typing import Any, List, Optional
from super_rag.models import QueryWithEmbedding
from super_rag.vectorstore.connector import VectorStoreConnectorAdaptor


class ContextManager(ABC):
    def __init__(self, collection_name, embedding_model, vectordb_type, vectordb_ctx):
        self.collection_name = collection_name
        self.embedding_model = embedding_model
        self.vectordb_type = vectordb_type
        self.adaptor = VectorStoreConnectorAdaptor(vectordb_type, vectordb_ctx)

    def query(self, query, score_threshold=0.5, topk=3, vector=None, index_types=None, chat_id=None):
        """
        Query vectors with optional filtering by index types and chat_id

        Args:
            query: Query string
            score_threshold: Similarity threshold
            topk: Number of results to return
            vector: Pre-computed query vector (optional)
            index_types: List of index types to include (e.g., ["vector", "vision", "summary"])
                        If None, no filtering is applied
            chat_id: Chat ID to filter chat documents (optional)

        Returns:
            List of DocumentWithScore objects
        """
        if vector is None:
            vector = self.embedding_model.embed_query(query)

        # Create filter based on index_types and chat_id if provided
        filter_condition = self._create_combined_filter(index_types, chat_id)

        query_embedding = QueryWithEmbedding(query=query, top_k=topk, embedding=vector)
        results = self.adaptor.connector.search(
            query_embedding,
            collection_name=self.collection_name,
            query_vector=query_embedding.embedding,
            with_vectors=True,
            limit=query_embedding.top_k,
            consistency="majority",
            search_params={"hnsw_ef": 128, "exact": False},
            score_threshold=score_threshold,
            filter=filter_condition,
        )
        return results.results

    def _create_index_types_filter(self, index_types: List[str]) -> Optional[Any]:
        """
        Create a filter to include only specified index types (for seekdb)

        Args:
            index_types: List of index types to include (e.g., ["vector", "vision", "summary"])

        Returns:
            Dict filter for seekdb or None if not needed
        """
        if not index_types:
            return None

        if self.vectordb_type == "seekdb":
            # SeekDB 支持类似 SQL 的条件过滤，表达为字典结构
            # indexer IN index_types 或 indexer 不存在
            return {
                "or": [
                    {"indexer": {"$in": index_types}},
                    {"indexer": {"$exists": False}},  # 兼容老向量无indexer字段
                ]
            }
        return None

    def _create_combined_filter(
        self, index_types: Optional[List[str]] = None, chat_id: Optional[str] = None
    ) -> Optional[Any]:
        """
        Create a combined filter for index types and chat_id (for seekdb)

        Args:
            index_types: List of index types to include (e.g., ["vector", "vision", "summary"])
            chat_id: Chat ID to filter chat documents

        Returns:
            Dict filter for seekdb or None if no filters
        """
        if not index_types and not chat_id:
            return None

        if self.vectordb_type == "seekdb":
            filter_clauses = []

            # Add index_types filter
            if index_types:
                filter_clauses.append({
                    "or": [
                        {"indexer": {"$in": index_types}},
                        {"indexer": {"$exists": False}},
                    ]
                })

            # Add chat_id filter
            if chat_id:
                filter_clauses.append({"chat_id": chat_id})

            if len(filter_clauses) == 1:
                return filter_clauses[0]
            elif len(filter_clauses) > 1:
                return {"and": filter_clauses}

        return None
