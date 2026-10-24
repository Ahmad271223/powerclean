"""Eingabemodelle (Pydantic). Feldnamen der Datenobjekte sind Englisch wie in der kostenlosen App,
damit PDF-Erzeugung und Formulare dort wiederverwendet werden können."""
from __future__ import annotations

import re
from datetime import date
from typing import Any, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from zeiten import datum_pruefen, zeit_pruefen

ROLLEN_MUSTER = "^(mitarbeiter|vorarbeiter|buero|inhaber)$"


def _trim(v: Any) -> Any:
    return v.strip() if isinstance(v, str) else v


class RegistrierungIn(BaseModel):
    firma_name: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    art: str = Field(default="betrieb", pattern="^(betrieb|auftraggeber|beides)$")   # Firmenart (siehe gemeinsam.FIRMENARTEN)


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


LOHNARTEN = ("normal", "ueberstunden", "nacht", "sonntag", "feiertag", "urlaub", "krank")


class LohnExportIn(BaseModel):
    """Einstellungen für die LODAS-Importdatei: Berater-/Mandantennummer und die Lohnarten-Nummern des Steuerberaters."""
    berater_nr: Optional[str] = Field(default="", max_length=10)
    mandanten_nr: Optional[str] = Field(default="", max_length=10)
    bs_nr: int = Field(default=1, ge=1, le=99)
    lohnarten: dict[str, str] = Field(default_factory=dict)

    @field_validator("lohnarten")
    @classmethod
    def _lohnarten(cls, v):
        aus = {}
        for k, wert in (v or {}).items():
            if k not in LOHNARTEN:
                raise ValueError(f"Unbekannte Lohnart-Kategorie: {k}")
            wert = str(wert or "").strip()
            if len(wert) > 10:
                raise ValueError("Lohnart-Nummer zu lang")
            aus[k] = wert
        return aus


class FirmaIn(BaseModel):
    name: Optional[str] = Field(default=None, max_length=120)
    art: Optional[str] = Field(default=None, pattern="^(betrieb|auftraggeber|beides)$")
    email_benachrichtigungen: Optional[bool] = None   # E-Mails zu Einladungen, Angeboten, Zuschlägen, Nachträgen, Abnahmen (Standard: an)
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
    country: Optional[str] = Field(default=None, min_length=2, max_length=2)   # Land des Unternehmens (ISO), Standard DE
    lohn_export: Optional["LohnExportIn"] = None                                # DATEV/LODAS-Einstellungen für die Lohnvorbereitung

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
    rechte: Optional[dict[str, bool]] = None   # nur Inhaber, nur für Büro-Konten (siehe auth.RECHTE)
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
    # E-Rechnung (XRechnung/ZUGFeRD): Leitweg-ID für öffentliche Auftraggeber, Kundennummer, USt-IdNr. des Kunden, Land (ISO 3166-1)
    customer_number: Optional[str] = Field(default="", max_length=40)
    leitweg_id: Optional[str] = Field(default="", max_length=60)
    vat_id: Optional[str] = Field(default="", max_length=40)
    country: Optional[str] = Field(default="DE", min_length=2, max_length=2)


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
    # Bauvorhaben (Ausschreibungsplattform), alles optional
    projektnummer: Optional[str] = Field(default="", max_length=60)
    auftraggeber: Optional[str] = Field(default="", max_length=160)
    generalunternehmer: Optional[str] = Field(default="", max_length=160)
    projektart: Optional[str] = Field(default="", max_length=120)
    beschreibung: Optional[str] = Field(default="", max_length=8000)
    baubeginn: Optional[str] = None
    bauende: Optional[str] = None
    phasen: list[str] = Field(default_factory=list, max_length=50)
    bauabschnitte: list[str] = Field(default_factory=list, max_length=100)
    gewerke: list[str] = Field(default_factory=list, max_length=40)
    projektstatus: str = Field(default="", pattern="^(|planung|ausschreibung|ausfuehrung|abgeschlossen)$")
    volumen: Optional[float] = Field(default=None, ge=0, le=1e12)
    kosten: Optional[float] = Field(default=None, ge=0, le=1e12)
    anforderungen: Optional[str] = Field(default="", max_length=4000)
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lon: Optional[float] = Field(default=None, ge=-180, le=180)
    kostenlos: bool = False   # bewusst ohne Stundensatz: 0 € bleibt 0 € (sonst gilt der Firmenstandard)
    abrechnungsart_projekt: str = Field(default="stunden", pattern="^(stunden|pauschal)$")   # Grundlage der Kalkulation (Rechnung weiter nach Stunden)
    pauschale_netto: float = Field(default=0, ge=0, le=1e12)
    abrechnungsart_projekt: str = Field(default="stunden", pattern="^(stunden|pauschal)$")   # Grundlage der Kalkulation (Rechnung weiter nach Stunden)
    pauschale_netto: float = Field(default=0, ge=0, le=1e12)
    abrechnungsart_projekt: str = Field(default="stunden", pattern="^(stunden|pauschal)$")   # Grundlage der Kalkulation (Rechnung weiter nach Stunden)
    pauschale_netto: float = Field(default=0, ge=0, le=1e12)

    @field_validator("baubeginn", "bauende")
    @classmethod
    def _bau_datum(cls, v):
        if v in (None, ""):
            return None
        datum_pruefen(v)
        return v

    @field_validator("phasen", "bauabschnitte", "gewerke")
    @classmethod
    def _listen(cls, v):
        return [x.strip()[:80] for x in v if x and x.strip()]


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
    offline_id: Optional[str] = Field(default=None, max_length=64)   # eindeutige Kennung eines Offline-Eintrags – der Server legt ihn höchstens einmal an
    start_at: Optional[str] = Field(default=None, max_length=40)     # echte Zeitstempel einer Offline-Stempelung (Nachweis)
    end_at: Optional[str] = Field(default=None, max_length=40)

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


