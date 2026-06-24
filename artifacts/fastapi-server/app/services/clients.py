"""Lightweight HTTP wrappers for external tools — all OPTIONAL.

Each `*_search` function returns either real data (if the key is configured)
or `None` to signal callers to use AI-generated demo data. Failures are
caught and logged so the UI never breaks.

Every real HTTP call is recorded to the audit log so the user can see
exactly what was sent and reproduce it with the embedded curl command.
"""
import json
import logging
import re
import time
from typing import Optional, Any
from urllib.parse import urlparse
import httpx

from app.services.rate_limit import consume as _rl_consume, RateLimitExceeded
from app.services import audit_service
from app.services import apollo_store

log = logging.getLogger("gtm.clients")
TIMEOUT = httpx.Timeout(20.0, connect=5.0)

_SENSITIVE_KEYS = {"api_key", "key", "secret", "token", "password", "authorization"}

_TECH_UID_ALIASES = {
    "google analytics": "google_analytics",
    "google tag manager": "google_tag_manager",
    "google workspace": "google_apps",
    "g suite": "google_apps",
    "salesforce crm": "salesforce",
    "salesforce": "salesforce",
    "hubspot crm": "hubspot",
    "hubspot": "hubspot",
    "zendesk support": "zendesk",
    "zendesk": "zendesk",
    "intercom": "intercom",
    "freshdesk": "freshdesk",
    "shopify plus": "shopify",
    "shopify": "shopify",
    "woocommerce": "woocommerce",
    "magento": "magento",
    "mailchimp": "mailchimp",
    "marketo": "marketo",
    "pardot": "pardot",
    "slack": "slack",
    "jira": "jira",
    "atlassian": "atlassian",
    "stripe": "stripe",
    "quickbooks": "quickbooks",
    "xero": "xero",
    "workday": "workday",
    "servicenow": "servicenow",
}
_TECH_UID_CACHE: dict[str, str | None] = {}


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
def apollo_org_domain(org: dict | None) -> Optional[str]:
    """Extract a clean website/domain from an Apollo organization payload."""
    if not org:
        return None
    raw = (
        org.get("primary_domain")
        or org.get("domain")
        or org.get("website_url")
        or org.get("website")
    )
    if not raw or not isinstance(raw, str):
        return None
    parsed = urlparse(raw.strip() if "://" in raw else f"https://{raw.strip()}")
    host = (parsed.netloc or parsed.path).strip().lower()
    host = host.split("/")[0].removeprefix("www.")
    return host or None


def _technology_uid_fallback(name: str) -> str | None:
    clean = re.sub(r"\s+", " ", str(name or "").strip().lower())
    if not clean or clean in {"crm", "helpdesk", "help desk", "analytics", "marketing automation"}:
        return None
    if clean in _TECH_UID_ALIASES:
        return _TECH_UID_ALIASES[clean]
    slug = re.sub(r"[^a-z0-9]+", "_", clean).strip("_")
    return slug or None


def _extract_technology_uid(payload: dict, wanted: str) -> str | None:
    wanted_key = re.sub(r"[^a-z0-9]+", "", wanted.lower())
    items = (
        payload.get("tags")
        or payload.get("technologies")
        or payload.get("results")
        or payload.get("data")
        or []
    )
    if isinstance(items, dict):
        items = items.get("items") or items.get("results") or []
    if not isinstance(items, list):
        return None
    for item in items:
        if not isinstance(item, dict):
            continue
        label = str(item.get("name") or item.get("label") or item.get("display_name") or "")
        uid = item.get("uid") or item.get("id") or item.get("value")
        label_key = re.sub(r"[^a-z0-9]+", "", label.lower())
        if uid and (label_key == wanted_key or wanted_key in label_key or label_key in wanted_key):
            return str(uid)
    return None


def apollo_resolve_technology_uids(
    api_key: str,
    names: list[str],
    _strategy_id: Optional[str] = None,
    _strategy_name: Optional[str] = None,
) -> list[str]:
    """Resolve technology display names into Apollo technology UIDs."""
    if not api_key or not names:
        return []
    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
        "X-Api-Key": api_key,
    }
    endpoints = [
        "https://api.apollo.io/api/v1/tags/search",
        "https://api.apollo.io/api/v1/technologies/search",
    ]
    resolved: list[str] = []
    lookup_notes: list[dict] = []
    status = None
    t0 = time.perf_counter()

    with httpx.Client(timeout=TIMEOUT) as c:
        for raw_name in names[:8]:
            name = str(raw_name or "").strip()
            if not name:
                continue
            cache_key = name.lower()
            uid = _TECH_UID_CACHE.get(cache_key)
            source = "cache" if cache_key in _TECH_UID_CACHE else None
            if cache_key not in _TECH_UID_CACHE:
                for url in endpoints:
                    try:
                        _rl_consume("apollo")
                        r = c.get(url, params={"q": name, "kind": "technology"}, headers=headers)
                        status = r.status_code
                        if r.status_code == 404:
                            continue
                        r.raise_for_status()
                        uid = _extract_technology_uid(r.json(), name)
                        if uid:
                            source = url.rsplit("/", 1)[-1]
                            break
                    except Exception as e:
                        log.debug("Apollo technology lookup failed for %s: %s", name, e)
                        continue
                if not uid:
                    uid = _technology_uid_fallback(name)
                    source = "slug_alias" if uid else "unresolved"
                _TECH_UID_CACHE[cache_key] = uid
            if uid and uid not in resolved:
                resolved.append(uid)
            lookup_notes.append({"input": name, "uid": uid, "source": source})

    audit_service.log_api_call(
        service="apollo",
        method="GET",
        url="technology_uid_resolution",
        request_params={"technologies": names[:8]},
        response_status=status,
        latency_ms=int((time.perf_counter() - t0) * 1000),
        curl_command=None,
        strategy_id=_strategy_id,
        strategy_name=_strategy_name,
        is_live=True,
        response_summary={"resolved": lookup_notes},
        summary=f"Apollo technology UID resolution: {len(resolved)}/{len(names[:8])} resolved",
    )
    return resolved


