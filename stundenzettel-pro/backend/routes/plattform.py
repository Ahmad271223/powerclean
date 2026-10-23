"""Plattform-Ebene: Firmenverzeichnis, Projektleiter, Beteiligungen (Einladung/Annahme/Entfernen), Aufgaben, Anwesenheit,
freigegebene Wochen-Nachweise und Benachrichtigungen. Siehe plattform.py für das Rechtemodell."""
from __future__ import annotations

import re
import secrets
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

import config
from auth import aktueller_nutzer, firma_laden, hat_rolle, jetzt, jetzt_iso, rolle_noetig, schreibend
from dateien import datei_speichern
from db import db
from gemeinsam import neue_id, nutzernamen, projekt_laden, projekt_normalisieren
from models import (AufgabeIn, AufgabeStatusIn, AufgabeUpdateIn, AufgabeZuteilungIn, BeteiligungAntwortIn, EinladungFirmaIn,
                    FreigabeNamenIn, LeiterIn, TokenIn, VerzeichnisIn, WochenFreigabeIn)
from plattform import (zuteilungs_filter, AUFGABEN_STATUS, EINLADUNG_TAGE, GEWERKE, MITARBEITER_STATUS, OFFEN, PARTNER_STATUS, ROLLEN_BETEILIGUNG,
                       STATUS_NAMEN, aufgabe_laden, benachrichtigen, eigentuemer_benachrichtigen, firma_am_projekt, firma_kurz, leitung_noetig,
                       meine_benachrichtigungen, rolle_fuer_aufgabe, zugang)
from protokoll import protokollieren
from zeiten import datum_pruefen, lokal_jetzt, zeit_pruefen

router = APIRouter(tags=["Zusammenarbeit"])


def _link(pfad: str) -> str:
    return f"{config.BASE_URL}/#{pfad}"


# ---------------------------------------------------------------- Firmenverzeichnis

@router.get("/api/firma/verzeichnis")
async def verzeichnis_lesen(user: dict = Depends(rolle_noetig("buero"))):
    firma = await firma_laden(user["firma_id"])
    v = firma.get("verzeichnis") or {}
    return {"verzeichnis": {"sichtbar": bool(v.get("sichtbar")), "gewerke": v.get("gewerke") or [], "beschreibung": v.get("beschreibung") or "",
                            "ort": v.get("ort") or firma.get("city") or "", "regionen": v.get("regionen") or [],
                            "ausschreibungen_benachrichtigen": v.get("ausschreibungen_benachrichtigen", True)}, "gewerke_vorschlaege": GEWERKE,
            "art": firma.get("art") or "betrieb"}


@router.put("/api/firma/verzeichnis")
async def verzeichnis_aendern(body: VerzeichnisIn, user: dict = Depends(rolle_noetig("inhaber"))):
    v = body.model_dump()
    await db().firmen.update_one({"id": user["firma_id"]}, {"$set": {"verzeichnis": v, "updated_at": jetzt_iso()}})
    await protokollieren(user, "firma.verzeichnis", details={"sichtbar": v["sichtbar"], "gewerke": v["gewerke"]})
    return {"verzeichnis": v}


@router.get("/api/verzeichnis/firmen")
async def firmen_suchen(q: str = Query("", max_length=80), user: dict = Depends(rolle_noetig("buero"))):
    """Suche im gemeinsamen Firmenverzeichnis: nur Firmen, die sich sichtbar geschaltet haben, nur freigegebene Felder."""
    begriff = q.strip().lower()
    aus = []
    async for f in db().firmen.find({"verzeichnis.sichtbar": True, "id": {"$ne": user["firma_id"]}}, {"_id": 0, "id": 1, "name": 1, "city": 1, "verzeichnis": 1, "art": 1}):
        v = f.get("verzeichnis") or {}
        text = " ".join([f.get("name") or "", f.get("city") or "", v.get("ort") or "", " ".join(v.get("gewerke") or []), v.get("beschreibung") or ""]).lower()
        if begriff and begriff not in text and begriff != f["id"]:
            continue
        aus.append({"id": f["id"], "name": f.get("name"), "ort": v.get("ort") or f.get("city") or "", "gewerke": v.get("gewerke") or [],
                    "beschreibung": (v.get("beschreibung") or "")[:200], "art": f.get("art") or "betrieb"})
        if len(aus) >= 20:
            break
    aus.sort(key=lambda x: (x["name"] or "").lower())
    return {"firmen": aus}


# ---------------------------------------------------------------- Projektleiter (mehrere je Projekt)

@router.get("/api/projekte/{project_id}/leiter")
async def leiter_liste(project_id: str, user: dict = Depends(aktueller_nutzer)):
    z = await zugang(user, project_id)
    if not z["eigentuemer"]:
        raise HTTPException(404, "Projekt nicht gefunden.")
    liste = [l async for l in db().projekt_leiter.find({"project_id": project_id}, {"_id": 0}).sort("created_at", 1)]
    return {"leiter": liste}


