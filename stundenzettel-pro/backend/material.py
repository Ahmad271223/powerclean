"""Artikelstamm, Materialverbrauch, Eingangsrechnungen und Projekt-Nachkalkulation (Stufe D).

- Artikel: Katalog je Firma (Nummer eindeutig), Einkaufspreis nur mit Recht „kostensaetze“ sichtbar; CSV-Import mit Vorschau und Fehlerzeilen
  (nichts wird stillschweigend ausgelassen).
- Materialverbrauch: Mitarbeiter buchen Mengen auf zugewiesene Projekte (ohne Preise zu sehen); der Einkaufspreis wird beim Buchen als Momentaufnahme
  aus dem Artikel übernommen; das Büro prüft und korrigiert. Lieferung (Termin), Lagereingang und Verbrauch sind getrennte Vorgänge.
- Eingangsrechnungen: Lieferantenrechnung mit Beleg (PDF/Bild/XML), Aufteilung auf Projekte und Kostenarten, Dublettenprüfung; automatisch ausgelesene
  Werte (XRechnung/ZUGFeRD) sind nur ein Vorschlag, erst „geprüft“ zählt in der Nachkalkulation.
- Nachkalkulation: Soll (Auftrag + Kalkulation des Angebots) gegen Ist (freigegebene/gebuchte Stunden × Kostenmodell, Material, Eingangsrechnungen);
  fehlende Lohnsätze, ungeprüfte Stunden, Material oder Rechnungen werden sichtbar gemacht – kein „Gewinn“, solange Kosten fehlen.
"""
from __future__ import annotations

import csv
import io
import re
from datetime import date
from typing import Optional

from lxml import etree

from angebote import rund
from db import db

KOSTENARTEN = {"material": "Material", "fremdleistung": "Fremdleistung", "geraete": "Geräte / Maschinen", "transport": "Transport / Anfahrt",
               "sonstiges": "Sonstige Kosten", "gemeinkosten": "Gemeinkosten (nicht projektbezogen)"}
EINGANG_STATUS = {"erfasst": "Erfasst – zu prüfen", "geprueft": "Geprüft", "bezahlt": "Bezahlt", "storniert": "Storniert"}
SPALTEN = {
    "nummer": ("artikelnummer", "nummer", "artikel-nr", "artikel-nr.", "art.-nr.", "art-nr", "artnr", "sku", "nr"),
    "name": ("bezeichnung", "name", "artikel", "artikelbezeichnung", "kurztext", "titel"),
    "beschreibung": ("beschreibung", "langtext", "text", "details"),
    "einheit": ("einheit", "me", "mengeneinheit", "einh", "einh."),
    "einkaufspreis": ("einkaufspreis", "ek", "ek-preis", "einkauf", "ekp", "listenpreis", "netto ek"),
    "verkaufspreis": ("verkaufspreis", "vk", "vk-preis", "verkauf", "preis", "vkp", "netto vk"),
    "hersteller": ("hersteller", "marke", "fabrikat"),
    "lieferant": ("lieferant", "lieferer", "händler", "haendler"),
    "kategorie": ("kategorie", "warengruppe", "gruppe", "rubrik"),
    "steuer_satz": ("steuersatz", "ust", "mwst", "steuer", "ust-satz", "mwst-satz"),
}


# ---------------------------------------------------------------- CSV-Import Artikel

def zahl(text) -> Optional[float]:
    """Deutsche und englische Zahlen: 1.234,56 / 1234.56 / 12,5 / „12,50 €“; leer → None; Unlesbares → ValueError."""
    if text is None:
        return None
    s = str(text).strip().replace("€", "").replace(" ", "")
    if not s:
        return None
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    elif s.count(".") > 1:
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError as exc:
        raise ValueError(f"„{text}“ ist keine Zahl") from exc


def csv_lesen(roh: bytes) -> tuple[list[str], list[list[str]], str]:
    """Trennzeichen (; , Tab) und Zeichensatz (UTF-8 mit/ohne BOM, sonst Windows-1252) erkennen; Kopfzeile und Zeilen liefern."""
    for enc in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            text = roh.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = roh.decode("latin-1")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    erste = next((z for z in text.split("\n") if z.strip()), "")
    trenner = max((";", ",", "\t", "|"), key=lambda t: erste.count(t))
    if erste.count(trenner) == 0:
        trenner = ";"
    leser = csv.reader(io.StringIO(text), delimiter=trenner, quotechar='"')
    zeilen = [z for z in leser]
    zeilen = [z for z in zeilen if any((c or "").strip() for c in z)]
    if not zeilen:
        return [], [], trenner
    kopf = [c.strip().lower() for c in zeilen[0]]
    return kopf, zeilen[1:], trenner


