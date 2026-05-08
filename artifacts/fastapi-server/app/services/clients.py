"""Lightweight HTTP wrappers for external tools — all OPTIONAL.

Each `*_search` function returns either real data (if the key is configured)
or `None` to signal callers to use AI-generated demo data. Failures are
caught and logged so the UI never breaks.
"""
import logging
from typing import Optional, Any
import httpx

from app.services.rate_limit import consume as _rl_consume, RateLimitExceeded

log = logging.getLogger("gtm.clients")
TIMEOUT = httpx.Timeout(15.0, connect=5.0)


def serpapi_search(api_key: str, query: str, num: int = 5) -> Optional[list[dict]]:
    if not api_key:
        return None
    _rl_consume("serpapi")
    try:
        with httpx.Client(timeout=TIMEOUT) as c:
            r = c.get(
                "https://serpapi.com/search.json",
                params={"q": query, "api_key": api_key, "num": num, "engine": "google"},
            )
            r.raise_for_status()
            data = r.json()
            results = []
            for item in (data.get("organic_results") or [])[:num]:
                results.append({
                    "title": item.get("title"),
                    "link": item.get("link"),
                    "snippet": item.get("snippet"),
                })
            return results
    except Exception as e:
        log.warning("serpapi_search failed: %s", e)
        return None


def apollo_people_search(api_key: str, filters: dict, per_page: int = 10) -> Optional[list[dict]]:
    if not api_key:
        return None
    _rl_consume("apollo")
    try:
        body = {
            "api_key": api_key,
            "page": 1,
            "per_page": per_page,
            "person_titles": filters.get("titles", []),
            "organization_num_employees_ranges": filters.get("employee_ranges", []),
            "person_locations": filters.get("locations", []),
        }
        with httpx.Client(timeout=TIMEOUT) as c:
            r = c.post(
                "https://api.apollo.io/v1/mixed_people/search",
                json=body,
                headers={"Cache-Control": "no-cache"},
            )
            r.raise_for_status()
            data = r.json()
            return data.get("people", [])
    except Exception as e:
        log.warning("apollo_people_search failed: %s", e)
        return None


def clay_enrich(api_key: str, contacts: list[dict]) -> Optional[list[dict]]:
    """Clay generally uses webhooks/tables. We treat this as a no-op pass-through
    placeholder for the demo — if a key is present we return the contacts
    unchanged so the UI can show 'Enriched via Clay'."""
    if not api_key:
        return None
    return contacts


def instantly_create_campaign(api_key: str, name: str, sequence_steps: list[dict]) -> Optional[dict]:
    if not api_key:
        return None
    _rl_consume("instantly")
    try:
        with httpx.Client(timeout=TIMEOUT) as c:
            r = c.post(
                "https://api.instantly.ai/api/v1/campaign/create",
                json={"api_key": api_key, "name": name, "steps": sequence_steps},
            )
            r.raise_for_status()
            return r.json()
    except Exception as e:
        log.warning("instantly_create_campaign failed: %s", e)
        return None


def instantly_get_events(api_key: str, campaign_id: str) -> Optional[list[dict]]:
    """Fetch recent engagement events for a campaign. Returns ``None`` on
    failure so callers can skip silently."""
    if not api_key or not campaign_id:
        return None
    _rl_consume("instantly")
    try:
        with httpx.Client(timeout=TIMEOUT) as c:
            r = c.get(
                "https://api.instantly.ai/api/v1/analytics/campaign/events",
                params={"api_key": api_key, "campaign_id": campaign_id, "limit": 200},
            )
            r.raise_for_status()
            data = r.json()
            return data.get("events", []) if isinstance(data, dict) else []
    except Exception as e:
        log.warning("instantly_get_events failed: %s", e)
        return None


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
            # Try Instantly v2 (Bearer auth) first, then fall back to v1.
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
                # Fallback to v1 query-param style for legacy keys.
                r2 = c.get(
                    "https://api.instantly.ai/api/v1/account/list",
                    params={"api_key": api_key},
                )
                if r2.status_code == 200:
                    return True, "Connected (v1)"
                return False, f"Instantly HTTP v2={r.status_code} v1={r2.status_code}"
        if name == "clay":
            # Clay does not have a simple health endpoint — treat presence as ok
            if len(api_key) >= 8:
                return True, "Key saved (Clay does not expose a public health endpoint)"
            return False, "Key looks too short"
        return False, "Unknown integration"
    except Exception as e:
        return False, str(e)
