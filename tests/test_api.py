import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_qualify_single_endpoint():
    payload = {
        "name": "API Test Lead",
        "company": "API Tech",
        "job_title": "CTO",
        "industry": "B2B SaaS",
        "company_size": 250,
        "budget": "$60,000",
        "interest": "AI Engine",
        "timeline": "Within 30 days",
        "notes": "Requesting immediate demo"
    }
    response = client.post("/qualify", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "lead_id" in data
    assert data["tier"] == "HOT"
    assert data["fit_score"] > 80

def test_qualify_batch_endpoint():
    payload = [
        {"name": "Batch 1", "company": "Co 1", "job_title": "VP Sales", "industry": "B2B SaaS", "company_size": 500, "budget": "$100k", "interest": "AI automation platform", "timeline": "Within 30 days", "notes": "Requesting immediate demo and pricing"},
        {"name": "Batch 2", "company": "Co 2", "industry": "Retail", "company_size": 5, "budget": "$0"}
    ]
    response = client.post("/qualify/batch", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["total_leads"] == 2
    assert data["hot"] >= 1

def test_get_leads_endpoint():
    response = client.get("/leads")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "leads" in data
