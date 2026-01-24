

"""
super_rag Tracing Module

Simplified OpenTelemetry integration for super_rag with support for:
- Basic tracing with console output
- Jaeger integration (future)
- FastAPI and SQLAlchemy instrumentation
- MCP Agent trace injection
"""

from typing import Optional

from .instrumentation import init_fastapi_instrumentation, init_sqlalchemy_instrumentation
from .mcp_integration import init_mcp_tracing
from .telemetry import init_telemetry, is_telemetry_available
from .utils import add_trace_attributes, get_current_trace_info, get_tracer, trace_async_function, trace_function

__all__ = [
    "init_tracing",
    "init_telemetry",
    "init_fastapi_instrumentation",
    "init_sqlalchemy_instrumentation",
    "init_mcp_tracing",
    "get_tracer",
    "get_current_trace_info",
    "trace_function",
    "trace_async_function",
    "add_trace_attributes",
    "is_telemetry_available",
]


def init_tracing(
    service_name: str = "super_rag",
    service_version: str = "1.0.0",
    jaeger_endpoint: Optional[str] = None,
    enable_console: bool = True,
    enable_fastapi: bool = True,
    enable_sqlalchemy: bool = True,
    enable_mcp: bool = True,
) -> bool:
    """
    Initialize complete tracing for super_rag.

    This is the main entry point that sets up all tracing components.

    Args:
        service_name: Name of the service
        service_version: Version of the service
        jaeger_endpoint: Jaeger collector endpoint (None for console-only mode)
        enable_console: Whether to enable console output
        enable_fastapi: Whether to instrument FastAPI
        enable_sqlalchemy: Whether to instrument SQLAlchemy
        enable_mcp: Whether to enable MCP agent trace injection

    Returns:
        True if tracing was successfully initialized, False otherwise
    """
    # Initialize core telemetry
    if not init_telemetry(
        service_name=service_name,
        service_version=service_version,
        jaeger_endpoint=jaeger_endpoint,
        enable_console=enable_console,
    ):
        return False

    # Initialize instrumentations
    if enable_fastapi:
        init_fastapi_instrumentation()

    if enable_sqlalchemy:
        init_sqlalchemy_instrumentation()

    if enable_mcp:
        init_mcp_tracing()

    return True
