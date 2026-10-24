"""Vollständige Projektakte als ZIP – für jede Firma (im Firmenabo enthalten), nicht nur für Auftraggeber.

Inhalt je nach Rolle: Die eigene Firma bekommt immer ihre eigenen Daten zum Projekt (Zeiten mit monatlichen Stundennachweisen, Fotos nach
Mitarbeiter und Tag, Dokumente, Rechnungen als PDF, Unterschriften, Checklisten, Kommentare, eigene Angebote und Aufträge, Nachträge,
Abnahmen, Protokoll und E-Mail-Nachweise). Die Eigentümerfirma eines Plattform-Projekts bekommt zusätzlich alle für sie sichtbaren
Unterlagen der beteiligten Firmen (Aufgaben, Lieferungen, Mängel, Bautagesberichte, Meilensteine, geteilte Dokumente, freigegebene
Wochen-Nachweise, Ausschreibungen mit allen Angeboten und Vergaben). Eine beteiligte Firma bekommt vom Plattform-Projekt nur ihre eigenen
und die für alle freigegebenen Unterlagen. Private Daten anderer Firmen (Stundenlöhne, Personal, Kalkulationen) sind nie enthalten.
Fehlen Ausschreibung oder Zuschlag, werden diese Bereiche einfach ausgelassen."""
from __future__ import annotations

import base64
import csv
import io
import json
import re
import zipfile
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from fastapi import HTTPException

import config
import erechnung
import pdfbasis
import pdfs
from auth import firma_laden, jetzt_iso
from csvsicher import zeile as csv_zeile
from db import db
from gemeinsam import kunde_laden, neue_id, nutzernamen, projekt_normalisieren
from plattform import firma_kurz, zugang
from zeiten import eintrag_minuten

MONATE = pdfs.MONATE


def _name(text: str, laenge: int = 80) -> str:
    """Dateisystem-sicherer Name (Umlaute bleiben, Sonderzeichen werden zu _)."""
    text = re.sub(r"[^\w.\- ()]+", "_", str(text or "ohne_namen"), flags=re.UNICODE).strip(" ._") or "ohne_namen"
    return text[:laenge]


def _csv(zeilen: list[list]) -> bytes:
    puffer = io.StringIO()
    w = csv.writer(puffer, delimiter=";", lineterminator="\r\n", quoting=csv.QUOTE_MINIMAL)
    for z in zeilen:
        w.writerow(csv_zeile(["" if v is None else v for v in z]))
    return ("﻿" + puffer.getvalue()).encode("utf-8")


def _json(daten) -> bytes:
    return json.dumps(daten, ensure_ascii=False, indent=2, default=str).encode("utf-8")


def _dez(minuten: int) -> str:
    return f"{minuten / 60:.2f}".replace(".", ",")


def _ohne_pfad(d: dict) -> dict:
    return {k: v for k, v in d.items() if k not in ("path", "_id")}


class _Zip:
    def __init__(self, pfad: Path):
        self.z = zipfile.ZipFile(pfad, "w", zipfile.ZIP_DEFLATED)
        self.zaehler: Counter = Counter()
        self.hinweise: list[str] = []
        self.namen: set[str] = set()

    def eindeutig(self, name: str) -> str:
        basis, i = name, 2
        while name in self.namen:
            stamm, punkt, endung = basis.rpartition(".")
            name = f"{stamm}_{i}.{endung}" if punkt else f"{basis}_{i}"
            i += 1
        self.namen.add(name)
        return name

    def schreiben(self, name: str, daten: bytes, art: str) -> None:
        self.z.writestr(self.eindeutig(name), daten)
        self.zaehler[art] += 1

    def datei(self, name: str, pfad: str, art: str) -> bool:
        try:
            if pfad and Path(pfad).is_file():
                self.z.write(pfad, self.eindeutig(name))
                self.zaehler[art] += 1
                return True
        except OSError:
            pass
        self.hinweise.append(f"Datei fehlt auf dem Server: {name}")
        return False

    def schliessen(self) -> None:
        self.z.close()


async def _dokumente(filt: dict) -> list[dict]:
    return [d async for d in db().documents.find(filt, {"_id": 0}).sort("created_at", 1)]


def _dateiname(d: dict) -> str:
    version = int(d.get("version") or 1)
    stamm, punkt, endung = (d.get("filename") or "datei").rpartition(".")
    if not punkt:
        stamm, endung = d.get("filename") or "datei", ""
    return _name(f"{stamm}{'_v' + str(version) if version > 1 else ''}") + (f".{endung}" if endung else "")


async def _fotos_schreiben(z: _Zip, ordner: str, dokumente: list[dict], namen: dict, art: str = "fotos") -> None:
    for d in dokumente:
        person = namen.get(d.get("uploaded_by") or "", "") or d.get("uploaded_by_name") or "Ohne Zuordnung"
        tag = (d.get("date") or (d.get("created_at") or "")[:10]) or "ohne_datum"
        z.datei(f"{ordner}/{_name(person, 40)}/{tag}/{_dateiname(d)}", d.get("path") or "", art)


async def _ausfuehrende_firma(firma_id: str) -> dict:
    f = await firma_laden(firma_id)
    return {k: f.get(k) for k in ("id", "name", "street", "zip_code", "city", "email", "phone")}


