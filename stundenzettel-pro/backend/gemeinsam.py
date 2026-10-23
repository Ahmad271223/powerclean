"""Gemeinsame Helfer für die Routen: Standardwerte, Laden mit Mandantenprüfung, Projektstatistik."""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import HTTPException

from auth import hat_rolle, jetzt_iso
from db import db
from zeiten import eintrag_minuten

FIRMA_DEFAULTS = {
    "name": "", "owner": "", "street": "", "zip_code": "", "city": "", "phone": "", "email": "", "website": "",
    "tax_number": "", "vat_id": "", "bank_name": "", "iban": "", "bic": "",
    "default_hourly_rate": 0, "vat_rate": 19, "small_business": False,
    "invoice_prefix": "RE-", "payment_days": 14,
    "invoice_text": "Reinigungsarbeiten laut beiliegenden Stundenzetteln",
    "logo": None, "logo_w": 0, "logo_h": 0,
    "stamp": None, "stamp_w": 0, "stamp_h": 0, "stamp_on_sheet": True, "stamp_on_invoice": True, "stamp_scale": 100,
    "stamp_config": None, "pdf_footer": False,
    # Pro Plus: Arbeitszeitregeln
    "bundesland": "", "auto_pause": False, "arbzg_pruefung": True, "sperre_tage_mitarbeiter": 7, "workdays": [0, 1, 2, 3, 4],
    # Plattform: Firmenart – „betrieb“ führt Aufträge aus (Handwerk, Reinigung, Dienstleistung), „auftraggeber“ vergibt sie (GU, Bauherr,
    # Projektsteuerung), „beides“ kann beides. Bestimmt Menü, Startseite und die Ansicht unter „Ausschreibungen“.
    "art": "betrieb",
}

FIRMENARTEN = {"betrieb": "Ausführender Betrieb", "auftraggeber": "Auftraggeber / Generalunternehmer", "beides": "Beides"}

PROJEKT_DEFAULTS = {
    "name": "", "color": "#C41E3A", "customer_id": None, "customer_name": "", "customer_address": "", "address": "",
    "employee_name": "", "employee_ids": [], "hourly_rate": 0, "notes": "", "archived": False, "default_workers": 1,
    "reverse_charge": False, "schedule": "", "budget_hours_month": 0, "budget_warn_percent": 80,
    "total_minutes": 0, "entry_count": 0, "last_activity_at": None,
    "leiter_ids": [], "verknuepft": None,   # Plattform: Projektleiter der Eigentümerfirma; Verknüpfung mit dem Projekt eines Auftraggebers
    # Bauvorhaben (Ausschreibungsplattform): alles optional, nur für Projekte mit Ausschreibungen/Beteiligungen relevant
    "projektnummer": "", "auftraggeber": "", "generalunternehmer": "", "projektart": "", "beschreibung": "", "baubeginn": None, "bauende": None,
    "phasen": [], "bauabschnitte": [], "gewerke": [], "projektstatus": "", "volumen": None, "kosten": None, "anforderungen": "", "lat": None, "lon": None,
    "kostenlos": False,
    "gu_abo": None,   # kostenpflichtiges GU-Projekt: {status, preis_monat, aktiviert_am, beendet_am, zeitraeume[]} (siehe abo.py)
}

# Felder, die Mitarbeiter und Vorarbeiter nicht sehen (Preise, Budgets, Kundendaten, interne Notizen)
PROJEKT_FELDER_VERTRAULICH = {"hourly_rate", "kostenlos", "budget_hours_month", "budget_warn_percent", "budget", "notes", "customer_address",
                              "customer_id", "reverse_charge", "volumen", "kosten", "quelle_id", "employee_name", "gu_abo"}

