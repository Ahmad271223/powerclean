"""Stufe C (24.10.2026): Kundenangebote – Positionen mit Titeln, Alternativ-/Eventualpositionen, Zuschlägen und Rabatt; Nummernkreis; PDF;
Vorlagen und Kopien; Rechte; Senden mit PDF-Anhang und Antwortlink; Versionen; Online-Annahme; Auftrag → Kundenprojekt; interne Kalkulation."""
import asyncio
from datetime import date, timedelta

import config
import db as dbmodul
import mail
from conftest import einladen, registrieren

POSITIONEN = [
    {"art": "titel", "text": "Regelmäßige Reinigung"},
    {"art": "stunden", "text": "Unterhaltsreinigung", "beschreibung": "Mo–Fr", "menge": 40, "einheit": "Std.", "einzelpreis": 32.5},
    {"art": "material", "text": "Reinigungsmittel", "menge": 1, "einheit": "Psch.", "einzelpreis": 45},
    {"art": "titel", "text": "Zusatzleistungen"},
    {"art": "pauschal", "text": "Grundreinigung", "menge": 1, "einheit": "Psch.", "einzelpreis": 480},
    {"art": "leistung", "text": "Glasreinigung", "menge": 120, "einheit": "m²", "einzelpreis": 2.2, "alternativ": True},
    {"art": "leistung", "text": "Teppichreinigung", "menge": 2, "einheit": "Stk.", "einzelpreis": 100, "eventual": True},
    {"art": "text", "text": "Alle Preise verstehen sich zzgl. gesetzlicher Umsatzsteuer."},
]


def _kunde(client, kopf, name="Hausverwaltung Nord", email="schulz@hv-nord.example", **extra):
    r = client.post("/api/kunden", json={"name": name, "contact": "Frau Schulz", "street": "Nordring 5", "zip_code": "12345", "city": "Musterstadt", "email": email, **extra}, headers=kopf)
    assert r.status_code == 200, r.text
    return r.json()["kunde"]


def _angebot(client, kopf, **extra):
    r = client.post("/api/kundenangebote", json={"titel": "Unterhaltsreinigung Nordring", "positionen": POSITIONEN, **extra}, headers=kopf)
    assert r.status_code == 200, r.text
    return r.json()["angebot"]


