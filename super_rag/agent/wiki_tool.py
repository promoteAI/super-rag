"""
Wiki tools for Agent ReAct loop.

Provides wiki_write_page, wiki_read_page, and wiki_search_pages as
direct Python tools (not MCP) so the agent can read/write wiki pages
during conversation ¡ª mirroring WeKnora's wiki tool integration.
"""
import json
import logging
from typing import Any, Dict, List, Optional

from agno.tools import Toolkit

from super_rag.db.ops import async_db_ops

logger = logging.getLogger(__name__)


def _tool_error(result: Dict[str, Any]) -> str:
    """Format a tool error result as JSON string."""
    return json.dumps(result, ensure_ascii=False)


class WikiTools(Toolkit):
    """Agent toolkit for wiki page operations."""

    name = "wiki"

    def __init__(self, **kwargs):
        super().__init__(name=self.name, **kwargs)
        self.register_functions([
            self.wiki_write_page,
            self.wiki_read_page,
            self.wiki_search_pages,
        ])

    async def wiki_write_page(
        self,
        collection_id: str,
        slug: str,
        title: str,
        page_type: str,
        content: str,
        user_id: str = "agent",
        summary: Optional[str] = None,
        aliases: Optional[List[str]] = None,
        source_refs: Optional[List[str]] = None,
        in_links: Optional[List[str]] = None,
        out_links: Optional[List[str]] = None,
    ) -> str:
        """Write or update a wiki page.

        Use this to create entity pages, concept pages, synthesis pages,
        or update existing pages with new information. The slug should be
        URL-friendly (e.g. entity/acme-corp or concept/rag).

        Args:
            collection_id: The knowledge base (collection) ID.
            slug: URL-friendly unique slug for the page.
            title: Human-readable page title.
            page_type: Type of page - summary, entity, concept, synthesis, comparison.
            content: Full markdown content of the page.
            user_id: User ID (defaults to "agent").
            summary: One-line summary for index listing (optional).
            aliases: Alternate names for the page (optional).
            source_refs: References to source document IDs (optional).
            in_links: Slugs of pages linking to this page (optional).
            out_links: Slugs of pages this page links to (optional).
        """
        try:
            existing = await async_db_ops.get_wiki_page(collection_id, slug)
            if existing:
                fields = {
                    "title": title, "content": content,
                    "summary": summary or existing.summary,
                    "page_type": page_type,
                    "aliases": aliases or existing.aliases,
                    "source_refs": source_refs or existing.source_refs,
                }
                if in_links is not None:
                    fields["in_links"] = in_links
                if out_links is not None:
                    fields["out_links"] = out_links
                page = await async_db_ops.update_wiki_page(collection_id, slug, **fields)
                action = "updated"
            else:
                page = await async_db_ops.create_wiki_page(
                    collection_id=collection_id, user_id=user_id,
                    slug=slug, title=title, page_type=page_type,
                    content=content, summary=summary or "",
                    aliases=aliases or [], source_refs=source_refs or [],
                )
                action = "created"

            return json.dumps({
                "success": True, "action": action,
                "slug": slug, "title": title,
                "page_type": page_type,
                "version": getattr(page, "version", 1),
            }, ensure_ascii=False)

        except Exception as e:
            logger.error(f"wiki_write_page error: {e}", exc_info=True)
            return _tool_error({"success": False, "error": str(e)})

    async def wiki_read_page(self, collection_id: str, slug: str) -> str:
        """Read a wiki page from a knowledge base.

        Use this to retrieve existing wiki content for reference
        before writing or synthesizing new information.

        Args:
            collection_id: The knowledge base (collection) ID.
            slug: URL-friendly slug of the page to read.
        """
        try:
            page = await async_db_ops.get_wiki_page(collection_id, slug)
            if not page:
                return _tool_error({"success": False, "error": f"Page not found: {slug}"})
            return json.dumps({
                "success": True,
                "slug": page.slug, "title": page.title,
                "page_type": page.page_type,
                "content": page.content,
                "summary": page.summary,
                "version": getattr(page, "version", 1),
            }, ensure_ascii=False)
        except Exception as e:
            logger.error(f"wiki_read_page error: {e}", exc_info=True)
            return _tool_error({"success": False, "error": str(e)})

    async def wiki_search_pages(self, collection_id: str, query: str, limit: int = 10) -> str:
        """Search wiki pages in a knowledge base by title or content.

        Useful for finding related pages before creating or updating one.

        Args:
            collection_id: The knowledge base (collection) ID.
            query: Search query string.
            limit: Maximum number of results (default 10).
        """
        try:
            pages = await async_db_ops.search_wiki_pages(collection_id, query, limit=limit)
            return json.dumps({
                "success": True, "query": query,
                "results": [
                    {"slug": p.slug, "title": p.title, "summary": p.summary}
                    for p in pages
                ],
                "count": len(pages),
            }, ensure_ascii=False)
        except Exception as e:
            logger.error(f"wiki_search error: {e}", exc_info=True)
            return _tool_error({"success": False, "error": str(e)})
