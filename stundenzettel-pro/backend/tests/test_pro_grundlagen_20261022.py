# -*- coding: utf-8 -*-
"""Server-Version (Wunsch Ahmad 22.10.2026): Registrierung, Rollen, Projekte, Zeiten, Stempeluhr, Abwesenheiten,
Rechnungen, Exporte, Import aus der kostenlosen App, API-Schlüssel, Lizenz und Protokoll."""
from datetime import datetime, timedelta

from conftest import einladen, projekt, registrieren, zeit


def test_01_registrierung_login_und_firma(client):
    kopf, daten = registrieren(client)
    assert daten["user"]["role"] == "inhaber" and daten["firma"]["name"] == "PowerClean Test"
    assert daten["plan"]["status"] == "test" and daten["plan"]["tage_rest"] >= 13
    # doppelte E-Mail
    r = client.post("/api/auth/registrieren", json={"firma_name": "X", "name": "Y", "email": "chef@beispiel.de", "password": "geheim123"})
    assert r.status_code == 409
    # Login falsch / richtig
    assert client.post("/api/auth/login", json={"email": "chef@beispiel.de", "password": "falsch123"}).status_code == 401
    r = client.post("/api/auth/login", json={"email": "CHEF@beispiel.de", "password": "geheim123"})
    assert r.status_code == 200 and r.json()["user"]["email"] == "chef@beispiel.de"
    # Firmendaten ändern, Mitarbeiter sehen keine Bankdaten
    r = client.put("/api/firma", json={"iban": "DE00 1234", "default_hourly_rate": 32.5, "small_business": False, "vat_rate": 19}, headers=kopf)
    assert r.status_code == 200 and r.json()["firma"]["iban"] == "DE00 1234"
    ma, _ = einladen(client, kopf)
    f = client.get("/api/firma", headers=ma).json()["firma"]
    assert "iban" not in f and f["name"] == "PowerClean Test"
    # Passwort ändern
    assert client.put("/api/auth/passwort", json={"alt": "geheim123", "neu": "neuesPasswort9"}, headers=kopf).status_code == 200
    assert client.post("/api/auth/login", json={"email": "chef@beispiel.de", "password": "neuesPasswort9"}).status_code == 200
    # Protokoll hat Einträge
    p = client.get("/api/protokoll", headers=kopf).json()["eintraege"]
    assert any(e["aktion"] == "firma.registriert" for e in p) and any(e["aktion"] == "mitarbeiter.eingeladen" for e in p)


def test_02_rollen_und_mitarbeiter(client):
    kopf, _ = registrieren(client)
    ma, ma_daten = einladen(client, kopf)
    assert ma_daten["user"]["role"] == "mitarbeiter"
    # Mitarbeiter darf nichts verwalten
    assert client.post("/api/kunden", json={"name": "K"}, headers=ma).status_code == 403
    assert client.post("/api/projekte", json={"name": "P"}, headers=ma).status_code == 403
    assert client.get("/api/protokoll", headers=ma).status_code == 403
    assert client.get("/api/rechnungen", headers=ma).status_code == 403
    # Büro-Rolle
    buero, _ = einladen(client, kopf, name="Bea Büro", email="bea@beispiel.de", role="buero")
    assert client.post("/api/kunden", json={"name": "Kunde A"}, headers=buero).status_code == 200
    assert client.get("/api/firma/api-tokens", headers=buero).status_code == 403          # nur Inhaber
    # Einladung erneuern geht nur, solange kein Passwort gesetzt ist
    uid = ma_daten["user"]["id"]
    assert client.post(f"/api/mitarbeiter/{uid}/einladung", headers=kopf).status_code == 400
    # Deaktivieren: nicht sich selbst, nicht den letzten Inhaber
    chef_id = client.get("/api/auth/ich", headers=kopf).json()["user"]["id"]
    assert client.put(f"/api/mitarbeiter/{chef_id}", json={"active": False}, headers=kopf).status_code == 400
    assert client.put(f"/api/mitarbeiter/{uid}", json={"active": False}, headers=kopf).status_code == 200
    assert client.get("/api/auth/ich", headers=ma).status_code == 401
    liste = client.get("/api/mitarbeiter", headers=kopf).json()["mitarbeiter"]
    assert [m["name"] for m in liste] == ["Ahmad Chef", "Bea Büro"]
    # Nutzergrenze der Lizenz
    r = client.post("/api/admin/plan", json={"email": "chef@beispiel.de", "status": "aktiv", "nutzer_max": 2}, headers={"X-Admin-Token": "betreiber-test"})
    assert r.status_code == 200
    r = client.post("/api/mitarbeiter", json={"name": "Dritte", "email": "d@beispiel.de"}, headers=kopf)
    assert r.status_code == 402


