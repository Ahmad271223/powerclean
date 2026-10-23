"""Übernahme einer Sicherungsdatei der kostenlosen App (Projekte, Einträge, Rechnungen) in die Firma.

Regeln (Go-live-Audit): erst alles prüfen, dann schreiben; stabile Kennungen je Eintrag (Wiederholung legt nichts doppelt an);
Projekte laufen durch dasselbe Eingabemodell wie von Hand angelegte; schlägt das Schreiben fehl, werden die bereits angelegten
Datensätze dieses Imports wieder entfernt; Rechnungsnummern bleiben eindeutig und der Nummernkreis wird nachgezogen."""
from __future__ import annotations

import hashlib
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import ValidationError

from auth import jetzt_iso, schreibend
from db import db
from gemeinsam import neue_id, projekt_normalisieren, projekt_stats_aktualisieren
from models import ProjektIn
from protokoll import protokollieren
from zeiten import datum_pruefen, netto_minuten, zeit_pruefen

router = APIRouter(prefix="/api/import", tags=["Import"])
FIRMENFELDER = ("owner", "street", "zip_code", "city", "phone", "website", "tax_number", "vat_id", "bank_name", "iban", "bic",
                "default_hourly_rate", "vat_rate", "small_business", "invoice_prefix", "payment_days", "invoice_text", "logo", "logo_w", "logo_h",
                "stamp", "stamp_w", "stamp_h", "stamp_on_sheet", "stamp_on_invoice", "stamp_scale", "stamp_config")


def _eintrag_kennung(projekt_quelle: str, e: dict) -> str:
    """Stabile Kennung auch ohne Quell-ID: gleicher Eintrag → gleiche Kennung → kein Doppelimport."""
    if e.get("id"):
        return str(e["id"])
    roh = "|".join(str(e.get(k) or "") for k in ("date", "start_time", "end_time", "pause_minutes", "activity", "workers"))
    return "h:" + hashlib.sha1(f"{projekt_quelle}|{roh}".encode("utf-8")).hexdigest()[:20]


