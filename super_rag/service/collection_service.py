

import logging
from typing import List, Optional, Tuple

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from super_rag.db import models as db_models
from super_rag.db.ops import AsyncDatabaseOps, async_db_ops
from super_rag.exceptions import ValidationException
from super_rag.nodeflow.base.models import Edge, NodeflowInstance, NodeInstance
from super_rag.nodeflow.engine import NodeflowEngine
from super_rag.schema import view_models
from super_rag.schema.utils import dumpCollectionConfig, parseCollectionConfig
from super_rag.schema.view_models import (
    Collection,
    SearchResult,
    SearchResultItem,
    SearchResultList,
)
from super_rag.service.utils import validate_source_connect_config
from config.ray_tasks import collection_delete_task, collection_init_task

logger = logging.getLogger(__name__)


class CollectionService:
    """Collection service that handles business logic for collections"""

    def __init__(self, session: AsyncSession = None):
        # Use global db_ops instance by default, or create custom one with provided session
        if session is None:
            self.db_ops = async_db_ops  # Use global instance
        else:
            self.db_ops = AsyncDatabaseOps(session)  # Create custom instance for transaction control

    async def build_collection_response(self, instance: db_models.Collection) -> view_models.Collection:
        """Build Collection response object for API return."""
        return Collection(
            id=instance.id,
            title=instance.title,
            description=instance.description,
            type=instance.type,
            status=getattr(instance, "status", None),
            config=parseCollectionConfig(instance.config),
            created=instance.gmt_created.isoformat(),
            updated=instance.gmt_updated.isoformat(),
        )

    async def create_collection(self, user: str, collection: view_models.CollectionCreate) -> view_models.Collection:
        collection_config = collection.config
        
        if collection.type != db_models.CollectionType.DOCUMENT:
            raise ValidationException("collection type is not supported")

        is_validate, error_msg = validate_source_connect_config(collection_config)
        if not is_validate:
            raise ValidationException(error_msg)

        # Create collection and consume quota in a single transaction
        async def _create_collection_with_quota(session):
            # Create collection within the same transaction
            config_str = dumpCollectionConfig(collection_config) if collection.config is not None else None
            from super_rag.db.models import Collection, CollectionStatus
            from super_rag.utils.utils import utc_now

            instance = Collection(
                user=user,
                title=collection.title,
                description=collection.description,
                type=collection.type,
                status=CollectionStatus.ACTIVE,
                config=config_str,
                gmt_created=utc_now(),
                gmt_updated=utc_now(),
            )
            
            session.add(instance)
            await session.flush()
            await session.refresh(instance)

            return instance

        instance = await self.db_ops.execute_with_transaction(_create_collection_with_quota)
        
        # Initialize collection based on type
        collection_init_task.remote(instance.id)

        return await self.build_collection_response(instance)

    async def list_collections_view(
        self, user_id: str, include_subscribed: bool = False, page: int = 1, page_size: int = 20
    ) -> view_models.CollectionViewList:
        """
        Get user's collection list (lightweight view)

        Args:
            user_id: User ID
            include_subscribed: Whether to include subscribed collections, default True
            page: Page number
            page_size: Page size
        """
        items = []

        # 1. Get user's owned collections with marketplace info
        owned_collections_data = await self.db_ops.query_collections_with_marketplace_info(user_id)
        for row in owned_collections_data:
            # is_published = row.marketplace_status == "PUBLISHED"
            items.append(
                view_models.CollectionView(
                    id=row.id,
                    title=row.title,
                    description=row.description,
                    type=row.type,
                    status=row.status,
                    created=row.gmt_created,
                    updated=row.gmt_updated,
                    owner_user_id=row.user,
                )
            )

        # 3. Sort by update time
        items.sort(key=lambda x: x.updated or x.created, reverse=True)

        # 4. Apply pagination
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_items = items[start_idx:end_idx]

        return view_models.CollectionViewList(
            items=paginated_items, pageResult=view_models.PageResult(total=len(items), page=page, page_size=page_size)
        )

    async def get_collection(self, user: str, collection_id: str) -> view_models.Collection:
        from super_rag.exceptions import CollectionNotFoundException

        collection = await self.db_ops.query_collection(user, collection_id)

        if collection is None:
            raise CollectionNotFoundException(collection_id)
        return await self.build_collection_response(collection)

    async def update_collection(
        self, user: str, collection_id: str, collection: view_models.CollectionUpdate
    ) -> view_models.Collection:
        from super_rag.exceptions import CollectionNotFoundException

        # First check if collection exists
        instance = await self.db_ops.query_collection(user, collection_id)
        if instance is None:
            raise CollectionNotFoundException(collection_id)

        # Direct call to repository method, which handles its own transaction
        config_str = dumpCollectionConfig(collection.config)

        updated_instance = await self.db_ops.update_collection_by_id(
            user=user,
            collection_id=collection_id,
            title=collection.title,
            description=collection.description,
            config=config_str,
        )

        if not updated_instance:
            raise CollectionNotFoundException(collection_id)

        return await self.build_collection_response(updated_instance)

    async def delete_collection(self, user: str, collection_id: str) -> Optional[view_models.Collection]:
        """Delete collection by ID (idempotent operation)

        Returns the deleted collection or None if already deleted/not found
        """
        # Check if collection exists - if not, silently succeed (idempotent)
        collection = await self.db_ops.query_collection(user, collection_id)
        if collection is None:
            return None

        # Delete collection and release quota in a single transaction
        async def _delete_collection_with_quota(session):
            from sqlalchemy import select

            from super_rag.db.models import CollectionStatus
            from super_rag.utils.utils import utc_now

            # Get collection within transaction
            stmt = select(db_models.Collection).where(
                db_models.Collection.id == collection_id, db_models.Collection.user == user
            )
            result = await session.execute(stmt)
            collection_to_delete = result.scalars().first()

            if not collection_to_delete:
                return None

            # Mark collection as deleted
            collection_to_delete.status = CollectionStatus.DELETED
            collection_to_delete.gmt_deleted = utc_now()

            await session.flush()
            await session.refresh(collection_to_delete)

            return collection_to_delete

        deleted_instance = await self.db_ops.execute_with_transaction(_delete_collection_with_quota)

        if deleted_instance:
            # Clean up related resources
            collection_delete_task.remote(collection_id)
            return await self.build_collection_response(deleted_instance)

        return None

    async def execute_search_flow(
        self,
        data: view_models.SearchRequest,
        collection_id: str,
        search_user_id: str,
        chat_id: Optional[str] = None,
        flow_name: str = "search",
        flow_title: str = "Search",
    ) -> Tuple[List[SearchResultItem], str]:
        """
        Execute search flow and return search result items and rerank node ID.

        Args:
            data: Search request data
            collection_id: Target collection ID for search
            search_user_id: User ID to use for search operations (may differ from requester for marketplace collections)
            chat_id: Optional chat ID for filtering in chat searches
            flow_name: Name of the flow instance
            flow_title: Title of the flow instance

        Returns:
            Tuple of (search result items, rerank node id)
        """
        from super_rag.service.default_model_service import default_model_service

        # Build flow for search execution
        nodes = {}
        edges = []
        merge_node_id = "merge"
        merge_node_values = {
            "merge_strategy": "union",
            "deduplicate": True,
        }
        query = data.query
        # Configure search nodes based on request
        if data.vector_search:
            node_id = "vector_search"
            input_values = {
                "query": query,
                "top_k": data.vector_search.topk if data.vector_search else 5,
                "similarity_threshold": data.vector_search.similarity if data.vector_search else 0.2,
                "collection_ids": [collection_id],
            }
            # Add chat_id for filtering if provided
            if chat_id:
                input_values["chat_id"] = chat_id

            nodes[node_id] = NodeInstance(
                id=node_id,
                type="vector_search",
                input_values=input_values,
            )
            merge_node_values["vector_search_docs"] = "{{ nodes.vector_search.output.docs }}"
            edges.append(Edge(source=node_id, target=merge_node_id))

        if data.graph_search:
            input_values = {
                "query": query,
                "top_k": data.graph_search.topk if data.graph_search else 5,
                "collection_ids": [collection_id],
            }
            # Add chat_id for filtering if provided
            if chat_id:
                input_values["chat_id"] = chat_id

            nodes["graph_search"] = NodeInstance(
                id="graph_search",
                type="graph_search",
                input_values=input_values,
            )
            merge_node_values["graph_search_docs"] = "{{ nodes.graph_search.output.docs }}"
            edges.append(Edge(source="graph_search", target=merge_node_id))

        nodes[merge_node_id] = NodeInstance(
            id=merge_node_id,
            type="merge",
            input_values=merge_node_values,
        )

        # Add rerank node to flow
        if data.rerank:
            model, model_service_provider, custom_llm_provider = await default_model_service.get_default_rerank_config(
                search_user_id
            )
            use_rerank_service = model is not None
        else:
            model, model_service_provider, custom_llm_provider = None, None, None
            use_rerank_service = False

        rerank_node_id = "rerank"
        nodes[rerank_node_id] = NodeInstance(
            id=rerank_node_id,
            type="rerank",
            input_values={
                "use_rerank_service": use_rerank_service,
                "model": model,
                "model_service_provider": model_service_provider,
                "custom_llm_provider": custom_llm_provider,
                "docs": "{{ nodes.merge.output.docs }}",
            },
        )
        # Add edge from merge to rerank
        edges.append(Edge(source=merge_node_id, target=rerank_node_id))

        # Execute search flow
        flow = NodeflowInstance(
            name=flow_name,
            title=flow_title,
            nodes=nodes,
            edges=edges,
        )
        logger.info(f"{flow}")
        engine = NodeflowEngine()
        # Build initial data with chat_id if provided
        initial_data = {"query": query, "user": search_user_id}
        if chat_id:
            initial_data["chat_id"] = chat_id
        result, _ = await engine.execute_nodeflow(flow,initial_data)

        if not result:
            raise Exception("Failed to execute flow")

        # Process search results from rerank node
        docs = result.get(rerank_node_id, {}).docs
        items = []
        for idx, doc in enumerate(docs):
            items.append(
                SearchResultItem(
                    rank=idx + 1,
                    score=doc.score,
                    content=doc.text,
                    source=doc.metadata.get("source", ""),
                    recall_type=doc.metadata.get("recall_type", ""),
                    metadata=doc.metadata,
                )
            )

        return items, rerank_node_id

    async def create_search(
        self, user: str, collection_id: str, data: view_models.SearchRequest
    ) -> view_models.SearchResult:
        from super_rag.exceptions import CollectionNotFoundException

        # Try to find collection as owner first
        collection = await self.db_ops.query_collection(user, collection_id)

        if not collection:
            # If not found as owner, check if it's a marketplace collection
            try:
                collection = await self.db_ops.query_collection(user, collection_id)
                if not collection:
                    raise CollectionNotFoundException(collection_id)
            except Exception:
                raise CollectionNotFoundException(collection_id)

        # Execute search flow using helper method
        items, _ = await self.execute_search_flow(
            data=data,
            collection_id=collection_id,
            search_user_id=user,
            chat_id=None,  # No chat filtering for regular collection searches
        )
        return SearchResult(
            id=None,  # No ID since not saved
            query=data.query,
            vector_search=data.vector_search,
            graph_search=data.graph_search,
            summary_search=data.summary_search,
            vision_search=data.vision_search,
            items=items,
            created=None,  # No creation time since not saved
        )

    
collection_service = CollectionService()