def test_01_entwurf_summen_nummern_pdf_vorlagen_rechte(client):
    chef, cd = registrieren(client, email="chef@angebot-c.de", firma="Angebot C", name="Chef")
    buero, bd = einladen(client, chef, name="Bea Büro", email="bea@angebot-c.de", role="buero")
    ma, _ = einladen(client, chef, name="Anna", email="anna@angebot-c.de", role="mitarbeiter")
    assert client.put("/api/firma", json={"angebot_prefix": "ANG-"}, headers=chef).status_code == 200
    kunde = _kunde(client, chef)
    a = _angebot(client, chef, customer_id=kunde["id"], zuschlaege=[{"text": "Kleinauftragszuschlag", "prozent": 10}], rabatt_prozent=5)
    jahr = date.today().year
    assert a["nummer"] == f"ANG-{jahr}-0001" and a["version"] == 1 and a["status"] == "entwurf" and a["kunde"]["name"] == "Hausverwaltung Nord"
    assert a["gueltig_bis"] == (date.today() + timedelta(days=30)).isoformat()
    # Nummerierung: Titel 1 / 1.1 / 1.2, Titel 2 / 2.1 / 2.2 / 2.3, Textzeile ohne Nummer
    assert [p["nr"] for p in a["positionen"]] == ["1", "1.1", "1.2", "2", "2.1", "2.2", "2.3", ""]
    s = a["summen"]
    assert s["positionen_netto"] == 1825.0 and s["zuschlaege"][0]["betrag"] == 182.5 and s["rabatt_betrag"] == 100.38
    assert s["netto"] == 1907.12 and s["ust_satz"] == 19 and s["ust"] == 362.35 and s["brutto"] == 2269.47
    assert s["alternativ_netto"] == 264.0 and s["eventual_netto"] == 200.0 and s["steuer"]["kategorie"] == "S"
    assert [t["netto"] for t in s["titel"]] == [1345.0, 480.0]
    assert [p.get("zaehlt") for p in a["positionen"] if p["art"] not in ("titel", "text")] == [True, True, True, False, False]
    assert "kalkulation" in a   # Inhaber sieht die (noch leere) Kalkulation
    # PDF
    pdf = client.get(f"/api/kundenangebote/{a['id']}/angebot.pdf", headers=chef)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF") and pdf.headers["content-type"] == "application/pdf"
    # Kleinunternehmer und § 13b
    assert client.put("/api/firma", json={"small_business": True}, headers=chef).status_code == 200
    a2 = client.put(f"/api/kundenangebote/{a['id']}", json={"titel": "Unterhaltsreinigung Nordring"}, headers=chef).json()["angebot"]
    assert a2["summen"]["ust"] == 0 and a2["summen"]["steuer"]["kategorie"] == "E" and a2["summen"]["brutto"] == a2["summen"]["netto"]
    assert client.put("/api/firma", json={"small_business": False}, headers=chef).status_code == 200
    bau = _kunde(client, chef, name="Bauträger Süd", email="bau@sued.example", reverse_charge=True)
    a3 = _angebot(client, chef, customer_id=bau["id"])
    assert a3["summen"]["steuer"]["kategorie"] == "AE" and a3["summen"]["ust"] == 0 and a3["nummer"].endswith("-0002")
    # Vorlage aus dem Angebot, neues Angebot aus der Vorlage, Kopie
    v = client.post(f"/api/kundenangebote/{a['id']}/als-vorlage", json={"name": "Unterhaltsreinigung Standard", "gueltig_tage": 14}, headers=chef)
    assert v.status_code == 200 and len(v.json()["vorlage"]["positionen"]) == 8
    assert len(client.get("/api/kundenangebote/vorlagen", headers=buero).json()["vorlagen"]) == 1
    aus_vorlage = client.post("/api/kundenangebote", json={"vorlage_id": v.json()["vorlage"]["id"], "customer_id": kunde["id"]}, headers=buero).json()["angebot"]
    assert aus_vorlage["nummer"].endswith("-0003") and len(aus_vorlage["positionen"]) == 8 and aus_vorlage["summen"]["netto"] == 1907.12
    assert aus_vorlage["gueltig_bis"] == (date.today() + timedelta(days=14)).isoformat() and aus_vorlage["titel"] == "Unterhaltsreinigung Nordring"
    kopie = client.post(f"/api/kundenangebote/{a['id']}/kopieren", headers=chef).json()["angebot"]
    assert kopie["nummer"].endswith("-0004") and kopie["summen"]["brutto"] == 2269.47 and kopie["status"] == "entwurf"
    # Löschen eines Entwurfs: Nummer wird nicht wiederverwendet
    assert client.delete(f"/api/kundenangebote/{kopie['id']}", headers=chef).status_code == 200
    assert _angebot(client, chef)["nummer"].endswith("-0005")
    liste = client.get("/api/kundenangebote", headers=chef).json()
    assert liste["zaehler"]["entwurf"] == 4 and liste["offen_netto"] > 0 and all("positionen" not in x for x in liste["angebote"])
    # Rechte: Mitarbeiter nie; Büro nur mit Recht „angebote“; Kalkulation nur mit Recht „kalkulation“
    assert client.get("/api/kundenangebote", headers=ma).status_code == 403
    assert client.get(f"/api/oeffentlich/angebot/{a['id']}").status_code == 404   # die interne ID ist kein Antwortlink
    sicht = client.get(f"/api/kundenangebote/{a['id']}", headers=buero).json()
    assert "kalkulation" not in sicht["angebot"] and sicht["kann_kalkulation"] is False and all("kalkulation" not in p for p in sicht["angebot"]["positionen"])
    assert client.get(f"/api/kundenangebote/{a['id']}/kalkulation", headers=buero).status_code == 403
    assert client.put(f"/api/mitarbeiter/{bd['user']['id']}", json={"rechte": {"angebote": False}}, headers=chef).status_code == 200
    assert client.get("/api/kundenangebote", headers=buero).status_code == 403
    assert client.post("/api/kundenangebote", json={"titel": "x"}, headers=buero).status_code == 403