# Mitarbeiter sehen keine Bank-/Steuerdaten; Logo und Stempel brauchen sie für den Stundenzettel beim Kunden
FIRMA_FELDER_MITARBEITER = {"id", "name", "owner", "street", "zip_code", "city", "phone", "email", "website", "logo",
                            "logo_w", "logo_h", "stamp", "stamp_w", "stamp_h", "stamp_on_sheet", "stamp_scale", "created_at",
                            "bundesland", "auto_pause", "arbzg_pruefung", "sperre_tage_mitarbeiter", "workdays", "art", "verifiziert"}


def neue_id() -> str:
    return str(uuid.uuid4())


def firma_oeffentlich(f: dict, user: Optional[dict] = None) -> dict:
    """Firma für die Oberfläche: Mitarbeiter sehen nur Name/Anschrift/Logo/Regeln, Büro und Inhaber alles."""
    aus = {**FIRMA_DEFAULTS, **{k: v for k, v in f.items() if k != "_id"}}
    if user is not None and not hat_rolle(user, "buero"):
        aus = {k: v for k, v in aus.items() if k in FIRMA_FELDER_MITARBEITER}
    aus.pop("plan", None)
    return aus


def projekt_normalisieren(p: dict) -> dict:
    return {**PROJEKT_DEFAULTS, **{k: v for k, v in p.items() if k != "_id"}}


def projekt_sichtbar(user: dict, projekt: dict) -> bool:
    """Büro/Inhaber sehen alles; Mitarbeiter und Vorarbeiter nur zugewiesene Projekte (keine Zuweisung = alle)."""
    if hat_rolle(user, "buero"):
        return True
    leiter = projekt.get("leiter_ids") or []
    if user["id"] in leiter:
        return True
    ids = projekt.get("employee_ids") or []
    if ids:
        return user["id"] in ids
    return not leiter   # ohne Zuweisung sehen alle – außer das Projekt hat ausdrückliche Projektleitung (Plattform)


def projekt_leitung(user: dict, projekt: dict) -> bool:
    """Darf alle Zeiten des Projekts sehen und für Kollegen eintragen: Büro/Inhaber oder zugewiesener Vorarbeiter."""
    if hat_rolle(user, "buero"):
        return True
    leiter = projekt.get("leiter_ids") or []
    if leiter:
        return user["id"] in leiter   # ausdrückliche Projektleitung: nur diese Personen
    return user.get("role") == "vorarbeiter" and projekt_sichtbar(user, projekt)


def projekt_fuer_nutzer(user: dict, projekt: dict) -> dict:
    """Projekt für die Antwort: Büro/Inhaber alles; Mitarbeiter ohne vertrauliche Felder; Projektleitung zusätzlich das Stundenbudget."""
    if hat_rolle(user, "buero"):
        return projekt
    aus = {k: v for k, v in projekt.items() if k not in PROJEKT_FELDER_VERTRAULICH}
    if projekt_leitung(user, projekt):
        for k in ("budget_hours_month", "budget_warn_percent", "budget"):
            if k in projekt:
                aus[k] = projekt[k]
    return aus


async def projekt_laden(user: dict, project_id: str, schreiben: bool = False) -> dict:
    p = await db().projects.find_one({"id": project_id, "firma_id": user["firma_id"]}, {"_id": 0})
    if not p or not projekt_sichtbar(user, p):
        raise HTTPException(404, "Projekt nicht gefunden.")
    if schreiben and p.get("archived") and not hat_rolle(user, "buero"):
        raise HTTPException(400, "Das Projekt ist archiviert.")
    if schreiben and not (p.get("verknuepft") or {}).get("project_id"):
        # Zeiten und Stempelungen auf eigenen Projekten brauchen das Firmenabo; verknüpfte GU-Projekte gehören zur kostenlosen Projektteilnahme
        from auth import firma_laden, firmenabo_pruefen
        firmenabo_pruefen(user.get("_firma") or await firma_laden(user["firma_id"]))
    return projekt_normalisieren(p)


async def kunde_laden(firma_id: str, customer_id: Optional[str]) -> Optional[dict]:
    if not customer_id:
        return None
    return await db().customers.find_one({"id": customer_id, "firma_id": firma_id}, {"_id": 0})


