"""Einteilung per Sprache (Flag `sprachplanung`): aus einem gesprochenen Satz wird ein Einteilungsvorschlag – gespeichert wird nichts.

Arbeitsteilung (Auftrag Schritt 4):
- Satz in Felder zerlegen (wer, Projekt, wo, Uhrzeit, Zeitraum): KI – auf dem iPhone Apples Modell (Felder kommen fertig an), sonst
  Mistral Small auf dem Server (nur mit Flag `ki` und MISTRAL_API_KEY), sonst feste Regeln (`regeln_zerlegen`).
- Datum ausrechnen („die ganze Woche“, „ab Montag drei Tage“, „morgen“): `tage_berechnen` – normaler Code, nicht die KI.
- Namen und Projekte zuordnen: `zuordnen` – unscharfe Suche über die echten Daten der Firma, bei Mehrdeutigkeit eine Rückfrage.
- Konflikte (schon eingeteilt, Urlaub, krank, Feiertag, Wochenende): dieselbe Prüfung wie die Plantafel.
Ergebnis: Vorschlag mit Rückfragen, Hinweisen, Konflikten und – wenn alles eindeutig ist – einem Entwurf für POST /api/einsatzplan.
Der Text wird nicht gespeichert oder protokolliert (nur Länge und Quelle).
"""
from __future__ import annotations

import json
import os
import re
import unicodedata
from datetime import date, timedelta
from difflib import SequenceMatcher
from typing import Any, Optional

STANDARD_START, STANDARD_ENDE, STANDARD_PAUSE = "07:00", "16:00", 30
FELDER = ("mitarbeiter", "projekt", "standort", "startzeit", "endzeit", "zeitraum")

WOCHENTAGE = {"montag": 0, "dienstag": 1, "mittwoch": 2, "donnerstag": 3, "freitag": 4, "samstag": 5, "sonntag": 6}
KURZ = {"mo": 0, "di": 1, "mi": 2, "do": 3, "fr": 4, "sa": 5, "so": 6}
TAG_NAMEN = ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So")
ZAHLWOERTER = {"null": 0, "ein": 1, "eins": 1, "eine": 1, "einen": 1, "einem": 1, "einer": 1, "zwei": 2, "drei": 3, "vier": 4, "fuenf": 5, "sechs": 6,
               "sieben": 7, "acht": 8, "neun": 9, "zehn": 10, "elf": 11, "zwoelf": 12, "dreizehn": 13, "vierzehn": 14, "fuenfzehn": 15,
               "sechzehn": 16, "siebzehn": 17, "achtzehn": 18, "neunzehn": 19, "zwanzig": 20, "einundzwanzig": 21, "zweiundzwanzig": 22,
               "dreiundzwanzig": 23}
MONATE = {"januar": 1, "jaenner": 1, "februar": 2, "maerz": 3, "april": 4, "mai": 5, "juni": 6, "juli": 7, "august": 8, "september": 9,
          "oktober": 10, "november": 11, "dezember": 12}
WORT = r"[^\W\d_][\w-]*"   # ein Wort mit beliebigen Buchstaben (auch Ş, Ç, É) und Bindestrich
STRASSE = r"[^\W\d_][\w.-]*?(?:straße|strasse|str\.|weg|platz|allee|ring|gasse|damm|ufer|chaussee)(?!\w)(?:\s+\d+(?:\s?[a-zA-Z](?![\wäöüÄÖÜß]))?)?"   # „Hauptstraße 5a“, aber nicht das „m“ von „5 morgen“
FUELLWOERTER = {"teile", "teil", "einteilen", "ein", "an", "die", "den", "der", "das", "dem", "projekt", "standort", "baustelle", "bei", "von", "bis",
                "uhr", "und", "ab", "am", "im", "in", "zur", "zum", "fuer", "ganze", "ganzen", "woche", "tage", "tag", "naechste", "naechsten",
                "kommende", "kommenden", "diese", "dieser", "morgen", "heute", "uebermorgen", "bitte", "mal", "plane", "planen", "einplanen",
                "schick", "schicke", "nach", "zu", "mit", "auf", "noch", "auch", "wieder", "jeden", "taeglich", "halb"}


# ---------------------------------------------------------------- Hilfen

def normal(s: Any) -> str:
    """Kleinbuchstaben, Umlaute ausgeschrieben, Satzzeichen weg – für Vergleiche."""
    s = str(s or "").lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9:.\- ]", " ", s)).strip()


def woerter(s: Any) -> list[str]:
    return [w for w in re.split(r"[\s.\-:]+", normal(s)) if w]


def _zahl(wort: str) -> Optional[int]:
    if wort.isdigit():
        return int(wort)
    return ZAHLWOERTER.get(wort)


# ---------------------------------------------------------------- Uhrzeiten

def uhrzeit(roh: Any) -> Optional[str]:
    """„7“, „7 Uhr“, „07:00“, „16.30“, „sieben“, „halb acht“, „16 Uhr 30“ → „HH:MM“ (sonst None)."""
    s = normal(roh).replace(" uhr", "").replace("uhr", "").strip()
    if not s:
        return None
    m = re.fullmatch(r"halb (\w+)", s)
    if m and _zahl(m.group(1)) is not None:
        h = _zahl(m.group(1)) - 1
        return f"{h % 24:02d}:30"
    m = re.fullmatch(r"(\w+)(?:[:. ](\d{2}))?", s)
    if not m:
        return None
    h = _zahl(m.group(1))
    minute = int(m.group(2) or 0)
    if h is None or not (0 <= h <= 24) or not (0 <= minute < 60):
        return None
    return f"{h % 24:02d}:{minute:02d}"


