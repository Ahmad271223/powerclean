"""KI-Routen (Stufe H): hinter dem Feature-Flag `ki` (Standard aus). Nur Entwürfe – gespeichert wird nichts; die Übernahme läuft über die
normalen Angebots- und Eingangsrechnungsrouten, nachdem ein Mensch geprüft hat."""
from __future__ import annotations

from fastapi import APIRouter, Depends

import ki
from auth import aktueller_nutzer, firma_laden, hat_recht, recht_noetig
from db import db
from features import feature_noetig
from models import KiTextIn
from protokoll import protokollieren

router = APIRouter(prefix="/api/ki", tags=["KI-Entwürfe"], dependencies=[feature_noetig("ki")])


@router.get("/status")
async def status(user: dict = Depends(aktueller_nutzer)):
    st = ki.eingerichtet()
    return {**st, "freigabe": "Jeder Entwurf wird erst durch Übernehmen in der Oberfläche gespeichert.", "rechte": {"angebot": hat_recht(user, "angebote"), "beleg": hat_recht(user, "rechnungen")}}


@router.post("/angebot-entwurf")
async def angebot_entwurf(body: KiTextIn, user: dict = Depends(recht_noetig("angebote"))):
    firma = await firma_laden(user["firma_id"])
    artikel = [a async for a in db().artikel.find({"firma_id": user["firma_id"], "aktiv": {"$ne": False}}, {"_id": 0, "name": 1, "einheit": 1, "verkaufspreis": 1}).limit(120)]
    leistungen = [l async for l in db().services.find({"firma_id": user["firma_id"]}, {"_id": 0, "name": 1, "hourly_rate": 1}).limit(60)]
    ergebnis = ki.angebot_entwurf(body.text, firma, artikel, leistungen)
    await protokollieren(user, "ki.angebot_entwurf", "", details={"zeichen": len(body.text), "positionen": len(ergebnis["positionen"]), "modell": ergebnis["modell"], "dauer_s": ergebnis["dauer_s"]})
    return ergebnis


@router.post("/beleg-vorschlag")
async def beleg_vorschlag(body: KiTextIn, user: dict = Depends(recht_noetig("rechnungen"))):
    ergebnis = ki.beleg_vorschlag(body.text)
    await protokollieren(user, "ki.beleg_vorschlag", "", details={"zeichen": len(body.text), "modell": ergebnis["modell"], "dauer_s": ergebnis["dauer_s"]})
    return ergebnis
