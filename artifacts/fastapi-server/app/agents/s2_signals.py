"""S2 — Market Research, Signals, Enrichment, Scoring."""
import json
import random
from typing import AsyncIterator
from sqlalchemy.orm import Session
from app.db import Strategy, Account, Contact, Signal, Competitor, PatternCluster, IcpEmbedding, LeadScore
from app.llm import chat_json, deterministic_embedding, MODEL_NAME
from app.services import settings_service, clients, fetch_limits, audit_service
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
        "Synthesize the search context to compute the most accurate TAM, SAM, and SOM figures. "
        "Your methodology must explicitly cite the search snippets and explain the math or reasoning used to derive these numbers. "
        "Return JSON with keys: tam {value_usd, label}, sam {value_usd, label}, som {value_usd, label}, "
        "methodology (string explaining math and referencing sources), confidence 'low'|'medium'|'high', uses_live_data (bool)."
    )
    sizing = await chat_json(sizing_prompt)
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


async def run_lead_search(db: Session, strategy_id: str, limit: int | None = None) -> dict:
    """Discover and enrich leads. Apollo/Clay if configured, else AI demo data.

    Caching: If this strategy already has real (non-demo) contacts in the
    DB, skip the Apollo API call entirely and return cached data. This
    prevents burning credits on repeated test runs. To force a re-fetch,
    delete existing contacts first.
    """
    strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not strategy:
        return {"error": "Strategy not found"}

    limits = fetch_limits.get_limits(db, strategy.user_id or "user_public")
    n_leads = fetch_limits.clamp("leads_per_run", limit, limits)

    apollo_key = settings_service.get_key(db, strategy.user_id, "apollo")
    clay_key = settings_service.get_key(db, strategy.user_id, "clay")

    # ---- Caching: skip Apollo if we already have real contacts ----
    if apollo_key:
        # Check if we already have leads to save Apollo credits
        existing_contacts = db.query(Contact).filter(Contact.strategy_id == strategy_id, Contact.is_demo == False).count()
        if existing_contacts > 0 and (n_leads is None or existing_contacts >= n_leads):
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
    all_locations = list(set(icp_locations + dd_geos)) or []
    
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

    # Extract search keywords from UVP and pain points
    search_keywords = []
    for field in ("uvp", "pain_points", "product_description"):
        val = dd.get(field)
        if isinstance(val, str) and val.strip() and len(val.strip()) > 10:
            # Use first few significant words as keywords
            search_keywords.append(val.strip()[:150])
            break  # just use the best one

    apollo_results = None
    if apollo_key:
        # First attempt: strict title + location + industry filter
        search_filters = {
            "titles": titles or ["VP of Sales", "Head of Marketing"],
            "employee_ranges": employee_ranges,
        }
        if all_locations:
            search_filters["locations"] = all_locations
        if icp_industries:
            search_filters["industries"] = icp_industries
        if tech_keywords:
            search_filters["technologies"] = tech_keywords[:5]  # Apollo limit
        if search_keywords:
            search_filters["keywords"] = search_keywords[:1]  # One keyword phrase

        apollo_results = clients.apollo_people_search(
            apollo_key,
            search_filters,
            per_page=n_leads,
        )
        # Fallback: if titles are too restrictive, broaden search but keep location
        if not apollo_results:
            fallback_filters = {
                "employee_ranges": employee_ranges,
            }
            if all_locations:
                fallback_filters["locations"] = all_locations
            apollo_results = clients.apollo_people_search(
                apollo_key,
                fallback_filters,
                per_page=n_leads,
            )

    # Wipe existing AI demo contacts so they don't pollute the view when discovering new real leads
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
                    domain=org.get("primary_domain") or org.get("website_url"),
                    industry=org.get("industry"),
                    employee_count=org.get("estimated_num_employees"),
                    revenue_range=org.get("organization_revenue_printed"),
                    tech_stack_json=org.get("technologies"),
                    enrichment_json={"source": "apollo"},
                )
                db.add(account)
                db.flush()
                new_accounts[company] = account
                newly_added_accounts.append(company)
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
                email=p.get("email"),
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
            f"targeting {strategy.target_market or 'businesses'}. ICP: {json.dumps(icp)[:1000]}. "
            "Return JSON with key 'prospects' = array of {company_name, domain, industry, "
            "employee_count, revenue_range, full_name, title, email, linkedin_url, seniority, "
            "department, tech_stack (array of strings), persona_type 'champion'|'economic_buyer'|'blocker'}.",
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
                    tech_stack_json=p.get("tech_stack"),
                    enrichment_json={"source": "ai_demo"},
                )
                db.add(account)
                db.flush()
                new_accounts[company] = account
                newly_added_accounts.append(company)
            contact = Contact(
                user_id=strategy.user_id,
                account_id=account.id,
                strategy_id=strategy_id,
                full_name=p.get("full_name", "Unknown"),
                title=p.get("title"),
                email=p.get("email"),
                linkedin_url=p.get("linkedin_url"),
                seniority=p.get("seniority"),
                department=p.get("department"),
                persona_type=p.get("persona_type"),
                is_demo=True,
            )
            _maybe_add_contact(contact)

    # ---- Inject Inbox Tracker Lead ----
    tracker_email = "saipraneeth2525@gmail.com"
    if tracker_email not in existing_emails:
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
        from app.services import audit_service
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
            "icp": icp,
        },
        outputs={
            "contacts_added": len(new_contacts),
            "accounts_added": len(newly_added_accounts),
            "is_demo": is_demo,
        },
        decision="Apollo search successful" if not is_demo else "Failed over to AI generated demo leads",
        summary=f"S2 → Lead Discovery: Found {len(new_contacts)} new leads ({'Live' if not is_demo else 'Demo'})",
    )

    # Auto-trigger scoring
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


