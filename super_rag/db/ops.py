import logging
from re import A
from super_rag.db.repositories.base import AsyncBaseRepository, SyncBaseRepository
from super_rag.db.repositories.collection import (
    AsyncCollectionRepositoryMixin,
    CollectionRepositoryMixin,
)
from super_rag.db.repositories.document import (
    AsyncDocumentRepositoryMixin,
    DocumentRepositoryMixin,
)
from super_rag.db.repositories.llm_provider import(
    AsyncLlmProviderRepositoryMixin,
    LlmProviderRepositoryMixin,
)
from super_rag.db.repositories.chat_message import(
    AsyncChatMessageRepositoryMixin,
    ChatMessageRepositoryMixin,
)
from super_rag.db.repositories.agent import (
    AsyncAgentRepositoryMixin,
)
from super_rag.db.repositories.chat import (
    AsyncChatRepositoryMixin,
)
from super_rag.db.repositories.document_index import(
    AsyncDocumentIndexRepositoryMixin,
)
from super_rag.db.repositories.workflow import (
    AsyncWorkflowRepositoryMixin,
)
from super_rag.db.repositories.user import( 
    AsyncUserRepositoryMixin,
)
from super_rag.db.repositories.marketplace import( 
    AsyncMarketplaceRepositoryMixin,
)
from super_rag.db.repositories.marketplace_collection import( 
    AsyncMarketplaceCollectionRepositoryMixin,
)
logger = logging.getLogger(__name__)


class DatabaseOps(
    SyncBaseRepository,
    DocumentRepositoryMixin,
    CollectionRepositoryMixin,
    LlmProviderRepositoryMixin,
    ChatMessageRepositoryMixin,
):
    pass


class AsyncDatabaseOps(
    AsyncBaseRepository,
    AsyncDocumentRepositoryMixin,
    AsyncCollectionRepositoryMixin,
    AsyncLlmProviderRepositoryMixin,
    AsyncChatMessageRepositoryMixin,
    AsyncAgentRepositoryMixin,
    AsyncChatRepositoryMixin,
    AsyncDocumentIndexRepositoryMixin,
    AsyncUserRepositoryMixin,
    AsyncWorkflowRepositoryMixin,
    AsyncMarketplaceRepositoryMixin,
    AsyncMarketplaceCollectionRepositoryMixin,
):
    pass


async_db_ops = AsyncDatabaseOps()
db_ops = DatabaseOps()
