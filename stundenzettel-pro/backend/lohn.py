"""Lohnvorbereitung – die App rechnet keinen Lohn.

Sie stellt je Monat und Mitarbeiter alles zusammen, was Lohnbüro oder Steuerberater (DATEV) brauchen:
Stunden gesamt und nach Art (Nacht 20–6 Uhr, Sonntag, Feiertag – die Zuschlagshöhe rechnet das Lohnbüro nach Vertrag/Tarif),
Soll/Saldo/Überstunden aus dem Stundenkonto, Urlaubs-, Krank- und sonstige Abwesenheitstage, Resturlaub, Stammdaten.
Ausgaben: JSON (Vorschau), CSV (jedes Lohnprogramm), LODAS-Importdatei (DATEV, Lohnarten einstellbar), PDF (Unterschrift/Ablage),
Stammdaten-CSV (einmalig für die Anlage beim Steuerberater).
"""
from __future__ import annotations

import csv
import io
from datetime import date, timedelta

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from db import db
from feiertage import feiertage_set
from geheim import entschluesseln
from konten import arbeitstage, kontoverlauf, monatskonto, urlaubskonto
from pdfbasis import SCHRIFT, SCHRIFT_FETT, schrift_registrieren
from zeiten import monatsletzter

NACHT_FENSTER = [(0, 360), (1200, 1440), (1440, 1800), (2640, 2880)]  # 20–6 Uhr, auch bei Einträgen über Mitternacht
GEHEIM = ("tax_id", "sv_number", "iban_salary")
BESCHAEFTIGUNG = {"vollzeit": "Vollzeit", "teilzeit": "Teilzeit", "minijob": "Minijob", "kurzfristig": "kurzfristig", "werkstudent": "Werkstudent",
                  "azubi": "Auszubildende/r", "sonstiges": "Sonstiges", "": ""}
KATEGORIEN = (("normal", "Stunden gesamt"), ("ueberstunden", "Überstunden (Saldo Monat)"), ("nacht", "Nachtstunden 20–6 Uhr"),
              ("sonntag", "Sonntagsstunden"), ("feiertag", "Feiertagsstunden"), ("urlaub", "Urlaubstage"), ("krank", "Kranktage"))
HINWEIS = ("Keine Lohnabrechnung: Stunden nach Art, Abwesenheiten und Stundenkonto als Grundlage für Lohnbüro/Steuerberater. "
           "Nachtstunden = Arbeit zwischen 20 und 6 Uhr (§ 3b EStG); Sonntags-/Feiertagsstunden zählen zusätzlich in den Gesamtstunden. "
           "Zuschlagshöhe und Abzüge rechnet das Lohnbüro nach Arbeitsvertrag bzw. Tarif.")


