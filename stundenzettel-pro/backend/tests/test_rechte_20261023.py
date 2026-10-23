"""Negativtests der Berechtigungen (Go-live-Audit): je Rolle verbotene Aktionen, Firmengrenzen, Vorarbeiter-Grenzen – 2026-10-23."""
from conftest import einladen, projekt, registrieren, zeit

BUERO_NUR = [("GET", "/api/kunden"), ("GET", "/api/rechnungen"), ("GET", "/api/protokoll"), ("GET", "/api/stempel/aktiv"),
             ("GET", "/api/abschluss"), ("GET", "/api/zeiten/warnungen?von=2026-10-01&bis=2026-10-31"), ("GET", "/api/plattform/uebersicht"),
             ("GET", "/api/ausschreibungen"), ("GET", "/api/firma/verzeichnis"), ("GET", "/api/firma/speicher"), ("GET", "/api/lohn/vorbereitung?jahr=2026&monat=10")]


def _aufbau(client):
    a_chef, a_d = registrieren(client, email="chef@a-test.de", firma="Firma A", name="Anna A")
    a_buero, _ = einladen(client, a_chef, name="Bea Büro", email="bea@a-test.de", role="buero")
    a_vor, a_vor_d = einladen(client, a_chef, name="Vera Vor", email="vera@a-test.de", role="vorarbeiter")
    a_ma, a_ma_d = einladen(client, a_chef, name="Milan Ma", email="milan@a-test.de", role="mitarbeiter")
    a_ma2, a_ma2_d = einladen(client, a_chef, name="Nora Ma", email="nora@a-test.de", role="mitarbeiter")
    p_geleitet = projekt(client, a_chef, name="Geleitetes Objekt", employee_ids=[a_vor_d["user"]["id"], a_ma_d["user"]["id"]])
    p_fremd = projekt(client, a_chef, name="Anderes Objekt", employee_ids=[a_ma2_d["user"]["id"]])
    b_chef, b_d = registrieren(client, email="chef@b-test.de", firma="Firma B", name="Bernd B")
    p_b = projekt(client, b_chef, name="Objekt von B")
    return {"a_chef": a_chef, "a_buero": a_buero, "a_vor": a_vor, "a_ma": a_ma, "a_ma2": a_ma2, "a_ma_id": a_ma_d["user"]["id"], "a_ma2_id": a_ma2_d["user"]["id"],
            "a_vor_id": a_vor_d["user"]["id"], "p_geleitet": p_geleitet, "p_fremd": p_fremd, "b_chef": b_chef, "p_b": p_b, "b_firma": b_d["firma"]["id"]}


def test_01_mitarbeiter_und_vorarbeiter_sehen_keine_bueroseiten(client):
    s = _aufbau(client)
    for kopf in (s["a_ma"], s["a_vor"]):
        for methode, pfad in BUERO_NUR:
            r = client.request(methode, pfad, headers=kopf)
            assert r.status_code == 403, f"{methode} {pfad} für Nicht-Büro: {r.status_code}"
    # Mitarbeiterliste: für Teamfunktionen lesbar, aber nur Name/Rolle – keine E-Mail, Lohn- oder Vertragsdaten
    for m in client.get("/api/mitarbeiter", headers=s["a_ma"]).json()["mitarbeiter"]:
        assert set(m) <= {"id", "name", "role", "active", "personalnummer"}, m.keys()
    # Schreibende Verwaltungsaktionen
    assert client.post("/api/projekte", json={"name": "Neu", "hourly_rate": 30}, headers=s["a_ma"]).status_code == 403
    assert client.put(f"/api/projekte/{s['p_geleitet']['id']}", json={"name": "Umbenannt", "hourly_rate": 30}, headers=s["a_vor"]).status_code == 403
    assert client.delete(f"/api/projekte/{s['p_geleitet']['id']}", headers=s["a_vor"]).status_code == 403
    assert client.post("/api/mitarbeiter", json={"name": "X", "email": "x@a-test.de", "role": "mitarbeiter"}, headers=s["a_vor"]).status_code == 403
    assert client.put("/api/firma", json={"name": "Gekapert"}, headers=s["a_ma"]).status_code == 403
    assert client.post("/api/rechnungen/anlegen", json={"project_id": s["p_geleitet"]["id"], "year": 2026, "month": 10}, headers=s["a_vor"]).status_code == 403
    assert client.post("/api/abschluss", json={"year": 2026, "month": 9}, headers=s["a_vor"]).status_code == 403
    assert client.get(f"/api/mitarbeiter/{s['a_ma2_id']}/lohndaten", headers=s["a_ma"]).status_code == 403


