"""
SuperRAG MCP (Model Context Protocol) Integration

This module provides MCP server functionality for SuperRAG, allowing
MCP clients to interact with SuperRAG's search and collection management
capabilities.

Features:
- Hybrid search (vector + fulltext + graph)
- Collection management
- API key authentication
- Resource and prompt providers
"""

from .server import mcp_server

__all__ = ["mcp_server"]
