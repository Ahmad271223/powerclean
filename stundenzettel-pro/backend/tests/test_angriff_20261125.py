"""Angriffstests (25.11.2026) für die neuen Funktionen: Einteilung per Sprache, Push-Nachrichten, einzelner Einsatz mit Lesebestätigung.

Die hier gefundenen Fehler (u. a. Push nach Gerätewechsel an fremde Firma, Rückgängig nach Übergabe, Speichern ohne Änderung, 29. Februar,
„heute und morgen“, „bis Freitag“, Namen mit Bindestrich/Ş/Ç, „um 8 Uhr“, „bis 14 Uhr“, andere Hausnummer) sind behoben –
alle Tests sind jetzt Regressionstests."""
import asyncio
import json
import re
from datetime import date, datetime, timedelta, timezone

import httpx
import pytest

import push
import sprachplanung as sp
from conftest import einladen, projekt, registrieren
from zeiten import lokal_jetzt, zeit_pruefen

HEUTE = lokal_jetzt().date()
MORGEN = (HEUTE + timedelta(days=1)).isoformat()
GESTERN = (HEUTE - timedelta(days=1)).isoformat()
TAG = (HEUTE + timedelta(days=5)).isoformat()
TAG2 = (HEUTE + timedelta(days=6)).isoformat()
TOKEN = "d" * 64

MI = date(2026, 11, 25)   # Mittwoch
FR = date(2026, 11, 27)   # Freitag
SA = date(2026, 11, 28)
SO = date(2026, 11, 29)
NAECHSTE_WOCHE = [(date(2026, 11, 30) + timedelta(days=i)).isoformat() for i in range(5)]


# ================================================================ Hilfen

def _db():
    import db as dbmodul
    return dbmodul.db()


def _lesen(sammlung, filt=None):
    async def lesen():
        return [x async for x in getattr(_db(), sammlung).find(filt or {}, {"_id": 0}).sort("created_at", 1)]
    return asyncio.run(lesen())


def _ausgang():
    return _lesen("push_ausgang")


@pytest.fixture()
def testmodus(monkeypatch):
    monkeypatch.setenv("PUSH_MODUS", "test")
    monkeypatch.delenv("PUSH_OHNE_DETAILS", raising=False)
    monkeypatch.setattr(push, "SOFORT_ZUSTELLEN", False)
    push.TEST_GESENDET.clear()
    yield
    push.TEST_GESENDET.clear()


def _firma_a(client, monkeypatch=None, sprache=True):
    if monkeypatch is not None:
        monkeypatch.setenv("FEATURE_SPRACHPLANUNG", "1" if sprache else "0")
    chef, _ = registrieren(client, email="chef@angriff-a.de", firma="Angriff A GmbH", name="Karl Chef")
    nils, nd = einladen(client, chef, name="Nils Becker", email="nils@angriff-a.de")
    tom, td = einladen(client, chef, name="Tom Wagner", email="tom@angriff-a.de", passwort="geheim4567")
    bea, bd = einladen(client, chef, name="Bea Büro", email="bea@angriff-a.de", role="buero", passwort="buero12345")
    m = projekt(client, chef, name="Badsanierung Müller", address="Hauptstraße 5, 30159 Hannover")
    s = projekt(client, chef, name="Dachsanierung Schmidt", address="Lindenweg 12, 30655 Hannover")
    return {"chef": chef, "nils": nils, "nils_id": nd["user"]["id"], "tom": tom, "tom_id": td["user"]["id"], "bea": bea, "bea_id": bd["user"]["id"],
            "m": m, "s": s}


def _firma_b(client):
    chef, _ = registrieren(client, email="chef@angriff-b.de", firma="Angriff B GmbH", name="Bernd Boss")
    zoe, zd = einladen(client, chef, name="Zoe Fremd", email="zoe@angriff-b.de", passwort="geheim1111")
    p = projekt(client, chef, name="Fremdprojekt Zander", address="Bahnhofstraße 1, 10115 Berlin")
    return {"chef": chef, "zoe": zoe, "zoe_id": zd["user"]["id"], "p": p}


def _planen(client, kopf, project_id, user_ids, tage, start="07:00", ende="16:00", status=200):
    r = client.post("/api/einsatzplan", json={"project_id": project_id, "user_ids": user_ids, "dates": tage, "start_time": start, "end_time": ende}, headers=kopf)
    assert r.status_code == status, r.text
    return r.json().get("einsaetze")


def _vorschlag(client, kopf, **body):
    r = client.post("/api/sprachplanung/vorschlag", json=body, headers=kopf)
    assert r.status_code == 200, r.text
    return r.json()["vorschlag"]


# ================================================================ A. Datum ausrechnen (tage_berechnen)

@pytest.mark.parametrize("zeitraum, heute, erwartet", [
    ("31.12.", MI, ["2026-12-31"]),
    ("am 1.1.", date(2026, 12, 30), ["2027-01-01"]),                                     # über den Jahreswechsel
    ("28.12. bis 3.1.", MI, ["2026-12-28", "2026-12-29", "2026-12-30", "2026-12-31", "2027-01-01"]),   # Wochenende raus
    ("29.02.", MI, ["2028-02-29"]),                                                       # 2027 kein Schaltjahr → nächster 29.2. (2028)
    ("31.04.", MI, []),
    ("99.99.", MI, []),
    ("die ganze Woche", SA, NAECHSTE_WOCHE),
    ("die ganze Woche", SO, NAECHSTE_WOCHE),
    ("nächsten Montag", MI, ["2026-11-30"]),
    ("ab Mittwoch", date(2026, 11, 24), ["2026-11-25", "2026-11-26", "2026-11-27"]),
    ("KW 50", MI, ["2026-12-07", "2026-12-08", "2026-12-09", "2026-12-10", "2026-12-11"]),
    ("KW 47", MI, ["2027-11-22", "2027-11-23", "2027-11-24", "2027-11-25", "2027-11-26"]),      # schon vorbei → nächstes Jahr
    ("KW 54", MI, []),
    ("irgendwann bald", MI, []),
    ("ab Montag 99999999999999999999 Tage", MI, None),                                    # gedeckelt, kein Absturz
])
def test_a01_tage_haelt(zeitraum, heute, erwartet):
    tage, _ = sp.tage_berechnen(zeitraum, heute)
    if erwartet is None:
        assert len(tage) == 60
    else:
        assert tage == erwartet


def test_a02_29_februar_nach_schalttag_stuerzt_nicht_ab():
    tage, _ = sp.tage_berechnen("am 29.2.", date(2028, 3, 1))
    assert all(t > "2028-03-01" for t in tage)   # leer (Rückfrage) oder nächster 29.2. – nur kein Absturz


