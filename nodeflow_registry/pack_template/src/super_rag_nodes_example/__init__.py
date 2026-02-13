def register() -> None:
    """Entry point：导入 nodes 子模块即完成所有节点的注册。"""
    from . import nodes  # noqa: F401
