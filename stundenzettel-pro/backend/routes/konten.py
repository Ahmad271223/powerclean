"""Feiertage, Sollstunden, Stundenkonto (Überstunden mit Buchungen) und Urlaubskonto."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from auth import aktueller_nutzer, firma_laden, hat_rolle, jetzt_iso, rolle_noetig, schreibend
from db import db
from feiertage import BUNDESLAENDER, feiertage
from gemeinsam import neue_id
from konten import kontoverlauf, monatskonto, urlaubskonto
from models import BuchungIn
from protokoll import protokollieren

router = APIRouter(tags=["Konten"])


@router.get("/api/feiertage")
async def feiertage_lesen(jahr: int = Query(..., ge=2025, le=2100), user: dict = Depends(aktueller_nutzer)):
    firma = await firma_laden(user["firma_id"])
    land = firma.get("bundesland") or ""
    return {"jahr": jahr, "bundesland": land, "bundesland_name": BUNDESLAENDER.get(land, "nur bundesweite Feiertage"),
            "feiertage": feiertage(jahr, land), "bundeslaender": BUNDESLAENDER}


async def _nutzer(user: dict, user_id: str) -> dict:
    if user["id"] != user_id and user.get("role") != "inhaber":
        raise HTTPException(403, "Dafür fehlt die Berechtigung.")
    u = await db().users.find_one({"id": user_id, "firma_id": user["firma_id"]}, {"_id": 0, "pw_hash": 0, "einladung_token": 0})
    if not u:
        raise HTTPException(404, "Mitarbeiter nicht gefunden.")
    return u


async def _konto(user: dict, user_id: str, jahr: int, monat: int) -> dict:
    u = await _nutzer(user, user_id)
    firma = await firma_laden(user["firma_id"])
    verlauf = await kontoverlauf(firma, u, jahr, monat)
    urlaub = await urlaubskonto(firma, u, jahr)
    buchungen = [b async for b in db().zeitkonto.find({"firma_id": user["firma_id"], "user_id": user_id}, {"_id": 0}).sort("date", -1).limit(200)]
    aktuell = await monatskonto(firma, u, jahr, monat)
    return {"mitarbeiter": {"id": u["id"], "name": u.get("name"), "weekly_hours": u.get("weekly_hours") or 0, "vacation_days": u.get("vacation_days") or 0,
                            "workdays": u.get("workdays") or firma.get("workdays") or [0, 1, 2, 3, 4]},
            "monat": aktuell, "verlauf": verlauf, "urlaub": urlaub, "buchungen": buchungen}


@router.get("/api/mitarbeiter/{user_id}/konto")
async def konto(user_id: str, jahr: int = Query(..., ge=2025, le=2100), monat: int = Query(..., ge=1, le=12), user: dict = Depends(aktueller_nutzer)):
    return await _konto(user, user_id, jahr, monat)


@router.get("/api/konto/meins")
async def meins(user: dict = Depends(aktueller_nutzer)):
    heute = date.today()
    return await _konto(user, user["id"], heute.year, heute.month)


@router.post("/api/mitarbeiter/{user_id}/konto/buchungen")
async def buchen(user_id: str, body: BuchungIn, user: dict = Depends(schreibend("inhaber"))):
    u = await _nutzer(user, user_id)
    b = {"id": neue_id(), "firma_id": user["firma_id"], "user_id": user_id, "date": body.date, "minutes": body.minutes, "type": body.type,
         "note": (body.note or "").strip(), "created_by": user.get("name"), "created_at": jetzt_iso()}
    await db().zeitkonto.insert_one(dict(b))
    await protokollieren(user, "stundenkonto.buchung", u.get("name", ""), details={"minuten": body.minutes, "art": body.type, "datum": body.date})
    return {"buchung": b}


@router.delete("/api/konto/buchungen/{buchung_id}")
async def buchung_loeschen(buchung_id: str, user: dict = Depends(schreibend("inhaber"))):
    b = await db().zeitkonto.find_one({"id": buchung_id, "firma_id": user["firma_id"]}, {"_id": 0})
    if not b:
        raise HTTPException(404, "Buchung nicht gefunden.")
    await db().zeitkonto.delete_one({"id": buchung_id})
    await protokollieren(user, "stundenkonto.buchung_geloescht", b.get("user_id", ""), details={"minuten": b.get("minutes"), "art": b.get("type")})
    return {"ok": True}


@router.get("/api/konto/uebersicht")
async def uebersicht(jahr: int = Query(..., ge=2025, le=2100), monat: int = Query(..., ge=1, le=12), user: dict = Depends(rolle_noetig("inhaber"))):
    """Alle aktiven Mitarbeiter: Soll, Ist, Saldo des Monats, kumulierter Saldo, Resturlaub."""
    firma = await firma_laden(user["firma_id"])
    aus = []
    async for u in db().users.find({"firma_id": user["firma_id"], "active": True}, {"_id": 0, "pw_hash": 0, "einladung_token": 0}):
        m = await monatskonto(firma, u, jahr, monat)
        v = await kontoverlauf(firma, u, jahr, monat)
        ul = await urlaubskonto(firma, u, jahr)
        aus.append({"user_id": u["id"], "name": u.get("name"), "personalnummer": u.get("personalnummer", ""), "weekly_hours": u.get("weekly_hours") or 0,
                    "soll_minuten": m["soll_minuten"], "ist_minuten": m["ist_minuten"], "saldo_monat": m["saldo_minuten"],
                    "saldo_gesamt": v["saldo_minuten"], "resturlaub": ul["rest"], "urlaub_genommen": ul["genommen"]})
    aus.sort(key=lambda r: r["name"] or "")
    return {"jahr": jahr, "monat": monat, "zeilen": aus}