def test_a02b_29_februar_im_vorjahr():
    assert sp.tage_berechnen("am 29.2.", date(2027, 12, 1))[0] == ["2028-02-29"]


def test_a03_heute_und_morgen():
    assert sp.tage_berechnen("heute und morgen", MI)[0] == ["2026-11-25", "2026-11-26"]


def test_a04_morgen_und_uebermorgen():
    assert sp.tage_berechnen("morgen und übermorgen", MI)[0] == ["2026-11-26", "2026-11-27"]


def test_a05_diese_woche_am_freitag_ist_nicht_naechste_woche():
    tage, _ = sp.tage_berechnen("diese Woche", FR)
    assert tage and all(t <= "2026-11-29" for t in tage)


def test_a06_bis_freitag_ist_ein_zeitraum():
    tage, _ = sp.tage_berechnen("bis Freitag", MI)
    assert tage[-1] == "2026-11-27" and "2026-11-26" in tage


def test_a07_ab_montag_zwei_wochen():
    tage, hinweise = sp.tage_berechnen("ab Montag zwei Wochen", MI)
    assert len(tage) == 10 or hinweise


# ================================================================ B. Uhrzeiten

@pytest.mark.parametrize("roh, erwartet", [("19 Uhr", "19:00"), ("7:30", "07:30"), ("16 Uhr 30", "16:30"), ("halb eins", "00:30"), ("24", "00:00"),
                                           ("25:00", None), ("7:61", None), ("-1", None), ("garbage", None), ("🕖", None), (None, None),
                                           ("99999999999999999999", None)])
def test_b01_uhrzeit_haelt(roh, erwartet):
    assert sp.uhrzeit(roh) == erwartet


def test_b02_nachtschicht_und_nachmittag_halten():
    assert sp.zeiten_ordnen("19:00", "06:00") == ("19:00", "06:00")
    assert sp.zeiten_ordnen("07:30", "05:00") == ("07:30", "17:00")
    f = sp.regeln_zerlegen("Tom morgen 19 Uhr bis 6 Uhr bei Müller", ["Tom Wagner"], [])
    assert (f["startzeit"], f["endzeit"]) == ("19:00", "06:00")
    f = sp.regeln_zerlegen("Tom morgen halb acht bis fünf bei Müller", ["Tom Wagner"], [])
    assert (f["startzeit"], f["endzeit"]) == ("07:30", "17:00")


@pytest.mark.parametrize("start, ende", [("13:00", "12:00"), ("14:00", "12:30"), ("12:00", "12:00")])
def test_b03_zeiten_ordnen_liefert_gueltige_uhrzeit(start, ende):
    """Früher wurde „13 bis 12“ zu „24:00“ (ungültig) – Regressionstest."""
    _, e = sp.zeiten_ordnen(start, ende)
    zeit_pruefen(e)


def test_b04_ende_vor_beginn_ist_gueltige_nachtschicht_mit_hinweis(client, monkeypatch):
    """Früher „24:00“ im Entwurf (POST scheiterte mit 422); jetzt bleibt 14–12 als Nachtschicht, markiert und mit Hinweis."""
    s = _firma_a(client, monkeypatch)
    v = _vorschlag(client, s["chef"], text="Tom Wagner morgen von 14 bis 12 Uhr bei Müller")
    assert re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", v["end_time"]) and (v["start_time"], v["end_time"]) == ("14:00", "12:00")
    assert {"startzeit", "endzeit"} <= set(v["unsicher"]) and any("Nachtschicht" in h for h in v["hinweise"])
    if v["entwurf"]:
        assert client.post("/api/einsatzplan", json=v["entwurf"], headers=s["chef"]).status_code == 200


# ================================================================ C. Zerlegen mit festen Regeln

NAMEN = ["Karl Chef", "Nils Becker", "Tom Wagner", "Hans-Peter Krause", "Emre Şahin", "Ali Çelik", "Tom Döring", "Karl Schmidt", "Jürgen Kahl"]
PROJEKTE = [{"name": "Badsanierung Müller"}, {"name": "Dachsanierung Schmidt"}]


def test_c01_regeln_halten():
    f = sp.regeln_zerlegen("Nils Becker, Tom Wagner und Karl Chef morgen bei Müller", NAMEN, PROJEKTE)
    assert f["mitarbeiter"] == ["Nils Becker", "Tom Wagner", "Karl Chef"] and f["projekt"] == "Müller"
    f = sp.regeln_zerlegen("JÜRGEN KAHL morgen bei Müller", NAMEN, PROJEKTE)        # Großschreibung + Umlaut
    assert f["mitarbeiter"] == ["JÜRGEN KAHL"]
    f = sp.regeln_zerlegen("Juergen morgen bei Müller", NAMEN, PROJEKTE)            # Umlaut ausgeschrieben
    assert f["mitarbeiter"] == ["Juergen"]
    # Nachname ist zugleich Projektwort, aber „bei“ nennt das Projekt → Name bleibt erhalten
    f = sp.regeln_zerlegen("Karl Schmidt morgen bei Müller", NAMEN, PROJEKTE)
    assert f["mitarbeiter"] == ["Karl Schmidt"] and f["projekt"] == "Müller"
    # Ende vor Beginn ohne Nachmittag bleibt Nachtschicht
    f = sp.regeln_zerlegen("Tom Wagner morgen ab 7 Uhr bei Müller", NAMEN, PROJEKTE)
    assert (f["startzeit"], f["endzeit"]) == ("07:00", None)


@pytest.mark.parametrize("satz", ["", "   ", "🔨🔨💥", "<script>alert(1)</script>", '{"$ne": null}', "'; DROP TABLE users; --", "‮etuoR‬", "\x00\x01",
                                  "a" * 1000, "Ü" * 1000, "99.99.9999 25:61 bis 99:99", "von bis ab am um"])
def test_c02_regeln_mit_muell_stuerzen_nicht_ab(satz):
    f = sp.regeln_zerlegen(satz, NAMEN, PROJEKTE)
    assert f["mitarbeiter"] == [] and set(f["unsicher"]) >= {"mitarbeiter"}


def test_c03_bindestrich_vorname():
    assert sp.regeln_zerlegen("Hans-Peter morgen bei Müller", NAMEN, PROJEKTE)["mitarbeiter"] == ["Hans-Peter"]


@pytest.mark.parametrize("satz, name", [("Şahin morgen bei Müller", "Şahin"), ("Çelik morgen bei Müller", "Çelik")])
def test_c04_namen_mit_sonderbuchstaben(satz, name):
    assert sp.regeln_zerlegen(satz, NAMEN, PROJEKTE)["mitarbeiter"] == [name]