class PauseIn(BaseModel):
    von: str = Field(max_length=40)
    bis: Optional[str] = Field(default=None, max_length=40)


class StempelStartIn(BaseModel):
    project_id: str
    gps: Optional[GpsIn] = None
    start_at: Optional[str] = Field(default=None, max_length=40)            # offline gestartete Stempelung übernehmen (höchstens 24 h zurück)
    pausen: list[PauseIn] = Field(default_factory=list, max_length=50)


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
    grund: Optional[str] = Field(default="", max_length=500)   # Pflicht, wenn das Büro einen bereits entschiedenen Antrag ändert

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
    grund: Optional[str] = Field(default="", max_length=500)   # Pflicht, wenn das Büro eine vorhandene Unterschrift ersetzt

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
    nur_pruefen: bool = False   # nur nachsehen, ob es die Rechnung schon gibt – keine Nummer vergeben


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
    erzwingen: bool = False   # trotz laufender Stempelungen abschließen (wird protokolliert)


class PlanIn(BaseModel):
    firma_id: Optional[str] = None
    email: Optional[EmailStr] = None
    status: str = Field(pattern="^(test|aktiv|gesperrt)$")
    nutzer_max: int = Field(default=0, ge=0, le=10000)
    gueltig_bis: Optional[str] = None
    test_bis: Optional[str] = None
    hinweis: Optional[str] = Field(default="", max_length=300)
    stufe: Optional[str] = Field(default=None, pattern="^(pro|plus|firma|teilnahme)$")   # firma = Firmenabo, teilnahme = kostenlose Projektteilnahme
    gu: Optional[bool] = None   # GU-Freischaltung (Ausschreibungen nach der Testphase) – nach Zahlungsbestätigung durch den Betreiber
    gu: Optional[bool] = None   # GU-Freischaltung (Ausschreibungen nach der Testphase) – nach Zahlungsbestätigung durch den Betreiber
    gu: Optional[bool] = None   # GU-Freischaltung (Ausschreibungen nach der Testphase) – nach Zahlungsbestätigung durch den Betreiber


class GuAboIn(BaseModel):
    aktiv: bool


class VerifizierungIn(BaseModel):
    """Betreiber bestätigt eine Firma (z. B. Handelsregister, Gewerbeanmeldung geprüft)."""
    firma_id: Optional[str] = None
    email: Optional[EmailStr] = None
    verifiziert: bool = True
    hinweis: Optional[str] = Field(default="", max_length=300)


# ---------------------------------------------------------------- Bauabwicklung: Nachträge und Abnahmen
class NachtragIn(BaseModel):
    firma_id: Optional[str] = None                     # nur Auftraggeber: beauftragte Firma (bei Anfrage)
    titel: str = Field(min_length=1, max_length=160)
    beschreibung: Optional[str] = Field(default="", max_length=8000)
    grund: Optional[str] = Field(default="", max_length=2000)
    gewerk: Optional[str] = Field(default=None, max_length=60)
    betrag_netto: Optional[float] = Field(default=None, ge=0, le=1e9)
    ust_satz: Optional[float] = Field(default=None, ge=0, le=30)


