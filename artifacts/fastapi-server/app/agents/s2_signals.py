"""S2 — Market Research, Signals, Enrichment, Scoring."""
import json
import random
from typing import AsyncIterator
from sqlalchemy.orm import Session
from app.db import Strategy, Account, Contact, Signal, Competitor, PatternCluster, IcpEmbedding, LeadScore
from app.llm import chat_json, deterministic_embedding
from app.services import settings_service, clients


async def run_market_sizing(db: Session, strategy_id: str) -> dict:
    strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not strategy:
        return {"error": "Strategy not found"}

    serp_key = settings_service.get_key(db, "serpapi")
    serp_context = ""
    if serp_key and strategy.naics_json:
        # Pull a quick sizing snippet from SerpAPI
        first_segment = (strategy.naics_json.get("segments") or [{}])[0]
        seg_name = first_segment.get("name", strategy.target_market or "market")
        results = clients.serpapi_search(serp_key, f"{seg_name} TAM market size 2025", num=3)
        if results:
            serp_context = " Recent search snippets: " + " | ".join(
                f"{r['title']}: {r.get('snippet', '')}" for r in results
            )

    sizing = chat_json(
        f"Estimate TAM/SAM/SOM for product '{strategy.product_name}' targeting "
        f"{strategy.target_market or 'businesses'}.{serp_context} Return JSON with "
        "keys: tam {value_usd, label}, sam {value_usd, label}, som {value_usd, label}, "
        "methodology, confidence 'low'|'medium'|'high', uses_live_data (bool)."
    )
    sizing["uses_live_data"] = bool(serp_key)
    strategy.tam_sam_som_json = sizing
    db.commit()
    return sizing


async def run_competitors(db: Session, strategy_id: str) -> list[dict]:
    strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not strategy:
        return []

    serp_key = settings_service.get_key(db, "serpapi")
    competitors = chat_json(
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


async def run_lead_search(db: Session, strategy_id: str) -> dict:
    """Discover and enrich leads. Apollo/Clay if configured, else AI demo data."""
    strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not strategy:
        return {"error": "Strategy not found"}

    apollo_key = settings_service.get_key(db, "apollo")
    clay_key = settings_service.get_key(db, "clay")

    icp = strategy.icp_json or {}
    titles = []
    if strategy.personas_json:
        for k in ("champion", "economic_buyer", "blocker"):
            p = strategy.personas_json.get(k) if isinstance(strategy.personas_json, dict) else None
            if p and p.get("title"):
                titles.append(p["title"])

    apollo_results = None
    if apollo_key:
        apollo_results = clients.apollo_people_search(
            apollo_key,
            {
                "titles": titles or ["VP of Sales", "Head of Marketing"],
                "employee_ranges": ["51,200", "201,500", "501,1000"],
            },
            per_page=8,
        )

    # Pre-load existing accounts/contacts to avoid duplicate inserts on re-run
    existing_accounts = (
        db.query(Account).filter(Account.strategy_id == strategy_id).all()
    )
    new_accounts: dict[str, Account] = {a.company_name: a for a in existing_accounts}
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
            contact = Contact(
                account_id=account.id,
                strategy_id=strategy_id,
                full_name=p.get("name") or "Unknown",
                title=p.get("title"),
                email=p.get("email"),
                linkedin_url=p.get("linkedin_url"),
                seniority=p.get("seniority"),
                department=p.get("departments", [None])[0] if p.get("departments") else None,
            )
            _maybe_add_contact(contact)
    else:
        # AI demo data
        demo = chat_json(
            f"Generate 8 realistic but synthetic prospects for product '{strategy.product_name}' "
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
            contact = Contact(
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

    for c in new_contacts:
        db.add(c)
    db.commit()

    # Auto-trigger scoring
    score_leads(db, strategy_id)

    return {
        "accounts_added": len(new_accounts),
        "contacts_added": len(new_contacts),
        "is_demo": is_demo,
        "uses_clay": bool(clay_key),
    }


async def run_signals(db: Session, strategy_id: str) -> dict:
    """Detect buying signals per account."""
    serp_key = settings_service.get_key(db, "serpapi")
    accounts = db.query(Account).filter(Account.strategy_id == strategy_id).limit(10).all()
    if not accounts:
        return {"signals_added": 0}

    db.query(Signal).filter(
        Signal.strategy_id == strategy_id, Signal.source != "m3_tracking"
    ).delete()

    added = 0
    if serp_key:
        for acct in accounts:
            for kind, query_tpl in [
                ("funding", "{c} raises funding"),
                ("hiring", "{c} hiring VP Sales"),
            ]:
                results = clients.serpapi_search(serp_key, query_tpl.format(c=acct.company_name), num=2)
                for r in results or []:
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
        demo = chat_json(
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
    return {"signals_added": added, "is_demo": not serp_key}


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
        if c.total_score >= 70:
            c.tier = 1
        elif c.total_score >= 40:
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
