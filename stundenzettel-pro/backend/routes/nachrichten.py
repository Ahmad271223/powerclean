"""Nachrichten-Routen (Stufe G): Chats öffnen, lesen, schreiben, Anhänge – hinter dem Feature-Flag `chat`.
Jede Nachricht wird gespeichert; die E-Mail-Ankündigung übernimmt der Dienst in `nachrichten.py` getrennt vom Senden."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

import nachrichten as nm
from auth import aktueller_nutzer, hat_rolle, jetzt_iso, schreibend
from dateien import datei_speichern
from db import db
from features import feature_noetig
from gemeinsam import foto_fuer_nutzer, projekt_laden
from models import ChatOeffnenIn, NachrichtIn, ProjektChatIn
from protokoll import protokollieren

router = APIRouter(tags=["Nachrichten"], dependencies=[feature_noetig("chat")])


@router.get("/api/chats")
async def chats(user: dict = Depends(aktueller_nutzer)):
    liste = await nm.meine_chats(user)
    return {"chats": liste, "ungelesen": sum(c["ungelesen"] for c in liste), "arten": nm.ARTEN}


@router.get("/api/chats/ungelesen")
async def ungelesen(user: dict = Depends(aktueller_nutzer)):
    return {"ungelesen": await nm.ungelesen_gesamt(user)}


@router.post("/api/chats/oeffnen")
async def oeffnen(body: ChatOeffnenIn, user: dict = Depends(schreibend("mitarbeiter"))):
    chat = await nm.chat_oeffnen(user, body.art, project_id=body.project_id, ausschreibung_id=body.ausschreibung_id, bieter_firma_id=body.bieter_firma_id,
                                 firma_id=body.firma_id, aufgabe_id=body.aufgabe_id)
    z = await nm.chat_zugang(user, chat)
    return {"chat": {**chat, "rolle": z["rolle"]}}


@router.get("/api/chats/{chat_id}")
async def lesen(chat_id: str, user: dict = Depends(aktueller_nutzer)):
    chat, z = await nm.chat_laden(user, chat_id)
    return {"chat": {**chat, "rolle": z["rolle"], "schreiben": z["schreiben"]}, "nachrichten": await nm.nachrichten_lesen(user, chat)}


@router.post("/api/chats/{chat_id}/nachrichten")
async def schreiben(chat_id: str, body: NachrichtIn, user: dict = Depends(schreibend("mitarbeiter"))):
    chat, z = await nm.chat_laden(user, chat_id)
    if not z["schreiben"]:
        raise HTTPException(403, "In diesem Chat darfst du nur lesen.")
    n = await nm.senden(user, chat, body.text)
    return {"nachricht": {**n, "eigene": True}}


@router.post("/api/chats/{chat_id}/anhaenge")
async def anhang(chat_id: str, datei: UploadFile = File(...), text: str = Form(""), user: dict = Depends(schreibend("mitarbeiter"))):
    """Datei als Nachricht: wird als Dokument mit scope `chat` abgelegt – Zugriff nur für Chat-Teilnehmer."""
    chat, z = await nm.chat_laden(user, chat_id)
    if not z["schreiben"]:
        raise HTTPException(403, "In diesem Chat darfst du nur lesen.")
    meta = await datei_speichern(user["firma_id"], datei, user["id"])
    doc = {**meta, "firma_id": user["firma_id"], "scope": "chat", "ref_id": chat["id"], "category": "Nachricht", "note": text[:500], "date": jetzt_iso()[:10],
           "uploaded_by": user["id"], "uploaded_by_name": user.get("name"), "created_at": jetzt_iso()}
    await db().documents.insert_one(dict(doc))
    doc.pop("path", None)
    n = await nm.senden(user, chat, text, anhaenge=[{"id": doc["id"], "filename": doc["filename"], "mime": doc["mime"], "size": doc["size"]}])
    return {"nachricht": {**n, "eigene": True}, "dokument": foto_fuer_nutzer(user, doc)}


@router.put("/api/projekte/{project_id}/chat")
async def projekt_chat_einstellen(project_id: str, body: ProjektChatIn, user: dict = Depends(schreibend("buero"))):
    """Inhaber/Büro schaltet den internen Projektchat je Projekt ein oder aus (bestehende Nachrichten bleiben erhalten)."""
    p = await projekt_laden(user, project_id, schreiben=True)
    await db().projects.update_one({"id": p["id"]}, {"$set": {"chat_intern": bool(body.chat_intern), "updated_at": jetzt_iso()}})
    await protokollieren(user, "projekt.chat", p.get("name", ""), details={"chat_intern": bool(body.chat_intern)})
    return {"chat_intern": bool(body.chat_intern)}


async def dokument_zugang(user: dict, chat_id: str) -> None:
    """Dateizugriff für scope `chat`: dieselben Regeln wie der Chat selbst."""
    await nm.chat_laden(user, chat_id)
