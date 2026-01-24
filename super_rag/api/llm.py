
import logging
from typing import Optional

from fastapi import APIRouter, Body, Depends, Path, Request

from super_rag.db.models import User
from super_rag.schema import view_models
from super_rag.service.default_model_service import default_model_service
from super_rag.service.llm_available_model_service import llm_available_model_service
from super_rag.service.llm_provider_service import (
    create_llm_provider,
    create_llm_provider_model,
    delete_llm_provider,
    delete_llm_provider_model,
    get_llm_configuration,
    get_llm_provider,
    list_llm_provider_models,
    update_llm_provider,
    update_llm_provider_model,
)
from super_rag.api.user import default_user


logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/available_models", tags=["llm_models"])
async def get_available_models_view(
    request: Request,
    tag_filter_request: Optional[view_models.TagFilterRequest] = Body(None),
    user: User = Depends(default_user),
) -> view_models.ModelConfigList:
    """Get available models with optional tag filtering"""
    # If no request body provided, create default request
    if tag_filter_request is None:
        tag_filter_request = view_models.TagFilterRequest()

    return await llm_available_model_service.get_available_models(str(user.id), tag_filter_request)


@router.get("/default_models", tags=["default_models"])
async def get_default_models_view(
    request: Request, user: User = Depends(default_user)
) -> view_models.DefaultModelsResponse:
    """Get default model configurations for different scenarios"""
    return await default_model_service.get_default_models(str(user.id))


@router.put("/default_models", tags=["default_models"])
async def update_default_models_view(
    request: Request, update_request: view_models.DefaultModelsUpdateRequest, user: User = Depends(default_user)
) -> view_models.DefaultModelsResponse:
    """Update default model configurations for different scenarios"""
    return await default_model_service.update_default_models(str(user.id), update_request)


# LLM Configuration API endpoints
@router.get("/llm_configuration", tags=["llm_providers"])
async def get_llm_configuration_view(request: Request, user: User = Depends(default_user)):
    """Get complete LLM configuration including providers and models"""
    from super_rag.db.models import Role

    is_admin = user.role == Role.ADMIN
    return await get_llm_configuration(str(user.id), is_admin)


@router.post("/llm_providers", tags=["llm_providers"])
async def create_llm_provider_view(
    request: Request,
    provider_data: view_models.LlmProviderCreateWithApiKey,
    user: User = Depends(default_user),
):
    """Create a new LLM provider with optional API key"""
    from super_rag.db.models import Role

    is_admin = user.role == Role.ADMIN
    return await create_llm_provider(provider_data.model_dump(), str(user.id), is_admin)


@router.get("/llm_providers/{provider_name}", tags=["llm_providers"])
async def get_llm_provider_view(request: Request, provider_name: str, user: User = Depends(default_user)):
    """Get a specific LLM provider"""
    from super_rag.db.models import Role

    is_admin = user.role == Role.ADMIN
    return await get_llm_provider(provider_name, str(user.id), is_admin)


@router.put("/llm_providers/{provider_name}", tags=["llm_providers"])
async def update_llm_provider_view(
    request: Request,
    provider_name: str,
    provider_data: view_models.LlmProviderUpdateWithApiKey,
    user: User = Depends(default_user),
):
    """Update an existing LLM provider with optional API key"""
    from super_rag.db.models import Role

    is_admin = user.role == Role.ADMIN
    return await update_llm_provider(provider_name, provider_data.model_dump(), str(user.id), is_admin)


@router.delete("/llm_providers/{provider_name}", tags=["llm_providers"])
async def delete_llm_provider_view(request: Request, provider_name: str, user: User = Depends(default_user)):
    """Delete an LLM provider"""
    from super_rag.db.models import Role

    is_admin = user.role == Role.ADMIN
    return await delete_llm_provider(provider_name, str(user.id), is_admin)


@router.get("/llm_provider_models", tags=["llm_models"])
async def list_llm_provider_models_view(
    request: Request, provider_name: str = None, user: User = Depends(default_user)
):
    """List LLM provider models, optionally filtered by provider"""
    from super_rag.db.models import Role

    is_admin = user.role == Role.ADMIN
    return await list_llm_provider_models(provider_name, str(user.id), is_admin)


@router.get("/llm_providers/{provider_name}/models", tags=["llm_models"])
async def get_provider_models_view(request: Request, provider_name: str, user: User = Depends(default_user)):
    """Get all models for a specific provider"""
    from super_rag.db.models import Role

    is_admin = user.role == Role.ADMIN
    return await list_llm_provider_models(provider_name=provider_name, user_id=str(user.id), is_admin=is_admin)


@router.post("/llm_providers/{provider_name}/models", tags=["llm_models"])
async def create_provider_model_view(request: Request, provider_name: str, user: User = Depends(default_user)):
    """Create a new model for a specific provider"""
    import json

    from super_rag.db.models import Role

    body = await request.body()
    data = json.loads(body.decode("utf-8"))
    is_admin = user.role == Role.ADMIN
    return await create_llm_provider_model(provider_name, data, str(user.id), is_admin)


@router.put("/llm_providers/{provider_name}/models/{api}/{model:path}", tags=["llm_models"])
async def update_provider_model_view(
    request: Request,
    provider_name: str,
    api: str,
    model: str = Path(..., description="Model name (supports names with slashes)"),
    user: User = Depends(default_user),
):
    """Update a specific model"""
    import json

    from super_rag.db.models import Role

    body = await request.body()
    data = json.loads(body.decode("utf-8"))
    is_admin = user.role == Role.ADMIN
    return await update_llm_provider_model(provider_name, api, model, data, str(user.id), is_admin)


@router.delete("/llm_providers/{provider_name}/models/{api}/{model:path}", tags=["llm_models"])
async def delete_provider_model_view(
    request: Request,
    provider_name: str,
    api: str,
    model: str = Path(..., description="Model name (supports names with slashes)"),
    user: User = Depends(default_user),
):
    """Delete a specific model"""
    from super_rag.db.models import Role

    is_admin = user.role == Role.ADMIN
    return await delete_llm_provider_model(provider_name, api, model, str(user.id), is_admin)
