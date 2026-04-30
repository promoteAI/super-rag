
import logging
import os
from urllib.parse import quote

from mcp_agent.app import MCPApp
from mcp_agent.config import LoggerSettings, MCPServerSettings, MCPSettings, OpenAISettings, Settings

from .agent_config import AgentConfig
from .exceptions import agent_config_invalid, mcp_init_failed

logger = logging.getLogger(__name__)

_DEFAULT_HINDSIGHT_MCP_BASE = "http://localhost:8888/mcp"


def hindsight_mcp_url_for_bank_id(bank_id: str) -> str:
    """
    Single-bank Hindsight MCP URL: /mcp/{bank_id}/ with path-safe encoding.

    Matches https://hindsight.vectorize.io/developer/mcp-server (bank from URL path).
    """
    base = os.getenv("HINDSIGHT_MCP_URL", _DEFAULT_HINDSIGHT_MCP_BASE).rstrip("/")
    segment = quote(bank_id, safe="")
    return f"{base}/{segment}/"


class MCPAppFactory:
    """Factory class for creating MCP applications."""

    @staticmethod
    def create_mcp_app(
        model: str,
        llm_provider_name: str,
        base_url: str,
        api_key: str,
        super_rag_api_key: str,
        super_rag_mcp_url: str,
        hindsight_bank_id: str | None = None,
        # Configurable LLM parameters
        temperature: float = 0.7,
        max_tokens: int = 60000,
    ) -> MCPApp:
        """Create MCPApp instance with the specified parameters."""
        # Validate required parameters
        required_params = {
            "model": model,
            "llm_provider_name": llm_provider_name,
            "base_url": base_url,
            "api_key": api_key,
            "super_rag_api_key": super_rag_api_key,
            "super_rag_mcp_url": super_rag_mcp_url,
        }

        for param_name, value in required_params.items():
            if not value:
                raise agent_config_invalid(param_name, f"{param_name} is required")

        if hindsight_bank_id:
            hindsight_mcp_url = hindsight_mcp_url_for_bank_id(hindsight_bank_id)
        else:
            hindsight_mcp_url = os.getenv("HINDSIGHT_MCP_URL", _DEFAULT_HINDSIGHT_MCP_BASE)
            logger.warning(
                "Hindsight MCP is using multi-bank root URL without per-user bank_id; "
                "pass hindsight_bank_id (e.g. user_id) for one-bank-per-user isolation."
            )

        try:
            settings = Settings(
                execution_engine="asyncio",
                logger=LoggerSettings(type="console", level="info"),
                mcp=MCPSettings(
                    servers={
                        "super_rag": MCPServerSettings(
                            transport="streamable_http",
                            url=super_rag_mcp_url,
                            headers={
                                "Authorization": f"Bearer {super_rag_api_key}",
                                "Content-Type": "application/json",
                            },
                            http_timeout_seconds=30,
                            read_timeout_seconds=120,
                            description="super_rag knowledge base server",
                        ),
                        "hindsight": MCPServerSettings(
                            transport="streamable_http",
                            url=hindsight_mcp_url,
                            headers={
                                "Content-Type": "application/json",
                            },
                            http_timeout_seconds=30,
                            read_timeout_seconds=120,
                            description="hindsight knowledge base server",
                        ),
                    }
                ),
                openai=OpenAISettings(
                    api_key=api_key,
                    base_url=base_url,
                    default_model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                ),
            )

            mcp_app = MCPApp(name="super_rag_agent", settings=settings)
            logger.info(f"Created MCP app for {llm_provider_name}:{model}")
            return mcp_app

        except Exception as e:
            logger.error(f"Failed to create MCP app: {e}")
            raise mcp_init_failed(f"MCP app creation failed: {str(e)}")

    @staticmethod
    def create_mcp_app_from_config(config: AgentConfig) -> MCPApp:
        """Create MCPApp instance using AgentConfig object."""
        return MCPAppFactory.create_mcp_app(
            model=config.default_model,
            llm_provider_name=config.provider_name,
            base_url=config.base_url,
            api_key=config.api_key,
            super_rag_api_key=config.super_rag_api_key,
            super_rag_mcp_url=config.super_rag_mcp_url,
            hindsight_bank_id=config.user_id,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )
