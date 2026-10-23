"""Einsatzplanung: vom Chef festgelegte Soll-Schichten, Stempel-Abgleich und explizite Freigaben.

Ein Dienstplan ist KEIN Nachweis tatsächlich geleisteter Arbeit. Niemals aus einem
ungeprüften Plan automatisch eine Stempelung oder einen Lohnbucheintrag erzeugen.
Mitarbeiter sehen ausschließlich ihre eigenen Einsätze; der Inhaber sieht alle.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from auth import aktueller_nutzer, jetzt_iso, schreibend
from db import db
from gemeinsam import neue_id, projekt_laden
from protokoll import protokollieren
from zeiten import datum_pruefen, lokal_jetzt, netto_minuten, zeit_pruefen

router = APIRouter(prefix="/api/einsatzplan", tags=["Einsatzplanung"])


class EinsatzSerieIn(BaseModel):
    project_id: str
    user_ids: list[str] = Field(min_length=1, max_length=80)
    from_date: str
    to_date: str
    weekdays: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4])
    start_time: str
    end_time: str
    pause_minutes: int = Field(default=30, ge=0, le=600)
    address: str = Field(default="", max_length=300)
    note: str = Field(default="", max_length=500)

    @field_validator("from_date", "to_date")
    @classmethod
    def datum(cls, wert):
        datum_pruefen(wert)
        return wert

    @field_validator("start_time", "end_time")
    @classmethod
    def uhrzeit(cls, wert):
        zeit_pruefen(wert)
        return wert

    @field_validator("weekdays")
    @classmethod
    def wochentage(cls, wert):
        if len(wert) != len(set(wert)) or any(not 0 <= x <= 6 for x in wert):
            raise ValueError("Wochentage müssen eindeutig zwischen 0 und 6 liegen.")
        return wert


class EinsatzFreigabeIn(BaseModel):
    start_time: str
    end_time: str
    pause_minutes: int = Field(ge=0, le=600)
    grund: str = Field(default="", max_length=500)
    arbeitsleistung_bestaetigt: bool = False

    @field_validator("start_time", "end_time")
    @classmethod
    def uhrzeit(cls, wert):
        zeit_pruefen(wert)
        return wert


def _minuten(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _dauer(start: str, ende: str, pause: int) -> int:
    if _minuten(ende) <= _minuten(start):
        raise HTTPException(422, "Nachtschichten benötigen eine separate Planung. Ende muss nach Beginn liegen.")
    minuten = netto_minuten(start, ende, pause)
    if minuten < 1:
        raise HTTPException(422, "Die Pause muss kürzer sein als die geplante Schicht.")
    return minuten


def _chef(user: dict) -> None:
    if user.get("role") != "inhaber":
        raise HTTPException(403, "Einsätze anderer Mitarbeiter darf ausschließlich der Firmeninhaber planen und freigeben.")


async def _stempel_eintraege(plan: dict) -> list[dict]:
    return [e async for e in db().entries.find(
        {"firma_id": plan["firma_id"], "project_id": plan["project_id"], "user_id": plan["user_id"],
         "date": plan["date"], "source": {"$in": ["stempel", "stempel_offline"]}},
        {"_id": 0, "id": 1, "start_time": 1, "end_time": 1, "pause_minutes": 1, "net_minutes": 1,
         "clock_start_at": 1, "clock_end_at": 1}).sort("start_time", 1)]


async def _ansicht(plan: dict, user: dict, project: Optional[dict] = None) -> dict:
    """Keine fremden Nutzer-/Lohninformationen für Mitarbeiter."""
    projekt = project or await db().projects.find_one(
        {"id": plan["project_id"], "firma_id": user["firma_id"]},
        {"_id": 0, "id": 1, "name": 1, "address": 1})
    eintraege = await _stempel_eintraege(plan)
    start = min((e["start_time"] for e in eintraege), default=None)
    ende = max((e["end_time"] for e in eintraege), default=None)
    tatsächlich = sum(int(e.get("net_minutes") or 0) for e in eintraege)
    verspätet = max(0, _minuten(start) - _minuten(plan["start_time"])) if start else None
    frueher = max(0, _minuten(plan["end_time"]) - _minuten(ende)) if ende else None
    aus = {k: plan.get(k) for k in ("id", "project_id", "date", "start_time", "end_time", "pause_minutes",
                                    "planned_minutes", "address", "note", "status", "freigabe", "updated_at")}
    aus["projekt"] = {"name": (projekt or {}).get("name") or "Projekt",
                       "address": plan.get("address") or (projekt or {}).get("address") or ""}
    aus["stempel"] = {"vorhanden": bool(eintraege), "start_time": start, "end_time": ende,
                      "net_minutes": tatsächlich, "spaet_minuten": verspätet, "frueher_minuten": frueher}
    aus["plan_ohne_stempel"] = not bool(eintraege)
    if user.get("role") == "inhaber":
        aus["user_id"] = plan["user_id"]
        mitarbeiter = await db().users.find_one({"id": plan["user_id"], "firma_id": user["firma_id"]},
                                                {"_id": 0, "name": 1})
        aus["mitarbeiter"] = (mitarbeiter or {}).get("name") or ""
    return aus


@router.get("")
async def auflisten(von: str = Query(...), bis: str = Query(...),
                    project_id: Optional[str] = None, user: dict = Depends(aktueller_nutzer)):
    try:
        start = datum_pruefen(von)
        ende = datum_pruefen(bis)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if ende < start or (ende - start).days > 62:
        raise HTTPException(400, "Einsatzplan maximal 63 Tage pro Anfrage.")
    filt = {"firma_id": user["firma_id"], "date": {"$gte": von, "$lte": bis}}
    if project_id:
        await projekt_laden(user, project_id)
        filt["project_id"] = project_id
    if user.get("role") != "inhaber":
        filt["user_id"] = user["id"]
    plaene = [p async for p in db().einsatzplaene.find(filt, {"_id": 0}).sort([("date", 1), ("start_time", 1)]).limit(3000)]
    return {"einsatzplaene": [await _ansicht(p, user) for p in plaene], "chef": user.get("role") == "inhaber"}


@router.post("/serie")
async def serie(body: EinsatzSerieIn, user: dict = Depends(schreibend("inhaber"))):
    _chef(user)
    try:
        von, bis = datum_pruefen(body.from_date), datum_pruefen(body.to_date)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if bis < von or (bis - von).days > 62:
        raise HTTPException(400, "Du kannst höchstens 63 Tage gleichzeitig planen.")
    dauer = _dauer(body.start_time, body.end_time, body.pause_minutes)
    p = await projekt_laden(user, body.project_id, schreiben=True)
    ids = list(dict.fromkeys(body.user_ids))
    personen = [u async for u in db().users.find(
        {"firma_id": user["firma_id"], "id": {"$in": ids}, "active": {"$ne": False}},
        {"_id": 0, "id": 1})]
    if len(personen) != len(ids):
        raise HTTPException(400, "Mindestens ein Mitarbeiter ist nicht aktiv oder gehört nicht zu deiner Firma.")

    dates = []
    tag = von
    while tag <= bis:
        if tag.weekday() in body.weekdays:
            dates.append(tag.isoformat())
        tag += timedelta(days=1)
    if not dates:
        raise HTTPException(400, "In diesem Zeitraum liegt keiner der ausgewählten Wochentage.")

    # Erst sämtliche Kollisionen und bereits freigegebenen Schichten prüfen,
    # bevor Änderungen erfolgen. Das minimiert Teiländerungen.
    for uid in ids:
        for datum in dates:
            vorhandene = [x async for x in db().einsatzplaene.find(
                {"firma_id": user["firma_id"], "user_id": uid, "date": datum},
                {"_id": 0, "id": 1, "project_id": 1, "start_time": 1, "end_time": 1, "status": 1})]
            for x in vorhandene:
                if x["project_id"] == p["id"] and x.get("status") == "freigegeben":
                    raise HTTPException(409, f"Einsatz am {datum} bereits freigegeben. Freigabe vorher kontrolliert aufheben.")
                if x["project_id"] != p["id"] and _minuten(body.start_time) < _minuten(x["end_time"]) and _minuten(body.end_time) > _minuten(x["start_time"]):
                    raise HTTPException(409, f"Mitarbeiter ist am {datum} bereits auf einem anderen Projekt verplant.")

    now = jetzt_iso()
    anzahl = 0
    for uid in ids:
        for datum in dates:
            filt = {"firma_id": user["firma_id"], "user_id": uid, "project_id": p["id"], "date": datum}
            alter = await db().einsatzplaene.find_one(filt, {"_id": 0, "id": 1, "version": 1, "created_at": 1})
            daten = {"start_time": body.start_time, "end_time": body.end_time, "pause_minutes": body.pause_minutes,
                     "planned_minutes": dauer, "address": body.address.strip() or p.get("address") or "",
                     "note": body.note.strip(), "status": "geplant", "updated_at": now,
                     "version": int((alter or {}).get("version") or 0) + 1}
            if alter:
                await db().einsatzplaene.update_one(filt, {"$set": daten, "$unset": {"freigabe": ""}})
            else:
                await db().einsatzplaene.insert_one({"id": neue_id(), **filt, **daten, "created_at": now})
            anzahl += 1

    # Geplante Mitarbeiter sehen nur ihnen zugewiesene Projekte. Wenn bisher keine
    # feste Zuweisung bestand, beginnt diese explizit mit der ersten Einsatzplanung.
    await db().projects.update_one({"id": p["id"], "firma_id": user["firma_id"]},
                                   {"$addToSet": {"employee_ids": {"$each": ids}}})
    await protokollieren(user, "einsatzplan.geplant", p["name"], details={"anzahl": anzahl, "von": body.from_date,
                                                                          "bis": body.to_date, "personen": len(ids)})
    return {"angelegt_oder_aktualisiert": anzahl, "tage": len(dates), "mitarbeiter": len(ids)}


@router.post("/{einsatz_id}/freigabe")
async def freigeben(einsatz_id: str, body: EinsatzFreigabeIn, user: dict = Depends(schreibend("inhaber"))):
    _chef(user)
    plan = await db().einsatzplaene.find_one({"id": einsatz_id, "firma_id": user["firma_id"]}, {"_id": 0})
    if not plan:
        raise HTTPException(404, "Einsatz nicht gefunden.")
    if plan["date"] > lokal_jetzt().date().isoformat():
        raise HTTPException(409, "Zukünftige Arbeitszeiten können nicht als geleistet freigegeben werden.")
    if plan.get("status") == "freigegeben":
        raise HTTPException(409, "Einsatz ist bereits freigegeben. Eine Korrektur braucht einen eigenen versionierten Vorgang.")
    dauer = _dauer(body.start_time, body.end_time, body.pause_minutes)
    stempel = await _stempel_eintraege(plan)
    stempel_min = sum(int(e.get("net_minutes") or 0) for e in stempel)
    abweichung = (not stempel or body.start_time != min(e["start_time"] for e in stempel) or
                  body.end_time != max(e["end_time"] for e in stempel) or dauer != stempel_min)
    if (abweichung or not stempel) and (not body.grund.strip() or not body.arbeitsleistung_bestaetigt):
        raise HTTPException(422, "Bei fehlender oder abweichender Stempelung tatsächliche Arbeit bestätigen und Begründung angeben.")
    freigabe = {"start_time": body.start_time, "end_time": body.end_time,
                "pause_minutes": body.pause_minutes, "net_minutes": dauer, "grund": body.grund.strip(),
                "stempel_minuten_zum_zeitpunkt": stempel_min, "hat_stempel": bool(stempel),
                "freigegeben_von": user["id"], "freigegeben_von_name": user.get("name"),
                "freigegeben_at": jetzt_iso()}
    await db().einsatzplaene.update_one({"id": einsatz_id, "firma_id": user["firma_id"], "status": {"$ne": "freigegeben"}},
                                      {"$set": {"freigabe": freigabe, "status": "freigegeben", "updated_at": jetzt_iso()}})
    await protokollieren(user, "einsatzplan.freigabe", plan["project_id"],
                         details={"einsatz_id": einsatz_id, "mitarbeiter_id": plan["user_id"],
                                  "abweichung": abweichung, "freigegebene_minuten": dauer})
    return {"einsatz": await _ansicht({**plan, "freigabe": freigabe, "status": "freigegeben"}, user)}


@router.get("/auswertung")
async def auswertung(von: str, bis: str, project_id: Optional[str] = None,
                     user: dict = Depends(aktueller_nutzer)):
    _chef(user)
    try:
        start, ende = datum_pruefen(von), datum_pruefen(bis)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if ende < start or (ende - start).days > 365:
        raise HTTPException(400, "Auswertung höchstens ein Jahr.")
    filt = {"firma_id": user["firma_id"], "date": {"$gte": von, "$lte": bis}}
    if project_id:
        await projekt_laden(user, project_id)
        filt["project_id"] = project_id
    result = {}
    async for p in db().einsatzplaene.find(filt, {"_id": 0}).sort("date", 1):
        eintraege = await _stempel_eintraege(p)
        tatsaechlich = sum(int(e.get("net_minutes") or 0) for e in eintraege)
        freigabe = p.get("freigabe") or {}
        gilt = int(freigabe["net_minutes"]) if p.get("status") == "freigegeben" and "net_minutes" in freigabe else tatsaechlich
        g = result.setdefault(p["project_id"], {"project_id": p["project_id"], "geplant_minuten": 0,
                         "gestempelt_minuten": 0, "beruecksichtigt_minuten": 0, "noch_zu_pruefen": 0, "lohnkosten_schaetzung": 0.0})
        g["geplant_minuten"] += int(p["planned_minutes"])
        g["gestempelt_minuten"] += tatsaechlich
        g["beruecksichtigt_minuten"] += gilt
        if not eintraege and p.get("status") != "freigegeben":
            g["noch_zu_pruefen"] += 1
        u = await db().users.find_one({"id": p["user_id"], "firma_id": user["firma_id"]},
                                      {"_id": 0, "lohndaten.hourly_wage": 1})
        stundensatz = float(((u or {}).get("lohndaten") or {}).get("hourly_wage") or 0)
        g["lohnkosten_schaetzung"] += (gilt / 60) * stundensatz
    aus = []
    for pid, w in result.items():
        p = await db().projects.find_one({"id": pid, "firma_id": user["firma_id"]}, {"_id": 0, "name": 1, "abrechnungsart_projekt": 1, "pauschale_netto": 1})
        w["projekt"] = (p or {}).get("name") or ""
        w["lohnkosten_schaetzung"] = round(w["lohnkosten_schaetzung"], 2)
        if (p or {}).get("abrechnungsart_projekt") == "pauschal":
            pauschale = float(p.get("pauschale_netto") or 0)
            w["pauschale_netto"] = pauschale
            w["deckung_vor_nebenkosten"] = round(pauschale - w["lohnkosten_schaetzung"], 2)
            w["kalkulationshinweis"] = "Noch ohne Material, Gemeinkosten, AG-Nebenkosten, Steuern und nicht erfasste Einsätze; kein vollständiger Gewinn."
        aus.append(w)
    return {"projekte": aus, "hinweis": "Planung, Stempelung und Freigabe sind getrennt. Die Kostenschätzung ist kein Lohnlauf und enthält keine Arbeitgebernebenkosten."}