def test_03_kunden_projekte_und_sichtbarkeit(client):
    kopf, _ = registrieren(client)
    k = client.post("/api/kunden", json={"name": "Reinigung Müller GmbH", "street": "Weg 1", "zip_code": "10115", "city": "Berlin", "reverse_charge": True}, headers=kopf).json()["kunde"]
    p = projekt(client, kopf, customer_id=k["id"])
    assert p["customer_name"] == "Reinigung Müller GmbH" and "10115 Berlin" in p["customer_address"] and p["reverse_charge"] is True
    # Kunde ändern zieht Projekt nach
    client.put(f"/api/kunden/{k['id']}", json={"name": "Müller Gebäudeservice", "reverse_charge": False}, headers=kopf)
    p2 = client.get(f"/api/projekte/{p['id']}", headers=kopf).json()["projekt"]
    assert p2["customer_name"] == "Müller Gebäudeservice" and p2["reverse_charge"] is False
    # Kunde mit Projekten nicht löschbar
    assert client.delete(f"/api/kunden/{k['id']}", headers=kopf).status_code == 400
    # Sichtbarkeit: zugewiesenes Projekt nur für die zugewiesene Person
    ma, ma_d = einladen(client, kopf)
    ma2, ma2_d = einladen(client, kopf, name="Tom", email="tom@beispiel.de")
    p_tom = projekt(client, kopf, name="Nur Tom", employee_ids=[ma2_d["user"]["id"]])
    assert {x["name"] for x in client.get("/api/projekte", headers=ma).json()["projekte"]} == {"Objekt Sparkasse"}
    assert {x["name"] for x in client.get("/api/projekte", headers=ma2).json()["projekte"]} == {"Objekt Sparkasse", "Nur Tom"}
    assert client.get(f"/api/projekte/{p_tom['id']}", headers=ma).status_code == 404
    # Archivieren / Standardsatz aus der Firma
    client.put("/api/firma", json={"default_hourly_rate": 28}, headers=kopf)
    p3 = projekt(client, kopf, name="Ohne Satz", hourly_rate=0)
    assert p3["hourly_rate"] == 28
    r = client.put(f"/api/projekte/{p3['id']}", json={"name": "Ohne Satz", "archived": True}, headers=kopf)
    assert r.json()["projekt"]["archived"] is True
    assert [x["name"] for x in client.get("/api/projekte?archiviert=true", headers=kopf).json()["projekte"]] == ["Ohne Satz"]


