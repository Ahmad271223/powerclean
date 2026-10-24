"""Digitales Aufmaß (Stufe F): Mengen aus Formeln berechnen – ohne eval, mit einem kleinen eigenen Parser.

Erlaubt sind Zahlen (Dezimalkomma oder -punkt), + - * / (auch „x“ und „×“ für mal), Klammern und ein Vorzeichen; mehrere Teilmengen lassen
sich mit „;“ oder Zeilenumbruch trennen und werden addiert (z. B. „3,20 x 2,60; 1,10 x 2,60“). Alles andere ist ein Fehler mit Klartext.
Ein Aufmaß gehört zu einem Projekt und wahlweise zu einer Position (Angebots- oder Auftragsposition); geprüfte Mengen werden in Positionen übernommen.
"""
from __future__ import annotations

import re
from typing import Optional

from angebote import rund

TYPEN = {"laenge": ("Länge", "m"), "flaeche": ("Fläche", "m²"), "volumen": ("Volumen", "m³"), "stueck": ("Stückzahl", "Stk."), "gewicht": ("Gewicht", "kg"), "sonstiges": ("Sonstiges", "")}
STATUS_NAMEN = {"erfasst": "Erfasst", "geprueft": "Geprüft"}
VORLAGEN = {"laenge": "L1 + L2 + …", "flaeche": "Länge x Höhe", "volumen": "Länge x Breite x Höhe", "stueck": "Anzahl", "gewicht": "Menge x kg je Einheit"}

_TOKEN = re.compile(r"\s*(?:(\d+(?:[.,]\d+)?)|([-+*/×x()]))", re.I)


class FormelFehler(ValueError):
    pass


def _tokens(text: str) -> list:
    text = text.strip()
    aus, pos = [], 0
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if not m or m.end() == pos:
            rest = text[pos:pos + 12]
            raise FormelFehler(f"Unerlaubtes Zeichen bei „{rest}“ – erlaubt sind Zahlen, + - * / x und Klammern.")
        zahl, op = m.group(1), m.group(2)
        if zahl is not None:
            if "," in zahl and "." in zahl:
                raise FormelFehler(f"Zahl „{zahl}“ hat Komma und Punkt – bitte nur ein Dezimalzeichen.")
            aus.append(("zahl", float(zahl.replace(",", "."))))
        else:
            aus.append(("op", "*" if op.lower() in ("x", "×") else op))
        pos = m.end()
    return aus


class _Parser:
    """Rekursiver Abstieg: ausdruck = term (('+'|'-') term)*, term = faktor (('*'|'/') faktor)*, faktor = ('-'|'+') faktor | zahl | '(' ausdruck ')'."""

    def __init__(self, tokens: list):
        self.t, self.i = tokens, 0

    def _peek(self):
        return self.t[self.i] if self.i < len(self.t) else (None, None)

    def _next(self):
        tok = self._peek()
        self.i += 1
        return tok

    def ausdruck(self) -> float:
        wert = self.term()
        while self._peek() == ("op", "+") or self._peek() == ("op", "-"):
            op = self._next()[1]
            rechts = self.term()
            wert = wert + rechts if op == "+" else wert - rechts
        return wert

    def term(self) -> float:
        wert = self.faktor()
        while self._peek() == ("op", "*") or self._peek() == ("op", "/"):
            op = self._next()[1]
            rechts = self.faktor()
            if op == "/":
                if rechts == 0:
                    raise FormelFehler("Division durch null.")
                wert = wert / rechts
            else:
                wert = wert * rechts
        return wert

    def faktor(self) -> float:
        art, wert = self._peek()
        if art == "op" and wert in ("-", "+"):
            self._next()
            f = self.faktor()
            return -f if wert == "-" else f
        if art == "zahl":
            self._next()
            return wert
        if art == "op" and wert == "(":
            self._next()
            innen = self.ausdruck()
            if self._peek() != ("op", ")"):
                raise FormelFehler("Klammer wurde nicht geschlossen.")
            self._next()
            return innen
        if art is None:
            raise FormelFehler("Die Formel endet unerwartet – es fehlt eine Zahl.")
        raise FormelFehler(f"„{wert}“ an dieser Stelle nicht erlaubt.")


def berechnen(formel: str) -> float:
    """Formel auswerten; Teilmengen durch „;“ oder Zeilenumbruch getrennt werden addiert. Ergebnis auf drei Stellen gerundet."""
    if not formel or not str(formel).strip():
        raise FormelFehler("Bitte eine Formel oder Zahl eingeben.")
    if len(str(formel)) > 500:
        raise FormelFehler("Die Formel ist zu lang (max. 500 Zeichen).")
    summe = 0.0
    for teil in re.split(r"[;\n]+", str(formel)):
        if not teil.strip():
            continue
        tokens = _tokens(teil)
        if not tokens:
            continue
        p = _Parser(tokens)
        wert = p.ausdruck()
        if p.i != len(tokens):
            art, rest = tokens[p.i]
            raise FormelFehler(f"„{rest}“ passt nicht in die Formel – fehlt ein Rechenzeichen?")
        summe += wert
    if summe != summe or abs(summe) > 1e12:   # NaN oder absurd groß
        raise FormelFehler("Das Ergebnis ist nicht plausibel.")
    return round(summe, 3)


def einheit_fuer(typ: str, einheit: Optional[str] = None) -> str:
    return (einheit or "").strip()[:20] or TYPEN.get(typ, ("", ""))[1] or "Stk."


def summen_je_position(aufmasse: list[dict], nur_geprueft: bool = False) -> dict[str, dict]:
    """Mengen je Positionsbezug (nr) – getrennt nach geprüft und gesamt."""
    aus: dict[str, dict] = {}
    for a in aufmasse:
        nr = (a.get("position") or {}).get("nr") or ""
        if not nr:
            continue
        z = aus.setdefault(nr, {"nr": nr, "text": (a.get("position") or {}).get("text") or "", "einheit": a.get("einheit"), "gesamt": 0.0, "geprueft": 0.0, "anzahl": 0})
        z["anzahl"] += 1
        z["gesamt"] = round(z["gesamt"] + float(a.get("menge") or 0), 3)
        if a.get("status") == "geprueft":
            z["geprueft"] = round(z["geprueft"] + float(a.get("menge") or 0), 3)
    return aus
