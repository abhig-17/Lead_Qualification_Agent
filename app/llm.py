import json
import logging
import re
import time
from typing import Dict, Any, Optional
from openai import OpenAI
from app.config import settings
from app.prompts import SYSTEM_PROMPT, EXTRACTION_SYSTEM_PROMPT
from app.schemas import LLMLeadAnalysis, ExtractedLeadAttributes

logger = logging.getLogger(__name__)


def get_openai_client() -> Optional[OpenAI]:
    """Returns an initialized OpenAI client if API key is present, else None."""
    api_key = settings.OPENAI_API_KEY.strip() if settings.OPENAI_API_KEY else ""
    if api_key and api_key != "your_api_key_here":
        try:
            kwargs = {"api_key": api_key}
            if settings.OPENAI_BASE_URL and settings.OPENAI_BASE_URL.strip():
                kwargs["base_url"] = settings.OPENAI_BASE_URL.strip()
            return OpenAI(**kwargs)
        except Exception as e:
            logger.warning(f"Failed to initialize OpenAI client: {e}")
            return None
    return None


def clean_json_response(content: str) -> str:
    """Strips markdown block wrappers like ```json ... ``` from model responses."""
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\n?", "", content)
        content = re.sub(r"\n?```$", "", content)
    return content.strip()


def fallback_extract_unstructured(text: str) -> ExtractedLeadAttributes:
    """Regex & rule-based deterministic fallback for unstructured text extraction when LLM is unavailable."""
    name = None
    company = None
    job_title = None
    industry = None
    company_size = None
    budget = None
    interest = None
    timeline = None

    text_lower = text.lower()

    # Budget extraction regex
    budget_match = re.search(r'\$\d+(?:,\d+)*(?:\s*k|\s*thousand|\s*million)?', text_lower)
    if budget_match:
        budget = budget_match.group(0)

    # Company size regex
    size_match = re.search(r'(\d+)\s*(?:employees|people|staff|team size)', text_lower)
    if size_match:
        company_size = int(size_match.group(1))

    # Timeline regex
    if "30 days" in text_lower or "immediately" in text_lower or "asap" in text_lower:
        timeline = "Within 30 days"
    elif "month" in text_lower or "quarter" in text_lower:
        timeline = "1-3 months"

    
    for t in ["vp engineering", "vp sales", "cto", "ceo", "director of engineering", "head of sales", "product manager", "it manager"]:
        if t in text_lower:
            job_title = t.title()
            break

    # Interest detection
    if "demo" in text_lower or "automation" in text_lower or "ai" in text_lower or "platform" in text_lower:
        interest = "AI automation / Software solution"

    return ExtractedLeadAttributes(
        name=name,
        company=company,
        job_title=job_title,
        industry=industry,
        company_size=company_size,
        budget=budget,
        interest=interest,
        timeline=timeline,
        buying_signals=["Inbound inquiry text submitted"],
        risk_signals=[]
    )


