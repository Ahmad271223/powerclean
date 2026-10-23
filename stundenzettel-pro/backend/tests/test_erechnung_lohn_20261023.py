"""E-Rechnung (XRechnung 3.0 / ZUGFeRD EN 16931) und Lohnvorbereitung ohne Lohnberechnung – 2026-10-23."""
import io
import os
from datetime import date, timedelta

import pikepdf
from lxml import etree

from conftest import einladen, projekt, registrieren, zeit

NS = {"rsm": "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100",
      "ram": "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100",
      "udt": "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100"}
FIRMA = {"street": "Musterstraße 1", "zip_code": "40210", "city": "Düsseldorf", "phone": "0211 123456", "email": "rechnung@powerclean-test.de",
         "vat_id": "DE123456789", "tax_number": "133/5678/9012", "iban": "DE89 3704 0044 0532 0130 00", "bic": "COBADEFFXXX", "bank_name": "Commerzbank",
         "payment_days": 14, "vat_rate": 19, "owner": "Ahmad Chef", "bundesland": "NW", "auto_pause": False}
KUNDE = {"name": "Stadt Düsseldorf – Schulverwaltung", "street": "Rathausufer 1", "zip_code": "40213", "city": "Düsseldorf",
         "email": "rechnungen@stadt-test.de", "leitweg_id": "05111-12345-67", "customer_number": "K-100"}


def _xsd():
    try:
        import drafthorse
    except ImportError:
        return None
    pfad = os.path.join(os.path.dirname(drafthorse.__file__), "schema", "Factur-X_1.0.07_EN16931.xsd")
    return etree.XMLSchema(etree.parse(pfad)) if os.path.exists(pfad) else None


def _rechnung(client, kopf, reverse=False, kunde=KUNDE):
    k = client.post("/api/kunden", json={**kunde, "reverse_charge": reverse}, headers=kopf).json()["kunde"]
    p = projekt(client, kopf, name="Grundschule Nord", customer_id=k["id"], reverse_charge=reverse)
    zeit(client, kopf, p["id"], date="2026-10-05", start="08:00", ende="12:00")   # KW 41: 4 h à 30 = 120
    zeit(client, kopf, p["id"], date="2026-10-13", start="08:00", ende="10:30")   # KW 42: 2,5 h = 75
    inv = client.post("/api/rechnungen/anlegen", json={"project_id": p["id"], "year": 2026, "month": 10}, headers=kopf).json()["rechnung"]
    r = client.put(f"/api/rechnungen/{inv['id']}/extras", json={"extras": [{"text": "Anfahrt", "quantity": 2, "unit": "Fahrten", "unit_price": 12.5}]}, headers=kopf)
    assert r.status_code == 200, r.text
    return k, p, r.json()["rechnung"]


def _text(root, pfad):
    return root.findtext(pfad, namespaces=NS)


