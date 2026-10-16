from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, Text, DateTime
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class LeadQualificationRecord(Base):
    __tablename__ = "lead_qualifications"

    lead_id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=True)
    company = Column(String, nullable=True)
    fit_score = Column(Integer, nullable=False)
    intent_score = Column(Integer, nullable=False)
    overall_score = Column(Integer, nullable=False)
    tier = Column(String, nullable=False, index=True)
    rank = Column(Integer, nullable=True)
    summary = Column(Text, nullable=True)
    buying_signals = Column(Text, nullable=True) # JSON string
    risk_signals = Column(Text, nullable=True)   # JSON string
    reasoning = Column(Text, nullable=True)
    recommended_action = Column(Text, nullable=True)
    confidence = Column(Float, default=0.9)
    raw_input = Column(Text, nullable=True)      # JSON string
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
