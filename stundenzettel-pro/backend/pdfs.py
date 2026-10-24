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


# ---------------------------------------------------------------- Kundenangebot (Stufe C)

def _bild_flowable(data_url: str, max_w: float, max_h: float):
    """Logo/Stempel aus einer Data-URL als platypus-Bild, proportional in den Rahmen eingepasst."""
    import base64
    try:
        if not data_url or not str(data_url).startswith("data:image"):
            return None
        roh = base64.b64decode(str(data_url).split(",", 1)[1])
        leser = ImageReader(io.BytesIO(roh))
        bw, bh = leser.getSize()
        faktor = min(max_w / bw, max_h / bh)
        return Image(io.BytesIO(roh), width=bw * faktor, height=bh * faktor)
    except Exception:  # noqa: BLE001 – ein kaputtes Bild darf das Angebot nicht verhindern
        return None


def _menge(x) -> str:
    try:
        v = float(x or 0)
    except (TypeError, ValueError):
        return "–"
    s = f"{v:,.2f}" if v != int(v) else f"{int(v):,}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def angebot_pdf(daten: dict) -> bytes:
    """Angebot an den Kunden: Briefkopf mit Logo, Anschrift, Angebotsdaten, gegliederte Positionen (Titel, Alternativ-/Eventualpositionen
    ausgewiesen, aber nicht summiert), Summenblock, Zahlungsbedingungen, Gültigkeit, Unterschrift/Stempel und Annahmefeld für den Kunden."""
    st = _stile()
    f = daten.get("firma") or {}
    k = daten.get("kunde") or {}
    s = daten.get("summen") or {}
    grau = colors.HexColor("#6E6E73")
    st_t = ParagraphStyle("t", parent=st["n"], fontName=SCHRIFT_FETT)
    st_klein = ParagraphStyle("kl", parent=st["k"], textColor=grau)
    st_r = ParagraphStyle("r", parent=st["z"], alignment=2)
    st_rf = ParagraphStyle("rf", parent=st_r, fontName=SCHRIFT_FETT)
    st_grau_r = ParagraphStyle("gr", parent=st_r, textColor=grau)
    version = int(daten.get("version") or 1)
    nummer = f"{daten.get('nummer') or ''}" + (f" (Version {version})" if version > 1 else "")

    def fuss(c, doc):
        c.saveState()
        c.setStrokeColor(GRAU)
        c.setLineWidth(0.3)
        c.line(16 * mm, 14 * mm, A4[0] - 16 * mm, 14 * mm)
        c.setFont(SCHRIFT, 7)
        c.setFillColor(grau)
        zeile1 = " · ".join(t for t in [f.get("name"), ", ".join(t for t in [f.get("street"), f"{f.get('zip_code') or ''} {f.get('city') or ''}".strip()] if t), f.get("phone"), f.get("email")] if t)
        zeile2 = " · ".join(t for t in [f"Bank {f['bank_name']}" if f.get("bank_name") else "", f"IBAN {f['iban']}" if f.get("iban") else "", f"BIC {f['bic']}" if f.get("bic") else "",
                                        f"St.-Nr. {f['tax_number']}" if f.get("tax_number") else "", f"USt-IdNr. {f['vat_id']}" if f.get("vat_id") else ""] if t)
        c.drawString(16 * mm, 10 * mm, zeile1[:170])
        c.drawString(16 * mm, 6.5 * mm, zeile2[:170])
        c.drawRightString(A4[0] - 16 * mm, 10 * mm, f"Angebot {daten.get('nummer') or ''} · Seite {doc.page}")
        c.restoreState()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=16 * mm, bottomMargin=20 * mm,
                            title=f"Angebot {nummer}", author=f.get("name") or "", creator="Stundenzettel Pro")
    story = []
    # Briefkopf: Firma links, Logo rechts
    logo = _bild_flowable(daten.get("logo"), 45 * mm, 20 * mm)
    kopf_links = Paragraph(f"<b>{esc(f.get('name'))}</b><br/>{esc(f.get('street'))}<br/>{esc((f.get('zip_code') or '') + ' ' + (f.get('city') or ''))}" +
                           (f"<br/>{esc(f.get('phone'))}" if f.get("phone") else "") + (f"<br/>{esc(f.get('email'))}" if f.get("email") else ""), st["n"])
    kopf = Table([[kopf_links, logo or ""]], colWidths=[120 * mm, 58 * mm])
    kopf.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (1, 0), (1, 0), "RIGHT")]))
    story += [kopf, Spacer(1, 8 * mm)]
    # Empfänger links, Angebotsdaten rechts
    absender = " · ".join(t for t in [f.get("name"), f.get("street"), f"{f.get('zip_code') or ''} {f.get('city') or ''}".strip()] if t)
    empf = [k.get("name"), k.get("contact"), k.get("street"), f"{k.get('zip_code') or ''} {k.get('city') or ''}".strip()]
    empf_p = Paragraph(f"<font size=7 color='#6E6E73'>{esc(absender)[:120]}</font><br/><br/>" + "<br/>".join(esc(z) for z in empf if z), st["n"])
    meta = [["Angebotsnummer", nummer], ["Datum", de(daten.get("datum"))], ["Gültig bis", de(daten.get("gueltig_bis")) if daten.get("gueltig_bis") else "auf Widerruf"]]
    if k.get("customer_number"):
        meta.append(["Kundennummer", k["customer_number"]])
    if daten.get("projekt"):
        meta.append(["Projekt / Objekt", daten["projekt"]])
    if f.get("owner"):
        meta.append(["Ansprechpartner", f["owner"]])
    meta_t = Table([[Paragraph(esc(a), st_klein), Paragraph(esc(b), st["z"])] for a, b in meta], colWidths=[30 * mm, 48 * mm])
    meta_t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5), ("TOPPADDING", (0, 0), (-1, -1), 1.5)]))
    block = Table([[empf_p, meta_t]], colWidths=[100 * mm, 78 * mm])
    block.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story += [block, Spacer(1, 8 * mm)]
    story.append(Paragraph(f"Angebot {esc(nummer)}" + (f" – {esc(daten.get('titel'))}" if daten.get("titel") else ""), st["h1"]))
    story.append(Spacer(1, 3 * mm))
    anrede = f"Sehr geehrte Damen und Herren," if not k.get("contact") else f"Guten Tag {esc(k.get('contact'))},"
    story.append(Paragraph(anrede, st["n"]))
    if daten.get("einleitung"):
        story.append(Paragraph(esc(daten["einleitung"]), st["n"]))
    story.append(Spacer(1, 4 * mm))
    # Positionen
    zeilen = [[Paragraph("Pos.", st_t), Paragraph("Leistung", st_t), Paragraph("Menge", ParagraphStyle("mt", parent=st_t, alignment=2)), Paragraph("Einheit", st_t),
               Paragraph("Einzelpreis", ParagraphStyle("et", parent=st_t, alignment=2)), Paragraph("Gesamt", ParagraphStyle("gt", parent=st_t, alignment=2))]]
    stil = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.25, GRAU), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F5F5F7")),
            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    for p in daten.get("positionen") or []:
        art = p.get("art") or "leistung"
        i = len(zeilen)
        if art == "titel":
            zeilen.append([Paragraph(esc(p.get("nr")), st_t), Paragraph(f"<b>{esc(p.get('text'))}</b>", st["n"]), "", "", "", ""])
            stil += [("SPAN", (1, i), (-1, i)), ("BACKGROUND", (0, i), (-1, i), colors.HexColor("#FAFAFA"))]
            continue
        if art == "text":
            zeilen.append(["", Paragraph(esc(p.get("text")) + (f"<br/><font size=7.5 color='#6E6E73'>{esc(p.get('beschreibung'))}</font>" if p.get("beschreibung") else ""), st["z"]), "", "", "", ""])
            stil += [("SPAN", (1, i), (-1, i))]
            continue
        kennz = "Alternativposition – nicht in der Summe" if p.get("alternativ") else "Eventualposition – nur bei Bedarf, nicht in der Summe" if p.get("eventual") else ""
        text = f"<b>{esc(p.get('text'))}</b>" + (f"<br/><font size=7.5 color='#6E6E73'>{esc(p.get('beschreibung'))}</font>" if p.get("beschreibung") else "") + \
               (f"<br/><font size=7.5 color='#B25E00'>{kennz}</font>" if kennz else "") + \
               (f"<br/><font size=7.5 color='#6E6E73'>abzüglich {_menge(p.get('rabatt_prozent'))} % Nachlass</font>" if float(p.get("rabatt_prozent") or 0) else "")
        st_g = st_grau_r if kennz else st_r
        zeilen.append([Paragraph(esc(p.get("nr")), st["z"]), Paragraph(text, st["z"]), Paragraph(_menge(p.get("menge")), st_r), Paragraph(esc(p.get("einheit")), st["z"]),
                       Paragraph(geld(p.get("einzelpreis")), st_r), Paragraph(geld(p.get("gesamt")), st_g)])
    t = Table(zeilen, colWidths=[13 * mm, 91 * mm, 17 * mm, 15 * mm, 21 * mm, 21 * mm], repeatRows=1)
    t.setStyle(TableStyle(stil))
    story += [t, Spacer(1, 4 * mm)]
    # Summen
    summen = [["Summe der Positionen (netto)", geld(s.get("positionen_netto"))]]
    for z in s.get("zuschlaege") or []:
        summen.append([f"zzgl. {z.get('text')} ({_menge(z.get('prozent'))} %)", geld(z.get("betrag"))])
    if float(s.get("rabatt_betrag") or 0):
        summen.append([f"abzüglich Rabatt ({_menge(s.get('rabatt_prozent'))} %)", "– " + geld(s.get("rabatt_betrag"))])
    summen.append(["Nettobetrag", geld(s.get("netto"))])
    steuer = s.get("steuer") or {}
    if steuer.get("kategorie") == "S":
        summen.append([f"zzgl. {_menge(s.get('ust_satz'))} % Umsatzsteuer", geld(s.get("ust"))])
    else:
        summen.append(["Umsatzsteuer", geld(0)])
    summen.append(["Angebotssumme (brutto)", geld(s.get("brutto"))])
    st_summe = [[Paragraph(esc(a), st_rf if i == len(summen) - 1 else st_r), Paragraph(esc(b), st_rf if i == len(summen) - 1 else st_r)] for i, (a, b) in enumerate(summen)]
    ts = Table(st_summe, colWidths=[120 * mm, 38 * mm], hAlign="RIGHT")
    ts.setStyle(TableStyle([("LINEABOVE", (0, len(summen) - 1), (-1, len(summen) - 1), 0.6, colors.black), ("TOPPADDING", (0, 0), (-1, -1), 1.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5)]))
    story.append(ts)
    hinweise = []
    if float(s.get("alternativ_netto") or 0):
        hinweise.append(f"Alternativpositionen (netto, nicht enthalten): {geld(s.get('alternativ_netto'))}")
    if float(s.get("eventual_netto") or 0):
        hinweise.append(f"Eventualpositionen (netto, nur bei Bedarf): {geld(s.get('eventual_netto'))}")
    if steuer.get("hinweis"):
        hinweise.append(steuer["hinweis"] + ".")
    for h in hinweise:
        story.append(Paragraph(esc(h), st_klein))
    story.append(Spacer(1, 5 * mm))
    if daten.get("zahlungsbedingungen"):
        story.append(Paragraph(f"<b>Zahlungsbedingungen:</b> {esc(daten['zahlungsbedingungen'])}", st["n"]))
    if daten.get("gueltig_bis"):
        story.append(Paragraph(f"Dieses Angebot ist gültig bis zum {de(daten['gueltig_bis'])}.", st["n"]))
    if daten.get("schluss"):
        story.append(Paragraph(esc(daten["schluss"]), st["n"]))
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph("Mit freundlichen Grüßen", st["n"]))
    stempel = _bild_flowable(daten.get("stempel"), 60 * mm * min(1.5, max(0.5, (daten.get("stempel_scale") or 100) / 100)), 28 * mm)
    if stempel is not None:
        story += [Spacer(1, 2 * mm), stempel]
    else:
        story.append(Spacer(1, 10 * mm))
    story.append(Paragraph(esc(f.get("owner") or f.get("name")), st["n"]))
    story.append(Paragraph(esc(f.get("name")), st_klein))
    annahme = daten.get("annahme")
    if annahme:
        story += [Spacer(1, 8 * mm), Paragraph(f"<b>Angenommen</b> am {de(annahme.get('am'))} durch {esc(annahme.get('von_name'))}" + (f" ({esc(annahme.get('art'))})" if annahme.get("art") else ""), st["n"])]
    else:
        story += [Spacer(1, 10 * mm), Paragraph("<b>Auftragserteilung</b> – Hiermit erteile ich den Auftrag gemäß diesem Angebot:", st["n"]), Spacer(1, 12 * mm),
                  Table([[Paragraph("______________________________<br/>Ort, Datum", st_klein), Paragraph("______________________________<br/>Unterschrift Auftraggeber", st_klein)]], colWidths=[85 * mm, 85 * mm])]
    doc.build(story, onFirstPage=fuss, onLaterPages=fuss)
    return buf.getvalue()
