import pytest
from app.agent import LeadQualificationAgent
from app.schemas import LeadInput, QualifiedLead, BatchQualificationResponse

def test_agent_qualify_single_lead():
    agent = LeadQualificationAgent()
    lead_in = LeadInput(
        name="Test Lead",
        company="Test Corp",
        job_title="VP Sales",
        industry="B2B SaaS",
        company_size=200,
        budget="$50,000",
        interest="AI platform",
        timeline="Within 30 days",
        notes="We need a demo asap"
    )
    res = agent.qualify_lead(lead_in)
    assert isinstance(res, QualifiedLead)
    assert res.lead_id is not None
    assert res.fit_score > 0
    assert res.intent_score > 0
    assert res.overall_score > 0
    assert res.tier in ["HOT", "WARM", "COLD"]
    assert res.summary != ""
    assert res.recommended_action != ""

def test_agent_qualify_unstructured_email_text():
    agent = LeadQualificationAgent()
    lead_in = LeadInput(
        email_text="Hi, I am Sarah, VP Engineering at Acme SaaS (200 people). We have a $50k budget and need an AI automation tool within 30 days. Please send demo details."
    )
    res = agent.qualify_lead(lead_in)
    assert isinstance(res, QualifiedLead)
    assert res.overall_score >= 70

def test_agent_batch_qualification():
    agent = LeadQualificationAgent()
    batch = [
        {"name": "Lead A", "company": "Co A", "industry": "B2B SaaS", "company_size": 300, "budget": "$50k", "interest": "Tool", "timeline": "Within 30 days"},
        {"name": "Lead B", "company": "Co B", "industry": "Retail", "company_size": 10, "budget": "$1k", "interest": "Software"},
    ]
    res = agent.qualify_batch(batch)
    assert isinstance(res, BatchQualificationResponse)
    assert res.total_leads == 2
    assert len(res.leads) == 2
    assert res.leads[0].rank == 1
    assert res.leads[1].rank == 2