@pytest.mark.parametrize("satz, mitarbeiter", [("Tom Döring morgen bei Müller", ["Tom Döring"]), ("Nils Becker ist morgen unterwegs bei Müller", ["Nils Becker"])])
def test_c05_kein_falscher_standort(satz, mitarbeiter):
    f = sp.regeln_zerlegen(satz, NAMEN, PROJEKTE)
    assert f["standort"] is None and f["mitarbeiter"] == mitarbeiter


def test_c06_nachname_gleich_projektwort():
    f = sp.regeln_zerlegen("Karl Schmidt morgen Badsanierung Müller", NAMEN, PROJEKTE)
    assert f["mitarbeiter"] == ["Karl Schmidt"] and f["projekt"] == "Badsanierung Müller"


def test_c07_projekt_frisst_namen():
    f = sp.regeln_zerlegen("Projekt Müller Tom Wagner morgen", NAMEN, PROJEKTE)
    assert f["mitarbeiter"] == ["Tom Wagner"] and f["projekt"] == "Müller"


def test_c08_nur_ende_genannt():
    assert sp.regeln_zerlegen("Nils Becker morgen bis 14 Uhr bei Müller", NAMEN, PROJEKTE)["endzeit"] == "14:00"


def test_c09_um_acht_uhr():
    assert sp.regeln_zerlegen("Nils Becker morgen um 8 Uhr bei Müller", NAMEN, PROJEKTE)["startzeit"] == "08:00"


def test_c10_vertippter_name_im_satz():
    assert sp.regeln_zerlegen("Jurgen morgen bei Müller", NAMEN, PROJEKTE)["mitarbeiter"] == ["Jurgen"]


# ================================================================ D. Zuordnen

NUTZER = [{"id": "k", "name": "Karl Chef"}, {"id": "nb1", "name": "Nils Becker"}, {"id": "nb2", "name": "Nils Becker"},
          {"id": "jk", "name": "Jürgen Kahl"}, {"id": "leer", "name": ""}, {"id": "none", "name": None}]
PROJ = [{"id": "m", "name": "Badsanierung Müller", "address": "Hauptstraße 5, 30159 Hannover", "customer_name": "Familie Müller"},
        {"id": "s", "name": "Dachsanierung Schmidt", "address": "Lindenweg 12, 30655 Hannover", "customer_name": ""}]


def test_d01_zuordnen_haelt():
    assert {u["id"] for u in sp.mitarbeiter_finden("Nils Becker", NUTZER)} == {"nb1", "nb2"}      # gleicher Name zweimal → Rückfrage
    assert [u["id"] for u in sp.mitarbeiter_finden("jürgen", NUTZER)] == ["jk"]
    assert [u["id"] for u in sp.mitarbeiter_finden("JUERGEN KAHL", NUTZER)] == ["jk"]
    assert [u["id"] for u in sp.mitarbeiter_finden("Jurgen Kahl", NUTZER)] == ["jk"]
    assert sp.mitarbeiter_finden("", NUTZER) == [] and sp.mitarbeiter_finden("🔨", NUTZER) == []
    assert sp.projekt_finden("Bad", None, PROJ) == []                                            # zu kurz für Teilwort
    assert sp.projekt_finden("die Baustelle", None, PROJ) == []
    assert [p["id"] for p in sp.projekt_finden(None, "Hauptstr.", PROJ)] == ["m"]


# ================================================================ E. Route /api/sprachplanung

def test_e01_flag_aus_sperrt_alle_routen(client, monkeypatch):
    s = _firma_a(client, monkeypatch, sprache=False)
    assert client.get("/api/sprachplanung/status", headers=s["chef"]).status_code == 404
    assert client.post("/api/sprachplanung/vorschlag", json={"text": "Tom morgen"}, headers=s["chef"]).status_code == 404
    assert client.post("/api/sprachplanung/pruefen", json={"user_ids": [], "dates": [], "start_time": "07:00", "end_time": "16:00"},
                       headers=s["chef"]).status_code == 404
    monkeypatch.setenv("FEATURE_SPRACHPLANUNG", "nein")
    assert client.post("/api/sprachplanung/vorschlag", json={"text": "Tom morgen"}, headers=s["chef"]).status_code == 404


def test_e02_rechte(client, monkeypatch):
    s = _firma_a(client, monkeypatch)
    body = {"text": "Tom Wagner morgen bei Müller"}
    assert client.post("/api/sprachplanung/vorschlag", json=body).status_code == 401
    for kopf in (s["nils"], s["tom"]):
        assert client.post("/api/sprachplanung/vorschlag", json=body, headers=kopf).status_code == 403
        assert client.get("/api/sprachplanung/status", headers=kopf).status_code == 403
    assert client.post("/api/sprachplanung/vorschlag", json=body, headers=s["bea"]).status_code == 200      # Büro hat plantafel standardmäßig
    assert client.put(f"/api/mitarbeiter/{s['bea_id']}", json={"rechte": {"plantafel": False}}, headers=s["chef"]).status_code == 200
    assert client.post("/api/sprachplanung/vorschlag", json=body, headers=s["bea"]).status_code == 403
    assert client.post("/api/sprachplanung/pruefen", json={"user_ids": [], "dates": [], "start_time": "07:00", "end_time": "16:00"},
                       headers=s["bea"]).status_code == 403


@pytest.mark.parametrize("body", [{"text": "x" * 1001}, {"text": "Tom", "quelle": "openai"}, {"felder": {"mitarbeiter": ["a"] * 21}},
                                  {"felder": {"zeitraum": "x" * 301}}, {"felder": {"projekt": "x" * 201}}, {"felder": {"startzeit": "x" * 21}},
                                  {"felder": {"unsicher": ["projekt"] * 11}}, {"felder": {"mitarbeiter": "Tom"}}])
def test_e03_grenzen(client, monkeypatch, body):
    s = _firma_a(client, monkeypatch)
    assert client.post("/api/sprachplanung/vorschlag", json=body, headers=s["chef"]).status_code == 422


@pytest.mark.parametrize("text", ["🔨🔨💥", "<script>alert(1)</script>", '{"$ne": null}', "'; DROP TABLE users; --", "‮etuoR", "\x00",
                                  "a" * 1000, "Ü" * 1000, "99.99.9999 25:61 bis 99:99 Uhr", "am 31.02. von 25 bis 26 Uhr"])
def test_e04_muell_ergibt_rueckfragen_statt_absturz(client, monkeypatch, text):
    s = _firma_a(client, monkeypatch)
    v = _vorschlag(client, s["chef"], text=text)
    assert v["entwurf"] is None and v["rueckfragen"]