def spalten_zuordnen(kopf: list[str]) -> dict[str, int]:
    aus = {}
    for i, name in enumerate(kopf):
        n = name.strip().lower()
        for feld, synonyme in SPALTEN.items():
            if feld not in aus and (n == feld or n in synonyme):
                aus[feld] = i
                break
    return aus


def artikel_aus_csv(roh: bytes) -> dict:
    """Vorschau eines Artikelimports (CSV): erkannte Spalten, gültige Zeilen, Fehlerzeilen mit Zeilennummer und Grund."""
    kopf, zeilen, trenner = csv_lesen(roh)
    return artikel_aus_tabelle(kopf, zeilen, trenner)


def artikel_aus_datei(roh: bytes, dateiname: str = "") -> dict:
    """CSV, Excel (.xlsx) oder DATANORM (A-/P-Sätze) → Artikelvorschau mit Fehlerzeilen."""
    import importe
    name = (dateiname or "").lower()
    if name.endswith(".xlsx") or roh[:4] == b"PK\x03\x04":
        return importe.artikel_aus_xlsx(roh)
    if importe.ist_datanorm(roh, dateiname):
        return importe.artikel_aus_datanorm(roh)
    return artikel_aus_csv(roh)


def artikel_aus_tabelle(kopf: list[str], zeilen: list[list[str]], trenner: str = ";") -> dict:
    if not kopf:
        return {"spalten": {}, "trenner": trenner, "artikel": [], "fehler": [{"zeile": 1, "grund": "Die Datei ist leer oder hat keine Kopfzeile."}], "kopf": []}
    sp = spalten_zuordnen(kopf)
    artikel, fehler = [], []
    if "nummer" not in sp or "name" not in sp:
        fehler.append({"zeile": 1, "grund": "Kopfzeile ohne „Artikelnummer“ oder „Bezeichnung“ – bitte die Spalten entsprechend benennen."})
        return {"spalten": sp, "trenner": trenner, "artikel": [], "fehler": fehler, "kopf": kopf}

    def wert(z: list[str], feld: str) -> str:
        i = sp.get(feld)
        return (z[i] if i is not None and i < len(z) else "").strip()

    gesehen = set()
    for nr, z in enumerate(zeilen, start=2):
        nummer, name = wert(z, "nummer"), wert(z, "name")
        if not nummer or not name:
            fehler.append({"zeile": nr, "grund": "Artikelnummer oder Bezeichnung fehlt."})
            continue
        if nummer.lower() in gesehen:
            fehler.append({"zeile": nr, "grund": f"Artikelnummer {nummer} kommt in der Datei mehrfach vor."})
            continue
        gesehen.add(nummer.lower())
        try:
            a = {"nummer": nummer[:60], "name": name[:200], "beschreibung": wert(z, "beschreibung")[:4000], "einheit": (wert(z, "einheit") or "Stk.")[:20],
                 "einkaufspreis": zahl(wert(z, "einkaufspreis")), "verkaufspreis": zahl(wert(z, "verkaufspreis")), "hersteller": wert(z, "hersteller")[:120],
                 "lieferant": wert(z, "lieferant")[:120], "kategorie": wert(z, "kategorie")[:80], "steuer_satz": zahl(wert(z, "steuer_satz"))}
        except ValueError as exc:
            fehler.append({"zeile": nr, "grund": str(exc)})
            continue
        for f in ("einkaufspreis", "verkaufspreis"):
            if a[f] is not None and a[f] < 0:
                fehler.append({"zeile": nr, "grund": f"{f} ist negativ."})
                break
        else:
            artikel.append(a)
    return {"spalten": sp, "trenner": trenner, "artikel": artikel, "fehler": fehler, "kopf": kopf}