async def erstellen(user: dict, projekt: dict) -> dict:
    """Projektakte bauen, auf der Platte ablegen und den Datensatz in `projektakten` anlegen."""
    firma_id = user["firma_id"]
    firma = await firma_laden(firma_id)
    projekt = projekt_normalisieren(projekt)
    namen = await nutzernamen(firma_id)
    verknuepft = projekt.get("verknuepft") or {}
    plattform_id = verknuepft.get("project_id") or projekt["id"]
    rolle = "beteiligt" if verknuepft.get("project_id") else "eigentuemer"
    z_pl: Optional[dict] = None
    try:
        z_pl = await zugang(user, plattform_id)
        if z_pl["eigentuemer"] and not z_pl["leitung"]:
            z_pl = None
    except HTTPException:
        z_pl = None   # Beteiligung beendet oder kein Zugang mehr: nur die eigenen Daten
    akte_id = neue_id()
    ordner = config.DATA_DIR / "projektakten" / re.sub(r"[^a-zA-Z0-9\-]", "", firma_id)
    ordner.mkdir(parents=True, exist_ok=True)
    pfad = ordner / f"{akte_id}.zip"
    z = _Zip(pfad)
    try:
        await _eigene_daten(z, user, firma, projekt, namen)
        if z_pl is not None:
            await _plattform_daten(z, user, firma, projekt, z_pl, namen, rolle)
        await _nachweise(z, firma_id, projekt, plattform_id)
        z.schreiben("00_LIESMICH.txt", _liesmich(firma, projekt, user, rolle, z, z_pl), "liesmich")
    finally:
        z.schliessen()
    groesse = pfad.stat().st_size
    aufbewahren_bis = (date.today().replace(year=date.today().year + config.AUFBEWAHRUNG_JAHRE)).isoformat()
    akte = {"id": akte_id, "firma_id": firma_id, "project_id": projekt["id"], "project_name": projekt.get("name"), "plattform_project_id": plattform_id if z_pl is not None else None,
            "rolle": rolle, "dateiname": f"Projektakte_{_name(projekt.get('name'), 60)}_{jetzt_iso()[:10]}.zip", "pfad": str(pfad), "size": groesse,
            "inhalt": dict(z.zaehler), "hinweise": z.hinweise[:50], "aufbewahren_bis": aufbewahren_bis, "created_by": user["id"], "created_by_name": user.get("name"), "created_at": jetzt_iso()}
    await db().projektakten.insert_one(dict(akte))
    return akte


