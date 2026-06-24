"""S3 — 3-Channel Outreach generation."""
import json
import random
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.db import Strategy, Contact, Sequence, SequenceStep, Account, InstantlyCampaign, OutreachEvent
from app.llm import chat_json, chat_text, MODEL_NAME
from app.services import settings_service, clients, audit_service
from app.services.instantly_poller import simulate_engagement_timeline
from app.provenance import stamp


SPAM_TRIGGERS = [
    # Classic spam words
    "free", "guarantee", "$$$", "act now", "click here", "buy now", "no risk",
    "limited time", "exclusive deal", "congratulations", "you've been selected",
    "urgent", "winner", "prize", "100%", "order now", "special offer",
    "risk-free", "no obligation", "lowest price", "best price", "discount",
    "double your", "earn money", "extra income", "make money", "cash bonus",
    "incredible deal", "offer expires", "once in a lifetime", "don't miss",
    "apply now", "call now", "click below", "direct email", "no cost",
    "no fees", "no strings attached", "satisfaction guaranteed", "while supplies last",
    "as seen on", "dear friend", "mass email", "bulk email", "multi-level",
    "hidden charges", "obligation", "unsolicited", "opt in", "opt out",
    "unsubscribe", "remove me", "cancel at any time", "no questions asked",
    "money back", "full refund",
]

SPAM_SUBJECT_TRIGGERS = [
    "re:", "fw:", "urgent", "act now", "limited time", "free", "winner",
    "congratulations", "$$$", "100%", "guaranteed", "!!!",
    "open immediately", "important notice", "action required",
]

URL_SHORTENERS = [
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd",
    "buff.ly", "rebrand.ly", "cutt.ly", "short.io",
]


def _normalize_merge_tags(text: str | None) -> str | None:
    if not text:
        return text
    # Replace various formats of company name to {{companyName}}
    for placeholder in ["{{{company_name}}}", "{{company_name}}", "{{{companyName}}}", "{{{company name}}}", "{{company name}}"]:
        text = text.replace(placeholder, "{{companyName}}")
    # Replace various formats of first name to {{firstName}}
    for placeholder in ["{{{first_name}}}", "{{first_name}}", "{{{firstName}}}", "{{{first name}}}", "{{first name}}"]:
        text = text.replace(placeholder, "{{firstName}}")
    return text


def _replace_merge_tags_with_values(text: str | None, contact: Contact, account: Account | None) -> str | None:
    if not text:
        return text
    # Normalize merge tags first
    text = _normalize_merge_tags(text)
    
    first_name = ""
    last_name = ""
    company_name = ""
    
    if contact:
        name_parts = (contact.full_name or "").split()
        first_name = name_parts[0] if name_parts else ""
        last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""
    if account:
        company_name = account.company_name or ""
        
    if first_name:
        text = text.replace("{{firstName}}", first_name)
    if last_name:
        text = text.replace("{{lastName}}", last_name)
    if company_name:
        text = text.replace("{{companyName}}", company_name)
        
    return text


