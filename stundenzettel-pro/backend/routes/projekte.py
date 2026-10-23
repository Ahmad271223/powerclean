"""Projekte (Objekte/Einsatzorte) mit Monatsdaten für Kalender und PDFs sowie Projektakte
(Kommentare, Fotos/Dateien, Checklisten, Kunden-Unterschriften je Kalenderwoche)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from auth import aktueller_nutzer, firma_laden, hat_rolle, jetzt_iso, rolle_noetig, schreibend
from dateien import KATEGORIEN_PROJEKT, datei_loeschen, datei_speichern, version_verknuepfen
from db import db
from feiertage import feiertage_set
from gemeinsam import projekt_fotos
from gemeinsam import (budget_info, eintrag_anreichern, firma_oeffentlich, kunde_laden, kundenadresse, neue_id, nutzernamen,
                       projekt_laden, projekt_leitung, projekt_normalisieren, projekt_sichtbar)
from models import ChecklisteIn, ChecklisteUpdateIn, KommentarIn, ProjektIn, UnterschriftIn
from protokoll import protokollieren
from sperre import monat_abgeschlossen
from zeiten import datum_pruefen, eintrag_minuten, lokal_jetzt, monatsletzter, rasterbereich

router = APIRouter(tags=["Projekte"])


def _sortierung(p: dict) -> tuple:
    return (p.get("last_activity_at") or p.get("created_at") or "", p.get("name") or "")


async def _projektdaten(user: dict, body: ProjektIn, alt: Optional[dict] = None) -> dict:
    daten = body.model_dump()
    kunde = await kunde_laden(user["firma_id"], daten.get("customer_id"))
    if daten.get("customer_id") and not kunde:
        raise HTTPException(400, "Kunde nicht gefunden.")
    if kunde:
        daten["customer_name"] = kunde["name"]
        daten["customer_address"] = kundenadresse(kunde)
        if not body.model_fields_set.intersection({"reverse_charge"}):
            daten["reverse_charge"] = bool(kunde.get("reverse_charge"))
    if daten.get("employee_ids"):
        gueltig = set()
        async for u in db().users.find({"firma_id": user["firma_id"], "id": {"$in": daten["employee_ids"]}}, {"_id": 0, "id": 1}):
            gueltig.add(u["id"])
        daten["employee_ids"] = [i for i in daten["employee_ids"] if i in gueltig]
    if not daten.get("hourly_rate"):
        firma = user.get("_firma") or await firma_laden(user["firma_id"])
        daten["hourly_rate"] = float(firma.get("default_hourly_rate") or 0)
    daten["name"] = daten["name"].strip()
    return daten


@router.get("/api/projekte")
async def liste(archiviert: bool = False, user: dict = Depends(aktueller_nutzer)):
    aus = []
    async for p in db().projects.find({"firma_id": user["firma_id"], "archived": archiviert}, {"_id": 0}):
        p = projekt_normalisieren(p)
        if projekt_sichtbar(user, p):
            aus.append(p)
    aus.sort(key=_sortierung, reverse=True)
    # Budget des laufenden Monats (eine Abfrage für alle Projekte)
    if any(float(p.get("budget_hours_month") or 0) for p in aus):
        heute = lokal_jetzt().date()
        von, bis = heute.replace(day=1).isoformat(), monatsletzter(heute.year, heute.month).isoformat()
        je_projekt: dict[str, int] = {}
        async for e in db().entries.find({"firma_id": user["firma_id"], "date": {"$gte": von, "$lte": bis}}, {"_id": 0, "project_id": 1, "net_minutes": 1, "workers": 1}):
            je_projekt[e["project_id"]] = je_projekt.get(e["project_id"], 0) + eintrag_minuten(e)
        for p in aus:
            p["budget"] = budget_info(p, je_projekt.get(p["id"], 0))
    return {"projekte": aus}


@router.post("/api/projekte")
async def anlegen(body: ProjektIn, user: dict = Depends(schreibend("buero"))):
    daten = await _projektdaten(user, body)
    p = {**daten, "id": neue_id(), "firma_id": user["firma_id"], "created_at": jetzt_iso(),
         "total_minutes": 0, "entry_count": 0, "last_activity_at": None}
    await db().projects.insert_one(dict(p))
    await protokollieren(user, "projekt.angelegt", p["name"])
    return {"projekt": projekt_normalisieren(p)}


@router.get("/api/projekte/{project_id}")
async def lesen(project_id: str, user: dict = Depends(aktueller_nutzer)):
    p = await projekt_laden(user, project_id)
    kunde = await kunde_laden(user["firma_id"], p.get("customer_id"))
    namen = await nutzernamen(user["firma_id"])
    p["employees"] = [{"id": i, "name": namen.get(i, "")} for i in p.get("employee_ids") or [] if i in namen]
    return {"projekt": p, "kunde": kunde}


@router.put("/api/projekte/{project_id}")
async def aendern(project_id: str, body: ProjektIn, user: dict = Depends(schreibend("buero"))):
    alt = await projekt_laden(user, project_id)
    daten = await _projektdaten(user, body, alt)
    daten["updated_at"] = jetzt_iso()
    await db().projects.update_one({"id": project_id, "firma_id": user["firma_id"]}, {"$set": daten})
    await protokollieren(user, "projekt.geaendert", daten["name"], details={"archiviert": daten["archived"]})
    return {"projekt": await projekt_laden(user, project_id)}


@router.delete("/api/projekte/{project_id}")
async def loeschen(project_id: str, erzwingen: bool = False, user: dict = Depends(schreibend("buero"))):
    """Projekt endgültig löschen. Nie mit laufenden Stempelungen; mit erfassten Zeiten nur durch den Inhaber mit ?erzwingen=true (sonst archivieren)."""
    p = await projekt_laden(user, project_id)
    filt = {"firma_id": user["firma_id"], "project_id": project_id}
    laufend = await db().stempel.count_documents(filt)
    if laufend:
        raise HTTPException(409, f"Auf diesem Projekt {'ist' if laufend == 1 else 'sind'} noch {laufend} Mitarbeiter eingestempelt. Bitte erst ausstempeln (oder vom Büro beenden).")
    bezahlt = await db().invoices.count_documents({"firma_id": user["firma_id"], "project_id": project_id, "status": "bezahlt"})
    if bezahlt:
        raise HTTPException(400, "Zu diesem Projekt gibt es bezahlte Rechnungen. Bitte archivieren statt löschen.")
    n = await db().entries.count_documents(filt)
    if n and not erzwingen:
        raise HTTPException(409, f"Zu diesem Projekt gibt es {n} erfasste Arbeitszeiten. Bitte archivieren. Endgültig löschen kann nur der Inhaber ausdrücklich (erzwingen).")
    if n and not hat_rolle(user, "inhaber"):
        raise HTTPException(403, "Projekte mit erfassten Arbeitszeiten darf nur der Inhaber endgültig löschen.")
    for sammlung in ("entries", "invoices", "comments", "checklists", "signatures"):
        await db()[sammlung].delete_many(filt)
    async for d in db().documents.find({"firma_id": user["firma_id"], "scope": "project", "ref_id": project_id}, {"_id": 0}):
        datei_loeschen(d)
    await db().documents.delete_many({"firma_id": user["firma_id"], "scope": "project", "ref_id": project_id})
    await db().stempel.delete_many(filt)
    await db().projects.delete_one({"id": project_id, "firma_id": user["firma_id"]})
    await protokollieren(user, "projekt.geloescht", p["name"], details={"eintraege": n, "erzwungen": bool(n)})
    return {"ok": True}


# ---------------------------------------------------------------- Monatsdaten (Kalender + PDFs)
@router.get("/api/projekte/{project_id}/monat")
async def monat(project_id: str, jahr: int = Query(..., ge=2025, le=2100), monat: int = Query(..., ge=1, le=12),
                user: dict = Depends(aktueller_nutzer)):
    p = await projekt_laden(user, project_id)
    firma = await firma_laden(user["firma_id"])
    von, bis = rasterbereich(jahr, monat)
    namen = await nutzernamen(user["firma_id"])
    leitung = projekt_leitung(user, p)
    filt = {"firma_id": user["firma_id"], "project_id": project_id, "date": {"$gte": von, "$lte": bis}}
    if not leitung:
        # Mitarbeiter sehen im Kalender nur eigene Zeiten und die "Anzahl"-Einträge des Büros
        filt["$or"] = [{"user_id": user["id"]}, {"user_id": None}]
    eintraege = []
    monatsminuten = 0
    erster, letzter = f"{jahr:04d}-{monat:02d}-01", monatsletzter(jahr, monat).isoformat()
    async for e in db().entries.find(filt, {"_id": 0}).sort([("date", 1), ("start_time", 1)]):
        eintraege.append(eintrag_anreichern(e, namen))
    if leitung:
        async for e in db().entries.find({"firma_id": user["firma_id"], "project_id": project_id, "date": {"$gte": erster, "$lte": letzter}}, {"_id": 0, "net_minutes": 1, "workers": 1}):
            monatsminuten += eintrag_minuten(e)
    rechnung = await db().invoices.find_one({"firma_id": user["firma_id"], "project_id": project_id, "year": jahr, "month": monat}, {"_id": 0}) if leitung else None
    unterschriften = []
    async for s in db().signatures.find({"firma_id": user["firma_id"], "project_id": project_id, "ersetzt": {"$ne": True},
                                         "week_monday": {"$gte": von, "$lte": bis}}, {"_id": 0}):
        unterschriften.append(s)
    ids = p.get("employee_ids") or []
    mitarbeiter = [{"id": i, "name": n} for i, n in namen.items() if (not ids or i in ids)] if leitung else []
    mitarbeiter.sort(key=lambda m: m["name"])
    jahre = {int(von[:4]), int(bis[:4])}
    frei = feiertage_set(sorted(jahre), firma.get("bundesland") or "")
    leistungen = [{"id": s["id"], "name": s["name"], "hourly_rate": s.get("hourly_rate") or 0} async for s in db().services.find({"firma_id": user["firma_id"], "active": True}, {"_id": 0}).sort("sort", 1)]
    fotos = await projekt_fotos(user["firma_id"], project_id, von, bis)
    return {"firma": firma_oeffentlich(firma, user), "projekt": p, "eintraege": eintraege, "rechnung": rechnung, "fotos": fotos,
            "unterschriften": unterschriften, "mitarbeiter": mitarbeiter, "raster": {"von": von, "bis": bis},
            "leitung": leitung, "budget": budget_info(p, monatsminuten) if leitung else None,
            "feiertage": {k: v for k, v in frei.items() if von <= k <= bis}, "leistungen": leistungen,
            "abgeschlossen": await monat_abgeschlossen(user["firma_id"], jahr, monat)}


@router.get("/api/projekte/{project_id}/zeiten")
async def zeiten(project_id: str, von: str, bis: str, user: dict = Depends(aktueller_nutzer)):
    await projekt_laden(user, project_id)
    try:
        datum_pruefen(von)
        datum_pruefen(bis)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    namen = await nutzernamen(user["firma_id"])
    filt = {"firma_id": user["firma_id"], "project_id": project_id, "date": {"$gte": von, "$lte": bis}}
    if not projekt_leitung(user, await projekt_laden(user, project_id)):
        filt["$or"] = [{"user_id": user["id"]}, {"user_id": None}]
    aus = []
    async for e in db().entries.find(filt, {"_id": 0}).sort([("date", 1), ("start_time", 1)]):
        aus.append(eintrag_anreichern(e, namen))
    return {"eintraege": aus}


# ---------------------------------------------------------------- Projektakte
@router.get("/api/projekte/{project_id}/akte")
async def akte(project_id: str, user: dict = Depends(aktueller_nutzer)):
    await projekt_laden(user, project_id)
    f = user["firma_id"]
    kommentare, dateien, checklisten, unterschriften = [], [], [], []
    async for k in db().comments.find({"firma_id": f, "project_id": project_id}, {"_id": 0}).sort("created_at", -1).limit(200):
        kommentare.append(k)
    async for d in db().documents.find({"firma_id": f, "scope": "project", "ref_id": project_id}, {"_id": 0, "path": 0}).sort("created_at", -1):
        dateien.append(d)
    async for c in db().checklists.find({"firma_id": f, "project_id": project_id}, {"_id": 0}).sort("created_at", -1):
        checklisten.append(c)
    async for s in db().signatures.find({"firma_id": f, "project_id": project_id}, {"_id": 0, "image": 0}).sort("week_monday", -1).limit(60):
        unterschriften.append(s)
    return {"kommentare": kommentare, "dateien": dateien, "checklisten": checklisten, "unterschriften": unterschriften,
            "kategorien": KATEGORIEN_PROJEKT}


@router.post("/api/projekte/{project_id}/kommentare")
async def kommentar(project_id: str, body: KommentarIn, user: dict = Depends(schreibend("mitarbeiter"))):
    await projekt_laden(user, project_id)
    k = {"id": neue_id(), "firma_id": user["firma_id"], "project_id": project_id, "user_id": user["id"],
         "user_name": user.get("name"), "text": body.text.strip(), "created_at": jetzt_iso()}
    await db().comments.insert_one(dict(k))
    return {"kommentar": k}


@router.delete("/api/kommentare/{kommentar_id}")
async def kommentar_loeschen(kommentar_id: str, user: dict = Depends(schreibend("mitarbeiter"))):
    k = await db().comments.find_one({"id": kommentar_id, "firma_id": user["firma_id"]}, {"_id": 0})
    if not k:
        raise HTTPException(404, "Kommentar nicht gefunden.")
    if k.get("user_id") != user["id"] and not hat_rolle(user, "buero"):
        raise HTTPException(403, "Nur eigene Kommentare lassen sich löschen.")
    await db().comments.delete_one({"id": kommentar_id})
    return {"ok": True}


@router.post("/api/projekte/{project_id}/dateien")
async def datei_hochladen(project_id: str, datei: UploadFile = File(...), kategorie: str = Form("Fotos"), note: str = Form(""),
                          date: str = Form(""), ordner: str = Form(""), ersetzt_id: str = Form(""), user: dict = Depends(schreibend("mitarbeiter"))):
    p = await projekt_laden(user, project_id)
    if date:   # erst prüfen, dann speichern – sonst bleibt bei ungültigen Angaben eine verwaiste Datei liegen
        try:
            datum_pruefen(date)
        except ValueError as exc:
            raise HTTPException(400, str(exc))
    meta = await datei_speichern(user["firma_id"], datei, user["id"])
    doc = {**meta, "firma_id": user["firma_id"], "scope": "project", "ref_id": project_id,
           "category": kategorie if kategorie in KATEGORIEN_PROJEKT else "Sonstiges", "note": note[:500], "date": date or None, "ordner": ordner.strip()[:120],
           "uploaded_by": user["id"], "uploaded_by_name": user.get("name"), "created_at": jetzt_iso()}
    doc = await version_verknuepfen(doc, ersetzt_id.strip() or None, user["firma_id"])
    await db().documents.insert_one(dict(doc))
    await protokollieren(user, "projektakte.datei", p["name"], details={"datei": meta["filename"], "kategorie": doc["category"], "version": doc["version"]})
    doc.pop("path", None)
    return {"dokument": doc}


@router.post("/api/projekte/{project_id}/checklisten")
async def checkliste_anlegen(project_id: str, body: ChecklisteIn, user: dict = Depends(schreibend("mitarbeiter"))):
    p = await projekt_laden(user, project_id)
    if not projekt_leitung(user, p):
        raise HTTPException(403, "Checklisten legen Büro und Vorarbeiter des Projekts an.")
    if body.date:
        try:
            datum_pruefen(body.date)
        except ValueError as exc:
            raise HTTPException(400, str(exc))
    c = {"id": neue_id(), "firma_id": user["firma_id"], "project_id": project_id, "name": body.name.strip(),
         "date": body.date or None, "created_by": user["id"], "created_at": jetzt_iso(),
         "items": [{"id": i.id or neue_id(), "text": i.text.strip(), "done": bool(i.done), "done_by": None, "done_at": None} for i in body.items]}
    await db().checklists.insert_one(dict(c))
    await protokollieren(user, "checkliste.angelegt", p["name"], details={"name": c["name"], "punkte": len(c["items"])})
    return {"checkliste": c}


@router.put("/api/checklisten/{checkliste_id}")
async def checkliste_aendern(checkliste_id: str, body: ChecklisteUpdateIn, user: dict = Depends(schreibend("mitarbeiter"))):
    c = await db().checklists.find_one({"id": checkliste_id, "firma_id": user["firma_id"]}, {"_id": 0})
    if not c:
        raise HTTPException(404, "Checkliste nicht gefunden.")
    await projekt_laden(user, c["project_id"])
    leitung = projekt_leitung(user, await projekt_laden(user, c["project_id"]))
    aenderung = {"updated_at": jetzt_iso()}
    if body.name is not None:
        if not leitung:
            raise HTTPException(403, "Umbenennen dürfen Büro und Vorarbeiter.")
        aenderung["name"] = body.name.strip()
    if body.items is not None:
        alt = {i["id"]: i for i in c.get("items", [])}
        neu = []
        if leitung:
            for i in body.items:
                vorher = alt.get(i.id or "")
                done_by, done_at = (vorher or {}).get("done_by"), (vorher or {}).get("done_at")
                if i.done and not (vorher or {}).get("done"):
                    done_by, done_at = user.get("name"), jetzt_iso()
                if not i.done:
                    done_by, done_at = None, None
                neu.append({"id": i.id or neue_id(), "text": i.text.strip(), "done": bool(i.done), "done_by": done_by, "done_at": done_at})
        else:
            # Mitarbeiter ändern nur den Erledigt-Status vorhandener Punkte; Punkte, die sie weglassen oder neu schicken, bleiben unverändert bzw. unberücksichtigt
            gesendet = {i.id: i for i in body.items if i.id}
            for vorher in c.get("items", []):
                punkt = dict(vorher)
                i = gesendet.get(vorher["id"])
                if i is not None and bool(i.done) != bool(vorher.get("done")):
                    punkt["done"] = bool(i.done)
                    punkt["done_by"], punkt["done_at"] = (user.get("name"), jetzt_iso()) if i.done else (None, None)
                neu.append(punkt)
        aenderung["items"] = neu
    await db().checklists.update_one({"id": checkliste_id}, {"$set": aenderung})
    return {"checkliste": await db().checklists.find_one({"id": checkliste_id}, {"_id": 0})}


@router.delete("/api/checklisten/{checkliste_id}")
async def checkliste_loeschen(checkliste_id: str, user: dict = Depends(schreibend("buero"))):
    r = await db().checklists.delete_one({"id": checkliste_id, "firma_id": user["firma_id"]})
    if not r.deleted_count:
        raise HTTPException(404, "Checkliste nicht gefunden.")
    return {"ok": True}


@router.post("/api/projekte/{project_id}/unterschriften")
async def unterschrift(project_id: str, body: UnterschriftIn, user: dict = Depends(schreibend("mitarbeiter"))):
    p = await projekt_laden(user, project_id)
    montag = datum_pruefen(body.week_monday)
    if montag.weekday() != 0:
        raise HTTPException(400, "week_monday muss ein Montag sein.")
    s = {"id": neue_id(), "firma_id": user["firma_id"], "project_id": project_id, "week_monday": body.week_monday,
         "signer_name": body.signer_name.strip(), "image": body.image, "signed_at": jetzt_iso(),
         "by_user_id": user["id"], "by_user_name": user.get("name"), "version": 1}
    # Vorhandene Unterschrift wird nie überschrieben: Mitarbeiter dürfen nicht ersetzen, das Büro nur mit Begründung – die alte bleibt als Version erhalten
    aktiv = await db().signatures.find_one({"firma_id": user["firma_id"], "project_id": project_id, "week_monday": body.week_monday, "ersetzt": {"$ne": True}}, {"_id": 0, "image": 0})
    if aktiv:
        if not hat_rolle(user, "buero"):
            raise HTTPException(409, f"Diese Woche ist bereits unterschrieben ({aktiv.get('signer_name')}). Ersetzen kann nur das Büro mit Begründung.")
        if not (body.grund or "").strip():
            raise HTTPException(400, "Bitte eine Begründung angeben, warum die vorhandene Unterschrift ersetzt wird.")
        await db().signatures.update_one({"id": aktiv["id"]}, {"$set": {"ersetzt": True, "ersetzt_at": jetzt_iso(), "ersetzt_von": user.get("name"), "ersetzt_grund": body.grund.strip()}})
        s["version"] = int(aktiv.get("version") or 1) + 1
        s["ersetzt_id"] = aktiv["id"]
        s["grund"] = body.grund.strip()
    await db().signatures.insert_one(dict(s))
    await protokollieren(user, "unterschrift.erfasst" if not aktiv else "unterschrift.ersetzt", p["name"],
                         details={"woche": body.week_monday, "unterzeichner": s["signer_name"], "version": s["version"], "grund": s.get("grund", ""), "vorher": (aktiv or {}).get("signer_name")})
    return {"unterschrift": s}


@router.get("/api/projekte/{project_id}/unterschriften")
async def unterschriften(project_id: str, von: str, bis: str, user: dict = Depends(aktueller_nutzer)):
    await projekt_laden(user, project_id)
    aus = []
    async for s in db().signatures.find({"firma_id": user["firma_id"], "project_id": project_id, "ersetzt": {"$ne": True},
                                         "week_monday": {"$gte": von, "$lte": bis}}, {"_id": 0}):
        aus.append(s)
    return {"unterschriften": aus}


@router.delete("/api/unterschriften/{unterschrift_id}")
async def unterschrift_loeschen(unterschrift_id: str, user: dict = Depends(schreibend("buero"))):
    s = await db().signatures.find_one({"id": unterschrift_id, "firma_id": user["firma_id"], "ersetzt": {"$ne": True}}, {"_id": 0, "image": 0})
    if not s:
        raise HTTPException(404, "Unterschrift nicht gefunden.")
    # Kein endgültiges Löschen: die Unterschrift bleibt als zurückgezogene Version nachvollziehbar
    await db().signatures.update_one({"id": unterschrift_id}, {"$set": {"ersetzt": True, "ersetzt_at": jetzt_iso(), "ersetzt_von": user.get("name"), "ersetzt_grund": "zurückgezogen"}})
    await protokollieren(user, "unterschrift.zurueckgezogen", s.get("project_id", ""), details={"woche": s.get("week_monday"), "unterzeichner": s.get("signer_name")})
    return {"ok": True}


@router.get("/api/projekte-kategorien")
async def kategorien(user: dict = Depends(rolle_noetig("mitarbeiter"))):
    return {"projekt": KATEGORIEN_PROJEKT}
