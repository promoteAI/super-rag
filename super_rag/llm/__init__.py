
# Export all LLM error types for easy access
# Export services
from super_rag.llm.completion.completion_service import CompletionService
from super_rag.llm.embed.embedding_service import EmbeddingService
from super_rag.llm.llm_error_types import (
    # API errors
    AuthenticationError,
    BatchProcessingError,
    # Service-specific errors
    CompletionError,
    DimensionMismatchError,
    EmbeddingError,
    EmptyTextError,
    InvalidConfigurationError,
    InvalidDocumentError,
    InvalidPromptError,
    LLMAPIError,
    LLMConfigurationError,
    # Base error classes
    LLMError,
    ModelNotFoundError,
    # Configuration errors
    ProviderNotFoundError,
    QuotaExceededError,
    RateLimitError,
    RerankError,
    ResponseParsingError,
    ScoreOutOfRangeError,
    ServerError,
    TextTooLongError,
    TimeoutError,
    ToolCallError,
    TooManyDocumentsError,
    is_retryable_error,
    # Utility functions
    wrap_litellm_error,
)
from super_rag.llm.rerank.rerank_service import RerankService

__all__ = [
    # Error classes
    "LLMError",
    "LLMConfigurationError",
    "LLMAPIError",
    "ProviderNotFoundError",
    "ModelNotFoundError",
    "InvalidConfigurationError",
    "AuthenticationError",
    "RateLimitError",
    "TimeoutError",
    "QuotaExceededError",
    "ServerError",
    "CompletionError",
    "InvalidPromptError",
    "ResponseParsingError",
    "ToolCallError",
    "EmbeddingError",
    "TextTooLongError",
    "EmptyTextError",
    "DimensionMismatchError",
    "BatchProcessingError",
    "RerankError",
    "InvalidDocumentError",
    "TooManyDocumentsError",
    "ScoreOutOfRangeError",
    "wrap_litellm_error",
    "is_retryable_error",
    # Services
    "CompletionService",
    "EmbeddingService",
    "RerankService",
]

# Initialize cache when module is imported
from super_rag.llm import litellm_cache, litellm_logging

litellm_cache.setup_litellm_cache()
litellm_logging.setup_litellm_logging()