@router.post("/api/projekte/{project_id}/leiter")
async def leiter_zuordnen(project_id: str, body: LeiterIn, user: dict = Depends(schreibend("buero"))):
    p = await projekt_laden(user, project_id)
    u = await db().users.find_one({"id": body.user_id, "firma_id": user["firma_id"], "active": {"$ne": False}}, {"_id": 0})
    if not u:
        raise HTTPException(400, "Mitarbeiter nicht gefunden.")
    doc = {"id": neue_id(), "project_id": project_id, "firma_id": user["firma_id"], "user_id": u["id"], "user_name": u.get("name"),
           "funktion": body.funktion.strip() or "Projektleitung", "created_at": jetzt_iso(), "created_by": user.get("name")}
    await db().projekt_leiter.delete_many({"project_id": project_id, "user_id": u["id"]})
    await db().projekt_leiter.insert_one(dict(doc))
    await db().projects.update_one({"id": project_id}, {"$addToSet": {"leiter_ids": u["id"]}})
    await benachrichtigen(user["firma_id"], "projektleitung", f"Du bist jetzt Projektleitung für „{p['name']}“ ({doc['funktion']}).", f"/projekte/{project_id}", user_ids=[u["id"]])
    await protokollieren(user, "projekt.leiter", p["name"], details={"user": u.get("name"), "funktion": doc["funktion"]})
    return {"leiter": doc}


@router.delete("/api/projekte/{project_id}/leiter/{user_id}")
async def leiter_entfernen(project_id: str, user_id: str, user: dict = Depends(schreibend("buero"))):
    p = await projekt_laden(user, project_id)
    await db().projekt_leiter.delete_many({"project_id": project_id, "user_id": user_id})
    await db().projects.update_one({"id": project_id}, {"$pull": {"leiter_ids": user_id}})
    await protokollieren(user, "projekt.leiter_entfernt", p["name"], details={"user_id": user_id})
    return {"ok": True}


# ---------------------------------------------------------------- Beteiligungen: Eigentümerseite

async def _beteiligung_anreichern(b: dict) -> dict:
    b = dict(b)
    b.pop("token", None)
    b["firma"] = await firma_kurz(b.get("firma_id")) if b.get("firma_id") else {"id": None, "name": b.get("firma_name") or "", "city": ""}
    b["rolle_name"] = ROLLEN_BETEILIGUNG.get(b.get("rolle"), b.get("rolle"))
    return b


@router.get("/api/projekte/{project_id}/beteiligungen")
async def beteiligungen_liste(project_id: str, user: dict = Depends(aktueller_nutzer)):
    z = await zugang(user, project_id)
    if not z["eigentuemer"]:
        raise HTTPException(404, "Projekt nicht gefunden.")
    aus = []
    async for b in db().beteiligungen.find({"project_id": project_id, "status": {"$ne": "entfernt"}}, {"_id": 0}).sort("created_at", 1):
        aus.append(await _beteiligung_anreichern(b))
    return {"beteiligungen": aus, "rollen": ROLLEN_BETEILIGUNG, "gewerke": GEWERKE, "leitung": z["leitung"]}


@router.post("/api/projekte/{project_id}/beteiligungen")
async def firma_einladen(project_id: str, body: EinladungFirmaIn, user: dict = Depends(schreibend("mitarbeiter"))):
    z = await zugang(user, project_id)
    leitung_noetig(z)
    p = z["projekt"]
    firma_id, firma_name, email = body.firma_id, (body.firma_name or "").strip(), (body.email or "").lower().strip()
    if firma_id:
        f = await db().firmen.find_one({"id": firma_id}, {"_id": 0, "id": 1, "name": 1})
        if not f:
            raise HTTPException(404, "Firma nicht gefunden.")
        firma_name = f["name"]
    elif email:
        inhaber = await db().users.find_one({"email": email, "active": {"$ne": False}}, {"_id": 0, "firma_id": 1})
        if inhaber:   # E-Mail gehört schon zu einer registrierten Firma → als registrierte Firma einladen
            firma_id = inhaber["firma_id"]
            f = await db().firmen.find_one({"id": firma_id}, {"_id": 0, "name": 1})
            firma_name = (f or {}).get("name") or firma_name
    if firma_id == user["firma_id"]:
        raise HTTPException(400, "Die eigene Firma ist bereits Eigentümerin des Projekts.")
    if firma_id and await db().beteiligungen.find_one({"project_id": project_id, "firma_id": firma_id, "status": {"$in": ["eingeladen", "aktiv"]}}):
        raise HTTPException(409, "Diese Firma ist bereits eingeladen oder beteiligt.")
    if not firma_id and email and await db().beteiligungen.find_one({"project_id": project_id, "email": email, "status": "eingeladen"}):
        raise HTTPException(409, "An diese E-Mail-Adresse wurde bereits eingeladen.")
    token = secrets.token_urlsafe(24)
    b = {"id": neue_id(), "project_id": project_id, "owner_firma_id": p["firma_id"], "firma_id": firma_id, "firma_name": firma_name, "email": email,
         "gewerk": body.gewerk.strip(), "rolle": body.rolle, "nachricht": (body.nachricht or "").strip(), "status": "eingeladen",
         "token": token, "token_bis": (jetzt() + timedelta(days=EINLADUNG_TAGE)).isoformat(), "eingeladen_von": user.get("name"),
         "eingeladen_von_id": user["id"], "lokales_project_id": None, "freigaben": {"namen": False}, "created_at": jetzt_iso()}
    await db().beteiligungen.insert_one(dict(b))
    eigentuemer = await firma_kurz(p["firma_id"])
    if firma_id:
        await benachrichtigen(firma_id, "projekteinladung", f"{eigentuemer['name']} lädt euch zum Projekt „{p['name']}“ ein ({b['gewerk'] or b['rolle']}).", "/zusammenarbeit")
    await protokollieren(user, "projekt.firma_eingeladen", p["name"], details={"firma": firma_name, "gewerk": b["gewerk"], "per_email": bool(email and not firma_id)})
    aus = await _beteiligung_anreichern(b)
    aus["einladung_link"] = _link(f"/projekteinladung/{token}")
    return {"beteiligung": aus}


