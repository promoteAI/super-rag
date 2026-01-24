

import json
import logging
from typing import List

import httpx
import litellm

from super_rag.llm.llm_error_types import (
    InvalidDocumentError,
    RerankError,
    TooManyDocumentsError,
    wrap_litellm_error,
)
from super_rag.models import DocumentWithScore

logger = logging.getLogger(__name__)


class RerankService:
    def __init__(
        self,
        rerank_provider: str,
        rerank_model: str,
        rerank_service_url: str,
        rerank_service_api_key: str,
        caching: bool = True,
    ):
        self.rerank_provider = rerank_provider
        self.model = rerank_model
        self.api_base = rerank_service_url
        self.api_key = rerank_service_api_key
        self.caching = caching

        # Set document limit based on provider
        self.max_documents = 1000

    async def async_rerank(self, query: str, results: List[DocumentWithScore]) -> List[DocumentWithScore]:
        try:
            # Validate inputs
            if not query or not query.strip():
                raise InvalidDocumentError("Query cannot be empty")

            if not results:
                logger.info("No documents to rerank, returning empty list")
                return []

            # Check document count limits
            if len(results) > self.max_documents:
                raise TooManyDocumentsError(
                    document_count=len(results), max_documents=self.max_documents, model_name=self.model
                )

            # Extract texts and validate documents
            texts = []
            invalid_indices = []
            for i, doc in enumerate(results):
                if not doc or not hasattr(doc, "text") or not doc.text or not doc.text.strip():
                    invalid_indices.append(i)
                    texts.append(" ")  # Use placeholder for empty docs
                else:
                    texts.append(doc.text)

            if invalid_indices:
                logger.warning(f"Found {len(invalid_indices)} invalid documents at indices: {invalid_indices}")
                if len(invalid_indices) == len(results):
                    raise InvalidDocumentError("All documents are empty or invalid", document_count=len(results))

            # Call the cached internal method with simple types
            reranked_indices = await self._rank_texts(query, texts)

            # Reconstruct DocumentWithScore objects in the new order
            reranked_results = [results[i] for i in reranked_indices if 0 <= i < len(results)]

            logger.info(f"Successfully reranked {len(reranked_results)} documents")
            return reranked_results

        except (InvalidDocumentError, TooManyDocumentsError, RerankError):
            # Re-raise our custom rerank errors
            raise
        except Exception as e:
            logger.error(f"Rerank operation failed: {str(e)}")
            # Convert litellm errors to our custom types
            raise wrap_litellm_error(e, "rerank", self.rerank_provider, self.model) from e

    async def _rank_texts(self, query: str, texts: List[str]) -> List[int]:
        try:
            # Handle different providers
            if self.rerank_provider == "alibabacloud" or "alibabacloud" in self.rerank_provider.lower():
                # Use Alibaba Cloud DashScope API format
                resp = await self._call_alibabacloud_rerank_api(query, texts)
            else:
                # Use litellm for other providers
                resp = await litellm.arerank(
                    custom_llm_provider=self.rerank_provider,
                    model=self.model,
                    query=query,
                    documents=texts,
                    api_key=self.api_key,
                    api_base=self.api_base,
                    return_documents=False,
                    caching=self.caching,
                )

            # Validate response
            if not resp or "results" not in resp:
                raise RerankError(
                    "Invalid response format from rerank API",
                    {"provider": self.rerank_provider, "model": self.model, "document_count": len(texts)},
                )

            # Extract and validate indices
            try:
                indices = [item["index"] for item in resp["results"]]

                # Validate indices
                if len(indices) != len(texts):
                    logger.warning(f"Rerank returned {len(indices)} indices for {len(texts)} documents")

                # Check for invalid indices
                invalid_rerank_indices = [idx for idx in indices if idx < 0 or idx >= len(texts)]
                if invalid_rerank_indices:
                    raise RerankError(
                        f"Invalid rerank indices: {invalid_rerank_indices}",
                        {
                            "provider": self.rerank_provider,
                            "model": self.model,
                            "invalid_indices": invalid_rerank_indices,
                        },
                    )

                # Return the valid indices
                valid_indices = [idx for idx in indices if 0 <= idx < len(texts)]
                return valid_indices

            except (KeyError, IndexError, TypeError) as e:
                raise RerankError(
                    f"Failed to parse rerank response: {str(e)}",
                    {
                        "provider": self.rerank_provider,
                        "model": self.model,
                        "response_keys": list(resp.keys()) if isinstance(resp, dict) else "non-dict",
                    },
                ) from e

        except RerankError:
            # Re-raise our custom rerank errors
            raise
        except Exception as e:
            logger.error(f"Internal rerank operation failed: {str(e)}")
            # Convert litellm errors to our custom types
            raise wrap_litellm_error(e, "rerank", self.rerank_provider, self.model) from e

    async def _call_alibabacloud_rerank_api(self, query: str, documents: List[str]) -> dict:
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                url = "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank"
                headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

                payload = {
                    "model": self.model,
                    "input": {"query": query, "documents": documents},
                    "parameters": {"return_documents": False, "top_n": len(documents)},
                }

                logger.debug(f"Alibaba Cloud rerank API request to {url} with {len(documents)} documents")

                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()

                result = response.json()

                if "output" in result and "results" in result["output"]:
                    # Convert to litellm format
                    return {
                        "results": [
                            {"index": item.get("index", i), "relevance_score": item.get("relevance_score", 0.0)}
                            for i, item in enumerate(result["output"]["results"])
                        ]
                    }
                else:
                    raise RerankError(
                        "Unexpected response format from Alibaba Cloud rerank API",
                        {
                            "provider": self.rerank_provider,
                            "model": self.model,
                            "response_keys": list(result.keys()) if isinstance(result, dict) else "non-dict",
                        },
                    )

        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error during Alibaba Cloud rerank API call: {e.response.status_code} - {e.response.text}"
            )
            raise RerankError(
                f"Alibaba Cloud rerank API returned {e.response.status_code}: {e.response.text}",
                {"provider": self.rerank_provider, "model": self.model, "status_code": e.response.status_code},
            ) from e
        except httpx.RequestError as e:
            logger.error(f"Request error during Alibaba Cloud rerank API call: {str(e)}")
            raise RerankError(
                f"Failed to connect to Alibaba Cloud rerank API: {str(e)}",
                {"provider": self.rerank_provider, "model": self.model, "api_base": self.api_base},
            ) from e
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Alibaba Cloud rerank API response as JSON: {str(e)}")
            raise RerankError(
                f"Invalid JSON response from Alibaba Cloud rerank API: {str(e)}",
                {"provider": self.rerank_provider, "model": self.model},
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error during Alibaba Cloud rerank API call: {str(e)}")
            raise RerankError(
                f"Unexpected error during Alibaba Cloud rerank API call: {str(e)}",
                {"provider": self.rerank_provider, "model": self.model},
            ) from e

    def validate_configuration(self) -> None:
        from super_rag.llm.llm_error_types import InvalidConfigurationError

        if not self.rerank_provider:
            raise InvalidConfigurationError("rerank_provider", self.rerank_provider, "Provider cannot be empty")

        if not self.model:
            raise InvalidConfigurationError("model", self.model, "Model name cannot be empty")

        if not self.api_key:
            raise InvalidConfigurationError("api_key", None, "API key cannot be empty")

        if not self.api_base:
            raise InvalidConfigurationError("api_base", self.api_base, "API base URL cannot be empty")


# ================ 以下为主程序测试代码 ================
if __name__ == "__main__":
    import asyncio
    from super_rag.models import DocumentWithScore
    litellm._turn_on_debug()
    # 案例测试：异步rerank

    print("====异步 rerank 测试====")

    # 可以替换为自己的 rerank provider、model、service_url、api_key
    reranker = RerankService(
        rerank_provider="cohere",      # or your provider
        rerank_model="BAAI/bge-reranker-v2-m3",   # model name
        rerank_service_url="https://api.siliconflow.cn/v1/rerank",    # base url
        rerank_service_api_key="sk-xmodfeodmqedhuxxafvuazjfrqqlnplotxnfnkvmsvtecngw",
        caching=True,
    )

    test_query = "什么是向量数据库？"
    test_docs = [DocumentWithScore(text="向量数据库是一种高效存储和检索大规模向量数据的数据库。", score=0.8),
                 DocumentWithScore(text="天气真好", score=0.1),
                 DocumentWithScore(text="本内容介绍了数据库结构。", score=0.3),
                 DocumentWithScore(text="向量检索是一种常见任务。", score=0.2)]

    async def async_rerank_test():
        try:
            new_results = await reranker.async_rerank(test_query, test_docs)
            print("[Rerank] 新顺序:")
            for idx, doc in enumerate(new_results):
                print(f"{idx+1}. {doc.text[:20]}... (score: {doc.score})")
        except Exception as e:
            print("Rerank error:", e)

    asyncio.run(async_rerank_test())

