"""Webhooks: Ereignisse der Firma (zeit.eingetragen, rechnung.angelegt, …) an fremde Adressen schicken.
Signatur: X-Signatur = HMAC-SHA256(secret, body) als Hex. Läuft im Hintergrund, bricht nie den Vorgang."""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
from datetime import datetime, timezone

import httpx

from db import db

EREIGNISSE = [
    "zeit.eingetragen", "zeit.geaendert", "zeit.geloescht", "zeit.serie", "stempel.start", "stempel.stop",
    "abwesenheit.angelegt", "abwesenheit.entschieden", "rechnung.angelegt", "rechnung.status",
    "mitarbeiter.eingeladen", "unterschrift.erfasst", "monat.abgeschlossen", "test",
]


async def _post(url: str, body: bytes, headers: dict) -> int:
    async with httpx.AsyncClient(timeout=8) as c:
        r = await c.post(url, content=body, headers=headers)
        return r.status_code


async def senden(firma_id: str, ereignis: str, daten: dict) -> list[dict]:
    """Alle passenden Hooks der Firma rufen; liefert [{id, status}] (für den Test-Knopf)."""
    aus = []
    try:
        hooks = [h async for h in db().webhooks.find({"firma_id": firma_id, "active": True}, {"_id": 0})]
    except Exception:  # noqa: BLE001
        return aus
    nutzlast = json.dumps({"ereignis": ereignis, "firma_id": firma_id, "zeitpunkt": datetime.now(timezone.utc).isoformat(),
                           "daten": daten}, ensure_ascii=False, default=str).encode("utf-8")
    for h in hooks:
        events = h.get("events") or ["*"]
        if "*" not in events and ereignis not in events:
            continue
        sig = hmac.new((h.get("secret") or "").encode(), nutzlast, hashlib.sha256).hexdigest()
        status = 0
        try:
            status = await _post(h["url"], nutzlast, {"Content-Type": "application/json", "X-Signatur": sig, "X-Ereignis": ereignis})
        except Exception:  # noqa: BLE001
            status = 0
        try:
            await db().webhooks.update_one({"id": h["id"]}, {"$set": {"last_status": status, "last_at": datetime.now(timezone.utc).isoformat(), "last_event": ereignis}})
        except Exception:  # noqa: BLE001
            pass
        aus.append({"id": h["id"], "status": status})
    return aus


def ausloesen(firma_id: str | None, ereignis: str, daten: dict) -> None:
    if not firma_id or ereignis not in EREIGNISSE:
        return
    try:
        asyncio.get_running_loop().create_task(senden(firma_id, ereignis, daten))
    except RuntimeError:
        pass
