import os
from super_rag.config import settings
from fastapi import FastAPI 
from super_rag.api.collections import router as collections_router
from super_rag.api.llm import router as llm_router
from super_rag.api.agent import router as agent_router
from super_rag.api.chat import router as chat_router
from super_rag.api.workflow import router as workflow_router
from super_rag.api.web import router as web_router
from super_rag.api.auth import router as auth_router
from super_rag.api.marketplace import router as marketplace_router

# Create the main FastAPI app with combined lifespan
app = FastAPI(
    title="super_rag API",
    description="Knowledge management and retrieval system",
    version="1.0.0"  # Combined lifecycle management
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
# Only include test router in dev mode
if os.environ.get("DEPLOYMENT_MODE") == "dev":
    pass
