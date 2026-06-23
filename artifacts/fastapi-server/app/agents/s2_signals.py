"""S2 — Market Research, Signals, Enrichment, Scoring."""
import json
import random
import re
from typing import AsyncIterator
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.db import Strategy, Account, Contact, Signal, Competitor, PatternCluster, IcpEmbedding, LeadScore
from app.llm import chat_json, deterministic_embedding, MODEL_NAME
from app.services import settings_service, clients, fetch_limits, audit_service
from app.services.vector_store import store as vector_store
from app.provenance import stamp


# Map ICP geographies to SerpAPI gl (Google country) codes
_GEO_MAP = {
    "north america": "us", "united states": "us", "usa": "us", "us": "us",
    "canada": "ca",
    "western europe": "gb", "europe": "gb", "uk": "gb", "united kingdom": "gb",
    "germany": "de", "france": "fr", "spain": "es", "italy": "it", "netherlands": "nl",
    "india": "in", "asia": "in", "asia-pacific": "au", "australia": "au",
    "japan": "jp", "south korea": "kr", "singapore": "sg",
    "brazil": "br", "latin america": "br", "mexico": "mx",
    "middle east": "ae", "uae": "ae", "saudi arabia": "sa",
    "africa": "za", "south africa": "za", "nigeria": "ng",
}


# Apollo's ``person_locations`` only matches real countries/cities — broad
# region names ("Asia-Pacific", "North America", "EMEA") silently match nothing
# and produce random global results. Expand regions into concrete countries.
_REGION_TO_COUNTRIES = {
    "north america": ["United States", "Canada"],
    "na": ["United States", "Canada"],
    "usa": ["United States"],
    "us": ["United States"],
    "united states": ["United States"],
    "asia-pacific": ["India", "Singapore", "Australia", "Japan", "Philippines"],
    "asia pacific": ["India", "Singapore", "Australia", "Japan", "Philippines"],
    "apac": ["India", "Singapore", "Australia", "Japan", "Philippines"],
    "asia": ["India", "Singapore", "Japan"],
    "europe": ["United Kingdom", "Germany", "France", "Netherlands"],
    "western europe": ["United Kingdom", "Germany", "France", "Netherlands"],
    "emea": ["United Kingdom", "Germany", "France", "United Arab Emirates"],
    "latam": ["Brazil", "Mexico"],
    "latin america": ["Brazil", "Mexico"],
    "middle east": ["United Arab Emirates", "Saudi Arabia"],
    "anz": ["Australia", "New Zealand"],
}


def _normalize_apollo_locations(raw_locations: list) -> list[str]:
    """Convert geography labels into Apollo-valid country names.

    Region buzzwords (e.g. "Asia-Pacific") are expanded into their member
    countries; concrete countries/cities pass through unchanged. Deduped while
    preserving order so the most relevant geos stay first.
    """
    out: list[str] = []
    seen: set[str] = set()

    def _add(name: str):
        key = name.strip().lower()
        if not key or key in seen:
            return
        seen.add(key)
        out.append(name.strip())

    for loc in raw_locations or []:
        if not isinstance(loc, str) or not loc.strip() or loc == "__other__":
            continue
        expanded = _REGION_TO_COUNTRIES.get(loc.strip().lower())
        if expanded:
            for country in expanded:
                _add(country)
        else:
            _add(loc)
    return out


_APOLLO_INDUSTRY_ALIASES = {
    "b2b saas": "computer software",
    "saas": "computer software",
    "software": "computer software",
    "customer support": None,
    "helpdesk": None,
    "help desk": None,
    "e-commerce": "retail",
    "ecommerce": "retail",
    "online retail": "retail",
    "retail": "retail",
    "fintech": "financial services",
    "finance": "financial services",
    "financial services": "financial services",
    "banking": "banking",
    "insurance": "insurance",
    "healthcare": "hospital & health care",
    "health care": "hospital & health care",
    "medical": "hospital & health care",
    "pharma": "pharmaceuticals",
    "pharmaceutical": "pharmaceuticals",
    "biotech": "biotechnology",
    "biotechnology": "biotechnology",
    "education": "education management",
    "edtech": "education management",
    "manufacturing": "manufacturing",
    "logistics": "logistics and supply chain",
    "supply chain": "logistics and supply chain",
    "real estate": "real estate",
    "construction": "construction",
    "hospitality": "hospitality",
    "travel": "leisure, travel & tourism",
    "tourism": "leisure, travel & tourism",
    "telecom": "telecommunications",
    "telecommunications": "telecommunications",
    "automotive": "automotive",
    "energy": "oil & energy",
    "legal": "legal services",
    "law": "legal services",
    "accounting": "accounting",
    "marketing": "marketing and advertising",
    "advertising": "marketing and advertising",
    "media": "online media",
    "government": "government administration",
    "nonprofit": "non-profit organization management",
    "non-profit": "non-profit organization management",
}


def _resolve_apollo_industries(raw_industries: list) -> tuple[list[str], list[dict]]:
    """Map fuzzy ICP industries to Apollo-compatible organization industries."""
    resolved: list[str] = []
    notes: list[dict] = []
    for raw in raw_industries or []:
        if not isinstance(raw, str) or not raw.strip() or raw == "__other__":
            continue
        clean = raw.strip().lower().replace("&", "and")
        mapped = _APOLLO_INDUSTRY_ALIASES.get(clean)
        if clean in _APOLLO_INDUSTRY_ALIASES:
            source = "alias"
        else:
            mapped = None
            source = "unresolved"
            for needle, value in _APOLLO_INDUSTRY_ALIASES.items():
                if value and needle in clean:
                    mapped = value
                    source = "keyword_alias"
                    break
        if mapped and mapped not in resolved:
            resolved.append(mapped)
        notes.append({"input": raw, "resolved": mapped, "source": source})
    return resolved[:5], notes


def _update_account_from_apollo_org(account: Account, org: dict) -> None:
    """Fill missing account firmographics from Apollo organization data."""
    if not org:
        return
    domain = clients.apollo_org_domain(org)
    if domain and not account.domain:
        account.domain = domain
    if org.get("industry") and not account.industry:
        account.industry = org.get("industry")
    if org.get("estimated_num_employees") and not account.employee_count:
        account.employee_count = org.get("estimated_num_employees")
    if org.get("organization_revenue_printed") and not account.revenue_range:
        account.revenue_range = org.get("organization_revenue_printed")
    if org.get("technologies") and not account.tech_stack_json:
        account.tech_stack_json = org.get("technologies")
    
    city = org.get("headquarters_city")
    country = org.get("headquarters_country")
    if city and country and not account.location:
        account.location = f"{city}, {country}"
    elif country and not account.location:
        account.location = country
        
    if org.get("founded_year") and not account.founded_year:
        account.founded_year = org.get("founded_year")

    enrichment = dict(account.enrichment_json or {})
    enrichment.setdefault("source", "apollo")
    account.enrichment_json = enrichment


def _extract_geo(strategy: Strategy) -> str | None:
    """Extract a SerpAPI `gl` country code from the strategy's ICP or target_market."""
    # Check ICP geographies first
    icp = strategy.icp_json or {}
    geos = icp.get("geographies", [])
    if geos and isinstance(geos, list):
        for g in geos:
            code = _GEO_MAP.get(g.lower().strip())
            if code:
                return code
    # Fall back to target_market text
    tm = (strategy.target_market or "").lower()
    for keyword, code in _GEO_MAP.items():
        if keyword in tm:
            return code
    return None


def _account_profile_text(acct, contact=None) -> str:
    """Natural-language profile of an account for semantic ICP matching."""
    if acct is None:
        return ""
    parts = [f"Company {acct.company_name}."]
    if acct.industry:
        parts.append(f"Industry: {acct.industry}.")
    if acct.employee_count:
        parts.append(f"Headcount: {acct.employee_count} employees.")
    if acct.revenue_range:
        parts.append(f"Revenue: {acct.revenue_range}.")
    tech = acct.tech_stack_json
    if isinstance(tech, list) and tech:
        parts.append("Tech stack: " + ", ".join(map(str, tech[:12])) + ".")
    if contact is not None and contact.title:
        parts.append(f"Key contact title: {contact.title}.")
    return " ".join(parts)


def _coerce_usd(val) -> float | None:
    """Parse a TAM/SAM/SOM value into a float number of dollars.

    Handles ints/floats and messy strings like '$1.2B', '1,200,000', '4.5M'.
    """
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if not isinstance(val, str):
        return None
    s = val.strip().lower().replace("$", "").replace(",", "").replace("usd", "").strip()
    mult = 1.0
    if s.endswith("b") or "billion" in s:
        mult = 1e9
        s = s.replace("billion", "").rstrip("b").strip()
    elif s.endswith("m") or "million" in s:
        mult = 1e6
        s = s.replace("million", "").rstrip("m").strip()
    elif s.endswith("k") or "thousand" in s:
        mult = 1e3
        s = s.replace("thousand", "").rstrip("k").strip()
    try:
        return float(s) * mult
    except ValueError:
        return None


def _clamp_market_sizing(sizing: dict) -> dict:
    """Normalise value_usd to numbers and enforce TAM >= SAM >= SOM.

    LLMs occasionally emit SAM > TAM or wildly inconsistent magnitudes. We
    coerce each value to a number and clamp the hierarchy so the dashboard
    never shows a SAM larger than its TAM.
    """
    if not isinstance(sizing, dict) or "_error" in sizing:
        return sizing
    tiers = ["tam", "sam", "som"]
    vals: dict[str, float | None] = {}
    for t in tiers:
        node = sizing.get(t)
        if isinstance(node, dict):
            vals[t] = _coerce_usd(node.get("value_usd"))
        else:
            vals[t] = _coerce_usd(node)

    adjusted = False
    # Enforce monotonic decrease TAM >= SAM >= SOM when values are present.
    if vals.get("tam") and vals.get("sam") and vals["sam"] > vals["tam"]:
        vals["sam"] = vals["tam"]
        adjusted = True
    if vals.get("sam") and vals.get("som") and vals["som"] > vals["sam"]:
        vals["som"] = vals["sam"]
        adjusted = True
    if vals.get("tam") and vals.get("som") and vals["som"] > vals["tam"]:
        vals["som"] = vals["tam"]
        adjusted = True

    for t in tiers:
        if vals.get(t) is not None:
            node = sizing.get(t)
            if isinstance(node, dict):
                node["value_usd"] = round(vals[t])
            else:
                sizing[t] = {"value_usd": round(vals[t]), "label": str(node) if node else ""}
    if adjusted:
        sizing["_clamped"] = True
    return sizing