# Authoritative domains whose data we trust for market sizing, signals, etc.
TRUSTED_DOMAINS = {
    # Market research & data
    "statista.com", "grandviewresearch.com", "ibisworld.com", "mordorintelligence.com",
    "marketsandmarkets.com", "fortunebusinessinsights.com", "precedenceresearch.com",
    "alliedmarketresearch.com", "researchandmarkets.com", "emergenresearch.com",
    # Analyst / advisory
    "gartner.com", "forrester.com", "mckinsey.com", "bcg.com", "bain.com", "deloitte.com",
    "pwc.com", "ey.com", "kpmg.com", "accenture.com",
    # Business news
    "bloomberg.com", "reuters.com", "cnbc.com", "ft.com", "wsj.com", "forbes.com",
    "businessinsider.com", "techcrunch.com", "venturebeat.com", "crunchbase.com",
    # Professional / B2B
    "linkedin.com", "g2.com", "capterra.com", "trustradius.com",
    # Government / authoritative
    "census.gov", "bls.gov", "sec.gov", "europa.eu",
    # Tech / SaaS
    "saastr.com", "openviewpartners.com", "tomtunguz.com",
}


def _is_trusted_source(link: str) -> bool:
    """Check if a URL belongs to a trusted/authoritative domain."""
    if not link:
        return False
    try:
        from urllib.parse import urlparse
        domain = urlparse(link).netloc.lower().lstrip("www.")
        return any(domain == td or domain.endswith("." + td) for td in TRUSTED_DOMAINS)
    except Exception:
        return False


def serpapi_search(
    api_key: str,
    query: str,
    num: int = 5,
    geo: Optional[str] = None,
    _strategy_id: Optional[str] = None,
    _strategy_name: Optional[str] = None,
) -> Optional[list[dict]]:
    if not api_key:
        return None
    _rl_consume("serpapi")
    url = "https://serpapi.com/search.json"
    params = {"q": query, "api_key": api_key, "num": num, "engine": "google"}
    if geo:
        params["gl"] = geo  # Google country code, e.g. "in" for India, "us" for USA
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
            for item in (data.get("organic_results") or [])[:num * 2]:  # fetch extra for filtering
                link = item.get("link", "")
                verified = _is_trusted_source(link)
                results.append({
                    "title": item.get("title"),
                    "link": link,
                    "snippet": item.get("snippet"),
                    "verified": verified,
                })
            # Prioritize trusted sources: put verified first, then unverified
            trusted = [r for r in results if r.get("verified")]
            untrusted = [r for r in results if not r.get("verified")]
            results = (trusted + untrusted)[:num]
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
    page: int = 1,
    enrich: bool = True,
    _strategy_id: Optional[str] = None,
    _strategy_name: Optional[str] = None,
) -> Optional[list[dict]]:
    """Search Apollo for people matching filters, then enrich via bulk_match.

    Step 1: ``/api/v1/mixed_people/api_search`` — free search, returns
    partial profiles (no credits consumed).
    Step 2: ``/api/v1/people/bulk_match`` — enrich found IDs to reveal
    emails (costs credits per reveal). Skipped when ``enrich=False`` so a
    caller (e.g. accounts-first discovery) can map the company universe
    without spending Apollo credits.

    The old ``/v1/mixed_people/search`` endpoint was deprecated and now
    returns 403/422 on newer API tokens.
    """
    if not api_key:
        return None
    _rl_consume("apollo")
    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
        "X-Api-Key": api_key,
    }

    # ---- Step 1: Search (0 credits) ----
    search_url = "https://api.apollo.io/api/v1/mixed_people/api_search"
    search_body = {
        "page": page,
        "per_page": per_page,
        "person_titles": filters.get("titles", []),
        "organization_num_employees_ranges": filters.get("employee_ranges", []),
        "person_locations": filters.get("locations", []),
    }
    # Add seniority filter (AI-selected decision-maker levels)
    if filters.get("seniorities"):
        search_body["person_seniorities"] = filters["seniorities"]
    # Scope the search to specific company domains (used when pulling contacts
    # for a hand-picked set of already-discovered accounts).
    if filters.get("organization_domains"):
        doms = [str(d).strip() for d in filters["organization_domains"] if str(d).strip()]
        if doms:
            search_body["q_organization_domains_list"] = doms
    # Add optional industry filter
    if filters.get("industries"):
        search_body["organization_industries"] = filters["industries"]
    # Add technology filter (find companies using specific tools)
    if filters.get("technologies"):
        search_body["currently_using_any_of_technology_uids"] = filters["technologies"]
    # Add revenue range filter
    if filters.get("revenue_ranges"):
        search_body["organization_revenue_ranges"] = filters["revenue_ranges"]
    # Add free-text keyword filter (q_keywords) — broadens reach to buyers
    # whose role/company context matches even when firmographics are sparse.
    if filters.get("keywords"):
        kw = filters["keywords"]
        if isinstance(kw, list):
            kw = " ".join(str(k).strip() for k in kw if str(k).strip())
        if kw and str(kw).strip():
            search_body["q_keywords"] = str(kw).strip()

    curl = _make_curl("POST", search_url, headers=headers, body=search_body)
    t0 = time.perf_counter()
    status = None
    result_count = 0
    people: list[dict] = []
    error_text: Optional[str] = None
    raw_response_preview: Optional[str] = None
    try:
        with httpx.Client(timeout=TIMEOUT) as c:
            r = c.post(search_url, json=search_body, headers=headers)
            status = r.status_code
            raw_response_preview = r.text[:2000]
            r.raise_for_status()
            data = r.json()
            search_results = data.get("people", [])
            if not search_results:
                result_count = 0
                return []

            # ---- Step 2: Enrich via bulk_match (costs credits) ----
            # Extract IDs from search results for enrichment
            person_ids = [p.get("id") for p in search_results if p.get("id")]
            if enrich and person_ids:
                _rl_consume("apollo")
                match_url = "https://api.apollo.io/api/v1/people/bulk_match"
                match_body = {
                    "details": [{"id": pid} for pid in person_ids[:per_page]],
                    "reveal_personal_emails": False,
                    "reveal_phone_number": False,
                }
                mr = c.post(match_url, json=match_body, headers=headers)
                if mr.status_code == 200:
                    match_data = mr.json()
                    # bulk_match returns enriched person objects in "matches"
                    people = match_data.get("matches", [])
                    # Filter out None entries (unmatched)
                    people = [p for p in people if p is not None]
                else:
                    # Fallback: use the search results as-is (partial data)
                    log.warning("Apollo bulk_match returned %d, using search results", mr.status_code)
                    people = search_results
            else:
                people = search_results

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
            url=search_url,
            request_params={
                "titles": filters.get("titles"),
                "employee_ranges": filters.get("employee_ranges"),
                "locations": filters.get("locations"),
                "seniorities": filters.get("seniorities"),
                "industries": filters.get("industries"),
                "technologies": filters.get("technologies"),
                "revenue_ranges": filters.get("revenue_ranges"),
                "keywords": filters.get("keywords"),
                "per_page": per_page,
                "apollo_search_body": search_body,
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
        # Silent capture: mirror everything Apollo returned into our own store.
        if people:
            apollo_store.capture_people(people, endpoint="people_search", strategy_id=_strategy_id)


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
    linkedin_url: Optional[str] = None,
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
    url = "https://api.apollo.io/api/v1/people/match"
    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
        "X-Api-Key": api_key,
    }
    body: dict = {
        "name": name,
        "reveal_personal_emails": False,
        "reveal_phone_number": reveal_phone,
    }
    if org_name:
        body["organization_name"] = org_name
    if domain:
        body["domain"] = domain
    if linkedin_url:
        body["linkedin_url"] = linkedin_url
    name_parts = [part for part in name.split(" ") if part]
    if len(name_parts) >= 2:
        body["first_name"] = name_parts[0]
        body["last_name"] = name_parts[-1]

    curl = _make_curl(
        "POST", url,
        headers=headers,
        body=body,
    )
    t0 = time.perf_counter()
    status = None
    person: Optional[dict] = None
    error_text: Optional[str] = None
    raw_response_preview: Optional[str] = None
    try:
        with httpx.Client(timeout=TIMEOUT) as c:
            r = c.post(url, json=body, headers=headers)
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
            request_params={
                "name": name,
                "org_name": org_name or "",
                "domain": domain or "",
                "linkedin_url": bool(linkedin_url),
                "reveal_phone": reveal_phone,
            },
            response_status=status,
            latency_ms=latency_ms,
            curl_command=curl,
            strategy_id=_strategy_id,
            strategy_name=_strategy_name,
            is_live=True,
            response_summary=summary_payload,
            summary=f"Apollo {kind}: {name} @ {org_name or '?'} → {'found' if person else 'not found'}",
        )
        # Silent capture: mirror the matched person (incl. revealed email).
        if person:
            apollo_store.capture_person(person, endpoint="people_match", strategy_id=_strategy_id)