def test_e05_fremde_firma_wird_nicht_zugeordnet(client, monkeypatch):
    s = _firma_a(client, monkeypatch)
    b = _firma_b(client)
    v = _vorschlag(client, s["chef"], text="Zoe Fremd morgen bei Zander")
    assert v["entwurf"] is None and v["projekt"] is None
    ids = {o["id"] for r in v["rueckfragen"] for o in r["optionen"]}
    assert b["zoe_id"] not in ids and b["p"]["id"] not in ids and s["nils_id"] in ids
    # Felder vom Gerät mit fremden Namen/Projekten ebenso
    v = _vorschlag(client, s["chef"], felder={"mitarbeiter": ["Zoe Fremd"], "projekt": "Fremdprojekt Zander", "zeitraum": "morgen"}, quelle="apple")
    assert v["entwurf"] is None and b["zoe_id"] not in json.dumps(v) and b["p"]["id"] not in json.dumps(v)
    # Prüfen mit fremden Personen → 400; Firma B sieht mit Flag die Personen von A nicht
    assert client.post("/api/sprachplanung/pruefen", json={"user_ids": [b["zoe_id"]], "dates": [TAG], "start_time": "07:00", "end_time": "16:00"},
                       headers=s["chef"]).status_code == 400
    v = _vorschlag(client, b["chef"], text="Nils Becker morgen bei Müller")
    assert v["entwurf"] is None and s["nils_id"] not in json.dumps(v) and s["m"]["id"] not in json.dumps(v)


def test_e06_inaktive_und_archivierte_werden_nicht_zugeordnet(client, monkeypatch):
    s = _firma_a(client, monkeypatch)
    assert client.put(f"/api/mitarbeiter/{s['tom_id']}", json={"active": False}, headers=s["chef"]).status_code == 200
    asyncio.run(_db().projects.update_one({"id": s["m"]["id"]}, {"$set": {"archived": True}}))
    v = _vorschlag(client, s["chef"], text="Tom Wagner morgen bei Müller")
    assert v["entwurf"] is None and s["tom_id"] not in json.dumps(v) and s["m"]["id"] not in json.dumps(v)


def test_e07_pruefen_grenzen(client, monkeypatch):
    s = _firma_a(client, monkeypatch)
    url = "/api/sprachplanung/pruefen"
    basis = {"user_ids": [s["nils_id"]], "dates": [TAG], "start_time": "07:00", "end_time": "16:00"}
    assert client.post(url, json={**basis, "dates": ["2026-02-30"]}, headers=s["chef"]).status_code == 400
    assert client.post(url, json={**basis, "dates": ["morgen"]}, headers=s["chef"]).status_code == 400
    assert client.post(url, json={**basis, "dates": ["1999-01-01"]}, headers=s["chef"]).status_code == 400
    assert client.post(url, json={**basis, "dates": [TAG] * 61}, headers=s["chef"]).status_code == 422
    assert client.post(url, json={**basis, "start_time": "07:00:00"}, headers=s["chef"]).status_code == 422
    assert client.post(url, json={**basis, "end_time": "25"}, headers=s["chef"]).status_code == 422
    r = client.post(url, json={**basis, "user_ids": [s["nils_id"], s["nils_id"]], "dates": [TAG, TAG]}, headers=s["chef"])
    assert r.status_code == 200


def test_e08_feiertag_und_wochenende_im_vorschlag(client, monkeypatch):
    s = _firma_a(client, monkeypatch)
    v = _vorschlag(client, s["chef"], text="Tom Wagner am 25.12. bei Müller")
    assert [k["art"] for k in v["konflikte"]] == ["feiertag"] and "Weihnacht" in v["konflikte"][0]["text"]
    v = _vorschlag(client, s["chef"], text="Tom Wagner am Samstag bei Müller")
    assert [k["art"] for k in v["konflikte"]] == ["wochenende"]


def test_e09_protokoll_ohne_gesprochenen_text(client, monkeypatch):
    s = _firma_a(client, monkeypatch)
    _vorschlag(client, s["chef"], text="Tom Wagner morgen bei Müller GEHEIM-SATZ-4711 Lindenweg 12")
    _vorschlag(client, s["chef"], felder={"mitarbeiter": ["GEHEIM-FELD-0815"], "projekt": "GEHEIM-PROJEKT", "zeitraum": "morgen"}, quelle="apple")
    eintraege = _lesen("protokoll", {"aktion": "sprachplanung.vorschlag"})
    roh = json.dumps(eintraege, ensure_ascii=False)
    assert len(eintraege) == 2 and "GEHEIM" not in roh and "Lindenweg" not in roh and eintraege[1]["details"]["quelle"] == "apple"


def test_e10_mistral_muell_faellt_auf_regeln_zurueck(client, monkeypatch):
    s = _firma_a(client, monkeypatch)
    monkeypatch.setenv("FEATURE_KI", "1")
    monkeypatch.setenv("MISTRAL_API_KEY", "test-schluessel")
    echt = sp.mistral_zerlegen
    antworten = iter([
        httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({"unsicher": 5, "mitarbeiter": 7})}}]}),   # falsche Typen
        httpx.Response(200, json={"choices": []}),
        httpx.Response(200, text="<html>Bad Gateway</html>"),
        httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(["Liste", "statt", "Objekt"])}}]}),
    ])

    async def ersatz(text, transport=None):
        return await echt(text, transport=httpx.MockTransport(lambda req: next(antworten)))
    monkeypatch.setattr(sp, "mistral_zerlegen", ersatz)
    for _ in range(3):
        v = _vorschlag(client, s["chef"], text="Tom Wagner morgen bei Müller")
        assert v["quelle"] == "regeln" and "nicht erreichbar" in v["hinweise"][0] and v["entwurf"]["user_ids"] == [s["tom_id"]]
    v = _vorschlag(client, s["chef"], text="Tom Wagner morgen bei Müller")       # Liste → leere Felder, Rückfragen statt Absturz
    assert v["quelle"] == "mistral" and v["entwurf"] is None


def test_e11_keine_doppelten_personen_im_entwurf(client, monkeypatch):
    s = _firma_a(client, monkeypatch)
    _planen(client, s["chef"], s["s"]["id"], [s["tom_id"]], [MORGEN], "08:00", "10:00")
    v = _vorschlag(client, s["chef"], felder={"mitarbeiter": ["Tom", "Tom Wagner"], "projekt": "Müller", "zeitraum": "morgen"}, quelle="apple")
    assert v["entwurf"]["user_ids"] == [s["tom_id"]]
    assert len([k for k in v["konflikte"] if k["art"] == "ueberschneidung"]) == 1


def test_e12_andere_hausnummer_wird_nicht_verschluckt(client, monkeypatch):
    s = _firma_a(client, monkeypatch)
    v = _vorschlag(client, s["chef"], text="Tom Wagner morgen bei Müller, Hauptstraße 7")
    assert v["adresse"].startswith("Hauptstraße 7") or "standort" in v["unsicher"]


