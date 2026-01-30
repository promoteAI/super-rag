import logging

from fastapi import APIRouter, Depends, Request, Response

from super_rag.api.user import default_user
from super_rag.db.models import User
from super_rag.schema import view_models
from super_rag.service.workflow_service import workflow_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["workflows"])


@router.post("/workflows", response_model=view_models.WorkflowRecord)
async def create_workflow_view(
    request: Request,
    body: view_models.WorkflowCreate,
    user: User = Depends(default_user),
) -> view_models.WorkflowRecord:
    return await workflow_service.create_workflow(str(user.id), body)


@router.get("/workflows", response_model=view_models.WorkflowList)
async def list_workflows_view(
    request: Request,
    user: User = Depends(default_user),
    limit: int = 100,
    offset: int = 0,
) -> view_models.WorkflowList:
    return await workflow_service.list_workflows(str(user.id), limit=limit, offset=offset)


@router.get("/workflows/{workflow_id}", response_model=view_models.WorkflowRecord)
async def get_workflow_view(
    request: Request,
    workflow_id: str,
    user: User = Depends(default_user),
) -> view_models.WorkflowRecord:
    return await workflow_service.get_workflow(str(user.id), workflow_id)


@router.put("/workflows/{workflow_id}", response_model=view_models.WorkflowRecord)
async def update_workflow_view(
    request: Request,
    workflow_id: str,
    body: view_models.WorkflowUpdate,
    user: User = Depends(default_user),
) -> view_models.WorkflowRecord:
    return await workflow_service.update_workflow(str(user.id), workflow_id, body)


@router.delete("/workflows/{workflow_id}")
async def delete_workflow_view(
    request: Request,
    workflow_id: str,
    user: User = Depends(default_user),
):
    await workflow_service.delete_workflow(str(user.id), workflow_id)
    return Response(status_code=204)


@router.post("/workflows/{workflow_id}/versions", response_model=view_models.WorkflowVersionRecord)
async def create_workflow_version_view(
    request: Request,
    workflow_id: str,
    body: view_models.WorkflowVersionCreate,
    user: User = Depends(default_user),
) -> view_models.WorkflowVersionRecord:
    return await workflow_service.create_workflow_version(str(user.id), workflow_id, body)


@router.get("/workflows/{workflow_id}/versions", response_model=view_models.WorkflowVersionList)
async def list_workflow_versions_view(
    request: Request,
    workflow_id: str,
    user: User = Depends(default_user),
    limit: int = 100,
    offset: int = 0,
) -> view_models.WorkflowVersionList:
    return await workflow_service.list_workflow_versions(str(user.id), workflow_id, limit=limit, offset=offset)


@router.get("/workflows/{workflow_id}/versions/{version}", response_model=view_models.WorkflowVersionRecord)
async def get_workflow_version_view(
    request: Request,
    workflow_id: str,
    version: int,
    user: User = Depends(default_user),
) -> view_models.WorkflowVersionRecord:
    return await workflow_service.get_workflow_version(str(user.id), workflow_id, version)
