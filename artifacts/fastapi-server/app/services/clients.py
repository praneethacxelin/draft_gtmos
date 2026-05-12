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
TIMEOUT = httpx.Timeout(20.0, connect=5.0)

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


def _truncate(obj: Any, max_len: int = 3000) -> str:
    """Serialize obj to a string, truncated if needed."""
    try:
        s = json.dumps(obj, default=str)
    except Exception:
        s = str(obj)
    return s[:max_len] + ("…" if len(s) > max_len else "")


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
    results = []
    error_text: Optional[str] = None
    try:
        with httpx.Client(timeout=TIMEOUT) as c:
            r = c.get(url, params=params)
            status = r.status_code
            r.raise_for_status()
            data = r.json()
            for item in (data.get("organic_results") or [])[:num]:
                results.append({
                    "title": item.get("title"),
                    "link": item.get("link"),
                    "snippet": item.get("snippet"),
                })
            result_count = len(results)
            return results
    except Exception as e:
        error_text = str(e)
        log.warning("serpapi_search failed: %s", e)
        return None
    finally:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        summary_payload: dict = {"result_count": result_count}
        if results:
            summary_payload["results_preview"] = [
                {"title": r.get("title", ""), "snippet": (r.get("snippet") or "")[:120]}
                for r in results[:3]
            ]
        if error_text:
            summary_payload["error"] = error_text[:500]
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
            response_summary=summary_payload,
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
        headers={"Content-Type": "application/json", "Cache-Control": "no-cache"},
        body=body,
    )
    t0 = time.perf_counter()
    status = None
    result_count = 0
    people: list[dict] = []
    error_text: Optional[str] = None
    raw_response_preview: Optional[str] = None
    try:
        with httpx.Client(timeout=TIMEOUT) as c:
            r = c.post(url, json=body, headers={"Content-Type": "application/json", "Cache-Control": "no-cache"})
            status = r.status_code
            raw_response_preview = r.text[:2000]
            r.raise_for_status()
            data = r.json()
            people = data.get("people", [])
            result_count = len(people)
            return people
    except Exception as e:
        error_text = str(e)
        log.warning("apollo_people_search failed: %s", e)
        return None
    finally:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        summary_payload: dict = {"people_count": result_count}
        if people:
            summary_payload["contacts_preview"] = [
                {
                    "name": _person_name(p),
                    "title": p.get("title", ""),
                    "company": (p.get("organization") or {}).get("name", ""),
                    "email": p.get("email") or "(not revealed)",
                }
                for p in people[:5]
            ]
        if error_text:
            summary_payload["error"] = error_text[:500]
        if raw_response_preview and status and status >= 400:
            summary_payload["response_body"] = raw_response_preview
        audit_service.log_api_call(
            service="apollo",
            method="POST",
            url=url,
            request_params={
                "titles": filters.get("titles"),
                "employee_ranges": filters.get("employee_ranges"),
                "per_page": per_page,
            },
            response_status=status,
            latency_ms=latency_ms,
            curl_command=curl,
            strategy_id=_strategy_id,
            strategy_name=_strategy_name,
            is_live=True,
            response_summary=summary_payload,
            summary=f"Apollo people search: titles={filters.get('titles', [])[:2]} → {result_count} contacts",
        )


def _person_name(p: dict) -> str:
    """Extract full name from an Apollo person dict, handling multiple formats."""
    if p.get("name"):
        return p["name"]
    first = (p.get("first_name") or "").strip()
    last = (p.get("last_name") or "").strip()
    combined = f"{first} {last}".strip()
    return combined or "Unknown"


def apollo_match_person(
    api_key: str,
    name: str,
    org_name: Optional[str] = None,
    domain: Optional[str] = None,
    reveal_phone: bool = False,
    _strategy_id: Optional[str] = None,
    _strategy_name: Optional[str] = None,
) -> Optional[dict]:
    """Match a single person by name + company and optionally reveal email or phone.

    Apollo `/v1/people/match` always returns the work email when it can be
    found without a personal email reveal credit. Set ``reveal_phone=True``
    to request phone numbers (costs an Apollo phone credit per call).
    """
    if not api_key:
        return None
    _rl_consume("apollo")
    url = "https://api.apollo.io/v1/people/match"
    body: dict = {
        "api_key": api_key,
        "name": name,
        "reveal_personal_emails": False,
        "reveal_phone_number": reveal_phone,
    }
    if org_name:
        body["organization_name"] = org_name
    if domain:
        body["domain"] = domain

    curl = _make_curl(
        "POST", url,
        headers={"Content-Type": "application/json", "Cache-Control": "no-cache"},
        body=body,
    )
    t0 = time.perf_counter()
    status = None
    person: Optional[dict] = None
    error_text: Optional[str] = None
    raw_response_preview: Optional[str] = None
    try:
        with httpx.Client(timeout=TIMEOUT) as c:
            r = c.post(url, json=body, headers={"Content-Type": "application/json", "Cache-Control": "no-cache"})
            status = r.status_code
            raw_response_preview = r.text[:2000]
            r.raise_for_status()
            data = r.json()
            person = data.get("person") or None
            return person
    except Exception as e:
        error_text = str(e)
        log.warning("apollo_match_person failed for %s: %s", name, e)
        return None
    finally:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        kind = "phone reveal" if reveal_phone else "email reveal"
        summary_payload: dict = {
            "name": name,
            "org_name": org_name or "",
            "reveal_phone": reveal_phone,
        }
        if person:
            summary_payload["matched_email"] = person.get("email") or "(none)"
            if reveal_phone:
                phones = person.get("phone_numbers") or []
                summary_payload["matched_phones"] = [p.get("raw_number", "") for p in phones[:3]]
        if error_text:
            summary_payload["error"] = error_text[:500]
        if raw_response_preview and status and status >= 400:
            summary_payload["response_body"] = raw_response_preview
        audit_service.log_api_call(
            service="apollo",
            method="POST",
            url=url,
            request_params={"name": name, "org_name": org_name or "", "reveal_phone": reveal_phone},
            response_status=status,
            latency_ms=latency_ms,
            curl_command=curl,
            strategy_id=_strategy_id,
            strategy_name=_strategy_name,
            is_live=True,
            response_summary=summary_payload,
            summary=f"Apollo {kind}: {name} @ {org_name or '?'} → {'found' if person else 'not found'}",
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
    result: Optional[dict] = None
    error_text: Optional[str] = None
    raw_response_preview: Optional[str] = None
    try:
        with httpx.Client(timeout=TIMEOUT) as c:
            r = c.post(url, json=body)
            status = r.status_code
            raw_response_preview = r.text[:1000]
            r.raise_for_status()
            result = r.json()
            return result
    except Exception as e:
        error_text = str(e)
        log.warning("instantly_create_campaign failed: %s", e)
        return None
    finally:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        summary_payload: dict = {"campaign_name": name, "step_count": len(sequence_steps)}
        if result:
            summary_payload["campaign_id"] = result.get("id") or result.get("campaign_id", "")
        if error_text:
            summary_payload["error"] = error_text[:500]
        if raw_response_preview and status and status >= 400:
            summary_payload["response_body"] = raw_response_preview
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
            response_summary=summary_payload,
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
    error_text: Optional[str] = None
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
        error_text = str(e)
        log.warning("instantly_get_events failed: %s", e)
        return None
    finally:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        summary_payload: dict = {"event_count": event_count}
        if error_text:
            summary_payload["error"] = error_text[:500]
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
            response_summary=summary_payload,
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