class NachtragEntscheidungIn(BaseModel):
    freigeben: bool
    begruendung: Optional[str] = Field(default="", max_length=2000)


class AbnahmeIn(BaseModel):
    firma_id: Optional[str] = None                     # nur Auftraggeber: beauftragte Firma
    art: str = Field(default="abnahme", pattern="^(teilabnahme|abnahme|endabnahme)$")
    gewerk: Optional[str] = Field(default=None, max_length=60)
    bereich: Optional[str] = Field(default="", max_length=120)
    datum: Optional[str] = None
    teilnehmer: Optional[str] = Field(default="", max_length=500)
    ergebnis: Optional[str] = Field(default=None, pattern="^(abgenommen|abgenommen_mit_maengeln|verweigert)$")
    vorbehalte: Optional[str] = Field(default="", max_length=4000)
    nachbesserung_bis: Optional[str] = None
    bemerkung: Optional[str] = Field(default="", max_length=2000)
    maengel_ids: list[str] = Field(default_factory=list, max_length=200)


class AbnahmeAntwortIn(BaseModel):
    bestaetigen: bool
    kommentar: Optional[str] = Field(default="", max_length=2000)


class ApiTokenIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    rechte: list[str] = Field(default_factory=lambda: ["zeiten", "projekte"], max_length=10)   # projekte, kunden, mitarbeiter, zeiten, abwesenheiten, rechnungen
    tage: int = Field(default=365, ge=1, le=730)                                                 # Gültigkeit ab Erzeugung


def _iban_pruefen(iban: str) -> str:
    iban = re.sub(r"[\s-]", "", iban or "").upper()
    if not iban:
        return ""
    if not re.fullmatch(r"[A-Z]{2}[0-9]{2}[A-Z0-9]{11,30}", iban):
        raise ValueError("IBAN hat kein gültiges Format")
    umgestellt = iban[4:] + iban[:4]
    zahl = "".join(str(int(c, 36)) for c in umgestellt)
    if int(zahl) % 97 != 1:
        raise ValueError("IBAN-Prüfziffer stimmt nicht")
    return iban


class LohndatenIn(BaseModel):
    """Daten, die Lohnbüro/Steuerberater für die Abrechnung brauchen. Die App rechnet keinen Lohn, sie sammelt und
    exportiert. Steuer-ID, SV-Nummer und IBAN werden verschlüsselt gespeichert."""
    birth_date: Optional[str] = None
    street: Optional[str] = Field(default=None, max_length=200)
    zip_code: Optional[str] = Field(default=None, max_length=20)
    city: Optional[str] = Field(default=None, max_length=120)
    tax_id: Optional[str] = Field(default=None, max_length=20)              # Steuer-ID (11 Ziffern)
    tax_class: Optional[str] = Field(default=None, pattern="^(|1|2|3|4|5|6)$")
    church_tax: Optional[bool] = None
    sv_number: Optional[str] = Field(default=None, max_length=20)           # Sozialversicherungsnummer
    health_insurance: Optional[str] = Field(default=None, max_length=120)
    employment_type: Optional[str] = Field(default=None, pattern="^(|vollzeit|teilzeit|minijob|kurzfristig|werkstudent|azubi|sonstiges)$")
    hourly_wage: Optional[float] = Field(default=None, ge=0, le=1000)
    monthly_salary: Optional[float] = Field(default=None, ge=0, le=100000)
    entry_date: Optional[str] = None
    exit_date: Optional[str] = None
    iban_salary: Optional[str] = Field(default=None, max_length=40)
    notes_payroll: Optional[str] = Field(default=None, max_length=500)

    @field_validator("birth_date", "entry_date", "exit_date")
    @classmethod
    def _datum(cls, v):
        if v in (None, ""):
            return v
        try:
            d = date.fromisoformat(str(v)[:10])
        except ValueError as e:
            raise ValueError("Datum im Format JJJJ-MM-TT angeben") from e
        if not 1900 <= d.year <= 2100:
            raise ValueError("Datum unplausibel")
        return d.isoformat()

    @field_validator("tax_id")
    @classmethod
    def _steuer_id(cls, v):
        if v in (None, ""):
            return v
        ziffern = re.sub(r"[^0-9]", "", v)
        if len(ziffern) != 11 or ziffern[0] == "0":
            raise ValueError("Die Steuer-ID hat 11 Ziffern und beginnt nicht mit 0")
        return ziffern

    @field_validator("sv_number")
    @classmethod
    def _sv(cls, v):
        if v in (None, ""):
            return v
        sv = re.sub(r"\s", "", v).upper()
        if not re.fullmatch(r"[0-9]{8}[A-Z][0-9]{3}", sv):
            raise ValueError("Die SV-Nummer hat 12 Zeichen, z. B. 12 345678 A 123")
        return sv

    @field_validator("iban_salary")
    @classmethod
    def _iban(cls, v):
        if v in (None, ""):
            return v
        return _iban_pruefen(v)