def test_04_zeiten_eintragen_aendern_serie(client):
    kopf, _ = registrieren(client)
    p = projekt(client, kopf)
    ma, ma_d = einladen(client, kopf)
    # Büro: Anzahl-Eintrag ohne Person zählt Mitarbeiterstunden
    e = zeit(client, kopf, p["id"], workers=3, pause=30)
    assert e["net_minutes"] == 210 and e["workers"] == 3 and e["user_id"] is None
    # Mitarbeiter: immer eigene Person, Anzahl 1
    e2 = zeit(client, ma, p["id"], date="2026-10-06", workers=5, user_id="jemand-anderes")
    assert e2["user_id"] == ma_d["user"]["id"] and e2["workers"] == 1 and e2["user_name"] == "Mia Mitarbeiterin"
    # Statistik am Projekt
    pr = client.get(f"/api/projekte/{p['id']}", headers=kopf).json()["projekt"]
    assert pr["total_minutes"] == 630 + 240 and pr["entry_count"] == 2 and pr["last_activity_at"] == "2026-10-06"
    # Mitarbeiter darf fremde Einträge nicht ändern, eigene schon
    assert client.put(f"/api/zeiten/{e['id']}", json={"end_time": "13:00"}, headers=ma).status_code == 403
    r = client.put(f"/api/zeiten/{e2['id']}", json={"end_time": "13:00"}, headers=ma)
    assert r.status_code == 200 and r.json()["eintrag"]["net_minutes"] == 300
    # Ungültiges
    assert client.post("/api/zeiten", json={"project_id": p["id"], "date": "2024-01-01", "start_time": "08:00", "end_time": "09:00"}, headers=kopf).status_code == 422
    assert client.post("/api/zeiten", json={"project_id": p["id"], "date": "2026-10-07", "start_time": "08:00", "end_time": "08:00"}, headers=kopf).status_code == 400
    # Serie Mo–Fr für zwei Wochen, vorhandene Tage werden übersprungen
    r = client.post("/api/zeiten/serie", json={"project_id": p["id"], "from_date": "2026-10-05", "to_date": "2026-10-18", "weekdays": [0, 1, 2, 3, 4],
                                               "start_time": "06:00", "end_time": "09:00", "workers": 2}, headers=kopf)
    assert r.status_code == 200 and r.json()["angelegt"] == 10
    r = client.post("/api/zeiten/serie", json={"project_id": p["id"], "from_date": "2026-10-05", "to_date": "2026-10-18", "start_time": "06:00", "end_time": "09:00"}, headers=kopf)
    assert r.json()["angelegt"] == 0
    # Monatsdaten für Kalender: Mitarbeiter sieht eigene + Anzahl-Einträge, nicht die anderer Personen
    ma2, _ = einladen(client, kopf, name="Tom", email="tom@beispiel.de")
    zeit(client, ma2, p["id"], date="2026-10-08")
    m = client.get(f"/api/projekte/{p['id']}/monat?jahr=2026&monat=10", headers=ma).json()
    assert all(x["user_id"] in (None, ma_d["user"]["id"]) for x in m["eintraege"]) and len(m["eintraege"]) == 12
    m2 = client.get(f"/api/projekte/{p['id']}/monat?jahr=2026&monat=10", headers=kopf).json()
    assert len(m2["eintraege"]) == 13 and m2["raster"]["von"] == "2026-09-28"
    # Löschen + Protokoll mit vorher/nachher
    assert client.delete(f"/api/zeiten/{e['id']}", headers=kopf).status_code == 200
    pr = client.get(f"/api/projekte/{p['id']}", headers=kopf).json()["projekt"]
    assert pr["entry_count"] == 12
    p_log = client.get("/api/protokoll", headers=kopf).json()["eintraege"]
    ge = next(x for x in p_log if x["aktion"] == "zeit.geaendert")
    assert ge["details"]["vorher"]["end_time"] == "12:00" and ge["details"]["nachher"]["end_time"] == "13:00"


def test_05_stempeluhr(client, monkeypatch):
    import routes.zeiten_routes as zr
    kopf, _ = registrieren(client)
    p = projekt(client, kopf)
    ma, ma_d = einladen(client, kopf)
    start = datetime(2026, 10, 22, 7, 58)
    uhr = {"jetzt": start}
    monkeypatch.setattr(zr, "lokal_jetzt", lambda: uhr["jetzt"])
    st = client.get("/api/stempel/status", headers=ma).json()
    assert st["aktiv"] is None and [x["name"] for x in st["projekte"]] == ["Objekt Sparkasse"]
    r = client.post("/api/stempel/start", json={"project_id": p["id"], "gps": {"lat": 52.52, "lng": 13.4, "accuracy": 12}}, headers=ma)
    assert r.status_code == 200 and r.json()["aktiv"]["project_name"] == "Objekt Sparkasse"
    assert client.post("/api/stempel/start", json={"project_id": p["id"]}, headers=ma).status_code == 409
    uhr["jetzt"] = start + timedelta(hours=2)
    assert client.post("/api/stempel/pause", headers=ma).status_code == 200
    assert client.post("/api/stempel/pause", headers=ma).status_code == 400
    uhr["jetzt"] = start + timedelta(hours=2, minutes=30)
    assert client.post("/api/stempel/weiter", headers=ma).status_code == 200
    st = client.get("/api/stempel/status", headers=ma).json()["aktiv"]
    assert st["pause_minuten"] == 30 and st["minuten"] == 120
    # Büro sieht, wer gerade arbeitet
    aktiv = client.get("/api/stempel/aktiv", headers=kopf).json()["aktiv"]
    assert aktiv[0]["user_name"] == "Mia Mitarbeiterin"
    uhr["jetzt"] = start + timedelta(hours=6, minutes=2)
    r = client.post("/api/stempel/stop", json={"activity": "Unterhaltsreinigung", "gps": {"lat": 52.5, "lng": 13.4}}, headers=ma)
    assert r.status_code == 200
    e = r.json()["eintrag"]
    assert e["date"] == "2026-10-22" and e["start_time"] == "07:58" and e["end_time"] == "14:00"
    assert e["pause_minutes"] == 30 and e["net_minutes"] == 332 and e["source"] == "stempel" and e["gps_start"]["lat"] == 52.52
    assert client.get("/api/stempel/status", headers=ma).json()["aktiv"] is None
    # unter einer Minute: verworfen
    client.post("/api/stempel/start", json={"project_id": p["id"]}, headers=ma)
    r = client.post("/api/stempel/stop", json={}, headers=ma)
    assert r.json()["verworfen"] is True
    # länger als 24 h: Fehler, Stempelung weg
    client.post("/api/stempel/start", json={"project_id": p["id"]}, headers=ma)
    uhr["jetzt"] = uhr["jetzt"] + timedelta(hours=25)
    assert client.post("/api/stempel/stop", json={}, headers=ma).status_code == 400
    assert client.get("/api/stempel/status", headers=ma).json()["aktiv"] is None


