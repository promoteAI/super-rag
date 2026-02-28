
import asyncio
import logging
import os
from datetime import datetime
from typing import Any, Awaitable, Dict

from collections.abc import Iterable

from super_rag.db.models import Collection
from super_rag.db.ops import db_ops, async_db_ops
from super_rag.llm.embed.base_embedding import get_collection_embedding_service_sync
from super_rag.llm.llm_error_types import RerankError
from super_rag.llm.rerank.rerank_service import RerankService
from super_rag.schema.utils import parseCollectionConfig
from super_rag.service.default_model_service import default_model_service
from super_rag.models import DocumentWithScore

from super_rag.graphiti.graphiti_core import Graphiti
from super_rag.graphiti.graphiti_core.cross_encoder.client import CrossEncoderClient
from super_rag.graphiti.graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient
from super_rag.graphiti.graphiti_core.embedder.client import EmbedderClient
from super_rag.graphiti.graphiti_core.errors import GraphitiError, NodeNotFoundError
from super_rag.graphiti.graphiti_core.llm_client.config import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_TEMPERATURE,
    LLMConfig,
)
from super_rag.graphiti.graphiti_core.llm_client.llm_client import SuperRagLLMClient
from super_rag.graphiti.graphiti_core.nodes import EpisodeType
from super_rag.graphiti.graphiti_core.utils.datetime_utils import utc_now
from super_rag.config import settings

logger = logging.getLogger(__name__)


class GraphitiManagerError(GraphitiError):
    """Graphiti 管理器异常"""

    pass


class SuperRagEmbedder(EmbedderClient):
    """
    将 SuperRAG 的 embedding service 适配为 Graphiti 的 `EmbedderClient`。
    """

    def __init__(self, collection: Collection):
        embedding_svc, dim = get_collection_embedding_service_sync(collection)
        self._svc = embedding_svc
        self._dim = dim

    @property
    def embedding_dim(self) -> int:
        return self._dim

    async def create(
        self,
        input_data: str | list[str] | Iterable[int] | Iterable[Iterable[int]],
    ) -> list[float]:
        # Graphiti 只会传入单条文本（str 或 [str]）
        if isinstance(input_data, str):
            texts = [input_data]
        elif isinstance(input_data, list) and input_data and isinstance(input_data[0], str):
            texts = [input_data[0]]
        else:
            # 退化处理：把 token 序列转成空格拼接文本
            texts = [" ".join(str(x) for x in input_data)]

        embeddings = await self._svc.aembed_documents(texts)
        # aembed_documents 返回 List[List[float]]
        return embeddings[0] if embeddings else []

    async def create_batch(self, input_data_list: list[str]) -> list[list[float]]:
        if not input_data_list:
            return []
        embeddings = await self._svc.aembed_documents(input_data_list)
        return embeddings


