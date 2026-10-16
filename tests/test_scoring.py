import pytest
from app.scoring import (
    calculate_fit_score,
    calculate_intent_score,
    evaluate_lead_scores,
    extract_buying_and_risk_signals,
    rank_leads,
    parse_company_size,
    parse_budget_numeric
)

def test_company_size_parsing():
    assert parse_company_size(200) == 200
    assert parse_company_size("500+") == 500
    assert parse_company_size("100-500") == 500
    assert parse_company_size(None) == 0

def test_budget_parsing():
    assert parse_budget_numeric("$50,000") == 50000.0
    assert parse_budget_numeric("$50k") == 50000.0
    assert parse_budget_numeric(120000) == 120000.0
    assert parse_budget_numeric("No budget") == 0.0

def test_fit_scoring_high():
    lead = {
        "industry": "B2B SaaS",
        "company_size": 500,
        "job_title": "VP Engineering",
        "budget": "$100,000",
        "location": "United States"
    }
    bd = calculate_fit_score(lead)
    assert bd.industry_relevance == 25
    assert bd.company_size == 20
    assert bd.decision_authority == 20
    assert bd.budget_compatibility == 20
    assert bd.geographic_fit == 15
    assert bd.total == 100

def test_fit_scoring_low():
    lead = {
        "industry": "Education",
        "company_size": 1,
        "job_title": "Student",
        "budget": "$0",
        "location": "Other"
    }
    bd = calculate_fit_score(lead)
    assert bd.total < 50

def test_intent_scoring_urgent_demo():
    lead = {
        "interest": "AI automation platform",
        "timeline": "Within 30 days",
        "notes": "We are evaluating vendors urgently and need a demo.",
        "source": "Website demo request"
    }
    bd = calculate_intent_score(lead)
    assert bd.product_interest == 25
    assert bd.purchase_timeline == 25
    assert bd.contact_request == 15
    assert bd.total >= 80

def test_overall_score_calculation_and_tier_hot():
    lead = {
        "lead_id": "L1",
        "industry": "B2B SaaS",
        "company_size": 250,
        "job_title": "CTO",
        "budget": "$60,000",
        "location": "United States",
        "interest": "AI platform",
        "timeline": "Within 30 days",
        "notes": "We are evaluating 3 vendors urgently and require a product demo and pricing details asap."
    }
    fit, intent, overall, tier, _ = evaluate_lead_scores(lead)
    assert fit >= 85
    assert intent >= 80
    assert overall >= 75
    assert tier == "HOT"

def test_tier_thresholds_warm_and_cold():
    # Warm lead
    warm_lead = {
        "industry": "Manufacturing",
        "company_size": 60,
        "job_title": "Sales Specialist",
        "budget": "$10,000",
        "location": "Mexico",
        "interest": "Lead sorting tool",
        "timeline": "1-3 months",
        "notes": "Exploring options to organize incoming web leads over the next quarter."
    }
    _, _, overall_warm, tier_warm, _ = evaluate_lead_scores(warm_lead)
    assert 50 <= overall_warm < 75
    assert tier_warm == "WARM"

    # Cold lead
    cold_lead = {
        "industry": "Education",
        "company_size": 1,
        "job_title": "Student",
        "budget": "No budget",
        "timeline": "No timeline"
    }
    _, _, overall_cold, tier_cold, _ = evaluate_lead_scores(cold_lead)
    assert overall_cold < 50
    assert tier_cold == "COLD"

def test_signal_extraction():
    lead = {
        "job_title": "VP Sales",
        "budget": "$50,000",
        "timeline": "Within 30 days",
        "notes": "We are evaluating 3 vendors and need a demo ASAP."
    }
    buying, risk = extract_buying_and_risk_signals(lead)
    assert any("demo" in b.lower() for b in buying)
    assert any("vendor" in b.lower() for b in buying)
    assert any("vp sales" in b.lower() for b in buying)

def test_deterministic_ranking_and_tie_breaking():
    leads = [
        {"lead_id": "L2", "overall_score": 85, "intent_score": 80, "buying_signals": []},
        {"lead_id": "L1", "overall_score": 85, "intent_score": 90, "buying_signals": ["Explicit request for product demo"]},
        {"lead_id": "L3", "overall_score": 60, "intent_score": 50, "buying_signals": []}
    ]
    ranked = rank_leads(leads)
    assert ranked[0]["lead_id"] == "L1" # Higher intent score & demo request
    assert ranked[0]["rank"] == 1
    assert ranked[1]["lead_id"] == "L2"
    assert ranked[1]["rank"] == 2
    assert ranked[2]["lead_id"] == "L3"
    assert ranked[2]["rank"] == 3
