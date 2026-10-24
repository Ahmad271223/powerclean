"""E-Rechnung nach EN 16931 aus den gespeicherten Rechnungsdaten.

- XRechnung 3.0 (Standard der öffentlichen Auftraggeber, Pflicht bei Bund/Ländern/Kommunen): reines XML in der
  Syntax UN/CEFACT CII mit der Kennung urn:xeinkauf.de:kosit:xrechnung_3.0.
- ZUGFeRD 2.x / Factur-X, Profil EN 16931: dieselbe CII-XML (Kennung urn:cen.eu:en16931:2017) eingebettet in ein
  PDF/A-3 (siehe pdfbasis.pdfa3_mit_xml). Für Geschäftskunden, die eine lesbare Rechnung plus Datensatz wollen.

Beide Formate erfüllen die E-Rechnungspflicht (§ 14 UStG: Empfang seit 2025, Ausstellung ab 2027 bei über 800.000 €
Vorjahresumsatz, ab 2028 für alle; Kleinbeträge bis 250 € brutto ausgenommen).

Vorgehen: `rechnungsdaten()` normalisiert Firma/Kunde/Projekt/Rechnung, `pruefen()` nennt fehlende Pflichtangaben
in Klartext (bevor etwas erzeugt wird), `cii_xml()` baut die XML, `rechnung_pdf()` die lesbare Rechnung (eingebettete Schrift).
"""
from __future__ import annotations

import base64
import io
import re
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from lxml import etree
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfgen import canvas

from pdfbasis import ERZEUGER, SCHRIFT, SCHRIFT_FETT, schrift_registrieren

NS = {
    "rsm": "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100",
    "ram": "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100",
    "udt": "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100",
    "qdt": "urn:un:unece:uncefact:data:standard:QualifiedDataType:100",
}
XRECHNUNG_KENNUNG = "urn:cen.eu:en16931:2017#compliant#urn:xeinkauf.de:kosit:xrechnung_3.0"
ZUGFERD_KENNUNG = "urn:cen.eu:en16931:2017"
PROZESS_KENNUNG = "urn:fdc:peppol.eu:2017:poacc:billing:01:1.0"
MONATE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"]
# Mengeneinheiten der Zusatzpositionen → UN/ECE Rec. 20 Codes
EINHEITEN = {"std": "HUR", "std.": "HUR", "stunde": "HUR", "stunden": "HUR", "h": "HUR", "tag": "DAY", "tage": "DAY", "kg": "KGM",
             "l": "LTR", "liter": "LTR", "m²": "MTK", "qm": "MTK", "m": "MTR", "km": "KMT", "monat": "MON", "pauschale": "LS"}
PROFILE = {"xrechnung": "XRechnung 3.0 (XML)", "zugferd": "ZUGFeRD 2.x / Factur-X EN 16931 (PDF/A-3)"}


# ---------- Daten zusammenstellen ----------