def artikel_fuer_nutzer(a: dict, ek_sehen: bool) -> dict:
    aus = {k: v for k, v in a.items() if k != "_id"}
    if not ek_sehen:
        aus.pop("einkaufspreis", None)
    return aus


# ---------------------------------------------------------------- E-Rechnung einlesen (nur Vorschlag)

NS = {"rsm": "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100",
      "ram": "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100",
      "udt": "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100"}


def _datum102(s: Optional[str]) -> Optional[str]:
    s = (s or "").strip()
    if re.fullmatch(r"\d{8}", s):
        return f"{s[:4]}-{s[4:6]}-{s[6:]}"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return s
    return None


def erechnung_auslesen(xml: bytes) -> Optional[dict]:
    """Aus einer CII-XML (XRechnung/ZUGFeRD) Lieferant, Nummer, Datum, Fälligkeit und Beträge lesen – als Vorschlag, der geprüft wird."""
    try:
        wurzel = etree.fromstring(xml)
    except etree.XMLSyntaxError:
        return None
    if etree.QName(wurzel).localname != "CrossIndustryInvoice":
        return None

    def t(pfad: str) -> Optional[str]:
        el = wurzel.find(pfad, NS)
        return el.text.strip() if el is not None and el.text else None

    summe = "rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeSettlement/ram:SpecifiedTradeSettlementHeaderMonetarySummation/"
    aus = {"lieferant": t("rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeAgreement/ram:SellerTradeParty/ram:Name"),
           "rechnungsnummer": t("rsm:ExchangedDocument/ram:ID"),
           "rechnungsdatum": _datum102(t("rsm:ExchangedDocument/ram:IssueDateTime/udt:DateTimeString")),
           "faellig_am": _datum102(t("rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeSettlement/ram:SpecifiedTradePaymentTerms/ram:DueDateDateTime/udt:DateTimeString")),
           "netto": None, "ust": None, "brutto": None}
    for feld, tag in (("netto", "ram:TaxBasisTotalAmount"), ("ust", "ram:TaxTotalAmount"), ("brutto", "ram:GrandTotalAmount")):
        try:
            v = t(summe + tag)
            aus[feld] = round(float(v), 2) if v is not None else None
        except ValueError:
            aus[feld] = None
    lieferant_ustid = t("rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeAgreement/ram:SellerTradeParty/ram:SpecifiedTaxRegistration/ram:ID")
    if lieferant_ustid:
        aus["lieferant_ustid"] = lieferant_ustid
    aus["quelle"] = "xrechnung"
    return aus


def zugferd_xml_aus_pdf(pdf: bytes) -> Optional[bytes]:
    """Eingebettete factur-x.xml / zugferd-invoice.xml aus einem PDF/A-3 lesen."""
    try:
        import pikepdf
        with pikepdf.open(io.BytesIO(pdf)) as doc:
            for name, datei in doc.attachments.items():
                if name.lower() in ("factur-x.xml", "zugferd-invoice.xml", "xrechnung.xml"):
                    return datei.get_file().read_bytes()
    except Exception:  # noqa: BLE001 – kein Anhang, kaputtes PDF: dann eben kein Vorschlag
        return None
    return None


def dublette_schluessel(lieferant: str, rechnungsnummer: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (lieferant or "").lower())[:40] + "|" + re.sub(r"[^a-z0-9]", "", (rechnungsnummer or "").lower())


# ---------------------------------------------------------------- Kostenmodell und Nachkalkulation

def _dz(x) -> str:
    """Zahl deutsch formatiert für Hinweistexte (1.234,56)."""
    return f"{rund(x):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def kostensatz_mitarbeiter(u: dict, firma_k: dict) -> tuple[Optional[float], str]:
    """Kosten je Arbeitsstunde eines Mitarbeiters: Stundenlohn (oder Monatsgehalt ÷ Monatsstunden) plus Lohnnebenkosten; sonst der
    Kalkulationsstundensatz der Firma; sonst unbekannt (wird ausgewiesen, nicht geraten)."""
    from lohn import lohndaten_lesen
    nk = 1 + float(firma_k.get("lohnnebenkosten_prozent") or 0) / 100
    l = lohndaten_lesen(u) if u.get("lohndaten") else {}
    if l.get("hourly_wage"):
        return rund(float(l["hourly_wage"]) * nk), "stundenlohn"
    if l.get("monthly_salary") and float(u.get("weekly_hours") or 0) > 0:
        return rund(float(l["monthly_salary"]) / (float(u["weekly_hours"]) * 4.33) * nk), "monatsgehalt"
    if float(firma_k.get("stundensatz") or 0) > 0:
        return rund(float(firma_k["stundensatz"])), "firmensatz"
    return None, "fehlt"