def _replace_sender_placeholders(text: str | None, db: Session, user_id: str | None, strategy_id: str | None) -> str | None:
    if not text:
        return text
    
    sender_email = "your-email@company.com"
    sender_name = "Your Name"
    sender_first_name = "Your Name"
    sender_position = "GTM Specialist"
    sender_linkedin = "https://www.linkedin.com/in/gtm-expert"
    
    if user_id:
        instantly_key = settings_service.get_key(db, user_id, "instantly")
        if instantly_key:
            try:
                accounts = clients.instantly_get_accounts(instantly_key) or []
                active_accounts = [a for a in accounts if a.get("status") == 1]
                account = active_accounts[0] if active_accounts else (accounts[0] if accounts else None)
                if account:
                    sender_email = account.get("email") or sender_email
                    first = account.get("first_name") or ""
                    last = account.get("last_name") or ""
                    if first or last:
                        sender_name = f"{first} {last}".strip()
                        sender_first_name = first or sender_name
                    else:
                        part = sender_email.split("@")[0]
                        sender_name = part.replace(".", " ").title()
                        sender_first_name = part.split(".")[0].capitalize()
            except Exception:
                pass

    if sender_email and sender_email != "your-email@company.com" and sender_first_name == "Your Name":
        part = sender_email.split("@")[0]
        sender_first_name = part.split(".")[0].capitalize()
        sender_name = part.replace(".", " ").title()

    if strategy_id:
        strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
        product_name = strategy.product_name if strategy else "Our Company"
    else:
        product_name = "Our Company"
        
    mapping = {}
    
    def reg(patterns, replacement):
        for p in patterns:
            mapping[p.lower()] = replacement

    # Name
    reg([
        "{{{your name}}}", "{{your name}}", "[your name]", "your name",
        "{{{your first name}}}", "{{your first name}}", "[your first name]", "your first name"
    ], sender_first_name)
    
    # Company
    reg([
        "{{{your company}}}", "{{your company}}", "[your company]", "your company",
        "{{{company name}}}", "{{company name}}", "[company name]", "company name",
        "{{{your company name}}}", "{{your company name}}", "[your company name]", "your company name"
    ], product_name)
    
    # Contact Info
    reg([
        "{{{your contact information}}}", "{{your contact information}}", "[your contact information]", "your contact information",
        "{{{your contact info}}}", "{{your contact info}}", "[your contact info]", "your contact info",
        "{{{contact information}}}", "{{contact information}}", "[contact information]", "contact information",
        "{{{your email}}}", "{{your email}}", "[your email]", "your email",
        "{{{contact info}}}", "{{contact info}}", "[contact info]", "contact info"
    ], sender_email)
    
    # Position
    reg([
        "{{{your position}}}", "{{your position}}", "[your position]", "your position",
        "{{{your title}}}", "{{your title}}", "[your title]", "your title"
    ], sender_position)
    
    # LinkedIn
    reg([
        "{{{your linkedin profile}}}", "{{your linkedin profile}}", "[your linkedin profile]", "your linkedin profile",
        "{{{your linkedin}}}", "{{your linkedin}}", "[your linkedin]", "your linkedin",
        "{{{linkedin profile}}}", "{{linkedin profile}}", "[linkedin profile]", "linkedin profile",
        "{{{linkedin}}}", "{{linkedin}}", "[linkedin]", "linkedin"
    ], sender_linkedin)

    import re
    sorted_keys = sorted(mapping.keys(), key=len, reverse=True)
    pattern = re.compile("|".join(re.escape(k) for k in sorted_keys), re.IGNORECASE)

    def replacer(match):
        matched_text = match.group(0).lower()
        return mapping.get(matched_text, match.group(0))

    return pattern.sub(replacer, text)



