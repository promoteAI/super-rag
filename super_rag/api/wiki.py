import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from super_rag.api.auth import required_user
from super_rag.db.models import Collection, CollectionStatus, User
from super_rag.db.ops import async_db_ops
from super_rag.schema.view_models_extra import (
    WikiGraphData,
    WikiIndexGroup,
    WikiIndexResponse,
    WikiLogListResponse,
    WikiPage,
    WikiPageCreate,
    WikiPageListResponse,
    WikiPageSearchResult,
    WikiPageUpdate,
    WikiStats,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["wiki"])


@router.get("/collections/{collection_id}/wiki/pages", response_model=WikiPageListResponse)
async def list_wiki_pages(
    collection_id: str,
    page_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    query: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("gmt_updated"),
    sort_order: str = Query("desc"),
    user: User = Depends(required_user),
):
    coll = await async_db_ops.query_collection(str(user.id), collection_id)
    if not coll:
        raise HTTPException(status_code=404, detail="Collection not found")
    if not hasattr(async_db_ops, "list_wiki_pages"):
        raise HTTPException(status_code=501, detail="Wiki feature not yet implemented")
    pages, total = await async_db_ops.list_wiki_pages(
        collection_id, page_type=page_type, status=status, query=query,
        page=page, page_size=page_size, sort_by=sort_by, sort_order=sort_order,
    )
    return WikiPageListResponse(
        items=pages, total=total, page=page, page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if page_size > 0 else 0,
    )


@router.post("/collections/{collection_id}/wiki/pages", response_model=WikiPage, status_code=201)
async def create_wiki_page(
    collection_id: str,
    page_data: WikiPageCreate,
    user: User = Depends(required_user),
):
    coll = await async_db_ops.query_collection(str(user.id), collection_id)
    if not coll:
        raise HTTPException(status_code=404, detail="Collection not found")
    if not hasattr(async_db_ops, "create_wiki_page"):
        raise HTTPException(status_code=501, detail="Wiki feature not yet implemented")
    page = await async_db_ops.create_wiki_page(
        collection_id=collection_id, user_id=str(user.id),
        slug=page_data.slug, title=page_data.title,
        page_type=page_data.page_type, content=page_data.content,
        summary=page_data.summary or "", aliases=page_data.aliases,
        source_refs=page_data.source_refs, metadata=page_data.page_metadata,
    )
    return page


@router.get("/collections/{collection_id}/wiki/pages/{slug:path}", response_model=WikiPage)
async def get_wiki_page(collection_id: str, slug: str, user: User = Depends(required_user)):
    coll = await async_db_ops.query_collection(str(user.id), collection_id)
    if not coll:
        raise HTTPException(status_code=404, detail="Collection not found")
    if not hasattr(async_db_ops, "get_wiki_page"):
        raise HTTPException(status_code=501, detail="Wiki feature not yet implemented")
    page = await async_db_ops.get_wiki_page(collection_id, slug)
    if not page:
        raise HTTPException(status_code=404, detail="Wiki page not found")
    return page


@router.put("/collections/{collection_id}/wiki/pages/{slug:path}", response_model=WikiPage)
async def update_wiki_page(
    collection_id: str, slug: str, page_data: WikiPageUpdate,
    user: User = Depends(required_user),
):
    coll = await async_db_ops.query_collection(str(user.id), collection_id)
    if not coll:
        raise HTTPException(status_code=404, detail="Collection not found")
    if not hasattr(async_db_ops, "update_wiki_page"):
        raise HTTPException(status_code=501, detail="Wiki feature not yet implemented")
    fields = {}
    for field in ("title", "content", "summary", "page_type", "status", "aliases", "source_refs", "chunk_refs", "page_metadata"):
        val = getattr(page_data, field, None)
        if val is not None:
            fields[field] = val
    page = await async_db_ops.update_wiki_page(collection_id, slug, **fields)
    if not page:
        raise HTTPException(status_code=404, detail="Wiki page not found")
    return page


