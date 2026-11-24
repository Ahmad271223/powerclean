"""Push-Nachrichten (24.11.2026): Geräte, Ausgang mit Testersatz, eine Nachricht je Vorgang, Zustellstand für den Chef, Wiederholung,
abgemeldete Geräte – und die genauen Anfragen an Apple (APNs) und Google (FCM), geprüft ohne Netz mit Wegwerf-Schlüsseln."""
import asyncio
import json
from datetime import timedelta

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa

import push
from conftest import einladen, projekt, registrieren
from zeiten import lokal_jetzt

HEUTE = lokal_jetzt().date()
MONTAG = HEUTE + timedelta(days=7 - HEUTE.weekday())          # nächster Montag
WOCHE = [(MONTAG + timedelta(days=i)).isoformat() for i in range(5)]
IOS_TOKEN = "a" * 64
ANDROID_TOKEN = "fcm-token_ABC:123-" + "x" * 40


@pytest.fixture()
def testmodus(monkeypatch):
    monkeypatch.setenv("PUSH_MODUS", "test")
    monkeypatch.setattr(push, "SOFORT_ZUSTELLEN", False)
    push.TEST_GESENDET.clear()
    yield
    push.TEST_GESENDET.clear()


def _aufbau(client):
    chef, _ = registrieren(client, email="chef@push-test.de", firma="Push Test GmbH", name="Chef")
    nils, nd = einladen(client, chef, name="Nils Becker", email="nils@push-test.de")
    tom, td = einladen(client, chef, name="Tom Wagner", email="tom@push-test.de", passwort="geheim4567")
    p = projekt(client, chef, name="Badsanierung Müller", address="Hauptstraße 5, 30159 Hannover")
    return {"chef": chef, "nils": nils, "nils_id": nd["user"]["id"], "tom": tom, "tom_id": td["user"]["id"], "p": p}


def _planen(client, s, user_id, tage, start="07:00", ende="16:00"):
    r = client.post("/api/einsatzplan", json={"project_id": s["p"]["id"], "user_ids": [user_id], "dates": tage, "start_time": start, "end_time": ende}, headers=s["chef"])
    assert r.status_code == 200, r.text
    return r.json()["einsaetze"]


def _ausgang():
    import db as dbmodul
    async def lesen():
        return [x async for x in dbmodul.db().push_ausgang.find({}, {"_id": 0}).sort("created_at", 1)]
    return asyncio.run(lesen())


def test_01_geraete_registrieren_wandern_abmelden(client):
    s = _aufbau(client)
    assert client.post("/api/geraete", json={"plattform": "windows", "token": IOS_TOKEN}, headers=s["nils"]).status_code == 422
    assert client.post("/api/geraete", json={"plattform": "ios", "token": "kurz"}, headers=s["nils"]).status_code == 422
    r = client.post("/api/geraete", json={"plattform": "ios", "token": IOS_TOKEN, "app_version": "1.0.0"}, headers=s["nils"])
    assert r.status_code == 200 and r.json()["push"]["modus"] == "auto"
    assert client.post("/api/geraete", json={"plattform": "ios", "token": IOS_TOKEN}, headers=s["nils"]).json()["geraet_id"] == r.json()["geraet_id"]   # kein Doppel
    meine = client.get("/api/geraete", headers=s["nils"]).json()
    assert len(meine["geraete"]) == 1 and "token" not in meine["geraete"][0]
    # Tom meldet sich auf demselben Handy an → das Gerät gehört jetzt Tom
    assert client.post("/api/geraete", json={"plattform": "ios", "token": IOS_TOKEN}, headers=s["tom"]).status_code == 200
    assert [g["aktiv"] for g in client.get("/api/geraete", headers=s["tom"]).json()["geraete"]] == [True]
    assert client.get("/api/geraete", headers=s["nils"]).json()["geraete"] == []
    # Abmelden nur für das eigene Gerät
    assert client.post("/api/geraete/abmelden", json={"token": IOS_TOKEN}, headers=s["nils"]).json()["ok"] is False
    assert client.post("/api/geraete/abmelden", json={"token": IOS_TOKEN}, headers=s["tom"]).json()["ok"] is True
    assert client.post("/api/geraete", json={"plattform": "ios", "token": IOS_TOKEN}).status_code == 401