def zeiten_ordnen(start: Optional[str], ende: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """„sieben bis vier“ meint 7–16 Uhr: beginnt es vormittags und liegt das Ende davor (≤ 12), gilt das Ende als Nachmittag.
    „16 bis 7“ bleibt, wie es ist (Ende vor Beginn = Nachtschicht) – das Bestätigungsfenster fragt dann ausdrücklich nach."""
    if start and ende:
        hs, he = int(start[:2]), int(ende[:2])
        if hs < 12 and he <= hs and he + 12 > hs:
            ende = f"{he + 12:02d}:{ende[3:]}"
    return start, ende


# ---------------------------------------------------------------- Tage (normaler Code, nicht die KI)

def _montag(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _naechster(heute: date, wochentag: int, auch_heute: bool) -> date:
    delta = (wochentag - heute.weekday()) % 7
    if delta == 0 and not auch_heute:
        delta = 7
    return heute + timedelta(days=delta)


def _werktage(start: date, anzahl: int) -> list[date]:
    tage, d = [], start
    while len(tage) < anzahl:
        if d.weekday() < 5:
            tage.append(d)
        d += timedelta(days=1)
    return tage


def _wochentag(wort: str) -> Optional[int]:
    return WOCHENTAGE.get(wort)


def tage_berechnen(zeitraum: Any, heute: date) -> tuple[list[str], list[str]]:
    """Zeitraum in Worten → Tage (JJJJ-MM-TT) und Hinweise. Leere Liste = nicht verstanden (Rückfrage)."""
    s = normal(zeitraum)
    hinweise: list[str] = []
    if not s:
        return [], []
    s = re.sub(r"\b(mo|di|mi|do|fr|sa|so)\b(?=\s*(?:-|bis)\s*(?:mo|di|mi|do|fr|sa|so)\b)", lambda m: [k for k, v in WOCHENTAGE.items() if v == KURZ[m.group(1)]][0], s)
    s = re.sub(r"(?<=bis )\b(mo|di|mi|do|fr|sa|so)\b|(?<=- )\b(mo|di|mi|do|fr|sa|so)\b|(?<=-)\b(mo|di|mi|do|fr|sa|so)\b",
               lambda m: [k for k, v in WOCHENTAGE.items() if v == KURZ[m.group(0)]][0], s)
    woche = 0                      # Wochen ab dieser Woche („nächste Woche“ = 1)
    kw_montag: Optional[date] = None
    m_in = re.search(r"\bin (\w+) wochen?\b", s)
    m_kw = re.search(r"\b(?:kw|kalenderwoche) ?(\d{1,2})\b", s)
    if re.search(r"\buebernaechste[nr]? woche\b", s):
        woche = 2
    elif re.search(r"\b(naechste[nr]?|kommende[nr]?) woche\b", s):
        woche = 1
    elif m_in and _zahl(m_in.group(1)) and _zahl(m_in.group(1)) <= 52:
        woche = _zahl(m_in.group(1))       # „in zwei Wochen“ = die Woche in zwei Wochen
    elif m_kw:
        kw = int(m_kw.group(1))
        try:
            kw_montag = date.fromisocalendar(heute.year, kw, 1)
            if kw_montag + timedelta(days=6) < heute:          # KW schon vorbei → nächstes Jahr
                kw_montag = date.fromisocalendar(heute.year + 1, kw, 1)
        except ValueError:
            return [], [f"Kalenderwoche {kw} gibt es nicht."]
        woche = (kw_montag - _montag(heute)).days // 7

    # Wochenende („am Wochenende“, „nächstes Wochenende“): Samstag und Sonntag – der Hinweis kommt aus der Konfliktprüfung
    if re.search(r"\bwochenende\b", s) and not re.search(r"\b(" + "|".join(WOCHENTAGE) + r")\b", s):
        samstag = _montag(heute) + timedelta(weeks=woche, days=5)
        if samstag + timedelta(days=1) < heute:
            samstag += timedelta(weeks=1)
        return [d.isoformat() for d in (samstag, samstag + timedelta(days=1)) if d >= heute], hinweise

    # ausdrückliches Datum: „3.12.“, „03.12.2026“, „3. dezember“
    daten = []
    for m in re.finditer(r"\b(\d{1,2})\.(\d{1,2})\.(\d{2,4})?", s):
        jahr = int(m.group(3)) if m.group(3) else heute.year
        jahr += 2000 if jahr < 100 else 0
        daten.append((int(m.group(1)), int(m.group(2)), jahr, bool(m.group(3))))
    for m in re.finditer(r"\b(\d{1,2})\.? (" + "|".join(MONATE) + r")\b", s):
        daten.append((int(m.group(1)), MONATE[m.group(2)], heute.year, False))
    if daten:
        aus = []
        for tag, monat, jahr, fest in daten:
            # ohne Jahr: das nächste gültige Datum ab heute (auch 29.2. → nächstes Schaltjahr)
            for j in ([jahr] if fest else range(jahr, jahr + 5)):
                try:
                    d = date(j, monat, tag)
                except ValueError:
                    continue
                if fest or d >= heute:
                    aus.append(d)
                    break
        if len(aus) == 2 and re.search(r"\bbis\b|-", s) and aus[1] > aus[0]:
            aus = [aus[0] + timedelta(days=i) for i in range((aus[1] - aus[0]).days + 1) if (aus[0] + timedelta(days=i)).weekday() < 5]
        return sorted({d.isoformat() for d in aus}), hinweise

    basis = kw_montag or (_montag(heute) + timedelta(weeks=woche) if woche else None)

    # Bereich „montag bis mittwoch“
    m = re.search(r"\b(" + "|".join(WOCHENTAGE) + r")\s*(?:-|bis)\s*(" + "|".join(WOCHENTAGE) + r")\b", s)
    if m:
        a, b = _wochentag(m.group(1)), _wochentag(m.group(2))
        start = basis + timedelta(days=a) if basis else _naechster(heute, a, auch_heute=True)
        ende = start + timedelta(days=(b - a) % 7)
        return [(start + timedelta(days=i)).isoformat() for i in range((ende - start).days + 1)], hinweise

    # Anfang „ab montag“, „ab morgen“, „ab heute“ – optional mit Anzahl („drei tage“)
    anzahl = None
    m_anz = re.search(r"\b(\w+) (?:arbeits)?tage?n?\b", s)
    m_wochen = re.search(r"(?<!in )\b(\w+) wochen?\b", s)
    if m_anz and _zahl(m_anz.group(1)):
        anzahl = _zahl(m_anz.group(1))
    elif m_wochen and _zahl(m_wochen.group(1)) and not m_in:
        anzahl = _zahl(m_wochen.group(1)) * 5          # „zwei Wochen“ = 10 Arbeitstage
        hinweise.append(f"„{m_wochen.group(0)}“ als {anzahl} Arbeitstage verstanden (ohne Wochenende).")
    m_ab = re.search(r"\bab (heute|morgen|uebermorgen|" + "|".join(WOCHENTAGE) + r")\b", s)
    if m_ab or anzahl:
        wort = m_ab.group(1) if m_ab else ""
        if wort == "heute":
            start = heute
        elif wort == "morgen":
            start = heute + timedelta(days=1)
        elif wort == "uebermorgen":
            start = heute + timedelta(days=2)
        elif wort:
            wt = _wochentag(wort)
            start = basis + timedelta(days=wt) if basis else _naechster(heute, wt, auch_heute=False)
        else:
            start = basis or heute + timedelta(days=1)
            hinweise.append(f"Kein Beginn genannt – ab {TAG_NAMEN[start.weekday()]} {start.strftime('%d.%m.')} angenommen.")
        if anzahl:
            return [d.isoformat() for d in _werktage(start, min(anzahl, 60))], hinweise
        freitag = _montag(start) + timedelta(days=4)
        if start > freitag:
            return [start.isoformat()], hinweise
        return [(start + timedelta(days=i)).isoformat() for i in range((freitag - start).days + 1)], hinweise

    # „bis freitag“ ohne Anfang: ab heute bis zu diesem Tag (Arbeitstage)
    m_bis = re.search(r"\bbis (" + "|".join(WOCHENTAGE) + r")\b", s)
    if m_bis and not re.search(r"\b(ab|von)\b", s):
        wt = _wochentag(m_bis.group(1))
        ziel = basis + timedelta(days=wt) if basis else _naechster(heute, wt, auch_heute=True)
        start = max(heute, basis) if basis else heute
        tage = [start + timedelta(days=i) for i in range((ziel - start).days + 1)]
        hinweise.append(f"„bis {TAG_NAMEN[wt]}“: ab {TAG_NAMEN[start.weekday()]} {start.strftime('%d.%m.')} angenommen.")
        return [d.isoformat() for d in tage if d.weekday() < 5 or d == ziel], hinweise

    # einzelner Wochentag („mittwoch“, „nächste woche mittwoch“)
    genannt = [WOCHENTAGE[w] for w in re.findall(r"\b(" + "|".join(WOCHENTAGE) + r")\b", s)]
    if genannt:
        aus = []
        for wt in dict.fromkeys(genannt):
            if basis:
                aus.append(basis + timedelta(days=wt))
            else:
                d = _naechster(heute, wt, auch_heute=False)
                if wt == heute.weekday():
                    hinweise.append(f"„{TAG_NAMEN[wt]}“ als kommenden {TAG_NAMEN[wt]} ({d.strftime('%d.%m.')}) verstanden, nicht heute.")
                aus.append(d)
        return sorted(d.isoformat() for d in aus), hinweise

    # heute / morgen / übermorgen – auch zusammen („heute und morgen“)
    relativ = [heute + timedelta(days=n) for wort, n in (("heute", 0), ("morgen", 1), ("uebermorgen", 2)) if re.search(rf"\b{wort}\b", s)]
    if relativ:
        return [d.isoformat() for d in relativ], hinweise

    # ganze Woche / diese Woche / nächste Woche / jeden Tag
    if basis or re.search(r"\b(ganze[n]? woche|diese woche|die woche|jeden tag|taeglich|mo bis fr|montag bis freitag)\b", s):
        diese = re.search(r"\bdiese woche\b", s) and not re.search(r"\bganze[n]? woche\b", s)
        if basis:
            start = max(basis, heute)
        elif diese and heute.weekday() == 4:     # „diese Woche“ am Freitag: nur noch heute
            start = heute
        elif heute.weekday() >= 4:   # Freitag bis Sonntag: gemeint ist die nächste Woche
            start = _montag(heute) + timedelta(weeks=1)
            hinweise.append("„Die ganze Woche“ als nächste Woche verstanden (heute ist Wochenende bzw. Freitag).")
        else:
            start = heute
            if heute.weekday() > 0:
                hinweise.append(f"„Die ganze Woche“: ab heute ({TAG_NAMEN[heute.weekday()]}) bis Freitag – vergangene Tage nicht.")
        freitag = _montag(start) + timedelta(days=4)
        return [(start + timedelta(days=i)).isoformat() for i in range((freitag - start).days + 1)], hinweise
    return [], hinweise


# ---------------------------------------------------------------- Regel-Rückfall (ohne KI)

def regeln_zerlegen(text: str, namen: list[str], projekte: list[dict]) -> dict:
    """Felder mit festen Regeln – für Sätze in der gewohnten Form. Namen werden gegen die echten Mitarbeiter erkannt."""
    roh = text or ""
    s = normal(roh)
    felder: dict = {"mitarbeiter": [], "projekt": None, "standort": None, "startzeit": None, "endzeit": None, "zeitraum": None, "unsicher": []}

    # Uhrzeit „(von) 7 (uhr) bis 16 (uhr)“ / „7:30 bis 16“ / „sieben bis vier“
    zahl = r"(?:halb )?(?:\d{1,2}(?:[:.]\d{2})?|" + "|".join(sorted(ZAHLWOERTER, key=len, reverse=True)) + r")"
    m = re.search(r"\b(?:von |ab )?(" + zahl + r")(?: uhr(?: (\d{2}))?)? bis (" + zahl + r")(?: uhr(?: (\d{2}))?)?\b", s)
    if m:
        a = uhrzeit(m.group(1) + (f":{m.group(2)}" if m.group(2) else ""))
        b = uhrzeit(m.group(3) + (f":{m.group(4)}" if m.group(4) else ""))
        felder["startzeit"], felder["endzeit"] = zeiten_ordnen(a, b)
        s_ohne_zeit = s[:m.start()] + " " + s[m.end():]
    else:
        s_ohne_zeit = s
        # „7-16“, „7:30 - 16 Uhr“ (nicht Datum „1.12.-3.12.“: kein Punkt direkt davor oder danach)
        m_strich = re.search(r"(?<![\d.])(\d{1,2}(?::\d{2})?)\s*-\s*(\d{1,2}(?::\d{2})?)(?![\d.])(?: uhr)?", s)
        if m_strich and uhrzeit(m_strich.group(1)) and uhrzeit(m_strich.group(2)):
            felder["startzeit"], felder["endzeit"] = zeiten_ordnen(uhrzeit(m_strich.group(1)), uhrzeit(m_strich.group(2)))
            s_ohne_zeit = s[:m_strich.start()] + " " + s[m_strich.end():]
        else:
            # nur Beginn („um 8 Uhr“, „ab 7:30“) oder nur Ende („bis 14 Uhr“) – mit „Uhr“ oder Doppelpunkt, sonst wäre es ein Tag
            einzeln = r"(" + zahl + r") uhr(?: (\d{2}))?\b|(\d{1,2}:\d{2})\b"
            for feld, wort in (("startzeit", r"(?:um|ab)"), ("endzeit", r"bis")):
                m1 = re.search(r"\b" + wort + r" (?:" + einzeln + r")", s_ohne_zeit)
                if m1:
                    roh_zeit = m1.group(3) or (m1.group(1) + (f":{m1.group(2)}" if m1.group(2) else ""))
                    felder[feld] = uhrzeit(roh_zeit)
                    s_ohne_zeit = s_ohne_zeit[:m1.start()] + " " + s_ohne_zeit[m1.end():]

    # Zeitraum: alles, was nach Tagen klingt
    teile = re.findall(r"\b(?:ab |von |am |bis )?(?:(?:uebernaechste|naechste|kommende)[nr]? woche|diese woche|(?:die )?ganzen? woche|heute|morgen|uebermorgen|jeden tag|taeglich|"
                       r"in \w+ wochen?|(?:kw|kalenderwoche) ?\d{1,2}|(?:(?:naechste|kommende|diese)[sn]? )?wochenende|"
                       r"\w+ (?:(?:arbeits)?tage?n?|wochen?)|\d{1,2}\.\d{1,2}\.(?:\d{2,4})?(?:\s*-\s*\d{1,2}\.\d{1,2}\.(?:\d{2,4})?)?|\d{1,2}\.? (?:" + "|".join(MONATE) + r")|"
                       r"(?:" + "|".join(list(WOCHENTAGE) + list(KURZ)) + r")(?:\s*(?:-|bis)\s*(?:" + "|".join(list(WOCHENTAGE) + list(KURZ)) + r"))?)(?!\w)", s_ohne_zeit)
    wochenwort = re.compile(r"(?:ueber)?naechste[nr]?|kommende[nr]?|diese[nr]?|ganzen?|die")
    teile = [t for t in teile if not re.fullmatch(r"(?:ab |von |am |bis )?\w+ (?:(?:arbeits)?tage?n?|wochen?)", t) or t.endswith("jeden tag")
             or wochenwort.fullmatch(t.split()[-2]) or _zahl(t.split()[-2]) is not None]   # „zwei wochen“ ja, „viele wochen“ nein
    teile = [t for t in teile if not re.fullmatch(r"(?:ab |von |am |bis )?(?:mo|di|mi|do|fr|sa|so)", t)]
    if teile:
        felder["zeitraum"] = " ".join(teile)

    # Namen: genau (auch „Hans-Peter“, „Şahin“) oder leicht verhört/vertippt („Jurgen“ für Jürgen)
    namenswoerter = {w for n in namen for w in woerter(n) if len(w) >= 2}
    voll = [set(woerter(n)) for n in namen]
    projektwoerter = {w for p in projekte for w in woerter(p.get("name")) if len(w) >= 4}

    def ist_name(w: str) -> bool:
        teile_w = [x for x in w.split("-") if x]
        if not teile_w:
            return False
        return all(x in namenswoerter or (len(x) >= 4 and x not in FUELLWOERTER and x not in projektwoerter
                                          and any(len(y) >= 4 and _aehnlich(x, y) >= 0.9 for y in namenswoerter)) for x in teile_w)

    tokens = re.findall(WORT, roh)
    # Vor- und Nachname direkt hintereinander („Karl Schmidt“) bleiben ein Name, auch wenn „Schmidt“ in einem Projektnamen vorkommt
    geschuetzt = {i for i in range(len(tokens) - 1) for v in voll
                  if normal(tokens[i]) in v and normal(tokens[i + 1]) in v and normal(tokens[i]) != normal(tokens[i + 1])}
    geschuetzt |= {i + 1 for i in geschuetzt}
    geschuetzte_woerter = {normal(tokens[i]) for i in geschuetzt}

    # Standort (Straße) aus dem Originaltext – kein Nachname wie „Döring“
    for m in re.finditer(STRASSE, roh):
        kandidat = m.group(0).strip(" ,.")
        if not all(w in namenswoerter for w in woerter(kandidat) if not w.isdigit()):
            felder["standort"] = kandidat
            break

    # Projekt: „Projekt X“, „Baustelle X“, „bei X“ – sonst Wörter aus Projektnamen
    def kuerzen(gesagt: str) -> str:   # „Projekt Müller Tom Wagner“ → „Müller“: beim ersten Mitarbeiternamen aufhören
        aus = []
        for i, w in enumerate(gesagt.split()):
            n = normal(w)
            if i and (ist_name(n) and n not in projektwoerter or n in geschuetzte_woerter):
                break
            aus.append(w)
        return " ".join(aus)
    m = re.search(r"\b(?i:projekt|baustelle|objekt)\s+(" + WORT + r"(?:\s+(?=[A-ZÄÖÜ])" + WORT + r")*)", roh)
    m2 = re.search(r"\b(?i:bei) (?i:der |dem |den |familie |firma )?((?=[A-ZÄÖÜ])" + WORT + r"(?:\s+(?=[A-ZÄÖÜ])" + WORT + r")?)", roh)
    if m:
        felder["projekt"] = kuerzen(m.group(1))
    elif m2:
        felder["projekt"] = kuerzen(m2.group(1))
    else:
        def projektwort(i: int, w: str) -> bool:   # ganzes Wort oder Wortanfang („Dach“ → „Dachsanierung“), aber kein Mitarbeitername
            n = normal(w)
            if n in FUELLWOERTER or i in geschuetzt:
                return False
            return n in projektwoerter or (len(n) >= 4 and n not in namenswoerter and any(x.startswith(n) for x in projektwoerter))
        treffer = [w for i, w in enumerate(tokens) if projektwort(i, w)]
        if treffer:
            felder["projekt"] = " ".join(dict.fromkeys(treffer))
    projekt_woerter = set(woerter(felder["projekt"])) if felder["projekt"] else set()
    strasse_woerter = set(woerter(felder["standort"])) if felder["standort"] else set()

    # Mitarbeiter: Wörter, die Vor- oder Nachnamen echter Mitarbeiter sind (aufeinanderfolgende = ein Name)
    aktuell: list[str] = []
    for wort in re.findall(WORT + r"|[,;]", roh):
        w = normal(wort)
        passt = ist_name(w) and w not in projekt_woerter and w not in strasse_woerter and w not in FUELLWOERTER
        if passt:
            aktuell.append(wort)
        elif aktuell:
            felder["mitarbeiter"].append(" ".join(aktuell))
            aktuell = []
    if aktuell:
        felder["mitarbeiter"].append(" ".join(aktuell))
    felder["mitarbeiter"] = list(dict.fromkeys(felder["mitarbeiter"]))
    for f in ("mitarbeiter", "projekt", "zeitraum"):
        if not felder[f]:
            felder["unsicher"].append(f)
    return felder


# ---------------------------------------------------------------- KI auf dem Server: Mistral Small (EU), nur mit Flag `ki`

MISTRAL_ANWEISUNG = (
    "Du zerlegst einen gesprochenen deutschen Satz eines Handwerksmeisters, der Mitarbeiter auf Baustellen einteilt. "
    "Antworte ausschließlich mit einem JSON-Objekt: {\"mitarbeiter\": [\"Name wie gesagt\"], \"projekt\": \"wie gesagt\"|null, "
    "\"standort\": \"Straße/Ort wie gesagt\"|null, \"startzeit\": \"HH:MM\"|null, \"endzeit\": \"HH:MM\"|null, "
    "\"zeitraum\": \"Zeitangabe wörtlich, z. B. die ganze Woche, ab Montag drei Tage, morgen, nächste Woche Mittwoch\"|null, "
    "\"unsicher\": [Feldnamen, bei denen du nicht sicher bist]}. Rechne KEINE Daten aus und erfinde nichts: was nicht gesagt wurde, ist null. "
    "Uhrzeiten im 24-Stunden-Format; „sieben bis vier“ auf der Baustelle bedeutet 07:00 bis 16:00."
)


def mistral_eingerichtet() -> bool:
    return bool(os.environ.get("MISTRAL_API_KEY"))


async def mistral_zerlegen(text: str, transport=None) -> dict:
    """Felder per Mistral Small. Schlüssel nur auf dem Server (MISTRAL_API_KEY). Tests übergeben einen Testersatz als transport."""
    import httpx
    modell = os.environ.get("MISTRAL_MODELL", "mistral-small-latest")
    async with httpx.AsyncClient(transport=transport, timeout=30) as c:
        r = await c.post("https://api.mistral.ai/v1/chat/completions",
                         headers={"Authorization": f"Bearer {os.environ.get('MISTRAL_API_KEY', '')}"},
                         json={"model": modell, "temperature": 0, "response_format": {"type": "json_object"},
                               "messages": [{"role": "system", "content": MISTRAL_ANWEISUNG}, {"role": "user", "content": text}]})
    if r.status_code != 200:
        raise RuntimeError(f"Mistral {r.status_code}")
    try:
        inhalt = r.json()["choices"][0]["message"]["content"]
        daten = json.loads(inhalt)
    except (KeyError, IndexError, ValueError) as exc:
        raise RuntimeError("Mistral-Antwort unlesbar") from exc
    return felder_pruefen(daten)


def felder_pruefen(daten: Any) -> dict:
    """Felder aus KI (Apple oder Mistral) säubern: nur erwartete Felder, Texte gekürzt, Uhrzeiten normalisiert."""
    d = daten if isinstance(daten, dict) else {}
    mitarbeiter = d.get("mitarbeiter") or []
    if isinstance(mitarbeiter, str):
        mitarbeiter = [t.strip() for t in re.split(r",| und ", mitarbeiter) if t.strip()]
    text = lambda v, n=120: (str(v).strip()[:n] or None) if v not in (None, "") else None  # noqa: E731
    start, ende = zeiten_ordnen(uhrzeit(d.get("startzeit")), uhrzeit(d.get("endzeit")))
    unsicher = [u for u in (d.get("unsicher") or []) if isinstance(u, str) and u in FELDER]
    return {"mitarbeiter": [str(m).strip()[:80] for m in mitarbeiter if str(m).strip()][:20], "projekt": text(d.get("projekt")),
            "standort": text(d.get("standort")), "startzeit": start, "endzeit": ende, "zeitraum": text(d.get("zeitraum"), 200), "unsicher": unsicher}


# ---------------------------------------------------------------- Zuordnen über die echten Daten

def _aehnlich(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def _passt(w: str, x: str) -> bool:
    """Wort passt zu Wort: fast gleich (verhört/vertippt), Teil eines zusammengesetzten Worts („sanierung“ in „badsanierung“)
    oder dessen Anfang („dach“ für „dachsanierung“)."""
    return (_aehnlich(w, x) >= 0.85 or (len(w) >= 5 and len(x) >= 5 and (w in x or x in w))
            or (len(w) >= 4 and len(x) > len(w) and x.startswith(w)))


def mitarbeiter_finden(gesagt: str, nutzer: list[dict]) -> list[dict]:
    """Beste Treffer für einen gesagten Namen (mehrere = Rückfrage). Vor- und Nachnamen, vertippt/verhört bis ~85 % Ähnlichkeit."""
    g = woerter(gesagt)
    if not g:
        return []
    bewertet = []
    for u in nutzer:
        n = woerter(u.get("name"))
        if not n:
            continue
        if g == n:
            punkte = 100
        elif all(w in n for w in g):
            punkte = 90
        else:
            punkte = 0
            for w in g:
                besser = max((_aehnlich(w, x) for x in n), default=0)
                if besser >= 0.85:
                    punkte = max(punkte, int(70 * besser))
            if punkte and not all(max((_aehnlich(w, x) for x in n), default=0) >= 0.85 for w in g):
                punkte = 0
        if punkte:
            bewertet.append((punkte, u))
    if not bewertet:
        return []
    beste = max(p for p, _ in bewertet)
    return [u for p, u in bewertet if p == beste]


def projekt_finden(gesagt: Optional[str], standort: Optional[str], projekte: list[dict]) -> list[dict]:
    """Projekt über Namen, Kunde und Adresse; ohne Projektangabe über den Standort."""
    g = [w for w in woerter(gesagt) if w not in FUELLWOERTER]
    st = [w for w in woerter(standort) if not w.isdigit()]
    bewertet = []
    for p in projekte:
        name, kunde, adresse = woerter(p.get("name")), woerter(p.get("customer_name")), woerter(p.get("address"))
        punkte = 0.0
        if g:
            if " ".join(g) == " ".join(name):
                punkte = 100
            elif all(w in name for w in g):
                punkte = 90
            elif all(w in name + kunde for w in g):
                punkte = 80
            else:
                treffer = sum(1 for w in g if any(_passt(w, x) for x in name + kunde))
                punkte = 60 * treffer / len(g) if treffer else 0
        if st and adresse and all(any(_aehnlich(w, x) >= 0.85 or x.startswith(w) for x in adresse) for w in st):
            punkte += 15 if g else 50
        if punkte:
            bewertet.append((punkte, p))
    if not bewertet:
        return []
    beste = max(p for p, _ in bewertet)
    return [p for punkte, p in bewertet if punkte == beste]


def _kurz_name(u: dict) -> dict:
    return {"id": u["id"], "name": u.get("name") or ""}


def _tage_text(tage: list[str]) -> str:
    ds = [date.fromisoformat(t) for t in tage]
    if not ds:
        return ""
    if len(ds) == 1:
        return f"{TAG_NAMEN[ds[0].weekday()]} {ds[0].strftime('%d.%m.')}"
    return f"{TAG_NAMEN[ds[0].weekday()]} {ds[0].strftime('%d.%m.')} – {TAG_NAMEN[ds[-1].weekday()]} {ds[-1].strftime('%d.%m.')} ({len(ds)} Tage)"


async def vorschlag(firma: dict, felder: dict, heute: date, quelle: str) -> dict:
    """Felder → Einteilungsvorschlag mit Rückfragen, Hinweisen und Konflikten. Speichert nichts."""
    from db import db

    firma_id = firma["id"]
    nutzer = [u async for u in db().users.find({"firma_id": firma_id, "active": {"$ne": False}}, {"_id": 0, "id": 1, "name": 1, "role": 1})]
    projekte = [p async for p in db().projects.find({"firma_id": firma_id, "archived": {"$ne": True}},
                                                     {"_id": 0, "id": 1, "name": 1, "address": 1, "customer_name": 1})]
    unsicher = set(felder.get("unsicher") or [])
    rueckfragen: list[dict] = []
    hinweise: list[str] = []

    # Mitarbeiter
    personen = []
    for gesagt in felder.get("mitarbeiter") or []:
        treffer = mitarbeiter_finden(gesagt, nutzer)
        if len(treffer) == 1:
            if any(p.get("id") == treffer[0]["id"] for p in personen):
                continue   # dieselbe Person zweimal genannt („Tom und Tom Wagner“)
            personen.append({"gesagt": gesagt, **_kurz_name(treffer[0])})
        elif treffer:
            namen = [t.get("name") for t in treffer]
            rueckfragen.append({"feld": "mitarbeiter", "gesagt": gesagt, "frage": f"Meinst du {', '.join(namen[:-1])} oder {namen[-1]}?",
                                "optionen": [_kurz_name(t) for t in treffer]})
            personen.append({"gesagt": gesagt, "id": None, "kandidaten": [_kurz_name(t) for t in treffer]})
        else:
            rueckfragen.append({"feld": "mitarbeiter", "gesagt": gesagt, "frage": f"Wen meinst du mit „{gesagt}“?",
                                "optionen": [_kurz_name(u) for u in sorted(nutzer, key=lambda u: u.get("name") or "")][:12]})
            personen.append({"gesagt": gesagt, "id": None, "kandidaten": []})
    if not personen:
        rueckfragen.append({"feld": "mitarbeiter", "gesagt": "", "frage": "Wen soll ich einteilen?",
                            "optionen": [_kurz_name(u) for u in sorted(nutzer, key=lambda u: u.get("name") or "")][:12]})

    # Projekt und Standort
    projekt = None
    p_treffer = projekt_finden(felder.get("projekt"), felder.get("standort"), projekte) if (felder.get("projekt") or felder.get("standort")) else []
    kurz_p = lambda p: {"id": p["id"], "name": p.get("name") or "", "address": p.get("address") or ""}  # noqa: E731
    if len(p_treffer) == 1:
        projekt = kurz_p(p_treffer[0])
        projekt["gesagt"] = felder.get("projekt") or ""
    elif p_treffer:
        namen = [p.get("name") for p in p_treffer]
        rueckfragen.append({"feld": "projekt", "gesagt": felder.get("projekt") or felder.get("standort") or "",
                            "frage": f"Welches Projekt: {', '.join(namen[:-1])} oder {namen[-1]}?", "optionen": [kurz_p(p) for p in p_treffer]})
    else:
        gesagt = felder.get("projekt") or ""
        rueckfragen.append({"feld": "projekt", "gesagt": gesagt, "frage": f"Welches Projekt ist „{gesagt}“?" if gesagt else "Für welches Projekt?",
                            "optionen": [kurz_p(p) for p in sorted(projekte, key=lambda p: p.get("name") or "")][:12]})
    adresse = (projekt or {}).get("address") or ""
    standort = felder.get("standort")
    if standort:
        nummern = [w for w in woerter(standort) if w[:1].isdigit()]
        if (projekt and all(any(x.startswith(w) or _aehnlich(w, x) >= 0.85 for x in woerter(adresse)) for w in woerter(standort) if not w[:1].isdigit())
                and all(n in woerter(adresse) for n in nummern)):   # andere Hausnummer = andere Adresse
            pass   # Standort passt zur Projektadresse
        else:
            adresse = standort
            unsicher.add("standort")
            hinweise.append(f"Standort „{standort}“ steht nicht in der Projektadresse – wird als Einsatzadresse übernommen. Bitte prüfen.")

    # Tage
    tage, t_hinweise = tage_berechnen(felder.get("zeitraum"), heute)
    hinweise += t_hinweise
    if not tage:
        rueckfragen.append({"feld": "tage", "gesagt": felder.get("zeitraum") or "", "frage": "An welchen Tagen?", "optionen": []})
    vergangen = [t for t in tage if t < heute.isoformat()]
    if vergangen:
        tage = [t for t in tage if t >= heute.isoformat()]
        hinweise.append("Vergangene Tage weggelassen.")

    # Uhrzeit (fehlt sie, Standardzeit vorschlagen und markieren)
    start, ende = felder.get("startzeit"), felder.get("endzeit")
    if not start or not ende:
        if not start and not ende:
            hinweise.append(f"Keine Uhrzeit genannt – Standardzeit {STANDARD_START[:2].lstrip('0')}–{STANDARD_ENDE[:2]} Uhr vorgeschlagen.")
        elif not ende:
            hinweise.append(f"Kein Ende genannt – {STANDARD_ENDE} Uhr vorgeschlagen.")
        else:
            hinweise.append(f"Kein Beginn genannt – {STANDARD_START} Uhr vorgeschlagen.")
        if not start:
            unsicher.add("startzeit")
        if not ende:
            unsicher.add("endzeit")
        start, ende = start or STANDARD_START, ende or STANDARD_ENDE
    if ende < start:
        unsicher.update({"startzeit", "endzeit"})
        hinweise.append(f"Ende {ende} liegt vor Beginn {start} – das wäre eine Nachtschicht bis zum nächsten Morgen. Bitte prüfen.")

    # Konflikte (wie die Plantafel) und Feiertage/Wochenende
    konflikte = await konflikte_pruefen(firma, [p["id"] for p in personen if p.get("id")], tage, start, ende, nutzer)

    user_ids = [p["id"] for p in personen if p.get("id")]
    vollstaendig = bool(projekt and user_ids and tage and not [r for r in rueckfragen if r["feld"] in ("mitarbeiter", "projekt", "tage")])
    entwurf = {"project_id": projekt["id"], "user_ids": user_ids, "dates": tage, "start_time": start, "end_time": ende,
               "pause_minutes": STANDARD_PAUSE, "address": adresse if adresse != (projekt or {}).get("address") else ""} if vollstaendig else None
    return {"quelle": quelle, "felder": felder, "mitarbeiter": personen, "projekt": projekt, "adresse": adresse, "tage": tage, "tage_text": _tage_text(tage),
            "start_time": start, "end_time": ende, "pause_minutes": STANDARD_PAUSE, "unsicher": sorted(unsicher), "rueckfragen": rueckfragen,
            "hinweise": hinweise, "konflikte": konflikte, "entwurf": entwurf,
            "hinweis": "Nur ein Vorschlag – gespeichert wird erst, wenn du ihn bestätigst."}


async def konflikte_pruefen(firma: dict, user_ids: list[str], tage: list[str], start: str, ende: str, nutzer: Optional[list[dict]] = None) -> list[dict]:
    """Konflikte einer geplanten Einteilung: Überschneidung (blockiert das Speichern), Abwesenheit (nur mit „trotzdem“),
    Feiertag und Wochenende (Hinweis). Speichert nichts – auch nach jeder Änderung im Bestätigungsfenster aufgerufen."""
    from db import db
    from feiertage import feiertage_set
    from routes.einsatzplan import _konflikte

    if nutzer is None:
        nutzer = [u async for u in db().users.find({"firma_id": firma["id"], "id": {"$in": user_ids}}, {"_id": 0, "id": 1, "name": 1})]
    namen = {u["id"]: u.get("name") or "" for u in nutzer}
    konflikte: list[dict] = []
    feiertage = feiertage_set(sorted({int(t[:4]) for t in tage}), firma.get("bundesland") or "") if tage else {}
    for t in tage:
        d = date.fromisoformat(t)
        if t in feiertage:
            konflikte.append({"user_id": None, "name": "", "datum": t, "art": "feiertag", "text": f"{_tage_text([t])}: Feiertag ({feiertage[t]})"})
        elif d.weekday() >= 5:
            konflikte.append({"user_id": None, "name": "", "datum": t, "art": "wochenende", "text": f"{_tage_text([t])}: Wochenende"})
    for uid in user_ids:
        for t in tage:
            ueberlappungen, abwesend = await _konflikte(firma["id"], uid, t, start, ende)
            for x in ueberlappungen:
                konflikte.append({"user_id": uid, "name": namen.get(uid, ""), "datum": t, "art": "ueberschneidung",
                                  "text": f"{namen.get(uid, '')} ist {_tage_text([t])} schon {x['start_time']}–{x['end_time']} eingeteilt."})
            for a in abwesend:
                art = {"urlaub": "Urlaub", "krank": "krank", "unbezahlt": "unbezahlt frei", "feiertag": "frei"}.get(a.get("type"), "abwesend")
                konflikte.append({"user_id": uid, "name": namen.get(uid, ""), "datum": t, "art": "abwesenheit",
                                  "text": f"{namen.get(uid, '')} ist {_tage_text([t])} {art}{' (beantragt)' if a.get('status') == 'beantragt' else ''}."})
    return konflikte