def test_06_abwesenheiten(client):
    kopf, _ = registrieren(client)
    ma, ma_d = einladen(client, kopf)
    r = client.post("/api/abwesenheiten", json={"type": "urlaub", "from_date": "2026-11-02", "to_date": "2026-11-06", "note": "Herbst"}, headers=ma)
    assert r.status_code == 200 and r.json()["abwesenheit"]["status"] == "beantragt"
    a = r.json()["abwesenheit"]
    # Büro legt direkt genehmigt an, muss Person wählen
    assert client.post("/api/abwesenheiten", json={"type": "krank", "from_date": "2026-11-09", "to_date": "2026-11-10"}, headers=kopf).status_code == 400
    r = client.post("/api/abwesenheiten", json={"user_id": ma_d["user"]["id"], "type": "krank", "from_date": "2026-11-09", "to_date": "2026-11-10"}, headers=kopf)
    assert r.json()["abwesenheit"]["status"] == "genehmigt"
    # Mitarbeiter sieht nur eigene; Büro genehmigt
    assert len(client.get("/api/abwesenheiten", headers=ma).json()["abwesenheiten"]) == 2
    assert client.put(f"/api/abwesenheiten/{a['id']}/status", json={"status": "genehmigt"}, headers=ma).status_code == 403
    r = client.put(f"/api/abwesenheiten/{a['id']}/status", json={"status": "genehmigt", "note": "ok"}, headers=kopf)
    assert r.json()["abwesenheit"]["status"] == "genehmigt"
    # genehmigte lassen sich vom Mitarbeiter nicht mehr zurückziehen
    assert client.delete(f"/api/abwesenheiten/{a['id']}", headers=ma).status_code == 403
    assert client.delete(f"/api/abwesenheiten/{a['id']}", headers=kopf).status_code == 200
    # Übersicht je Mitarbeiter zählt Kranktage
    u = client.get(f"/api/mitarbeiter/{ma_d['user']['id']}/uebersicht?jahr=2026&monat=11", headers=kopf).json()
    assert u["summe"]["kranktage"] == 2 and u["summe"]["urlaubstage"] == 0


