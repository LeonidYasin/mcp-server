"""Entry point for mcp-server command."""

import asyncio
import os
import sys

from dotenv import load_dotenv

from mcp_server.core.registry import ToolRegistry
from mcp_server.core.server import MCPServer


def main():
    """Main entry point."""
    load_dotenv()

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("Error: GITHUB_TOKEN environment variable is not set.", file=sys.stderr)
        print("Create a .env file with: GITHUB_TOKEN=ghp_your_token", file=sys.stderr)
        sys.exit(1)

    registry = ToolRegistry()
    registry.discover()

    server = MCPServer(token, registry)
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
