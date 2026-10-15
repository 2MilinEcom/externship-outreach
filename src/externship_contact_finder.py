from __future__ import annotations

import re
import ssl
import time
from html import unescape
from urllib.error import URLError, HTTPError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from src.externship_models import Lead

EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
PHONE_RE = re.compile(r"(?:\+?1[\s.-]?)?(?:\(?\d{3}\)?[\s.-]?)\d{3}[\s.-]?\d{4}")
BAD_EMAIL_TERMS = {
    "example.com",
    "email.com",
    "domain.com",
    "sentry.io",
    "wixpress.com",
    "wordpress.com",
    "schema.org",
}
GOOD_LINK_TERMS = ["contact", "career", "jobs", "volunteer", "externship", "internship", "student", "team", "about"]


def normalize_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) == 10:
        return f"{digits[0:3]}{digits[3:6]}{digits[6:10]}"
    return digits


def clean_html_text(html: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def fetch_url(url: str, timeout: int = 12) -> tuple[str, str]:
    if not url or not url.startswith(("http://", "https://")):
        return "", "invalid_url"
    req = Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; ExternshipOutreachBot/1.0; public-contact-review-only)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })
    try:
        ctx = ssl.create_default_context()
        with urlopen(req, timeout=timeout, context=ctx) as resp:
            ctype = resp.headers.get("Content-Type", "")
            if "text" not in ctype and "html" not in ctype and not ctype.startswith("application/xhtml"):
                return "", f"non_html:{ctype}"
            raw = resp.read(800_000)
            enc = resp.headers.get_content_charset() or "utf-8"
            return raw.decode(enc, errors="replace"), "ok"
    except HTTPError as exc:
        return "", f"http_{exc.code}"
    except URLError as exc:
        return "", f"url_error:{exc.reason}"
    except Exception as exc:
        return "", f"error:{type(exc).__name__}:{exc}"


def extract_emails(text_or_html: str) -> list[str]:
    found = []
    for email in EMAIL_RE.findall(text_or_html or ""):
        email = email.strip(".,;:()[]{}<>").lower()
        if any(term in email for term in BAD_EMAIL_TERMS):
            continue
        if email.startswith(("noreply@", "no-reply@", "donotreply@")):
            continue
        if email not in found:
            found.append(email)
    return found


def extract_phones(text_or_html: str) -> list[str]:
    found = []
    for phone in PHONE_RE.findall(text_or_html or ""):
        clean = normalize_phone(phone)
        if len(clean) == 10 and clean not in found:
            found.append(clean)
    return found


def extract_candidate_links(base_url: str, html: str, limit: int = 12) -> list[str]:
    links: list[str] = []
    for match in re.finditer(r"<a\s+[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", html or "", flags=re.I | re.S):
        href = unescape(match.group(1)).strip()
        label = clean_html_text(match.group(2)).lower()
        absolute = urljoin(base_url, href)
        parsed = urlparse(absolute)
        if parsed.scheme not in {"http", "https"}:
            continue
        hay = f"{absolute.lower()} {label}"
        if not any(term in hay for term in GOOD_LINK_TERMS):
            continue
        if absolute not in links:
            links.append(absolute)
        if len(links) >= limit:
            break
    return links


def infer_contact_person_from_text(text: str) -> tuple[str, str]:
    # Conservative: only match explicit manager/coordinator patterns near names.
    patterns = [
        r"([A-Z][a-z]+\s+[A-Z][a-z]+)[,\s\-–—]+(?:our\s+)?(clinic manager|office manager|practice manager|volunteer coordinator|externship coordinator|program coordinator|director of [A-Za-z\s]+)",
        r"(clinic manager|office manager|practice manager|volunteer coordinator|externship coordinator|program coordinator|director of [A-Za-z\s]+)[,\s\-–—]+([A-Z][a-z]+\s+[A-Z][a-z]+)",
    ]
    for pat in patterns:
        m = re.search(pat, text or "")
        if not m:
            continue
        a, b = m.group(1).strip(), m.group(2).strip()
        if "manager" in a.lower() or "coordinator" in a.lower() or "director" in a.lower():
            return b, a
        return a, b
    return "", ""


def score_lead(lead: Lead) -> int:
    score = 0
    hay = " ".join([lead.clinic_name, lead.specialty, lead.tags, lead.source_note, lead.website, lead.contact_page]).lower()
    if "externship" in hay:
        score += 40
    if "medical assistant" in hay or "ma " in hay:
        score += 30
    if "community health" in hay or "clinic" in hay:
        score += 12
    if "volunteer" in hay:
        score += 8
    if lead.contact_email:
        score += 15
    if lead.main_phone:
        score += 10
    if lead.contact_name:
        score += 10
    if "school coordinator required" in hay:
        score -= 25
    if "not accepting" in hay or "closed" in hay:
        score -= 20
    return score


def enrich_lead(lead: Lead, *, sleep_seconds: float = 0.25) -> Lead:
    urls = []
    for url in [lead.website, lead.contact_page, lead.careers_page, lead.source_url]:
        if url and url.startswith(("http://", "https://")) and url not in urls:
            urls.append(url)
    pages_checked = list(lead.pages_checked or [])
    emails = set(lead.emails_found or [])
    phones = set(lead.phones_found or [])
    found_links: list[str] = []
    notes = []

    for url in urls[:4]:
        html, status = fetch_url(url)
        pages_checked.append(f"{url} ({status})")
        if status == "ok" and html:
            emails.update(extract_emails(html))
            phones.update(extract_phones(html))
            text = clean_html_text(html)
            if not lead.contact_name or not lead.contact_title:
                name, title = infer_contact_person_from_text(text)
                if name and not lead.contact_name:
                    lead.contact_name = name
                if title and not lead.contact_title:
                    lead.contact_title = title
            for link in extract_candidate_links(url, html):
                if link not in urls and link not in found_links:
                    found_links.append(link)
        time.sleep(sleep_seconds)

    # Check a few likely internal pages discovered from official pages.
    for url in found_links[:8]:
        html, status = fetch_url(url)
        pages_checked.append(f"{url} ({status})")
        if status == "ok" and html:
            emails.update(extract_emails(html))
            phones.update(extract_phones(html))
        time.sleep(sleep_seconds)

    # Do not overwrite stronger public contact with random extracted email unless missing.
    emails = {e for e in emails if e and "@" in e}
    phones = {p for p in phones if len(p) == 10}
    if not lead.contact_email and emails:
        lead.contact_email = sorted(emails)[0]
    if not lead.main_phone and phones:
        lead.main_phone = sorted(phones)[0]
    lead.emails_found = sorted(emails)
    lead.phones_found = sorted(phones)
    lead.pages_checked = pages_checked[-30:]
    if notes:
        lead.notes = (lead.notes + " | " + " | ".join(notes)).strip(" |")
    return lead


def enrich_leads(leads: list[Lead], *, max_leads: int | None = None) -> list[Lead]:
    selected = leads[:max_leads] if max_leads else leads
    for i, lead in enumerate(selected, start=1):
        print(f"[{i}/{len(selected)}] Enriching: {lead.clinic_name}")
        try:
            enrich_lead(lead)
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            lead.notes = (lead.notes + f" | enrich_error:{exc}").strip(" |")
    return leads
