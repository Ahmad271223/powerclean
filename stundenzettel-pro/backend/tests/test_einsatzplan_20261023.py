"""Einsatzplanung, Privatheit, Foto-Zuordnung und Freigaben – Regressionstests.

Laufen mit DB_MODE=memory nach: cd stundenzettel-pro/backend && pytest -q tests/test_einsatzplan_20261023.py
"""
import io
from PIL import Image

from conftest import einladen, projekt, registrieren


def schicht(p, ids, datum="2026-10-19", ende_datum=None):
    return {"project_id": p["id"], "user_ids": ids, "from_date": datum,
            "to_date": ende_datum or datum, "weekdays": [0, 1, 2, 3, 4],
            "start_time": "08:00", "end_time": "16:00", "pause_minutes": 30,
            "address": "Hauptstraße 12, Hannover", "note": "Tor B"}


def aufbau(client):
    chef, _ = registrieren(client, email="chef-plan@beispiel.de", firma="Planungs-Test", name="Chef")
    buero, _ = einladen(client, chef, "Büro", "buero-plan@beispiel.de", "buero")
    ma1, d1 = einladen(client, chef, "Anna", "anna-plan@beispiel.de", "mitarbeiter")
    ma2, d2 = einladen(client, chef, "Ben", "ben-plan@beispiel.de", "mitarbeiter")
    p = projekt(client, chef, name="Projekt Baustelle", address="Kanalstraße 4, Hannover")
    return chef, buero, ma1, ma2, d1["user"]["id"], d2["user"]["id"], p


def test_01_nur_inhaber_darf_projekte_erstellen_und_einsatz_zuweisen(client):
    chef, buero, ma1, ma2, id1, id2, p = aufbau(client)
    assert client.post("/api/projekte", json={"name": "Büro-Projekt"}, headers=buero).status_code == 403
    assert client.post("/api/einsatzplan/serie", json=schicht(p, [id1]), headers=buero).status_code == 403
    assert client.post("/api/einsatzplan/serie", json=schicht(p, [id1, id2]), headers=chef).status_code == 200
    r = client.get("/api/einsatzplan?von=2026-10-19&bis=2026-10-19", headers=ma1)
    assert r.status_code == 200, r.text
    plans = r.json()["einsatzplaene"]
    assert len(plans) == 1 and plans[0]["projekt"]["address"] == "Hauptstraße 12, Hannover"
    assert plans[0]["start_time"] == "08:00" and "mitarbeiter" not in plans[0]
    rb = client.get("/api/einsatzplan?von=2026-10-19&bis=2026-10-19", headers=ma2)
    assert len(rb.json()["einsatzplaene"]) == 1 and rb.json()["einsatzplaene"][0]["id"] != plans[0]["id"]
    rc = client.get("/api/einsatzplan?von=2026-10-19&bis=2026-10-19", headers=chef)
    assert len(rc.json()["einsatzplaene"]) == 2


def test_02_geplante_zeit_ist_keine_automatische_arbeitszeit(client):
    chef, buero, ma1, _, id1, _, p = aufbau(client)
    assert client.post("/api/einsatzplan/serie", json=schicht(p, [id1]), headers=chef).status_code == 200
    einsatz = client.get("/api/einsatzplan?von=2026-10-19&bis=2026-10-19", headers=chef).json()["einsatzplaene"][0]
    assert einsatz["planned_minutes"] == 450
    assert einsatz["stempel"]["vorhanden"] is False and einsatz["freigabe"] is None
    x = client.post(f"/api/einsatzplan/{einsatz['id']}/freigabe",
        json={"start_time": "08:00", "end_time": "16:00", "pause_minutes": 30,
              "grund": "", "arbeitsleistung_bestaetigt": False}, headers=chef)
    assert x.status_code == 422
    x = client.post(f"/api/einsatzplan/{einsatz['id']}/freigabe",
        json={"start_time": "08:00", "end_time": "16:00", "pause_minutes": 30,
              "grund": "Vor Ort kontrolliert", "arbeitsleistung_bestaetigt": True}, headers=chef)
    assert x.status_code == 200, x.text
    assert x.json()["einsatz"]["freigabe"]["net_minutes"] == 450
    # Auch nach Freigabe wird keine erfundene Stempelung geschrieben.
    self_times = client.get("/api/zeiten/meine?von=2026-10-19&bis=2026-10-19", headers=ma1).json()
    assert not self_times["eintraege"]
    assert client.post(f"/api/einsatzplan/{einsatz['id']}/freigabe",
        json={"start_time": "08:00", "end_time": "16:00", "pause_minutes": 30,
              "grund": "nochmals", "arbeitsleistung_bestaetigt": True}, headers=chef).status_code == 409
    assert client.post(f"/api/einsatzplan/{einsatz['id']}/freigabe",
        json={"start_time": "08:00", "end_time": "16:00", "pause_minutes": 30,
              "grund": "test", "arbeitsleistung_bestaetigt": True}, headers=buero).status_code == 403


