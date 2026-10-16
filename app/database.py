import json
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker, Session
from app.config import settings
from app.models import Base, LeadQualificationRecord
from app.schemas import QualifiedLead

logger = logging.getLogger(__name__)

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Initializes database tables automatically."""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created / verified successfully.")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")

def get_db():
    """FastAPI dependency for DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def save_qualified_lead(lead: QualifiedLead, raw_input: Optional[Dict[str, Any]] = None, db: Optional[Session] = None) -> None:
    """Saves or updates a qualified lead record in SQLite database."""
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        buying_signals_json = json.dumps(lead.buying_signals)
        risk_signals_json = json.dumps(lead.risk_signals)
        raw_input_json = json.dumps(raw_input) if raw_input else "{}"

        record = db.query(LeadQualificationRecord).filter(LeadQualificationRecord.lead_id == lead.lead_id).first()
        if not record:
            record = LeadQualificationRecord(
                lead_id=lead.lead_id,
                name=lead.name,
                company=lead.company,
                fit_score=lead.fit_score,
                intent_score=lead.intent_score,
                overall_score=lead.overall_score,
                tier=lead.tier,
                rank=lead.rank,
                summary=lead.summary,
                buying_signals=buying_signals_json,
                risk_signals=risk_signals_json,
                reasoning=lead.reasoning,
                recommended_action=lead.recommended_action,
                confidence=lead.confidence,
                raw_input=raw_input_json,
                created_at=datetime.now(timezone.utc)
            )
            db.add(record)
        else:
            record.name = lead.name
            record.company = lead.company
            record.fit_score = lead.fit_score
            record.intent_score = lead.intent_score
            record.overall_score = lead.overall_score
            record.tier = lead.tier
            record.rank = lead.rank
            record.summary = lead.summary
            record.buying_signals = buying_signals_json
            record.risk_signals = risk_signals_json
            record.reasoning = lead.reasoning
            record.recommended_action = lead.recommended_action
            record.confidence = lead.confidence
            record.raw_input = raw_input_json

        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Error saving lead {lead.lead_id} to DB: {e}")
    finally:
        if should_close:
            db.close()

def save_batch_qualified_leads(leads: List[QualifiedLead], raw_inputs: Optional[List[Dict[str, Any]]] = None) -> None:
    """Saves a batch of qualified leads to SQLite database."""
    db = SessionLocal()
    try:
        raw_map = {}
        if raw_inputs:
            for r in raw_inputs:
                if isinstance(r, dict) and r.get("lead_id"):
                    raw_map[str(r["lead_id"])] = r

        for lead in leads:
            raw_inp = raw_map.get(lead.lead_id)
            save_qualified_lead(lead, raw_input=raw_inp, db=db)
    finally:
        db.close()

def fetch_all_qualified_leads() -> List[Dict[str, Any]]:
    """Retrieves all qualified lead records ordered by rank / overall_score."""
    db = SessionLocal()
    try:
        records = db.query(LeadQualificationRecord).order_by(
            LeadQualificationRecord.rank.asc().nullslast(),
            desc(LeadQualificationRecord.overall_score)
        ).all()

        results = []
        for r in records:
            results.append({
                "lead_id": r.lead_id,
                "name": r.name,
                "company": r.company,
                "fit_score": r.fit_score,
                "intent_score": r.intent_score,
                "overall_score": r.overall_score,
                "tier": r.tier,
                "rank": r.rank,
                "summary": r.summary,
                "buying_signals": json.loads(r.buying_signals or "[]"),
                "risk_signals": json.loads(r.risk_signals or "[]"),
                "reasoning": r.reasoning,
                "recommended_action": r.recommended_action,
                "confidence": r.confidence,
                "created_at": r.created_at.isoformat() if r.created_at else None
            })
        return results
    finally:
        db.close()

def rerank_all_database_leads() -> List[Dict[str, Any]]:
    """Re-ranks all leads stored in SQLite database and updates their rank field."""
    from app.scoring import rank_leads
    db = SessionLocal()
    try:
        records = db.query(LeadQualificationRecord).all()
        if not records:
            return []

        dict_list = []
        record_map = {}
        for r in records:
            item = {
                "lead_id": r.lead_id,
                "name": r.name,
                "company": r.company,
                "fit_score": r.fit_score,
                "intent_score": r.intent_score,
                "overall_score": r.overall_score,
                "tier": r.tier,
                "summary": r.summary,
                "buying_signals": json.loads(r.buying_signals or "[]"),
                "risk_signals": json.loads(r.risk_signals or "[]"),
                "reasoning": r.reasoning,
                "recommended_action": r.recommended_action,
                "confidence": r.confidence,
                "created_at": r.created_at.isoformat() if r.created_at else None
            }
            dict_list.append(item)
            record_map[r.lead_id] = r

        ranked_dicts = rank_leads(dict_list)

        for item in ranked_dicts:
            lid = item["lead_id"]
            if lid in record_map:
                record_map[lid].rank = item["rank"]

        db.commit()
        return ranked_dicts
    except Exception as e:
        db.rollback()
        logger.error(f"Error reranking database leads: {e}")
        return fetch_all_qualified_leads()
    finally:
        db.close()

def fetch_qualified_lead_by_id(lead_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves a specific qualified lead by lead_id."""
    db = SessionLocal()
    try:
        r = db.query(LeadQualificationRecord).filter(LeadQualificationRecord.lead_id == lead_id).first()
        if not r:
            return None
        return {
            "lead_id": r.lead_id,
            "name": r.name,
            "company": r.company,
            "fit_score": r.fit_score,
            "intent_score": r.intent_score,
            "overall_score": r.overall_score,
            "tier": r.tier,
            "rank": r.rank,
            "summary": r.summary,
            "buying_signals": json.loads(r.buying_signals or "[]"),
            "risk_signals": json.loads(r.risk_signals or "[]"),
            "reasoning": r.reasoning,
            "recommended_action": r.recommended_action,
            "confidence": r.confidence,
            "created_at": r.created_at.isoformat() if r.created_at else None
        }
    finally:
        db.close()

def delete_qualified_lead_by_id(lead_id: str) -> bool:
    """Deletes a specific qualified lead by lead_id from SQLite database."""
    db = SessionLocal()
    try:
        r = db.query(LeadQualificationRecord).filter(LeadQualificationRecord.lead_id == lead_id).first()
        if not r:
            return False
        db.delete(r)
        db.commit()
        rerank_all_database_leads()
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting lead {lead_id}: {e}")
        return False
    finally:
        db.close()

def delete_all_qualified_leads() -> int:
    """Deletes ALL qualified lead records from SQLite database."""
    db = SessionLocal()
    try:
        num_deleted = db.query(LeadQualificationRecord).delete()
        db.commit()
        return num_deleted
    except Exception as e:
        db.rollback()
        logger.error(f"Error clearing all leads: {e}")
        return 0
    finally:
        db.close()
