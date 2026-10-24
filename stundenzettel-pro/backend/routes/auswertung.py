"""Auswertung: Stunden und Umsatz je Kunde, Projekt, Mitarbeiter oder Leistung in einem Zeitraum."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from auth import firma_laden, hat_recht, rolle_noetig
from db import db
from gemeinsam import nutzernamen, projekt_normalisieren
from zeiten import datum_pruefen, eintrag_minuten, eintrag_satz

router = APIRouter(prefix="/api/auswertung", tags=["Auswertung"])
GRUPPEN = ("kunde", "projekt", "mitarbeiter", "leistung", "monat")


@router.get("")
async def auswertung(von: str, bis: str, gruppe: str = Query("projekt"), user: dict = Depends(rolle_noetig("buero"))):
    if gruppe == "mitarbeiter" and not hat_recht(user, "personal"):
        raise HTTPException(403, "Die Auswertung je Mitarbeiter sieht nur, wer das Personalrecht hat.")
    try:
        datum_pruefen(von)
        datum_pruefen(bis)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    if gruppe not in GRUPPEN:
        raise HTTPException(400, f"gruppe muss eine von {', '.join(GRUPPEN)} sein.")
    firma = await firma_laden(user["firma_id"])
    projekte = {}
    async for p in db().projects.find({"firma_id": user["firma_id"]}, {"_id": 0}):
        projekte[p["id"]] = projekt_normalisieren(p)
    namen = await nutzernamen(user["firma_id"])
    zeilen: dict[str, dict] = {}
    gesamt = {"minuten": 0, "umsatz": 0.0, "eintraege": 0, "tage": set()}
    async for e in db().entries.find({"firma_id": user["firma_id"], "date": {"$gte": von, "$lte": bis}}, {"_id": 0}).limit(200000):
        p = projekte.get(e.get("project_id")) or {"name": "Projekt gelöscht", "customer_name": ""}
        minuten = eintrag_minuten(e)
        umsatz = minuten / 60 * eintrag_satz(e, p, firma)
        if gruppe == "kunde":
            schluessel, name = (p.get("customer_id") or p.get("customer_name") or "-"), (p.get("customer_name") or "Ohne Kunde")
        elif gruppe == "projekt":
            schluessel, name = e.get("project_id"), p.get("name")
        elif gruppe == "mitarbeiter":
            schluessel, name = (e.get("user_id") or "-"), (namen.get(e.get("user_id") or "", "") or "Ohne Person (Anzahl)")
        elif gruppe == "leistung":
            schluessel, name = (e.get("service_id") or "-"), (e.get("service_name") or "Ohne Leistung")
        else:
            schluessel = name = e["date"][:7]
        z = zeilen.setdefault(schluessel, {"schluessel": schluessel, "name": name, "minuten": 0, "umsatz": 0.0, "eintraege": 0, "tage": set(), "projekte": set()})
        z["minuten"] += minuten
        z["umsatz"] += umsatz
        z["eintraege"] += 1
        z["tage"].add(e["date"])
        z["projekte"].add(e.get("project_id"))
        gesamt["minuten"] += minuten
        gesamt["umsatz"] += umsatz
        gesamt["eintraege"] += 1
        gesamt["tage"].add(e["date"])
    aus = []
    for z in zeilen.values():
        aus.append({**z, "umsatz": round(z["umsatz"], 2), "tage": len(z["tage"]), "projekte": len(z["projekte"]),
                    "anteil": round(z["minuten"] / gesamt["minuten"] * 100, 1) if gesamt["minuten"] else 0})
    aus.sort(key=lambda z: (z["schluessel"] if gruppe == "monat" else -z["minuten"], z["name"]))
    return {"von": von, "bis": bis, "gruppe": gruppe, "zeilen": aus,
            "gesamt": {"minuten": gesamt["minuten"], "umsatz": round(gesamt["umsatz"], 2), "eintraege": gesamt["eintraege"], "tage": len(gesamt["tage"])}}
