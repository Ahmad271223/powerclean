"""Stufe B (24.10.2026): Plantafel – Einsätze planen (Serie, Konflikte, Abwesenheit, Feiertage), verschieben, kopieren, absagen,
rückgängig, Kolonnen, Planänderungs-Mitteilung, Abgleich mit der Stempelung, Freigabe mit Original, Erinnerungen, eigene Einsätze, PDF."""
import asyncio
from datetime import date, timedelta

import erinnerungen
import mail
from conftest import einladen, projekt, registrieren, zeit
from zeiten import lokal_jetzt

HEUTE = lokal_jetzt().date()
GESTERN = (HEUTE - timedelta(days=1)).isoformat()
MORGEN = (HEUTE + timedelta(days=1)).isoformat()
SERIE = {"from_date": "2026-11-02", "to_date": "2026-11-06", "weekdays": [0, 1, 2, 3, 4], "start_time": "08:00", "end_time": "16:00", "pause_minutes": 30, "address": "Hauptstraße 12, Hannover", "note": "Treffpunkt Tor B"}


def _aufbau(client):
    chef, _ = registrieren(client, email="chef@plan-b.de", firma="Plan B GmbH", name="Chef")
    buero, bd = einladen(client, chef, name="Bea Büro", email="bea@plan-b.de", role="buero")
    anna, ad = einladen(client, chef, name="Anna", email="anna@plan-b.de", role="mitarbeiter")
    ben, bnd = einladen(client, chef, name="Ben", email="ben@plan-b.de", role="mitarbeiter", passwort="geheim456")
    p = projekt(client, chef, name="Halle Hannover", address="Industrieweg 1, Hannover")
    return {"chef": chef, "buero": buero, "buero_id": bd["user"]["id"], "anna": anna, "anna_id": ad["user"]["id"], "ben": ben, "ben_id": bnd["user"]["id"], "p": p}


def test_01_planen_sichtbarkeit_konflikte(client):
    s = _aufbau(client)
    body = {"project_id": s["p"]["id"], "user_ids": [s["anna_id"], s["ben_id"]], **SERIE}
    r = client.post("/api/einsatzplan", json=body, headers=s["chef"])
    assert r.status_code == 200, r.text
    assert len(r.json()["einsaetze"]) == 10 and r.json()["serie_id"] and r.json()["einsaetze"][0]["planned_minutes"] == 450
    assert client.post("/api/einsatzplan", json=body, headers=s["anna"]).status_code == 403
    # Büro plant standardmäßig; ohne Plantafel-Recht nicht
    assert client.put(f"/api/mitarbeiter/{s['buero_id']}", json={"rechte": {"plantafel": False}}, headers=s["chef"]).status_code == 200
    assert client.post("/api/einsatzplan", json={**body, "from_date": "2026-11-09", "to_date": "2026-11-09"}, headers=s["buero"]).status_code == 403
    assert client.get("/api/einsatzplan?von=2026-11-02&bis=2026-11-06", headers=s["buero"]).json()["planer"] is False
    # Mitarbeiter sehen nur eigene Einsätze ohne Namen anderer; Planer sehen alles samt Mitarbeiter-, Projekt- und Kapazitätsliste
    eigene = client.get("/api/einsatzplan?von=2026-11-02&bis=2026-11-06", headers=s["anna"]).json()
    assert len(eigene["einsaetze"]) == 5 and "mitarbeiter" not in eigene["einsaetze"][0] and eigene["planer"] is False and eigene["einsaetze"][0]["projekt"]["address"] == "Hauptstraße 12, Hannover"
    alle = client.get("/api/einsatzplan?von=2026-11-02&bis=2026-11-06", headers=s["chef"]).json()
    assert len(alle["einsaetze"]) == 10 and alle["planer"] is True and {m["name"] for m in alle["mitarbeiter"]} >= {"Anna", "Ben"} and alle["projekte"][0]["name"] == "Halle Hannover"
    assert any(k["user_id"] == s["anna_id"] and k["geplant_minuten"] == 5 * 450 for k in alle["kapazitaet"])
    # Überschneidung am selben Tag → 409; andere Uhrzeit ohne Überschneidung → zweiter Einsatz am Tag ist erlaubt
    r = client.post("/api/einsatzplan", json={**body, "user_ids": [s["anna_id"]], "from_date": "2026-11-02", "to_date": "2026-11-02", "start_time": "10:00", "end_time": "12:00"}, headers=s["chef"])
    assert r.status_code == 409 and "Überschneidung" in r.json()["detail"]
    r = client.post("/api/einsatzplan", json={**body, "user_ids": [s["anna_id"]], "from_date": "2026-11-02", "to_date": "2026-11-02", "start_time": "16:30", "end_time": "19:00", "pause_minutes": 0}, headers=s["chef"])
    assert r.status_code == 200 and r.json()["einsaetze"][0]["planned_minutes"] == 150
    # Abwesenheit: Planung nur mit „trotzdem“
    assert client.post("/api/abwesenheiten", json={"user_id": s["ben_id"], "type": "urlaub", "from_date": "2026-11-09", "to_date": "2026-11-10"}, headers=s["chef"]).status_code == 200
    r = client.post("/api/einsatzplan", json={**body, "user_ids": [s["ben_id"]], "from_date": "2026-11-09", "to_date": "2026-11-09"}, headers=s["chef"])
    assert r.status_code == 409 and "abwesend" in r.json()["detail"]
    assert client.post("/api/einsatzplan", json={**body, "user_ids": [s["ben_id"]], "from_date": "2026-11-09", "to_date": "2026-11-09", "erzwingen": True}, headers=s["chef"]).status_code == 200
    u = client.get("/api/einsatzplan?von=2026-11-09&bis=2026-12-31", headers=s["chef"]).json()
    assert any(a["user_id"] == s["ben_id"] and a["type"] == "urlaub" for a in u["abwesenheiten"]) and "2026-12-25" in u["feiertage"]
    # Nachtschicht über Mitternacht
    r = client.post("/api/einsatzplan", json={**body, "user_ids": [s["anna_id"]], "from_date": "2026-11-20", "to_date": "2026-11-20", "start_time": "22:00", "end_time": "06:00", "pause_minutes": 30}, headers=s["chef"])
    assert r.status_code == 200 and r.json()["einsaetze"][0]["planned_minutes"] == 450