@router.delete("/api/projekte/{project_id}/beteiligungen/{beteiligung_id}")
async def beteiligung_entfernen(project_id: str, beteiligung_id: str, user: dict = Depends(schreibend("mitarbeiter"))):
    z = await zugang(user, project_id)
    leitung_noetig(z)
    b = await db().beteiligungen.find_one({"id": beteiligung_id, "project_id": project_id}, {"_id": 0})
    if not b:
        raise HTTPException(404, "Beteiligung nicht gefunden.")
    await db().beteiligungen.update_one({"id": beteiligung_id}, {"$set": {"status": "entfernt", "entfernt_at": jetzt_iso(), "entfernt_von": user.get("name")}})
    if b.get("lokales_project_id"):
        await db().projects.update_one({"id": b["lokales_project_id"]}, {"$set": {"verknuepft.status": "entfernt"}})
    if b.get("firma_id"):
        await benachrichtigen(b["firma_id"], "beteiligung_entfernt", f"Eure Beteiligung am Projekt „{z['projekt']['name']}“ wurde beendet.", "/zusammenarbeit")
    await protokollieren(user, "projekt.firma_entfernt", z["projekt"]["name"], details={"firma": b.get("firma_name")})
    return {"ok": True}


# ---------------------------------------------------------------- Beteiligungen: Partnerseite

async def _annehmen(user: dict, b: dict) -> dict:
    """Einladung annehmen: verknüpftes lokales Projekt in der Partnerfirma anlegen, Beteiligung aktiv schalten."""
    p = await db().projects.find_one({"id": b["project_id"]}, {"_id": 0})
    if not p:
        raise HTTPException(404, "Das Projekt gibt es nicht mehr.")
    eigentuemer = await firma_kurz(p["firma_id"])
    firma = await firma_laden(user["firma_id"])
    lokal = projekt_normalisieren({
        "id": neue_id(), "firma_id": user["firma_id"], "name": f"{eigentuemer['name']}: {p['name']}"[:160],
        "customer_name": eigentuemer["name"], "customer_address": "\n".join(t for t in [eigentuemer.get("street") or "", f"{eigentuemer.get('zip_code') or ''} {eigentuemer.get('city') or ''}".strip()] if t),
        "address": p.get("address") or "", "hourly_rate": float(firma.get("default_hourly_rate") or 0), "color": p.get("color") or "#1D4ED8",
        "employee_ids": [], "archived": False, "notes": b.get("nachricht") or "",
        "verknuepft": {"project_id": p["id"], "owner_firma_id": p["firma_id"], "owner_firma_name": eigentuemer["name"], "beteiligung_id": b["id"],
                       "gewerk": b.get("gewerk"), "rolle": b.get("rolle"), "status": "aktiv"},
        "created_at": jetzt_iso(),
    })
    await db().projects.insert_one(dict(lokal))
    aenderung = {"status": "aktiv", "firma_id": user["firma_id"], "firma_name": firma.get("name"), "lokales_project_id": lokal["id"],
                 "angenommen_at": jetzt_iso(), "kontakt_user_id": user["id"], "kontakt_name": user.get("name"), "token": None}
    await db().beteiligungen.update_one({"id": b["id"]}, {"$set": aenderung})
    b = {**b, **aenderung}
    await eigentuemer_benachrichtigen(projekt_normalisieren(p), "einladung_angenommen", f"{firma.get('name')} hat die Einladung zum Projekt „{p['name']}“ angenommen.", f"/projekte/{p['id']}")
    await protokollieren(user, "beteiligung.angenommen", p["name"], details={"auftraggeber": eigentuemer["name"]})
    await protokollieren(user, "projekt.firma_beigetreten", p["name"], details={"firma": firma.get("name")}, firma_id=p["firma_id"])
    return b


@router.get("/api/beteiligungen")
async def meine_beteiligungen(user: dict = Depends(rolle_noetig("buero"))):
    """Offene Einladungen und aktive Beteiligungen der eigenen Firma (Partnerseite)."""
    einladungen, aktiv = [], []
    async for b in db().beteiligungen.find({"firma_id": user["firma_id"], "status": {"$in": ["eingeladen", "aktiv"]}}, {"_id": 0}).sort("created_at", -1):
        p = await db().projects.find_one({"id": b["project_id"]}, {"_id": 0, "name": 1, "address": 1, "firma_id": 1, "archived": 1})
        eintrag = {**(await _beteiligung_anreichern(b)), "projekt": {"name": (p or {}).get("name"), "address": (p or {}).get("address")},
                   "auftraggeber": await firma_kurz(b.get("owner_firma_id"))}
        (einladungen if b["status"] == "eingeladen" else aktiv).append(eintrag)
    return {"einladungen": einladungen, "aktiv": aktiv}


@router.post("/api/beteiligungen/{beteiligung_id}/antwort")
async def einladung_beantworten(beteiligung_id: str, body: BeteiligungAntwortIn, user: dict = Depends(rolle_noetig("buero"))):
    b = await db().beteiligungen.find_one({"id": beteiligung_id, "firma_id": user["firma_id"], "status": "eingeladen"}, {"_id": 0})
    if not b:
        raise HTTPException(404, "Einladung nicht gefunden.")
    if body.annehmen:
        return {"beteiligung": await _beteiligung_anreichern(await _annehmen(user, b))}
    await db().beteiligungen.update_one({"id": beteiligung_id}, {"$set": {"status": "abgelehnt", "abgelehnt_at": jetzt_iso()}})
    p = await db().projects.find_one({"id": b["project_id"]}, {"_id": 0})
    if p:
        await eigentuemer_benachrichtigen(projekt_normalisieren(p), "einladung_abgelehnt", f"{b.get('firma_name')} hat die Einladung zum Projekt „{p['name']}“ abgelehnt.", f"/projekte/{p['id']}")
    await protokollieren(user, "beteiligung.abgelehnt", (p or {}).get("name", ""))
    return {"beteiligung": {**b, "status": "abgelehnt"}}


