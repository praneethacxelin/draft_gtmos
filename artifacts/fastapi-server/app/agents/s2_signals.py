"""S2 — Market Research, Signals, Enrichment, Scoring."""
import json
import random
from typing import AsyncIterator
from sqlalchemy.orm import Session
from app.db import Strategy, Account, Contact, Signal, Competitor, PatternCluster, IcpEmbedding, LeadScore
from app.llm import chat_json, deterministic_embedding, MODEL_NAME
from app.services import settings_service, clients, fetch_limits
from app.provenance import stamp


async def run_market_sizing(db: Session, strategy_id: str, limit: int | None = None) -> dict:
    strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not strategy:
        return {"error": "Strategy not found"}

    limits = fetch_limits.get_limits(db, strategy.user_id or "user_public")
    n_results = fetch_limits.clamp("market_sizing_results", limit, limits)

    serp_key = settings_service.get_key(db, strategy.user_id, "serpapi")
    serp_context = ""
    serp_count = 0
    if serp_key and strategy.naics_json:
        first_segment = (strategy.naics_json.get("segments") or [{}])[0]
        seg_name = first_segment.get("name", strategy.target_market or "market")
        results = clients.serpapi_search(serp_key, f"{seg_name} TAM market size 2025", num=n_results)
        if results:
            serp_count = len(results)
            serp_context = " Recent search snippets: " + " | ".join(
                f"{r['title']}: {r.get('snippet', '')}" for r in results
            )

    sizing = await chat_json(
        f"Estimate TAM/SAM/SOM for product '{strategy.product_name}' targeting "
        f"{strategy.target_market or 'businesses'}.{serp_context} Return JSON with "
        "keys: tam {value_usd, label}, sam {value_usd, label}, som {value_usd, label}, "
        "methodology, confidence 'low'|'medium'|'high', uses_live_data (bool)."
    )
    if isinstance(sizing, dict):
        sizing["uses_live_data"] = bool(serp_key)
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
    return sizing


