import re
from typing import Dict, Any, Tuple, List
from app.config import settings
from app.schemas import FitBreakdown, IntentBreakdown, ScoreBreakdown

HIGH_TARGET_INDUSTRIES = [
    "b2b saas", "saas", "software", "artificial intelligence", "ai", "cloud",
    "fintech", "healthtech", "technology", "deeptech", "cybersecurity", "edtech"
]
MEDIUM_TARGET_INDUSTRIES = [
    "manufacturing", "financial services", "banking", "e-commerce", "ecommerce",
    "logistics", "telecom", "professional services", "healthcare", "insurance", "consulting"
]
LOW_TARGET_INDUSTRIES = [
    "retail", "hospitality", "media", "entertainment", "education", "non-profit", "agriculture"
]

EXEC_TITLES = ["ceo", "cto", "cfo", "cio", "cro", "cmo", "vp", "vice president", "head of", "founder", "co-founder", "owner", "president", "chief"]
DIRECTOR_TITLES = ["director", "lead", "manager", "head", "principal"]
SENIOR_TITLES = ["senior", "sr", "architect", "engineer", "consultant", "specialist", "analyst"]

HIGH_INTENT_KEYWORDS = [
    "demo", "pricing", "quote", "cost", "how much", "contact me", "call me",
    "evaluating vendors", "urgently", "ready to buy", "schedule a call", "purchase", "proposal"
]
NEGATIVE_KEYWORDS = [
    "just researching", "no current project", "no budget", "student", "academic",
    "homework", "personal project", "browsing", "unemployed", "job opening"
]

def parse_company_size(size_raw: Any) -> int:
    """Parses numeric employee count from integer, float, or string."""
    if size_raw is None:
        return 0
    if isinstance(size_raw, (int, float)):
        return int(size_raw)
    
    s = str(size_raw).lower().strip()
    if not s:
        return 0
    
    # Range handling e.g. "100-500", "200", "500+"
    matches = re.findall(r'\d+', s)
    if matches:
        # If range like 100-500, take average or lower bound
        nums = [int(m) for m in matches]
        return max(nums)
    return 0

def parse_budget_numeric(budget_raw: Any) -> float:
    """Extracts numeric dollar budget value from input string or number."""
    if budget_raw is None:
        return 0.0
    if isinstance(budget_raw, (int, float)):
        return float(budget_raw)
    
    s = str(budget_raw).lower().replace(",", "").replace("$", "").strip()
    if "k" in s:
        m = re.findall(r'(\d+(?:\.\d+)?)k', s)
        if m:
            return float(m[0]) * 1000
    
    matches = re.findall(r'\d+(?:\.\d+)?', s)
    if matches:
        return float(matches[0])
    return 0.0

def calculate_fit_score(lead_dict: Dict[str, Any]) -> FitBreakdown:
    """Calculates deterministic Fit Score (0-100 across 5 categories)."""
    # 1. Industry Relevance (0-25)
    industry = str(lead_dict.get("industry") or "").lower().strip()
    if any(ind in industry for ind in HIGH_TARGET_INDUSTRIES):
        ind_score = 25
    elif any(ind in industry for ind in MEDIUM_TARGET_INDUSTRIES):
        ind_score = 18
    elif any(ind in industry for ind in LOW_TARGET_INDUSTRIES):
        ind_score = 10
    elif industry:
        ind_score = 12
    else:
        ind_score = 5 # missing/unknown industry

    # 2. Company Size (0-20)
    size_num = parse_company_size(lead_dict.get("company_size"))
    if size_num >= 500:
        size_score = 20
    elif size_num >= 100:
        size_score = 16
    elif size_num >= 20:
        size_score = 12
    elif size_num >= 1:
        size_score = 6
    else:
        size_score = 0 # Unknown/Missing

    # 3. Decision-making Authority (0-20)
    title = str(lead_dict.get("job_title") or "").lower().strip()
    if any(t in title for t in EXEC_TITLES):
        auth_score = 20
    elif any(t in title for t in DIRECTOR_TITLES):
        auth_score = 15
    elif any(t in title for t in SENIOR_TITLES):
        auth_score = 10
    elif any(t in title for t in ["intern", "student", "junior"]):
        auth_score = 3
    elif title:
        auth_score = 8
    else:
        auth_score = 5 # Missing/Unknown

    # 4. Budget Compatibility (0-20)
    budget_raw = str(lead_dict.get("budget") or "").lower()
    budget_num = parse_budget_numeric(lead_dict.get("budget"))
    
    if "no budget" in budget_raw:
        budget_score = 0
    elif budget_num >= 50000 or "$50k" in budget_raw or "50,000" in budget_raw:
        budget_score = 20
    elif budget_num >= 20000 or "$20k" in budget_raw:
        budget_score = 16
    elif budget_num >= 5000 or "$5k" in budget_raw:
        budget_score = 10
    elif budget_num > 0:
        budget_score = 4
    else:
        budget_score = 0 # Unknown/Missing

    # 5. Geographic Compatibility (0-15)
    location = str(lead_dict.get("location") or "").lower().strip()
    tier1_locs = ["united states", "usa", "us", "canada", "uk", "united kingdom", "germany", "france", "australia", "india"]
    tier2_locs = ["brazil", "mexico", "singapore", "uae", "dubai", "japan", "spain", "italy"]
    
    if any(loc in location for loc in tier1_locs):
        geo_score = 15
    elif any(loc in location for loc in tier2_locs):
        geo_score = 10
    elif location:
        geo_score = 6
    else:
        geo_score = 5 # Missing/Unknown

    total_fit = ind_score + size_score + auth_score + budget_score + geo_score
    total_fit = min(100, max(0, total_fit))

    return FitBreakdown(
        industry_relevance=ind_score,
        company_size=size_score,
        decision_authority=auth_score,
        budget_compatibility=budget_score,
        geographic_fit=geo_score,
        total=total_fit
    )