class SuperRagReranker(CrossEncoderClient):
    """
    将 SuperRAG 的通用重排服务适配为 Graphiti 的 `CrossEncoderClient`。
    优先使用 SuperRAG 中为当前用户配置的默认 rerank 模型；如果未配置或调用失败，
    则回退到 Graphiti 自带的 `OpenAIRerankerClient` 行为。
    """

    def __init__(self, collection: Collection):
        self._collection = collection
        self._rerank_service: RerankService | None = None
        self._fallback_client: CrossEncoderClient | None = None

    async def _get_rerank_service(self) -> RerankService | None:
        """
        懒加载并缓存 SuperRAG 的 RerankService。
        返回 None 表示使用回退 reranker。
        """
        if self._rerank_service is not None:
            return self._rerank_service

        user_id = self._collection.user

        try:
            model, model_service_provider, custom_llm_provider = await default_model_service.get_default_rerank_config(
                user_id
            )
        except Exception as e:
            logger.warning(f"Failed to load default rerank config for user {user_id}: {e}")
            return None

        if not model or not model_service_provider or not custom_llm_provider:
            logger.info("No default rerank model configured, fallback to Graphiti built-in reranker")
            return None

        api_key = await async_db_ops.query_provider_api_key(model_service_provider, user_id)
        if not api_key:
            logger.warning(f"API KEY not found for LLM Provider: {model_service_provider}")
            return None

        try:
            llm_provider = await async_db_ops.query_llm_provider_by_name(model_service_provider)
        except Exception as e:
            logger.error(f"Failed to query LLM provider '{model_service_provider}': {e}")
            return None

        base_url = getattr(llm_provider, "base_url", None)
        if not base_url:
            logger.warning(f"Base URL not configured for provider '{model_service_provider}'")
            return None

        rerank_service = RerankService(
            rerank_provider=custom_llm_provider,
            rerank_model=model,
            rerank_service_url=base_url,
            rerank_service_api_key=api_key,
        )

        try:
            rerank_service.validate_configuration()
        except Exception as e:
            logger.warning(f"Invalid rerank service configuration, fallback to Graphiti built-in reranker: {e}")
            return None

        logger.info(
            "Initialized SuperRagReranker with provider=%s, model=%s, base_url=%s",
            model_service_provider,
            model,
            base_url,
        )
        self._rerank_service = rerank_service
        return rerank_service

    def _get_fallback_client(self) -> CrossEncoderClient:
        """
        获取或初始化回退的 Graphiti 内置 reranker。
        当前直接使用 `OpenAIRerankerClient`，其行为与 Graphiti 默认一致。
        """
        if self._fallback_client is None:
            self._fallback_client = OpenAIRerankerClient()
        return self._fallback_client

    async def rank(self, query: str, passages: list[str]) -> list[tuple[str, float]]:
        """
        使用 SuperRAG 的 rerank 服务对候选文本进行重排。
        返回值与 Graphiti 期望的 CrossEncoderClient.rank 接口保持一致。
        """
        if not passages:
            return []

        # 优先尝试使用 SuperRAG rerank 服务
        rerank_service = await self._get_rerank_service()
        if rerank_service is None:
            # 未配置或初始化失败，直接使用 Graphiti 默认 reranker
            logger.info("SuperRagReranker disabled or misconfigured, using fallback OpenAI reranker")
            return await self._get_fallback_client().rank(query, passages)

        docs = [
            DocumentWithScore(text=passage, score=None, metadata={"source": "graphiti_rerank"})
            for passage in passages
        ]

        try:
            reranked_docs = await rerank_service.async_rerank(query, docs)
            # RerankService 目前只返回新的顺序，不修改 score，这里统一赋予 1.0 作为占位分数，
            # Graphiti 主要使用顺序以及与 reranker_min_score 的比较。
            return [(doc.text or "", 1.0) for doc in reranked_docs]
        except RerankError as e:
            logger.warning(f"SuperRagReranker service failed, falling back to OpenAI reranker: {e}")
            return await self._get_fallback_client().rank(query, passages)
        except Exception as e:
            logger.error(f"Unexpected error in SuperRagReranker.rank, falling back to OpenAI reranker: {e}")
            return await self._get_fallback_client().rank(query, passages)


def _build_superrag_llm_client(collection: Collection) -> SuperRagLLMClient | None:
    """
    基于 Collection 配置构造一个 Graphiti 使用的 SuperRAG LLMClient。
    """
    try:
        config = parseCollectionConfig(collection.config)
        if not config.completion or not config.completion.model:
            return None

        provider_name = config.completion.model_service_provider
        if not provider_name:
            return None

        api_key = db_ops.query_provider_api_key(provider_name, collection.user)
        if not api_key:
            raise GraphitiManagerError(f"API KEY not found for LLM Provider: {provider_name}")

        llm_provider = db_ops.query_llm_provider_by_name(provider_name)
        base_url = llm_provider.base_url

        llm_config = LLMConfig(
            api_key=api_key,
            model=config.completion.model,
            base_url=base_url,
            temperature=config.completion.temperature or DEFAULT_TEMPERATURE,
            max_tokens=(
                config.completion.max_completion_tokens
                or config.completion.max_tokens
                or DEFAULT_MAX_TOKENS
            ),
        )

        provider = config.completion.custom_llm_provider or provider_name

        return SuperRagLLMClient(
            config=llm_config,
            provider=provider,
        )
    except Exception as e:  # pragma: no cover - 防御性兜底
        logger.warning(f"Failed to build SuperRagLLMClient, fallback to Graphiti default LLM: {e}")
        return None


def _create_graphiti_instance(collection: Collection) -> Graphiti:
    """
    为给定的 Collection 创建一个 Graphiti 实例。
    """
    # 图数据库连接配置
    uri = settings.neo4j_uri
    user = settings.neo4j_user
    password = settings.neo4j_password

    if not uri or not user or not password:
        raise GraphitiManagerError(
            "Neo4j connection is not configured. Please set GRAPHITI_NEO4J_URI/NEO4J_URI, "
            "NEO4J_USER and NEO4J_PASSWORD."
        )

    # LLM & Embedder 适配到 Graphiti
    llm_client = _build_superrag_llm_client(collection)
    embedder = SuperRagEmbedder(collection)
    cross_encoder = SuperRagReranker(collection)

    graphiti = Graphiti(
        uri=uri,
        user=user,
        password=password,
        llm_client=llm_client,
        embedder=embedder,
        cross_encoder=cross_encoder,
    )
    return graphiti