class DokumentIn(BaseModel):
    """Datum (Arbeitstag) und Notiz einer Datei der Projektakte ändern."""
    date: Optional[str] = None
    note: Optional[str] = Field(default=None, max_length=500)

    @field_validator("date")
    @classmethod
    def _datum(cls, v):
        if v in (None, ""):
            return v
        datum_pruefen(v)
        return v


# ---------------------------------------------------------------- Plattform: Zusammenarbeit mehrerer Firmen

class VerzeichnisIn(BaseModel):
    """Eintrag im gemeinsamen Firmenverzeichnis (nur freigegebene Felder sind für andere sichtbar)."""
    sichtbar: bool = False
    gewerke: list[str] = Field(default_factory=list, max_length=12)
    beschreibung: Optional[str] = Field(default="", max_length=500)
    ort: Optional[str] = Field(default="", max_length=120)
    regionen: list[str] = Field(default_factory=list, max_length=20)        # Interessen für Ausschreibungen: Orte/Regionen/PLZ-Bereiche
    ausschreibungen_benachrichtigen: bool = True

    @field_validator("gewerke", "regionen")
    @classmethod
    def _gewerke(cls, v):
        return [g.strip()[:40] for g in v if g and g.strip()]


class LeiterIn(BaseModel):
    user_id: str
    funktion: str = Field(default="Projektleitung", max_length=60)


class EinladungFirmaIn(BaseModel):
    """Firma zum Projekt einladen: registrierte Firma per ID (Verzeichnis) oder per E-Mail (auch unregistriert)."""
    firma_id: Optional[str] = None
    firma_name: Optional[str] = Field(default="", max_length=160)
    email: Optional[str] = Field(default="", max_length=120)
    gewerk: str = Field(default="", max_length=60)
    rolle: str = Field(default="subunternehmer", pattern="^(subunternehmer|nachunternehmer|dienstleister|lieferant)$")
    nachricht: Optional[str] = Field(default="", max_length=500)

    @field_validator("email")
    @classmethod
    def _email(cls, v):
        v = (v or "").strip().lower()
        if v and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", v):
            raise ValueError("E-Mail-Adresse ungültig")
        return v

    @model_validator(mode="after")
    def _ziel(self):
        if not self.firma_id and not (self.email and (self.firma_name or "").strip()):
            raise ValueError("Entweder eine registrierte Firma wählen oder Firmenname und E-Mail angeben")
        return self


class BeteiligungAntwortIn(BaseModel):
    annehmen: bool


class TokenIn(BaseModel):
    token: str = Field(min_length=8, max_length=120)


class FreigabeNamenIn(BaseModel):
    namen: bool = False


class AufgabeIn(BaseModel):
    titel: str = Field(min_length=1, max_length=160)
    beschreibung: Optional[str] = Field(default="", max_length=2000)
    gewerk: Optional[str] = Field(default="", max_length=60)
    firma_id: Optional[str] = None                      # beauftragte Firma (leer = eigene Firma)
    datum: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    prioritaet: str = Field(default="normal", pattern="^(niedrig|normal|hoch|dringend)$")
    bereich: Optional[str] = Field(default="", max_length=160)
    material: Optional[str] = Field(default="", max_length=500)
    vorarbeiter_user_id: Optional[str] = None
    mitarbeiter_ids: list[str] = Field(default_factory=list, max_length=50)


