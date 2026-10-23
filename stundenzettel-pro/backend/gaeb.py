"""GAEB-Anbindung (eigenständiges, klar abgegrenztes Modul).

Stand: Erkennung der Datei und ehrliche Fehlermeldung. Ein vollständiger GAEB-DA-XML-Import (X83 = Angebotsaufforderung,
X84 = Angebotsabgabe) bzw. GAEB 90/2000 wird erst umgesetzt, wenn feststeht, welche Austauschphasen und Versionen die
Auftraggeber tatsächlich liefern. Bis dahin läuft der Austausch des Leistungsverzeichnisses über CSV (Nr;Leistung;Menge;Einheit).

Schnittstelle für die spätere Umsetzung: `lesen(inhalt, dateiname) -> list[dict]` mit Positionen
{nr, leistung, beschreibung, menge, einheit} und `schreiben(positionen) -> bytes`.
"""
from __future__ import annotations

import re


class GaebNichtUnterstuetzt(Exception):
    pass


def erkennen(inhalt: bytes, dateiname: str = "") -> str:
    """Grobe Erkennung: 'xml' (GAEB DA XML), 'gaeb90' (Satzformat), '' (unbekannt)."""
    kopf = inhalt[:4000].decode("latin-1", errors="ignore")
    name = (dateiname or "").lower()
    if "<GAEB" in kopf or re.search(r"\.x8[1-9]$|\.x9[0-9]$", name):
        return "xml"
    if re.match(r"^\s*00\s", kopf) or re.search(r"\.d8[1-9]$|\.p8[1-9]$", name):
        return "gaeb90"
    return ""


def lesen(inhalt: bytes, dateiname: str = "") -> list[dict]:
    art = erkennen(inhalt, dateiname)
    if art == "xml":
        raise GaebNichtUnterstuetzt("GAEB DA XML erkannt. Der Import ist vorbereitet, aber noch nicht umgesetzt – bitte das Leistungsverzeichnis als CSV (Nr;Leistung;Menge;Einheit) übergeben.")
    if art == "gaeb90":
        raise GaebNichtUnterstuetzt("GAEB 90/2000 erkannt. Dieses Format ist noch nicht unterstützt – bitte als CSV übergeben.")
    raise GaebNichtUnterstuetzt("Keine GAEB-Datei erkannt (erwartet .x83/.x84 oder .d83). Bitte als CSV übergeben.")


def schreiben(positionen: list[dict]) -> bytes:
    raise GaebNichtUnterstuetzt("GAEB-Export ist noch nicht umgesetzt – bitte den CSV-Export nutzen.")
