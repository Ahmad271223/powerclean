"""Eingabemodelle (Pydantic). Feldnamen der Datenobjekte sind Englisch wie in der kostenlosen App,
damit PDF-Erzeugung und Formulare dort wiederverwendet werden können."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from zeiten import datum_pruefen, zeit_pruefen

ROLLEN_MUSTER = "^(mitarbeiter|vorarbeiter|buero|inhaber)$"


def _trim(v: Any) -> Any:
    return v.strip() if isinstance(v, str) else v


class RegistrierungIn(BaseModel):
    firma_name: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=200)


class EinladungAnnehmenIn(BaseModel):
    password: str = Field(min_length=8, max_length=200)


class PasswortIn(BaseModel):
    alt: str = Field(max_length=200)
    neu: str = Field(min_length=8, max_length=200)


class KontoLoeschenIn(BaseModel):
    password: str = Field(max_length=200)


class FirmaLoeschenIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)   # Firmenname zur Bestätigung
    password: str = Field(max_length=200)


class FirmaIn(BaseModel):
    name: Optional[str] = Field(default=None, max_length=120)
    owner: Optional[str] = Field(default=None, max_length=120)
    street: Optional[str] = Field(default=None, max_length=200)
    zip_code: Optional[str] = Field(default=None, max_length=20)
    city: Optional[str] = Field(default=None, max_length=120)
    phone: Optional[str] = Field(default=None, max_length=60)
    email: Optional[str] = Field(default=None, max_length=120)
    website: Optional[str] = Field(default=None, max_length=120)
    tax_number: Optional[str] = Field(default=None, max_length=60)
    vat_id: Optional[str] = Field(default=None, max_length=60)
    bank_name: Optional[str] = Field(default=None, max_length=120)
    iban: Optional[str] = Field(default=None, max_length=60)
    bic: Optional[str] = Field(default=None, max_length=30)
    default_hourly_rate: Optional[float] = Field(default=None, ge=0, le=10000)
    vat_rate: Optional[float] = Field(default=None, ge=0, le=100)
    small_business: Optional[bool] = None
    invoice_prefix: Optional[str] = Field(default=None, max_length=20)
    payment_days: Optional[int] = Field(default=None, ge=0, le=365)
    invoice_text: Optional[str] = Field(default=None, max_length=500)
    logo: Optional[str] = Field(default=None, max_length=3_000_000)
    logo_w: Optional[int] = Field(default=None, ge=0, le=10000)
    logo_h: Optional[int] = Field(default=None, ge=0, le=10000)
    stamp: Optional[str] = Field(default=None, max_length=3_000_000)
    stamp_w: Optional[int] = Field(default=None, ge=0, le=10000)
    stamp_h: Optional[int] = Field(default=None, ge=0, le=10000)
    stamp_on_sheet: Optional[bool] = None
    stamp_on_invoice: Optional[bool] = None
    stamp_scale: Optional[int] = Field(default=None, ge=50, le=150)
    stamp_config: Optional[dict] = None
    pdf_footer: Optional[bool] = None
    # Pro Plus: Arbeitszeitregeln
    bundesland: Optional[str] = Field(default=None, max_length=2)
    auto_pause: Optional[bool] = None
    arbzg_pruefung: Optional[bool] = None
    sperre_tage_mitarbeiter: Optional[int] = Field(default=None, ge=0, le=365)
    workdays: Optional[list[int]] = Field(default=None, max_length=7)

    @field_validator("logo", "stamp")
    @classmethod
    def _bild(cls, v):
        if v is None or v == "":
            return v
        if not v.startswith("data:image/"):
            raise ValueError("Bild muss als Data-URL (PNG/JPG) übergeben werden.")
        return v

    @field_validator("bundesland")
    @classmethod
    def _land(cls, v):
        from feiertage import BUNDESLAENDER
        if v in (None, ""):
            return v or ""
        if v.upper() not in BUNDESLAENDER:
            raise ValueError("Unbekanntes Bundesland-Kürzel.")
        return v.upper()

    @field_validator("workdays")
    @classmethod
    def _tage(cls, v):
        if v is None:
            return v
        tage = sorted({int(t) for t in v if 0 <= int(t) <= 6})
        if not tage:
            raise ValueError("Mindestens ein Arbeitstag.")
        return tage


class MitarbeiterIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    role: str = Field(default="mitarbeiter", pattern=ROLLEN_MUSTER)
    personalnummer: Optional[str] = Field(default="", max_length=40)
    phone: Optional[str] = Field(default="", max_length=60)
    notes: Optional[str] = Field(default="", max_length=1000)


class MitarbeiterUpdateIn(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    role: Optional[str] = Field(default=None, pattern=ROLLEN_MUSTER)
    personalnummer: Optional[str] = Field(default=None, max_length=40)
    phone: Optional[str] = Field(default=None, max_length=60)
    notes: Optional[str] = Field(default=None, max_length=1000)
    active: Optional[bool] = None
    weekly_hours: Optional[float] = Field(default=None, ge=0, le=80)
    vacation_days: Optional[float] = Field(default=None, ge=0, le=100)
    workdays: Optional[list[int]] = Field(default=None, max_length=7)
    balance_start_minutes: Optional[int] = Field(default=None, ge=-100000, le=100000)
    balance_start_date: Optional[str] = None
    vacation_carryover: Optional[float] = Field(default=None, ge=-100, le=100)
    vacation_carryover_year: Optional[int] = Field(default=None, ge=2025, le=2100)
    pin: Optional[str] = Field(default=None, max_length=8)

    @field_validator("balance_start_date")
    @classmethod
    def _d(cls, v):
        if v:
            datum_pruefen(v)
        return v or None

    @field_validator("workdays")
    @classmethod
    def _tage(cls, v):
        if v is None:
            return v
        return sorted({int(t) for t in v if 0 <= int(t) <= 6})


class KundeIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    contact: Optional[str] = Field(default="", max_length=120)
    street: Optional[str] = Field(default="", max_length=200)
    zip_code: Optional[str] = Field(default="", max_length=20)
    city: Optional[str] = Field(default="", max_length=120)
    email: Optional[str] = Field(default="", max_length=120)
    phone: Optional[str] = Field(default="", max_length=60)
    notes: Optional[str] = Field(default="", max_length=2000)
    reverse_charge: bool = False


class ProjektIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    customer_id: Optional[str] = None
    customer_name: Optional[str] = Field(default="", max_length=160)
    customer_address: Optional[str] = Field(default="", max_length=400)
    address: Optional[str] = Field(default="", max_length=300)
    employee_name: Optional[str] = Field(default="", max_length=200)
    employee_ids: list[str] = Field(default_factory=list, max_length=200)
    hourly_rate: float = Field(default=0, ge=0, le=10000)
    color: str = Field(default="#C41E3A", pattern=r"^#[0-9A-Fa-f]{6}$")
    notes: Optional[str] = Field(default="", max_length=2000)
    archived: bool = False
    default_workers: int = Field(default=1, ge=1, le=99)
    reverse_charge: bool = False
    schedule: Optional[str] = Field(default="", max_length=300)  # z. B. "Mo–Fr 06:00–09:00"
    budget_hours_month: float = Field(default=0, ge=0, le=100000)
    budget_warn_percent: int = Field(default=80, ge=1, le=100)


class ZeitIn(BaseModel):
    project_id: str
    date: str
    start_time: str
    end_time: str
    pause_minutes: int = Field(default=0, ge=0, le=1440)
    activity: Optional[str] = Field(default="", max_length=500)
    workers: int = Field(default=1, ge=1, le=99)
    user_id: Optional[str] = None
    service_id: Optional[str] = None
    offline: bool = False

    @field_validator("date")
    @classmethod
    def _d(cls, v):
        datum_pruefen(v)
        return v

    @field_validator("start_time", "end_time")
    @classmethod
    def _t(cls, v):
        return zeit_pruefen(v)


class ZeitUpdateIn(BaseModel):
    project_id: Optional[str] = None
    date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    pause_minutes: Optional[int] = Field(default=None, ge=0, le=1440)
    activity: Optional[str] = Field(default=None, max_length=500)
    workers: Optional[int] = Field(default=None, ge=1, le=99)
    user_id: Optional[str] = None
    service_id: Optional[str] = None

    @field_validator("date")
    @classmethod
    def _d(cls, v):
        if v is not None:
            datum_pruefen(v)
        return v

    @field_validator("start_time", "end_time")
    @classmethod
    def _t(cls, v):
        return zeit_pruefen(v) if v is not None else v


class SerieIn(BaseModel):
    """Serien-Einträge: gleiche Zeit an mehreren Tagen (z. B. Mo–Fr 06:00–09:00 für den ganzen Monat)."""
    project_id: str
    from_date: str
    to_date: str
    weekdays: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4], max_length=7)  # 0 = Montag
    start_time: str
    end_time: str
    pause_minutes: int = Field(default=0, ge=0, le=1440)
    activity: Optional[str] = Field(default="", max_length=500)
    workers: int = Field(default=1, ge=1, le=99)
    user_id: Optional[str] = None
    service_id: Optional[str] = None
    skip_existing: bool = True
    skip_holidays: bool = True

    @field_validator("from_date", "to_date")
    @classmethod
    def _d(cls, v):
        datum_pruefen(v)
        return v

    @field_validator("start_time", "end_time")
    @classmethod
    def _t(cls, v):
        return zeit_pruefen(v)


class GpsIn(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    accuracy: Optional[float] = Field(default=None, ge=0)


class StempelStartIn(BaseModel):
    project_id: str
    gps: Optional[GpsIn] = None


class StempelStopIn(BaseModel):
    activity: Optional[str] = Field(default="", max_length=500)
    gps: Optional[GpsIn] = None
    service_id: Optional[str] = None


class AbwesenheitIn(BaseModel):
    user_id: Optional[str] = None
    type: str = Field(pattern="^(urlaub|krank|feiertag|unbezahlt|sonstiges)$")
    from_date: str
    to_date: str
    note: Optional[str] = Field(default="", max_length=500)

    @field_validator("from_date", "to_date")
    @classmethod
    def _d(cls, v):
        datum_pruefen(v)
        return v


class AbwesenheitStatusIn(BaseModel):
    status: str = Field(pattern="^(beantragt|genehmigt|abgelehnt)$")
    note: Optional[str] = Field(default=None, max_length=500)


class KommentarIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class ChecklistePunktIn(BaseModel):
    id: Optional[str] = None
    text: str = Field(min_length=1, max_length=300)
    done: bool = False


class ChecklisteIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    items: list[ChecklistePunktIn] = Field(default_factory=list, max_length=200)
    date: Optional[str] = None  # Einsatztag, leer = Dauer-Checkliste


class ChecklisteUpdateIn(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=160)
    items: Optional[list[ChecklistePunktIn]] = Field(default=None, max_length=200)


class UnterschriftIn(BaseModel):
    week_monday: str
    signer_name: str = Field(min_length=1, max_length=120)
    image: str = Field(min_length=50, max_length=800_000)

    @field_validator("week_monday")
    @classmethod
    def _d(cls, v):
        datum_pruefen(v)
        return v

    @field_validator("image")
    @classmethod
    def _bild(cls, v):
        if not v.startswith("data:image/png"):
            raise ValueError("Unterschrift muss ein PNG sein.")
        return v


class RechnungAnlegenIn(BaseModel):
    project_id: str
    year: int = Field(ge=2025, le=2100)
    month: int = Field(ge=1, le=12)


class RechnungStatusIn(BaseModel):
    status: str = Field(pattern="^(offen|bezahlt|storniert)$")
    paid_at: Optional[str] = None
    invoice_date: Optional[str] = None


class ExtraIn(BaseModel):
    text: str = Field(min_length=1, max_length=200)
    quantity: float = Field(default=1, ge=0, le=100000)
    unit: Optional[str] = Field(default="Stk.", max_length=20)
    unit_price: float = Field(ge=-100000, le=100000)


class ExtrasIn(BaseModel):
    extras: list[ExtraIn] = Field(default_factory=list, max_length=50)


class LeistungIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    hourly_rate: float = Field(default=0, ge=0, le=10000)   # 0 = Satz des Projekts
    active: bool = True
    sort: int = Field(default=0, ge=0, le=1000)


class BuchungIn(BaseModel):
    """Buchung auf dem Stundenkonto: Minuten positiv (Gutschrift) oder negativ (Auszahlung/Abbau)."""
    date: str
    minutes: int = Field(ge=-100000, le=100000)
    type: str = Field(pattern="^(auszahlung|ausgleich|korrektur|start)$")
    note: Optional[str] = Field(default="", max_length=300)

    @field_validator("date")
    @classmethod
    def _d(cls, v):
        datum_pruefen(v)
        return v


class WebhookIn(BaseModel):
    url: str = Field(min_length=8, max_length=500, pattern=r"^https?://")
    events: list[str] = Field(default_factory=lambda: ["*"], max_length=30)
    active: bool = True
    name: Optional[str] = Field(default="", max_length=80)


class AbschlussIn(BaseModel):
    year: int = Field(ge=2025, le=2100)
    month: int = Field(ge=1, le=12)


class PlanIn(BaseModel):
    firma_id: Optional[str] = None
    email: Optional[EmailStr] = None
    status: str = Field(pattern="^(test|aktiv|gesperrt)$")
    nutzer_max: int = Field(default=0, ge=0, le=10000)
    gueltig_bis: Optional[str] = None
    test_bis: Optional[str] = None
    hinweis: Optional[str] = Field(default="", max_length=300)
    stufe: Optional[str] = Field(default=None, pattern="^(pro|plus)$")


class ApiTokenIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