async def run_market_sizing(db: Session, strategy_id: str, limit: int | None = None) -> dict:
    strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not strategy:
        return {"error": "Strategy not found"}

    limits = fetch_limits.get_limits(db, strategy.user_id or "user_public")
    n_results = fetch_limits.clamp("market_sizing_results", limit, limits)

    serp_key = settings_service.get_key(db, strategy.user_id, "serpapi")
    serp_context = ""
    serp_count = 0
    serp_query = None
    serp_sources = []  # Store source references for the UI
    if serp_key:
        # Ask LLM to generate the perfect market sizing search query
        discovery_ctx = json.dumps(strategy.discovery_data) if strategy.discovery_data else "None"
        query_prompt = (
            f"Product: '{strategy.product_name}'. Description: {strategy.description[:500]}\n"
            f"Target Market: {strategy.target_market}\n"
            f"Additional Discovery Context: {discovery_ctx}\n"
            "Generate 1 highly optimized Google search query to find the Total Addressable Market (TAM) "
            "size for this specific product category. The query should be short and focused (e.g. 'AI recruitment software TAM market size 2026'). "
            "Return JSON with key 'query'."
        )
        query_response = await chat_json(query_prompt)
        serp_query = query_response.get("query") if isinstance(query_response, dict) else None
        
        # Fallback if LLM fails
        if not serp_query:
            first_segment = (strategy.naics_json.get("segments") or [{}])[0] if strategy.naics_json else {}
            seg_name = first_segment.get("name", strategy.target_market or "market")
            sub_vertical = first_segment.get("sub_vertical", "")
            search_topic = f"{sub_vertical} {seg_name}".strip() if sub_vertical else seg_name
            serp_query = f"{search_topic} TAM market size 2026"
            
        geo = _extract_geo(strategy)
        results = clients.serpapi_search(
            serp_key, 
            serp_query, 
            num=n_results, 
            geo=geo,
            _strategy_id=strategy_id, 
            _strategy_name=strategy.product_name
        )
        if results:
            serp_count = len(results)
            serp_sources = [
                {
                    "title": r.get("title", ""),
                    "link": r.get("link", ""),
                    "snippet": r.get("snippet", ""),
                    "verified": r.get("verified", False),
                }
                for r in results
            ]
            serp_context = " Recent search snippets: " + " | ".join(
                f"{r['title']}: {r.get('snippet', '')}" for r in results
            )

    discovery_ctx = json.dumps(strategy.discovery_data) if strategy.discovery_data else "None"
    sizing_prompt = (
        f"Estimate TAM/SAM/SOM for product '{strategy.product_name}' targeting "
        f"{strategy.target_market or 'businesses'}. Additional context: {discovery_ctx}\n"
        f"Live search context: {serp_context}\n"
        "Compute the figures with BOTH a top-down (cite market-size snippets) and a "
        "bottom-up (target company count x realistic annual contract value) approach, then "
        "reconcile them into a single defensible number for each tier. "
        "Rules you MUST follow: TAM >= SAM >= SOM (SAM is the share you can realistically "
        "serve given geo/segment focus; SOM is the 1-3 year obtainable share). "
        "Each value_usd MUST be a plain integer number of US dollars (no commas, no '$', no 'M'/'B' suffix). "
        "The methodology must show the actual math and reference the search snippets used. "
        "Return JSON with keys: tam {value_usd, label}, sam {value_usd, label}, som {value_usd, label}, "
        "methodology (string explaining top-down + bottom-up math and citing sources), "
        "assumptions (array of short strings), confidence 'low'|'medium'|'high', uses_live_data (bool)."
    )
    sizing = await chat_json(sizing_prompt)
    sizing = _clamp_market_sizing(sizing)

    if isinstance(sizing, dict):
        sizing["uses_live_data"] = bool(serp_key)
        sizing["sources"] = serp_sources  # Attach references for UI
        sizing["_provenance"] = stamp(
            source="serpapi" if serp_key else "ai_generated",
            logic=(
                "Pulled sizing snippets from SerpAPI then asked the model to "
                "estimate TAM/SAM/SOM grounded in those snippets."
                if serp_key
                else "Model produced TAM/SAM/SOM estimates from the product brief alone (no SerpAPI key)."
            ),
            steps=[
                ("Pick top NAICS segment as the search anchor" if serp_key else "Skip live search (no SerpAPI key)"),
                f"SerpAPI search: '{n_results}' results requested" if serp_key else "Compose sizing prompt",
                "Prompt model with sizing schema",
                "Persist TAM/SAM/SOM payload",
            ],
            counts={"serp_results": serp_count, "limit_used": n_results},
            model=MODEL_NAME,
        )
    strategy.tam_sam_som_json = sizing
    db.commit()
    
    audit_service.log_pipeline_event(
        stage="market_sizing",
        service="s2_signals",
        strategy_id=strategy_id,
        strategy_name=strategy.product_name,
        inputs={
            "serp_query": serp_query,
            "serp_results_count": serp_count,
            "target_market": strategy.target_market,
            "product_name": strategy.product_name,
        },
        outputs=sizing,
        prompt=sizing_prompt,
        decision="Using SerpAPI snippets to ground sizing estimates" if serp_key else "Falling back to LLM-only sizing due to missing SerpAPI key",
        summary=f"S2 → Market Sizing: Estimated TAM/SAM/SOM",
    )
    return sizing


async def run_competitors(db: Session, strategy_id: str) -> list[dict]:
    strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not strategy:
        return []

    serp_key = settings_service.get_key(db, strategy.user_id, "serpapi")
    geo = _extract_geo(strategy)

    # Step 1: Search SerpAPI for real competitors BEFORE asking LLM
    competitor_context = ""
    serp_queries = []
    if serp_key:
        # Ask LLM to generate the perfect competitor search query
        discovery_ctx = json.dumps(strategy.discovery_data) if strategy.discovery_data else "None"
        query_prompt = (
            f"Product: '{strategy.product_name}'. Description: {strategy.description[:500]}\n"
            f"Target Market: {strategy.target_market}\n"
            f"Additional Context: {discovery_ctx}\n"
            "Generate 1 highly optimized Google search query to find direct competitors and software alternatives "
            "for this specific product. The query should use the product's category, NOT its brand name "
            "(e.g. 'best AI recruitment platforms competitors 2026'). "
            "Return JSON with key 'query'."
        )
        query_response = await chat_json(query_prompt)
        comp_query = query_response.get("query") if isinstance(query_response, dict) else None
        
        # Fallback if LLM fails
        if not comp_query:
            product_category = strategy.product_name
            if strategy.naics_json:
                first_segment = (strategy.naics_json.get("segments") or [{}])[0]
                sub_vertical = first_segment.get("sub_vertical", "")
                if sub_vertical:
                    product_category = sub_vertical
            comp_query = f"best {product_category} software competitors 2026"

        serp_queries.append(comp_query)
        comp_results = clients.serpapi_search(
            serp_key,
            comp_query,
            num=5,
            geo=geo,
            _strategy_id=strategy_id,
            _strategy_name=strategy.product_name,
        )
        if comp_results:
            competitor_context = " Recent search results about competitors in this space: " + " | ".join(
                f"{r.get('title', '')}: {r.get('snippet', '')}" for r in comp_results
            )

    desc_snippet = strategy.description[:500] if strategy.description else "No description"
    discovery_ctx = json.dumps(strategy.discovery_data) if strategy.discovery_data else "None"
    competitors_prompt = (
        f"Product: '{strategy.product_name}'. "
        f"Category: {desc_snippet}. "
        f"Target Market: {strategy.target_market or 'unspecified'}."
        f"Discovery Context: {discovery_ctx}. "
        f"{competitor_context}"
        " Based on the product category and description above, identify 4 DIRECT competitors "
        "that solve the SAME problem for the SAME buyer persona. Do NOT list tangentially related tools. "
        "Return JSON with key 'competitors' = array of "
        "{name, website, positioning, features (array), pricing_info, "
        "weaknesses (array), g2_rating (1.0-5.0)}."
    )
    competitors = await chat_json(competitors_prompt)
    items = competitors.get("competitors", []) if isinstance(competitors, dict) else []

    db.query(Competitor).filter(Competitor.strategy_id == strategy_id).delete()
    out = []
    serp_queries = []
    for c in items:
        # Optionally enrich with SerpAPI news
        if serp_key:
            query = f"{c.get('name')} latest news"
            serp_queries.append(query)
            news = clients.serpapi_search(
                serp_key, 
                query, 
                num=2, 
                _strategy_id=strategy_id, 
                _strategy_name=strategy.product_name
            )
            if news:
                c["recent_news"] = news
        comp = Competitor(
            strategy_id=strategy_id,
            name=c.get("name", "Unknown"),
            website=c.get("website"),
            positioning=c.get("positioning"),
            features_json=c.get("features"),
            pricing_info=c.get("pricing_info"),
            weaknesses_json=c.get("weaknesses"),
            g2_rating=c.get("g2_rating"),
        )
        db.add(comp)
        out.append(c)
    db.commit()

    audit_service.log_pipeline_event(
        stage="competitors",
        service="s2_signals",
        strategy_id=strategy_id,
        strategy_name=strategy.product_name,
        inputs={
            "product": strategy.product_name,
            "serp_queries": serp_queries if serp_key else None
        },
        outputs={"competitors": out},
        prompt=competitors_prompt,
        decision="Enriched AI-generated competitors with live SerpAPI news" if serp_key else "AI-generated competitors without live enrichment",
        summary=f"S2 → Competitor Analysis: Found {len(out)} competitors",
    )
    return out


# Apollo's fixed seniority taxonomy — surfaced to the params-gate UI so the
# user edits from a valid set instead of free-typing values Apollo ignores.
APOLLO_SENIORITY_OPTIONS = [
    "owner", "founder", "c_suite", "partner", "vp", "head", "director", "manager",
]

# Discovery org-size labels → Apollo "min,max" employee ranges. Shared by the
# heuristic facet design and run_lead_search so both stay in lockstep.
_ORG_SIZE_MAP = {
    "1–10 (Startup)": "1,10",
    "11–50 (Small)": "11,50",
    "51–200 (Mid-Market)": "51,200",
    "201–1,000 (Enterprise)": "201,1000",
    "1,000+ (Large Enterprise)": "1001,5000",
}

