"""Sollstunden, Stundenkonto (Überstunden) und Urlaubskonto je Mitarbeiter."""
from __future__ import annotations

from datetime import date, timedelta

from db import db
from feiertage import feiertage_set
from zeiten import monatsletzter

ARBEITSTAGE_STANDARD = [0, 1, 2, 3, 4]
BEZAHLT = ("urlaub", "krank", "feiertag", "sonstiges")   # senken das Soll (gelten als geleistet)


def arbeitstage(user: dict, firma: dict) -> list[int]:
    tage = user.get("workdays") or firma.get("workdays") or ARBEITSTAGE_STANDARD
    return [int(t) for t in tage if 0 <= int(t) <= 6] or ARBEITSTAGE_STANDARD


def soll_tag_minuten(user: dict, firma: dict) -> int:
    wochen = float(user.get("weekly_hours") or 0)
    tage = arbeitstage(user, firma)
    return int(round(wochen * 60 / len(tage))) if wochen and tage else 0


async def _abwesenheiten(firma_id: str, user_id: str, von: str, bis: str) -> dict[str, str]:
    """Tag -> Art für genehmigte (und bei Krankheit auch beantragte) Abwesenheiten im Bereich."""
    aus = {}
    async for a in db().absences.find({"firma_id": firma_id, "user_id": user_id, "from_date": {"$lte": bis}, "to_date": {"$gte": von}}, {"_id": 0}):
        if a.get("status") == "abgelehnt" or (a.get("status") == "beantragt" and a["type"] != "krank"):
            continue
        d = date.fromisoformat(a["from_date"])
        ende = date.fromisoformat(a["to_date"])
        while d <= ende:
            k = d.isoformat()
            if von <= k <= bis:
                aus[k] = a["type"]
            d += timedelta(days=1)
    return aus


async def monatskonto(firma: dict, user: dict, jahr: int, monat: int, heute: date | None = None) -> dict:
    """Soll, Ist, Abwesenheitstage und Buchungen eines Monats (Soll nur bis heute, wenn der Monat läuft)."""
    von = date(jahr, monat, 1)
    bis = monatsletzter(jahr, monat)
    heute = heute or date.today()
    tage = arbeitstage(user, firma)
    soll_tag = soll_tag_minuten(user, firma)
    frei = feiertage_set([jahr], firma.get("bundesland") or "")
    abw = await _abwesenheiten(firma["id"], user["id"], von.isoformat(), bis.isoformat())
    start = user.get("balance_start_date") or ""
    soll = 0
    abwesend = {k: 0 for k in BEZAHLT}
    abwesend["unbezahlt"] = 0
    d = von
    while d <= bis:
        k = d.isoformat()
        if d <= heute and (not start or k >= start) and d.weekday() in tage and k not in frei:
            art = abw.get(k)
            if art:
                abwesend[art if art in abwesend else "sonstiges"] += 1
            else:
                soll += soll_tag
        d += timedelta(days=1)
    ist = 0
    async for e in db().entries.find({"firma_id": firma["id"], "user_id": user["id"], "date": {"$gte": von.isoformat(), "$lte": bis.isoformat()}}, {"_id": 0, "net_minutes": 1, "date": 1}):
        if not start or e["date"] >= start:
            ist += int(e.get("net_minutes") or 0)
    buchungen = 0
    async for b in db().zeitkonto.find({"firma_id": firma["id"], "user_id": user["id"], "date": {"$gte": von.isoformat(), "$lte": bis.isoformat()}}, {"_id": 0, "minutes": 1}):
        buchungen += int(b.get("minutes") or 0)
    return {"jahr": jahr, "monat": monat, "soll_minuten": soll, "ist_minuten": ist, "buchungen_minuten": buchungen,
            "saldo_minuten": ist - soll + buchungen, "abwesend": abwesend, "soll_tag_minuten": soll_tag}


async def kontoverlauf(firma: dict, user: dict, bis_jahr: int, bis_monat: int) -> dict:
    """Monate vom Kontostart bis zum gewünschten Monat mit kumuliertem Saldo."""
    start = user.get("balance_start_date")
    if start:
        s = date.fromisoformat(start)
    else:
        erster = await db().entries.find_one({"firma_id": firma["id"], "user_id": user["id"]}, {"_id": 0, "date": 1}, sort=[("date", 1)])
        s = date.fromisoformat(erster["date"]) if erster else date.fromisoformat((user.get("created_at") or date.today().isoformat())[:10])
    monate = []
    kumuliert = int(user.get("balance_start_minutes") or 0)
    j, m = s.year, s.month
    while (j, m) <= (bis_jahr, bis_monat) and len(monate) < 120:
        k = await monatskonto(firma, user, j, m)
        kumuliert += k["saldo_minuten"]
        k["kumuliert_minuten"] = kumuliert
        monate.append(k)
        j, m = (j + 1, 1) if m == 12 else (j, m + 1)
    return {"startsaldo_minuten": int(user.get("balance_start_minutes") or 0), "start": s.isoformat(), "monate": monate,
            "saldo_minuten": kumuliert}


async def urlaubskonto(firma: dict, user: dict, jahr: int, heute: date | None = None) -> dict:
    """Anspruch, Übertrag, genommen (bis heute), geplant (genehmigt, Zukunft), beantragt, Rest — in Arbeitstagen."""
    heute = heute or date.today()
    tage = arbeitstage(user, firma)
    frei = feiertage_set([jahr], firma.get("bundesland") or "")
    von, bis = f"{jahr}-01-01", f"{jahr}-12-31"
    genommen = geplant = beantragt = 0
    async for a in db().absences.find({"firma_id": firma["id"], "user_id": user["id"], "type": "urlaub", "from_date": {"$lte": bis}, "to_date": {"$gte": von}}, {"_id": 0}):
        if a.get("status") == "abgelehnt":
            continue
        d = max(date.fromisoformat(a["from_date"]), date(jahr, 1, 1))
        ende = min(date.fromisoformat(a["to_date"]), date(jahr, 12, 31))
        while d <= ende:
            if d.weekday() in tage and d.isoformat() not in frei:
                if a.get("status") == "beantragt":
                    beantragt += 1
                elif d <= heute:
                    genommen += 1
                else:
                    geplant += 1
            d += timedelta(days=1)
    anspruch = float(user.get("vacation_days") or 0)
    uebertrag = float(user.get("vacation_carryover") or 0) if int(user.get("vacation_carryover_year") or jahr) == jahr else 0.0
    return {"jahr": jahr, "anspruch": anspruch, "uebertrag": uebertrag, "genommen": genommen, "geplant": geplant,
            "beantragt": beantragt, "rest": round(anspruch + uebertrag - genommen - geplant, 1)}
