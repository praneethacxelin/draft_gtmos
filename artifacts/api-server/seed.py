"""Seed minimal demo data so the UI isn't empty on first load."""
from app.db import (
    init_db,
    SessionLocal,
    Strategy,
    Account,
    Contact,
    Signal,
    Competitor,
    EngagementEvent,
    FeedbackEntry,
    AttributionEvent,
    PatternCluster,
)
from app.llm import deterministic_embedding


def main():
    init_db()
    db = SessionLocal()
    try:
        if db.query(Strategy).count() > 0:
            print("Already seeded")
            return

        s = Strategy(
            product_name="Acme Sales Intelligence Platform",
            description="Real-time pipeline intelligence and deal scoring for B2B SaaS revenue teams.",
            target_market="Series B/C SaaS companies, 100-500 employees, in North America",
            pain_points_raw="VP Sales has no visibility into pipeline health; deals slip without warning; SDR teams miss high-intent accounts.",
            status="ready",
            icp_json={
                "industries": ["B2B SaaS", "Fintech SaaS", "DevTools"],
                "employee_size_range": "100-500",
                "revenue_range": "$10M-$100M ARR",
                "geographies": ["North America"],
                "tech_stack_signals": ["Salesforce", "Outreach", "Gong"],
                "segments": [
                    {"name": "Series B SaaS scaling SDR teams", "fit_score": 92, "rationale": "Active hiring + Salesforce in stack"},
                    {"name": "Late-stage B2B SaaS with pipeline gaps", "fit_score": 78, "rationale": "Forecast misses signal latent need"},
                ],
            },
            personas_json={
                "champion": {"title": "Director of Sales Operations", "goals": ["Improve forecast accuracy", "Operational excellence"], "frustrations": ["Manual reporting", "Scattered data"], "communication_style": "Data-driven and pragmatic"},
                "economic_buyer": {"title": "VP of Sales", "goals": ["Hit quota", "Predictable pipeline"], "frustrations": ["Missed forecasts"], "communication_style": "ROI focused, time-poor"},
                "blocker": {"title": "Head of IT", "goals": ["Security compliance", "Vendor consolidation"], "frustrations": ["Tool sprawl"], "communication_style": "Risk-averse"},
                "influence_edges": [
                    {"from": "champion", "to": "economic_buyer", "label": "proposes"},
                    {"from": "blocker", "to": "economic_buyer", "label": "vetoes"},
                ],
            },
            naics_json={
                "segments": [
                    {"naics_code": "541511", "name": "Custom Computer Programming Services", "opportunity_score": 88, "est_company_count": 12000},
                    {"naics_code": "522320", "name": "Financial Transactions Processing", "opportunity_score": 74, "est_company_count": 4200},
                ]
            },
            stakeholder_map_json={
                "nodes": [
                    {"id": "champ", "label": "Director Sales Ops", "role": "Champion", "tier": "champion", "influence": 70},
                    {"id": "vp", "label": "VP Sales", "role": "Economic Buyer", "tier": "economic_buyer", "influence": 95},
                    {"id": "it", "label": "Head of IT", "role": "Security Blocker", "tier": "blocker", "influence": 60},
                    {"id": "cro", "label": "CRO", "role": "Final Approver", "tier": "economic_buyer", "influence": 100},
                ],
                "edges": [
                    {"from": "champ", "to": "vp", "label": "proposes to"},
                    {"from": "vp", "to": "cro", "label": "needs approval from"},
                    {"from": "it", "to": "vp", "label": "can veto"},
                ],
            },
            use_cases_json={
                "use_cases": [
                    {"title": "Forecast Accuracy Boost", "vertical": "B2B SaaS", "persona": "VP Sales", "scenario": "End-of-quarter pipeline review", "value_prop": "Cut forecast variance by 30%"},
                    {"title": "Hot Account Alerts", "vertical": "Fintech SaaS", "persona": "Director Sales Ops", "scenario": "Daily SDR prioritisation", "value_prop": "Surface 5x more buying signals"},
                ]
            },
            tam_sam_som_json={
                "tam": {"value_usd": 12_000_000_000, "label": "$12B"},
                "sam": {"value_usd": 2_400_000_000, "label": "$2.4B"},
                "som": {"value_usd": 180_000_000, "label": "$180M"},
                "methodology": "Top-down based on B2B SaaS sales tech spend reports",
                "confidence": "medium",
                "uses_live_data": False,
            },
        )
        db.add(s)
        db.flush()

        # Embedding for pattern recognition
        from app.db import IcpEmbedding
        db.add(IcpEmbedding(strategy_id=s.id, embedding=deterministic_embedding("Acme ICP " + s.description), summary="Acme seed ICP"))

        # Competitors
        for c in [
            {"name": "Gong", "website": "gong.io", "positioning": "Revenue intelligence platform", "g2_rating": 4.7, "weaknesses": ["High price"], "features": ["Call recording", "Deal coaching"], "pricing_info": "$$$ enterprise"},
            {"name": "Chorus", "website": "chorus.ai", "positioning": "Conversation intelligence", "g2_rating": 4.5, "weaknesses": ["Less ML depth"], "features": ["Call recording", "Coaching"], "pricing_info": "$$ mid-market"},
            {"name": "Clari", "website": "clari.com", "positioning": "Forecasting and revenue ops", "g2_rating": 4.5, "weaknesses": ["UX complexity"], "features": ["Forecasting", "Pipeline insights"], "pricing_info": "$$$ enterprise"},
        ]:
            db.add(Competitor(
                strategy_id=s.id,
                name=c["name"],
                website=c["website"],
                positioning=c["positioning"],
                g2_rating=c["g2_rating"],
                pricing_info=c["pricing_info"],
                features_json=c["features"],
                weaknesses_json=c["weaknesses"],
            ))

        # Accounts + contacts
        seed_accts = [
            ("Linear Stack Inc", "linearstack.io", "B2B SaaS", 240, "$25M-$50M", 1),
            ("Halo Fintech", "halofintech.com", "Fintech SaaS", 410, "$50M-$100M", 1),
            ("Bridgewell Cloud", "bridgewell.cloud", "DevTools", 180, "$10M-$25M", 2),
            ("Pacific Ledger", "pacificledger.com", "Fintech SaaS", 95, "$5M-$10M", 2),
            ("Cobaltbase", "cobaltbase.io", "B2B SaaS", 320, "$25M-$50M", 3),
        ]
        contacts_seed = [
            ("Linear Stack Inc", "Maya Chen", "VP of Sales", "maya@linearstack.io", "vp", "champion", 1),
            ("Linear Stack Inc", "Daniel Park", "Director Sales Ops", "daniel@linearstack.io", "director", "champion", 1),
            ("Halo Fintech", "Priya Singh", "VP Revenue", "priya@halofintech.com", "vp", "economic_buyer", 1),
            ("Halo Fintech", "Alex Reyes", "Head of IT", "alex@halofintech.com", "head", "blocker", 2),
            ("Bridgewell Cloud", "Jordan Liu", "Head of Growth", "jordan@bridgewell.cloud", "head", "champion", 2),
            ("Pacific Ledger", "Sam Okonkwo", "CRO", "sam@pacificledger.com", "c_suite", "economic_buyer", 2),
            ("Cobaltbase", "Riley Murphy", "Sales Manager", "riley@cobaltbase.io", "manager", "champion", 3),
        ]
        accounts: dict[str, Account] = {}
        for name, dom, ind, emp, rev, tier in seed_accts:
            a = Account(strategy_id=s.id, company_name=name, domain=dom, industry=ind, employee_count=emp, revenue_range=rev, tier=tier, enrichment_json={"source": "seed"})
            db.add(a)
            db.flush()
            accounts[name] = a

        for company, name, title, email, sen, persona, tier in contacts_seed:
            acct = accounts[company]
            score = 85 if tier == 1 else (55 if tier == 2 else 30)
            db.add(Contact(
                account_id=acct.id, strategy_id=s.id, full_name=name, title=title,
                email=email, seniority=sen, persona_type=persona,
                icp_fit_score=score, signal_score=score - 10, total_score=score, tier=tier,
                is_demo=True,
            ))

        # Signals
        signals_seed = [
            ("Linear Stack Inc", "funding", "Linear Stack raises $30M Series B led by Accel"),
            ("Linear Stack Inc", "hiring", "Linear Stack hiring 8 SDRs in Q2"),
            ("Halo Fintech", "funding", "Halo Fintech raises $45M Series C"),
            ("Halo Fintech", "tech", "Halo Fintech adopts Salesforce + Gong"),
            ("Bridgewell Cloud", "hiring", "Bridgewell hiring VP Sales"),
            ("Pacific Ledger", "news", "Pacific Ledger expands into European market"),
            ("Cobaltbase", "hiring", "Cobaltbase hiring 3 Account Executives"),
        ]
        for company, kind, summary in signals_seed:
            db.add(Signal(
                strategy_id=s.id, account_id=accounts[company].id,
                signal_type=kind, source="ai_demo", summary=summary,
                strength_score=0.75 if kind == "funding" else 0.5,
            ))

        # Engagement events
        for company in ["Linear Stack Inc", "Halo Fintech", "Bridgewell Cloud"]:
            acct = accounts[company]
            for ev_type, score in [("page_view", 2), ("pricing_view", 8), ("case_study_view", 6), ("demo_request", 12)]:
                db.add(EngagementEvent(
                    strategy_id=s.id, account_id=acct.id, channel="website",
                    event_type=ev_type, intent_contribution_score=score,
                ))

        # Feedback
        for source, sentiment, themes, text in [
            ("nps", "positive", ["forecast accuracy", "ease of use"], "We finally trust our forecast — saves us hours weekly."),
            ("survey", "negative", ["price"], "Love the product but pricing is steep for our size."),
            ("form", "neutral", ["integrations"], "Need a HubSpot integration before we can adopt."),
        ]:
            db.add(FeedbackEntry(strategy_id=s.id, source=source, sentiment=sentiment, themes_json=themes, raw_text=text))

        # Attribution
        for ch, conv, val in [("email", "demo_booked", 0), ("linkedin", "trial_started", 0), ("paid_search", "deal_created", 25000)]:
            db.add(AttributionEvent(strategy_id=s.id, source_channel=ch, conversion_event=conv, conversion_value=val))

        # Pattern cluster
        db.add(PatternCluster(
            strategy_id=s.id,
            pattern_name="funding + hiring co-occurrence",
            signal_combination_json=["funding", "hiring"],
            conversion_rate=0.6,
            cluster_embedding=deterministic_embedding("funding + hiring"),
        ))

        db.commit()
        print(f"Seeded strategy {s.id}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
