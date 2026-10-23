"""CSV-Ausgaben gegen Formel-Einschleusung schützen: Tabellenprogramme werten Zellen, die mit = + - @ oder Steuerzeichen beginnen,
als Formel aus. Solche Texte bekommen ein führendes Hochkomma; Zahlen (auch negative) bleiben unverändert."""
from __future__ import annotations

import re

_ZAHL = re.compile(r"^[-+]?\d+([.,]\d+)?$")
_GEFAEHRLICH = ("=", "+", "-", "@", "\t", "\r", "\n")


def zelle(v):
    if isinstance(v, str) and v and v[0] in _GEFAEHRLICH and not _ZAHL.match(v.strip()):
        return "'" + v
    return v


def zeile(werte: list) -> list:
    return [zelle(v) for v in werte]


class Writer:
    """Ersatz für csv.writer: jede Zelle läuft durch zelle()."""

    def __init__(self, datei, **kw):
        import csv
        self.w = csv.writer(datei, **kw)

    def writerow(self, z):
        self.w.writerow(zeile(list(z)))

    def writerows(self, zs):
        for z in zs:
            self.writerow(z)
