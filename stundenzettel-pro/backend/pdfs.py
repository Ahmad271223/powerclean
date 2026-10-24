"""Serverseitige PDFs (reportlab, eingebettete Schrift): Stundennachweis je Projekt und Monat, Nachtrag, Abnahmeprotokoll, Bautagesbericht.
Alle Funktionen sind reine Funktionen über Dictionaries, damit Routen und die ZIP-Projektakte dieselben Dokumente erzeugen."""
from __future__ import annotations

import io
from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from pdfbasis import SCHRIFT, SCHRIFT_FETT, schrift_registrieren

MONATE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"]
GRAU = colors.HexColor("#DDDDDD")


def esc(t) -> str:
    return (str(t) if t not in (None, "") else "–").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")


def de(iso) -> str:
    try:
        return date.fromisoformat(str(iso)[:10]).strftime("%d.%m.%Y")
    except ValueError:
        return str(iso or "–")


def zeit(iso) -> str:
    """ISO-Zeitstempel als dd.mm.yyyy hh:mm (ohne Zeitzonenumrechnung – es ist die gespeicherte Serverzeit)."""
    if not iso:
        return "–"
    s = str(iso)
    return f"{de(s)} {s[11:16]}" if len(s) >= 16 else de(s)


def geld(x) -> str:
    try:
        return f"{float(x or 0):,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "–"


def _stile() -> dict:
    schrift_registrieren()
    return {"h1": ParagraphStyle("h1", fontName=SCHRIFT_FETT, fontSize=15, leading=19),
            "h2": ParagraphStyle("h2", fontName=SCHRIFT_FETT, fontSize=10, leading=13, spaceBefore=6),
            "n": ParagraphStyle("n", fontName=SCHRIFT, fontSize=9.5, leading=13),
            "k": ParagraphStyle("k", fontName=SCHRIFT, fontSize=8, leading=10, textColor=colors.HexColor("#666666")),
            "z": ParagraphStyle("z", fontName=SCHRIFT, fontSize=8.5, leading=11)}


def _doc(buf, titel: str, autor: str) -> SimpleDocTemplate:
    return SimpleDocTemplate(buf, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
                             title=titel, author=autor or "", creator="Stundenzettel Pro")


