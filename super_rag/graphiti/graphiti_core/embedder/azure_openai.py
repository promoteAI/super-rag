

import logging
from typing import Any

from openai import AsyncAzureOpenAI, AsyncOpenAI

from .client import EmbedderClient

logger = logging.getLogger(__name__)


class AzureOpenAIEmbedderClient(EmbedderClient):
    """Wrapper class for Azure OpenAI that implements the EmbedderClient interface.

    Supports both AsyncAzureOpenAI and AsyncOpenAI (with Azure v1 API endpoint).
    """

    def __init__(
        self,
        azure_client: AsyncAzureOpenAI | AsyncOpenAI,
        model: str = 'text-embedding-3-small',
    ):
        self.azure_client = azure_client
        self.model = model

    async def create(self, input_data: str | list[str] | Any) -> list[float]:
        """Create embeddings using Azure OpenAI client."""
        try:
            # Handle different input types
            if isinstance(input_data, str):
                text_input = [input_data]
            elif isinstance(input_data, list) and all(isinstance(item, str) for item in input_data):
                text_input = input_data
            else:
                # Convert to string list for other types
                text_input = [str(input_data)]

            response = await self.azure_client.embeddings.create(model=self.model, input=text_input)

            # Return the first embedding as a list of floats
            return response.data[0].embedding
        except Exception as e:
            logger.error(f'Error in Azure OpenAI embedding: {e}')
            raise

    async def create_batch(self, input_data_list: list[str]) -> list[list[float]]:
        """Create batch embeddings using Azure OpenAI client."""
        try:
            response = await self.azure_client.embeddings.create(
                model=self.model, input=input_data_list
            )

            return [embedding.embedding for embedding in response.data]
        except Exception as e:
            logger.error(f'Error in Azure OpenAI batch embedding: {e}')
            raise
