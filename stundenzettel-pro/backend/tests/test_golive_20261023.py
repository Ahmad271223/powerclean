"""Go-live-Audit (Prüfungsrunden 2 und 3) – Reproduktionstests für die bestätigten Befunde und ihre Behebung – 2026-10-23.
Stempeluhr (Zeitstempel, >24 h, Offline-Übernahme, Offline-Kennung), Projektlöschung, Unterschriften-Versionen, Rechnungs-Lebenszyklus
und Nummernkreis, Monatsabschluss, Checklisten, Upload-Reihenfolge, Abwesenheitsverlauf, Produktionsprüfung der Geheimnisse."""
import asyncio
from datetime import date, datetime, timedelta

import pytest

import config
import db as dbmodul
from conftest import einladen, projekt, registrieren, zeit
from zeiten import lokal_jetzt


def _stempel_zurueckdatieren(user_id: str, stunden: float, pausen=None):
    """Startzeit der laufenden Stempelung zurücksetzen (so, wie der Server sie speichert)."""
    start = (lokal_jetzt() - timedelta(hours=stunden))
    asyncio.run(dbmodul.db().stempel.update_one({"user_id": user_id}, {"$set": {"start_at": start.isoformat(), "pausen": pausen or []}}))
    return start


def _aufbau(client):
    chef, chef_d = registrieren(client, email="chef@golive-test.de", firma="GoLive Test GmbH", name="Gabi Chefin")
    buero, buero_d = einladen(client, chef, name="Bea Büro", email="bea@golive-test.de", role="buero")
    vor, vor_d = einladen(client, chef, name="Vera Vorarbeiterin", email="vera@golive-test.de", role="vorarbeiter")
    ma, ma_d = einladen(client, chef, name="Milan Mitarbeiter", email="milan@golive-test.de", role="mitarbeiter")
    p = projekt(client, chef, name="Objekt Bahnhof", hourly_rate=30)
    return {"chef": chef, "buero": buero, "vor": vor, "ma": ma, "ma_id": ma_d["user"]["id"], "vor_id": vor_d["user"]["id"], "p": p, "firma_id": chef_d["firma"]["id"]}