def test_01_xrechnung_xml_vollstaendig_und_schemagueltig(client):
    kopf, _ = registrieren(client)
    assert client.put("/api/firma", json=FIRMA, headers=kopf).status_code == 200
    _, _, inv = _rechnung(client, kopf)
    assert inv["net"] == 220 and inv["gross"] == 261.8
    st = client.get(f"/api/rechnungen/{inv['id']}/erechnung", headers=kopf).json()
    assert st["xrechnung"]["ok"] and st["zugferd"]["ok"], st
    assert st["kaeufer"]["leitweg_id"] == "05111-12345-67" and st["steuer"] == "S"

    r = client.get(f"/api/rechnungen/{inv['id']}/xrechnung.xml", headers=kopf)
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/xml")
    assert "XRechnung_" in r.headers["content-disposition"]
    root = etree.fromstring(r.content)
    assert _text(root, ".//ram:GuidelineSpecifiedDocumentContextParameter/ram:ID") == "urn:cen.eu:en16931:2017#compliant#urn:xeinkauf.de:kosit:xrechnung_3.0"
    assert _text(root, "rsm:ExchangedDocument/ram:ID") == inv["number"] and _text(root, "rsm:ExchangedDocument/ram:TypeCode") == "380"
    assert _text(root, ".//ram:BuyerReference") == "05111-12345-67"
    assert _text(root, ".//ram:SellerTradeParty/ram:SpecifiedTaxRegistration/ram:ID") == "DE123456789"
    assert _text(root, ".//ram:SellerTradeParty/ram:DefinedTradeContact/ram:EmailURIUniversalCommunication/ram:URIID") == "rechnung@powerclean-test.de"
    assert _text(root, ".//ram:BuyerTradeParty/ram:PostalTradeAddress/ram:PostcodeCode") == "40213"
    assert _text(root, ".//ram:BuyerTradeParty/ram:ID") == "K-100"
    zeilen = root.findall(".//ram:IncludedSupplyChainTradeLineItem", NS)
    assert len(zeilen) == 3
    assert zeilen[0].find(".//ram:BilledQuantity", NS).get("unitCode") == "HUR" and _text(zeilen[0], ".//ram:BilledQuantity") == "4.00"
    assert "Reinigungsarbeiten KW 41" in _text(zeilen[0], ".//ram:SpecifiedTradeProduct/ram:Name")
    assert _text(zeilen[2], ".//ram:SpecifiedTradeProduct/ram:Name") == "Anfahrt" and zeilen[2].find(".//ram:BilledQuantity", NS).get("unitCode") == "C62"
    assert round(sum(float(_text(z, ".//ram:LineTotalAmount")) for z in zeilen), 2) == 220.0
    su = root.find(".//ram:SpecifiedTradeSettlementHeaderMonetarySummation", NS)
    assert (_text(su, "ram:LineTotalAmount"), _text(su, "ram:TaxBasisTotalAmount"), _text(su, "ram:TaxTotalAmount"), _text(su, "ram:GrandTotalAmount"), _text(su, "ram:DuePayableAmount")) == ("220.00", "220.00", "41.80", "261.80", "261.80")
    assert su.find("ram:TaxTotalAmount", NS).get("currencyID") == "EUR"
    steuer = root.find(".//ram:ApplicableHeaderTradeSettlement/ram:ApplicableTradeTax", NS)
    assert _text(steuer, "ram:CategoryCode") == "S" and _text(steuer, "ram:RateApplicablePercent") == "19.00" and _text(steuer, "ram:CalculatedAmount") == "41.80"
    assert _text(root, ".//ram:PayeePartyCreditorFinancialAccount/ram:IBANID") == "DE89370400440532013000"
    assert _text(root, ".//ram:SpecifiedTradeSettlementPaymentMeans/ram:TypeCode") == "58"
    faellig = (date.fromisoformat(inv["invoice_date"]) + timedelta(days=14)).isoformat().replace("-", "")
    assert _text(root, ".//ram:SpecifiedTradePaymentTerms/ram:DueDateDateTime/udt:DateTimeString") == faellig
    assert _text(root, ".//ram:ApplicableHeaderTradeSettlement/ram:BillingSpecifiedPeriod/ram:StartDateTime/udt:DateTimeString") == "20261001"
    xsd = _xsd()
    if xsd is not None:
        assert xsd.validate(root), xsd.error_log
    # Kennzeichnung und Protokoll
    assert client.get(f"/api/rechnungen/{inv['id']}/erechnung", headers=kopf).json()["erzeugt"].get("xrechnung_at")
    prot = client.get("/api/exporte/protokoll.csv", headers=kopf).text
    assert "rechnung.erechnung" in prot


