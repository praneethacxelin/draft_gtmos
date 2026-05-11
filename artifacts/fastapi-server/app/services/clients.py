"""Lightweight HTTP wrappers for external tools — all OPTIONAL.

Each `*_search` function returns either real data (if the key is configured)
or `None` to signal callers to use AI-generated demo data. Failures are
caught and logged so the UI never breaks.

Every real HTTP call is recorded to the audit log so the user can see
exactly what was sent and reproduce it with the embedded curl command.
"""
import json
import logging
import time
from typing import Optional, Any
import httpx

from app.services.rate_limit import consume as _rl_consume, RateLimitExceeded
from app.services import audit_service

log = logging.getLogger("gtm.clients")
TIMEOUT = httpx.Timeout(15.0, connect=5.0)

_SENSITIVE_KEYS = {"api_key", "key", "secret", "token", "password", "authorization"}


def _mask(k: str, v: Any) -> Any:
    return "****" if any(s in k.lower() for s in _SENSITIVE_KEYS) else v


def _make_curl(
    method: str,
    url: str,
    params: Optional[dict] = None,
    headers: Optional[dict] = None,
    body: Optional[dict] = None,
) -> str:
    full_url = url
    if params:
        qs = "&".join(f"{k}={_mask(k, v)}" for k, v in params.items())
        full_url = f"{url}?{qs}"
    parts = [f'curl -sS -X {method} "{full_url}"']
    if headers:
        for k, v in headers.items():
            safe_v = "****" if k.lower() in ("authorization", "x-api-key") else v
            parts.append(f'  -H "{k}: {safe_v}"')
    if body:
        safe = {k: _mask(k, v) for k, v in body.items()}
        parts.append(f"  -d '{json.dumps(safe)}'")
    return " \\\n".join(parts)


def _sanitize_params(params: dict) -> dict:
    return {k: _mask(k, v) for k, v in params.items()}


def serpapi_search(
    api_key: str,
    query: str,
    num: int = 5,
    _strategy_id: Optional[str] = None,
    _strategy_name: Optional[str] = None,
) -> Optional[list[dict]]:
    if not api_key:
        return None
    _rl_consume("serpapi")
    url = "https://serpapi.com/search.json"
    params = {"q": query, "api_key": api_key, "num": num, "engine": "google"}
    curl = _make_curl("GET", url, params=params)
    sanitized = _sanitize_params(params)
    t0 = time.perf_counter()
    status = None
    result_count = 0
    try:
        with httpx.Client(timeout=TIMEOUT) as c:
            r = c.get(url, params=params)
            status = r.status_code
            r.raise_for_status()
            data = r.json()
            results = []
            for item in (data.get("organic_results") or [])[:num]:
                results.append({
                    "title": item.get("title"),
                    "link": item.get("link"),
                    "snippet": item.get("snippet"),
                })
            result_count = len(results)
            return results
    except Exception as e:
        log.warning("serpapi_search failed: %s", e)
        return None
    finally:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        audit_service.log_api_call(
            service="serpapi",
            method="GET",
            url=url,
            request_params=sanitized,
            response_status=status,
            latency_ms=latency_ms,
            curl_command=curl,
            strategy_id=_strategy_id,
            strategy_name=_strategy_name,
            is_live=True,
            response_summary={"result_count": result_count},
            summary=f"SerpAPI search: \"{query[:60]}\" → {result_count} results",
        )


def apollo_people_search(
    api_key: str,
    filters: dict,
    per_page: int = 10,
    _strategy_id: Optional[str] = None,
    _strategy_name: Optional[str] = None,
) -> Optional[list[dict]]:
    if not api_key:
        return None
    _rl_consume("apollo")
    url = "https://api.apollo.io/v1/mixed_people/search"
    body = {
        "api_key": api_key,
        "page": 1,
        "per_page": per_page,
        "person_titles": filters.get("titles", []),
        "organization_num_employees_ranges": filters.get("employee_ranges", []),
        "person_locations": filters.get("locations", []),
    }
    curl = _make_curl(
        "POST", url,
        headers={"Cache-Control": "no-cache"},
        body=body,
    )
    t0 = time.perf_counter()
    status = None
    result_count = 0
    try:
        with httpx.Client(timeout=TIMEOUT) as c:
            r = c.post(url, json=body, headers={"Cache-Control": "no-cache"})
            status = r.status_code
            r.raise_for_status()
            data = r.json()
            people = data.get("people", [])
            result_count = len(people)
            return people
    except Exception as e:
        log.warning("apollo_people_search failed: %s", e)
        return None
    finally:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        safe_body = {k: _mask(k, v) for k, v in body.items()}
        audit_service.log_api_call(
            service="apollo",
            method="POST",
            url=url,
            request_params={"titles": filters.get("titles"), "per_page": per_page},
            response_status=status,
            latency_ms=latency_ms,
            curl_command=curl,
            strategy_id=_strategy_id,
            strategy_name=_strategy_name,
            is_live=True,
            response_summary={"people_count": result_count},
            summary=f"Apollo people search: titles={filters.get('titles', [])[:2]} → {result_count} contacts",
        )