@router.post("/api/beteiligungen/token")
async def einladung_per_link(body: TokenIn, user: dict = Depends(rolle_noetig("buero"))):
    """Einladungslink einlösen (auch für Firmen, die sich erst nach der Einladung registriert haben)."""
    b = await db().beteiligungen.find_one({"token": body.token, "status": "eingeladen"}, {"_id": 0})
    if not b or (b.get("token_bis") or "") < jetzt().isoformat():
        raise HTTPException(404, "Einladung ungültig oder abgelaufen.")
    if b.get("firma_id") and b["firma_id"] != user["firma_id"]:
        raise HTTPException(403, "Diese Einladung gilt für eine andere Firma.")
    if await db().beteiligungen.find_one({"project_id": b["project_id"], "firma_id": user["firma_id"], "status": "aktiv"}):
        raise HTTPException(409, "Eure Firma ist an diesem Projekt bereits beteiligt.")
    return {"beteiligung": await _beteiligung_anreichern(await _annehmen(user, b))}


@router.put("/api/beteiligungen/{beteiligung_id}/freigaben")
async def freigaben_setzen(beteiligung_id: str, body: FreigabeNamenIn, user: dict = Depends(rolle_noetig("buero"))):
    b = await db().beteiligungen.find_one({"id": beteiligung_id, "firma_id": user["firma_id"], "status": "aktiv"}, {"_id": 0})
    if not b:
        raise HTTPException(404, "Beteiligung nicht gefunden.")
    await db().beteiligungen.update_one({"id": beteiligung_id}, {"$set": {"freigaben.namen": bool(body.namen)}})
    await protokollieren(user, "beteiligung.freigaben", b.get("firma_name", ""), details={"namen": bool(body.namen)})
    return {"freigaben": {"namen": bool(body.namen)}}


# ---------------------------------------------------------------- Übersicht

@router.get("/api/plattform/uebersicht")
async def uebersicht(user: dict = Depends(rolle_noetig("buero"))):
    heute = lokal_jetzt().date().isoformat()
    projekte = []
    async for p in db().projects.find({"firma_id": user["firma_id"], "archived": False}, {"_id": 0, "id": 1, "name": 1, "address": 1, "leiter_ids": 1, "color": 1, "verknuepft": 1}):
        if p.get("verknuepft"):
            continue
        firmen = await db().beteiligungen.count_documents({"project_id": p["id"], "status": "aktiv"})
        eingeladen = await db().beteiligungen.count_documents({"project_id": p["id"], "status": "eingeladen"})
        if not firmen and not eingeladen and not p.get("leiter_ids"):
            continue
        offen = await db().aufgaben.count_documents({"project_id": p["id"], "status": {"$in": list(OFFEN)}})
        heute_n = await db().aufgaben.count_documents({"project_id": p["id"], "datum": heute, "status": {"$in": list(OFFEN)}})
        lieferungen_heute = await db().lieferungen.count_documents({"project_id": p["id"], "geplant_am": heute, "status": {"$nin": ["storniert", "abgeschlossen"]}})
        maengel_offen = await db().maengel.count_documents({"project_id": p["id"], "status": {"$ne": "abgenommen"}})
        berichte_offen = await db().tagesberichte.count_documents({"project_id": p["id"], "status": "eingereicht"})
        projekte.append({"id": p["id"], "name": p["name"], "address": p.get("address") or "", "color": p.get("color"), "leiter": len(p.get("leiter_ids") or []),
                         "firmen": firmen, "eingeladen": eingeladen, "aufgaben_offen": offen, "aufgaben_heute": heute_n, "lieferungen_heute": lieferungen_heute,
                         "maengel_offen": maengel_offen, "berichte_offen": berichte_offen})
    b = await meine_beteiligungen(user)
    ungelesen = sum(1 for n in await meine_benachrichtigungen(user, 100) if not n["gelesen"])
    return {"projekte": projekte, "einladungen": b["einladungen"], "beteiligungen": b["aktiv"], "ungelesen": ungelesen}


# ---------------------------------------------------------------- Aufgaben

def _aufgabe_pruefen(daten: dict) -> None:
    if daten.get("datum"):
        datum_pruefen(daten["datum"])
    for k in ("start_time", "end_time"):
        if daten.get(k):
            daten[k] = zeit_pruefen(daten[k])


async def _firma_am_projekt(project_id: str, projekt: dict, firma_id: Optional[str]) -> tuple[str, Optional[dict]]:
    return await firma_am_projekt(project_id, projekt, firma_id)


async def _aufgabe_anreichern(a: dict, namen_cache: dict) -> dict:
    a = dict(a)
    fid = a.get("firma_id")
    if fid not in namen_cache:
        namen_cache[fid] = (await firma_kurz(fid))["name"]
    a["firma_name"] = namen_cache[fid]
    a["status_name"] = STATUS_NAMEN.get(a.get("status"), a.get("status"))
    a["fotos_anzahl"] = await db().documents.count_documents({"scope": "aufgabe", "ref_id": a["id"]})
    return a