# --- Ray Support Functions ---


def process_document_for_ray(
    collection: Collection,
    content: str,
    doc_id: str,
    file_path: str,
) -> Dict[str, Any]:
    """
    在同步上下文（Ray worker）中处理单个文档，调用 Graphiti 构建知识图谱。
    """
    return _run_in_new_loop(_process_document_async(collection, content, doc_id, file_path))


def delete_document_for_ray(collection: Collection, doc_id: str) -> Dict[str, Any]:
    """
    在同步上下文中，根据文档 ID 删除对应的 Graphiti episode。
    """
    return _run_in_new_loop(_delete_document_async(collection, doc_id))


async def _process_document_async(
    collection: Collection,
    content: str,
    doc_id: str,
    file_path: str,
) -> Dict[str, Any]:
    """
    使用 Graphiti 对单个文档进行知识图谱抽取。

    目前策略：将整个文档作为一个 EpisodeType.text 的 episode 写入图中，
    episode 的 uuid 即为文档 ID，方便后续删除。
    """
    logger.info(f"Processing document {doc_id} with Graphiti")

    if not content:
        # 兼容原 LightRAG 返回结构
        return {
            "status": "success",
            "doc_id": doc_id,
            "chunks_created": 0,
            "entities_extracted": 0,
            "relations_extracted": 0,
        }

    graphiti = _create_graphiti_instance(collection)

    try:
        reference_time: datetime = utc_now()

        result = await graphiti.add_episode(
            name=str(doc_id),
            episode_body=content,
            source_description=file_path,
            reference_time=reference_time,
            source=EpisodeType.text,
            group_id=None,  # 使用驱动默认 database / group
            # 注意：如果传入 uuid 且该 episode 不存在，Graphiti 内部会尝试 EpisodicNode.get_by_uuid 并抛出 NodeNotFoundError。
            # 这里不传 uuid，让 Graphiti 自行生成，避免首次建图时报 "node xxx not found"。
        )

        entities_count = len(result.nodes)
        relations_count = len(result.edges)

        return {
            "status": "success",
            "doc_id": doc_id,
            # 为兼容旧的 LightRAG 统计字段，这里把 1 个 episode 映射为 1 个 "chunk"
            "chunks_created": 1,
            "entities_extracted": entities_count,
            "relations_extracted": relations_count,
        }
    except Exception as e:
        logger.error(f"Graphiti processing failed for document {doc_id}: {e}")
        return {
            "status": "error",
            "doc_id": doc_id,
            "message": str(e),
        }
    finally:
        try:
            await graphiti.close()
        except Exception as e:  # pragma: no cover
            logger.warning(f"Failed to close Graphiti driver: {e}")


async def _delete_document_async(collection: Collection, doc_id: str) -> Dict[str, Any]:
    """
    根据文档 ID 删除对应的 Graphiti episode。

    约定：索引时 episode.uuid == str(doc_id)，因此这里可以直接按 uuid 删除。
    """
    graphiti = _create_graphiti_instance(collection)

    try:
        try:
            await graphiti.remove_episode(str(doc_id))
            logger.info(f"Deleted Graphiti episode for document {doc_id}")
            return {
                "status": "success",
                "doc_id": doc_id,
                "message": "Episode deleted successfully",
            }
        except NodeNotFoundError:
            logger.warning(f"Graphiti episode not found for document {doc_id}")
            return {
                "status": "warning",
                "doc_id": doc_id,
                "message": "Episode not found for given document_id",
            }
    except Exception as e:
        logger.error(f"Failed to delete Graphiti episode for document {doc_id}: {e}")
        return {
            "status": "error",
            "doc_id": doc_id,
            "message": str(e),
        }
    finally:
        try:
            await graphiti.close()
        except Exception as e:  # pragma: no cover
            logger.warning(f"Failed to close Graphiti driver during delete: {e}")


def _run_in_new_loop(coro: Awaitable) -> Any:
    """在新的事件循环中运行协程（用于 Ray 等同步环境）"""
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    finally:
        try:
            pending = [task for task in asyncio.all_tasks(loop) if not task.done()]
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.wait(pending, timeout=1.0))
        except Exception:
            pass
        finally:
            loop.close()
            asyncio.set_event_loop(None)

if __name__ == "__main__":
    from super_rag.tasks.utils import get_document_and_collection
    from super_rag.tasks.document import document_index_task
    parsed_data = document_index_task.parse_document(
        document_id="doce4941010ffb0ffbc"
    )
    _, collection = get_document_and_collection("doce4941010ffb0ffbc")
    
    process_document_for_ray(collection, parsed_data.content, parsed_data.document_id, parsed_data.file_path)