def _geld(x) -> str:
    return str(Decimal(str(x or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _menge(x) -> str:
    return str(Decimal(str(x or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _datum102(iso: str) -> str:
    return iso.replace("-", "")[:8]


def _iban(s: str) -> str:
    return re.sub(r"\s", "", s or "").upper()


def adresse_aus_text(text: str) -> dict:
    """Freitext-Adresse eines Projekts ('Straße 1\\n12345 Ort') in Straße/PLZ/Ort zerlegen."""
    zeilen = [z.strip() for z in (text or "").replace("\r", "").split("\n") if z.strip()]
    aus = {"street": "", "zip_code": "", "city": ""}
    if not zeilen:
        return aus
    m = re.match(r"^(\d{4,5})\s+(.+)$", zeilen[-1])
    if m:
        aus["zip_code"], aus["city"] = m.group(1), m.group(2)
        aus["street"] = ", ".join(zeilen[:-1])
    elif len(zeilen) >= 2:
        aus["street"], aus["city"] = ", ".join(zeilen[:-1]), zeilen[-1]
    else:
        aus["city"] = zeilen[0]
    return aus


def einheit_code(einheit: str) -> str:
    return EINHEITEN.get((einheit or "").strip().lower(), "C62")


def rechnungsdaten(firma: dict, projekt: dict, kunde: dict | None, rechnung: dict) -> dict:
    """Alles, was XML und PDF brauchen, in einer flachen Struktur (Beträge als float, Codes vorberechnet)."""
    verkaeufer = {
        "name": (firma.get("name") or "").strip(), "street": (firma.get("street") or "").strip(), "zip_code": (firma.get("zip_code") or "").strip(),
        "city": (firma.get("city") or "").strip(), "country": (firma.get("country") or "DE").upper(),
        "vat_id": re.sub(r"\s", "", firma.get("vat_id") or ""), "tax_number": (firma.get("tax_number") or "").strip(),
        "contact_name": (firma.get("owner") or firma.get("name") or "").strip(), "phone": (firma.get("phone") or "").strip(),
        "email": (firma.get("email") or "").strip(), "iban": _iban(firma.get("iban")), "bic": re.sub(r"\s", "", firma.get("bic") or "").upper(),
        "bank_name": (firma.get("bank_name") or "").strip(), "website": (firma.get("website") or "").strip(),
    }
    if kunde:
        kaeufer = {"name": kunde.get("name") or "", "street": kunde.get("street") or "", "zip_code": kunde.get("zip_code") or "", "city": kunde.get("city") or "",
                   "country": (kunde.get("country") or "DE").upper(), "email": kunde.get("email") or "", "leitweg_id": (kunde.get("leitweg_id") or "").strip(),
                   "customer_number": kunde.get("customer_number") or "", "vat_id": re.sub(r"\s", "", kunde.get("vat_id") or ""), "contact": kunde.get("contact") or ""}
    else:
        kaeufer = {"name": projekt.get("customer_name") or "", **adresse_aus_text(projekt.get("customer_address") or ""), "country": "DE", "email": "",
                   "leitweg_id": "", "customer_number": "", "vat_id": "", "contact": ""}
    kaeufer = {k: (v.strip() if isinstance(v, str) else v) for k, v in kaeufer.items()}

    art = rechnung.get("art") or "monat"
    if art == "monat":
        jahr, monat = int(rechnung["year"]), int(rechnung["month"])
        von = date(jahr, monat, 1)
        bis = (date(jahr + 1, 1, 1) if monat == 12 else date(jahr, monat + 1, 1)) - timedelta(days=1)
    else:
        # Auftrags-, Abschlags-, Schluss-, Storno- und Gutschriftsrechnungen: Leistungszeitraum aus den Feldern, sonst das Rechnungsdatum
        _rd = (rechnung.get("invoice_date") or date.today().isoformat())[:10]
        von = date.fromisoformat((rechnung.get("leistung_von") or _rd)[:10])
        bis = date.fromisoformat((rechnung.get("leistung_bis") or _rd)[:10])
        monat = bis.month
        jahr = bis.year
    rdatum = date.fromisoformat((rechnung.get("invoice_date") or date.today().isoformat())[:10])
    zahlungsziel = int(firma.get("payment_days") or 14)
    faellig = rdatum + timedelta(days=zahlungsziel)

    zeilen = []
    for p in rechnung.get("positions") or []:
        name = f"{p.get('service') or 'Reinigungsarbeiten'} KW {p.get('week')} ({_de(p.get('from'))} – {_de(p.get('to'))})"
        zeilen.append({"name": name, "quantity": float(p.get("hours") or 0), "unit": "HUR", "unit_label": "Std.", "price": float(p.get("rate") or 0),
                       "amount": float(p.get("amount") or 0), "from": p.get("from"), "to": p.get("to")})
    for x in rechnung.get("extras") or []:
        zeilen.append({"name": x.get("text") or "Zusatzposition", "quantity": float(x.get("quantity") or 0), "unit": einheit_code(x.get("unit")),
                       "unit_label": x.get("unit") or "", "price": float(x.get("unit_price") or 0), "amount": float(x.get("amount") or 0), "from": None, "to": None})

    netto = round(float(rechnung.get("net") or 0), 2)
    ust_satz = float(rechnung.get("vat_rate") or 0)
    ust = round(float(rechnung.get("vat") or 0), 2)
    brutto = round(float(rechnung.get("gross") or 0), 2)
    umkehr = bool(rechnung.get("reverse_charge"))
    klein = bool(firma.get("small_business")) and not umkehr
    if umkehr:
        steuer = {"category": "AE", "rate": 0.0, "exemption_code": "VATEX-EU-AE", "exemption_text": "Steuerschuldnerschaft des Leistungsempfängers (§ 13b UStG)"}
    elif klein:
        steuer = {"category": "E", "rate": 0.0, "exemption_code": "", "exemption_text": "Keine Umsatzsteuer gemäß § 19 UStG (Kleinunternehmerregelung)"}
    else:
        steuer = {"category": "S", "rate": ust_satz, "exemption_code": "", "exemption_text": ""}

    if art == "monat":
        notizen = [t for t in [(firma.get("invoice_text") or "").strip(), f"Leistungszeitraum {MONATE[monat - 1]} {jahr}. Die Stundenzettel der Kalenderwochen liegen dieser Rechnung bei."] if t]
    else:
        notizen = [t for t in [(rechnung.get("rechnungstext") or "").strip(),
                               f"Leistungszeitraum {_de(von.isoformat())} – {_de(bis.isoformat())}." if rechnung.get("leistung_von") or rechnung.get("leistung_bis") else "",
                               f"Bezug: Auftrag {rechnung['auftrag_nummer']}." if rechnung.get("auftrag_nummer") else "",
                               f"Storno der Rechnung {rechnung['storno_von']['number']} vom {_de(rechnung['storno_von'].get('invoice_date'))}." if rechnung.get("storno_von") else "",
                               f"Bereits gestellte Abschlagsrechnungen sind abgezogen; daraus noch offen: {rechnung['offen_aus_abschlaegen_brutto']:,.2f} € brutto.".replace(",", "X").replace(".", ",").replace("X", ".") if art == "schluss" and float(rechnung.get("offen_aus_abschlaegen_brutto") or 0) > 0 else ""] if t]
    if art == "gutschrift":   # EN 16931: Gutschrift (381) mit positiven Beträgen
        for z in zeilen:
            z["price"], z["amount"] = abs(z["price"]), abs(z["amount"])
        netto, ust, brutto = abs(netto), abs(ust), abs(brutto)
    from rechnungslauf import ARTEN as _ARTEN, TYPECODES as _TYPECODES
    vorherige = [{"nummer": v.get("number"), "datum": v.get("invoice_date")} for v in (rechnung.get("_vorherige_belege") or [])]
    if rechnung.get("storno_von"):
        vorherige.append({"nummer": rechnung["storno_von"].get("number"), "datum": rechnung["storno_von"].get("invoice_date")})
    return {
        "verkaeufer": verkaeufer, "kaeufer": kaeufer, "nummer": rechnung.get("number") or "", "datum": rdatum.isoformat(), "faellig": faellig.isoformat(),
        "zahlungsziel_tage": zahlungsziel, "von": von.isoformat(), "bis": bis.isoformat(), "monat_text": f"{MONATE[monat - 1]} {jahr}", "projekt": projekt.get("name") or "",
        "projekt_adresse": projekt.get("address") or "", "waehrung": "EUR", "zeilen": zeilen, "netto": netto, "ust_satz": ust_satz, "ust": ust, "brutto": brutto,
        "steuer": steuer, "notizen": notizen, "gesamt_minuten": int(rechnung.get("total_minutes") or 0), "status": rechnung.get("status") or "offen",
        "logo": firma.get("logo") or "", "stempel": firma.get("stamp") if firma.get("stamp_on_invoice") else "", "stempel_scale": int(firma.get("stamp_scale") or 100),
        "stempel_w": firma.get("stamp_w"), "stempel_h": firma.get("stamp_h"), "inhaber": firma.get("owner") or "",
        "art": art, "art_name": _ARTEN.get(art, "Rechnung"), "typecode": _TYPECODES.get(art, "380"), "vorherige": vorherige,
        "bezahlt_betrag": float(rechnung.get("bezahlt_betrag") or 0), "mahngebuehren": float(rechnung.get("mahngebuehren") or 0),
    }


def _de(iso: str | None) -> str:
    if not iso:
        return ""
    j, m, t = iso[:10].split("-")
    return f"{t}.{m}.{j}"


# ---------- Prüfung ----------

def pruefen(daten: dict, profil: str) -> dict:
    """Fehlende Pflichtangaben in Klartext. `fehlt` blockiert die Erzeugung, `hinweise` nicht."""
    v, k = daten["verkaeufer"], daten["kaeufer"]
    fehlt, hinweise = [], []
    if not v["name"]:
        fehlt.append("Firmenname (Firma → Firmendaten)")
    if not (v["street"] and v["zip_code"] and v["city"]):
        fehlt.append("vollständige Firmenanschrift mit Straße, PLZ und Ort (Firma → Firmendaten)")
    if not (v["vat_id"] or v["tax_number"]):
        fehlt.append("USt-IdNr. oder Steuernummer der Firma (Firma → Rechnungsdaten)")
    if not k["name"]:
        fehlt.append("Name des Kunden")
    if not (k["zip_code"] and k["city"]):
        fehlt.append("PLZ und Ort des Kunden (Kunde bearbeiten; bei freiem Projektkunden: Adresse als „Straße“ Zeilenumbruch „PLZ Ort“)")
    if not daten["zeilen"]:
        fehlt.append("mindestens eine Rechnungsposition")
    if not daten["nummer"]:
        fehlt.append("Rechnungsnummer")
    if profil == "xrechnung":
        if not k["leitweg_id"]:
            fehlt.append("Leitweg-ID des Auftraggebers (Kunde bearbeiten → E-Rechnung); öffentliche Stellen teilen sie bei Auftrag mit")
        if not v["email"]:
            fehlt.append("E-Mail der Firma (Firma → Firmendaten)")
        if not v["phone"]:
            fehlt.append("Telefon der Firma (Firma → Firmendaten)")
        if not v["contact_name"]:
            fehlt.append("Ansprechpartner (Inhaber/Geschäftsführer in den Firmendaten)")
        if not k["email"]:
            fehlt.append("E-Mail des Kunden (Kunde bearbeiten)")
        if not v["iban"]:
            fehlt.append("IBAN der Firma (Firma → Rechnungsdaten)")
    else:
        if not v["iban"]:
            hinweise.append("Ohne IBAN enthält die Rechnung keine Zahlungsdaten.")
        if not k["email"]:
            hinweise.append("E-Mail des Kunden fehlt – zum Versand der Rechnung sinnvoll.")
    if v["iban"] and not re.fullmatch(r"[A-Z]{2}[0-9]{2}[A-Z0-9]{11,30}", v["iban"]):
        fehlt.append("IBAN der Firma hat kein gültiges Format")
    if daten["status"] == "storniert":
        fehlt.append("Rechnung ist storniert")
    if daten["steuer"]["category"] == "S" and daten["ust_satz"] <= 0:
        hinweise.append("Umsatzsteuersatz ist 0 % – prüfen, ob Kleinunternehmer (§ 19) oder § 13b gemeint ist.")
    return {"profil": profil, "bezeichnung": PROFILE[profil], "ok": not fehlt, "fehlt": fehlt, "hinweise": hinweise}


# ---------- XML (UN/CEFACT CII, EN 16931) ----------

def _el(parent, tag: str, text=None, **attrs):
    prefix, name = tag.split(":")
    e = etree.SubElement(parent, f"{{{NS[prefix]}}}{name}")
    for k, v in attrs.items():
        e.set(k, str(v))
    if text is not None:
        e.text = str(text)
    return e


def _datumselement(parent, tag: str, iso: str):
    e = _el(parent, tag)
    _el(e, "udt:DateTimeString", _datum102(iso), format="102")
    return e


def _partei(parent, tag: str, p: dict, kontakt: bool, kundennummer: str = ""):
    e = _el(parent, tag)
    if kundennummer:
        _el(e, "ram:ID", kundennummer)
    _el(e, "ram:Name", p["name"])
    if kontakt and (p.get("contact_name") or p.get("phone") or p.get("email")):
        c = _el(e, "ram:DefinedTradeContact")
        if p.get("contact_name"):
            _el(c, "ram:PersonName", p["contact_name"])
        if p.get("phone"):
            _el(_el(c, "ram:TelephoneUniversalCommunication"), "ram:CompleteNumber", p["phone"])
        if p.get("email"):
            _el(_el(c, "ram:EmailURIUniversalCommunication"), "ram:URIID", p["email"])
    a = _el(e, "ram:PostalTradeAddress")
    if p.get("zip_code"):
        _el(a, "ram:PostcodeCode", p["zip_code"])
    if p.get("street"):
        _el(a, "ram:LineOne", p["street"])
    if p.get("city"):
        _el(a, "ram:CityName", p["city"])
    _el(a, "ram:CountryID", p.get("country") or "DE")
    if p.get("email"):
        _el(_el(e, "ram:URIUniversalCommunication"), "ram:URIID", p["email"], schemeID="EM")
    if p.get("vat_id"):
        _el(_el(e, "ram:SpecifiedTaxRegistration"), "ram:ID", p["vat_id"], schemeID="VA")
    if p.get("tax_number") and not p.get("vat_id"):
        _el(_el(e, "ram:SpecifiedTaxRegistration"), "ram:ID", p["tax_number"], schemeID="FC")
    return e


def cii_xml(daten: dict, profil: str = "xrechnung") -> bytes:
    """EN-16931-konforme CII-Rechnung. Reihenfolge der Elemente folgt dem Schema (sonst ungültig)."""
    v, k, st = daten["verkaeufer"], daten["kaeufer"], daten["steuer"]
    root = etree.Element(f"{{{NS['rsm']}}}CrossIndustryInvoice", nsmap=NS)
    ctx = _el(root, "rsm:ExchangedDocumentContext")
    _el(_el(ctx, "ram:BusinessProcessSpecifiedDocumentContextParameter"), "ram:ID", PROZESS_KENNUNG)
    _el(_el(ctx, "ram:GuidelineSpecifiedDocumentContextParameter"), "ram:ID", XRECHNUNG_KENNUNG if profil == "xrechnung" else ZUGFERD_KENNUNG)

    doc = _el(root, "rsm:ExchangedDocument")
    _el(doc, "ram:ID", daten["nummer"])
    _el(doc, "ram:TypeCode", daten.get("typecode") or "380")
    _datumselement(doc, "ram:IssueDateTime", daten["datum"])
    for n in daten["notizen"]:
        _el(_el(doc, "ram:IncludedNote"), "ram:Content", n)

    tx = _el(root, "rsm:SupplyChainTradeTransaction")
    for i, z in enumerate(daten["zeilen"], start=1):
        li = _el(tx, "ram:IncludedSupplyChainTradeLineItem")
        _el(_el(li, "ram:AssociatedDocumentLineDocument"), "ram:LineID", i)
        _el(_el(li, "ram:SpecifiedTradeProduct"), "ram:Name", z["name"][:250])
        ag = _el(li, "ram:SpecifiedLineTradeAgreement")
        _el(_el(ag, "ram:NetPriceProductTradePrice"), "ram:ChargeAmount", _geld(z["price"]))
        _el(_el(li, "ram:SpecifiedLineTradeDelivery"), "ram:BilledQuantity", _menge(z["quantity"]), unitCode=z["unit"])
        se = _el(li, "ram:SpecifiedLineTradeSettlement")
        t = _el(se, "ram:ApplicableTradeTax")
        _el(t, "ram:TypeCode", "VAT")
        _el(t, "ram:CategoryCode", st["category"])
        _el(t, "ram:RateApplicablePercent", _geld(st["rate"]))
        if z.get("from") and z.get("to"):
            per = _el(se, "ram:BillingSpecifiedPeriod")
            _datumselement(per, "ram:StartDateTime", z["from"])
            _datumselement(per, "ram:EndDateTime", z["to"])
        _el(_el(se, "ram:SpecifiedTradeSettlementLineMonetarySummation"), "ram:LineTotalAmount", _geld(z["amount"]))

    ag = _el(tx, "ram:ApplicableHeaderTradeAgreement")
    if k["leitweg_id"]:
        _el(ag, "ram:BuyerReference", k["leitweg_id"])
    _partei(ag, "ram:SellerTradeParty", v, kontakt=True)
    _partei(ag, "ram:BuyerTradeParty", k, kontakt=False, kundennummer=k.get("customer_number") or "")

    lief = _el(tx, "ram:ApplicableHeaderTradeDelivery")
    _datumselement(_el(lief, "ram:ActualDeliverySupplyChainEvent"), "ram:OccurrenceDateTime", daten["bis"])

    se = _el(tx, "ram:ApplicableHeaderTradeSettlement")
    _el(se, "ram:PaymentReference", daten["nummer"])
    _el(se, "ram:InvoiceCurrencyCode", daten["waehrung"])
    if v["iban"]:
        zm = _el(se, "ram:SpecifiedTradeSettlementPaymentMeans")
        _el(zm, "ram:TypeCode", "58")
        _el(zm, "ram:Information", "Überweisung (SEPA)")
        konto = _el(zm, "ram:PayeePartyCreditorFinancialAccount")
        _el(konto, "ram:IBANID", v["iban"])
        _el(konto, "ram:AccountName", v["name"])
        if v["bic"]:
            _el(_el(zm, "ram:PayeeSpecifiedCreditorFinancialInstitution"), "ram:BICID", v["bic"])
    t = _el(se, "ram:ApplicableTradeTax")
    _el(t, "ram:CalculatedAmount", _geld(daten["ust"]))
    _el(t, "ram:TypeCode", "VAT")
    if st["exemption_text"]:
        _el(t, "ram:ExemptionReason", st["exemption_text"])
    _el(t, "ram:BasisAmount", _geld(daten["netto"]))
    _el(t, "ram:CategoryCode", st["category"])
    if st["exemption_code"]:
        _el(t, "ram:ExemptionReasonCode", st["exemption_code"])
    _el(t, "ram:RateApplicablePercent", _geld(st["rate"]))
    per = _el(se, "ram:BillingSpecifiedPeriod")
    _datumselement(per, "ram:StartDateTime", daten["von"])
    _datumselement(per, "ram:EndDateTime", daten["bis"])
    zb = _el(se, "ram:SpecifiedTradePaymentTerms")
    _el(zb, "ram:Description", f"Zahlbar innerhalb von {daten['zahlungsziel_tage']} Tagen ohne Abzug, bis {_de(daten['faellig'])}.")
    _datumselement(zb, "ram:DueDateDateTime", daten["faellig"])
    su = _el(se, "ram:SpecifiedTradeSettlementHeaderMonetarySummation")
    _el(su, "ram:LineTotalAmount", _geld(daten["netto"]))
    _el(su, "ram:TaxBasisTotalAmount", _geld(daten["netto"]))
    _el(su, "ram:TaxTotalAmount", _geld(daten["ust"]), currencyID=daten["waehrung"])
    _el(su, "ram:GrandTotalAmount", _geld(daten["brutto"]))
    _el(su, "ram:DuePayableAmount", _geld(daten["brutto"]))
    for v in daten.get("vorherige") or []:   # BG-3: vorausgegangene Rechnungen (Abschläge bei der Schlussrechnung, Original beim Storno)
        if not v.get("nummer"):
            continue
        ref = _el(se, "ram:InvoiceReferencedDocument")
        _el(ref, "ram:IssuerAssignedID", v["nummer"])
        if v.get("datum"):
            _datumselement(ref, "ram:FormattedIssueDateTime", v["datum"])
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)


# ---------- Lesbare Rechnung (PDF, eingebettete Schrift) ----------

def _eur(x: float) -> str:
    s = f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{s} €"


def _dez(x: float, stellen: int = 2) -> str:
    return f"{x:.{stellen}f}".replace(".", ",")


def _bild(data_url: str):
    try:
        if not data_url or not data_url.startswith("data:image"):
            return None
        roh = base64.b64decode(data_url.split(",", 1)[1])
        return ImageReader(io.BytesIO(roh))
    except Exception:  # noqa: BLE001 – kaputtes Bild darf die Rechnung nicht verhindern
        return None


class _Blatt:
    """Kleiner Zeiger für Seitenaufbau mit automatischem Seitenumbruch und Fußzeile."""

    def __init__(self, c: canvas.Canvas, daten: dict):
        self.c, self.d = c, daten
        self.w, self.h = A4
        self.rand = 20 * mm
        self.y = self.h - 20 * mm
        self.seite = 1

    def text(self, x, s, groesse=9.5, fett=False, farbe=(0.11, 0.11, 0.12), rechts=False):
        self.c.setFont(SCHRIFT_FETT if fett else SCHRIFT, groesse)
        self.c.setFillColorRGB(*farbe)
        if rechts:
            self.c.drawRightString(x, self.y, s)
        else:
            self.c.drawString(x, self.y, s)

    def absatz(self, s, groesse=9.5, breite=None, zeilenhoehe=None, fett=False, farbe=(0.11, 0.11, 0.12)):
        breite = breite or (self.w - 2 * self.rand)
        zh = zeilenhoehe or groesse * 1.35
        for zeile in simpleSplit(s, SCHRIFT_FETT if fett else SCHRIFT, groesse, breite):
            self.platz(zh)
            self.text(self.rand, zeile, groesse, fett, farbe)
            self.y -= zh
        return self

    def platz(self, hoehe):
        if self.y - hoehe < 22 * mm:
            self.fusszeile()
            self.c.showPage()
            self.seite += 1
            self.y = self.h - 20 * mm

    def fusszeile(self):
        v = self.d["verkaeufer"]
        teile = [v["name"], ", ".join(t for t in [v["street"], f"{v['zip_code']} {v['city']}".strip()] if t), " · ".join(t for t in [v["phone"], v["email"]] if t)]
        zeile = " · ".join(t for t in teile if t)
        self.c.setStrokeColorRGB(0.85, 0.85, 0.85)
        self.c.setLineWidth(0.3)
        self.c.line(self.rand, 14 * mm, self.w - self.rand, 14 * mm)
        self.c.setFont(SCHRIFT, 7)
        self.c.setFillColorRGB(0.45, 0.45, 0.47)
        self.c.drawString(self.rand, 10 * mm, zeile[:160])
        self.c.drawRightString(self.w - self.rand, 10 * mm, f"Seite {self.seite}")


def rechnung_pdf(daten: dict) -> bytes:
    """Lesbare Rechnung (A4) – gleicher Aufbau wie die Rechnung aus der Oberfläche, aber serverseitig und PDF/A-tauglich."""
    schrift_registrieren()
    v, k = daten["verkaeufer"], daten["kaeufer"]
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4, initialFontName=SCHRIFT, initialFontSize=10)
    c.setTitle(f"{daten.get('art_name', 'Rechnung')} {daten['nummer']}")
    c.setAuthor(v["name"])
    c.setSubject(f"Rechnung {daten['nummer']} – {daten['projekt']}")
    c.setCreator(ERZEUGER)
    b = _Blatt(c, daten)
    grau = (0.43, 0.43, 0.45)
    schwarz = (0.11, 0.11, 0.12)
    rechts = b.w - b.rand

    # Kopf: Firma links, Logo rechts
    logo = _bild(daten.get("logo"))
    if logo is not None:
        try:
            bw, bh = logo.getSize()
            zw = 40 * mm
            zh = zw * bh / bw
            if zh > 18 * mm:
                zh, zw = 18 * mm, 18 * mm * bw / bh
            c.drawImage(logo, rechts - zw, b.y - zh + 4 * mm, width=zw, height=zh, mask="auto")
        except Exception:  # noqa: BLE001
            pass
    b.text(b.rand, v["name"], 16, fett=True)
    b.y -= 7 * mm
    b.text(b.rand, daten.get("art_name", "Rechnung"), 11, fett=True, farbe=grau)
    b.text(b.rand + 28 * mm, f"Nr. {daten['nummer']}", 11, farbe=grau)
    b.y -= 12 * mm

    # Absenderzeile + Empfänger links, Angaben rechts
    absender = " · ".join(t for t in [v["name"], ", ".join(t for t in [v["street"], f"{v['zip_code']} {v['city']}".strip()] if t)] if t)
    b.text(b.rand, absender[:110], 7, farbe=grau)
    y0 = b.y - 5 * mm
    empfaenger = [t for t in [k["name"], k.get("contact"), k["street"], f"{k['zip_code']} {k['city']}".strip()] if t]
    for i, zeile in enumerate(empfaenger[:5]):
        c.setFont(SCHRIFT, 9.5)
        c.setFillColorRGB(*schwarz)
        c.drawString(b.rand, y0 - i * 4.6 * mm, zeile[:60])
    meta = [("Rechnungsnummer", daten["nummer"]), ("Rechnungsdatum", _de(daten["datum"])), ("Leistungszeitraum", f"{_de(daten['von'])} – {_de(daten['bis'])}"),
            ("Fällig am", _de(daten["faellig"])), ("Projekt / Objekt", daten["projekt"])]
    if k.get("customer_number"):
        meta.append(("Kundennummer", k["customer_number"]))
    if k.get("leitweg_id"):
        meta.append(("Leitweg-ID", k["leitweg_id"]))
    mx = b.rand + 100 * mm
    for i, (name, wert) in enumerate(meta):
        c.setFont(SCHRIFT, 8)
        c.setFillColorRGB(*grau)
        c.drawString(mx, y0 - i * 4.8 * mm, name)
        c.setFont(SCHRIFT, 9)
        c.setFillColorRGB(*schwarz)
        c.drawString(mx + 34 * mm, y0 - i * 4.8 * mm, str(wert or "–")[:38])
    b.y = y0 - max(len(meta), len(empfaenger)) * 4.8 * mm - 10 * mm

    b.absatz(f"{daten.get('art_name', 'Rechnung')} Nr. {daten['nummer']}", 12, fett=True)
    b.y -= 1 * mm
    for n in daten["notizen"]:
        b.absatz(n, 9)
    b.y -= 4 * mm

    # Tabelle
    spalten = [(12 * mm, "Pos.", "c"), (86 * mm, "Beschreibung", "l"), (24 * mm, "Menge", "r"), (24 * mm, "Einzelpreis", "r"), (24 * mm, "Gesamt", "r")]
    x_start = b.rand

    def kopf():
        b.platz(8 * mm)
        c.setFillColorRGB(0.96, 0.96, 0.97)
        c.rect(x_start, b.y - 2.2 * mm, sum(s[0] for s in spalten), 7 * mm, fill=1, stroke=0)
        x = x_start
        for breite, titel, ausr in spalten:
            c.setFont(SCHRIFT_FETT, 8.5)
            c.setFillColorRGB(*schwarz)
            if ausr == "r":
                c.drawRightString(x + breite - 2 * mm, b.y, titel)
            elif ausr == "c":
                c.drawCentredString(x + breite / 2, b.y, titel)
            else:
                c.drawString(x + 2 * mm, b.y, titel)
            x += breite
        b.y -= 7.5 * mm

    kopf()
    for i, z in enumerate(daten["zeilen"], start=1):
        beschreibung = simpleSplit(z["name"], SCHRIFT, 9, spalten[1][0] - 4 * mm) or [""]
        hoehe = max(1, len(beschreibung)) * 4.4 * mm + 2.5 * mm
        if b.y - hoehe < 22 * mm:
            b.platz(hoehe + 20 * mm)
            kopf()
        menge = f"{_dez(z['quantity'], 2 if z['quantity'] != int(z['quantity']) else 0)} {z['unit_label']}".strip()
        werte = [str(i), None, menge, _eur(z["price"]), _eur(z["amount"])]
        x = x_start
        for (breite, _, ausr), wert in zip(spalten, werte):
            c.setFont(SCHRIFT, 9)
            c.setFillColorRGB(*schwarz)
            if wert is None:
                for j, zeile in enumerate(beschreibung):
                    c.drawString(x + 2 * mm, b.y - j * 4.4 * mm, zeile)
            elif ausr == "r":
                c.drawRightString(x + breite - 2 * mm, b.y, wert)
            elif ausr == "c":
                c.drawCentredString(x + breite / 2, b.y, wert)
            else:
                c.drawString(x + 2 * mm, b.y, wert)
            x += breite
        b.y -= hoehe
        c.setStrokeColorRGB(0.9, 0.9, 0.9)
        c.setLineWidth(0.2)
        c.line(x_start, b.y + 1.5 * mm, x_start + sum(s[0] for s in spalten), b.y + 1.5 * mm)

    # Summen
    b.platz(30 * mm)
    b.y -= 3 * mm
    label_x = rechts - 38 * mm
    if daten.get("art", "monat") == "monat":
        b.text(b.rand, f"Gesamtstunden: {_dez(daten['gesamt_minuten'] / 60)} Std.", 8, farbe=grau)
    b.text(label_x, "Nettobetrag", 9, rechts=True)
    b.text(rechts, _eur(daten["netto"]), 9, rechts=True)
    b.y -= 6 * mm
    st = daten["steuer"]
    ust_text = "Umsatzsteuer" if st["category"] != "S" else f"zzgl. {_dez(daten['ust_satz'], 0 if daten['ust_satz'] == int(daten['ust_satz']) else 1)} % USt."
    b.text(label_x, ust_text, 9, rechts=True)
    b.text(rechts, _eur(daten["ust"]), 9, rechts=True)
    b.y -= 3 * mm
    c.setStrokeColorRGB(*schwarz)
    c.setLineWidth(0.3)
    c.line(label_x - 45 * mm, b.y, rechts, b.y)
    b.y -= 5 * mm
    b.text(label_x, {"gutschrift": "Gutschriftsbetrag", "storno": "Stornobetrag"}.get(daten.get("art"), "Rechnungsbetrag"), 9.5, fett=True, rechts=True)
    b.text(rechts, _eur(daten["brutto"]), 9.5, fett=True, rechts=True)
    b.y -= 11 * mm

    if st["exemption_text"]:
        b.absatz(st["exemption_text"] + ".", 9)
        b.y -= 2 * mm
    if daten.get("art") == "gutschrift":
        b.absatz(f"Der Gutschriftsbetrag von {_eur(daten['brutto'])} wird mit offenen Forderungen verrechnet oder auf Ihr Konto erstattet.", 9)
    elif daten.get("art") == "storno":
        b.absatz("Diese Stornorechnung hebt die genannte Rechnung vollständig auf. Bereits geleistete Zahlungen werden verrechnet oder erstattet.", 9)
    else:
        b.absatz(f"Bitte überweisen Sie den Rechnungsbetrag von {_eur(daten['brutto'])} bis zum {_de(daten['faellig'])} unter Angabe der Rechnungsnummer "
                 f"auf das unten genannte Konto. Vielen Dank für Ihren Auftrag.", 9)
    b.y -= 5 * mm
    bank = [("Bank", v["bank_name"]), ("IBAN", v["iban"]), ("BIC", v["bic"]), ("Steuernummer", v["tax_number"]), ("USt-IdNr.", v["vat_id"])]
    bank = [(n, w) for n, w in bank if w]
    if bank:
        b.platz(len(bank) * 5 * mm)
        spalte_w = (b.w - 2 * b.rand) / 2
        for i, (n, w) in enumerate(bank):
            x = b.rand + (i % 2) * spalte_w
            yy = b.y - (i // 2) * 5 * mm
            c.setFont(SCHRIFT, 8)
            c.setFillColorRGB(*grau)
            c.drawString(x, yy, n)
            c.setFont(SCHRIFT, 9)
            c.setFillColorRGB(*schwarz)
            c.drawString(x + 26 * mm, yy, str(w))
        b.y -= ((len(bank) + 1) // 2) * 5 * mm + 8 * mm

    stempel = _bild(daten.get("stempel"))
    sh = 0
    if stempel is not None:
        try:
            bw, bh = stempel.getSize()
            faktor = daten.get("stempel_scale", 100) / 100
            sw = min(60 * mm * faktor, 90 * mm)
            sh = sw * bh / bw
        except Exception:  # noqa: BLE001
            stempel = None
    b.platz(sh + 25 * mm)
    b.text(b.rand, "Mit freundlichen Grüßen", 9)
    b.y -= 5 * mm
    if stempel is not None:
        c.drawImage(stempel, b.rand, b.y - sh, width=sw, height=sh, mask="auto")
        b.y -= sh + 4 * mm
    else:
        b.y -= 8 * mm
    b.text(b.rand, daten.get("inhaber") or "", 9)
    b.y -= 4 * mm
    b.text(b.rand, v["name"], 7.5, farbe=grau)
    b.fusszeile()
    c.showPage()
    c.save()
    return buf.getvalue()


def dateiname(daten: dict, endung: str) -> str:
    sicher = re.sub(r"[^A-Za-z0-9_.-]+", "_", f"{daten['nummer']}_{daten['projekt']}")[:80]
    return f"{sicher}.{endung}"


def erzeugt_am() -> str:
    return datetime.now().isoformat(timespec="seconds")
