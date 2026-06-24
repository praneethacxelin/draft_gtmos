import pytest
from unittest.mock import MagicMock
from app.services.deliverability import analyze_email_content
from app.routes.analytics import outreach_analytics
from app.db import Sequence, InstantlyCampaign, Contact, Strategy

def test_deliverability_service():
    # Test text containing spam triggers
    res_spam = analyze_email_content("100% Free Guarantee!", "Click here to claim your cash bonus now. Free money!")
    assert res_spam["score"] < 100
    assert len(res_spam["warnings"]) > 0
    assert "spam_words_found" in res_spam["details"]
    
    # Test clean text
    res_clean = analyze_email_content(
        "Meeting request",
        "Hi, I would love to schedule a quick 10 minute call next week to discuss your engineering needs and how our platform can support your team's development. Please let me know what day works best for you. Best, John"
    )
    assert res_clean["score"] == 100
    assert len(res_clean["warnings"]) == 0

def test_outreach_analytics_empty():
    db = MagicMock()
    user = MagicMock()
    
    # Query for Sequence returns empty list
    query_mock = MagicMock()
    query_mock.all.return_value = []
    query_mock.filter.return_value = query_mock
    db.query.return_value = query_mock
    
    res = outreach_analytics(strategy_id=None, db=db, user=user)
    assert res["total_sent"] == 0
    assert res["total_opened"] == 0
    assert res["total_clicked"] == 0
    assert res["total_replied"] == 0
    assert res["total_bounced"] == 0
    assert res["open_rate"] == 0.0
    assert res["click_rate"] == 0.0
    assert res["reply_rate"] == 0.0
    assert res["bounce_rate"] == 0.0
    assert res["sequences"] == []
    assert res["by_strategy"] == []

def test_outreach_analytics_with_data():
    db = MagicMock()
    user = MagicMock()
    
    mock_seq = MagicMock()
    mock_seq.id = "seq1"
    mock_seq.contact_id = "contact1"
    mock_seq.strategy_id = "strat1"
    mock_seq.status = "active"
    mock_seq.instantly_campaign_id = "inst1"
    
    mock_camp = MagicMock()
    mock_camp.sequence_id = "seq1"
    mock_camp.analytics_json = {"sent": 10, "opened": 5, "clicked": 2, "replied": 1, "bounced": 0}
    
    mock_contact = MagicMock()
    mock_contact.id = "contact1"
    mock_contact.full_name = "John Doe"
    mock_contact.email = "john@example.com"
    
    mock_strategy = MagicMock()
    mock_strategy.id = "strat1"
    mock_strategy.product_name = "Product 1"
    
    # Mocking different queries based on arguments
    seq_query = MagicMock()
    seq_query.filter.return_value = seq_query
    seq_query.all.return_value = [mock_seq]
    
    camp_query = MagicMock()
    camp_query.filter.return_value = camp_query
    camp_query.all.return_value = [mock_camp]
    
    contact_query = MagicMock()
    contact_query.filter.return_value = contact_query
    contact_query.all.return_value = [mock_contact]
    
    strategy_query = MagicMock()
    strategy_query.filter.return_value = strategy_query
    strategy_query.all.return_value = [mock_strategy]
    
    event_query = MagicMock()
    event_query.filter.return_value = event_query
    event_query.group_by.return_value = event_query
    event_query.all.return_value = []
    
    def side_effect(model_or_func, *args, **kwargs):
        if model_or_func is Sequence:
            return seq_query
        elif model_or_func is InstantlyCampaign:
            return camp_query
        elif model_or_func is Contact:
            return contact_query
        elif model_or_func is Strategy:
            return strategy_query
        else:
            return event_query
            
    db.query.side_effect = side_effect
    
    res = outreach_analytics(strategy_id="strat1", db=db, user=user)
    assert res["total_sent"] == 10
    assert res["total_opened"] == 5
    assert res["total_clicked"] == 2
    assert res["total_replied"] == 1
    assert res["total_bounced"] == 0
    assert res["open_rate"] == 50.0
    assert res["click_rate"] == 20.0
    assert res["reply_rate"] == 10.0
    assert len(res["sequences"]) == 1
    assert res["sequences"][0]["contact_name"] == "John Doe"
    assert len(res["by_strategy"]) == 1
    assert res["by_strategy"][0]["strategy_name"] == "Product 1"
