"""iPhone-App, Schritt 1 (24.11.2026): Feature-Flag `sprachplanung`, einzelner Einsatz (Ziel einer Push-Nachricht) und Lesebestätigung
„Gelesen/Bestätigt“ je Version – nur durch die eingeplante Person, nach einer Planänderung wieder offen."""
from datetime import timedelta

from conftest import einladen, projekt, registrieren
from zeiten import lokal_jetzt

TAG = (lokal_jetzt().date() + timedelta(days=5)).isoformat()


def _aufbau(client):
    chef, _ = registrieren(client, email="chef@app-test.de", firma="App Test GmbH", name="Chef")
    nils, nd = einladen(client, chef, name="Nils Becker", email="nils@app-test.de")
    tom, td = einladen(client, chef, name="Tom Wagner", email="tom@app-test.de", passwort="geheim4567")
    buero, _ = einladen(client, chef, name="Bea Büro", email="bea@app-test.de", role="buero", passwort="buero12345")
    p = projekt(client, chef, name="Badsanierung Müller", address="Hauptstraße 5, Hannover")
    r = client.post("/api/einsatzplan", json={"project_id": p["id"], "user_ids": [nd["user"]["id"]], "dates": [TAG], "start_time": "07:00", "end_time": "16:00"}, headers=chef)
    assert r.status_code == 200, r.text
    return {"chef": chef, "nils": nils, "tom": tom, "buero": buero, "p": p, "e": r.json()["einsaetze"][0], "nils_id": nd["user"]["id"]}


def test_01_flag_sprachplanung_standard_aus(client):
    f = client.get("/api/features").json()
    assert f["features"]["sprachplanung"] is False and "Sprache" in f["beschreibung"]["sprachplanung"]


def test_02_einzelner_einsatz_sichtbarkeit(client):
    s = _aufbau(client)
    eid = s["e"]["id"]
    eigen = client.get(f"/api/einsatzplan/{eid}", headers=s["nils"])
    assert eigen.status_code == 200, eigen.text
    e = eigen.json()["einsatz"]
    assert e["projekt"]["name"] == "Badsanierung Müller" and e["projekt"]["address"] == "Hauptstraße 5, Hannover" and e["start_time"] == "07:00"
    assert "Hauptstra" in e["navigation"] and "mitarbeiter" not in e and "verlauf" not in e
    assert e["quittung"] == {"gelesen": False, "bestaetigt": False, "gelesen_at": None, "bestaetigt_at": None}
    # fremder Mitarbeiter: 404 (nicht 403), Planer sieht Namen und Verlauf
    assert client.get(f"/api/einsatzplan/{eid}", headers=s["tom"]).status_code == 404
    planer = client.get(f"/api/einsatzplan/{eid}", headers=s["buero"]).json()["einsatz"]
    assert planer["mitarbeiter"] == "Nils Becker" and planer["verlauf"]
    assert client.get("/api/einsatzplan/gibt-es-nicht", headers=s["chef"]).status_code == 404
    # bestehende Routen mit festem Pfad werden nicht vom neuen /{einsatz_id} verdeckt
    assert client.get("/api/einsatzplan/meine", headers=s["nils"]).status_code == 200
    assert client.get("/api/einsatzplan/kolonnen", headers=s["nils"]).status_code == 200


def test_03_gelesen_und_bestaetigt_je_version(client):
    s = _aufbau(client)
    eid = s["e"]["id"]
    r = client.post(f"/api/einsatzplan/{eid}/gelesen", headers=s["nils"])
    assert r.status_code == 200 and r.json()["einsatz"]["quittung"]["gelesen"] is True and r.json()["einsatz"]["quittung"]["bestaetigt"] is False
    r = client.post(f"/api/einsatzplan/{eid}/bestaetigen", headers=s["nils"])
    q = r.json()["einsatz"]["quittung"]
    assert r.status_code == 200 and q["gelesen"] and q["bestaetigt"] and q["bestaetigt_at"]
    # wiederholt: Zeitpunkt bleibt der erste
    assert client.post(f"/api/einsatzplan/{eid}/bestaetigen", headers=s["nils"]).json()["einsatz"]["quittung"]["bestaetigt_at"] == q["bestaetigt_at"]
    # Planer sieht den Stand in Plantafel und „meine“ zeigt ihn dem Mitarbeiter
    tafel = client.get(f"/api/einsatzplan?von={TAG}&bis={TAG}", headers=s["chef"]).json()["einsaetze"]
    assert tafel[0]["quittung"]["bestaetigt"] is True
    meine = client.get("/api/einsatzplan/meine", headers=s["nils"]).json()
    assert any(x["id"] == eid and x["quittung"]["bestaetigt"] for x in meine["woche"] + meine["naechste_woche"] + meine["spaeter"])
    # nur die eingeplante Person: Planer 403, anderer Mitarbeiter 404
    assert client.post(f"/api/einsatzplan/{eid}/bestaetigen", headers=s["chef"]).status_code == 403
    assert client.post(f"/api/einsatzplan/{eid}/gelesen", headers=s["tom"]).status_code == 404
    # Planänderung (neue Version) → Bestätigung wieder offen
    assert client.put(f"/api/einsatzplan/{eid}", json={"start_time": "08:00"}, headers=s["chef"]).status_code == 200
    assert client.get(f"/api/einsatzplan/{eid}", headers=s["nils"]).json()["einsatz"]["quittung"] == {"gelesen": False, "bestaetigt": False, "gelesen_at": None, "bestaetigt_at": None}
    # abgesagt → nicht bestätigbar, gelesen geht
    assert client.delete(f"/api/einsatzplan/{eid}?grund=Kunde+krank", headers=s["chef"]).status_code == 200
    assert client.post(f"/api/einsatzplan/{eid}/bestaetigen", headers=s["nils"]).status_code == 409
    assert client.post(f"/api/einsatzplan/{eid}/gelesen", headers=s["nils"]).status_code == 200
