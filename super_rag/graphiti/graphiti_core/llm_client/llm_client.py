from __future__ import annotations

import json
import logging
import typing
from json import JSONDecodeError
from typing import Any, ClassVar

import litellm
from pydantic import BaseModel

from super_rag.llm import CompletionService

from ..prompts.models import Message
from .client import LLMClient, get_extraction_language_instruction
from .config import DEFAULT_MAX_TOKENS, LLMConfig, ModelSize
from .errors import RateLimitError, RefusalError

logger = logging.getLogger(__name__)


class SuperRagLLMClient(LLMClient):
    """
    A thin adapter that lets Graphiti's `LLMClient` abstraction
    call SuperRAG's generic `CompletionService`-based LLM.

    This client:
    - Delegates the actual completion call to litellm with proper response_format
    - Supports structured output via json_schema response_format
    - Includes retry logic with error context for robustness
    """

    MAX_RETRIES: ClassVar[int] = 2

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
        if config is None:
            config = LLMConfig(
                api_key=api_key,
                model=model,
                base_url=base_url,
                max_tokens=max_tokens if max_tokens is not None else DEFAULT_MAX_TOKENS,
            )

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

        super().__init__(config, cache=cache)

        self.temperature = config.temperature
        self.max_tokens = config.max_tokens
        self.provider = provider

        self._service = CompletionService(
            provider=provider,
            model=config.model or '',
            base_url=config.base_url or '',
            api_key=config.api_key or '',
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            vision=vision,
            caching=caching,
        )

    def _extract_json_from_text(self, text: str) -> dict[str, typing.Any]:
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
        response_model: type[BaseModel] | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        model_size: ModelSize = ModelSize.medium,
    ) -> dict[str, Any]:
        if not messages:
            return {'content': ''}

        effective_max_tokens = max_tokens or self.max_tokens or DEFAULT_MAX_TOKENS

        litellm_messages: list[dict[str, str]] = []
        for m in messages:
            m.content = self._clean_input(m.content)
            if m.role == 'user':
                litellm_messages.append({'role': 'user', 'content': m.content})
            elif m.role == 'system':
                litellm_messages.append({'role': 'system', 'content': m.content})

        try:
            response_format: dict[str, Any] = {'type': 'json_object'}
            if response_model is not None:
                schema_name = getattr(response_model, '__name__', 'structured_response')
                json_schema = response_model.model_json_schema()
                response_format = {
                    'type': 'json_schema',
                    'json_schema': {
                        'name': schema_name,
                        'schema': json_schema,
                    },
                }

            response = await litellm.acompletion(
                custom_llm_provider=self.provider,
                model=self._service.model,
                base_url=self._service.base_url,
                api_key=self._service.api_key,
                temperature=self.temperature,
                max_tokens=effective_max_tokens,
                messages=litellm_messages,
                stream=False,
                caching=self._service.caching,
                response_format=response_format,
            )

            result = response.choices[0].message.content or ''
            return json.loads(result)
        except Exception as e:
            logger.error(f'Error in generating LLM response: {e}')
            raise

    async def generate_response(
        self,
        messages: list[Message],
        response_model: type[BaseModel] | None = None,
        max_tokens: int | None = None,
        model_size: ModelSize = ModelSize.medium,
        group_id: str | None = None,
        prompt_name: str | None = None,
    ) -> dict[str, typing.Any]:
        if max_tokens is None:
            max_tokens = self.max_tokens

        messages[0].content += get_extraction_language_instruction(group_id)

        with self.tracer.start_span('llm.generate') as span:
            attributes: dict[str, Any] = {
                'llm.provider': self.provider,
                'model.size': model_size.value,
                'max_tokens': max_tokens,
            }
            if prompt_name:
                attributes['prompt.name'] = prompt_name
            span.add_attributes(attributes)

            retry_count = 0
            last_error: Exception | None = None

            while retry_count <= self.MAX_RETRIES:
                try:
                    response = await self._generate_response(
                        messages, response_model, max_tokens=max_tokens, model_size=model_size
                    )
                    return response
                except (RateLimitError, RefusalError):
                    span.set_status('error', str(last_error))
                    raise
                except Exception as e:
                    last_error = e

                    if retry_count >= self.MAX_RETRIES:
                        logger.error(f'Max retries ({self.MAX_RETRIES}) exceeded. Last error: {e}')
                        span.set_status('error', str(e))
                        span.record_exception(e)
                        raise

                    retry_count += 1

                    error_context = (
                        f'The previous response attempt was invalid. '
                        f'Error type: {e.__class__.__name__}. '
                        f'Error details: {str(e)}. '
                        f'Please try again with a valid response, ensuring the output matches '
                        f'the expected format and constraints.'
                    )

                    error_message = Message(role='user', content=error_context)
                    messages.append(error_message)
                    logger.warning(
                        f'Retrying after application error (attempt {retry_count}/{self.MAX_RETRIES}): {e}'
                    )

            span.set_status('error', str(last_error))
            raise last_error or Exception('Max retries exceeded with no specific error')