def test_02_13b_kleinunternehmer_und_fehlende_angaben(client):
    kopf, _ = registrieren(client)
    client.put("/api/firma", json=FIRMA, headers=kopf)
    _, _, inv = _rechnung(client, kopf, reverse=True)
    assert inv["reverse_charge"] and inv["gross"] == 220
    root = etree.fromstring(client.get(f"/api/rechnungen/{inv['id']}/xrechnung.xml", headers=kopf).content)
    steuer = root.find(".//ram:ApplicableHeaderTradeSettlement/ram:ApplicableTradeTax", NS)
    assert _text(steuer, "ram:CategoryCode") == "AE" and _text(steuer, "ram:ExemptionReasonCode") == "VATEX-EU-AE" and _text(steuer, "ram:CalculatedAmount") == "0.00"
    assert "13b" in _text(steuer, "ram:ExemptionReason")
    assert {_text(z, ".//ram:ApplicableTradeTax/ram:CategoryCode") for z in root.findall(".//ram:IncludedSupplyChainTradeLineItem", NS)} == {"AE"}
    assert _text(root, ".//ram:SpecifiedTradeSettlementHeaderMonetarySummation/ram:GrandTotalAmount") == "220.00"
    xsd = _xsd()
    if xsd is not None:
        assert xsd.validate(root), xsd.error_log

    # Kleinunternehmer + Kunde ohne Leitweg-ID: ZUGFeRD geht, XRechnung nennt das Fehlende
    client.put("/api/firma", json={"small_business": True}, headers=kopf)
    k2 = client.post("/api/kunden", json={**KUNDE, "name": "Privatkunde Meier", "leitweg_id": "", "email": ""}, headers=kopf).json()["kunde"]
    p2 = projekt(client, kopf, name="Praxis Meier", customer_id=k2["id"])
    zeit(client, kopf, p2["id"], date="2026-10-06", start="08:00", ende="10:00")
    inv2 = client.post("/api/rechnungen/anlegen", json={"project_id": p2["id"], "year": 2026, "month": 10}, headers=kopf).json()["rechnung"]
    assert inv2["vat"] == 0
    st = client.get(f"/api/rechnungen/{inv2['id']}/erechnung", headers=kopf).json()
    assert not st["xrechnung"]["ok"] and any("Leitweg-ID" in f for f in st["xrechnung"]["fehlt"]) and any("E-Mail des Kunden" in f for f in st["xrechnung"]["fehlt"])
    assert st["zugferd"]["ok"] and st["steuer"] == "E"
    r = client.get(f"/api/rechnungen/{inv2['id']}/xrechnung.xml", headers=kopf)
    assert r.status_code == 422 and "Leitweg-ID" in r.json()["detail"]
    pdf = pikepdf.open(io.BytesIO(client.get(f"/api/rechnungen/{inv2['id']}/zugferd.pdf", headers=kopf).content))
    root2 = etree.fromstring(pdf.attachments["factur-x.xml"].get_file().read_bytes())
    steuer2 = root2.find(".//ram:ApplicableHeaderTradeSettlement/ram:ApplicableTradeTax", NS)
    assert _text(steuer2, "ram:CategoryCode") == "E" and "19" in _text(steuer2, "ram:ExemptionReason")

    # Projekt ohne Kundenstamm: Adresse aus dem Freitext, fehlende Firmenanschrift blockiert beides
    p3 = projekt(client, kopf, name="Hausverwaltung", customer_name="Hausverwaltung Schmidt", customer_address="Musterweg 3\n12345 Musterstadt")
    zeit(client, kopf, p3["id"], date="2026-10-07", start="08:00", ende="10:00")
    inv3 = client.post("/api/rechnungen/anlegen", json={"project_id": p3["id"], "year": 2026, "month": 10}, headers=kopf).json()["rechnung"]
    st3 = client.get(f"/api/rechnungen/{inv3['id']}/erechnung", headers=kopf).json()
    assert st3["zugferd"]["ok"] and st3["kaeufer"] == {"name": "Hausverwaltung Schmidt", "leitweg_id": "", "email": "", "zip_code": "12345", "city": "Musterstadt"}
    client.put("/api/firma", json={"zip_code": ""}, headers=kopf)
    st4 = client.get(f"/api/rechnungen/{inv3['id']}/erechnung", headers=kopf).json()
    assert not st4["zugferd"]["ok"] and any("Firmenanschrift" in f for f in st4["zugferd"]["fehlt"])
    assert client.get(f"/api/rechnungen/{inv3['id']}/zugferd.pdf", headers=kopf).status_code == 422


