# Lead Qualification Agent 🎯

A production-grade, end-to-end AI agent system built for the **Rooman AI Agent Challenge**. The agent analyzes inbound lead information (structured forms, sales notes, or raw email text), deterministically scores each lead on **Fit** and **Intent**, classifies leads into **HOT**, **WARM**, or **COLD** tiers, ranks leads for sales teams, and generates actionable, evidence-based recommendations so sales teams know **who to call first**.

---

## 📌 Problem

Sales teams often receive hundreds of inbound leads daily through web forms, emails, and campaign responses. Reps waste critical time manually reviewing unstructured inquiries, leading to delayed response times for urgent high-value leads and missed conversion opportunities. Generic LLM chatbots or random AI scoring engines are prone to hallucinations, non-reproducible score volatility, and invented budgets or timelines.

## 💡 Solution

The **Lead Qualification Agent** solves this problem by decoupling numerical lead scoring from generative narrative synthesis:
1. **100% Deterministic Scoring Engine**: Fit Score (0–100 across 5 explicit business categories) and Intent Score (0–100 across 5 explicit engagement categories) are calculated using transparent rule logic.
2. **Zero-Hallucination LLM Rationale**: The LLM is strictly restricted to extracting missing properties from raw text (`email_text`/`notes`), identifying factual buying and risk signals, and generating tailored next sales actions. Missing information is explicitly reported as `"Not provided"` or `"Unknown"`.
3. **Deterministic Ranking & Tie-Breaking**: Ranks leads descending by score and applies tie-breaker logic to ensure sales reps always have a clear, prioritized daily outreach queue.

---

## 🏗️ Architecture

```mermaid
flowchart TD
    A[Inbound Lead Input\nJSON / CSV / Raw Email Text] --> B[Lead Agent Orchestrator]
    B --> C{Unstructured Text?}
    C -- Yes --> D[LLM / Rule Extraction Engine]
    C -- No --> E[Structured Fields]
    D --> E
    E --> F[Deterministic Scoring Engine]
    F --> G1[Fit Analysis 0-100\n45% Weight]
    F --> G2[Intent Analysis 0-100\n55% Weight]
    G1 & G2 --> H[Overall Score Calculation\nround 0.45*Fit + 0.55*Intent]
    H --> I[Tier Classification\nHOT ≥ 75 | WARM ≥ 50 | COLD < 50]
    I --> J[LLM Narrative Synthesis\nSummary, Signals & Sales Action]
    J --> K[Deterministic Lead Ranker & Tie-Breaker]
    K --> L[(SQLite Database Persistence)]
    K --> M[Output Outputs/sample_output.json / API Response / Streamlit UI]
```

---

## 📊 Scoring Logic & Breakdown

The overall qualification score is calculated as:
$$\text{Overall Score} = \text{round}\left( (\text{Fit Score} \times 0.45) + (\text{Intent Score} \times 0.55) \right)$$

Intent is weighted slightly higher (55%) because high immediate intent warrants faster sales response.

### 1. FIT SCORE (0–100 points max)
Evaluates how closely the lead matches the ideal customer profile (ICP):
* **Company/Industry Relevance (0–25 pts)**: High-target sectors (B2B SaaS, AI, Cloud, DeepTech) = 25 pts; Medium (Manufacturing, Logistics, Financials) = 18 pts; Low (Retail, Hospitality) = 10 pts; Unknown = 5 pts.
* **Company Size (0–20 pts)**: Enterprise 500+ = 20 pts; Mid-Market 100–499 = 16 pts; Growing SMB 20–99 = 12 pts; Micro SMB 1–19 = 6 pts; Unknown = 0 pts.
* **Decision-Making Authority (0–20 pts)**: Executive/C-Level/VP/Founder = 20 pts; Director/Manager = 15 pts; Senior IC = 10 pts; Entry/Student = 3 pts; Unknown = 5 pts.
* **Budget Compatibility (0–20 pts)**: $\ge \$50\text{k}$ = 20 pts; $\$20\text{k}\text{--}\$49.9\text{k}$ = 16 pts; $\$5\text{k}\text{--}\$19.9\text{k}$ = 10 pts; $<\$5\text{k}$ = 4 pts; No budget / Unknown = 0 pts.
* **Geographic Compatibility (0–15 pts)**: Tier 1 markets (US, UK, CA, AU, DE, IN) = 15 pts; Tier 2 = 10 pts; Other = 6 pts; Unknown = 5 pts.