def apollo_bulk_reveal(
    api_key: str,
    person_ids: list[str],
    reveal_personal: bool = False,
    _strategy_id: Optional[str] = None,
    _strategy_name: Optional[str] = None,
) -> dict[str, dict]:
    """Reveal work emails for a set of Apollo person IDs via ``/people/bulk_match``.

    Matching by the Apollo person ``id`` we captured during the (free) people
    search is far more reliable than re-matching by name, and it returns the
    work email when the account's plan includes it. Returns a mapping of
    ``person_id -> matched person dict`` (only entries Apollo could match).
    """
    out: dict[str, dict] = {}
    if not api_key or not person_ids:
        return out
    url = "https://api.apollo.io/api/v1/people/bulk_match"
    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
        "X-Api-Key": api_key,
    }
    # Apollo caps bulk_match at 10 records per call.
    for start in range(0, len(person_ids), 10):
        chunk = [pid for pid in person_ids[start : start + 10] if pid]
        if not chunk:
            continue
        _rl_consume("apollo")
        body = {
            "details": [{"id": pid} for pid in chunk],
            "reveal_personal_emails": reveal_personal,
            "reveal_phone_number": False,
        }
        curl = _make_curl("POST", url, headers=headers, body=body)
        t0 = time.perf_counter()
        status = None
        matched = 0
        error_text: Optional[str] = None
        raw_response_preview: Optional[str] = None
        try:
            with httpx.Client(timeout=TIMEOUT) as c:
                r = c.post(url, json=body, headers=headers)
                status = r.status_code
                raw_response_preview = r.text[:2000]
                r.raise_for_status()
                data = r.json()
                matches = data.get("matches", []) or []
                for p in matches:
                    if not p:
                        continue
                    pid = p.get("id")
                    if pid:
                        out[str(pid)] = p
                        matched += 1
                # Positional fallback: align matches to the chunk order when
                # Apollo does not echo the queried id back on each match.
                if matched == 0:
                    for pid, p in zip(chunk, matches):
                        if p:
                            out[str(pid)] = p
                            matched += 1
        except Exception as e:
            error_text = str(e)
            log.warning("apollo_bulk_reveal failed: %s", e)
        finally:
            latency_ms = int((time.perf_counter() - t0) * 1000)
            summary_payload: dict = {"requested": len(chunk), "matched": matched}
            if error_text:
                summary_payload["error"] = error_text[:500]
            if raw_response_preview and status and status >= 400:
                summary_payload["response_body"] = raw_response_preview
            audit_service.log_api_call(
                service="apollo",
                method="POST",
                url=url,
                request_params={"ids": chunk, "reveal_personal_emails": reveal_personal},
                response_status=status,
                latency_ms=latency_ms,
                curl_command=curl,
                strategy_id=_strategy_id,
                strategy_name=_strategy_name,
                is_live=True,
                response_summary=summary_payload,
                summary=f"Apollo bulk email reveal: {len(chunk)} ids → {matched} matched",
            )
    # Silent capture: mirror all revealed people (incl. work emails).
    if out:
        apollo_store.capture_people(list(out.values()), endpoint="bulk_match", strategy_id=_strategy_id)
    return out


def clay_enrich(api_key: str, contacts: list[dict]) -> Optional[list[dict]]:
    """Clay generally uses webhooks/tables. We treat this as a no-op pass-through
    placeholder for the demo — if a key is present we return the contacts
    unchanged so the UI can show 'Enriched via Clay'."""
    if not api_key:
        return None
    return contacts