def test_07_rechnungen_nummern_status(client):
    kopf, _ = registrieren(client)
    client.put("/api/firma", json={"vat_rate": 19, "invoice_prefix": "PC-"}, headers=kopf)
    p = projekt(client, kopf)                                   # 30 €/h
    p2 = projekt(client, kopf, name="Zweites", reverse_charge=True)
    zeit(client, kopf, p["id"], date="2026-10-05", start="08:00", ende="12:00", workers=2)   # 8 h
    zeit(client, kopf, p["id"], date="2026-09-30", start="08:00", ende="12:00")               # September, zählt nicht
    zeit(client, kopf, p2["id"], date="2026-10-20", start="08:00", ende="18:00")              # 10 h
    # ohne Zeiten keine Rechnung
    assert client.post("/api/rechnungen/anlegen", json={"project_id": p["id"], "year": 2026, "month": 11}, headers=kopf).status_code == 400
    r1 = client.post("/api/rechnungen/anlegen", json={"project_id": p["id"], "year": 2026, "month": 10}, headers=kopf).json()
    assert r1["neu"] is True and r1["rechnung"]["number"] == "PC-2026-0001"
    inv = r1["rechnung"]
    assert inv["total_minutes"] == 480 and inv["net"] == 240 and inv["vat"] == 45.6 and inv["gross"] == 285.6
    assert inv["positions"][0]["week"] == 41 and inv["positions"][0]["from"] == "2026-10-05"
    # zweiter Aufruf: dieselbe Rechnung, neu berechnet
    zeit(client, kopf, p["id"], date="2026-10-06", start="08:00", ende="09:00")
    r1b = client.post("/api/rechnungen/anlegen", json={"project_id": p["id"], "year": 2026, "month": 10}, headers=kopf).json()
    assert r1b["neu"] is False and r1b["rechnung"]["number"] == "PC-2026-0001" and r1b["rechnung"]["total_minutes"] == 540
    # § 13b: keine USt
    r2 = client.post("/api/rechnungen/anlegen", json={"project_id": p2["id"], "year": 2026, "month": 10}, headers=kopf).json()["rechnung"]
    assert r2["number"] == "PC-2026-0002" and r2["vat"] == 0 and r2["reverse_charge"] is True and r2["gross"] == 300
    # Daten fürs PDF
    d = client.get(f"/api/rechnungen/{inv['id']}/daten", headers=kopf).json()
    assert d["firma"]["invoice_prefix"] == "PC-" and len(d["eintraege"]) == 3 and d["projekt"]["name"] == "Objekt Sparkasse"
    # Status bezahlt → nicht mehr löschbar, Summen eingefroren
    r = client.put(f"/api/rechnungen/{inv['id']}", json={"status": "bezahlt", "paid_at": "2026-11-03"}, headers=kopf)
    assert r.json()["rechnung"]["paid_at"] == "2026-11-03"
    assert client.delete(f"/api/rechnungen/{inv['id']}", headers=kopf).status_code == 400
    # bezahlter Monat ist für Zeiten gesperrt (Pro Plus), Summen bleiben eingefroren
    r = client.post("/api/zeiten", json={"project_id": p["id"], "date": "2026-10-07", "start_time": "08:00", "end_time": "09:00"}, headers=kopf)
    assert r.status_code == 423
    r1c = client.post("/api/rechnungen/anlegen", json={"project_id": p["id"], "year": 2026, "month": 10}, headers=kopf).json()["rechnung"]
    assert r1c["total_minutes"] == 540
    # offene zurücksetzen → Nummer wird neu vergeben (lückenlos: nächste freie)
    assert client.delete(f"/api/rechnungen/{r2['id']}", headers=kopf).status_code == 200
    r3 = client.post("/api/rechnungen/anlegen", json={"project_id": p2["id"], "year": 2026, "month": 10}, headers=kopf).json()["rechnung"]
    assert r3["number"] == "PC-2026-0002"
    liste = client.get("/api/rechnungen?jahr=2026", headers=kopf).json()
    assert [x["number"] for x in liste["rechnungen"]] == ["PC-2026-0002", "PC-2026-0001"] and liste["jahre"] == [2026]
    assert liste["rechnungen"][1]["status"] == "bezahlt" and liste["rechnungen"][0]["project_name"] == "Zweites"