def test_03_zugferd_pdfa3_aufbau(client):
    kopf, _ = registrieren(client)
    client.put("/api/firma", json=FIRMA, headers=kopf)
    _, _, inv = _rechnung(client, kopf)
    r = client.get(f"/api/rechnungen/{inv['id']}/zugferd.pdf", headers=kopf)
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf" and r.content.startswith(b"%PDF-1.7")
    pdf = pikepdf.open(io.BytesIO(r.content))
    assert list(pdf.attachments.keys()) == ["factur-x.xml"]
    anhang = pdf.attachments["factur-x.xml"]
    assert anhang.obj.get("/AFRelationship") == pikepdf.Name("/Data")
    xml = anhang.get_file().read_bytes()
    root = etree.fromstring(xml)
    assert _text(root, ".//ram:GuidelineSpecifiedDocumentContextParameter/ram:ID") == "urn:cen.eu:en16931:2017"
    assert _text(root, ".//ram:SpecifiedTradeSettlementHeaderMonetarySummation/ram:GrandTotalAmount") == "261.80"
    xsd = _xsd()
    if xsd is not None:
        assert xsd.validate(root), xsd.error_log
    assert "/AF" in pdf.Root and "/OutputIntents" in pdf.Root and str(pdf.Root.OutputIntents[0].S) == "/GTS_PDFA1"
    meta = pdf.Root.Metadata.read_bytes().decode("utf-8")
    for teil in ("<pdfaid:part>3</pdfaid:part>", "<pdfaid:conformance>B</pdfaid:conformance>", "<fx:ConformanceLevel>EN 16931</fx:ConformanceLevel>",
                 "<fx:DocumentFileName>factur-x.xml</fx:DocumentFileName>", "pdfaExtension:schemas"):
        assert teil in meta, teil
    assert str(pdf.docinfo["/Title"]) == f"Rechnung {inv['number']}"
    schriften = [f for pg in pdf.pages for f in pg.Resources.get("/Font", {}).values()]
    assert schriften and all("BitstreamVeraSans" in str(f.BaseFont) for f in schriften), [str(f.BaseFont) for f in schriften]
    assert all("/FontFile2" in (f.get("/FontDescriptor") or f.DescendantFonts[0].FontDescriptor) for f in schriften)   # eingebettet (PDF/A-Pflicht)
    # Reine Server-Rechnung ohne XML
    r2 = client.get(f"/api/rechnungen/{inv['id']}/rechnung.pdf", headers=kopf)
    assert r2.status_code == 200 and r2.content.startswith(b"%PDF")
    assert not pikepdf.open(io.BytesIO(r2.content)).attachments.keys()