async def _eigene_daten(z: _Zip, user: dict, firma: dict, projekt: dict, namen: dict) -> None:
    fid, pid = firma["id"], projekt["id"]
    z.schreiben("01_Projekt/projekt.json", _json({k: v for k, v in projekt.items() if k not in ("stats",)}), "projekt")
    kommentare = [["Datum", "Von", "Text"]]
    async for k in db().comments.find({"firma_id": fid, "project_id": pid}, {"_id": 0}).sort("created_at", 1):
        kommentare.append([k.get("created_at"), k.get("user_name"), k.get("text")])
    if len(kommentare) > 1:
        z.schreiben("01_Projekt/kommentare.csv", _csv(kommentare), "kommentare")
    checklisten = [c async for c in db().checklists.find({"firma_id": fid, "project_id": pid}, {"_id": 0}).sort("created_at", 1)]
    if checklisten:
        zeilen = [["Checkliste", "Datum", "Punkt", "Erledigt", "Erledigt von", "Erledigt am"]]
        for c in checklisten:
            for i in c.get("items") or []:
                zeilen.append([c.get("name"), c.get("date") or "", i.get("text"), "ja" if i.get("done") else "nein", namen.get(i.get("done_by") or "", "") or (i.get("done_by") or ""), i.get("done_at") or ""])
        z.schreiben("01_Projekt/checklisten.csv", _csv(zeilen), "checklisten")
    # Zeiten: CSV gesamt und Stundennachweis-PDF je Monat, Unterschriften
    eintraege = [e async for e in db().entries.find({"firma_id": fid, "project_id": pid}, {"_id": 0}).sort([("date", 1), ("start_time", 1)])]
    unterschriften = [u async for u in db().signatures.find({"firma_id": fid, "project_id": pid}, {"_id": 0}).sort([("week_monday", 1), ("version", 1)])]
    if eintraege:
        zeilen = [["Datum", "Mitarbeiter", "Beginn", "Ende", "Pause (Min)", "Anzahl", "Netto (Min)", "Mitarbeiterstunden (dezimal)", "Tätigkeit", "Leistung", "Quelle", "Prüfen", "Hinweise", "Stempel Start", "Stempel Ende",
                   "Freigegeben", "Freigegeben von", "Ursprünglich Beginn", "Ursprünglich Ende", "Ursprünglich Netto (Min)"]]
        for e in eintraege:
            f, o = e.get("freigabe") or {}, e.get("original") or {}
            zeilen.append([e.get("date"), namen.get(e.get("user_id") or "", ""), e.get("start_time"), e.get("end_time"), e.get("pause_minutes", 0), e.get("workers", 1), e.get("net_minutes", 0),
                           _dez(eintrag_minuten(e)), e.get("activity", ""), e.get("service_name", ""), e.get("source", "manuell"), "ja" if e.get("pruefen") else "", "; ".join(h.get("text", "") for h in e.get("hinweise") or []),
                           e.get("clock_start_at") or "", e.get("clock_end_at") or "", "ja" if f else "", f.get("von_name") or "", o.get("start_time") or "", o.get("end_time") or "", o.get("net_minutes") if o else ""])
        z.schreiben("02_Zeiten/zeiten.csv", _csv(zeilen), "zeiten")
        monate = sorted({(e["date"][:7]) for e in eintraege if e.get("date")})
        for ym in monate:
            jahr, monat = int(ym[:4]), int(ym[5:7])
            im_monat = [e for e in eintraege if (e.get("date") or "").startswith(ym)]
            u_monat = [u for u in unterschriften if (u.get("week_monday") or "").startswith(ym) and not u.get("ersetzt")]
            try:
                z.schreiben(f"02_Zeiten/Stundennachweis_{ym}.pdf", pdfs.zeiten_pdf(firma, projekt, jahr, monat, im_monat, namen, u_monat), "stundennachweise")
            except Exception as exc:  # noqa: BLE001 – ein PDF-Fehler darf die Akte nicht verhindern
                z.hinweise.append(f"Stundennachweis {ym} konnte nicht erzeugt werden: {exc}")
    if unterschriften:
        zeilen = [["Woche ab", "Unterschrieben von", "Am", "Version", "Ersetzt", "Grund", "Datei"]]
        for u in unterschriften:
            datei = ""
            bild = u.get("image") or ""
            if isinstance(bild, str) and bild.startswith("data:image"):
                try:
                    kopf, daten = bild.split(",", 1)
                    endung = "png" if "png" in kopf else "jpg"
                    datei = f"02_Zeiten/Unterschriften/{u.get('week_monday')}_v{u.get('version') or 1}.{endung}"
                    z.schreiben(datei, base64.b64decode(daten), "unterschriften")
                except (ValueError, TypeError):
                    datei = ""
            zeilen.append([u.get("week_monday"), u.get("signer_name"), u.get("signed_at"), u.get("version") or 1, "ja" if u.get("ersetzt") else "", u.get("grund") or u.get("ersetzt_grund") or "", datei])
        z.schreiben("02_Zeiten/unterschriften.csv", _csv(zeilen), "unterschriften_liste")
    # Fotos und Dokumente der Projektakte
    dokumente = await _dokumente({"firma_id": fid, "scope": "project", "ref_id": pid})
    await _fotos_schreiben(z, "03_Fotos", [d for d in dokumente if d.get("category") == "Fotos" or (d.get("mime") or "").startswith("image/")], namen)
    for d in dokumente:
        if d.get("category") == "Fotos" or (d.get("mime") or "").startswith("image/"):
            continue
        z.datei(f"04_Dokumente/{_name(d.get('ordner') or d.get('category') or 'Sonstiges', 60)}/{_dateiname(d)}", d.get("path") or "", "dokumente")
    if dokumente:
        z.schreiben("04_Dokumente/dokumente.csv", _csv([["Datei", "Kategorie", "Ordner", "Notiz", "Datum", "Version", "Aktuell", "Hochgeladen von", "Am", "Größe"]] +
                                                       [[d.get("filename"), d.get("category"), d.get("ordner") or "", d.get("note") or "", d.get("date") or "", d.get("version") or 1, "nein" if d.get("aktuell") is False else "ja", d.get("uploaded_by_name") or "", d.get("created_at"), d.get("size")] for d in dokumente]), "dokumente_liste")
    # Rechnungen: Liste plus PDF (PDF/A-3, mit ZUGFeRD-XML wenn die Kundendaten vollständig sind)
    rechnungen = [r async for r in db().invoices.find({"firma_id": fid, "project_id": pid}, {"_id": 0}).sort([("year", 1), ("seq", 1)])]
    if rechnungen:
        zeilen = [["Nummer", "Jahr", "Monat", "Rechnungsdatum", "Status", "Netto", "USt", "Brutto", "Bezahlt am", "Festgeschrieben am"]]
        for r in rechnungen:
            zeilen.append([r.get("number"), r.get("year"), r.get("month"), r.get("invoice_date"), r.get("status"), r.get("net"), r.get("vat"), r.get("gross"), r.get("paid_at") or "", r.get("festgeschrieben_at") or ""])
            try:
                kunde = await kunde_laden(fid, r.get("customer_id") or projekt.get("customer_id"))
                daten = erechnung.rechnungsdaten(firma, projekt, kunde, r)
                xml = erechnung.cii_xml(daten, "zugferd") if erechnung.pruefen(daten, "zugferd")["ok"] else None
                z.schreiben(f"05_Rechnungen/{_name(r.get('number'))}.pdf", pdfbasis.pdfa3_mit_xml(erechnung.rechnung_pdf(daten), xml, f"Rechnung {r.get('number')}", firma.get("name") or ""), "rechnungen")
            except Exception as exc:  # noqa: BLE001
                z.hinweise.append(f"Rechnung {r.get('number')} konnte nicht als PDF erzeugt werden: {exc}")
        z.schreiben("05_Rechnungen/rechnungen.csv", _csv(zeilen), "rechnungen_liste")
    # Kundenangebote und Auftrag (Stufe C): jede Version als PDF (gesendete aus dem Snapshot), Liste, Auftrag des Projekts
    angebote_k = [a async for a in db().kundenangebote.find({"firma_id": fid, "project_id": pid}, {"_id": 0}).sort([("seq", 1), ("version", 1)])]
    if angebote_k:
        import angebote as ang_modul
        zeilen = [["Nummer", "Version", "Status", "Titel", "Datum", "Gültig bis", "Netto", "USt", "Brutto", "Gesendet an", "Annahme durch", "Annahme am"]]
        for a in angebote_k:
            s = a.get("summen") or {}
            an = a.get("annahme") or {}
            zeilen.append([a.get("nummer"), a.get("version"), a.get("status"), a.get("titel"), a.get("datum"), a.get("gueltig_bis"), s.get("netto"), s.get("ust"), s.get("brutto"),
                           "; ".join((v.get("an") or v.get("art") or "") for v in a.get("versand") or []), an.get("von_name") or "", an.get("am") or ""])
            try:
                pfad = a.get("pdf_pfad")
                inhalt = (config.DATA_DIR / pfad).read_bytes() if pfad and (config.DATA_DIR / pfad).is_file() else pdfs.angebot_pdf(ang_modul.pdf_daten(firma, a))
                z.schreiben(f"06_Angebote/{_name(a.get('nummer'))}_v{a.get('version') or 1}.pdf", inhalt, "angebote_kunde")
            except Exception as exc:  # noqa: BLE001
                z.hinweise.append(f"Angebot {a.get('nummer')} konnte nicht als PDF erzeugt werden: {exc}")
        z.schreiben("06_Angebote/angebote.csv", _csv(zeilen), "angebote_kunde_liste")
    if projekt.get("auftrag"):
        z.schreiben("06_Angebote/auftrag.json", _json(projekt["auftrag"]), "auftrag")
    # Material, Eingangsrechnungen (Belege), Nachkalkulation (Stufe D)
    material = [m async for m in db().materialverbrauch.find({"firma_id": fid, "project_id": pid}, {"_id": 0}).sort([("date", 1)])]
    if material:
        z.schreiben("07_Material/material.csv", _csv([["Datum", "Mitarbeiter", "Artikelnummer", "Material", "Menge", "Einheit", "Einkaufspreis", "Kosten", "Status", "Geprüft von", "Notiz"]] +
                                                  [[m.get("date"), m.get("user_name"), m.get("artikel_nummer") or "", m.get("bezeichnung"), m.get("menge"), m.get("einheit"), m.get("einkaufspreis"), m.get("kosten"), m.get("status"), m.get("geprueft_von") or "", m.get("note") or ""] for m in material]), "material")
    eingang = [r async for r in db().eingangsrechnungen.find({"firma_id": fid, "zuordnungen.project_id": pid}, {"_id": 0}).sort([("rechnungsdatum", 1)])]
    if eingang:
        zeilen = [["Lieferant", "Rechnungsnummer", "Rechnungsdatum", "Fällig", "Netto gesamt", "Brutto gesamt", "Anteil Projekt netto", "Kostenart", "Status", "Bezahlt am", "Beleg"]]
        for r in eingang:
            for zu in r.get("zuordnungen") or []:
                if zu.get("project_id") != pid:
                    continue
                beleg = ""
                if r.get("dokument_id"):
                    d = await db().documents.find_one({"id": r["dokument_id"]}, {"_id": 0})
                    if d:
                        beleg = f"08_Eingangsrechnungen/{_name(r.get('rechnungsnummer') or r['id'], 60)}_{_dateiname(d)}"
                        z.datei(beleg, d.get("path") or "", "eingangsrechnungen_belege")
                zeilen.append([r.get("lieferant"), r.get("rechnungsnummer"), r.get("rechnungsdatum"), r.get("faellig_am") or "", r.get("netto"), r.get("brutto"), zu.get("betrag_netto"), zu.get("kostenart"), r.get("status"), r.get("bezahlt_am") or "", beleg])
        z.schreiben("08_Eingangsrechnungen/eingangsrechnungen.csv", _csv(zeilen), "eingangsrechnungen")
    aufmasse = [a async for a in db().aufmasse.find({"firma_id": fid, "project_id": pid}, {"_id": 0}).sort([("messdatum", 1)])]
    if aufmasse:
        z.schreiben("10_Aufmass/aufmasse.csv", _csv([["Datum", "Position", "Bezeichnung", "Raum", "Typ", "Formel", "Menge", "Einheit", "Status", "Erfasst von", "Geprüft von"]] +
                                                  [[a.get("messdatum"), (a.get("position") or {}).get("nr") or "", a.get("bezeichnung"), a.get("raum") or "", a.get("typ"), a.get("formel"), a.get("menge"), a.get("einheit"), a.get("status"), a.get("user_name") or "", a.get("geprueft_von") or ""] for a in aufmasse]), "aufmasse")
        try:
            import aufmass as aufmass_modul
            z.schreiben("10_Aufmass/Aufmassblatt.pdf", pdfs.aufmass_pdf(firma, projekt, aufmasse, list(aufmass_modul.summen_je_position(aufmasse).values())), "aufmassblatt")
        except Exception as exc:  # noqa: BLE001
            z.hinweise.append(f"Aufmaßblatt konnte nicht erzeugt werden: {exc}")
        for a in aufmasse:
            for f_ in a.get("fotos") or []:
                d = await db().documents.find_one({"id": f_.get("id")}, {"_id": 0})
                if d:
                    z.datei(f"10_Aufmass/Fotos/{_name((a.get('position') or {}).get('nr') or 'ohne', 20)}_{_dateiname(d)}", d.get("path") or "", "aufmass_fotos")
    if projekt.get("auftrag") or material or eingang:
        try:
            import material as material_modul
            z.schreiben("09_Nachkalkulation/nachkalkulation.json", _json(await material_modul.nachkalkulation(firma, projekt)), "nachkalkulation")
        except Exception as exc:  # noqa: BLE001
            z.hinweise.append(f"Nachkalkulation konnte nicht erzeugt werden: {exc}")