def test_02_senden_versionen_online_annahme_auftrag(client, monkeypatch):
    gesendet = []
    monkeypatch.setattr(mail, "SOFORT_ZUSTELLEN", False)
    monkeypatch.setattr(mail, "VERSAND", lambda an, betreff, text, anhaenge=None: gesendet.append((an, betreff, text, anhaenge)))
    monkeypatch.setattr(config, "SMTP_HOST", "smtp.test")
    monkeypatch.setattr(config, "SMTP_ABSENDER", "noreply@test.de")
    chef, cd = registrieren(client, email="chef@angebot-s.de", firma="Angebot S", name="Chef")
    kunde = _kunde(client, chef)
    a = _angebot(client, chef, customer_id=kunde["id"], positionen=[{"art": "pauschal", "text": "Grundreinigung", "menge": 1, "einheit": "Psch.", "einzelpreis": 480},
                                                                     {"art": "material", "text": "Pflegemittel", "menge": 2, "einheit": "l", "einzelpreis": 10}])
    assert client.post(f"/api/kundenangebote/{a['id']}/senden", json={"nachricht": "Gerne kommen wir zur Besichtigung."}, headers=chef).status_code == 200
    r = client.post(f"/api/kundenangebote/{a['id']}/senden", json={}, headers=chef)   # zweites Senden: gleiche Version, kein neues Festschreiben
    assert r.status_code == 200
    g = client.get(f"/api/kundenangebote/{a['id']}", headers=chef).json()
    a = g["angebot"]
    assert a["status"] == "gesendet" and a["token"] and a["pdf_pfad"] and (config.DATA_DIR / a["pdf_pfad"]).is_file() and len(a["versand"]) == 2
    assert g["antwortlink"].endswith(f"/angebot/{a['token']}")
    emails = client.get("/api/firma/emails", headers=chef).json()["emails"]
    es = [x for x in emails if x["art"] == "angebot_kunde"]
    assert len(es) == 2 and all(x["an"] == "schulz@hv-nord.example" and x["anhaenge"][0]["name"].startswith("Angebot_") and a["token"] in x["text"] for x in es)
    assert any("Besichtigung" in x["text"] for x in es)
    assert asyncio.run(mail.ausgang_abarbeiten()) == 2
    an, betreff, text, anhaenge = gesendet[-1]
    assert an == "schulz@hv-nord.example" and "Angebot" in betreff and anhaenge and anhaenge[0][0].endswith(".pdf") and open(anhaenge[0][1], "rb").read(4) == b"%PDF"
    # Gesendet = unveränderlich
    assert client.put(f"/api/kundenangebote/{a['id']}", json={"titel": "anders"}, headers=chef).status_code == 409
    assert client.delete(f"/api/kundenangebote/{a['id']}", headers=chef).status_code == 409
    # Öffentlicher Antwortlink: keine Kalkulation, kein Verlauf; falscher Token 404
    o = client.get(f"/api/oeffentlich/angebot/{a['token']}")
    assert o.status_code == 200
    oa = o.json()["angebot"]
    assert oa["antwort_moeglich"] is True and oa["firma"]["name"] == "Angebot S" and "verlauf" not in oa and "kalkulation" not in oa and all("kalkulation" not in p for p in oa["positionen"])
    assert client.get(f"/api/oeffentlich/angebot/{a['token']}/angebot.pdf").content.startswith(b"%PDF")
    assert client.get("/api/oeffentlich/angebot/gibt-es-nicht-1234567890").status_code == 404
    # Neue Version: alte wird „ersetzt“, der alte Link kann nicht mehr beantwortet werden
    v2 = client.post(f"/api/kundenangebote/{a['id']}/version", headers=chef)
    assert v2.status_code == 200
    v2 = v2.json()["angebot"]
    assert v2["version"] == 2 and v2["status"] == "entwurf" and v2["nummer"] == a["nummer"] and v2["vorgaenger_id"] == a["id"] and v2["token"] is None
    alt = client.get(f"/api/kundenangebote/{a['id']}", headers=chef).json()["angebot"]
    assert alt["status"] == "ersetzt" and alt["ersetzt_durch"] == v2["id"]
    assert client.get(f"/api/oeffentlich/angebot/{a['token']}").json()["angebot"]["antwort_moeglich"] is False
    assert client.post(f"/api/oeffentlich/angebot/{a['token']}/antwort", json={"entscheidung": "angenommen", "name": "Frau Schulz"}).status_code == 409
    assert client.post(f"/api/kundenangebote/{a['id']}/version", headers=chef).status_code == 409   # schon ersetzt
    liste = client.get("/api/kundenangebote", headers=chef).json()["angebote"]
    assert [x["version"] for x in liste] == [2] and len(client.get("/api/kundenangebote?alle=1", headers=chef).json()["angebote"]) == 2
    # Version 2 mit neuem Preis senden, Kunde nimmt online an → Benachrichtigung und E-Mail an die Firma
    pos = [{**{k: p[k] for k in ("id", "art", "text", "menge", "einheit")}, "einzelpreis": 450 if p["art"] == "pauschal" else p["einzelpreis"]} for p in v2["positionen"]]
    v2 = client.put(f"/api/kundenangebote/{v2['id']}", json={"positionen": pos}, headers=chef).json()["angebot"]
    assert v2["summen"]["netto"] == 470.0
    assert client.post(f"/api/kundenangebote/{v2['id']}/senden", json={}, headers=chef).status_code == 200
    v2 = client.get(f"/api/kundenangebote/{v2['id']}", headers=chef).json()["angebot"]
    assert v2["token"] and v2["token"] != a["token"]
    assert client.get(f"/api/oeffentlich/angebot/{a['token']}").json()["angebot"]["version"] == 2   # alter Link zeigt auf die aktuelle Version
    r = client.post(f"/api/oeffentlich/angebot/{v2['token']}/antwort", json={"entscheidung": "angenommen", "name": "Frau Schulz", "text": "Bitte ab 1.11. starten"})
    assert r.status_code == 200 and r.json()["angebot"]["status"] == "angenommen" and r.json()["angebot"]["annahme"]["art"] == "online"
    assert client.post(f"/api/oeffentlich/angebot/{v2['token']}/antwort", json={"entscheidung": "abgelehnt", "name": "Frau Schulz"}).status_code == 409
    n = client.get("/api/benachrichtigungen", headers=chef).json()
    n = n.get("benachrichtigungen", n) if isinstance(n, dict) else n
    assert any(x["art"] == "angebot_angenommen" and "Frau Schulz" in x["text"] for x in n)
    assert any(x["art"] == "angebot_angenommen" and x["an"] == "chef@angebot-s.de" for x in client.get("/api/firma/emails", headers=chef).json()["emails"])
    # Auftrag: neues Kundenprojekt mit Pauschale (keine Stundenposition), Kundendaten übernommen; kein zweiter Auftrag
    r = client.post(f"/api/kundenangebote/{v2['id']}/auftrag", json={}, headers=chef)
    assert r.status_code == 200, r.text
    p = r.json()["projekt"]
    assert p["name"] == "Unterhaltsreinigung Nordring" and p["customer_name"] == "Hausverwaltung Nord" and p["abrechnungsart_projekt"] == "pauschal" and p["pauschale_netto"] == 470.0
    pr = client.get(f"/api/projekte/{p['id']}", headers=chef).json()["projekt"]
    assert pr["auftrag"]["nummer"] == v2["nummer"] and pr["auftrag"]["netto"] == 470.0 and len(pr["auftrag"]["positionen"]) == 2
    assert client.get(f"/api/kundenangebote/{v2['id']}", headers=chef).json()["angebot"]["auftrag"]["project_id"] == p["id"]
    assert client.post(f"/api/kundenangebote/{v2['id']}/auftrag", json={}, headers=chef).status_code == 409
    assert client.post(f"/api/kundenangebote/{v2['id']}/version", headers=chef).status_code == 409   # angenommen → Nachtrag statt Version
    assert len(client.get(f"/api/kundenangebote/{v2['id']}", headers=chef).json()["versionen"]) == 2
    # Angebot an einem Projekt: Liste je Projekt; Projektakte enthält den Ordner 06_Angebote
    assert [x["id"] for x in client.get(f"/api/kundenangebote?project_id={p['id']}", headers=chef).json()["angebote"]] == [v2["id"]]
    akte = client.post(f"/api/projekte/{p['id']}/projektakte", headers=chef)
    assert akte.status_code == 200, akte.text
    import io
    import zipfile
    z = zipfile.ZipFile(io.BytesIO(client.get(f"/api/projektakten/{akte.json()['projektakte']['id']}.zip", headers=chef).content))
    namen = z.namelist()
    assert any(n_.startswith("06_Angebote/") and n_.endswith("_v2.pdf") for n_ in namen) and "06_Angebote/angebote.csv" in namen and "06_Angebote/auftrag.json" in namen
    # Ohne E-Mail übergeben, Annahme durch das Büro erfassen; Zurückziehen; Ablauf der Gültigkeit; Ablehnung mit Grund
    b = _angebot(client, chef, customer_id=kunde["id"])
    assert client.post(f"/api/kundenangebote/{b['id']}/senden", json={"ohne_email": True}, headers=chef).status_code == 200
    r = client.post(f"/api/kundenangebote/{b['id']}/annahme", json={"von_name": "Herr Nord", "art": "unterschrift", "am": date.today().isoformat()}, headers=chef)
    assert r.status_code == 200 and r.json()["angebot"]["status"] == "angenommen" and r.json()["angebot"]["annahme"]["von_name"] == "Herr Nord"
    c = _angebot(client, chef, customer_id=kunde["id"])
    assert client.post(f"/api/kundenangebote/{c['id']}/zurueckziehen", json={"grund": "x"}, headers=chef).status_code == 409   # noch nicht gesendet
    assert client.post(f"/api/kundenangebote/{c['id']}/senden", json={"ohne_email": True}, headers=chef).status_code == 200
    assert client.post(f"/api/kundenangebote/{c['id']}/zurueckziehen", json={"grund": "Preis falsch kalkuliert"}, headers=chef).json()["angebot"]["status"] == "zurueckgezogen"
    d = _angebot(client, chef, customer_id=kunde["id"])
    assert client.post(f"/api/kundenangebote/{d['id']}/senden", json={"ohne_email": True}, headers=chef).status_code == 200
    asyncio.run(dbmodul.db().kundenangebote.update_one({"id": d["id"]}, {"$set": {"gueltig_bis": (date.today() - timedelta(days=1)).isoformat()}}))
    assert client.get(f"/api/kundenangebote/{d['id']}", headers=chef).json()["angebot"]["status"] == "abgelaufen"
    assert client.get(f"/api/oeffentlich/angebot/{client.get(f'/api/kundenangebote/{d['id']}', headers=chef).json()['angebot']['token']}").json()["angebot"]["antwort_moeglich"] is False
    dv = client.post(f"/api/kundenangebote/{d['id']}/version", headers=chef).json()["angebot"]   # abgelaufen → neue Version erlaubt
    assert dv["version"] == 2 and dv["gueltig_bis"] >= date.today().isoformat()
    e_ = _angebot(client, chef, customer_id=kunde["id"])
    assert client.post(f"/api/kundenangebote/{e_['id']}/ablehnen", json={"grund": "Kunde hat anderen Anbieter"}, headers=chef).json()["angebot"]["ablehnung"]["grund"] == "Kunde hat anderen Anbieter"
    # Anfrage → Entwurf
    f_ = client.post("/api/kundenangebote", json={"status": "anfrage", "titel": "Treppenhaus", "kunde_frei": {"name": "WEG Süd", "email": "weg@sued.example"}, "anfrage": {"text": "3 Aufgänge", "kanal": "Telefon"}}, headers=chef).json()["angebot"]
    assert f_["status"] == "anfrage" and f_["kunde"]["name"] == "WEG Süd" and f_["customer_id"] is None
    assert client.post(f"/api/kundenangebote/{f_['id']}/senden", json={}, headers=chef).status_code == 400   # ohne Positionen
    f_ = client.put(f"/api/kundenangebote/{f_['id']}", json={"status": "entwurf", "positionen": [{"art": "pauschal", "text": "Treppenhaus wöchentlich", "menge": 4, "einheit": "Wo.", "einzelpreis": 90}]}, headers=chef).json()["angebot"]
    assert f_["status"] == "entwurf" and f_["summen"]["netto"] == 360.0
    uebersicht = client.get("/api/dashboard", headers=chef).json()
    assert uebersicht["angebote_offen"]["anzahl"] >= 1
    aufgaben = client.get("/api/dashboard/aufgaben", headers=chef).json()
    arten = {p_["art"] for p_ in (aufgaben.get("punkte") or aufgaben.get("aufgaben") or [])}
    assert "auftraege_anlegen" in arten   # Angebot b ist angenommen, aber noch ohne Auftrag


