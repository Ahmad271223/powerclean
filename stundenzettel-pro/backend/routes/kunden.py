"""Kundenverwaltung (Auftraggeber mit Rechnungsadresse, § 13b-Kennzeichen)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from auth import jetzt_iso, rolle_noetig, schreibend
from db import db
from gemeinsam import kundenadresse, neue_id
from models import KundeIn
from protokoll import protokollieren

router = APIRouter(prefix="/api/kunden", tags=["Kunden"])


@router.get("")
async def liste(user: dict = Depends(rolle_noetig("buero"))):
    aus = []
    async for k in db().customers.find({"firma_id": user["firma_id"]}, {"_id": 0}).sort("name", 1):
        k["projekte"] = await db().projects.count_documents({"firma_id": user["firma_id"], "customer_id": k["id"]})
        aus.append(k)
    return {"kunden": aus}


@router.post("")
async def anlegen(body: KundeIn, user: dict = Depends(schreibend("buero"))):
    k = {**body.model_dump(), "id": neue_id(), "firma_id": user["firma_id"], "created_at": jetzt_iso()}
    k["name"] = k["name"].strip()
    await db().customers.insert_one(dict(k))
    await protokollieren(user, "kunde.angelegt", k["name"])
    return {"kunde": k}


@router.put("/{kunde_id}")
async def aendern(kunde_id: str, body: KundeIn, user: dict = Depends(schreibend("buero"))):
    k = await db().customers.find_one({"id": kunde_id, "firma_id": user["firma_id"]}, {"_id": 0})
    if not k:
        raise HTTPException(404, "Kunde nicht gefunden.")
    neu = {**k, **body.model_dump(), "updated_at": jetzt_iso()}
    neu["name"] = neu["name"].strip()
    await db().customers.update_one({"id": kunde_id}, {"$set": {kk: v for kk, v in neu.items() if kk != "id"}})
    # Projekte tragen Name/Adresse des Kunden als Kopie (für PDFs) — nachziehen
    await db().projects.update_many({"firma_id": user["firma_id"], "customer_id": kunde_id},
                                    {"$set": {"customer_name": neu["name"], "customer_address": kundenadresse(neu),
                                              "reverse_charge": bool(neu.get("reverse_charge"))}})
    await protokollieren(user, "kunde.geaendert", neu["name"])
    return {"kunde": neu}


@router.delete("/{kunde_id}")
async def loeschen(kunde_id: str, user: dict = Depends(schreibend("buero"))):
    k = await db().customers.find_one({"id": kunde_id, "firma_id": user["firma_id"]}, {"_id": 0})
    if not k:
        raise HTTPException(404, "Kunde nicht gefunden.")
    n = await db().projects.count_documents({"firma_id": user["firma_id"], "customer_id": kunde_id})
    if n:
        raise HTTPException(400, f"Der Kunde hat noch {n} Projekte. Bitte zuerst die Projekte einem anderen Kunden zuordnen.")
    await db().customers.delete_one({"id": kunde_id})
    await protokollieren(user, "kunde.geloescht", k.get("name", ""))
    return {"ok": True}