# ---------------------------------------------------------------------------
# Timezone normalisation for Instantly v2
# Instantly only accepts specific IANA timezone strings. Windows (and some
# browsers) emit deprecated aliases like "Asia/Calcutta" or legacy zone IDs
# like "US/Eastern". This map converts known bad values to accepted ones and
# we fall back to "UTC" for anything we can't recognise.
# ---------------------------------------------------------------------------
_INSTANTLY_TZ_ALIASES: dict[str, str] = {
    # Indian subcontinent
    "Asia/Calcutta":         "Asia/Kolkata",
    # US legacy zones
    "US/Eastern":            "America/New_York",
    "US/Central":            "America/Chicago",
    "US/Mountain":           "America/Denver",
    "US/Pacific":            "America/Los_Angeles",
    "US/Alaska":             "America/Anchorage",
    "US/Hawaii":             "Pacific/Honolulu",
    "US/Arizona":            "America/Phoenix",
    # Other common aliases
    "America/Indiana/Indianapolis": "America/Indianapolis",
    "Atlantic/Reykjavik":    "UTC",
    "Etc/UTC":               "UTC",
    "Etc/GMT":               "UTC",
    "GMT":                   "UTC",
    "GB":                    "Europe/London",
    "Japan":                 "Asia/Tokyo",
    "Singapore":             "Asia/Singapore",
    "Australia/ACT":         "Australia/Sydney",
    "Australia/Queensland":  "Australia/Brisbane",
    "Etc/GMT+5":             "America/New_York",   # rough mapping
}

# The 26 timezones accepted by Instantly v2 API whitelist
_INSTANTLY_ALLOWED_TZ: set[str] = {
    "Australia/Darwin", "America/Santiago", "Asia/Kathmandu", "America/Bogota",
    "Asia/Dhaka", "Asia/Colombo", "America/Chicago", "Australia/Adelaide",
    "Australia/Brisbane", "Asia/Dubai", "Asia/Jerusalem", "Asia/Kolkata",
    "Pacific/Auckland", "America/Anchorage", "America/Caracas", "Australia/Melbourne",
    "Europe/Istanbul", "Pacific/Fiji", "Europe/Helsinki", "Asia/Karachi",
    "Asia/Taipei", "Europe/Bucharest", "Africa/Cairo", "Australia/Perth",
    "America/Sao_Paulo", "Asia/Hong_Kong"
}

# Map common standard IANA timezones to one of the 26 allowed timezones (grouped by GMT offset / proximity)
_INSTANTLY_ALLOWED_TZ_MAP: dict[str, str] = {
    "UTC": "Europe/Bucharest",
    "America/New_York": "America/Bogota",
    "America/Chicago": "America/Chicago",
    "America/Denver": "America/Chicago",
    "America/Los_Angeles": "America/Anchorage",
    "America/Phoenix": "America/Chicago",
    "America/Anchorage": "America/Anchorage",
    "Pacific/Honolulu": "America/Anchorage",
    "America/Halifax": "America/Bogota",
    "America/Sao_Paulo": "America/Sao_Paulo",
    "America/Buenos_Aires": "America/Santiago",
    "America/Santiago": "America/Santiago",
    "America/Bogota": "America/Bogota",
    "America/Lima": "America/Bogota",
    "America/Mexico_City": "America/Chicago",
    "America/Caracas": "America/Caracas",
    "America/Indianapolis": "America/Chicago",
    "America/Toronto": "America/Bogota",
    "America/Vancouver": "America/Anchorage",
    "America/Edmonton": "America/Chicago",
    "America/Winnipeg": "America/Chicago",
    "Europe/London": "Europe/Bucharest",
    "Europe/Paris": "Europe/Bucharest",
    "Europe/Berlin": "Europe/Bucharest",
    "Europe/Rome": "Europe/Bucharest",
    "Europe/Madrid": "Europe/Bucharest",
    "Europe/Amsterdam": "Europe/Bucharest",
    "Europe/Brussels": "Europe/Bucharest",
    "Europe/Vienna": "Europe/Bucharest",
    "Europe/Zurich": "Europe/Bucharest",
    "Europe/Stockholm": "Europe/Bucharest",
    "Europe/Oslo": "Europe/Bucharest",
    "Europe/Copenhagen": "Europe/Bucharest",
    "Europe/Helsinki": "Europe/Helsinki",
    "Europe/Warsaw": "Europe/Bucharest",
    "Europe/Prague": "Europe/Bucharest",
    "Europe/Budapest": "Europe/Bucharest",
    "Europe/Bucharest": "Europe/Bucharest",
    "Europe/Athens": "Europe/Bucharest",
    "Europe/Istanbul": "Europe/Istanbul",
    "Europe/Moscow": "Europe/Istanbul",
    "Europe/Kiev": "Europe/Bucharest",
    "Africa/Nairobi": "Europe/Istanbul",
    "Africa/Lagos": "Africa/Cairo",
    "Africa/Cairo": "Africa/Cairo",
    "Africa/Johannesburg": "Africa/Cairo",
    "Asia/Kolkata": "Asia/Kolkata",
    "Asia/Colombo": "Asia/Colombo",
    "Asia/Dhaka": "Asia/Dhaka",
    "Asia/Kathmandu": "Asia/Kathmandu",
    "Asia/Dubai": "Asia/Dubai",
    "Asia/Riyadh": "Europe/Istanbul",
    "Asia/Kuwait": "Europe/Istanbul",
    "Asia/Bahrain": "Europe/Istanbul",
    "Asia/Qatar": "Europe/Istanbul",
    "Asia/Jerusalem": "Asia/Jerusalem",
    "Asia/Karachi": "Asia/Karachi",
    "Asia/Tashkent": "Asia/Karachi",
    "Asia/Almaty": "Asia/Dhaka",
    "Asia/Bangkok": "Asia/Dhaka",
    "Asia/Jakarta": "Asia/Dhaka",
    "Asia/Singapore": "Asia/Hong_Kong",
    "Asia/Kuala_Lumpur": "Asia/Hong_Kong",
    "Asia/Hong_Kong": "Asia/Hong_Kong",
    "Asia/Shanghai": "Asia/Hong_Kong",
    "Asia/Taipei": "Asia/Taipei",
    "Asia/Manila": "Asia/Hong_Kong",
    "Asia/Seoul": "Asia/Hong_Kong",
    "Asia/Tokyo": "Asia/Hong_Kong",
    "Asia/Vladivostok": "Australia/Melbourne",
    "Australia/Sydney": "Australia/Melbourne",
    "Australia/Melbourne": "Australia/Melbourne",
    "Australia/Brisbane": "Australia/Brisbane",
    "Australia/Adelaide": "Australia/Adelaide",
    "Australia/Perth": "Australia/Perth",
    "Australia/Darwin": "Australia/Darwin",
    "Pacific/Auckland": "Pacific/Auckland",
    "Pacific/Fiji": "Pacific/Fiji",
    "Pacific/Guam": "Australia/Brisbane",
}


