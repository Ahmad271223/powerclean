"""Übernahme einer Sicherungsdatei der kostenlosen App (Projekte, Einträge, Rechnungen) in die Firma."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from pymongo.errors import DuplicateKeyError

from auth import jetzt_iso, schreibend
from db import db
from gemeinsam import neue_id, projekt_stats_aktualisieren
from protokoll import protokollieren
from zeiten import datum_pruefen, netto_minuten, zeit_pruefen

router = APIRouter(prefix="/api/import", tags=["Import"])


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
    if firmendaten_uebernehmen and companies:
        c = companies[0]
        felder = ("owner", "street", "zip_code", "city", "phone", "website", "tax_number", "vat_id", "bank_name", "iban", "bic",
                  "default_hourly_rate", "vat_rate", "small_business", "invoice_prefix", "payment_days", "invoice_text", "logo", "logo_w", "logo_h",
                  "stamp", "stamp_w", "stamp_h", "stamp_on_sheet", "stamp_on_invoice", "stamp_scale", "stamp_config")
        aenderung = {k: c[k] for k in felder if k in c}
        if aenderung:
            await db().firmen.update_one({"id": f}, {"$set": aenderung})
    # schon importierte Projekte (gleiche Quell-ID) nicht doppelt anlegen
    bekannt = {}
    async for p in db().projects.find({"firma_id": f, "quelle_id": {"$exists": True}}, {"_id": 0, "id": 1, "quelle_id": 1}):
        bekannt[p["quelle_id"]] = p["id"]
    kunden = {}
    async for k in db().customers.find({"firma_id": f}, {"_id": 0, "id": 1, "name": 1}):
        kunden[(k.get("name") or "").strip().lower()] = k["id"]
    zuordnung = {}
    neue_projekte = 0
    for p in projekte:
        quelle = str(p.get("id") or neue_id())
        if quelle in bekannt:
            zuordnung[quelle] = bekannt[quelle]
            continue
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
                kunde_id = kunde["id"]
                kunden[name_k.lower()] = kunde_id
        neu = {"id": neue_id(), "firma_id": f, "quelle_id": quelle, "name": str(p.get("name") or "Projekt")[:160], "color": p.get("color") or "#C41E3A",
               "customer_id": kunde_id, "customer_name": name_k, "customer_address": p.get("customer_address") or "", "address": "",
               "employee_name": p.get("employee_name") or "", "employee_ids": [], "hourly_rate": float(p.get("hourly_rate") or 0),
               "notes": p.get("notes") or "", "archived": bool(p.get("archived")), "default_workers": int(p.get("default_workers") or 1),
               "reverse_charge": False, "schedule": "", "total_minutes": 0, "entry_count": 0, "last_activity_at": None,
               "created_at": p.get("created_at") or jetzt_iso()}
        await db().projects.insert_one(dict(neu))
        zuordnung[quelle] = neu["id"]
        neue_projekte += 1
    vorhandene = set()
    async for e in db().entries.find({"firma_id": f, "quelle_id": {"$exists": True}}, {"_id": 0, "quelle_id": 1}):
        vorhandene.add(e["quelle_id"])
    neue_eintraege, uebersprungen = [], 0
    for e in eintraege:
        quelle = str(e.get("id") or "")
        pid = zuordnung.get(str(e.get("project_id")))
        if not pid or (quelle and quelle in vorhandene):
            uebersprungen += 1
            continue
        try:
            datum_pruefen(str(e.get("date")))
            zeit_pruefen(str(e.get("start_time")))
            zeit_pruefen(str(e.get("end_time")))
        except ValueError:
            uebersprungen += 1
            continue
        pause = int(e.get("pause_minutes") or 0)
        workers = max(1, min(99, int(e.get("workers") or 1)))
        netto = netto_minuten(e["start_time"], e["end_time"], pause)
        if netto <= 0:
            uebersprungen += 1
            continue
        neue_eintraege.append({"id": neue_id(), "quelle_id": quelle or neue_id(), "firma_id": f, "project_id": pid, "user_id": None, "date": e["date"],
                               "start_time": e["start_time"], "end_time": e["end_time"], "pause_minutes": pause, "activity": str(e.get("activity") or "")[:500],
                               "workers": workers, "net_minutes": netto, "source": "import", "created_by": user["id"], "created_at": e.get("created_at") or jetzt_iso()})
    if neue_eintraege:
        await db().entries.insert_many([dict(x) for x in neue_eintraege])
    neue_rechnungen = 0
    for r in rechnungen:
        pid = zuordnung.get(str(r.get("project_id")))
        if not pid or not r.get("number") or not r.get("year") or not r.get("month"):
            continue
        if await db().invoices.find_one({"firma_id": f, "project_id": pid, "year": int(r["year"]), "month": int(r["month"])}):
            continue
        basis = {"id": neue_id(), "firma_id": f, "project_id": pid, "customer_id": None, "year": int(r["year"]), "month": int(r["month"]),
                 "number": str(r["number"]), "invoice_date": r.get("invoice_date") or jetzt_iso()[:10], "status": "offen", "paid_at": None,
                 "total_minutes": r.get("total_minutes"), "rate": r.get("rate"), "net": r.get("net"), "vat": r.get("vat"), "gross": r.get("gross"),
                 "vat_rate": None, "reverse_charge": False, "positions": [], "created_by": user["id"], "created_at": r.get("created_at") or jetzt_iso(), "quelle": "free-app"}
        seq = int(r.get("seq") or 0)
        for _ in range(50):
            try:
                await db().invoices.insert_one({**basis, "seq": seq})
                neue_rechnungen += 1
                break
            except DuplicateKeyError:
                letzte = await db().invoices.find_one({"firma_id": f, "year": basis["year"]}, {"_id": 0, "seq": 1}, sort=[("seq", -1)])
                seq = int((letzte or {}).get("seq") or 0) + 1
    for pid in set(zuordnung.values()):
        await projekt_stats_aktualisieren(f, pid)
    ergebnis = {"projekte": neue_projekte, "eintraege": len(neue_eintraege), "rechnungen": neue_rechnungen, "uebersprungen": uebersprungen}
    await protokollieren(user, "import.free_app", details=ergebnis)
    return ergebnis
