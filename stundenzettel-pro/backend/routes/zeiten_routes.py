"""Arbeitszeiten (Einträge, Serien), Stempeluhr (mit optionalem GPS) und Abwesenheiten.
Pro Plus: Leistungen am Eintrag, gesetzlicher Pausenabzug, ArbZG-Hinweise, Bearbeitungssperren, Vorarbeiter."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

import arbzg
from auth import aktueller_nutzer, firma_laden, hat_rolle, jetzt_iso, rolle_noetig, schreibend, schreibender_nutzer
from db import db
from feiertage import feiertage_set
from gemeinsam import (eintrag_anreichern, neue_id, nutzernamen, projekt_laden, projekt_leitung, projekt_sichtbar,
                       projekt_stats_aktualisieren)
from models import AbwesenheitIn, AbwesenheitStatusIn, SerieIn, StempelStartIn, StempelStopIn, ZeitIn, ZeitUpdateIn
from protokoll import protokollieren
from sperre import sperre_pruefen
from zeiten import datum_pruefen, lokal_jetzt, netto_minuten

router = APIRouter(tags=["Zeiten"])

EINTRAG_FELDER = ("project_id", "date", "start_time", "end_time", "pause_minutes", "activity", "workers", "user_id", "service_name")
LANGE_STEMPELUNG_MINUTEN = 10 * 60


def _bereich(von: str, bis: str) -> tuple[str, str]:
    try:
        datum_pruefen(von)
        datum_pruefen(bis)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    if bis < von:
        raise HTTPException(400, "„bis“ liegt vor „von“.")
    return von, bis


async def _person_pruefen(user: dict, user_id: Optional[str], projekt: dict) -> Optional[str]:
    """Nur der Firmeninhaber kann Zeiten einer anderen Person erfassen oder korrigieren."""
    if user.get("role") != "inhaber":
        return user["id"]
    if not user_id:
        return None
    u = await db().users.find_one({"id": user_id, "firma_id": user["firma_id"]}, {"_id": 0, "id": 1})
    if not u:
        raise HTTPException(400, "Mitarbeiter nicht gefunden.")
    zugewiesen = set(projekt.get("employee_ids") or []) | set(projekt.get("leiter_ids") or [])
    if zugewiesen and user_id not in zugewiesen:
        raise HTTPException(403, "Diese Person ist dem Projekt nicht zugewiesen.")
    return user_id


async def _leistung_setzen(e: dict, firma_id: str, service_id: Optional[str]) -> None:
    if not service_id:
        e["service_id"], e["service_name"], e["service_rate"] = None, "", 0
        return
    s = await db().services.find_one({"id": service_id, "firma_id": firma_id}, {"_id": 0})
    if not s:
        raise HTTPException(400, "Leistung nicht gefunden.")
    e["service_id"], e["service_name"], e["service_rate"] = s["id"], s.get("name", ""), float(s.get("hourly_rate") or 0)


def _fertig(e: dict, firma: dict) -> dict:
    e["activity"] = (e.get("activity") or "").strip()
    e["pause_minutes"] = int(e.get("pause_minutes") or 0)
    e["pause_auto"] = False
    if firma.get("auto_pause"):
        e["pause_minutes"], e["pause_auto"] = arbzg.pause_abziehen(e["start_time"], e["end_time"], e["pause_minutes"])
    e["workers"] = 1 if e.get("user_id") else max(1, min(99, int(e.get("workers") or 1)))
    e["net_minutes"] = netto_minuten(e["start_time"], e["end_time"], e["pause_minutes"])
    if e["net_minutes"] <= 0:
        raise HTTPException(400, "Die Netto-Arbeitszeit muss größer als 0 sein.")
    e.setdefault("warnungen", [])
    return e


async def _warnungen_aktualisieren(firma: dict, user_id: Optional[str], tage: set[str]) -> None:
    """ArbZG-Hinweise für die Tage einer Person neu berechnen (und den Folgetag wegen der Ruhezeit)."""
    if not user_id:
        return
    alle = set()
    for t in tage:
        alle.add(t)
        alle.add((date.fromisoformat(t) + timedelta(days=1)).isoformat())
    for t in sorted(alle):
        if not firma.get("arbzg_pruefung", True):
            await db().entries.update_many({"firma_id": firma["id"], "user_id": user_id, "date": t}, {"$set": {"warnungen": []}})
            continue
        vortag = (date.fromisoformat(t) - timedelta(days=1)).isoformat()
        heute = [e async for e in db().entries.find({"firma_id": firma["id"], "user_id": user_id, "date": t}, {"_id": 0})]
        gestern = [e async for e in db().entries.find({"firma_id": firma["id"], "user_id": user_id, "date": vortag}, {"_id": 0})]
        if heute:
            await db().entries.update_many({"firma_id": firma["id"], "user_id": user_id, "date": t},
                                           {"$set": {"warnungen": arbzg.tages_warnungen(heute, gestern)}})


async def _nach_aenderung(firma: dict, project_ids: set[str], user_id: Optional[str], tage: set[str]) -> None:
    for pid in project_ids:
        await projekt_stats_aktualisieren(firma["id"], pid)
    await _warnungen_aktualisieren(firma, user_id, tage)


async def _frisch(firma_id: str, eintrag_id: str) -> dict:
    e = await db().entries.find_one({"id": eintrag_id, "firma_id": firma_id}, {"_id": 0})
    return eintrag_anreichern(e, await nutzernamen(firma_id)) if e else {}


# ---------------------------------------------------------------- Einträge
@router.get("/api/zeiten")
async def liste(von: str, bis: str, user_id: Optional[str] = None, project_id: Optional[str] = None, limit: int = Query(5000, ge=1, le=20000),
                offset: int = Query(0, ge=0), user: dict = Depends(rolle_noetig("inhaber"))):
    von, bis = _bereich(von, bis)
    filt = {"firma_id": user["firma_id"], "date": {"$gte": von, "$lte": bis}}
    if user_id:
        filt["user_id"] = user_id
    if project_id:
        filt["project_id"] = project_id
    namen = await nutzernamen(user["firma_id"])
    projekte = {}
    async for p in db().projects.find({"firma_id": user["firma_id"]}, {"_id": 0, "id": 1, "name": 1, "color": 1}):
        projekte[p["id"]] = p
    aus = []
    async for e in db().entries.find(filt, {"_id": 0}).sort([("date", 1), ("start_time", 1)]).skip(offset).limit(limit + 1):
        e = eintrag_anreichern(e, namen)
        e["project_name"] = projekte.get(e.get("project_id"), {}).get("name", "")
        e["project_color"] = projekte.get(e.get("project_id"), {}).get("color", "")
        aus.append(e)
    hat_mehr = len(aus) > limit
    aus = aus[:limit]
    return {"hat_mehr": hat_mehr, "offset": offset, "limit": limit, "eintraege": aus}


@router.get("/api/zeiten/warnungen")
async def warnungen(von: str, bis: str, user: dict = Depends(rolle_noetig("buero"))):
    """ArbZG-Hinweise im Zeitraum, je Person und Tag."""
    von, bis = _bereich(von, bis)
    namen = await nutzernamen(user["firma_id"])
    tage: dict[tuple, dict] = {}
    async for e in db().entries.find({"firma_id": user["firma_id"], "date": {"$gte": von, "$lte": bis}, "warnungen.0": {"$exists": True}},
                                      {"_id": 0, "user_id": 1, "date": 1, "warnungen": 1, "net_minutes": 1}):
        k = (e.get("user_id"), e["date"])
        t = tage.setdefault(k, {"user_id": e.get("user_id"), "user_name": namen.get(e.get("user_id") or "", ""), "date": e["date"], "warnungen": e.get("warnungen") or [], "minuten": 0})
        t["minuten"] += int(e.get("net_minutes") or 0)
    aus = sorted(tage.values(), key=lambda t: (t["date"], t["user_name"]), reverse=True)
    return {"tage": aus, "anzahl": len(aus)}


@router.get("/api/zeiten/meine")
async def meine(von: str, bis: str, user: dict = Depends(aktueller_nutzer)):
    von, bis = _bereich(von, bis)
    projekte = {}
    async for p in db().projects.find({"firma_id": user["firma_id"]}, {"_id": 0, "id": 1, "name": 1, "color": 1}):
        projekte[p["id"]] = p
    aus = []
    async for e in db().entries.find({"firma_id": user["firma_id"], "user_id": user["id"], "date": {"$gte": von, "$lte": bis}},
                                      {"_id": 0}).sort([("date", 1), ("start_time", 1)]):
        e["project_name"] = projekte.get(e.get("project_id"), {}).get("name", "")
        e["project_color"] = projekte.get(e.get("project_id"), {}).get("color", "")
        e["user_name"] = user.get("name")
        aus.append(e)
    return {"eintraege": aus}


@router.post("/api/zeiten")
async def anlegen(body: ZeitIn, user: dict = Depends(schreibender_nutzer)):
    firma = user["_firma"]
    if body.offline_id:   # Offline-Eintrag: höchstens einmal anlegen, Wiederholungen liefern den vorhandenen Eintrag
        vorhanden = await db().entries.find_one({"firma_id": user["firma_id"], "offline_id": body.offline_id}, {"_id": 0, "id": 1})
        if vorhanden:
            return {"eintrag": await _frisch(user["firma_id"], vorhanden["id"]), "doppelt": True}
    p = await projekt_laden(user, body.project_id, schreiben=True)
    leitung = projekt_leitung(user, p)
    await sperre_pruefen(user, firma, p["id"], body.date, leitung)
    e = {**body.model_dump(exclude={"offline", "service_id", "offline_id", "start_at", "end_at"}), "id": neue_id(), "firma_id": user["firma_id"],
         "source": "stempel_offline" if body.offline else "manuell", "created_by": user["id"], "created_at": jetzt_iso()}
    if body.offline_id:
        e["offline_id"] = body.offline_id
    if body.start_at:
        e["clock_start_at"], e["clock_end_at"] = body.start_at, body.end_at
    e["user_id"] = await _person_pruefen(user, body.user_id, p)
    await _leistung_setzen(e, user["firma_id"], body.service_id)
    _fertig(e, firma)
    await db().entries.insert_one(dict(e))
    await _nach_aenderung(firma, {p["id"]}, e["user_id"], {e["date"]})
    await protokollieren(user, "zeit.eingetragen", p["name"], details={k: e.get(k) for k in ("date", "start_time", "end_time", "pause_minutes", "workers", "user_id", "service_name")})
    return {"eintrag": await _frisch(user["firma_id"], e["id"])}


@router.post("/api/zeiten/serie")
async def serie(body: SerieIn, user: dict = Depends(schreibender_nutzer)):
    firma = user["_firma"]
    p = await projekt_laden(user, body.project_id, schreiben=True)
    if user.get("role") != "inhaber":
        raise HTTPException(403, "Serien für Mitarbeiter erstellt nur der Firmeninhaber.")
    von, bis = _bereich(body.from_date, body.to_date)
    if (date.fromisoformat(bis) - date.fromisoformat(von)).days > 370:
        raise HTTPException(400, "Eine Serie darf höchstens ein Jahr umfassen.")
    await sperre_pruefen(user, firma, p["id"], von, True)
    await sperre_pruefen(user, firma, p["id"], bis, True)
    user_id = await _person_pruefen(user, body.user_id, p)
    frei = feiertage_set(range(date.fromisoformat(von).year, date.fromisoformat(bis).year + 1), firma.get("bundesland") or "") if body.skip_holidays else {}
    vorhanden = set()
    async for e in db().entries.find({"firma_id": user["firma_id"], "project_id": p["id"], "date": {"$gte": von, "$lte": bis}},
                                      {"_id": 0, "date": 1, "user_id": 1, "start_time": 1}):
        vorhanden.add((e["date"], e.get("user_id"), e.get("start_time")))
    vorlage = {"service_id": None}
    await _leistung_setzen(vorlage, user["firma_id"], body.service_id)
    neu, tage = [], set()
    d = date.fromisoformat(von)
    ende = date.fromisoformat(bis)
    while d <= ende:
        k = d.isoformat()
        if d.weekday() in body.weekdays and k not in frei and not (body.skip_existing and (k, user_id, body.start_time) in vorhanden):
            e = {"id": neue_id(), "firma_id": user["firma_id"], "project_id": p["id"], "date": k, "start_time": body.start_time,
                 "end_time": body.end_time, "pause_minutes": body.pause_minutes, "activity": body.activity or "",
                 "workers": body.workers, "user_id": user_id, "source": "serie", "created_by": user["id"], "created_at": jetzt_iso(), **vorlage}
            neu.append(_fertig(e, firma))
            tage.add(k)
        d += timedelta(days=1)
    if neu:
        await db().entries.insert_many([dict(e) for e in neu])
        await _nach_aenderung(firma, {p["id"]}, user_id, tage)
    await protokollieren(user, "zeit.serie", p["name"], details={"von": von, "bis": bis, "anzahl": len(neu), "user_id": user_id})
    return {"angelegt": len(neu)}


async def _eintrag_laden(user: dict, eintrag_id: str) -> tuple[dict, dict]:
    e = await db().entries.find_one({"id": eintrag_id, "firma_id": user["firma_id"]}, {"_id": 0})
    if not e:
        raise HTTPException(404, "Eintrag nicht gefunden.")
    p = await projekt_laden(user, e["project_id"])
    if e.get("user_id") != user["id"] and user.get("role") != "inhaber":
        raise HTTPException(403, "Nur eigene Arbeitszeiten lassen sich ändern. Zeiten anderer Personen korrigiert der Inhaber.")
    return e, p


@router.put("/api/zeiten/{eintrag_id}")
async def aendern(eintrag_id: str, body: ZeitUpdateIn, user: dict = Depends(schreibender_nutzer)):
    firma = user["_firma"]
    alt, p_alt = await _eintrag_laden(user, eintrag_id)
    aenderung = body.model_dump(exclude_unset=True)
    neu = {**alt, **{k: v for k, v in aenderung.items() if k != "service_id"}}
    p = p_alt
    if "project_id" in aenderung and aenderung["project_id"] != alt["project_id"]:
        p = await projekt_laden(user, neu["project_id"], schreiben=True)
    leitung = projekt_leitung(user, p)
    await sperre_pruefen(user, firma, alt["project_id"], alt["date"], leitung)
    await sperre_pruefen(user, firma, p["id"], neu["date"], leitung)
    if "user_id" in aenderung or not leitung:
        neu["user_id"] = await _person_pruefen(user, aenderung.get("user_id", alt.get("user_id")), p)
    if "service_id" in aenderung:
        await _leistung_setzen(neu, user["firma_id"], aenderung["service_id"])
    _fertig(neu, firma)
    neu["updated_at"] = jetzt_iso()
    neu["updated_by"] = user["id"]
    await db().entries.update_one({"id": eintrag_id}, {"$set": {k: v for k, v in neu.items() if k != "id"}})
    tage = {alt["date"], neu["date"]}
    await _nach_aenderung(firma, {alt["project_id"], neu["project_id"]}, neu.get("user_id"), tage)
    if alt.get("user_id") and alt.get("user_id") != neu.get("user_id"):
        await _warnungen_aktualisieren(firma, alt["user_id"], tage)
    await protokollieren(user, "zeit.geaendert", neu.get("date", ""), details={
        "vorher": {k: alt.get(k) for k in EINTRAG_FELDER}, "nachher": {k: neu.get(k) for k in EINTRAG_FELDER}})
    return {"eintrag": await _frisch(user["firma_id"], eintrag_id)}


@router.delete("/api/zeiten/{eintrag_id}")
async def loeschen(eintrag_id: str, user: dict = Depends(schreibender_nutzer)):
    firma = user["_firma"]
    e, p = await _eintrag_laden(user, eintrag_id)
    await sperre_pruefen(user, firma, e["project_id"], e["date"], projekt_leitung(user, p))
    await db().entries.delete_one({"id": eintrag_id})
    await _nach_aenderung(firma, {e["project_id"]}, e.get("user_id"), {e["date"]})
    await protokollieren(user, "zeit.geloescht", e.get("date", ""), details={k: e.get(k) for k in EINTRAG_FELDER})
    return {"ok": True}


# ---------------------------------------------------------------- Stempeluhr
def _stempel_oeffentlich(s: dict, projekte: dict) -> dict:
    s = {k: v for k, v in s.items() if k != "_id"}
    start = datetime.fromisoformat(s["start_at"])
    jetzt = lokal_jetzt()
    if start.tzinfo is None:
        jetzt = jetzt.replace(tzinfo=None)
    pause = 0
    pause_sek = 0
    offen = False
    for p in s.get("pausen", []):
        von = datetime.fromisoformat(p["von"])
        bis = datetime.fromisoformat(p["bis"]) if p.get("bis") else None
        if bis is None:
            offen = True
            bis = jetzt
        dauer = max(0, (bis - von).total_seconds())
        pause += int(dauer // 60)
        pause_sek += int(dauer)
    s["pause_minuten"] = pause
    s["pause_laeuft"] = offen
    s["sekunden"] = max(0, int((jetzt - start).total_seconds()) - pause_sek)   # sekundengenau aus den Zeitstempeln
    s["minuten"] = max(0, int((jetzt - start).total_seconds() // 60) - pause)
    s["server_jetzt"] = jetzt.isoformat()
    s["lange"] = s["minuten"] >= LANGE_STEMPELUNG_MINUTEN
    s["project_name"] = projekte.get(s.get("project_id"), {}).get("name", "")
    s["project_color"] = projekte.get(s.get("project_id"), {}).get("color", "")
    return s


async def _projekte_sichtbar(user: dict) -> dict:
    aus = {}
    async for p in db().projects.find({"firma_id": user["firma_id"], "archived": False}, {"_id": 0, "id": 1, "name": 1, "color": 1, "employee_ids": 1, "leiter_ids": 1, "customer_name": 1, "address": 1}):
        if projekt_sichtbar(user, p):
            aus[p["id"]] = p
    return aus


@router.get("/api/stempel/status")
async def stempel_status(user: dict = Depends(aktueller_nutzer)):
    projekte = await _projekte_sichtbar(user)
    s = await db().stempel.find_one({"firma_id": user["firma_id"], "user_id": user["id"]}, {"_id": 0})
    heute = lokal_jetzt().date().isoformat()
    minuten_heute = 0
    async for e in db().entries.find({"firma_id": user["firma_id"], "user_id": user["id"], "date": heute}, {"_id": 0, "net_minutes": 1}):
        minuten_heute += int(e.get("net_minutes") or 0)
    liste = sorted(projekte.values(), key=lambda p: p["name"])
    for p in liste:
        p.pop("employee_ids", None)
        p.pop("leiter_ids", None)
    leistungen = [{"id": s["id"], "name": s["name"]} async for s in db().services.find({"firma_id": user["firma_id"], "active": True}, {"_id": 0}).sort("sort", 1)]
    return {"aktiv": _stempel_oeffentlich(s, projekte) if s else None, "projekte": liste, "heute": heute, "minuten_heute": minuten_heute,
            "leistungen": leistungen, "jetzt": lokal_jetzt().isoformat()}   # Server-Uhr: die Anzeige rechnet damit, nie mit der Geräteuhr allein


def _zeitstempel(text: str, jetzt: datetime, feld: str) -> datetime:
    """Zeitstempel vom Gerät (ISO, meist UTC mit Z) in die Zeitrechnung des Servers bringen."""
    try:
        t = datetime.fromisoformat((text or "").replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(400, f"{feld} ist kein gültiger Zeitstempel.")
    if jetzt.tzinfo is not None:
        t = t.astimezone(jetzt.tzinfo) if t.tzinfo is not None else t.replace(tzinfo=jetzt.tzinfo)
    elif t.tzinfo is not None:
        t = t.astimezone().replace(tzinfo=None)
    return t


@router.post("/api/stempel/start")
async def stempel_start(body: StempelStartIn, user: dict = Depends(schreibender_nutzer)):
    """Einstempeln – oder eine offline gestartete Stempelung mit echter Startzeit und Pausen übernehmen (höchstens 24 Stunden zurück)."""
    p = await projekt_laden(user, body.project_id, schreiben=True)
    if await db().stempel.find_one({"firma_id": user["firma_id"], "user_id": user["id"]}):
        raise HTTPException(409, "Du bist schon eingestempelt. Bitte erst ausstempeln.")
    jetzt = lokal_jetzt()
    start_at, pausen, uebernommen = jetzt, [], False
    if body.start_at:
        start_at = _zeitstempel(body.start_at, jetzt, "start_at")
        if start_at > jetzt + timedelta(minutes=2):
            raise HTTPException(400, "Der Startzeitpunkt liegt in der Zukunft.")
        if jetzt - start_at > timedelta(hours=24):
            raise HTTPException(400, "Übernehmen geht nur für Stempelungen der letzten 24 Stunden. Bitte die Zeit von Hand eintragen.")
        letztes_ende = start_at
        for pz in body.pausen:
            von = _zeitstempel(pz.von, jetzt, "Pause von")
            bis = _zeitstempel(pz.bis, jetzt, "Pause bis") if pz.bis else None
            if von < letztes_ende or (bis is not None and bis < von) or von > jetzt or (bis is not None and bis > jetzt + timedelta(minutes=2)):
                raise HTTPException(400, "Die Pausen passen nicht zum Startzeitpunkt.")
            pausen.append({"von": von.isoformat(), "bis": bis.isoformat() if bis else None})
            letztes_ende = bis or jetzt
        uebernommen = True
    s = {"id": neue_id(), "firma_id": user["firma_id"], "user_id": user["id"], "project_id": p["id"],
         "start_at": start_at.isoformat(), "pausen": pausen, "gps_start": body.gps.model_dump() if body.gps else None, "offline_uebernommen": uebernommen}
    await db().stempel.insert_one(dict(s))
    await protokollieren(user, "stempel.start", p["name"], details={"gps": bool(body.gps), "offline_uebernommen": uebernommen, "start_at": s["start_at"]})
    return {"aktiv": _stempel_oeffentlich(s, {p["id"]: p})}


@router.post("/api/stempel/pause")
async def stempel_pause(user: dict = Depends(schreibender_nutzer)):
    s = await db().stempel.find_one({"firma_id": user["firma_id"], "user_id": user["id"]}, {"_id": 0})
    if not s:
        raise HTTPException(400, "Nicht eingestempelt.")
    if s.get("pausen") and not s["pausen"][-1].get("bis"):
        raise HTTPException(400, "Die Pause läuft schon.")
    s["pausen"] = s.get("pausen", []) + [{"von": lokal_jetzt().isoformat(), "bis": None}]
    await db().stempel.update_one({"id": s["id"]}, {"$set": {"pausen": s["pausen"]}})
    return {"aktiv": _stempel_oeffentlich(s, await _projekte_sichtbar(user))}


@router.post("/api/stempel/weiter")
async def stempel_weiter(user: dict = Depends(schreibender_nutzer)):
    s = await db().stempel.find_one({"firma_id": user["firma_id"], "user_id": user["id"]}, {"_id": 0})
    if not s or not s.get("pausen") or s["pausen"][-1].get("bis"):
        raise HTTPException(400, "Es läuft keine Pause.")
    s["pausen"][-1]["bis"] = lokal_jetzt().isoformat()
    await db().stempel.update_one({"id": s["id"]}, {"$set": {"pausen": s["pausen"]}})
    return {"aktiv": _stempel_oeffentlich(s, await _projekte_sichtbar(user))}


async def _stempel_beenden(s: dict, firma: dict, handelnder: dict, activity: str, gps: Optional[dict], service_id: Optional[str],
                           beendet_durch: Optional[str] = None) -> dict:
    """Stempelung abschließen: Eintrag für die gestempelte Person anlegen (auch durch das Büro)."""
    jetzt = lokal_jetzt()
    start = datetime.fromisoformat(s["start_at"])
    if start.tzinfo is None:
        jetzt = jetzt.replace(tzinfo=None)
    pausen = [dict(p) for p in s.get("pausen", [])]
    for p in pausen:
        if not p.get("bis"):
            p["bis"] = jetzt.isoformat()
    gesamt = int((jetzt - start).total_seconds() // 60)
    pause = sum(max(0, int((datetime.fromisoformat(p["bis"]) - datetime.fromisoformat(p["von"])).total_seconds() // 60)) for p in pausen)
    ende, hinweise = jetzt, []
    if gesamt > 24 * 60:
        # Nichts verwerfen: der Eintrag wird auf 24 Stunden begrenzt und zur Prüfung markiert; die echten Zeitstempel bleiben am Eintrag
        ende = start + timedelta(hours=23, minutes=59)
        gesamt = 24 * 60 - 1
        pause = min(pause, gesamt - 1)
        hinweise.append({"art": "pruefen", "text": "Die Stempelung lief länger als 24 Stunden. Der Eintrag wurde auf 24 Stunden begrenzt – bitte prüfen und korrigieren."})
    if gesamt - pause < 1:
        await db().stempel.delete_one({"id": s["id"]})
        await protokollieren(handelnder, "stempel.verworfen", s.get("project_id", ""), details={"grund": "unter einer Minute", "user_id": s["user_id"], "start_at": s["start_at"]})
        return {"eintrag": None, "verworfen": True, "hinweis": "Weniger als eine Minute, nichts eingetragen."}
    e = {"id": neue_id(), "firma_id": firma["id"], "project_id": s["project_id"], "user_id": s["user_id"],
         "date": start.date().isoformat(), "start_time": start.strftime("%H:%M"), "end_time": ende.strftime("%H:%M"),
         "pause_minutes": pause, "activity": (activity or "").strip(), "workers": 1, "source": "stempel",
         "gps_start": s.get("gps_start"), "gps_end": gps, "clock_start_at": s["start_at"], "clock_end_at": jetzt.isoformat(),
         "beendet_durch": beendet_durch, "pruefen": bool(hinweise), "hinweise": hinweise, "created_by": handelnder["id"], "created_at": jetzt_iso()}
    await _leistung_setzen(e, firma["id"], service_id)
    _fertig(e, firma)
    await db().entries.insert_one(dict(e))              # erst der Arbeitszeitnachweis …
    await db().stempel.delete_one({"id": s["id"]})       # … dann die laufende Stempelung entfernen
    await _nach_aenderung(firma, {e["project_id"]}, e["user_id"], {e["date"]})
    await protokollieren(handelnder, "stempel.stop", e["project_id"], details={"date": e["date"], "start": e["start_time"], "ende": e["end_time"], "pause": e["pause_minutes"], "netto": e["net_minutes"], "user_id": s["user_id"], "beendet_durch": beendet_durch, "pruefen": e["pruefen"]})
    return {"eintrag": await _frisch(firma["id"], e["id"]), "verworfen": False}


@router.post("/api/stempel/stop")
async def stempel_stop(body: StempelStopIn, user: dict = Depends(schreibender_nutzer)):
    s = await db().stempel.find_one({"firma_id": user["firma_id"], "user_id": user["id"]}, {"_id": 0})
    if not s:
        raise HTTPException(400, "Nicht eingestempelt.")
    return await _stempel_beenden(s, user["_firma"], user, body.activity or "", body.gps.model_dump() if body.gps else None, body.service_id)


@router.post("/api/stempel/{stempel_id}/beenden")
async def stempel_beenden_buero(stempel_id: str, body: StempelStopIn, user: dict = Depends(schreibend("inhaber"))):
    """Büro beendet eine vergessene Stempelung eines Mitarbeiters (Eintrag endet jetzt, Vermerk im Protokoll)."""
    s = await db().stempel.find_one({"id": stempel_id, "firma_id": user["firma_id"]}, {"_id": 0})
    if not s:
        raise HTTPException(404, "Stempelung nicht gefunden.")
    return await _stempel_beenden(s, user["_firma"], user, body.activity or "", None, body.service_id, beendet_durch=user.get("name"))


@router.delete("/api/stempel")
async def stempel_abbrechen(user: dict = Depends(schreibender_nutzer)):
    s = await db().stempel.find_one({"firma_id": user["firma_id"], "user_id": user["id"]}, {"_id": 0, "start_at": 1, "project_id": 1})
    r = await db().stempel.delete_one({"firma_id": user["firma_id"], "user_id": user["id"]})
    if r.deleted_count:
        await protokollieren(user, "stempel.abgebrochen", (s or {}).get("project_id", ""), details={"start_at": (s or {}).get("start_at")})
    return {"ok": True}


@router.get("/api/stempel/aktiv")
async def stempel_aktiv(user: dict = Depends(rolle_noetig("inhaber"))):
    projekte = await _projekte_sichtbar(user)
    namen = await nutzernamen(user["firma_id"])
    aus = []
    async for s in db().stempel.find({"firma_id": user["firma_id"]}, {"_id": 0}):
        o = _stempel_oeffentlich(s, projekte)
        o["user_name"] = namen.get(s.get("user_id"), "")
        aus.append(o)
    aus.sort(key=lambda o: o["start_at"])
    return {"aktiv": aus}


# ---------------------------------------------------------------- Abwesenheiten
@router.get("/api/abwesenheiten")
async def abwesenheiten(von: Optional[str] = None, bis: Optional[str] = None, user_id: Optional[str] = None,
                        status: Optional[str] = None, user: dict = Depends(aktueller_nutzer)):
    filt = {"firma_id": user["firma_id"]}
    if not hat_rolle(user, "buero"):
        filt["user_id"] = user["id"]
    elif user_id:
        filt["user_id"] = user_id
    if von and bis:
        _bereich(von, bis)
        filt["from_date"] = {"$lte": bis}
        filt["to_date"] = {"$gte": von}
    if status:
        filt["status"] = status
    namen = await nutzernamen(user["firma_id"])
    aus = []
    async for a in db().absences.find(filt, {"_id": 0}).sort("from_date", -1).limit(2000):
        a["user_name"] = namen.get(a.get("user_id"), "")
        aus.append(a)
    return {"abwesenheiten": aus}


@router.post("/api/abwesenheiten")
async def abwesenheit_anlegen(body: AbwesenheitIn, user: dict = Depends(schreibender_nutzer)):
    if body.to_date < body.from_date:
        raise HTTPException(400, "„bis“ liegt vor „von“.")
    buero = hat_rolle(user, "buero")
    user_id = user["id"]
    if buero:
        if not body.user_id:
            raise HTTPException(400, "Bitte einen Mitarbeiter wählen.")
        if not await db().users.find_one({"id": body.user_id, "firma_id": user["firma_id"]}, {"_id": 0, "id": 1}):
            raise HTTPException(400, "Mitarbeiter nicht gefunden.")
        user_id = body.user_id
    a = {"id": neue_id(), "firma_id": user["firma_id"], "user_id": user_id, "type": body.type, "from_date": body.from_date,
         "to_date": body.to_date, "note": (body.note or "").strip(), "status": "genehmigt" if buero else "beantragt",
         "created_by": user["id"], "created_at": jetzt_iso(), "decided_by": user.get("name") if buero else None,
         "decided_at": jetzt_iso() if buero else None}
    await db().absences.insert_one(dict(a))
    await protokollieren(user, "abwesenheit.angelegt", a["type"], details={"von": a["from_date"], "bis": a["to_date"], "user_id": user_id, "status": a["status"]})
    namen = await nutzernamen(user["firma_id"])
    a["user_name"] = namen.get(user_id, "")
    return {"abwesenheit": a}


async def _abwesenheit(user: dict, abwesenheit_id: str) -> dict:
    a = await db().absences.find_one({"id": abwesenheit_id, "firma_id": user["firma_id"]}, {"_id": 0})
    if not a:
        raise HTTPException(404, "Abwesenheit nicht gefunden.")
    return a


@router.put("/api/abwesenheiten/{abwesenheit_id}/status")
async def abwesenheit_status(abwesenheit_id: str, body: AbwesenheitStatusIn, user: dict = Depends(schreibend("buero"))):
    a = await _abwesenheit(user, abwesenheit_id)
    aenderung = {"status": body.status, "decided_by": user.get("name"), "decided_at": jetzt_iso()}
    if body.note is not None:
        aenderung["decision_note"] = body.note.strip()
    schritt = {"at": jetzt_iso(), "user_id": user["id"], "user_name": user.get("name"), "aktion": "entschieden", "vorher": {"status": a.get("status")},
               "nachher": {"status": body.status}, "grund": (body.note or "").strip()}
    await db().absences.update_one({"id": abwesenheit_id}, {"$set": aenderung, "$push": {"verlauf": schritt}})
    aenderung["verlauf"] = (a.get("verlauf") or []) + [schritt]
    await protokollieren(user, "abwesenheit.entschieden", a["type"], details={"status": body.status, "user_id": a["user_id"], "von": a["from_date"]})
    return {"abwesenheit": {**a, **aenderung}}


@router.put("/api/abwesenheiten/{abwesenheit_id}")
async def abwesenheit_aendern(abwesenheit_id: str, body: AbwesenheitIn, user: dict = Depends(schreibender_nutzer)):
    a = await _abwesenheit(user, abwesenheit_id)
    buero = hat_rolle(user, "buero")
    if not buero and (a["user_id"] != user["id"] or a.get("status") != "beantragt"):
        raise HTTPException(403, "Nur eigene, noch nicht entschiedene Anträge lassen sich ändern.")
    if body.to_date < body.from_date:
        raise HTTPException(400, "„bis“ liegt vor „von“.")
    if buero and a.get("status") in ("genehmigt", "abgelehnt") and not (body.grund or "").strip():
        raise HTTPException(400, "Dieser Antrag ist bereits entschieden. Bitte einen Grund für die Änderung angeben.")
    aenderung = {"type": body.type, "from_date": body.from_date, "to_date": body.to_date, "note": (body.note or "").strip(), "updated_at": jetzt_iso()}
    if buero and body.user_id:
        if not await db().users.find_one({"id": body.user_id, "firma_id": user["firma_id"]}, {"_id": 0, "id": 1}):
            raise HTTPException(400, "Mitarbeiter nicht gefunden.")
        aenderung["user_id"] = body.user_id
    felder = [k for k in ("type", "from_date", "to_date", "note", "user_id") if k in aenderung and aenderung[k] != a.get(k)]
    schritt = {"at": jetzt_iso(), "user_id": user["id"], "user_name": user.get("name"), "aktion": "geaendert", "vorher": {k: a.get(k) for k in felder},
               "nachher": {k: aenderung[k] for k in felder}, "grund": (body.grund or "").strip()}
    await db().absences.update_one({"id": abwesenheit_id}, {"$set": aenderung, "$push": {"verlauf": schritt}})
    await protokollieren(user, "abwesenheit.geaendert", a["type"], details={"felder": felder, "grund": schritt["grund"], "user_id": aenderung.get("user_id", a["user_id"]), "status": a.get("status")})
    return {"abwesenheit": {**a, **aenderung, "verlauf": (a.get("verlauf") or []) + [schritt]}}


@router.delete("/api/abwesenheiten/{abwesenheit_id}")
async def abwesenheit_loeschen(abwesenheit_id: str, user: dict = Depends(schreibender_nutzer)):
    a = await _abwesenheit(user, abwesenheit_id)
    if not hat_rolle(user, "buero") and (a["user_id"] != user["id"] or a.get("status") != "beantragt"):
        raise HTTPException(403, "Nur eigene, noch nicht entschiedene Anträge lassen sich zurückziehen.")
    await db().absences.delete_one({"id": abwesenheit_id})
    await protokollieren(user, "abwesenheit.geloescht", a["type"], details={"von": a["from_date"], "user_id": a["user_id"]})
    return {"ok": True}
