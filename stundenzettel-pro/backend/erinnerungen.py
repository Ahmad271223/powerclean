"""Erinnerungen an den nächsten Arbeitstag: am Abend (Standard 18:00 Uhr Europe/Berlin, je Firma einstellbar) bekommt jede eingeplante
Person eine In-App-Mitteilung und – wenn die Firma es nicht abgeschaltet hat – eine E-Mail mit Projekt, Zeit, Adresse und Hinweisen.

Eindeutige Kennung je Einsatz und Version: nach einem Neustart oder bei mehreren Prozessen entsteht keine doppelte Erinnerung;
ändert sich der Plan (neue Version), kommt eine neue Erinnerung. Betriebssystem-Push gibt es noch nicht (keine APNs/FCM-Anbindung)."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Optional

import mail
from auth import jetzt_iso
from db import db
from zeiten import lokal_jetzt


def _uhrzeit(firma: dict) -> str:
    u = (firma.get("erinnerung") or {}).get("uhrzeit") or "18:00"
    return u if len(u) == 5 and u[2] == ":" else "18:00"


async def einmal_pruefen(jetzt: Optional[datetime] = None) -> int:
    """Alle Einsätze von morgen prüfen und fällige Erinnerungen genau einmal anlegen. Gibt die Anzahl neuer Erinnerungen zurück."""
    jetzt = jetzt or lokal_jetzt()
    morgen = (jetzt.date() + timedelta(days=1)).isoformat()
    firmen: dict = {}
    projekte: dict = {}
    nutzer: dict = {}
    neu = 0
    async for e in db().einsaetze.find({"date": morgen, "status": "geplant"}, {"_id": 0}):
        f = firmen.get(e["firma_id"])
        if f is None:
            f = await db().firmen.find_one({"id": e["firma_id"]}, {"_id": 0, "id": 1, "name": 1, "erinnerung": 1}) or {"id": e["firma_id"]}
            firmen[e["firma_id"]] = f
        if jetzt.strftime("%H:%M") < _uhrzeit(f):
            continue
        kennung = f"einsatz-erinnerung-{e['id']}-v{e.get('version', 1)}"
        ergebnis = await db().erinnerungen.update_one({"id": kennung}, {"$setOnInsert": {"id": kennung, "firma_id": e["firma_id"], "user_id": e["user_id"], "einsatz_id": e["id"],
                                                                                          "version": e.get("version", 1), "datum": morgen, "created_at": jetzt_iso()}}, upsert=True)
        if ergebnis.upserted_id is None:
            continue
        p = projekte.get(e["project_id"])
        if p is None:
            p = await db().projects.find_one({"id": e["project_id"]}, {"_id": 0, "name": 1, "address": 1}) or {}
            projekte[e["project_id"]] = p
        ort = e.get("address") or p.get("address") or "Adresse im Projekt"
        text = f"Morgen: {p.get('name') or 'Projekt'}, {e['start_time']}–{e['end_time']} Uhr, {ort}.{(' ' + e['note']) if e.get('note') else ''}"
        await db().benachrichtigungen.update_one({"id": kennung}, {"$setOnInsert": {"id": kennung, "firma_id": e["firma_id"], "user_ids": [e["user_id"]], "mindestens": "mitarbeiter",
                                                                                     "art": "einsatz_erinnerung", "text": text[:300], "link": "/einsaetze", "gelesen_von": [], "created_at": jetzt_iso()}}, upsert=True)
        if (f.get("erinnerung") or {}).get("email", True):
            u = nutzer.get(e["user_id"])
            if u is None:
                u = await db().users.find_one({"id": e["user_id"]}, {"_id": 0, "email": 1, "name": 1, "email_benachrichtigungen": 1}) or {}
                nutzer[e["user_id"]] = u
            if u.get("email") and u.get("email_benachrichtigungen") is not False:
                await mail.senden(e["firma_id"], u["email"], f"Dein Einsatz morgen: {p.get('name') or 'Projekt'}",
                                  f"Hallo {u.get('name') or ''},\n\n{text}\n{('Tätigkeit: ' + e['taetigkeit']) if e.get('taetigkeit') else ''}\n\nDein Einsatzplan: {mail.link('/einsaetze')}",
                                  "einsatz_erinnerung", e["id"], e["project_id"])
        neu += 1
    return neu


async def dienst(intervall: int = 60) -> None:
    while True:
        try:
            await einmal_pruefen()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 – der Dienst darf nie sterben
            pass
        await asyncio.sleep(intervall)
