from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.orm import Session

from super_rag.db.models import (
    WikiLogEntry,
    WikiPage,
    WikiPageIssue,
    WikiPageStatus,
    WikiPageType,
)
from super_rag.db.repositories.base import AsyncRepositoryProtocol


class AsyncWikiRepositoryMixin(AsyncRepositoryProtocol):
    """Repository mixin for wiki-related database operations."""

    async def create_wiki_page(
        self,
        collection_id: str,
        user_id: str,
        slug: str,
        title: str,
        page_type: str,
        content: str,
        summary: str,
        aliases: Optional[List[str]] = None,
        source_refs: Optional[List[str]] = None,
        chunk_refs: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> WikiPage:
        async def _op(session):
            page = WikiPage(
                collection_id=collection_id,
                user_id=user_id,
                slug=slug,
                title=title,
                page_type=page_type,
                content=content,
                summary=summary,
                aliases=aliases or [],
                source_refs=source_refs or [],
                chunk_refs=chunk_refs or [],
                page_metadata=metadata or {},
            )
            session.add(page)
            await session.flush()
            await session.refresh(page)
            return page
        return await self.execute_with_transaction(_op)

    async def update_wiki_page(
        self, collection_id: str, slug: str, **fields: Any
    ) -> Optional[WikiPage]:
        async def _op(session):
            stmt = select(WikiPage).where(
                WikiPage.collection_id == collection_id,
                WikiPage.slug == slug,
                WikiPage.gmt_deleted.is_(None),
            )
            result = await session.execute(stmt)
            page = result.scalars().first()
            if page:
                for k, v in fields.items():
                    if hasattr(page, k):
                        setattr(page, k, v)
                page.version += 1
                session.add(page)
                await session.flush()
                await session.refresh(page)
            return page
        return await self.execute_with_transaction(_op)

    async def get_wiki_page(self, collection_id: str, slug: str) -> Optional[WikiPage]:
        async def _q(session):
            stmt = select(WikiPage).where(
                WikiPage.collection_id == collection_id,
                WikiPage.slug == slug,
                WikiPage.gmt_deleted.is_(None),
            )
            return await session.scalar(stmt)
        return await self._execute_query(_q)

    async def list_wiki_pages(
        self,
        collection_id: str,
        page_type: Optional[str] = None,
        status: Optional[str] = None,
        query: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "gmt_updated",
        sort_order: str = "desc",
    ) -> Tuple[List[WikiPage], int]:
        async def _q(session):
            stmt = select(WikiPage).where(
                WikiPage.collection_id == collection_id,
                WikiPage.gmt_deleted.is_(None),
            )
            if page_type:
                stmt = stmt.where(WikiPage.page_type == page_type)
            if status:
                stmt = stmt.where(WikiPage.status == status)
            if query:
                stmt = stmt.where(WikiPage.title.ilike(f"%{query}%"))
            count_stmt = select(func.count()).select_from(stmt.subquery())
            total = await session.scalar(count_stmt) or 0
            order_col = getattr(WikiPage, sort_by, WikiPage.gmt_updated)
            stmt = stmt.order_by(desc(order_col) if sort_order == "desc" else order_col)
            stmt = stmt.offset((page - 1) * page_size).limit(page_size)
            result = await session.execute(stmt)
            return result.scalars().all(), total
        return await self._execute_query(_q)

    async def delete_wiki_page(self, collection_id: str, slug: str) -> bool:
        async def _op(session):
            stmt = select(WikiPage).where(
                WikiPage.collection_id == collection_id,
                WikiPage.slug == slug,
                WikiPage.gmt_deleted.is_(None),
            )
            result = await session.execute(stmt)
            page = result.scalars().first()
            if page:
                from super_rag.utils.utils import utc_now
                page.gmt_deleted = utc_now()
                session.add(page)
                await session.flush()
                return True
            return False
        return await self.execute_with_transaction(_op)

    async def update_links(
        self, collection_id: str, slug: str, in_links: List[str], out_links: List[str]
    ) -> Optional[WikiPage]:
        async def _op(session):
            stmt = select(WikiPage).where(
                WikiPage.collection_id == collection_id,
                WikiPage.slug == slug,
                WikiPage.gmt_deleted.is_(None),
            )
            result = await session.execute(stmt)
            page = result.scalars().first()
            if page:
                page.in_links = in_links
                page.out_links = out_links
                session.add(page)
                await session.flush()
                await session.refresh(page)
            return page
        return await self.execute_with_transaction(_op)

    async def search_wiki_pages(self, collection_id: str, query: str, limit: int = 20) -> List[WikiPage]:
        async def _q(session):
            stmt = (
                select(WikiPage)
                .where(
                    WikiPage.collection_id == collection_id,
                    WikiPage.gmt_deleted.is_(None),
                    WikiPage.status == WikiPageStatus.PUBLISHED,
                )
                .where(or_(
                    WikiPage.title.ilike(f"%{query}%"),
                    WikiPage.content.ilike(f"%{query}%"),
                ))
                .limit(limit)
            )
            return await session.scalars(stmt).all()
        return await self._execute_query(_q)

    async def get_wiki_graph(
        self,
        collection_id: str,
        mode: str = "overview",
        center: Optional[str] = None,
        depth: int = 1,
        limit: int = 500,
        types: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        async def _q(session):
            stmt = select(WikiPage).where(
                WikiPage.collection_id == collection_id,
                WikiPage.gmt_deleted.is_(None),
                WikiPage.status == WikiPageStatus.PUBLISHED,
            )
            if types:
                stmt = stmt.where(WikiPage.page_type.in_(types))
            stmt = stmt.order_by(desc(WikiPage.gmt_updated)).limit(limit)
            result = await session.execute(stmt)
            pages = result.scalars().all()
            slug_set = {p.slug for p in pages}
            slug_map = {p.slug: p for p in pages}
            nodes = []
            for p in pages:
                lc = len(p.in_links or []) + len(p.out_links or [])
                nodes.append({
                    "slug": p.slug,
                    "title": p.title,
                    "page_type": p.page_type,
                    "link_count": lc,
                })
            edges = []
            if mode == "ego" and center:
                neighbor_slugs = set()
                if center in slug_map:
                    cp = slug_map[center]
                    for nl in (cp.out_links or []) + (cp.in_links or []):
                        if nl in slug_set:
                            neighbor_slugs.add(nl)
                    neighbor_slugs.add(center)
                nodes = [n for n in nodes if n["slug"] in neighbor_slugs]
                for ns in neighbor_slugs:
                    if ns in slug_map:
                        for ol in (slug_map[ns].out_links or []):
                            if ol in neighbor_slugs:
                                edges.append({"source": ns, "target": ol})
                        for il in (slug_map[ns].in_links or []):
                            if il in neighbor_slugs:
                                edges.append({"source": il, "target": ns})
            else:
                for p in pages:
                    for ol in (p.out_links or []):
                        if ol in slug_set:
                            edges.append({"source": p.slug, "target": ol})
                    for il in (p.in_links or []):
                        if il in slug_set:
                            edges.append({"source": il, "target": p.slug})
            return {
                "nodes": nodes,
                "edges": edges,
                "meta": {"mode": mode, "total": len(nodes), "returned": len(nodes)},
            }
        return await self._execute_query(_q)

    async def get_wiki_stats(self, collection_id: str) -> Dict[str, Any]:
        async def _q(session):
            total = await session.scalar(select(func.count(WikiPage.id)).where(
                WikiPage.collection_id == collection_id, WikiPage.gmt_deleted.is_(None))) or 0
            by_type_rows = await session.execute(
                select(WikiPage.page_type, func.count(WikiPage.id)).where(
                    WikiPage.collection_id == collection_id, WikiPage.gmt_deleted.is_(None)
                ).group_by(WikiPage.page_type))
            pages_by_type = {r[0]: r[1] for r in by_type_rows.fetchall()}
            pi = await session.scalar(select(func.count(WikiPageIssue.id)).where(
                WikiPageIssue.collection_id == collection_id,
                WikiPageIssue.gmt_deleted.is_(None),
                WikiPageIssue.status == "pending")) or 0
            return {
                "total_pages": total,
                "pages_by_type": pages_by_type,
                "total_links": 0,
                "orphan_count": 0,
                "recent_updates": [],
                "pending_tasks": 0,
                "pending_issues": pi,
                "is_active": total > 0,
            }
        return await self._execute_query(_q)

    async def create_wiki_issue(
        self,
        collection_id: str,
        user_id: str,
        slug: str,
        issue_type: str,
        description: str,
        reported_by: str,
        suspected_ids: Optional[List[str]] = None,
    ) -> WikiPageIssue:
        async def _op(session):
            issue = WikiPageIssue(
                collection_id=collection_id, user_id=user_id, slug=slug,
                issue_type=issue_type, description=description,
                reported_by=reported_by,
                suspected_collection_ids=suspected_ids or [])
            session.add(issue)
            await session.flush()
            await session.refresh(issue)
            return issue
        return await self.execute_with_transaction(_op)

    async def list_wiki_issues(
        self, collection_id: str, slug: Optional[str] = None, status: Optional[str] = None
    ) -> List[WikiPageIssue]:
        async def _q(session):
            stmt = select(WikiPageIssue).where(
                WikiPageIssue.collection_id == collection_id,
                WikiPageIssue.gmt_deleted.is_(None),
            )
            if slug:
                stmt = stmt.where(WikiPageIssue.slug == slug)
            if status:
                stmt = stmt.where(WikiPageIssue.status == status)
            return await session.scalars(stmt).all()
        return await self._execute_query(_q)

    async def update_issue_status(self, issue_id: str, status: str) -> Optional[WikiPageIssue]:
        async def _op(session):
            stmt = select(WikiPageIssue).where(WikiPageIssue.id == issue_id)
            result = await session.execute(stmt)
            issue = result.scalars().first()
            if issue:
                issue.status = status
                session.add(issue)
                await session.flush()
                await session.refresh(issue)
            return issue
        return await self.execute_with_transaction(_op)

    async def create_wiki_log(
        self,
        collection_id: str,
        action: str,
        collection_ref: Optional[str] = None,
        doc_title: Optional[str] = None,
        summary: Optional[str] = None,
        pages_affected: Optional[List[Dict[str, str]]] = None,
    ) -> WikiLogEntry:
        async def _op(session):
            entry = WikiLogEntry(
                collection_id=collection_id, action=action,
                collection_ref=collection_ref, doc_title=doc_title,
                summary=summary, pages_affected=pages_affected or [])
            session.add(entry)
            await session.flush()
            await session.refresh(entry)
            return entry
        return await self.execute_with_transaction(_op)

    async def list_wiki_logs(
        self, collection_id: str, cursor: Optional[str] = None, limit: int = 50
    ) -> Tuple[List[WikiLogEntry], Optional[str]]:
        async def _q(session):
            stmt = (
                select(WikiLogEntry)
                .where(WikiLogEntry.collection_id == collection_id)
                .order_by(desc(WikiLogEntry.gmt_created))
                .limit(limit)
            )
            if cursor:
                stmt = stmt.where(WikiLogEntry.id < int(cursor))
            result = await session.execute(stmt)
            entries = result.scalars().all()
            next_cursor = str(entries[-1].id) if entries else None
            return entries, next_cursor
        return await self._execute_query(_q)

    async def get_wiki_index(
        self, collection_id: str, types: Optional[List[str]] = None, limit: int = 10
    ) -> Dict[str, Any]:
        async def _q(session):
            groups = []
            target_types = types or [
                WikiPageType.SUMMARY.value, WikiPageType.ENTITY.value,
                WikiPageType.CONCEPT.value, WikiPageType.SYNTHESIS.value,
                WikiPageType.COMPARISON.value,
            ]
            for pt in target_types:
                result = await session.execute(
                    select(WikiPage.slug, WikiPage.title, WikiPage.summary).where(
                        WikiPage.collection_id == collection_id,
                        WikiPage.gmt_deleted.is_(None),
                        WikiPage.page_type == pt,
                        WikiPage.status == WikiPageStatus.PUBLISHED,
                    ).order_by(desc(WikiPage.gmt_updated)).limit(limit))
                rows = result.fetchall()
                items = [{"slug": r[0], "title": r[1], "summary": r[2]} for r in rows]
                total = await session.scalar(select(func.count(WikiPage.id)).where(
                    WikiPage.collection_id == collection_id,
                    WikiPage.gmt_deleted.is_(None),
                    WikiPage.page_type == pt,
                    WikiPage.status == WikiPageStatus.PUBLISHED)) or 0
                groups.append({"type": pt, "total": total, "items": items})
            return {"groups": groups}
        return await self._execute_query(_q)