async def generate_sequence(db: Session, contact_id: str, step_count: int = 4, dynamic: bool = False) -> dict:
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        return {"error": "Contact not found"}
    strategy = db.query(Strategy).filter(Strategy.id == contact.strategy_id).first()
    account = db.query(Account).filter(Account.id == contact.account_id).first()

    persona_block = ""
    if strategy and strategy.personas_json:
        ptype = contact.persona_type or "champion"
        persona = strategy.personas_json.get(ptype) if isinstance(strategy.personas_json, dict) else None
        if persona:
            persona_block = json.dumps(persona)[:600]

    use_cases = ""
    if strategy and strategy.use_cases_json:
        ucs = strategy.use_cases_json.get("use_cases", []) if isinstance(strategy.use_cases_json, dict) else []
        use_cases = json.dumps(ucs[:3])[:600]

    # Set default channel plan (always prioritises email first)
    if step_count == 5:
        channel_plan = [
            {"step": 1, "channel": "email", "wait_days": 0},
            {"step": 2, "channel": "email", "wait_days": 1},
            {"step": 3, "channel": "email", "wait_days": 2},
            {"step": 4, "channel": "linkedin", "wait_days": 3},
            {"step": 5, "channel": "linkedin", "wait_days": 4},
        ]
    else:
        channel_plan = [
            {"step": 1, "channel": "email", "wait_days": 0},
            {"step": 2, "channel": "email", "wait_days": 1},
            {"step": 3, "channel": "email", "wait_days": 2},
            {"step": 4, "channel": "linkedin", "wait_days": 3},
        ]

    # Log the channel plan decision
    audit_service.log_pipeline_event(
        stage="channel_plan",
        service="s3_outreach",
        strategy_id=contact.strategy_id,
        strategy_name=strategy.product_name if strategy else None,
        inputs={
            "contact_name": contact.full_name,
            "contact_title": contact.title,
            "persona_type": contact.persona_type,
            "step_count": step_count,
        },
        outputs={"channel_plan": channel_plan},
        decision=f"Generating default {step_count}-step sequence with 3 initial emails and subsequent LinkedIn step(s).",
        summary=f"S3 → Channel Plan: {step_count}-step sequence for {contact.full_name}",
    )

    # Personalize messages — with strong deliverability constraints
    plan_str = ", ".join(f"step {s['step']} via {s['channel']}" for s in channel_plan)
    contact_first = (contact.full_name or "there").split()[0]
    company_name = account.company_name if account else "the company"
    product_description = strategy.description if strategy else ""
    contact_department = contact.department or "Unknown"
    contact_seniority = contact.seniority or "Unknown"
    contact_persona = contact.persona_type or "Unknown"

    def _build_msg_prompt(extra_guidance: str = "") -> str:
        if dynamic:
            rule3 = (
                "3. This is a REUSABLE TEMPLATE for many similar leads — MUST greet the contact using "
                "the literal merge tag {{firstName}} in the opening line, and reference their company "
                "using the literal merge tag {{companyName}} at least once. Write these merge tags exactly "
                "as shown (with double curly braces). DO NOT write any real first name or company name. "
            )
        else:
            rule3 = (
                f"3. MUST include the contact's actual first name (use '{contact_first}') in the opening line, "
                f"and the actual company name (use '{company_name}') at least once — write their actual names directly, "
                "DO NOT use placeholders or merge tags like {{first_name}} or {{company_name}}. "
            )
        return (
            f"Write personalized outreach messages for {contact.full_name}, {contact.title} at "
            f"{company_name}. "
            f"Product Name: {strategy.product_name if strategy else ''}. "
            f"Product Description: {product_description}. "
            f"Persona profile: {persona_block}. Top use cases: {use_cases}. "
            f"Sequence: {plan_str}. Return JSON with key 'messages' = array of "
            "{{step, subject, body}}. "
            "DELIVERABILITY RULES (strictly follow all): "
            "1. Subjects must be under 60 characters, conversational, no punctuation spam. "
            "2. Email bodies must be 75-150 words — concise, specific, zero filler. "
            f"{rule3}"
            "4. MAX 1 hyperlink per email body — use full URLs only (no bit.ly or URL shorteners). "
            "5. NEVER use these words/phrases: free, guarantee, act now, click here, "
            "buy now, limited time, exclusive deal, urgent, winner, prize, 100%%, "
            "order now, special offer, risk-free, no obligation, earn money, make money, "
            "cash bonus, incredible deal, don't miss, apply now, call now, no cost, "
            "no fees, satisfaction guaranteed, money back, bulk email, mass email. "
            "6. No ALL-CAPS words. No '!!!', '???', or '$$$' patterns. "
            "7. For LinkedIn steps: 2-3 sentence DM, warm and human. "
            "8. For call steps: 3-bullet talking-points outline (no subject needed). "
            f"9. Write as if you are a trusted peer of {contact_first}, not a salesperson. "
            f"10. JOB-ROLE PROFILE ALIGNMENT: The outreach must be heavily tailored to their specific job role/profile (Title: {contact.title}, Department: {contact_department}, Seniority: {contact_seniority}, Persona Type: {contact_persona}). Adapt the tone, pain points, and use cases to directly address their specific department tasks, goals, and challenges. "
            f"11. PRODUCT PROFILE BRIEF: You must mention a small, natural brief/context about the product ({strategy.product_name if strategy else ''}: {product_description}) in the body of the email so the lead understands exactly what the product is and how it solves their challenges. "
            f"12. EMAIL THREADING FOLLOW-UPS: Step 1 is the initial email. Steps 2 and 3 are follow-up emails in the same thread (replies). Make sure the copy of Step 2 and Step 3 is written naturally as follow-ups to the preceding steps (e.g., refer back to the previous note, keep it shorter, check in on timing), rather than sounding like completely new, detached emails."
            f"{(' ' + extra_guidance) if extra_guidance else ''}"
        )

    msgs = await chat_json(_build_msg_prompt(), max_tokens=2000)

    audit_service.log_pipeline_event(
        stage="message_generation",
        service="s3_outreach",
        strategy_id=contact.strategy_id,
        strategy_name=strategy.product_name if strategy else None,
        inputs={
            "contact": contact.full_name,
            "company": account.company_name if account else None,
            "persona_block_len": len(persona_block),
            "use_cases_len": len(use_cases),
        },
        outputs=msgs,
        prompt=_build_msg_prompt(),
        summary=f"S3 → Message Draft: AI wrote {len(msgs.get('messages', [])) if isinstance(msgs, dict) else '?'} personalized steps (deliverability-hardened)",
    )

    # Persist
    seq = db.query(Sequence).filter(Sequence.contact_id == contact_id).first()
    if seq:
        db.query(SequenceStep).filter(SequenceStep.sequence_id == seq.id).delete()
    else:
        seq = Sequence(contact_id=contact_id, strategy_id=contact.strategy_id)
        db.add(seq)
        db.flush()

    seq.status = "draft"
    sequence_provenance = stamp(
        source="ai_generated",
        logic=(
            f"Generated a {step_count}-step plan prioritizing 3 emails then {step_count - 3} LinkedIn step(s), "
            "then asked the model to write personalised subject lines and bodies grounded in the lead's "
            "job role/department, the product description/brief, and natural follow-up threading rules."
        ),
        steps=[
            "Read contact + strategy + persona profile",
            f"Choose '{step_count}-step email-first' priority layout",
            "Prompt model for per-step subject + body with role personalization, product brief, and natural follow-up threading",
            "Auto deliverability check — re-prompt once if score < 70",
            "Schedule send_at timestamps",
        ],
        counts={"steps": len(channel_plan)},
        model=MODEL_NAME,
    )
    # Persist provenance alongside the plan so GET /sequences/by-contact
    # can serve it back to the UI without re-running the agent.
    seq.channel_plan_json = {"plan": channel_plan, "_provenance": sequence_provenance}

    base_time = datetime.utcnow().replace(hour=9, minute=0, second=0, microsecond=0)
    cumulative = 0
    msg_by_step = {m.get("step"): m for m in (msgs.get("messages", []) if isinstance(msgs, dict) else [])}
    owner_id = strategy.user_id if strategy else "user_public"
    for s in channel_plan:
        m = msg_by_step.get(s["step"], {})
        cumulative += s["wait_days"]
        send_at = base_time + timedelta(days=cumulative, hours=random.randint(0, 4))
        
        if dynamic:
            subject = _normalize_merge_tags(m.get("subject"))
            body = _normalize_merge_tags(m.get("body"))
        else:
            subject = _replace_merge_tags_with_values(m.get("subject"), contact, account)
            body = _replace_merge_tags_with_values(m.get("body"), contact, account)
        
        subject = _replace_sender_placeholders(subject, db, owner_id, contact.strategy_id)
        body = _replace_sender_placeholders(body, db, owner_id, contact.strategy_id)
        
        db.add(SequenceStep(
            sequence_id=seq.id,
            step_number=s["step"],
            channel=s["channel"],
            subject=subject,
            body=body,
            wait_days=s["wait_days"],
            send_at=send_at,
        ))
    db.commit()

    # ---- Auto deliverability check; re-generate once if score < 70 ----
    d_report = deliverability_check(db, seq.id)
    d_score = d_report.get("score", 100)

    if d_score < 70:
        # One retry with explicit guidance on what was wrong
        suggestions_str = "; ".join(d_report.get("suggestions", [])[:4])
        extra = (
            f"IMPORTANT — previous draft scored only {d_score}/100 on deliverability. "
            f"Fix these specific issues: {suggestions_str}. "
            "Rewrite all email steps to fully comply."
        )
        msgs2 = await chat_json(_build_msg_prompt(extra), max_tokens=2000)
        if isinstance(msgs2, dict) and msgs2.get("messages"):
            # Replace steps with improved copy
            db.query(SequenceStep).filter(SequenceStep.sequence_id == seq.id).delete()
            cumulative = 0
            msg_by_step2 = {m.get("step"): m for m in msgs2["messages"]}
            owner_id = strategy.user_id if strategy else "user_public"
            for s in channel_plan:
                m = msg_by_step2.get(s["step"], {})
                cumulative += s["wait_days"]
                send_at = base_time + timedelta(days=cumulative, hours=random.randint(0, 4))
                
                if dynamic:
                    subject = _normalize_merge_tags(m.get("subject"))
                    body = _normalize_merge_tags(m.get("body"))
                else:
                    subject = _replace_merge_tags_with_values(m.get("subject"), contact, account)
                    body = _replace_merge_tags_with_values(m.get("body"), contact, account)
                
                subject = _replace_sender_placeholders(subject, db, owner_id, contact.strategy_id)
                body = _replace_sender_placeholders(body, db, owner_id, contact.strategy_id)
                
                db.add(SequenceStep(
                    sequence_id=seq.id,
                    step_number=s["step"],
                    channel=s["channel"],
                    subject=subject,
                    body=body,
                    wait_days=s["wait_days"],
                    send_at=send_at,
                ))
            db.commit()
            # Re-run check to persist final score
            d_report = deliverability_check(db, seq.id)

    audit_service.log_pipeline_event(
        stage="deliverability_auto_check",
        service="s3_outreach",
        strategy_id=contact.strategy_id,
        strategy_name=strategy.product_name if strategy else None,
        inputs={"sequence_id": seq.id, "initial_score": d_score},
        outputs={"final_score": d_report.get("score"), "retried": d_score < 70},
        summary=(
            f"S3 → Auto deliverability: score {d_score} → {d_report.get('score')} "
            f"({'retried' if d_score < 70 else 'passed first attempt'})"
        ),
    )

    return {
        "sequence_id": seq.id,
        "step_count": len(channel_plan),
        "provenance": sequence_provenance,
        "deliverability_score": d_report.get("score"),
    }