async def _angebot_schreiben(z: _Zip, ordner: str, a: dict, g: dict, namen_frei: bool) -> None:
    z.schreiben(f"{ordner}/angebot.json", _json(_ohne_pfad(g)), "angebote")
    for d in await _dokumente({"scope": "angebot", "ref_id": g["id"]}):
        z.datei(f"{ordner}/unterlagen/{_dateiname(d)}", d.get("path") or "", "angebot_dokumente")


async def _plattform_daten(z: _Zip, user: dict, firma: dict, projekt: dict, z_pl: dict, namen: dict, rolle: str) -> None:
    fid = firma["id"]
    p = z_pl["projekt"]
    pid = p["id"]
    eigentuemer = bool(z_pl["eigentuemer"])
    firmen_filter = {} if eigentuemer else {"firma_id": fid}
    firmennamen: dict = {}

    async def fname(x: Optional[str]) -> str:
        if x not in firmennamen:
            firmennamen[x] = (await firma_kurz(x))["name"] if x else ""
        return firmennamen[x]

    if not eigentuemer:
        z.schreiben("08_Zusammenarbeit/auftraggeber_projekt.json", _json({"id": pid, "name": p.get("name"), "address": p.get("address"), "auftraggeber": await firma_kurz(p["firma_id"]),
                                                                           "beteiligung": _ohne_pfad(z_pl["beteiligung"] or {})}), "plattform")
    else:
        beteiligungen = [b async for b in db().beteiligungen.find({"project_id": pid}, {"_id": 0, "token": 0})]
        if beteiligungen:
            z.schreiben("08_Zusammenarbeit/beteiligte_firmen.csv", _csv([["Firma", "Gewerk", "Rolle", "Status", "Eingeladen von", "Angenommen am", "Auftragswert aktuell", "Nachträge"]] +
                                                                        [[b.get("firma_name"), b.get("gewerk"), b.get("rolle"), b.get("status"), b.get("eingeladen_von"), b.get("angenommen_at") or "", b.get("auftragswert_aktuell") or "", b.get("nachtraege_summe") or ""] for b in beteiligungen]), "plattform")
    # Aufgaben (+ Fotos), Lieferungen, Mängel (+ Kommentare, Fotos), Meilensteine
    aufgaben = [a async for a in db().aufgaben.find({"project_id": pid, **firmen_filter}, {"_id": 0}).sort([("datum", 1)])]
    if aufgaben:
        zeilen = [["Datum", "Titel", "Firma", "Status", "Bereich", "Von", "Bis", "Priorität", "Beschreibung", "Mitarbeiter"]]
        for a in aufgaben:
            zeilen.append([a.get("datum"), a.get("titel"), await fname(a.get("firma_id")), a.get("status"), a.get("bereich") or "", a.get("start_time") or "", a.get("end_time") or "", a.get("prioritaet") or "", a.get("beschreibung") or "",
                           ", ".join(namen.get(i, "") for i in a.get("mitarbeiter_ids") or []) if a.get("firma_id") == fid else ""])
            await _fotos_schreiben(z, f"08_Zusammenarbeit/Aufgaben_Fotos/{_name(a.get('titel'), 40)}", await _dokumente({"scope": "aufgabe", "ref_id": a["id"]}), namen, "aufgaben_fotos")
        z.schreiben("08_Zusammenarbeit/aufgaben.csv", _csv(zeilen), "aufgaben")
    lieferungen = [l async for l in db().lieferungen.find({"project_id": pid, **firmen_filter}, {"_id": 0}).sort("geplant_am", 1)]
    if lieferungen:
        z.schreiben("08_Zusammenarbeit/lieferungen.csv", _csv([["Geplant am", "Material", "Menge", "Lieferant", "Firma", "Status", "Eingetroffen am", "Entladeort"]] +
                                                              [[l.get("geplant_am"), l.get("material"), l.get("menge") or "", l.get("lieferant") or "", await fname(l.get("firma_id")), l.get("status"), l.get("tatsaechlich_am") or "", l.get("entladeort") or ""] for l in lieferungen]), "lieferungen")
        for l in lieferungen:
            await _fotos_schreiben(z, f"08_Zusammenarbeit/Lieferungen_Fotos/{_name(l.get('material'), 40)}", await _dokumente({"scope": "lieferung", "ref_id": l["id"]}), namen, "lieferungen_fotos")
    maengel = [m async for m in db().maengel.find({"project_id": pid, **firmen_filter}, {"_id": 0}).sort("created_at", 1)]
    if maengel:
        zeilen = [["Gemeldet am", "Beschreibung", "Ort", "Kategorie", "Firma", "Status", "Frist", "Priorität", "Gemeldet von", "Kommentare"]]
        for m in maengel:
            zeilen.append([m.get("created_at"), m.get("beschreibung"), m.get("bereich") or "", m.get("kategorie") or "", await fname(m.get("firma_id")), m.get("status"), m.get("frist") or "", m.get("prioritaet") or "", m.get("gemeldet_von") or "",
                           " | ".join(f"{k.get('user_name')} ({k.get('at', '')[:16]}): {k.get('text')}" for k in m.get("kommentare") or [])])
            await _fotos_schreiben(z, f"08_Zusammenarbeit/Maengel_Fotos/{_name(m.get('beschreibung'), 40)}", await _dokumente({"scope": "mangel", "ref_id": m["id"]}), namen, "maengel_fotos")
        z.schreiben("08_Zusammenarbeit/maengel.csv", _csv(zeilen), "maengel")
    meilensteine = [m async for m in db().meilensteine.find({"project_id": pid}, {"_id": 0}).sort("datum", 1)]
    if meilensteine:
        z.schreiben("08_Zusammenarbeit/meilensteine.csv", _csv([["Datum", "Titel", "Notiz", "Erledigt"]] + [[m.get("datum"), m.get("titel"), m.get("notiz") or "", "ja" if m.get("erledigt") else ""] for m in meilensteine]), "meilensteine")
    # Bautagesberichte als PDF (eigene bzw. alle), geteilte Dokumente
    berichte = [b async for b in db().tagesberichte.find({"project_id": pid, **firmen_filter}, {"_id": 0}).sort("datum", 1)]
    for b in berichte:
        try:
            from dateien import bild_verkleinern
            fotos = []
            for d in await _dokumente({"scope": "tagesbericht", "ref_id": b["id"]}):
                try:
                    fotos.append((bild_verkleinern(d["path"], 700), d.get("note") or d.get("uploaded_by_name") or ""))
                except Exception:  # noqa: BLE001
                    continue
            b["firma_name"] = await fname(b.get("firma_id"))
            b["status_name"] = {"entwurf": "Entwurf", "eingereicht": "Zur Freigabe eingereicht", "freigegeben": "Freigegeben"}.get(b.get("status"), b.get("status"))
            z.schreiben(f"08_Zusammenarbeit/Bautagesberichte/Bautagesbericht_{b.get('datum')}_{_name(b['firma_name'], 30)}.pdf", pdfs.tagesbericht_pdf(b, p, fotos), "tagesberichte")
        except Exception as exc:  # noqa: BLE001
            z.hinweise.append(f"Bautagesbericht {b.get('datum')} konnte nicht erzeugt werden: {exc}")
    if berichte:
        z.schreiben("08_Zusammenarbeit/tagesberichte.json", _json([_ohne_pfad(b) for b in berichte]), "tagesberichte_daten")
    for d in await _dokumente({"scope": "plattform", "ref_id": pid}):
        if eigentuemer or d.get("firma_id") == fid or d.get("freigabe_alle"):
            z.datei(f"08_Zusammenarbeit/Dokumente/{_name(d.get('ordner') or d.get('category') or 'Sonstiges', 60)}/{_dateiname(d)}", d.get("path") or "", "plattform_dokumente")
    # Freigegebene Wochen-Nachweise (nur Eigentümer)
    if eigentuemer:
        freigaben = [f async for f in db().freigaben.find({"project_id": pid}, {"_id": 0}).sort("week_monday", 1)]
        if freigaben:
            zeilen = [["Firma", "Woche ab", "Freigegeben von", "Am", "Datum", "Mitarbeiter", "Beginn", "Ende", "Pause", "Netto (Min)", "Tätigkeit"]]
            for f in freigaben:
                von = f["week_monday"]
                bis = (date.fromisoformat(von) + timedelta(days=6)).isoformat()
                pnamen = await nutzernamen(f["firma_id"])
                async for e in db().entries.find({"firma_id": f["firma_id"], "project_id": f["lokales_project_id"], "date": {"$gte": von, "$lte": bis}}, {"_id": 0}).sort([("date", 1), ("start_time", 1)]):
                    zeilen.append([await fname(f["firma_id"]), von, f.get("freigegeben_von"), f.get("created_at"), e.get("date"), pnamen.get(e.get("user_id") or "", ""), e.get("start_time"), e.get("end_time"), e.get("pause_minutes", 0), e.get("net_minutes", 0), e.get("activity", "")])
            z.schreiben("08_Zusammenarbeit/freigegebene_nachweise.csv", _csv(zeilen), "nachweise")
    # Ausschreibungen (Eigentümer: alle mit allen Angeboten und Vergaben; Beteiligte: nur eigene Angebote und Aufträge)
    if eigentuemer:
        async for a in db().ausschreibungen.find({"project_id": pid, "firma_id": fid}, {"_id": 0}).sort("created_at", 1):
            ordner = f"06_Ausschreibungen/{_name(a.get('nummer') or '')}_{_name(a.get('titel'), 40)}"
            z.schreiben(f"{ordner}/ausschreibung.json", _json(_ohne_pfad(a)), "ausschreibungen")
            for d in await _dokumente({"scope": "ausschreibung", "ref_id": a["id"]}):
                z.datei(f"{ordner}/unterlagen/{_dateiname(d)}", d.get("path") or "", "ausschreibung_dokumente")
            fragen = [f async for f in db().ausschreibung_fragen.find({"ausschreibung_id": a["id"]}, {"_id": 0}).sort("created_at", 1)]
            if fragen:
                z.schreiben(f"{ordner}/rueckfragen.csv", _csv([["Gestellt am", "Firma", "Von", "Position", "Frage", "Antwort", "Beantwortet am", "Öffentlich"]] +
                                                              [[f.get("created_at"), f.get("firma_name") or "", f.get("user_name") or "", f.get("position_nr") or "", f.get("text"), f.get("antwort") or "", f.get("antwort_at") or "", "ja" if f.get("oeffentlich") else ""] for f in fragen]), "rueckfragen")
            async for g in db().angebote.find({"ausschreibung_id": a["id"], "status": {"$nin": ["entwurf"]}}, {"_id": 0}):
                await _angebot_schreiben(z, f"{ordner}/Angebote/{_name(g.get('firma_name'), 40)}", a, g, True)
            async for v in db().vergaben.find({"ausschreibung_id": a["id"]}, {"_id": 0}):
                z.schreiben(f"{ordner}/Vergabe/vergabe_{_name(v.get('firma_name'), 30)}_{v.get('status')}.json", _json(_ohne_pfad(v)), "vergaben")
                for d in await _dokumente({"scope": "vergabe", "ref_id": v["id"]}):
                    z.datei(f"{ordner}/Vergabe/unterlagen/{_dateiname(d)}", d.get("path") or "", "vergabe_dokumente")
    else:
        async for g in db().angebote.find({"firma_id": fid}, {"_id": 0}):
            a = await db().ausschreibungen.find_one({"id": g["ausschreibung_id"], "project_id": pid}, {"_id": 0})
            if not a:
                continue
            from ausschreibung import oeffentliche_ansicht
            ordner = f"07_Angebote/{_name(a.get('nummer') or '')}_{_name(a.get('titel'), 40)}"
            z.schreiben(f"{ordner}/ausschreibung.json", _json(oeffentliche_ansicht(a)), "ausschreibungen")
            for d in await _dokumente({"scope": "ausschreibung", "ref_id": a["id"]}):
                z.datei(f"{ordner}/unterlagen_auftraggeber/{_dateiname(d)}", d.get("path") or "", "ausschreibung_dokumente")
            await _angebot_schreiben(z, f"{ordner}/eigenes_angebot", a, g, True)
            async for v in db().vergaben.find({"ausschreibung_id": a["id"], "firma_id": fid, "status": {"$in": ["mitgeteilt", "angenommen", "abgelehnt_firma"]}}, {"_id": 0}):
                z.schreiben(f"{ordner}/auftrag_{v.get('status')}.json", _json(_ohne_pfad(v)), "vergaben")
                for d in await _dokumente({"scope": "vergabe", "ref_id": v["id"]}):
                    z.datei(f"{ordner}/auftrag_unterlagen/{_dateiname(d)}", d.get("path") or "", "vergabe_dokumente")
    # Nachträge und Abnahmen (eigene bzw. alle) als JSON und PDF
    from routes.abwicklung import ABNAHME_ART_NAMEN, ABNAHME_ERGEBNIS_NAMEN, ABNAHME_STATUS_NAMEN, NACHTRAG_STATUS_NAMEN
    ag = await firma_kurz(p["firma_id"])
    async for n in db().nachtraege.find({"project_id": pid, **firmen_filter}, {"_id": 0}).sort("created_at", 1):
        ordner = f"09_Nachtraege/{_name(n.get('nummer'))}_{_name(n.get('firma_name'), 30)}"
        z.schreiben(f"{ordner}/nachtrag.json", _json(n), "nachtraege")
        try:
            z.schreiben(f"{ordner}/Nachtrag_{_name(n.get('nummer'))}.pdf", pdfs.nachtrag_pdf(n, p, ag, await firma_kurz(n["firma_id"]), NACHTRAG_STATUS_NAMEN.get(n.get("status"), "")), "nachtraege_pdf")
        except Exception as exc:  # noqa: BLE001
            z.hinweise.append(f"Nachtrag {n.get('nummer')} konnte nicht als PDF erzeugt werden: {exc}")
        for d in await _dokumente({"scope": "nachtrag", "ref_id": n["id"]}):
            z.datei(f"{ordner}/unterlagen/{_dateiname(d)}", d.get("path") or "", "nachtrag_dokumente")
    async for a in db().abnahmen.find({"project_id": pid, **firmen_filter}, {"_id": 0}).sort("created_at", 1):
        ordner = f"10_Abnahmen/{_name(a.get('nummer'))}_{_name(a.get('firma_name'), 30)}"
        z.schreiben(f"{ordner}/abnahme.json", _json(a), "abnahmen")
        try:
            z.schreiben(f"{ordner}/Abnahmeprotokoll_{_name(a.get('nummer'))}.pdf", pdfs.abnahme_pdf(a, p, ag, await firma_kurz(a["firma_id"]), ABNAHME_ART_NAMEN.get(a.get("art"), ""), ABNAHME_ERGEBNIS_NAMEN.get(a.get("ergebnis"), ""), ABNAHME_STATUS_NAMEN.get(a.get("status"), "")), "abnahmen_pdf")
        except Exception as exc:  # noqa: BLE001
            z.hinweise.append(f"Abnahme {a.get('nummer')} konnte nicht als PDF erzeugt werden: {exc}")
        for d in await _dokumente({"scope": "abnahme", "ref_id": a["id"]}):
            z.datei(f"{ordner}/unterlagen/{_dateiname(d)}", d.get("path") or "", "abnahme_dokumente")