def test_02_mitarbeiter_nur_eigene_daten(client):
    s = _aufbau(client)
    pid = s["p_geleitet"]["id"]
    zeit(client, s["a_ma"], pid, date="2026-10-05")
    zeit(client, s["a_chef"], pid, date="2026-10-05", start="13:00", ende="15:00", user_id=s["a_vor_id"])
    # Zeiten-Liste: Mitarbeiter bekommt nur eigene Einträge, auch mit fremder user_id in der Anfrage
    eigene = client.get(f"/api/zeiten/meine?von=2026-10-01&bis=2026-10-31", headers=s["a_ma"]).json()["eintraege"]
    assert [e["user_id"] for e in eigene] == [s["a_ma_id"]]
    r = client.get(f"/api/zeiten?von=2026-10-01&bis=2026-10-31&user_id={s['a_vor_id']}", headers=s["a_ma"])
    assert r.status_code == 403 or all(e["user_id"] == s["a_ma_id"] for e in r.json().get("eintraege", []))
    # Zeit für eine andere Person eintragen: Mitarbeiter nein
    r = client.post("/api/zeiten", json={"project_id": pid, "date": "2026-10-06", "start_time": "08:00", "end_time": "10:00", "user_id": s["a_vor_id"]}, headers=s["a_ma"])
    assert r.status_code == 403 or r.json()["eintrag"]["user_id"] == s["a_ma_id"]
    # Fremden Eintrag ändern/löschen: nein
    fremd = [e for e in client.get(f"/api/projekte/{pid}/zeiten?von=2026-10-01&bis=2026-10-31", headers=s["a_chef"]).json()["eintraege"] if e["user_id"] == s["a_vor_id"]][0]
    assert client.put(f"/api/zeiten/{fremd['id']}", json={"activity": "gekapert"}, headers=s["a_ma"]).status_code in (403, 404)
    assert client.delete(f"/api/zeiten/{fremd['id']}", headers=s["a_ma"]).status_code in (403, 404)
    # Projekt ohne Zuweisung: Mitarbeiter sieht es nicht und kann dort nicht stempeln
    assert client.get(f"/api/projekte/{s['p_fremd']['id']}", headers=s["a_ma"]).status_code in (403, 404)
    assert client.post("/api/stempel/start", json={"project_id": s["p_fremd"]["id"]}, headers=s["a_ma"]).status_code in (403, 404)
    assert client.post("/api/zeiten", json={"project_id": s["p_fremd"]["id"], "date": "2026-10-06", "start_time": "08:00", "end_time": "10:00"}, headers=s["a_ma"]).status_code in (403, 404)
    # Abwesenheiten anderer: unsichtbar; eigene nur solange beantragt
    client.post("/api/abwesenheiten", json={"type": "urlaub", "from_date": "2026-11-02", "to_date": "2026-11-03"}, headers=s["a_ma2"])
    assert client.get("/api/abwesenheiten", headers=s["a_ma"]).json()["abwesenheiten"] == []
    assert client.get(f"/api/abwesenheiten?user_id={s['a_ma2_id']}", headers=s["a_ma"]).json()["abwesenheiten"] == []


def test_03_vorarbeiter_nur_auf_zugewiesenen_projekten(client):
    s = _aufbau(client)
    # Auf dem zugewiesenen Projekt darf die Vorarbeiterin Zeiten für Kollegen eintragen – für Kollegen, die nicht auf dem Projekt sind, nicht
    r = client.post("/api/zeiten", json={"project_id": s["p_geleitet"]["id"], "date": "2026-10-06", "start_time": "08:00", "end_time": "10:00", "user_id": s["a_ma_id"]}, headers=s["a_vor"])
    assert r.status_code == 200 and r.json()["eintrag"]["user_id"] == s["a_ma_id"]
    r = client.post("/api/zeiten", json={"project_id": s["p_geleitet"]["id"], "date": "2026-10-06", "start_time": "08:00", "end_time": "10:00", "user_id": s["a_ma2_id"]}, headers=s["a_vor"])
    assert r.status_code in (400, 403)
    # Auf einem Projekt, dem sie nicht zugewiesen ist: kein Zugriff, keine Einträge für andere
    assert client.get(f"/api/projekte/{s['p_fremd']['id']}", headers=s["a_vor"]).status_code in (403, 404)
    r = client.post("/api/zeiten", json={"project_id": s["p_fremd"]["id"], "date": "2026-10-06", "start_time": "08:00", "end_time": "10:00", "user_id": s["a_ma2_id"]}, headers=s["a_vor"])
    assert r.status_code in (403, 404)
    # Stempelung eines Kollegen beenden ist Bürosache
    assert client.post("/api/stempel/start", json={"project_id": s["p_geleitet"]["id"]}, headers=s["a_ma"]).status_code == 200
    aktiv = client.get("/api/stempel/aktiv", headers=s["a_chef"]).json()["aktiv"]
    assert client.post(f"/api/stempel/{aktiv[0]['id']}/beenden", json={}, headers=s["a_vor"]).status_code == 403
    # Lohndaten und Personalakte anderer: nein
    assert client.get(f"/api/mitarbeiter/{s['a_ma_id']}/lohndaten", headers=s["a_vor"]).status_code == 403
    assert client.get(f"/api/mitarbeiter/{s['a_ma_id']}/dokumente", headers=s["a_vor"]).status_code == 403