def deliverability_check(db: Session, sequence_id: str) -> dict:
    """Comprehensive email deliverability and spam analysis.

    Checks email steps for spam triggers, excessive caps, punctuation abuse,
    personalization, subject line quality, URL shorteners, and body length.
    Returns a score 0-100 with actionable suggestions.
    """
    steps = db.query(SequenceStep).filter(
        SequenceStep.sequence_id == sequence_id, SequenceStep.channel == "email"
    ).all()
    if not steps:
        return {"score": 100, "flagged_phrases": [], "notes": "No email steps to evaluate."}

    flagged: list[str] = []
    subject_flagged: list[str] = []
    suggestions: list[str] = []
    total_chars = 0
    link_count = 0
    shortener_found = False
    total_words = 0
    caps_words = 0
    excessive_punctuation = False
    has_personalization = False

    for s in steps:
        body = (s.body or "").lower()
        body_raw = s.body or ""
        subject = (s.subject or "").lower()
        total_chars += len(body)

        # Word count and caps analysis
        words = body_raw.split()
        total_words += len(words)
        for w in words:
            if len(w) > 2 and w.isupper():
                caps_words += 1

        # Link count
        link_count += body.count("http")

        # URL shortener check
        for shortener in URL_SHORTENERS:
            if shortener in body:
                shortener_found = True
                break

        # Spam trigger check (body)
        for trig in SPAM_TRIGGERS:
            if trig in body and trig not in flagged:
                flagged.append(trig)

        # Spam trigger check (subject)
        for trig in SPAM_SUBJECT_TRIGGERS:
            if trig in subject and trig not in subject_flagged:
                subject_flagged.append(trig)

        # Excessive punctuation
        if "!!!" in body or "???" in body or "$$$" in body:
            excessive_punctuation = True

        # Personalization check (look for merge tags or contact-specific content)
        personalization_markers = [
            "{first_name}", "{last_name}", "{company_name}", "{company}",
            "{name}", "{{first_name}}", "{{company}}", "hi ", "hey ",
        ]
        for marker in personalization_markers:
            if marker in body:
                has_personalization = True
                break

    # ---- Scoring ----
    score = 100
    avg_words = total_words / max(len(steps), 1)
    avg_length = int(total_chars / max(len(steps), 1))

    # Spam triggers in body: -5 each, max -25
    body_penalty = min(len(flagged) * 5, 25)
    if body_penalty:
        score -= body_penalty
        suggestions.append(f"Remove spam trigger words: {', '.join(flagged[:5])}")

    # Spam triggers in subject: -15
    if subject_flagged:
        score -= 15
        suggestions.append(f"Subject line contains spam words: {', '.join(subject_flagged[:3])}")

    # Excessive caps: -10 if >30% of words are ALL CAPS
    if total_words > 0 and (caps_words / total_words) > 0.3:
        score -= 10
        suggestions.append("Too many ALL CAPS words — reduces trust and triggers spam filters")

    # Excessive punctuation: -5
    if excessive_punctuation:
        score -= 5
        suggestions.append("Avoid excessive punctuation (!!!, ???, $$$)")

    # Too many links: -10 if >2
    if link_count > 2:
        score -= 10
        suggestions.append(f"Too many links ({link_count}) — keep to 1-2 per email")

    # URL shorteners: -10
    if shortener_found:
        score -= 10
        suggestions.append("Avoid URL shorteners (bit.ly, etc.) — use full URLs for trust")

    # Body too long: -5 if avg >300 words
    if avg_words > 300:
        score -= 5
        suggestions.append(f"Emails are too long ({int(avg_words)} avg words) — aim for 50-200 words")

    # Body too short: -5 if avg <30 words
    if avg_words < 30 and avg_words > 0:
        score -= 5
        suggestions.append(f"Emails are too short ({int(avg_words)} avg words) — add more value")

    # No personalization: -10
    if not has_personalization:
        score -= 10
        suggestions.append("Add personalization (use recipient's name or company name)")
    else:
        # Personalization bonus: +5
        score = min(score + 5, 100)

    score = max(score, 0)

    # Generate overall assessment
    if score >= 90:
        notes = "Excellent deliverability — your emails should land in the primary inbox."
    elif score >= 75:
        notes = "Good deliverability — minor improvements recommended."
    elif score >= 50:
        notes = "Fair deliverability — several issues should be addressed before sending."
    else:
        notes = "Poor deliverability — significant changes needed to avoid spam folder."

    report = {
        "score": score,
        "flagged_phrases": list(set(flagged)),
        "subject_flags": list(set(subject_flagged)),
        "link_count": link_count,
        "avg_length": avg_length,
        "avg_words": int(avg_words),
        "has_personalization": has_personalization,
        "shortener_detected": shortener_found,
        "excessive_caps": total_words > 0 and (caps_words / total_words) > 0.3,
        "suggestions": suggestions,
        "notes": notes,
    }

    sequence = db.query(Sequence).filter(Sequence.id == sequence_id).first()
    if sequence:
        sequence.deliverability_score = score
        sequence.deliverability_report_json = report
        db.commit()

    return report


