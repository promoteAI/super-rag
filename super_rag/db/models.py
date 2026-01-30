import uuid,random
from enum import Enum
from sqlalchemy import (
    ARRAY,
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    select,
)
from fastapi_users.db import SQLAlchemyBaseOAuthAccountTable
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Mapped, mapped_column, relationship

from super_rag.utils.utils import utc_now
from super_rag.models import APIType

# Create the declarative base
Base = declarative_base()

def random_id():
    """Generate a random ID string"""
    return "".join(random.sample(uuid.uuid4().hex, 16))


# Helper function for creating enum columns that store values as varchar instead of database enum
def EnumColumn(enum_class, **kwargs):
    """Create a String column for enum values to avoid database enum constraints"""
    # Remove enum-specific kwargs that don't apply to String columns
    kwargs.pop("name", None)

    # Determine the maximum length needed for enum values
    max_length = max(len(e.value) for e in enum_class) if enum_class and len(enum_class) > 0 else 50
    # Add some buffer for future enum values
    max_length = max(max_length + 20, 50)

    # Set default length if not specified
    kwargs.setdefault("length", max_length)

    return String(**kwargs)

# Enums for choices
class CollectionStatus(str, Enum):
    INACTIVE = "INACTIVE"
    ACTIVE = "ACTIVE"
    DELETED = "DELETED"

class CollectionType(str, Enum):
    DOCUMENT = "document"
    CHAT = "CHAT"

class DocumentStatus(str, Enum):
    UPLOADED = "UPLOADED"  # 新增：已上传但未确认添加到collection
    EXPIRED = "EXPIRED"  # 新增：已过期的临时上传文档
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    DELETED = "DELETED"


class DocumentIndexStatus(str, Enum):
    """Document index lifecycle status"""

    PENDING = "PENDING"  # Awaiting processing (create/update)
    CREATING = "CREATING"  # Task claimed, creation/update in progress
    ACTIVE = "ACTIVE"  # Index is up-to-date and ready for use
    DELETING = "DELETING"  # Deletion has been requested
    DELETION_IN_PROGRESS = "DELETION_IN_PROGRESS"  # Task claimed, deletion in progress
    FAILED = "FAILED"  # The last operation failed

class DocumentIndexType(str, Enum):
    """Document index type enumeration"""

    VECTOR_AND_FULLTEXT= "VECTOR_AND_FULLTEXT"
    GRAPH = "GRAPH"
    SUMMARY = "SUMMARY"
    VISION = "VISION"

# Models
class Collection(Base):
    __tablename__ = "collection"

    id = Column(String(24), primary_key=True, default=lambda: "col" + random_id())
    title = Column(String(256), nullable=False)
    description = Column(Text, nullable=True)
    user = Column(String(256), nullable=False, index=True)  # Add index for frequent queries
    status = Column(EnumColumn(CollectionStatus), nullable=False, index=True)  # Add index for status queries
    type = Column(EnumColumn(CollectionType), nullable=False)
    config = Column(Text, nullable=False)
    gmt_created = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    gmt_updated = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    gmt_deleted = Column(DateTime(timezone=True), nullable=True, index=True)  # Add index for soft delete queries

class Role(str, Enum):
    ADMIN = "admin"
    RW = "rw"
    RO = "ro"

class OAuthAccount(SQLAlchemyBaseOAuthAccountTable[str], Base):
    __tablename__ = "oauth_account"

    id = Column(String(24), primary_key=True, default=lambda: "oauth" + random_id())
    user_id: Mapped[str] = mapped_column(String(24), ForeignKey("user.id", ondelete="cascade"), nullable=False)
    user: Mapped["User"] = relationship("User", back_populates="oauth_accounts")


