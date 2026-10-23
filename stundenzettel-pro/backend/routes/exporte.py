"""Exporte: Lohnbüro (CSV je Eintrag und Summen je Mitarbeiter), Zeiten, Abwesenheiten, Protokoll,
Mindestlohn-Nachweis (§ 17 MiLoG, Daten für das PDF), Komplettsicherung, Rückweg in die kostenlose App."""
from __future__ import annotations

import csv
import io
import os
import tempfile
import zipfile
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response

import config
from csvsicher import zeile as csv_zeile

from auth import aktueller_nutzer, firma_laden, hat_rolle, jetzt_iso, nutzer_oeffentlich, rolle_noetig
from db import db
from gemeinsam import FIRMA_DEFAULTS, firma_oeffentlich, nutzernamen
from protokoll import protokollieren
from zeiten import datum_pruefen, eintrag_minuten, monatsletzter, tage_zwischen

router = APIRouter(prefix="/api/exporte", tags=["Exporte"])
WOCHENTAGE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


def _csv(zeilen: list[list], dateiname: str) -> Response:
    puffer = io.StringIO()
    w = csv.writer(puffer, delimiter=";", lineterminator="\r\n", quoting=csv.QUOTE_MINIMAL)
    for z in zeilen:
        w.writerow(csv_zeile(["" if v is None else v for v in z]))
    daten = ("﻿" + puffer.getvalue()).encode("utf-8")
    return Response(content=daten, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{dateiname}"'})


def _dez(minuten: int) -> str:
    return f"{minuten / 60:.2f}".replace(".", ",")


def _wochentag(datum: str) -> str:
    from datetime import date
    try:
        return WOCHENTAGE[date.fromisoformat(datum).weekday()]
    except ValueError:
        return ""


async def _projekte(firma_id: str) -> dict:
    aus = {}
    async for p in db().projects.find({"firma_id": firma_id}, {"_id": 0, "id": 1, "name": 1, "customer_name": 1}):
        aus[p["id"]] = p
    return aus


async def _nutzer(firma_id: str) -> dict:
    aus = {}
    async for u in db().users.find({"firma_id": firma_id}, {"_id": 0, "pw_hash": 0, "einladung_token": 0}):
        aus[u["id"]] = u
    return aus


def _monatsbereich(jahr: int, monat: int) -> tuple[str, str]:
    return f"{jahr:04d}-{monat:02d}-01", monatsletzter(jahr, monat).isoformat()


@router.get("/lohn.csv")
async def lohn(jahr: int = Query(..., ge=2025, le=2100), monat: int = Query(..., ge=1, le=12), user: dict = Depends(rolle_noetig("inhaber"))):
    von, bis = _monatsbereich(jahr, monat)
    projekte = await _projekte(user["firma_id"])
    nutzer = await _nutzer(user["firma_id"])
    zeilen = [["Personalnummer", "Mitarbeiter", "Datum", "Wochentag", "Beginn", "Ende", "Pause (Min)", "Netto (Min)", "Netto (Std)",
               "Anzahl", "Projekt", "Kunde", "Tätigkeit", "Quelle", "Eintrag-ID"]]
    async for e in db().entries.find({"firma_id": user["firma_id"], "date": {"$gte": von, "$lte": bis}}, {"_id": 0}).sort([("user_id", 1), ("date", 1), ("start_time", 1)]):
        u = nutzer.get(e.get("user_id") or "", {})
        p = projekte.get(e.get("project_id"), {})
        zeilen.append([u.get("personalnummer", ""), u.get("name", "") if u else "(ohne Person)", e["date"], _wochentag(e["date"]),
                       e["start_time"], e["end_time"], e.get("pause_minutes", 0), e.get("net_minutes", 0), _dez(int(e.get("net_minutes") or 0)),
                       e.get("workers", 1), p.get("name", ""), p.get("customer_name", ""), e.get("activity", ""), e.get("source", "manuell"), e["id"]])
    await protokollieren(user, "export.lohn", f"{jahr}-{monat:02d}", details={"zeilen": len(zeilen) - 1})
    return _csv(zeilen, f"Lohn_{jahr}-{monat:02d}.csv")


@router.get("/lohn-summen.csv")
async def lohn_summen(jahr: int = Query(..., ge=2025, le=2100), monat: int = Query(..., ge=1, le=12), user: dict = Depends(rolle_noetig("inhaber"))):
    von, bis = _monatsbereich(jahr, monat)
    nutzer = await _nutzer(user["firma_id"])
    summen = {uid: {"minuten": 0, "tage": set()} for uid in nutzer}
    async for e in db().entries.find({"firma_id": user["firma_id"], "user_id": {"$ne": None}, "date": {"$gte": von, "$lte": bis}}, {"_id": 0, "user_id": 1, "net_minutes": 1, "date": 1}):
        s = summen.setdefault(e["user_id"], {"minuten": 0, "tage": set()})
        s["minuten"] += int(e.get("net_minutes") or 0)
        s["tage"].add(e["date"])
    urlaub = {uid: 0 for uid in nutzer}
    krank = {uid: 0 for uid in nutzer}
    async for a in db().absences.find({"firma_id": user["firma_id"], "from_date": {"$lte": bis}, "to_date": {"$gte": von}, "status": "genehmigt"}, {"_id": 0}):
        tage = tage_zwischen(max(a["from_date"], von), min(a["to_date"], bis))
        if a["type"] == "urlaub":
            urlaub[a["user_id"]] = urlaub.get(a["user_id"], 0) + tage
        elif a["type"] == "krank":
            krank[a["user_id"]] = krank.get(a["user_id"], 0) + tage
    from konten import kontoverlauf, monatskonto, urlaubskonto
    firma = await firma_laden(user["firma_id"])
    zeilen = [["Personalnummer", "Mitarbeiter", "Rolle", "Arbeitstage", "Stunden (dezimal)", "Minuten", "Urlaubstage", "Kranktage",
               "Wochenstunden (Soll)", "Soll Monat (Std)", "Saldo Monat (Std)", "Saldo gesamt (Std)", "Resturlaub (Tage)"]]
    for uid, u in sorted(nutzer.items(), key=lambda kv: kv[1].get("name", "")):
        if not u.get("active", True) and not summen.get(uid, {}).get("minuten"):
            continue
        s = summen.get(uid, {"minuten": 0, "tage": set()})
        konto = await monatskonto(firma, u, jahr, monat)
        verlauf = await kontoverlauf(firma, u, jahr, monat) if u.get("weekly_hours") else {"saldo_minuten": 0}
        ul = await urlaubskonto(firma, u, jahr)
        zeilen.append([u.get("personalnummer", ""), u.get("name", ""), u.get("role", ""), len(s["tage"]), _dez(s["minuten"]), s["minuten"],
                       urlaub.get(uid, 0), krank.get(uid, 0), str(u.get("weekly_hours") or "").replace(".", ","),
                       _dez(konto["soll_minuten"]), _dez(konto["saldo_minuten"]), _dez(verlauf["saldo_minuten"]), str(ul["rest"]).replace(".", ",")])
    await protokollieren(user, "export.lohn_summen", f"{jahr}-{monat:02d}")
    return _csv(zeilen, f"Lohn-Summen_{jahr}-{monat:02d}.csv")


@router.get("/zeiten.csv")
async def zeiten(von: str, bis: str, project_id: Optional[str] = None, user: dict = Depends(rolle_noetig("inhaber"))):
    try:
        datum_pruefen(von)
        datum_pruefen(bis)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    projekte = await _projekte(user["firma_id"])
    namen = await nutzernamen(user["firma_id"])
    filt = {"firma_id": user["firma_id"], "date": {"$gte": von, "$lte": bis}}
    if project_id:
        filt["project_id"] = project_id
    zeilen = [["Datum", "Wochentag", "Projekt", "Kunde", "Mitarbeiter", "Beginn", "Ende", "Pause (Min)", "Anzahl", "Netto (Min)", "Mitarbeiterstunden (dezimal)", "Tätigkeit", "Quelle"]]
    async for e in db().entries.find(filt, {"_id": 0}).sort([("date", 1), ("start_time", 1)]).limit(20000):
        p = projekte.get(e.get("project_id"), {})
        zeilen.append([e["date"], _wochentag(e["date"]), p.get("name", ""), p.get("customer_name", ""), namen.get(e.get("user_id") or "", ""),
                       e["start_time"], e["end_time"], e.get("pause_minutes", 0), e.get("workers", 1), e.get("net_minutes", 0),
                       _dez(eintrag_minuten(e)), e.get("activity", ""), e.get("source", "manuell")])
    return _csv(zeilen, f"Zeiten_{von}_{bis}.csv")


@router.get("/abwesenheiten.csv")
async def abwesenheiten(jahr: int = Query(..., ge=2025, le=2100), user: dict = Depends(rolle_noetig("inhaber"))):
    namen = await nutzernamen(user["firma_id"])
    zeilen = [["Mitarbeiter", "Art", "Von", "Bis", "Tage", "Status", "Notiz", "Entschieden von"]]
    async for a in db().absences.find({"firma_id": user["firma_id"], "from_date": {"$lte": f"{jahr}-12-31"}, "to_date": {"$gte": f"{jahr}-01-01"}}, {"_id": 0}).sort("from_date", 1):
        zeilen.append([namen.get(a["user_id"], ""), a["type"], a["from_date"], a["to_date"], tage_zwischen(a["from_date"], a["to_date"]), a.get("status", ""), a.get("note", ""), a.get("decided_by", "")])
    return _csv(zeilen, f"Abwesenheiten_{jahr}.csv")


@router.get("/protokoll.csv")
async def protokoll_export(user: dict = Depends(rolle_noetig("inhaber"))):
    zeilen = [["Zeitpunkt", "Nutzer", "Aktion", "Ziel", "Details"]]
    async for p in db().protokoll.find({"firma_id": user["firma_id"]}, {"_id": 0}).sort("created_at", -1).limit(20000):
        zeilen.append([p.get("created_at"), p.get("user_name"), p.get("aktion"), p.get("ziel"), str(p.get("details") or "")])
    return _csv(zeilen, "Sicherheitsprotokoll.csv")


@router.get("/milog")
async def milog(jahr: int = Query(..., ge=2025, le=2100), monat: int = Query(..., ge=1, le=12), user_id: str = Query(...),
                user: dict = Depends(aktueller_nutzer)):
    """Daten für den Mindestlohn-Nachweis (Beginn, Ende, Dauer je Tag) eines Mitarbeiters — PDF entsteht in der App."""
    if user["id"] != user_id and not hat_rolle(user, "buero"):
        raise HTTPException(403, "Dafür fehlt die Berechtigung.")
    u = await db().users.find_one({"id": user_id, "firma_id": user["firma_id"]}, {"_id": 0})
    if not u:
        raise HTTPException(404, "Mitarbeiter nicht gefunden.")
    von, bis = _monatsbereich(jahr, monat)
    projekte = await _projekte(user["firma_id"])
    eintraege, minuten = [], 0
    async for e in db().entries.find({"firma_id": user["firma_id"], "user_id": user_id, "date": {"$gte": von, "$lte": bis}}, {"_id": 0}).sort([("date", 1), ("start_time", 1)]):
        e["project_name"] = projekte.get(e.get("project_id"), {}).get("name", "")
        minuten += int(e.get("net_minutes") or 0)
        eintraege.append(e)
    abwesenheiten = []
    async for a in db().absences.find({"firma_id": user["firma_id"], "user_id": user_id, "from_date": {"$lte": bis}, "to_date": {"$gte": von}}, {"_id": 0}).sort("from_date", 1):
        abwesenheiten.append(a)
    firma = await firma_laden(user["firma_id"])
    from feiertage import feiertage_set
    frei = {k: v for k, v in feiertage_set([jahr], firma.get("bundesland") or "").items() if von <= k <= bis}
    await protokollieren(user, "export.milog", u.get("name", ""), details={"monat": f"{jahr}-{monat:02d}"})
    return {"firma": firma_oeffentlich(firma, user), "mitarbeiter": nutzer_oeffentlich(u), "jahr": jahr, "monat": monat,
            "eintraege": eintraege, "abwesenheiten": abwesenheiten, "feiertage": frei,
            "summe": {"minuten": minuten, "arbeitstage": len({e["date"] for e in eintraege})}, "erstellt_am": jetzt_iso()}


SICHERUNG_FIRMA = (("users", {"pw_hash", "einladung_token", "pin_hash"}), ("customers", set()), ("projects", set()), ("entries", set()), ("absences", set()),
                   ("invoices", set()), ("comments", set()), ("checklists", set()), ("signatures", set()), ("documents", {"path"}), ("protokoll", set()),
                   ("services", set()), ("zeitkonto", set()), ("abschluesse", set()), ("stempel", set()), ("webhooks", {"secret"}), ("api_tokens", {"token_hash"}),
                   ("ausschreibungen", set()), ("projekt_leiter", set()))
SICHERUNG_PLATTFORM = ("beteiligungen", "aufgaben", "freigaben", "benachrichtigungen", "lieferungen", "maengel", "tagesberichte", "meilensteine",
                       "ausschreibung_einladungen", "angebote", "ausschreibung_fragen", "vergaben", "webhook_ausgang")


@router.get("/sicherung.json")
async def sicherung(user: dict = Depends(rolle_noetig("inhaber"))):
    """Datensicherung der Firma: alle Sammlungen (ohne Passwörter, Schlüssel-Hashes, Webhook-Geheimnisse). Dateiinhalte liegen getrennt
    in /api/exporte/dateien.zip. Die Datei enthält Personaldaten – verschlüsselt ablegen, Zugriff beschränken."""
    f = user["firma_id"]
    aus = {"app": "stundenzettel-pro", "version": 2, "exported_at": jetzt_iso(), "data": {},
           "hinweis": "Dateiinhalte (Fotos, Dokumente) sind nicht enthalten: zusätzlich /api/exporte/dateien.zip sichern. Enthält Personaldaten – nur verschlüsselt aufbewahren."}
    aus["data"]["firma"] = {k: v for k, v in (await firma_laden(f)).items() if k != "plan"}
    for sammlung, ausschluss in SICHERUNG_FIRMA:
        aus["data"][sammlung] = [{k: v for k, v in d.items() if k not in ausschluss} async for d in db()[sammlung].find({"firma_id": f}, {"_id": 0})]
    projekt_ids = [p["id"] for p in aus["data"]["projects"]]
    for sammlung in SICHERUNG_PLATTFORM:
        filt = {"$or": [{"firma_id": f}, {"owner_firma_id": f}, {"project_id": {"$in": projekt_ids}}]}
        aus["data"][sammlung] = [d async for d in db()[sammlung].find(filt, {"_id": 0})]
    await protokollieren(user, "export.sicherung", details={"sammlungen": len(aus["data"])})
    return aus


@router.get("/dateien.zip")
async def dateien_zip(hintergrund: BackgroundTasks, user: dict = Depends(rolle_noetig("inhaber"))):
    """Alle Dateien der Firma (Fotos, Dokumente, Anhänge) als ZIP – Ergänzung zur Datensicherung."""
    f = user["firma_id"]
    tmp = tempfile.NamedTemporaryFile(prefix="dateien-", suffix=".zip", delete=False)
    tmp.close()
    anzahl = 0
    with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_DEFLATED) as z:
        async for d in db().documents.find({"firma_id": f}, {"_id": 0, "id": 1, "path": 1, "filename": 1, "scope": 1}):
            pfad = d.get("path") or ""
            if pfad and os.path.isfile(pfad):
                z.write(pfad, f"{d.get('scope', 'datei')}/{d['id']}_{d.get('filename') or 'datei'}")
                anzahl += 1
    hintergrund.add_task(os.unlink, tmp.name)
    await protokollieren(user, "export.dateien", details={"dateien": anzahl})
    return FileResponse(tmp.name, media_type="application/zip", filename=f"dateien-{jetzt_iso()[:10]}.zip")