def test_03_stempel_abweichung_bleibt_und_wird_fuer_chef_markiert(client):
    chef, _, ma1, _, id1, _, p = aufbau(client)
    client.post("/api/einsatzplan/serie", json=schicht(p, [id1]), headers=chef)
    e = client.post("/api/zeiten", json={
        "project_id": p["id"], "date": "2026-10-19", "start_time": "08:10",
        "end_time": "15:00", "pause_minutes": 30, "offline": True}, headers=ma1)
    assert e.status_code == 200, e.text
    plan = client.get("/api/einsatzplan?von=2026-10-19&bis=2026-10-19", headers=chef).json()["einsatzplaene"][0]
    assert plan["stempel"]["start_time"] == "08:10"
    assert plan["stempel"]["spaet_minuten"] == 10
    assert plan["stempel"]["frueher_minuten"] == 60
    assert plan["stempel"]["net_minutes"] == 380
    r = client.post(f"/api/einsatzplan/{plan['id']}/freigabe",
        json={"start_time": "08:00", "end_time": "15:00", "pause_minutes": 30,
              "grund": "Beginn pünktlich vor Ort, erst 08:10 gestempelt",
              "arbeitsleistung_bestaetigt": True}, headers=chef)
    assert r.status_code == 200, r.text
    assert r.json()["einsatz"]["freigabe"]["net_minutes"] == 390
    still = client.get("/api/zeiten/meine?von=2026-10-19&bis=2026-10-19", headers=ma1).json()["eintraege"]
    assert still[0]["start_time"] == "08:10" and still[0]["net_minutes"] == 380


def test_04_fremde_zeiten_und_fotograf_fuer_mitarbeiter_unsichtbar(client):
    chef, buero, ma1, ma2, id1, id2, p = aufbau(client)
    client.post("/api/einsatzplan/serie", json=schicht(p, [id1, id2]), headers=chef)
    now = client.post("/api/zeiten", json={
        "project_id": p["id"], "date": "2026-10-19", "start_time": "08:00",
        "end_time": "12:00", "pause_minutes": 0}, headers=ma2)
    assert now.status_code == 200, now.text
    r = client.get(f"/api/projekte/{p['id']}/zeiten?von=2026-10-19&bis=2026-10-19", headers=ma1)
    assert r.status_code == 200 and r.json()["eintraege"] == []
    assert client.get("/api/zeiten?von=2026-10-19&bis=2026-10-19", headers=buero).status_code == 403
    assert client.get(f"/api/projekte/{p['id']}/zeiten?von=2026-10-19&bis=2026-10-19",
                      headers=chef).json()["eintraege"][0]["net_minutes"] == 240
    buf = io.BytesIO()
    Image.new("RGB", (80, 80), (160, 100, 60)).save(buf, format="PNG")
    foto = client.post(f"/api/projekte/{p['id']}/dateien",
        data={"date": "2026-10-19", "kategorie": "Fotos"},
        files={"datei": ("ben-foto.png", buf.getvalue(), "image/png")}, headers=ma2)
    assert foto.status_code == 200, foto.text
    fotodaten = foto.json()["dokument"]
    eid = fotodaten["id"]
    rn = client.get(f"/api/projekte/{p['id']}/monat?jahr=2026&monat=10", headers=ma1)
    assert rn.status_code == 200, rn.text
    sicht = next(f for f in rn.json()["fotos"] if f["id"] == eid)
    assert "uploaded_by_name" not in sicht and "uploaded_by" not in sicht
    assert client.get(f"/api/dokumente/{eid}/datei", headers=ma1).headers["content-type"].startswith("image/jpeg")
    chef_fotos = client.get(f"/api/projekte/{p['id']}/monat?jahr=2026&monat=10", headers=chef).json()["fotos"]
    assert next(f for f in chef_fotos if f["id"] == eid)["uploaded_by"] == id2
    assert client.delete(f"/api/dokumente/{eid}", headers=ma1).status_code == 403
    assert client.delete(f"/api/dokumente/{eid}", headers=ma2).status_code == 200
