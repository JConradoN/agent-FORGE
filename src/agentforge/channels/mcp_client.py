"""MCP client with OAuth 2.0 support for calling external MCP servers (e.g. HeyGen).

First-run flow:
  1. A free local port is allocated.
  2. OAuth client metadata is registered with redirect_uri pointing to that port.
  3. The authorization URL is printed — the user opens it in a browser.
  4. A local asyncio HTTP server captures the callback code.
  5. Tokens are saved to ~/.agentforge/mcp_tokens/<slug>.json.
  6. Subsequent calls load tokens from disk (auto-refresh on expiry).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import socket
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from mcp import ClientSession
from mcp.client.auth import OAuthClientProvider, TokenStorage
from mcp.client.streamable_http import streamablehttp_client
from mcp.shared.auth import OAuthClientInformationFull, OAuthClientMetadata, OAuthToken

logger = logging.getLogger(__name__)

_TOKEN_DIR = Path.home() / ".agentforge" / "mcp_tokens"


# ---------------------------------------------------------------------------
# Token persistence
# ---------------------------------------------------------------------------


class FileTokenStorage:
    """Implements TokenStorage protocol — persists OAuth tokens/client info to disk."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict:
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save(self, data: dict) -> None:
        self._path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    async def get_tokens(self) -> OAuthToken | None:
        data = self._load()
        raw = data.get("tokens")
        if not raw:
            return None
        try:
            return OAuthToken.model_validate(raw)
        except Exception:
            return None

    async def set_tokens(self, tokens: OAuthToken) -> None:
        data = self._load()
        data["tokens"] = tokens.model_dump(mode="json", exclude_none=True)
        self._save(data)

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        data = self._load()
        raw = data.get("client_info")
        if not raw:
            return None
        try:
            return OAuthClientInformationFull.model_validate(raw)
        except Exception:
            return None

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        data = self._load()
        data["client_info"] = client_info.model_dump(mode="json", exclude_none=True)
        self._save(data)


# ---------------------------------------------------------------------------
# OAuth callback server
# ---------------------------------------------------------------------------


_OAUTH_PORT = int(os.environ.get("MCP_OAUTH_PORT", "9876"))


async def _start_callback_server(
    port: int,
) -> tuple[asyncio.Server, asyncio.Future[tuple[str, str | None]]]:
    """Starts the OAuth callback server and returns (server, result_future).

    The server listens immediately so the port is ready before the OAuth URL is opened.
    result_future is resolved when the browser completes the redirect.
    """
    loop = asyncio.get_running_loop()
    result_future: asyncio.Future[tuple[str, str | None]] = loop.create_future()

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            raw = await asyncio.wait_for(reader.read(4096), timeout=10.0)
        except asyncio.TimeoutError:
            writer.close()
            return

        first_line = raw.decode(errors="replace").split("\n")[0]
        parts = first_line.split(" ")
        path = parts[1] if len(parts) > 1 else "/"
        params = parse_qs(urlparse(path).query)
        code = params.get("code", [None])[0]
        state = params.get("state", [None])[0]

        body = b"<html><body><h2>Autorizado com sucesso. Pode fechar esta aba.</h2></body></html>"
        writer.write(
            b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n"
            + f"Content-Length: {len(body)}\r\n\r\n".encode()
            + body
        )
        await writer.drain()
        writer.close()

        if not result_future.done() and code:
            result_future.set_result((code, state))

    server = await asyncio.start_server(handle, "localhost", port)
    return server, result_future


# ---------------------------------------------------------------------------
# Core MCP call
# ---------------------------------------------------------------------------


def _server_slug(server_url: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]", "_", server_url)
    return slug[:80]


async def call_mcp_tool_async(
    server_url: str,
    tool_name: str,
    args: dict[str, Any],
    token_path: Path | None = None,
) -> Any:
    """Connects to an MCP server via SSE, handles OAuth, and calls a tool.

    Args:
        server_url: Base SSE URL of the MCP server.
        tool_name: Tool name to invoke on the server.
        args: Arguments dict for the tool call.
        token_path: Where to persist OAuth tokens. Defaults to ~/.agentforge/mcp_tokens/<slug>.json.

    Returns:
        The tool result (parsed content from the MCP response).
    """
    if token_path is None:
        token_path = _TOKEN_DIR / f"{_server_slug(server_url)}.json"

    storage = FileTokenStorage(token_path)

    port = _OAUTH_PORT
    redirect_uri = f"http://localhost:{port}/callback"

    # Start the callback server BEFORE beginning OAuth so the port is ready
    # by the time the user opens the authorization URL in the browser.
    callback_server, callback_future = await _start_callback_server(port)

    async def redirect_handler(url: str) -> None:
        print(
            "\n[MCP OAuth] Abra esta URL no navegador para autorizar:\n"
            f"  {url}\n"
            f"\nAguardando callback em {redirect_uri} ...\n",
            flush=True,
        )

    async def callback_handler() -> tuple[str, str | None]:
        return await asyncio.wait_for(callback_future, timeout=300.0)

    metadata = OAuthClientMetadata(
        redirect_uris=[redirect_uri],
        client_name="AgentForge",
        grant_types=["authorization_code"],
        response_types=["code"],
        token_endpoint_auth_method="none",
    )

    auth_provider = OAuthClientProvider(
        server_url=server_url,
        client_metadata=metadata,
        storage=storage,
        redirect_handler=redirect_handler,
        callback_handler=callback_handler,
    )

    logger.debug("mcp_client: connecting to %s, tool=%s", server_url, tool_name)

    try:
        async with streamablehttp_client(server_url, auth=auth_provider) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, args)
    finally:
        callback_server.close()
        await callback_server.wait_closed()

    # result.content is a list of content blocks (TextContent, etc.)
    if result.content:
        parts = []
        for block in result.content:
            if hasattr(block, "text"):
                parts.append(block.text)
            else:
                parts.append(str(block))
        return "\n".join(parts)
    return None


def call_mcp_tool(
    server_url: str,
    tool_name: str,
    args: dict[str, Any],
    token_path: Path | None = None,
) -> Any:
    """Synchronous wrapper around call_mcp_tool_async for use in AgentForge tools."""
    try:
        # Check if there's already a running event loop (e.g. Jupyter, async context).
        # If so, spawn a new thread with its own loop to avoid nesting.
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(
                    asyncio.run,
                    call_mcp_tool_async(server_url, tool_name, args, token_path),
                )
                return future.result(timeout=120)

        return asyncio.run(call_mcp_tool_async(server_url, tool_name, args, token_path))
    except Exception as exc:
        logger.error("mcp_client error: %s", exc)
        raise
