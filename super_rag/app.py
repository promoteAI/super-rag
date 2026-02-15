import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from super_rag.agent.agent_event_listener import agent_event_listener
from super_rag.agent.agent_session_manager_lifecycle import agent_session_manager_lifespan
from super_rag.api.agent import router as agent_router
from super_rag.api.auth import router as auth_router
from super_rag.api.chat import router as chat_router
from super_rag.api.collections import router as collections_router
from super_rag.api.llm import router as llm_router
from super_rag.api.marketplace import router as marketplace_router
from super_rag.api.nodeflow import router as nodeflow_router
from super_rag.api.web import router as web_router
from super_rag.api.workflow import router as workflow_router
from super_rag.nodeflow.registry import load_nodeflow_packs
from super_rag.mcp.server import mcp_server

# Initialize MCP server integration with stateless HTTP to fix OpenAI tool call sequence issues
mcp_app = mcp_server.http_app(path="/", stateless_http=True)

# Combined lifespan function for both MCP and Agent session management
@asynccontextmanager
async def combined_lifespan(app: FastAPI):
    """Combined lifespan manager for MCP and Agent sessions."""
    # Load Nodeflow external node packs for extended workflow functionality
    load_nodeflow_packs()
    # Initialize the global proxy listener at startup
    await agent_event_listener.initialize()

    # Start MCP sub-app lifespan (required for StreamableHTTP session manager when mounted)
    async with mcp_app.router.lifespan_context(mcp_app):
        # Then start Agent session manager
        async with agent_session_manager_lifespan(app):
            yield

# Explicit name so "lifespan=lifespan" or "lifespan=combined_lifespan" both work
lifespan = combined_lifespan

app = FastAPI(
    title="super_rag API",
    description="Knowledge management and retrieval system",
    version="1.0.0",
    lifespan=lifespan,
)


# Health check endpoint
@app.get("/health")
async def health_check():
    """Simple health check endpoint for container health monitoring"""
    return {"status": "healthy", "service": "super_rag-api"}

app.include_router(auth_router, prefix="/api/v1")
app.include_router(collections_router, prefix="/api/v1")  # Add collections router
app.include_router(llm_router, prefix="/api/v1")  # Add llm router
app.include_router(agent_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")
app.include_router(workflow_router, prefix="/api/v1")
app.include_router(web_router, prefix="/api/v1")
app.include_router(marketplace_router, prefix="/api/v1")
app.include_router(nodeflow_router, prefix="/api/v1")

# Only include test router in dev mode
if os.environ.get("DEPLOYMENT_MODE") == "dev":
    pass

# Mount the MCP server at /mcp path
app.mount("/mcp", mcp_app)