@router.delete("/collections/{collection_id}/wiki/pages/{slug:path}")
async def delete_wiki_page(collection_id: str, slug: str, user: User = Depends(required_user)):
    coll = await async_db_ops.query_collection(str(user.id), collection_id)
    if not coll:
        raise HTTPException(status_code=404, detail="Collection not found")
    if not hasattr(async_db_ops, "delete_wiki_page"):
        raise HTTPException(status_code=501, detail="Wiki feature not yet implemented")
    deleted = await async_db_ops.delete_wiki_page(collection_id, slug)
    if not deleted:
        raise HTTPException(status_code=404, detail="Wiki page not found")
    return {"deleted": True}


@router.get("/collections/{collection_id}/wiki/graph", response_model=WikiGraphData)
async def get_wiki_graph(
    collection_id: str, mode: str = Query("overview"),
    center: Optional[str] = Query(None), limit: int = Query(500, ge=1, le=5000),
    types: Optional[str] = Query(None), user: User = Depends(required_user),
):
    coll = await async_db_ops.query_collection(str(user.id), collection_id)
    if not coll:
        raise HTTPException(status_code=404, detail="Collection not found")
    if not hasattr(async_db_ops, "get_wiki_graph"):
        raise HTTPException(status_code=501, detail="Wiki feature not yet implemented")
    type_list = types.split(",") if types else None
    graph = await async_db_ops.get_wiki_graph(
        collection_id, mode=mode, center=center, limit=limit, types=type_list,
    )
    return graph


@router.get("/collections/{collection_id}/wiki/stats", response_model=WikiStats)
async def get_wiki_stats(collection_id: str, user: User = Depends(required_user)):
    coll = await async_db_ops.query_collection(str(user.id), collection_id)
    if not coll:
        raise HTTPException(status_code=404, detail="Collection not found")
    if not hasattr(async_db_ops, "get_wiki_stats"):
        raise HTTPException(status_code=501, detail="Wiki feature not yet implemented")
    stats = await async_db_ops.get_wiki_stats(collection_id)
    return stats


@router.get("/collections/{collection_id}/wiki/index", response_model=WikiIndexResponse)
async def get_wiki_index(
    collection_id: str, types: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=100), user: User = Depends(required_user),
):
    coll = await async_db_ops.query_collection(str(user.id), collection_id)
    if not coll:
        raise HTTPException(status_code=404, detail="Collection not found")
    if not hasattr(async_db_ops, "get_wiki_index"):
        raise HTTPException(status_code=501, detail="Wiki feature not yet implemented")
    type_list = types.split(",") if types else None
    result = await async_db_ops.get_wiki_index(collection_id, types=type_list, limit=limit)
    groups = [WikiIndexGroup(**g) for g in result.get("groups", [])]
    return WikiIndexResponse(groups=groups)


@router.get("/collections/{collection_id}/wiki/search", response_model=List[WikiPageSearchResult])
async def search_wiki_pages(
    collection_id: str, q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100), user: User = Depends(required_user),
):
    coll = await async_db_ops.query_collection(str(user.id), collection_id)
    if not coll:
        raise HTTPException(status_code=404, detail="Collection not found")
    if not hasattr(async_db_ops, "search_wiki_pages"):
        raise HTTPException(status_code=501, detail="Wiki feature not yet implemented")
    pages = await async_db_ops.search_wiki_pages(collection_id, q, limit=limit)
    return [WikiPageSearchResult(slug=p.slug, title=p.title, summary=p.summary) for p in pages]


@router.get("/collections/{collection_id}/wiki/logs", response_model=WikiLogListResponse)
async def list_wiki_logs(
    collection_id: str, cursor: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200), user: User = Depends(required_user),
):
    coll = await async_db_ops.query_collection(str(user.id), collection_id)
    if not coll:
        raise HTTPException(status_code=404, detail="Collection not found")
    if not hasattr(async_db_ops, "list_wiki_logs"):
        raise HTTPException(status_code=501, detail="Wiki feature not yet implemented")
    logs, next_cursor = await async_db_ops.list_wiki_logs(collection_id, cursor=cursor, limit=limit)
    return WikiLogListResponse(entries=logs, next_cursor=next_cursor)


@router.post("/collections/{collection_id}/wiki/rebuild-links")
async def rebuild_wiki_links(collection_id: str, user: User = Depends(required_user)):
    coll = await async_db_ops.query_collection(str(user.id), collection_id)
    if not coll:
        raise HTTPException(status_code=404, detail="Collection not found")
    return {"status": "rebuild_triggered", "collection_id": collection_id}
