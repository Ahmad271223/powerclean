"""Go-live-Audit Runde 4 – Reproduktionstests: Webhook-SSRF und Ausgang mit Wiederholung, API-Schlüssel mit Rechten/Ablauf/Sperre,
Import (Prüfung zuerst, Kennungen, Rücknahme, Rechnungsnummern), Leistungsnamen als Momentaufnahme, CSV-Formelschutz,
Projektfelder je Rolle, kostenlose Projekte, Mitarbeiter-Zuweisung, Sicherung und Dateien-ZIP, Seitengrößen – 2026-10-23."""
import asyncio
import io
import zipfile
from datetime import datetime, timedelta, timezone

import db as dbmodul
import webhooks as wh
from conftest import einladen, projekt, registrieren, zeit


def _aufbau(client):
    chef, chef_d = registrieren(client, email="chef@audit4-test.de", firma="Audit4 GmbH", name="Clara Chefin")
    buero, _ = einladen(client, chef, name="Bea Büro", email="bea@audit4-test.de", role="buero")
    vor, vor_d = einladen(client, chef, name="Vera Vor", email="vera@audit4-test.de", role="vorarbeiter")
    ma, ma_d = einladen(client, chef, name="Milan Ma", email="milan@audit4-test.de", role="mitarbeiter")
    p = projekt(client, chef, name="Objekt Rathaus", hourly_rate=42, notes="Schlüssel beim Hausmeister", budget_hours_month=80, employee_ids=[vor_d["user"]["id"], ma_d["user"]["id"]])
    return {"chef": chef, "buero": buero, "vor": vor, "ma": ma, "ma_id": ma_d["user"]["id"], "vor_id": vor_d["user"]["id"], "p": p, "firma_id": chef_d["firma"]["id"]}


def test_01_webhook_ssrf_und_ausgang(client, monkeypatch):
    s = _aufbau(client)
    # Formale Prüfung: interne Ziele, Zugangsdaten, fremde Ports, http
    for url in ("http://127.0.0.1:8010/hook", "https://localhost/hook", "https://169.254.169.254/latest/meta-data", "https://10.0.0.5/hook", "https://[::1]/hook",
                "https://192.168.1.20/hook", "https://metadata.google.internal/x", "https://intranet.firma.local/hook", "https://buchhaltung/hook",
                "https://hooks.example.com:9200/hook", "https://user:pw@hooks.example.com/hook", "https://[::ffff:127.0.0.1]/hook", "https://100.64.1.1/hook"):
        r = client.post("/api/firma/webhooks", json={"url": url, "events": ["test"]}, headers=s["chef"])
        assert r.status_code == 400, f"{url} → {r.status_code}"
    assert wh.ip_erlaubt("8.8.8.8") and wh.ip_erlaubt("2606:4700::1111") and not wh.ip_erlaubt("fc00::1") and not wh.ip_erlaubt("0.0.0.0")
    r = client.post("/api/firma/webhooks", json={"url": "https://hooks.example.com/stundenzettel", "events": ["test", "rechnung.angelegt"], "name": "Buchhaltung"}, headers=s["chef"])
    assert r.status_code == 200, r.text
    hook = r.json()["webhook"]
    assert "secret" not in hook and r.json()["secret"]
    # DNS-Auflösung vor dem Senden: zeigt der Name auf ein internes Netz, wird nicht gesendet
    async def intern(url): raise wh.UnsichereAdresse("intern")
    monkeypatch.setattr(wh, "adressen_pruefen", intern)
    t = client.post(f"/api/firma/webhooks/{hook['id']}/test", headers=s["chef"]).json()
    assert t["status"] == -2 and t["ok"] is False
    ausgang = asyncio.run(dbmodul.db().webhook_ausgang.find_one({"webhook_id": hook["id"]}, {"_id": 0}))
    assert ausgang["status"] == "fehlgeschlagen" and ausgang["versuche"] == 1
    # Netzfehler: Eintrag bleibt offen mit nächstem Versuch; Hintergrunddienst stellt später zu (kein Verlust bei Neustart)
    aufrufe = []
    async def kaputt(url, body, headers): aufrufe.append(url); raise ConnectionError("Ziel nicht erreichbar")
    async def ok(url, body, headers): aufrufe.append(url); return 200
    async def frei(url): return None
    monkeypatch.setattr(wh, "adressen_pruefen", frei)
    monkeypatch.setattr(wh, "_post", kaputt)
    t = client.post(f"/api/firma/webhooks/{hook['id']}/test", headers=s["chef"]).json()
    assert t["status"] == 0
    offen = asyncio.run(dbmodul.db().webhook_ausgang.find_one({"webhook_id": hook["id"], "status": "offen"}, {"_id": 0}))
    assert offen and offen["versuche"] == 1 and offen["naechster_versuch_at"] > offen["created_at"]
    liste = client.get("/api/firma/webhooks", headers=s["chef"]).json()["webhooks"]
    assert liste[0]["ausgang"] == {"offen": 1, "fehlgeschlagen": 1}
    asyncio.run(dbmodul.db().webhook_ausgang.update_one({"id": offen["id"]}, {"$set": {"naechster_versuch_at": datetime.now(timezone.utc).isoformat()}}))
    monkeypatch.setattr(wh, "_post", ok)
    assert asyncio.run(wh.ausgang_abarbeiten()) == 1
    assert asyncio.run(dbmodul.db().webhook_ausgang.find_one({"id": offen["id"]}, {"_id": 0}))["status"] == "zugestellt"
    assert len(aufrufe) == 2 and all(u == "https://hooks.example.com/stundenzettel" for u in aufrufe)