def test_e13_vorschlag_speichert_nichts(client, monkeypatch):
    s = _firma_a(client, monkeypatch)
    vorher = len(_lesen("einsaetze"))
    for _ in range(3):
        _vorschlag(client, s["chef"], text="Tom Wagner morgen von 7 bis 16 Uhr bei Müller")
    assert len(_lesen("einsaetze")) == vorher and _lesen("push_ausgang") == []


# ================================================================ F. Einzelner Einsatz und Lesebestätigung

def _einsatz(client, s, tag=TAG):
    return _planen(client, s["chef"], s["m"]["id"], [s["nils_id"]], [tag])[0]


def test_f01_fremde_firma_404_ueberall(client):
    s = _firma_a(client)
    b = _firma_b(client)
    eid = _einsatz(client, s)["id"]
    for kopf in (b["chef"], b["zoe"]):
        assert client.get(f"/api/einsatzplan/{eid}", headers=kopf).status_code == 404
        assert client.post(f"/api/einsatzplan/{eid}/gelesen", headers=kopf).status_code == 404
        assert client.post(f"/api/einsatzplan/{eid}/bestaetigen", headers=kopf).status_code == 404
    assert client.put(f"/api/einsatzplan/{eid}", json={"start_time": "08:00"}, headers=b["chef"]).status_code == 404
    assert client.delete(f"/api/einsatzplan/{eid}", headers=b["chef"]).status_code == 404
    assert client.post(f"/api/einsatzplan/{eid}/kopieren", json={"dates": [TAG2]}, headers=b["chef"]).status_code == 404
    assert client.post(f"/api/einsatzplan/{eid}/rueckgaengig", headers=b["chef"]).status_code == 404
    # Firma A darf keine fremden Personen/Projekte einsetzen
    assert client.put(f"/api/einsatzplan/{eid}", json={"user_id": b["zoe_id"]}, headers=s["chef"]).status_code == 400
    assert client.put(f"/api/einsatzplan/{eid}", json={"project_id": b["p"]["id"]}, headers=s["chef"]).status_code == 404
    assert client.post(f"/api/einsatzplan/{eid}/kopieren", json={"user_ids": [b["zoe_id"]]}, headers=s["chef"]).status_code == 400
    assert client.get(f"/api/einsatzplan/{eid}", headers=s["nils"]).json()["einsatz"]["quittung"]["gelesen"] is False


def test_f02_rollen(client):
    s = _firma_a(client)
    eid = _einsatz(client, s)["id"]
    # Mitarbeiter: fremder Einsatz 404, eigener ohne Planerdaten, ändern verboten
    assert client.get(f"/api/einsatzplan/{eid}", headers=s["tom"]).status_code == 404
    eigen = client.get(f"/api/einsatzplan/{eid}", headers=s["nils"]).json()["einsatz"]
    assert not {"zustellung", "verlauf", "mitarbeiter", "user_id"} & set(eigen)
    assert client.put(f"/api/einsatzplan/{eid}", json={"start_time": "05:00"}, headers=s["nils"]).status_code == 403
    assert client.delete(f"/api/einsatzplan/{eid}", headers=s["nils"]).status_code == 403
    # Büro (Planer) darf nicht stellvertretend quittieren
    assert client.post(f"/api/einsatzplan/{eid}/bestaetigen", headers=s["bea"]).status_code == 403
    assert client.post(f"/api/einsatzplan/{eid}/gelesen", headers=s["bea"]).status_code == 403
    # Büro ohne Recht plantafel ist wie ein Mitarbeiter
    assert client.put(f"/api/mitarbeiter/{s['bea_id']}", json={"rechte": {"plantafel": False}}, headers=s["chef"]).status_code == 200
    assert client.get(f"/api/einsatzplan/{eid}", headers=s["bea"]).status_code == 404
    assert client.post(f"/api/einsatzplan/{eid}/bestaetigen", headers=s["bea"]).status_code == 404
    # deaktivierter Mitarbeiter kommt nicht mehr dran
    assert client.put(f"/api/mitarbeiter/{s['nils_id']}", json={"active": False}, headers=s["chef"]).status_code == 200
    assert client.post(f"/api/einsatzplan/{eid}/bestaetigen", headers=s["nils"]).status_code == 401
    assert _lesen("einsaetze", {"id": eid})[0].get("quittung") is None


def test_f03_quittung_je_version(client):
    s = _firma_a(client)
    eid = _einsatz(client, s)["id"]
    leer = {"gelesen": False, "bestaetigt": False, "gelesen_at": None, "bestaetigt_at": None}
    q1 = client.post(f"/api/einsatzplan/{eid}/bestaetigen", headers=s["nils"]).json()["einsatz"]["quittung"]
    assert q1["gelesen"] and q1["bestaetigt"]
    # Kopie auf einen anderen Tag ändert das Original nicht
    kopie = client.post(f"/api/einsatzplan/{eid}/kopieren", json={"dates": [TAG2]}, headers=s["chef"]).json()["einsaetze"][0]
    assert kopie["quittung"] == leer
    assert client.get(f"/api/einsatzplan/{eid}", headers=s["nils"]).json()["einsatz"]["quittung"]["bestaetigt"] is True
    # Absagen → offen; abgesagt nicht bestätigbar; Wiederherstellen → neue Version, wieder offen
    assert client.delete(f"/api/einsatzplan/{eid}", headers=s["chef"]).status_code == 200
    assert client.get(f"/api/einsatzplan/{eid}", headers=s["nils"]).json()["einsatz"]["quittung"] == leer
    assert client.post(f"/api/einsatzplan/{eid}/bestaetigen", headers=s["nils"]).status_code == 409
    assert client.post(f"/api/einsatzplan/{eid}/wiederherstellen", headers=s["chef"]).status_code == 200
    assert client.get(f"/api/einsatzplan/{eid}", headers=s["nils"]).json()["einsatz"]["quittung"] == leer
    q2 = client.post(f"/api/einsatzplan/{eid}/bestaetigen", headers=s["nils"]).json()["einsatz"]["quittung"]
    assert q2["bestaetigt"] and _lesen("einsaetze", {"id": eid})[0]["quittung"]["version"] == _lesen("einsaetze", {"id": eid})[0]["version"]
    # Rückgängig ist auch eine Planänderung
    assert client.put(f"/api/einsatzplan/{eid}", json={"start_time": "08:00"}, headers=s["chef"]).status_code == 200
    client.post(f"/api/einsatzplan/{eid}/bestaetigen", headers=s["nils"])
    assert client.post(f"/api/einsatzplan/{eid}/rueckgaengig", headers=s["chef"]).status_code == 200
    assert client.get(f"/api/einsatzplan/{eid}", headers=s["nils"]).json()["einsatz"]["quittung"] == leer
    # Übergabe an Tom: Nils sieht ihn nicht mehr, Tom muss selbst bestätigen
    assert client.put(f"/api/einsatzplan/{eid}", json={"user_id": s["tom_id"]}, headers=s["chef"]).status_code == 200
    assert client.get(f"/api/einsatzplan/{eid}", headers=s["nils"]).status_code == 404
    assert client.post(f"/api/einsatzplan/{eid}/bestaetigen", headers=s["nils"]).status_code == 404
    assert client.get(f"/api/einsatzplan/{eid}", headers=s["tom"]).json()["einsatz"]["quittung"] == leer