async def _nachweise(z: _Zip, firma_id: str, projekt: dict, plattform_id: str) -> None:
    """Sicherheitsprotokoll und E-Mail-Nachweise der eigenen Firma, soweit sie das Projekt betreffen."""
    name = projekt.get("name") or ""
    kennungen = {projekt["id"], plattform_id}
    zeilen = [["Zeit", "Wer", "Aktion", "Ziel", "Details"]]
    async for e in db().protokoll.find({"firma_id": firma_id}, {"_id": 0}).sort("created_at", 1).limit(20000):
        details = e.get("details") or {}
        text = json.dumps(details, ensure_ascii=False, default=str)
        if e.get("ziel") == name or any(k in text for k in kennungen) or details.get("projekt") == name or details.get("project_id") in kennungen:
            zeilen.append([e.get("created_at"), e.get("user_name"), e.get("aktion"), e.get("ziel"), text])
    if len(zeilen) > 1:
        z.schreiben("11_Protokoll/protokoll.csv", _csv(zeilen), "protokoll")
    mails = [["Zeit", "An", "Betreff", "Anlass", "Status", "Gesendet am", "Fehler"]]
    async for e in db().email_ausgang.find({"firma_id": firma_id, "project_id": {"$in": list(kennungen)}}, {"_id": 0}).sort("created_at", 1):
        mails.append([e.get("created_at"), e.get("an"), e.get("betreff"), e.get("art"), e.get("status"), e.get("gesendet_at") or "", e.get("fehler") or ""])
    if len(mails) > 1:
        z.schreiben("11_Protokoll/email_nachweise.csv", _csv(mails), "emails")


