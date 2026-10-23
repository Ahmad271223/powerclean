"""Monatsabschluss: abgeschlossene Monate sind für alle gesperrt (Bearbeitungssperre), das Büro kann wieder öffnen."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from auth import jetzt_iso, rolle_noetig, schreibend
from db import db
from gemeinsam import neue_id
from models import AbschlussIn
from protokoll import protokollieren

router = APIRouter(prefix="/api/abschluss", tags=["Monatsabschluss"])


@router.get("")
async def liste(jahr: Optional[int] = Query(None, ge=2025, le=2100), user: dict = Depends(rolle_noetig("buero"))):
    filt = {"firma_id": user["firma_id"]}
    if jahr:
        filt["year"] = jahr
    return {"abschluesse": [a async for a in db().abschluesse.find(filt, {"_id": 0}).sort([("year", -1), ("month", -1)])]}


@router.post("")
async def abschliessen(body: AbschlussIn, user: dict = Depends(schreibend("buero"))):
    if await db().abschluesse.find_one({"firma_id": user["firma_id"], "year": body.year, "month": body.month}):
        raise HTTPException(400, "Dieser Monat ist schon abgeschlossen.")
    offen = await db().stempel.count_documents({"firma_id": user["firma_id"]})
    a = {"id": neue_id(), "firma_id": user["firma_id"], "year": body.year, "month": body.month, "closed_by": user.get("name"),
         "closed_at": jetzt_iso()}
    await db().abschluesse.insert_one(dict(a))
    n = await db().entries.count_documents({"firma_id": user["firma_id"], "date": {"$gte": f"{body.year}-{body.month:02d}-01", "$lte": f"{body.year}-{body.month:02d}-31"}})
    await protokollieren(user, "monat.abgeschlossen", f"{body.month:02d}/{body.year}", details={"eintraege": n, "laufende_stempelungen": offen})
    return {"abschluss": a, "eintraege": n}


@router.delete("/{jahr}/{monat}")
async def oeffnen(jahr: int, monat: int, user: dict = Depends(schreibend("buero"))):
    r = await db().abschluesse.delete_one({"firma_id": user["firma_id"], "year": jahr, "month": monat})
    if not r.deleted_count:
        raise HTTPException(404, "Dieser Monat ist nicht abgeschlossen.")
    await protokollieren(user, "monat.geoeffnet", f"{monat:02d}/{jahr}")
    return {"ok": True}
