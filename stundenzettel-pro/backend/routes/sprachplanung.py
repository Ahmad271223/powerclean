"""Einteilung per Sprache (Flag `sprachplanung`): Satz oder fertige Felder → Einteilungsvorschlag. Speichert nichts – gespeichert wird erst,
wenn der Planer den Vorschlag bestätigt (normale Route POST /api/einsatzplan)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

import features
import sprachplanung as sp
from auth import firma_laden, recht_noetig
from db import db
from features import feature_noetig
from protokoll import protokollieren
from zeiten import lokal_jetzt

router = APIRouter(prefix="/api/sprachplanung", tags=["Einteilung per Sprache"], dependencies=[feature_noetig("sprachplanung")])


class FelderIn(BaseModel):
    mitarbeiter: list[str] = Field(default_factory=list, max_length=20)
    projekt: Optional[str] = Field(default=None, max_length=200)
    standort: Optional[str] = Field(default=None, max_length=200)
    startzeit: Optional[str] = Field(default=None, max_length=20)
    endzeit: Optional[str] = Field(default=None, max_length=20)
    zeitraum: Optional[str] = Field(default=None, max_length=300)
    unsicher: list[str] = Field(default_factory=list, max_length=10)


class VorschlagIn(BaseModel):
    text: Optional[str] = Field(default=None, max_length=1000)
    felder: Optional[FelderIn] = None   # schon auf dem Gerät zerlegt (iPhone: Apple-KI)
    quelle: Optional[str] = Field(default=None, pattern="^(apple|mistral|regeln)$")


class PruefenIn(BaseModel):
    user_ids: list[str] = Field(default_factory=list, max_length=50)
    dates: list[str] = Field(default_factory=list, max_length=60)
    start_time: str = Field(max_length=5)
    end_time: str = Field(max_length=5)


@router.post("/pruefen")
async def pruefen(body: PruefenIn, user: dict = Depends(recht_noetig("plantafel"))):
    """Konflikte des geänderten Vorschlags neu prüfen (Bestätigungsfenster). Speichert nichts."""
    from zeiten import datum_pruefen
    start, ende = sp.uhrzeit(body.start_time), sp.uhrzeit(body.end_time)
    if not start or not ende:
        raise HTTPException(422, "Bitte Beginn und Ende als Uhrzeit angeben (z. B. 07:00).")
    for d in body.dates:
        try:
            datum_pruefen(d)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
    erlaubt = {u["id"] async for u in db().users.find({"firma_id": user["firma_id"], "id": {"$in": body.user_ids}}, {"_id": 0, "id": 1})}
    if set(body.user_ids) - erlaubt:
        raise HTTPException(400, "Mindestens ein Mitarbeiter gehört nicht zur Firma.")
    firma = await firma_laden(user["firma_id"])
    konflikte = await sp.konflikte_pruefen(firma, list(dict.fromkeys(body.user_ids)), sorted(set(body.dates)), start, ende)
    return {"konflikte": konflikte, "blockiert": any(k["art"] == "ueberschneidung" for k in konflikte),
            "trotzdem_noetig": any(k["art"] == "abwesenheit" for k in konflikte)}


@router.get("/status")
async def status(user: dict = Depends(recht_noetig("plantafel"))):
    """Welche Zerlegung der Server anbietet (ohne Geheimnisse)."""
    mistral = features.aktiv("ki") and sp.mistral_eingerichtet()
    return {"server_ki": "mistral" if mistral else None, "regeln": True,
            "hinweis": "Auf dem iPhone zerlegt Apples Modell auf dem Gerät; sonst " + ("Mistral auf dem Server." if mistral else "feste Regeln auf dem Server.")}


@router.post("/vorschlag")
async def vorschlag(body: VorschlagIn, user: dict = Depends(recht_noetig("plantafel"))):
    if not body.felder and not (body.text or "").strip():
        raise HTTPException(400, "Bitte einen Satz sprechen oder eintippen.")
    firma = await firma_laden(user["firma_id"])
    hinweise = []
    if body.felder:
        felder, quelle = sp.felder_pruefen(body.felder.model_dump()), body.quelle or "apple"
    else:
        text = body.text.strip()
        quelle = "regeln"
        felder = None
        if features.aktiv("ki") and sp.mistral_eingerichtet():
            try:
                felder, quelle = await sp.mistral_zerlegen(text), "mistral"
            except Exception:  # noqa: BLE001 – ohne KI weiter mit festen Regeln
                hinweise.append("Die KI auf dem Server war nicht erreichbar – der Satz wurde mit festen Regeln zerlegt.")
        if felder is None:
            namen = [u.get("name") or "" async for u in db().users.find({"firma_id": user["firma_id"], "active": {"$ne": False}}, {"_id": 0, "name": 1})]
            projekte = [p async for p in db().projects.find({"firma_id": user["firma_id"], "archived": {"$ne": True}}, {"_id": 0, "name": 1})]
            felder = sp.regeln_zerlegen(text, namen, projekte)
    ergebnis = await sp.vorschlag(firma, felder, lokal_jetzt().date(), quelle)
    ergebnis["hinweise"] = hinweise + ergebnis["hinweise"]
    # Datenschutz: kein Text im Protokoll – nur Länge, Quelle und ob der Vorschlag vollständig war
    await protokollieren(user, "sprachplanung.vorschlag", "", details={"zeichen": len(body.text or ""), "quelle": quelle,
                                                                       "vollstaendig": ergebnis["entwurf"] is not None, "rueckfragen": len(ergebnis["rueckfragen"])})
    return {"vorschlag": ergebnis}