# The single source of truth for the Apollo filter-design prompt, reused by
# both run_lead_search and design_apollo_facets so the preview the user edits
# matches what discovery would otherwise send.
def _apollo_filter_prompt(strategy, icp: dict, dd: dict, all_locations: list) -> str:
    return (
        "You are a senior B2B prospecting strategist configuring an Apollo.io "
        "people search to surface the highest-fit decision makers for a product.\n"
        f"Product: {strategy.product_name}\n"
        f"ICP: {json.dumps(icp)[:1200]}\n"
        f"Personas: {json.dumps(strategy.personas_json)[:1000] if strategy.personas_json else 'none'}\n"
        f"Discovery answers: {json.dumps(dd)[:1500] if dd else 'none'}\n"
        f"Target countries (already normalized, use these verbatim): {all_locations}\n\n"
        "Decide the OPTIMAL Apollo parameters. Return JSON with keys: "
        "person_titles (array of 4-8 specific job titles of the people who OWN the "
        "problem this product solves and would buy/champion it — be specific to the "
        "product's domain, not generic 'VP of Sales'), "
        "person_seniorities (subset of: owner, founder, c_suite, partner, vp, head, director, manager), "
        "employee_ranges (array of 'min,max' strings, e.g. '51,200'), "
        "industries (array of the buyer's OWN industry — the companies that would "
        "USE this product, not the product's category), "
        "technologies (array of specific tools these buyers likely already use), "
        "locations (array of specific COUNTRY names only — never regions like "
        "'Asia-Pacific' or 'North America'; use the Target countries above). "
        "Do not emit generic keywords. Only include a key when it sharpens precision; omit it otherwise."
    )


def _lead_heuristics(strategy) -> dict:
    """Deterministic ICP/discovery-derived facet fallbacks (no LLM, no Apollo).

    Returns the raw heuristic values used both as the LLM safety-net and as
    the base for the editable params gate.
    """
    icp = strategy.icp_json or {}
    dd = strategy.discovery_data or {}

    titles: list[str] = []
    if isinstance(strategy.personas_json, dict):
        for k in ("champion", "economic_buyer", "blocker"):
            p = strategy.personas_json.get(k)
            if p and p.get("title"):
                titles.append(p["title"])
    if not titles:
        for field in ("economic_buyer", "champion"):
            val = dd.get(field)
            if isinstance(val, str) and val.strip() and val != "__other__":
                titles.append(val.strip())

    icp_locations = icp.get("geographies", []) or []
    dd_geos = dd.get("target_geos", [])
    if isinstance(dd_geos, list):
        dd_geos = [g for g in dd_geos if g and g != "__other__"]
    elif isinstance(dd_geos, str) and dd_geos.strip():
        dd_geos = [dd_geos.strip()]
    else:
        dd_geos = []
    all_locations = _normalize_apollo_locations(list(icp_locations) + list(dd_geos))

    icp_industries = icp.get("industries", []) or []

    dd_org_sizes = dd.get("org_size", [])
    if isinstance(dd_org_sizes, list):
        employee_ranges = [_ORG_SIZE_MAP.get(s) for s in dd_org_sizes if _ORG_SIZE_MAP.get(s)]
    else:
        employee_ranges = []
    if not employee_ranges:
        employee_ranges = ["51,200", "201,500", "501,1000"]

    tech_keywords: list[str] = []
    dd_alternatives = dd.get("alternatives")
    if isinstance(dd_alternatives, str) and dd_alternatives.strip():
        tech_keywords = [t.strip() for t in dd_alternatives.split(",") if t.strip()]
    icp_tech = icp.get("tech_stack_signals", [])
    if isinstance(icp_tech, list):
        tech_keywords = list(dict.fromkeys(tech_keywords + icp_tech))

    return {
        "titles": titles,
        "all_locations": all_locations,
        "icp_industries": icp_industries,
        "employee_ranges": employee_ranges,
        "tech_keywords": tech_keywords,
        "icp": icp,
        "dd": dd,
    }


async def design_apollo_facets(db: Session, strategy_id: str) -> dict:
    """Design the raw, human-readable Apollo facets for a strategy WITHOUT
    running a search — powers the "preview & edit filters" gate.

    The user sees exactly which titles / seniorities / locations / industries /
    company sizes / technologies / keywords would be sent to Apollo and can
    edit them before discovery runs. The edited facets are then passed back as
    ``override_filters`` so the search uses them verbatim.

    Returns raw DISPLAY values (industry/technology NAMES, not resolved Apollo
    taxonomy UIDs); resolution happens inside ``run_lead_search``.
    """
    strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not strategy:
        return {"error": "Strategy not found"}

    h = _lead_heuristics(strategy)
    apollo_key = settings_service.get_key(db, strategy.user_id, "apollo")

    ai_filters: dict = {}
    if apollo_key:
        ai_resp = await chat_json(
            _apollo_filter_prompt(strategy, h["icp"], h["dd"], h["all_locations"]),
            max_tokens=600,
        )
        if isinstance(ai_resp, dict) and "_error" not in ai_resp:
            ai_filters = ai_resp

    def _pick(key, fallback):
        val = ai_filters.get(key)
        if isinstance(val, list):
            val = [v for v in val if v]
        return val or fallback

    raw_tech = _pick("technologies", h["tech_keywords"])
    raw_kw = ai_filters.get("keywords")
    facets = {
        "titles": _pick("person_titles", h["titles"] or ["VP of Sales", "Head of Marketing"]),
        "seniorities": _pick("person_seniorities", []),
        "locations": _normalize_apollo_locations(_pick("locations", h["all_locations"])),
        "industries": _pick("industries", h["icp_industries"]),
        "employee_ranges": _pick("employee_ranges", h["employee_ranges"]),
        "technologies": raw_tech if isinstance(raw_tech, list) else [raw_tech],
        "keywords": raw_kw if isinstance(raw_kw, list) else ([raw_kw] if raw_kw else []),
    }
    # Coerce every facet to a clean list[str] so the UI never chokes on a stray
    # scalar/None the model may emit.
    facets = {k: [str(x) for x in (v or []) if x is not None and str(x).strip()] for k, v in facets.items()}

    return {
        "facets": facets,
        "seniority_options": APOLLO_SENIORITY_OPTIONS,
        "ai_designed": bool(ai_filters),
        "apollo_key_present": bool(apollo_key),
    }


