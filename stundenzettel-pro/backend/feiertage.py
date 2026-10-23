"""Gesetzliche Feiertage in Deutschland je Bundesland (bewegliche über das Osterdatum)."""
from __future__ import annotations

from datetime import date, timedelta

BUNDESLAENDER = {
    "BW": "Baden-Württemberg", "BY": "Bayern", "BE": "Berlin", "BB": "Brandenburg", "HB": "Bremen", "HH": "Hamburg",
    "HE": "Hessen", "MV": "Mecklenburg-Vorpommern", "NI": "Niedersachsen", "NW": "Nordrhein-Westfalen",
    "RP": "Rheinland-Pfalz", "SL": "Saarland", "SN": "Sachsen", "ST": "Sachsen-Anhalt", "SH": "Schleswig-Holstein",
    "TH": "Thüringen",
}


def ostersonntag(jahr: int) -> date:
    """Gauß'sche Osterformel (gregorianisch)."""
    a = jahr % 19
    b = jahr // 100
    c = jahr % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7  # noqa: E741
    m = (a + 11 * h + 22 * l) // 451
    monat = (h + l - 7 * m + 114) // 31
    tag = ((h + l - 7 * m + 114) % 31) + 1
    return date(jahr, monat, tag)


def _bussbettag(jahr: int) -> date:
    d = date(jahr, 11, 22)
    while d.weekday() != 2:
        d -= timedelta(days=1)
    return d


def feiertage(jahr: int, bundesland: str = "") -> list[dict]:
    """Liste [{date: 'JJJJ-MM-TT', name}] — bundesweite plus die des Bundeslands (Kürzel, leer = nur bundesweit)."""
    o = ostersonntag(jahr)
    aus = {
        date(jahr, 1, 1): "Neujahr", o - timedelta(days=2): "Karfreitag", o + timedelta(days=1): "Ostermontag",
        date(jahr, 5, 1): "Tag der Arbeit", o + timedelta(days=39): "Christi Himmelfahrt", o + timedelta(days=50): "Pfingstmontag",
        date(jahr, 10, 3): "Tag der Deutschen Einheit", date(jahr, 12, 25): "1. Weihnachtstag", date(jahr, 12, 26): "2. Weihnachtstag",
    }
    land = (bundesland or "").upper()
    if land in ("BW", "BY", "ST"):
        aus[date(jahr, 1, 6)] = "Heilige Drei Könige"
    if land in ("BE", "MV"):
        aus[date(jahr, 3, 8)] = "Internationaler Frauentag"
    if land in ("BW", "BY", "HE", "NW", "RP", "SL"):
        aus[o + timedelta(days=60)] = "Fronleichnam"
    if land in ("SL", "BY"):
        aus[date(jahr, 8, 15)] = "Mariä Himmelfahrt"
    if land == "TH":
        aus[date(jahr, 9, 20)] = "Weltkindertag"
    if land in ("BB", "HB", "HH", "MV", "NI", "SN", "ST", "SH", "TH"):
        aus[date(jahr, 10, 31)] = "Reformationstag"
    if land in ("BW", "BY", "NW", "RP", "SL"):
        aus[date(jahr, 11, 1)] = "Allerheiligen"
    if land == "SN":
        aus[_bussbettag(jahr)] = "Buß- und Bettag"
    return [{"date": d.isoformat(), "name": n} for d, n in sorted(aus.items())]


def feiertage_set(jahre: list[int] | range, bundesland: str = "") -> dict[str, str]:
    aus = {}
    for j in jahre:
        for f in feiertage(j, bundesland):
            aus[f["date"]] = f["name"]
    return aus