@router.get("/free-app.json")
async def free_app(user: dict = Depends(rolle_noetig("inhaber"))):
    """Daten im Format der kostenlosen App (Sicherungsdatei) — der Weg zurück steht immer offen."""
    f = user["firma_id"]
    firma = await firma_laden(f)
    company = {k: firma.get(k, v) for k, v in FIRMA_DEFAULTS.items()}
    company.update({"id": firma["id"], "created_at": firma.get("created_at")})
    projects, entries, invoices = [], [], []
    namen = await nutzernamen(f)
    async for p in db().projects.find({"firma_id": f}, {"_id": 0}):
        projects.append({"id": p["id"], "company_id": firma["id"], "name": p.get("name"), "color": p.get("color"), "customer_name": p.get("customer_name", ""),
                         "customer_address": p.get("customer_address", ""), "employee_name": p.get("employee_name", ""), "hourly_rate": p.get("hourly_rate", 0),
                         "notes": p.get("notes", ""), "archived": bool(p.get("archived")), "default_workers": p.get("default_workers", 1), "created_at": p.get("created_at")})
    async for e in db().entries.find({"firma_id": f}, {"_id": 0}):
        taetigkeit = e.get("activity", "")
        if e.get("user_id") and namen.get(e["user_id"]):
            taetigkeit = f"{namen[e['user_id']]}: {taetigkeit}".strip(": ")
        entries.append({"id": e["id"], "project_id": e["project_id"], "date": e["date"], "start_time": e["start_time"], "end_time": e["end_time"],
                        "pause_minutes": e.get("pause_minutes", 0), "activity": taetigkeit, "workers": e.get("workers", 1), "net_minutes": e.get("net_minutes", 0), "created_at": e.get("created_at")})
    async for r in db().invoices.find({"firma_id": f}, {"_id": 0}):
        invoices.append({"id": r["id"], "company_id": firma["id"], "project_id": r["project_id"], "year": r["year"], "month": r["month"], "seq": r["seq"], "number": r["number"],
                         "invoice_date": r.get("invoice_date"), "total_minutes": r.get("total_minutes"), "rate": r.get("rate"), "net": r.get("net"), "vat": r.get("vat"), "gross": r.get("gross"), "created_at": r.get("created_at")})
    await protokollieren(user, "export.free_app")
    return {"app": "stundenzettel", "version": 2, "exported_at": jetzt_iso(), "data": {"companies": [company], "projects": projects, "entries": entries, "invoices": invoices}}