def test_08_exporte_und_milog(client):
    kopf, _ = registrieren(client)
    p = projekt(client, kopf)
    ma, ma_d = einladen(client, kopf)
    uid = ma_d["user"]["id"]
    zeit(client, ma, p["id"], date="2026-10-05", start="06:00", ende="09:30", pause=15)
    zeit(client, kopf, p["id"], date="2026-10-05", start="10:00", ende="12:00", workers=4)
    client.post("/api/abwesenheiten", json={"user_id": uid, "type": "urlaub", "from_date": "2026-10-12", "to_date": "2026-10-13"}, headers=kopf)
    r = client.get("/api/exporte/lohn.csv?jahr=2026&monat=10", headers=kopf)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    text = r.content.decode("utf-8-sig")
    zeilen = text.strip().split("\r\n")
    assert zeilen[0].startswith("Personalnummer;Mitarbeiter;Datum") and len(zeilen) == 3
    assert "Mia Mitarbeiterin;2026-10-05;Mo;06:00;09:30;15;195;3,25" in text and "(ohne Person)" in text
    r = client.get("/api/exporte/lohn-summen.csv?jahr=2026&monat=10", headers=kopf)
    text = r.content.decode("utf-8-sig")
    assert "Mia Mitarbeiterin;mitarbeiter;1;3,25;195;2;0" in text
    assert client.get("/api/exporte/zeiten.csv?von=2026-10-01&bis=2026-10-31", headers=kopf).content.decode("utf-8-sig").count("\r\n") == 3
    assert client.get("/api/exporte/lohn.csv?jahr=2026&monat=10", headers=ma).status_code == 403
    # MiLoG-Nachweis: Mitarbeiter für sich selbst, Büro für alle
    m = client.get(f"/api/exporte/milog?jahr=2026&monat=10&user_id={uid}", headers=ma).json()
    assert m["summe"]["minuten"] == 195 and m["eintraege"][0]["project_name"] == "Objekt Sparkasse" and m["mitarbeiter"]["name"] == "Mia Mitarbeiterin"
    ma2, ma2_d = einladen(client, kopf, name="Tom", email="tom@beispiel.de")
    assert client.get(f"/api/exporte/milog?jahr=2026&monat=10&user_id={uid}", headers=ma2).status_code == 403
    # Sicherung + Rückweg in die kostenlose App
    s = client.get("/api/exporte/sicherung.json", headers=kopf).json()
    assert s["app"] == "stundenzettel-pro" and len(s["data"]["entries"]) == 2 and "pw_hash" not in s["data"]["users"][0]
    fa = client.get("/api/exporte/free-app.json", headers=kopf).json()
    assert fa["app"] == "stundenzettel" and fa["data"]["companies"][0]["name"] == "PowerClean Test"
    assert any(e["activity"].startswith("Mia Mitarbeiterin") for e in fa["data"]["entries"])
    assert client.get("/api/exporte/protokoll.csv", headers=kopf).status_code == 200


def test_09_import_aus_free_app(client):
    kopf, _ = registrieren(client)
    sicherung = {"app": "stundenzettel", "version": 2, "data": {
        "companies": [{"id": "c1", "name": "Alt", "default_hourly_rate": 25, "iban": "DE99"}],
        "projects": [{"id": "p1", "company_id": "c1", "name": "Altes Objekt", "customer_name": "Kunde Alt", "customer_address": "Straße 1\n12345 Ort", "hourly_rate": 27, "default_workers": 2},
                     {"id": "p2", "company_id": "c1", "name": "Zweites", "customer_name": "Kunde Alt"}],
        "entries": [{"id": "e1", "project_id": "p1", "date": "2026-03-02", "start_time": "08:00", "end_time": "16:00", "pause_minutes": 30, "workers": 2, "activity": "Grundreinigung"},
                    {"id": "e2", "project_id": "p1", "date": "2026-03-03", "start_time": "08:00", "end_time": "08:00"},
                    {"id": "e3", "project_id": "fehlt", "date": "2026-03-03", "start_time": "08:00", "end_time": "09:00"}],
        "invoices": [{"id": "r1", "company_id": "c1", "project_id": "p1", "year": 2026, "month": 3, "seq": 1, "number": "RE-2026-0001", "gross": 100}]}}
    r = client.post("/api/import/free-app?firmendaten_uebernehmen=true", json=sicherung, headers=kopf)
    assert r.status_code == 200, r.text
    assert r.json() == {"projekte": 2, "eintraege": 1, "rechnungen": 1, "uebersprungen": 2}
    f = client.get("/api/firma", headers=kopf).json()["firma"]
    assert f["iban"] == "DE99" and f["default_hourly_rate"] == 25 and f["name"] == "PowerClean Test"
    projekte = client.get("/api/projekte", headers=kopf).json()["projekte"]
    alt = next(p for p in projekte if p["name"] == "Altes Objekt")
    assert alt["total_minutes"] == 900 and alt["customer_name"] == "Kunde Alt" and alt["hourly_rate"] == 27
    kunden = client.get("/api/kunden", headers=kopf).json()["kunden"]
    assert len(kunden) == 1 and kunden[0]["projekte"] == 2
    # zweiter Import derselben Datei legt nichts doppelt an
    r = client.post("/api/import/free-app", json=sicherung, headers=kopf).json()
    assert r["projekte"] == 0 and r["eintraege"] == 0 and r["rechnungen"] == 0
    assert client.get("/api/rechnungen", headers=kopf).json()["rechnungen"][0]["number"] == "RE-2026-0001"


