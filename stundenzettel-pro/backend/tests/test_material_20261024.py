"""Stufe D (24.10.2026): Artikelstamm mit CSV-Import und Rechten, Materialverbrauch der Mitarbeiter ohne Preise, Eingangsrechnungen mit Beleg,
XRechnung-Vorschlag, Aufteilung und Dublettenprüfung, Projekt-Nachkalkulation nach Kostenarten mit Unvollständigkeitshinweisen."""
import io
import zipfile

from conftest import einladen, projekt, registrieren, zeit

CSV = ("﻿Artikelnummer;Bezeichnung;Einheit;EK;VK;Kategorie\n"
       'RM-210;"Glasreiniger; 5 l";Kanister;12,40;19,90;Reinigungsmittel\n'
       "VM-050;Mikrofasertücher;Pack;6,50;11,00;Verbrauch\n"
       ";Ohne Nummer;Stk.;1;2;x\n"
       "MS-1;Maschine;Tag;abc;80;Maschinen\n"
       "RM-210;Doppelt;Stk.;1;1;x\n").encode("utf-8")

XRECHNUNG = b"""<?xml version="1.0" encoding="UTF-8"?>
<rsm:CrossIndustryInvoice xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
  xmlns:ram="urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"
  xmlns:udt="urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100">
  <rsm:ExchangedDocument><ram:ID>RN-2026-4471</ram:ID><ram:TypeCode>380</ram:TypeCode>
    <ram:IssueDateTime><udt:DateTimeString format="102">20261020</udt:DateTimeString></ram:IssueDateTime></rsm:ExchangedDocument>
  <rsm:SupplyChainTradeTransaction>
    <ram:ApplicableHeaderTradeAgreement><ram:SellerTradeParty><ram:Name>Reinigungsbedarf Nord GmbH</ram:Name>
      <ram:SpecifiedTaxRegistration><ram:ID schemeID="VA">DE123456789</ram:ID></ram:SpecifiedTaxRegistration></ram:SellerTradeParty></ram:ApplicableHeaderTradeAgreement>
    <ram:ApplicableHeaderTradeSettlement>
      <ram:SpecifiedTradePaymentTerms><ram:DueDateDateTime><udt:DateTimeString format="102">20261119</udt:DateTimeString></ram:DueDateDateTime></ram:SpecifiedTradePaymentTerms>
      <ram:SpecifiedTradeSettlementHeaderMonetarySummation><ram:TaxBasisTotalAmount>150.00</ram:TaxBasisTotalAmount>
        <ram:TaxTotalAmount currencyID="EUR">28.50</ram:TaxTotalAmount><ram:GrandTotalAmount>178.50</ram:GrandTotalAmount><ram:DuePayableAmount>178.50</ram:DuePayableAmount>
      </ram:SpecifiedTradeSettlementHeaderMonetarySummation>
    </ram:ApplicableHeaderTradeSettlement>
  </rsm:SupplyChainTradeTransaction>
</rsm:CrossIndustryInvoice>"""


def _artikel(client, kopf, nummer="RM-100", name="Allzweckreiniger 10 l", **extra):
    r = client.post("/api/artikel", json={"nummer": nummer, "name": name, "einheit": "Kanister", "einkaufspreis": 18.9, "verkaufspreis": 29.9, "kategorie": "Reinigungsmittel", **extra}, headers=kopf)
    assert r.status_code == 200, r.text
    return r.json()["artikel"]


