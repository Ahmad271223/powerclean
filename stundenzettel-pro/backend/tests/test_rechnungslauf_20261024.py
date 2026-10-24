"""Stufe E (24.10.2026): Abschlags- und Schlussrechnungen (kumulativ), Rechnung aus dem Auftrag, Storno/Korrekturbeleg, Gutschrift, Teilzahlungen,
Rechnungsversand mit Anhang, Mahnwesen mit Stufen, Fristen und Nachweisen – ohne den Nummernkreis oder die E-Rechnung zu beschädigen."""
import asyncio
from datetime import date, timedelta

from lxml import etree

import config
import db as dbmodul
import mail
from conftest import projekt, registrieren, zeit

NS = {"rsm": "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100", "ram": "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"}
FIRMA = {"street": "Werkstraße 1", "zip_code": "12345", "city": "Musterstadt", "vat_id": "DE123456789", "iban": "DE89370400440532013000", "email": "info@firma.de", "phone": "0123", "owner": "Chef"}
KUNDE = {"name": "Hausverwaltung Nord", "contact": "Frau Schulz", "street": "Nordring 5", "zip_code": "12345", "city": "Musterstadt", "email": "schulz@hv-nord.example", "leitweg_id": "04011000-1234512345-06"}


def _xml(client, kopf, rid):
    r = client.get(f"/api/rechnungen/{rid}/xrechnung.xml", headers=kopf)
    assert r.status_code == 200, r.text
    return etree.fromstring(r.content)


def _auftrag(client, kopf, netto=10000.0, name="Sanierung"):
    k = client.post("/api/kunden", json=KUNDE, headers=kopf).json()["kunde"]
    ag = client.post("/api/kundenangebote", json={"titel": name, "customer_id": k["id"], "positionen": [
        {"art": "pauschal", "text": "Sanierung komplett", "menge": 1, "einheit": "Psch.", "einzelpreis": netto}]}, headers=kopf).json()["angebot"]
    assert client.post(f"/api/kundenangebote/{ag['id']}/senden", json={"ohne_email": True}, headers=kopf).status_code == 200
    assert client.post(f"/api/kundenangebote/{ag['id']}/annahme", json={"von_name": "Frau Schulz"}, headers=kopf).status_code == 200
    return client.post(f"/api/kundenangebote/{ag['id']}/auftrag", json={}, headers=kopf).json()["projekt"], k


