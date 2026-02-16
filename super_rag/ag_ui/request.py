"""Request models for AG-UI endpoint. Accept AG-UI RunAgentInput or a minimal body."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AGUIRunRequest(BaseModel):
    """
    Request body for AG-UI run endpoint.
    Maps from AG-UI RunAgentInput: thread_id -> chat_id, run_id -> message_id,
    last user message content -> query. Extra super_rag options in forwarded_props.
    """

    thread_id: str = Field(..., description="Conversation thread ID (use as chat_id)")
    run_id: str = Field(..., description="Run ID (use as message_id)")
    parent_run_id: Optional[str] = None
    messages: List[Dict[str, Any]] = Field(default_factory=list, description="Conversation messages")
    forwarded_props: Optional[Dict[str, Any]] = Field(
        None,
        description="Extra props: query (override), collections, completion, language, files, web_search_enabled",
    )

    def get_query_from_messages(self) -> str:
        """Extract the latest user message content as query."""
        for msg in reversed(self.messages or []):
            role = (msg or {}).get("role") or (msg or {}).get("role")
            if role == "user":
                content = (msg or {}).get("content")
                if isinstance(content, str) and content.strip():
                    return content.strip()
                if isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict) and part.get("type") == "text":
                            text = part.get("text", "")
                            if isinstance(text, str) and text.strip():
                                return text.strip()
                break
        # Fallback to forwarded_props
        if self.forwarded_props and isinstance(self.forwarded_props.get("query"), str):
            return self.forwarded_props["query"].strip()
        return ""