def extract_unstructured_lead_info(text: str) -> ExtractedLeadAttributes:
    """Extracts structured lead details from raw email/notes using LLM or deterministic fallback."""
    client = get_openai_client()
    if not client:
        return fallback_extract_unstructured(text)

    for attempt in range(2):
        try:
            try:
                response = client.chat.completions.create(
                    model=settings.MODEL_NAME,
                    messages=[
                        {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                        {"role": "user", "content": f"Extract lead details from this text in JSON format:\n\n{text}"}
                    ],
                    temperature=0.1,
                    response_format={"type": "json_object"}
                )
            except Exception:
                response = client.chat.completions.create(
                    model=settings.MODEL_NAME,
                    messages=[
                        {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                        {"role": "user", "content": f"Extract lead details from this text in valid JSON format:\n\n{text}"}
                    ],
                    temperature=0.1
                )
            raw_json = clean_json_response(response.choices[0].message.content or "{}")
            parsed = json.loads(raw_json)
            return ExtractedLeadAttributes(**parsed)
        except Exception as e:
            if "rate_limit" in str(e).lower() and attempt == 0:
                time.sleep(1.5)
                continue
            logger.error(f"LLM extraction error: {e}. Falling back to rule extraction.")
            return fallback_extract_unstructured(text)


# ---------------------------------------------------------------------------
# Combined prompt: extracts unstructured attributes AND generates analysis
# in a single LLM call, cutting round-trips in half for leads with raw text.
# ---------------------------------------------------------------------------
_COMBINED_SYSTEM_PROMPT = """You are a senior B2B sales lead analysis assistant.

CRITICAL ANTI-HALLUCINATION RULES:
1. Use ONLY information present in the lead data. NEVER invent facts, budgets, timelines, company sizes, or buyer roles.
2. When information is missing, report it explicitly as "Not provided" or "Unknown".
3. Do NOT treat missing information as positive evidence.
4. Clearly distinguish KNOWN FACTS from INFERRED SIGNALS.
5. Do NOT override the deterministic numerical scores provided; use them only for context.

Return ONLY a single valid JSON object with these top-level keys:
{
  "extracted": {
    "name": str or null,
    "company": str or null,
    "job_title": str or null,
    "industry": str or null,
    "company_size": int or str or null,
    "location": str or null,
    "budget": str or null,
    "interest": str or null,
    "timeline": str or null,
    "buying_signals": [str],
    "risk_signals": [str]
  },
  "analysis": {
    "lead_id": str,
    "summary": str,
    "buying_signals": [str],
    "risk_signals": [str],
    "recommended_action": str,
    "confidence": float
  }
}
"""


def extract_and_analyze_combined(
    text: str,
    lead_dict: Dict[str, Any],
    fit_score: int,
    intent_score: int,
    overall_score: int,
    tier: str,
    rule_buying_signals: list,
    rule_risk_signals: list,
) -> tuple[ExtractedLeadAttributes, LLMLeadAnalysis]:
    """
    Single combined LLM call that performs both unstructured extraction and
    lead analysis in one round-trip (faster than two sequential calls).

    Returns (ExtractedLeadAttributes, LLMLeadAnalysis).
    Falls back to the individual functions on any failure.
    """
    client = get_openai_client()
    if not client:
        extracted = fallback_extract_unstructured(text)
        analysis = generate_fallback_analysis(
            lead_dict, fit_score, intent_score, overall_score,
            tier, rule_buying_signals, rule_risk_signals
        )
        return extracted, analysis

    user_prompt = f"""Raw unstructured text to extract from:
\"\"\"
{text}
\"\"\"

Lead structured context (use only as supplement, do not invent beyond what is present):
- Lead ID: {lead_dict.get('lead_id')}
- Name: {lead_dict.get('name', 'Not provided')}
- Company: {lead_dict.get('company', 'Not provided')}
- Job Title: {lead_dict.get('job_title', 'Not provided')}
- Industry: {lead_dict.get('industry', 'Not provided')}
- Company Size: {lead_dict.get('company_size', 'Not provided')}
- Location: {lead_dict.get('location', 'Not provided')}
- Budget: {lead_dict.get('budget', 'Not provided')}
- Product Interest: {lead_dict.get('interest', 'Not provided')}
- Timeline: {lead_dict.get('timeline', 'Not provided')}
- Source: {lead_dict.get('source', 'Not provided')}

DETERMINISTIC SCORING RESULTS (do NOT modify these numbers):
- Fit Score: {fit_score}/100
- Intent Score: {intent_score}/100
- Overall Score: {overall_score}/100
- Tier: {tier}

Rule-identified signals:
- Buying signals: {rule_buying_signals}
- Risk signals: {rule_risk_signals}

Return the combined JSON with both "extracted" and "analysis" keys."""

    for attempt in range(2):
        try:
            try:
                response = client.chat.completions.create(
                    model=settings.MODEL_NAME,
                    messages=[
                        {"role": "system", "content": _COMBINED_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.1,
                    response_format={"type": "json_object"},
                )
            except Exception:
                response = client.chat.completions.create(
                    model=settings.MODEL_NAME,
                    messages=[
                        {"role": "system", "content": _COMBINED_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt + "\n\nReturn JSON only."},
                    ],
                    temperature=0.1,
                )
            raw = clean_json_response(response.choices[0].message.content or "{}")
            parsed = json.loads(raw)

            ext_data = parsed.get("extracted", {})
            extracted = ExtractedLeadAttributes(**ext_data)

            ana_data = parsed.get("analysis", {})
            ana_data["lead_id"] = str(lead_dict.get("lead_id", "L000"))
            analysis = LLMLeadAnalysis(**ana_data)

            return extracted, analysis

        except Exception as e:
            if "rate_limit" in str(e).lower() and attempt == 0:
                time.sleep(1.5)
                continue
            logger.error(f"Combined LLM call failed: {e}. Falling back to individual calls.")
            break

    # Fallback: independent calls
    extracted = extract_unstructured_lead_info(text)
    analysis = generate_llm_analysis(
        lead_dict, fit_score, intent_score, overall_score,
        tier, rule_buying_signals, rule_risk_signals
    )
    return extracted, analysis


def generate_fallback_analysis(
    lead_dict: Dict[str, Any],
    fit_score: int,
    intent_score: int,
    overall_score: int,
    tier: str,
    rule_buying_signals: list,
    rule_risk_signals: list
) -> LLMLeadAnalysis:
    """Deterministic, template-based fallback analysis when LLM API is unavailable or fails."""
    name = lead_dict.get("name") or "Lead"
    company = lead_dict.get("company") or "Unknown Company"
    title = lead_dict.get("job_title") or "Representative"
    industry = lead_dict.get("industry") or "Unspecified Industry"
    size = lead_dict.get("company_size") or "Unknown size"
    interest = lead_dict.get("interest") or "General inquiry"

    summary = f"{title} at {company} ({industry}, {size} employees) interested in {interest}."

    if tier == "HOT":
        action = f"Contact {name} within 24 hours. Prioritize product demo and pricing discussion."
    elif tier == "WARM":
        action = f"Contact {name} within 2-3 business days. Validate budget, timeline, and decision authority."
    else:
        action = f"Add {name} to automated nurture campaign. Follow up in 30-60 days; do not prioritize immediate call."

    return LLMLeadAnalysis(
        lead_id=str(lead_dict.get("lead_id", "L000")),
        summary=summary,
        buying_signals=rule_buying_signals or ["Inbound engagement signal"],
        risk_signals=rule_risk_signals,
        recommended_action=action,
        confidence=0.85
    )


def generate_llm_analysis(
    lead_dict: Dict[str, Any],
    fit_score: int,
    intent_score: int,
    overall_score: int,
    tier: str,
    rule_buying_signals: list,
    rule_risk_signals: list
) -> LLMLeadAnalysis:
    """Generates structured lead summary, reasoning, buying signals, and recommended next sales action."""
    client = get_openai_client()
    if not client:
        return generate_fallback_analysis(lead_dict, fit_score, intent_score, overall_score, tier, rule_buying_signals, rule_risk_signals)

    user_prompt = f"""
Analyze the following lead data:

Lead ID: {lead_dict.get('lead_id')}
Name: {lead_dict.get('name', 'Not provided')}
Company: {lead_dict.get('company', 'Not provided')}
Job Title: {lead_dict.get('job_title', 'Not provided')}
Industry: {lead_dict.get('industry', 'Not provided')}
Company Size: {lead_dict.get('company_size', 'Not provided')}
Location: {lead_dict.get('location', 'Not provided')}
Budget: {lead_dict.get('budget', 'Not provided')}
Product Interest: {lead_dict.get('interest', 'Not provided')}
Timeline: {lead_dict.get('timeline', 'Not provided')}
Source: {lead_dict.get('source', 'Not provided')}
Sales Notes / Email Text: {lead_dict.get('notes') or lead_dict.get('email_text') or lead_dict.get('sales_notes') or 'None'}

DETERMINISTIC EVALUATION RESULTS:
- Fit Score: {fit_score}/100
- Intent Score: {intent_score}/100
- Overall Score: {overall_score}/100
- Tier: {tier}

Identified Rule Signals:
- Buying signals: {rule_buying_signals}
- Risk signals: {rule_risk_signals}

Respond in structured JSON format with:
- lead_id: string
- summary: string (1-2 sentence evidence-based summary)
- buying_signals: list of strings (factual positive intent signals)
- risk_signals: list of strings (factual risk/missing information signals)
- recommended_action: string (practical, customized next sales action for sales rep based on {tier} tier)
- confidence: float (0.0 to 1.0)
"""

    for attempt in range(2):
        try:
            try:
                response = client.chat.completions.create(
                    model=settings.MODEL_NAME,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.2,
                    response_format={"type": "json_object"}
                )
            except Exception:
                response = client.chat.completions.create(
                    model=settings.MODEL_NAME,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt + "\n\nReturn JSON only."}
                    ],
                    temperature=0.2
                )
            raw_content = clean_json_response(response.choices[0].message.content or "{}")
            parsed = json.loads(raw_content)

            # Ensure lead_id is present
            parsed["lead_id"] = str(lead_dict.get("lead_id", "L000"))
            return LLMLeadAnalysis(**parsed)
        except Exception as e:
            if "rate_limit" in str(e).lower() and attempt == 0:
                time.sleep(2.0)
                continue
            logger.error(f"LLM analysis error: {e}. Falling back to template analysis.")
            return generate_fallback_analysis(lead_dict, fit_score, intent_score, overall_score, tier, rule_buying_signals, rule_risk_signals)