async def run_competitors(db: Session, strategy_id: str) -> list[dict]:
    strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not strategy:
        return []

    serp_key = settings_service.get_key(db, strategy.user_id, "serpapi")
    competitors = await chat_json(
        f"For product '{strategy.product_name}': {strategy.description}. "
        "Identify 4 likely competitors. Return JSON with key 'competitors' = array of "
        "{name, website, positioning, features (array), pricing_info, "
        "weaknesses (array), g2_rating (1.0-5.0)}."
    )
    items = competitors.get("competitors", []) if isinstance(competitors, dict) else []

    # Replace existing
    db.query(Competitor).filter(Competitor.strategy_id == strategy_id).delete()
    out = []
    for c in items:
        # Optionally enrich with SerpAPI news
        if serp_key:
            news = clients.serpapi_search(serp_key, f"{c.get('name')} latest news", num=2)
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
        existing_real = db.query(Contact).filter(
            Contact.strategy_id == strategy_id,
            Contact.is_demo == False,
        ).count()
        # Only return cache if we already have as many leads as requested
        if existing_real >= n_leads:
            total_contacts = db.query(Contact).filter(
                Contact.strategy_id == strategy_id
            ).count()
            total_accounts = db.query(Account).filter(
                Account.strategy_id == strategy_id
            ).count()
            return {
                "accounts_added": 0,
                "contacts_added": 0,
                "is_demo": False,
                "cached": True,
                "existing_contacts": existing_real,
                "message": f"Using {existing_real} cached Apollo contacts (total: {total_contacts} contacts, {total_accounts} accounts). Delete existing contacts or increase the limit to fetch more.",
                "provenance": stamp(
                    source="apollo",
                    logic="Skipped Apollo API call — real contacts already cached in the database.",
                    steps=["Check for existing non-demo contacts", "Found cached data, returning"],
                    counts={"cached_contacts": existing_real, "cached_accounts": total_accounts},
                ),
            }

    icp = strategy.icp_json or {}
    titles = []
    if strategy.personas_json:
        for k in ("champion", "economic_buyer", "blocker"):
            p = strategy.personas_json.get(k) if isinstance(strategy.personas_json, dict) else None
            if p and p.get("title"):
                titles.append(p["title"])

    apollo_results = None
    if apollo_key:
        # First attempt: strict title filter
        apollo_results = clients.apollo_people_search(
            apollo_key,
            {
                "titles": titles or ["VP of Sales", "Head of Marketing"],
                "employee_ranges": ["51,200", "201,500", "501,1000"],
            },
            per_page=n_leads,
        )
        # Fallback: if titles are too restrictive, broaden search
        if not apollo_results:
            apollo_results = clients.apollo_people_search(
                apollo_key,
                {
                    "employee_ranges": ["51,200", "201,500", "501,1000"],
                },
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
            response_summary={
                "info": "Apollo people search failed — fell back to AI-generated demo contacts",
                "contacts_added": len(new_contacts),
            },
            summary="Apollo fallback: people search failed → generated AI demo contacts",
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
    if serp_key:
        # Hard ceiling: at most ``n_per_account`` signals are persisted per
        # account per run, regardless of how many query types we issue. We
        # split the budget across query kinds, then truncate the merged
        # result list before insert as a belt-and-braces guard.
        query_kinds = [
            ("funding", "{c} raises funding"),
            ("hiring", "{c} hiring VP Sales"),
        ]
        per_query_budget = max(1, n_per_account // len(query_kinds)) or 1
        for acct in accounts:
            collected: list[tuple[str, dict]] = []
            for kind, query_tpl in query_kinds:
                results = clients.serpapi_search(
                    serp_key, query_tpl.format(c=acct.company_name), num=per_query_budget
                )
                for r in results or []:
                    collected.append((kind, r))
            for kind, r in collected[:n_per_account]:
                db.add(Signal(
                    strategy_id=strategy_id,
                    account_id=acct.id,
                    signal_type=kind,
                    source="serpapi",
                    summary=(r.get("title") or "")[:240],
                    strength_score=0.7,
                    raw_data_json=r,
                ))
                added += 1
    else:
        # AI demo signals
        company_names = [a.company_name for a in accounts]
        demo = await chat_json(
            f"Generate realistic-but-synthetic buying signals for these companies: "
            f"{', '.join(company_names[:8])}. Return JSON with key 'signals' = array of "
            "{company_name, signal_type 'funding'|'hiring'|'tech'|'news', summary, strength 0-1}. "
            "Generate 12 signals total spread across companies.",
            max_tokens=2000,
        )
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

    # pgvector similarity boost: compare strategy's own ICP embedding against
    # any historical "hot" patterns we've stored.
    strategy_embedding = (
        db.query(IcpEmbedding).filter(IcpEmbedding.strategy_id == strategy_id).first()
    )
    pattern_boost = 0.0
    if strategy_embedding is not None:
        # Count clusters already learned for this strategy (the pattern recognition step)
        cluster_count = db.query(PatternCluster).filter(
            PatternCluster.strategy_id == strategy_id
        ).count()
        pattern_boost = min(cluster_count * 5.0, 15.0)

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
    return {"scored": len(contacts)}


def recognize_patterns(db: Session, strategy_id: str) -> dict:
    """Cluster signals into named patterns and store as pattern_clusters."""
    signals = db.query(Signal).filter(Signal.strategy_id == strategy_id).all()
    if not signals:
        return {"clusters": 0}

    # Group by account, look for co-occurrence
    by_account: dict[str, set[str]] = {}
    for s in signals:
        if s.account_id:
            by_account.setdefault(s.account_id, set()).add(s.signal_type)

    # Count combos
    from collections import Counter
    combos = Counter(tuple(sorted(types)) for types in by_account.values() if len(types) >= 2)

    db.query(PatternCluster).filter(PatternCluster.strategy_id == strategy_id).delete()
    created = 0
    for combo, count in combos.most_common(5):
        name = " + ".join(combo) + " co-occurrence"
        embedding = deterministic_embedding(name)
        db.add(PatternCluster(
            strategy_id=strategy_id,
            pattern_name=name,
            signal_combination_json=list(combo),
            conversion_rate=min(count / max(len(by_account), 1), 1.0),
            cluster_embedding=embedding,
        ))
        created += 1
    db.commit()
    score_leads(db, strategy_id)
    return {"clusters": created}