def launch_sequence(
    db: Session,
    sequence_id: str,
    test_email: str | None = None,
    schedule: dict | None = None,
    is_test: bool = False,
) -> dict:
    """Launch or test-launch a sequence.

    When ``is_test=True`` the email is sent to ``test_email`` (which is
    required) and the sequence status is kept as ``"draft"`` so that a real
    launch can still be performed later.  All other behaviour — Instantly
    campaign creation, lead add, activation — is identical to a live launch.
    When ``is_test=False`` this is a live launch: the actual lead email is
    used and status moves to ``"active"``.
    """
    seq = db.query(Sequence).filter(Sequence.id == sequence_id).first()
    if not seq:
        return {"error": "Sequence not found"}

    strategy = db.query(Strategy).filter(Strategy.id == seq.strategy_id).first() if seq.strategy_id else None
    owner_id = strategy.user_id if strategy else None
    instantly_key = settings_service.get_key(db, owner_id, "instantly")
    steps = db.query(SequenceStep).filter(SequenceStep.sequence_id == sequence_id).order_by(SequenceStep.step_number).all()

    if instantly_key:
        contact = db.query(Contact).filter(Contact.id == seq.contact_id).first()
        account = db.query(Account).filter(Account.id == contact.account_id).first() if contact and contact.account_id else None

        # Only include email steps in the Instantly sequence
        email_steps = [s for s in steps if s.channel == "email"]
        campaign_steps = email_steps if email_steps else steps

        result = clients.instantly_create_campaign(
            instantly_key,
            f"GTM-{seq.id[:8]}",
            [{"channel": s.channel, "subject": _replace_merge_tags_with_values(s.subject, contact, account), "body": _replace_merge_tags_with_values(s.body, contact, account), "wait_days": s.wait_days} for s in campaign_steps],
            _strategy_id=seq.strategy_id,
            _strategy_name=strategy.product_name if strategy else None,
            schedule=schedule,
        )
        campaign_id = (result or {}).get("id") if isinstance(result, dict) else None

        if not campaign_id:
            # Instantly rejected the campaign — log the raw error and fall
            # back to simulated mode so the sequence still progresses.
            instantly_error = (result or {}).get("error") or "Instantly campaign creation returned no ID"
            audit_service.log_pipeline_event(
                stage="launch_instantly_error",
                service="s3_outreach",
                strategy_id=seq.strategy_id,
                strategy_name=strategy.product_name if strategy else None,
                inputs={"sequence_id": sequence_id, "is_test": is_test},
                outputs={"instantly_raw_response": result},
                summary=f"S3 → Instantly rejected campaign: {instantly_error[:200]}",
            )
            seq.status = "draft" if is_test else "simulated"
            db.commit()
            ingested = simulate_engagement_timeline(db, seq.id)
            return {
                "status": seq.status,
                "instantly_pushed": False,
                "events": ingested,
                "is_test": is_test,
                "warning": f"Instantly campaign creation failed — simulated instead. Error: {instantly_error[:300]}",
            }

        # Status: test launches keep "draft" so live launch can still be done;
        # live launches promote to "active".
        new_status = "draft" if is_test else "active"
        seq.status = new_status
        # Only persist the campaign ID on a live launch so the badge only
        # shows "Active via Instantly" for real launches.
        if not is_test:
            seq.instantly_campaign_id = campaign_id
        lead_email: str | None = None

        if campaign_id:
            db.add(InstantlyCampaign(
                sequence_id=seq.id,
                instantly_campaign_id=str(campaign_id),
                status="test" if is_test else "active",
            ))

            # Determine recipient:
            # • Test launch  → test_email (required; caller validates this)
            # • Live launch  → actual contact email
            lead_email = test_email if is_test else (contact.email if contact else None)
            if lead_email:
                name_parts = (contact.full_name if contact else "Test User").split()
                # For test launches use tester's name so personalisation
                # looks correct in the test inbox.
                if is_test:
                    first = name_parts[0] if name_parts else "Test"
                    last = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""
                    personalization = f"Hi {first}"   # real contact greeting
                else:
                    first = name_parts[0] if name_parts else ""
                    last = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""
                    personalization = f"Hi {first}"

                clients.instantly_add_leads(
                    instantly_key,
                    campaign_id,
                    leads=[{
                        "email": lead_email,
                        "first_name": first,
                        "last_name": last,
                        "company_name": account.company_name if account else "",
                        "personalization": personalization,
                    }],
                    _strategy_id=seq.strategy_id,
                    _strategy_name=strategy.product_name if strategy else None,
                )
                # Activate the campaign — Instantly starts sending immediately
                clients.instantly_launch_campaign(
                    instantly_key,
                    campaign_id,
                    _strategy_id=seq.strategy_id,
                    _strategy_name=strategy.product_name if strategy else None,
                )

            # Record outreach events for both test and live launches.
            event_type_prefix = "test_sent" if is_test else "sent"
            for s in steps:
                s.sent_at = datetime.utcnow()
                s.status = event_type_prefix
                db.add(OutreachEvent(
                    sequence_id=seq.id,
                    sequence_step_id=s.id,
                    event_type=event_type_prefix,
                    raw_data_json={
                        "instantly_campaign_id": campaign_id,
                        "is_test": is_test,
                        "recipient": lead_email,
                    },
                ))
        db.commit()
        return {
            "status": new_status,
            "instantly_pushed": True,
            "campaign_id": campaign_id,
            "lead_email": lead_email,
            "is_test": is_test,
        }
    else:
        seq.status = "draft" if is_test else "simulated"
        db.commit()
        ingested = simulate_engagement_timeline(db, seq.id)
        return {"status": seq.status, "instantly_pushed": False, "events": ingested, "is_test": is_test}