def test_01_abschlaege_kumulativ_und_schlussrechnung(client):
    chef, cd = registrieren(client, email="chef@abschlag-e.de", firma="Abschlag E", name="Chef")
    assert client.put("/api/firma", json=FIRMA, headers=chef).status_code == 200
    p, k = _auftrag(client, chef)
    ab = client.get(f"/api/projekte/{p['id']}/abrechnung", headers=chef).json()
    assert ab["basis"]["basis_netto"] == 10000.0 and ab["kann_abschlag"] and ab["kann_schluss"] and ab["kann_pauschal"] and ab["naechster_abschlag_nr"] == 1
    # Vorschau ohne Nummer, dann 1. Abschlag 30 % → 3.000 netto / 3.570 brutto; Nummernkreis läuft mit RE-JJJJ-0001
    v = client.post("/api/rechnungen/auftrag", json={"project_id": p["id"], "art": "abschlag", "leistungsstand_prozent": 30, "nur_pruefen": True}, headers=chef).json()["vorschau"]
    assert v["net"] == 3000.0 and v["gross"] == 3570.0 and v["info"]["kumulativ"] is True
    r1 = client.post("/api/rechnungen/auftrag", json={"project_id": p["id"], "art": "abschlag", "leistungsstand_prozent": 30}, headers=chef)
    assert r1.status_code == 200, r1.text
    r1 = r1.json()["rechnung"]
    jahr = date.today().year
    assert r1["number"] == f"RE-{jahr}-0001" and r1["art"] == "abschlag" and r1["abschlag_nr"] == 1 and r1["net"] == 3000.0 and r1["gross"] == 3570.0 and r1["month"] == -1
    assert client.post("/api/rechnungen/auftrag", json={"project_id": p["id"], "art": "abschlag", "leistungsstand_prozent": 20}, headers=chef).status_code == 400   # unter dem Stand
    assert client.post("/api/rechnungen/auftrag", json={"project_id": p["id"], "art": "abschlag", "betrag_netto": 500}, headers=chef).status_code == 409           # Arten nicht mischen
    assert client.post("/api/rechnungen/auftrag", json={"project_id": p["id"], "art": "pauschal"}, headers=chef).status_code == 409                               # Abschläge laufen
    # PDF stellt aus (festgeschrieben), XML: Teilrechnung 326; danach 2. Abschlag 60 % kumuliert → 6.000 − 3.000 = 3.000 netto, Abzugszeile negativ
    assert client.get(f"/api/rechnungen/{r1['id']}/rechnung.pdf", headers=chef).content.startswith(b"%PDF")
    x = _xml(client, chef, r1["id"])
    assert x.find("rsm:ExchangedDocument/ram:TypeCode", NS).text == "326"
    r2 = client.post("/api/rechnungen/auftrag", json={"project_id": p["id"], "art": "abschlag", "leistungsstand_prozent": 60}, headers=chef).json()["rechnung"]
    assert r2["number"].endswith("-0002") and r2["net"] == 3000.0 and r2["abschlag_nr"] == 2 and [z["amount"] for z in r2["extras"]] == [6000.0, -3000.0] and r2["vorherige"] == [r1["id"]]
    # Teilzahlung auf Abschlag 1: 2.000 → teilbezahlt, offen 1.570; Überzahlung abgelehnt; Rest zahlen → bezahlt
    z = client.post(f"/api/rechnungen/{r1['id']}/zahlungen", json={"betrag": 2000, "art": "ueberweisung"}, headers=chef)
    assert z.status_code == 200 and z.json()["rechnung"]["status"] == "teilbezahlt" and z.json()["rechnung"]["offen_betrag"] == 1570.0
    assert client.post(f"/api/rechnungen/{r1['id']}/zahlungen", json={"betrag": 1600}, headers=chef).status_code == 400
    z = client.post(f"/api/rechnungen/{r1['id']}/zahlungen", json={"betrag": 1570, "am": "2026-11-02"}, headers=chef).json()["rechnung"]
    assert z["status"] == "bezahlt" and z["paid_at"] == "2026-11-02" and len(z["zahlungen"]) == 2
    zid = z["zahlungen"][1]["id"]
    assert client.delete(f"/api/rechnungen/{r1['id']}/zahlungen/{zid}", headers=chef).json()["rechnung"]["status"] == "teilbezahlt"
    # Freigegebener Nachtrag (500) fließt in die Basis; Schlussrechnung: 10.500 − 6.000 = 4.500 netto, zwei Abzugszeilen, XML mit zwei Vorgängerbelegen
    asyncio.run(dbmodul.db().nachtraege.insert_one({"id": "n1", "firma_id": cd["firma"]["id"], "project_id": p["id"], "status": "freigegeben", "betrag_netto": 500, "titel": "Zusatzfläche", "nummer": "N-1"}))
    s = client.post("/api/rechnungen/auftrag", json={"project_id": p["id"], "art": "schluss", "leistung_von": "2026-09-01", "leistung_bis": "2026-10-31"}, headers=chef)
    assert s.status_code == 200, s.text
    s = s.json()["rechnung"]
    assert s["art"] == "schluss" and s["net"] == 4500.0 and s["gross"] == 5355.0 and s["abschlaege_netto"] == 6000.0 and len(s["vorherige"]) == 2
    assert [z_["amount"] for z_ in s["extras"]] == [10000.0, 500.0, -3000.0, -3000.0] and s["offen_aus_abschlaegen_brutto"] == 5140.0   # 1.570 + 3.570 offen
    x = _xml(client, chef, s["id"])
    assert x.find("rsm:ExchangedDocument/ram:TypeCode", NS).text == "380"
    refs = x.findall("rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeSettlement/ram:InvoiceReferencedDocument/ram:IssuerAssignedID", NS)
    assert [e.text for e in refs] == [r1["number"], r2["number"]]
    assert client.post("/api/rechnungen/auftrag", json={"project_id": p["id"], "art": "schluss"}, headers=chef).status_code == 409
    assert client.post("/api/rechnungen/auftrag", json={"project_id": p["id"], "art": "abschlag", "leistungsstand_prozent": 80}, headers=chef).status_code == 409
    ab = client.get(f"/api/projekte/{p['id']}/abrechnung", headers=chef).json()
    assert ab["summen"]["gestellt_netto"] == 10500.0 and ab["summen"]["rest_netto"] == 0 and ab["summen"]["bezahlt_brutto"] == 2000.0 and ab["schluss"]["number"] == s["number"]
    liste = client.get("/api/rechnungen", headers=chef).json()["rechnungen"]
    assert [r["art"] for r in liste] == ["schluss", "abschlag", "abschlag"] and liste[2]["offen_betrag"] == 1570.0 and liste[2]["status_name"] == "Teilweise bezahlt"
    # Pauschaler (nicht kumulativer) Abschlag in einem zweiten Projekt, dann Rechnung aus dem Auftrag ist gesperrt, PDF-Daten ohne Wochenraster
    p2, _ = _auftrag(client, chef, netto=2000.0, name="Kleinauftrag")
    r3 = client.post("/api/rechnungen/auftrag", json={"project_id": p2["id"], "art": "abschlag", "betrag_netto": 800}, headers=chef).json()["rechnung"]
    assert r3["kumulativ"] is False and r3["net"] == 800.0
    d = client.get(f"/api/rechnungen/{r3['id']}/daten", headers=chef).json()
    assert d["server_pdf"] is True and d["eintraege"] == [] and d["rechnung"]["festgeschrieben_at"]


