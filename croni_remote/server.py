"""Authenticated Streamable HTTP MCP entry point for Croni Call."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress
import secrets
import time
from typing import AsyncIterator

from pydantic import AnyHttpUrl
from starlette.requests import Request
from starlette.responses import JSONResponse

from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from .config import RemoteConfig
from .policy import CallPolicy
from .service import CallGateway
from .worker import PhoneWorker

REQUIRED_SCOPE = "croni:call"


class StaticTokenVerifier(TokenVerifier):
    """Single-user bootstrap auth; replaceable with OAuth token introspection."""

    def __init__(self, expected_token: str, resource_url: str):
        self._expected_token = expected_token
        self._resource_url = resource_url

    async def verify_token(self, token: str) -> AccessToken | None:
        if not secrets.compare_digest(token, self._expected_token):
            return None
        return AccessToken(
            token=token,
            client_id="croni-single-user",
            scopes=[REQUIRED_SCOPE],
            expires_at=int(time.time()) + 3600,
            resource=self._resource_url,
            subject="yolie",
        )


def build_server(config: RemoteConfig, gateway: CallGateway | None = None) -> MCPServer:
    worker = None
    if gateway is None:
        worker = PhoneWorker()
        gateway = CallGateway(CallPolicy(config), worker)

    @asynccontextmanager
    async def lifespan(_: MCPServer) -> AsyncIterator[dict[str, CallGateway]]:
        task = asyncio.create_task(gateway.watchdog(), name="croni-call-watchdog")
        try:
            yield {"gateway": gateway}
        finally:
            gateway.stop()
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
            if gateway.policy.status()["active"]:
                with suppress(Exception):
                    await gateway.call_end()
            if worker is not None:
                worker.close()

    mcp = MCPServer(
        "croni-call",
        title="Croni Call",
        version="0.1.0",
        instructions=(
            "Use call_start only when Yolie explicitly asks for a phone call or an "
            "already-authorized automation requires one. The callee is fixed by the "
            "server and cannot be supplied by a tool call. Keep each spoken turn to "
            "one or two short sentences. Respect blocked results, never retry them "
            "immediately, and always call call_end when the conversation finishes."
        ),
        token_verifier=StaticTokenVerifier(config.bearer_token, config.resource_url),
        auth=AuthSettings(
            issuer_url=AnyHttpUrl(config.auth_issuer_url),
            resource_server_url=AnyHttpUrl(config.resource_url),
            required_scopes=[REQUIRED_SCOPE],
            validate_token_resource=True,
        ),
        lifespan=lifespan,
    )

    @mcp.tool(description="Ring Yolie's fixed SIP account, speak one short opening line, and return her reply.")
    async def call_start(opening_line: str) -> dict:
        return await gateway.call_start(opening_line)

    @mcp.tool(description="On the active call, speak one short reply and listen for Yolie's next words.")
    async def converse(text: str) -> dict:
        return await gateway.converse(text)

    @mcp.tool(description="End the active call, optionally after speaking one short closing line.")
    async def call_end(closing_line: str = "") -> dict:
        return await gateway.call_end(closing_line)

    @mcp.tool(description="Return non-sensitive call and policy status. This never starts a call.")
    async def call_status() -> dict:
        return await gateway.call_status()

    @mcp.custom_route("/healthz", methods=["GET"], include_in_schema=False)
    async def healthz(_: Request) -> JSONResponse:
        return JSONResponse({"status": "ok"})

    return mcp


def main() -> None:
    config = RemoteConfig.from_env()
    mcp = build_server(config)
    security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=list(config.allowed_hosts),
        allowed_origins=list(config.allowed_origins),
    )
    mcp.run(
        transport="streamable-http",
        host=config.host,
        port=config.port,
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
        max_request_body_size=64 * 1024,
        transport_security=security,
    )


if __name__ == "__main__":
    main()