def calculate_intent_score(lead_dict: Dict[str, Any]) -> IntentBreakdown:
    """Calculates deterministic Intent Score (0-100 across 5 categories)."""
    text_corpus = f"{lead_dict.get('interest', '')} {lead_dict.get('notes', '')} {lead_dict.get('sales_notes', '')} {lead_dict.get('email_text', '')}".lower()

    # 1. Explicit Product Interest (0-25)
    interest = str(lead_dict.get("interest") or "").lower().strip()
    if interest and len(interest) > 5 and interest != "unknown":
        prod_score = 25
    elif interest:
        prod_score = 15
    elif any(kw in text_corpus for kw in ["solution", "platform", "agent", "software", "automation", "tool"]):
        prod_score = 10
    else:
        prod_score = 0

    # 2. Purchase Timeline (0-25)
    timeline = str(lead_dict.get("timeline") or "").lower().strip()
    if any(t in timeline or t in text_corpus for t in ["30 days", "immediately", "asap", "1 month", "urgent", "next month"]):
        time_score = 25
    elif any(t in timeline or t in text_corpus for t in ["1-3 months", "this quarter", "90 days", "2 months", "3 months"]):
        time_score = 18
    elif any(t in timeline or t in text_corpus for t in ["3-6 months", "6 months"]):
        time_score = 10
    elif any(t in timeline or t in text_corpus for t in ["6+ months", "next year", "long term", "researching"]):
        time_score = 4
    elif "no timeline" in timeline:
        time_score = 0
    else:
        time_score = 0

    # 3. Specific Requirements/Questions (0-20)
    notes_len = len(text_corpus)
    if any(req in text_corpus for req in ["requirement", "evaluating", "vendor", "features", "integrate", "compliance", "security", "sla"]):
        req_score = 20
    elif notes_len > 80:
        req_score = 15
    elif notes_len > 20:
        req_score = 8
    else:
        req_score = 0

    # 4. Pricing / Demo / Contact Request (0-15)
    source = str(lead_dict.get("source") or "").lower()
    if any(kw in text_corpus for kw in ["demo", "pricing", "cost", "quote", "schedule", "contact me", "talk to sales"]):
        contact_score = 15
    elif "demo" in source or "contact form" in source or "website" in source:
        contact_score = 10
    elif source:
        contact_score = 5
    else:
        contact_score = 0

    # 5. Engagement & Urgency Signals (0-15)
    has_negative = any(neg in text_corpus for neg in NEGATIVE_KEYWORDS)
    if has_negative:
        urgency_score = 0
    elif any(urg in text_corpus for urg in ["urgently", "evaluating 3 vendors", "evaluating vendors", "budget approved", "ready to deploy"]):
        urgency_score = 15
    elif any(urg in text_corpus for urg in ["looking to replace", "active project", "need solution"]):
        urgency_score = 10
    elif notes_len > 30:
        urgency_score = 5
    else:
        urgency_score = 0

    total_intent = prod_score + time_score + req_score + contact_score + urgency_score
    total_intent = min(100, max(0, total_intent))

    return IntentBreakdown(
        product_interest=prod_score,
        purchase_timeline=time_score,
        specific_requirements=req_score,
        contact_request=contact_score,
        urgency_signals=urgency_score,
        total=total_intent
    )

