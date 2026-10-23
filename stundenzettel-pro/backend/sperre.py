"""Bearbeitungssperren: abgeschlossener Monat, bezahlte Rechnung, Frist für Mitarbeiter."""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import HTTPException

from auth import hat_rolle
from db import db


async def monat_abgeschlossen(firma_id: str, jahr: int, monat: int) -> bool:
    return await db().abschluesse.find_one({"firma_id": firma_id, "year": jahr, "month": monat}) is not None


async def sperre_pruefen(user: dict, firma: dict, project_id: str | None, datum: str, leitung: bool = False) -> None:
    """Wirft 423, wenn der Tag nicht mehr bearbeitet werden darf."""
    d = date.fromisoformat(datum)
    if await monat_abgeschlossen(user["firma_id"], d.year, d.month):
        raise HTTPException(423, f"{d.month:02d}/{d.year} ist abgeschlossen. Das Büro kann den Monat unter „Exporte“ wieder öffnen.")
    if project_id:
        r = await db().invoices.find_one({"firma_id": user["firma_id"], "project_id": project_id, "year": d.year, "month": d.month, "status": "bezahlt"}, {"_id": 0, "number": 1})
        if r:
            raise HTTPException(423, f"Die Rechnung {r['number']} für diesen Monat ist bezahlt – Zeiten sind gesperrt.")
    if not hat_rolle(user, "buero") and not leitung:
        tage = int(firma.get("sperre_tage_mitarbeiter") if firma.get("sperre_tage_mitarbeiter") is not None else 7)
        if tage >= 0 and d < date.today() - timedelta(days=tage):
            raise HTTPException(403, f"Einträge, die älter als {tage} Tage sind, kann nur das Büro ändern.")