def test_02_verschieben_kopieren_absagen_rueckgaengig_kolonnen(client):
    s = _aufbau(client)
    e = client.post("/api/einsatzplan", json={"project_id": s["p"]["id"], "user_ids": [s["anna_id"]], "dates": ["2026-11-10"], "start_time": "08:00", "end_time": "16:00"}, headers=s["chef"]).json()["einsaetze"][0]
    r = client.put(f"/api/einsatzplan/{e['id']}", json={"date": "2026-11-11", "start_time": "09:00"}, headers=s["chef"])
    assert r.status_code == 200 and r.json()["einsatz"]["date"] == "2026-11-11" and r.json()["einsatz"]["version"] == 2 and r.json()["einsatz"]["verlauf"][-1]["vorher"]["date"] == "2026-11-10"
    r = client.post(f"/api/einsatzplan/{e['id']}/rueckgaengig", headers=s["chef"])
    assert r.status_code == 200 and r.json()["einsatz"]["date"] == "2026-11-10" and r.json()["einsatz"]["start_time"] == "08:00" and r.json()["einsatz"]["version"] == 3
    r = client.post(f"/api/einsatzplan/{e['id']}/kopieren", json={"dates": ["2026-11-10", "2026-11-12", "2026-11-13"], "user_ids": [s["anna_id"], s["ben_id"]]}, headers=s["chef"])
    assert r.status_code == 200 and len(r.json()["einsaetze"]) == 5 and r.json()["uebersprungen"] == []   # Quelle (Anna, 10.) bleibt, 5 Kopien
    assert client.delete(f"/api/einsatzplan/{e['id']}?grund=Kunde+verschoben", headers=s["chef"]).status_code == 200
    liste = client.get("/api/einsatzplan?von=2026-11-10&bis=2026-11-10", headers=s["chef"]).json()["einsaetze"]
    assert next(x for x in liste if x["id"] == e["id"])["status"] == "abgesagt"
    assert client.post(f"/api/einsatzplan/{e['id']}/wiederherstellen", headers=s["chef"]).json()["einsatz"]["status"] == "geplant"
    # Kolonne anlegen und als Ganzes planen; Mitglieder sehen ihre Kolonne, Planer ordnet zu
    k = client.post("/api/einsatzplan/kolonnen", json={"name": "Trupp 1", "user_ids": [s["anna_id"], s["ben_id"]], "vorarbeiter_id": s["anna_id"], "farbe": "#1D4ED8"}, headers=s["chef"])
    assert k.status_code == 200 and k.json()["kolonne"]["vorarbeiter_id"] == s["anna_id"]
    kid = k.json()["kolonne"]["id"]
    assert client.get("/api/einsatzplan/kolonnen", headers=s["anna"]).json()["kolonnen"][0]["mitglieder"][0]["name"] in ("Anna", "Ben")
    r = client.post("/api/einsatzplan", json={"project_id": s["p"]["id"], "user_ids": [s["anna_id"], s["ben_id"]], "dates": ["2026-11-16"], "start_time": "07:00", "end_time": "15:00", "kolonne_id": kid}, headers=s["chef"])
    assert r.status_code == 200 and all(x["kolonne"] == "Trupp 1" for x in r.json()["einsaetze"])
    meine = client.get("/api/einsatzplan/meine?tage=40", headers=s["anna"]).json()
    assert any(x["date"] == "2026-11-16" and x["kollegen"] == ["Ben"] for x in meine["spaeter"] + meine["naechste_woche"] + meine["woche"])
    # Planänderung für morgen → sofortige Mitteilung an die betroffene Person (einmal je Version)
    e2 = client.post("/api/einsatzplan", json={"project_id": s["p"]["id"], "user_ids": [s["ben_id"]], "dates": [MORGEN], "start_time": "08:00", "end_time": "16:00"}, headers=s["chef"]).json()["einsaetze"][0]
    assert client.put(f"/api/einsatzplan/{e2['id']}", json={"start_time": "07:00"}, headers=s["chef"]).status_code == 200
    arten = [n["art"] for n in client.get("/api/benachrichtigungen", headers=s["ben"]).json()["benachrichtigungen"]]
    assert arten.count("einsatz_aenderung") == 2   # neuer Einsatz für morgen + Änderung
    assert client.delete(f"/api/einsatzplan/kolonnen/{kid}", headers=s["chef"]).status_code == 200


