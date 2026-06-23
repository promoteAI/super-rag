"""
Wiki index indexer for document processing pipeline.

Generates wiki pages from parsed document content using LLM-based
information extraction ¡ª mirroring WeKnora's wiki ingest pipeline.
"""
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from super_rag.models import DocumentIndexType, IndexTaskResult, ParsedDocumentData
from super_rag.db.ops import async_db_ops

logger = logging.getLogger(__name__)


@dataclass
class WikiIndexer:
    """Handles wiki page generation from document content."""

    async def create_index(
        self,
        document_id: str,
        content: str,
        doc_parts: List[Any],
        collection,
        file_path: str = "",
    ) -> IndexTaskResult:
        """Generate wiki pages from document content.

        This is a skeleton implementation. In production, you would:
        1. Call an LLM to extract entities, concepts, and relationships
        2. Create/update wiki pages accordingly
        3. Maintain link graph (in_links/out_links)

        For now, this creates a single summary page per document.
        """
        try:
            from super_rag.config import settings

            # Check if wiki is enabled for this collection
            config = getattr(collection, "config", "{}")
            if isinstance(config, str):
                config_dict = json.loads(config)
            else:
                config_dict = config

            index_types = config_dict.get("indexTypes", {})
            wiki_enabled = index_types.get("wiki", False)

            if not wiki_enabled:
                logger.info(f"Wiki indexing disabled for document {document_id}")
                return IndexTaskResult.success_result(
                    index_type=DocumentIndexType.WIKI.value,
                    document_id=document_id,
                    message="Wiki indexing disabled",
                )

            # Extract doc title from doc_parts or file_path
            doc_title = file_path.split("/")[-1] if file_path else "Untitled"
            for part in (doc_parts or []):
                if hasattr(part, "title") and part.title:
                    doc_title = part.title
                    break
                if hasattr(part, "filename") and part.filename:
                    doc_title = part.filename
                    break

            # Generate slug from title
            slug = f"document/{doc_title.lower().replace(' ', '-').replace('_', '-')}"
            slug = slug[:200]  # Limit slug length

            # Create a summary page from document content
            summary = content[:500] + "..." if len(content) > 500 else content

            user_id = getattr(collection, "user", "system")

            # Create wiki page
            page = await async_db_ops.create_wiki_page(
                collection_id=collection.id,
                user_id=str(user_id),
                slug=slug,
                title=doc_title,
                page_type="summary",
                content=content,
                summary=summary,
                source_refs=[document_id],
                metadata={"document_id": document_id, "file_path": file_path},
            )

            # Log the wiki creation
            await async_db_ops.create_wiki_log(
                collection_id=collection.id,
                action="page_create",
                collection_ref=document_id,
                doc_title=doc_title,
                summary=f"Created wiki page: {doc_title}",
                pages_affected=[{"slug": slug, "title": doc_title}],
            )

            logger.info(f"Wiki page created for document {document_id}: {slug}")

            return IndexTaskResult.success_result(
                index_type=DocumentIndexType.WIKI.value,
                document_id=document_id,
                data={"page_slug": slug, "page_id": page.id, "version": page.version},
                message=f"Wiki page created: {slug}",
            )

        except Exception as e:
            error_msg = f"Failed to create wiki index for document {document_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return IndexTaskResult.failed_result(
                index_type=DocumentIndexType.WIKI.value,
                document_id=document_id,
                error=error_msg,
            )

    async def delete_index(self, document_id: str, index_type: str) -> IndexTaskResult:
        """Delete wiki index for a document."""
        try:
            return IndexTaskResult.success_result(
                index_type=index_type,
                document_id=document_id,
                message="Wiki index deleted",
            )
        except Exception as e:
            error_msg = f"Failed to delete wiki index: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return IndexTaskResult.failed_result(
                index_type=index_type, document_id=document_id, error=error_msg
            )

    async def update_index(
        self,
        document_id: str,
        content: str,
        doc_parts: List[Any],
        collection,
        file_path: str = "",
    ) -> IndexTaskResult:
        """Update wiki index for a document (re-generate from new content)."""
        return await self.create_index(document_id, content, doc_parts, collection, file_path)

    def is_enabled(self, collection) -> bool:
        """Check if wiki indexing is enabled for this collection."""
        try:
            config = getattr(collection, "config", "{}")
            if isinstance(config, str):
                config_dict = json.loads(config)
            else:
                config_dict = config
            index_types = config_dict.get("indexTypes", {})
            return index_types.get("wiki", False)
        except Exception:
            return False


wiki_indexer = WikiIndexer()