def launch_group_sequence(
    db: Session,
    contact_ids: list[str],
    template_sequence_id: str | None = None,
    schedule: dict | None = None,
    campaign_name: str | None = None,
    is_test: bool = False,
    test_email: str | None = None,
) -> dict:
    """Create ONE Instantly campaign containing MULTIPLE selected contacts as leads.

    The steps of ``template_sequence_id`` (a generated sequence) are used as a
    reusable, dynamic-variable template: recipient fields stay as
    ``{{firstName}}`` / ``{{companyName}}`` so Instantly personalises each lead,
    while sender placeholders are resolved up-front.  Every selected contact is
    added as a lead with its real first/last/company values, sending accounts
    are auto-assigned (the campaign "from"), the schedule (timezone / window /
    days) is applied, and the campaign is activated.
    """
    if not contact_ids:
        return {"error": "No contacts selected"}

    seq = None
    if template_sequence_id:
        seq = db.query(Sequence).filter(Sequence.id == template_sequence_id).first()
    if not seq:
        seq = db.query(Sequence).filter(Sequence.contact_id == contact_ids[0]).first()
    if not seq:
        return {"error": "No sequence found to use as a template. Generate a sequence first."}

    strategy = db.query(Strategy).filter(Strategy.id == seq.strategy_id).first() if seq.strategy_id else None
    owner_id = strategy.user_id if strategy else None
    instantly_key = settings_service.get_key(db, owner_id, "instantly")
    if not instantly_key:
        return {"error": "No Instantly key configured for this workspace."}

    steps = db.query(SequenceStep).filter(SequenceStep.sequence_id == seq.id).order_by(SequenceStep.step_number).all()
    email_steps = [s for s in steps if s.channel == "email"]
    campaign_steps = email_steps if email_steps else steps
    if not campaign_steps:
        return {"error": "Template sequence has no steps to send."}

    # Build dynamic merge-tag template steps. Recipient tags ({{firstName}} /
    # {{companyName}}) are kept so Instantly fills them per lead; sender
    # placeholders are resolved here.
    template_steps = []
    for s in campaign_steps:
        subj = _replace_sender_placeholders(_normalize_merge_tags(s.subject), db, owner_id, seq.strategy_id)
        body = _replace_sender_placeholders(_normalize_merge_tags(s.body), db, owner_id, seq.strategy_id)
        template_steps.append({
            "channel": s.channel,
            "subject": subj,
            "body": body,
            "wait_days": s.wait_days,
        })

    name = campaign_name or f"GTM-Group-{seq.id[:8]}"
    result = clients.instantly_create_campaign(
        instantly_key,
        name,
        template_steps,
        _strategy_id=seq.strategy_id,
        _strategy_name=strategy.product_name if strategy else None,
        schedule=schedule,
    )
    campaign_id = (result or {}).get("id") if isinstance(result, dict) else None
    if not campaign_id:
        instantly_error = (result or {}).get("error") if isinstance(result, dict) else None
        return {"error": f"Instantly campaign creation failed: {str(instantly_error or 'no campaign id returned')[:300]}"}

    contacts = db.query(Contact).filter(Contact.id.in_(contact_ids)).all()

    leads: list[dict] = []
    if is_test and test_email:
        c0 = contacts[0] if contacts else None
        name_parts = (c0.full_name if c0 else "Test User").split()
        first = name_parts[0] if name_parts else "Test"
        last = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""
        acct = db.query(Account).filter(Account.id == c0.account_id).first() if c0 and c0.account_id else None
        leads.append({
            "email": test_email,
            "first_name": first,
            "last_name": last,
            "company_name": acct.company_name if acct else "",
            "personalization": f"Hi {first}" if first else "Hi there",
        })
    else:
        for c in contacts:
            if not c.email:
                continue
            acct = db.query(Account).filter(Account.id == c.account_id).first() if c.account_id else None
            name_parts = (c.full_name or "").split()
            first = name_parts[0] if name_parts else ""
            last = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""
            leads.append({
                "email": c.email,
                "first_name": first,
                "last_name": last,
                "company_name": acct.company_name if acct else "",
                "personalization": f"Hi {first}" if first else "Hi there",
            })

    leads_added = 0
    if leads:
        add_res = clients.instantly_add_leads(
            instantly_key,
            campaign_id,
            leads=leads,
            _strategy_id=seq.strategy_id,
            _strategy_name=strategy.product_name if strategy else None,
        )
        leads_added = (add_res or {}).get("total_new_leads", 0) if isinstance(add_res, dict) else 0

    if not is_test:
        clients.instantly_launch_campaign(
            instantly_key,
            campaign_id,
            _strategy_id=seq.strategy_id,
            _strategy_name=strategy.product_name if strategy else None,
        )

    db.add(InstantlyCampaign(
        sequence_id=seq.id,
        instantly_campaign_id=str(campaign_id),
        status="test" if is_test else "active",
    ))
    if not is_test:
        seq.status = "active"
        if not seq.instantly_campaign_id:
            seq.instantly_campaign_id = str(campaign_id)
    db.commit()

    return {
        "status": "test" if is_test else "active",
        "instantly_pushed": True,
        "campaign_id": campaign_id,
        "campaign_name": name,
        "leads_added": leads_added,
        "contacts_count": len(contact_ids),
        "is_test": is_test,
    }
