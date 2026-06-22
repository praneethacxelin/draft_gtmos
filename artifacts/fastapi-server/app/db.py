"""SQLAlchemy models + DB session for the GTM Factory.

All tables created with `init_db()` on startup. ICP/pattern embeddings are
stored as JSON lists; the queryable vector store is ChromaDB
(``app/services/vector_store.py``) so the stack stays portable to Windows
without compiling the pgvector native extension.
"""
import os
import uuid
from datetime import datetime
from typing import Optional, Generator

from sqlalchemy import (
    create_engine,
    Column,
    String,
    Integer,
    Float,
    Boolean,
    DateTime,
    Text,
    ForeignKey,
    JSON,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship
from sqlalchemy.types import TypeDecorator
from sqlalchemy.dialects.postgresql import JSONB as PgJSONB, ARRAY as PgARRAY


def _db_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is required")
    # SQLAlchemy expects postgresql+psycopg:// for psycopg v3
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url

db_url = _db_url()
is_sqlite = db_url.startswith("sqlite")

if is_sqlite:
    JSONB = JSON
    class SqliteARRAY(TypeDecorator):
        impl = JSON
        cache_ok = True
        def process_bind_param(self, value, dialect):
            return value
        def process_result_value(self, value, dialect):
            return value
    def PgARRAY(item_type):
        return SqliteARRAY()
    engine = create_engine(db_url, pool_pre_ping=True)
else:
    JSONB = PgJSONB
    engine = create_engine(db_url, pool_pre_ping=True, pool_size=5, max_overflow=10)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def gen_id() -> str:
    return str(uuid.uuid4())


def now() -> datetime:
    return datetime.utcnow()


# ---------- Users ----------
#
# Authentication has been removed. The ``users`` table is kept because
# downstream rows still hold user_id foreign keys (legacy from when the
# app shipped with an auth provider). All requests resolve to the
# shared ``user_public`` row created on startup by ``app.auth``.


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True)  # opaque user id (e.g. user_public)
    email = Column(String, nullable=True)
    is_admin = Column(Boolean, nullable=False, default=False, server_default="false")
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


# ---------- Settings (in-app integration config) ----------


class AppSetting(Base):
    __tablename__ = "app_settings"
    __table_args__ = (
        UniqueConstraint("user_id", "integration_name", name="uq_app_settings_user_integration"),
    )
    id = Column(String, primary_key=True, default=gen_id)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    integration_name = Column(String, nullable=False)  # serpapi/apollo/clay/instantly
    api_key_encrypted = Column(Text, nullable=True)
    is_enabled = Column(Boolean, default=False, nullable=False)
    last_tested_at = Column(DateTime, nullable=True)
    test_status = Column(String, nullable=True)  # ok/failed/untested
    test_message = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=now, onupdate=now)


# ---------- Core GTM ----------


class Strategy(Base):
    __tablename__ = "strategies"
    id = Column(String, primary_key=True, default=gen_id)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    product_name = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    target_market = Column(Text, nullable=True)
    pain_points_raw = Column(Text, nullable=True)
    icp_json = Column(JSONB, nullable=True)
    personas_json = Column(JSONB, nullable=True)
    problems_json = Column(JSONB, nullable=True)
    naics_json = Column(JSONB, nullable=True)
    stakeholder_map_json = Column(JSONB, nullable=True)
    use_cases_json = Column(JSONB, nullable=True)
    tam_sam_som_json = Column(JSONB, nullable=True)
    # ROI expectation validation (investment vs expected revenue) grounded in
    # this profile's market sizing + ICP. Computed by app/agents/roi_validator.py.
    roi_json = Column(JSONB, nullable=True)
    status = Column(String, default="draft")  # draft / generating / ready
    discovery_data = Column(JSONB, nullable=True)
    last_signal_scan = Column(DateTime, nullable=True)
    daily_signal_summary = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class IcpEmbedding(Base):
    __tablename__ = "icp_embeddings"
    id = Column(String, primary_key=True, default=gen_id)
    strategy_id = Column(String, ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False)
    # Stored as a JSON list of floats. ChromaDB is the queryable vector store
    # (see app/services/vector_store.py); this column keeps a portable copy
    # and avoids the pgvector native extension (hard to compile on Windows).
    embedding = Column(JSONB, nullable=False)
    summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=now)


class Competitor(Base):
    __tablename__ = "competitor_profiles"
    id = Column(String, primary_key=True, default=gen_id)
    strategy_id = Column(String, ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    website = Column(String, nullable=True)
    positioning = Column(Text, nullable=True)
    features_json = Column(JSONB, nullable=True)
    pricing_info = Column(Text, nullable=True)
    weaknesses_json = Column(JSONB, nullable=True)
    g2_rating = Column(Float, nullable=True)
    last_updated = Column(DateTime, default=now)


class Account(Base):
    __tablename__ = "accounts"
    id = Column(String, primary_key=True, default=gen_id)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    strategy_id = Column(String, ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False)
    company_name = Column(String, nullable=False)
    domain = Column(String, nullable=True)
    industry = Column(String, nullable=True)
    employee_count = Column(Integer, nullable=True)
    revenue_range = Column(String, nullable=True)
    location = Column(String, nullable=True)
    founded_year = Column(Integer, nullable=True)
    tech_stack_json = Column(JSONB, nullable=True)
    enrichment_json = Column(JSONB, nullable=True)
    tier = Column(Integer, nullable=True)  # 1/2/3
    created_at = Column(DateTime, default=now)


class Contact(Base):
    __tablename__ = "contacts"
    id = Column(String, primary_key=True, default=gen_id)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    account_id = Column(String, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    strategy_id = Column(String, ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False)
    full_name = Column(String, nullable=False)
    title = Column(String, nullable=True)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    linkedin_url = Column(String, nullable=True)
    seniority = Column(String, nullable=True)
    department = Column(String, nullable=True)
    persona_type = Column(String, nullable=True)  # champion/economic_buyer/blocker
    icp_fit_score = Column(Float, default=0.0)
    signal_score = Column(Float, default=0.0)
    engagement_score = Column(Float, default=0.0)
    total_score = Column(Float, default=0.0)
    tier = Column(Integer, nullable=True)
    is_demo = Column(Boolean, default=False)
    email_verified = Column(String, nullable=True)  # valid/invalid/catch_all/pending/None
    # Where this contact came from, so outreach can group leads by origin:
    #   discovery  — standard ICP/persona lead search
    #   experiment — pulled via a winning experiment's facets
    #   campaign   — pulled as part of phased campaign execution
    source = Column(String, default="discovery", nullable=True)
    source_ref = Column(String, nullable=True)  # batch_id / experiment_id / phase label
    created_at = Column(DateTime, default=now)


class Signal(Base):
    __tablename__ = "signals"
    id = Column(String, primary_key=True, default=gen_id)
    strategy_id = Column(String, ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False)
    account_id = Column(String, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=True)
    signal_type = Column(String, nullable=False)  # funding/hiring/tech/engagement/news
    source = Column(String, nullable=True)  # serpapi/m3_tracking/ai_demo/...
    summary = Column(Text, nullable=False)
    strength_score = Column(Float, default=0.5)
    raw_data_json = Column(JSONB, nullable=True)
    detected_at = Column(DateTime, default=now)


class PatternCluster(Base):
    __tablename__ = "pattern_clusters"
    id = Column(String, primary_key=True, default=gen_id)
    strategy_id = Column(String, ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False)
    pattern_name = Column(String, nullable=False)
    signal_combination_json = Column(JSONB, nullable=True)
    conversion_rate = Column(Float, default=0.0)
    cluster_embedding = Column(JSONB, nullable=True)  # JSON list of floats (see vector_store.py)
    created_at = Column(DateTime, default=now)


# ---------- Scoring ----------


class LeadScore(Base):
    __tablename__ = "lead_scores"
    id = Column(String, primary_key=True, default=gen_id)
    contact_id = Column(String, ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False)
    strategy_id = Column(String, ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False)
    icp_fit_score = Column(Float, default=0.0)
    engagement_score = Column(Float, default=0.0)
    signal_score = Column(Float, default=0.0)
    pattern_bonus = Column(Float, default=0.0)
    total_score = Column(Float, default=0.0)
    tier = Column(Integer, nullable=True)  # 1/2/3
    qualified_at = Column(DateTime, default=now)


# ---------- Outreach ----------


class Sequence(Base):
    __tablename__ = "sequences"
    id = Column(String, primary_key=True, default=gen_id)
    contact_id = Column(String, ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False)
    strategy_id = Column(String, ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False)
    channel_plan_json = Column(JSONB, nullable=True)
    status = Column(String, default="draft")  # draft/active/paused/complete/simulated
    instantly_campaign_id = Column(String, nullable=True)
    deliverability_score = Column(Float, nullable=True)
    deliverability_report_json = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=now)


class SequenceStep(Base):
    __tablename__ = "sequence_steps"
    id = Column(String, primary_key=True, default=gen_id)
    sequence_id = Column(String, ForeignKey("sequences.id", ondelete="CASCADE"), nullable=False)
    step_number = Column(Integer, nullable=False)
    channel = Column(String, nullable=False)  # email/linkedin/call
    subject = Column(String, nullable=True)
    body = Column(Text, nullable=True)
    wait_days = Column(Integer, default=0)
    send_at = Column(DateTime, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    status = Column(String, default="pending")  # pending/sent/skipped


class InstantlyCampaign(Base):
    __tablename__ = "instantly_campaigns"
    id = Column(String, primary_key=True, default=gen_id)
    sequence_id = Column(String, ForeignKey("sequences.id", ondelete="CASCADE"), nullable=False)
    instantly_campaign_id = Column(String, nullable=False)
    status = Column(String, default="active")
    analytics_json = Column(JSONB, nullable=True)
    daily_analytics_json = Column(JSONB, nullable=True)
    steps_analytics_json = Column(JSONB, nullable=True)
    synced_at = Column(DateTime, default=now)


class OutreachEvent(Base):
    __tablename__ = "outreach_events"
    id = Column(String, primary_key=True, default=gen_id)
    sequence_id = Column(String, ForeignKey("sequences.id", ondelete="CASCADE"), nullable=False)
    sequence_step_id = Column(String, ForeignKey("sequence_steps.id", ondelete="CASCADE"), nullable=True)
    event_type = Column(String, nullable=False)  # sent/opened/clicked/replied/bounced
    occurred_at = Column(DateTime, default=now)
    raw_data_json = Column(JSONB, nullable=True)


# ---------- M3 Intelligence Loop ----------


class EngagementEvent(Base):
    __tablename__ = "engagement_events"
    id = Column(String, primary_key=True, default=gen_id)
    contact_id = Column(String, ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True)
    account_id = Column(String, ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True)
    strategy_id = Column(String, ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False)
    channel = Column(String, nullable=False)
    event_type = Column(String, nullable=False)  # page_view / ad_click / video_view / form_fill / email_open
    intent_contribution_score = Column(Float, default=1.0)
    metadata_json = Column(JSONB, nullable=True)
    occurred_at = Column(DateTime, default=now)


class IntentScore(Base):
    __tablename__ = "intent_scores"
    id = Column(String, primary_key=True, default=gen_id)
    account_id = Column(String, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    strategy_id = Column(String, ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False)
    score = Column(Float, default=0.0)
    classification = Column(String, default="low")  # low/medium/high
    computed_at = Column(DateTime, default=now)


class FeedbackEntry(Base):
    __tablename__ = "feedback_entries"
    id = Column(String, primary_key=True, default=gen_id)
    strategy_id = Column(String, ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False)
    contact_id = Column(String, ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True)
    source = Column(String, nullable=False)  # survey/nps/form/rating
    sentiment = Column(String, default="neutral")  # positive/neutral/negative
    themes_json = Column(JSONB, nullable=True)
    raw_text = Column(Text, nullable=True)
    captured_at = Column(DateTime, default=now)


class AttributionEvent(Base):
    __tablename__ = "attribution_events"
    id = Column(String, primary_key=True, default=gen_id)
    strategy_id = Column(String, ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False)
    contact_id = Column(String, ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True)
    source_channel = Column(String, nullable=False)
    touchpoint_type = Column(String, nullable=True)
    conversion_event = Column(String, nullable=False)  # demo_booked / trial_started / deal_created
    conversion_value = Column(Float, default=0.0)
    occurred_at = Column(DateTime, default=now)


class QualificationRecord(Base):
    __tablename__ = "qualification_records"
    id = Column(String, primary_key=True, default=gen_id)
    contact_id = Column(String, ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False)
    strategy_id = Column(String, ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False)
    status = Column(String, nullable=False)  # mql/sql/nurture
    icp_fit_score = Column(Float, default=0.0)
    intent_score = Column(Float, default=0.0)
    engagement_score = Column(Float, default=0.0)
    decided_at = Column(DateTime, default=now)


class ContactSnooze(Base):
    __tablename__ = "contact_snoozes"
    id = Column(String, primary_key=True, default=gen_id)
    contact_id = Column(String, ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False)
    strategy_id = Column(String, ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False)
    snoozed_until = Column(DateTime, nullable=False)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class GtmLoopUpdate(Base):
    __tablename__ = "gtm_loop_updates"
    id = Column(String, primary_key=True, default=gen_id)
    strategy_id = Column(String, ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False)
    trigger_summary = Column(Text, nullable=True)
    suggested_icp_delta_json = Column(JSONB, nullable=True)
    applied = Column(Boolean, default=False)
    applied_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=now)


# ---------- Audit ----------


class AuditLog(Base):
    """Immutable log of every external API call and every data change.

    ``strategy_id`` is stored as a plain string (no FK) so audit rows
    survive strategy deletion.
    """
    __tablename__ = "audit_logs"
    id = Column(String, primary_key=True, default=gen_id)
    occurred_at = Column(DateTime, default=now, index=True)
    event_type = Column(String, nullable=False)  # api_call | strategy_change | contact_change | step_change
    service = Column(String, nullable=True)       # serpapi / apollo / instantly / openai / internal
    strategy_id = Column(String, nullable=True, index=True)
    strategy_name = Column(String, nullable=True)
    http_method = Column(String, nullable=True)
    endpoint_url = Column(Text, nullable=True)
    request_params = Column(JSONB, nullable=True)
    response_status = Column(Integer, nullable=True)
    response_summary = Column(JSONB, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    curl_command = Column(Text, nullable=True)
    is_live = Column(Boolean, default=True)
    entity_type = Column(String, nullable=True)   # strategy / contact / step
    entity_id = Column(String, nullable=True)
    change_field = Column(String, nullable=True)
    change_before = Column(JSONB, nullable=True)
    change_after = Column(JSONB, nullable=True)
    actor = Column(String, nullable=True)         # user | agent
    summary = Column(Text, nullable=True)


# ---------- Experiments (Apollo parameter search) ----------
#
# A profile can run multiple experiment batches. Each batch holds N
# experiments — distinct Apollo facet combinations (location, industry,
# employee size, revenue, titles, …) — that are run against Apollo and then
# analysed together so the LLM can surface the best-performing parameter set
# and the most relevant leads for the product profile.


class ExperimentBatch(Base):
    __tablename__ = "experiment_batches"
    id = Column(String, primary_key=True, default=gen_id)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    strategy_id = Column(String, ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=True)
    n_experiments = Column(Integer, nullable=False, default=3)
    leads_per_experiment = Column(Integer, nullable=False, default=10)
    status = Column(String, default="draft")  # draft / seeded / running / analyzed
    hypothesis = Column(Text, nullable=True)
    best_experiment_id = Column(String, nullable=True)
    analysis_json = Column(JSONB, nullable=True)  # cross-experiment summary + ranking
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class Experiment(Base):
    __tablename__ = "experiments"
    id = Column(String, primary_key=True, default=gen_id)
    batch_id = Column(String, ForeignKey("experiment_batches.id", ondelete="CASCADE"), nullable=False, index=True)
    strategy_id = Column(String, ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False, index=True)
    idx = Column(Integer, nullable=False)  # 1-based position within the batch
    name = Column(String, nullable=True)
    hypothesis = Column(Text, nullable=True)
    # Editable Apollo facet form: {titles, seniorities, locations, industries,
    # employee_ranges, technologies, revenue_ranges}
    params_json = Column(JSONB, nullable=True)
    source = Column(String, default="ai")  # ai | user
    status = Column(String, default="draft")  # draft / running / done / failed
    # Run outputs
    result_summary_json = Column(JSONB, nullable=True)  # counts, winning tier, provenance
    leads_json = Column(JSONB, nullable=True)  # list of normalized lead dicts (NOT persisted to contacts)
    relevancy_json = Column(JSONB, nullable=True)  # per-experiment relevancy scoring vs profile
    score = Column(Float, nullable=True)  # composite 0-100 (relevancy x volume)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


# ---------- Learnings ----------
#
# Centralized "what we've learned" memory. Every workstream (experiments,
# persona intelligence, outreach, manual notes) writes durable insights here
# so the rest of the factory can recall them. The text is also embedded into
# the ChromaDB ``gtm_learnings`` collection (see vector_store) for semantic
# similarity search; ``embedded`` records whether that succeeded.


class Learning(Base):
    __tablename__ = "learnings"
    id = Column(String, primary_key=True, default=gen_id)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    # Tagged with a source strategy for filtering, but learnings are recallable
    # across strategies (cross-pollination of what works).
    strategy_id = Column(String, ForeignKey("strategies.id", ondelete="SET NULL"), nullable=True, index=True)
    category = Column(String, nullable=False, default="general", index=True)
    # persona | segment | messaging | timing | experiment | channel | general
    title = Column(String, nullable=True)
    content = Column(Text, nullable=False)  # the learning text (this is what gets embedded)
    source = Column(String, default="manual")  # experiment | persona | outreach | roi | manual
    source_ref = Column(String, nullable=True)  # e.g. batch_id / experiment_id / contact_id
    metrics_json = Column(JSONB, nullable=True)  # supporting numbers (response %, depth, score)
    tags_json = Column(JSONB, nullable=True)  # list[str] for filtering
    confidence = Column(String, default="Moderate")  # High | Moderate | Low
    embedded = Column(Boolean, default=False)  # stored in the vector collection
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


# ---------- Helpers ----------


def init_db() -> None:
    """Run light migrations and create new tables.

    Heavy schema migrations live under ``alembic/`` (see ``alembic upgrade
    head``). The startup hook here only does the additive work needed for
    the seeded demo to come up cleanly: drop the legacy ``competitors``
    table that has been renamed to ``competitor_profiles`` and ensure all
    model tables exist.

    Note: the pgvector native extension is intentionally NOT enabled here.
    Embeddings are stored as JSON lists and the queryable vector store is
    ChromaDB (``app/services/vector_store.py``), which keeps the stack
    portable to Windows where compiling pgvector is painful.
    """
    if is_sqlite:
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS competitors"))
    else:
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS competitors CASCADE"))
    Base.metadata.create_all(bind=engine)
    # Additive column migrations for already-existing tables (create_all only
    # creates missing tables, it never alters existing ones). Postgres supports
    # IF NOT EXISTS so these are safe to run on every startup.
    with engine.begin() as conn:
        conn.execute(text(
            "ALTER TABLE contacts ADD COLUMN IF NOT EXISTS source VARCHAR DEFAULT 'discovery'"
        ))
        conn.execute(text(
            "ALTER TABLE contacts ADD COLUMN IF NOT EXISTS source_ref VARCHAR"
        ))


def get_session() -> Generator[Session, None, None]:
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()
