import json
import os
from functools import wraps
from pathlib import Path
from typing import Annotated, Any, AsyncGenerator, Dict, Generator, Optional

from dotenv import load_dotenv
from fastapi import Depends
from pydantic import Field
from pydantic_settings import BaseSettings
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from super_rag.vectorstore.connector import VectorStoreConnectorAdaptor

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(os.path.join(BASE_DIR, ".env"))


class S3Config(BaseSettings):
    endpoint: str = Field("http://127.0.0.1:9000", alias="OBJECT_STORE_S3_ENDPOINT")
    access_key: str = Field("minioadmin", alias="OBJECT_STORE_S3_ACCESS_KEY")
    secret_key: str = Field("minioadmin", alias="OBJECT_STORE_S3_SECRET_KEY")
    bucket: str = Field("super_rag", alias="OBJECT_STORE_S3_BUCKET")
    region: Optional[str] = Field(None, alias="OBJECT_STORE_S3_REGION")
    prefix_path: Optional[str] = Field(None, alias="OBJECT_STORE_S3_PREFIX_PATH")
    use_path_style: bool = Field(True, alias="OBJECT_STORE_S3_USE_PATH_STYLE")


class LocalObjectStoreConfig(BaseSettings):
    root_dir: str = Field(".objects", alias="OBJECT_STORE_LOCAL_ROOT_DIR")


class Config(BaseSettings):
    # Debug mode
    debug: bool = Field(False, alias="DEBUG")

    # Postgres atomic fields
    mysql_host: str = Field("127.0.0.1", alias="MYSQL_HOST")
    mysql_port: int = Field(2881, alias="MYSQL_PORT")
    mysql_db: str = Field("super_rag", alias="MYSQL_DB")
    mysql_user: str = Field("root", alias="MYSQL_USER")
    mysql_password: str = Field("123456", alias="MYSQL_PASSWORD")

    # Database
    database_url: Optional[str] = Field("", alias="DATABASE_URL")

    # Database connection pool settings
    db_pool_size: int = Field(20, alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(40, alias="DB_MAX_OVERFLOW")
    db_pool_timeout: int = Field(60, alias="DB_POOL_TIMEOUT")
    db_pool_recycle: int = Field(3600, alias="DB_POOL_RECYCLE")
    db_pool_pre_ping: bool = Field(True, alias="DB_POOL_PRE_PING")

    # Model configs
    model_configs: Dict[str, Any] = {}

    # Embedding
    embedding_max_chunks_in_batch: int = Field(10, alias="EMBEDDING_MAX_CHUNKS_IN_BATCH")

    # Vector DB
    vector_db_type: str = Field("seekdb", alias="VECTOR_DB_TYPE")
    vector_db_context: str = Field(
        '{"host":"localhost", "port":2881, "distance":"cosine", "user":"root", "password":"123456", "database":"test"}', alias="VECTOR_DB_CONTEXT"
    )

    # Object store
    object_store_type: str = Field("local", alias="OBJECT_STORE_TYPE")
    object_store_local_config: Optional[LocalObjectStoreConfig] = None
    object_store_s3_config: Optional[S3Config] = None

    # Limits
    max_bot_count: int = Field(10, alias="MAX_BOT_COUNT")
    max_collection_count: int = Field(50, alias="MAX_COLLECTION_COUNT")
    max_document_count: int = Field(1000, alias="MAX_DOCUMENT_COUNT")
    max_document_size: int = Field(100 * 1024 * 1024, alias="MAX_DOCUMENT_SIZE")
    max_conversation_count: int = Field(100, alias="MAX_CONVERSATION_COUNT")

    # Chunking
    chunk_size: int = Field(400, alias="CHUNK_SIZE")
    chunk_overlap_size: int = Field(20, alias="CHUNK_OVERLAP_SIZE")

    # OCR/ASR
    whisper_host: str = Field("", alias="WHISPER_HOST")
    paddleocr_host: str = Field("", alias="PADDLEOCR_HOST")
    docray_host: str = Field("", alias="DOCRAY_HOST")

    # Register mode
    register_mode: str = Field("unlimited", alias="REGISTER_MODE")

    # Cache
    cache_enabled: bool = Field(True, alias="CACHE_ENABLED")
    cache_ttl: int = Field(86400, alias="CACHE_TTL")

    # JWT
    jwt_secret: str = Field("your-super-secret-key-change-in-production", alias="JWT_SECRET")
    jwt_lifetime_seconds: int = Field(86400, alias="JWT_LIFETIME_SECONDS")  # 24 hours

    # Super Rag
    super_rag_api_key: str = Field("1234567890", alias="SUPER_RAG_API_KEY")
    super_rag_mcp_url: str = Field("http://localhost:8000/mcp/", alias="SUPER_RAG_MCP_URL")


    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Load model configs from file
        import json
        import os

        json_path = os.path.join(BASE_DIR, "model_configs.json")
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                self.model_configs = json.load(f)

        # DATABASE_URL - Use correct async driver by default!
        if not self.database_url:
            # Use an async driver for async SQLAlchemy!
            self.database_url = (
                f"mysql+aiomysql://{self.mysql_user}:{self.mysql_password}"
                f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_db}"
            )

        # Object store config
        if self.object_store_type == "local":
            self.object_store_local_config = LocalObjectStoreConfig()
        elif self.object_store_type == "s3":
            self.object_store_s3_config = S3Config()
        else:
            raise ValueError(
                f"Unsupported OBJECT_STORE_TYPE: {self.object_store_type}. Supported types are: local, s3."
            )


