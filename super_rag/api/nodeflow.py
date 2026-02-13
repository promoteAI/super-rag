"""Nodeflow 节点类型与注册表 API，供工作流画布发现可用节点。"""

from fastapi import APIRouter, Depends

from super_rag.api.user import default_user
from super_rag.db.models import User
from super_rag.nodeflow.registry import get_registered_node_types, get_registry_packages

router = APIRouter(tags=["nodeflow"])


@router.get("/nodeflow/node-types")
async def list_node_types(user: User = Depends(default_user)):
    """
    返回当前已注册的节点类型列表（内置 + 通过 entry point 安装的 node pack）。
    用于工作流编辑器的节点面板：展示 type、label、category、input_schema、output_schema。
    """
    return {"node_types": get_registered_node_types()}


@router.get("/nodeflow/packs")
async def list_registry_packs(user: User = Depends(default_user)):
    """
    返回注册表 index.json 中的可安装节点包列表。
    用于「节点管理」或设置页：展示可安装的 pack、描述、repo_id、安装说明等。
    """
    return {"packages": get_registry_packages()}