class User(Base):
    __tablename__ = "user"

    id = Column(String(24), primary_key=True, default=lambda: "user" + random_id())
    username = Column(String(256), unique=True, nullable=True)  # Unified with other user fields
    email = Column(String(254), unique=True, nullable=True)
    role = Column(EnumColumn(Role), nullable=False, default=Role.RO)
    hashed_password = Column(String(128), nullable=False)  # fastapi-users expects hashed_password
    is_active = Column(Boolean, default=True, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)
    is_verified = Column(Boolean, default=True, nullable=False)  # fastapi-users requires is_verified
    is_staff = Column(Boolean, default=False, nullable=False)
    chat_collection_id = Column(String(24), nullable=True, index=True)  # Chat collection for user
    date_joined = Column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )  # Unified naming with other time fields
    gmt_created = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    gmt_updated = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    gmt_deleted = Column(DateTime(timezone=True), nullable=True)
    oauth_accounts: Mapped[list["OAuthAccount"]] = relationship("OAuthAccount", lazy="joined", back_populates="user")

    @property
    def password(self):
        raise AttributeError("password is not a readable attribute")

    @password.setter
    def password(self, value):
        self.hashed_password = value


class DocumentIndex(Base):
    """Document index - single status model"""

    __tablename__ = "document_index"
    __table_args__ = (UniqueConstraint("document_id", "index_type", name="uq_document_index"),)

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(String(24), nullable=False, index=True)
    index_type = Column(EnumColumn(DocumentIndexType), nullable=False, index=True)

    status = Column(EnumColumn(DocumentIndexStatus), nullable=False, default=DocumentIndexStatus.PENDING, index=True)
    version = Column(Integer, nullable=False, default=1)  # Incremented on each spec change
    observed_version = Column(Integer, nullable=False, default=0)  # Last processed spec version

    # Index data and task tracking
    index_data = Column(Text, nullable=True)  # JSON string for index-specific data
    error_message = Column(Text, nullable=True)

    # Timestamps
    gmt_created = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    gmt_updated = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    gmt_last_reconciled = Column(DateTime(timezone=True), nullable=True)  # Last reconciliation attempt

    def __repr__(self):
        return f"<DocumentIndex(id={self.id}, document_id={self.document_id}, type={self.index_type}, status={self.status}, version={self.version})>"

    def update_version(self):
        """Update the version to trigger reconciliation"""
        self.version += 1
        self.gmt_updated = utc_now()



class Document(Base):
    __tablename__ = "document"
    __table_args__ = (
        UniqueConstraint("collection_id", "name", "gmt_deleted", name="uq_document_collection_name_deleted"),
    )

    id = Column(String(24), primary_key=True, default=lambda: "doc" + random_id())
    name = Column(String(1024), nullable=False)
    user = Column(String(256), nullable=False, index=True)  # Add index for user queries
    collection_id = Column(String(24), nullable=True, index=True)  # Add index for collection queries
    status = Column(EnumColumn(DocumentStatus), nullable=False, index=True)  # Add index for status queries
    size = Column(BigInteger, nullable=False)  # Support larger files (up to 9 exabytes)
    content_hash = Column(
        String(64), nullable=True, index=True
    )  # SHA-256 hash of original file content for duplicate detection
    object_path = Column(Text, nullable=True)
    doc_metadata = Column(Text, nullable=True)  # Store document metadata as JSON string
    gmt_created = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    gmt_updated = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    gmt_deleted = Column(DateTime(timezone=True), nullable=True, index=True)  # Add index for soft delete queries

    def get_document_indexes(self, session):
        """Get document indexes from the merged table"""

        stmt = select(DocumentIndex).where(DocumentIndex.document_id == self.id)
        result = session.execute(stmt)
        return result.scalars().all()

    def get_overall_index_status(self, session) -> "DocumentStatus":
        """Calculate overall status based on document indexes"""
        document_indexes = self.get_document_indexes(session)

        if not document_indexes:
            return DocumentStatus.PENDING

        statuses = [idx.status for idx in document_indexes]

        if any(status == DocumentIndexStatus.FAILED for status in statuses):
            return DocumentStatus.FAILED
        elif any(
            status in [DocumentIndexStatus.CREATING, DocumentIndexStatus.DELETION_IN_PROGRESS] for status in statuses
        ):
            return DocumentStatus.RUNNING
        elif all(status == DocumentIndexStatus.ACTIVE for status in statuses):
            return DocumentStatus.COMPLETE
        else:
            return DocumentStatus.PENDING

    def object_store_base_path(self) -> str:
        """Generate the base path for object store"""
        user = self.user.replace("|", "-")
        return f"user-{user}/{self.collection_id}/{self.id}"

    # async def get_collection(self, session):
    #     """Get the associated collection object"""
    #     return await session.get(Collection, self.collection_id)

    async def set_collection(self, collection):
        """Set the collection_id by Collection object or id"""
        if hasattr(collection, "id"):
            self.collection_id = collection.id
        elif isinstance(collection, str):
            self.collection_id = collection