def test_03_kalkulation_aufschlag_marge_deckungsbeitrag(client):
    chef, cd = registrieren(client, email="chef@kalk-c.de", firma="Kalk C", name="Chef")
    buero, bd = einladen(client, chef, name="Bea Büro", email="bea@kalk-c.de", role="buero")
    # Kalkulationssätze der Firma: nur mit Recht „kostensaetze“ (Inhaber hat es, Büro standardmäßig nicht)
    assert client.put("/api/firma", json={"kalkulation": {"stundensatz": 30, "gemeinkosten_prozent": 10, "risiko_prozent": 0, "gewinn_prozent": 20}}, headers=buero).status_code == 403
    assert client.put("/api/firma", json={"kalkulation": {"stundensatz": 30, "gemeinkosten_prozent": 10, "risiko_prozent": 0, "gewinn_prozent": 20}}, headers=chef).status_code == 200
    assert client.get("/api/firma", headers=chef).json()["firma"]["kalkulation"]["stundensatz"] == 30
    assert "kalkulation" not in client.get("/api/firma", headers=buero).json()["firma"]
    kunde = _kunde(client, chef)
    a = _angebot(client, chef, customer_id=kunde["id"], positionen=[
        {"art": "stunden", "text": "Montage", "menge": 10, "einheit": "Std.", "einzelpreis": 50},
        {"art": "material", "text": "Material", "menge": 2, "einheit": "Stk.", "einzelpreis": 100},
        {"art": "leistung", "text": "Entsorgung", "menge": 1, "einheit": "Psch.", "einzelpreis": 80}])
    assert a["summen"]["netto"] == 780.0
    ids = {p["art"]: p["id"] for p in a["positionen"]}
    k = client.put(f"/api/kundenangebote/{a['id']}/kalkulation", json={"positionen": {ids["stunden"]: {"stunden": 10}, ids["material"]: {"material_ek": 150, "gemeinkosten_prozent": 0, "risiko_prozent": 0}}}, headers=chef)
    assert k.status_code == 200, k.text
    k = k.json()["kalkulation"]
    st = k["je_position"][ids["stunden"]]
    assert st["lohn"] == 300.0 and st["gemeinkosten"] == 30.0 and st["selbstkosten"] == 330.0 and st["vk"] == 500.0 and st["gewinn"] == 170.0
    assert st["aufschlag_prozent"] == 51.52 and st["marge_prozent"] == 34.0 and st["deckungsbeitrag"] == 200.0 and st["stundenverrechnungssatz"] == 50.0 and st["vk_vorschlag"] == 396.0
    mt = k["je_position"][ids["material"]]
    assert mt["selbstkosten"] == 150.0 and mt["gewinn"] == 50.0 and mt["aufschlag_prozent"] == 33.33 and mt["marge_prozent"] == 25.0
    # Gesamt: Entsorgung ohne Kalkulation → unvollständig, kein irreführender Gewinn
    assert k["vollstaendig"] is False and k["kalkuliert"] == 2 and k["zaehlend"] == 3 and any("ohne Kalkulation" in h for h in k["hinweise"])
    assert k["selbstkosten"] == 480.0 and k["gewinn"] == 300.0 and k["deckungsbeitrag"] == 330.0
    k = client.put(f"/api/kundenangebote/{a['id']}/kalkulation", json={"positionen": {ids["leistung"]: {"fremd": 60, "gemeinkosten_prozent": 0}}}, headers=chef).json()["kalkulation"]
    assert k["vollstaendig"] is True and k["selbstkosten"] == 540.0 and k["gewinn"] == 240.0 and k["aufschlag_prozent"] == 44.44 and k["marge_prozent"] == 30.77
    assert "Aufschlag" in k["erklaerung"]["aufschlag"] and "Marge" in k["erklaerung"]["marge"]
    # Assistent: Preisvorschlag übernehmen (nur im Entwurf)
    r = client.post(f"/api/kundenangebote/{a['id']}/kalkulation/uebernehmen?position_id={ids['stunden']}", headers=chef)
    assert r.status_code == 200 and r.json()["uebernommen"] == 1
    neu = r.json()["angebot"]
    assert next(p for p in neu["positionen"] if p["id"] == ids["stunden"])["einzelpreis"] == 39.6 and neu["summen"]["netto"] == 676.0
    # Vertraulich: Büro ohne Recht sieht nichts, mit Recht alles; Kunde (Antwortlink) nie
    assert client.get(f"/api/kundenangebote/{a['id']}/kalkulation", headers=buero).status_code == 403
    assert client.put(f"/api/kundenangebote/{a['id']}/kalkulation", json={"positionen": {}}, headers=buero).status_code == 403
    assert client.put(f"/api/mitarbeiter/{bd['user']['id']}", json={"rechte": {"kalkulation": True}}, headers=chef).status_code == 200
    sicht = client.get(f"/api/kundenangebote/{a['id']}", headers=buero).json()
    assert sicht["kann_kalkulation"] is True and sicht["angebot"]["kalkulation"]["vollstaendig"] is True
    assert client.get("/api/firma", headers=buero).json()["firma"].get("kalkulation") is None   # Kostensätze bleiben ohne „kostensaetze“ verborgen
    assert client.post(f"/api/kundenangebote/{a['id']}/senden", json={"ohne_email": True}, headers=chef).status_code == 200
    token = client.get(f"/api/kundenangebote/{a['id']}", headers=chef).json()["angebot"]["token"]
    oeff = client.get(f"/api/oeffentlich/angebot/{token}").json()["angebot"]
    assert "kalkulation" not in oeff and all("kalkulation" not in p for p in oeff["positionen"])
    # Kalkulation darf nach dem Senden verfeinert werden (ändert das Kundendokument nicht), Preise nicht mehr
    assert client.put(f"/api/kundenangebote/{a['id']}/kalkulation", json={"positionen": {ids["stunden"]: {"stunden": 12}}}, headers=chef).status_code == 200
    assert client.post(f"/api/kundenangebote/{a['id']}/kalkulation/uebernehmen", headers=chef).status_code == 409