def _normalize_tz(tz: str | None) -> str:
    """Return an Instantly-accepted IANA timezone string from the whitelisted set.

    1. Map known deprecated/alias names to their canonical equivalents.
    2. If the result is in the whitelisted set, return it.
    3. If the result is in the allowed map, return the mapped zone.
    4. Try a case-insensitive match against the whitelisted set.
    5. Fall back to 'Asia/Kolkata' to prevent any 400 Bad Request campaign errors.
    """
    if not tz:
        return "Asia/Kolkata"
    tz = tz.strip()
    # Apply alias map first
    tz = _INSTANTLY_TZ_ALIASES.get(tz, tz)

    # Check whitelisted set directly
    if tz in _INSTANTLY_ALLOWED_TZ:
        return tz

    # Check allowed map
    mapped = _INSTANTLY_ALLOWED_TZ_MAP.get(tz)
    if mapped:
        return mapped

    # Case-insensitive lookup as fallback
    tz_lower = tz.lower()
    for good in _INSTANTLY_ALLOWED_TZ:
        if good.lower() == tz_lower:
            return good

    log.warning("Unknown/unsupported Instantly timezone '%s', falling back to Asia/Kolkata", tz)
    return "Asia/Kolkata"


def _instantly_headers(api_key: str) -> dict:
    """Build standard headers for Instantly v2 API calls."""
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def instantly_create_campaign(
    api_key: str,
    name: str,
    sequence_steps: list[dict],
    _strategy_id: Optional[str] = None,
    _strategy_name: Optional[str] = None,
    schedule: Optional[dict] = None,
) -> Optional[dict]:
    """Create a campaign via Instantly v2 API."""
    if not api_key:
        return None
    _rl_consume("instantly")
    url = "https://api.instantly.ai/api/v2/campaigns"
    headers = _instantly_headers(api_key)
    # Instantly v2 expects a 'sequences' array containing step objects
    # Example format: "sequences": [{"steps": [{"type": "email", "subject": "Hello", "body": "World", "delay": 0}]}]
    instantly_sequences = []
    if sequence_steps:
        steps = []
        for i, s in enumerate(sequence_steps):
            delay_val = s.get("wait_days")
            if delay_val is None:
                delay_val = 1 if i > 0 else 0
            else:
                try:
                    delay_val = int(delay_val)
                except Exception:
                    delay_val = 1 if i > 0 else 0

            # Ensure follow-up steps have at least 1 day delay to prevent immediate sending
            if i > 0 and delay_val <= 0:
                delay_val = 1

            steps.append({
                "type": "email",
                "delay": delay_val,
                "delay_unit": "days",
                "variants": [
                    {
                        "subject": s.get("subject", "Following up"),
                        "body": s.get("body", "")
                    }
                ]
            })
        instantly_sequences.append({"steps": steps})

    # Default schedule: 24/7 (using Asia/Kolkata to avoid 400 error as UTC is not whitelisted)
    camp_schedule = {
        "name": "Default 24/7",
        "timing": {"from": "00:00", "to": "23:59"},
        "timezone": "Asia/Kolkata",
        "days": {"0": True, "1": True, "2": True, "3": True, "4": True, "5": True, "6": True}
    }

    if schedule:
        raw_tz = schedule.get("timezone", "UTC")
        camp_schedule = {
            "name": "Custom UI Schedule",
            "timing": {"from": schedule.get("time_from", "09:00"), "to": schedule.get("time_to", "17:00")},
            "timezone": _normalize_tz(raw_tz),
            "days": schedule.get("days", camp_schedule["days"])
        }

    body = {
        "name": name,
        "sequences": instantly_sequences,
        "campaign_schedule": {
            "schedules": [camp_schedule]
        }
    }
    curl = _make_curl("POST", url, headers=headers, body=body)
    t0 = time.perf_counter()
    status = None
    result: Optional[dict] = None
    error_text: Optional[str] = None
    raw_response_preview: Optional[str] = None
    try:
        with httpx.Client(timeout=TIMEOUT) as c:
            r = c.post(url, json=body, headers=headers)
            status = r.status_code
            raw_response_preview = r.text[:1000]
            r.raise_for_status()
            result = r.json()

            # Fetch accounts to assign as senders in email_list
            email_list = []
            try:
                accts_url = "https://api.instantly.ai/api/v2/accounts"
                accts_headers = _instantly_headers(api_key)
                r_accts = c.get(accts_url, headers=accts_headers)
                if r_accts.status_code == 200:
                    items = r_accts.json().get("items", [])
                    email_list = [item["email"] for item in items if item.get("status") == 1]
            except Exception as e:
                log.warning("Failed to fetch Instantly accounts for email_list assignment: %s", e)

            # PATCH campaign to set schedule and assign accounts
            campaign_id = result.get("id") or result.get("campaign_id")
            if campaign_id:
                patch_url = f"https://api.instantly.ai/api/v2/campaigns/{campaign_id}"
                patch_body = {
                    "stop_on_reply": True
                }
                if schedule:
                    patch_body["campaign_schedule"] = {
                        "schedules": [camp_schedule]
                    }
                if email_list:
                    patch_body["email_list"] = email_list

                if patch_body:
                    try:
                        patch_curl = _make_curl("PATCH", patch_url, headers=headers, body=patch_body)
                        r_patch = c.patch(patch_url, json=patch_body, headers=headers)
                        r_patch.raise_for_status()
                        audit_service.log_api_call(
                            service="instantly",
                            method="PATCH",
                            url=patch_url,
                            request_params={"campaign_id": campaign_id},
                            response_status=r_patch.status_code,
                            latency_ms=0,
                            curl_command=patch_curl,
                            strategy_id=_strategy_id,
                            strategy_name=_strategy_name,
                            is_live=True,
                            response_summary=r_patch.json(),
                            summary=f"Instantly: patch campaign schedule/accounts {campaign_id[:12]}",
                        )
                    except Exception as e:
                        log.warning("Failed to patch Instantly campaign schedule/accounts: %s", e)

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


