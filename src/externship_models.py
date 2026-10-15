from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Any


@dataclass
class Lead:
    clinic_name: str
    specialty: str = ""
    city: str = ""
    address: str = ""
    website: str = ""
    contact_page: str = ""
    careers_page: str = ""
    main_phone: str = ""
    contact_name: str = ""
    contact_title: str = ""
    contact_email: str = ""
    secondary_email: str = ""
    source_url: str = ""
    source_note: str = ""
    priority: str = "medium"
    status: str = "new"
    last_contact_date: str = ""
    next_followup_date: str = ""
    notes: str = ""
    tags: str = ""
    emails_found: list[str] = field(default_factory=list)
    phones_found: list[str] = field(default_factory=list)
    pages_checked: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["emails_found"] = "; ".join(self.emails_found)
        data["phones_found"] = "; ".join(self.phones_found)
        data["pages_checked"] = "; ".join(self.pages_checked)
        return data

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> "Lead":
        values = dict(row)
        for key in ["emails_found", "phones_found", "pages_checked"]:
            raw = values.get(key, "")
            if isinstance(raw, str):
                values[key] = [x.strip() for x in raw.split(";") if x.strip()]
            elif not isinstance(raw, list):
                values[key] = []
        return cls(**{k: values.get(k, "") for k in cls.__dataclass_fields__})


FIELDNAMES = list(Lead.__dataclass_fields__.keys())