def test_f04_planer_quittiert_eigenen_einsatz(client):
    s = _firma_a(client)
    chef_id = client.get("/api/auth/ich", headers=s["chef"]).json()["user"]["id"]
    eid = _planen(client, s["chef"], s["m"]["id"], [chef_id], [TAG])[0]["id"]
    r = client.post(f"/api/einsatzplan/{eid}/bestaetigen", headers=s["chef"])
    assert r.status_code == 200 and r.json()["einsatz"]["quittung"]["bestaetigt"] is True and "verlauf" in r.json()["einsatz"]


def test_f05_speichern_ohne_aenderung(client, testmodus):
    s = _firma_a(client)
    eid = _einsatz(client, s)["id"]
    client.post(f"/api/einsatzplan/{eid}/bestaetigen", headers=s["nils"])
    vorher = len(_ausgang())
    assert client.put(f"/api/einsatzplan/{eid}", json={"start_time": "07:00", "end_time": "16:00"}, headers=s["chef"]).status_code == 200
    assert client.get(f"/api/einsatzplan/{eid}", headers=s["nils"]).json()["einsatz"]["quittung"]["bestaetigt"] is True
    assert len(_ausgang()) == vorher


# ================================================================ G. Push

def test_g01_geraet_registrieren_angriffe(client):
    s = _firma_a(client)
    url = "/api/geraete"
    for token in ("x" * 15, "x" * 4097, "a" * 20 + " " + "b" * 20, "a" * 20 + "<script>", "a" * 20 + "\n", "ä" * 20, "$ne" + "a" * 20):
        assert client.post(url, json={"plattform": "ios", "token": token}, headers=s["nils"]).status_code == 422
    assert client.post(url, json={"plattform": "IOS", "token": TOKEN}, headers=s["nils"]).status_code == 422
    assert client.post(url, json={"plattform": "ios", "token": TOKEN, "app_version": "v" * 41}, headers=s["nils"]).status_code == 422
    assert client.post(url, json={"plattform": "ios", "token": TOKEN}, headers=s["nils"]).status_code == 200
    # Token landet nie im Protokoll oder in der Liste
    assert TOKEN not in json.dumps(_lesen("protokoll")) and TOKEN not in json.dumps(client.get(url, headers=s["nils"]).json())
    # Fremder kann es nicht abmelden; zu kurzes Token beim Abmelden → 422
    assert client.post(f"{url}/abmelden", json={"token": TOKEN}, headers=s["tom"]).json()["ok"] is False
    assert client.post(f"{url}/abmelden", json={"token": "kurz"}, headers=s["nils"]).status_code == 422
    assert [g["aktiv"] for g in client.get(url, headers=s["nils"]).json()["geraete"]] == [True]
    # Abmelden und erneut anmelden → wieder aktiv, kein zweites Gerät
    assert client.post(f"{url}/abmelden", json={"token": TOKEN}, headers=s["nils"]).json()["ok"] is True
    assert client.post(url, json={"plattform": "ios", "token": TOKEN}, headers=s["nils"]).status_code == 200
    assert [g["aktiv"] for g in client.get(url, headers=s["nils"]).json()["geraete"]] == [True]
    assert len(_lesen("geraete")) == 1


def test_g02_token_wandert_in_andere_firma(client, testmodus):
    s = _firma_a(client)
    b = _firma_b(client)
    client.post("/api/geraete", json={"plattform": "ios", "token": TOKEN}, headers=s["nils"])
    client.post("/api/geraete", json={"plattform": "ios", "token": TOKEN}, headers=b["zoe"])
    assert client.get("/api/geraete", headers=s["nils"]).json()["geraete"] == []
    g = _lesen("geraete")
    assert len(g) == 1 and (g[0]["firma_id"], g[0]["user_id"]) == (_lesen("users", {"id": b["zoe_id"]})[0]["firma_id"], b["zoe_id"])
    # neue Einteilungen für Nils gehen nicht mehr an das Handy
    _einsatz(client, s)
    assert [a["status"] for a in _ausgang()] == ["kein_geraet"]
    asyncio.run(push.ausgang_abarbeiten())
    assert push.TEST_GESENDET == []


def test_g03_offene_nachricht_leckt_nach_geraetewechsel(client, testmodus):
    s = _firma_a(client)
    b = _firma_b(client)
    client.post("/api/geraete", json={"plattform": "ios", "token": TOKEN}, headers=s["nils"])
    _einsatz(client, s)
    assert [a["status"] for a in _ausgang()] == ["offen"]
    client.post("/api/geraete", json={"plattform": "ios", "token": TOKEN}, headers=b["zoe"])   # Handy wechselt den Besitzer
    asyncio.run(push.ausgang_abarbeiten())
    assert not [x for x in push.TEST_GESENDET if x["token"] == TOKEN]
    assert _ausgang()[0]["status"] != "zugestellt"


def test_g04_abmelden_stoppt_offene_nachricht(client, testmodus):
    s = _firma_a(client)
    client.post("/api/geraete", json={"plattform": "ios", "token": TOKEN}, headers=s["nils"])
    _einsatz(client, s)
    assert client.post("/api/geraete/abmelden", json={"token": TOKEN}, headers=s["nils"]).json()["ok"] is True
    assert asyncio.run(push.ausgang_abarbeiten()) == 0
    a = _ausgang()[0]
    assert push.TEST_GESENDET == [] and a["status"] == "fehlgeschlagen" and "abgemeldet" in a["fehler"]
    eid = a["einsatz_ids"][0]
    assert client.get(f"/api/einsatzplan/{eid}", headers=s["chef"]).json()["einsatz"]["zustellung"] == "fehlgeschlagen"