async def nachkalkulation(firma: dict, projekt: dict) -> dict:
    """Soll-Ist je Kostenart für ein Projekt der eigenen Firma. Zeiten: freigegebene Zeiten gelten als geprüft, andere als „ungeprüft“ und werden
    getrennt ausgewiesen; die Kosten rechnen mit allen gebuchten Zeiten, die Unvollständigkeit wird benannt."""
    from angebote import firmen_kalkulation, kalkulation_angebot
    from zeiten import eintrag_minuten, eintrag_satz
    fid, pid = firma["id"], projekt["id"]
    firma_k = firmen_kalkulation(firma)
    firma_k["lohnnebenkosten_prozent"] = float((firma.get("kalkulation") or {}).get("lohnnebenkosten_prozent") or 0)
    auftrag = projekt.get("auftrag") or {}
    hinweise: list[str] = []

    # Soll: Auftrag, freigegebene Nachträge, Kalkulation des angenommenen Angebots, geplante Einsätze
    auftragswert = auftrag.get("netto") if auftrag else (float(projekt.get("pauschale_netto") or 0) or None)
    nachtraege = 0.0
    async for n in db().nachtraege.find({"firma_id": fid, "status": "freigegeben", "$or": [{"project_id": pid}, {"project_id": (projekt.get("verknuepft") or {}).get("project_id") or "-"}]}, {"_id": 0, "betrag_netto": 1}):
        nachtraege += float(n.get("betrag_netto") or 0)
    plan = {"stunden": 0.0, "lohn": 0.0, "material": 0.0, "fremdleistung": 0.0, "geraete": 0.0, "transport": 0.0, "sonstiges": 0.0, "gemeinkosten": 0.0, "risiko": 0.0, "selbstkosten": 0.0, "direkt": 0.0, "quelle": None}
    angebot = None
    if auftrag.get("angebot_id"):
        angebot = await db().kundenangebote.find_one({"id": auftrag["angebot_id"], "firma_id": fid}, {"_id": 0})
    if angebot:
        k = kalkulation_angebot(angebot, firma)
        if k.get("kalkuliert"):
            plan.update({"stunden": k["stunden"], "lohn": k["lohn"], "material": k["material_ek"], "fremdleistung": k["fremd"], "geraete": k["geraete"], "transport": k["transport"],
                         "sonstiges": k["sonstige"], "gemeinkosten": k["gemeinkosten"], "risiko": k["risiko"], "selbstkosten": k["selbstkosten"], "direkt": k["direkt"],
                         "quelle": f"Kalkulation Angebot {angebot.get('nummer')}", "vollstaendig": k.get("vollstaendig", False)})
            if not k.get("vollstaendig"):
                hinweise.append("Die Angebotskalkulation ist unvollständig – Plankosten sind nur teilweise belegt.")
        else:
            hinweise.append(f"Das Angebot {angebot.get('nummer')} hat keine interne Kalkulation – keine Plankosten.")
    elif auftragswert:
        hinweise.append("Kein Angebot mit Kalkulation hinterlegt – Plankosten fehlen, nur der Auftragswert ist bekannt.")
    else:
        hinweise.append("Kein Auftragswert (weder Auftrag aus Angebot noch Pauschale) – Deckungsbeitrag nicht berechenbar.")
    plan_einsatz_minuten = 0
    async for e in db().einsaetze.find({"firma_id": fid, "project_id": pid, "status": "geplant"}, {"_id": 0, "planned_minutes": 1}):
        plan_einsatz_minuten += int(e.get("planned_minutes") or 0)

    # Ist: Zeiten × Kostenmodell
    nutzer = {}
    async for u in db().users.find({"firma_id": fid}, {"_id": 0, "id": 1, "name": 1, "lohndaten": 1, "weekly_hours": 1}):
        nutzer[u["id"]] = u
    minuten_gesamt = minuten_frei = 0
    personal_ist = 0.0
    ohne_satz_minuten = 0
    abrechenbar = 0.0
    je_person: dict[str, dict] = {}
    modelle = set()
    async for e in db().entries.find({"firma_id": fid, "project_id": pid}, {"_id": 0}):
        m = eintrag_minuten(e)
        minuten_gesamt += m
        if e.get("freigabe"):
            minuten_frei += m
        abrechenbar += m / 60 * eintrag_satz(e, projekt, firma)
        u = nutzer.get(e.get("user_id")) or {}
        satz, modell = kostensatz_mitarbeiter(u, firma_k)
        modelle.add(modell)
        p = je_person.setdefault(e.get("user_id") or "?", {"name": u.get("name") or "?", "minuten": 0, "kosten": 0.0, "modell": modell, "ohne_satz": False})
        p["minuten"] += m
        if satz is None:
            ohne_satz_minuten += m
            p["ohne_satz"] = True
        else:
            kosten = rund(m / 60 * satz)
            personal_ist += kosten
            p["kosten"] = rund(p["kosten"] + kosten)
    if ohne_satz_minuten:
        hinweise.append(f"{_dz(ohne_satz_minuten / 60)} Stunden ohne Lohnsatz (weder Lohndaten noch Kalkulationsstundensatz) – Personalkosten unvollständig.")
    if minuten_gesamt and minuten_frei < minuten_gesamt:
        hinweise.append(f"{_dz((minuten_gesamt - minuten_frei) / 60)} von {_dz(minuten_gesamt / 60)} Stunden sind noch nicht freigegeben (Plantafel → Zeiten prüfen).")

    # Ist: Material
    material_ist = material_ungeprueft = 0.0
    material_anzahl = 0
    async for v in db().materialverbrauch.find({"firma_id": fid, "project_id": pid}, {"_id": 0}):
        material_anzahl += 1
        kosten = float(v.get("kosten") or 0)
        if v.get("status") == "geprueft":
            material_ist += kosten
        else:
            material_ungeprueft += kosten
            if v.get("kosten") is None:
                hinweise.append(f"Materialbuchung „{v.get('bezeichnung')}“ ohne Einkaufspreis – bitte prüfen und bepreisen.")
    if material_ungeprueft:
        hinweise.append(f"Materialverbrauch von {_dz(material_ungeprueft)} € ist noch ungeprüft und zählt noch nicht.")

    # Ist: Eingangsrechnungen (nur geprüft/bezahlt), Aufteilung auf dieses Projekt
    kostenarten_ist = {k: 0.0 for k in KOSTENARTEN}
    kostenarten_ist["material"] = material_ist
    rechnungen_offen = 0
    rechnungen = []
    async for r in db().eingangsrechnungen.find({"firma_id": fid, "zuordnungen.project_id": pid}, {"_id": 0}):
        anteil = sum(float(z.get("betrag_netto") or 0) for z in r.get("zuordnungen") or [] if z.get("project_id") == pid)
        if r.get("status") in ("geprueft", "bezahlt"):
            for z in r.get("zuordnungen") or []:
                if z.get("project_id") == pid:
                    art = z.get("kostenart") if z.get("kostenart") in KOSTENARTEN else "sonstiges"
                    kostenarten_ist[art] = rund(kostenarten_ist[art] + float(z.get("betrag_netto") or 0))
        elif r.get("status") == "erfasst":
            rechnungen_offen += 1
        rechnungen.append({"id": r["id"], "lieferant": r.get("lieferant"), "rechnungsnummer": r.get("rechnungsnummer"), "rechnungsdatum": r.get("rechnungsdatum"),
                           "status": r.get("status"), "anteil_netto": rund(anteil)})
    if rechnungen_offen:
        hinweise.append(f"{rechnungen_offen} Eingangsrechnung(en) zu diesem Projekt sind noch nicht geprüft und zählen noch nicht.")

    direkt_ist = rund(personal_ist + sum(v for k, v in kostenarten_ist.items() if k != "gemeinkosten"))
    gk_prozent = float(firma_k.get("gemeinkosten_prozent") or 0)
    gemeinkosten_ist = rund(direkt_ist * gk_prozent / 100)
    ist_gesamt = rund(direkt_ist + gemeinkosten_ist + kostenarten_ist["gemeinkosten"])
    vollstaendig = not ohne_satz_minuten and not material_ungeprueft and not rechnungen_offen and minuten_frei == minuten_gesamt
    soll_gesamt = plan["selbstkosten"] if plan.get("quelle") else None
    umsatz = rund(float(auftragswert or 0) + nachtraege) if auftragswert else None
    kostenarten = [
        {"art": "personal", "name": "Personal (Stunden × Kostensatz)", "plan": plan["lohn"] if plan.get("quelle") else None, "ist": rund(personal_ist)},
        {"art": "material", "name": "Material", "plan": plan["material"] if plan.get("quelle") else None, "ist": rund(kostenarten_ist["material"])},
        {"art": "fremdleistung", "name": "Fremdleistungen", "plan": plan["fremdleistung"] if plan.get("quelle") else None, "ist": rund(kostenarten_ist["fremdleistung"])},
        {"art": "geraete", "name": "Geräte / Maschinen", "plan": plan["geraete"] if plan.get("quelle") else None, "ist": rund(kostenarten_ist["geraete"])},
        {"art": "transport", "name": "Transport / Anfahrt", "plan": plan["transport"] if plan.get("quelle") else None, "ist": rund(kostenarten_ist["transport"])},
        {"art": "sonstiges", "name": "Sonstige Kosten", "plan": plan["sonstiges"] if plan.get("quelle") else None, "ist": rund(kostenarten_ist["sonstiges"])},
        {"art": "gemeinkosten", "name": f"Gemeinkosten ({gk_prozent:g} % + direkt zugeordnete)", "plan": rund(plan["gemeinkosten"] + plan["risiko"]) if plan.get("quelle") else None, "ist": rund(gemeinkosten_ist + kostenarten_ist["gemeinkosten"])},
    ]
    return {
        "projekt": {"id": pid, "name": projekt.get("name"), "abrechnungsart": projekt.get("abrechnungsart_projekt") or "stunden", "auftrag": auftrag or None},
        "auftragswert_netto": auftragswert, "nachtraege_freigegeben": rund(nachtraege), "umsatz_vereinbart": umsatz,
        "abrechenbar_stunden_netto": rund(abrechenbar) if (projekt.get("abrechnungsart_projekt") or "stunden") == "stunden" else None,
        "stunden": {"plan_kalkulation": plan["stunden"] if plan.get("quelle") else None, "plan_einsaetze": rund(plan_einsatz_minuten / 60), "gebucht": rund(minuten_gesamt / 60),
                    "freigegeben": rund(minuten_frei / 60), "ungeprueft": rund((minuten_gesamt - minuten_frei) / 60), "ohne_lohnsatz": rund(ohne_satz_minuten / 60)},
        "kostenmodell": {"lohnnebenkosten_prozent": firma_k["lohnnebenkosten_prozent"], "firmensatz": firma_k.get("stundensatz"), "verwendet": sorted(modelle),
                         "text": "Stundenlohn bzw. Monatsgehalt ÷ Monatsstunden aus den Lohndaten, jeweils plus Lohnnebenkosten; ohne Lohndaten der Kalkulationsstundensatz der Firma."},
        "plan": {**plan, "gesamt": soll_gesamt}, "ist": {"personal": rund(personal_ist), **{k: rund(v) for k, v in kostenarten_ist.items()}, "gemeinkosten_zuschlag": gemeinkosten_ist,
                                                         "direkt": direkt_ist, "gesamt": ist_gesamt, "material_ungeprueft": rund(material_ungeprueft), "material_buchungen": material_anzahl},
        "abweichung": rund(ist_gesamt - soll_gesamt) if soll_gesamt is not None else None,
        "deckungsbeitrag": {"erwartet": rund(umsatz - plan["direkt"]) if (umsatz is not None and plan.get("quelle")) else None,
                            "aktuell": rund(umsatz - direkt_ist) if umsatz is not None else None,
                            "ergebnis": rund(umsatz - ist_gesamt) if (umsatz is not None and vollstaendig) else None},
        "kostenarten": kostenarten, "je_person": sorted(je_person.values(), key=lambda p: -p["minuten"]), "eingangsrechnungen": rechnungen,
        "vollstaendig": vollstaendig, "hinweise": hinweise, "stand": date.today().isoformat(),
    }
