"""Sicherheitsprotokoll: wer hat wann was geändert. Darf den eigentlichen Vorgang nie brechen."""
from __future__ import annotations

import uuid
from typing import Any, Optional

from auth import jetzt_iso
from db import db

DETAILS_MAX = 20


def _kuerzen(wert: Any) -> Any:
    if isinstance(wert, (int, float, bool)) or wert is None:
        return wert
    if isinstance(wert, dict):
        return {k: _kuerzen(v) for k, v in list(wert.items())[:DETAILS_MAX] if not str(k).startswith("_")}
    if isinstance(wert, list):
        return [_kuerzen(v) for v in wert[:DETAILS_MAX]]
    text = str(wert)
    return text if len(text) <= 300 else text[:300] + "…"


async def protokollieren(user: Optional[dict], aktion: str, ziel: str = "", details: Optional[dict] = None,
                         firma_id: Optional[str] = None) -> None:
    fid = firma_id or (user or {}).get("firma_id")
    eintrag = {
        "id": str(uuid.uuid4()), "firma_id": fid, "user_id": (user or {}).get("id"),
        "user_name": (user or {}).get("name") or (user or {}).get("email") or "System",
        "aktion": aktion, "ziel": ziel[:200], "details": _kuerzen(details or {}), "created_at": jetzt_iso(),
    }
    try:
        await db().protokoll.insert_one(dict(eintrag))
    except Exception as exc:  # noqa: BLE001
        print(f"Protokoll nicht geschrieben ({aktion}): {exc}")
    try:
        import webhooks
        webhooks.ausloesen(fid, aktion, {k: v for k, v in eintrag.items() if k != "firma_id"})
    except Exception:  # noqa: BLE001
        pass