def test_03_abgleich_und_freigabe(client):
    s = _aufbau(client)
    e = client.post("/api/einsatzplan", json={"project_id": s["p"]["id"], "user_ids": [s["anna_id"]], "dates": [GESTERN], "start_time": "08:00", "end_time": "16:00", "pause_minutes": 30}, headers=s["chef"]).json()["einsaetze"][0]
    zeit(client, s["anna"], s["p"]["id"], date=GESTERN, start="08:10", ende="15:00", pause=30)
    a = client.get(f"/api/einsatzplan/abgleich?von={GESTERN}&bis={GESTERN}", headers=s["chef"]).json()
    x = a["einsaetze"][0]["abgleich"]
    assert x["status"] == "abweichung" and "10 Minuten nach geplantem Beginn" in x["hinweise"][0] and "60 Minuten vor geplantem Ende" in x["hinweise"][1] and x["net_minutes"] == 380
    assert a["zaehler"]["abweichung"] == 1
    assert client.get(f"/api/einsatzplan/abgleich?von={GESTERN}&bis={GESTERN}", headers=s["anna"]).status_code == 403
    # Freigabe mit Abweichung braucht Bestätigung und Grund; dann gilt die freigegebene Zeit, die Stempelung bleibt im Original
    r = client.post(f"/api/einsatzplan/{e['id']}/freigabe", json={"start_time": "08:00", "end_time": "15:00", "pause_minutes": 30}, headers=s["chef"])
    assert r.status_code == 422
    r = client.post(f"/api/einsatzplan/{e['id']}/freigabe", json={"start_time": "08:00", "end_time": "15:00", "pause_minutes": 30, "grund": "Beginn vor Ort geprüft, Stempeluhr später geöffnet", "arbeitsleistung_bestaetigt": True}, headers=s["chef"])
    assert r.status_code == 200, r.text
    assert r.json()["einsatz"]["freigabe"]["net_minutes"] == 390 and r.json()["einsatz"]["abgleich"]["status"] == "freigegeben"
    eintrag = client.get(f"/api/zeiten/meine?von={GESTERN}&bis={GESTERN}", headers=s["anna"]).json()["eintraege"][0]
    assert eintrag["start_time"] == "08:00" and eintrag["net_minutes"] == 390 and eintrag["original"]["start_time"] == "08:10" and eintrag["original"]["net_minutes"] == 380 and eintrag["freigabe"]["von_name"] == "Chef" and eintrag["korrigiert"] is True
    assert client.post(f"/api/einsatzplan/{e['id']}/freigabe", json={"start_time": "08:00", "end_time": "15:00", "pause_minutes": 30, "grund": "x", "arbeitsleistung_bestaetigt": True}, headers=s["chef"]).status_code == 409
    assert client.put(f"/api/einsatzplan/{e['id']}", json={"start_time": "07:00"}, headers=s["chef"]).status_code == 409
    # Projekt-Stundenzettel aus freigegebenen Zeiten
    pdf = client.get(f"/api/einsatzplan/stundenzettel.pdf?project_id={s['p']['id']}&von={GESTERN}&bis={GESTERN}", headers=s["chef"])
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    # Freigabe zurücknehmen → Original wieder wirksam
    assert client.post(f"/api/einsatzplan/{e['id']}/freigabe-zuruecknehmen?grund=Irrtum", headers=s["chef"]).status_code == 200
    eintrag = client.get(f"/api/zeiten/meine?von={GESTERN}&bis={GESTERN}", headers=s["anna"]).json()["eintraege"][0]
    assert eintrag["start_time"] == "08:10" and eintrag["net_minutes"] == 380 and "freigabe" not in eintrag
    assert client.get(f"/api/einsatzplan/stundenzettel.pdf?project_id={s['p']['id']}&von={GESTERN}&bis={GESTERN}", headers=s["chef"]).status_code == 409
    # Fehlende Stempelung: Plan bleibt „zu prüfen“; Freigabe erzeugt einen Eintrag der Quelle „freigabe“, Rücknahme entfernt ihn
    e2 = client.post("/api/einsatzplan", json={"project_id": s["p"]["id"], "user_ids": [s["ben_id"]], "dates": [GESTERN], "start_time": "08:00", "end_time": "16:00", "pause_minutes": 30}, headers=s["chef"]).json()["einsaetze"][0]
    assert e2["abgleich"]["status"] == "fehlt"
    r = client.post(f"/api/einsatzplan/{e2['id']}/freigabe", json={"start_time": "08:00", "end_time": "16:00", "pause_minutes": 30, "grund": "War laut Vorarbeiter den ganzen Tag vor Ort", "arbeitsleistung_bestaetigt": True}, headers=s["chef"])
    assert r.status_code == 200 and r.json()["einsatz"]["freigabe"]["eintrag_neu"] is True
    ben_zeiten = client.get(f"/api/zeiten/meine?von={GESTERN}&bis={GESTERN}", headers=s["ben"]).json()["eintraege"]
    assert len(ben_zeiten) == 1 and ben_zeiten[0]["source"] == "freigabe" and ben_zeiten[0]["net_minutes"] == 450
    assert client.post(f"/api/einsatzplan/{e2['id']}/freigabe-zuruecknehmen", headers=s["chef"]).status_code == 200
    assert client.get(f"/api/zeiten/meine?von={GESTERN}&bis={GESTERN}", headers=s["ben"]).json()["eintraege"] == []
    # Zukunft lässt sich nicht freigeben; Stempelung ohne Plan erscheint im Abgleich
    e3 = client.post("/api/einsatzplan", json={"project_id": s["p"]["id"], "user_ids": [s["anna_id"]], "dates": [MORGEN], "start_time": "08:00", "end_time": "16:00"}, headers=s["chef"]).json()["einsaetze"][0]
    assert client.post(f"/api/einsatzplan/{e3['id']}/freigabe", json={"start_time": "08:00", "end_time": "16:00", "pause_minutes": 30, "grund": "x", "arbeitsleistung_bestaetigt": True}, headers=s["chef"]).status_code == 409
    vorgestern = (HEUTE - timedelta(days=2)).isoformat()
    import db as dbmodul
    firma_id = client.get("/api/auth/ich", headers=s["chef"]).json()["firma"]["id"]
    asyncio.run(dbmodul.db().entries.insert_one({"id": "e-ungeplant", "firma_id": firma_id, "project_id": s["p"]["id"], "user_id": s["ben_id"], "date": vorgestern, "start_time": "06:00",
                                                 "end_time": "10:00", "pause_minutes": 0, "net_minutes": 240, "workers": 1, "source": "stempel"}))
    a = client.get(f"/api/einsatzplan/abgleich?von={vorgestern}&bis={GESTERN}", headers=s["chef"]).json()
    assert any(x["date"] == vorgestern and x["mitarbeiter"] == "Ben" for x in a["ungeplante_stempelungen"])


