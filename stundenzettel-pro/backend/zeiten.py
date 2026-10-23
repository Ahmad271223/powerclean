"""Reine Rechenhilfen: Netto-Minuten, ISO-Wochen, Monatsraster, Rechnungssummen.
Spiegelt die Regeln der kostenlosen App: Stundenzettel = ganze Kalenderwoche, Rechnung = nur Tage im Monat,
Stunden zählen je Mitarbeiter (Netto-Minuten × Anzahl)."""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Iterable

import config

DATUM_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ZEIT_RE = re.compile(r"^\d{2}:\d{2}$")


def max_jahr() -> int:
    return max(2035, date.today().year + 10)


def datum_pruefen(text: str) -> date:
    if not DATUM_RE.match(text or ""):
        raise ValueError("Datum im Format JJJJ-MM-TT angeben.")
    try:
        d = date.fromisoformat(text)
    except ValueError:
        raise ValueError("Ungültiges Datum.")
    if d.year < config.MIN_JAHR or d.year > max_jahr():
        raise ValueError(f"Datum muss zwischen {config.MIN_JAHR} und {max_jahr()} liegen.")
    return d


def zeit_pruefen(text: str) -> str:
    if not ZEIT_RE.match(text or ""):
        raise ValueError("Uhrzeit im Format HH:MM eingeben.")
    h, m = (int(x) for x in text.split(":"))
    if h > 23 or m > 59:
        raise ValueError("Ungültige Uhrzeit.")
    return text


def netto_minuten(start: str, ende: str, pause: int = 0) -> int:
    sh, sm = (int(x) for x in start.split(":"))
    eh, em = (int(x) for x in ende.split(":"))
    s = sh * 60 + sm
    e = eh * 60 + em
    if e < s:
        e += 24 * 60
    return max(0, e - s - int(pause or 0))


def anzahl(e: dict) -> int:
    try:
        return max(1, min(99, int(round(float(e.get("workers") or 1)))))
    except (TypeError, ValueError):
        return 1


def eintrag_minuten(e: dict) -> int:
    """Minuten, die ein Eintrag zählt: Netto × Mitarbeiter."""
    return int(e.get("net_minutes") or 0) * anzahl(e)


def montag_von(d: date) -> date:
    return d - timedelta(days=d.weekday())


def iso_woche(d: date) -> tuple[int, int]:
    jahr, woche, _ = d.isocalendar()
    return woche, jahr


def monatsletzter(jahr: int, monat: int) -> date:
    return (date(jahr + (monat == 12), monat % 12 + 1, 1) - timedelta(days=1))


def monatswochen(jahr: int, monat: int) -> list[date]:
    """Montage aller ISO-Wochen, die den Monat berühren (Monat 1–12)."""
    letzter = monatsletzter(jahr, monat)
    aus = []
    cur = montag_von(date(jahr, monat, 1))
    while cur <= letzter:
        aus.append(cur)
        cur += timedelta(days=7)
    return aus


def rasterbereich(jahr: int, monat: int) -> tuple[str, str]:
    """Erster und letzter Tag des Wochenrasters eines Monats (für Stundenzettel aller Wochen)."""
    wochen = monatswochen(jahr, monat)
    return wochen[0].isoformat(), (wochen[-1] + timedelta(days=6)).isoformat()


def eintrag_satz(e: dict, projekt: dict, firma: dict) -> float:
    """Stundensatz eines Eintrags: Leistungssatz (Schnappschuss am Eintrag), sonst Projekt, sonst Firma."""
    satz = float(e.get("service_rate") or 0) if e.get("service_id") else 0.0
    return satz or float(projekt.get("hourly_rate") or 0) or float(firma.get("default_hourly_rate") or 0)


def rechnung_berechnen(projekt: dict, firma: dict, jahr: int, monat: int, eintraege: Iterable[dict],
                       extras: Iterable[dict] = ()) -> dict:
    """Positionen je Kalenderwoche und Leistung (auf den Monat beschnitten) plus Zusatzpositionen
    (Material, Anfahrt, Pauschalen); Netto, USt, Brutto."""
    eintraege = list(eintraege)
    erster = date(jahr, monat, 1)
    letzter = monatsletzter(jahr, monat)
    satz_projekt = float(projekt.get("hourly_rate") or 0) or float(firma.get("default_hourly_rate") or 0)
    positionen = []
    gesamt = 0
    stunden_netto = 0.0
    for montag in monatswochen(jahr, monat):
        von = max(montag, erster)
        bis = min(montag + timedelta(days=6), letzter)
        von_k, bis_k = von.isoformat(), bis.isoformat()
        gruppen: dict[tuple, dict] = {}
        for e in eintraege:
            if not (von_k <= e.get("date", "") <= bis_k):
                continue
            satz = eintrag_satz(e, projekt, firma)
            name = (e.get("service_name") or "") if e.get("service_id") else ""
            g = gruppen.setdefault((name, satz), {"minutes": 0})
            g["minutes"] += eintrag_minuten(e)
        for (name, satz), g in sorted(gruppen.items(), key=lambda kv: (kv[0][0], -kv[0][1])):
            if not g["minutes"]:
                continue
            gesamt += g["minutes"]
            betrag = round(g["minutes"] / 60 * satz, 2)
            stunden_netto += betrag
            positionen.append({"week": iso_woche(montag)[0], "from": von_k, "to": bis_k, "service": name, "minutes": g["minutes"],
                               "hours": round(g["minutes"] / 60, 2), "rate": satz, "amount": betrag})
    zusatz = []
    extras_netto = 0.0
    for x in extras or ():
        menge = float(x.get("quantity") or 0)
        preis = float(x.get("unit_price") or 0)
        betrag = round(menge * preis, 2)
        extras_netto += betrag
        zusatz.append({"text": str(x.get("text") or "")[:200], "quantity": menge, "unit": str(x.get("unit") or "Stk.")[:20],
                       "unit_price": preis, "amount": betrag})
    netto = round(stunden_netto + extras_netto, 2)
    umkehr = bool(projekt.get("reverse_charge"))
    ust_satz = 0.0 if (firma.get("small_business") or umkehr) else float(firma.get("vat_rate") or 0)
    ust = round(netto * ust_satz / 100, 2)
    return {"rate": satz_projekt, "positions": positionen, "extras": zusatz, "total_minutes": gesamt, "hours_net": round(stunden_netto, 2),
            "extras_net": round(extras_netto, 2), "net": netto, "vat_rate": ust_satz, "vat": ust, "gross": round(netto + ust, 2),
            "reverse_charge": umkehr}


def tage_zwischen(von: str, bis: str) -> int:
    return (date.fromisoformat(bis) - date.fromisoformat(von)).days + 1


def lokal_jetzt() -> datetime:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo(config.ZEITZONE))
    except Exception:  # noqa: BLE001 — ohne Zeitzonendaten (z. B. Windows ohne tzdata) Systemzeit
        return datetime.now()