class AufgabeUpdateIn(BaseModel):
    titel: Optional[str] = Field(default=None, min_length=1, max_length=160)
    beschreibung: Optional[str] = Field(default=None, max_length=2000)
    gewerk: Optional[str] = Field(default=None, max_length=60)
    firma_id: Optional[str] = None
    datum: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    prioritaet: Optional[str] = Field(default=None, pattern="^(niedrig|normal|hoch|dringend)$")
    bereich: Optional[str] = Field(default=None, max_length=160)
    material: Optional[str] = Field(default=None, max_length=500)


class AufgabeStatusIn(BaseModel):
    status: str = Field(pattern="^(geplant|zugewiesen|in_bearbeitung|blockiert|eingereicht|abgeschlossen|abgenommen)$")
    kommentar: Optional[str] = Field(default="", max_length=500)


class AufgabeZuteilungIn(BaseModel):
    vorarbeiter_user_id: Optional[str] = None
    mitarbeiter_ids: list[str] = Field(default_factory=list, max_length=50)


class WochenFreigabeIn(BaseModel):
    week_monday: str


class LieferungIn(BaseModel):
    material: str = Field(min_length=1, max_length=200)
    menge: Optional[str] = Field(default="", max_length=60)
    lieferant: Optional[str] = Field(default="", max_length=160)
    firma_id: Optional[str] = None                      # zuständige Firma (leer = eigene)
    geplant_am: str
    zeitfenster_von: Optional[str] = None
    zeitfenster_bis: Optional[str] = None
    entladeort: Optional[str] = Field(default="", max_length=160)
    ansprechpartner: Optional[str] = Field(default="", max_length=120)
    bemerkungen: Optional[str] = Field(default="", max_length=1000)


class LieferungUpdateIn(BaseModel):
    material: Optional[str] = Field(default=None, min_length=1, max_length=200)
    menge: Optional[str] = Field(default=None, max_length=60)
    lieferant: Optional[str] = Field(default=None, max_length=160)
    firma_id: Optional[str] = None
    geplant_am: Optional[str] = None
    tatsaechlich_am: Optional[str] = None
    zeitfenster_von: Optional[str] = None
    zeitfenster_bis: Optional[str] = None
    entladeort: Optional[str] = Field(default=None, max_length=160)
    ansprechpartner: Optional[str] = Field(default=None, max_length=120)
    bemerkungen: Optional[str] = Field(default=None, max_length=1000)


class LieferungStatusIn(BaseModel):
    status: str = Field(pattern="^(angefragt|bestaetigt|unterwegs|eingetroffen|entladen|abgeschlossen|verspaetet|storniert)$")
    kommentar: Optional[str] = Field(default="", max_length=500)
    tatsaechlich_am: Optional[str] = None


class MangelIn(BaseModel):
    beschreibung: str = Field(min_length=1, max_length=2000)
    bereich: Optional[str] = Field(default="", max_length=160)
    kategorie: Optional[str] = Field(default="", max_length=60)
    firma_id: Optional[str] = None                      # verantwortliche Firma
    frist: Optional[str] = None
    prioritaet: str = Field(default="normal", pattern="^(niedrig|normal|hoch|dringend)$")


class MangelUpdateIn(BaseModel):
    beschreibung: Optional[str] = Field(default=None, min_length=1, max_length=2000)
    bereich: Optional[str] = Field(default=None, max_length=160)
    kategorie: Optional[str] = Field(default=None, max_length=60)
    firma_id: Optional[str] = None
    frist: Optional[str] = None
    prioritaet: Optional[str] = Field(default=None, pattern="^(niedrig|normal|hoch|dringend)$")


class MangelStatusIn(BaseModel):
    status: str = Field(pattern="^(offen|zugewiesen|in_bearbeitung|behoben_gemeldet|in_pruefung|abgenommen|erneut_geoeffnet)$")
    kommentar: Optional[str] = Field(default="", max_length=500)


class TagesberichtIn(BaseModel):
    datum: str
    bereich: Optional[str] = Field(default="", max_length=160)
    wetter: Optional[str] = Field(default="", max_length=80)
    firmen: list[str] = Field(default_factory=list, max_length=50)
    mitarbeiter_anzahl: int = Field(default=0, ge=0, le=10000)
    taetigkeiten: Optional[str] = Field(default="", max_length=4000)
    fortschritt: Optional[str] = Field(default="", max_length=1000)
    lieferungen: Optional[str] = Field(default="", max_length=2000)
    behinderungen: Optional[str] = Field(default="", max_length=2000)
    maengel: Optional[str] = Field(default="", max_length=2000)
    besondere_vorkommnisse: Optional[str] = Field(default="", max_length=2000)
    notizen: Optional[str] = Field(default="", max_length=2000)


