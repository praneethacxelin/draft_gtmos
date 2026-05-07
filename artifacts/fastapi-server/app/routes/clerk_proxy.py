"""Reverse-proxy for Clerk's Frontend API.

Replit's production build automatically sets VITE_CLERK_PROXY_URL to
/api/__clerk so that Clerk JS loads through the app domain.  This
route forwards those requests to https://frontend-api.clerk.dev with
the required Clerk-Proxy-Url and Clerk-Secret-Key headers.

Only active in production (NODE_ENV=production). In development Clerk
loads directly from the CDN — this bypass is intentional per Clerk docs.
"""
import os
import logging
import httpx
from fastapi import APIRouter, Request
from fastapi.responses import Response

log = logging.getLogger("gtm.clerk_proxy")

router = APIRouter()

CLERK_FAPI = "https://frontend-api.clerk.dev"
CLERK_PROXY_PATH = "/api/__clerk"

# Hop-by-hop headers that must not be forwarded
_HOP_HEADERS = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade",
    "content-encoding",  # httpx decodes for us
}


@router.api_route("/__clerk/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
async def clerk_proxy(path: str, request: Request) -> Response:
    secret_key = os.environ.get("CLERK_SECRET_KEY", "")
    if not secret_key:
        log.warning("CLERK_SECRET_KEY not set — Clerk proxy returning 503")
        return Response(status_code=503, content="Clerk proxy not configured")

    # Build Clerk-Proxy-Url from the incoming request
    proto = request.headers.get("x-forwarded-proto", "https")
    forwarded_host = request.headers.get("x-forwarded-host", "")
    host = forwarded_host.split(",")[0].strip() if forwarded_host else request.headers.get("host", "")
    proxy_url = f"{proto}://{host}{CLERK_PROXY_PATH}"

    # Forward headers, stripping hop-by-hop and injecting Clerk headers
    forward_headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in _HOP_HEADERS
    }
    forward_headers["Clerk-Proxy-Url"] = proxy_url
    forward_headers["Clerk-Secret-Key"] = secret_key

    # Preserve client IP
    xff = request.headers.get("x-forwarded-for", "")
    client_ip = xff.split(",")[0].strip() if xff else (request.client.host if request.client else "")
    if client_ip:
        forward_headers["X-Forwarded-For"] = client_ip

    target_url = f"{CLERK_FAPI}/{path}"
    if request.url.query:
        target_url += f"?{request.url.query}"

    body = await request.body()

    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        upstream = await client.request(
            method=request.method,
            url=target_url,
            headers=forward_headers,
            content=body,
        )

    response_headers = {
        k: v for k, v in upstream.headers.items()
        if k.lower() not in _HOP_HEADERS
    }

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=response_headers,
        media_type=upstream.headers.get("content-type"),
    )