class LLMProvider(Base):
    """LLM Provider configuration model

    This model stores the provider-level configuration that was previously
    stored in model_configs.json file. Each provider has basic information
    and dialect configurations for different API types.
    """

    __tablename__ = "llm_provider"

    name = Column(String(128), primary_key=True)  # Unique provider name identifier
    user_id = Column(String(256), nullable=False, index=True)  # Owner of the provider config, "public" for global
    label = Column(String(256), nullable=False)  # Human-readable provider display name
    completion_dialect = Column(String(64), nullable=False)  # API dialect for completion/chat APIs
    embedding_dialect = Column(String(64), nullable=False)  # API dialect for embedding APIs
    rerank_dialect = Column(String(64), nullable=False)  # API dialect for rerank APIs
    allow_custom_base_url = Column(Boolean, default=False, nullable=False)  # Whether custom base URLs are allowed
    base_url = Column(String(512), nullable=False)  # Default API base URL for this provider
    extra = Column(Text, nullable=True)  # Additional configuration data in JSON format
    gmt_created = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    gmt_updated = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    gmt_deleted = Column(DateTime(timezone=True), nullable=True)

    def __str__(self):
        return f"LLMProvider(name={self.name}, label={self.label}, user_id={self.user_id})"


class LLMProviderModel(Base):
    """LLM Provider Model configuration

    This model stores individual model configurations for each provider.
    Each model belongs to a provider and has a specific API type (completion, embedding, rerank).
    """

    __tablename__ = "llm_provider_models"

    provider_name = Column(String(128), primary_key=True)  # Reference to LLMProvider.name
    api = Column(EnumColumn(APIType), nullable=False, primary_key=True)
    model = Column(String(256), primary_key=True)  # Model name/identifier
    custom_llm_provider = Column(String(128), nullable=False)  # Custom LLM provider implementation
    context_window = Column(Integer, nullable=True)  # Context window size (total tokens)
    max_input_tokens = Column(Integer, nullable=True)  # Maximum input tokens
    max_output_tokens = Column(Integer, nullable=True)  # Maximum output tokens
    tags = Column(JSON, default=lambda: [], nullable=True)  # Tags for model categorization
    gmt_created = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    gmt_updated = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    gmt_deleted = Column(DateTime(timezone=True), nullable=True)

    def __str__(self):
        return f"LLMProviderModel(provider={self.provider_name}, api={self.api}, model={self.model})"

    async def get_provider(self, session):
        """Get the associated provider object"""
        return await session.get(LLMProvider, self.provider_name)

    async def set_provider(self, provider):
        """Set the provider_name by LLMProvider object or name"""
        if hasattr(provider, "name"):
            self.provider_name = provider.name
        elif isinstance(provider, str):
            self.provider_name = provider

    def has_tag(self, tag: str) -> bool:
        """Check if model has a specific tag"""
        return tag in (self.tags or [])

    def add_tag(self, tag: str) -> bool:
        """Add a tag to model. Returns True if tag was added, False if already exists"""
        if self.tags is None:
            self.tags = []
        if tag not in self.tags:
            self.tags.append(tag)
            return True
        return False

    def remove_tag(self, tag: str) -> bool:
        """Remove a tag from model. Returns True if tag was removed, False if not found"""
        if self.tags and tag in self.tags:
            self.tags.remove(tag)
            return True
        return False

    def get_tags(self) -> list:
        """Get all tags for this model"""
        return self.tags or []

class ModelServiceProviderStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    DELETED = "DELETED"

class ModelServiceProvider(Base):
    __tablename__ = "model_service_provider"
    __table_args__ = (UniqueConstraint("name", "gmt_deleted", name="uq_model_service_provider_name_deleted"),)

    id = Column(String(24), primary_key=True, default=lambda: "msp" + random_id())
    name = Column(String(256), nullable=False, index=True)  # Reference to LLMProvider.name
    status = Column(EnumColumn(ModelServiceProviderStatus), nullable=False, index=True)  # Add index for status queries
    api_key = Column(String(256), nullable=False)
    gmt_created = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    gmt_updated = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    gmt_deleted = Column(DateTime(timezone=True), nullable=True)

class ChatMessageTable(Base):
    """Chat history table definition for storing messages"""

    __tablename__ = "chat_message"

    id = Column(String(24), primary_key=True, default=lambda: "msg" + random_id())
    chat_id = Column(String(64), index=True, nullable=False)
    message_id = Column(String(128), nullable=True, index=True)
    role = Column(String(32), nullable=True)  # e.g., "human", "ai"
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    raw_message = Column(Text, nullable=False)  # Store JSON string of message model here
    gmt_created = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    gmt_updated = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    gmt_deleted = Column(DateTime(timezone=True), nullable=True)
    
    def to_dict(self):
        return {
            "id": self.id,
            "chat_id": self.chat_id,
            "message_id": self.message_id,
            "role": self.role,
            "created_at": self.created_at,
            "raw_message": self.raw_message,
            "gmt_deleted": self.gmt_deleted,
        }

class BotStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DELETED = "DELETED"


class BotType(str, Enum):
    KNOWLEDGE = "knowledge"
    COMMON = "common"
    AGENT = "agent"

class Bot(Base):
    __tablename__ = "bot"

    id = Column(String(24), primary_key=True, default=lambda: "bot" + random_id())
    user = Column(String(256), nullable=False, index=True)  # Add index for user queries
    title = Column(String(256), nullable=True)
    type = Column(EnumColumn(BotType), nullable=False, default=BotType.KNOWLEDGE)
    description = Column(Text, nullable=True)
    status = Column(EnumColumn(BotStatus), nullable=False, index=True)  # Add index for status queries
    config = Column(Text, nullable=False)
    gmt_created = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    gmt_updated = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    gmt_deleted = Column(DateTime(timezone=True), nullable=True, index=True)  # Add index for soft delete queries