def test_01_artikel_crud_csv_import_rechte(client):
    chef, _ = registrieren(client, email="chef@artikel-d.de", firma="Artikel D", name="Chef")
    buero, bd = einladen(client, chef, name="Bea Büro", email="bea@artikel-d.de", role="buero")
    ma, _ = einladen(client, chef, name="Anna", email="anna@artikel-d.de", role="mitarbeiter")
    a = _artikel(client, chef)
    assert a["einkaufspreis"] == 18.9 and a["aktiv"] is True
    assert client.post("/api/artikel", json={"nummer": "rm-100".upper(), "name": "Doppelt"}, headers=chef).status_code == 409
    # Büro ohne „kostensaetze“: kein Einkaufspreis sehen oder setzen; Mitarbeiter: nur die Auswahlliste ohne Preise
    liste = client.get("/api/artikel", headers=buero).json()
    assert liste["ek_sichtbar"] is False and "einkaufspreis" not in liste["artikel"][0] and liste["artikel"][0]["verkaufspreis"] == 29.9
    assert client.get("/api/artikel", headers=chef).json()["artikel"][0]["einkaufspreis"] == 18.9
    assert client.post("/api/artikel", json={"nummer": "X-1", "name": "Mit EK", "einkaufspreis": 5}, headers=buero).status_code == 403
    assert client.post("/api/artikel", json={"nummer": "X-1", "name": "Ohne EK", "verkaufspreis": 9}, headers=buero).status_code == 200
    assert client.put(f"/api/artikel/{a['id']}", json={"nummer": "RM-100", "name": "Allzweckreiniger 10 l Zitrone", "verkaufspreis": 31}, headers=buero).status_code == 200
    assert next(x for x in client.get("/api/artikel", headers=chef).json()["artikel"] if x["id"] == a["id"])["einkaufspreis"] == 18.9   # EK blieb
    assert client.get("/api/artikel", headers=ma).status_code == 403
    auswahl = client.get("/api/artikel/auswahl", headers=ma).json()["artikel"]
    assert auswahl and all("einkaufspreis" not in x and "verkaufspreis" not in x for x in auswahl)
    # CSV-Vorschau: Trennzeichen, Anführungszeichen mit Semikolon im Text, Dezimalkomma, drei Fehlerzeilen mit Zeilennummer
    v = client.post("/api/artikel/import", data={"vorschau": "1"}, files={"datei": ("artikel.csv", CSV, "text/csv")}, headers=chef)
    assert v.status_code == 200, v.text
    v = v.json()
    assert v["vorschau"] is True and v["anzahl"] == 2 and [f["zeile"] for f in v["fehler"]] == [4, 5, 6]
    assert v["artikel"][0]["name"] == "Glasreiniger; 5 l" and v["artikel"][0]["einkaufspreis"] == 12.4 and v["artikel"][0]["verkaufspreis"] == 19.9
    assert "keine Zahl" in v["fehler"][1]["grund"] and "mehrfach" in v["fehler"][2]["grund"]
    i1 = client.post("/api/artikel/import", data={"vorschau": "0"}, files={"datei": ("artikel.csv", CSV, "text/csv")}, headers=chef).json()
    assert i1["angelegt"] == 2 and i1["aktualisiert"] == 0 and len(i1["fehler"]) == 3
    i2 = client.post("/api/artikel/import", data={"vorschau": "0"}, files={"datei": ("artikel.csv", CSV, "text/csv")}, headers=chef).json()
    assert i2["angelegt"] == 0 and i2["aktualisiert"] == 2
    rm210 = next(x for x in client.get("/api/artikel", headers=chef).json()["artikel"] if x["nummer"] == "RM-210")
    assert rm210["einkaufspreis"] == 12.4 and rm210["kategorie"] == "Reinigungsmittel" and rm210["quelle"] == "csv"
    # Büro-Import ohne Kostensätze: Einkaufspreise werden ausdrücklich nicht übernommen
    i3 = client.post("/api/artikel/import", data={"vorschau": "0"}, files={"datei": ("neu.csv", "Artikelnummer;Bezeichnung;EK\nNEU-1;Neu;9,99\n".encode(), "text/csv")}, headers=buero).json()
    assert i3["angelegt"] == 1 and any(f["zeile"] == 0 and "Kostensätze" in f["grund"] for f in i3["fehler"])
    assert next(x for x in client.get("/api/artikel", headers=chef).json()["artikel"] if x["nummer"] == "NEU-1").get("einkaufspreis") is None
    # Löschen: unbenutzt → weg; Artikel in einem Angebot → deaktiviert; Einkauf wird in die Angebotskalkulation vorbelegt
    vm = next(x for x in client.get("/api/artikel", headers=chef).json()["artikel"] if x["nummer"] == "VM-050")
    assert client.delete(f"/api/artikel/{vm['id']}", headers=chef).json()["deaktiviert"] is False
    k = client.post("/api/kunden", json={"name": "Kunde"}, headers=chef).json()["kunde"]
    ag = client.post("/api/kundenangebote", json={"titel": "Material", "customer_id": k["id"], "positionen": [{"art": "material", "text": "Allzweckreiniger", "artikel_id": a["id"], "menge": 4, "einheit": "Kanister", "einzelpreis": 29.9}]}, headers=chef)
    assert ag.status_code == 200, ag.text
    ag = ag.json()["angebot"]
    assert ag["positionen"][0]["artikel_id"] == a["id"] and ag["kalkulation"]["je_position"][ag["positionen"][0]["id"]]["material_ek"] == 75.6
    assert client.delete(f"/api/artikel/{a['id']}", headers=chef).json()["deaktiviert"] is True
    assert client.get("/api/artikel?aktiv=true", headers=chef).json()["artikel"] and all(x["id"] != a["id"] for x in client.get("/api/artikel?aktiv=true", headers=chef).json()["artikel"])