def test_04_firmengrenzen(client):
    s = _aufbau(client)
    pid = s["p_geleitet"]["id"]
    e = zeit(client, s["a_chef"], pid, date="2026-10-05", user_id=s["a_ma_id"])
    inv = client.post("/api/rechnungen/anlegen", json={"project_id": pid, "year": 2026, "month": 10}, headers=s["a_chef"]).json()["rechnung"]
    dok = client.post(f"/api/projekte/{pid}/dateien", data={"kategorie": "Fotos"}, files={"datei": ("f.png", b"\x89PNG\r\n\x1a\n" + b"0" * 50, "image/png")}, headers=s["a_chef"]).json()["dokument"]
    b = s["b_chef"]
    # Inhaber von Firma B sieht nichts von Firma A – auch nicht mit erratenen IDs
    assert client.get(f"/api/projekte/{pid}", headers=b).status_code == 404
    assert client.get(f"/api/projekte/{pid}/monat?jahr=2026&monat=10", headers=b).status_code == 404
    assert client.put(f"/api/projekte/{pid}", json={"name": "Gekapert", "hourly_rate": 1}, headers=b).status_code == 404
    assert client.delete(f"/api/projekte/{pid}", headers=b).status_code == 404
    assert client.put(f"/api/zeiten/{e['id']}", json={"activity": "x"}, headers=b).status_code == 404
    assert client.delete(f"/api/zeiten/{e['id']}", headers=b).status_code == 404
    assert client.get(f"/api/rechnungen/{inv['id']}/daten", headers=b).status_code == 404
    assert client.get(f"/api/rechnungen/{inv['id']}/rechnung.pdf", headers=b).status_code == 404
    assert client.put(f"/api/rechnungen/{inv['id']}", json={"status": "bezahlt"}, headers=b).status_code == 404
    assert client.get(f"/api/dokumente/{dok['id']}/datei", headers=b).status_code == 404
    assert client.delete(f"/api/dokumente/{dok['id']}", headers=b).status_code == 404
    assert client.get(f"/api/mitarbeiter/{s['a_ma_id']}", headers=b).status_code == 404
    assert client.get(f"/api/mitarbeiter/{s['a_ma_id']}/lohndaten", headers=b).status_code == 404
    assert client.put(f"/api/mitarbeiter/{s['a_ma_id']}", json={"name": "Gekapert", "role": "mitarbeiter"}, headers=b).status_code == 404
    assert client.post("/api/zeiten", json={"project_id": pid, "date": "2026-10-06", "start_time": "08:00", "end_time": "10:00"}, headers=b).status_code == 404
    assert client.post("/api/stempel/start", json={"project_id": pid}, headers=b).status_code == 404
    assert client.post(f"/api/projekte/{pid}/unterschriften", json={"week_monday": "2026-10-05", "signer_name": "X", "image": "data:image/png;base64," + "A" * 80}, headers=b).status_code == 404
    # Listen von B enthalten nichts von A
    assert client.get("/api/projekte", headers=b).json()["projekte"] and all(p["name"] == "Objekt von B" for p in client.get("/api/projekte", headers=b).json()["projekte"])
    assert client.get("/api/rechnungen", headers=b).json()["rechnungen"] == []
    assert client.get("/api/mitarbeiter", headers=b).json()["mitarbeiter"] and all(m["email"].endswith("b-test.de") for m in client.get("/api/mitarbeiter", headers=b).json()["mitarbeiter"])
    # Ohne Anmeldung: nichts
    assert client.get("/api/stempel/status").status_code == 401
    assert client.get(f"/api/projekte/{pid}").status_code == 401