async def run_lead_search(
    db: Session,
    strategy_id: str,
    limit: int | None = None,
    *,
    override_filters: dict | None = None,
    source: str = "discovery",
    source_ref: str | None = None,
    persona_hint: str | None = None,
    accounts_only: bool = False,
) -> dict:
    """Discover and enrich leads. Apollo/Clay if configured, else AI demo data.

    ``accounts_only`` runs the same robust filter design + Apollo relaxation
    ladder but persists ONLY the company (Account) universe — no contacts, no
    bulk_match enrichment (free), no scoring. This powers the accounts-first
    step on Prospects; contacts are pulled afterwards via a normal run.

    Caching: If this strategy already has real (non-demo) contacts in the
    DB, skip the Apollo API call entirely and return cached data. This
    prevents burning credits on repeated test runs. To force a re-fetch,
    delete existing contacts first.

    ``override_filters`` lets a caller (e.g. experiment-driven discovery) supply
    a proven Apollo facet set directly instead of having the LLM design one.
    Inserted contacts are tagged with ``source``/``source_ref`` so outreach can
    group leads by origin, and ``persona_hint`` backfills the persona for leads
    Apollo doesn't classify.
    """
    strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not strategy:
        return {"error": "Strategy not found"}

    limits = fetch_limits.get_limits(db, strategy.user_id or "user_public")
    n_leads = fetch_limits.clamp("leads_per_run", limit, limits)

    apollo_key = settings_service.get_key(db, strategy.user_id, "apollo")
    clay_key = settings_service.get_key(db, strategy.user_id, "clay")

    # ---- Caching: skip Apollo if we already have real contacts ----
    # A *default* re-run (no explicit limit chosen) reuses cached contacts to
    # save Apollo credits. But when the user deliberately picks a number from
    # the "Leads" dropdown, treat it as an intent to fetch MORE — never block
    # it on the cache, otherwise the button feels broken.
    explicit_limit = limit is not None or override_filters is not None or accounts_only
    existing_contacts = 0
    if apollo_key:
        # Check if we already have leads to save Apollo credits
        existing_contacts = db.query(Contact).filter(Contact.strategy_id == strategy_id, Contact.is_demo == False).count()
        if (
            not explicit_limit
            and existing_contacts > 0
            and (n_leads is None or existing_contacts >= n_leads)
        ):
            # We already have enough real contacts. Do not spend Apollo credits.
            audit_service.log_pipeline_event(
                stage="lead_search",
                service="s2_signals",
                strategy_id=strategy_id,
                strategy_name=strategy.product_name,
                inputs={"limit": n_leads, "existing_contacts": existing_contacts},
                outputs={"cached_contacts_used": existing_contacts},
                decision=f"Skipped Apollo search - already have {existing_contacts} cached contacts",
                summary="S2 → Lead Discovery: Used cached contacts"
            )
            total_accounts = db.query(Account).filter(Account.strategy_id == strategy_id).count()
            return {
                "accounts_added": 0,
                "contacts_added": 0,
                "is_demo": False,
                "cached": True,
                "existing_contacts": existing_contacts,
                "message": f"Using {existing_contacts} cached Apollo contacts (total: {existing_contacts} contacts, {total_accounts} accounts). Delete existing contacts or increase the limit to fetch more.",
                "provenance": stamp(
                    source="apollo",
                    logic="Skipped Apollo API call — real contacts already cached in the database.",
                    steps=["Check for existing non-demo contacts", "Found cached data, returning"],
                    counts={"cached_contacts": existing_contacts, "cached_accounts": total_accounts},
                ),
            }

    icp = strategy.icp_json or {}
    dd = strategy.discovery_data or {}
    titles = []
    if strategy.personas_json:
        for k in ("champion", "economic_buyer", "blocker"):
            p = strategy.personas_json.get(k) if isinstance(strategy.personas_json, dict) else None
            if p and p.get("title"):
                titles.append(p["title"])
    
    # Also pull buyer titles from discovery data
    if not titles:
        discovery_titles = []
        for field in ("economic_buyer", "champion"):
            val = dd.get(field)
            if isinstance(val, str) and val.strip() and val != "__other__":
                discovery_titles.append(val.strip())
        if discovery_titles:
            titles = discovery_titles

    # Extract location filters from discovery data + ICP
    icp_locations = icp.get("geographies", [])
    dd_geos = dd.get("target_geos", [])
    if isinstance(dd_geos, list):
        dd_geos = [g for g in dd_geos if g and g != "__other__"]
    elif isinstance(dd_geos, str) and dd_geos.strip():
        dd_geos = [dd_geos.strip()]
    else:
        dd_geos = []
    # Apollo needs concrete countries, not region buzzwords — expand them so
    # "Asia-Pacific"/"North America" actually constrain the search instead of
    # being ignored (which returns random global companies).
    all_locations = _normalize_apollo_locations(list(icp_locations) + list(dd_geos))
    
    # Extract industry filters from ICP
    icp_industries = icp.get("industries", [])

    # Map discovery org_size to Apollo employee ranges
    _ORG_SIZE_MAP = {
        "1–10 (Startup)": "1,10",
        "11–50 (Small)": "11,50",
        "51–200 (Mid-Market)": "51,200",
        "201–1,000 (Enterprise)": "201,1000",
        "1,000+ (Large Enterprise)": "1001,5000",
    }
    dd_org_sizes = dd.get("org_size", [])
    if isinstance(dd_org_sizes, list):
        employee_ranges = [_ORG_SIZE_MAP.get(s) for s in dd_org_sizes if _ORG_SIZE_MAP.get(s)]
    else:
        employee_ranges = []
    if not employee_ranges:
        employee_ranges = ["51,200", "201,500", "501,1000"]

    # Extract tech/tool keywords from discovery alternatives
    tech_keywords = []
    dd_alternatives = dd.get("alternatives")
    if isinstance(dd_alternatives, str) and dd_alternatives.strip():
        # Split comma-separated alternatives into tech keywords
        tech_keywords = [t.strip() for t in dd_alternatives.split(",") if t.strip()]
    icp_tech = icp.get("tech_stack_signals", [])
    tech_keywords = list(set(tech_keywords + icp_tech))

    apollo_results = None
    ai_filters: dict = {}
    search_filters: dict = {}
    filter_resolution: dict = {}
    if apollo_key:
        # ---- Let the LLM design the optimal Apollo query ----
        # The model sees the full ICP + personas + raw discovery answers and
        # decides which Apollo facets (titles, seniorities, size, industries,
        # technologies, locations) will surface the highest-fit
        # decision makers. Heuristic values below act as a safety net.
        filter_prompt = (
            "You are a senior B2B prospecting strategist configuring an Apollo.io "
            "people search to surface the highest-fit decision makers for a product.\n"
            f"Product: {strategy.product_name}\n"
            f"ICP: {json.dumps(icp)[:1200]}\n"
            f"Personas: {json.dumps(strategy.personas_json)[:1000] if strategy.personas_json else 'none'}\n"
            f"Discovery answers: {json.dumps(dd)[:1500] if dd else 'none'}\n"
            f"Target countries (already normalized, use these verbatim): {all_locations}\n\n"
            "Decide the OPTIMAL Apollo parameters. Return JSON with keys: "
            "person_titles (array of 4-8 specific job titles of the people who OWN the "
            "problem this product solves and would buy/champion it — be specific to the "
            "product's domain, not generic 'VP of Sales'), "
            "person_seniorities (subset of: owner, founder, c_suite, partner, vp, head, director, manager), "
            "employee_ranges (array of 'min,max' strings, e.g. '51,200'), "
            "industries (array of the buyer's OWN industry — the companies that would "
            "USE this product, not the product's category), "
            "technologies (array of specific tools these buyers likely already use), "
            "locations (array of specific COUNTRY names only — never regions like "
            "'Asia-Pacific' or 'North America'; use the Target countries above). "
            "Do not emit generic keywords. Only include a key when it sharpens precision; omit it otherwise."
        )
        if override_filters:
            # Experiment-driven discovery: use the proven winning facets directly
            # (mapped onto the LLM's key names so the assembly below reuses them).
            ai_filters = {
                k: v
                for k, v in {
                    "person_titles": override_filters.get("titles"),
                    "person_seniorities": override_filters.get("seniorities"),
                    "employee_ranges": override_filters.get("employee_ranges"),
                    "locations": override_filters.get("locations"),
                    "industries": override_filters.get("industries"),
                    "technologies": override_filters.get("technologies"),
                    "keywords": override_filters.get("keywords"),
                }.items()
                if v
            }
        else:
            ai_resp = await chat_json(filter_prompt, max_tokens=600)
            if isinstance(ai_resp, dict) and "_error" not in ai_resp:
                ai_filters = ai_resp

        def _pick(key, fallback):
            val = ai_filters.get(key)
            if isinstance(val, list):
                val = [v for v in val if v]
            return val or fallback

        # First attempt: AI-designed (with heuristic fallback) precise filter.
        # Do not send q_keywords: Apollo applies it to person text and it
        # over-narrows product/problem phrases that titles already express.
        search_filters = {
            "titles": _pick("person_titles", titles or ["VP of Sales", "Head of Marketing"]),
            "employee_ranges": _pick("employee_ranges", employee_ranges),
        }
        seniorities = _pick("person_seniorities", [])
        if seniorities:
            search_filters["seniorities"] = seniorities
        # Normalize whatever the LLM returned for locations back to concrete
        # countries (belt-and-suspenders in case it ignored the instruction).
        locations = _normalize_apollo_locations(_pick("locations", all_locations))
        if locations:
            search_filters["locations"] = locations
        raw_industries = _pick("industries", icp_industries)
        industries, industry_notes = _resolve_apollo_industries(raw_industries)
        if industries:
            search_filters["industries"] = industries
        raw_technologies = _pick("technologies", tech_keywords)
        raw_technologies_list = raw_technologies if isinstance(raw_technologies, list) else [raw_technologies]
        technologies = clients.apollo_resolve_technology_uids(
            apollo_key,
            raw_technologies_list[:5],
            _strategy_id=strategy_id,
            _strategy_name=strategy.product_name,
        )
        if technologies:
            search_filters["technologies"] = technologies[:5]  # Apollo limit
        # q_keywords is normally omitted (it over-narrows people-text search),
        # but when the user EXPLICITLY sets keywords in the params gate we honor
        # that intent — it sits in the precise tier and is peeled by relaxation.
        if override_filters and override_filters.get("keywords"):
            search_filters["keywords"] = override_filters["keywords"]
        filter_resolution = {
            "industries": industry_notes,
            "technologies": {
                "raw": raw_technologies_list,
                "resolved_uids": technologies,
            },
            "keywords": {
                "raw": ai_filters.get("keywords"),
                "used": False,
                "reason": "q_keywords searches person text and over-narrows people search",
            },
        }

        # ---- Forensic audit: record exactly what the LLM decided vs the
        # heuristic fallback, plus the final merged filter set sent to Apollo.
        # This is the single source of truth for "why did Apollo return these
        # leads" — inspect this event first when results look off.
        _filter_provenance = {
            key: ("ai" if ai_filters.get(key) else "heuristic_fallback")
            for key in (
                "titles", "employee_ranges", "seniorities",
                "locations", "industries", "technologies",
            )
        }
        audit_service.log_pipeline_event(
            stage="apollo_filter_design",
            service="s2_signals",
            strategy_id=strategy_id,
            strategy_name=strategy.product_name,
            prompt=filter_prompt,
            inputs={
                "llm_raw_decision": ai_filters or {"_note": "LLM returned no usable filters; using heuristics"},
                "heuristic_fallbacks": {
                    "titles": titles or ["VP of Sales", "Head of Marketing"],
                    "employee_ranges": employee_ranges,
                    "locations": all_locations,
                    "industries": icp_industries,
                    "technologies": tech_keywords,
                },
            },
            outputs={
                "final_apollo_filters": search_filters,
                "field_source": _filter_provenance,
                "filter_resolution": filter_resolution,
                "requested_limit": n_leads,
            },
            decision=(
                "LLM designed Apollo query from ICP + personas + discovery answers"
                if ai_filters else
                "LLM gave no filters — fell back to heuristic ICP/discovery values"
            ),
            summary=(
                f"S2 → Apollo Filter Design: {len(search_filters.get('titles', []))} titles, "
                f"{'AI-designed' if ai_filters else 'heuristic'}"
            ),
        )

        # Over-fetch beyond contacts we already have so that, after dedup, a
        # re-run surfaces genuinely NEW people instead of re-pulling the same
        # page-1 results. Capped at Apollo's per_page ceiling (100).
        _fetch_per_page = min((existing_contacts or 0) + (n_leads or 10), 100)

        # ---- Progressive relaxation ladder ----
        # Apollo's mixed_people/api_search silently returns 0 when fragile
        # free-text facets (q_keywords, organization_industries, technology
        # UIDs) don't resolve to its taxonomy. ANDing all of them together is
        # the #1 cause of "no leads". So we try the precise query first, then
        # peel off the fragile facets one tier at a time — keeping the robust
        # anchors (titles/seniority + locations + employee size) longest — and
        # stop at the first tier that returns people.
        robust_locations = search_filters.get("locations") or all_locations
        robust_sizes = search_filters.get("employee_ranges") or employee_ranges
        robust_titles = search_filters.get("titles") or (titles or [])
        robust_seniorities = search_filters.get("seniorities") or [
            "c_suite", "vp", "head", "director", "manager",
        ]

        ladder: list[tuple[str, dict]] = [
            # Tier 0 — full precision (titles + every AI facet)
            ("precise (all AI facets)", dict(search_filters)),
        ]
        # Tier 1 — drop q_keywords + technologies (the harshest people-text /
        # taxonomy narrowers) but keep titles + geo + size anchors.
        t1 = {k: v for k, v in search_filters.items() if k not in ("technologies", "keywords")}
        ladder.append(("dropped technologies", t1))
        # Tier 2 — also drop technologies (need Apollo UIDs, often unresolved)
        t2 = {k: v for k, v in t1.items() if k != "industries"}
        ladder.append(("titles + geo + size", t2))
        # Tier 3 — also drop industries (free-text often off-taxonomy); keep
        # titles + locations + size — all well-supported facets
        # Tier 4 — broaden people: swap exact titles for seniority levels but
        # KEEP geo + size so results never become random global noise
        t4 = {"employee_ranges": robust_sizes, "seniorities": robust_seniorities}
        if robust_locations:
            t4["locations"] = robust_locations
        ladder.append(("seniority + geo + size", t4))
        # Tier 5 — last resort: titles + size only (geo may be over-narrow)
        t5 = {"employee_ranges": robust_sizes}
        if robust_titles:
            t5["titles"] = robust_titles
        else:
            t5["seniorities"] = robust_seniorities
        ladder.append(("size + titles only", t5))

        apollo_results = None
        used_tier = None
        # De-dupe identical consecutive tiers so we don't waste API calls.
        seen_signatures: set = set()
        for tier_name, tier_filters in ladder:
            # Skip empty/degenerate tiers and exact repeats.
            cleaned = {k: v for k, v in tier_filters.items() if v}
            sig = json.dumps(cleaned, sort_keys=True, default=str)
            if not cleaned or sig in seen_signatures:
                continue
            seen_signatures.add(sig)
            apollo_results = clients.apollo_people_search(
                apollo_key,
                cleaned,
                per_page=_fetch_per_page,
                enrich=not accounts_only,
                _strategy_id=strategy_id,
                _strategy_name=strategy.product_name,
            )
            if apollo_results:
                used_tier = tier_name
                if tier_name != "precise (all AI facets)":
                    audit_service.log_pipeline_event(
                        stage="apollo_filter_relaxation",
                        service="s2_signals",
                        strategy_id=strategy_id,
                        strategy_name=strategy.product_name,
                        inputs={"precise_filters": search_filters},
                        outputs={"winning_tier": tier_name, "winning_filters": cleaned, "count": len(apollo_results)},
                        decision=(
                            f"Precise Apollo query returned 0 — relaxed to '{tier_name}', "
                            f"which surfaced {len(apollo_results)} leads while keeping geo/size anchors"
                        ),
                        summary=f"S2 → Apollo Relaxation: '{tier_name}' → {len(apollo_results)} leads",
                    )
                break

        if not apollo_results:
            audit_service.log_pipeline_event(
                stage="apollo_filter_exhausted",
                service="s2_signals",
                strategy_id=strategy_id,
                strategy_name=strategy.product_name,
                inputs={"precise_filters": search_filters, "tiers_tried": [t[0] for t in ladder]},
                outputs={"count": 0},
                decision=(
                    "Every relaxation tier returned 0 — Apollo has no people for "
                    "these countries/sizes, or the API key lacks search access. "
                    "Falling back to AI-generated demo leads."
                ),
                summary="S2 → Apollo Relaxation: exhausted all tiers, 0 leads",
            )

    # Wipe existing AI demo contacts so they don't pollute the view when discovering new real leads.
    # In accounts-only mode we never touch contacts, so leave them be.
    if not accounts_only:
        db.query(Contact).filter(Contact.strategy_id == strategy_id, Contact.is_demo == True).delete()
        db.commit()

    # Pre-load existing accounts/contacts to avoid duplicate inserts on re-run
    existing_accounts = (
        db.query(Account).filter(Account.strategy_id == strategy_id).all()
    )
    # Map of all known accounts (existing + newly created in this run) keyed
    # by company name; used to dedupe inserts. ``newly_added_accounts`` tracks
    # only the rows actually inserted in this run for the response payload.
    new_accounts: dict[str, Account] = {a.company_name: a for a in existing_accounts}
    newly_added_accounts: list[str] = []
    existing_emails = {
        (c.email or "").lower()
        for c in db.query(Contact).filter(Contact.strategy_id == strategy_id).all()
        if c.email
    }
    existing_contact_keys = {
        (c.account_id, (c.full_name or "").lower())
        for c in db.query(Contact).filter(Contact.strategy_id == strategy_id).all()
    }
    new_contacts: list[Contact] = []
    is_demo = apollo_results is None

    def _maybe_add_contact(contact: Contact):
        email_key = (contact.email or "").lower()
        if email_key and email_key in existing_emails:
            return
        name_key = (contact.account_id, (contact.full_name or "").lower())
        if name_key in existing_contact_keys:
            return
        if email_key:
            existing_emails.add(email_key)
        existing_contact_keys.add(name_key)
        # Tag origin so outreach can group leads by source. Apollo doesn't
        # classify persona, so backfill it from the winning persona when given.
        contact.source = source
        contact.source_ref = source_ref
        if persona_hint and not contact.persona_type:
            contact.persona_type = persona_hint
        new_contacts.append(contact)

    if apollo_results:
        for p in apollo_results:
            org = p.get("organization") or {}
            company = org.get("name") or "Unknown Co"
            account = new_accounts.get(company)
            if not account:
                account = Account(
                    user_id=strategy.user_id,
                    strategy_id=strategy_id,
                    company_name=company,
                    domain=clients.apollo_org_domain(org),
                    industry=org.get("industry"),
                    employee_count=org.get("estimated_num_employees"),
                    revenue_range=org.get("organization_revenue_printed"),
                    tech_stack_json=org.get("technologies"),
                    enrichment_json={"source": "apollo"},
                    tier=3,  # default until run signals + score leads re-tier it
                )
                db.add(account)
                db.flush()
                new_accounts[company] = account
                newly_added_accounts.append(company)
            else:
                _update_account_from_apollo_org(account, org)
            if accounts_only:
                continue
            # Apollo returns name as "name" OR as first_name + last_name
            full_name = (
                p.get("name")
                or f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()
                or "Unknown"
            )
            # Apollo free tier returns email as None or masked; phone similarly
            raw_phones = p.get("phone_numbers") or []
            phone = raw_phones[0].get("raw_number") if raw_phones else None
            contact = Contact(
                user_id=strategy.user_id,
                account_id=account.id,
                strategy_id=strategy_id,
                full_name=full_name,
                title=p.get("title"),
                # Email is intentionally NOT stored here — it is revealed later
                # via the explicit "Fetch emails" action (Apollo credit cost),
                # so we surface name + role first and spend credits only on
                # contacts the GTM engineer actually selects.
                email=None,
                phone=phone,
                linkedin_url=p.get("linkedin_url"),
                seniority=p.get("seniority"),
                department=p.get("departments", [None])[0] if p.get("departments") else None,
            )
            _maybe_add_contact(contact)
    else:
        # AI demo data
        demo = await chat_json(
            f"Generate {n_leads} realistic but synthetic prospects for product '{strategy.product_name}' "
            f"targeting {strategy.target_market or 'businesses'}.\n"
            f"ICP: {json.dumps(icp)[:1000]}.\n"
            f"Discovery: {json.dumps(dd)[:800] if dd else 'none'}.\n"
            "Each prospect MUST have COMPLETE data — do NOT leave any field empty.\n"
            "Return JSON with key 'prospects' = array of:\n"
            "- company_name: real-sounding company name for this vertical\n"
            "- domain: a plausible .com domain\n"
            "- industry: specific industry (e.g. 'Computer Software')\n"
            "- employee_count: realistic number (50-5000 range)\n"
            "- revenue_range: e.g. '$10M-$50M'\n"
            "- location: city and country (e.g. 'Bangalore, India')\n"
            "- founded_year: realistic year (e.g. 2018)\n"
            "- tech_stack: array of 3-5 specific tools they'd use\n"
            "- full_name, title, email, linkedin_url, seniority, department\n"
            "- persona_type: 'champion'|'economic_buyer'|'blocker'",
            max_tokens=2500,
        )
        for p in (demo.get("prospects") or []) if isinstance(demo, dict) else []:
            company = p.get("company_name", "Demo Co")
            account = new_accounts.get(company)
            if not account:
                account = Account(
                    user_id=strategy.user_id,
                    strategy_id=strategy_id,
                    company_name=company,
                    domain=p.get("domain"),
                    industry=p.get("industry"),
                    employee_count=p.get("employee_count"),
                    revenue_range=p.get("revenue_range"),
                    location=p.get("location"),
                    founded_year=p.get("founded_year"),
                    tech_stack_json=p.get("tech_stack"),
                    enrichment_json={"source": "ai_demo"},
                    tier=3,  # default until run signals + score leads re-tier it
                )
                db.add(account)
                db.flush()
                new_accounts[company] = account
                newly_added_accounts.append(company)
            if accounts_only:
                continue
            contact = Contact(
                user_id=strategy.user_id,
                account_id=account.id,
                strategy_id=strategy_id,
                full_name=p.get("full_name", "Unknown"),
                title=p.get("title"),
                # Email revealed later via "Fetch emails" (credit conservation).
                email=None,
                linkedin_url=p.get("linkedin_url"),
                seniority=p.get("seniority"),
                department=p.get("department"),
                persona_type=p.get("persona_type"),
                is_demo=True,
            )
            _maybe_add_contact(contact)

    # ---- Inject Inbox Tracker Lead ----
    tracker_email = "saipraneeth2525@gmail.com"
    if not accounts_only and tracker_email not in existing_emails:
        tracker_company = "Inbox Tracker Corp"
        account = new_accounts.get(tracker_company)
        if not account:
            account = Account(
                user_id=strategy.user_id,
                strategy_id=strategy_id,
                company_name=tracker_company,
                domain="gmail.com",
                industry="Testing",
                enrichment_json={"source": "inbox_tracker"},
            )
            db.add(account)
            db.flush()
            new_accounts[tracker_company] = account
            newly_added_accounts.append(tracker_company)
        tracker_contact = Contact(
            user_id=strategy.user_id,
            account_id=account.id,
            strategy_id=strategy_id,
            full_name="Inbox Tracker",
            title="Inbox Monitor",
            email=tracker_email,
            seniority="vp",
            persona_type="champion",
            is_demo=False,
        )
        _maybe_add_contact(tracker_contact)

    for c in new_contacts:
        db.add(c)
    db.commit()

    # Log demo fallback when Apollo returned nothing
    if apollo_key and apollo_results is None:
        audit_service.log_api_call(
            service="apollo",
            method="internal",
            url="ai_demo_fallback",
            request_params={},
            response_status=None,
            latency_ms=0,
            curl_command=None,
            strategy_id=strategy_id,
            strategy_name=strategy.product_name,
            is_live=False,
            summary="S2 → Lead Discovery: Demo mode fallback triggered because Apollo returned no results or API key is missing",
        )

    audit_service.log_pipeline_event(
        stage="lead_search",
        service="s2_signals",
        strategy_id=strategy_id,
        strategy_name=strategy.product_name,
        inputs={
            "requested_limit": n_leads,
            "apollo_key_present": bool(apollo_key),
            "search_titles": titles or ["VP of Sales", "Head of Marketing"],
            "ai_apollo_filters": ai_filters or None,
            "final_search_filters": search_filters if apollo_key else None,
            "icp": icp,
        },
        outputs={
            "contacts_added": len(new_contacts),
            "accounts_added": len(newly_added_accounts),
            "is_demo": is_demo,
            "demo_reason": (
                None if not is_demo else (
                    "No Apollo API key configured — generated synthetic demo leads"
                    if not apollo_key else
                    "Apollo returned no matches — fell back to synthetic demo leads"
                )
            ),
            "accounts_preview": newly_added_accounts[:10],
            "contacts_preview": [
                {
                    "name": c.full_name,
                    "title": c.title,
                    "company": new_accounts and next(
                        (name for name, a in new_accounts.items() if a.id == c.account_id),
                        None,
                    ),
                    "email": c.email or "(not revealed)",
                    "seniority": c.seniority,
                }
                for c in new_contacts[:10]
            ],
        },
        decision="Apollo search successful" if not is_demo else "Failed over to AI generated demo leads",
        summary=f"S2 → Lead Discovery: Found {len(new_contacts)} new leads ({'Live' if not is_demo else 'Demo'})",
    )

    # Auto-trigger scoring (skipped in accounts-only mode — nothing to score yet)
    if not accounts_only:
        score_leads(db, strategy_id)

    provenance = stamp(
        source="apollo" if apollo_key else "ai_generated",
        logic=(
            f"Pulled up to {n_leads} contacts from Apollo using the persona titles "
            "and ICP firmographics as filters; deduped against existing rows; "
            "scored ICP fit + signals automatically."
            if apollo_key
            else f"No Apollo key — generated {n_leads} synthetic-but-realistic prospects "
                 "with the model and badged them as demo data."
        ),
        steps=[
            "Read ICP and persona titles from the strategy",
            ("Apollo people search with filters" if apollo_key else "Prompt model for synthetic prospects"),
            "Dedupe by email + (account, name)",
            "Insert accounts and contacts",
            "Run lead scoring",
        ],
        counts={
            "limit_used": n_leads,
            "accounts_added": len(newly_added_accounts),
            "contacts_added": len(new_contacts),
        },
        model=None if apollo_key else MODEL_NAME,
    )

    return {
        "accounts_added": len(newly_added_accounts),
        "contacts_added": len(new_contacts),
        "is_demo": is_demo,
        "uses_clay": bool(clay_key),
        "provenance": provenance,
    }