@router.post("/free-app")
async def free_app(body: dict[str, Any] = Body(...), firmendaten_uebernehmen: bool = False, user: dict = Depends(schreibend("inhaber"))):
    if body.get("app") not in (None, "stundenzettel"):
        raise HTTPException(400, "Die Datei stammt nicht aus der Stundenzettel-App.")
    daten = body.get("data") or body
    companies = [c for c in (daten.get("companies") or []) if isinstance(c, dict)]
    projekte = [p for p in (daten.get("projects") or []) if isinstance(p, dict)]
    eintraege = [e for e in (daten.get("entries") or []) if isinstance(e, dict)]
    rechnungen = [r for r in (daten.get("invoices") or []) if isinstance(r, dict)]
    if not projekte and not companies:
        raise HTTPException(400, "Keine Projekte oder Firmen in der Datei.")
    f = user["firma_id"]

    # ---- 1. Prüfen (nichts wird geschrieben) ------------------------------------------------------------
    bekannt = {}
    async for p in db().projects.find({"firma_id": f, "quelle_id": {"$exists": True}}, {"_id": 0, "id": 1, "quelle_id": 1}):
        bekannt[p["quelle_id"]] = p["id"]
    fehler: list[str] = []
    geprueft: list[tuple[str, dict]] = []
    for nr, p in enumerate(projekte, 1):
        quelle = str(p.get("id") or f"import-{nr}")
        if quelle in bekannt:
            continue
        try:
            modell = ProjektIn(name=str(p.get("name") or "Projekt"), customer_name=str(p.get("customer_name") or "")[:160], customer_address=str(p.get("customer_address") or "")[:400],
                               employee_name=str(p.get("employee_name") or "")[:200], hourly_rate=float(p.get("hourly_rate") or 0), color=str(p.get("color") or "#C41E3A"),
                               notes=str(p.get("notes") or "")[:2000], archived=bool(p.get("archived")), default_workers=int(p.get("default_workers") or 1))
        except (ValidationError, ValueError, TypeError) as exc:
            fehler.append(f"Projekt {nr} („{str(p.get('name') or '')[:40]}“): {str(exc).splitlines()[0][:120]}")
            continue
        geprueft.append((quelle, {**modell.model_dump(), "created_at": p.get("created_at") or jetzt_iso()}))
    if fehler:
        raise HTTPException(400, "Import abgebrochen, nichts übernommen. " + " · ".join(fehler[:5]))
    vorhandene = set()
    async for e in db().entries.find({"firma_id": f, "quelle_id": {"$exists": True}}, {"_id": 0, "quelle_id": 1}):
        vorhandene.add(e["quelle_id"])
    uebersprungen: list[str] = []
    eintraege_ok: list[tuple[str, dict]] = []   # (projekt_quelle, eintrag)
    gesehen = set()
    for e in eintraege:
        projekt_quelle = str(e.get("project_id") or "")
        kennung = _eintrag_kennung(projekt_quelle, e)
        if kennung in vorhandene or kennung in gesehen:
            uebersprungen.append(f"{e.get('date')}: schon vorhanden")
            continue
        try:
            datum_pruefen(str(e.get("date")))
            zeit_pruefen(str(e.get("start_time")))
            zeit_pruefen(str(e.get("end_time")))
            pause = int(e.get("pause_minutes") or 0)
            workers = max(1, min(99, int(e.get("workers") or 1)))
        except (ValueError, TypeError) as exc:
            uebersprungen.append(f"{e.get('date')}: {exc}")
            continue
        netto = netto_minuten(e["start_time"], e["end_time"], pause)
        if netto <= 0:
            uebersprungen.append(f"{e.get('date')}: keine Nettozeit")
            continue
        gesehen.add(kennung)
        eintraege_ok.append((projekt_quelle, {"quelle_id": kennung, "date": e["date"], "start_time": e["start_time"], "end_time": e["end_time"], "pause_minutes": pause,
                                              "activity": str(e.get("activity") or "")[:500], "workers": workers, "net_minutes": netto, "created_at": e.get("created_at") or jetzt_iso()}))

    # ---- 2. Schreiben (bei Fehlern wird alles aus diesem Import wieder entfernt) ----------------------
    angelegt: dict[str, list[str]] = {"customers": [], "projects": [], "entries": [], "invoices": []}
    kunden = {}
    async for k in db().customers.find({"firma_id": f}, {"_id": 0, "id": 1, "name": 1}):
        kunden[(k.get("name") or "").strip().lower()] = k["id"]
    zuordnung = dict(bekannt)
    ergebnis = {"projekte": 0, "eintraege": 0, "rechnungen": 0, "rechnungen_uebersprungen": 0, "uebersprungen": len(uebersprungen), "hinweise": uebersprungen[:20]}
    try:
        if firmendaten_uebernehmen and companies:
            aenderung = {k: companies[0][k] for k in FIRMENFELDER if k in companies[0]}
            if aenderung:
                await db().firmen.update_one({"id": f}, {"$set": aenderung})
        for quelle, p in geprueft:
            kunde_id = None
            name_k = (p.get("customer_name") or "").strip()
            if name_k:
                kunde_id = kunden.get(name_k.lower())
                if not kunde_id:
                    adresse = (p.get("customer_address") or "").splitlines()
                    kunde = {"id": neue_id(), "firma_id": f, "name": name_k, "contact": "", "street": adresse[0] if adresse else "",
                             "zip_code": "", "city": " ".join(adresse[1:]) if len(adresse) > 1 else "", "email": "", "phone": "", "notes": "",
                             "reverse_charge": False, "created_at": jetzt_iso(), "quelle": "free-app"}
                    await db().customers.insert_one(dict(kunde))
                    angelegt["customers"].append(kunde["id"])
                    kunde_id = kunde["id"]
                    kunden[name_k.lower()] = kunde_id
            neu = projekt_normalisieren({**p, "id": neue_id(), "firma_id": f, "quelle_id": quelle, "customer_id": kunde_id, "employee_ids": [],
                                         "total_minutes": 0, "entry_count": 0, "last_activity_at": None})
            await db().projects.insert_one(dict(neu))
            angelegt["projects"].append(neu["id"])
            zuordnung[quelle] = neu["id"]
            ergebnis["projekte"] += 1
        for projekt_quelle, e in eintraege_ok:
            pid = zuordnung.get(projekt_quelle)
            if not pid:
                ergebnis["uebersprungen"] += 1
                continue
            doc = {**e, "id": neue_id(), "firma_id": f, "project_id": pid, "user_id": None, "source": "import", "created_by": user["id"]}
            await db().entries.insert_one(dict(doc))
            angelegt["entries"].append(doc["id"])
            ergebnis["eintraege"] += 1
        hoechste_seq: dict[int, int] = {}
        for r in rechnungen:
            pid = zuordnung.get(str(r.get("project_id")))
            if not pid or not r.get("number") or not r.get("year") or not r.get("month"):
                continue
            jahr, monat, nummer = int(r["year"]), int(r["month"]), str(r["number"])
            if await db().invoices.find_one({"firma_id": f, "$or": [{"project_id": pid, "year": jahr, "month": monat}, {"number": nummer}]}, {"_id": 0, "id": 1}):
                ergebnis["rechnungen_uebersprungen"] += 1   # Monat schon abgerechnet oder Nummer schon vergeben – nie doppelt
                continue
            letzte = await db().invoices.find_one({"firma_id": f, "year": jahr}, {"_id": 0, "seq": 1}, sort=[("seq", -1)])
            seq = max(int(r.get("seq") or 0), int((letzte or {}).get("seq") or 0) + 1, hoechste_seq.get(jahr, 0) + 1)
            doc = {"id": neue_id(), "firma_id": f, "project_id": pid, "customer_id": None, "year": jahr, "month": monat, "seq": seq, "number": nummer,
                   "invoice_date": r.get("invoice_date") or jetzt_iso()[:10], "status": "offen", "paid_at": None, "total_minutes": r.get("total_minutes"),
                   "rate": r.get("rate"), "net": r.get("net"), "vat": r.get("vat"), "gross": r.get("gross"), "vat_rate": None, "reverse_charge": False, "positions": [],
                   "festgeschrieben_at": r.get("created_at") or jetzt_iso(), "festgeschrieben_anlass": "import", "created_by": user["id"],
                   "created_at": r.get("created_at") or jetzt_iso(), "quelle": "free-app"}
            await db().invoices.insert_one(dict(doc))
            angelegt["invoices"].append(doc["id"])
            hoechste_seq[jahr] = max(hoechste_seq.get(jahr, 0), seq)
            ergebnis["rechnungen"] += 1
        for jahr, seq in hoechste_seq.items():   # Nummernkreis nachziehen, damit neue Rechnungen keine importierte Nummer wiederholen
            firma = await db().firmen.find_one({"id": f}, {"_id": 0, "rechnungszaehler": 1})
            stand = int(((firma or {}).get("rechnungszaehler") or {}).get(str(jahr)) or 0)
            if seq > stand:
                await db().firmen.update_one({"id": f}, {"$set": {f"rechnungszaehler.{jahr}": seq}})
        for pid in set(zuordnung.values()):
            await projekt_stats_aktualisieren(f, pid)
    except Exception as exc:  # noqa: BLE001 – Teilimport zurücknehmen
        for sammlung, ids in angelegt.items():
            if ids:
                await db()[sammlung].delete_many({"id": {"$in": ids}, "firma_id": f})
        await protokollieren(user, "import.free_app_abgebrochen", details={"grund": str(exc)[:200]})
        raise HTTPException(500, "Import abgebrochen – es wurde nichts übernommen. Bitte die Datei prüfen und erneut versuchen.") from exc
    await protokollieren(user, "import.free_app", details={k: v for k, v in ergebnis.items() if k != "hinweise"})
    return ergebnis
