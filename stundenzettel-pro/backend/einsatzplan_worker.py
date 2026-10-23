"""Tägliche In-App-Einsatzbenachrichtigungen für den Folgetag.

Vorgabe: ab 18 Uhr deutscher Ortszeit. Mehrere Worker dürfen dieselbe
Benachrichtigung nicht doppelt anlegen (deterministische Ereignis-ID).
Dies ist noch KEINE Betriebssystem-Push- oder E-Mail-Zustellung.
"""
from __future__ import annotations

import asyncio
from datetime import timedelta

from db import db
from zeiten import lokal_jetzt


async def einmal_pruefen() -> int:
    jetzt = lokal_jetzt()
    if jetzt.hour < 18:
        return 0
    morgen = (jetzt.date() + timedelta(days=1)).isoformat()
    gesendet = 0
    async for p in db().einsatzplaene.find({"date": morgen, "status": "geplant"}, {"_id": 0}):
        version = int(p.get("version") or 1)
        event_id = f"einsatz-termin-{p['id']}-v{version}"
        project = await db().projects.find_one({"id": p["project_id"], "firma_id": p["firma_id"]},
                                                {"_id": 0, "name": 1, "address": 1})
        ort = p.get("address") or (project or {}).get("address") or "Adresse im Projekt ansehen"
        # id ist im Datenbankindex eindeutig. Erneute Prüfung nach Neustart
        # legt denselben Hinweis nicht noch einmal an.
        ergebnis = await db().benachrichtigungen.update_one(
            {"id": event_id},
            {"$setOnInsert": {
                "id": event_id, "firma_id": p["firma_id"], "user_ids": [p["user_id"]],
                "mindestens": "mitarbeiter", "art": "einsatz_morgen",
                "text": f"Morgen: {(project or {}).get('name') or 'Projekt'}, {p['start_time']}–{p['end_time']} Uhr. Ort: {ort}"[:300],
                "link": f"/einsatzplan?datum={morgen}", "gelesen_von": [],
                "created_at": jetzt.isoformat()}},
            upsert=True)
        if ergebnis.upserted_id is not None:
            gesendet += 1
    return gesendet


async def erinnerungsdienst() -> None:
    """Ein einfacher periodischer Worker; für Skalierung als eigener Prozess auslagern."""
    while True:
        try:
            await einmal_pruefen()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print("WARNUNG: Einsatz-Erinnerung fehlgeschlagen:", type(exc).__name__)
        await asyncio.sleep(300)