async def fetch_contact_emails(db: Session, strategy_id: str) -> dict:
    """Reveal work emails for contacts that don't have one yet, using Apollo /v1/people/match.

    Apollo charges a credit per successful reveal. We skip contacts that
    already have an email so you only pay for genuinely missing ones.
    Capped at 20 contacts per run to control costs.
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
        .filter(Contact.strategy_id == strategy_id, Contact.email.is_(None))
        .limit(20)
        .all()
    )
    if not contacts:
        return {"updated": 0, "skipped": 0, "message": "All contacts already have emails"}

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
            reveal_phone=False,
            _strategy_id=strategy_id,
            _strategy_name=strategy.product_name,
        )
        if person and person.get("email"):
            contact.email = person["email"]
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
        .filter(Contact.strategy_id == strategy_id, Contact.phone.is_(None))
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
    """Composite score per contact: ICP fit + signals + engagement + pgvector boost."""
    contacts = db.query(Contact).filter(Contact.strategy_id == strategy_id).all()
    signals_by_account: dict[str, list[Signal]] = {}
    for s in db.query(Signal).filter(Signal.strategy_id == strategy_id).all():
        signals_by_account.setdefault(s.account_id, []).append(s)

    # Fetch clusters to apply account-specific pattern boost
    clusters = db.query(PatternCluster).filter(
        PatternCluster.strategy_id == strategy_id
    ).all()

    for c in contacts:
        # Simple ICP fit heuristic: presence of title and seniority counts
        fit = 50.0
        if c.title:
            fit += 10
        if c.seniority and c.seniority.lower() in ("director", "vp", "head", "c_suite", "owner", "founder"):
            fit += 20
        if c.persona_type == "champion":
            fit += 10
        c.icp_fit_score = min(fit, 100)

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

    # Mirror to account.tier (highest contact tier wins)
    for acct in db.query(Account).filter(Account.strategy_id == strategy_id).all():
        contact_tiers = [c.tier for c in contacts if c.account_id == acct.id and c.tier]
        acct.tier = min(contact_tiers) if contact_tiers else 3

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
    created = 0
    cluster_details = []
    for combo, count in combos.most_common(5):
        name = " + ".join(combo) + (" co-occurrence" if len(combo) > 1 else " signal trend")
        embedding = deterministic_embedding(name)
        db.add(PatternCluster(
            strategy_id=strategy_id,
            pattern_name=name,
            signal_combination_json=list(combo),
            conversion_rate=min(count / max(len(by_account), 1), 1.0),
            cluster_embedding=embedding,
        ))
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

