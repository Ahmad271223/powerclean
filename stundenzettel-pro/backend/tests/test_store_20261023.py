# -*- coding: utf-8 -*-
"""Store-Pflichten (Wunsch Ahmad 23.10.2026, Play Store + App Store): Konto in der App löschen, Firma löschen,
Datenschutz/Impressum als Seiten, Deep-Link-Dateien für Android App Links und iOS Universal Links, CORS für die nativen Apps."""
from conftest import einladen, projekt, registrieren, zeit


def test_01_konto_loeschen_anonymisiert(client):
    kopf, _ = registrieren(client)
    p = projekt(client, kopf)
    ma, ma_d = einladen(client, kopf)
    uid = ma_d["user"]["id"]
    zeit(client, ma, p["id"], date="2026-10-05")
    assert client.request("DELETE", "/api/auth/konto", json={"password": "falsch"}, headers=ma).status_code == 400
    r = client.request("DELETE", "/api/auth/konto", json={"password": "mitarbeit123"}, headers=ma)
    assert r.status_code == 200, r.text
    # Anmeldung weg, Kontaktdaten weg, Name auf den Zeiten bleibt (MiLoG)
    assert client.post("/api/auth/login", json={"email": "mia@beispiel.de", "password": "mitarbeit123"}).status_code == 401
    assert client.get("/api/auth/ich", headers=ma).status_code == 401
    u = client.get(f"/api/mitarbeiter/{uid}", headers=kopf).json()["mitarbeiter"]
    assert u["active"] is False and u["email"].endswith("@konto.geloescht") and u["name"] == "Mia Mitarbeiterin" and u["deleted_at"]
    m = client.get(f"/api/projekte/{p['id']}/monat?jahr=2026&monat=10", headers=kopf).json()
    assert m["eintraege"][0]["user_name"] == "Mia Mitarbeiterin"
    # E-Mail ist wieder frei
    assert client.post("/api/mitarbeiter", json={"name": "Mia neu", "email": "mia@beispiel.de"}, headers=kopf).status_code == 200
    # einziger Inhaber kann sein Konto nicht löschen, nur die Firma
    r = client.request("DELETE", "/api/auth/konto", json={"password": "geheim123"}, headers=kopf)
    assert r.status_code == 400 and "Firma" in r.json()["detail"]


def test_02_firma_loeschen(client):
    kopf, daten = registrieren(client)
    p = projekt(client, kopf)
    ma, _ = einladen(client, kopf)
    zeit(client, ma, p["id"], date="2026-10-05")
    client.post("/api/leistungen", json={"name": "X"}, headers=kopf)
    assert client.request("DELETE", "/api/firma", json={"name": "falsch", "password": "geheim123"}, headers=kopf).status_code == 400
    assert client.request("DELETE", "/api/firma", json={"name": "PowerClean Test", "password": "falsch"}, headers=kopf).status_code == 400
    assert client.request("DELETE", "/api/firma", json={"name": "PowerClean Test", "password": "geheim123"}, headers=ma).status_code == 403
    r = client.request("DELETE", "/api/firma", json={"name": "PowerClean Test", "password": "geheim123"}, headers=kopf)
    assert r.status_code == 200, r.text
    assert client.get("/api/auth/ich", headers=kopf).status_code in (401, 404)
    assert client.get("/api/auth/ich", headers=ma).status_code in (401, 404)
    assert client.post("/api/auth/login", json={"email": "chef@beispiel.de", "password": "geheim123"}).status_code == 401
    # dieselbe Firma kann neu registriert werden
    assert client.post("/api/auth/registrieren", json={"firma_name": "PowerClean Test", "name": "Ahmad", "email": "chef@beispiel.de", "password": "geheim123"}).status_code == 200


def test_03_rechtstexte_und_deep_links(client, monkeypatch):
    import config
    r = client.get("/datenschutz")
    assert r.status_code == 200 and "Datenschutzerklärung" in r.text and "Konto löschen" in r.text and "Standort" in r.text
    assert "Impressum" in client.get("/impressum").text
    assert client.get("/.well-known/assetlinks.json").status_code == 404
    assert client.get("/.well-known/apple-app-site-association").status_code == 404
    monkeypatch.setattr(config, "ANDROID_SHA256", ["AA:BB"])
    monkeypatch.setattr(config, "APPLE_TEAM_ID", "TEAM123")
    a = client.get("/.well-known/assetlinks.json").json()
    assert a[0]["target"]["package_name"] == config.ANDROID_PACKAGE and a[0]["target"]["sha256_cert_fingerprints"] == ["AA:BB"]
    aasa = client.get("/.well-known/apple-app-site-association")
    assert aasa.headers["content-type"].startswith("application/json")
    assert aasa.json()["applinks"]["details"][0]["appID"] == f"TEAM123.{config.IOS_BUNDLE_ID}"
    assert "capacitor://localhost" in config.CORS_ORIGINS and "https://localhost" in config.CORS_ORIGINS