def test_04_lohndaten_verschluesselt_rollen_und_protokoll(client):
    kopf, chef = registrieren(client)
    mia_kopf, mia = einladen(client, kopf)
    uid, chef_id = mia["user"]["id"], chef["user"]["id"]
    daten = {"birth_date": "1990-05-04", "street": "Gartenweg 2", "zip_code": "40211", "city": "Düsseldorf", "tax_id": "12 345 678 901", "tax_class": "1",
             "church_tax": False, "sv_number": "12 345678 A 123", "health_insurance": "AOK Rheinland", "employment_type": "teilzeit", "hourly_wage": 14.5,
             "entry_date": "2025-03-01", "iban_salary": "DE89 3704 0044 0532 0130 00"}
    r = client.put(f"/api/mitarbeiter/{uid}/lohndaten", json=daten, headers=kopf)
    assert r.status_code == 200, r.text
    l = r.json()["lohndaten"]
    assert l["tax_id"] == "12345678901" and l["sv_number"] == "12345678A123" and l["iban_salary"] == "DE89370400440532013000" and l["hourly_wage"] == 14.5
    # In der Datenbank verschlüsselt (Sicherung zeigt den Rohbestand), nie in der normalen Mitarbeiter-Antwort
    sicherung = client.get("/api/exporte/sicherung.json", headers=kopf).text
    assert "12345678901" not in sicherung and "DE89370400440532013000" not in sicherung and "enc:" in sicherung
    assert "lohndaten" not in client.get(f"/api/mitarbeiter/{uid}", headers=kopf).json()["mitarbeiter"]
    assert all("lohndaten" not in m for m in client.get("/api/mitarbeiter", headers=kopf).json()["mitarbeiter"])
    # Mitarbeiterin: eigene Daten lesen ja, fremde nein, ändern nein
    assert client.get(f"/api/mitarbeiter/{uid}/lohndaten", headers=mia_kopf).json()["lohndaten"]["tax_class"] == "1"
    assert client.get(f"/api/mitarbeiter/{chef_id}/lohndaten", headers=mia_kopf).status_code == 403
    assert client.put(f"/api/mitarbeiter/{uid}/lohndaten", json={"tax_class": "3"}, headers=mia_kopf).status_code == 403
    # Prüfungen
    assert client.put(f"/api/mitarbeiter/{uid}/lohndaten", json={"sv_number": "123"}, headers=kopf).status_code == 422
    assert client.put(f"/api/mitarbeiter/{uid}/lohndaten", json={"iban_salary": "DE89 3704 0044 0532 0130 01"}, headers=kopf).status_code == 422
    assert client.put(f"/api/mitarbeiter/{uid}/lohndaten", json={"tax_id": "0123"}, headers=kopf).status_code == 422
    # Protokoll nennt Felder, nie Werte
    prot = client.get("/api/exporte/protokoll.csv", headers=kopf).text
    assert "mitarbeiter.lohndaten" in prot and "tax_id" in prot and "12345678901" not in prot and "DE89370400440532013000" not in prot