class TagesberichtStatusIn(BaseModel):
    status: str = Field(pattern="^(entwurf|eingereicht|freigegeben)$")
    kommentar: Optional[str] = Field(default="", max_length=500)


class MeilensteinIn(BaseModel):
    titel: str = Field(min_length=1, max_length=160)
    datum: str
    erledigt: bool = False
    notiz: Optional[str] = Field(default="", max_length=500)


class DokumentFreigabeIn(BaseModel):
    fuer_alle: bool = False


# ---------------------------------------------------------------- Ausschreibungen, Angebote, Vergabe

def _datum_optional(v):
    if v in (None, ""):
        return None
    datum_pruefen(v)
    return v


class PositionIn(BaseModel):
    nr: str = Field(min_length=1, max_length=20)
    leistung: str = Field(min_length=1, max_length=300)
    beschreibung: Optional[str] = Field(default="", max_length=2000)
    menge: float = Field(default=0, ge=0, le=1e9)
    einheit: str = Field(default="Stück", max_length=20)


class AnforderungenIn(BaseModel):
    qualifikationen: Optional[str] = Field(default="", max_length=2000)
    zertifikate: Optional[str] = Field(default="", max_length=2000)
    versicherungen: Optional[str] = Field(default="", max_length=2000)
    kapazitaet: Optional[str] = Field(default="", max_length=1000)
    ausruestung: Optional[str] = Field(default="", max_length=2000)
    material: Optional[str] = Field(default="", max_length=2000)
    technik: Optional[str] = Field(default="", max_length=4000)
    bedingungen: Optional[str] = Field(default="", max_length=4000)
    sicherheit: Optional[str] = Field(default="", max_length=2000)
    sonstiges: Optional[str] = Field(default="", max_length=2000)


class KaufmaennischIn(BaseModel):
    abrechnungsart: str = Field(default="pauschal", pattern="^(pauschal|einheitspreise|stunden|gemischt)$")
    budget: Optional[float] = Field(default=None, ge=0, le=1e12)
    zahlungsbedingungen: Optional[str] = Field(default="", max_length=2000)
    vertragsbedingungen: Optional[str] = Field(default="", max_length=4000)
    preisaufschluesselung: Optional[str] = Field(default="", max_length=2000)


class FreigabeAusschreibungIn(BaseModel):
    budget: bool = False          # Budgetrahmen für Bieter sichtbar
    auftraggeber: bool = True     # Firmenname des Auftraggebers sichtbar
    adresse: bool = True          # Projektadresse sichtbar


class AusschreibungIn(BaseModel):
    titel: str = Field(min_length=1, max_length=200)
    gewerk: str = Field(default="", max_length=60)
    leistungsart: Optional[str] = Field(default="", max_length=120)
    beschreibung: Optional[str] = Field(default="", max_length=20000)
    leistungsumfang: Optional[str] = Field(default="", max_length=20000)
    ausfuehrungsort: Optional[str] = Field(default="", max_length=300)
    sichtbarkeit: str = Field(default="privat", pattern="^(oeffentlich|privat|kombiniert)$")
    bewerbungsfrist: Optional[str] = None
    angebotsfrist: Optional[str] = None
    ausfuehrung_von: Optional[str] = None
    ausfuehrung_bis: Optional[str] = None
    anforderungen: AnforderungenIn = Field(default_factory=AnforderungenIn)
    kaufmaennisch: KaufmaennischIn = Field(default_factory=KaufmaennischIn)
    freigabe: FreigabeAusschreibungIn = Field(default_factory=FreigabeAusschreibungIn)
    positionen: list[PositionIn] = Field(default_factory=list, max_length=500)
    verantwortlich_user_id: Optional[str] = None
    intern: Optional[str] = Field(default="", max_length=4000)   # interne Vermerke, nie für Bieter sichtbar

    @field_validator("bewerbungsfrist", "angebotsfrist", "ausfuehrung_von", "ausfuehrung_bis")
    @classmethod
    def _d(cls, v):
        return _datum_optional(v)

    @model_validator(mode="after")
    def _pruefen(self):
        nrn = [p.nr for p in self.positionen]
        if len(nrn) != len(set(nrn)):
            raise ValueError("Positionsnummern müssen eindeutig sein")
        if self.ausfuehrung_von and self.ausfuehrung_bis and self.ausfuehrung_bis < self.ausfuehrung_von:
            raise ValueError("Ausführungsende liegt vor dem Beginn")
        return self