@router.get("/api/projekte/{project_id}/aufgaben")
async def aufgaben_liste(project_id: str, von: Optional[str] = None, bis: Optional[str] = None, user: dict = Depends(aktueller_nutzer)):
    z = await zugang(user, project_id)
    filt: dict = {"project_id": project_id}
    if von and bis:
        filt["datum"] = {"$gte": von, "$lte": bis}
    if not (z["eigentuemer"] and z["leitung"]):
        filt["firma_id"] = user["firma_id"]
        if not z["leitung"] and not hat_rolle(user, "buero"):
            filt["$or"] = zuteilungs_filter(user["id"])
    cache: dict = {}
    aus = [await _aufgabe_anreichern(a, cache) async for a in db().aufgaben.find(filt, {"_id": 0}).sort([("datum", 1), ("start_time", 1)]).limit(2000)]
    firmen = [{"id": z["projekt"]["firma_id"], "name": (await firma_kurz(z["projekt"]["firma_id"]))["name"], "eigentuemer": True}]
    if z["eigentuemer"] and z["leitung"]:
        async for b in db().beteiligungen.find({"project_id": project_id, "status": "aktiv"}, {"_id": 0}):
            firmen.append({"id": b["firma_id"], "name": b.get("firma_name"), "gewerk": b.get("gewerk"), "eigentuemer": False})
    return {"aufgaben": aus, "firmen": firmen, "status": STATUS_NAMEN, "leitung": bool(z["eigentuemer"] and z["leitung"]), "eigentuemer": z["eigentuemer"],
            "gewerke": GEWERKE, "lokales_project_id": (z["lokal"] or {}).get("id") if not z["eigentuemer"] else None}


@router.post("/api/projekte/{project_id}/aufgaben")
async def aufgabe_anlegen(project_id: str, body: AufgabeIn, user: dict = Depends(schreibend("mitarbeiter"))):
    z = await zugang(user, project_id)
    leitung_noetig(z)
    daten = body.model_dump()
    _aufgabe_pruefen(daten)
    firma_id, _ = await _firma_am_projekt(project_id, z["projekt"], daten.get("firma_id"))
    status = "zugewiesen" if firma_id != z["projekt"]["firma_id"] or daten.get("mitarbeiter_ids") else "geplant"
    a = {**daten, "id": neue_id(), "project_id": project_id, "owner_firma_id": z["projekt"]["firma_id"], "firma_id": firma_id, "status": status,
         "verlauf": [{"status": status, "user_name": user.get("name"), "at": jetzt_iso()}], "erstellt_von": user.get("name"), "erstellt_von_id": user["id"],
         "created_at": jetzt_iso(), "updated_at": jetzt_iso()}
    if firma_id != user["firma_id"]:
        a["mitarbeiter_ids"], a["vorarbeiter_user_id"] = [], None     # Zuteilung macht die beauftragte Firma selbst
    await db().aufgaben.insert_one(dict(a))
    if firma_id != z["projekt"]["firma_id"]:
        await benachrichtigen(firma_id, "aufgabe_neu", f"Neue Aufgabe im Projekt „{z['projekt']['name']}“: {a['titel']} ({a['datum']}).", "/aufgaben", mindestens="vorarbeiter")
    await protokollieren(user, "aufgabe.angelegt", a["titel"], details={"projekt": z["projekt"]["name"], "firma_id": firma_id, "datum": a["datum"]})
    return {"aufgabe": await _aufgabe_anreichern(a, {})}


@router.get("/api/aufgaben/meine")
async def meine_aufgaben(user: dict = Depends(aktueller_nutzer)):
    """Aufgaben der eigenen Firma für die Tagesansicht: Büro/Vorarbeiter alle, Mitarbeiter nur zugeteilte oder ohne Zuteilung."""
    von = (lokal_jetzt().date() - timedelta(days=14)).isoformat()
    filt: dict = {"firma_id": user["firma_id"], "status": {"$in": list(OFFEN)}, "datum": {"$gte": von}}
    if not hat_rolle(user, "vorarbeiter"):
        filt["$or"] = zuteilungs_filter(user["id"])
    cache: dict = {}
    aus = []
    projekte: dict = {}
    async for a in db().aufgaben.find(filt, {"_id": 0}).sort([("datum", 1), ("start_time", 1)]).limit(500):
        a = await _aufgabe_anreichern(a, cache)
        if a["project_id"] not in projekte:
            p = await db().projects.find_one({"id": a["project_id"]}, {"_id": 0, "name": 1, "address": 1, "firma_id": 1})
            projekte[a["project_id"]] = {"name": (p or {}).get("name"), "address": (p or {}).get("address"), "auftraggeber": (await firma_kurz((p or {}).get("firma_id")))["name"]}
        a["projekt"] = projekte[a["project_id"]]
        aus.append(a)
    return {"aufgaben": aus, "status": STATUS_NAMEN, "heute": lokal_jetzt().date().isoformat()}