class WorkflowStatus(str, Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"
    DELETED = "DELETED"


class WorkflowTable(Base):
    __tablename__ = "workflow"

    id = Column(String(24), primary_key=True, default=lambda: "wf" + random_id())
    user = Column(String(256), nullable=False, index=True)
    name = Column(String(256), nullable=False)
    title = Column(String(256), nullable=True)
    description = Column(Text, nullable=True)
    tags = Column(JSON, nullable=True, default=list)
    status = Column(EnumColumn(WorkflowStatus), nullable=False, default=WorkflowStatus.DRAFT, index=True)
    graph = Column(JSON, nullable=False, default=dict)
    input_schema = Column(JSON, nullable=True)
    output_schema = Column(JSON, nullable=True)
    gmt_created = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    gmt_updated = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    gmt_deleted = Column(DateTime(timezone=True), nullable=True, index=True)


class WorkflowVersionTable(Base):
    __tablename__ = "workflow_version"
    __table_args__ = (UniqueConstraint("workflow_id", "version", name="uq_workflow_version"),)

    id = Column(String(24), primary_key=True, default=lambda: "wfv" + random_id())
    workflow_id = Column(String(24), ForeignKey("workflow.id"), nullable=False, index=True)
    user = Column(String(256), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    name = Column(String(256), nullable=True)
    title = Column(String(256), nullable=True)
    description = Column(Text, nullable=True)
    graph = Column(JSON, nullable=False, default=dict)
    input_schema = Column(JSON, nullable=True)
    output_schema = Column(JSON, nullable=True)
    save_type = Column(String(64), nullable=False, default="manual")
    autosave_metadata = Column(JSON, nullable=True, default=dict)
    gmt_created = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    gmt_updated = Column(DateTime(timezone=True), default=utc_now, nullable=False)


class WorkflowRunStatus(str, Enum):
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class NodeRunStatus(str, Enum):
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class WorkflowRunTable(Base):
    __tablename__ = "workflow_run"

    id = Column(String(24), primary_key=True, default=lambda: "wfr" + random_id())
    workflow_id = Column(String(24), ForeignKey("workflow.id"), nullable=True, index=True)
    workflow_version = Column(Integer, nullable=True)
    user = Column(String(256), nullable=False, index=True)
    execution_id = Column(String(64), nullable=True, index=True)
    status = Column(EnumColumn(WorkflowRunStatus), nullable=False, default=WorkflowRunStatus.RUNNING, index=True)
    input = Column(JSON, nullable=True)
    output = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    gmt_created = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    gmt_updated = Column(DateTime(timezone=True), default=utc_now, nullable=False)


class NodeRunTable(Base):
    __tablename__ = "node_run"

    id = Column(String(24), primary_key=True, default=lambda: "nr" + random_id())
    run_id = Column(String(24), ForeignKey("workflow_run.id"), nullable=False, index=True)
    node_id = Column(String(128), nullable=False, index=True)
    node_type = Column(String(128), nullable=True)
    status = Column(EnumColumn(NodeRunStatus), nullable=False, default=NodeRunStatus.RUNNING, index=True)
    input_snapshot = Column(JSON, nullable=True)
    output_snapshot = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    started_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    gmt_created = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    gmt_updated = Column(DateTime(timezone=True), default=utc_now, nullable=False)


class ChatStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DELETED = "DELETED"


class ChatPeerType(str, Enum):
    SYSTEM = "system"
    FEISHU = "feishu"
    WEIXIN = "weixin"
    WEIXIN_OFFICIAL = "weixin_official"
    WEB = "web"
    DINGTALK = "dingtalk"

class Chat(Base):
    __tablename__ = "chat"
    __table_args__ = (
        UniqueConstraint("bot_id", "peer_type", "peer_id", "gmt_deleted", name="uq_chat_bot_peer_deleted"),
    )

    id = Column(String(24), primary_key=True, default=lambda: "chat" + random_id())
    user = Column(String(256), nullable=False, index=True)  # Add index for user queries
    peer_type = Column(EnumColumn(ChatPeerType), nullable=False, default=ChatPeerType.SYSTEM)
    peer_id = Column(String(256), nullable=True)
    status = Column(EnumColumn(ChatStatus), nullable=False, index=True)  # Add index for status queries
    bot_id = Column(String(24), nullable=False, index=True)  # Add index for bot queries
    title = Column(String(256), nullable=True)
    gmt_created = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    gmt_updated = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    gmt_deleted = Column(DateTime(timezone=True), nullable=True, index=True)  # Add index for soft delete queries

    async def get_bot(self, session):
        """Get the associated bot object"""
        return await session.get(Bot, self.bot_id)

    async def set_bot(self, bot):
        """Set the bot_id by Bot object or id"""
        if hasattr(bot, "id"):
            self.bot_id = bot.id
        elif isinstance(bot, str):
            self.bot_id = bot

class MessageFeedbackStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class MessageFeedbackType(str, Enum):
    GOOD = "good"
    BAD = "bad"


class MessageFeedbackTag(str, Enum):
    HARMFUL = "Harmful"
    UNSAFE = "Unsafe"
    FAKE = "Fake"
    UNHELPFUL = "Unhelpful"
    OTHER = "Other"

class MessageFeedback(Base):
    __tablename__ = "message_feedback"
    __table_args__ = (
        UniqueConstraint("chat_id", "message_id", "gmt_deleted", name="uq_feedback_chat_message_deleted"),
    )

    user = Column(String(256), nullable=False, index=True)  # Add index for user queries
    chat_id = Column(String(24), primary_key=True)
    message_id = Column(String(256), primary_key=True)
    type = Column(EnumColumn(MessageFeedbackType), nullable=True)
    tag = Column(EnumColumn(MessageFeedbackTag), nullable=True)
    message = Column(Text, nullable=True)
    question = Column(Text, nullable=True)
    status = Column(EnumColumn(MessageFeedbackStatus), nullable=True, index=True)  # Add index for status queries
    original_answer = Column(Text, nullable=True)
    revised_answer = Column(Text, nullable=True)
    gmt_created = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    gmt_updated = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    gmt_deleted = Column(DateTime(timezone=True), nullable=True, index=True)  # Add index for soft delete queries

    async def get_chat(self, session):
        """Get the associated chat object"""
        return await session.get(Chat, self.chat_id)

    async def set_chat(self, chat):
        """Set the chat_id by Chat object or id"""
        if hasattr(chat, "id"):
            self.chat_id = chat.id
        elif isinstance(chat, str):
            self.chat_id = chat

class AuditResource(str, Enum):
    """Audit resource types"""

    COLLECTION = "collection"
    DOCUMENT = "document"
    BOT = "bot"
    CHAT = "chat"
    MESSAGE = "message"
    LLM_PROVIDER = "llm_provider"
    LLM_PROVIDER_MODEL = "llm_provider_model"
    MODEL_SERVICE_PROVIDER = "model_service_provider"
    USER = "user"
    CONFIG = "config"
    AUTH = "auth"
    CHAT_COMPLETION = "chat_completion"
    SEARCH = "search"
    LLM = "llm"
    FLOW = "flow"
    SYSTEM = "system"
    INDEX = "index"


class AuditLog(Base):
    """Audit log model to track all system operations"""

    __tablename__ = "audit_log"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=True, comment="User ID")
    username = Column(String(255), nullable=True, comment="Username")
    resource_type = Column(EnumColumn(AuditResource), nullable=True, comment="Resource type")
    resource_id = Column(String(255), nullable=True, comment="Resource ID (extracted at query time)")
    api_name = Column(String(255), nullable=False, comment="API operation name")
    http_method = Column(String(10), nullable=False, comment="HTTP method (POST, PUT, DELETE)")
    path = Column(String(512), nullable=False, comment="API path")
    status_code = Column(Integer, nullable=True, comment="HTTP status code")
    request_data = Column(Text, nullable=True, comment="Request data (JSON)")
    response_data = Column(Text, nullable=True, comment="Response data (JSON)")
    error_message = Column(Text, nullable=True, comment="Error message if failed")
    ip_address = Column(String(45), nullable=True, comment="Client IP address")
    user_agent = Column(String(500), nullable=True, comment="User agent string")
    request_id = Column(String(255), nullable=False, comment="Request ID for tracking")
    start_time = Column(BigInteger, nullable=False, comment="Request start time (milliseconds since epoch)")
    end_time = Column(BigInteger, nullable=True, comment="Request end time (milliseconds since epoch)")
    gmt_created = Column(DateTime(timezone=True), nullable=False, default=utc_now, comment="Created time")

    # Index for better query performance
    __table_args__ = (
        Index("idx_audit_user_id", "user_id"),
        Index("idx_audit_resource_type", "resource_type"),
        Index("idx_audit_api_name", "api_name"),
        Index("idx_audit_http_method", "http_method"),
        Index("idx_audit_status_code", "status_code"),
        Index("idx_audit_gmt_created", "gmt_created"),
        Index("idx_audit_resource_id", "resource_id"),
        Index("idx_audit_request_id", "request_id"),
        Index("idx_audit_start_time", "start_time"),
    )

    def __repr__(self):
        return f"<AuditLog(id={self.id}, user={self.username}, api={self.api_name}, method={self.http_method}, status={self.status_code})>"