def test_02_storno_gutschrift_rechnung_aus_auftrag_versand(client, monkeypatch):
    gesendet = []
    monkeypatch.setattr(mail, "SOFORT_ZUSTELLEN", False)
    monkeypatch.setattr(mail, "VERSAND", lambda an, betreff, text, anhaenge=None: gesendet.append((an, betreff, text, anhaenge)))
    monkeypatch.setattr(config, "SMTP_HOST", "smtp.test")
    monkeypatch.setattr(config, "SMTP_ABSENDER", "noreply@test.de")
    chef, cd = registrieren(client, email="chef@storno-e.de", firma="Storno E", name="Chef")
    assert client.put("/api/firma", json=FIRMA, headers=chef).status_code == 200
    # Monatsrechnung aus Zeiten (bestehender Weg) → Entwurf ohne Storno löschen; ausgestellt → Storno mit Gegenbuchung
    k = client.post("/api/kunden", json=KUNDE, headers=chef).json()["kunde"]
    p = projekt(client, chef, name="Objekt", customer_id=k["id"])
    zeit(client, chef, p["id"], date="2026-10-05", start="08:00", ende="12:00")
    m = client.post("/api/rechnungen/anlegen", json={"project_id": p["id"], "year": 2026, "month": 10}, headers=chef).json()["rechnung"]
    assert m["art"] == "monat" and m["net"] == 120.0
    assert client.post(f"/api/rechnungen/{m['id']}/storno", json={"grund": "falsch"}, headers=chef).status_code == 409   # Entwurf: zurücksetzen statt Storno
    assert client.get(f"/api/rechnungen/{m['id']}/rechnung.pdf", headers=chef).status_code == 200
    st = client.post(f"/api/rechnungen/{m['id']}/storno", json={"grund": "Stunden doppelt erfasst"}, headers=chef)
    assert st.status_code == 200, st.text
    storno, orig = st.json()["storno"], st.json()["rechnung"]
    assert storno["art"] == "storno" and storno["net"] == -120.0 and storno["gross"] == -142.8 and storno["festgeschrieben_at"] and storno["storno_von"]["number"] == m["number"]
    assert orig["status"] == "storniert" and orig["storno_nummer"] == storno["number"]
    assert client.post(f"/api/rechnungen/{m['id']}/storno", json={"grund": "nochmal"}, headers=chef).status_code == 409
    assert client.post(f"/api/rechnungen/{storno['id']}/storno", json={"grund": "x"}, headers=chef).status_code == 409
    assert client.post(f"/api/rechnungen/{storno['id']}/zahlungen", json={"betrag": 10}, headers=chef).status_code == 409
    x = _xml(client, chef, storno["id"])
    assert x.find("rsm:ExchangedDocument/ram:TypeCode", NS).text == "384"
    assert x.find("rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeSettlement/ram:InvoiceReferencedDocument/ram:IssuerAssignedID", NS).text == m["number"]
    assert client.get(f"/api/rechnungen/{storno['id']}/rechnung.pdf", headers=chef).content.startswith(b"%PDF")
    # Gutschrift: negativ gespeichert, XML als Credit Note (381) mit positiven Beträgen
    g = client.post("/api/rechnungen/gutschrift", json={"customer_id": k["id"], "grund": "Kulanz", "bezug_nummer": m["number"], "positionen": [{"text": "Nachlass Reinigung", "quantity": 1, "unit": "Psch.", "unit_price": 50}]}, headers=chef)
    assert g.status_code == 200, g.text
    g = g.json()["rechnung"]
    assert g["art"] == "gutschrift" and g["net"] == -50.0 and g["gross"] == -59.5 and g["project_id"] is None
    x = _xml(client, chef, g["id"])
    assert x.find("rsm:ExchangedDocument/ram:TypeCode", NS).text == "381"
    assert x.find("rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeSettlement/ram:SpecifiedTradeSettlementHeaderMonetarySummation/ram:GrandTotalAmount", NS).text == "59.50"
    # Rechnung aus dem Auftrag (pauschal) mit Auftragspositionen; Versand per E-Mail mit PDF-Anhang (ZUGFeRD, weil Kundendaten vollständig)
    pa, _ = _auftrag(client, chef, netto=1500.0, name="Pauschalauftrag")
    r = client.post("/api/rechnungen/auftrag", json={"project_id": pa["id"], "art": "pauschal", "text": "Vielen Dank für den Auftrag."}, headers=chef).json()["rechnung"]
    assert r["art"] == "pauschal" and r["net"] == 1500.0 and r["extras"][0]["text"].startswith("1 Sanierung komplett")
    v = client.post(f"/api/rechnungen/{r['id']}/senden", json={"nachricht": "Anbei die Rechnung."}, headers=chef)
    assert v.status_code == 200, v.text
    assert v.json()["profil"] == "zugferd" and v.json()["rechnung"]["versand"][0]["an"] == "schulz@hv-nord.example" and v.json()["rechnung"]["festgeschrieben_at"]
    assert asyncio.run(mail.ausgang_abarbeiten()) == 1 and gesendet[-1][3][0][0].startswith("Rechnung_RE-")
    e = next(x_ for x_ in client.get("/api/firma/emails", headers=chef).json()["emails"] if x_["art"] == "rechnung")
    assert "Anbei die Rechnung." in e["text"] and e["anhaenge"]
    # Als bezahlt markieren (bestehender Weg) legt die Zahlung über den Rest an; wieder öffnen leert sie
    b = client.put(f"/api/rechnungen/{r['id']}", json={"status": "bezahlt"}, headers=chef).json()["rechnung"]
    assert b["status"] == "bezahlt" and b["bezahlt_betrag"] == 1785.0 and len(b["zahlungen"]) == 1
    assert client.put(f"/api/rechnungen/{r['id']}", json={"status": "offen"}, headers=chef).json()["rechnung"]["bezahlt_betrag"] == 0.0