@router.get("/api/aufgaben/{aufgabe_id}")
async def aufgabe_lesen(aufgabe_id: str, user: dict = Depends(aktueller_nutzer)):
    a, z = await aufgabe_laden(user, aufgabe_id)
    fotos = [d async for d in db().documents.find({"scope": "aufgabe", "ref_id": aufgabe_id}, {"_id": 0, "path": 0}).sort("created_at", 1)]
    rolle = rolle_fuer_aufgabe(user, a, z)
    erlaubt = list(AUFGABEN_STATUS) if rolle == "leitung" else sorted(PARTNER_STATUS) if rolle == "firma" else sorted(MITARBEITER_STATUS) if rolle == "mitarbeiter" else []
    mitarbeiter = []
    if rolle in ("firma", "leitung") and a.get("firma_id") == user["firma_id"]:
        async for u in db().users.find({"firma_id": user["firma_id"], "active": {"$ne": False}}, {"_id": 0, "id": 1, "name": 1, "role": 1}):
            mitarbeiter.append(u)
    return {"aufgabe": await _aufgabe_anreichern(a, {}), "fotos": fotos, "rolle": rolle, "status_erlaubt": erlaubt, "mitarbeiter": mitarbeiter,
            "projekt": {"id": z["projekt"]["id"], "name": z["projekt"]["name"], "address": z["projekt"].get("address")}}


@router.put("/api/aufgaben/{aufgabe_id}")
async def aufgabe_aendern(aufgabe_id: str, body: AufgabeUpdateIn, user: dict = Depends(schreibend("mitarbeiter"))):
    a, z = await aufgabe_laden(user, aufgabe_id)
    leitung_noetig(z)
    daten = body.model_dump(exclude_unset=True)
    _aufgabe_pruefen(daten)
    if "firma_id" in daten:
        daten["firma_id"], _ = await _firma_am_projekt(a["project_id"], z["projekt"], daten.get("firma_id"))
        if daten["firma_id"] != a.get("firma_id"):
            daten["mitarbeiter_ids"], daten["vorarbeiter_user_id"] = [], None
    daten["updated_at"] = jetzt_iso()
    await db().aufgaben.update_one({"id": aufgabe_id}, {"$set": daten})
    await protokollieren(user, "aufgabe.geaendert", a["titel"], details={"felder": sorted(k for k in daten if k != "updated_at")})
    return {"aufgabe": await _aufgabe_anreichern({**a, **daten}, {})}


@router.delete("/api/aufgaben/{aufgabe_id}")
async def aufgabe_loeschen(aufgabe_id: str, user: dict = Depends(schreibend("mitarbeiter"))):
    a, z = await aufgabe_laden(user, aufgabe_id)
    leitung_noetig(z)
    await db().aufgaben.delete_one({"id": aufgabe_id})
    await protokollieren(user, "aufgabe.geloescht", a["titel"])
    return {"ok": True}


@router.post("/api/aufgaben/{aufgabe_id}/status")
async def aufgabe_status(aufgabe_id: str, body: AufgabeStatusIn, user: dict = Depends(aktueller_nutzer)):
    a, z = await aufgabe_laden(user, aufgabe_id)
    rolle = rolle_fuer_aufgabe(user, a, z)
    erlaubt = set(AUFGABEN_STATUS) if rolle == "leitung" else PARTNER_STATUS if rolle == "firma" else MITARBEITER_STATUS if rolle == "mitarbeiter" else set()
    if body.status not in erlaubt:
        raise HTTPException(403, "Diesen Status darfst du hier nicht setzen." if rolle else "Dafür fehlt die Berechtigung.")
    schritt = {"status": body.status, "user_name": user.get("name"), "firma_id": user["firma_id"], "at": jetzt_iso(), "kommentar": (body.kommentar or "").strip()[:500]}
    await db().aufgaben.update_one({"id": aufgabe_id}, {"$set": {"status": body.status, "updated_at": jetzt_iso()}, "$push": {"verlauf": schritt}})
    if body.status == "eingereicht":
        await eigentuemer_benachrichtigen(z["projekt"], "aufgabe_eingereicht", f"„{a['titel']}“ wurde zur Prüfung eingereicht ({user.get('name')}).", f"/projekte/{a['project_id']}")
    elif body.status in ("abgenommen", "abgeschlossen") and a.get("firma_id") != z["projekt"]["firma_id"]:
        await benachrichtigen(a["firma_id"], "aufgabe_abgenommen", f"„{a['titel']}“ ist {STATUS_NAMEN[body.status].lower()}.", "/aufgaben", mindestens="vorarbeiter")
    await protokollieren(user, "aufgabe.status", a["titel"], details={"status": body.status})
    return {"aufgabe": await _aufgabe_anreichern({**a, "status": body.status, "verlauf": (a.get("verlauf") or []) + [schritt]}, {})}


@router.post("/api/aufgaben/{aufgabe_id}/zuteilung")
async def aufgabe_zuteilen(aufgabe_id: str, body: AufgabeZuteilungIn, user: dict = Depends(aktueller_nutzer)):
    """Die beauftragte Firma teilt Vorarbeiter und Mitarbeiter aus den eigenen Reihen zu."""
    a, z = await aufgabe_laden(user, aufgabe_id)
    rolle = rolle_fuer_aufgabe(user, a, z)
    if rolle not in ("firma", "leitung") or a.get("firma_id") != user["firma_id"]:
        raise HTTPException(403, "Zuteilen darf nur Büro oder Vorarbeiter der beauftragten Firma.")
    ids = set(body.mitarbeiter_ids or [])
    if body.vorarbeiter_user_id:
        ids.add(body.vorarbeiter_user_id)
    gueltig = {u["id"] async for u in db().users.find({"firma_id": user["firma_id"], "id": {"$in": list(ids)}, "active": {"$ne": False}}, {"_id": 0, "id": 1})}
    if ids - gueltig:
        raise HTTPException(400, "Nur eigene aktive Mitarbeiter lassen sich zuteilen.")
    aenderung = {"mitarbeiter_ids": [i for i in body.mitarbeiter_ids if i in gueltig], "vorarbeiter_user_id": body.vorarbeiter_user_id if body.vorarbeiter_user_id in gueltig else None,
                 "updated_at": jetzt_iso()}
    if a.get("status") == "geplant":
        aenderung["status"] = "zugewiesen"
    await db().aufgaben.update_one({"id": aufgabe_id}, {"$set": aenderung})
    neu = [i for i in aenderung["mitarbeiter_ids"] if i not in (a.get("mitarbeiter_ids") or [])]
    if neu:
        await benachrichtigen(user["firma_id"], "aufgabe_zugeteilt", f"Neue Aufgabe für dich: {a['titel']} am {a.get('datum')}.", "/aufgaben", user_ids=neu)
    await protokollieren(user, "aufgabe.zuteilung", a["titel"], details={"mitarbeiter": len(aenderung["mitarbeiter_ids"])})
    return {"aufgabe": await _aufgabe_anreichern({**a, **aenderung}, {})}