def extract_buying_and_risk_signals(lead_dict: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """Extracts explicit positive buying signals and risk signals from structured & text fields."""
    buying_signals = []
    risk_signals = []

    text_corpus = f"{lead_dict.get('interest', '')} {lead_dict.get('notes', '')} {lead_dict.get('sales_notes', '')} {lead_dict.get('email_text', '')}".lower()
    
    # Buying signals
    if any(kw in text_corpus for kw in ["demo", "request demo", "see a demo"]):
        buying_signals.append("Explicit request for product demo")
    if any(kw in text_corpus for kw in ["pricing", "cost", "quote"]):
        buying_signals.append("Requested pricing / quote details")
    if any(t in text_corpus or t in str(lead_dict.get("timeline", "")).lower() for t in ["30 days", "immediately", "asap", "urgent"]):
        buying_signals.append("Urgent purchase timeline (< 30 days)")
    if any(kw in text_corpus for kw in ["evaluating vendors", "evaluating 3 vendors", "comparing vendors"]):
        buying_signals.append("Active vendor evaluation in progress")

    title = str(lead_dict.get("job_title") or "").lower()
    if any(exec_t in title for exec_t in EXEC_TITLES):
        buying_signals.append(f"High-authority decision maker ({lead_dict.get('job_title')})")

    budget_num = parse_budget_numeric(lead_dict.get("budget"))
    if budget_num >= 50000:
        buying_signals.append(f"Strong budget compatibility (${int(budget_num):,})")

    # Risk signals
    if "no budget" in text_corpus or "no budget" in str(lead_dict.get("budget", "")).lower():
        risk_signals.append("No allocated budget stated")
    if any(kw in text_corpus for kw in ["just researching", "no current project", "no timeline"]):
        risk_signals.append("No immediate active project / just researching")
    if any(kw in text_corpus for kw in ["student", "academic", "homework"]):
        risk_signals.append("Student or academic inquiry")
    if not lead_dict.get("company_size") or parse_company_size(lead_dict.get("company_size")) == 0:
        risk_signals.append("Company size unknown or unverified")
    if not lead_dict.get("budget"):
        risk_signals.append("Budget not specified")

    return buying_signals, risk_signals

def evaluate_lead_scores(lead_dict: Dict[str, Any]) -> Tuple[int, int, int, str, ScoreBreakdown]:
    """
    Computes Fit Score, Intent Score, Overall Score, Tier, and detailed Breakdown.
    Overall Score = round(Fit * 0.45 + Intent * 0.55)
    Tier thresholds: HOT (>=75), WARM (>=50), COLD (<50)
    """
    fit_bd = calculate_fit_score(lead_dict)
    intent_bd = calculate_intent_score(lead_dict)

    overall_score = round(fit_bd.total * settings.FIT_WEIGHT + intent_bd.total * settings.INTENT_WEIGHT)
    overall_score = min(100, max(0, overall_score))

    if overall_score >= settings.HOT_THRESHOLD:
        tier = "HOT"
    elif overall_score >= settings.WARM_THRESHOLD:
        tier = "WARM"
    else:
        tier = "COLD"

    score_bd = ScoreBreakdown(fit=fit_bd, intent=intent_bd)
    return fit_bd.total, intent_bd.total, overall_score, tier, score_bd

def rank_leads(qualified_leads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Ranks a list of qualified lead dicts deterministically.
    Tie-breaking logic:
    1. Overall score (descending)
    2. Intent score (descending)
    3. Timeline score (descending)
    4. Explicit demo request (True first)
    5. lead_id (alphabetical ascending)
    """
    def sorting_key(lead: Dict[str, Any]):
        overall = lead.get("overall_score", 0)
        intent = lead.get("intent_score", 0)
        
        # Timeline priority
        timeline_score = 0
        if lead.get("score_breakdown") and hasattr(lead["score_breakdown"], "intent"):
            timeline_score = lead["score_breakdown"].intent.purchase_timeline
        elif isinstance(lead.get("score_breakdown"), dict):
            timeline_score = lead.get("score_breakdown", {}).get("intent", {}).get("purchase_timeline", 0)
            
        has_demo_request = any("demo" in sig.lower() for sig in lead.get("buying_signals", []))
        lead_id = str(lead.get("lead_id", ""))
        
        return (-overall, -intent, -timeline_score, not has_demo_request, lead_id)

    sorted_leads = sorted(qualified_leads, key=sorting_key)
    
    # Assign ranks 1..N
    for index, lead in enumerate(sorted_leads, start=1):
        lead["rank"] = index

    return sorted_leads
