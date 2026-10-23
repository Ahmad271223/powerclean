"""Leistungen (Unterhaltsreinigung, Grundreinigung, Glasreinigung …) mit eigenem Stundensatz."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from auth import aktueller_nutzer, jetzt_iso, schreibend
from db import db
from gemeinsam import neue_id
from models import LeistungIn
from protokoll import protokollieren

router = APIRouter(prefix="/api/leistungen", tags=["Leistungen"])


@router.get("")
async def liste(alle: bool = False, user: dict = Depends(aktueller_nutzer)):
    filt = {"firma_id": user["firma_id"]}
    if not alle:
        filt["active"] = True
    return {"leistungen": [s async for s in db().services.find(filt, {"_id": 0}).sort([("sort", 1), ("name", 1)])]}


@router.post("")
async def anlegen(body: LeistungIn, user: dict = Depends(schreibend("buero"))):
    s = {**body.model_dump(), "id": neue_id(), "firma_id": user["firma_id"], "created_at": jetzt_iso()}
    s["name"] = s["name"].strip()
    await db().services.insert_one(dict(s))
    await protokollieren(user, "leistung.angelegt", s["name"], details={"satz": s["hourly_rate"]})
    return {"leistung": s}


@router.put("/{leistung_id}")
async def aendern(leistung_id: str, body: LeistungIn, user: dict = Depends(schreibend("buero"))):
    s = await db().services.find_one({"id": leistung_id, "firma_id": user["firma_id"]}, {"_id": 0})
    if not s:
        raise HTTPException(404, "Leistung nicht gefunden.")
    neu = {**s, **body.model_dump(), "updated_at": jetzt_iso()}
    neu["name"] = neu["name"].strip()
    await db().services.update_one({"id": leistung_id}, {"$set": {k: v for k, v in neu.items() if k != "id"}})
    # Name am Eintrag nachziehen (der Satz bleibt der Stand zum Leistungszeitpunkt)
    await db().entries.update_many({"firma_id": user["firma_id"], "service_id": leistung_id}, {"$set": {"service_name": neu["name"]}})
    await protokollieren(user, "leistung.geaendert", neu["name"], details={"satz": neu["hourly_rate"], "aktiv": neu["active"]})
    return {"leistung": neu}


@router.delete("/{leistung_id}")
async def loeschen(leistung_id: str, user: dict = Depends(schreibend("buero"))):
    s = await db().services.find_one({"id": leistung_id, "firma_id": user["firma_id"]}, {"_id": 0})
    if not s:
        raise HTTPException(404, "Leistung nicht gefunden.")
    n = await db().entries.count_documents({"firma_id": user["firma_id"], "service_id": leistung_id})
    if n:
        await db().services.update_one({"id": leistung_id}, {"$set": {"active": False}})
        await protokollieren(user, "leistung.deaktiviert", s["name"], details={"eintraege": n})
        return {"ok": True, "deaktiviert": True, "hinweis": f"{n} Einträge nutzen diese Leistung – sie wurde deaktiviert statt gelöscht."}
    await db().services.delete_one({"id": leistung_id})
    await protokollieren(user, "leistung.geloescht", s["name"])
    return {"ok": True, "deaktiviert": False}