# Deterministic demo name pool for synthesizing contacts without an Apollo key.
_DEMO_FIRST = [
    "Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Jamie", "Avery",
    "Quinn", "Cameron", "Drew", "Reese", "Skyler", "Devon", "Harper", "Rowan",
]
_DEMO_LAST = [
    "Patel", "Nguyen", "Garcia", "Smith", "Kim", "Johnson", "Mehta", "Lopez",
    "Brown", "Singh", "Davis", "Martin", "Chen", "Wilson", "Khan", "Adams",
]


async def fetch_account_contacts(
    db: Session,
    strategy_id: str,
    *,
    account_ids: list[str] | None = None,
    persona: str | None = None,
    per_account: int = 5,
    override_filters: dict | None = None,
) -> dict:
    """Pull contacts (people) for a hand-picked set of accounts, scoped to the
    given persona. This is the credit-conscious step the GTM engineer runs
    AFTER scoring has re-tiered accounts: they select the accounts/tier they
    care about, choose a persona, and we fetch up to ``per_account`` people per
    account WITHOUT revealing emails (email is a separate paid "Fetch emails"
    step). Demo installs (no Apollo key) get synthesized contacts so the flow
    is testable end-to-end.
    """
    strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not strategy:
        return {"error": "Strategy not found"}

    aq = db.query(Account).filter(Account.strategy_id == strategy_id)
    if account_ids:
        aq = aq.filter(Account.id.in_(account_ids))
    accounts = aq.all()
    if not accounts:
        return {
            "contacts_added": 0,
            "accounts_targeted": 0,
            "message": "No accounts selected. Discover accounts and run scoring first, then pick the accounts (or a tier) to pull contacts for.",
        }

    per_account = max(1, min(int(per_account or 5), 50))

    # Resolve persona → person titles/seniorities.
    personas = strategy.personas_json if isinstance(strategy.personas_json, dict) else {}
    persona_titles: list[str] = []
    persona_seniorities: list[str] = []
    if persona and isinstance(personas.get(persona), dict):
        pj = personas[persona]
        if pj.get("title"):
            persona_titles.append(str(pj["title"]))
        sen = pj.get("seniority") or pj.get("seniorities")
        if isinstance(sen, str):
            persona_seniorities.append(sen)
        elif isinstance(sen, list):
            persona_seniorities.extend(str(s) for s in sen if s)

    ov = override_filters or {}
    titles = list(dict.fromkeys((ov.get("titles") or []) + persona_titles))
    seniorities = list(dict.fromkeys((ov.get("seniorities") or []) + persona_seniorities))

    apollo_key = settings_service.get_key(db, strategy.user_id, "apollo")

    # When a real Apollo key is configured we never fabricate demo people. Clear
    # any previously synthesized demo contacts for the targeted accounts so a
    # real fetch replaces them instead of stacking AI-generated rows on top.
    if apollo_key:
        target_ids = [a.id for a in accounts]
        if target_ids:
            db.query(Contact).filter(
                Contact.strategy_id == strategy_id,
                Contact.account_id.in_(target_ids),
                Contact.is_demo == True,  # noqa: E712
            ).delete(synchronize_session=False)
            db.commit()

    # Dedupe against contacts that already exist for each account.
    existing = {
        (c.account_id, (c.full_name or "").lower())
        for c in db.query(Contact).filter(Contact.strategy_id == strategy_id).all()
    }

    new_contacts: list[Contact] = []
    accounts_no_domain = 0
    accounts_no_results = 0
    for acct in accounts:
        if apollo_key:
            # ---- Real Apollo path only — no synthesized fallback. ----
            if not acct.domain:
                # We can't reliably target a company in Apollo without its
                # domain; skip rather than invent contacts.
                accounts_no_domain += 1
                continue
            filt = {
                "titles": titles,
                "seniorities": seniorities,
                "organization_domains": [acct.domain],
            }
            people = clients.apollo_people_search(
                apollo_key,
                filt,
                per_page=per_account,
                enrich=False,
                _strategy_id=strategy_id,
                _strategy_name=strategy.product_name,
            )
            if not people:
                accounts_no_results += 1
                continue
            for p in people[:per_account]:
                name = clients._person_name(p)
                if not name or (acct.id, name.lower()) in existing:
                    continue
                existing.add((acct.id, name.lower()))
                contact = Contact(
                    user_id=strategy.user_id,
                    account_id=acct.id,
                    strategy_id=strategy_id,
                    full_name=name,
                    title=p.get("title") or (titles[0] if titles else None),
                    email=None,  # revealed later via Fetch emails (paid)
                    linkedin_url=p.get("linkedin_url"),
                    seniority=p.get("seniority") or (seniorities[0] if seniorities else None),
                    department=(p.get("departments") or [None])[0] if p.get("departments") else None,
                    persona_type=persona,
                    is_demo=False,
                    source="discovery",
                    source_ref=p.get("id"),  # Apollo person id → reliable email reveal later
                )
                db.add(contact)
                new_contacts.append(contact)
        else:
            # ---- No Apollo key: synthesize demo people so the flow is testable. ----
            title = titles[0] if titles else "Decision Maker"
            for i in range(per_account):
                fn = _DEMO_FIRST[(hash(acct.id) + i) % len(_DEMO_FIRST)]
                ln = _DEMO_LAST[(hash(acct.id) // 7 + i) % len(_DEMO_LAST)]
                name = f"{fn} {ln}"
                if (acct.id, name.lower()) in existing:
                    continue
                existing.add((acct.id, name.lower()))
                contact = Contact(
                    user_id=strategy.user_id,
                    account_id=acct.id,
                    strategy_id=strategy_id,
                    full_name=name,
                    title=title,
                    email=None,
                    seniority=seniorities[0] if seniorities else None,
                    persona_type=persona,
                    is_demo=True,
                    source="discovery",
                )
                db.add(contact)
                new_contacts.append(contact)

    db.commit()

    # Re-score so the freshly pulled contacts get tiered immediately.
    try:
        score_leads(db, strategy_id)
    except Exception as exc:  # never block contact creation on scoring
        log.warning("score after fetch_account_contacts failed: %s", exc)

    # Build a precise, honest message (no fabricated data when Apollo is live).
    msg = (
        f"Pulled {len(new_contacts)} real contact(s) across {len(accounts)} account(s)"
        + (f" for the {persona} persona" if persona else "")
    )
    if apollo_key:
        notes = []
        if accounts_no_results:
            notes.append(f"{accounts_no_results} account(s) returned no Apollo matches for this persona")
        if accounts_no_domain:
            notes.append(f"{accounts_no_domain} account(s) had no domain to search")
        if notes:
            msg += " — " + "; ".join(notes)
        msg += ". Emails are hidden — use Fetch emails (or Get Email per row) to reveal them (Apollo credit)."
    else:
        msg += ". Demo mode (no Apollo key) — connect Apollo in Settings for real contacts."

    return {
        "contacts_added": len(new_contacts),
        "accounts_targeted": len(accounts),
        "accounts_no_results": accounts_no_results,
        "accounts_no_domain": accounts_no_domain,
        "persona": persona,
        "per_account": per_account,
        "is_demo": not apollo_key,
        "message": msg,
    }


async def run_experiment_discovery(
    db: Session, strategy_id: str, limit: int | None = None
) -> dict:
    """Discover leads using the winning experiment's proven facets.

    This is a *separate* trigger from the generic ICP/persona lead search: it
    only runs once a batch of experiments has been analyzed, and it reuses the
    winning experiment's Apollo facets verbatim plus the persona 70/30 split so
    prospecting stays aligned with what the experiments actually validated.
    Contacts are tagged ``source="experiment"`` for downstream outreach grouping.
    """
    from app.agents.campaign_plan import _experiment_gate, _winning_facets
    from app.agents.persona_intelligence import compute_persona_allocation

    strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not strategy:
        return {"ready": False, "gate": "missing_strategy", "reason": "Strategy not found."}

    batch, winner = _experiment_gate(db, strategy_id)
    if not batch or not winner:
        return {
            "ready": False,
            "gate": "experiments_pending",
            "reason": "Run and analyze a batch of experiments first — discovery uses the winning experiment's facets.",
        }

    facets = _winning_facets(winner)
    if not any(facets.values()):
        return {
            "ready": False,
            "gate": "no_facets",
            "reason": "The winning experiment has no usable Apollo facets to search with.",
        }

    # Persona allocation gives the recommended 70/30 split; the top persona
    # backfills Apollo leads that come through unclassified.
    allocation = compute_persona_allocation(db, strategy_id, total_prospects=limit)
    persona_rows = allocation.get("allocations") or []
    top_persona = persona_rows[0]["persona_type"] if persona_rows else None

    result = await run_lead_search(
        db,
        strategy_id,
        limit,
        override_filters=facets,
        source="experiment",
        source_ref=batch.id,
        persona_hint=top_persona,
    )

    result.update(
        {
            "ready": True,
            "gate": "ok",
            "source_batch_id": batch.id,
            "winning_experiment_id": winner.id,
            "winning_experiment_name": getattr(winner, "name", None),
            "winning_facets": facets,
            "persona_allocation": persona_rows,
        }
    )
    return result


async def run_signals(db: Session, strategy_id: str, limit: int | None = None) -> dict:
    """Detect buying signals per account."""
    strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not strategy:
        return {"signals_added": 0}
    limits = fetch_limits.get_limits(db, strategy.user_id or "user_public")
    n_per_account = fetch_limits.clamp("signals_per_account", limit, limits)

    serp_key = settings_service.get_key(db, strategy.user_id, "serpapi")
    accounts = db.query(Account).filter(Account.strategy_id == strategy_id).limit(10).all()
    if not accounts:
        return {"signals_added": 0}

    db.query(Signal).filter(
        Signal.strategy_id == strategy_id, Signal.source != "m3_tracking"
    ).delete()

    added = 0
    serp_queries = []
    geo = _extract_geo(strategy)
    if serp_key:
        # Hard ceiling: at most ``n_per_account`` signals are persisted per
        # account per run, regardless of how many query types we issue. We
        # split the budget across query kinds, then truncate the merged
        # result list before insert as a belt-and-braces guard.
        query_kinds = [
            ("funding", '"{c}" funding OR investment OR raises OR raised'),
            ("hiring", '"{c}" hiring OR "new hire" OR "joins as"'),
        ]
        per_query_budget = max(1, n_per_account // len(query_kinds)) or 1
        raw_signals = []
        acct_by_id = {a.id: a for a in accounts}
        for acct in accounts:
            collected: list[tuple[str, dict]] = []
            company_lower = acct.company_name.lower()
            for kind, query_tpl in query_kinds:
                query = query_tpl.format(c=acct.company_name)
                serp_queries.append(query)
                results = clients.serpapi_search(
                    serp_key, 
                    query, 
                    num=per_query_budget * 2,  # fetch extra for filtering
                    geo=geo,
                    _strategy_id=strategy_id,
                    _strategy_name=strategy.product_name
                )
                for r in results or []:
                    # Relevance filter: the result must actually mention the company name
                    title = (r.get("title") or "").lower()
                    snippet = (r.get("snippet") or "").lower()
                    if company_lower in title or company_lower in snippet:
                        collected.append((kind, r))
            
            for kind, r in collected[:n_per_account]:
                raw_signals.append((acct.id, kind, r))
                
        if raw_signals:
            # Bulk LLM translation: turn raw search snippets into actionable sales insights
            signals_context = json.dumps([
                {"idx": i, "company": acct_by_id[sid].company_name, "type": kind, "title": r.get("title", ""), "snippet": r.get("snippet", "")}
                for i, (sid, kind, r) in enumerate(raw_signals)
            ])
            insights_prompt = (
                "You are a GTM / RevOps expert. I have a list of raw search results (buying signals) for target companies. "
                "For each signal, write a short, highly actionable summary (1-2 sentences) explaining WHY this matters for a sales rep. "
                "Format: '[Fact] - [Why it matters / Action]'. "
                "Example: 'Just raised $10M Series A — likely expanding their revops team and tooling budget soon.'\n\n"
                f"Raw signals:\n{signals_context}\n\n"
                "Return JSON with key 'summaries' = array of {idx: int, actionable_summary: string}"
            )
            insights_res = await chat_json(insights_prompt, max_tokens=2000)
            insights_map = {}
            if isinstance(insights_res, dict) and "summaries" in insights_res:
                for s in insights_res["summaries"]:
                    insights_map[s.get("idx")] = s.get("actionable_summary", "")
                    
            for i, (sid, kind, r) in enumerate(raw_signals):
                strength = {"funding": 0.9, "hiring": 0.85, "tech": 0.75, "news": 0.6}.get(kind, 0.7)
                summary = insights_map.get(i) or (r.get("title", "") + " - " + r.get("snippet", ""))[:240]
                db.add(Signal(
                    strategy_id=strategy_id,
                    account_id=sid,
                    signal_type=kind,
                    source="serpapi",
                    summary=summary[:240],
                    strength_score=strength,
                    raw_data_json=r,
                ))
                added += 1
    else:
        # AI demo signals
        company_names = [a.company_name for a in accounts]
        signals_prompt = (
            f"Generate realistic-but-synthetic buying signals for these companies: "
            f"{', '.join(company_names[:8])}. Return JSON with key 'signals' = array of "
            "{company_name, signal_type 'funding'|'hiring'|'tech'|'news', summary, strength 0-1}. "
            "For 'summary', write a highly actionable insight for a sales rep. Format: '[Fact] - [Why it matters]'. "
            "Example: 'Just raised $10M Series A — likely expanding their revops team and tooling budget soon.'\n"
            "Generate 12 signals total spread across companies."
        )
        demo = await chat_json(signals_prompt, max_tokens=2000)
        by_name = {a.company_name: a for a in accounts}
        for s in (demo.get("signals") or []) if isinstance(demo, dict) else []:
            acct = by_name.get(s.get("company_name"))
            if not acct:
                continue
            db.add(Signal(
                strategy_id=strategy_id,
                account_id=acct.id,
                signal_type=s.get("signal_type", "news"),
                source="ai_demo",
                summary=s.get("summary", "")[:240],
                strength_score=float(s.get("strength", 0.5)),
            ))
            added += 1
    db.commit()

    audit_service.log_pipeline_event(
        stage="signals",
        service="s2_signals",
        strategy_id=strategy_id,
        strategy_name=strategy.product_name,
        inputs={
            "accounts_scanned": len(accounts),
            "serpapi_key_present": bool(serp_key),
            "limit_per_account": n_per_account,
            "serp_queries": serp_queries if serp_key else None
        },
        outputs={"signals_added": added},
        prompt=signals_prompt if not serp_key else None,
        decision="Live SerpAPI search used" if serp_key else "Falling back to LLM synthetic signal generation",
        summary=f"S2 → Signals Detected: Found {added} buying signals across {len(accounts)} accounts",
    )

    score_leads(db, strategy_id)
    return {
        "signals_added": added,
        "is_demo": not serp_key,
        "provenance": stamp(
            source="serpapi" if serp_key else "ai_generated",
            logic=(
                f"Queried SerpAPI for funding + hiring signals across the top "
                f"{len(accounts)} accounts (up to {n_per_account} results per query)."
                if serp_key
                else "No SerpAPI key — model generated synthetic-but-realistic buying signals "
                     "for the existing account list."
            ),
            steps=[
                f"Pull top {len(accounts)} accounts in this strategy",
                ("SerpAPI: 'funding' and 'hiring' query per account" if serp_key else "Prompt model with company list"),
                "Persist signals + run lead scoring",
            ],
            counts={
                "accounts_scanned": len(accounts),
                "signals_added": added,
                "limit_per_account": n_per_account,
            },
            model=None if serp_key else MODEL_NAME,
        ),
    }


async def fetch_contact_emails(
    db: Session, strategy_id: str, contact_ids: list[str] | None = None
) -> dict:
    """Reveal work emails for contacts that don't have one yet, using Apollo /v1/people/match.

    Apollo charges a credit per successful reveal. We skip contacts that
    already have an email so you only pay for genuinely missing ones.
    When ``contact_ids`` is provided we reveal only that selection (so the GTM
    engineer pays for exactly the contacts they picked); otherwise we cap at 50
    per run to control costs. Demo contacts get a synthesized email so the flow
    is testable without an Apollo key.
    """
    strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not strategy:
        return {"error": "Strategy not found", "updated": 0}

    apollo_key = settings_service.get_key(db, strategy.user_id, "apollo")

    q = (
        db.query(Contact)
        .join(Account, Account.id == Contact.account_id)
        .filter(
            Contact.strategy_id == strategy_id,
            or_(
                Contact.email.is_(None),
                Contact.email == "(not revealed)",
                Contact.email == "Not found",
            ),
        )
    )
    if contact_ids:
        q = q.filter(Contact.id.in_(contact_ids))
    contacts = q.limit(200 if contact_ids else 50).all()
    if not contacts:
        return {"updated": 0, "skipped": 0, "message": "Selected contacts already have emails"}

    accounts = {
        a.id: a
        for a in db.query(Account).filter(Account.strategy_id == strategy_id).all()
    }

    def _demo_email(name: str, domain: str | None) -> str:
        slug = re.sub(r"[^a-z]", ".", (name or "contact").strip().lower()).strip(".")
        slug = re.sub(r"\.+", ".", slug) or "contact"
        return f"{slug}@{domain or 'example.com'}"

    def _real_email(value: str | None) -> str | None:
        """Return a usable work email, or None for Apollo's locked placeholders."""
        if not value:
            return None
        low = value.strip().lower()
        if not low or "@" not in low:
            return None
        # Apollo returns these sentinels when the email is not unlocked.
        if "not_unlocked" in low or low.startswith("email_not_unlocked") or "domain.com" == low.split("@")[-1]:
            return None
        return value.strip()

    updated = 0
    skipped = 0

    # --- Fast path: reveal by Apollo person id via bulk_match (most reliable). ---
    if apollo_key:
        by_apollo_id = {
            c.source_ref: c
            for c in contacts
            if not c.is_demo and c.source_ref and str(c.source_ref).strip()
        }
        if by_apollo_id:
            revealed = clients.apollo_bulk_reveal(
                apollo_key,
                list(by_apollo_id.keys()),
                reveal_personal=False,
                _strategy_id=strategy_id,
                _strategy_name=strategy.product_name,
            )
            for pid, person in revealed.items():
                contact = by_apollo_id.get(pid)
                if not contact:
                    continue
                email = _real_email(person.get("email"))
                if email:
                    contact.email = email
                    updated += 1

    # --- Fallback path: per-contact match for demo/no-id/unresolved contacts. ---
    for contact in contacts:
        if contact.email and _real_email(contact.email):
            continue  # already revealed above
        account = accounts.get(contact.account_id)
        # Demo contacts (or installs without an Apollo key) get a synthesized
        # email so the reveal step is testable end-to-end.
        if contact.is_demo or not apollo_key:
            domain = account.domain if account else None
            contact.email = _demo_email(contact.full_name, domain)
            updated += 1
            continue
        person = clients.apollo_match_person(
            apollo_key,
            name=contact.full_name,
            org_name=account.company_name if account else None,
            domain=account.domain if account else None,
            linkedin_url=contact.linkedin_url,
            reveal_phone=False,
            _strategy_id=strategy_id,
            _strategy_name=strategy.product_name,
        )
        email = _real_email((person or {}).get("email"))
        if email:
            contact.email = email
            updated += 1
        else:
            skipped += 1

    db.commit()
    return {
        "updated": updated,
        "skipped": skipped,
        "total_processed": len(contacts),
        "message": f"Revealed {updated} email(s); {skipped} contact(s) not found in Apollo",
    }


async def fetch_contact_phones(db: Session, strategy_id: str) -> dict:
    """Reveal phone numbers for contacts that don't have one yet, using Apollo /v1/people/match.

    Costs an Apollo phone credit per successful reveal. Capped at 20 per run.
    """
    strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not strategy:
        return {"error": "Strategy not found", "updated": 0}

    apollo_key = settings_service.get_key(db, strategy.user_id, "apollo")
    if not apollo_key:
        return {"error": "No Apollo API key configured in Settings → Integrations", "updated": 0}

    contacts = (
        db.query(Contact)
        .join(Account, Account.id == Contact.account_id)
        .filter(
            Contact.strategy_id == strategy_id,
            or_(
                Contact.phone.is_(None),
                Contact.phone == "Not found",
                Contact.phone == "Maybe: please request direct dial via people/bulk_match",
            ),
        )
        .limit(20)
        .all()
    )
    if not contacts:
        return {"updated": 0, "skipped": 0, "message": "All contacts already have phone numbers"}

    accounts = {
        a.id: a
        for a in db.query(Account).filter(Account.strategy_id == strategy_id).all()
    }

    updated = 0
    skipped = 0
    for contact in contacts:
        account = accounts.get(contact.account_id)
        person = clients.apollo_match_person(
            apollo_key,
            name=contact.full_name,
            org_name=account.company_name if account else None,
            domain=account.domain if account else None,
            linkedin_url=contact.linkedin_url,
            reveal_phone=True,
            _strategy_id=strategy_id,
            _strategy_name=strategy.product_name,
        )
        if person:
            phone_numbers = person.get("phone_numbers") or []
            phone = phone_numbers[0].get("raw_number") if phone_numbers else None
            if phone:
                contact.phone = phone
                updated += 1
                continue
        skipped += 1

    db.commit()
    return {
        "updated": updated,
        "skipped": skipped,
        "total_processed": len(contacts),
        "message": f"Revealed {updated} phone(s); {skipped} contact(s) not found in Apollo",
    }


def score_leads(db: Session, strategy_id: str) -> dict:
    """Composite score per contact: ICP fit + signals + engagement + pattern boost.

    ICP fit blends a fast heuristic (title/seniority) with a *semantic*
    similarity from ChromaDB (account profile vs. the strategy's ICP), so a
    well-matched but oddly-titled account is no longer penalised.
    """
    contacts = db.query(Contact).filter(Contact.strategy_id == strategy_id).all()
    accounts = {
        a.id: a for a in db.query(Account).filter(Account.strategy_id == strategy_id).all()
    }
    signals_by_account: dict[str, list[Signal]] = {}
    for s in db.query(Signal).filter(Signal.strategy_id == strategy_id).all():
        signals_by_account.setdefault(s.account_id, []).append(s)

    # Fetch clusters to apply account-specific pattern boost
    clusters = db.query(PatternCluster).filter(
        PatternCluster.strategy_id == strategy_id
    ).all()

    # Cache semantic ICP-fit per account (one vector query per account, not
    # per contact) so a 200-contact run stays cheap.
    semantic_fit_cache: dict[str, float | None] = {}

    def _semantic_fit(acct: "Account", contact: "Contact") -> float | None:
        if acct is None:
            return None
        if acct.id in semantic_fit_cache:
            return semantic_fit_cache[acct.id]
        text = _account_profile_text(acct, contact)
        sim = vector_store.icp_fit(strategy_id, text) if text else None
        semantic_fit_cache[acct.id] = sim
        return sim

    for c in contacts:
        # Simple ICP fit heuristic: presence of title and seniority counts
        fit = 50.0
        if c.title:
            fit += 10
        if c.seniority and c.seniority.lower() in ("director", "vp", "head", "c_suite", "owner", "founder"):
            fit += 20
        if c.persona_type == "champion":
            fit += 10
        heuristic_fit = min(fit, 100)

        # Blend in semantic similarity when the vector store is available.
        sim = _semantic_fit(accounts.get(c.account_id), c)
        if sim is not None:
            c.icp_fit_score = round(min(heuristic_fit * 0.5 + (sim * 100) * 0.5, 100), 1)
        else:
            c.icp_fit_score = heuristic_fit

        sigs = signals_by_account.get(c.account_id, [])
        sig_score = min(sum((s.strength_score or 0) * 25 for s in sigs), 100)
        c.signal_score = sig_score

        # Calculate account-specific pattern boost
        account_signal_types = set(s.signal_type for s in sigs)
        matched_clusters = 0
        for cluster in clusters:
            required_signals = set(cluster.signal_combination_json or [])
            if required_signals and required_signals.issubset(account_signal_types):
                matched_clusters += 1
        
        pattern_boost = min(matched_clusters * 8.0, 20.0)

        # engagement_score is updated by M3 separately
        total = (c.icp_fit_score * 0.30) + (sig_score * 0.40) + (c.engagement_score * 0.30) + pattern_boost
        c.total_score = round(min(total, 100), 1)
        # Thresholds calibrated for demo/no-live-key installs:
        # Without SerpAPI or engagement events the max achievable score
        # via ICP-fit alone is ~45 (VP/Director-level title + champion
        # persona). Setting Tier 1 at ≥50 lets high-seniority demo
        # contacts qualify after a lead-discovery run.
        if c.total_score >= 50:
            c.tier = 1
        elif c.total_score >= 25:
            c.tier = 2
        else:
            c.tier = 3

        # Persist a snapshot row (history of scoring runs).
        db.add(LeadScore(
            contact_id=c.id,
            strategy_id=strategy_id,
            icp_fit_score=c.icp_fit_score,
            signal_score=sig_score,
            engagement_score=c.engagement_score,
            pattern_bonus=pattern_boost,
            total_score=c.total_score,
            tier=c.tier,
        ))

    # ---- Account-level scoring (works even before any contacts exist) ----
    # The new prospect flow discovers ACCOUNTS first (no contacts), so account
    # tiers must be derived from the account's own firmographic ICP fit + live
    # signals + pattern boost — not only from contact tiers. Once contacts are
    # pulled and scored, the better of the two tiers wins.
    strat = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    icp = (strat.icp_json or {}) if strat else {}
    dd = (strat.discovery_data or {}) if strat else {}
    icp_industries = {str(x).lower() for x in (icp.get("industries") or [])}
    for v in (dd.get("target_industries") or []):
        icp_industries.add(str(v).lower())

    for acct in db.query(Account).filter(Account.strategy_id == strategy_id).all():
        # Firmographic ICP-fit heuristic (no contacts required).
        a_fit = 50.0
        if acct.industry:
            a_fit += 10
            ind = acct.industry.lower()
            if any(ci and (ci in ind or ind in ci) for ci in icp_industries):
                a_fit += 20
        if acct.employee_count:
            a_fit += 5
        if isinstance(acct.tech_stack_json, list) and acct.tech_stack_json:
            a_fit += 5
        a_heuristic = min(a_fit, 100)
        sim = _semantic_fit(acct, None)
        a_icp = (
            round(min(a_heuristic * 0.5 + (sim * 100) * 0.5, 100), 1)
            if sim is not None
            else a_heuristic
        )

        sigs = signals_by_account.get(acct.id, [])
        a_sig = min(sum((s.strength_score or 0) * 25 for s in sigs), 100)
        a_sig_types = set(s.signal_type for s in sigs)
        a_matched = 0
        for cluster in clusters:
            required = set(cluster.signal_combination_json or [])
            if required and required.issubset(a_sig_types):
                a_matched += 1
        a_pattern = min(a_matched * 8.0, 20.0)

        a_total = round(min(a_icp * 0.5 + a_sig * 0.5 + a_pattern, 100), 1)
        if a_total >= 50:
            acct_tier = 1
        elif a_total >= 25:
            acct_tier = 2
        else:
            acct_tier = 3

        # Blend with contact-derived tier (lower number = better) when contacts exist.
        contact_tiers = [c.tier for c in contacts if c.account_id == acct.id and c.tier]
        acct.tier = min(acct_tier, min(contact_tiers)) if contact_tiers else acct_tier

    db.commit()

    strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    audit_service.log_pipeline_event(
        stage="scoring",
        service="s2_signals",
        strategy_id=strategy_id,
        strategy_name=strategy.product_name if strategy else None,
        inputs={"contacts_scored": len(contacts)},
        outputs={"pattern_boost_applied": pattern_boost},
        decision="Scoring heuristic: (ICP Fit * 0.30) + (Signals * 0.40) + (Engagement * 0.30) + Pattern Boost",
        summary=f"S2 → Scoring: Evaluated {len(contacts)} leads",
    )

    return {"scored": len(contacts)}


def recognize_patterns(db: Session, strategy_id: str) -> dict:
    """Cluster signals into named patterns and store as pattern_clusters."""
    signals = db.query(Signal).filter(Signal.strategy_id == strategy_id).all()
    if not signals:
        strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
        audit_service.log_pipeline_event(
            stage="patterns",
            service="s2_signals",
            strategy_id=strategy_id,
            strategy_name=strategy.product_name if strategy else None,
            inputs={"signals_found": 0},
            outputs={"clusters": 0},
            decision="No signals found — run 'Run Signals' first to gather buying signals from SerpAPI",
            summary="S2 → Pattern Recognition: Skipped (no signals)",
        )
        return {"clusters": 0}

    # Group by account, look for co-occurrence
    by_account: dict[str, set[str]] = {}
    for s in signals:
        if s.account_id:
            by_account.setdefault(s.account_id, set()).add(s.signal_type)

    # Count combos
    from collections import Counter
    combos = Counter(tuple(sorted(types)) for types in by_account.values() if len(types) >= 1)

    db.query(PatternCluster).filter(PatternCluster.strategy_id == strategy_id).delete()
    vector_store.delete_patterns(strategy_id)
    created = 0
    cluster_details = []
    for combo, count in combos.most_common(5):
        name = " + ".join(combo) + (" co-occurrence" if len(combo) > 1 else " signal trend")
        embedding = deterministic_embedding(name)
        cluster = PatternCluster(
            strategy_id=strategy_id,
            pattern_name=name,
            signal_combination_json=list(combo),
            conversion_rate=min(count / max(len(by_account), 1), 1.0),
            cluster_embedding=embedding,
        )
        db.add(cluster)
        db.flush()
        vector_store.upsert_pattern(strategy_id, cluster.id, name)
        cluster_details.append({
            "pattern": name,
            "signals": list(combo),
            "accounts_matching": count,
            "conversion_rate": round(min(count / max(len(by_account), 1), 1.0), 2),
        })
        created += 1
    db.commit()

    strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    audit_service.log_pipeline_event(
        stage="patterns",
        service="s2_signals",
        strategy_id=strategy_id,
        strategy_name=strategy.product_name if strategy else None,
        inputs={
            "total_signals": len(signals),
            "accounts_with_signals": len(by_account),
            "unique_signal_types": list(set(s.signal_type for s in signals)),
        },
        outputs={
            "clusters_created": created,
            "clusters": cluster_details,
        },
        decision=f"Identified {created} signal pattern(s) across {len(by_account)} accounts, then re-scored all leads with pattern boost",
        summary=f"S2 → Pattern Recognition: Found {created} pattern(s) across {len(by_account)} accounts",
    )

    score_leads(db, strategy_id)
    return {"clusters": created, "details": cluster_details}