def test_02_api_schluessel_rechte_ablauf_sperre(client):
    s = _aufbau(client)
    zeit(client, s["chef"], s["p"]["id"], date="2026-10-05", user_id=s["ma_id"])
    r = client.post("/api/firma/api-tokens", json={"name": "Lohnbüro", "rechte": ["zeiten", "abwesenheiten"], "tage": 30}, headers=s["chef"])
    assert r.status_code == 200, r.text
    schluessel = {"Authorization": f"Bearer {r.json()['token']}"}
    eintrag = r.json()["eintrag"]
    assert eintrag["rechte"] == ["zeiten", "abwesenheiten"] and eintrag["gueltig_bis"] > datetime.now(timezone.utc).isoformat()
    assert client.get("/api/v1/zeiten?von=2026-10-01&bis=2026-10-31", headers=schluessel).status_code == 200
    assert client.get("/api/v1/abwesenheiten?von=2026-10-01&bis=2026-10-31", headers=schluessel).status_code == 200
    for pfad in ("/api/v1/rechnungen", "/api/v1/mitarbeiter", "/api/v1/projekte", "/api/v1/kunden"):
        assert client.get(pfad, headers=schluessel).status_code == 403, pfad
    # Unbekannte Rechte werden verworfen, leere Liste → nur Zeiten
    r = client.post("/api/firma/api-tokens", json={"name": "x", "rechte": ["admin", "alles"]}, headers=s["chef"]).json()
    assert r["eintrag"]["rechte"] == ["zeiten"]
    # Ablauf
    asyncio.run(dbmodul.db().api_tokens.update_one({"id": eintrag["id"]}, {"$set": {"gueltig_bis": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()}}))
    r = client.get("/api/v1/zeiten?von=2026-10-01&bis=2026-10-31", headers=schluessel)
    assert r.status_code == 401 and "abgelaufen" in r.json()["detail"]
    asyncio.run(dbmodul.db().api_tokens.update_one({"id": eintrag["id"]}, {"$set": {"gueltig_bis": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()}}))
    # Gesperrte Firma: kein Zugriff per Schlüssel
    asyncio.run(dbmodul.db().firmen.update_one({"id": s["firma_id"]}, {"$set": {"plan.status": "gesperrt"}}))
    assert client.get("/api/v1/zeiten?von=2026-10-01&bis=2026-10-31", headers=schluessel).status_code == 403
    asyncio.run(dbmodul.db().firmen.update_one({"id": s["firma_id"]}, {"$set": {"plan.status": "test"}}))
    # Schlüssel aus früheren Versionen (ohne Rechte, ohne Ablauf): voller Lesezugriff bleibt bis zur Erneuerung
    import hashlib
    asyncio.run(dbmodul.db().api_tokens.insert_one({"id": "alt", "firma_id": s["firma_id"], "name": "alt", "token_hash": hashlib.sha256(b"sz_alt").hexdigest(), "created_at": "2026-01-01T00:00:00"}))
    assert client.get("/api/v1/rechnungen", headers={"Authorization": "Bearer sz_alt"}).status_code == 200


