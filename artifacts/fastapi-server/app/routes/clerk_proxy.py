"""Reverse-proxy for Clerk's Frontend API.

Mirrors the reference implementation from the clerk-auth skill
(`clerkProxyMiddleware.ts`):

- Target is the multiplex endpoint `frontend-api.clerk.dev`. Clerk
  identifies the tenant from the `Clerk-Proxy-Url` header, NOT from the
  hostname. Do not target the per-instance FAPI domain — it breaks
  proxy mode for live (satellite) keys.
- `Clerk-Proxy-Url` and `Clerk-Secret-Key` are set on every request,
  including `npm/*` paths.
- Redirects are NOT followed — they are passed straight through to the
  browser, which re-fetches via this proxy at the new path. Following
  redirects server-side causes an infinite loop because FAPI redirects
  the npm path back to the proxy URL.
"""
import logging
import os
import traceback

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import Response

log = logging.getLogger("gtm.clerk_proxy")
router = APIRouter()

CLERK_FAPI = "https://frontend-api.clerk.dev"
CLERK_PROXY_PATH = "/api/__clerk"

# Hop-by-hop and content-encoding headers that must not be forwarded.
_HOP_HEADERS = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade",
    "content-encoding", "content-length",
}


@router.api_route(
    "/__clerk/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
)
async def clerk_proxy(path: str, request: Request) -> Response:
    try:
        return await _do_proxy(path, request)
    except Exception as exc:
        log.error(
            "Clerk proxy error for path=%s: %s\n%s",
            path, exc, traceback.format_exc(),
        )
        return Response(
            status_code=502,
            content="Clerk proxy upstream error",
            media_type="text/plain",
        )


async def _do_proxy(path: str, request: Request) -> Response:
    secret_key = os.environ.get("CLERK_SECRET_KEY", "")
    if not secret_key:
        log.warning("CLERK_SECRET_KEY not set — Clerk proxy returning 503")
        return Response(status_code=503, content="Clerk proxy not configured")

    target_url = f"{CLERK_FAPI}/{path}"
    if request.url.query:
        target_url += f"?{request.url.query}"

    # Build Clerk-Proxy-Url from the public-facing host of the incoming
    # request. x-forwarded-host's leftmost value is the original client-
    # facing host when behind multiple proxies.
    proto = request.headers.get("x-forwarded-proto", "https")
    forwarded_host = request.headers.get("x-forwarded-host", "")
    host = (
        forwarded_host.split(",")[0].strip()
        if forwarded_host
        else request.headers.get("host", "")
    )
    proxy_url = f"{proto}://{host}{CLERK_PROXY_PATH}"

    # Forward request headers, dropping hop-by-hop and host. httpx will
    # set Host correctly from target_url.
    forward_headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in _HOP_HEADERS and k.lower() != "host"
    }
    forward_headers["Clerk-Proxy-Url"] = proxy_url
    forward_headers["Clerk-Secret-Key"] = secret_key

    # Preserve client IP for Clerk's bot/risk detection.
    xff = request.headers.get("x-forwarded-for", "")
    client_ip = (
        xff.split(",")[0].strip()
        if xff
        else (request.client.host if request.client else "")
    )
    if client_ip:
        forward_headers["X-Forwarded-For"] = client_ip

    body = await request.body()

    # CRITICAL: follow_redirects=False. Clerk redirects npm paths back
    # to the proxy URL with a versioned path. Following the redirect
    # server-side causes an infinite loop. The browser must follow it.
    async with httpx.AsyncClient(follow_redirects=False, timeout=30.0) as client:
        upstream = await client.request(
            method=request.method,
            url=target_url,
            headers=forward_headers,
            content=body,
        )

    log.info(
        "Clerk proxy: %s %s → %s (%s)",
        request.method, path, target_url, upstream.status_code,
    )

    response_headers = {
        k: v
        for k, v in upstream.headers.items()
        if k.lower() not in _HOP_HEADERS
    }

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=response_headers,
        media_type=upstream.headers.get("content-type"),
    )
