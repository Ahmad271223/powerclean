"""Abonnements: kostenpflichtige GU-Projekte (je aktivem Projekt) und Firmenabo – Preise in preise.py.

Ein GU-Projekt wird mit der ersten Veröffentlichung einer Ausschreibung oder der ersten Einladung einer Firma aktiviert
(nur für Firmen der Art „auftraggeber“ oder „beides“); Entwürfe bleiben kostenlos. Beenden kann der Inhaber; eine spätere
Veröffentlichung oder Einladung aktiviert das Projekt wieder (neuer Zeitraum). Die Zeiträume bleiben für die Abrechnung erhalten.
Zahlung: Rechnung des Anbieters auf Basis von /api/admin/abos, bis ein Zahlungsdienst angebunden ist."""
from __future__ import annotations

from typing import Optional

from fastapi import HTTPException

from auth import firma_laden, jetzt_iso, plan_status
from db import db
from plattform import benachrichtigen
from preise import PREISE, firmenabo_kosten
from protokoll import protokollieren
from zeiten import lokal_jetzt


def ist_auftraggeber(firma: dict) -> bool:
    return (firma.get("art") or "betrieb") in ("auftraggeber", "beides")


async def gu_abo_aktivieren(user: dict, projekt: dict, anlass: str) -> Optional[dict]:
    """Projekt als kostenpflichtiges GU-Projekt aktivieren (einmalig; läuft es schon, passiert nichts)."""
    firma = user.get("_firma") or await firma_laden(user["firma_id"])
    if not ist_auftraggeber(firma) or projekt.get("firma_id") != user["firma_id"]:
        return None
    abo = projekt.get("gu_abo") or {}
    if abo.get("status") == "aktiv":
        return abo
    heute = lokal_jetzt().date().isoformat()
    neu = {"status": "aktiv", "preis_monat": PREISE["projekt_gu"], "aktiviert_am": heute, "aktiviert_von": user.get("name"), "anlass": anlass,
           "beendet_am": None, "beendet_von": None, "zeitraeume": (abo.get("zeitraeume") or []) + [{"von": heute, "bis": None}]}
    await db().projects.update_one({"id": projekt["id"]}, {"$set": {"gu_abo": neu, "updated_at": jetzt_iso()}})
    projekt["gu_abo"] = neu
    await protokollieren(user, "projekt.gu_abo_aktiviert", projekt.get("name", ""), details={"anlass": anlass, "preis_monat": neu["preis_monat"]})
    await benachrichtigen(user["firma_id"], "gu_abo", f"„{projekt.get('name')}“ ist jetzt ein kostenpflichtiges GU-Projekt ({PREISE['projekt_gu']:.2f} € netto je Monat). Anlass: {anlass}.", f"/projekte/{projekt['id']}")
    return neu


async def gu_abo_beenden(user: dict, projekt: dict) -> dict:
    abo = projekt.get("gu_abo") or {}
    if abo.get("status") != "aktiv":
        raise HTTPException(400, "Dieses Projekt hat kein laufendes GU-Abo.")
    heute = lokal_jetzt().date().isoformat()
    zeitraeume = [dict(z) for z in abo.get("zeitraeume") or []]
    if zeitraeume and not zeitraeume[-1].get("bis"):
        zeitraeume[-1]["bis"] = heute
    neu = {**abo, "status": "beendet", "beendet_am": heute, "beendet_von": user.get("name"), "zeitraeume": zeitraeume}
    await db().projects.update_one({"id": projekt["id"]}, {"$set": {"gu_abo": neu, "updated_at": jetzt_iso()}})
    await protokollieren(user, "projekt.gu_abo_beendet", projekt.get("name", ""), details={"zeitraeume": len(zeitraeume)})
    return neu


async def firma_abos(firma_id: str) -> dict:
    """Stand für die Lizenzseite: Firmenabo, aktive GU-Projekte und die daraus folgenden Monatskosten."""
    firma = await firma_laden(firma_id)
    st = plan_status(firma)
    nutzer = await db().users.count_documents({"firma_id": firma_id, "active": True})
    projekte = [p async for p in db().projects.find({"firma_id": firma_id, "gu_abo": {"$ne": None}}, {"_id": 0, "id": 1, "name": 1, "gu_abo": 1, "archived": 1})]
    aktiv = [p for p in projekte if (p.get("gu_abo") or {}).get("status") == "aktiv"]
    kosten_projekte = round(len(aktiv) * PREISE["projekt_gu"], 2)
    firmenabo = st["stufe"] == "firma" and st["status"] in ("test", "aktiv")
    kosten_firma = firmenabo_kosten(nutzer) if firmenabo else 0.0
    return {"plan": st, "art": firma.get("art") or "betrieb", "nutzer_aktiv": nutzer, "preise": PREISE, "projekte": projekte,
            "gu_projekte_aktiv": len(aktiv), "kosten_projekte_monat": kosten_projekte, "kosten_firma_monat": kosten_firma,
            "kosten_monat": round(kosten_projekte + kosten_firma, 2), "firmenabo": firmenabo,
            "zahlung": "Abrechnung per Rechnung des Anbieters; ein Zahlungsdienst (Karte/Lastschrift) ist noch nicht angebunden."}