def test_02_materialverbrauch_mitarbeiter_ohne_preise(client):
    chef, _ = registrieren(client, email="chef@material-d.de", firma="Material D", name="Chef")
    buero, bd = einladen(client, chef, name="Bea Büro", email="bea@material-d.de", role="buero")
    anna, ad = einladen(client, chef, name="Anna", email="anna@material-d.de", role="mitarbeiter")
    ben, _ = einladen(client, chef, name="Ben", email="ben@material-d.de", role="mitarbeiter", passwort="geheim456")
    p = projekt(client, chef, name="Objekt", employee_ids=[ad["user"]["id"]])
    a = _artikel(client, chef)
    r = client.post(f"/api/projekte/{p['id']}/material", json={"artikel_id": a["id"], "menge": 2}, headers=anna)
    assert r.status_code == 200, r.text
    m1 = r.json()["material"]
    assert m1["bezeichnung"] == "Allzweckreiniger 10 l" and m1["einheit"] == "Kanister" and "einkaufspreis" not in m1 and "kosten" not in m1 and m1["status"] == "erfasst"
    assert client.post(f"/api/projekte/{p['id']}/material", json={"artikel_id": a["id"], "menge": 1}, headers=ben).status_code in (403, 404)   # nicht zugeteilt
    assert client.post(f"/api/projekte/{p['id']}/material", json={"menge": 1}, headers=anna).status_code == 400                               # weder Artikel noch Name
    m2 = client.post(f"/api/projekte/{p['id']}/material", json={"bezeichnung": "Müllsäcke", "menge": 1, "einheit": "Rolle"}, headers=anna).json()["material"]
    assert client.post(f"/api/projekte/{p['id']}/material", json={"artikel_id": a["id"], "menge": 1, "einkaufspreis": 1}, headers=anna).status_code == 403   # Preis setzen nur Büro mit Recht
    # Sichten: Mitarbeiterin nur eigene ohne Preise; Büro ohne Kostensätze ohne Preise, aber mit Prüfstand; Inhaber mit Kosten
    eigene = client.get(f"/api/projekte/{p['id']}/material", headers=anna).json()
    assert len(eigene["material"]) == 2 and eigene["kosten_summe"] is None and eigene["preise_sichtbar"] is False
    bs = client.get(f"/api/projekte/{p['id']}/material", headers=buero).json()
    assert bs["preise_sichtbar"] is False and bs["ungeprueft"] == 2 and all("kosten" not in x for x in bs["material"])
    cs = client.get(f"/api/projekte/{p['id']}/material", headers=chef).json()
    assert cs["preise_sichtbar"] is True and cs["kosten_summe"] == 37.8 and next(x for x in cs["material"] if x["id"] == m1["id"])["einkaufspreis"] == 18.9
    assert next(x for x in cs["material"] if x["id"] == m2["id"])["kosten"] is None
    # Eigene Buchung ändern und löschen; Prüfung durch das Büro mit Recht „kalkulation“ (Preis setzen braucht „kostensaetze“)
    assert client.put(f"/api/material/{m1['id']}", json={"artikel_id": a["id"], "menge": 3}, headers=anna).status_code == 200
    assert client.delete(f"/api/material/{m2['id']}", headers=anna).status_code == 200
    assert client.post(f"/api/material/{m1['id']}/pruefen", json={}, headers=buero).status_code == 403
    assert client.put(f"/api/mitarbeiter/{bd['user']['id']}", json={"rechte": {"kalkulation": True}}, headers=chef).status_code == 200
    g = client.post(f"/api/material/{m1['id']}/pruefen", json={}, headers=buero)
    assert g.status_code == 200 and g.json()["material"]["status"] == "geprueft" and "kosten" not in g.json()["material"]
    assert client.post(f"/api/material/{m1['id']}/pruefen", json={"einkaufspreis": 20}, headers=buero).status_code == 403
    assert client.get(f"/api/projekte/{p['id']}/material", headers=chef).json()["kosten_summe"] == 56.7
    assert client.put(f"/api/material/{m1['id']}", json={"menge": 1}, headers=anna).status_code == 409   # geprüft: nur noch Büro
    assert client.delete(f"/api/artikel/{a['id']}", headers=chef).json()["deaktiviert"] is True