def test_g05_wiederholungen_dann_fehlgeschlagen(client, testmodus, monkeypatch):
    s = _firma_a(client)
    client.post("/api/geraete", json={"plattform": "android", "token": TOKEN}, headers=s["nils"])
    uhr = [datetime(2026, 11, 25, 8, 0, tzinfo=timezone.utc)]
    monkeypatch.setattr(push, "_jetzt", lambda: uhr[0])
    aufrufe = []

    async def kaputt(g, titel, text, link):
        aufrufe.append(g["token"])
        raise RuntimeError("FCM 503 UNAVAILABLE")
    monkeypatch.setattr(push, "VERSAND", kaputt)
    _einsatz(client, s)
    for i, minuten in enumerate(push.WIEDERHOLUNG_MINUTEN, start=1):
        asyncio.run(push.ausgang_abarbeiten())
        a = _ausgang()[0]
        assert (a["status"], a["versuche"]) == ("offen", i) and "503" in a["fehler"]
        assert datetime.fromisoformat(a["naechster_versuch_at"]) == uhr[0] + timedelta(minutes=minuten)
        assert asyncio.run(push.ausgang_abarbeiten()) == 0 and len(aufrufe) == i          # vor der Frist kein neuer Versuch
        uhr[0] = uhr[0] + timedelta(minutes=minuten, seconds=1)
    asyncio.run(push.ausgang_abarbeiten())
    a = _ausgang()[0]
    assert (a["status"], a["versuche"]) == ("fehlgeschlagen", push.MAX_VERSUCHE) and len(aufrufe) == push.MAX_VERSUCHE
    uhr[0] = uhr[0] + timedelta(days=1)
    asyncio.run(push.ausgang_abarbeiten())
    assert len(aufrufe) == push.MAX_VERSUCHE
    # Gerät bleibt aktiv (nur Netzfehler, nicht abgemeldet)
    assert client.get("/api/geraete", headers=s["nils"]).json()["geraete"][0]["aktiv"] is True


def test_g06_buendelung_je_person_und_projekt(client, testmodus):
    s = _firma_a(client)
    tage = [(HEUTE + timedelta(days=i)).isoformat() for i in (7, 8, 9)]
    _planen(client, s["chef"], s["m"]["id"], [s["nils_id"], s["tom_id"]], tage)
    assert sorted(a["user_id"] for a in _ausgang()) == sorted([s["nils_id"], s["tom_id"]])
    assert all(len(a["einsatz_ids"]) == 3 for a in _ausgang())
    # zwei Projekte in einem Aufruf → zwei Nachrichten für dieselbe Person
    roh = _lesen("einsaetze", {"user_id": s["nils_id"]})
    zweites = {**roh[0], "id": "x-1", "project_id": s["s"]["id"]}
    assert asyncio.run(push.einsaetze_melden(roh + [zweites], "neu")) == 2
    # Kopie auf mehrere Personen → je Person eine Nachricht
    vorher = len(_ausgang())
    r = client.post(f"/api/einsatzplan/{roh[0]['id']}/kopieren", json={"user_ids": [s["tom_id"], s["bea_id"]], "dates": [TAG, TAG2]}, headers=s["chef"])
    assert r.status_code == 200 and len(r.json()["einsaetze"]) == 4
    neu = _ausgang()[vorher:]
    assert sorted(a["user_id"] for a in neu) == sorted([s["tom_id"], s["bea_id"]]) and all(len(a["einsatz_ids"]) == 2 for a in neu)


def test_g07_vergangene_tage_werden_nicht_gemeldet(client, testmodus):
    s = _firma_a(client)
    client.post("/api/geraete", json={"plattform": "ios", "token": TOKEN}, headers=s["nils"])
    _planen(client, s["chef"], s["m"]["id"], [s["nils_id"]], [GESTERN, MORGEN])
    a = _ausgang()
    assert len(a) == 1 and len(a[0]["einsatz_ids"]) == 1
    asyncio.run(push.ausgang_abarbeiten())
    text = push.TEST_GESENDET[0]["text"]
    assert date.fromisoformat(MORGEN).strftime("%d.%m.") in text and date.fromisoformat(GESTERN).strftime("%d.%m.") not in text
    # nur Vergangenheit → gar keine Nachricht; Absagen eines vergangenen Einsatzes ebenso
    vorher = len(_ausgang())
    alt = _planen(client, s["chef"], s["s"]["id"], [s["nils_id"]], [(HEUTE - timedelta(days=3)).isoformat()])[0]
    assert client.delete(f"/api/einsatzplan/{alt['id']}", headers=s["chef"]).status_code == 200
    assert len(_ausgang()) == vorher


def test_g08_ohne_details_kein_projekt_keine_adresse(client, testmodus, monkeypatch):
    monkeypatch.setenv("PUSH_OHNE_DETAILS", "1")
    s = _firma_a(client)
    client.post("/api/geraete", json={"plattform": "ios", "token": TOKEN}, headers=s["nils"])
    e = _einsatz(client, s)
    client.put(f"/api/einsatzplan/{e['id']}", json={"address": "Geheimweg 9, 12345 Irgendwo"}, headers=s["chef"])
    client.delete(f"/api/einsatzplan/{e['id']}", headers=s["chef"])
    asyncio.run(push.ausgang_abarbeiten())
    assert len(push.TEST_GESENDET) == 3
    roh = json.dumps(push.TEST_GESENDET + _ausgang(), ensure_ascii=False)
    for verboten in ("Müller", "Badsanierung", "Hauptstraße", "Geheimweg", "Hannover", "Uhr", date.fromisoformat(TAG).strftime("%d.%m.")):
        assert verboten not in roh
    assert [x["titel"] for x in push.TEST_GESENDET] == ["Neue Einteilung", "Einteilung geändert", "Einteilung abgesagt"]


def test_g09_push_aus_nur_nachweis(client, testmodus, monkeypatch):
    monkeypatch.setenv("PUSH_MODUS", "aus")
    s = _firma_a(client)
    client.post("/api/geraete", json={"plattform": "ios", "token": TOKEN}, headers=s["nils"])
    eid = _einsatz(client, s)["id"]
    assert [a["status"] for a in _ausgang()] == ["aus"] and asyncio.run(push.ausgang_abarbeiten()) == 0 and push.TEST_GESENDET == []
    assert client.get(f"/api/einsatzplan/{eid}", headers=s["chef"]).json()["einsatz"]["zustellung"] == "aus"


def test_g10_rueckgaengig_nach_uebergabe_sagt_der_anderen_person_ab(client, testmodus):
    s = _firma_a(client)
    eid = _einsatz(client, s)["id"]
    assert client.put(f"/api/einsatzplan/{eid}", json={"user_id": s["tom_id"]}, headers=s["chef"]).status_code == 200
    vorher = len(_ausgang())
    assert client.post(f"/api/einsatzplan/{eid}/rueckgaengig", headers=s["chef"]).json()["einsatz"]["user_id"] == s["nils_id"]
    neu = [(a["user_id"], a["art"]) for a in _ausgang()[vorher:]]
    assert (s["tom_id"], "einsatz_abgesagt") in neu