def test_03_import_pruefung_kennung_ruecknahme_nummern(client, monkeypatch):
    s = _aufbau(client)
    datei = {"app": "stundenzettel", "data": {"projects": [{"id": "p1", "name": "Altes Objekt", "hourly_rate": 25, "customer_name": "Alt-Kunde"}],
                                               "entries": [{"project_id": "p1", "date": "2026-09-01", "start_time": "08:00", "end_time": "12:00", "pause_minutes": 0, "activity": "Reinigung"},
                                                           {"project_id": "p1", "date": "2026-09-01", "start_time": "08:00", "end_time": "12:00", "pause_minutes": 0, "activity": "Reinigung"},
                                                           {"project_id": "p1", "date": "31.09.2026", "start_time": "08:00", "end_time": "12:00"}],
                                               "invoices": [{"project_id": "p1", "year": 2026, "month": 9, "seq": 7, "number": "RE-2026-0007", "net": 100, "vat": 19, "gross": 119},
                                                            {"project_id": "p1", "year": 2026, "month": 8, "seq": 3, "number": "RE-2026-0007", "net": 50, "vat": 9.5, "gross": 59.5}]}}
    r = client.post("/api/import/free-app", json=datei, headers=s["chef"])
    assert r.status_code == 200, r.text
    e = r.json()
    assert e["projekte"] == 1 and e["eintraege"] == 1 and e["uebersprungen"] == 2 and e["rechnungen"] == 1 and e["rechnungen_uebersprungen"] == 1
    # Wiederholung desselben Imports legt nichts doppelt an (stabile Kennung auch ohne Quell-ID)
    e2 = client.post("/api/import/free-app", json=datei, headers=s["chef"]).json()
    assert e2["projekte"] == 0 and e2["eintraege"] == 0 and e2["rechnungen"] == 0
    assert len([r for r in client.get("/api/rechnungen", headers=s["chef"]).json()["rechnungen"]]) == 1
    # Nummernkreis nachgezogen: die nächste neue Rechnung bekommt 0008, nicht 0001
    pid = [p for p in client.get("/api/projekte", headers=s["chef"]).json()["projekte"] if p["name"] == "Altes Objekt"][0]["id"]
    zeit(client, s["chef"], pid, date="2026-10-05", user_id=s["ma_id"])
    assert client.post("/api/rechnungen/anlegen", json={"project_id": pid, "year": 2026, "month": 10}, headers=s["chef"]).json()["rechnung"]["number"].endswith("2026-0008")
    # Ungültiges Projekt → nichts übernommen (Prüfung vor dem Schreiben)
    r = client.post("/api/import/free-app", json={"app": "stundenzettel", "data": {"projects": [{"id": "p9", "name": "Gültig"}, {"id": "p10", "name": "", "color": "rot"}]}}, headers=s["chef"])
    assert r.status_code == 400 and "nichts übernommen" in r.json()["detail"]
    assert not [p for p in client.get("/api/projekte", headers=s["chef"]).json()["projekte"] if p["name"] == "Gültig"]
    # Fehler beim Schreiben → alles aus diesem Import wird zurückgenommen
    sammlung_klasse = type(dbmodul.db().entries)
    original = sammlung_klasse.insert_one
    zaehler = {"n": 0}
    async def kaputt(self, doc, *a, **k):
        zaehler["n"] += 1
        if zaehler["n"] >= 2:   # erster Schreibvorgang (Projekt) klappt, der zweite (Eintrag) scheitert
            raise RuntimeError("Platte voll")
        return await original(self, doc, *a, **k)
    monkeypatch.setattr(sammlung_klasse, "insert_one", kaputt)
    r = client.post("/api/import/free-app", json={"app": "stundenzettel", "data": {"projects": [{"id": "p20", "name": "Rollback-Objekt"}],
                                                                                   "entries": [{"project_id": "p20", "date": "2026-09-02", "start_time": "08:00", "end_time": "10:00"}]}}, headers=s["chef"])
    monkeypatch.setattr(sammlung_klasse, "insert_one", original)
    assert r.status_code == 500 and zaehler["n"] >= 2
    assert not [p for p in client.get("/api/projekte", headers=s["chef"]).json()["projekte"] if p["name"] == "Rollback-Objekt"]
    # Importierte Rechnung ist ausgestellt (keine stille Neuberechnung)
    alt = [r for r in client.get("/api/rechnungen", headers=s["chef"]).json()["rechnungen"] if r["number"] == "RE-2026-0007"][0]
    assert alt["festgeschrieben_at"] and alt["festgeschrieben_anlass"] == "import"


