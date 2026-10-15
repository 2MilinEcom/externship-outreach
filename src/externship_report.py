from __future__ import annotations

import html
import json
from pathlib import Path
from urllib.parse import quote

from src.externship_models import Lead
from src.externship_email_writer import choose_recipient, subject_for_lead, body_for_lead
from src.externship_contact_finder import score_lead
from src.externship_profile import SAMPLE_PROFILE


def mailto_for(lead: Lead) -> str:
    to = choose_recipient(lead)
    subject = subject_for_lead(lead)
    body = body_for_lead(lead)
    return f"mailto:{quote(to)}?subject={quote(subject)}&body={quote(body)}"


def lead_row(lead: Lead, index: int) -> str:
    recipient = choose_recipient(lead) or ""
    phone = lead.main_phone or (lead.phones_found[0] if lead.phones_found else "")
    score = score_lead(lead)
    priority = html.escape(lead.priority or "")
    tags = html.escape(lead.tags or "")
    source = html.escape(lead.source_url or "")
    source_link = f'<a href="{source}" target="_blank">source</a>' if source else ""
    website = html.escape(lead.website or lead.contact_page or "")
    site_link = f'<a href="{website}" target="_blank">website</a>' if website else ""
    email_link = f'<a href="{mailto_for(lead)}">draft email</a>' if recipient else "find email / use contact form"
    call = f'<a href="tel:{html.escape(phone)}">{html.escape(phone)}</a>' if phone else ""
    notes = html.escape(lead.source_note or lead.notes or "")
    return f"""
    <tr>
      <td>{index}</td>
      <td><b>{html.escape(lead.clinic_name)}</b><br><span class="muted">{html.escape(lead.specialty)}</span></td>
      <td>{html.escape(lead.city)}<br><span class="muted">{html.escape(lead.address)}</span></td>
      <td>{html.escape(lead.contact_name)}<br><span class="muted">{html.escape(lead.contact_title)}</span></td>
      <td>{html.escape(recipient)}<br>{email_link}</td>
      <td>{call}</td>
      <td>{site_link}<br>{source_link}</td>
      <td>{score}<br><span class="badge">{priority}</span><br><span class="muted">{tags}</span></td>
      <td>{notes}</td>
      <td><input type="checkbox"> emailed<br><input type="checkbox"> called<br><input type="checkbox"> follow-up</td>
    </tr>
    """


def write_report(leads: list[Lead], report_path: Path, json_path: Path) -> None:
    leads_sorted = sorted(leads, key=score_lead, reverse=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps([lead.to_dict() for lead in leads_sorted], indent=2, ensure_ascii=False), encoding="utf-8")
    rows = "\n".join(lead_row(lead, i) for i, lead in enumerate(leads_sorted, 1))
    p = SAMPLE_PROFILE
    report_path.write_text(f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Sample Externship Outreach Dashboard</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif; margin: 24px; color: #1f2937; }}
h1 {{ margin-bottom: 0; }}
.summary {{ background: #f3f4f6; border-radius: 12px; padding: 16px; margin: 16px 0 24px; }}
table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
th, td {{ border: 1px solid #e5e7eb; padding: 8px; vertical-align: top; }}
th {{ background: #111827; color: white; position: sticky; top: 0; }}
tr:nth-child(even) {{ background: #fafafa; }}
.badge {{ display: inline-block; background: #dbeafe; padding: 2px 6px; border-radius: 6px; }}
.muted {{ color: #6b7280; font-size: 12px; }}
a {{ color: #2563eb; }}
</style>
</head>
<body>
<h1>Sample Externship Outreach Dashboard</h1>
<div class="summary">
  <b>Candidate:</b> {html.escape(p['full_name'])}<br>
  <b>Email:</b> {html.escape(p['email'])}<br>
  <b>Phone:</b> {html.escape(p['phone'])}<br>
  <b>Base:</b> {html.escape(p['base_location'])}; {html.escape(p['commute_limit'])}<br>
  <b>Goal:</b> {html.escape(p['target_externship'])}<br>
  <b>Rules:</b> drafts only; do not auto-send; use public work contacts only; call scripts for manual calling.
</div>
<h2>Leads</h2>
<table>
<thead><tr><th>#</th><th>Clinic</th><th>Location</th><th>Contact</th><th>Email / Draft</th><th>Phone</th><th>Links</th><th>Score</th><th>Notes</th><th>Manual Log</th></tr></thead>
<tbody>
{rows}
</tbody>
</table>
</body>
</html>""", encoding="utf-8")
