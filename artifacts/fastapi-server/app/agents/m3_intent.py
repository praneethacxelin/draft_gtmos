"""M3 — Intelligence Loop: intent scoring, qualification, loop-back to S1."""
import json
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db import (
    Strategy,
    EngagementEvent,
    IntentScore,
    QualificationRecord,
    AttributionEvent,
    FeedbackEntry,
    GtmLoopUpdate,
    Contact,
    Account,
    Signal,
)
from app.llm import chat_json, MODEL_NAME
from app.provenance import stamp


HIGH_INTENT_PAGES = ("pricing", "demo", "case-study", "case_study", "trial")


def score_intent(db: Session, strategy_id: str) -> list[dict]:
    """Recompute intent scores for all accounts in this strategy."""
    cutoff = datetime.utcnow() - timedelta(days=30)
    accounts = db.query(Account).filter(Account.strategy_id == strategy_id).all()
    out = []
    for acct in accounts:
        events = (
            db.query(EngagementEvent)
            .filter(
                EngagementEvent.account_id == acct.id,
                EngagementEvent.occurred_at >= cutoff,
            )
            .all()
        )
        if not events:
            continue
        depth = sum(e.intent_contribution_score or 1 for e in events)
        recent = sum(
            (e.intent_contribution_score or 1)
            for e in events
            if e.occurred_at >= datetime.utcnow() - timedelta(days=7)
        ) * 3
        score = min(depth + recent, 100)

        if score >= 60:
            classification = "high"
        elif score >= 25:
            classification = "medium"
        else:
            classification = "low"

        # Replace previous score
        db.query(IntentScore).filter(
            IntentScore.account_id == acct.id, IntentScore.strategy_id == strategy_id
        ).delete()
        rec = IntentScore(
            account_id=acct.id,
            strategy_id=strategy_id,
            score=score,
            classification=classification,
        )
        db.add(rec)

        # Mirror engagement onto contacts at this account
        for c in db.query(Contact).filter(Contact.account_id == acct.id).all():
            c.engagement_score = min(score, 100)

        out.append({
            "account_id": acct.id,
            "company_name": acct.company_name,
            "score": score,
            "classification": classification,
        })

    db.commit()
    return out


async def capture_feedback_with_ai(db: Session, strategy_id: str, source: str, raw_text: str, contact_id=None) -> FeedbackEntry:
    extracted = await chat_json(
        f"Analyse this customer feedback and return JSON with keys: "
        f"sentiment ('positive'|'neutral'|'negative'), themes (array of 1-3 short strings). "
        f"Feedback: {raw_text[:1500]}",
        max_tokens=300,
    )
    themes = extracted.get("themes", []) or []
    entry = FeedbackEntry(
        strategy_id=strategy_id,
        contact_id=contact_id,
        source=source,
        sentiment=extracted.get("sentiment", "neutral"),
        themes_json=themes,
        raw_text=raw_text,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def qualify_contact(db: Session, contact_id: str) -> dict:
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        return {"error": "Contact not found"}
    intent = (
        db.query(IntentScore)
        .filter(IntentScore.account_id == contact.account_id)
        .order_by(IntentScore.computed_at.desc())
        .first()
    )
    intent_score = intent.score if intent else 0
    fit = contact.icp_fit_score or 0
    eng = contact.engagement_score or 0

    if fit >= 70 and intent_score >= 60:
        status = "sql"
    elif fit >= 70 or intent_score >= 40:
        status = "mql"
    else:
        status = "nurture"

    db.query(QualificationRecord).filter(QualificationRecord.contact_id == contact_id).delete()
    rec = QualificationRecord(
        contact_id=contact_id,
        strategy_id=contact.strategy_id,
        status=status,
        icp_fit_score=fit,
        intent_score=intent_score,
        engagement_score=eng,
    )
    db.add(rec)
    db.commit()
    return {"contact_id": contact_id, "status": status, "icp_fit": fit, "intent": intent_score}


async def loop_back(db: Session, strategy_id: str) -> dict:
    strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not strategy:
        return {"error": "Strategy not found"}

    # Aggregate evidence
    attr_rows = db.query(
        AttributionEvent.source_channel, func.count().label("n")
    ).filter(AttributionEvent.strategy_id == strategy_id).group_by(AttributionEvent.source_channel).all()
    feedback_themes: dict[str, int] = {}
    for f in db.query(FeedbackEntry).filter(FeedbackEntry.strategy_id == strategy_id).all():
        for theme in (f.themes_json or []):
            feedback_themes[theme] = feedback_themes.get(theme, 0) + 1

    sql_count = db.query(QualificationRecord).filter(
        QualificationRecord.strategy_id == strategy_id, QualificationRecord.status == "sql"
    ).count()
    mql_count = db.query(QualificationRecord).filter(
        QualificationRecord.strategy_id == strategy_id, QualificationRecord.status == "mql"
    ).count()

    summary = {
        "current_icp": strategy.icp_json,
        "attribution_top_channels": [{"channel": r[0], "count": r[1]} for r in attr_rows],
        "feedback_themes": feedback_themes,
        "sql_count": sql_count,
        "mql_count": mql_count,
    }

    delta = await chat_json(
        "Given this GTM performance summary, suggest concrete refinements to the ICP. "
        "Return JSON with keys: rationale (string), changes (array of {field, current_value, "
        "suggested_value, reason}), promote_personas (array of strings), deprioritize_personas "
        f"(array of strings). Summary: {json.dumps(summary)[:3000]}"
    )

    if isinstance(delta, dict) and "_error" not in delta:
        delta["_provenance"] = stamp(
            source="ai_generated",
            logic=(
                "Aggregated qualification, attribution, and feedback themes, then "
                "asked the model to suggest concrete ICP refinements as a delta."
            ),
            steps=[
                "Aggregate SQL/MQL counts from QualificationRecord",
                "Group AttributionEvent by source channel",
                "Tally FeedbackEntry themes",
                "Prompt model with the summary",
            ],
            counts={
                "sql_count": sql_count,
                "mql_count": mql_count,
                "feedback_themes": len(feedback_themes),
                "channels": len(attr_rows),
            },
            model=MODEL_NAME,
        )

    update = GtmLoopUpdate(
        strategy_id=strategy_id,
        trigger_summary=json.dumps(summary)[:1500],
        suggested_icp_delta_json=delta,
    )
    db.add(update)
    db.commit()
    db.refresh(update)
    return {"id": update.id, "delta": delta, "summary": summary}


def apply_loop_back(db: Session, update_id: str) -> dict:
    update = db.query(GtmLoopUpdate).filter(GtmLoopUpdate.id == update_id).first()
    if not update or update.applied:
        return {"applied": False}
    strategy = db.query(Strategy).filter(Strategy.id == update.strategy_id).first()
    if not strategy:
        return {"applied": False}

    icp = dict(strategy.icp_json or {})
    for change in (update.suggested_icp_delta_json or {}).get("changes", []):
        field = change.get("field")
        if field:
            icp[field] = change.get("suggested_value")
    strategy.icp_json = icp
    update.applied = True
    update.applied_at = datetime.utcnow()
    db.commit()
    return {"applied": True, "strategy_id": strategy.id}