def instantly_add_leads(
    api_key: str,
    campaign_id: str,
    leads: list[dict],
    _strategy_id: Optional[str] = None,
    _strategy_name: Optional[str] = None,
) -> Optional[dict]:
    """Add leads to an existing Instantly campaign via v2 API."""
    if not api_key or not campaign_id or not leads:
        return None
    _rl_consume("instantly")
    url = "https://api.instantly.ai/api/v2/leads"
    headers = _instantly_headers(api_key)
    # v2 adds leads one at a time or in bulk; we send each lead individually
    # but wrapped in a single call to /api/v2/leads with campaign reference
    results = []
    t0 = time.perf_counter()
    status = None
    error_text: Optional[str] = None
    raw_response_preview: Optional[str] = None
    try:
        with httpx.Client(timeout=TIMEOUT) as c:
            for lead in leads:
                lead_body = {
                    "campaign": campaign_id,
                    "email": lead.get("email", ""),
                    "first_name": lead.get("first_name", ""),
                    "last_name": lead.get("last_name", ""),
                    "company_name": lead.get("company_name", ""),
                }
                if lead.get("personalization"):
                    lead_body["personalization"] = lead["personalization"]
                r = c.post(url, json=lead_body, headers=headers)
                status = r.status_code
                raw_response_preview = r.text[:1000]
                if r.status_code in (200, 201):
                    results.append(r.json())
                else:
                    log.warning("instantly_add_leads lead %s returned %d: %s",
                                lead.get("email"), r.status_code, r.text[:200])
        return {"total_new_leads": len(results), "leads": results}
    except Exception as e:
        error_text = str(e)
        log.warning("instantly_add_leads failed: %s", e)
        return None
    finally:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        emails = [l.get("email", "") for l in leads[:5]]
        summary_payload: dict = {"campaign_id": campaign_id, "lead_count": len(leads), "emails": emails}
        summary_payload["added"] = len(results)
        if error_text:
            summary_payload["error"] = error_text[:500]
        if raw_response_preview and status and status >= 400:
            summary_payload["response_body"] = raw_response_preview
        audit_service.log_api_call(
            service="instantly",
            method="POST",
            url=url,
            request_params={"campaign_id": campaign_id, "lead_count": len(leads)},
            response_status=status,
            latency_ms=latency_ms,
            curl_command=_make_curl("POST", url, headers=headers, body={"campaign": campaign_id, "leads_count": len(leads)}),
            strategy_id=_strategy_id,
            strategy_name=_strategy_name,
            is_live=True,
            response_summary=summary_payload,
            summary=f"Instantly: add {len(leads)} lead(s) to campaign {campaign_id[:12]} — {', '.join(emails[:2])}",
        )


def instantly_launch_campaign(
    api_key: str,
    campaign_id: str,
    _strategy_id: Optional[str] = None,
    _strategy_name: Optional[str] = None,
) -> Optional[dict]:
    """Activate/launch an Instantly campaign via v2 API so it starts sending."""
    if not api_key or not campaign_id:
        return None
    _rl_consume("instantly")
    url = f"https://api.instantly.ai/api/v2/campaigns/{campaign_id}/activate"
    headers = _instantly_headers(api_key)
    curl = _make_curl("POST", url, headers=headers)
    t0 = time.perf_counter()
    status = None
    result: Optional[dict] = None
    error_text: Optional[str] = None
    raw_response_preview: Optional[str] = None
    try:
        with httpx.Client(timeout=TIMEOUT) as c:
            r = c.post(url, headers=headers)
            status = r.status_code
            raw_response_preview = r.text[:1000]
            r.raise_for_status()
            result = r.json() if r.text.strip() else {"status": "activated"}
            return result
    except Exception as e:
        error_text = str(e)
        log.warning("instantly_launch_campaign failed: %s", e)
        return None
    finally:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        summary_payload: dict = {"campaign_id": campaign_id}
        if result:
            summary_payload["status"] = result.get("status", "launched")
        if error_text:
            summary_payload["error"] = error_text[:500]
        if raw_response_preview and status and status >= 400:
            summary_payload["response_body"] = raw_response_preview
        audit_service.log_api_call(
            service="instantly",
            method="POST",
            url=url,
            request_params={"campaign_id": campaign_id},
            response_status=status,
            latency_ms=latency_ms,
            curl_command=curl,
            strategy_id=_strategy_id,
            strategy_name=_strategy_name,
            is_live=True,
            response_summary=summary_payload,
            summary=f"Instantly: launch campaign {campaign_id[:12]}",
        )


def instantly_verify_email(
    api_key: str,
    email: str,
    _strategy_id: Optional[str] = None,
    _strategy_name: Optional[str] = None,
) -> Optional[str]:
    """Verify an email using Instantly v2 API. Returns a normalized status
    (valid/invalid/catch_all/pending) matching ``hunter_verify_email``."""
    if not api_key or not email:
        return None
    _rl_consume("instantly")
    url = "https://api.instantly.ai/api/v2/email-verification"
    headers = _instantly_headers(api_key)
    payload = {"email": email}
    curl = _make_curl("POST", url, body=payload, headers=headers)
    t0 = time.perf_counter()
    status = None
    verification_status = None
    error_text: Optional[str] = None
    try:
        with httpx.Client(timeout=15.0) as c:
            r = c.post(url, json=payload, headers=headers)
            status = r.status_code
            r.raise_for_status()
            data = r.json() or {}
            # NB: the top-level ``status`` field is only the request status
            # (success/error). The real result lives in ``verification_status``
            # (pending/verified/invalid) plus a separate ``catch_all`` flag.
            raw = (data.get("verification_status") or "").lower()
            catch_all = data.get("catch_all")
            if raw == "verified":
                # A verified-but-catch-all mailbox is risky -> surface as catch_all.
                verification_status = "catch_all" if catch_all is True else "valid"
            elif raw == "invalid":
                verification_status = "invalid"
            elif raw == "pending":
                verification_status = "pending"
            else:
                verification_status = raw or "pending"
            return verification_status
    except Exception as e:
        error_text = str(e)
        log.warning("instantly_verify_email failed: %s", e)
        # Re-raise so the caller can return a proper HTTP 400 to the UI
        raise e
    finally:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        summary_payload: dict = {"email": email}
        if verification_status:
            summary_payload["verification_status"] = verification_status
        if error_text:
            summary_payload["error"] = error_text[:500]
        audit_service.log_api_call(
            service="instantly",
            method="POST",
            url=url,
            request_params={"email": email},
            response_status=status,
            latency_ms=latency_ms,
            curl_command=curl,
            strategy_id=_strategy_id,
            strategy_name=_strategy_name,
            is_live=True,
            response_summary=summary_payload,
            summary=f"Instantly: verify email {email}",
        )


