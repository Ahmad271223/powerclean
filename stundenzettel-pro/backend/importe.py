"""Tabellen- und Dateiimporte (Stufe F): CSV (robust), Excel (.xlsx) und GAEB DA XML für Positionen; DATANORM und Excel für Artikel.
Alle Importe liefern eine Vorschau mit Fehlerzeilen (Zeilennummer + Grund) – nichts wird stillschweigend ausgelassen."""
from __future__ import annotations

import io
import re
from typing import Optional

import gaeb
from material import csv_lesen, zahl

POSITIONS_SPALTEN = {
    "nr": ("nr", "nr.", "pos", "pos.", "position", "positionsnummer", "oz", "ordnungszahl", "lfd. nr.", "lfd nr"),
    "leistung": ("leistung", "bezeichnung", "kurztext", "text", "beschreibung kurz", "titel", "artikel", "name"),
    "beschreibung": ("beschreibung", "langtext", "details", "erläuterung", "erlaeuterung"),
    "menge": ("menge", "anzahl", "qty", "quantity"),
    "einheit": ("einheit", "me", "mengeneinheit", "einh", "einh.", "unit"),
    "einzelpreis": ("einzelpreis", "ep", "preis", "einzelpreis netto", "ep netto", "unit_price", "vk"),
    "art": ("art", "typ", "positionsart"),
}
ARTEN_TEXT = {"titel": "titel", "gruppe": "titel", "t": "titel", "stunden": "stunden", "std": "stunden", "material": "material", "pauschal": "pauschal", "psch": "pauschal", "text": "text", "hinweis": "text"}


def xlsx_lesen(roh: bytes) -> tuple[list[str], list[list[str]]]:
    """Erstes Tabellenblatt als Kopfzeile + Zeilen (Zellen als Text, Zahlen unverändert als Text mit Punkt)."""
    try:
        import openpyxl
    except ImportError as exc:  # pragma: no cover
        raise ValueError("Excel-Import braucht das Paket openpyxl.") from exc
    try:
        wb = openpyxl.load_workbook(io.BytesIO(roh), read_only=True, data_only=True)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Die Excel-Datei lässt sich nicht lesen: {str(exc)[:120]}") from exc
    ws = wb.worksheets[0]
    zeilen = []
    for row in ws.iter_rows(values_only=True):
        werte = ["" if v is None else (str(v) if not isinstance(v, float) or v != int(v) else str(int(v))) for v in row]
        if any(str(w).strip() for w in werte):
            zeilen.append([str(w).strip() for w in werte])
    wb.close()
    if not zeilen:
        return [], []
    return [c.lower() for c in zeilen[0]], zeilen[1:]


def tabelle_lesen(roh: bytes, dateiname: str = "") -> tuple[list[str], list[list[str]], str]:
    name = (dateiname or "").lower()
    if name.endswith(".xlsx") or roh[:4] == b"PK\x03\x04":
        kopf, zeilen = xlsx_lesen(roh)
        return kopf, zeilen, "xlsx"
    kopf, zeilen, trenner = csv_lesen(roh)
    return kopf, zeilen, "csv"


def _spalten(kopf: list[str], schema: dict) -> dict[str, int]:
    aus = {}
    for i, name in enumerate(kopf):
        n = name.strip().lower()
        for feld, synonyme in schema.items():
            if feld not in aus and (n == feld or n in synonyme):
                aus[feld] = i
                break
    return aus