def get_sync_database_url(url: str):
    """Convert async database URL to sync version for celery"""
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql://")
    if url.startswith("postgres+asyncpg://"):
        return url.replace("postgres+asyncpg://", "postgres://")
    if url.startswith("sqlite+aiosqlite://"):
        return url.replace("sqlite+aiosqlite://", "sqlite://")
    if url.startswith("mysql+aiomysql://"):
        return url.replace("mysql+aiomysql://", "mysql+pymysql://")
    return url


def get_async_database_url(url: str):
    """Convert sync database URL to async version"""
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://")
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://")
    if url.startswith("sqlite://"):
        return url.replace("sqlite://", "sqlite+aiosqlite://")
    if url.startswith("mysql+pymysql://"):
        return url.replace("mysql+pymysql://", "mysql+aiomysql://")
    return url


def new_async_engine():
    return create_async_engine(
        get_async_database_url(settings.database_url),
        echo=settings.debug,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout,
        pool_recycle=settings.db_pool_recycle,
        pool_pre_ping=settings.db_pool_pre_ping,
    )


def new_sync_engine():
    return create_engine(
        get_sync_database_url(settings.database_url),
        echo=settings.debug,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout,
        pool_recycle=settings.db_pool_recycle,
        pool_pre_ping=settings.db_pool_pre_ping,
    )


settings = Config()

# Database connection pool settings from configuration
async_engine = new_async_engine()
sync_engine = new_sync_engine()


async def get_async_session(engine=None) -> AsyncGenerator[AsyncSession, None]:
    if engine is None:
        engine = async_engine
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session


def get_sync_session(engine=None) -> Generator[Session, None, None]:
    if engine is None:
        engine = sync_engine
    sync_session = sessionmaker(engine)
    with sync_session() as session:
        yield session


def with_sync_session(func):
    """Decorator to inject sync session into sync functions"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        for session in get_sync_session():
            return func(session, *args, **kwargs)

    return wrapper


def with_async_session(func):
    """Decorator to inject async session into async functions"""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        async for session in get_async_session():
            return await func(session, *args, **kwargs)

    return wrapper


AsyncSessionDep = Annotated[AsyncSession, Depends(get_async_session)]
SyncSessionDep = Annotated[Session, Depends(get_sync_session)]


def get_vector_db_connector(collection: str) -> VectorStoreConnectorAdaptor:
    # todo: specify the collection for different user
    # one person one collection
    ctx = json.loads(settings.vector_db_context)
    ctx["collection"] = collection
    return VectorStoreConnectorAdaptor(settings.vector_db_type, ctx=ctx)

if __name__ == "__main__":
    print(settings)