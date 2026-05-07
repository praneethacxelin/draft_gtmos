"""Reverse-proxy for Clerk's Frontend API.

Replit's production build automatically sets VITE_CLERK_PROXY_URL to
/api/__clerk so that Clerk JS loads through the app domain.  This
route forwards those requests to the instance-specific Clerk FAPI domain
derived from CLERK_PUBLISHABLE_KEY, with the required Clerk-Proxy-Url
and Clerk-Secret-Key headers.
"""
import base64
import logging
import os
import traceback

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import Response

log = logging.getLogger("gtm.clerk_proxy")
router = APIRouter()

CLERK_PROXY_PATH = "/api/__clerk"

# Hop-by-hop headers that must not be forwarded
_HOP_HEADERS = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade",
    "content-encoding",
}


def _fapi_domain() -> str:
    """Derive the Clerk Frontend API domain from the publishable key.

    Format: pk_test_{base64(fapi_domain)} or pk_live_{base64(fapi_domain)}
    """
    key = os.environ.get("CLERK_PUBLISHABLE_KEY", "")
    parts = key.split("_", 2)
    if len(parts) != 3:
        return "clerk.accounts.dev"
    raw = parts[2].rstrip("$")
    # Restore base64 padding
    raw += "=" * (4 - len(raw) % 4)
    try:
        return base64.b64decode(raw).decode("utf-8").rstrip("$").strip()
    except Exception:
        return "clerk.accounts.dev"


@router.api_route(
    "/__clerk/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
)
async def clerk_proxy(path: str, request: Request) -> Response:
    try:
        return await _do_proxy(path, request)
    except Exception as exc:
        tb = traceback.format_exc()
        log.error("Clerk proxy error for path=%s: %s\n%s", path, exc, tb)
        return Response(
            status_code=502,
            content=f"Clerk proxy error: {exc}\n\n{tb}",
            media_type="text/plain",
        )


async def _do_proxy(path: str, request: Request) -> Response:
    secret_key = os.environ.get("CLERK_SECRET_KEY", "")
    if not secret_key:
        log.warning("CLERK_SECRET_KEY not set — Clerk proxy returning 503")
        return Response(status_code=503, content="Clerk proxy not configured")

    fapi = _fapi_domain()
    target_url = f"https://{fapi}/{path}"
    if request.url.query:
        target_url += f"?{request.url.query}"

    log.info("Clerk proxy: %s %s → %s", request.method, path, target_url)

    # Build Clerk-Proxy-Url from the incoming request
    proto = request.headers.get("x-forwarded-proto", "https")
    forwarded_host = request.headers.get("x-forwarded-host", "")
    host = (
        forwarded_host.split(",")[0].strip()
        if forwarded_host
        else request.headers.get("host", "")
    )
    proxy_url = f"{proto}://{host}{CLERK_PROXY_PATH}"

    # Determine whether this is a static npm bundle request.
    # npm/* paths need special handling: if we send Clerk-Proxy-Url,
    # FAPI will redirect BACK to our proxy (loop). Without it, FAPI
    # redirects to the versioned CDN URL which resolves correctly.
    is_npm_path = path.startswith("npm/")

    # Forward headers, stripping hop-by-hop. Don't carry over host —
    # httpx sets it correctly from the target URL.
    forward_headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in _HOP_HEADERS and k.lower() != "host"
    }
    if not is_npm_path:
        forward_headers["Clerk-Proxy-Url"] = proxy_url
        forward_headers["Clerk-Secret-Key"] = secret_key

    # Preserve client IP
    xff = request.headers.get("x-forwarded-for", "")
    client_ip = (
        xff.split(",")[0].strip()
        if xff
        else (request.client.host if request.client else "")
    )
    if client_ip:
        forward_headers["X-Forwarded-For"] = client_ip

    body = await request.body()

    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        upstream = await client.request(
            method=request.method,
            url=target_url,
            headers=forward_headers,
            content=body,
        )

    log.info("Clerk proxy upstream status: %s for %s", upstream.status_code, target_url)

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