@router.post("/api/aufgaben/{aufgabe_id}/fotos")
async def aufgabe_foto(aufgabe_id: str, datei: UploadFile = File(...), note: str = Form(""), user: dict = Depends(aktueller_nutzer)):
    a, z = await aufgabe_laden(user, aufgabe_id)
    if not rolle_fuer_aufgabe(user, a, z):
        raise HTTPException(403, "Dafür fehlt die Berechtigung.")
    meta = await datei_speichern(user["firma_id"], datei)
    if not meta["mime"].startswith("image/"):
        raise HTTPException(400, "Bitte ein Foto hochladen.")
    doc = {**meta, "firma_id": user["firma_id"], "scope": "aufgabe", "ref_id": aufgabe_id, "project_id": a["project_id"], "category": "Fotos",
           "note": note[:500], "date": a.get("datum"), "uploaded_by": user["id"], "uploaded_by_name": user.get("name"), "created_at": jetzt_iso()}
    await db().documents.insert_one(dict(doc))
    await db().aufgaben.update_one({"id": aufgabe_id}, {"$set": {"updated_at": jetzt_iso()}})
    doc.pop("path", None)
    return {"dokument": doc}


# ---------------------------------------------------------------- Anwesenheit (Eigentümerseite)

@router.get("/api/projekte/{project_id}/anwesenheit")
async def anwesenheit(project_id: str, user: dict = Depends(aktueller_nutzer)):
    """Je Firma: gerade eingestempelt, heute gearbeitet, heute eingeplant (Aufgaben). Namen fremder Firmen nur nach deren Freigabe."""
    z = await zugang(user, project_id)
    leitung_noetig(z)
    heute = lokal_jetzt().date().isoformat()
    p = z["projekt"]
    zeilen = []

    async def zeile(firma_id: str, lokal_id: str, name: str, namen_frei: bool, gewerk: str = "", eigentuemer: bool = False) -> dict:
        namen = await nutzernamen(firma_id)
        aktiv = [namen.get(s.get("user_id"), "") async for s in db().stempel.find({"firma_id": firma_id, "project_id": lokal_id}, {"_id": 0, "user_id": 1})]
        heute_ids = {e.get("user_id") async for e in db().entries.find({"firma_id": firma_id, "project_id": lokal_id, "date": heute}, {"_id": 0, "user_id": 1}) if e.get("user_id")}
        geplant = 0
        async for a in db().aufgaben.find({"project_id": project_id, "firma_id": firma_id, "datum": heute, "status": {"$in": list(OFFEN)}}, {"_id": 0, "mitarbeiter_ids": 1}):
            geplant += max(1, len(a.get("mitarbeiter_ids") or []))
        return {"firma_id": firma_id, "name": name, "gewerk": gewerk, "eigentuemer": eigentuemer, "aktiv": len(aktiv), "heute": len(heute_ids), "geplant": geplant,
                "namen_aktiv": sorted(n for n in aktiv if n) if namen_frei else [], "namen_heute": sorted(namen.get(i, "") for i in heute_ids) if namen_frei else [],
                "namen_freigegeben": namen_frei}

    zeilen.append(await zeile(p["firma_id"], p["id"], (await firma_kurz(p["firma_id"]))["name"], True, eigentuemer=True))
    async for b in db().beteiligungen.find({"project_id": project_id, "status": "aktiv"}, {"_id": 0}):
        if b.get("lokales_project_id"):
            zeilen.append(await zeile(b["firma_id"], b["lokales_project_id"], b.get("firma_name") or "", bool((b.get("freigaben") or {}).get("namen")), b.get("gewerk") or ""))
    return {"heute": heute, "firmen": zeilen, "gesamt": {"aktiv": sum(x["aktiv"] for x in zeilen), "heute": sum(x["heute"] for x in zeilen), "geplant": sum(x["geplant"] for x in zeilen)},
            "hinweis": "Eingestempelt und gearbeitet sind Selbstauskünfte der Mitarbeiter über die Stempeluhr; eingeplant stammt aus den Aufgaben."}


# ---------------------------------------------------------------- Wochen-Nachweise: Partner gibt frei, Eigentümer sieht

async def _lokal_mit_verknuepfung(user: dict, lokal_id: str) -> tuple[dict, dict]:
    lokal = await projekt_laden(user, lokal_id)
    v = lokal.get("verknuepft") or {}
    if not v.get("project_id") or v.get("status") == "entfernt":
        raise HTTPException(400, "Dieses Projekt ist mit keinem Auftraggeber-Projekt verknüpft.")
    return lokal, v