def positionen_aus_tabelle(kopf: list[str], zeilen: list[list[str]]) -> dict:
    """Positionen aus CSV/Excel: Spalten werden über Synonyme erkannt; ohne Kopfzeile gilt Nr;Leistung;Menge;Einheit;Beschreibung;Einzelpreis."""
    sp = _spalten(kopf, POSITIONS_SPALTEN)
    start = 2
    if "leistung" not in sp:   # keine erkennbare Kopfzeile → feste Reihenfolge, die erste Zeile ist eine Datenzeile
        sp = {"nr": 0, "leistung": 1, "menge": 2, "einheit": 3, "beschreibung": 4, "einzelpreis": 5}
        zeilen = [kopf] + zeilen if kopf and any(kopf) else zeilen
        start = 1

    def wert(z: list[str], feld: str) -> str:
        i = sp.get(feld)
        return (z[i] if i is not None and i < len(z) else "").strip()

    positionen, fehler, gesehen = [], [], set()
    for nr_zeile, z in enumerate(zeilen, start=start):
        leistung = wert(z, "leistung")
        nr = wert(z, "nr")
        art_text = wert(z, "art").lower()
        art = ARTEN_TEXT.get(art_text, "leistung")
        if not leistung:
            fehler.append({"zeile": nr_zeile, "grund": "Leistung/Bezeichnung fehlt."})
            continue
        if art in ("titel", "text"):
            positionen.append({"nr": nr[:20], "leistung": leistung[:300], "beschreibung": wert(z, "beschreibung")[:4000], "menge": 0.0, "einheit": "", "art": art})
            continue
        try:
            menge = zahl(wert(z, "menge"))
            ep = zahl(wert(z, "einzelpreis"))
        except ValueError as exc:
            fehler.append({"zeile": nr_zeile, "grund": str(exc)})
            continue
        if nr and nr in gesehen:
            fehler.append({"zeile": nr_zeile, "grund": f"Position {nr} kommt mehrfach vor."})
            continue
        if nr:
            gesehen.add(nr)
        p = {"nr": nr[:20], "leistung": leistung[:300], "beschreibung": wert(z, "beschreibung")[:4000], "menge": menge if menge is not None else 0.0,
             "einheit": (wert(z, "einheit") or "Stück")[:20], "art": art}
        if ep is not None:
            p["einzelpreis"] = ep
        positionen.append(p)
    return {"positionen": positionen, "fehler": fehler, "spalten": sp}


def positionen_aus_datei(roh: bytes, dateiname: str = "") -> dict:
    """CSV, Excel oder GAEB DA XML → Positionen mit Vorschau und Fehlerzeilen."""
    if len(roh) > 20 * 1024 * 1024:
        raise ValueError("Die Datei ist zu groß (max. 20 MB).")
    if gaeb.erkennen(roh, dateiname):
        try:
            g = gaeb.lesen(roh, dateiname)
        except gaeb.GaebNichtUnterstuetzt as exc:
            raise ValueError(str(exc)) from exc
        return {"positionen": g["positionen"], "fehler": [{"zeile": 0, "grund": h} for h in g["hinweise"]], "quelle": f"gaeb-x{g['phase']}", "projekt": g.get("projekt") or ""}
    kopf, zeilen, quelle = tabelle_lesen(roh, dateiname)
    if not kopf and not zeilen:
        return {"positionen": [], "fehler": [{"zeile": 1, "grund": "Die Datei ist leer."}], "quelle": quelle}
    aus = positionen_aus_tabelle(kopf, zeilen)
    if len(aus["positionen"]) > 1000:
        raise ValueError("Höchstens 1000 Positionen je Import.")
    return {**aus, "quelle": quelle}


# ---------------------------------------------------------------- DATANORM (Artikelkataloge der Lieferanten)

def ist_datanorm(roh: bytes, dateiname: str = "") -> bool:
    name = (dateiname or "").lower()
    if re.search(r"\.(001|002|003|dat)$", name) or "datanorm" in name:
        return True
    kopf = roh[:200].decode("latin-1", errors="ignore").lstrip("﻿")
    return kopf.startswith("V;") or kopf.startswith("V ") or re.match(r"^[AB];[NAL];", kopf) is not None