def test_04_erinnerungen_meine_und_einstellungen(client, monkeypatch):
    monkeypatch.setattr(mail, "SOFORT_ZUSTELLEN", False)
    s = _aufbau(client)
    client.post("/api/einsatzplan", json={"project_id": s["p"]["id"], "user_ids": [s["anna_id"], s["ben_id"]], "dates": [MORGEN], "start_time": "08:00", "end_time": "16:00", "note": "Treffpunkt Tor B"}, headers=s["chef"])
    um = lambda h, m=0: lokal_jetzt().replace(hour=h, minute=m, second=0, microsecond=0)   # noqa: E731
    assert asyncio.run(erinnerungen.einmal_pruefen(um(17))) == 0          # vor 18 Uhr nichts
    assert asyncio.run(erinnerungen.einmal_pruefen(um(18, 30))) == 2      # genau einmal je Einsatz
    assert asyncio.run(erinnerungen.einmal_pruefen(um(18, 45))) == 0
    n = [x for x in client.get("/api/benachrichtigungen", headers=s["anna"]).json()["benachrichtigungen"] if x["art"] == "einsatz_erinnerung"]
    assert len(n) == 1 and "Morgen: Halle Hannover, 08:00–16:00 Uhr, Industrieweg 1, Hannover. Treffpunkt Tor B" in n[0]["text"]
    mails = [m for m in client.get("/api/firma/emails", headers=s["chef"]).json()["emails"] if m["art"] == "einsatz_erinnerung"]
    assert len(mails) == 2 and mails[0]["status"] == "nicht_konfiguriert"
    # Planänderung (neue Version) → neue Erinnerung; Firma stellt Uhrzeit um und schaltet E-Mail ab
    e = client.get(f"/api/einsatzplan?von={MORGEN}&bis={MORGEN}", headers=s["chef"]).json()["einsaetze"][0]
    client.put(f"/api/einsatzplan/{e['id']}", json={"start_time": "09:00"}, headers=s["chef"])
    assert asyncio.run(erinnerungen.einmal_pruefen(um(19))) == 1
    assert client.put("/api/firma", json={"erinnerung": {"uhrzeit": "20:00", "email": False}}, headers=s["chef"]).status_code == 200
    client.post("/api/einsatzplan", json={"project_id": s["p"]["id"], "user_ids": [s["anna_id"]], "dates": [MORGEN], "start_time": "17:00", "end_time": "19:00", "pause_minutes": 0}, headers=s["chef"])
    assert asyncio.run(erinnerungen.einmal_pruefen(um(19, 30))) == 0      # vor der neuen Uhrzeit
    vorher = len([m for m in client.get("/api/firma/emails", headers=s["chef"]).json()["emails"] if m["art"] == "einsatz_erinnerung"])
    assert asyncio.run(erinnerungen.einmal_pruefen(um(20, 30))) == 1
    assert len([m for m in client.get("/api/firma/emails", headers=s["chef"]).json()["emails"] if m["art"] == "einsatz_erinnerung"]) == vorher   # keine E-Mail mehr
    # Eigene Einsätze: morgen mit Navigation; Planer sehen die Einstellungen
    meine = client.get("/api/einsatzplan/meine", headers=s["anna"]).json()
    assert len(meine["morgen"]) == 2 and meine["morgen"][0]["navigation"].startswith("https://www.google.com/maps") and meine["heute"] == []
    assert client.get(f"/api/einsatzplan?von={MORGEN}&bis={MORGEN}", headers=s["chef"]).json()["erinnerung"] == {"uhrzeit": "20:00", "email": False}
    punkte = client.get("/api/dashboard/aufgaben", headers=s["chef"]).json()["punkte"]
    assert isinstance(punkte, list)