def _min(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def eintrag_kategorien(e: dict, feiertage: dict) -> dict:
    """Netto-Minuten eines Eintrags gesamt und davon Nacht/Sonntag/Feiertag (Pause anteilig abgezogen)."""
    s, en = _min(e["start_time"]), _min(e["end_time"])
    if en <= s:
        en += 1440
    brutto = en - s
    netto = int(e["net_minutes"]) if e.get("net_minutes") is not None else max(0, brutto - int(e.get("pause_minutes") or 0))
    faktor = (netto / brutto) if brutto else 0
    nacht = round(sum(max(0, min(en, b) - max(s, a)) for a, b in NACHT_FENSTER) * faktor)
    d = date.fromisoformat(e["date"])
    return {"netto": netto, "nacht": nacht, "sonntag": netto if d.weekday() == 6 else 0, "feiertag": netto if e["date"] in feiertage else 0}


def lohndaten_lesen(u: dict) -> dict:
    l = dict(u.get("lohndaten") or {})
    for k in GEHEIM:
        l[k] = entschluesseln(l.get(k))
    return l


async def mitarbeiter_monat(firma: dict, u: dict, jahr: int, monat: int, feiertage: dict, eintraege: list[dict]) -> dict:
    summe = {"netto": 0, "nacht": 0, "sonntag": 0, "feiertag": 0}
    tage = set()
    for e in eintraege:
        k = eintrag_kategorien(e, feiertage)
        for key in summe:
            summe[key] += k[key]
        tage.add(e["date"])
    von, bis = date(jahr, monat, 1), monatsletzter(jahr, monat)
    atage = arbeitstage(u, firma)
    abwesend = {"urlaub": 0, "krank": 0, "feiertag": 0, "unbezahlt": 0, "sonstiges": 0}
    async for a in db().absences.find({"firma_id": firma["id"], "user_id": u["id"], "status": "genehmigt",
                                       "from_date": {"$lte": bis.isoformat()}, "to_date": {"$gte": von.isoformat()}}, {"_id": 0}):
        d = max(date.fromisoformat(a["from_date"]), von)
        ende = min(date.fromisoformat(a["to_date"]), bis)
        while d <= ende:
            if d.weekday() in atage and d.isoformat() not in feiertage:
                abwesend[a["type"] if a["type"] in abwesend else "sonstiges"] += 1
            d += timedelta(days=1)
    konto = await monatskonto(firma, u, jahr, monat)
    verlauf = await kontoverlauf(firma, u, jahr, monat) if u.get("weekly_hours") else None
    urlaub = await urlaubskonto(firma, u, jahr)
    gesetzliche = sum(1 for k in feiertage if von.isoformat() <= k <= bis.isoformat() and date.fromisoformat(k).weekday() in atage)
    l = lohndaten_lesen(u)
    return {
        "user_id": u["id"], "personalnummer": u.get("personalnummer") or "", "name": u.get("name") or "", "role": u.get("role"),
        "employment_type": l.get("employment_type") or "", "hourly_wage": l.get("hourly_wage"), "monthly_salary": l.get("monthly_salary"),
        "arbeitstage": len(tage), "minuten": summe["netto"], "nacht_minuten": summe["nacht"], "sonntag_minuten": summe["sonntag"], "feiertag_minuten": summe["feiertag"],
        "wochenstunden": float(u.get("weekly_hours") or 0), "soll_minuten": konto["soll_minuten"], "saldo_monat_minuten": konto["saldo_minuten"],
        "ueberstunden_minuten": max(0, konto["saldo_minuten"]) if u.get("weekly_hours") else 0,
        "saldo_gesamt_minuten": verlauf["saldo_minuten"] if verlauf else None,
        "urlaubstage": abwesend["urlaub"], "kranktage": abwesend["krank"], "feiertage_abwesend": abwesend["feiertag"], "unbezahlt_tage": abwesend["unbezahlt"],
        "sonstige_tage": abwesend["sonstiges"], "gesetzliche_feiertage": gesetzliche, "resturlaub": urlaub["rest"],
    }


async def lohnvorbereitung(firma: dict, jahr: int, monat: int) -> dict:
    von, bis = date(jahr, monat, 1).isoformat(), monatsletzter(jahr, monat).isoformat()
    feiertage = feiertage_set([jahr], firma.get("bundesland") or "")
    nutzer = {u["id"]: u async for u in db().users.find({"firma_id": firma["id"]}, {"_id": 0, "pw_hash": 0, "pin_hash": 0, "einladung_token": 0})}
    eintraege: dict[str, list] = {}
    async for e in db().entries.find({"firma_id": firma["id"], "user_id": {"$ne": None}, "date": {"$gte": von, "$lte": bis}}, {"_id": 0}):
        eintraege.setdefault(e["user_id"], []).append(e)
    zeilen = []
    for uid, u in sorted(nutzer.items(), key=lambda kv: (kv[1].get("name") or "").lower()):
        if u.get("deleted_at"):
            continue
        if not u.get("active", True) and uid not in eintraege:
            continue
        zeilen.append(await mitarbeiter_monat(firma, u, jahr, monat, feiertage, eintraege.get(uid, [])))
    return {"jahr": jahr, "monat": monat, "von": von, "bis": bis, "bundesland": firma.get("bundesland") or "",
            "feiertage": {k: v for k, v in feiertage.items() if von <= k <= bis}, "mitarbeiter": zeilen, "hinweis": HINWEIS,
            "lohn_export": firma.get("lohn_export") or {}}


# ---------- Ausgaben ----------

def dez(minuten) -> str:
    return f"{(minuten or 0) / 60:.2f}".replace(".", ",")


def _zahl(x) -> str:
    return "" if x is None else f"{float(x):.2f}".replace(".", ",")


def csv_bytes(zeilen: list[list]) -> bytes:
    puffer = io.StringIO()
    w = csv.writer(puffer, delimiter=";", lineterminator="\r\n", quoting=csv.QUOTE_MINIMAL)
    for z in zeilen:
        w.writerow(["" if v is None else v for v in z])
    return ("﻿" + puffer.getvalue()).encode("utf-8")


def vorbereitung_csv(daten: dict) -> bytes:
    zeilen = [["Personalnummer", "Mitarbeiter", "Beschäftigung", "Stundenlohn", "Monatsgehalt", "Arbeitstage", "Stunden gesamt", "davon Nacht 20-6",
               "davon Sonntag", "davon Feiertag", "Wochenstunden", "Soll (Std)", "Saldo Monat (Std)", "Überstunden Monat (Std)", "Saldo gesamt (Std)",
               "Urlaubstage", "Kranktage", "Feiertage (Abwesenheit)", "Unbezahlt (Tage)", "Sonstige (Tage)", "Resturlaub (Tage)", "Monat"]]
    for m in daten["mitarbeiter"]:
        zeilen.append([m["personalnummer"], m["name"], BESCHAEFTIGUNG.get(m["employment_type"], m["employment_type"]), _zahl(m["hourly_wage"]), _zahl(m["monthly_salary"]),
                       m["arbeitstage"], dez(m["minuten"]), dez(m["nacht_minuten"]), dez(m["sonntag_minuten"]), dez(m["feiertag_minuten"]), _zahl(m["wochenstunden"]),
                       dez(m["soll_minuten"]), dez(m["saldo_monat_minuten"]), dez(m["ueberstunden_minuten"]),
                       dez(m["saldo_gesamt_minuten"]) if m["saldo_gesamt_minuten"] is not None else "", m["urlaubstage"], m["kranktage"], m["feiertage_abwesend"],
                       m["unbezahlt_tage"], m["sonstige_tage"], _zahl(m["resturlaub"]), f"{daten['monat']:02d}/{daten['jahr']}"])
    zeilen.append([])
    zeilen.append([daten["hinweis"]])
    return csv_bytes(zeilen)


def lodas_text(daten: dict) -> tuple[str, list[str]]:
    """LODAS-Importdatei (Bewegungsdaten, Tabelle u_lod_bwd_buchung_standard). Lohnarten-Nummern kommen aus den Firmeneinstellungen;
    Kategorien ohne Nummer werden ausgelassen. Rückgabe: Text und Hinweise (z. B. fehlende Personalnummern)."""
    einst = daten.get("lohn_export") or {}
    lohnarten = einst.get("lohnarten") or {}
    bs = int(einst.get("bs_nr") or 1)
    jahr, monat = daten["jahr"], daten["monat"]
    hinweise = []
    kopf = ["[Allgemein]", "Ziel=LODAS", "Version_SST=1.0", f"BeraterNr={einst.get('berater_nr') or ''}", f"MandantenNr={einst.get('mandanten_nr') or ''}",
            "Feldtrennzeichen=;", "Zahlenkomma=,", "Datumsformat=TT.MM.JJJJ", 'Stringbegrenzer="', "Kommentarzeichen=*", f"StammdatenGueltigAb=01.{monat:02d}.{jahr}", "",
            "[Satzbeschreibung]", "100;u_lod_bwd_buchung_standard;pnr#bwd;abrechnung_zeitraum#bwd;bs_wert_butab#bwd;bs_nr#bwd;la_eigene#bwd;", "",
            "[Bewegungsdaten]"]
    if not any(lohnarten.values()):
        hinweise.append("Keine Lohnarten-Nummern hinterlegt (Exporte → Lohnvorbereitung → DATEV-Einstellungen).")
    if not (einst.get("berater_nr") and einst.get("mandanten_nr")):
        hinweise.append("Berater- und Mandantennummer fehlen (DATEV-Einstellungen) – die Kanzlei kann sie auch selbst eintragen.")
    zeilen = []
    for m in daten["mitarbeiter"]:
        if not m["personalnummer"]:
            hinweise.append(f"{m['name']}: keine Personalnummer – Zeile ausgelassen.")
            continue
        werte = {"normal": m["minuten"] / 60, "ueberstunden": m["ueberstunden_minuten"] / 60, "nacht": m["nacht_minuten"] / 60, "sonntag": m["sonntag_minuten"] / 60,
                 "feiertag": m["feiertag_minuten"] / 60, "urlaub": m["urlaubstage"], "krank": m["kranktage"]}
        for key, _ in KATEGORIEN:
            la = (lohnarten.get(key) or "").strip()
            wert = werte[key]
            if la and wert:
                zeilen.append(f"100;{m['personalnummer']};01.{monat:02d}.{jahr};{str(round(float(wert), 2)).replace('.', ',')};{bs};{la};")
    return "\r\n".join(kopf + zeilen) + "\r\n", hinweise


def stammdaten_csv(nutzer: list[dict]) -> bytes:
    zeilen = [["Personalnummer", "Name", "E-Mail", "Telefon", "Geburtsdatum", "Straße", "PLZ", "Ort", "Steuer-ID", "Steuerklasse", "Kirchensteuer", "SV-Nummer",
               "Krankenkasse", "Beschäftigung", "Eintritt", "Austritt", "Stundenlohn", "Monatsgehalt", "Wochenstunden", "Urlaubstage/Jahr", "IBAN", "Hinweise"]]
    for u in nutzer:
        l = lohndaten_lesen(u)
        zeilen.append([u.get("personalnummer") or "", u.get("name") or "", u.get("email") or "", u.get("phone") or "", _de(l.get("birth_date")), l.get("street") or "",
                       l.get("zip_code") or "", l.get("city") or "", l.get("tax_id") or "", l.get("tax_class") or "",
                       "" if l.get("church_tax") is None else ("ja" if l.get("church_tax") else "nein"), l.get("sv_number") or "", l.get("health_insurance") or "",
                       BESCHAEFTIGUNG.get(l.get("employment_type") or "", l.get("employment_type") or ""), _de(l.get("entry_date")), _de(l.get("exit_date")),
                       _zahl(l.get("hourly_wage")), _zahl(l.get("monthly_salary")), _zahl(u.get("weekly_hours")), _zahl(u.get("vacation_days")),
                       l.get("iban_salary") or "", l.get("notes_payroll") or ""])
    return csv_bytes(zeilen)


def _de(iso) -> str:
    if not iso:
        return ""
    j, m, t = str(iso)[:10].split("-")
    return f"{t}.{m}.{j}"


MONATE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"]


def vorbereitung_pdf(firma: dict, daten: dict) -> bytes:
    """Übersicht als PDF (Querformat): eine Zeile je Mitarbeiter, zum Unterschreiben und Ablegen."""
    schrift_registrieren()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=14 * mm, rightMargin=14 * mm, topMargin=14 * mm, bottomMargin=14 * mm,
                            title=f"Lohnvorbereitung {MONATE[daten['monat'] - 1]} {daten['jahr']}", author=firma.get("name") or "", creator="Stundenzettel Pro")
    h1 = ParagraphStyle("h1", fontName=SCHRIFT_FETT, fontSize=15, leading=19)
    norm = ParagraphStyle("n", fontName=SCHRIFT, fontSize=8.5, leading=11, textColor=colors.HexColor("#444444"))
    klein = ParagraphStyle("k", fontName=SCHRIFT, fontSize=7.5, leading=9.5, textColor=colors.HexColor("#666666"))
    teile = [Paragraph(f"Lohnvorbereitung {MONATE[daten['monat'] - 1]} {daten['jahr']} – {firma.get('name') or ''}", h1),
             Paragraph(f"Zeitraum {_de(daten['von'])} bis {_de(daten['bis'])}. Feiertage ({daten.get('bundesland') or 'bundesweit'}): "
                       + (", ".join(f"{_de(k)} {v}" for k, v in sorted(daten['feiertage'].items())) or "keine"), norm), Spacer(1, 4 * mm)]
    kopf = ["Pers.-Nr.", "Mitarbeiter", "Tage", "Std. gesamt", "Nacht", "Sonntag", "Feiertag", "Soll", "Saldo Monat", "Überstd.", "Urlaub", "Krank", "Unbez.", "Resturlaub"]
    zeilen = [kopf]
    for m in daten["mitarbeiter"]:
        zeilen.append([m["personalnummer"], m["name"], m["arbeitstage"], dez(m["minuten"]), dez(m["nacht_minuten"]), dez(m["sonntag_minuten"]), dez(m["feiertag_minuten"]),
                       dez(m["soll_minuten"]) if m["wochenstunden"] else "–", dez(m["saldo_monat_minuten"]) if m["wochenstunden"] else "–",
                       dez(m["ueberstunden_minuten"]) if m["wochenstunden"] else "–", m["urlaubstage"], m["kranktage"], m["unbezahlt_tage"], _zahl(m["resturlaub"])])
    breiten = [18 * mm, 48 * mm, 12 * mm] + [19 * mm] * 7 + [14 * mm, 14 * mm, 14 * mm, 20 * mm]
    t = Table(zeilen, colWidths=breiten, repeatRows=1)
    t.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, 0), SCHRIFT_FETT), ("FONTNAME", (0, 1), (-1, -1), SCHRIFT), ("FONTSIZE", (0, 0), (-1, -1), 8),
                           ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F5F5F7")), ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
                           ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#DDDDDD")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                           ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    teile += [t, Spacer(1, 5 * mm), Paragraph(daten["hinweis"], klein), Spacer(1, 10 * mm),
              Paragraph("Geprüft (Datum, Unterschrift Büro/Inhaber): ______________________________", norm)]
    doc.build(teile)
    return buf.getvalue()
