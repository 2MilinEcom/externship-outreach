from __future__ import annotations

import re
from email.message import EmailMessage
from pathlib import Path

from src.externship_models import Lead
from src.externship_profile import SAMPLE_PROFILE


def clean_filename(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value or "lead").strip("_")
    return value[:100] or "lead"


def choose_recipient(lead: Lead) -> str:
    if lead.contact_email:
        return lead.contact_email
    if lead.emails_found:
        return lead.emails_found[0]
    return ""


def subject_for_lead(lead: Lead) -> str:
    if "externship" in (lead.specialty + " " + lead.tags).lower():
        return "Medical externship inquiry"
    return "Clinic externship / medical assistant opportunity inquiry"


def greeting_for_lead(lead: Lead) -> str:
    if lead.contact_name:
        first = lead.contact_name.split()[0]
        return f"Hi {first},"
    if lead.contact_title:
        return f"Hello {lead.contact_title},"
    return "Hello,"


def body_for_lead(lead: Lead, *, followup: bool = False) -> str:
    p = SAMPLE_PROFILE
    name = p["full_name"]
    email = p["email"]
    phone = p["phone"]
    location = p["base_location"]
    commute = p["commute_limit"]

    externship_type = p["target_externship"]
    availability = p["availability"]
    credentials = []
    for label, key in [
        ("CPR", "cpr"),
        ("HIPAA training", "hipaa"),
        ("immunization/TB documentation", "immunizations_tb"),
        ("background check/drug screen readiness", "background_drug_screen"),
    ]:
        if str(p.get(key, "")).lower().startswith("yes"):
            credentials.append(label)
    cred_text = ", ".join(credentials) if credentials else "standard onboarding documents as requested"

    if followup:
        return f"""{greeting_for_lead(lead)}

I wanted to follow up on my note about an externship or entry-level clinic opportunity for {name}. She is based in {location}, can commute {commute.lower()}, and is trying to get hands-on experience in a clinical setting as soon as possible.

She can provide her resume and documentation for {cred_text}. If your clinic is not the right contact, would you be willing to point us to the office manager, practice manager, externship coordinator, or clinical supervisor who handles student placements?

Thank you,
{name}
{email}
{phone}
""".strip()

    custom = ""
    hay = f"{lead.clinic_name} {lead.specialty} {lead.tags} {lead.source_note}".lower()
    if "community health" in hay:
        custom = " I am especially interested in community health clinics because they offer meaningful patient-facing experience and exposure to real clinical workflows."
    elif "urgent" in hay:
        custom = " I am especially interested in urgent care because it offers fast-paced exposure to patient intake, vitals, rooming, and front/back-office clinic workflows."
    elif "free clinic" in hay or "volunteer" in hay:
        custom = " I am also open to volunteer-based clinical experience if that is the best path to prove reliability and learn the clinic workflow."

    return f"""{greeting_for_lead(lead)}

My name is {name}, and I am reaching out to ask whether {lead.clinic_name or 'your clinic'} would be open to hosting a medical extern or considering an entry-level clinic assistant / medical assistant opportunity.

I am based in {location}, have access to a car, and can commute {commute.lower()}. I am flexible on schedule and start date right now, and my main goal is to get into a clinical environment where I can learn, contribute, and build experience.{custom}

I can provide my resume and supporting documents, including {cred_text}. If your clinic works with students or externs, I would be grateful for the chance to speak with the office manager, practice manager, clinical supervisor, or whoever coordinates externships.

Would your team be open to a quick call, or is there a better person I should contact?

Thank you,
{name}
{email}
{phone}
""".strip()


def write_draft_files(lead: Lead, out_dir: Path) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = clean_filename(f"{lead.clinic_name}_{lead.city}")
    recipient = choose_recipient(lead)
    subject = subject_for_lead(lead)
    body = body_for_lead(lead)
    followup_body = body_for_lead(lead, followup=True)

    txt_path = out_dir / f"{stem}_email.txt"
    txt_path.write_text(
        f"TO: {recipient or '[find public contact email or use contact form]'}\n"
        f"SUBJECT: {subject}\n\n"
        f"{body}\n",
        encoding="utf-8",
    )

    followup_path = out_dir / f"{stem}_followup.txt"
    followup_path.write_text(
        f"TO: {recipient or '[same as first email]'}\n"
        f"SUBJECT: Re: {subject}\n\n"
        f"{followup_body}\n",
        encoding="utf-8",
    )

    eml = EmailMessage()
    eml["To"] = recipient or ""
    eml["From"] = SAMPLE_PROFILE["email"]
    eml["Subject"] = subject
    eml.set_content(body)
    eml_path = out_dir / f"{stem}.eml"
    eml_path.write_text(eml.as_string(), encoding="utf-8")

    return {"email_txt": txt_path, "followup_txt": followup_path, "eml": eml_path}