def hunter_verify_email(
    api_key: str,
    email: str,
    _strategy_id: Optional[str] = None,
    _strategy_name: Optional[str] = None,
) -> Optional[str]:
    """Verify an email using Hunter.io email-verifier. Returns a normalized
    status (valid/invalid/catch_all/pending) matching ``instantly_verify_email``.
    """
    if not api_key or not email:
        return None
    _rl_consume("hunter")
    url = "https://api.hunter.io/v2/email-verifier"
    params = {"email": email, "api_key": api_key}
    # Don't leak the key into the recorded curl/audit.
    curl = _make_curl("GET", f"{url}?email={email}&api_key=***")
    t0 = time.perf_counter()
    status = None
    normalized: Optional[str] = None
    error_text: Optional[str] = None
    try:
        with httpx.Client(timeout=15.0) as c:
            r = c.get(url, params=params)
            status = r.status_code
            r.raise_for_status()
            data = (r.json() or {}).get("data") or {}
            result = (data.get("result") or "").lower()
            hstatus = (data.get("status") or "").lower()
            if result == "deliverable" or hstatus == "valid":
                normalized = "valid"
            elif result == "undeliverable" or hstatus in ("invalid", "disposable"):
                normalized = "invalid"
            elif hstatus in ("accept_all", "webmail") or result == "risky":
                normalized = "catch_all"
            else:
                normalized = "pending"
            return normalized
    except Exception as e:
        error_text = str(e)
        log.warning("hunter_verify_email failed: %s", e)
        raise e
    finally:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        summary_payload: dict = {"email": email}
        if normalized:
            summary_payload["verification_status"] = normalized
        if error_text:
            summary_payload["error"] = error_text[:500]
        audit_service.log_api_call(
            service="hunter",
            method="GET",
            url=url,
            request_params={"email": email},
            response_status=status,
            latency_ms=latency_ms,
            curl_command=curl,
            strategy_id=_strategy_id,
            strategy_name=_strategy_name,
            is_live=True,
            response_summary=summary_payload,
            summary=f"Hunter: verify email {email}",
        )


class InstantlyAPIError(Exception):
    """Raised when the Instantly v2 API rejects a request (e.g. 402 no active plan)."""
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"Instantly API {status_code}: {message}")


def _instantly_error_from(exc: "httpx.HTTPStatusError") -> InstantlyAPIError:
    status = exc.response.status_code
    message = exc.response.reason_phrase or "Request failed"
    try:
        body = exc.response.json()
        message = body.get("message") or body.get("error") or message
    except Exception:
        pass
    return InstantlyAPIError(status, message)


def instantly_get_campaigns(api_key: str, raise_on_error: bool = False) -> Optional[list[dict]]:
    if not api_key: return None
    _rl_consume("instantly")
    url = "https://api.instantly.ai/api/v2/campaigns"
    headers = _instantly_headers(api_key)
    try:
        with httpx.Client(timeout=15.0) as c:
            r = c.get(url, headers=headers)
            r.raise_for_status()
            res = r.json()
            return res.get("items") or res.get("data") or []
    except httpx.HTTPStatusError as e:
        log.warning("instantly_get_campaigns failed: %s", e)
        if raise_on_error:
            raise _instantly_error_from(e) from e
        return None
    except Exception as e:
        log.warning("instantly_get_campaigns failed: %s", e)
        return None


def instantly_get_accounts(api_key: str, raise_on_error: bool = False) -> Optional[list[dict]]:
    """Retrieve connected sending accounts from Instantly v2 API."""
    if not api_key: return None
    _rl_consume("instantly")
    url = "https://api.instantly.ai/api/v2/accounts"
    headers = _instantly_headers(api_key)
    try:
        with httpx.Client(timeout=TIMEOUT) as c:
            r = c.get(url, headers=headers)
            r.raise_for_status()
            return r.json().get("items", [])
    except httpx.HTTPStatusError as e:
        log.warning("instantly_get_accounts failed: %s", e)
        if raise_on_error:
            raise _instantly_error_from(e) from e
        return None
    except Exception as e:
        log.warning("instantly_get_accounts failed: %s", e)
        return None


def instantly_create_account(api_key: str, data: dict) -> Optional[dict]:
    """Connect a new sending account via Instantly v2 API."""
    if not api_key:
        return None
    _rl_consume("instantly")
    url = "https://api.instantly.ai/api/v2/accounts"
    headers = _instantly_headers(api_key)
    curl = _make_curl("POST", url, headers=headers, body=data)
    t0 = time.perf_counter()
    status = None
    result: Optional[dict] = None
    error_text: Optional[str] = None
    raw_response_preview: Optional[str] = None
    try:
        with httpx.Client(timeout=TIMEOUT) as c:
            r = c.post(url, json=data, headers=headers)
            status = r.status_code
            raw_response_preview = r.text[:1000]
            r.raise_for_status()
            result = r.json()
            return result
    except Exception as e:
        error_text = str(e)
        log.warning("instantly_create_account failed: %s", e)
        if status == 400:
            raise ValueError(raw_response_preview or error_text)
        raise e
    finally:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        summary_payload: dict = {"email": data.get("email")}
        if result:
            summary_payload["account_id"] = result.get("id") or result.get("email", "")
        if error_text:
            summary_payload["error"] = error_text[:500]
        if raw_response_preview and status and status >= 400:
            summary_payload["response_body"] = raw_response_preview
        audit_service.log_api_call(
            service="instantly",
            method="POST",
            url=url,
            request_params={"email": data.get("email")},
            response_status=status,
            latency_ms=latency_ms,
            curl_command=curl,
            strategy_id=None,
            strategy_name=None,
            is_live=True,
            response_summary=summary_payload,
            summary=f"Instantly: connect sending account {data.get('email')}",
        )


