"""Nachrichten (Stufe G): Projektchat intern, Projektchat mit Partnerfirmen, privater Bieterchat, Kontaktanfrage zwischen Firmen,
Aufgabenkommunikation. Jede Nachricht wird zuerst dauerhaft gespeichert; ein getrennter Dienst kündigt ungelesene Nachrichten per E-Mail an
(gesammelt je Chat, einmal je Nachricht, mit Nachweis im E-Mail-Ausgang). Eine E-Mail ist kein Zustellnachweis.

Regeln: Bieter A liest nie Nachrichten von Bieter B (ein Chat je Bieterfirma). Der interne Projektchat gehört der eigenen Firma; der Chef kann
ihn je Projekt sperren (`projects.chat_intern = False`). Der Partnerchat eines Plattform-Projekts ist nur für die Projektleitung des Eigentümers
und die Leitung beteiligter Firmen offen – Mitarbeiter sehen nur, was ihnen zugeteilt ist (Aufgabenchats). Anhänge haben die Rechte des Chats.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException

from auth import hat_rolle, jetzt_iso
from db import db
from gemeinsam import neue_id, projekt_leitung, projekt_normalisieren, projekt_sichtbar

ARTEN = {"projekt_intern": "Projektchat (intern)", "projekt_gu": "Projektchat mit Partnern", "bieter": "Bieterchat", "kontakt": "Kontaktanfrage", "aufgabe": "Aufgabe"}
WARTEZEIT_MINUTEN = 2   # ungelesene Nachrichten werden nach dieser Zeit per E-Mail angekündigt


def _jetzt() -> datetime:
    return datetime.now(timezone.utc)


async def _projekt(project_id: str) -> dict:
    p = await db().projects.find_one({"id": project_id}, {"_id": 0})
    if not p:
        raise HTTPException(404, "Projekt nicht gefunden.")
    return projekt_normalisieren(p)


# ---------------------------------------------------------------- Zugang

async def chat_zugang(user: dict, chat: dict) -> dict:
    """Zugang zu einem Chat (404 ohne Zugang): liefert rolle und ob geschrieben werden darf."""
    from plattform import aufgabe_laden, partner_leitung, zugang
    art = chat.get("art")
    if art == "projekt_intern":
        if chat.get("firma_id") != user["firma_id"]:
            raise HTTPException(404, "Chat nicht gefunden.")
        p = await _projekt(chat["project_id"])
        if not projekt_sichtbar(user, p):
            raise HTTPException(404, "Chat nicht gefunden.")
        if not hat_rolle(user, "buero") and p.get("chat_intern") is False:
            raise HTTPException(404, "Chat nicht gefunden.")
        return {"rolle": "buero" if hat_rolle(user, "buero") else "mitarbeiter", "schreiben": True, "projekt": p}
    if art == "projekt_gu":
        z = await zugang(user, chat["project_id"])
        if not ((z["eigentuemer"] and z["leitung"]) or (not z["eigentuemer"] and partner_leitung(z, user))):
            raise HTTPException(404, "Chat nicht gefunden.")
        return {"rolle": "leitung" if z["eigentuemer"] else "partner", "schreiben": True, "projekt": z["projekt"]}
    if art == "bieter":
        from ausschreibung import ausschreibung_zugang
        zg = await ausschreibung_zugang(user, chat["ausschreibung_id"])
        if zg["rolle"] == "leitung":
            return {"rolle": "leitung", "schreiben": True, "ausschreibung": zg["ausschreibung"]}
        if zg["rolle"] == "bieter" and chat.get("bieter_firma_id") == user["firma_id"]:
            return {"rolle": "bieter", "schreiben": True, "ausschreibung": zg["ausschreibung"]}
        raise HTTPException(404, "Chat nicht gefunden.")
    if art == "kontakt":
        if user["firma_id"] not in (chat.get("firma_ids") or []) or not hat_rolle(user, "buero"):
            raise HTTPException(404, "Chat nicht gefunden.")
        return {"rolle": "buero", "schreiben": True}
    if art == "aufgabe":
        a, z = await aufgabe_laden(user, chat["aufgabe_id"])
        return {"rolle": "leitung" if (z["eigentuemer"] and z["leitung"]) else "firma", "schreiben": True, "aufgabe": a}
    raise HTTPException(404, "Chat nicht gefunden.")


async def chat_laden(user: dict, chat_id: str) -> tuple[dict, dict]:
    chat = await db().chats.find_one({"id": chat_id}, {"_id": 0})
    if not chat:
        raise HTTPException(404, "Chat nicht gefunden.")
    try:
        return chat, await chat_zugang(user, chat)
    except HTTPException as exc:
        raise HTTPException(404, "Chat nicht gefunden.") from exc   # auch 403 der Projekt-/Ausschreibungsprüfung verrät nichts über fremde Chats


# ---------------------------------------------------------------- Chats finden oder anlegen

async def _firma_name(firma_id: str) -> str:
    f = await db().firmen.find_one({"id": firma_id}, {"_id": 0, "name": 1})
    return (f or {}).get("name") or "Firma"


async def chat_oeffnen(user: dict, art: str, project_id: Optional[str] = None, ausschreibung_id: Optional[str] = None, bieter_firma_id: Optional[str] = None,
                       firma_id: Optional[str] = None, aufgabe_id: Optional[str] = None) -> dict:
    """Den passenden Chat finden oder anlegen – nur, wenn der Nutzer dort Zugang hat."""
    from plattform import aufgabe_laden, partner_leitung, zugang
    if art == "projekt_intern":
        if not project_id:
            raise HTTPException(400, "Projekt fehlt.")
        p = await _projekt(project_id)
        if p["firma_id"] != user["firma_id"] or not projekt_sichtbar(user, p):
            raise HTTPException(404, "Projekt nicht gefunden.")
        if not hat_rolle(user, "buero") and p.get("chat_intern") is False:
            raise HTTPException(403, "Der Projektchat ist für dieses Projekt vom Büro geschlossen.")
        schluessel = {"art": art, "project_id": p["id"], "firma_id": user["firma_id"]}
        neu = {**schluessel, "titel": f"{p['name']} – intern", "firma_ids": [user["firma_id"]]}
    elif art == "projekt_gu":
        if not project_id:
            raise HTTPException(400, "Projekt fehlt.")
        z = await zugang(user, project_id)
        if not ((z["eigentuemer"] and z["leitung"]) or (not z["eigentuemer"] and partner_leitung(z, user))):
            raise HTTPException(403, "Den Partnerchat führen die Projektleitung des Eigentümers und die Leitung beteiligter Firmen.")
        p = z["projekt"]
        schluessel = {"art": art, "project_id": p["id"]}
        neu = {**schluessel, "titel": f"{p['name']} – Partner", "firma_id": p["firma_id"], "firma_ids": [p["firma_id"]]}
    elif art == "bieter":
        from ausschreibung import ausschreibung_zugang
        if not ausschreibung_id:
            raise HTTPException(400, "Ausschreibung fehlt.")
        zg = await ausschreibung_zugang(user, ausschreibung_id)
        a = zg["ausschreibung"]
        if zg["rolle"] == "bieter":
            bieter_firma_id = user["firma_id"]
        elif not bieter_firma_id:
            raise HTTPException(400, "Bieterfirma fehlt.")
        schluessel = {"art": art, "ausschreibung_id": a["id"], "bieter_firma_id": bieter_firma_id}
        if zg["rolle"] == "leitung" and not await db().chats.find_one(schluessel, {"_id": 0, "id": 1}):
            # Die Leitung eröffnet einen Bieterchat nur mit Firmen, die eingeladen sind oder ein Angebot abgegeben haben
            beteiligt = await db().angebote.find_one({"ausschreibung_id": a["id"], "firma_id": bieter_firma_id}, {"_id": 0, "id": 1}) or \
                await db().ausschreibung_einladungen.find_one({"ausschreibung_id": a["id"], "firma_id": bieter_firma_id}, {"_id": 0, "id": 1})
            if not beteiligt:
                raise HTTPException(404, "Diese Firma ist an der Ausschreibung nicht beteiligt.")
        neu = {**schluessel, "titel": f"{a.get('titel')} – {await _firma_name(bieter_firma_id)}", "firma_id": a["firma_id"], "firma_ids": sorted({a["firma_id"], bieter_firma_id}), "project_id": a.get("project_id")}
    elif art == "kontakt":
        if not hat_rolle(user, "buero"):
            raise HTTPException(403, "Kontaktanfragen stellt das Büro oder der Inhaber.")
        if not firma_id or firma_id == user["firma_id"]:
            raise HTTPException(400, "Zielfirma fehlt.")
        ziel = await db().firmen.find_one({"id": firma_id}, {"_id": 0, "id": 1, "name": 1, "verzeichnis": 1})
        bestehend = await db().chats.find_one({"art": "kontakt", "firma_ids": {"$all": sorted([user["firma_id"], firma_id])}}, {"_id": 0})
        if not ziel or (not (ziel.get("verzeichnis") or {}).get("sichtbar") and not bestehend):
            raise HTTPException(404, "Firma nicht im Verzeichnis.")
        schluessel = {"art": art, "firma_ids": sorted([user["firma_id"], firma_id])}
        neu = {**schluessel, "titel": f"Kontakt: {await _firma_name(user['firma_id'])} ↔ {ziel['name']}", "firma_id": user["firma_id"]}
    elif art == "aufgabe":
        if not aufgabe_id:
            raise HTTPException(400, "Aufgabe fehlt.")
        a, z = await aufgabe_laden(user, aufgabe_id)
        schluessel = {"art": art, "aufgabe_id": a["id"]}
        neu = {**schluessel, "titel": f"Aufgabe: {a.get('titel')}", "firma_id": a.get("owner_firma_id"), "firma_ids": sorted({a.get("owner_firma_id"), a.get("firma_id")} - {None}), "project_id": a.get("project_id")}
    else:
        raise HTTPException(400, "Unbekannte Chat-Art.")
    chat = await db().chats.find_one(schluessel, {"_id": 0})
    if chat:
        return chat
    chat = {**neu, "id": neue_id(), "art_name": ARTEN[art], "erstellt_von": user["id"], "erstellt_von_name": user.get("name"), "created_at": jetzt_iso(),
            "letzte_nachricht_at": None, "letzter_text": "", "nachrichten_anzahl": 0}
    await db().chats.insert_one(dict(chat))
    return chat


async def meine_chats(user: dict) -> list[dict]:
    """Alle Chats, in denen der Nutzer Zugang hat – mit ungelesenen Nachrichten (Zugang wird je Chat geprüft, nie nur über firma_id)."""
    kandidaten = []
    # Partnerchats von Projekten, an denen die Firma beteiligt ist, gehören dazu – auch wenn sie noch nie geschrieben hat
    beteiligt = [b["project_id"] async for b in db().beteiligungen.find({"firma_id": user["firma_id"], "status": "aktiv"}, {"_id": 0, "project_id": 1})]
    filt = {"$or": [{"firma_ids": user["firma_id"]}, {"firma_id": user["firma_id"]}, {"art": "projekt_gu", "project_id": {"$in": beteiligt}}]}
    async for c in db().chats.find(filt, {"_id": 0}).sort([("letzte_nachricht_at", -1), ("created_at", -1)]).limit(500):
        kandidaten.append(c)
    aus = []
    for c in kandidaten:
        try:
            z = await chat_zugang(user, c)
        except HTTPException:
            continue
        ungelesen = await db().nachrichten.count_documents({"chat_id": c["id"], "user_id": {"$ne": user["id"]}, "gelesen_von": {"$ne": user["id"]}})
        aus.append({**c, "rolle": z["rolle"], "ungelesen": ungelesen})
    return aus


async def ungelesen_gesamt(user: dict) -> int:
    return sum(c["ungelesen"] for c in await meine_chats(user))


# ---------------------------------------------------------------- Teilnehmer (für Mitteilungen und E-Mail-Ankündigung)

async def _leitung_ids(p: dict, firma_id: Optional[str] = None) -> list[str]:
    """Projektleitung einer Firma wie `projekt_leitung`: Büro/Inhaber, ausdrückliche Leiter oder sonst zugewiesene Vorarbeiter."""
    firma_id = firma_id or p["firma_id"]
    nutzer = set()
    async for u in db().users.find({"firma_id": firma_id, "active": True, "role": {"$in": ["buero", "inhaber"]}}, {"_id": 0, "id": 1}):
        nutzer.add(u["id"])
    if p.get("leiter_ids"):
        nutzer |= set(p["leiter_ids"])
    else:
        async for u in db().users.find({"firma_id": firma_id, "active": True, "role": "vorarbeiter", "id": {"$in": p.get("employee_ids") or []}}, {"_id": 0, "id": 1}):
            nutzer.add(u["id"])
    return sorted(nutzer)

async def teilnehmer(chat: dict) -> list[dict]:
    """Wer eine neue Nachricht erfahren soll: je Firma Rolle/Nutzerliste – ohne die Rechte des Chats aufzuweichen."""
    art = chat.get("art")
    if art == "projekt_intern":
        p = await _projekt(chat["project_id"])
        nutzer = set(p.get("employee_ids") or []) | set(p.get("leiter_ids") or [])
        async for u in db().users.find({"firma_id": p["firma_id"], "active": True, "role": {"$in": ["buero", "inhaber"]}}, {"_id": 0, "id": 1}):
            nutzer.add(u["id"])
        return [{"firma_id": p["firma_id"], "user_ids": sorted(nutzer), "mindestens": "mitarbeiter"}]
    if art == "projekt_gu":
        p = await _projekt(chat["project_id"])
        aus = [{"firma_id": p["firma_id"], "user_ids": await _leitung_ids(p), "mindestens": "mitarbeiter"}]
        async for b in db().beteiligungen.find({"project_id": p["id"], "status": "aktiv"}, {"_id": 0, "firma_id": 1, "lokales_project_id": 1}):
            lokal = await db().projects.find_one({"id": b.get("lokales_project_id") or ""}, {"_id": 0}) if b.get("lokales_project_id") else None
            aus.append({"firma_id": b["firma_id"], "user_ids": await _leitung_ids(projekt_normalisieren(lokal), b["firma_id"]) if lokal else None, "mindestens": "mitarbeiter" if lokal else "buero"})
        return aus
    if art == "bieter":
        return [{"firma_id": chat["firma_id"], "user_ids": None, "mindestens": "buero"}, {"firma_id": chat["bieter_firma_id"], "user_ids": None, "mindestens": "buero"}]
    if art == "kontakt":
        return [{"firma_id": f, "user_ids": None, "mindestens": "buero"} for f in chat.get("firma_ids") or []]
    if art == "aufgabe":
        a = await db().aufgaben.find_one({"id": chat["aufgabe_id"]}, {"_id": 0})
        if not a:
            return []
        aus = [{"firma_id": a.get("owner_firma_id"), "user_ids": None, "mindestens": "buero"}]
        if a.get("firma_id"):
            nutzer = set(a.get("mitarbeiter_ids") or [])
            if a.get("vorarbeiter_user_id"):
                nutzer.add(a["vorarbeiter_user_id"])
            async for u in db().users.find({"firma_id": a["firma_id"], "active": True, "role": {"$in": ["buero", "inhaber"]}}, {"_id": 0, "id": 1}):
                nutzer.add(u["id"])
            aus.append({"firma_id": a["firma_id"], "user_ids": sorted(nutzer), "mindestens": "mitarbeiter"})
        return aus
    return []


# ---------------------------------------------------------------- Nachrichten

async def senden(user: dict, chat: dict, text: str, anhaenge: Optional[list[dict]] = None) -> dict:
    from plattform import benachrichtigen
    text = (text or "").strip()[:4000]
    if not text and not anhaenge:
        raise HTTPException(400, "Nachricht ist leer.")
    n = {"id": neue_id(), "chat_id": chat["id"], "firma_id": user["firma_id"], "firma_name": await _firma_name(user["firma_id"]), "user_id": user["id"], "user_name": user.get("name"),
         "text": text, "anhaenge": anhaenge or [], "gelesen_von": [user["id"]], "angekuendigt_at": None, "created_at": jetzt_iso()}
    await db().nachrichten.insert_one(dict(n))
    await db().chats.update_one({"id": chat["id"]}, {"$set": {"letzte_nachricht_at": n["created_at"], "letzter_text": (text or "Anhang")[:120], "letzter_von": user.get("name")},
                                                     "$inc": {"nachrichten_anzahl": 1}, "$addToSet": {"firma_ids": user["firma_id"]}})
    kurz = f"{user.get('name')}: {(text or 'Anhang')[:80]}"
    for t in await teilnehmer(chat):
        ids = t.get("user_ids")
        if ids is not None:
            ids = [i for i in ids if i != user["id"]]
            if not ids:
                continue
        await benachrichtigen(t["firma_id"], "nachricht", f"{chat.get('titel')} – {kurz}", f"/nachrichten?chat={chat['id']}", user_ids=ids, mindestens=t.get("mindestens") or "buero")
    return n


async def nachrichten_lesen(user: dict, chat: dict, limit: int = 200) -> list[dict]:
    aus = [n async for n in db().nachrichten.find({"chat_id": chat["id"]}, {"_id": 0}).sort("created_at", 1).limit(limit)]
    ungelesen = [n["id"] for n in aus if user["id"] not in (n.get("gelesen_von") or [])]
    if ungelesen:
        await db().nachrichten.update_many({"id": {"$in": ungelesen}}, {"$addToSet": {"gelesen_von": user["id"]}})
    return [{**n, "gelesen_von": (n.get("gelesen_von") or []) + ([user["id"]] if n["id"] in ungelesen else []), "eigene": n.get("user_id") == user["id"]} for n in aus]


# ---------------------------------------------------------------- E-Mail-Ankündigung (getrennter Dienst)

async def einmal_pruefen(jetzt: Optional[datetime] = None, wartezeit_minuten: int = WARTEZEIT_MINUTEN) -> int:
    """Ungelesene Nachrichten, die älter als die Wartezeit sind, je Chat und Empfängerfirma gesammelt per E-Mail ankündigen – einmal je Nachricht."""
    import mail
    jetzt = jetzt or _jetzt()
    grenze = (jetzt - timedelta(minutes=wartezeit_minuten)).isoformat()
    offen: dict[str, list[dict]] = {}
    async for n in db().nachrichten.find({"angekuendigt_at": None, "created_at": {"$lte": grenze}}, {"_id": 0}).sort("created_at", 1).limit(500):
        offen.setdefault(n["chat_id"], []).append(n)
    versendet = 0
    for chat_id, liste in offen.items():
        chat = await db().chats.find_one({"id": chat_id}, {"_id": 0})
        if not chat:
            continue
        link = mail.link(f"/nachrichten?chat={chat_id}")
        for t in await teilnehmer(chat):
            for u in await _empfaenger(t):
                # nur fremde, vom Empfänger noch nicht gelesene Nachrichten – eine Mail je Chat und Person
                ns = [n for n in liste if n.get("user_id") != u["id"] and u["id"] not in (n.get("gelesen_von") or [])]
                if not ns:
                    continue
                zeilen = "\n".join(f"– {n.get('user_name')} ({n.get('firma_name')}): {(n.get('text') or 'Anhang')[:160]}" for n in ns[-5:])
                text = f"Neue Nachricht{'en' if len(ns) > 1 else ''} in „{chat.get('titel')}“:\n\n{zeilen}\n\nAntworten in Stundenzettel Pro: {link}"
                if await mail.senden(t["firma_id"], u["email"], f"{len(ns)} neue Nachricht{'en' if len(ns) > 1 else ''}: {chat.get('titel')}", text, art="nachricht", ref_id=chat_id, project_id=chat.get("project_id") or ""):
                    versendet += 1
        await db().nachrichten.update_many({"id": {"$in": [n["id"] for n in liste]}}, {"$set": {"angekuendigt_at": jetzt_iso()}})
    return versendet


async def _empfaenger(t: dict) -> list[dict]:
    """Nutzer einer Teilnehmergruppe mit E-Mail-Adresse – Firmen- und Nutzerabschaltung der Benachrichtigungen wird beachtet."""
    from auth import ROLLEN
    f = await db().firmen.find_one({"id": t["firma_id"]}, {"_id": 0, "email_benachrichtigungen": 1})
    if f is None or f.get("email_benachrichtigungen") is False:
        return []
    filt: dict = {"firma_id": t["firma_id"], "active": True}
    if t.get("user_ids") is not None:
        filt["id"] = {"$in": t["user_ids"]}
    stufe = ROLLEN.get(t.get("mindestens") or "buero", 3)
    aus = []
    async for u in db().users.find(filt, {"_id": 0, "id": 1, "email": 1, "role": 1, "email_benachrichtigungen": 1}):
        adresse = (u.get("email") or "").lower()
        if u.get("email_benachrichtigungen") is False or ROLLEN.get(u.get("role"), 0) < stufe or "@" not in adresse or adresse.endswith("@konto.geloescht"):
            continue
        aus.append({"id": u["id"], "email": adresse})
    return aus


async def dienst(intervall: int = 60) -> None:
    while True:
        try:
            await einmal_pruefen()
        except Exception:  # noqa: BLE001 – der Dienst darf nie sterben
            pass
        await asyncio.sleep(intervall)
