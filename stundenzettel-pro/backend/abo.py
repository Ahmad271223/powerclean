"""Abonnements: kostenpflichtige GU-Projekte (je aktivem Projekt) und Firmenabo – Preise in preise.py.

Zustände eines GU-Projekts (projects.gu_abo.status):
- (kein Abo)   Entwurf: interne Vorbereitung, 0 €.
- aktiv        50,99 € netto je Monat ab der Aktivierung (erste Veröffentlichung einer Ausschreibung, Einladung von Bietern oder einer Firma
               zum Projekt, oder ausdrücklich von Hand) – nur für Firmen der Art „auftraggeber“ oder „beides“.
- gekuendigt   Zum Periodenende gekündigt (Periode = Kalendermonat): bis `endet_am` kostenpflichtig und voll nutzbar, danach beendet.
               Eine erneute Aktivierung vor dem Periodenende nimmt die Kündigung zurück, ohne neuen Zeitraum.
- beendet      Keine Projektgebühr mehr; Lesen, Export und Projektakte bleiben. Veröffentlichen oder Einladen aktiviert erneut (neuer Zeitraum).
Alle Zeiträume bleiben in `zeitraeume[]` für die Abrechnung erhalten. Zahlung: Rechnung des Anbieters auf Basis von /api/admin/abos."""
from __future__ import annotations

from calendar import monthrange
from datetime import date
from typing import Optional

from fastapi import HTTPException

from auth import firma_laden, jetzt_iso, plan_status
from db import db
from plattform import benachrichtigen
from preise import PREISE, firmenabo_kosten
from protokoll import protokollieren
from zeiten import lokal_jetzt

STATUS_NAMEN = {"aktiv": "Aktiv", "gekuendigt": "Gekündigt zum Periodenende", "beendet": "Beendet"}


def ist_auftraggeber(firma: dict) -> bool:
    return (firma.get("art") or "betrieb") in ("auftraggeber", "beides")


def _heute() -> date:
    return lokal_jetzt().date()


def periodenende(tag: Optional[date] = None) -> str:
    tag = tag or _heute()
    return tag.replace(day=monthrange(tag.year, tag.month)[1]).isoformat()


def abgelaufen(abo: Optional[dict], heute: Optional[str] = None) -> Optional[dict]:
    """Gekündigte Abos nach dem Periodenende als beendet ansehen (ohne Datenbankzugriff)."""
    if not abo:
        return abo
    heute = heute or _heute().isoformat()
    if abo.get("status") == "gekuendigt" and abo.get("endet_am") and abo["endet_am"] < heute:
        zeitraeume = [dict(z) for z in abo.get("zeitraeume") or []]
        if zeitraeume:
            zeitraeume[-1]["bis"] = abo["endet_am"]
        return {**abo, "status": "beendet", "beendet_am": abo["endet_am"], "zeitraeume": zeitraeume}
    return abo


def kostenpflichtig(abo: Optional[dict]) -> bool:
    abo = abgelaufen(abo)
    return bool(abo and abo.get("status") in ("aktiv", "gekuendigt"))


async def _speichern(projekt: dict, neu: dict) -> dict:
    neu["status_name"] = STATUS_NAMEN.get(neu.get("status"), neu.get("status"))
    await db().projects.update_one({"id": projekt["id"]}, {"$set": {"gu_abo": neu, "updated_at": jetzt_iso()}})
    projekt["gu_abo"] = neu
    return neu


async def gu_abo_aktivieren(user: dict, projekt: dict, anlass: str) -> Optional[dict]:
    """Projekt als kostenpflichtiges GU-Projekt aktivieren (einmalig; läuft es schon, passiert nichts; eine Kündigung wird zurückgenommen)."""
    firma = user.get("_firma") or await firma_laden(user["firma_id"])
    if not ist_auftraggeber(firma) or projekt.get("firma_id") != user["firma_id"]:
        return None
    abo = abgelaufen(projekt.get("gu_abo")) or {}
    if abo.get("status") == "aktiv":
        return abo
    heute = _heute().isoformat()
    if abo.get("status") == "gekuendigt":
        zeitraeume = [dict(z) for z in abo.get("zeitraeume") or []]
        if zeitraeume:
            zeitraeume[-1]["bis"] = None
        neu = {**abo, "status": "aktiv", "endet_am": None, "gekuendigt_am": None, "gekuendigt_von": None, "zeitraeume": zeitraeume}
        await _speichern(projekt, neu)
        await protokollieren(user, "projekt.gu_abo_kuendigung_zurueck", projekt.get("name", ""), details={"anlass": anlass})
        return neu
    neu = {"status": "aktiv", "preis_monat": PREISE["projekt_gu"], "aktiviert_am": heute, "aktiviert_von": user.get("name"), "anlass": anlass,
           "endet_am": None, "gekuendigt_am": None, "gekuendigt_von": None, "beendet_am": None,
           "zeitraeume": (abo.get("zeitraeume") or []) + [{"von": heute, "bis": None}]}
    await _speichern(projekt, neu)
    await protokollieren(user, "projekt.gu_abo_aktiviert", projekt.get("name", ""), details={"anlass": anlass, "preis_monat": neu["preis_monat"]})
    await benachrichtigen(user["firma_id"], "gu_abo", f"„{projekt.get('name')}“ ist jetzt ein kostenpflichtiges GU-Projekt ({PREISE['projekt_gu']:.2f} € netto je Monat). Anlass: {anlass}.", f"/projekte/{projekt['id']}")
    return neu


