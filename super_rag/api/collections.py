import logging
from typing import List

from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, Request, UploadFile
from super_rag.service.marketplace_service import marketplace_service
from super_rag.db.models import User
from super_rag.schema import view_models
from super_rag.service.document_service import document_service
from super_rag.service.collection_service import collection_service
from super_rag.api.user import default_user

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/collections", tags=["collections"])
async def create_collection_view(
    collection: view_models.CollectionCreate,
    user: User = Depends(default_user),
) -> view_models.Collection:
    return await collection_service.create_collection(str(user.id), collection)

@router.get("/collections", tags=["collections"])
async def list_collections_view(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1),
    user: User = Depends(default_user),
) -> view_models.CollectionViewList:
    # include_subscribed consistent with source--here: always True.
    include_subscribed = False
    return await collection_service.list_collections_view(str(user.id), include_subscribed, page, page_size)

@router.get("/collections/{collection_id}", tags=["collections"])
async def get_collection_view(
    request: Request,
    collection_id: str,
    user: User = Depends(default_user),
) -> view_models.Collection:
    return await collection_service.get_collection(str(user.id), collection_id)

@router.put("/collections/{collection_id}", tags=["collections"])
async def update_collection_view(
    request: Request,
    collection_id: str,
    collection: view_models.CollectionUpdate,
    user: User = Depends(default_user),
) -> view_models.Collection:
    return await collection_service.update_collection(str(user.id), collection_id, collection)

@router.delete("/collections/{collection_id}", tags=["collections"])
async def delete_collection_view(
    request: Request,
    collection_id: str,
    user: User = Depends(default_user),
) -> view_models.Collection:
    return await collection_service.delete_collection(str(user.id), collection_id)

# Collection sharing endpoints
@router.get("/collections/{collection_id}/sharing", tags=["collections"])
async def get_collection_sharing_status(
    collection_id: str,
    user: User = Depends(default_user),
) -> view_models.SharingStatusResponse:
    """Get collection sharing status (owner only)"""
    from super_rag.exceptions import CollectionNotFoundException, PermissionDeniedError

    try:
        is_published, published_at = await marketplace_service.get_sharing_status(user.id, collection_id)
        return view_models.SharingStatusResponse(is_published=is_published, published_at=published_at)
    except CollectionNotFoundException:
        raise HTTPException(status_code=404, detail="Collection not found")
    except PermissionDeniedError:
        raise HTTPException(status_code=403, detail="Permission denied")
    except Exception as e:
        logger.error(f"Error getting collection sharing status {collection_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/collections/{collection_id}/sharing", tags=["collections"])
async def publish_collection_to_marketplace(
    collection_id: str,
    user: User = Depends(default_user),
) -> view_models.SharingStatusResponse:
    """Publish collection to marketplace (owner only)"""
    from super_rag.exceptions import CollectionNotFoundException, PermissionDeniedError

    try:
        await marketplace_service.publish_collection(user.id, collection_id)
        is_published, published_at = await marketplace_service.get_sharing_status(user.id, collection_id)
        return view_models.SharingStatusResponse(is_published=is_published, published_at=published_at)
    except CollectionNotFoundException:
        raise HTTPException(status_code=404, detail="Collection not found")
    except PermissionDeniedError:
        raise HTTPException(status_code=403, detail="Permission denied")
    except Exception as e:
        logger.error(f"Error publishing collection {collection_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/collections/{collection_id}/sharing", tags=["collections"])
async def unpublish_collection_from_marketplace(
    collection_id: str,
    user: User = Depends(default_user),
) -> view_models.SharingStatusResponse:
    """Unpublish collection from marketplace (owner only)"""
    from super_rag.exceptions import CollectionNotFoundException, PermissionDeniedError

    try:
        await marketplace_service.unpublish_collection(user.id, collection_id)
        return view_models.SharingStatusResponse(is_published=False, published_at=None)
    except CollectionNotFoundException:
        raise HTTPException(status_code=404, detail="Collection not found")
    except PermissionDeniedError:
        raise HTTPException(status_code=403, detail="Permission denied")
    except Exception as e:
        logger.error(f"Error unpublishing collection {collection_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/collections/{collection_id}/documents", tags=["documents"])
async def create_documents_view(
    request: Request,
    collection_id: str,
    files: List[UploadFile] = File(...),
    user: User = Depends(default_user),
) -> view_models.DocumentList:
    return await document_service.create_documents(str(user.id), collection_id, files)