class AusschreibungEinladungIn(BaseModel):
    firma_ids: list[str] = Field(min_length=1, max_length=50)
    nachricht: Optional[str] = Field(default="", max_length=1000)


class AngebotPositionIn(BaseModel):
    nr: str = Field(min_length=1, max_length=20)
    einzelpreis: Optional[float] = Field(default=None, ge=0, le=1e9)
    bemerkung: Optional[str] = Field(default="", max_length=300)


class AngebotIn(BaseModel):
    nummer: Optional[str] = Field(default="", max_length=60)
    ansprechpartner: Optional[str] = Field(default="", max_length=160)
    preisart: str = Field(default="pauschal", pattern="^(pauschal|einheitspreise|stunden)$")
    preis_netto: Optional[float] = Field(default=None, ge=0, le=1e12)
    stundensatz: Optional[float] = Field(default=None, ge=0, le=100000)
    stunden_geschaetzt: Optional[float] = Field(default=None, ge=0, le=1e7)
    ust_satz: float = Field(default=19, ge=0, le=30)
    reverse_charge: bool = False
    positionen: list[AngebotPositionIn] = Field(default_factory=list, max_length=500)
    leistungsbeschreibung: Optional[str] = Field(default="", max_length=20000)
    ausfuehrung_von: Optional[str] = None
    ausfuehrung_bis: Optional[str] = None
    verfuegbarkeit: Optional[str] = Field(default="", max_length=1000)
    kapazitaet: Optional[str] = Field(default="", max_length=1000)
    material: Optional[str] = Field(default="", max_length=2000)
    zusatzleistungen: Optional[str] = Field(default="", max_length=2000)
    bemerkungen: Optional[str] = Field(default="", max_length=4000)
    gueltig_bis: Optional[str] = None

    @field_validator("ausfuehrung_von", "ausfuehrung_bis", "gueltig_bis")
    @classmethod
    def _d(cls, v):
        return _datum_optional(v)


class AngebotPruefungIn(BaseModel):
    """Entscheidung der Projektleitung zu einem eingereichten Angebot."""
    status: str = Field(pattern="^(in_pruefung|rueckfrage|abgelehnt)$")
    nachricht: Optional[str] = Field(default="", max_length=2000)
    nachreichen_bis: Optional[str] = None

    @field_validator("nachreichen_bis")
    @classmethod
    def _d(cls, v):
        return _datum_optional(v)


class BewertungIn(BaseModel):
    kriterien: dict[str, int] = Field(default_factory=dict)
    notiz: Optional[str] = Field(default="", max_length=4000)
    mindestanforderungen_erfuellt: Optional[bool] = None

    @field_validator("kriterien")
    @classmethod
    def _k(cls, v):
        erlaubt = {"preis", "leistung", "termin", "verfuegbarkeit", "qualifikation", "vollstaendigkeit", "mindestanforderungen"}
        aus = {}
        for k, punkte in v.items():
            if k not in erlaubt:
                raise ValueError(f"Unbekanntes Kriterium: {k}")
            if not 0 <= int(punkte) <= 5:
                raise ValueError("Punkte 0–5")
            aus[k] = int(punkte)
        return aus


class FrageIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    position_nr: Optional[str] = Field(default="", max_length=20)


class AntwortIn(BaseModel):
    antwort: str = Field(min_length=1, max_length=4000)
    oeffentlich: bool = False   # Antwort allen berechtigten Bietern zeigen (ohne Nennung der fragenden Firma)


class VergabeVorschlagIn(BaseModel):
    angebot_id: str
    begruendung: Optional[str] = Field(default="", max_length=4000)


class VergabeMitteilungIn(BaseModel):
    nachricht: Optional[str] = Field(default="", max_length=4000)


class VergabeAntwortIn(BaseModel):
    annehmen: bool
    bestaetigung: Optional[str] = Field(default="", max_length=200)
    name: Optional[str] = Field(default="", max_length=160)
    grund: Optional[str] = Field(default="", max_length=2000)


class PositionenTextIn(BaseModel):
    """Leistungsverzeichnis als Text (CSV: Nr;Leistung;Menge;Einheit[;Beschreibung])."""
    csv: str = Field(min_length=1, max_length=400000)
