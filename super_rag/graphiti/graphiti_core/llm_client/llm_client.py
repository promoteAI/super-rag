from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from super_rag.llm import CompletionService

from ..prompts.models import Message
from .client import DEFAULT_MAX_TOKENS, LLMClient
from .config import LLMConfig, ModelSize
import json
import typing
from json import JSONDecodeError


class SuperRagLLMClient(LLMClient):
    """
    A thin adapter that lets Graphiti's `LLMClient` abstraction
    call SuperRAG's generic `CompletionService`-based LLM.

    This client:
    - Reuses the existing `LLMClient.generate_response` logic
      (language instructions, JSON schema hints, tracing, caching)
    - Delegates the actual completion call to `CompletionService.agenerate`
    - Returns a simple `{"content": <text>}` dict for unstructured output
    """

    def __init__(
        self,
        config: LLMConfig | None = None,
        cache: bool = False,
        *,
        provider: str = 'openai',
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        vision: bool = False,
        caching: bool = True,
    ) -> None:
        """
        Initialize SuperRagLLMClient.

        Args:
            config: Standard Graphiti `LLMConfig`. This is the primary way
                to configure the client and matches other Graphiti LLM clients.
            provider: SuperRAG / litellm `custom_llm_provider` name.
                Defaults to "openai" (对 DeepSeek、SiliconFlow 这类
                OpenAI 兼容 API 通常也是用这个字符串)。
            model / base_url / api_key / temperature / max_tokens:
                这些参数如果提供，会覆盖 / 补全 `config` 里的值。
            cache: Whether to enable Graphiti-level response caching.
            temperature: Optional temperature override.
            max_tokens: Optional max output tokens override.
            vision: Whether this model supports image input (matches CompletionService).
            caching: Whether to enable litellm-level caching inside `CompletionService`.
        """
        # 1. 先保证有一个 LLMConfig（如果外面没传，就用单独参数构造）
        if config is None:
            config = LLMConfig(
                api_key=api_key,
                model=model,
                base_url=base_url,
                max_tokens=max_tokens if max_tokens is not None else DEFAULT_MAX_TOKENS,
            )

        # 如果又通过显式参数传了这些值，就覆盖到 config 上
        if api_key is not None:
            config.api_key = api_key
        if model is not None:
            config.model = model
        if base_url is not None:
            config.base_url = base_url
        if temperature is not None:
            config.temperature = temperature
        if max_tokens is not None:
            config.max_tokens = max_tokens

        # 2. 初始化父类，沿用 Graphiti 的通用逻辑（缓存、tracer、token_tracker 等）
        super().__init__(config, cache=cache)

        # 3. 记录最终运行时参数
        self.temperature = config.temperature
        self.max_tokens = config.max_tokens

        # 4. 创建底层 SuperRAG CompletionService
        service_model = config.model or ''
        service_base_url = config.base_url or ''
        service_api_key = config.api_key or ''

        self._service = CompletionService(
            provider=provider,
            model=service_model,
            base_url=service_base_url,
            api_key=service_api_key,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            vision=vision,
            caching=caching,
        )

    def _extract_json_from_text(self, text: str) -> dict[str, typing.Any]:
        """Extract JSON from text content.

        A helper method to extract JSON from text content, used when tool use fails or
        no response_model is provided.

        Args:
            text: The text to extract JSON from

        Returns:
            Extracted JSON as a dictionary

        Raises:
            ValueError: If JSON cannot be extracted or parsed
        """
        try:
            json_start = text.find('{')
            json_end = text.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = text[json_start:json_end]
                return json.loads(json_str)
            else:
                raise ValueError(f'Could not extract JSON from model response: {text}')
        except (JSONDecodeError, ValueError) as e:
            raise ValueError(f'Could not extract JSON from model response: {text}') from e

    async def _generate_response(
        self,
        messages: list[Message],
        response_model: type[BaseModel] | None = None,  # noqa: ARG002 - kept for interface compatibility
        max_tokens: int = DEFAULT_MAX_TOKENS,
        model_size: ModelSize = ModelSize.medium,  # noqa: ARG002 - not used by CompletionService
    ) -> dict[str, Any]:
        """
        Concrete implementation of the abstract Graphiti `_generate_response`.

        We flatten `messages` into:
        - `history`: all but the final message (role/content pairs)
        - `prompt`: the final message content

        The JSON-schema and language-instruction prompting is already handled
        in the base `LLMClient.generate_response`, so here we simply pass the
        prepared text through to SuperRAG's `CompletionService`.
        """
        if not messages:
            return {"content": ""}

        # Respect method-level max_tokens override if provided,
        # and clamp to a safe upper bound for OpenAI 兼容接口（常见上限 8192）
        effective_max_tokens = max_tokens or self.max_tokens or DEFAULT_MAX_TOKENS
        if effective_max_tokens > 8192:
            effective_max_tokens = 8192

        # Update underlying service config for this call
        self._service.max_tokens = effective_max_tokens
        self._service.temperature = self.temperature

        # Split history vs final prompt
        *history_msgs, final_msg = messages

        history = [{"role": m.role, "content": m.content} for m in history_msgs]
        prompt = final_msg.content

        # Use the non-streaming async completion API
        text = await self._service.agenerate(
            history=history,
            prompt=prompt,
            images=None,
            memory=False,
        )

        # Extract JSON from text
        return self._extract_json_from_text(text)