def _tabelle(zeilen: list[list], breiten: list, kopf: bool = True) -> Table:
    t = Table(zeilen, colWidths=breiten, repeatRows=1 if kopf else 0)
    stil = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.25, GRAU), ("FONTNAME", (0, 0), (-1, -1), SCHRIFT), ("FONTSIZE", (0, 0), (-1, -1), 8.5)]
    if kopf:
        stil += [("FONTNAME", (0, 0), (-1, 0), SCHRIFT_FETT), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F5F5F7"))]
    t.setStyle(TableStyle(stil))
    return t


def _parteien(st: dict, auftraggeber: dict, auftragnehmer: dict) -> Table:
    def block(f: dict) -> str:
        zeilen = [f.get("name") or "–", f.get("street") or "", f"{f.get('zip_code') or ''} {f.get('city') or ''}".strip(), f.get("email") or ""]
        return "<br/>".join(esc(z) for z in zeilen if z)
    t = Table([[Paragraph("Auftraggeber", st["h2"]), Paragraph("Auftragnehmer", st["h2"])], [Paragraph(block(auftraggeber), st["n"]), Paragraph(block(auftragnehmer), st["n"])]],
              colWidths=[85 * mm, 85 * mm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return t


def _unterschriften(st: dict, links: str, rechts: str) -> list:
    return [Spacer(1, 14 * mm), Table([[Paragraph("______________________________<br/>" + esc(links), st["k"]), Paragraph("______________________________<br/>" + esc(rechts), st["k"])]],
                                      colWidths=[85 * mm, 85 * mm])]


# ---------------------------------------------------------------- Stundennachweis je Projekt und Monat

def zeiten_pdf(firma: dict, projekt: dict, jahr: int, monat: int, eintraege: list[dict], namen: dict, unterschriften: list[dict] | None = None) -> bytes:
    st = _stile()
    buf = io.BytesIO()
    doc = _doc(buf, f"Stundennachweis {MONATE[monat - 1]} {jahr} – {projekt.get('name')}", firma.get("name") or "")
    teile = [Paragraph(f"Stundennachweis {MONATE[monat - 1]} {jahr}", st["h1"]),
             Paragraph(f"{esc(projekt.get('name'))}{' · ' + esc(projekt.get('address')) if projekt.get('address') else ''}{' · Auftraggeber: ' + esc(projekt.get('customer_name')) if projekt.get('customer_name') else ''}", st["n"]),
             Paragraph(f"{esc(firma.get('name'))} · erstellt aus den Zeiteinträgen (Quelle: Stempeluhr oder manuell)", st["k"]), Spacer(1, 4 * mm)]
    zeilen = [["Datum", "Mitarbeiter", "Beginn", "Ende", "Pause", "Anz.", "Netto", "Tätigkeit / Leistung"]]
    gesamt = 0
    for e in sorted(eintraege, key=lambda x: (x.get("date") or "", x.get("start_time") or "")):
        netto = int(e.get("net_minutes") or 0)
        anzahl = max(1, int(e.get("workers") or 1))
        gesamt += netto * anzahl
        text = " · ".join(t for t in [e.get("service_name") or "", e.get("activity") or ""] if t)
        if e.get("pruefen"):
            text = (text + " · " if text else "") + "⚠ zu prüfen"
        zeilen.append([de(e.get("date")), Paragraph(esc(namen.get(e.get("user_id") or "", "") or "–"), st["z"]), e.get("start_time") or "", e.get("end_time") or "",
                       f"{int(e.get('pause_minutes') or 0)} min", str(anzahl), f"{netto // 60}:{netto % 60:02d}", Paragraph(esc(text) if text else "", st["z"])])
    zeilen.append(["Summe", "", "", "", "", "", f"{gesamt // 60}:{gesamt % 60:02d}", Paragraph(f"{gesamt / 60:.2f} Mitarbeiterstunden".replace(".", ","), st["z"])])
    teile.append(_tabelle(zeilen, [20 * mm, 38 * mm, 14 * mm, 14 * mm, 14 * mm, 10 * mm, 14 * mm, 54 * mm]))
    if unterschriften:
        teile += [Spacer(1, 4 * mm), Paragraph("Unterschriften des Kunden (Wochen)", st["h2"])]
        for u in unterschriften:
            teile.append(Paragraph(f"Woche ab {de(u.get('week_monday'))}: {esc(u.get('signer_name'))} am {zeit(u.get('signed_at'))}{' (Version ' + str(u.get('version')) + ')' if u.get('version') and int(u.get('version')) > 1 else ''}", st["n"]))
    teile += [Spacer(1, 6 * mm), Paragraph("Erstellt mit Stundenzettel Pro. Änderungen an Einträgen stehen im Sicherheitsprotokoll der Firma.", st["k"])]
    doc.build(teile)
    return buf.getvalue()


# ---------------------------------------------------------------- Nachtrag

def nachtrag_pdf(n: dict, projekt: dict, auftraggeber: dict, auftragnehmer: dict, status_name: str) -> bytes:
    st = _stile()
    buf = io.BytesIO()
    doc = _doc(buf, f"Nachtrag {n.get('nummer')} – {projekt.get('name')}", auftraggeber.get("name") or "")
    teile = [Paragraph(f"Nachtrag {esc(n.get('nummer'))}: {esc(n.get('titel'))}", st["h1"]),
             Paragraph(f"Projekt: {esc(projekt.get('name'))}{' · ' + esc(projekt.get('address')) if projekt.get('address') else ''}{' · Gewerk ' + esc(n.get('gewerk')) if n.get('gewerk') else ''}", st["n"]),
             Paragraph(f"Status: {esc(status_name)} · angelegt am {zeit(n.get('created_at'))}", st["k"]), Spacer(1, 4 * mm), _parteien(st, auftraggeber, auftragnehmer), Spacer(1, 4 * mm),
             Paragraph("Zusätzliche Leistung", st["h2"]), Paragraph(esc(n.get("beschreibung")), st["n"])]
    if n.get("grund"):
        teile += [Paragraph("Anlass / Begründung", st["h2"]), Paragraph(esc(n.get("grund")), st["n"])]
    freigegeben = n.get("status") == "freigegeben"
    vorher = n.get("auftragswert_vorher")
    nachher = n.get("auftragswert_nachher")
    zeilen = [["Ursprünglicher Auftragswert (netto)", geld(vorher) if vorher is not None else "–"],
              ["Nachtrag (netto)", geld(n.get("betrag_netto"))],
              ["Neuer Auftragswert nach Zustimmung (netto)", geld(nachher) if freigegeben and nachher is not None else "erst nach Freigabe"]]
    teile += [Spacer(1, 3 * mm), _tabelle([[Paragraph(a, st["n"]), Paragraph(b, st["n"])] for a, b in zeilen], [110 * mm, 60 * mm], kopf=False)]
    teile += [Paragraph("Vor einer Freigabe bleibt der ursprüngliche Auftragswert unverändert.", st["k"]), Paragraph("Verlauf", st["h2"])]
    for v in n.get("verlauf") or []:
        teile.append(Paragraph(f"{zeit(v.get('at'))} · {esc(v.get('status'))} · {esc(v.get('user_name'))} ({esc(v.get('firma_name'))}){' · „' + esc(v.get('kommentar')) + '“' if v.get('kommentar') else ''}", st["n"]))
    if freigegeben:
        teile.append(Paragraph(f"Freigegeben von {esc((n.get('entschieden_von') or {}).get('name'))} am {zeit(n.get('entschieden_at'))}.", st["n"]))
    elif n.get("status") == "abgelehnt":
        teile.append(Paragraph(f"Abgelehnt von {esc((n.get('entschieden_von') or {}).get('name'))} am {zeit(n.get('entschieden_at'))}{': ' + esc(n.get('entscheidung_begruendung')) if n.get('entscheidung_begruendung') else ''}.", st["n"]))
    teile += _unterschriften(st, f"Auftraggeber · {auftraggeber.get('name') or ''}", f"Auftragnehmer · {auftragnehmer.get('name') or ''}")
    teile += [Spacer(1, 4 * mm), Paragraph("Erstellt mit Stundenzettel Pro. Die digitale Freigabe ist mit Name und Zeitstempel protokolliert.", st["k"])]
    doc.build(teile)
    return buf.getvalue()


# ---------------------------------------------------------------- Abnahmeprotokoll

def abnahme_pdf(a: dict, projekt: dict, auftraggeber: dict, auftragnehmer: dict, art_name: str, ergebnis_name: str, status_name: str) -> bytes:
    st = _stile()
    buf = io.BytesIO()
    doc = _doc(buf, f"Abnahmeprotokoll {a.get('nummer')} – {projekt.get('name')}", auftraggeber.get("name") or "")
    teile = [Paragraph(f"Abnahmeprotokoll {esc(a.get('nummer'))} – {esc(art_name)}", st["h1"]),
             Paragraph(f"Projekt: {esc(projekt.get('name'))}{' · ' + esc(projekt.get('address')) if projekt.get('address') else ''}", st["n"]),
             Paragraph(f"Status: {esc(status_name)}", st["k"]), Spacer(1, 4 * mm), _parteien(st, auftraggeber, auftragnehmer), Spacer(1, 4 * mm)]
    kopf = [["Datum der Abnahme", de(a.get("datum"))], ["Gewerk / Bereich", " · ".join(t for t in [a.get("gewerk") or "", a.get("bereich") or ""] if t) or "–"],
            ["Teilnehmer", a.get("teilnehmer") or "–"], ["Ergebnis", ergebnis_name or "–"], ["Vorbehalte / Bemerkungen", a.get("vorbehalte") or "–"],
            ["Nachbesserung bis", de(a.get("nachbesserung_bis")) if a.get("nachbesserung_bis") else "–"]]
    teile.append(_tabelle([[Paragraph(k, st["h2"]), Paragraph(esc(v), st["n"])] for k, v in kopf], [50 * mm, 120 * mm], kopf=False))
    maengel = a.get("maengel") or []
    teile.append(Paragraph(f"Festgestellte Mängel ({len(maengel)})", st["h2"]))
    if maengel:
        zeilen = [["Nr.", "Beschreibung", "Ort", "Status", "Frist"]]
        for i, m in enumerate(maengel, 1):
            zeilen.append([str(i), Paragraph(esc(m.get("beschreibung")), st["z"]), Paragraph(esc(m.get("bereich") or ""), st["z"]), esc(m.get("status_name") or m.get("status")), de(m.get("frist")) if m.get("frist") else "–"])
        teile.append(_tabelle(zeilen, [10 * mm, 80 * mm, 30 * mm, 30 * mm, 20 * mm]))
    else:
        teile.append(Paragraph("Keine offenen Mängel vermerkt.", st["n"]))
    antwort = a.get("antwort") or {}
    teile.append(Paragraph("Stellungnahme des Auftragnehmers", st["h2"]))
    if a.get("status") in ("bestaetigt", "widersprochen"):
        teile.append(Paragraph(f"{'Bestätigt' if a.get('status') == 'bestaetigt' else 'Widersprochen'} von {esc(antwort.get('user_name'))} am {zeit(antwort.get('at'))}{': ' + esc(antwort.get('kommentar')) if antwort.get('kommentar') else ''}.", st["n"]))
    else:
        teile.append(Paragraph("Noch keine Stellungnahme.", st["n"]))
    teile.append(Paragraph("Verlauf", st["h2"]))
    for v in a.get("verlauf") or []:
        teile.append(Paragraph(f"{zeit(v.get('at'))} · {esc(v.get('status'))} · {esc(v.get('user_name'))} ({esc(v.get('firma_name'))}){' · „' + esc(v.get('kommentar')) + '“' if v.get('kommentar') else ''}", st["n"]))
    teile += _unterschriften(st, f"Auftraggeber · {auftraggeber.get('name') or ''}", f"Auftragnehmer · {auftragnehmer.get('name') or ''}")
    teile += [Spacer(1, 4 * mm), Paragraph("Erstellt mit Stundenzettel Pro. Eine Abnahme unter Vorbehalt dokumentiert die offenen Mängel mit Frist.", st["k"])]
    doc.build(teile)
    return buf.getvalue()


# ---------------------------------------------------------------- Bautagesbericht

def tagesbericht_pdf(b: dict, projekt: dict, fotos: list[tuple[bytes, str]]) -> bytes:
    """Bautagesbericht (A4, bis zu sechs Fotos als JPEG-Bytes mit Notiz)."""
    st = _stile()
    buf = io.BytesIO()
    doc = _doc(buf, f"Bautagesbericht {b.get('datum')} – {projekt.get('name')}", b.get("firma_name") or "")
    teile = [Paragraph(f"Bautagesbericht {esc(b.get('datum'))}", st["h1"]), Paragraph(f"{esc(projekt.get('name'))}{' · ' + esc(projekt.get('address')) if projekt.get('address') else ''}", st["n"]),
             Paragraph(f"Verfasser: {esc(b.get('verfasser'))} ({esc(b.get('firma_name'))}) · Status: {esc(b.get('status_name'))}{' · Bauabschnitt ' + esc(b.get('bereich')) if b.get('bereich') else ''}{' · Wetter: ' + esc(b.get('wetter')) if b.get('wetter') else ''}", st["k"]), Spacer(1, 4 * mm)]
    kopf = [["Beteiligte Firmen", esc(", ".join(b.get("firmen") or []))], ["Mitarbeiter vor Ort", str(b.get("mitarbeiter_anzahl") or 0)], ["Fortschritt", esc(b.get("fortschritt"))]]
    t = Table([[Paragraph(k, st["h2"]), Paragraph(v, st["n"])] for k, v in kopf], colWidths=[45 * mm, 125 * mm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.25, GRAU)]))
    teile.append(t)
    for titel, feld in (("Tätigkeiten", "taetigkeiten"), ("Lieferungen", "lieferungen"), ("Behinderungen", "behinderungen"), ("Mängel", "maengel"),
                        ("Besondere Vorkommnisse", "besondere_vorkommnisse"), ("Notizen", "notizen")):
        if b.get(feld):
            teile += [Paragraph(titel, st["h2"]), Paragraph(esc(b[feld]), st["n"])]
    if fotos:
        teile.append(Paragraph("Fotos", st["h2"]))
        zellen = []
        for daten, note in fotos[:6]:
            try:
                bild = ImageReader(io.BytesIO(daten))
                bw, bh = bild.getSize()
                w = 82 * mm
                h = w * bh / bw
                if h > 60 * mm:
                    h, w = 60 * mm, 60 * mm * bw / bh
                zellen.append([Image(io.BytesIO(daten), width=w, height=h), Paragraph(esc(note or ""), st["k"])])
            except Exception:  # noqa: BLE001 – defektes Bild auslassen
                continue
        for zeile in [zellen[i:i + 2] for i in range(0, len(zellen), 2)]:
            while len(zeile) < 2:
                zeile.append("")
            teile.append(Table([[z_[0] if z_ else "" for z_ in zeile], [z_[1] if z_ else "" for z_ in zeile]], colWidths=[88 * mm, 88 * mm]))
    teile += [Spacer(1, 8 * mm), Paragraph("Erstellt mit Stundenzettel Pro · Freigabe: " + ("erteilt" if b.get("status") == "freigegeben" else "offen"), st["k"])]
    doc.build(teile)
    return buf.getvalue()


# ---------------------------------------------------------------- Projekt-Stundenzettel aus freigegebenen Zeiten (Plantafel)

def freigegebene_zeiten_pdf(firma: dict, projekt: dict, von: str, bis: str, einsaetze: list[dict], offen: int, namen: dict) -> bytes:
    """Nur ausdrücklich freigegebene Einsatzzeiten; ungeprüfte Einsätze werden oben als fehlend genannt."""
    st = _stile()
    buf = io.BytesIO()
    doc = _doc(buf, f"Projekt-Stundenzettel {projekt.get('name')} {von}–{bis}", firma.get("name") or "")
    teile = [Paragraph("Projekt-Stundenzettel – freigegebene Arbeitszeiten", st["h1"]),
             Paragraph(f"{esc(projekt.get('name'))}{' · ' + esc(projekt.get('address')) if projekt.get('address') else ''} · Zeitraum {de(von)} bis {de(bis)}", st["n"]),
             Paragraph(f"{esc(firma.get('name'))} · Nur vom Betrieb geprüfte und freigegebene Zeiten – nicht identisch mit den ursprünglichen Stempelungen, die gesondert erhalten bleiben.", st["k"]), Spacer(1, 4 * mm)]
    if offen:
        teile += [Paragraph(f"Hinweis: {offen} Einsätze im Zeitraum sind noch nicht geprüft und fehlen in diesem Nachweis.", st["n"]), Spacer(1, 2 * mm)]
    zeilen = [["Datum", "Mitarbeiter", "Beginn", "Ende", "Pause", "Netto", "Freigegeben von", "Vermerk"]]
    gesamt = 0
    for e in einsaetze:
        f = e.get("freigabe") or {}
        netto = int(f.get("net_minutes") or 0)
        gesamt += netto
        vermerk = ("Stempelung korrigiert" if f.get("abweichung") and f.get("hat_stempel") else "ohne Stempelung bestätigt" if not f.get("hat_stempel") else "")
        zeilen.append([de(e.get("date")), Paragraph(esc(namen.get(e.get("user_id"), "")), st["z"]), f.get("start_time", ""), f.get("end_time", ""), f"{int(f.get('pause_minutes') or 0)} min",
                       f"{netto // 60}:{netto % 60:02d}", Paragraph(esc(f.get("von_name")), st["z"]), Paragraph(esc(vermerk), st["z"])])
    zeilen.append(["Summe", "", "", "", "", f"{gesamt // 60}:{gesamt % 60:02d}", "", Paragraph(f"{gesamt / 60:.2f} Stunden".replace(".", ","), st["z"])])
    teile.append(_tabelle(zeilen, [20 * mm, 36 * mm, 14 * mm, 14 * mm, 14 * mm, 14 * mm, 32 * mm, 34 * mm]))
    teile += [Spacer(1, 6 * mm), Paragraph("Grundlage: Freigaben in der Plantafel mit Name, Zeitstempel und Begründung (Sicherheitsprotokoll). Erstellt mit Stundenzettel Pro.", st["k"])]
    doc.build(teile)
    return buf.getvalue()
