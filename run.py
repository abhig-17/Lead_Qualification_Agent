import os
import sys
import json
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Load env variables
load_dotenv()

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from app.agent import LeadQualificationAgent
from app.utils import load_leads_from_json, load_leads_from_csv

def main():
    parser = argparse.ArgumentParser(description="Lead Qualification Agent CLI")
    parser.add_argument("--file", type=str, default="data/sample_leads.json", help="Path to input JSON or CSV file")
    parser.add_argument("--output", type=str, default="outputs/sample_output.json", help="Path to save output JSON")
    args = parser.parse_args()

    input_path = Path(args.file)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        print(f"Error: Input file '{input_path}' does not exist.")
        sys.exit(1)

    print("\n========================================")
    print("LEAD QUALIFICATION AGENT")
    print("========================================")
    print(f"Loading leads from: {input_path}")

    # Load data
    if input_path.suffix.lower() == ".csv":
        raw_leads = load_leads_from_csv(str(input_path))
    else:
        raw_leads = load_leads_from_json(str(input_path))

    agent = LeadQualificationAgent()
    response = agent.qualify_batch(raw_leads)

    print(f"\nProcessed: {response.total_leads} leads")
    print(f"HOT:  {response.hot}")
    print(f"WARM: {response.warm}")
    print(f"COLD: {response.cold}")
    print("\n----------------------------------------")
    print("## RANKED LEADS")
    print("----------------------------------------")

    for lead in response.leads:
        print(f"\n#{lead.rank} {lead.name} ({lead.company or 'N/A'})")
        print(f"Score: {lead.overall_score} | Tier: {lead.tier} | Fit: {lead.fit_score} | Intent: {lead.intent_score}")
        print(f"Summary: {lead.summary}")
        print(f"Action: {lead.recommended_action}")

    # Save to output file
    output_data = response.model_dump()
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)

    print("\n========================================")
    print(f"SUCCESS: Saved ranked output to {output_path}")
    print("========================================\n")

if __name__ == "__main__":
    main()
