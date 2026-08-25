"""LottoLab-level read-only MCP interface."""

from lottolab.interfaces.mcp.server import (
    LottoLabMcpServer,
    build_production_service,
    serve_stdio,
)

__all__ = ["LottoLabMcpServer", "build_production_service", "serve_stdio"]