def test_04_leistungsname_csv_projektfelder(client):
    s = _aufbau(client)
    pid = s["p"]["id"]
    # Leistung umbenennen ändert alte Einträge nicht mehr
    l = client.post("/api/leistungen", json={"name": "Unterhaltsreinigung", "hourly_rate": 0}, headers=s["chef"]).json()["leistung"]
    e = zeit(client, s["chef"], pid, date="2026-10-05", user_id=s["ma_id"], service_id=l["id"], activity="=1+1")
    assert e["service_name"] == "Unterhaltsreinigung"
    assert client.put(f"/api/leistungen/{l['id']}", json={"name": "Unterhaltsreinigung Büro", "hourly_rate": 0}, headers=s["chef"]).status_code == 200
    e2 = [x for x in client.get(f"/api/projekte/{pid}/zeiten?von=2026-10-01&bis=2026-10-31", headers=s["chef"]).json()["eintraege"] if x["id"] == e["id"]][0]
    assert e2["service_name"] == "Unterhaltsreinigung"
    # CSV: Formel-Einschleusung wird entschärft, Zahlen bleiben Zahlen
    csv = client.get("/api/exporte/zeiten.csv?von=2026-10-01&bis=2026-10-31", headers=s["chef"]).text
    assert "'=1+1" in csv and "=1+1" not in csv.replace("'=1+1", "")
    from csvsicher import zelle
    assert zelle("-30") == "-30" and zelle("+49 170 1234") == "'+49 170 1234" and zelle("@sum") == "'@sum" and zelle(5) == 5 and zelle("Normal") == "Normal"
    # Projektfelder: Mitarbeiter sehen keine Stundensätze, Budgets, Notizen, Kundendaten – weder in der Liste noch im Monat
    for kopf, mit_budget in ((s["ma"], False), (s["vor"], True)):
        liste = client.get("/api/projekte", headers=kopf).json()["projekte"]
        p = [x for x in liste if x["id"] == pid][0]
        assert "hourly_rate" not in p and "notes" not in p and "customer_address" not in p and "reverse_charge" not in p and p["name"] == "Objekt Rathaus"
        assert ("budget_hours_month" in p) is mit_budget
        einzel = client.get(f"/api/projekte/{pid}", headers=kopf).json()
        assert "hourly_rate" not in einzel["projekt"] and einzel["kunde"] is None
        m = client.get(f"/api/projekte/{pid}/monat?jahr=2026&monat=10", headers=kopf).json()
        assert "hourly_rate" not in m["projekt"] and m["rechnung"] is None and all("hourly_rate" not in x for x in m["leistungen"])
    voll = [x for x in client.get("/api/projekte", headers=s["buero"]).json()["projekte"] if x["id"] == pid][0]
    assert voll["hourly_rate"] == 42 and voll["notes"] == "Schlüssel beim Hausmeister"