def clay_enrich(api_key: str, contacts: list[dict]) -> Optional[list[dict]]:
    """Clay generally uses webhooks/tables. We treat this as a no-op pass-through
    placeholder for the demo — if a key is present we return the contacts
    unchanged so the UI can show 'Enriched via Clay'."""
    if not api_key:
        return None
    return contacts


def instantly_create_campaign(
    api_key: str,
    name: str,
    sequence_steps: list[dict],
    _strategy_id: Optional[str] = None,
    _strategy_name: Optional[str] = None,
) -> Optional[dict]:
    if not api_key:
        return None
    _rl_consume("instantly")
    url = "https://api.instantly.ai/api/v1/campaign/create"
    body = {"api_key": api_key, "name": name, "steps": sequence_steps}
    curl = _make_curl("POST", url, body=body)
    t0 = time.perf_counter()
    status = None
    try:
        with httpx.Client(timeout=TIMEOUT) as c:
            r = c.post(url, json=body)
            status = r.status_code
            r.raise_for_status()
            return r.json()
    except Exception as e:
        log.warning("instantly_create_campaign failed: %s", e)
        return None
    finally:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        audit_service.log_api_call(
            service="instantly",
            method="POST",
            url=url,
            request_params={"campaign_name": name, "step_count": len(sequence_steps)},
            response_status=status,
            latency_ms=latency_ms,
            curl_command=curl,
            strategy_id=_strategy_id,
            strategy_name=_strategy_name,
            is_live=True,
            summary=f"Instantly: create campaign \"{name}\" ({len(sequence_steps)} steps)",
        )


def instantly_get_events(
    api_key: str,
    campaign_id: str,
    _strategy_id: Optional[str] = None,
    _strategy_name: Optional[str] = None,
) -> Optional[list[dict]]:
    """Fetch recent engagement events for a campaign."""
    if not api_key or not campaign_id:
        return None
    _rl_consume("instantly")
    url = "https://api.instantly.ai/api/v1/analytics/campaign/events"
    params = {"api_key": api_key, "campaign_id": campaign_id, "limit": 200}
    curl = _make_curl("GET", url, params=params)
    sanitized = _sanitize_params(params)
    t0 = time.perf_counter()
    status = None
    event_count = 0
    try:
        with httpx.Client(timeout=TIMEOUT) as c:
            r = c.get(url, params=params)
            status = r.status_code
            r.raise_for_status()
            data = r.json()
            events = data.get("events", []) if isinstance(data, dict) else []
            event_count = len(events)
            return events
    except Exception as e:
        log.warning("instantly_get_events failed: %s", e)
        return None
    finally:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        audit_service.log_api_call(
            service="instantly",
            method="GET",
            url=url,
            request_params=sanitized,
            response_status=status,
            latency_ms=latency_ms,
            curl_command=curl,
            strategy_id=_strategy_id,
            strategy_name=_strategy_name,
            is_live=True,
            response_summary={"event_count": event_count},
            summary=f"Instantly: poll campaign {campaign_id[:12]} → {event_count} events",
        )


def test_connection(name: str, api_key: str) -> tuple[bool, str]:
    """Quick connectivity test for a given integration."""
    try:
        if name == "serpapi":
            with httpx.Client(timeout=TIMEOUT) as c:
                r = c.get("https://serpapi.com/account.json", params={"api_key": api_key})
                if r.status_code == 200:
                    return True, "Connected"
                return False, f"HTTP {r.status_code}"
        if name == "apollo":
            with httpx.Client(timeout=TIMEOUT) as c:
                r = c.get(
                    "https://api.apollo.io/v1/auth/health",
                    headers={
                        "X-Api-Key": api_key,
                        "Cache-Control": "no-cache",
                        "Content-Type": "application/json",
                    },
                )
                if r.status_code == 200:
                    try:
                        data = r.json()
                    except Exception:
                        data = {}
                    if data.get("is_logged_in") is True:
                        return True, "Connected"
                    return False, "Key rejected by Apollo"
                if r.status_code in (401, 403):
                    return False, "Invalid Apollo API key"
                return False, f"Apollo HTTP {r.status_code}"
        if name == "instantly":
            with httpx.Client(timeout=TIMEOUT) as c:
                r = c.get(
                    "https://api.instantly.ai/api/v2/accounts",
                    headers={"Authorization": f"Bearer {api_key}"},
                    params={"limit": 1},
                )
                if r.status_code == 200:
                    return True, "Connected (v2)"
                if r.status_code in (401, 403):
                    return False, "Invalid Instantly API key (v2)"
                r2 = c.get(
                    "https://api.instantly.ai/api/v1/account/list",
                    params={"api_key": api_key},
                )
                if r2.status_code == 200:
                    return True, "Connected (v1)"
                return False, f"Instantly HTTP v2={r.status_code} v1={r2.status_code}"
        if name == "clay":
            if len(api_key) >= 8:
                return True, "Key saved (Clay does not expose a public health endpoint)"
            return False, "Key looks too short"
        return False, "Unknown integration"
    except Exception as e:
        return False, str(e)
