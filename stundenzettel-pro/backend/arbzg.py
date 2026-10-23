"""Arbeitszeitgesetz-Prüfung: Hinweise (keine Sperre) zu Tageshöchstarbeitszeit, Pausen, Ruhezeit, Sonntagsarbeit.
Plus der gesetzliche Pausenabzug, wenn die Firma ihn eingeschaltet hat."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from zeiten import netto_minuten

MAX_TAG_MINUTEN = 10 * 60          # § 3 ArbZG: 8 h, Ausgleich bis 10 h
RUHEZEIT_MINUTEN = 11 * 60         # § 5 ArbZG


def gesetzliche_pause(brutto_minuten: int) -> int:
    """§ 4 ArbZG: ab 6 h 30 Min., ab 9 h 45 Min."""
    if brutto_minuten > 9 * 60:
        return 45
    if brutto_minuten > 6 * 60:
        return 30
    return 0


def pause_abziehen(start: str, ende: str, pause: int) -> tuple[int, bool]:
    """Pause auf das gesetzliche Minimum anheben, falls kleiner. Liefert (pause, angehoben)."""
    brutto = netto_minuten(start, ende, 0)
    soll = gesetzliche_pause(brutto)
    if pause < soll:
        return soll, True
    return pause, False


def _zeitpunkt(datum: str, uhrzeit: str) -> datetime:
    h, m = (int(x) for x in uhrzeit.split(":"))
    return datetime.fromisoformat(datum) + timedelta(hours=h, minutes=m)


def _ende(e: dict) -> datetime:
    start = _zeitpunkt(e["date"], e["start_time"])
    ende = _zeitpunkt(e["date"], e["end_time"])
    if ende < start:
        ende += timedelta(days=1)
    return ende


def tages_warnungen(heute: list[dict], vortag: list[dict]) -> list[dict]:
    """Hinweise für die Einträge EINER Person an EINEM Tag (vortag = ihre Einträge des Vortags)."""
    if not heute:
        return []
    heute = sorted(heute, key=lambda e: e["start_time"])
    netto = sum(int(e.get("net_minutes") or 0) for e in heute)
    pause = sum(int(e.get("pause_minutes") or 0) for e in heute)
    for a, b in zip(heute, heute[1:]):
        luecke = int((_zeitpunkt(b["date"], b["start_time"]) - _ende(a)).total_seconds() // 60)
        if luecke > 0:
            pause += luecke
    aus = []
    if netto > MAX_TAG_MINUTEN:
        aus.append({"code": "ueber_10h", "text": "Mehr als 10 Stunden an einem Tag (§ 3 ArbZG)"})
    if pause < gesetzliche_pause(netto + pause):
        aus.append({"code": "pause_zu_kurz", "text": "Pause zu kurz: ab 6 Std. 30 Min., ab 9 Std. 45 Min. (§ 4 ArbZG)"})
    if vortag:
        letztes_ende = max(_ende(e) for e in vortag)
        erster_start = _zeitpunkt(heute[0]["date"], heute[0]["start_time"])
        if 0 <= int((erster_start - letztes_ende).total_seconds() // 60) < RUHEZEIT_MINUTEN:
            aus.append({"code": "ruhezeit", "text": "Ruhezeit unter 11 Stunden zum Vortag (§ 5 ArbZG)"})
    if date.fromisoformat(heute[0]["date"]).weekday() == 6:
        aus.append({"code": "sonntag", "text": "Sonntagsarbeit (§ 9 ArbZG, nur mit Ausnahme erlaubt)"})
    return aus