@router.get("/collections/{collection_id}/documents", tags=["documents"])
async def list_documents_view(
    request: Request,
    collection_id: str,
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(10, ge=1, le=100, description="Number of items per page"),
    sort_by: str = Query("created", description="Field to sort by"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="Sort order"),
    search: str = Query(None, description="Search documents by name"),
    user: User = Depends(default_user),
):
    """List documents with pagination, sorting and search capabilities"""

    result = await document_service.list_documents(
        user=str(user.id),
        collection_id=collection_id,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
        search=search,
    )

    return {
        "items": result.items,
        "total": result.total,
        "page": result.page,
        "page_size": result.page_size,
        "total_pages": result.total_pages,
        "has_next": result.has_next,
        "has_prev": result.has_prev,
    }


@router.get("/collections/{collection_id}/documents/{document_id}", tags=["documents"])
async def get_document_view(
    request: Request,
    collection_id: str,
    document_id: str,
    user: User = Depends(default_user),
) -> view_models.Document:
    return await document_service.get_document(str(user.id), collection_id, document_id)


@router.delete("/collections/{collection_id}/documents/{document_id}", tags=["documents"])
async def delete_document_view(
    request: Request,
    collection_id: str,
    document_id: str,
    user: User = Depends(default_user),
) -> view_models.Document:
    return await document_service.delete_document(str(user.id), collection_id, document_id)


@router.delete("/collections/{collection_id}/documents", tags=["documents"])
async def delete_documents_view(
    request: Request,
    collection_id: str,
    document_ids: List[str],
    user: User = Depends(default_user),
):
    return await document_service.delete_documents(str(user.id), collection_id, document_ids)


@router.get(
    "/collections/{collection_id}/documents/{document_id}/preview",
    tags=["documents"],
    operation_id="get_document_preview",
)
async def get_document_preview(
    collection_id: str,
    document_id: str,
    user: User = Depends(default_user),
):
    return await document_service.get_document_preview(str(user.id), collection_id, document_id)


@router.get(
    "/collections/{collection_id}/documents/{document_id}/object",
    tags=["documents"],
    operation_id="get_document_object",
)
async def get_document_object(
    request: Request,
    collection_id: str,
    document_id: str,
    path: str,
    user: User = Depends(default_user),
):
    range_header = request.headers.get("range")
    return await document_service.get_document_object(str(user.id), collection_id, document_id, path, range_header)


@router.post("/collections/{collection_id}/documents/{document_id}/rebuild_indexes", tags=["documents"])
async def rebuild_document_indexes_view(
    request: Request,
    collection_id: str,
    document_id: str,
    rebuild_request: view_models.RebuildIndexesRequest,
    user: User = Depends(default_user),
):
    """Rebuild specified indexes for a document"""
    return await document_service.rebuild_document_indexes(
        str(user.id), collection_id, document_id, rebuild_request.index_types
    )


@router.post("/collections/{collection_id}/rebuild_failed_indexes", tags=["documents"])
async def rebuild_failed_indexes_view(
    request: Request,
    collection_id: str,
    user: User = Depends(default_user),
):
    """Rebuild all failed indexes for all documents in a collection"""
    return await document_service.rebuild_failed_indexes(str(user.id), collection_id)

# New upload-related endpoints
@router.post("/collections/{collection_id}/documents/upload", tags=["documents"])
async def upload_document_view(
    request: Request,
    collection_id: str,
    file: UploadFile = File(...),
    user: User = Depends(default_user),
) -> view_models.UploadDocumentResponse:
    """Upload a single document file to temporary storage"""
    return await document_service.upload_document(str(user.id), collection_id, file)


@router.post("/collections/{collection_id}/documents/confirm", tags=["documents"])
async def confirm_documents_view(
    request: Request,
    collection_id: str,
    confirm_request: view_models.ConfirmDocumentsRequest,
    user: User = Depends(default_user),
) -> view_models.ConfirmDocumentsResponse:
    """Confirm uploaded documents and add them to the collection"""
    return await document_service.confirm_documents(str(user.id), collection_id, confirm_request.document_ids)

# Collection search endpoints
@router.post("/collections/{collection_id}/searches", tags=["search"])
async def create_search_view(
    request: Request,
    collection_id: str,
    data: view_models.SearchRequest,
    user: User = Depends(default_user),
) -> view_models.SearchResult:
    return await collection_service.create_search(str(user.id), collection_id, data)