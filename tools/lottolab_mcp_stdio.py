"""Canonical stdio entrypoint for the existing read-only LottoLab MCP server."""

from lottolab.interfaces.mcp.server import serve_stdio

if __name__ == "__main__":
    serve_stdio()
