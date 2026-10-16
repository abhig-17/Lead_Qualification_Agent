import uuid
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Union
from datetime import datetime, timezone

from app.schemas import (
    LeadInput, QualifiedLead, BatchQualificationResponse
)
from app.scoring import (
    evaluate_lead_scores, extract_buying_and_risk_signals, rank_leads
)
from app.llm import (
    generate_llm_analysis,
    extract_and_analyze_combined,
)
from app.database import init_db, save_qualified_lead, save_batch_qualified_leads, rerank_all_database_leads

logger = logging.getLogger(__name__)

# Max parallel LLM calls during batch processing (bounded to avoid rate-limit bursts)
_BATCH_MAX_WORKERS = 5


class LeadQualificationAgent:
    def __init__(self):
        init_db()

    def qualify_lead(
        self,
        input_data: Union[LeadInput, Dict[str, Any]],
        _skip_rerank: bool = False,
    ) -> QualifiedLead:
        """
        Analyzes a single inbound lead:
        1. Normalizes input and auto-assigns ID if missing.
        2. Performs unstructured text extraction if email_text or notes exist.
        3. Deterministically computes Fit Score, Intent Score, Overall Score, and Tier.
        4. Extracts buying and risk signals.
        5. Calls LLM (or fallback) for factual summary and recommended sales action.
        6. Persists result to SQLite DB.

        Args:
            input_data: The raw lead input (LeadInput or dict).
            _skip_rerank: Internal flag — when True, skips the per-lead global DB
                re-rank so batch processing can do a single re-rank at the end
                instead of one per lead (eliminates O(N²) DB round-trips).
        """
        if isinstance(input_data, LeadInput):
            lead_dict = input_data.model_dump(exclude_unset=True)
        elif isinstance(input_data, dict):
            lead_dict = dict(input_data)
        else:
            raise ValueError("Input data must be a LeadInput or a dictionary.")

        # Ensure lead_id
        if not lead_dict.get("lead_id"):
            lead_dict["lead_id"] = f"L-{uuid.uuid4().hex[:6].upper()}"
        lead_id = str(lead_dict["lead_id"])

        # Detect unstructured text
        unstructured_text = lead_dict.get("email_text") or lead_dict.get("notes") or lead_dict.get("sales_notes")
        has_unstructured = bool(unstructured_text and len(str(unstructured_text).strip()) > 10)

        if has_unstructured:
            # ---------------------------------------------------------------
            # FAST PATH: single combined LLM call does extraction + analysis
            # in one round-trip instead of two sequential calls.
            # ---------------------------------------------------------------
            # Score first with whatever structured fields we already have
            fit_score, intent_score, overall_score, tier, score_bd = evaluate_lead_scores(lead_dict)
            rule_buying_signals, rule_risk_signals = extract_buying_and_risk_signals(lead_dict)

            extracted, llm_analysis = extract_and_analyze_combined(
                text=str(unstructured_text),
                lead_dict=lead_dict,
                fit_score=fit_score,
                intent_score=intent_score,
                overall_score=overall_score,
                tier=tier,
                rule_buying_signals=rule_buying_signals,
                rule_risk_signals=rule_risk_signals,
            )

            # Enrich lead_dict with newly extracted attributes and re-score
            enriched = False
            for field in ["name", "company", "job_title", "industry", "company_size", "location", "budget", "interest", "timeline"]:
                if not lead_dict.get(field) and getattr(extracted, field, None):
                    lead_dict[field] = getattr(extracted, field)
                    enriched = True

            if enriched:
                # Re-score with richer data (deterministic, near-zero cost)
                fit_score, intent_score, overall_score, tier, score_bd = evaluate_lead_scores(lead_dict)
                rule_buying_signals, rule_risk_signals = extract_buying_and_risk_signals(lead_dict)
        else:
            # ---------------------------------------------------------------
            # STRUCTURED PATH: score deterministically, one LLM analysis call
            # ---------------------------------------------------------------
            fit_score, intent_score, overall_score, tier, score_bd = evaluate_lead_scores(lead_dict)
            rule_buying_signals, rule_risk_signals = extract_buying_and_risk_signals(lead_dict)

            llm_analysis = generate_llm_analysis(
                lead_dict=lead_dict,
                fit_score=fit_score,
                intent_score=intent_score,
                overall_score=overall_score,
                tier=tier,
                rule_buying_signals=rule_buying_signals,
                rule_risk_signals=rule_risk_signals,
            )

        # Combine signals (deduplicated)
        all_buying_signals = list(dict.fromkeys(rule_buying_signals + llm_analysis.buying_signals))
        all_risk_signals = list(dict.fromkeys(rule_risk_signals + llm_analysis.risk_signals))

        # Generate transparent reasoning string
        reasoning = (
            f"Fit Score ({fit_score}/100) based on industry relevance ({score_bd.fit.industry_relevance}/25), "
            f"company size ({score_bd.fit.company_size}/20), decision authority ({score_bd.fit.decision_authority}/20), "
            f"budget ({score_bd.fit.budget_compatibility}/20), and location ({score_bd.fit.geographic_fit}/15). "
            f"Intent Score ({intent_score}/100) based on product interest ({score_bd.intent.product_interest}/25), "
            f"timeline ({score_bd.intent.purchase_timeline}/25), requirements ({score_bd.intent.specific_requirements}/20), "
            f"contact request ({score_bd.intent.contact_request}/15), and urgency ({score_bd.intent.urgency_signals}/15). "
            f"Overall Score = round(0.45 * {fit_score} + 0.55 * {intent_score}) = {overall_score} [{tier}]."
        )

        name_final = lead_dict.get("name") or "Unknown Lead"
        company_final = lead_dict.get("company") or "Unknown Company"
        title_final = lead_dict.get("job_title") or "Unknown Role"

        qualified_lead = QualifiedLead(
            lead_id=lead_id,
            name=name_final,
            company=company_final,
            job_title=title_final,
            fit_score=fit_score,
            intent_score=intent_score,
            overall_score=overall_score,
            tier=tier,
            summary=llm_analysis.summary,
            buying_signals=all_buying_signals,
            risk_signals=all_risk_signals,
            reasoning=reasoning,
            recommended_action=llm_analysis.recommended_action,
            confidence=llm_analysis.confidence,
            score_breakdown=score_bd,
            created_at=datetime.now(timezone.utc).isoformat()
        )

        # Save to database
        save_qualified_lead(qualified_lead, raw_input=lead_dict)

        # Re-rank all database records — skipped during batch to avoid O(N²) DB calls.
        # qualify_batch() performs a single re-rank after all leads are processed.
        if not _skip_rerank:
            reranked = rerank_all_database_leads()
            for item in reranked:
                if item.get("lead_id") == lead_id:
                    qualified_lead.rank = item.get("rank")
                    break

        return qualified_lead

    def qualify_batch(self, leads_input: List[Union[LeadInput, Dict[str, Any]]]) -> BatchQualificationResponse:
        """
        Qualifies multiple leads in parallel, ranks them deterministically, saves them
        to SQLite DB, and returns a summary response with counts per tier.

        Parallelism: up to _BATCH_MAX_WORKERS concurrent threads process LLM calls
        simultaneously. The global DB re-rank is performed once after all leads are
        processed (instead of once per lead), which eliminates the O(N²) bottleneck.
        """
        qualified_list = []
        raw_inputs = []

        def _process_one(lead_item):
            """Worker: qualify a single lead with rerank suppressed."""
            return self.qualify_lead(lead_item, _skip_rerank=True)

        # Parallel execution with bounded thread pool
        with ThreadPoolExecutor(max_workers=_BATCH_MAX_WORKERS) as executor:
            future_to_item = {
                executor.submit(_process_one, lead_item): lead_item
                for lead_item in leads_input
            }
            for future in as_completed(future_to_item):
                lead_item = future_to_item[future]
                try:
                    qualified_lead = future.result()
                    qualified_list.append(qualified_lead.model_dump())
                    if isinstance(lead_item, LeadInput):
                        raw_inputs.append(lead_item.model_dump())
                    elif isinstance(lead_item, dict):
                        raw_inputs.append(lead_item)
                except Exception as e:
                    logger.error(f"Error processing lead item {lead_item}: {e}")
                    # Continue batch processing despite single lead failure

        # Single deterministic re-rank + tie-break across the whole batch
        ranked_list = rank_leads(qualified_list)

        # Re-construct QualifiedLead objects with assigned ranks
        final_qualified_leads = [QualifiedLead(**item) for item in ranked_list]

        # Persist final ranks to SQLite (one batch write)
        save_batch_qualified_leads(final_qualified_leads, raw_inputs=raw_inputs)

        # Counts per tier
        hot_count = sum(1 for lead in final_qualified_leads if lead.tier == "HOT")
        warm_count = sum(1 for lead in final_qualified_leads if lead.tier == "WARM")
        cold_count = sum(1 for lead in final_qualified_leads if lead.tier == "COLD")

        return BatchQualificationResponse(
            total_leads=len(final_qualified_leads),
            hot=hot_count,
            warm=warm_count,
            cold=cold_count,
            leads=final_qualified_leads
        )