def test_02_serie_eine_nachricht_zustellung_fuer_chef(client, testmodus):
    s = _aufbau(client)
    client.post("/api/geraete", json={"plattform": "ios", "token": IOS_TOKEN}, headers=s["nils"])
    client.post("/api/geraete", json={"plattform": "android", "token": ANDROID_TOKEN}, headers=s["nils"])
    serie = _planen(client, s, s["nils_id"], WOCHE)
    ausgang = _ausgang()
    assert len(ausgang) == 2 and {a["plattform"] for a in ausgang} == {"ios", "android"} and all(a["status"] == "offen" for a in ausgang)
    # vor der Zustellung: Chef sieht „offen“
    tafel = client.get(f"/api/einsatzplan?von={WOCHE[0]}&bis={WOCHE[-1]}", headers=s["chef"]).json()["einsaetze"]
    assert {e["zustellung"] for e in tafel} == {"offen"}
    assert asyncio.run(push.ausgang_abarbeiten()) == 2
    gesendet = push.TEST_GESENDET
    assert len(gesendet) == 2 and gesendet[0]["titel"] == "📅 Neue Einteilung"
    tag1, tag5 = MONTAG.strftime("%d.%m."), (MONTAG + timedelta(days=4)).strftime("%d.%m.")
    assert gesendet[0]["text"] == f"Badsanierung Müller, Hauptstraße 5, Mo–Fr {tag1}–{tag5} 7–16 Uhr"
    assert gesendet[0]["link"] == f"/einsaetze?einsatz={serie[0]['id']}"
    tafel = client.get(f"/api/einsatzplan?von={WOCHE[0]}&bis={WOCHE[-1]}", headers=s["chef"]).json()["einsaetze"]
    assert {e["zustellung"] for e in tafel} == {"zugestellt"}
    # Mitarbeiter sehen den Zustellstand nicht (nur Planer)
    assert "zustellung" not in client.get("/api/einsatzplan/meine", headers=s["nils"]).json()["naechste_woche"][0]
    # Änderung → neue Version: Stand wieder offen, eigene Nachricht „geändert“
    assert client.put(f"/api/einsatzplan/{serie[2]['id']}", json={"start_time": "08:00"}, headers=s["chef"]).status_code == 200
    e = client.get(f"/api/einsatzplan/{serie[2]['id']}", headers=s["chef"]).json()["einsatz"]
    assert e["zustellung"] == "offen"
    push.TEST_GESENDET.clear()
    asyncio.run(push.ausgang_abarbeiten())
    assert push.TEST_GESENDET[0]["titel"] == "✏️ Einteilung geändert" and push.TEST_GESENDET[0]["text"].endswith(f"Mi {(MONTAG + timedelta(days=2)).strftime('%d.%m.')} 8–16 Uhr")
    assert client.get(f"/api/einsatzplan/{serie[2]['id']}", headers=s["chef"]).json()["einsatz"]["zustellung"] == "zugestellt"
    # Absagen → Nachricht „abgesagt“ ohne Uhrzeit
    push.TEST_GESENDET.clear()
    assert client.delete(f"/api/einsatzplan/{serie[4]['id']}?grund=Regen", headers=s["chef"]).status_code == 200
    asyncio.run(push.ausgang_abarbeiten())
    assert push.TEST_GESENDET[0]["titel"] == "❌ Einteilung abgesagt" and "Uhr" not in push.TEST_GESENDET[0]["text"]


def test_03_uebergabe_vergangenheit_kein_geraet(client, testmodus):
    s = _aufbau(client)
    client.post("/api/geraete", json={"plattform": "android", "token": ANDROID_TOKEN}, headers=s["tom"])
    # Nils hat kein Gerät → Nachweis „kein_geraet“, Chef sieht es
    e = _planen(client, s, s["nils_id"], [WOCHE[0]])[0]
    assert [a["status"] for a in _ausgang()] == ["kein_geraet"]
    assert client.get(f"/api/einsatzplan/{e['id']}", headers=s["chef"]).json()["einsatz"]["zustellung"] == "kein_geraet"
    # Übergabe an Tom: Tom bekommt „neu“, Nils' Nachweis „abgesagt“
    assert client.put(f"/api/einsatzplan/{e['id']}", json={"user_id": s["tom_id"]}, headers=s["chef"]).status_code == 200
    arten = [(a["user_id"], a["art"], a["status"]) for a in _ausgang()]
    assert (s["nils_id"], "einsatz_abgesagt", "kein_geraet") in arten and (s["tom_id"], "einsatz_neu", "offen") in arten
    # Vergangene Tage werden nicht gemeldet
    vorher = len(_ausgang())
    _planen(client, s, s["tom_id"], [(HEUTE - timedelta(days=3)).isoformat()])
    assert len(_ausgang()) == vorher