### 2. INTENT SCORE (0–100 points max)
Evaluates urgency and buying signals:
* **Explicit Product Interest (0–25 pts)**: Specific core platform solution specified = 25 pts; General interest = 15 pts; Vague = 8 pts; Missing = 0 pts.
* **Purchase Timeline (0–25 pts)**: Urgent / Within 30 days = 25 pts; 1–3 months = 18 pts; 3–6 months = 10 pts; 6+ months / Researching = 4 pts; No timeline = 0 pts.
* **Specific Requirements / Questions (0–20 pts)**: Detailed custom requirements / tech criteria = 20 pts; Basic questions = 12 pts; Minimal = 5 pts; Unknown = 0 pts.
* **Pricing/Demo/Contact Request (0–15 pts)**: Explicit demo or pricing request = 15 pts; Inbound form = 10 pts; Content download = 5 pts; Unknown = 0 pts.
* **Engagement / Urgency Signals (0–15 pts)**: Strong urgency ("evaluating 3 vendors", "budget approved") = 15 pts; Moderate = 10 pts; Negative signals (student, no project) = 0 pts.

### 3. LEAD TIERS
Deterministic threshold cutoffs configured in `app/config.py`:
* **🔥 HOT**: Overall Score $\ge 75$
* **⚡ WARM**: Overall Score $50 \le \text{Score} < 75$
* **❄️ COLD**: Overall Score $< 50$

---

## 🏆 Ranking & Tie-Breaking Logic

When multiple leads are qualified in a batch, leads are sorted descending to determine their rank ($1 \dots N$):
1. **Overall Score** (descending)
2. **Intent Score** (descending)
3. **Purchase Timeline Urgency Score** (descending)
4. **Explicit Demo/Pricing Request Present** (True before False)
5. **Lead ID** (alphabetical ascending for deterministic reproducibility)

---

## 📦 Project Structure

```
lead-qualification-agent/
│
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI application & REST endpoints
│   ├── config.py        # Pydantic Settings & threshold configuration
│   ├── models.py        # SQLAlchemy ORM model for SQLite persistence
│   ├── schemas.py       # Pydantic validation schemas
│   ├── scoring.py       # Deterministic scoring engine & tie-breaker ranker
│   ├── prompts.py       # System prompts & anti-hallucination templates
│   ├── llm.py           # Structured OpenAI client integration & fallback
│   ├── agent.py         # Main LeadQualificationAgent orchestrator
│   ├── database.py      # SQLite connection & CRUD repository
│   └── utils.py         # CSV/JSON file loaders & CLI formatters
│
├── data/
│   ├── sample_leads.json # 10 diverse sample leads (HOT/WARM/COLD)
│   └── sample_leads.csv  # CSV version of sample leads
│
├── tests/
│   ├── __init__.py
│   ├── test_scoring.py  # Unit tests for scoring engine & thresholds
│   ├── test_agent.py    # Tests for agent orchestration & batching
│   └── test_api.py      # Tests for FastAPI REST endpoints
│
├── outputs/
│   └── sample_output.json # Pre-generated sample qualification output
│
├── requirements.txt     # Python dependencies
├── .env.example         # Environment variable template
├── README.md            # System documentation
└── run.py               # CLI entrypoint runner
```

---

## ⚙️ Installation & Setup

### Prerequisites
* Python 3.11+
* pip package manager

### 1. Clone & Set Up Virtual Environment
```bash
git clone <repository_url>
cd "Lead Qualification Agent"

python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Edit `.env` to supply your OpenAI API key (optional - system runs seamlessly with offline fallback if omitted):
```env
OPENAI_API_KEY=your_api_key_here
MODEL_NAME=gpt-4o-mini
DATABASE_URL=sqlite:///./leads.db
HOT_THRESHOLD=75
WARM_THRESHOLD=50
```

---

## 🚀 Running the Application

### 1. Run Web Dashboard & REST API
Start the FastAPI server:
```bash
python -m uvicorn app.main:app --reload --port 8000
```
Then open your web browser at:
* **Interactive AI Dashboard**: `http://localhost:8000`
* **Swagger API Docs**: `http://localhost:8000/docs`
* **ReDoc API Docs**: `http://localhost:8000/redoc`

### 2. Run CLI Batch Runner
Process sample leads and print ranked outputs directly in terminal:
```bash
python run.py
```
To run against a custom CSV or JSON file:
```bash
python run.py --file data/sample_leads.csv --output outputs/my_output.json
```

### 4. Run Automated Unit Tests
Execute the comprehensive offline test suite:
```bash
pytest
```

---

## 📡 API Reference

### `GET /health`
Returns system status.
**Response:**
```json
{
  "status": "ok"
}
```

### `POST /qualify`
Qualifies a single lead input.
**Request Body:**
```json
{
  "name": "Sarah Johnson",
  "company": "Acme SaaS",
  "job_title": "VP Engineering",
  "industry": "B2B SaaS",
  "company_size": 200,
  "location": "United States",
  "budget": "$50,000",
  "interest": "AI automation platform",
  "timeline": "Within 30 days",
  "source": "Website demo request",
  "notes": "We are evaluating three vendors and would like a demo and pricing."
}
```

