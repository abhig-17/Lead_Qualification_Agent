import json
import pandas as pd
from typing import List, Dict, Any

def load_leads_from_json(filepath: str) -> List[Dict[str, Any]]:
    """Loads lead data from a JSON file."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
        if isinstance(data, list):
            return data
        elif isinstance(data, dict) and "leads" in data:
            return data["leads"]
        else:
            return [data]

def load_leads_from_csv(filepath: str) -> List[Dict[str, Any]]:
    """Loads lead data from a CSV file using Pandas with clean column parsing."""
    df = pd.read_csv(filepath)
    # Fill NaN values with None or empty string
    df = df.where(pd.notnull(df), None)
    records = df.to_dict(orient="records")
    
    cleaned = []
    for row in records:
        clean_row = {}
        for k, v in row.items():
            if pd.isna(v) or v is None:
                continue
            # Convert numeric types if string
            if k == "company_size" and isinstance(v, float):
                v = int(v)
            clean_row[k] = v
        cleaned.append(clean_row)
    return cleaned

def format_cli_lead_card(lead: Dict[str, Any]) -> str:
    """Formats a single qualified lead for terminal output."""
    rank = lead.get("rank", "-")
    name = lead.get("name", "Unknown")
    company = lead.get("company", "Unknown")
    tier = lead.get("tier", "COLD")
    overall = lead.get("overall_score", 0)
    fit = lead.get("fit_score", 0)
    intent = lead.get("intent_score", 0)
    action = lead.get("recommended_action", "N/A")
    summary = lead.get("summary", "N/A")

    tier_color = {
        "HOT": "\033[91m[HOT]\033[0m",
        "WARM": "\033[93m[WARM]\033[0m",
        "COLD": "\033[94m[COLD]\033[0m"
    }.get(tier, f"[{tier}]")

    output = f"""
#{rank} {name} ({company})
Status: {tier_color} | Overall Score: {overall}/100 (Fit: {fit}, Intent: {intent})
Summary: {summary}
Recommended Action: {action}
--------------------------------------------------------------------------------"""
    return output
