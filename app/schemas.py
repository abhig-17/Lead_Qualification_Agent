from typing import List, Optional, Any, Union, Dict
from pydantic import BaseModel, Field, ConfigDict

class LeadInput(BaseModel):
    lead_id: Optional[str] = Field(None, description="Unique lead identifier. Auto-generated if omitted.")
    name: Optional[str] = Field(None, description="Contact name")
    company: Optional[str] = Field(None, description="Company name")
    job_title: Optional[str] = Field(None, description="Job title / role")
    industry: Optional[str] = Field(None, description="Industry sector")
    company_size: Optional[Union[int, str]] = Field(None, description="Employee count or size range")
    location: Optional[str] = Field(None, description="Geographic location / country")
    budget: Optional[Union[str, float, int]] = Field(None, description="Stated budget")
    interest: Optional[str] = Field(None, description="Product or service interest")
    timeline: Optional[str] = Field(None, description="Purchase timeline")
    source: Optional[str] = Field(None, description="Lead acquisition source")
    form_responses: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Custom form key-value pairs")
    sales_notes: Optional[str] = Field(None, description="Internal sales notes")
    email_text: Optional[str] = Field(None, description="Raw email or inquiry text")
    notes: Optional[str] = Field(None, description="General notes")
    model_config = ConfigDict(extra="ignore")


class ExtractedLeadAttributes(BaseModel):
    name: Optional[str] = None
    company: Optional[str] = None
    job_title: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[Union[int, str]] = None
    location: Optional[str] = None
    budget: Optional[Union[str, float, int]] = None
    interest: Optional[str] = None
    timeline: Optional[str] = None
    buying_signals: List[str] = Field(default_factory=list)
    risk_signals: List[str] = Field(default_factory=list)
    key_requirements: List[str] = Field(default_factory=list)


class LLMLeadAnalysis(BaseModel):
    lead_id: str
    summary: str = Field(..., description="Factual summary of lead based strictly on input data")
    buying_signals: List[str] = Field(default_factory=list, description="Extracted positive buying intent signals")
    risk_signals: List[str] = Field(default_factory=list, description="Extracted negative or risk signals")
    recommended_action: str = Field(..., description="Actionable next step for sales rep")
    confidence: float = Field(default=0.9, ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")


class FitBreakdown(BaseModel):
    industry_relevance: int = Field(..., ge=0, le=25)
    company_size: int = Field(..., ge=0, le=20)
    decision_authority: int = Field(..., ge=0, le=20)
    budget_compatibility: int = Field(..., ge=0, le=20)
    geographic_fit: int = Field(..., ge=0, le=15)
    total: int = Field(..., ge=0, le=100)


class IntentBreakdown(BaseModel):
    product_interest: int = Field(..., ge=0, le=25)
    purchase_timeline: int = Field(..., ge=0, le=25)
    specific_requirements: int = Field(..., ge=0, le=20)
    contact_request: int = Field(..., ge=0, le=15)
    urgency_signals: int = Field(..., ge=0, le=15)
    total: int = Field(..., ge=0, le=100)


class ScoreBreakdown(BaseModel):
    fit: FitBreakdown
    intent: IntentBreakdown


class QualifiedLead(BaseModel):
    lead_id: str
    name: str
    company: Optional[str] = "Unknown"
    job_title: Optional[str] = "Unknown"
    fit_score: int = Field(..., ge=0, le=100)
    intent_score: int = Field(..., ge=0, le=100)
    overall_score: int = Field(..., ge=0, le=100)
    tier: str = Field(..., description="HOT, WARM, or COLD")
    rank: Optional[int] = None
    summary: str
    buying_signals: List[str] = Field(default_factory=list)
    risk_signals: List[str] = Field(default_factory=list)
    reasoning: str
    recommended_action: str
    confidence: float = 0.90
    score_breakdown: Optional[ScoreBreakdown] = None
    created_at: Optional[str] = None

    model_config = ConfigDict(extra="ignore")


class BatchQualificationResponse(BaseModel):
    total_leads: int
    hot: int
    warm: int
    cold: int
    leads: List[QualifiedLead]