### `POST /qualify/batch`
Qualifies a list of leads and returns deterministically ranked results.
**Request Body:**
```json
[
  { "lead_id": "L001", "name": "Sarah Johnson", "company": "Acme SaaS", "job_title": "VP Engineering", "industry": "B2B SaaS", "company_size": 200, "budget": "$50,000", "timeline": "Within 30 days", "notes": "Requesting demo" },
  { "lead_id": "L002", "name": "Kevin Patel", "company": "BrightStar Media", "industry": "Media", "company_size": 15, "budget": "No budget", "timeline": "Just researching" }
]
```

### `GET /leads`
Retrieves all stored qualification records from SQLite database ordered by rank.

### `GET /leads/{lead_id}`
Retrieves specific qualification record by lead ID.

---

## 📑 Sample Output Format

```json
{
  "total_leads": 10,
  "hot": 5,
  "warm": 3,
  "cold": 2,
  "leads": [
    {
      "lead_id": "L001",
      "name": "Sarah Johnson",
      "company": "Acme SaaS",
      "job_title": "VP Engineering",
      "fit_score": 96,
      "intent_score": 90,
      "overall_score": 93,
      "tier": "HOT",
      "rank": 1,
      "summary": "VP Engineering at Acme SaaS (B2B SaaS, 200 employees) interested in AI automation platform.",
      "buying_signals": [
        "Explicit request for product demo",
        "Requested pricing / quote details",
        "Urgent purchase timeline (< 30 days)",
        "Active vendor evaluation in progress",
        "High-authority decision maker (VP Engineering)",
        "Strong budget compatibility ($50,000)"
      ],
      "risk_signals": [],
      "reasoning": "Fit Score (96/100) based on industry relevance (25/25), company size (16/20), decision authority (20/20), budget (20/20), and location (15/15). Intent Score (90/100) based on product interest (25/25), timeline (25/25), requirements (10/20), contact request (15/15), and urgency (15/15). Overall Score = round(0.45 * 96 + 0.55 * 90) = 93 [HOT].",
      "recommended_action": "Contact Sarah Johnson within 24 hours. Prioritize product demo and pricing discussion.",
      "confidence": 0.92
    }
  ]
}
```

---

## 🎯 Design Decisions

1. **Why Deterministic Scoring over 100% LLM Prompting?**
   Prompting an LLM to generate a numerical score (e.g. "Give this lead a score out of 100") introduces high score variance, non-reproducible output across runs, and vulnerability to prompt injection or hallucinated numbers. By separating numerical scoring into a rule engine and using the LLM strictly for natural language extraction and narrative synthesis, the system achieves 100% explainability, auditability, and zero score hallucination.

2. **Why Weight Intent (55%) higher than Fit (45%)?**
   A high-fit enterprise lead that has no purchase timeline or immediate interest ("just researching") should not displace a slightly smaller SMB lead that needs an active deployment within 30 days and requested a demo today. Intent reflects immediate revenue velocity.

3. **Offline Fallback Architecture**:
   If no OpenAI API key is present or if the LLM API times out, the system automatically falls back to regex-based extraction and template-based narrative generation, guaranteeing 0% runtime crash rate.

---

## ⚖️ Tradeoffs

* **Accuracy vs. Simplicity**: Rule-based scoring requires pre-defined keyword lists and thresholds. While simple and reliable, extreme edge cases in specialized sub-niches may require periodic keyword updates.
* **Rule Precision vs. Generalization**: Hardcoded thresholds (e.g. $50k budget = 20 pts) provide strict consistency but may require tier customization across different product lines.
* **Unstructured Extraction Dependency**: Highly messy or ambiguous email text relies on LLM extraction. If the LLM is offline, fallback regex extraction captures basic entities but may miss nuanced secondary notes.

---

## 🚫 Limitations

* **Single Product Focus**: The current rules assume a single core product/service ICP model. Multi-product enterprises would need product-specific weight configurations.
* **Static Keyword Lists**: Signal extraction relies on predefined buying and risk signal dictionaries.
* **No Real-Time Enrichment**: Does not currently perform live web scraping (e.g., Clearbit / LinkedIn lookup) to auto-fill missing company data.

---

## 🔮 Future Improvements

1. **CRM Integrations**: Bi-directional integration with Salesforce, HubSpot, and Pipedrive to sync lead tiers and trigger automated SDR task creation.
2. **Historical Conversion Rate Learning**: Machine learning model trained on historic closed-won CRM deals to dynamically tune category weightings.
3. **Multi-Product / Multi-ICP Configuration**: Dynamic scoring profiles selectable per business unit.
4. **Third-Party Data Enrichment**: Automatic firmographic enrichment via ZoomInfo / Clearbit API when company fields are missing.
5. **Human-in-the-Loop Review**: Sales rep feedback buttons ("Agree / Disagree with Tier") to refine signal extraction.