def _liesmich(firma: dict, projekt: dict, user: dict, rolle: str, z: _Zip, z_pl: Optional[dict]) -> bytes:
    zeilen = [f"PROJEKTAKTE – {projekt.get('name')}", f"Firma: {firma.get('name')}", f"Erstellt am {jetzt_iso()[:16].replace('T', ' ')} von {user.get('name')}",
              f"Rolle im Projekt: {'Eigentümerfirma (Auftraggeber)' if rolle == 'eigentuemer' else 'Beteiligte Firma (verknüpftes Projekt)'}", "",
              "Inhalt (Ordner):", "  00_LIESMICH.txt – diese Übersicht", "  01_Projekt – Stammdaten, Kommentare, Checklisten",
              "  02_Zeiten – alle Zeiteinträge (CSV), Stundennachweis je Monat (PDF), Kunden-Unterschriften", "  03_Fotos – Fotos nach Mitarbeiter und Tag",
              "  04_Dokumente – Unterlagen der Projektakte (mit Versionen)", "  05_Rechnungen – Rechnungen als PDF/A-3 (ZUGFeRD-XML, wenn die Kundendaten vollständig sind)",
              "  06_Ausschreibungen – eigene Ausschreibungen mit allen Angeboten, Rückfragen und Vergaben (nur Auftraggeber)",
              "  07_Angebote – eigene Angebote und erhaltene Aufträge (nur beteiligte Firma)",
              "  08_Zusammenarbeit – Aufgaben, Lieferungen, Mängel, Bautagesberichte (PDF), Meilensteine, geteilte Dokumente, freigegebene Nachweise",
              "  09_Nachtraege – Nachträge mit Freigabe (JSON + PDF)", "  10_Abnahmen – Abnahmeprotokolle (JSON + PDF)",
              "  11_Protokoll – Sicherheitsprotokoll und E-Mail-Nachweise zum Projekt", "",
              "Enthalten: " + (", ".join(f"{k}: {v}" for k, v in sorted(z.zaehler.items())) or "keine Daten"),
              "Plattform-Projekt: " + ("ja" if z_pl is not None else "nein – Bereiche ohne Daten wurden ausgelassen"),
              "Nachrichten/Chat: in dieser Version nicht enthalten (E-Mail-Nachweise siehe 11_Protokoll).", "",
              f"Aufbewahrung: {config.AUFBEWAHRUNG_JAHRE} Jahre (Rechnungen und Buchungsbelege nach § 147 AO / § 257 HGB; Arbeitszeitnachweise mindestens zwei Jahre nach § 17 MiLoG).",
              "Enthält personenbezogene Daten – nur verschlüsselt und mit beschränktem Zugriff aufbewahren."]
    if z.hinweise:
        zeilen += ["", "Hinweise:"] + [f"  - {h}" for h in z.hinweise]
    return "\r\n".join(zeilen).encode("utf-8")