async def gu_abo_kuendigen(user: dict, projekt: dict) -> dict:
    """Zum Periodenende (Monatsende) kündigen: bis dahin kostenpflichtig und voll nutzbar, danach beendet."""
    abo = abgelaufen(projekt.get("gu_abo")) or {}
    if abo.get("status") != "aktiv":
        raise HTTPException(400, "Dieses Projekt hat kein laufendes GU-Abo." if abo.get("status") != "gekuendigt" else "Dieses GU-Abo ist bereits gekündigt.")
    heute = _heute()
    ende = periodenende(heute)
    zeitraeume = [dict(z) for z in abo.get("zeitraeume") or []]
    if zeitraeume and not zeitraeume[-1].get("bis"):
        zeitraeume[-1]["bis"] = ende
    neu = {**abo, "status": "gekuendigt", "endet_am": ende, "gekuendigt_am": heute.isoformat(), "gekuendigt_von": user.get("name"), "zeitraeume": zeitraeume}
    await _speichern(projekt, neu)
    await protokollieren(user, "projekt.gu_abo_gekuendigt", projekt.get("name", ""), details={"endet_am": ende})
    return neu


async def gu_abo_beenden(user: dict, projekt: dict) -> dict:
    """Frühere Bezeichnung – heute eine Kündigung zum Periodenende."""
    return await gu_abo_kuendigen(user, projekt)


async def firma_abos(firma_id: str) -> dict:
    """Stand für die Lizenzseite: Firmenabo, aktive GU-Projekte (inkl. gekündigter bis zum Periodenende) und die Monatskosten."""
    firma = await firma_laden(firma_id)
    st = plan_status(firma)
    nutzer = await db().users.count_documents({"firma_id": firma_id, "active": True})
    heute = _heute().isoformat()
    projekte = []
    async for p in db().projects.find({"firma_id": firma_id, "gu_abo": {"$ne": None}}, {"_id": 0, "id": 1, "name": 1, "gu_abo": 1, "archived": 1}):
        abo = abgelaufen(p.get("gu_abo"), heute)
        if abo and abo != p.get("gu_abo"):
            await db().projects.update_one({"id": p["id"]}, {"$set": {"gu_abo": abo}})
        if abo:
            abo["status_name"] = STATUS_NAMEN.get(abo.get("status"), abo.get("status"))
        projekte.append({**p, "gu_abo": abo})
    aktiv = [p for p in projekte if kostenpflichtig(p.get("gu_abo"))]
    kosten_projekte = round(len(aktiv) * PREISE["projekt_gu"], 2)
    firmenabo = st["stufe"] == "firma" and st["status"] in ("test", "aktiv")
    kosten_firma = firmenabo_kosten(nutzer) if firmenabo else 0.0
    return {"plan": st, "art": firma.get("art") or "betrieb", "nutzer_aktiv": nutzer, "preise": PREISE, "projekte": projekte,
            "gu_projekte_aktiv": len(aktiv), "kosten_projekte_monat": kosten_projekte, "kosten_firma_monat": kosten_firma,
            "kosten_monat": round(kosten_projekte + kosten_firma, 2), "firmenabo": firmenabo, "periode": "Kalendermonat",
            "fair_use": {"speicher_gb": float(((firma.get("plan") or {}).get("speicher_gb")) or __import__("config").SPEICHER_GB), "max_datei_mb": __import__("config").MAX_DATEI_MB,
                         "uploads_je_10_min": __import__("config").UPLOADS_JE_10_MIN},
            "zahlung": "Abrechnung per Rechnung des Anbieters; ein Zahlungsdienst (Karte/Lastschrift) ist noch nicht angebunden."}