def test_05_lohnvorbereitung_stunden_nach_art_und_exporte(client):
    kopf, chef = registrieren(client)
    r = client.get("/api/lohn/lodas.txt?jahr=2026&monat=10", headers=kopf)
    assert r.status_code == 422 and "Lohnarten" in r.json()["detail"]          # leere Datei wird nicht ausgeliefert
    assert client.put("/api/firma", json={**FIRMA, "lohn_export": {"berater_nr": "1234567", "mandanten_nr": "12345", "lohnarten": {"normal": "100", "nacht": "300", "urlaub": "400", "krank": "500"}}}, headers=kopf).status_code == 200
    mia_kopf, mia = einladen(client, kopf)
    uid = mia["user"]["id"]
    assert client.put(f"/api/mitarbeiter/{uid}", json={"personalnummer": "0007", "weekly_hours": 20, "vacation_days": 24}, headers=kopf).status_code == 200
    p = projekt(client, kopf)
    zeit(client, kopf, p["id"], date="2026-10-03", start="09:00", ende="11:00", user_id=uid)            # Samstag, Tag der Deutschen Einheit → Feiertag 120
    zeit(client, kopf, p["id"], date="2026-10-04", start="08:00", ende="12:00", user_id=uid)            # Sonntag 240
    zeit(client, kopf, p["id"], date="2026-10-05", start="18:00", ende="23:00", user_id=uid)            # Nacht 180 (20–23 Uhr)
    zeit(client, kopf, p["id"], date="2026-10-06", start="22:00", ende="06:00", pause=30, user_id=uid)  # über Mitternacht: netto 450, alles Nacht
    assert client.post("/api/abwesenheiten", json={"user_id": uid, "type": "urlaub", "from_date": "2026-10-12", "to_date": "2026-10-13"}, headers=kopf).status_code == 200
    assert client.post("/api/abwesenheiten", json={"user_id": uid, "type": "krank", "from_date": "2026-10-14", "to_date": "2026-10-14"}, headers=kopf).status_code == 200

    d = client.get("/api/lohn/vorbereitung?jahr=2026&monat=10", headers=kopf).json()
    assert "2026-10-03" in d["feiertage"] and d["hinweis"].startswith("Keine Lohnabrechnung")
    m = next(x for x in d["mitarbeiter"] if x["personalnummer"] == "0007")
    assert (m["minuten"], m["nacht_minuten"], m["sonntag_minuten"], m["feiertag_minuten"], m["arbeitstage"]) == (1110, 630, 240, 120, 4)
    assert m["urlaubstage"] == 2 and m["kranktage"] == 1 and m["wochenstunden"] == 20 and m["resturlaub"] == 22
    assert m["ueberstunden_minuten"] == 0 and m["saldo_monat_minuten"] < 0

    csv_text = client.get("/api/lohn/vorbereitung.csv?jahr=2026&monat=10", headers=kopf).content.decode("utf-8-sig")
    assert csv_text.startswith("Personalnummer;Mitarbeiter;") and "0007;Mia Mitarbeiterin;" in csv_text and ";18,50;10,50;4,00;2,00;" in csv_text
    lod = client.get("/api/lohn/lodas.txt?jahr=2026&monat=10", headers=kopf).content.decode("cp1252")
    for teil in ("[Allgemein]", "BeraterNr=1234567", "MandantenNr=12345", "StammdatenGueltigAb=01.10.2026", "[Satzbeschreibung]",
                 "100;u_lod_bwd_buchung_standard;pnr#bwd;abrechnung_zeitraum#bwd;bs_wert_butab#bwd;bs_nr#bwd;la_eigene#bwd;", "[Bewegungsdaten]",
                 "100;0007;01.10.2026;18,5;1;100;", "100;0007;01.10.2026;10,5;1;300;", "100;0007;01.10.2026;2,0;1;400;", "100;0007;01.10.2026;1,0;1;500;"):
        assert teil in lod, teil
    assert "100;0007;01.10.2026;4,0;" not in lod   # Sonntag ohne Lohnart → nicht exportiert
    pr = client.get("/api/lohn/lodas-pruefung?jahr=2026&monat=10", headers=kopf).json()
    assert pr["zeilen"] == 4 and pr["hinweise"] == []          # Inhaber hat Personalnummer 1, aber keine Werte → keine Zeile, kein Hinweis
    client.put("/api/firma", json={"lohn_export": {"lohnarten": {"normal": "100"}}}, headers=kopf)
    pr0 = client.get("/api/lohn/lodas-pruefung?jahr=2026&monat=10", headers=kopf).json()
    assert pr0["zeilen"] == 1 and any("Mandantennummer" in h for h in pr0["hinweise"])
    client.put("/api/firma", json={"lohn_export": {"berater_nr": "1234567", "mandanten_nr": "12345", "lohnarten": {"normal": "100", "nacht": "300", "urlaub": "400", "krank": "500"}}}, headers=kopf)
    client.put(f"/api/mitarbeiter/{chef['user']['id']}", json={"personalnummer": ""}, headers=kopf)
    pr2 = client.get("/api/lohn/lodas-pruefung?jahr=2026&monat=10", headers=kopf).json()
    assert pr2["zeilen"] == 4 and any("Ahmad Chef" in h and "Personalnummer" in h for h in pr2["hinweise"])
    pdf = client.get("/api/lohn/vorbereitung.pdf?jahr=2026&monat=10", headers=kopf)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    client.put(f"/api/mitarbeiter/{uid}/lohndaten", json={"tax_id": "12345678901", "employment_type": "teilzeit"}, headers=kopf)
    stamm = client.get("/api/lohn/stammdaten.csv", headers=kopf).content.decode("utf-8-sig")
    assert "0007;Mia Mitarbeiterin;" in stamm and "12345678901" in stamm and "Teilzeit" in stamm
    # Mitarbeiter dürfen nichts davon
    assert client.get("/api/lohn/vorbereitung?jahr=2026&monat=10", headers=mia_kopf).status_code == 403
    assert client.get("/api/lohn/stammdaten.csv", headers=mia_kopf).status_code == 403
    prot = client.get("/api/exporte/protokoll.csv", headers=kopf).text
    assert "export.lohnvorbereitung" in prot and "export.stammdaten" in prot
