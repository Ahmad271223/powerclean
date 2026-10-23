"""Projektarchive: vollständige Projektakte als ZIP erstellen, auflisten, herunterladen und (Inhaber) löschen.
Für jede Firma im Firmenabo – und für Auftraggeber bei GU-Projekten auch nach deren Ende (Export und Aufbewahrung)."""
from __future__ import annotations

import os
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

import config
import projektakte
from auth import firmenabo_pruefen, plan_status, rolle_noetig, schreibend
from db import db
from gemeinsam import projekt_laden
from protokoll import protokollieren

router = APIRouter(tags=["Projektarchiv"])


def _oeffentlich(a: dict) -> dict:
    aus = {k: v for k, v in a.items() if k != "pfad"}
    aus["ablauf_erreicht"] = bool(a.get("aufbewahren_bis") and a["aufbewahren_bis"] <= date.today().isoformat())
    return aus


@router.post("/api/projekte/{project_id}/projektakte")
async def projektakte_erstellen(project_id: str, user: dict = Depends(schreibend("buero"))):
    """Vollständige Projektakte (ZIP) erzeugen. Im Firmenabo enthalten; GU-Projekte des Auftraggebers auch ohne Firmenabo."""
    p = await projekt_laden(user, project_id)
    if plan_status(user["_firma"]).get("stufe") == "teilnahme" and not p.get("gu_abo"):
        firmenabo_pruefen(user["_firma"])
    akte = await projektakte.erstellen(user, p)
    await protokollieren(user, "projektakte.erstellt", p.get("name", ""), details={"akte_id": akte["id"], "size": akte["size"], "inhalt": akte["inhalt"]})
    return {"projektakte": _oeffentlich(akte)}


@router.get("/api/projekte/{project_id}/projektakten")
async def projektakten_projekt(project_id: str, user: dict = Depends(rolle_noetig("buero"))):
    await projekt_laden(user, project_id)
    aus = [_oeffentlich(a) async for a in db().projektakten.find({"firma_id": user["firma_id"], "project_id": project_id}, {"_id": 0}).sort("created_at", -1)]
    return {"projektakten": aus, "aufbewahrung_jahre": config.AUFBEWAHRUNG_JAHRE}


@router.get("/api/projektakten")
async def projektakten_liste(user: dict = Depends(rolle_noetig("buero"))):
    aus = [_oeffentlich(a) async for a in db().projektakten.find({"firma_id": user["firma_id"]}, {"_id": 0}).sort("created_at", -1)]
    return {"projektakten": aus, "aufbewahrung_jahre": config.AUFBEWAHRUNG_JAHRE, "gesamt_bytes": sum(int(a.get("size") or 0) for a in aus)}


@router.get("/api/projektakten/{akte_id}.zip")
async def projektakte_herunterladen(akte_id: str, user: dict = Depends(rolle_noetig("buero"))):
    a = await db().projektakten.find_one({"id": akte_id, "firma_id": user["firma_id"]}, {"_id": 0})
    if not a or not os.path.isfile(a.get("pfad") or ""):
        raise HTTPException(404, "Projektakte nicht gefunden.")
    await protokollieren(user, "projektakte.heruntergeladen", a.get("project_name", ""), details={"akte_id": akte_id})
    return FileResponse(a["pfad"], media_type="application/zip", filename=a.get("dateiname") or "Projektakte.zip")


@router.delete("/api/projektakten/{akte_id}")
async def projektakte_loeschen(akte_id: str, erzwingen: bool = False, user: dict = Depends(schreibend("inhaber"))):
    """Archiv löschen – vor Ablauf der Aufbewahrungsfrist nur ausdrücklich (erzwingen=true), mit Protokolleintrag."""
    a = await db().projektakten.find_one({"id": akte_id, "firma_id": user["firma_id"]}, {"_id": 0})
    if not a:
        raise HTTPException(404, "Projektakte nicht gefunden.")
    if a.get("aufbewahren_bis") and a["aufbewahren_bis"] > date.today().isoformat() and not erzwingen:
        raise HTTPException(400, f"Die Aufbewahrungsfrist läuft bis {a['aufbewahren_bis']}. Löschen vorher nur ausdrücklich (erzwingen=true) – bitte vorher eine Kopie sichern.")
    try:
        os.unlink(a.get("pfad") or "")
    except OSError:
        pass
    await db().projektakten.delete_one({"id": akte_id})
    await protokollieren(user, "projektakte.geloescht", a.get("project_name", ""), details={"akte_id": akte_id, "vor_ablauf": bool(a.get("aufbewahren_bis") and a["aufbewahren_bis"] > date.today().isoformat())})
    return {"ok": True}
