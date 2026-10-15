from __future__ import annotations

import argparse
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.externship_models import Lead
from src.externship_seed_data import STARTER_LEADS
from src.externship_io import ensure_dirs, load_leads_csv, merge_leads, save_leads_csv, save_leads_json
from src.externship_contact_finder import enrich_leads, score_lead
from src.externship_email_writer import write_draft_files
from src.externship_call_scripts import write_call_script
from src.externship_report import write_report
from src.externship_tracker import initialize_tracker, print_followups_due

DATA_DIR = ROOT / "data"
LEADS_CSV = DATA_DIR / "externship_leads.csv"
LEADS_JSON = DATA_DIR / "externship_leads.json"
TRACKER_CSV = DATA_DIR / "externship_tracker.csv"
REPORT_HTML = DATA_DIR / "externship_review.html"
REPORT_JSON = DATA_DIR / "externship_review.json"
DRAFTS_DIR = ROOT / "drafts" / "externship"


def seed_leads() -> list[Lead]:
    return [Lead.from_dict(item) for item in STARTER_LEADS]


def cmd_init(args) -> None:
    ensure_dirs(ROOT)
    existing = load_leads_csv(LEADS_CSV)
    merged = merge_leads(existing, seed_leads())
    save_leads_csv(LEADS_CSV, merged)
    save_leads_json(LEADS_JSON, merged)
    initialize_tracker(TRACKER_CSV, merged)
    print(f"Initialized externship outreach data with {len(merged)} leads.")
    print(f"Lead CSV: {LEADS_CSV}")
    print(f"Tracker:  {TRACKER_CSV}")


def cmd_add_lead(args) -> None:
    ensure_dirs(ROOT)
    leads = load_leads_csv(LEADS_CSV)
    lead = Lead(
        clinic_name=args.name,
        specialty=args.specialty or "",
        city=args.city or "",
        website=args.website or "",
        contact_page=args.contact_page or "",
        main_phone=args.phone or "",
        contact_name=args.contact_name or "",
        contact_title=args.contact_title or "",
        contact_email=args.email or "",
        source_note="manually added",
        priority=args.priority or "medium",
        tags=args.tags or "manual",
    )
    merged = merge_leads(leads, [lead])
    save_leads_csv(LEADS_CSV, merged)
    save_leads_json(LEADS_JSON, merged)
    print(f"Added/merged lead: {args.name}")


def load_or_seed() -> list[Lead]:
    ensure_dirs(ROOT)
    leads = load_leads_csv(LEADS_CSV)
    if not leads:
        leads = seed_leads()
        save_leads_csv(LEADS_CSV, leads)
        save_leads_json(LEADS_JSON, leads)
    return leads


def cmd_enrich(args) -> None:
    leads = load_or_seed()
    leads = enrich_leads(leads, max_leads=args.max_leads)
    save_leads_csv(LEADS_CSV, leads)
    save_leads_json(LEADS_JSON, leads)
    print(f"Enriched {len(leads)} leads.")


def cmd_drafts(args) -> None:
    leads = load_or_seed()
    if args.top:
        leads = sorted(leads, key=score_lead, reverse=True)[:args.top]
    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    for lead in leads:
        paths = write_draft_files(lead, DRAFTS_DIR)
        script_path = write_call_script(lead, DRAFTS_DIR)
        print(f"Drafted {lead.clinic_name}: {paths['email_txt'].name}, {script_path.name}")
    print(f"Drafts folder: {DRAFTS_DIR}")


def cmd_report(args) -> None:
    leads = load_or_seed()
    write_report(leads, REPORT_HTML, REPORT_JSON)
    initialize_tracker(TRACKER_CSV, leads)
    print(f"Report: {REPORT_HTML}")
    print(f"JSON:   {REPORT_JSON}")
    if args.open:
        webbrowser.open(REPORT_HTML.resolve().as_uri())


def cmd_run(args) -> None:
    cmd_init(args)
    if not args.skip_enrich:
        cmd_enrich(args)
    cmd_drafts(args)
    cmd_report(args)
    print("\nPipeline complete. Review drafts before sending anything.")


def cmd_followups(args) -> None:
    print_followups_due(TRACKER_CSV)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Medical externship outreach CRM for Sample Applicant. Drafts only; no auto-send.")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("init", help="Create seed lead CSV/tracker.")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("add-lead", help="Add one manual lead.")
    p.add_argument("--name", required=True)
    p.add_argument("--specialty", default="")
    p.add_argument("--city", default="")
    p.add_argument("--website", default="")
    p.add_argument("--contact-page", default="")
    p.add_argument("--phone", default="")
    p.add_argument("--email", default="")
    p.add_argument("--contact-name", default="")
    p.add_argument("--contact-title", default="")
    p.add_argument("--priority", default="medium")
    p.add_argument("--tags", default="manual")
    p.set_defaults(func=cmd_add_lead)

    p = sub.add_parser("enrich", help="Visit public clinic pages and extract public emails/phones/contact links.")
    p.add_argument("--max-leads", type=int, default=None)
    p.set_defaults(func=cmd_enrich)

    p = sub.add_parser("drafts", help="Generate email drafts and call scripts.")
    p.add_argument("--top", type=int, default=None)
    p.set_defaults(func=cmd_drafts)

    p = sub.add_parser("report", help="Generate HTML review dashboard.")
    p.add_argument("--open", action="store_true")
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("run", help="Run seed + enrich + drafts + report.")
    p.add_argument("--skip-enrich", action="store_true")
    p.add_argument("--max-leads", type=int, default=None)
    p.add_argument("--top", type=int, default=None)
    p.add_argument("--open", action="store_true")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("followups", help="Print follow-ups due from tracker CSV.")
    p.set_defaults(func=cmd_followups)

    parser.set_defaults(func=cmd_run, skip_enrich=False, max_leads=None, top=None, open=True)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