def test_g11_rueckgaengig_nach_wiederherstellen_meldet_absage(client, testmodus):
    s = _firma_a(client)
    client.post("/api/geraete", json={"plattform": "ios", "token": TOKEN}, headers=s["nils"])
    eid = _einsatz(client, s)["id"]
    client.delete(f"/api/einsatzplan/{eid}", headers=s["chef"])
    client.post(f"/api/einsatzplan/{eid}/wiederherstellen", headers=s["chef"])
    r = client.post(f"/api/einsatzplan/{eid}/rueckgaengig", headers=s["chef"])
    assert r.status_code == 200 and r.json()["einsatz"]["status"] == "abgesagt"
    assert _ausgang()[-1]["art"] == "einsatz_abgesagt"


def test_g12_zustellstand_nur_aktuelle_version_und_planer(client, testmodus):
    s = _firma_a(client)
    client.post("/api/geraete", json={"plattform": "ios", "token": TOKEN}, headers=s["nils"])
    eid = _einsatz(client, s)["id"]
    asyncio.run(push.ausgang_abarbeiten())
    assert client.get(f"/api/einsatzplan/{eid}", headers=s["bea"]).json()["einsatz"]["zustellung"] == "zugestellt"
    client.put(f"/api/einsatzplan/{eid}", json={"end_time": "15:00"}, headers=s["chef"])
    assert client.get(f"/api/einsatzplan/{eid}", headers=s["chef"]).json()["einsatz"]["zustellung"] == "offen"
    assert "zustellung" not in client.get(f"/api/einsatzplan/{eid}", headers=s["nils"]).json()["einsatz"]
    # ohne Einsatz ohne Nachweis → None
    ohne = _planen(client, s["chef"], s["s"]["id"], [s["nils_id"]], [GESTERN])[0]
    assert client.get(f"/api/einsatzplan/{ohne['id']}", headers=s["chef"]).json()["einsatz"]["zustellung"] is None


def test_g13_apns_und_fcm_fehlerantworten(monkeypatch):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec, rsa
    pem = ec.generate_private_key(ec.SECP256R1()).private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                                                serialization.NoEncryption()).decode()
    monkeypatch.setenv("APNS_TEAM_ID", "TEAM123456")
    monkeypatch.setenv("APNS_KEY_ID", "KEY1234567")
    monkeypatch.setenv("APNS_SCHLUESSEL", pem)
    monkeypatch.delenv("APNS_UMGEBUNG", raising=False)
    push._apns_jwt.clear()
    hosts = []

    def nur(status, koerper=None, text=None):
        def antwort(req):
            hosts.append(req.url.host)
            return httpx.Response(status, json=koerper) if text is None else httpx.Response(status, text=text)
        return httpx.MockTransport(antwort)
    # 410 in Produktion → abgemeldet, ohne Umweg über die Entwicklungsumgebung
    with pytest.raises(push.GeraetAbgemeldet):
        asyncio.run(push.apns_senden(TOKEN, "t", "x", "/", transport=nur(410, {"reason": "Unregistered"})))
    assert hosts == ["api.push.apple.com"]
    # BadDeviceToken in beiden Umgebungen → abgemeldet
    hosts.clear()
    with pytest.raises(push.GeraetAbgemeldet):
        asyncio.run(push.apns_senden(TOKEN, "t", "x", "/", transport=nur(400, {"reason": "BadDeviceToken"})))
    assert hosts == ["api.push.apple.com", "api.sandbox.push.apple.com"]
    # HTML-Fehlerseite → RuntimeError (wird wiederholt), kein Absturz beim JSON-Lesen
    with pytest.raises(RuntimeError):
        asyncio.run(push.apns_senden(TOKEN, "t", "x", "/", transport=nur(502, text="<html>Bad Gateway</html>")))
    monkeypatch.setenv("APNS_UMGEBUNG", "entwicklung")
    hosts.clear()
    asyncio.run(push.apns_senden(TOKEN, "t", "x", "/", transport=nur(200, {})))
    assert hosts == ["api.sandbox.push.apple.com"]
    # FCM: Anmeldung scheitert → RuntimeError; HTML-Fehler → RuntimeError
    rpem = rsa.generate_private_key(public_exponent=65537, key_size=2048).private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                                                                        serialization.NoEncryption()).decode()
    monkeypatch.setenv("FCM_DIENSTKONTO", json.dumps({"project_id": "p", "client_email": "a@b.iam.gserviceaccount.com", "private_key": rpem}))
    push._fcm_zugang.clear()
    with pytest.raises(RuntimeError):
        asyncio.run(push.fcm_senden(TOKEN, "t", "x", "/", transport=nur(401, {"error": "invalid_grant"})))

    def fcm(req):
        if req.url.host == "oauth2.googleapis.com":
            return httpx.Response(200, json={"access_token": "z", "expires_in": 3600})
        return httpx.Response(500, text="<html>kaputt</html>")
    with pytest.raises(RuntimeError):
        asyncio.run(push.fcm_senden(TOKEN, "t", "x", "/", transport=httpx.MockTransport(fcm)))
    # kaputtes Dienstkonto → nicht eingerichtet
    monkeypatch.setenv("FCM_DIENSTKONTO", "{kein json")
    monkeypatch.delenv("PUSH_MODUS", raising=False)
    assert push.eingerichtet("android") is False
    push._apns_jwt.clear()
    push._fcm_zugang.clear()


def test_g14_texte_grenzen():
    assert push.tage_text([]) == ""
    assert push.tage_text(["2026-11-27", "2026-11-30"]) == "Fr–Mo 27.11.–30.11."            # Wochenende dazwischen gilt als lückenlos
    assert push.tage_text(["2026-12-31", "2027-01-01"]) == "Do–Fr 31.12.–01.01."
    assert push.tage_text(["2026-12-02", "2026-12-02"]) == "Mi 02.12."
    lang = "P" * 500
    titel, text = push.einteilungs_text("neu", lang, "A" * 500, [{"date": "2026-12-02", "start_time": "07:00", "end_time": "16:00"}])
    assert len(push._ort("A" * 500)) == 60 and text.endswith("7–16 Uhr")
    # unterschiedliche Zeiten in einer Serie → keine (falsche) Uhrzeit
    _, text = push.einteilungs_text("neu", "X", "", [{"date": "2026-12-02", "start_time": "07:00", "end_time": "16:00"},
                                                    {"date": "2026-12-03", "start_time": "08:00", "end_time": "16:00"}])
    assert "Uhr" not in text
