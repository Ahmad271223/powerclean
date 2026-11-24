"""Geräte für Push-Nachrichten (iPhone/Android): Die App meldet nach der Anmeldung ihr Push-Token, beim Abmelden meldet sie es ab."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

import push
from auth import aktueller_nutzer
from db import db
from protokoll import protokollieren

router = APIRouter(prefix="/api/geraete", tags=["Push-Geräte"])


class GeraetIn(BaseModel):
    plattform: str = Field(pattern="^(ios|android)$")
    token: str = Field(min_length=16, max_length=4096, pattern=r"^[A-Za-z0-9_:\-.]+$")
    app_version: str = Field(default="", max_length=40)


class GeraetAbIn(BaseModel):
    token: str = Field(min_length=16, max_length=4096)


@router.post("")
async def registrieren(body: GeraetIn, user: dict = Depends(aktueller_nutzer)):
    g = await push.geraet_registrieren(user, body.plattform, body.token, body.app_version)
    await protokollieren(user, "geraet.registriert", body.plattform)
    return {"ok": True, "geraet_id": g["id"], "push": push.stand()}


@router.post("/abmelden")
async def abmelden(body: GeraetAbIn, user: dict = Depends(aktueller_nutzer)):
    """Beim Abmelden in der App: dieses Gerät bekommt keine Nachrichten mehr für dieses Konto."""
    return {"ok": await push.geraet_abmelden(user, body.token)}


@router.get("")
async def meine(user: dict = Depends(aktueller_nutzer)):
    """Eigene Geräte (ohne Token) und ob der Server Push zustellen kann."""
    liste = [{"id": g["id"], "plattform": g["plattform"], "aktiv": g.get("aktiv", False), "updated_at": g.get("updated_at")}
             async for g in db().geraete.find({"user_id": user["id"]}, {"_id": 0, "token": 0}).sort("updated_at", -1)]
    return {"geraete": liste, "push": push.stand()}
