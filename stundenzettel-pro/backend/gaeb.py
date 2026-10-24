"""GAEB DA XML (Stufe F): Leistungsverzeichnisse lesen (X81–X86, Schwerpunkt X83 Angebotsaufforderung) und schreiben
(X83 = LV des Auftraggebers, X84 = Angebotsabgabe mit Einheitspreisen).

Umgesetzt ist der fachliche Kern von GAEB DA XML 3.2/3.3: Gliederung über BoQCtgy (Titel/Lose, beliebig tief), Positionen (Item) mit
Ordnungszahl (RNoPart entlang des Pfads), Kurztext (OutlineText), Langtext (CompleteText/DetailTxt), Menge (Qty), Einheit (QU) und bei X84
Einheits- und Gesamtpreis (UP, IT) samt Summe. Nicht umgesetzt: Zuschlagspositionen, Bedarfs-/Alternativkennzeichen, Textergänzungen,
Pauschalpositionen mit Teilmengen, Zeitvertragsarbeiten, GAEB 90/2000 (Satzformat) – solche Dateien werden mit Klartext abgewiesen oder die
unbekannten Elemente übersprungen und gezählt. Vor dem Produktivbetrieb mit den tatsächlich gelieferten Dateien der Auftraggeber prüfen.

Schnittstelle: `lesen(inhalt, dateiname) -> dict(positionen=[{nr, leistung, beschreibung, menge, einheit, einzelpreis?, art titel|leistung, ebene}],
hinweise=[], phase, version)`; `schreiben(positionen, phase="83"|"84", info={...}) -> bytes`.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Optional

from lxml import etree

GAEB_NS = "http://www.gaeb.de/GAEB_DA_XML/DA{phase}/{version}"
VERSION = "3.2"


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


def _ln(el) -> str:
    return etree.QName(el).localname if isinstance(el.tag, str) else ""


def _kind(el, name: str):
    for k in el:
        if _ln(k) == name:
            return k
    return None


def _text(el) -> str:
    """Alle Textknoten (auch in <p>, <span>) zusammengezogen, Zeilen getrennt."""
    if el is None:
        return ""
    teile = []
    for p in el.iter():
        if _ln(p) in ("p", "div", "TextOutlTxt", "TextComplement") and (p.text or "").strip():
            teile.append(" ".join(("".join(p.itertext())).split()))
    if not teile:
        teile = [" ".join("".join(el.itertext()).split())]
    return "\n".join(t for t in teile if t).strip()


def _zahl(text: Optional[str]) -> Optional[float]:
    if text is None or not str(text).strip():
        return None
    try:
        return float(str(text).strip().replace(",", "."))
    except ValueError:
        return None


def lesen(inhalt: bytes, dateiname: str = "") -> dict:
    art = erkennen(inhalt, dateiname)
    if art == "gaeb90":
        raise GaebNichtUnterstuetzt("GAEB 90/2000 (Satzformat .d83/.p83) wird nicht unterstützt – bitte GAEB DA XML (.x83) anfordern oder als CSV übergeben.")
    if art != "xml":
        raise GaebNichtUnterstuetzt("Keine GAEB-Datei erkannt (erwartet GAEB DA XML, z. B. .x83). CSV geht über den Tabellenimport.")
    try:
        wurzel = etree.fromstring(inhalt)
    except etree.XMLSyntaxError as exc:
        raise GaebNichtUnterstuetzt(f"Die GAEB-Datei ist kein gültiges XML: {str(exc)[:120]}")
    if _ln(wurzel) != "GAEB":
        raise GaebNichtUnterstuetzt("Wurzelelement ist nicht <GAEB>.")
    ns = etree.QName(wurzel).namespace or ""
    m = re.search(r"DA(\d\d)/([\d.]+)", ns)
    phase, version = (m.group(1), m.group(2)) if m else ("", "")
    award = _kind(wurzel, "Award")
    boq = _kind(award, "BoQ") if award is not None else _kind(wurzel, "BoQ")
    if boq is None:
        raise GaebNichtUnterstuetzt("Die Datei enthält kein Leistungsverzeichnis (<BoQ>).")
    body = _kind(boq, "BoQBody")
    positionen: list[dict] = []
    hinweise: list[str] = []
    uebersprungen = {"n": 0}

    def ebene(body_el, pfad: list[str], tiefe: int) -> None:
        if body_el is None:
            return
        for k in body_el:
            name = _ln(k)
            if name == "BoQCtgy":
                nr = (k.get("RNoPart") or k.get("RNoIndex") or "").strip()
                titel = _text(_kind(k, "LblTx")) or f"Titel {nr}"
                neu = pfad + ([nr] if nr else [])
                positionen.append({"nr": ".".join(neu) if neu else "", "leistung": titel[:300], "beschreibung": "", "menge": 0.0, "einheit": "", "art": "titel", "ebene": tiefe})
                ebene(_kind(k, "BoQBody"), neu, tiefe + 1)
            elif name == "Itemlist":
                for it in k:
                    if _ln(it) != "Item":
                        uebersprungen["n"] += 1
                        continue
                    nr = (it.get("RNoPart") or it.get("RNoIndex") or "").strip()
                    oz = ".".join(pfad + ([nr] if nr else []))
                    desc = _kind(it, "Description")
                    komplett = _kind(desc, "CompleteText") if desc is not None else None
                    kurz = _text(_kind(komplett, "OutlineText")) if komplett is not None else ""
                    lang = _text(_kind(komplett, "DetailTxt")) if komplett is not None else ""
                    if not kurz and lang:
                        kurz, lang = lang.split("\n")[0][:300], lang
                    if not kurz and desc is not None:
                        kurz = _text(desc)
                    p = {"nr": oz or f"{len(positionen) + 1}", "leistung": (kurz or "Position")[:300], "beschreibung": lang[:4000] if lang != kurz else "",
                         "menge": _zahl((_kind(it, "Qty").text if _kind(it, "Qty") is not None else None)) or 0.0,
                         "einheit": ((_kind(it, "QU").text or "") if _kind(it, "QU") is not None else "").strip()[:20] or "Stück", "art": "leistung", "ebene": tiefe}
                    up = _kind(it, "UP")
                    if up is not None and _zahl(up.text) is not None:
                        p["einzelpreis"] = _zahl(up.text)
                    for kz, feld in (("Provis", "eventual"), ("ALNGroupNo", "alternativ")):
                        if _kind(it, kz) is not None:
                            p[feld] = True
                    positionen.append(p)
            elif name in ("Remark", "MarkupList", "Precon", "Hint"):
                uebersprungen["n"] += 1
            elif name == "BoQBody":
                ebene(k, pfad, tiefe)

    ebene(body, [], 0)
    if not any(p["art"] == "leistung" for p in positionen):
        raise GaebNichtUnterstuetzt("Das Leistungsverzeichnis enthält keine Positionen (<Item>).")
    if uebersprungen["n"]:
        hinweise.append(f"{uebersprungen['n']} Element(e) wurden übersprungen (Hinweise, Vorbemerkungen, Zuschläge sind nicht umgesetzt).")
    gesehen, doppelt = set(), 0
    for p in positionen:
        if p["art"] == "leistung":
            if p["nr"] in gesehen:
                doppelt += 1
            gesehen.add(p["nr"])
    if doppelt:
        hinweise.append(f"{doppelt} Ordnungszahl(en) kommen mehrfach vor – bitte prüfen.")
    prj = _kind(wurzel, "PrjInfo")
    titel = _text(_kind(prj, "NamePrj")) if prj is not None else ""
    return {"positionen": positionen, "hinweise": hinweise, "phase": phase, "version": version, "projekt": titel, "quelle": "gaeb"}


# ---------------------------------------------------------------- Schreiben

def _rnopart(nr: str, fallback: int) -> str:
    teil = re.sub(r"[^0-9]", "", nr or "")
    return teil if teil else f"{fallback * 10:04d}"


def _baum(positionen: list[dict]) -> dict:
    """Gliederungsbaum aus Ordnungszahlen: „01.02.0010“ → Titel 01 → Titel 02 → Position 0010. Titelzeilen liefern die Beschriftung
    ihres Pfads; Positionen ohne Punkt in der Nummer hängen am zuletzt gesehenen Titel, ohne Titel an der Wurzel."""
    wurzel = {"label": "", "kinder": {}, "items": []}
    aktueller_pfad: list[str] = []

    def knoten(pfad: list[str]) -> dict:
        k = wurzel
        for teil in pfad:
            k = k["kinder"].setdefault(teil, {"label": "", "kinder": {}, "items": []})
        return k

    for p in positionen:
        art = p.get("art") or "leistung"
        nr = str(p.get("nr") or "").strip()
        if art == "text":
            continue
        if art == "titel":
            aktueller_pfad = [t for t in nr.split(".") if t] if nr else aktueller_pfad + [str(len(knoten(aktueller_pfad)["kinder"]) + 1)]
            knoten(aktueller_pfad)["label"] = p.get("leistung") or p.get("text") or ""
            continue
        teile = [t for t in nr.split(".") if t]
        if len(teile) > 1:
            knoten(teile[:-1])["items"].append((teile[-1], p))
        else:
            knoten(aktueller_pfad)["items"].append((teile[0] if teile else "", p))
    return wurzel


def schreiben(positionen: list[dict], phase: str = "83", info: Optional[dict] = None) -> bytes:
    """GAEB DA XML erzeugen. phase 83: LV ohne Preise; 84: Angebot mit Einheitspreisen (Preise aus p['einzelpreis'])."""
    info = info or {}
    ns = GAEB_NS.format(phase=phase, version=VERSION)
    E = lambda parent, tag, text=None, **attr: _el(parent, f"{{{ns}}}{tag}", text, **attr)  # noqa: E731
    root = etree.Element(f"{{{ns}}}GAEB", nsmap={None: ns})
    gi = E(root, "GAEBInfo")
    E(gi, "Version", VERSION)
    E(gi, "VersDate", "2013-10")
    E(gi, "Date", date.today().isoformat())
    E(gi, "Time", datetime.now().strftime("%H:%M:%S"))
    E(gi, "ProgSystem", "Stundenzettel Pro")
    E(gi, "ProgName", "Stundenzettel Pro")
    pi = E(root, "PrjInfo")
    E(pi, "NamePrj", (info.get("projekt") or info.get("titel") or "Leistungsverzeichnis")[:60])
    E(pi, "LblPrj", (info.get("titel") or info.get("projekt") or "Leistungsverzeichnis")[:100])
    award = E(root, "Award")
    E(award, "DP", phase)
    ai = E(award, "AwardInfo")
    E(ai, "Cur", "EUR")
    E(ai, "CurLbl", "Euro")
    if info.get("auftraggeber"):
        own = E(award, "OWN")
        adr = E(own, "Address")
        E(adr, "Name1", str(info["auftraggeber"])[:40])
    if phase == "84" and info.get("bieter"):
        ctr = E(award, "CTR")
        adr = E(ctr, "Address")
        E(adr, "Name1", str(info["bieter"])[:40])
    boq = E(award, "BoQ")
    bi = E(boq, "BoQInfo")
    E(bi, "Name", (info.get("titel") or "LV")[:40])
    E(bi, "LblBoQ", (info.get("titel") or "Leistungsverzeichnis")[:100])
    E(bi, "Date", date.today().isoformat())
    for typ, laenge in (("BoQLevel", 2), ("Item", 4)):
        bk = E(bi, "BoQBkdn")
        E(bk, "Type", typ)
        E(bk, "Length", str(laenge))
        E(bk, "Num", "Yes")
    body = E(boq, "BoQBody")
    gesamt = [0.0]

    def item_schreiben(il, teil: str, i: int, p: dict) -> None:
        it = E(il, "Item", RNoPart=_rnopart(teil, i).rjust(4, "0")[-4:])
        menge = float(p.get("menge") or 0)
        E(it, "Qty", f"{menge:.3f}")
        E(it, "QU", (p.get("einheit") or "Stück")[:4])
        desc = E(it, "Description")
        ct = E(desc, "CompleteText")
        dt = E(ct, "DetailTxt")
        tx = E(dt, "Text")
        for absatz in ((p.get("beschreibung") or p.get("leistung") or p.get("text") or "").split("\n") or [""]):
            E(tx, "p", absatz[:1000])
        ot = E(ct, "OutlineText")
        o = E(ot, "OutlTxt")
        E(o, "TextOutlTxt", (p.get("leistung") or p.get("text") or "")[:70])
        if phase == "84":
            ep = float(p.get("einzelpreis") or 0)
            E(it, "UP", f"{ep:.2f}")
            E(it, "IT", f"{menge * ep:.2f}")
            gesamt[0] += menge * ep

    def knoten_schreiben(parent_body, knoten: dict) -> None:
        for idx, (schluessel, kind) in enumerate(knoten["kinder"].items(), start=1):
            ctg = E(parent_body, "BoQCtgy", RNoPart=_rnopart(schluessel, idx).rjust(2, "0")[-2:])
            lbl = E(ctg, "LblTx")
            E(lbl, "p", (kind["label"] or f"Titel {schluessel}")[:100])
            knoten_schreiben(E(ctg, "BoQBody"), kind)
        if knoten["items"]:
            il = E(parent_body, "Itemlist")
            for i, (teil, p) in enumerate(knoten["items"], start=1):
                item_schreiben(il, teil, i, p)

    knoten_schreiben(body, _baum(positionen))
    if phase == "84":
        tot = E(boq, "Totals")
        E(tot, "Total", f"{gesamt[0]:.2f}")
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)


def _el(parent, tag, text=None, **attrs):
    el = etree.SubElement(parent, tag, **{k: str(v) for k, v in attrs.items()})
    if text is not None:
        el.text = str(text)
    return el