def test_10_api_schluessel_und_lizenz(client):
    kopf, daten = registrieren(client)
    p = projekt(client, kopf)
    zeit(client, kopf, p["id"])
    r = client.post("/api/firma/api-tokens", json={"name": "Lohnbüro"}, headers=kopf)
    assert r.status_code == 200 and r.json()["token"].startswith("sz_")
    schluessel = {"Authorization": f"Bearer {r.json()['token']}"}
    assert client.get("/api/v1/zeiten?von=2026-10-01&bis=2026-10-31", headers=schluessel).json()["zeiten"][0]["minutes_total"] == 240
    assert client.get("/api/v1/projekte", headers=schluessel).json()["projekte"][0]["name"] == "Objekt Sparkasse"
    assert client.get("/api/v1/zeiten?von=2026-10-01&bis=2026-10-31", headers={"Authorization": "Bearer sz_falsch"}).status_code == 401
    liste = client.get("/api/firma/api-tokens", headers=kopf).json()["tokens"]
    assert len(liste) == 1 and "token_hash" not in liste[0] and liste[0]["last_used_at"]
    assert client.delete(f"/api/firma/api-tokens/{liste[0]['id']}", headers=kopf).status_code == 200
    assert client.get("/api/v1/projekte", headers=schluessel).status_code == 401
    # Lizenz: Testphase abgelaufen → Lesen geht, Schreiben 402; Freischaltung durch Betreiber
    firma_id = daten["firma"]["id"]
    gestern = (datetime.now().astimezone() - timedelta(days=1)).isoformat()
    r = client.post("/api/admin/plan", json={"firma_id": firma_id, "status": "test", "test_bis": gestern}, headers={"X-Admin-Token": "betreiber-test"})
    assert r.status_code == 200 and r.json()["plan"]["status"] == "abgelaufen"
    assert client.get("/api/projekte", headers=kopf).status_code == 200
    assert client.post("/api/zeiten", json={"project_id": p["id"], "date": "2026-10-06", "start_time": "08:00", "end_time": "09:00"}, headers=kopf).status_code == 402
    assert client.post("/api/admin/plan", json={"firma_id": firma_id, "status": "aktiv"}, headers={"X-Admin-Token": "falsch"}).status_code == 403
    client.post("/api/admin/plan", json={"firma_id": firma_id, "status": "aktiv", "nutzer_max": 5}, headers={"X-Admin-Token": "betreiber-test"})
    assert client.post("/api/zeiten", json={"project_id": p["id"], "date": "2026-10-06", "start_time": "08:00", "end_time": "09:00"}, headers=kopf).status_code == 200
    assert client.get("/api/firma/plan", headers=kopf).json()["status"] == "aktiv"
    assert client.get("/api/admin/firmen", headers={"X-Admin-Token": "betreiber-test"}).json()["firmen"][0]["nutzer"] == 1


