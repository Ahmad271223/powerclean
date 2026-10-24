"""Plantafel und Einsatzplanung: Soll-Einsätze je Mitarbeiter und Tag, Kolonnen, Verschieben/Kopieren/Rückgängig, Abgleich mit der
Stempelung und ausdrückliche Freigabe der Arbeitszeit.

Grundsätze:
- Ein Einsatz ist ein Plan, kein Nachweis geleisteter Arbeit. Aus einem Plan entsteht nie automatisch eine Stempelung.
- Drei getrennte Zeitwerte: geplant (Einsatz), tatsächlich gestempelt (Eintrag, bleibt im Feld `original` erhalten) und freigegeben
  (korrigierte Zeit am Eintrag mit Name, Zeitstempel und Begründung).
- Planen und freigeben dürfen der Inhaber und Büro-Konten mit dem Recht „plantafel“; Mitarbeiter sehen nur ihre eigenen Einsätze.
- Jede Änderung trägt eine Version und einen Verlauf mit dem vorherigen Stand (Rückgängig möglich).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

import mail
from auth import aktueller_nutzer, firma_laden, hat_recht, jetzt_iso, recht_fehlt, schreibender_nutzer
from db import db
from feiertage import feiertage_set
from gemeinsam import neue_id, nutzernamen, projekt_laden, projekt_normalisieren, projekt_stats_aktualisieren
from models import EinsatzFreigabeIn, EinsatzIn, EinsatzKopierenIn, EinsatzUpdateIn, KolonneIn
from plattform import benachrichtigen
from protokoll import protokollieren
from zeiten import datum_pruefen, lokal_jetzt, montag_von

router = APIRouter(prefix="/api/einsatzplan", tags=["Plantafel"])
MAX_TAGE = 93
ABGLEICH_NAMEN = {"offen": "Noch nicht fällig", "fehlt": "Keine Stempelung", "abweichung": "Weicht vom Plan ab", "passt": "Wie geplant", "freigegeben": "Freigegeben"}


# ---------------------------------------------------------------- Hilfen

def _min(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _dauer(start: str, ende: str, pause: int) -> int:
    """Nettominuten; Ende vor oder gleich Beginn gilt als Nachtschicht über Mitternacht."""
    brutto = _min(ende) - _min(start)
    if brutto <= 0:
        brutto += 24 * 60
    netto = brutto - int(pause or 0)
    if netto < 1:
        raise HTTPException(422, "Die Pause muss kürzer sein als der Einsatz.")
    return netto


def _ueberlappt(a_start: str, a_ende: str, b_start: str, b_ende: str) -> bool:
    a1, a2 = _min(a_start), _min(a_ende) if _min(a_ende) > _min(a_start) else 24 * 60
    b1, b2 = _min(b_start), _min(b_ende) if _min(b_ende) > _min(b_start) else 24 * 60
    return a1 < b2 and b1 < a2


async def _planer(user: dict) -> dict:
    if not hat_recht(user, "plantafel"):
        raise HTTPException(403, recht_fehlt("plantafel"))
    return user


async def planer_schreibend(user: dict = Depends(schreibender_nutzer)) -> dict:
    return await _planer(user)


async def planer_lesend(user: dict = Depends(aktueller_nutzer)) -> dict:
    return await _planer(user)


def _bereich(von: str, bis: str, max_tage: int = MAX_TAGE) -> tuple[date, date]:
    try:
        a, b = datum_pruefen(von), datum_pruefen(bis)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if b < a:
        raise HTTPException(400, "„bis“ liegt vor „von“.")
    if (b - a).days > max_tage:
        raise HTTPException(400, f"Höchstens {max_tage + 1} Tage je Anfrage.")
    return a, b


def _schritt(user: dict, aktion: str, vorher: Optional[dict] = None, text: str = "") -> dict:
    return {"aktion": aktion, "user_id": user["id"], "user_name": user.get("name"), "at": jetzt_iso(), "vorher": vorher, "text": text[:300]}


FELDER = ("project_id", "user_id", "date", "start_time", "end_time", "pause_minutes", "planned_minutes", "address", "note", "taetigkeit", "kolonne_id", "status")


def _snapshot(e: dict) -> dict:
    return {k: e.get(k) for k in FELDER}


async def _einsatz(user: dict, einsatz_id: str) -> dict:
    e = await db().einsaetze.find_one({"id": einsatz_id, "firma_id": user["firma_id"]}, {"_id": 0})
    if not e:
        raise HTTPException(404, "Einsatz nicht gefunden.")
    return e


async def _personen_pruefen(user: dict, ids: list[str]) -> list[str]:
    ids = list(dict.fromkeys(ids))
    gefunden = [u["id"] async for u in db().users.find({"firma_id": user["firma_id"], "id": {"$in": ids}, "active": {"$ne": False}}, {"_id": 0, "id": 1})]
    fehlend = [i for i in ids if i not in gefunden]
    if fehlend:
        raise HTTPException(400, "Mindestens ein Mitarbeiter ist nicht aktiv oder gehört nicht zur Firma.")
    return ids


async def _abwesenheiten(firma_id: str, von: str, bis: str, user_ids: Optional[list[str]] = None) -> list[dict]:
    filt = {"firma_id": firma_id, "from_date": {"$lte": bis}, "to_date": {"$gte": von}, "status": {"$in": ["genehmigt", "beantragt"]}}
    if user_ids is not None:
        filt["user_id"] = {"$in": user_ids}
    return [a async for a in db().absences.find(filt, {"_id": 0, "id": 1, "user_id": 1, "type": 1, "from_date": 1, "to_date": 1, "status": 1})]


async def _konflikte(firma_id: str, user_id: str, datum: str, start: str, ende: str, ausser_id: Optional[str] = None) -> tuple[list[dict], list[dict]]:
    """(überlappende Einsätze, Abwesenheiten) am Tag."""
    ueberlappungen = []
    async for x in db().einsaetze.find({"firma_id": firma_id, "user_id": user_id, "date": datum, "status": "geplant"}, {"_id": 0, "id": 1, "project_id": 1, "start_time": 1, "end_time": 1}):
        if x["id"] != ausser_id and _ueberlappt(start, ende, x["start_time"], x["end_time"]):
            ueberlappungen.append(x)
    abwesend = await _abwesenheiten(firma_id, datum, datum, [user_id])
    return ueberlappungen, abwesend


async def _stempel_eintraege(e: dict) -> list[dict]:
    return [x async for x in db().entries.find({"firma_id": e["firma_id"], "project_id": e["project_id"], "user_id": e["user_id"], "date": e["date"]},
                                                 {"_id": 0}).sort("start_time", 1)]


def _abgleich(e: dict, eintraege: list[dict], heute: str) -> dict:
    """Plan gegen Stempelung: Hinweise, kein Vorwurf."""
    if e.get("freigabe"):
        return {"status": "freigegeben", "hinweise": [], "net_minutes": e["freigabe"].get("net_minutes")}
    if e["date"] > heute:
        return {"status": "offen", "hinweise": []}
    if not eintraege:
        return {"status": "fehlt", "hinweise": ["Keine Stempelung an diesem Tag – Arbeitszeit prüfen."]}
    start = min(x["start_time"] for x in eintraege)
    ende = max(x["end_time"] for x in eintraege)
    netto = sum(int(x.get("net_minutes") or 0) for x in eintraege)
    hinweise = []
    spaet = _min(start) - _min(e["start_time"])
    frueh = _min(e["end_time"]) - _min(ende)
    if spaet > 0:
        hinweise.append(f"{spaet} Minuten nach geplantem Beginn eingestempelt")
    elif spaet < 0:
        hinweise.append(f"{-spaet} Minuten vor geplantem Beginn eingestempelt")
    if frueh > 0:
        hinweise.append(f"{frueh} Minuten vor geplantem Ende ausgestempelt")
    elif frueh < 0:
        hinweise.append(f"{-frueh} Minuten nach geplantem Ende ausgestempelt")
    return {"status": "abweichung" if hinweise or abs(netto - int(e.get("planned_minutes") or 0)) > 5 else "passt", "hinweise": hinweise,
            "start_time": start, "end_time": ende, "net_minutes": netto, "spaet_minuten": max(0, spaet), "frueher_minuten": max(0, frueh)}


async def _ansicht(e: dict, user: dict, planer: bool, projekte: dict, namen: dict, kolonnen: dict, heute: str) -> dict:
    p = projekte.get(e["project_id"]) or {}
    aus = {k: e.get(k) for k in ("id", "project_id", "date", "start_time", "end_time", "pause_minutes", "planned_minutes", "address", "note", "taetigkeit", "kolonne_id", "status", "version", "freigabe", "serie_id", "updated_at")}
    aus["projekt"] = {"id": e["project_id"], "name": p.get("name") or "Projekt", "color": p.get("color"), "address": e.get("address") or p.get("address") or ""}
    aus["kolonne"] = (kolonnen.get(e.get("kolonne_id")) or {}).get("name")
    if e["date"] <= heute:
        aus["abgleich"] = _abgleich(e, await _stempel_eintraege(e), heute)
    else:
        aus["abgleich"] = {"status": "offen", "hinweise": []}
    aus["abgleich"]["status_name"] = ABGLEICH_NAMEN.get(aus["abgleich"]["status"], aus["abgleich"]["status"])
    if planer:
        aus["user_id"] = e["user_id"]
        aus["mitarbeiter"] = namen.get(e["user_id"], "")
        aus["verlauf"] = e.get("verlauf") or []
    return aus


async def _projekte(firma_id: str) -> dict:
    return {p["id"]: p async for p in db().projects.find({"firma_id": firma_id}, {"_id": 0, "id": 1, "name": 1, "address": 1, "color": 1, "archived": 1, "verknuepft": 1, "employee_ids": 1})}


async def _kolonnen(firma_id: str) -> dict:
    return {k["id"]: k async for k in db().kolonnen.find({"firma_id": firma_id}, {"_id": 0})}


async def _planaenderung_melden(e: dict, grund: str, firma: dict) -> None:
    """Betroffene Person sofort informieren, wenn ein Einsatz für heute oder morgen geändert oder abgesagt wird (idempotent je Version)."""
    heute = lokal_jetzt().date()
    if e["date"] not in (heute.isoformat(), (heute + timedelta(days=1)).isoformat()):
        return
    p = await db().projects.find_one({"id": e["project_id"]}, {"_id": 0, "name": 1, "address": 1})
    kennung = f"einsatz-aenderung-{e['id']}-v{e.get('version', 1)}"
    if await db().benachrichtigungen.find_one({"id": kennung}, {"_id": 0, "id": 1}):
        return
    text = (f"Planänderung {e['date']}: {(p or {}).get('name') or 'Projekt'} {e['start_time']}–{e['end_time']} Uhr"
            f"{' – ' + grund if grund else ''}{' (abgesagt)' if e.get('status') == 'abgesagt' else ''}.")
    await db().benachrichtigungen.insert_one({"id": kennung, "firma_id": e["firma_id"], "user_ids": [e["user_id"]], "mindestens": "mitarbeiter", "art": "einsatz_aenderung",
                                              "text": text[:300], "link": "/einsaetze", "gelesen_von": [], "created_at": jetzt_iso()})
    if (firma.get("erinnerung") or {}).get("email", True):
        u = await db().users.find_one({"id": e["user_id"]}, {"_id": 0, "email": 1, "email_benachrichtigungen": 1})
        if u and u.get("email_benachrichtigungen") is not False:
            await mail.senden(e["firma_id"], u.get("email") or "", f"Planänderung für {e['date']}", text + f"\n\nDein Einsatzplan: {mail.link('/einsaetze')}", "einsatz_aenderung", e["id"], e["project_id"])


# ---------------------------------------------------------------- Übersicht (Plantafel und eigene Einsätze)

@router.get("")
async def uebersicht(von: str, bis: str, project_id: Optional[str] = None, user_id: Optional[str] = None, kolonne_id: Optional[str] = None,
                     user: dict = Depends(aktueller_nutzer)):
    """Einsätze im Zeitraum; Planer sehen alle Personen, Mitarbeiter nur sich selbst. Dazu Abwesenheiten, Feiertage, Kolonnen, Kapazität."""
    a, b = _bereich(von, bis)
    planer = hat_recht(user, "plantafel")
    firma = await firma_laden(user["firma_id"])
    filt = {"firma_id": user["firma_id"], "date": {"$gte": von, "$lte": bis}}
    if not planer:
        filt["user_id"] = user["id"]
    elif user_id:
        filt["user_id"] = user_id
    if project_id:
        filt["project_id"] = project_id
    if kolonne_id:
        filt["kolonne_id"] = kolonne_id
    projekte = await _projekte(user["firma_id"])
    namen = await nutzernamen(user["firma_id"])
    kolonnen = await _kolonnen(user["firma_id"])
    heute = lokal_jetzt().date().isoformat()
    einsaetze = [await _ansicht(e, user, planer, projekte, namen, kolonnen, heute)
                 async for e in db().einsaetze.find(filt, {"_id": 0}).sort([("date", 1), ("start_time", 1)]).limit(5000)]
    abwesenheiten = await _abwesenheiten(user["firma_id"], von, bis, None if planer else [user["id"]])
    if planer:
        for x in abwesenheiten:
            x["user_name"] = namen.get(x["user_id"], "")
    jahre = sorted({a.year, b.year})
    feiertage = {k: v for k, v in feiertage_set(jahre, firma.get("bundesland") or "").items() if von <= k <= bis}
    aus = {"einsaetze": einsaetze, "abwesenheiten": abwesenheiten, "feiertage": feiertage, "planer": planer, "heute": heute,
           "erinnerung": {"uhrzeit": (firma.get("erinnerung") or {}).get("uhrzeit", "18:00"), "email": (firma.get("erinnerung") or {}).get("email", True)}}
    if planer:
        mitarbeiter = [u async for u in db().users.find({"firma_id": user["firma_id"], "active": True}, {"_id": 0, "id": 1, "name": 1, "role": 1, "weekly_hours": 1, "workdays": 1}).sort("name", 1)]
        for m in mitarbeiter:
            m["kolonne_id"] = next((k["id"] for k in kolonnen.values() if m["id"] in (k.get("user_ids") or [])), None)
        # Kapazität: geplante Minuten je Person und Kalenderwoche gegen Wochenstunden
        wochen: dict = {}
        for e in einsaetze:
            if e.get("status") != "geplant":
                continue
            kw = montag_von(date.fromisoformat(e["date"])).isoformat()
            wochen.setdefault(e["user_id"], {}).setdefault(kw, 0)
            wochen[e["user_id"]][kw] += int(e.get("planned_minutes") or 0)
        kapazitaet = []
        for m in mitarbeiter:
            soll = int(float(m.get("weekly_hours") or 0) * 60)
            for kw, minuten in sorted((wochen.get(m["id"]) or {}).items()):
                kapazitaet.append({"user_id": m["id"], "woche": kw, "geplant_minuten": minuten, "soll_minuten": soll, "ueber": bool(soll and minuten > soll)})
        aus.update({"mitarbeiter": mitarbeiter, "kolonnen": sorted(kolonnen.values(), key=lambda k: k["name"].lower()),
                    "projekte": sorted([{"id": p["id"], "name": p["name"], "color": p.get("color"), "address": p.get("address") or "", "verknuepft": bool(p.get("verknuepft"))}
                                        for p in projekte.values() if not p.get("archived")], key=lambda p: p["name"].lower()),
                    "kapazitaet": kapazitaet})
    return aus


@router.get("/meine")
async def meine(tage: int = Query(14, ge=1, le=60), user: dict = Depends(aktueller_nutzer)):
    """Eigene Einsätze: heute, morgen, diese Woche, nächste Woche – mit Adresse, Navigation, Zeiten, Hinweisen und Kolonne."""
    heute_d = lokal_jetzt().date()
    heute, morgen = heute_d.isoformat(), (heute_d + timedelta(days=1)).isoformat()
    montag = montag_von(heute_d)
    woche_bis = (montag + timedelta(days=6)).isoformat()
    naechste_von, naechste_bis = (montag + timedelta(days=7)).isoformat(), (montag + timedelta(days=13)).isoformat()
    bis = (heute_d + timedelta(days=tage)).isoformat()
    projekte = await _projekte(user["firma_id"])
    kolonnen = await _kolonnen(user["firma_id"])
    namen = await nutzernamen(user["firma_id"])
    liste = []
    async for e in db().einsaetze.find({"firma_id": user["firma_id"], "user_id": user["id"], "date": {"$gte": (heute_d - timedelta(days=7)).isoformat(), "$lte": bis}, "status": "geplant"}, {"_id": 0}).sort([("date", 1), ("start_time", 1)]):
        v = await _ansicht(e, user, False, projekte, namen, kolonnen, heute)
        adresse = v["projekt"]["address"]
        v["navigation"] = f"https://www.google.com/maps/search/?api=1&query={adresse.replace(' ', '+')}" if adresse else ""
        k = kolonnen.get(e.get("kolonne_id"))
        v["kollegen"] = [namen.get(i, "") for i in (k.get("user_ids") or []) if i != user["id"]] if k else []
        liste.append(v)
    return {"heute": [e for e in liste if e["date"] == heute], "morgen": [e for e in liste if e["date"] == morgen],
            "woche": [e for e in liste if montag.isoformat() <= e["date"] <= woche_bis],
            "naechste_woche": [e for e in liste if naechste_von <= e["date"] <= naechste_bis],
            "vergangen": [e for e in liste if e["date"] < heute], "spaeter": [e for e in liste if e["date"] > naechste_bis], "stand": jetzt_iso()}


# ---------------------------------------------------------------- Einsätze anlegen, ändern, verschieben, kopieren, absagen, rückgängig

async def _anlegen(user: dict, firma: dict, p: dict, user_id: str, datum: str, body, serie_id: Optional[str], erzwingen: bool) -> dict:
    ueberlappungen, abwesend = await _konflikte(user["firma_id"], user_id, datum, body.start_time, body.end_time)
    if ueberlappungen:
        raise HTTPException(409, f"Überschneidung am {datum}: die Person ist von {ueberlappungen[0]['start_time']} bis {ueberlappungen[0]['end_time']} schon verplant.")
    if abwesend and not erzwingen:
        a = abwesend[0]
        raise HTTPException(409, f"Am {datum} ist die Person abwesend ({a['type']}, {a['status']}). Mit „trotzdem planen“ lässt sich das überstimmen.")
    e = {"id": neue_id(), "firma_id": user["firma_id"], "project_id": p["id"], "user_id": user_id, "date": datum, "start_time": body.start_time, "end_time": body.end_time,
         "pause_minutes": int(body.pause_minutes or 0), "planned_minutes": _dauer(body.start_time, body.end_time, body.pause_minutes), "address": (body.address or "").strip() or p.get("address") or "",
         "note": (body.note or "").strip(), "taetigkeit": (body.taetigkeit or "").strip(), "kolonne_id": body.kolonne_id or None, "status": "geplant", "version": 1,
         "serie_id": serie_id, "freigabe": None, "verlauf": [_schritt(user, "angelegt")], "created_by": user["id"], "created_at": jetzt_iso(), "updated_at": jetzt_iso()}
    await db().einsaetze.insert_one(dict(e))
    return e


def _tage(body: EinsatzIn) -> list[str]:
    if body.dates:
        tage = []
        for d in body.dates:
            try:
                datum_pruefen(d)
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc
            tage.append(d)
        return list(dict.fromkeys(tage))
    if not (body.from_date and body.to_date):
        raise HTTPException(400, "Bitte Tage angeben (Liste oder von/bis mit Wochentagen).")
    a, b = _bereich(body.from_date, body.to_date)
    tage = []
    tag = a
    while tag <= b:
        if tag.weekday() in (body.weekdays or [0, 1, 2, 3, 4]):
            tage.append(tag.isoformat())
        tag += timedelta(days=1)
    if not tage:
        raise HTTPException(400, "In diesem Zeitraum liegt keiner der gewählten Wochentage.")
    return tage


@router.post("")
async def anlegen(body: EinsatzIn, user: dict = Depends(planer_schreibend)):
    """Einsätze für eine oder mehrere Personen an einem oder mehreren Tagen (auch ganze Kolonnen über user_ids)."""
    firma = user["_firma"]
    p = await projekt_laden(user, body.project_id)
    ids = await _personen_pruefen(user, body.user_ids)
    tage = _tage(body)
    if len(ids) * len(tage) > 2000:
        raise HTTPException(400, "Bitte in kleineren Schritten planen (höchstens 2000 Einsätze je Vorgang).")
    _dauer(body.start_time, body.end_time, body.pause_minutes)
    # erst alle Konflikte prüfen, dann schreiben (keine halben Serien)
    for uid in ids:
        for datum in tage:
            ueberlappungen, abwesend = await _konflikte(user["firma_id"], uid, datum, body.start_time, body.end_time)
            if ueberlappungen:
                raise HTTPException(409, f"Überschneidung am {datum} ({(await nutzernamen(user['firma_id'])).get(uid, '')}): {ueberlappungen[0]['start_time']}–{ueberlappungen[0]['end_time']} ist schon verplant.")
            if abwesend and not body.erzwingen:
                raise HTTPException(409, f"Am {datum} ist {(await nutzernamen(user['firma_id'])).get(uid, 'die Person')} abwesend ({abwesend[0]['type']}). Mit „trotzdem planen“ überstimmen.")
    serie_id = neue_id() if len(tage) > 1 else None
    neu = [await _anlegen(user, firma, p, uid, datum, body, serie_id, True) for uid in ids for datum in tage]
    await db().projects.update_one({"id": p["id"], "firma_id": user["firma_id"], "employee_ids": {"$ne": []}}, {"$addToSet": {"employee_ids": {"$each": ids}}})
    for e in neu:
        await _planaenderung_melden(e, "neuer Einsatz", firma)
    await protokollieren(user, "einsatz.geplant", p["name"], details={"anzahl": len(neu), "personen": len(ids), "tage": len(tage), "von": tage[0], "bis": tage[-1]})
    heute = lokal_jetzt().date().isoformat()
    projekte, namen, kolonnen = await _projekte(user["firma_id"]), await nutzernamen(user["firma_id"]), await _kolonnen(user["firma_id"])
    return {"einsaetze": [await _ansicht(e, user, True, projekte, namen, kolonnen, heute) for e in neu], "serie_id": serie_id}


async def _aendern(user: dict, e: dict, aenderung: dict, aktion: str, erzwingen: bool, text: str = "") -> dict:
    if e.get("freigabe"):
        raise HTTPException(409, "Ein freigegebener Einsatz lässt sich nicht mehr ändern – zuerst die Freigabe zurücknehmen.")
    neu = {**e, **aenderung}
    if "project_id" in aenderung:
        p = await projekt_laden(user, neu["project_id"])
        if not aenderung.get("address"):
            neu["address"] = p.get("address") or ""
    if "user_id" in aenderung:
        await _personen_pruefen(user, [neu["user_id"]])
    if "date" in aenderung:
        try:
            datum_pruefen(neu["date"])
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
    neu["planned_minutes"] = _dauer(neu["start_time"], neu["end_time"], neu["pause_minutes"])
    ueberlappungen, abwesend = await _konflikte(user["firma_id"], neu["user_id"], neu["date"], neu["start_time"], neu["end_time"], ausser_id=e["id"])
    if ueberlappungen:
        raise HTTPException(409, f"Überschneidung am {neu['date']}: {ueberlappungen[0]['start_time']}–{ueberlappungen[0]['end_time']} ist schon verplant.")
    if abwesend and not erzwingen:
        raise HTTPException(409, f"Am {neu['date']} ist die Person abwesend ({abwesend[0]['type']}). Mit „trotzdem planen“ überstimmen.")
    felder = {k: neu[k] for k in FELDER}
    felder.update({"version": int(e.get("version") or 1) + 1, "updated_at": jetzt_iso()})
    schritt = _schritt(user, aktion, _snapshot(e), text)
    await db().einsaetze.update_one({"id": e["id"]}, {"$set": felder, "$push": {"verlauf": schritt}})
    return {**e, **felder, "verlauf": (e.get("verlauf") or []) + [schritt]}


@router.put("/{einsatz_id}")
async def aendern(einsatz_id: str, body: EinsatzUpdateIn, user: dict = Depends(planer_schreibend)):
    e = await _einsatz(user, einsatz_id)
    aenderung = {k: v for k, v in body.model_dump(exclude_unset=True).items() if k != "erzwingen" and v is not None}
    for k in ("address", "note", "taetigkeit"):
        if k in aenderung:
            aenderung[k] = aenderung[k].strip()
    if "kolonne_id" in body.model_dump(exclude_unset=True):
        aenderung["kolonne_id"] = body.kolonne_id or None
    neu = await _aendern(user, e, aenderung, "geaendert", body.erzwingen)
    await _planaenderung_melden(neu, "Einsatz geändert", user["_firma"])
    if "user_id" in aenderung and aenderung["user_id"] != e["user_id"]:
        await _planaenderung_melden({**e, "status": "abgesagt"}, "Einsatz an eine andere Person übergeben", user["_firma"])
    await protokollieren(user, "einsatz.geaendert", e["project_id"], details={"einsatz_id": einsatz_id, "felder": sorted(aenderung)})
    heute = lokal_jetzt().date().isoformat()
    return {"einsatz": await _ansicht(neu, user, True, await _projekte(user["firma_id"]), await nutzernamen(user["firma_id"]), await _kolonnen(user["firma_id"]), heute)}


@router.post("/{einsatz_id}/kopieren")
async def kopieren(einsatz_id: str, body: EinsatzKopierenIn, user: dict = Depends(planer_schreibend)):
    """Einsatz auf weitere Tage und/oder Personen kopieren (Konflikte werden gemeldet, Kopien ohne Konflikt angelegt)."""
    e = await _einsatz(user, einsatz_id)
    tage = body.dates or [e["date"]]
    ids = await _personen_pruefen(user, body.user_ids or [e["user_id"]])
    for d in tage:
        try:
            datum_pruefen(d)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
    p = await projekt_laden(user, e["project_id"])
    neu, uebersprungen = [], []

    class Vorlage:  # Felder wie EinsatzIn
        start_time, end_time, pause_minutes = e["start_time"], e["end_time"], e["pause_minutes"]
        address, note, taetigkeit, kolonne_id = e.get("address") or "", e.get("note") or "", e.get("taetigkeit") or "", e.get("kolonne_id")
    for uid in ids:
        for datum in tage:
            if uid == e["user_id"] and datum == e["date"]:
                continue
            try:
                neu.append(await _anlegen(user, user["_firma"], p, uid, datum, Vorlage, None, body.erzwingen))
            except HTTPException as exc:
                uebersprungen.append({"user_id": uid, "date": datum, "grund": exc.detail})
    for x in neu:
        await _planaenderung_melden(x, "neuer Einsatz (Kopie)", user["_firma"])
    await protokollieren(user, "einsatz.kopiert", e["project_id"], details={"anzahl": len(neu), "uebersprungen": len(uebersprungen)})
    heute = lokal_jetzt().date().isoformat()
    projekte, namen, kolonnen = await _projekte(user["firma_id"]), await nutzernamen(user["firma_id"]), await _kolonnen(user["firma_id"])
    return {"einsaetze": [await _ansicht(x, user, True, projekte, namen, kolonnen, heute) for x in neu], "uebersprungen": uebersprungen}


@router.delete("/{einsatz_id}")
async def absagen(einsatz_id: str, grund: str = Query("", max_length=300), user: dict = Depends(planer_schreibend)):
    """Einsatz absagen (bleibt mit Verlauf erhalten und lässt sich wiederherstellen)."""
    e = await _einsatz(user, einsatz_id)
    if e.get("freigabe"):
        raise HTTPException(409, "Ein freigegebener Einsatz lässt sich nicht absagen – zuerst die Freigabe zurücknehmen.")
    if e.get("status") == "abgesagt":
        return {"ok": True}
    await db().einsaetze.update_one({"id": einsatz_id}, {"$set": {"status": "abgesagt", "version": int(e.get("version") or 1) + 1, "updated_at": jetzt_iso()},
                                                          "$push": {"verlauf": _schritt(user, "abgesagt", _snapshot(e), grund)}})
    await _planaenderung_melden({**e, "status": "abgesagt", "version": int(e.get("version") or 1) + 1}, grund or "Einsatz abgesagt", user["_firma"])
    await protokollieren(user, "einsatz.abgesagt", e["project_id"], details={"einsatz_id": einsatz_id, "grund": grund})
    return {"ok": True}


@router.post("/{einsatz_id}/wiederherstellen")
async def wiederherstellen(einsatz_id: str, user: dict = Depends(planer_schreibend)):
    e = await _einsatz(user, einsatz_id)
    if e.get("status") != "abgesagt":
        raise HTTPException(400, "Dieser Einsatz ist nicht abgesagt.")
    neu = await _aendern(user, e, {"status": "geplant"}, "wiederhergestellt", False)
    await _planaenderung_melden(neu, "Einsatz wiederhergestellt", user["_firma"])
    heute = lokal_jetzt().date().isoformat()
    return {"einsatz": await _ansicht(neu, user, True, await _projekte(user["firma_id"]), await nutzernamen(user["firma_id"]), await _kolonnen(user["firma_id"]), heute)}


@router.post("/{einsatz_id}/rueckgaengig")
async def rueckgaengig(einsatz_id: str, user: dict = Depends(planer_schreibend)):
    """Letzte Änderung zurücknehmen (vorheriger Stand aus dem Verlauf)."""
    e = await _einsatz(user, einsatz_id)
    if e.get("freigabe"):
        raise HTTPException(409, "Zuerst die Freigabe zurücknehmen.")
    letzte = next((v for v in reversed(e.get("verlauf") or []) if v.get("vorher") and v.get("aktion") != "rueckgaengig"), None)
    if not letzte:
        raise HTTPException(400, "Es gibt keine Änderung, die sich zurücknehmen lässt.")
    vorher = {k: v for k, v in letzte["vorher"].items() if k in FELDER}
    neu = await _aendern(user, e, vorher, "rueckgaengig", True, text=f"Stand vor „{letzte.get('aktion')}“ wiederhergestellt")
    await _planaenderung_melden(neu, "Änderung zurückgenommen", user["_firma"])
    heute = lokal_jetzt().date().isoformat()
    return {"einsatz": await _ansicht(neu, user, True, await _projekte(user["firma_id"]), await nutzernamen(user["firma_id"]), await _kolonnen(user["firma_id"]), heute)}


# ---------------------------------------------------------------- Kolonnen

@router.get("/kolonnen")
async def kolonnen_liste(user: dict = Depends(aktueller_nutzer)):
    namen = await nutzernamen(user["firma_id"])
    aus = []
    async for k in db().kolonnen.find({"firma_id": user["firma_id"]}, {"_id": 0}).sort("name", 1):
        if hat_recht(user, "plantafel") or user["id"] in (k.get("user_ids") or []):
            k["mitglieder"] = [{"id": i, "name": namen.get(i, "")} for i in k.get("user_ids") or [] if i in namen]
            aus.append(k)
    return {"kolonnen": aus}


@router.post("/kolonnen")
async def kolonne_anlegen(body: KolonneIn, user: dict = Depends(planer_schreibend)):
    ids = await _personen_pruefen(user, body.user_ids) if body.user_ids else []
    k = {"id": neue_id(), "firma_id": user["firma_id"], "name": body.name.strip(), "user_ids": ids, "vorarbeiter_id": body.vorarbeiter_id if body.vorarbeiter_id in ids else None,
         "farbe": body.farbe or "#1D4ED8", "created_at": jetzt_iso()}
    await db().kolonnen.insert_one(dict(k))
    await protokollieren(user, "kolonne.angelegt", k["name"], details={"personen": len(ids)})
    return {"kolonne": k}


@router.put("/kolonnen/{kolonne_id}")
async def kolonne_aendern(kolonne_id: str, body: KolonneIn, user: dict = Depends(planer_schreibend)):
    k = await db().kolonnen.find_one({"id": kolonne_id, "firma_id": user["firma_id"]}, {"_id": 0})
    if not k:
        raise HTTPException(404, "Kolonne nicht gefunden.")
    ids = await _personen_pruefen(user, body.user_ids) if body.user_ids else []
    aenderung = {"name": body.name.strip(), "user_ids": ids, "vorarbeiter_id": body.vorarbeiter_id if body.vorarbeiter_id in ids else None, "farbe": body.farbe or k.get("farbe") or "#1D4ED8", "updated_at": jetzt_iso()}
    await db().kolonnen.update_one({"id": kolonne_id}, {"$set": aenderung})
    return {"kolonne": {**k, **aenderung}}


@router.delete("/kolonnen/{kolonne_id}")
async def kolonne_loeschen(kolonne_id: str, user: dict = Depends(planer_schreibend)):
    r = await db().kolonnen.delete_one({"id": kolonne_id, "firma_id": user["firma_id"]})
    if not r.deleted_count:
        raise HTTPException(404, "Kolonne nicht gefunden.")
    await db().einsaetze.update_many({"firma_id": user["firma_id"], "kolonne_id": kolonne_id}, {"$set": {"kolonne_id": None}})
    return {"ok": True}


# ---------------------------------------------------------------- Abgleich und Freigabe

@router.get("/abgleich")
async def abgleich(von: str, bis: str, user_id: Optional[str] = None, project_id: Optional[str] = None, user: dict = Depends(planer_lesend)):
    """Plan gegen Stempelung je Einsatz (vergangene Tage): fehlende Stempelungen, Abweichungen, Freigaben – plus Stempelungen ohne Plan."""
    _bereich(von, bis)
    heute = lokal_jetzt().date().isoformat()
    filt = {"firma_id": user["firma_id"], "date": {"$gte": von, "$lte": min(bis, heute)}, "status": "geplant"}
    if user_id:
        filt["user_id"] = user_id
    if project_id:
        filt["project_id"] = project_id
    projekte, namen, kolonnen = await _projekte(user["firma_id"]), await nutzernamen(user["firma_id"]), await _kolonnen(user["firma_id"])
    einsaetze = [await _ansicht(e, user, True, projekte, namen, kolonnen, heute) async for e in db().einsaetze.find(filt, {"_id": 0}).sort([("date", 1), ("start_time", 1)])]
    geplant = {(e["user_id"], e["project_id"], e["date"]) for e in einsaetze}
    ungeplant = []
    efilt = {"firma_id": user["firma_id"], "date": {"$gte": von, "$lte": min(bis, heute)}, "source": {"$in": ["stempel", "stempel_offline"]}}
    if user_id:
        efilt["user_id"] = user_id
    async for x in db().entries.find(efilt, {"_id": 0, "id": 1, "user_id": 1, "project_id": 1, "date": 1, "start_time": 1, "end_time": 1, "net_minutes": 1}):
        if (x.get("user_id"), x.get("project_id"), x.get("date")) not in geplant:
            ungeplant.append({**x, "mitarbeiter": namen.get(x.get("user_id") or "", ""), "projekt": (projekte.get(x.get("project_id")) or {}).get("name", "")})
    zaehler = {"fehlt": 0, "abweichung": 0, "passt": 0, "freigegeben": 0}
    for e in einsaetze:
        zaehler[e["abgleich"]["status"]] = zaehler.get(e["abgleich"]["status"], 0) + 1
    return {"einsaetze": einsaetze, "ungeplante_stempelungen": ungeplant, "zaehler": zaehler, "status_namen": ABGLEICH_NAMEN,
            "hinweis": "Hinweise sind keine Vorwürfe: Die Freigabe legt die anrechenbare Zeit fest; die ursprüngliche Stempelung bleibt dokumentiert."}


@router.post("/{einsatz_id}/freigabe")
async def freigeben(einsatz_id: str, body: EinsatzFreigabeIn, user: dict = Depends(planer_schreibend)):
    """Arbeitszeit eines Einsatzes nach Prüfung freigeben: die anrechenbare Zeit landet am Zeiteintrag, die Stempelung bleibt in `original`.
    Ohne Stempelung entsteht ein Eintrag der Quelle „freigabe“ – nur mit Bestätigung und Begründung."""
    e = await _einsatz(user, einsatz_id)
    if e.get("status") != "geplant":
        raise HTTPException(400, "Nur geplante Einsätze lassen sich freigeben.")
    if e.get("freigabe"):
        raise HTTPException(409, "Dieser Einsatz ist bereits freigegeben – zum Ändern zuerst die Freigabe zurücknehmen.")
    jetzt_l = lokal_jetzt()
    heute = jetzt_l.date().isoformat()
    if e["date"] > heute or (e["date"] == heute and jetzt_l.strftime("%H:%M") < body.end_time and _min(body.end_time) > _min(body.start_time)):
        raise HTTPException(409, "Zukünftige Arbeitszeit lässt sich nicht als geleistet freigeben.")
    if await db().stempel.find_one({"firma_id": user["firma_id"], "user_id": e["user_id"]}, {"_id": 0, "id": 1}):
        raise HTTPException(409, "Die Person ist noch eingestempelt – bitte zuerst den Arbeitstag beenden.")
    netto = _dauer(body.start_time, body.end_time, body.pause_minutes)
    eintraege = await _stempel_eintraege(e)
    abweichung = (not eintraege or body.start_time != min(x["start_time"] for x in eintraege) or body.end_time != max(x["end_time"] for x in eintraege)
                  or netto != sum(int(x.get("net_minutes") or 0) for x in eintraege))
    if abweichung and (not body.grund.strip() or not body.arbeitsleistung_bestaetigt):
        raise HTTPException(422, "Bei fehlender oder abweichender Stempelung bitte die tatsächliche Arbeit bestätigen und eine Begründung angeben.")
    firma = user["_firma"]
    freigabe = {"start_time": body.start_time, "end_time": body.end_time, "pause_minutes": int(body.pause_minutes), "net_minutes": netto, "grund": body.grund.strip(),
                "abweichung": abweichung, "hat_stempel": bool(eintraege), "von_id": user["id"], "von_name": user.get("name"), "at": jetzt_iso(), "version": int(e.get("version") or 1)}
    if eintraege:
        haupt = eintraege[0]
        original = haupt.get("original") or {k: haupt.get(k) for k in ("start_time", "end_time", "pause_minutes", "net_minutes", "clock_start_at", "clock_end_at", "source")}
        aenderung = {"start_time": body.start_time, "end_time": body.end_time, "pause_minutes": int(body.pause_minutes), "net_minutes": netto, "original": original,
                     "freigabe": {**freigabe, "einsatz_id": einsatz_id}, "korrigiert": abweichung, "pruefen": False, "updated_at": jetzt_iso()}
        await db().entries.update_one({"id": haupt["id"]}, {"$set": aenderung})
        freigabe["eintrag_id"] = haupt["id"]
        freigabe["eintrag_neu"] = False
    else:
        neu = {"id": neue_id(), "firma_id": user["firma_id"], "project_id": e["project_id"], "user_id": e["user_id"], "date": e["date"], "start_time": body.start_time,
               "end_time": body.end_time, "pause_minutes": int(body.pause_minutes), "net_minutes": netto, "activity": (e.get("taetigkeit") or "")[:200], "workers": 1,
               "source": "freigabe", "pruefen": False, "hinweise": [], "freigabe": {**freigabe, "einsatz_id": einsatz_id}, "korrigiert": False, "created_by": user["id"], "created_at": jetzt_iso()}
        await db().entries.insert_one(dict(neu))
        freigabe["eintrag_id"] = neu["id"]
        freigabe["eintrag_neu"] = True
    await projekt_stats_aktualisieren(user["firma_id"], e["project_id"])
    await db().einsaetze.update_one({"id": einsatz_id}, {"$set": {"freigabe": freigabe, "updated_at": jetzt_iso()}, "$push": {"verlauf": _schritt(user, "freigegeben", None, body.grund)}})
    await protokollieren(user, "einsatz.freigegeben", e["project_id"], details={"einsatz_id": einsatz_id, "user_id": e["user_id"], "datum": e["date"], "netto": netto, "abweichung": abweichung, "grund": body.grund.strip(), "eintrag_neu": freigabe["eintrag_neu"]})
    heute = lokal_jetzt().date().isoformat()
    return {"einsatz": await _ansicht({**e, "freigabe": freigabe}, user, True, await _projekte(user["firma_id"]), await nutzernamen(user["firma_id"]), await _kolonnen(user["firma_id"]), heute)}


@router.post("/{einsatz_id}/freigabe-zuruecknehmen")
async def freigabe_zuruecknehmen(einsatz_id: str, grund: str = Query("", max_length=300), user: dict = Depends(planer_schreibend)):
    """Freigabe aufheben: Eintrag auf die ursprüngliche Stempelung zurücksetzen bzw. einen ohne Stempelung angelegten Eintrag entfernen."""
    e = await _einsatz(user, einsatz_id)
    f = e.get("freigabe")
    if not f:
        raise HTTPException(400, "Dieser Einsatz ist nicht freigegeben.")
    eintrag = await db().entries.find_one({"id": f.get("eintrag_id")}, {"_id": 0}) if f.get("eintrag_id") else None
    if eintrag:
        if f.get("eintrag_neu") or eintrag.get("source") == "freigabe":
            await db().entries.delete_one({"id": eintrag["id"]})
        else:
            original = eintrag.get("original") or {}
            await db().entries.update_one({"id": eintrag["id"]}, {"$set": {k: original.get(k, eintrag.get(k)) for k in ("start_time", "end_time", "pause_minutes", "net_minutes")} | {"korrigiert": False, "updated_at": jetzt_iso()},
                                                                   "$unset": {"freigabe": "", "original": ""}})
        await projekt_stats_aktualisieren(user["firma_id"], e["project_id"])
    await db().einsaetze.update_one({"id": einsatz_id}, {"$set": {"freigabe": None, "updated_at": jetzt_iso()}, "$push": {"verlauf": _schritt(user, "freigabe_zurueckgenommen", None, grund)}})
    await protokollieren(user, "einsatz.freigabe_zurueckgenommen", e["project_id"], details={"einsatz_id": einsatz_id, "grund": grund})
    return {"ok": True}


@router.get("/stundenzettel.pdf")
async def stundenzettel_pdf(project_id: str, von: str, bis: str, user: dict = Depends(planer_lesend)):
    """Projekt-Stundenzettel für Auftraggeber oder Projektleitung aus ausdrücklich freigegebenen Zeiten; ungeprüfte Einsätze werden als fehlend genannt."""
    import pdfs
    _bereich(von, bis)
    p = await projekt_laden(user, project_id)
    firma = await firma_laden(user["firma_id"])
    namen = await nutzernamen(user["firma_id"])
    alle = [e async for e in db().einsaetze.find({"firma_id": user["firma_id"], "project_id": project_id, "date": {"$gte": von, "$lte": bis}, "status": "geplant"}, {"_id": 0}).sort([("date", 1), ("start_time", 1)])]
    frei = [e for e in alle if e.get("freigabe")]
    if not frei:
        raise HTTPException(409, "Für diesen Zeitraum sind noch keine Arbeitszeiten freigegeben.")
    pdf = pdfs.freigegebene_zeiten_pdf(firma, p, von, bis, frei, len(alle) - len(frei), namen)
    await protokollieren(user, "einsatz.stundenzettel_pdf", p.get("name", ""), details={"von": von, "bis": bis, "freigegeben": len(frei), "offen": len(alle) - len(frei)})
    return Response(content=pdf, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="Projekt-Stundenzettel_{von}_{bis}.pdf"'})