def test_03_eingangsrechnungen_und_nachkalkulation(client):
    chef, cd = registrieren(client, email="chef@nachkalk-d.de", firma="Nachkalk D", name="Chef")
    buero, bd = einladen(client, chef, name="Bea Büro", email="bea@nachkalk-d.de", role="buero")
    anna, ad = einladen(client, chef, name="Anna", email="anna@nachkalk-d.de", role="mitarbeiter")
    ben, bend = einladen(client, chef, name="Ben", email="ben@nachkalk-d.de", role="mitarbeiter", passwort="geheim456")
    assert client.put("/api/firma", json={"kalkulation": {"stundensatz": 20, "gemeinkosten_prozent": 10, "risiko_prozent": 0, "gewinn_prozent": 20, "lohnnebenkosten_prozent": 25}}, headers=chef).status_code == 200
    assert client.put(f"/api/mitarbeiter/{ad['user']['id']}/lohndaten", json={"hourly_wage": 16}, headers=chef).status_code == 200   # 16 € + 25 % = 20 €/Std.
    # Angebot mit Kalkulation → Annahme → Auftrag (Projekt P mit Auftragswert 700 netto, Abrechnung nach Stunden)
    k = client.post("/api/kunden", json={"name": "Kunde N"}, headers=chef).json()["kunde"]
    ag = client.post("/api/kundenangebote", json={"titel": "Objekt N", "customer_id": k["id"], "positionen": [
        {"art": "stunden", "text": "Montage", "menge": 10, "einheit": "Std.", "einzelpreis": 50}, {"art": "material", "text": "Material", "menge": 2, "einheit": "Stk.", "einzelpreis": 100}]}, headers=chef).json()["angebot"]
    ids = {p["art"]: p["id"] for p in ag["positionen"]}
    assert client.put(f"/api/kundenangebote/{ag['id']}/kalkulation", json={"positionen": {ids["stunden"]: {"stunden": 10}, ids["material"]: {"material_ek": 150, "gemeinkosten_prozent": 0}}}, headers=chef).status_code == 200
    assert client.post(f"/api/kundenangebote/{ag['id']}/senden", json={"ohne_email": True}, headers=chef).status_code == 200
    assert client.post(f"/api/kundenangebote/{ag['id']}/annahme", json={"von_name": "Kunde N"}, headers=chef).status_code == 200
    p = client.post(f"/api/kundenangebote/{ag['id']}/auftrag", json={}, headers=chef).json()["projekt"]
    assert p["auftrag"]["netto"] == 700.0 and p["abrechnungsart_projekt"] == "stunden" and p["hourly_rate"] == 50
    assert client.put(f"/api/projekte/{p['id']}", json={"name": p["name"], "hourly_rate": 50, "customer_id": k["id"], "employee_ids": [ad["user"]["id"], bend["user"]["id"]]}, headers=chef).status_code == 200
    zeit(client, anna, p["id"], date="2026-10-05", start="08:00", ende="12:00")   # 4 h × 20 € = 80 €
    zeit(client, ben, p["id"], date="2026-10-05", start="08:00", ende="10:00")    # 2 h × Firmensatz 20 € = 40 €
    a = _artikel(client, chef)
    m = client.post(f"/api/projekte/{p['id']}/material", json={"artikel_id": a["id"], "menge": 2}, headers=chef).json()["material"]   # 37,80 € ungeprüft
    # Beleg hochladen: XRechnung-XML liefert einen Vorschlag (nur Vorschlag); Eingangsrechnung mit Aufteilung auf Kostenarten
    up = client.post("/api/eingangsrechnungen/datei", files={"datei": ("rechnung.xml", XRECHNUNG, "application/xml")}, headers=chef)
    assert up.status_code == 200, up.text
    vs = up.json()["vorschlag"]
    assert vs["lieferant"] == "Reinigungsbedarf Nord GmbH" and vs["rechnungsnummer"] == "RN-2026-4471" and vs["rechnungsdatum"] == "2026-10-20" and vs["faellig_am"] == "2026-11-19"
    assert vs["netto"] == 150.0 and vs["ust"] == 28.5 and vs["brutto"] == 178.5 and vs["lieferant_ustid"] == "DE123456789" and vs["quelle"] == "xrechnung"
    beleg = up.json()["dokument"]
    daten = {"lieferant": vs["lieferant"], "rechnungsnummer": vs["rechnungsnummer"], "rechnungsdatum": vs["rechnungsdatum"], "faellig_am": vs["faellig_am"], "netto": 150, "ust": 28.5,
             "zuordnungen": [{"project_id": p["id"], "betrag_netto": 100, "kostenart": "fremdleistung"}, {"project_id": p["id"], "betrag_netto": 50, "kostenart": "material"}], "dokument_id": beleg["id"]}
    assert client.post("/api/eingangsrechnungen", json={**daten, "zuordnungen": [{"project_id": p["id"], "betrag_netto": 200, "kostenart": "material"}]}, headers=chef).status_code == 400   # Aufteilung > netto
    assert client.post("/api/eingangsrechnungen", json={**daten, "brutto": 170}, headers=chef).status_code in (400, 422)   # brutto ≠ netto + USt
    r = client.post("/api/eingangsrechnungen", json=daten, headers=chef)
    assert r.status_code == 200, r.text
    er = r.json()["eingangsrechnung"]
    assert er["status"] == "erfasst" and er["brutto"] == 178.5 and er["zugeordnet_netto"] == 150.0 and er["nicht_zugeordnet_netto"] == 0
    assert client.post("/api/eingangsrechnungen", json=daten, headers=chef).status_code == 409   # Dublette
    doppelt = client.post("/api/eingangsrechnungen", json={**daten, "erzwingen": True, "dokument_id": None}, headers=chef).json()["eingangsrechnung"]
    assert doppelt["dublette_hinweis"] is True
    assert client.post(f"/api/eingangsrechnungen/{doppelt['id']}/storno", json={"grund": "versehentlich doppelt"}, headers=chef).json()["eingangsrechnung"]["status"] == "storniert"
    # Beleg: nur mit Recht „rechnungen“, Mitarbeiter nie
    assert client.get(f"/api/dokumente/{beleg['id']}/datei", headers=chef).status_code == 200
    assert client.get(f"/api/dokumente/{beleg['id']}/datei", headers=anna).status_code in (403, 404)
    # Nachkalkulation vor der Prüfung: ungeprüftes Material und ungeprüfte Rechnung zählen nicht, Hinweise benennen das
    assert client.get(f"/api/projekte/{p['id']}/nachkalkulation", headers=buero).status_code == 403
    n = client.get(f"/api/projekte/{p['id']}/nachkalkulation", headers=chef).json()["nachkalkulation"]
    assert n["auftragswert_netto"] == 700.0 and n["plan"]["selbstkosten"] == 370.0 and n["plan"]["lohn"] == 200.0 and n["plan"]["material"] == 150.0
    assert n["ist"]["personal"] == 120.0 and n["ist"]["material"] == 0 and n["ist"]["fremdleistung"] == 0 and n["ist"]["material_ungeprueft"] == 37.8
    assert n["stunden"]["gebucht"] == 6.0 and n["stunden"]["freigegeben"] == 0 and n["stunden"]["plan_kalkulation"] == 10.0
    assert n["vollstaendig"] is False and any("ungeprüft" in h for h in n["hinweise"]) and any("nicht freigegeben" in h for h in n["hinweise"]) and any("Eingangsrechnung" in h for h in n["hinweise"])
    assert n["deckungsbeitrag"]["ergebnis"] is None and n["abrechenbar_stunden_netto"] == 300.0 and len(n["je_person"]) == 2
    assert {x["modell"] for x in n["je_person"]} == {"stundenlohn", "firmensatz"}
    # Prüfen → Kosten zählen; Büro mit „kalkulation“, aber ohne „kostensaetze“ sieht keine Personenkosten
    assert client.post(f"/api/material/{m['id']}/pruefen", json={}, headers=chef).status_code == 200
    assert client.post(f"/api/eingangsrechnungen/{er['id']}/pruefen", headers=chef).json()["eingangsrechnung"]["status"] == "geprueft"
    n = client.get(f"/api/projekte/{p['id']}/nachkalkulation", headers=chef).json()["nachkalkulation"]
    assert n["ist"]["material"] == 87.8 and n["ist"]["fremdleistung"] == 100.0 and n["ist"]["direkt"] == 307.8 and n["ist"]["gemeinkosten_zuschlag"] == 30.78 and n["ist"]["gesamt"] == 338.58
    assert n["abweichung"] == -31.42 and n["deckungsbeitrag"]["erwartet"] == 350.0 and n["deckungsbeitrag"]["aktuell"] == 392.2
    assert [x["ist"] for x in n["kostenarten"] if x["art"] in ("personal", "material", "fremdleistung")] == [120.0, 87.8, 100.0]
    assert client.put(f"/api/mitarbeiter/{bd['user']['id']}", json={"rechte": {"kalkulation": True}}, headers=chef).status_code == 200
    nb = client.get(f"/api/projekte/{p['id']}/nachkalkulation", headers=buero).json()["nachkalkulation"]
    assert nb["je_person"] == [] and nb["ist"]["personal"] == 120.0
    # Bezahlen, danach keine Änderung mehr; Übersicht und Startseite
    assert client.post(f"/api/eingangsrechnungen/{er['id']}/bezahlt", json={"am": "2026-11-02", "zahlungsart": "Überweisung"}, headers=chef).json()["eingangsrechnung"]["status"] == "bezahlt"
    assert client.put(f"/api/eingangsrechnungen/{er['id']}", json=daten, headers=chef).status_code == 409
    assert client.delete(f"/api/eingangsrechnungen/{er['id']}", headers=chef).status_code == 409
    liste = client.get("/api/eingangsrechnungen", headers=chef).json()
    assert liste["zaehler"] == {"bezahlt": 1, "storniert": 1} and liste["offen_brutto"] == 0
    ue = client.get("/api/nachkalkulation", headers=chef).json()["projekte"]
    assert len(ue) == 1 and ue[0]["project_id"] == p["id"] and ue[0]["warnung"] is False and ue[0]["ist"] == 338.58
    client.post("/api/eingangsrechnungen", json={**daten, "rechnungsnummer": "RN-2026-4472", "dokument_id": None, "zuordnungen": []}, headers=chef)
    d = client.get("/api/dashboard", headers=chef).json()
    assert d["kostenabweichungen"]["projekte"] == 1 and d["kostenabweichungen"]["anzahl"] == 0
    assert "eingangsrechnungen_pruefen" in {x["art"] for x in client.get("/api/dashboard/aufgaben", headers=chef).json()["punkte"]}
    # Projektakte enthält Material, Eingangsrechnungen mit Beleg und Nachkalkulation
    akte = client.post(f"/api/projekte/{p['id']}/projektakte", headers=chef).json()["projektakte"]
    namen = zipfile.ZipFile(io.BytesIO(client.get(f"/api/projektakten/{akte['id']}.zip", headers=chef).content)).namelist()
    assert "07_Material/material.csv" in namen and "08_Eingangsrechnungen/eingangsrechnungen.csv" in namen and "09_Nachkalkulation/nachkalkulation.json" in namen
    assert any(n_.startswith("08_Eingangsrechnungen/RN-2026-4471") for n_ in namen)
