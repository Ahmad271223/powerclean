"""Offene Schnittstelle (nur lesend) mit API-Schlüssel der Firma: Authorization: Bearer sz_…
Für Lohnbüro, Steuerberater oder eigene Auswertungen. Dokumentation unter /api/docs."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from auth import api_firma
from db import db
from gemeinsam import nutzernamen
from zeiten import datum_pruefen, eintrag_minuten

router = APIRouter(prefix="/api/v1", tags=["API v1 (Schlüssel)"])


def _bereich(von: str, bis: str) -> None:
    try:
        datum_pruefen(von)
        datum_pruefen(bis)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.get("/projekte")
async def projekte(archiviert: Optional[bool] = None, firma_id: str = Depends(api_firma)):
    filt = {"firma_id": firma_id}
    if archiviert is not None:
        filt["archived"] = archiviert
    aus = []
    async for p in db().projects.find(filt, {"_id": 0, "firma_id": 0}):
        aus.append(p)
    return {"projekte": aus}


@router.get("/kunden")
async def kunden(firma_id: str = Depends(api_firma)):
    return {"kunden": [k async for k in db().customers.find({"firma_id": firma_id}, {"_id": 0, "firma_id": 0})]}


@router.get("/mitarbeiter")
async def mitarbeiter(firma_id: str = Depends(api_firma)):
    felder = {"_id": 0, "id": 1, "name": 1, "email": 1, "role": 1, "personalnummer": 1, "active": 1, "weekly_hours": 1}
    return {"mitarbeiter": [u async for u in db().users.find({"firma_id": firma_id}, felder)]}


@router.get("/zeiten")
async def zeiten(von: str, bis: str, project_id: Optional[str] = None, user_id: Optional[str] = None,
                 limit: int = Query(5000, ge=1, le=50000), firma_id: str = Depends(api_firma)):
    _bereich(von, bis)
    filt = {"firma_id": firma_id, "date": {"$gte": von, "$lte": bis}}
    if project_id:
        filt["project_id"] = project_id
    if user_id:
        filt["user_id"] = user_id
    namen = await nutzernamen(firma_id)
    aus = []
    async for e in db().entries.find(filt, {"_id": 0, "firma_id": 0}).sort([("date", 1), ("start_time", 1)]).limit(limit):
        e["user_name"] = namen.get(e.get("user_id") or "", "")
        e["minutes_total"] = eintrag_minuten(e)
        aus.append(e)
    return {"zeiten": aus}


@router.get("/abwesenheiten")
async def abwesenheiten(von: str, bis: str, firma_id: str = Depends(api_firma)):
    _bereich(von, bis)
    namen = await nutzernamen(firma_id)
    aus = []
    async for a in db().absences.find({"firma_id": firma_id, "from_date": {"$lte": bis}, "to_date": {"$gte": von}}, {"_id": 0, "firma_id": 0}):
        a["user_name"] = namen.get(a.get("user_id"), "")
        aus.append(a)
    return {"abwesenheiten": aus}


@router.get("/rechnungen")
async def rechnungen(jahr: Optional[int] = Query(None, ge=2025, le=2100), firma_id: str = Depends(api_firma)):
    filt = {"firma_id": firma_id}
    if jahr:
        filt["year"] = jahr
    return {"rechnungen": [r async for r in db().invoices.find(filt, {"_id": 0, "firma_id": 0}).sort([("year", -1), ("seq", -1)])]}
