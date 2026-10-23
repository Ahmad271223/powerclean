"""Registrierung (Firma + Inhaber), Anmeldung, Einladungen, Passwort."""
from __future__ import annotations

import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException

import config
from auth import (aktueller_nutzer, firma_laden, jetzt, jetzt_iso, nutzer_oeffentlich, passwort_hash,
                  passwort_pruefen, passwort_regel, plan_status, token_erzeugen)
from db import db
from gemeinsam import FIRMA_DEFAULTS, firma_oeffentlich, neue_id
from models import EinladungAnnehmenIn, LoginIn, PasswortIn, RegistrierungIn
from protokoll import protokollieren

router = APIRouter(prefix="/api/auth", tags=["Anmeldung"])


def _antwort(user: dict, firma: dict) -> dict:
    return {"token": token_erzeugen(user), "user": nutzer_oeffentlich(user),
            "firma": firma_oeffentlich(firma, user), "plan": plan_status(firma)}


@router.post("/registrieren")
async def registrieren(body: RegistrierungIn):
    email = body.email.lower().strip()
    if await db().users.find_one({"email": email}):
        raise HTTPException(409, "Für diese E-Mail-Adresse gibt es schon ein Konto. Bitte anmelden.")
    passwort_regel(body.password)
    firma = {**FIRMA_DEFAULTS, "id": neue_id(), "name": body.firma_name.strip(), "owner": body.name.strip(),
             "email": email, "created_at": jetzt_iso(),
             "plan": {"status": "test", "test_bis": (jetzt() + timedelta(days=config.TEST_TAGE)).isoformat(),
                      "nutzer_max": 0}}
    user = {"id": neue_id(), "firma_id": firma["id"], "email": email, "name": body.name.strip(), "role": "inhaber",
            "personalnummer": "1", "phone": "", "notes": "", "active": True, "pw_hash": passwort_hash(body.password),
            "created_at": jetzt_iso()}
    await db().firmen.insert_one(dict(firma))
    await db().users.insert_one(dict(user))
    await protokollieren(user, "firma.registriert", firma["name"])
    return _antwort(user, firma)


@router.post("/login")
async def login(body: LoginIn):
    email = body.email.lower().strip()
    u = await db().users.find_one({"email": email}, {"_id": 0})
    if not u or not u.get("pw_hash") or not passwort_pruefen(body.password, u.get("pw_hash")):
        raise HTTPException(401, "E-Mail oder Passwort stimmt nicht.")
    if not u.get("active", True):
        raise HTTPException(401, "Dieses Konto ist deaktiviert.")
    firma = await firma_laden(u["firma_id"])
    await db().users.update_one({"id": u["id"]}, {"$set": {"last_login_at": jetzt_iso()}})
    await protokollieren(u, "anmeldung")
    return _antwort(u, firma)


@router.get("/ich")
async def ich(user: dict = Depends(aktueller_nutzer)):
    firma = await firma_laden(user["firma_id"])
    return {"user": nutzer_oeffentlich(user), "firma": firma_oeffentlich(firma, user), "plan": plan_status(firma)}


async def _einladung(token: str) -> dict:
    u = await db().users.find_one({"einladung_token": token}, {"_id": 0})
    if not u or not u.get("active", True):
        raise HTTPException(404, "Diese Einladung ist ungültig.")
    bis = u.get("einladung_bis") or ""
    if bis and bis < jetzt_iso():
        raise HTTPException(410, "Diese Einladung ist abgelaufen. Bitte eine neue anfordern.")
    return u


@router.get("/einladung/{token}")
async def einladung_lesen(token: str):
    u = await _einladung(token)
    firma = await firma_laden(u["firma_id"])
    return {"name": u.get("name"), "email": u.get("email"), "firma_name": firma.get("name"), "rolle": u.get("role")}


@router.post("/einladung/{token}")
async def einladung_annehmen(token: str, body: EinladungAnnehmenIn):
    u = await _einladung(token)
    passwort_regel(body.password)
    await db().users.update_one({"id": u["id"]}, {"$set": {"pw_hash": passwort_hash(body.password), "accepted_at": jetzt_iso()},
                                                  "$unset": {"einladung_token": "", "einladung_bis": ""}})
    u = await db().users.find_one({"id": u["id"]}, {"_id": 0})
    firma = await firma_laden(u["firma_id"])
    await protokollieren(u, "einladung.angenommen")
    return _antwort(u, firma)


@router.put("/passwort")
async def passwort_aendern(body: PasswortIn, user: dict = Depends(aktueller_nutzer)):
    if not passwort_pruefen(body.alt, user.get("pw_hash")):
        raise HTTPException(400, "Das bisherige Passwort stimmt nicht.")
    passwort_regel(body.neu)
    await db().users.update_one({"id": user["id"]}, {"$set": {"pw_hash": passwort_hash(body.neu)}})
    await protokollieren(user, "passwort.geaendert")
    return {"ok": True}


def einladungs_token() -> tuple[str, str]:
    return secrets.token_urlsafe(24), (jetzt() + timedelta(days=14)).isoformat()