def artikel_aus_datanorm(roh: bytes) -> dict:
    """DATANORM 4.0/5.0 (Satzformat mit Semikolon): A-Sätze = Artikel (Nummer, Kurztexte, Einheit, Preis), P-Sätze = Preise, T-/B-Sätze = Zusatztexte.
    Preise ohne Dezimalzeichen gelten als Cent; die Preiseinheit (je 1/10/100/1000) wird umgerechnet. Unbekannte Satzarten werden gezählt, nicht verarbeitet."""
    for enc in ("cp850", "cp1252", "utf-8"):
        try:
            text = roh.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = roh.decode("latin-1")
    artikel: dict[str, dict] = {}
    fehler, uebersprungen, lieferant = [], {}, ""
    for nr, zeile in enumerate(text.replace("\r\n", "\n").replace("\r", "\n").split("\n"), start=1):
        if not zeile.strip():
            continue
        satz = zeile[0].upper()
        felder = [f.strip() for f in zeile.split(";")]
        if satz == "V":
            lieferant = next((f for f in felder[2:6] if f and not f.isdigit()), "") or lieferant
            continue
        if satz == "A" and len(felder) >= 5:
            nummer = felder[2]
            if not nummer:
                fehler.append({"zeile": nr, "grund": "A-Satz ohne Artikelnummer."})
                continue
            name = " ".join(t for t in (felder[4], felder[5] if len(felder) > 5 else "") if t).strip() or nummer
            einheit = (felder[8] if len(felder) > 8 else "") or "Stk."
            preis = _datanorm_preis(felder[9] if len(felder) > 9 else "", felder[7] if len(felder) > 7 else "0")
            a = artikel.setdefault(nummer, {"nummer": nummer[:60], "name": name[:200], "beschreibung": "", "einheit": einheit[:20], "einkaufspreis": None, "verkaufspreis": None,
                                            "hersteller": "", "lieferant": lieferant[:120], "kategorie": (felder[11] if len(felder) > 11 else "")[:80], "steuer_satz": None})
            a["name"] = name[:200]
            if preis is not None:
                if (felder[6] if len(felder) > 6 else "1") == "2":   # 2 = Nettopreis (Einkauf), 1 = Brutto-/Listenpreis
                    a["einkaufspreis"] = preis
                else:
                    a["einkaufspreis"] = a["einkaufspreis"] if a["einkaufspreis"] is not None else preis
                    a["verkaufspreis"] = preis
        elif satz == "P" and len(felder) >= 5:
            i = 2
            while i + 2 < len(felder):
                nummer, kz, preis = felder[i], felder[i + 1], _datanorm_preis(felder[i + 2], "0")
                if nummer and preis is not None:
                    a = artikel.setdefault(nummer, {"nummer": nummer[:60], "name": nummer, "beschreibung": "", "einheit": "Stk.", "einkaufspreis": None, "verkaufspreis": None,
                                                    "hersteller": "", "lieferant": lieferant[:120], "kategorie": "", "steuer_satz": None})
                    if kz == "2":
                        a["einkaufspreis"] = preis
                    else:
                        a["verkaufspreis"] = preis
                i += 3
        elif satz in ("T", "B") and len(felder) >= 4:
            nummer = felder[2]
            if nummer in artikel and felder[-1]:
                a = artikel[nummer]
                a["beschreibung"] = (a["beschreibung"] + "\n" + felder[-1]).strip()[:4000]
        else:
            uebersprungen[satz] = uebersprungen.get(satz, 0) + 1
    for satz, n in sorted(uebersprungen.items()):
        fehler.append({"zeile": 0, "grund": f"{n} Satz/Sätze der Art „{satz}“ nicht verarbeitet (nicht unterstützt)."})
    if not artikel:
        fehler.append({"zeile": 1, "grund": "Keine A-Sätze (Artikel) gefunden – ist das eine DATANORM-Datei?"})
    return {"spalten": {"quelle": "datanorm"}, "trenner": ";", "artikel": list(artikel.values()), "fehler": fehler, "kopf": [], "lieferant": lieferant}


def _datanorm_preis(text: str, einheit_kz: str) -> Optional[float]:
    text = (text or "").strip()
    if not text:
        return None
    try:
        wert = float(text.replace(",", ".")) if ("," in text or "." in text) else int(text) / 100
    except ValueError:
        return None
    teiler = {"0": 1, "1": 10, "2": 100, "3": 1000}.get((einheit_kz or "0").strip(), 1)
    return round(wert / teiler, 4)


def artikel_aus_xlsx(roh: bytes) -> dict:
    from material import artikel_aus_tabelle
    kopf, zeilen = xlsx_lesen(roh)
    return artikel_aus_tabelle(kopf, zeilen, "xlsx")