def instantly_toggle_warmup(api_key: str, emails: list[str], enable: bool = True) -> Optional[dict]:
    """Enable or disable warmup for specified email accounts."""
    if not api_key or not emails:
        return None
    _rl_consume("instantly")
    action = "enable" if enable else "disable"
    url = f"https://api.instantly.ai/api/v2/accounts/warmup/{action}"
    headers = _instantly_headers(api_key)
    body = {"emails": emails}
    curl = _make_curl("POST", url, headers=headers, body=body)
    t0 = time.perf_counter()
    status = None
    result: Optional[dict] = None
    error_text: Optional[str] = None
    raw_response_preview: Optional[str] = None
    try:
        with httpx.Client(timeout=TIMEOUT) as c:
            r = c.post(url, json=body, headers=headers)
            status = r.status_code
            raw_response_preview = r.text[:1000]
            r.raise_for_status()
            result = r.json()
            return result
    except Exception as e:
        error_text = str(e)
        log.warning(f"instantly_toggle_warmup {action} failed: %s", e)
        if status == 409:
            raise ValueError("Conflict: A warmup update job is already in progress.")
        raise e
    finally:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        summary_payload: dict = {"emails": emails, "enable": enable}
        if error_text:
            summary_payload["error"] = error_text[:500]
        if raw_response_preview and status and status >= 400:
            summary_payload["response_body"] = raw_response_preview
        audit_service.log_api_call(
            service="instantly",
            method="POST",
            url=url,
            request_params={"emails": emails, "enable": enable},
            response_status=status,
            latency_ms=latency_ms,
            curl_command=curl,
            strategy_id=None,
            strategy_name=None,
            is_live=True,
            response_summary=summary_payload,
            summary=f"Instantly: {action} warmup for {', '.join(emails[:2])}",
        )


def instantly_get_warmup_analytics(api_key: str, emails: list[str]) -> Optional[dict]:
    """Get warmup analytics for specified email accounts."""
    if not api_key or not emails:
        return None
    _rl_consume("instantly")
    url = "https://api.instantly.ai/api/v2/accounts/warmup-analytics"
    headers = _instantly_headers(api_key)
    body = {"emails": emails}
    curl = _make_curl("POST", url, headers=headers, body=body)
    t0 = time.perf_counter()
    status = None
    result: Optional[dict] = None
    error_text: Optional[str] = None
    raw_response_preview: Optional[str] = None
    try:
        with httpx.Client(timeout=TIMEOUT) as c:
            r = c.post(url, json=body, headers=headers)
            status = r.status_code
            raw_response_preview = r.text[:1000]
            r.raise_for_status()
            result = r.json()
            return result
    except Exception as e:
        error_text = str(e)
        log.warning("instantly_get_warmup_analytics failed: %s", e)
        return None
    finally:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        summary_payload: dict = {"emails": emails}
        if error_text:
            summary_payload["error"] = error_text[:500]
        audit_service.log_api_call(
            service="instantly",
            method="POST",
            url=url,
            request_params={"emails": emails},
            response_status=status,
            latency_ms=latency_ms,
            curl_command=curl,
            strategy_id=None,
            strategy_name=None,
            is_live=True,
            response_summary=summary_payload,
            summary=f"Instantly: fetch warmup analytics for {', '.join(emails[:2])}",
        )


def instantly_get_analytics(api_key: str, campaign_id: Optional[str] = None) -> Optional[dict]:
    if not api_key: return None
    _rl_consume("instantly")
    url = "https://api.instantly.ai/api/v2/campaigns/analytics"
    if campaign_id:
        url += f"?campaign_id={campaign_id}"
    headers = _instantly_headers(api_key)
    try:
        with httpx.Client(timeout=15.0) as c:
            r = c.get(url, headers=headers)
            r.raise_for_status()
            data = r.json()
            # Returns an array, we return the first if specific campaign or the whole list if not
            if campaign_id and isinstance(data, list) and len(data) > 0:
                return data[0]
            return data if isinstance(data, dict) else {"data": data}
    except Exception as e:
        log.warning("instantly_get_analytics failed: %s", e)
        return None

def instantly_get_daily_analytics(api_key: str, campaign_id: str, start_date: str, end_date: str) -> Optional[list[dict]]:
    if not api_key: return None
    _rl_consume("instantly")
    url = f"https://api.instantly.ai/api/v2/campaigns/analytics/daily?campaign_id={campaign_id}&start_date={start_date}&end_date={end_date}"
    headers = _instantly_headers(api_key)
    try:
        with httpx.Client(timeout=15.0) as c:
            r = c.get(url, headers=headers)
            r.raise_for_status()
            return r.json()
    except Exception as e:
        log.warning("instantly_get_daily_analytics failed: %s", e)
        return None

def instantly_get_steps_analytics(api_key: str, campaign_id: str) -> Optional[list[dict]]:
    if not api_key: return None
    _rl_consume("instantly")
    url = f"https://api.instantly.ai/api/v2/campaigns/analytics/steps?campaign_id={campaign_id}"
    headers = _instantly_headers(api_key)
    try:
        with httpx.Client(timeout=15.0) as c:
            r = c.get(url, headers=headers)
            r.raise_for_status()
            return r.json()
    except Exception as e:
        log.warning("instantly_get_steps_analytics failed: %s", e)
        return None

def instantly_get_leads(api_key: str, campaign_id: str, status: Optional[str] = None) -> Optional[list[dict]]:
    if not api_key: return None
    _rl_consume("instantly")
    url = "https://api.instantly.ai/api/v2/leads/list"
    headers = _instantly_headers(api_key)
    payload: dict = {"campaign_id": campaign_id, "limit": 1000}
    if status:
        payload["status"] = status
    try:
        with httpx.Client(timeout=15.0) as c:
            r = c.post(url, json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()
            return data.get("data", [])
    except Exception as e:
        log.warning("instantly_get_leads failed: %s", e)
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
        if name == "hunter":
            with httpx.Client(timeout=TIMEOUT) as c:
                r = c.get(
                    "https://api.hunter.io/v2/account",
                    params={"api_key": api_key},
                )
                if r.status_code == 200:
                    return True, "Connected"
                if r.status_code in (401, 403):
                    return False, "Invalid Hunter.io API key"
                return False, f"Hunter HTTP {r.status_code}"
        if name == "clay":
            return False, (
                "Clay is not supported — no stable programmatic enrichment API. "
                "Use Apollo + SerpAPI + Hunter for the equivalent flow."
            )
        return False, "Unknown integration"
    except Exception as e:
        return False, str(e)