def kundenadresse(k: Optional[dict]) -> str:
    if not k:
        return ""
    zeilen = [k.get("contact") or "", k.get("street") or "", " ".join(x for x in [k.get("zip_code") or "", k.get("city") or ""] if x)]
    return "\n".join(z for z in zeilen if z.strip())


async def nutzernamen(firma_id: str) -> dict[str, str]:
    aus = {}
    async for u in db().users.find({"firma_id": firma_id}, {"_id": 0, "id": 1, "name": 1}):
        aus[u["id"]] = u.get("name") or ""
    return aus


async def leistungen_map(firma_id: str) -> dict[str, dict]:
    aus = {}
    async for s in db().services.find({"firma_id": firma_id}, {"_id": 0}):
        aus[s["id"]] = s
    return aus


def eintrag_anreichern(e: dict, namen: dict[str, str]) -> dict:
    e = {k: v for k, v in e.items() if k != "_id"}
    e["user_name"] = namen.get(e.get("user_id") or "", "") if e.get("user_id") else ""
    return e


async def projekt_stats_aktualisieren(firma_id: str, project_id: str) -> dict:
    """Summen am Projekt nachführen (Mitarbeiterstunden, Einträge, letzter Tag) — die Projektliste braucht keine Einträge."""
    gesamt, n, letzter = 0, 0, None
    async for e in db().entries.find({"firma_id": firma_id, "project_id": project_id},
                                      {"_id": 0, "net_minutes": 1, "workers": 1, "date": 1}):
        gesamt += eintrag_minuten(e)
        n += 1
        if not letzter or e.get("date", "") > letzter:
            letzter = e.get("date")
    st = {"total_minutes": gesamt, "entry_count": n, "last_activity_at": letzter, "updated_at": jetzt_iso()}
    await db().projects.update_one({"id": project_id, "firma_id": firma_id}, {"$set": st})
    return st


async def monatsminuten(firma_id: str, project_id: str, jahr: int, monat: int) -> int:
    from zeiten import monatsletzter
    von = f"{jahr:04d}-{monat:02d}-01"
    bis = monatsletzter(jahr, monat).isoformat()
    gesamt = 0
    async for e in db().entries.find({"firma_id": firma_id, "project_id": project_id, "date": {"$gte": von, "$lte": bis}}, {"_id": 0, "net_minutes": 1, "workers": 1}):
        gesamt += eintrag_minuten(e)
    return gesamt


def budget_info(projekt: dict, verbraucht_minuten: int) -> Optional[dict]:
    stunden = float(projekt.get("budget_hours_month") or 0)
    if not stunden:
        return None
    prozent = round(verbraucht_minuten / 60 / stunden * 100) if stunden else 0
    warn = int(projekt.get("budget_warn_percent") or 80)
    return {"stunden_monat": stunden, "verbraucht_minuten": verbraucht_minuten, "prozent": prozent, "warn_prozent": warn,
            "warnung": prozent >= warn, "ueberschritten": prozent > 100}


def ohne_id(doc: Optional[dict]) -> Optional[dict]:
    return None if doc is None else {k: v for k, v in doc.items() if k != "_id"}


async def projekt_fotos(firma_id: str, project_id: str, von: str, bis: str) -> list[dict]:
    """Fotos der Projektakte, deren Arbeitstag (date, sonst Upload-Tag) im Zeitraum liegt – für Kalender und PDF-Anhang."""
    fotos = []
    async for d in db().documents.find({"firma_id": firma_id, "scope": "project", "ref_id": project_id, "mime": {"$regex": "^image/"}}, {"_id": 0, "path": 0}):
        tag = (d.get("date") or (d.get("created_at") or "")[:10])
        if von <= tag <= bis:
            d["tag"] = tag
            fotos.append(d)
    fotos.sort(key=lambda d: (d["tag"], d.get("created_at") or ""))
    return fotos
