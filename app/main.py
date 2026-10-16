import logging
import json
import uvicorn
from pathlib import Path
from typing import List, Union, Dict, Any
from fastapi import FastAPI, HTTPException, status, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse

from app.schemas import LeadInput, QualifiedLead, BatchQualificationResponse
from app.agent import LeadQualificationAgent
from app.database import (
    init_db, fetch_all_qualified_leads, fetch_qualified_lead_by_id,
    rerank_all_database_leads, delete_qualified_lead_by_id, delete_all_qualified_leads
)
from app.utils import load_leads_from_json, load_leads_from_csv

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("lead-agent-api")

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("Lead Qualification Agent API initialized successfully.")
    yield

app = FastAPI(
    title="Lead Qualification Agent API",
    description="Production-grade AI agent system for scoring, prioritizing, and ranking inbound sales leads.",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

agent = LeadQualificationAgent()

@app.get("/health", status_code=status.HTTP_200_OK)
def health_check():
    return {"status": "ok"}

@app.get("/sample-leads", status_code=status.HTTP_200_OK)
def get_sample_leads():
    """Reads live sample leads from data/sample_leads.json on disk."""
    sample_path = Path("data/sample_leads.json")
    if not sample_path.exists():
        raise HTTPException(status_code=404, detail="Sample leads file not found.")
    return load_leads_from_json(str(sample_path))

@app.get("/", response_class=HTMLResponse)
def index_web_dashboard():
    """Serves the high-contrast modern AI Sales Intelligence SaaS Dashboard on http://localhost:8000."""
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Lead Qualification AI — Sales Intelligence Platform</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.2/font/bootstrap-icons.min.css">
    <style>
        :root {
            --bg-dark: #0B1120;
            --bg-surface: #111827;
            --bg-card: rgba(21, 31, 50, 0.85);
            --bg-card-hover: rgba(30, 41, 59, 0.95);
            --border-subtle: rgba(255, 255, 255, 0.12);
            --border-glow: rgba(56, 189, 248, 0.4);
            
            --accent-cyan: #38BDF8;
            --accent-blue: #3B82F6;
            --accent-purple: #818CF8;
            
            --tier-hot-bg: rgba(239, 68, 68, 0.15);
            --tier-hot-border: rgba(239, 68, 68, 0.5);
            --tier-hot-text: #F87171;
            
            --tier-warm-bg: rgba(245, 158, 11, 0.15);
            --tier-warm-border: rgba(245, 158, 11, 0.5);
            --tier-warm-text: #FBBF24;
            
            --tier-cold-bg: rgba(59, 130, 246, 0.15);
            --tier-cold-border: rgba(59, 130, 246, 0.5);
            --tier-cold-text: #60A5FA;
            
            --text-primary: #F8FAFC;
            --text-secondary: #CBD5E1;
            --text-muted: #94A3B8;
        }

        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background-color: var(--bg-dark);
            color: var(--text-primary);
            min-height: 100vh;
            padding-bottom: 60px;
            overflow-x: hidden;
            background-image: 
                radial-gradient(circle at 15% 15%, rgba(56, 189, 248, 0.05) 0%, transparent 45%),
                radial-gradient(circle at 85% 65%, rgba(99, 102, 241, 0.05) 0%, transparent 45%);
        }

        /* Top Bar Navigation */
        .top-navbar {
            background-color: rgba(11, 17, 32, 0.95);
            backdrop-filter: blur(16px);
            border-bottom: 1px solid var(--border-subtle);
            padding: 0.85rem 0;
            position: sticky;
            top: 0;
            z-index: 1000;
        }

        .brand-logo {
            display: flex;
            align-items: center;
            gap: 12px;
            text-decoration: none;
            color: var(--text-primary);
        }

        .brand-icon {
            width: 40px;
            height: 40px;
            background: linear-gradient(135deg, var(--accent-blue) 0%, var(--accent-cyan) 100%);
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 1.25rem;
            box-shadow: 0 0 20px rgba(56, 189, 248, 0.35);
        }

        .brand-text {
            font-weight: 700;
            font-size: 1.15rem;
            letter-spacing: -0.02em;
        }

        .nav-pills-custom {
            display: flex;
            gap: 8px;
            background: rgba(17, 24, 39, 0.8);
            padding: 5px;
            border-radius: 12px;
            border: 1px solid var(--border-subtle);
        }

        .nav-pills-custom .nav-link {
            color: var(--text-secondary);
            font-weight: 600;
            font-size: 0.9rem;
            padding: 8px 18px;
            border-radius: 8px;
            transition: all 0.2s ease;
            border: none;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .nav-pills-custom .nav-link:hover {
            color: var(--text-primary);
            background: rgba(255, 255, 255, 0.08);
        }

        .nav-pills-custom .nav-link.active {
            color: #ffffff;
            background: linear-gradient(135deg, rgba(59, 130, 246, 0.95) 0%, rgba(37, 99, 235, 0.95) 100%);
            box-shadow: 0 4px 14px rgba(37, 99, 235, 0.4);
        }

        /* Hero Header */
        .hero-section {
            padding: 2.2rem 0 1.5rem 0;
        }

        .hero-title {
            font-weight: 800;
            font-size: 2rem;
            letter-spacing: -0.03em;
            background: linear-gradient(180deg, #FFFFFF 0%, #E2E8F0 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .hero-subtitle {
            color: var(--text-secondary);
            font-size: 0.95rem;
            margin-top: 4px;
        }

        /* Metric Cards */
        .card-surface {
            background: var(--bg-card);
            backdrop-filter: blur(16px);
            border: 1px solid var(--border-subtle);
            border-radius: 16px;
            padding: 1.4rem;
            transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
        }

        .card-surface:hover {
            border-color: rgba(255, 255, 255, 0.2);
            transform: translateY(-2px);
            box-shadow: 0 10px 30px -5px rgba(0, 0, 0, 0.4);
        }

        .metric-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.75rem;
        }

        .metric-title {
            color: var(--text-muted);
            font-size: 0.78rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.08em;
        }

        .metric-icon-box {
            width: 36px;
            height: 36px;
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.1rem;
        }

        .metric-num {
            font-size: 2.2rem;
            font-weight: 800;
            letter-spacing: -0.03em;
            line-height: 1;
        }

        .metric-badge {
            font-size: 0.75rem;
            font-weight: 600;
            padding: 3px 10px;
            border-radius: 6px;
            display: inline-flex;
            align-items: center;
            gap: 4px;
            margin-top: 10px;
        }

        /* Tier Badges */
        .tier-badge-hot {
            background: var(--tier-hot-bg);
            border: 1px solid var(--tier-hot-border);
            color: var(--tier-hot-text);
            padding: 5px 14px;
            border-radius: 20px;
            font-weight: 700;
            font-size: 0.85rem;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            letter-spacing: 0.03em;
        }

        .tier-badge-warm {
            background: var(--tier-warm-bg);
            border: 1px solid var(--tier-warm-border);
            color: var(--tier-warm-text);
            padding: 5px 14px;
            border-radius: 20px;
            font-weight: 700;
            font-size: 0.85rem;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            letter-spacing: 0.03em;
        }

        .tier-badge-cold {
            background: var(--tier-cold-bg);
            border: 1px solid var(--tier-cold-border);
            color: var(--tier-cold-text);
            padding: 5px 14px;
            border-radius: 20px;
            font-weight: 700;
            font-size: 0.85rem;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            letter-spacing: 0.03em;
        }

        /* Form Inputs */
        .form-label-custom {
            color: #E2E8F0;
            font-size: 0.82rem;
            font-weight: 700;
            margin-bottom: 6px;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }

        .form-control-custom, .form-select-custom {
            background-color: rgba(15, 23, 42, 0.9);
            border: 1px solid rgba(255, 255, 255, 0.15);
            color: #F8FAFC;
            border-radius: 10px;
            padding: 0.65rem 0.9rem;
            font-size: 0.92rem;
            transition: all 0.2s ease;
        }

        .form-control-custom:focus, .form-select-custom:focus {
            background-color: rgba(15, 23, 42, 1);
            border-color: var(--accent-cyan);
            color: #FFFFFF;
            box-shadow: 0 0 0 3px rgba(56, 189, 248, 0.2);
            outline: none;
        }

        /* Buttons */
        .btn-gradient-primary {
            background: linear-gradient(135deg, #3B82F6 0%, #2563EB 100%);
            color: white;
            border: none;
            font-weight: 700;
            border-radius: 10px;
            padding: 0.75rem 1.4rem;
            transition: all 0.2s ease;
            box-shadow: 0 4px 16px rgba(37, 99, 235, 0.4);
        }

        .btn-gradient-primary:hover {
            background: linear-gradient(135deg, #60A5FA 0%, #3B82F6 100%);
            color: white;
            transform: translateY(-1px);
            box-shadow: 0 6px 22px rgba(37, 99, 235, 0.5);
        }

        .btn-gradient-success {
            background: linear-gradient(135deg, #10B981 0%, #059669 100%);
            color: white;
            border: none;
            font-weight: 700;
            border-radius: 10px;
            padding: 0.75rem 1.4rem;
            transition: all 0.2s ease;
            box-shadow: 0 4px 16px rgba(16, 185, 129, 0.4);
        }

        .btn-gradient-success:hover {
            background: linear-gradient(135deg, #34D399 0%, #10B981 100%);
            color: white;
            transform: translateY(-1px);
        }

        .btn-glass-danger {
            background: rgba(239, 68, 68, 0.15);
            border: 1px solid rgba(239, 68, 68, 0.4);
            color: #F87171;
            font-weight: 600;
            border-radius: 8px;
            padding: 0.4rem 0.9rem;
            transition: all 0.2s ease;
        }

        .btn-glass-danger:hover {
            background: rgba(239, 68, 68, 0.3);
            color: #FFFFFF;
            border-color: rgba(239, 68, 68, 0.7);
        }

        /* Progress Bars */
        .progress-custom {
            height: 10px;
            background-color: rgba(255, 255, 255, 0.1);
            border-radius: 99px;
            overflow: hidden;
        }

        .progress-bar-fit {
            background: linear-gradient(90deg, #38BDF8 0%, #3B82F6 100%);
            border-radius: 99px;
        }

        .progress-bar-intent {
            background: linear-gradient(90deg, #F59E0B 0%, #EF4444 100%);
            border-radius: 99px;
        }

        /* Signal Pills */
        .signal-pill-buy {
            background: rgba(16, 185, 129, 0.15);
            border: 1px solid rgba(16, 185, 129, 0.35);
            color: #34D399;
            padding: 6px 12px;
            border-radius: 8px;
            font-size: 0.85rem;
            font-weight: 600;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            margin-bottom: 6px;
            margin-right: 6px;
        }

        .signal-pill-risk {
            background: rgba(239, 68, 68, 0.15);
            border: 1px solid rgba(239, 68, 68, 0.35);
            color: #F87171;
            padding: 6px 12px;
            border-radius: 8px;
            font-size: 0.85rem;
            font-weight: 600;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            margin-bottom: 6px;
            margin-right: 6px;
        }

        /* Recommended Action Box */
        .action-card {
            background: linear-gradient(135deg, rgba(30, 41, 59, 0.95) 0%, rgba(15, 23, 42, 0.98) 100%);
            border: 1px solid rgba(56, 189, 248, 0.35);
            border-radius: 12px;
            padding: 1.25rem;
            position: relative;
            overflow: hidden;
            box-shadow: 0 0 25px rgba(56, 189, 248, 0.15);
        }

        .action-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 4px;
            height: 100%;
            background: linear-gradient(180deg, var(--accent-cyan) 0%, var(--accent-blue) 100%);
        }

        /* Tables */
        .table-custom {
            color: var(--text-primary);
            vertical-align: middle;
            margin-bottom: 0;
        }

        .table-custom th {
            background: rgba(15, 23, 42, 0.95);
            color: var(--text-muted);
            font-size: 0.75rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            padding: 1rem 1.2rem;
            border-bottom: 1px solid var(--border-subtle);
        }

        .table-custom td {
            padding: 1rem 1.2rem;
            border-bottom: 1px solid var(--border-subtle);
            background: transparent;
            font-size: 0.9rem;
        }

        .table-custom tbody tr {
            transition: background 0.15s ease;
        }

        .table-custom tbody tr:hover {
            background: var(--bg-card-hover) !important;
        }

        /* Spinner Overlay */
        .spinner-overlay {
            display: none;
            text-align: center;
            padding: 4rem 1rem;
            margin: auto;
        }

        .spinner-overlay .spinner-border {
            width: 3.5rem;
            height: 3.5rem;
            border-width: 0.25em;
            color: #38BDF8 !important;
        }

        .spinner-overlay p {
            color: #F8FAFC !important;
            font-weight: 600;
            font-size: 1rem;
            margin-top: 1.2rem;
        }

        /* Podium Section */
        .podium-container {
            display: flex;
            justify-content: center;
            align-items: flex-end;
            gap: 16px;
            margin: 1.5rem 0 2rem 0;
        }

        .podium-card {
            background: var(--bg-card);
            border: 1px solid var(--border-subtle);
            border-radius: 16px;
            padding: 1.2rem;
            text-align: center;
            flex: 1;
            max-width: 280px;
            transition: all 0.2s ease;
            position: relative;
        }

        .podium-card-1 {
            border-color: rgba(251, 191, 36, 0.6);
            background: linear-gradient(180deg, rgba(251, 191, 36, 0.12) 0%, var(--bg-card) 100%);
            transform: scale(1.05);
            z-index: 2;
        }

        .podium-crown {
            font-size: 1.8rem;
            margin-bottom: 4px;
        }

        /* Drag and Drop Zone */
        .dropzone-card {
            border: 2px dashed rgba(255, 255, 255, 0.2);
            background: rgba(15, 23, 42, 0.6);
            border-radius: 16px;
            padding: 2.5rem;
            text-align: center;
            transition: all 0.2s ease;
        }

        .dropzone-card:hover {
            border-color: var(--accent-cyan);
            background: rgba(15, 23, 42, 0.95);
        }

        /* Toast notifications */
        .toast-container-custom {
            position: fixed;
            bottom: 24px;
            right: 24px;
            z-index: 9999;
        }

        .toast-custom {
            background: var(--bg-surface);
            border: 1px solid var(--accent-cyan);
            color: white;
            padding: 12px 20px;
            border-radius: 10px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 0.9rem;
            font-weight: 600;
            animation: slideIn 0.3s ease;
        }

        @keyframes slideIn {
            from { transform: translateY(100%); opacity: 0; }
            to { transform: translateY(0); opacity: 1; }
        }
    </style>
</head>
<body>

<!-- Top Navigation Bar -->
<nav class="top-navbar">
    <div class="container d-flex justify-content-between align-items-center">
        <a href="/" class="brand-logo">
            <div class="brand-icon">
                <i class="bi bi-cpu-fill"></i>
            </div>
            <div>
                <div class="brand-text">Lead Qualification AI</div>
                <div style="font-size: 0.72rem; color: var(--text-muted); font-weight: 600;">ROAMAN AI CHALLENGE</div>
            </div>
        </a>

        <div class="nav-pills-custom" id="mainTab" role="tablist">
            <button class="nav-link active" id="single-tab" data-bs-toggle="tab" data-bs-target="#single" type="button">
                <i class="bi bi-lightning-charge-fill"></i> Single Lead
            </button>
            <button class="nav-link" id="batch-tab" data-bs-toggle="tab" data-bs-target="#batch" type="button">
                <i class="bi bi-layers-fill"></i> Pipeline Workspace
            </button>
            <button class="nav-link" id="leaderboard-tab" data-bs-toggle="tab" data-bs-target="#leaderboard" type="button">
                <i class="bi bi-trophy-fill"></i> Leaderboard
            </button>
        </div>

        <div class="d-flex align-items-center gap-3">
            <span class="badge bg-success-subtle text-success border border-success-subtle px-3 py-2 rounded-pill" style="font-size: 0.78rem; font-weight: 600;">
                <i class="bi bi-circle-fill me-1" style="font-size: 0.5rem;"></i> AI Engine Active
            </span>
        </div>
    </div>
</nav>

<!-- Hero Section -->
<div class="container hero-section">
    <div class="d-flex justify-content-between align-items-end">
        <div>
            <h1 class="hero-title">Lead Qualification Intelligence</h1>
            <p class="hero-subtitle">Deterministic scoring engine & Groq LLM narrative synthesis for high-velocity sales.</p>
        </div>
        <div>
            <button class="btn btn-sm btn-outline-light rounded-pill px-3" onclick="loadLeaderboard()" style="font-weight: 600;">
                <i class="bi bi-arrow-clockwise me-1"></i> Refresh Pipeline
            </button>
        </div>
    </div>
</div>

<div class="container">
    <!-- Metric Summary Row -->
    <div class="row g-3 mb-4">
        <div class="col-md-3">
            <div class="card-surface">
                <div class="metric-header">
                    <span class="metric-title">Total Pipeline Leads</span>
                    <div class="metric-icon-box" style="background: rgba(56, 189, 248, 0.15); color: var(--accent-cyan);">
                        <i class="bi bi-people-fill"></i>
                    </div>
                </div>
                <div class="metric-num text-white" id="metric-total">0</div>
                <div class="metric-badge" style="background: rgba(255,255,255,0.08); color: var(--text-secondary);">
                    All Inbound Records
                </div>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card-surface">
                <div class="metric-header">
                    <span class="metric-title">🔥 Hot Leads</span>
                    <div class="metric-icon-box" style="background: rgba(239, 68, 68, 0.15); color: #F87171;">
                        <i class="bi bi-fire"></i>
                    </div>
                </div>
                <div class="metric-num text-danger" id="metric-hot">0</div>
                <div class="metric-badge" style="background: var(--tier-hot-bg); color: var(--tier-hot-text);">
                    Score ≥ 75 • Immediate Action
                </div>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card-surface">
                <div class="metric-header">
                    <span class="metric-title">⚡ Warm Leads</span>
                    <div class="metric-icon-box" style="background: rgba(245, 158, 11, 0.15); color: #FBBF24;">
                        <i class="bi bi-bolt-fill"></i>
                    </div>
                </div>
                <div class="metric-num text-warning" id="metric-warm">0</div>
                <div class="metric-badge" style="background: var(--tier-warm-bg); color: var(--tier-warm-text);">
                    Score 50–74 • Follow Up 2–3 Days
                </div>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card-surface">
                <div class="metric-header">
                    <span class="metric-title">❄️ Cold Leads</span>
                    <div class="metric-icon-box" style="background: rgba(59, 130, 246, 0.15); color: #60A5FA;">
                        <i class="bi bi-snow2"></i>
                    </div>
                </div>
                <div class="metric-num text-info" id="metric-cold">0</div>
                <div class="metric-badge" style="background: var(--tier-cold-bg); color: var(--tier-cold-text);">
                    Score < 50 • Nurture Campaign
                </div>
            </div>
        </div>
    </div>

    <div class="tab-content" id="mainTabContent">
        <!-- Tab 1: Single Lead Qualification -->
        <div class="tab-pane fade show active" id="single" role="tabpanel">
            <div class="row g-4">
                <div class="col-lg-6">
                    <div class="card-surface">
                        <div class="d-flex justify-content-between align-items-center mb-3">
                            <h5 class="fw-bold mb-0"><i class="bi bi-person-badge me-2 text-info"></i>Inbound Lead Details</h5>
                            <span class="text-muted" style="font-size: 0.8rem; font-weight: 600;">Form / Unstructured Inquiry</span>
                        </div>
                        <form id="lead-form">
                            <div class="mb-3">
                                <label class="form-label-custom">Contact Name *</label>
                                <input type="text" id="name" class="form-control-custom w-100" value="Abhishek" required>
                            </div>
                            <div class="row g-2 mb-3">
                                <div class="col-md-6">
                                    <label class="form-label-custom">Company</label>
                                    <input type="text" id="company" class="form-control-custom w-100" value="Acme SaaS">
                                </div>
                                <div class="col-md-6">
                                    <label class="form-label-custom">Job Title</label>
                                    <input type="text" id="job_title" class="form-control-custom w-100" value="VP Engineering">
                                </div>
                            </div>
                            <div class="row g-2 mb-3">
                                <div class="col-md-6">
                                    <label class="form-label-custom">Industry</label>
                                    <input type="text" id="industry" class="form-control-custom w-100" value="B2B SaaS">
                                </div>
                                <div class="col-md-6">
                                    <label class="form-label-custom">Company Size</label>
                                    <input type="number" id="company_size" class="form-control-custom w-100" value="200">
                                </div>
                            </div>
                            <div class="row g-2 mb-3">
                                <div class="col-md-6">
                                    <label class="form-label-custom">Budget</label>
                                    <input type="text" id="budget" class="form-control-custom w-100" value="$50,000">
                                </div>
                                <div class="col-md-6">
                                    <label class="form-label-custom">Timeline</label>
                                    <input type="text" id="timeline" class="form-control-custom w-100" value="Within 30 days">
                                </div>
                            </div>
                            <div class="mb-3">
                                <label class="form-label-custom">Product Interest</label>
                                <input type="text" id="interest" class="form-control-custom w-100" value="AI automation platform">
                            </div>
                            <div class="mb-3">
                                <label class="form-label-custom">Sales Notes / Email Text</label>
                                <textarea id="notes" class="form-control-custom w-100" rows="3">We are actively evaluating three vendors and would like a product demo and pricing discussion ASAP.</textarea>
                            </div>
                            <button type="submit" class="btn btn-gradient-primary w-100 py-2.5" id="single-submit-btn">
                                <i class="bi bi-lightning-charge-fill me-1"></i> Qualify Lead Now
                            </button>
                        </form>
                    </div>
                </div>

                <div class="col-lg-6">
                    <div class="card-surface h-100 d-flex flex-column" id="result-card">
                        <h5 class="fw-bold mb-3"><i class="bi bi-stars me-2 text-warning"></i>AI Qualification Results</h5>
                        
                        <!-- High Contrast Placeholder -->
                        <div id="result-placeholder" class="text-center py-5 my-auto" style="color: #94A3B8;">
                            <div class="mb-3">
                                <i class="bi bi-robot" style="font-size: 3.5rem; color: #38BDF8; filter: drop-shadow(0 0 15px rgba(56, 189, 248, 0.4));"></i>
                            </div>
                            <h6 class="fw-bold text-white mb-2" style="font-size: 1.1rem;">Awaiting Lead Submission</h6>
                            <p class="mx-auto" style="max-width: 360px; color: #CBD5E1; font-size: 0.9rem; line-height: 1.5;">
                                Fill out the lead details on the left and click <strong class="text-white">Qualify Lead Now</strong> to generate instant AI scoring & sales recommendations.
                            </p>
                        </div>

                        <!-- Centered Glowing Spinner -->
                        <div id="single-spinner" class="spinner-overlay my-auto">
                            <div class="spinner-border" role="status"></div>
                            <p>Analyzing lead with Groq LLM & Scoring Engine...</p>
                        </div>

                        <div id="result-content" style="display: none;">
                            <div class="d-flex justify-content-between align-items-center mb-4">
                                <div>
                                    <span id="res-rank" class="badge bg-warning-subtle text-warning border border-warning-subtle px-2.5 py-1 font-weight-700 me-2" style="font-size: 0.9rem;">#1</span>
                                    <h3 class="fw-bold d-inline mb-0" id="res-name">-</h3>
                                    <div class="text-secondary mt-1" style="font-size: 0.9rem;" id="res-company">-</div>
                                </div>
                                <div>
                                    <span id="res-tier" class="tier-badge-hot">🔥 HOT</span>
                                </div>
                            </div>

                            <!-- Overall Score Card -->
                            <div class="p-3 mb-4 rounded-3 border" style="background: rgba(15, 23, 42, 0.85); border-color: rgba(255,255,255,0.12)!important;">
                                <div class="row align-items-center">
                                    <div class="col-md-5 text-center border-end border-secondary border-opacity-25">
                                        <span class="text-muted text-uppercase fw-bold" style="font-size: 0.75rem; letter-spacing: 0.08em;">Overall Score</span>
                                        <div class="display-5 fw-extrabold text-white my-1" id="res-overall">94</div>
                                        <span class="text-secondary" style="font-size: 0.8rem;">45% Fit + 55% Intent</span>
                                    </div>
                                    <div class="col-md-7 ps-4">
                                        <div class="mb-3">
                                            <div class="d-flex justify-content-between text-secondary mb-1" style="font-size: 0.83rem;">
                                                <span class="fw-bold text-info"><i class="bi bi-building me-1"></i> FIT SCORE</span>
                                                <span class="fw-bold text-white"><span id="res-fit">91</span> / 100</span>
                                            </div>
                                            <div class="progress-custom">
                                                <div class="progress-bar-fit" id="bar-fit" style="width: 91%;"></div>
                                            </div>
                                        </div>
                                        <div>
                                            <div class="d-flex justify-content-between text-secondary mb-1" style="font-size: 0.83rem;">
                                                <span class="fw-bold text-warning"><i class="bi bi-graph-up-arrow me-1"></i> INTENT SCORE</span>
                                                <span class="fw-bold text-white"><span id="res-intent">96</span> / 100</span>
                                            </div>
                                            <div class="progress-custom">
                                                <div class="progress-bar-intent" id="bar-intent" style="width: 96%;"></div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <!-- Summary -->
                            <div class="mb-4">
                                <h6 class="text-uppercase text-muted fw-bold mb-2" style="font-size: 0.75rem; letter-spacing: 0.08em;">Summary</h6>
                                <p class="text-light fs-6 mb-0" id="res-summary" style="line-height: 1.6;">-</p>
                            </div>

                            <!-- Action Box -->
                            <div class="action-card mb-4">
                                <div class="fw-bold text-info text-uppercase mb-1" style="font-size: 0.78rem; letter-spacing: 0.08em;">
                                    <i class="bi bi-send-fill me-1"></i> RECOMMENDED NEXT ACTION
                                </div>
                                <div class="fs-6 font-weight-600 text-white" id="res-action">-</div>
                            </div>

                            <!-- Signals -->
                            <div class="row">
                                <div class="col-md-6 mb-3 mb-md-0">
                                    <h6 class="text-uppercase text-success fw-bold mb-2" style="font-size: 0.75rem; letter-spacing: 0.08em;">🟢 Buying Signals</h6>
                                    <div id="res-buying"></div>
                                </div>
                                <div class="col-md-6">
                                    <h6 class="text-uppercase text-danger fw-bold mb-2" style="font-size: 0.75rem; letter-spacing: 0.08em;">🔴 Risk Signals</h6>
                                    <div id="res-risk"></div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Tab 2: Live Pipeline Batch -->
        <div class="tab-pane fade" id="batch" role="tabpanel">
            <div class="card-surface mb-4">
                <div class="d-flex justify-content-between align-items-center mb-3">
                    <div>
                        <h4 class="fw-bold mb-1"><i class="bi bi-layers-fill me-2 text-primary"></i>Lead Pipeline Workspace</h4>
                        <p class="text-secondary mb-0" style="font-size: 0.9rem;">Analyze, rank, and prioritize every lead in your sales pipeline.</p>
                    </div>
                </div>
                
                <div class="d-flex flex-wrap gap-2 mb-4">
                    <button class="btn btn-gradient-success px-4 py-2.5" id="rank-all-pipeline-btn">
                        <i class="bi bi-play-circle-fill me-1"></i> Rank All Live Leads in Pipeline
                    </button>
                    <button class="btn btn-outline-info px-4 py-2.5 rounded-3" id="run-default-batch-btn" style="font-weight: 600;">
                        <i class="bi bi-plus-circle me-1"></i> Append Sample Dataset (10 Leads)
                    </button>
                    <button class="btn btn-glass-danger px-4 py-2.5 ms-auto" onclick="clearAllLeads()">
                        <i class="bi bi-trash3 me-1"></i> Clear Pipeline
                    </button>
                </div>

                <div class="dropzone-card">
                    <i class="bi bi-cloud-arrow-up display-5 text-info d-block mb-2"></i>
                    <h6 class="fw-bold mb-1 text-white">Drop your JSON or CSV file here</h6>
                    <p class="text-secondary small mb-3">or browse from your local computer</p>
                    <div class="d-flex justify-content-center align-items-center gap-2 max-w-md mx-auto">
                        <input type="file" id="batch-file-input" class="form-control-custom" accept=".json,.csv" style="max-width: 320px;">
                        <button class="btn btn-gradient-primary px-3 py-2" id="upload-batch-btn">Process Upload</button>
                    </div>
                </div>
            </div>

            <div id="batch-spinner" class="spinner-overlay">
                <div class="spinner-border" role="status"></div>
                <p>Evaluating Fit & Intent Engine across pipeline...</p>
            </div>

            <div class="card-surface p-0 overflow-hidden" id="batch-results-card" style="display: none;">
                <div class="p-3 border-bottom border-secondary border-opacity-25 d-flex justify-content-between align-items-center">
                    <h5 class="fw-bold mb-0 ms-2">Ranked Lead Queue</h5>
                </div>
                <div class="table-responsive">
                    <table class="table table-custom align-middle" id="batch-table">
                        <thead>
                            <tr>
                                <th>Rank</th>
                                <th>Lead & Role</th>
                                <th>Company</th>
                                <th>Tier</th>
                                <th>Overall</th>
                                <th>Fit</th>
                                <th>Intent</th>
                                <th>Recommended Action</th>
                                <th>Action</th>
                            </tr>
                        </thead>
                        <tbody></tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- Tab 3: Leaderboard -->
        <div class="tab-pane fade" id="leaderboard" role="tabpanel">
            <!-- Podium View for Top 3 Leads -->
            <div class="podium-container" id="podium-section" style="display: none;">
                <!-- 2nd Place -->
                <div class="podium-card" id="podium-2">
                    <div class="podium-crown text-secondary"><i class="bi bi-award-fill"></i></div>
                    <span class="badge bg-secondary mb-2">SILVER #2</span>
                    <h5 class="fw-bold mb-1 text-white" id="podium-2-name">-</h5>
                    <div class="text-secondary small mb-2" id="podium-2-company">-</div>
                    <div class="fw-extrabold fs-4 text-warning" id="podium-2-score">-</div>
                </div>

                <!-- 1st Place -->
                <div class="podium-card podium-card-1" id="podium-1">
                    <div class="podium-crown text-warning"><i class="bi bi-trophy-fill"></i></div>
                    <span class="badge bg-warning text-dark mb-2 font-weight-700">GOLD #1</span>
                    <h4 class="fw-bold mb-1 text-white" id="podium-1-name">-</h4>
                    <div class="text-secondary small mb-2" id="podium-1-company">-</div>
                    <div class="fw-extrabold fs-3 text-info" id="podium-1-score">-</div>
                </div>

                <!-- 3rd Place -->
                <div class="podium-card" id="podium-3">
                    <div class="podium-crown text-danger"><i class="bi bi-award-fill"></i></div>
                    <span class="badge bg-danger-subtle text-danger mb-2">BRONZE #3</span>
                    <h5 class="fw-bold mb-1 text-white" id="podium-3-name">-</h5>
                    <div class="text-secondary small mb-2" id="podium-3-company">-</div>
                    <div class="fw-extrabold fs-4 text-warning" id="podium-3-score">-</div>
                </div>
            </div>

            <div class="card-surface p-0 overflow-hidden">
                <div class="p-3 border-bottom border-secondary border-opacity-25 d-flex justify-content-between align-items-center">
                    <h5 class="fw-bold mb-0 ms-2">🏆 Pipeline Leaderboard (Stored in SQLite)</h5>
                    <div class="d-flex gap-2">
                        <button class="btn btn-sm btn-outline-light rounded-2" onclick="loadLeaderboard()">🔄 Refresh</button>
                        <button class="btn btn-glass-danger btn-sm" onclick="clearAllLeads()">🗑️ Clear All</button>
                    </div>
                </div>
                <div class="table-responsive">
                    <table class="table table-custom align-middle" id="leaderboard-table">
                        <thead>
                            <tr>
                                <th>Rank</th>
                                <th>Lead & Role</th>
                                <th>Company</th>
                                <th>Tier</th>
                                <th>Overall</th>
                                <th>Fit</th>
                                <th>Intent</th>
                                <th>Live LLM Summary</th>
                                <th>Action</th>
                            </tr>
                        </thead>
                        <tbody></tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>
</div>

<!-- Toast Container -->
<div class="toast-container-custom" id="toast-container"></div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
<script>
    function showToast(message, isError = false) {
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = 'toast-custom';
        if (isError) toast.style.borderColor = '#EF4444';
        toast.innerHTML = (isError ? '<i class="bi bi-exclamation-triangle-fill text-danger"></i>' : '<i class="bi bi-check-circle-fill text-success"></i>') + `<span>${message}</span>`;
        container.appendChild(toast);
        setTimeout(() => { toast.remove(); }, 3500);
    }

    document.getElementById('lead-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        document.getElementById('result-placeholder').style.display = 'none';
        document.getElementById('result-content').style.display = 'none';
        document.getElementById('single-spinner').style.display = 'block';

        const payload = {
            name: document.getElementById('name').value,
            company: document.getElementById('company').value,
            job_title: document.getElementById('job_title').value,
            industry: document.getElementById('industry').value,
            company_size: parseInt(document.getElementById('company_size').value) || 0,
            budget: document.getElementById('budget').value,
            timeline: document.getElementById('timeline').value,
            interest: document.getElementById('interest').value,
            notes: document.getElementById('notes').value
        };

        try {
            const res = await fetch('/qualify', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            document.getElementById('single-spinner').style.display = 'none';
            renderResult(data);
            showToast(`Lead '${data.name}' qualified successfully as ${data.tier}!`);
            loadLeaderboard();
        } catch (err) {
            document.getElementById('single-spinner').style.display = 'none';
            showToast('Error qualifying lead: ' + err, true);
        }
    });

    function renderResult(data) {
        document.getElementById('result-content').style.display = 'block';
        document.getElementById('res-rank').innerText = '#' + (data.rank || 1);
        document.getElementById('res-name').innerText = data.name || 'Lead';
        document.getElementById('res-company').innerText = (data.company || 'Unknown') + ' • ' + (data.job_title || '');
        document.getElementById('res-overall').innerText = data.overall_score;
        document.getElementById('res-fit').innerText = data.fit_score;
        document.getElementById('res-intent').innerText = data.intent_score;
        
        document.getElementById('bar-fit').style.width = (data.fit_score || 0) + '%';
        document.getElementById('bar-intent').style.width = (data.intent_score || 0) + '%';

        document.getElementById('res-summary').innerText = data.summary;
        document.getElementById('res-action').innerText = data.recommended_action;

        const tierElem = document.getElementById('res-tier');
        tierElem.innerText = data.tier === 'HOT' ? '🔥 HOT' : (data.tier === 'WARM' ? '⚡ WARM' : '❄️ COLD');
        tierElem.className = data.tier === 'HOT' ? 'tier-badge-hot' : (data.tier === 'WARM' ? 'tier-badge-warm' : 'tier-badge-cold');

        const bList = document.getElementById('res-buying');
        bList.innerHTML = (data.buying_signals || []).map(s => `<div class="signal-pill-buy"><i class="bi bi-check-circle-fill"></i> ${s}</div>`).join('') || '<div class="text-muted small">✓ No special signals</div>';

        const rList = document.getElementById('res-risk');
        rList.innerHTML = (data.risk_signals || []).map(s => `<div class="signal-pill-risk"><i class="bi bi-exclamation-triangle-fill"></i> ${s}</div>`).join('') || '<div class="text-muted small">✓ No major risk signals detected</div>';
    }

    // Rank All Live Leads in Pipeline
    document.getElementById('rank-all-pipeline-btn').addEventListener('click', async () => {
        document.getElementById('batch-spinner').style.display = 'block';
        document.getElementById('batch-results-card').style.display = 'none';

        try {
            const res = await fetch('/leads/re-rank', { method: 'POST' });
            const data = await res.json();
            renderBatchResults(data);
            showToast('All pipeline leads re-ranked successfully!');
        } catch (err) {
            document.getElementById('batch-spinner').style.display = 'none';
            showToast('Error reranking pipeline: ' + err, true);
        }
    });

    // Live Dataset Batch Process
    document.getElementById('run-default-batch-btn').addEventListener('click', async () => {
        document.getElementById('batch-spinner').style.display = 'block';
        document.getElementById('batch-results-card').style.display = 'none';

        try {
            const sampleRes = await fetch('/sample-leads');
            const sampleLeads = await sampleRes.json();
            await processBatch(sampleLeads);
            showToast('Sample dataset appended and ranked!');
        } catch (err) {
            document.getElementById('batch-spinner').style.display = 'none';
            showToast('Error running batch: ' + err, true);
        }
    });

    // File Upload Batch Process
    document.getElementById('upload-batch-btn').addEventListener('click', async () => {
        const fileInput = document.getElementById('batch-file-input');
        if (!fileInput.files || fileInput.files.length === 0) {
            showToast('Please select a JSON or CSV file first.', true);
            return;
        }

        const file = fileInput.files[0];
        const reader = new FileReader();

        reader.onload = async (e) => {
            document.getElementById('batch-spinner').style.display = 'block';
            document.getElementById('batch-results-card').style.display = 'none';

            try {
                let leads = [];
                if (file.name.endsWith('.json')) {
                    const parsed = JSON.parse(e.target.result);
                    leads = Array.isArray(parsed) ? parsed : (parsed.leads || []);
                } else if (file.name.endsWith('.csv')) {
                    leads = parseCSV(e.target.result);
                }

                await processBatch(leads);
                showToast(`Processed '${file.name}' successfully!`);
            } catch (err) {
                document.getElementById('batch-spinner').style.display = 'none';
                showToast('Error parsing uploaded file: ' + err, true);
            }
        };

        reader.readAsText(file);
    });

    async function processBatch(leadsPayload) {
        const res = await fetch('/qualify/batch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(leadsPayload)
        });
        const data = await res.json();
        renderBatchResults(data);
    }

    function renderBatchResults(data) {
        document.getElementById('batch-spinner').style.display = 'none';

        document.getElementById('metric-total').innerText = data.total_leads;
        document.getElementById('metric-hot').innerText = data.hot;
        document.getElementById('metric-warm').innerText = data.warm;
        document.getElementById('metric-cold').innerText = data.cold;

        const tbody = document.querySelector('#batch-table tbody');
        tbody.innerHTML = (data.leads || []).map(l => `
            <tr>
                <td class="fw-bold text-warning">#${l.rank || 1}</td>
                <td>
                    <div class="fw-bold text-white">${l.name}</div>
                    <div class="text-secondary small" style="font-size: 0.8rem;">${l.job_title || '-'}</div>
                </td>
                <td class="text-secondary">${l.company || '-'}</td>
                <td><span class="${l.tier === 'HOT' ? 'tier-badge-hot' : (l.tier === 'WARM' ? 'tier-badge-warm' : 'tier-badge-cold')}">${l.tier === 'HOT' ? '🔥 HOT' : (l.tier === 'WARM' ? '⚡ WARM' : '❄️ COLD')}</span></td>
                <td class="fw-extrabold text-info fs-6">${l.overall_score}</td>
                <td>${l.fit_score}</td>
                <td>${l.intent_score}</td>
                <td class="small text-light" style="max-width: 280px;">${l.recommended_action || '-'}</td>
                <td>
                    <button class="btn btn-sm btn-glass-danger" onclick="deleteLead('${l.lead_id}')"><i class="bi bi-trash3"></i></button>
                </td>
            </tr>
        `).join('');

        document.getElementById('batch-results-card').style.display = 'block';
        loadLeaderboard();
    }

    function parseCSV(text) {
        const lines = text.split('\\n').filter(l => l.trim());
        if (lines.length < 2) return [];
        const headers = lines[0].split(',').map(h => h.trim().replace(/^"|"$/g, ''));
        const result = [];
        for (let i = 1; i < lines.length; i++) {
            const currentline = lines[i].split(',').map(v => v.trim().replace(/^"|"$/g, ''));
            const obj = {};
            for (let j = 0; j < headers.length; j++) {
                obj[headers[j]] = currentline[j] || null;
            }
            result.push(obj);
        }
        return result;
    }

    async function loadLeaderboard() {
        const res = await fetch('/leads');
        const data = await res.json();
        const leads = data.leads || [];

        const hot = leads.filter(l => l.tier === 'HOT').length;
        const warm = leads.filter(l => l.tier === 'WARM').length;
        const cold = leads.filter(l => l.tier === 'COLD').length;
        document.getElementById('metric-total').innerText = leads.length;
        document.getElementById('metric-hot').innerText = hot;
        document.getElementById('metric-warm').innerText = warm;
        document.getElementById('metric-cold').innerText = cold;

        // Render Podium if at least 3 leads
        if (leads.length >= 3) {
            document.getElementById('podium-section').style.display = 'flex';
            document.getElementById('podium-1-name').innerText = leads[0].name;
            document.getElementById('podium-1-company').innerText = leads[0].company || 'Unknown';
            document.getElementById('podium-1-score').innerText = leads[0].overall_score + ' pts';

            document.getElementById('podium-2-name').innerText = leads[1].name;
            document.getElementById('podium-2-company').innerText = leads[1].company || 'Unknown';
            document.getElementById('podium-2-score').innerText = leads[1].overall_score + ' pts';

            document.getElementById('podium-3-name').innerText = leads[2].name;
            document.getElementById('podium-3-company').innerText = leads[2].company || 'Unknown';
            document.getElementById('podium-3-score').innerText = leads[2].overall_score + ' pts';
        } else {
            document.getElementById('podium-section').style.display = 'none';
        }

        const tbody = document.querySelector('#leaderboard-table tbody');
        if (leads.length === 0) {
            tbody.innerHTML = '<tr><td colspan="9" class="text-center text-secondary py-5"><i class="bi bi-inbox display-6 d-block mb-2 text-info"></i>No leads in pipeline. Qualify a lead or run a batch to get started.</td></tr>';
            return;
        }

        tbody.innerHTML = leads.map(l => `
            <tr>
                <td class="fw-bold text-warning">#${l.rank || '-'}</td>
                <td>
                    <div class="fw-bold text-white">${l.name}</div>
                    <div class="text-secondary small" style="font-size: 0.8rem;">${l.job_title || '-'}</div>
                </td>
                <td class="text-secondary">${l.company || '-'}</td>
                <td><span class="${l.tier === 'HOT' ? 'tier-badge-hot' : (l.tier === 'WARM' ? 'tier-badge-warm' : 'tier-badge-cold')}">${l.tier === 'HOT' ? '🔥 HOT' : (l.tier === 'WARM' ? '⚡ WARM' : '❄️ COLD')}</span></td>
                <td class="fw-extrabold text-info fs-6">${l.overall_score}</td>
                <td>${l.fit_score}</td>
                <td>${l.intent_score}</td>
                <td class="small text-light" style="max-width: 300px;">${l.summary || '-'}</td>
                <td>
                    <button class="btn btn-sm btn-glass-danger" onclick="deleteLead('${l.lead_id}')"><i class="bi bi-trash3"></i></button>
                </td>
            </tr>
        `).join('');
    }

    async function deleteLead(leadId) {
        if (!confirm('Are you sure you want to delete this lead?')) return;
        try {
            const res = await fetch('/leads/' + encodeURIComponent(leadId), { method: 'DELETE' });
            if (res.ok) {
                loadLeaderboard();
                showToast('Lead deleted successfully.');
            } else {
                showToast('Failed to delete lead.', true);
            }
        } catch (err) {
            showToast('Error deleting lead: ' + err, true);
        }
    }

    async function clearAllLeads() {
        if (!confirm('Are you sure you want to clear ALL leads from the leaderboard?')) return;
        try {
            const res = await fetch('/leads', { method: 'DELETE' });
            if (res.ok) {
                loadLeaderboard();
                document.getElementById('batch-results-card').style.display = 'none';
                showToast('All pipeline leads cleared successfully.');
            } else {
                showToast('Failed to clear leads.', true);
            }
        } catch (err) {
            showToast('Error clearing leads: ' + err, true);
        }
    }

    loadLeaderboard();
</script>
</body>
</html>"""
    return HTMLResponse(content=html_content)

@app.post("/qualify", response_model=QualifiedLead, status_code=status.HTTP_200_OK)
def qualify_single_lead(lead_input: LeadInput):
    """
    Qualify a single inbound lead.
    Accepts lead details, email text, or notes, computes deterministic scores,
    and returns structured qualification rationale and recommended next action.
    """
    try:
        result = agent.qualify_lead(lead_input)
        return result
    except Exception as e:
        logger.error(f"Error qualifying single lead: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to qualify lead: {str(e)}"
        )

@app.post("/qualify/batch", response_model=BatchQualificationResponse, status_code=status.HTTP_200_OK)
def qualify_batch_leads(payload: Union[List[LeadInput], Dict[str, Any]] = Body(...)):
    """
    Qualify a batch of inbound leads, rank them deterministically, and return prioritized sales insights.
    """
    try:
        leads_list = []
        if isinstance(payload, list):
            leads_list = payload
        elif isinstance(payload, dict):
            leads_list = payload.get("leads", [])
            if not leads_list and "lead_id" in payload:
                leads_list = [payload]
        
        if not leads_list:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Batch payload must be a list of leads or a JSON object containing a 'leads' array."
            )

        result = agent.qualify_batch(leads_list)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error qualifying batch leads: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process lead batch: {str(e)}"
        )

@app.get("/leads", status_code=status.HTTP_200_OK)
def get_all_stored_leads():
    """Returns all stored lead qualifications from SQLite database re-ranked dynamically."""
    try:
        leads = rerank_all_database_leads()
        return {"total": len(leads), "leads": leads}
    except Exception as e:
        logger.error(f"Error fetching leads: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve leads: {str(e)}"
        )

@app.post("/leads/re-rank", status_code=status.HTTP_200_OK)
def rerank_stored_leads():
    """Re-ranks all leads stored in SQLite database and returns prioritized results."""
    try:
        ranked_leads = rerank_all_database_leads()
        hot_count = sum(1 for lead in ranked_leads if lead.get("tier") == "HOT")
        warm_count = sum(1 for lead in ranked_leads if lead.get("tier") == "WARM")
        cold_count = sum(1 for lead in ranked_leads if lead.get("tier") == "COLD")
        return {
            "total_leads": len(ranked_leads),
            "hot": hot_count,
            "warm": warm_count,
            "cold": cold_count,
            "leads": ranked_leads
        }
    except Exception as e:
        logger.error(f"Error reranking leads: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to rerank leads: {str(e)}"
        )

@app.delete("/leads/{lead_id}", status_code=status.HTTP_200_OK)
def delete_single_lead(lead_id: str):
    """Deletes a specific lead by ID from SQLite database."""
    try:
        success = delete_qualified_lead_by_id(lead_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Lead with ID '{lead_id}' not found."
            )
        return {"status": "ok", "message": f"Lead {lead_id} deleted successfully."}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting lead {lead_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete lead: {str(e)}"
        )

@app.delete("/leads", status_code=status.HTTP_200_OK)
def delete_all_leads():
    """Clears all leads from SQLite database."""
    try:
        count = delete_all_qualified_leads()
        return {"status": "ok", "message": f"Cleared {count} leads from pipeline."}
    except Exception as e:
        logger.error(f"Error clearing leads: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear leads: {str(e)}"
        )

@app.get("/leads/{lead_id}", status_code=status.HTTP_200_OK)
def get_lead_by_id(lead_id: str):
    """Retrieves a specific qualification record by lead_id."""
    try:
        lead = fetch_qualified_lead_by_id(lead_id)
        if not lead:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Lead with ID '{lead_id}' not found."
            )
        return lead
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching lead {lead_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve lead: {str(e)}"
        )

@app.exception_handler(Exception)
def generic_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred.", "error": str(exc)}
    )

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