def test_11_projektakte_checklisten_unterschriften_dateien(client):
    kopf, _ = registrieren(client)
    p = projekt(client, kopf)
    ma, _ = einladen(client, kopf)
    # Kommentar vom Mitarbeiter, Checkliste vom Büro, Abhaken vom Mitarbeiter
    assert client.post(f"/api/projekte/{p['id']}/kommentare", json={"text": "Schlüssel liegt beim Hausmeister"}, headers=ma).status_code == 200
    c = client.post(f"/api/projekte/{p['id']}/checklisten", json={"name": "Unterhaltsreinigung", "items": [{"text": "Böden wischen"}, {"text": "Müll raus"}]}, headers=kopf).json()["checkliste"]
    assert client.post(f"/api/projekte/{p['id']}/checklisten", json={"name": "X", "items": []}, headers=ma).status_code == 403
    items = [{**i, "done": True} for i in c["items"]]
    r = client.put(f"/api/checklisten/{c['id']}", json={"items": items}, headers=ma).json()["checkliste"]
    assert all(i["done"] and i["done_by"] == "Mia Mitarbeiterin" for i in r["items"])
    assert client.put(f"/api/checklisten/{c['id']}", json={"name": "Neu"}, headers=ma).status_code == 403
    # Kunden-Unterschrift je Woche (nur Montage)
    bild = "data:image/png;base64," + "A" * 80
    assert client.post(f"/api/projekte/{p['id']}/unterschriften", json={"week_monday": "2026-10-06", "signer_name": "Objektleiter", "image": bild}, headers=ma).status_code == 400
    r = client.post(f"/api/projekte/{p['id']}/unterschriften", json={"week_monday": "2026-10-05", "signer_name": "Objektleiter", "image": bild}, headers=ma)
    assert r.status_code == 200
    m = client.get(f"/api/projekte/{p['id']}/monat?jahr=2026&monat=10", headers=kopf).json()
    assert m["unterschriften"][0]["signer_name"] == "Objektleiter"
    # Dateien: Projektfoto vom Mitarbeiter, Personalakte nur Büro; falscher Typ abgelehnt
    r = client.post(f"/api/projekte/{p['id']}/dateien", files={"datei": ("foto.png", b"\x89PNG\r\n" + b"0" * 100, "image/png")}, data={"kategorie": "Fotos", "note": "Vorher"}, headers=ma)
    assert r.status_code == 200, r.text
    doc = r.json()["dokument"]
    assert "path" not in doc and doc["category"] == "Fotos"
    assert client.get(f"/api/dokumente/{doc['id']}/datei", headers=ma).status_code == 200
    r = client.post(f"/api/projekte/{p['id']}/dateien", files={"datei": ("x.exe", b"MZ" * 50, "application/x-msdownload")}, headers=ma)
    assert r.status_code == 400
    akte = client.get(f"/api/projekte/{p['id']}/akte", headers=kopf).json()
    assert len(akte["kommentare"]) == 1 and len(akte["dateien"]) == 1 and len(akte["checklisten"]) == 1 and len(akte["unterschriften"]) == 1
    uid = client.get("/api/mitarbeiter", headers=kopf).json()["mitarbeiter"][1]["id"]
    assert client.post(f"/api/mitarbeiter/{uid}/dokumente", files={"datei": ("vertrag.pdf", b"%PDF-1.4 " + b"0" * 50, "application/pdf")}, data={"kategorie": "Arbeitsvertrag"}, headers=ma).status_code == 403
    r = client.post(f"/api/mitarbeiter/{uid}/dokumente", files={"datei": ("vertrag.pdf", b"%PDF-1.4 " + b"0" * 50, "application/pdf")}, data={"kategorie": "Arbeitsvertrag"}, headers=kopf)
    assert r.status_code == 200
    # Mitarbeiter liest die eigene Akte, nicht die anderer
    assert len(client.get(f"/api/mitarbeiter/{uid}/dokumente", headers=ma).json()["dokumente"]) == 1
    ma2, _ = einladen(client, kopf, name="Tom", email="tom@beispiel.de")
    assert client.get(f"/api/mitarbeiter/{uid}/dokumente", headers=ma2).status_code == 403
    assert client.delete(f"/api/dokumente/{r.json()['dokument']['id']}", headers=kopf).status_code == 200
    # Projekt löschen räumt alles ab
    assert client.delete(f"/api/projekte/{p['id']}", headers=kopf).status_code == 200
    assert client.get(f"/api/projekte/{p['id']}", headers=kopf).status_code == 404


def test_12_dashboard(client):
    kopf, _ = registrieren(client)
    p = projekt(client, kopf)
    ma, _ = einladen(client, kopf)
    heute = datetime.now().date().isoformat()
    zeit(client, ma, p["id"], date=heute, start="06:00", ende="10:00")
    zeit(client, kopf, p["id"], date=heute, start="10:00", ende="12:00", workers=3)
    d = client.get("/api/dashboard", headers=kopf).json()
    assert d["heute_eintraege"] == 2 and d["monat"]["minuten"] == 240 + 360 and d["monat"]["umsatz_netto"] == 300 and d["mitarbeiter_aktiv"] == 2
    assert d["letzte_projekte"][0]["name"] == "Objekt Sparkasse"
    d2 = client.get("/api/dashboard", headers=ma).json()
    assert d2["monat_minuten"] == 240 and d2["gestempelt"] is False and d2["projekte_sichtbar"] == 1
    assert client.get("/api/health").json()["status"] == "ok"