def test_01_stempeluhr_zeitstempel_24h_und_nachtarbeit(client):
    s = _aufbau(client)
    pid = s["p"]["id"]
    r = client.post("/api/stempel/start", json={"project_id": pid}, headers=s["ma"])
    assert r.status_code == 200, r.text
    st = client.get("/api/stempel/status", headers=s["ma"]).json()
    # Die Anzeige rechnet mit Zeitstempeln und Server-Uhr, nicht mit gerundeten Minuten plus Abrufzeitpunkt
    assert st["jetzt"] and st["aktiv"]["start_at"] and st["aktiv"]["sekunden"] >= 0 and st["aktiv"]["server_jetzt"] and st["aktiv"]["pausen"] == []
    # Pause sekundengenau: 90 s Pause → Nettosekunden ≈ brutto − 90
    _stempel_zurueckdatieren(s["ma_id"], 1, pausen=[{"von": (lokal_jetzt() - timedelta(minutes=30)).isoformat(), "bis": (lokal_jetzt() - timedelta(minutes=28, seconds=30)).isoformat()}])
    st = client.get("/api/stempel/status", headers=s["ma"]).json()["aktiv"]
    assert 3600 - 90 - 3 <= st["sekunden"] <= 3600 - 90 + 3 and st["pause_minuten"] == 1 and st["minuten"] == 59
    # Länger als 24 Stunden: früher wurde die Stempelung gelöscht und der Eintrag verworfen – jetzt bleibt der Nachweis (begrenzt, zur Prüfung markiert)
    _stempel_zurueckdatieren(s["ma_id"], 26)
    r = client.post("/api/stempel/stop", json={"activity": "Nachtschicht"}, headers=s["ma"])
    assert r.status_code == 200, r.text
    e = r.json()["eintrag"]
    assert e["pruefen"] is True and "24 Stunden" in e["hinweise"][0]["text"] and e["net_minutes"] == 24 * 60 - 1 and e["clock_end_at"]
    assert client.get("/api/stempel/status", headers=s["ma"]).json()["aktiv"] is None
    assert len(client.get(f"/api/projekte/{pid}/zeiten?von=2026-01-01&bis=2027-12-31", headers=s["chef"]).json()["eintraege"]) == 1
    # Nachtarbeit über Mitternacht: Start gestern 22:00, Ende jetzt → Datum = Starttag, Netto über Mitternacht korrekt
    assert client.post("/api/stempel/start", json={"project_id": pid}, headers=s["ma"]).status_code == 200
    jetzt_l = lokal_jetzt()
    start = (jetzt_l - timedelta(days=1)).replace(hour=22, minute=0, second=0, microsecond=0)
    if jetzt_l - start >= timedelta(hours=24):   # Testlauf spät am Abend: 23 Stunden zurück, damit die 24-Stunden-Grenze nicht greift
        start = (jetzt_l - timedelta(hours=23)).replace(second=0, microsecond=0)
    asyncio.run(dbmodul.db().stempel.update_one({"user_id": s["ma_id"]}, {"$set": {"start_at": start.isoformat(), "pausen": []}}))
    r = client.post("/api/stempel/stop", json={}, headers=s["ma"])
    assert r.status_code == 200, r.text
    e = r.json()["eintrag"]
    erwartet = int((lokal_jetzt().replace(tzinfo=None) - start.replace(tzinfo=None)).total_seconds() // 60)
    assert e["date"] == start.date().isoformat() and e["start_time"] == start.strftime("%H:%M") and abs(e["net_minutes"] - erwartet) <= 1 and e["pruefen"] is False
    # Stop-Reihenfolge: Eintrag zuerst, Stempelung danach – nach einem Stop gibt es den Eintrag und keine Stempelung mehr
    assert client.get("/api/stempel/status", headers=s["ma"]).json()["aktiv"] is None


def test_02_offline_uebernahme_und_offline_kennung(client):
    s = _aufbau(client)
    pid = s["p"]["id"]
    jetzt = datetime.now().astimezone()
    start = (jetzt - timedelta(hours=2)).isoformat()
    pause = [{"von": (jetzt - timedelta(minutes=60)).isoformat(), "bis": (jetzt - timedelta(minutes=45)).isoformat()}]
    # Offline gestartete Stempelung wird mit echter Startzeit und Pausen übernommen (statt im Browser zu verschwinden)
    r = client.post("/api/stempel/start", json={"project_id": pid, "start_at": start, "pausen": pause}, headers=s["ma"])
    assert r.status_code == 200, r.text
    a = r.json()["aktiv"]
    assert a["offline_uebernommen"] is True and 104 <= a["minuten"] <= 106 and a["pause_minuten"] == 15
    assert client.post("/api/stempel/start", json={"project_id": pid, "start_at": start}, headers=s["ma"]).status_code == 409
    assert client.delete("/api/stempel", headers=s["ma"]).status_code == 200
    assert client.post("/api/stempel/start", json={"project_id": pid, "start_at": (jetzt + timedelta(hours=1)).isoformat()}, headers=s["ma"]).status_code == 400
    assert client.post("/api/stempel/start", json={"project_id": pid, "start_at": (jetzt - timedelta(hours=30)).isoformat()}, headers=s["ma"]).status_code == 400
    assert client.post("/api/stempel/start", json={"project_id": pid, "start_at": start, "pausen": [{"von": (jetzt - timedelta(hours=3)).isoformat(), "bis": None}]}, headers=s["ma"]).status_code == 400
    # Offline-Eintrag: dieselbe offline_id wird höchstens einmal angelegt (doppelte Übertragung nach Netzwechsel)
    body = {"project_id": pid, "date": "2026-10-06", "start_time": "06:00", "end_time": "14:30", "pause_minutes": 30, "offline": True, "offline_id": "geraet-1-eintrag-7",
            "start_at": "2026-10-06T04:00:00.000Z", "end_at": "2026-10-06T12:30:00.000Z"}
    r1 = client.post("/api/zeiten", json=body, headers=s["ma"])
    r2 = client.post("/api/zeiten", json=body, headers=s["ma"])
    assert r1.status_code == 200 and r2.status_code == 200 and r1.json()["eintrag"]["id"] == r2.json()["eintrag"]["id"] and r2.json()["doppelt"] is True
    liste = client.get(f"/api/projekte/{pid}/zeiten?von=2026-10-01&bis=2026-10-31", headers=s["chef"]).json()["eintraege"]
    assert len(liste) == 1 and liste[0]["source"] == "stempel_offline" and liste[0]["clock_start_at"] == body["start_at"] and liste[0]["net_minutes"] == 480
    # Ein abgelehnter Offline-Eintrag (hier: gesperrter Tag durch Monatsabschluss) kommt als Fehler zurück und wird serverseitig nicht angelegt –
    # der Browser behält ihn in der Warteschlange (siehe StempeluhrPage: nie stilles Verwerfen)
    assert client.post("/api/abschluss", json={"year": 2026, "month": 9}, headers=s["chef"]).status_code == 200
    r = client.post("/api/zeiten", json={**body, "date": "2026-09-15", "offline_id": "geraet-1-eintrag-8"}, headers=s["ma"])
    assert r.status_code in (400, 423) and r.json()["detail"]


def test_03_projekt_loeschen_und_monatsabschluss(client):
    s = _aufbau(client)
    pid = s["p"]["id"]
    assert client.post("/api/stempel/start", json={"project_id": pid}, headers=s["ma"]).status_code == 200
    # Laufende Stempelung: Löschen blockiert (auch für den Inhaber mit erzwingen)
    r = client.delete(f"/api/projekte/{pid}", headers=s["buero"])
    assert r.status_code == 409 and "eingestempelt" in r.json()["detail"]
    assert client.delete(f"/api/projekte/{pid}?erzwingen=true", headers=s["chef"]).status_code == 409
    # Monatsabschluss mit laufender Stempelung im Monat: blockiert mit Namen; erzwingen möglich und protokolliert
    heute = date.today()
    r = client.post("/api/abschluss", json={"year": heute.year, "month": heute.month}, headers=s["chef"])
    assert r.status_code == 409 and "Milan Mitarbeiter" in r.json()["detail"]
    assert client.post("/api/abschluss", json={"year": 2025, "month": 1}, headers=s["chef"]).status_code == 200   # früherer Monat: nicht betroffen
    r = client.post("/api/abschluss", json={"year": heute.year, "month": heute.month, "erzwingen": True}, headers=s["chef"])
    assert r.status_code == 200 and r.json()["abschluss"]["erzwungen"] is True
    assert client.delete(f"/api/abschluss/{heute.year}/{heute.month}", headers=s["chef"]).status_code == 200
    # Ausstempeln → erfasste Zeit: Löschen nur archivieren oder Inhaber mit erzwingen
    _stempel_zurueckdatieren(s["ma_id"], 2)
    assert client.post("/api/stempel/stop", json={}, headers=s["ma"]).status_code == 200
    r = client.delete(f"/api/projekte/{pid}", headers=s["buero"])
    assert r.status_code == 409 and "archivieren" in r.json()["detail"]
    assert client.delete(f"/api/projekte/{pid}?erzwingen=true", headers=s["buero"]).status_code == 403
    assert client.delete(f"/api/projekte/{pid}?erzwingen=true", headers=s["chef"]).status_code == 200
    assert client.get(f"/api/projekte/{pid}", headers=s["chef"]).status_code == 404
    # Projekt ohne Zeiten darf das Büro weiterhin löschen
    p2 = projekt(client, s["chef"], name="Leeres Projekt")
    assert client.delete(f"/api/projekte/{p2['id']}", headers=s["buero"]).status_code == 200


def test_04_unterschriften_werden_nicht_ueberschrieben(client):
    s = _aufbau(client)
    pid = s["p"]["id"]
    bild = "data:image/png;base64," + "A" * 80
    zeit(client, s["ma"], pid, date="2026-10-06", start="08:00", ende="12:00")
    r = client.post(f"/api/projekte/{pid}/unterschriften", json={"week_monday": "2026-10-05", "signer_name": "Frau Richter", "image": bild}, headers=s["ma"])
    assert r.status_code == 200 and r.json()["unterschrift"]["version"] == 1
    erste = r.json()["unterschrift"]["id"]
    # Mitarbeiter kann die vorhandene Unterschrift nicht ersetzen
    r = client.post(f"/api/projekte/{pid}/unterschriften", json={"week_monday": "2026-10-05", "signer_name": "Jemand anders", "image": bild}, headers=s["ma"])
    assert r.status_code == 409
    # Büro nur mit Begründung; die alte bleibt als Version erhalten
    assert client.post(f"/api/projekte/{pid}/unterschriften", json={"week_monday": "2026-10-05", "signer_name": "Herr Kurt", "image": bild}, headers=s["buero"]).status_code == 400
    r = client.post(f"/api/projekte/{pid}/unterschriften", json={"week_monday": "2026-10-05", "signer_name": "Herr Kurt", "image": bild, "grund": "Falsche Person hatte unterschrieben"}, headers=s["buero"])
    assert r.status_code == 200 and r.json()["unterschrift"]["version"] == 2 and r.json()["unterschrift"]["ersetzt_id"] == erste
    monat = client.get(f"/api/projekte/{pid}/monat?jahr=2026&monat=10", headers=s["chef"]).json()
    gueltig = [u for u in monat["unterschriften"] if u["week_monday"] == "2026-10-05"]
    assert [u["signer_name"] for u in gueltig] == ["Herr Kurt"]
    akte = client.get(f"/api/projekte/{pid}/akte", headers=s["chef"]).json()["unterschriften"]
    assert sorted((u["signer_name"], bool(u.get("ersetzt"))) for u in akte) == [("Frau Richter", True), ("Herr Kurt", False)]
    assert {e["aktion"] for e in client.get("/api/protokoll", headers=s["chef"]).json()["eintraege"]} >= {"unterschrift.erfasst", "unterschrift.ersetzt"}
    # „Löschen“ zieht zurück statt zu vernichten
    zweite = r.json()["unterschrift"]["id"]
    assert client.delete(f"/api/unterschriften/{zweite}", headers=s["buero"]).status_code == 200
    assert client.delete(f"/api/unterschriften/{zweite}", headers=s["buero"]).status_code == 404
    assert len(client.get(f"/api/projekte/{pid}/akte", headers=s["chef"]).json()["unterschriften"]) == 2


def test_05_rechnungen_lebenszyklus_und_nummernkreis(client):
    s = _aufbau(client)
    pid = s["p"]["id"]
    zeit(client, s["chef"], pid, date="2026-10-05", start="08:00", ende="12:00", user_id=s["ma_id"])
    # Nur prüfen: nichts wird angelegt, keine Nummer vergeben
    r = client.post("/api/rechnungen/anlegen", json={"project_id": pid, "year": 2026, "month": 10, "nur_pruefen": True}, headers=s["chef"])
    assert r.status_code == 200 and r.json()["rechnung"] is None and r.json()["vorschau"]["total_minutes"] == 240
    assert client.get("/api/rechnungen", headers=s["chef"]).json()["rechnungen"] == []
    r = client.post("/api/rechnungen/anlegen", json={"project_id": pid, "year": 2026, "month": 10}, headers=s["chef"]).json()
    r1 = r["rechnung"]
    assert r["neu"] is True and r1["number"].endswith("2026-0001") and r1["net"] == 120.0
    # Entwurf: weitere Zeiten → anlegen berechnet neu
    zeit(client, s["chef"], pid, date="2026-10-06", start="08:00", ende="10:00", user_id=s["ma_id"])
    assert client.post("/api/rechnungen/anlegen", json={"project_id": pid, "year": 2026, "month": 10}, headers=s["chef"]).json()["rechnung"]["net"] == 180.0
    # PDF-Daten abrufen = ausstellen: ab jetzt keine stillschweigende Neuberechnung mehr
    d = client.get(f"/api/rechnungen/{r1['id']}/daten", headers=s["chef"]).json()
    assert d["rechnung"]["festgeschrieben_at"]
    zeit(client, s["chef"], pid, date="2026-10-07", start="08:00", ende="10:00", user_id=s["ma_id"])
    r = client.post("/api/rechnungen/anlegen", json={"project_id": pid, "year": 2026, "month": 10}, headers=s["chef"]).json()["rechnung"]
    assert r["net"] == 180.0 and r["festgeschrieben_at"]
    assert client.put(f"/api/rechnungen/{r1['id']}/extras", json={"extras": [{"text": "Anfahrt", "quantity": 1, "unit_price": 20}]}, headers=s["chef"]).status_code == 400
    assert client.post(f"/api/rechnungen/{r1['id']}/neu-berechnen", headers=s["buero"]).status_code == 400
    assert client.post(f"/api/rechnungen/{r1['id']}/neu-berechnen?erzwingen=true", headers=s["buero"]).status_code == 403
    r = client.post(f"/api/rechnungen/{r1['id']}/neu-berechnen?erzwingen=true", headers=s["chef"])
    assert r.status_code == 200 and r.json()["rechnung"]["net"] == 240.0 and r.json()["rechnung"]["korrekturen"][0]["vorher"]["net"] == 180.0
    assert client.put(f"/api/rechnungen/{r1['id']}", json={"status": "offen", "invoice_date": "2026-11-02"}, headers=s["chef"]).status_code == 400
    # Ausgestellte Rechnung lässt sich nicht zurücksetzen (Beleg), nur stornieren
    assert client.delete(f"/api/rechnungen/{r1['id']}", headers=s["chef"]).status_code == 400
    assert client.put(f"/api/rechnungen/{r1['id']}", json={"status": "storniert"}, headers=s["chef"]).status_code == 200
    # Nummernkreis: Entwurf 0002 zurücksetzen → nächste Rechnung bekommt 0003, nie wieder 0002
    p2 = projekt(client, s["chef"], name="Zweites Objekt", hourly_rate=25)
    zeit(client, s["chef"], p2["id"], date="2026-10-05", start="08:00", ende="12:00", user_id=s["ma_id"])
    r2 = client.post("/api/rechnungen/anlegen", json={"project_id": p2["id"], "year": 2026, "month": 10}, headers=s["chef"]).json()["rechnung"]
    assert r2["number"].endswith("2026-0002")
    assert client.delete(f"/api/rechnungen/{r2['id']}", headers=s["chef"]).status_code == 200
    r3 = client.post("/api/rechnungen/anlegen", json={"project_id": p2["id"], "year": 2026, "month": 10}, headers=s["chef"]).json()["rechnung"]
    assert r3["number"].endswith("2026-0003")
    # Ausdrückliches Festschreiben (nach PDF im Browser) und Abruf über die Liste
    assert client.post(f"/api/rechnungen/{r3['id']}/festschreiben", headers=s["buero"]).json()["rechnung"]["festgeschrieben_anlass"] == "ausgestellt"


def test_06_checkliste_upload_abwesenheit(client):
    s = _aufbau(client)
    pid = s["p"]["id"]
    c = client.post(f"/api/projekte/{pid}/checklisten", json={"name": "Sicherheit", "items": [{"text": "Gerüst prüfen"}, {"text": "Schutzkleidung prüfen"}, {"text": "Arbeitsbereich absichern"}]}, headers=s["chef"]).json()["checkliste"]
    erster = c["items"][0]["id"]
    # Mitarbeiter schickt nur einen Punkt (abgehakt): die anderen bleiben erhalten, neue Punkte werden nicht angelegt
    r = client.put(f"/api/checklisten/{c['id']}", json={"items": [{"id": erster, "text": "Gerüst prüfen", "done": True}, {"text": "Neuer Punkt", "done": False}]}, headers=s["ma"])
    assert r.status_code == 200
    items = r.json()["checkliste"]["items"]
    assert [i["text"] for i in items] == ["Gerüst prüfen", "Schutzkleidung prüfen", "Arbeitsbereich absichern"] and items[0]["done"] is True and items[0]["done_by"] == "Milan Mitarbeiter"
    assert client.put(f"/api/checklisten/{c['id']}", json={"name": "Neu"}, headers=s["ma"]).status_code == 403
    # Upload: ungültiges Datum wird vor dem Speichern abgewiesen – keine verwaiste Datei, kein Datensatz
    vorher = len(list((config.DATA_DIR / "dateien").rglob("*"))) if (config.DATA_DIR / "dateien").exists() else 0
    r = client.post(f"/api/projekte/{pid}/dateien", data={"kategorie": "Fotos", "date": "31.02.2026"}, files={"datei": ("f.png", b"\x89PNG\r\n\x1a\n" + b"0" * 100, "image/png")}, headers=s["ma"])
    assert r.status_code == 400
    assert client.get(f"/api/projekte/{pid}/akte", headers=s["chef"]).json()["dateien"] == []
    nachher = len(list((config.DATA_DIR / "dateien").rglob("*"))) if (config.DATA_DIR / "dateien").exists() else 0
    assert nachher == vorher
    # Abwesenheiten: Entscheidung und Änderungen genehmigter Anträge mit Verlauf und Grund
    a = client.post("/api/abwesenheiten", json={"type": "urlaub", "from_date": "2026-12-21", "to_date": "2026-12-23"}, headers=s["ma"]).json()["abwesenheit"]
    r = client.put(f"/api/abwesenheiten/{a['id']}/status", json={"status": "genehmigt", "note": "Passt"}, headers=s["buero"])
    assert r.status_code == 200 and r.json()["abwesenheit"]["verlauf"][0]["aktion"] == "entschieden"
    assert client.put(f"/api/abwesenheiten/{a['id']}", json={"type": "urlaub", "from_date": "2026-12-21", "to_date": "2026-12-22"}, headers=s["buero"]).status_code == 400
    r = client.put(f"/api/abwesenheiten/{a['id']}", json={"type": "urlaub", "from_date": "2026-12-21", "to_date": "2026-12-22", "grund": "Betriebliche Gründe, mit Mitarbeiter abgestimmt"}, headers=s["buero"])
    assert r.status_code == 200
    v = r.json()["abwesenheit"]["verlauf"]
    assert v[-1]["aktion"] == "geaendert" and v[-1]["vorher"] == {"to_date": "2026-12-23"} and v[-1]["grund"].startswith("Betriebliche")
    assert client.put(f"/api/abwesenheiten/{a['id']}", json={"type": "urlaub", "from_date": "2026-12-21", "to_date": "2026-12-22"}, headers=s["ma"]).status_code == 403


def test_07_produktionspruefung_geheimnisse(monkeypatch):
    import server
    monkeypatch.setattr(config, "DB_MODE", "mongo")
    monkeypatch.setattr(config, "JWT_SECRET", "nur-entwicklung-bitte-in-env-setzen")
    monkeypatch.delenv("UNSICHER_ERLAUBEN", raising=False)
    with pytest.raises(RuntimeError):
        server.sicherheit_pruefen()
    monkeypatch.setattr(config, "JWT_SECRET", "x" * 40)
    monkeypatch.setattr(config, "DATEN_SCHLUESSEL", "")
    hinweise = server.sicherheit_pruefen()
    assert any("DATEN_SCHLUESSEL" in h for h in hinweise)
    monkeypatch.setattr(config, "DB_MODE", "memory")
    assert server.sicherheit_pruefen() == []