@router.get("/api/projekte/{project_id}/freigaben")
async def freigaben_liste(project_id: str, user: dict = Depends(rolle_noetig("buero"))):
    _, v = await _lokal_mit_verknuepfung(user, project_id)
    liste = [f async for f in db().freigaben.find({"beteiligung_id": v["beteiligung_id"]}, {"_id": 0}).sort("week_monday", -1)]
    return {"freigaben": liste, "auftraggeber": v.get("owner_firma_name")}


@router.post("/api/projekte/{project_id}/freigaben")
async def woche_freigeben(project_id: str, body: WochenFreigabeIn, user: dict = Depends(rolle_noetig("buero"))):
    lokal, v = await _lokal_mit_verknuepfung(user, project_id)
    montag = datum_pruefen(body.week_monday)
    if montag.weekday() != 0:
        raise HTTPException(400, "Bitte den Montag der Woche angeben.")
    f = {"id": neue_id(), "project_id": v["project_id"], "beteiligung_id": v["beteiligung_id"], "firma_id": user["firma_id"], "lokales_project_id": lokal["id"],
         "week_monday": montag.isoformat(), "freigegeben_von": user.get("name"), "created_at": jetzt_iso()}
    await db().freigaben.delete_many({"beteiligung_id": v["beteiligung_id"], "week_monday": f["week_monday"]})
    await db().freigaben.insert_one(dict(f))
    p = await db().projects.find_one({"id": v["project_id"]}, {"_id": 0})
    if p:
        firma = await firma_laden(user["firma_id"])
        await eigentuemer_benachrichtigen(projekt_normalisieren(p), "nachweis_freigegeben", f"{firma.get('name')} hat den Stundennachweis der Woche ab {f['week_monday']} freigegeben.", f"/projekte/{p['id']}")
    await protokollieren(user, "nachweis.freigegeben", lokal["name"], details={"woche": f["week_monday"]})
    return {"freigabe": f}


@router.delete("/api/projekte/{project_id}/freigaben/{freigabe_id}")
async def freigabe_zurueck(project_id: str, freigabe_id: str, user: dict = Depends(rolle_noetig("buero"))):
    lokal, v = await _lokal_mit_verknuepfung(user, project_id)
    r = await db().freigaben.delete_one({"id": freigabe_id, "beteiligung_id": v["beteiligung_id"]})
    if not r.deleted_count:
        raise HTTPException(404, "Freigabe nicht gefunden.")
    await protokollieren(user, "nachweis.zurueckgezogen", lokal["name"])
    return {"ok": True}


@router.get("/api/projekte/{project_id}/nachweise")
async def nachweise(project_id: str, user: dict = Depends(aktueller_nutzer)):
    """Vom Partner freigegebene Wochen: Zeiten (mit Namen, da ausdrücklich freigegeben) und Kunden-Unterschrift."""
    z = await zugang(user, project_id)
    leitung_noetig(z)
    aus = []
    async for f in db().freigaben.find({"project_id": project_id}, {"_id": 0}).sort([("week_monday", -1)]):
        von = f["week_monday"]
        bis = (date.fromisoformat(von) + timedelta(days=6)).isoformat()
        namen = await nutzernamen(f["firma_id"])
        zeiten = []
        async for e in db().entries.find({"firma_id": f["firma_id"], "project_id": f["lokales_project_id"], "date": {"$gte": von, "$lte": bis}},
                                          {"_id": 0, "date": 1, "start_time": 1, "end_time": 1, "pause_minutes": 1, "net_minutes": 1, "user_id": 1, "activity": 1, "workers": 1}).sort([("date", 1), ("start_time", 1)]):
            zeiten.append({**{k: v for k, v in e.items() if k != "user_id"}, "user_name": namen.get(e.get("user_id"), "")})
        u = await db().signatures.find_one({"firma_id": f["firma_id"], "project_id": f["lokales_project_id"], "week_monday": von, "ersetzt": {"$ne": True}}, {"_id": 0, "signer_name": 1, "signed_at": 1})
        aus.append({**f, "firma_name": (await firma_kurz(f["firma_id"]))["name"], "bis": bis, "zeiten": zeiten, "minuten": sum(int(x.get("net_minutes") or 0) * max(1, int(x.get("workers") or 1)) for x in zeiten),
                    "unterschrift": u})
    return {"nachweise": aus}


# ---------------------------------------------------------------- Benachrichtigungen

@router.get("/api/benachrichtigungen")
async def benachrichtigungen(user: dict = Depends(aktueller_nutzer)):
    liste = await meine_benachrichtigungen(user)
    return {"benachrichtigungen": liste, "ungelesen": sum(1 for n in liste if not n["gelesen"])}


@router.post("/api/benachrichtigungen/{nid}/gelesen")
async def gelesen(nid: str, user: dict = Depends(aktueller_nutzer)):
    await db().benachrichtigungen.update_one({"id": nid, "firma_id": user["firma_id"]}, {"$addToSet": {"gelesen_von": user["id"]}})
    return {"ok": True}


@router.post("/api/benachrichtigungen/alle-gelesen")
async def alle_gelesen(user: dict = Depends(aktueller_nutzer)):
    for n in await meine_benachrichtigungen(user, 400):
        if not n["gelesen"]:
            await db().benachrichtigungen.update_one({"id": n["id"]}, {"$addToSet": {"gelesen_von": user["id"]}})
    return {"ok": True}