def test_03_mahnwesen_stufen_fristen_nachweise(client, monkeypatch):
    gesendet = []
    monkeypatch.setattr(mail, "SOFORT_ZUSTELLEN", False)
    monkeypatch.setattr(mail, "VERSAND", lambda an, betreff, text, anhaenge=None: gesendet.append((an, betreff, text, anhaenge)))
    monkeypatch.setattr(config, "SMTP_HOST", "smtp.test")
    monkeypatch.setattr(config, "SMTP_ABSENDER", "noreply@test.de")
    chef, cd = registrieren(client, email="chef@mahn-e.de", firma="Mahn E", name="Chef")
    assert client.put("/api/firma", json={**FIRMA, "payment_days": 14}, headers=chef).status_code == 200
    p, k = _auftrag(client, chef, netto=1000.0)
    vor40 = (date.today() - timedelta(days=40)).isoformat()
    r = client.post("/api/rechnungen/auftrag", json={"project_id": p["id"], "art": "pauschal", "invoice_date": vor40}, headers=chef).json()["rechnung"]
    assert r["faellig_am"] == (date.today() - timedelta(days=26)).isoformat()
    assert client.get("/api/mahnwesen", headers=chef).json()["rechnungen"] == []          # Entwurf: nicht ausgestellt → kein Mahnwesen
    assert client.get(f"/api/rechnungen/{r['id']}/rechnung.pdf", headers=chef).status_code == 200
    client.post(f"/api/rechnungen/{r['id']}/zahlungen", json={"betrag": 190}, headers=chef)   # Teilzahlung: 1.000 offen
    mw = client.get("/api/mahnwesen", headers=chef).json()
    assert len(mw["rechnungen"]) == 1 and mw["offen_brutto"] == 1000.0 and mw["jetzt_faellig"] == 1
    e = mw["rechnungen"][0]
    assert e["tage_ueberfaellig"] == 26 and e["naechste_stufe"] == 1 and e["jetzt_faellig"] is True and e["kunde_email"] == "schulz@hv-nord.example" and e["offen_betrag"] == 1000.0
    assert client.post(f"/api/rechnungen/{r['id']}/mahnung", json={"stufe": 2}, headers=chef).status_code == 409   # Stufen nicht überspringen
    m1 = client.post(f"/api/rechnungen/{r['id']}/mahnung", json={}, headers=chef)
    assert m1.status_code == 200, m1.text
    m1 = m1.json()["mahnung"]
    assert m1["stufe"] == 1 and m1["name"] == "Zahlungserinnerung" and m1["gebuehr"] == 0 and m1["an"] == "schulz@hv-nord.example" and m1["email_id"] and (config.DATA_DIR / m1["pdf_pfad"]).is_file()
    assert asyncio.run(mail.ausgang_abarbeiten()) == 1 and "Zahlungserinnerung" in gesendet[-1][1] and gesendet[-1][3][0][0].startswith("Zahlungserinnerung_")
    assert client.get(f"/api/rechnungen/{r['id']}/mahnung/1.pdf", headers=chef).content.startswith(b"%PDF")
    # Stufe 2 erst nach der Frist (14 Tage) – oder ausdrücklich erzwungen; Gebühr aus den Firmenregeln
    assert client.post(f"/api/rechnungen/{r['id']}/mahnung", json={}, headers=chef).status_code == 409
    assert client.put("/api/firma", json={"mahnwesen": {"gebuehr_mahnung": 5, "mahnung_tage": 0}}, headers=chef).status_code == 200
    m2 = client.post(f"/api/rechnungen/{r['id']}/mahnung", json={"per_email": False}, headers=chef).json()["mahnung"]
    assert m2["stufe"] == 2 and m2["gebuehr"] == 5.0 and m2["gesamt"] == 1005.0 and m2["an"] == "" and m2["email_id"] is None
    m3 = client.post(f"/api/rechnungen/{r['id']}/mahnung", json={"erzwingen": True, "text": "Letzte Chance.", "gebuehr": 10}, headers=chef).json()["mahnung"]
    assert m3["stufe"] == 3 and m3["text"] == "Letzte Chance." and m3["gebuehr"] == 10.0
    assert client.post(f"/api/rechnungen/{r['id']}/mahnung", json={"erzwingen": True}, headers=chef).status_code == 409   # alle Stufen durch
    rr = client.get("/api/rechnungen", headers=chef).json()["rechnungen"][0]
    assert rr["mahnstufe"] == 3 and len(client.get("/api/mahnwesen", headers=chef).json()["rechnungen"]) == 1
    d = client.get("/api/dashboard", headers=chef).json()
    assert d["zahlungen_ueberfaellig"]["anzahl"] == 1 and d["zahlungen_ueberfaellig"]["summe"] == 1000.0 and d["rechnungen_offen"]["summe"] == 1000.0
    # Zahlung schließt den Vorgang: nichts mehr im Mahnwesen
    assert client.post(f"/api/rechnungen/{r['id']}/zahlungen", json={"betrag": 1000}, headers=chef).json()["rechnung"]["status"] == "bezahlt"
    assert client.get("/api/mahnwesen", headers=chef).json()["rechnungen"] == []
    assert client.get("/api/dashboard", headers=chef).json()["zahlungen_ueberfaellig"]["anzahl"] == 0