def test_04_ohne_zugangsdaten_nur_nachweis(client, monkeypatch):
    monkeypatch.delenv("PUSH_MODUS", raising=False)
    for name in ("APNS_TEAM_ID", "APNS_KEY_ID", "APNS_SCHLUESSEL", "APNS_SCHLUESSEL_DATEI", "FCM_DIENSTKONTO", "FCM_DIENSTKONTO_DATEI"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(push, "SOFORT_ZUSTELLEN", False)
    s = _aufbau(client)
    client.post("/api/geraete", json={"plattform": "ios", "token": IOS_TOKEN}, headers=s["nils"])
    _planen(client, s, s["nils_id"], [WOCHE[1]])
    assert [a["status"] for a in _ausgang()] == ["nicht_konfiguriert"]
    assert asyncio.run(push.ausgang_abarbeiten()) == 0


def test_05_wiederholung_und_abgemeldetes_geraet(client, testmodus, monkeypatch):
    s = _aufbau(client)
    client.post("/api/geraete", json={"plattform": "ios", "token": IOS_TOKEN}, headers=s["nils"])

    async def netzfehler(*_):
        raise RuntimeError("APNs 503")
    monkeypatch.setattr(push, "VERSAND", netzfehler)
    _planen(client, s, s["nils_id"], [WOCHE[0]])
    assert asyncio.run(push.ausgang_abarbeiten()) == 0
    a = _ausgang()[0]
    assert a["status"] == "offen" and a["versuche"] == 1 and "503" in a["fehler"] and a["naechster_versuch_at"] > a["created_at"]

    async def abgemeldet(*_):
        raise push.GeraetAbgemeldet("Unregistered")
    monkeypatch.setattr(push, "VERSAND", abgemeldet)
    _planen(client, s, s["nils_id"], [WOCHE[1]])
    asyncio.run(push.ausgang_abarbeiten())
    assert _ausgang()[-1]["status"] == "fehlgeschlagen"
    assert client.get("/api/geraete", headers=s["nils"]).json()["geraete"][0]["aktiv"] is False


def test_06_texte():
    assert push.uhrzeit("07:00") == "7" and push.uhrzeit("06:30") == "6:30"
    assert push.tage_text(["2026-12-02"]) == "Mi 02.12."
    assert push.tage_text(["2026-11-30", "2026-12-01", "2026-12-02"]) == "Mo–Mi 30.11.–02.12."
    assert push.tage_text(["2026-11-30", "2026-12-02"]) == "Mo 30.11., Mi 02.12."
    assert push.tage_text(["2026-11-30", "2026-12-02", "2026-12-04", "2026-12-08", "2026-12-10"]) == "Mo 30.11., Mi 02.12., Fr 04.12. + 2"
    e = [{"date": "2026-12-02", "start_time": "07:00", "end_time": "16:00"}]
    assert push.einteilungs_text("neu", "Badsanierung Müller", "Hauptstraße 5, 30159 Hannover", e) == ("📅 Neue Einteilung", "Badsanierung Müller, Hauptstraße 5, Mi 02.12. 7–16 Uhr")


def test_06b_ohne_details(monkeypatch):
    monkeypatch.setenv("PUSH_OHNE_DETAILS", "1")
    assert push.einteilungs_text("neu", "Badsanierung Müller", "Hauptstraße 5", [{"date": "2026-12-02", "start_time": "07:00", "end_time": "16:00"}]) == ("Neue Einteilung", "In der App ansehen.")


def test_07_apns_anfrage_mit_wegwerfschluessel(monkeypatch):
    schluessel = ec.generate_private_key(ec.SECP256R1())
    pem = schluessel.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
    monkeypatch.setenv("APNS_TEAM_ID", "TEAM123456")
    monkeypatch.setenv("APNS_KEY_ID", "KEY1234567")
    monkeypatch.setenv("APNS_SCHLUESSEL", pem)
    monkeypatch.setenv("APNS_BUNDLE_ID", "de.stundenzettelpro.app")
    monkeypatch.delenv("PUSH_MODUS", raising=False)
    push._apns_jwt.clear()
    assert push.eingerichtet("ios")
    anfragen = []

    def antwort(request: httpx.Request) -> httpx.Response:
        anfragen.append(request)
        if request.url.host == "api.push.apple.com":
            return httpx.Response(400, json={"reason": "BadDeviceToken"})   # Xcode-Build → Entwicklungsumgebung
        return httpx.Response(200)
    asyncio.run(push.apns_senden(IOS_TOKEN, "📅 Neue Einteilung", "Badsanierung Müller", "/einsaetze?einsatz=e1", transport=httpx.MockTransport(antwort)))
    assert [r.url.host for r in anfragen] == ["api.push.apple.com", "api.sandbox.push.apple.com"]
    r = anfragen[-1]
    assert r.url.path == f"/3/device/{IOS_TOKEN}" and r.headers["apns-topic"] == "de.stundenzettelpro.app" and r.headers["apns-push-type"] == "alert"
    token = r.headers["authorization"].split(" ", 1)[1]
    assert jwt.get_unverified_header(token) == {"alg": "ES256", "kid": "KEY1234567", "typ": "JWT"}
    assert jwt.decode(token, schluessel.public_key(), algorithms=["ES256"])["iss"] == "TEAM123456"
    koerper = json.loads(r.content)
    assert koerper["aps"]["alert"] == {"title": "📅 Neue Einteilung", "body": "Badsanierung Müller"} and koerper["link"] == "/einsaetze?einsatz=e1"
    with pytest.raises(push.GeraetAbgemeldet):
        asyncio.run(push.apns_senden(IOS_TOKEN, "t", "x", "/", transport=httpx.MockTransport(lambda req: httpx.Response(410, json={"reason": "Unregistered"}))))
    with pytest.raises(RuntimeError):
        asyncio.run(push.apns_senden(IOS_TOKEN, "t", "x", "/", transport=httpx.MockTransport(lambda req: httpx.Response(429, json={"reason": "TooManyRequests"}))))


def test_08_fcm_anfrage_mit_wegwerf_dienstkonto(monkeypatch):
    schluessel = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = schluessel.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
    monkeypatch.setenv("FCM_DIENSTKONTO", json.dumps({"project_id": "stundenzettel-test", "client_email": "push@stundenzettel-test.iam.gserviceaccount.com",
                                                      "private_key": pem, "token_uri": "https://oauth2.googleapis.com/token"}))
    monkeypatch.delenv("PUSH_MODUS", raising=False)
    push._fcm_zugang.clear()
    assert push.eingerichtet("android")
    anfragen = []

    def antwort(request: httpx.Request) -> httpx.Response:
        anfragen.append(request)
        if request.url.host == "oauth2.googleapis.com":
            return httpx.Response(200, json={"access_token": "zugang-123", "expires_in": 3600})
        return httpx.Response(200, json={"name": "projects/stundenzettel-test/messages/1"})
    asyncio.run(push.fcm_senden(ANDROID_TOKEN, "📅 Neue Einteilung", "Badsanierung Müller", "/einsaetze?einsatz=e1", transport=httpx.MockTransport(antwort)))
    anmeldung, nachricht = anfragen
    nachweis = dict(x.split("=", 1) for x in anmeldung.content.decode().split("&"))["assertion"]
    daten = jwt.decode(nachweis, schluessel.public_key(), algorithms=["RS256"], audience="https://oauth2.googleapis.com/token")
    assert daten["iss"] == "push@stundenzettel-test.iam.gserviceaccount.com" and daten["scope"].endswith("firebase.messaging")
    assert nachricht.url.path == "/v1/projects/stundenzettel-test/messages:send" and nachricht.headers["authorization"] == "Bearer zugang-123"
    m = json.loads(nachricht.content)["message"]
    assert m["token"] == ANDROID_TOKEN and m["notification"]["title"] == "📅 Neue Einteilung" and m["data"] == {"link": "/einsaetze?einsatz=e1"}
    # Zugang wird wiederverwendet; abgemeldetes Gerät erkannt
    with pytest.raises(push.GeraetAbgemeldet):
        asyncio.run(push.fcm_senden(ANDROID_TOKEN, "t", "x", "/", transport=httpx.MockTransport(lambda req: httpx.Response(404, json={"error": {"status": "NOT_FOUND"}}))))