def test_05_kostenlos_mitarbeiter_ids_sicherung_seiten(client):
    s = _aufbau(client)
    pid = s["p"]["id"]
    basis = {"name": "Objekt Rathaus", "employee_ids": [s["vor_id"], s["ma_id"]]}
    # Stundensatz 0 ohne „kostenlos“ → Firmenstandard; mit „kostenlos“ bleibt 0
    assert client.put("/api/firma", json={"default_hourly_rate": 31}, headers=s["chef"]).status_code == 200
    assert client.put(f"/api/projekte/{pid}", json={**basis, "hourly_rate": 0}, headers=s["chef"]).json()["projekt"]["hourly_rate"] == 31
    p = client.put(f"/api/projekte/{pid}", json={**basis, "hourly_rate": 0, "kostenlos": True}, headers=s["chef"]).json()["projekt"]
    assert p["hourly_rate"] == 0 and p["kostenlos"] is True
    # Unbekannte Mitarbeiter-IDs werden nicht stillschweigend entfernt (sonst würde das Projekt für alle sichtbar)
    r = client.put(f"/api/projekte/{pid}", json={**basis, "employee_ids": ["gibt-es-nicht"], "hourly_rate": 30}, headers=s["chef"])
    assert r.status_code == 400
    assert client.get(f"/api/projekte/{pid}", headers=s["chef"]).json()["projekt"]["employee_ids"] == [s["vor_id"], s["ma_id"]]
    # Sicherung: alle Sammlungen, Hinweis auf Dateien; Dateien als ZIP
    zeit(client, s["chef"], pid, date="2026-10-05", user_id=s["ma_id"])
    assert client.post("/api/abschluss", json={"year": 2026, "month": 8}, headers=s["chef"]).status_code == 200
    d = client.post(f"/api/projekte/{pid}/dateien", data={"kategorie": "Fotos"}, files={"datei": ("foto.png", b"\x89PNG\r\n\x1a\n" + b"1" * 40, "image/png")}, headers=s["chef"]).json()["dokument"]
    sich = client.get("/api/exporte/sicherung.json", headers=s["chef"]).json()
    assert sich["version"] == 2 and "dateien.zip" in sich["hinweis"]
    for sammlung in ("users", "projects", "entries", "abschluesse", "zeitkonto", "services", "stempel", "documents", "protokoll", "aufgaben", "ausschreibungen", "webhooks", "api_tokens"):
        assert sammlung in sich["data"], sammlung
    assert len(sich["data"]["abschluesse"]) == 1 and all("pw_hash" not in u for u in sich["data"]["users"]) and all("path" not in x for x in sich["data"]["documents"])
    z = client.get("/api/exporte/dateien.zip", headers=s["chef"])
    assert z.status_code == 200
    namen = zipfile.ZipFile(io.BytesIO(z.content)).namelist()
    assert len(namen) == 1 and d["id"] in namen[0]
    assert client.get("/api/exporte/dateien.zip", headers=s["buero"]).status_code == 403
    # Seitengrößen mit Hinweis auf weitere Datensätze
    p2 = projekt(client, s["chef"], name="Zweites", hourly_rate=30)
    zeit(client, s["chef"], p2["id"], date="2026-10-06", user_id=s["ma_id"])
    client.post("/api/rechnungen/anlegen", json={"project_id": pid, "year": 2026, "month": 10}, headers=s["chef"])
    client.post("/api/rechnungen/anlegen", json={"project_id": p2["id"], "year": 2026, "month": 10}, headers=s["chef"])
    r = client.get("/api/rechnungen?limit=1", headers=s["chef"]).json()
    assert len(r["rechnungen"]) == 1 and r["hat_mehr"] is True and r["gesamt"] == 2
    assert client.get("/api/rechnungen?limit=1&offset=1", headers=s["chef"]).json()["hat_mehr"] is False
    r = client.get("/api/zeiten?von=2026-10-01&bis=2026-10-31&limit=1", headers=s["chef"]).json()
    assert len(r["eintraege"]) == 1 and r["hat_mehr"] is True
