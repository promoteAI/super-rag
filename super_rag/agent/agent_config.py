

"""Agent configuration management for session creation."""

from dataclasses import dataclass
from typing import List


@dataclass
class AgentConfig:
    """
    Configuration for agent session creation.

    This centralizes all agent-related configuration parameters to make
    the session creation more flexible and maintainable.
    """

    # Basic agent info
    user_id: str
    chat_id: str

    # LLM Settings
    provider_name: str
    api_key: str
    base_url: str
    default_model: str
    temperature: float = 0.7
    max_tokens: int = 60000

    # MCP configuration
    super_rag_api_key: str = None
    super_rag_mcp_url: str = None

    # Agent behavior configuration
    language: str = "en-US"
    instruction: str = ""
    server_names: List[str] = None

    def get_session_key(self) -> str:
        """Generate session key based on user, chat, and provider."""
        return f"{self.user_id}:{self.chat_id}:{self.provider_name}"
