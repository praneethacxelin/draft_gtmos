"""SQLAlchemy models + DB session for the GTM Factory.

All tables created with `init_db()` on startup. Uses pgvector for ICP
embeddings to support similarity-based pattern recognition.
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
    text,
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector


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


engine = create_engine(_db_url(), pool_pre_ping=True, pool_size=5, max_overflow=10)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def gen_id() -> str:
    return str(uuid.uuid4())


def now() -> datetime:
    return datetime.utcnow()


# ---------- Settings (in-app integration config) ----------


class AppSetting(Base):
    __tablename__ = "app_settings"
    id = Column(String, primary_key=True, default=gen_id)
    integration_name = Column(String, unique=True, nullable=False)  # serpapi/apollo/clay/instantly
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
    status = Column(String, default="draft")  # draft / generating / ready
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class IcpEmbedding(Base):
    __tablename__ = "icp_embeddings"
    id = Column(String, primary_key=True, default=gen_id)
    strategy_id = Column(String, ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False)
    embedding = Column(Vector(384), nullable=False)
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
    strategy_id = Column(String, ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False)
    company_name = Column(String, nullable=False)
    domain = Column(String, nullable=True)
    industry = Column(String, nullable=True)
    employee_count = Column(Integer, nullable=True)
    revenue_range = Column(String, nullable=True)
    tech_stack_json = Column(JSONB, nullable=True)
    enrichment_json = Column(JSONB, nullable=True)
    tier = Column(Integer, nullable=True)  # 1/2/3
    created_at = Column(DateTime, default=now)


class Contact(Base):
    __tablename__ = "contacts"
    id = Column(String, primary_key=True, default=gen_id)
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
    cluster_embedding = Column(Vector(384), nullable=True)
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


# ---------- Helpers ----------


def init_db() -> None:
    """Enable pgvector, run light migrations, create new tables.

    Heavy schema migrations live under ``alembic/`` (see ``alembic upgrade
    head``). The startup hook here only does the additive work needed for
    the seeded demo to come up cleanly: enable pgvector, drop the legacy
    ``competitors`` table that has been renamed to ``competitor_profiles``,
    and ensure all model tables exist.
    """
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.execute(text("DROP TABLE IF EXISTS competitors CASCADE"))
    Base.metadata.create_all(bind=engine)


def get_session() -> Generator[Session, None, None]:
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()
