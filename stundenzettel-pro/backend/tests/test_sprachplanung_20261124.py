"""Einteilung per Sprache, Schritt 4 (24.11.2026): Datum ausrechnen (normaler Code), Uhrzeiten, Zerlegen mit festen Regeln, Zuordnen über
echte Daten mit Rückfragen, Konflikte, Route hinter Flag `sprachplanung` (speichert nichts), Mistral nur mit Flag `ki` – ohne Netz geprüft."""
import asyncio
import json
from datetime import date, timedelta

import httpx
import pytest

import sprachplanung as sp
from conftest import einladen, projekt, registrieren
from zeiten import lokal_jetzt

DI = date(2026, 11, 24)    # Dienstag
FR = date(2026, 11, 27)    # Freitag
MI = date(2026, 11, 25)    # Mittwoch
NAMEN = ["Karl Chef", "Nils Becker", "Nils Wagner", "Tom Wagner"]
PROJEKTE = [{"name": "Badsanierung Müller"}, {"name": "Dachsanierung Schmidt"}]


def iso(*tage):
    return [d.isoformat() for d in tage]


def woche(montag, n=5):
    return [(montag + timedelta(days=i)).isoformat() for i in range(n)]


# ---------------------------------------------------------------- Datum (normaler Code)

@pytest.mark.parametrize("zeitraum, heute, erwartet", [
    ("die ganze Woche", DI, iso(DI, MI, date(2026, 11, 26), FR)),
    ("ganze Woche", FR, woche(date(2026, 11, 30))),                     # am Freitag gemeint: nächste Woche
    ("diese Woche", date(2026, 11, 23), woche(date(2026, 11, 23))),
    ("nächste Woche", DI, woche(date(2026, 11, 30))),
    ("kommende Woche", DI, woche(date(2026, 11, 30))),
    ("morgen", DI, iso(MI)),
    ("übermorgen", DI, iso(date(2026, 11, 26))),
    ("heute", DI, iso(DI)),
    ("Mittwoch", DI, iso(MI)),
    ("am Montag", DI, iso(date(2026, 11, 30))),
    ("nächste Woche Mittwoch", DI, iso(date(2026, 12, 2))),
    ("übernächste Woche Freitag", DI, iso(date(2026, 12, 11))),
    ("Montag bis Mittwoch", DI, iso(date(2026, 11, 30), date(2026, 12, 1), date(2026, 12, 2))),
    ("von Mo bis Mi", DI, iso(date(2026, 11, 30), date(2026, 12, 1), date(2026, 12, 2))),
    ("Mo-Fr", DI, woche(date(2026, 11, 30))),
    ("nächste Woche Montag bis Mittwoch", DI, iso(date(2026, 11, 30), date(2026, 12, 1), date(2026, 12, 2))),
    ("Dienstag bis Donnerstag", DI, iso(DI, MI, date(2026, 11, 26))),    # heute zählt mit
    ("ab Montag", DI, woche(date(2026, 11, 30))),
    ("ab Montag drei Tage", DI, iso(date(2026, 11, 30), date(2026, 12, 1), date(2026, 12, 2))),
    ("ab morgen", DI, iso(MI, date(2026, 11, 26), FR)),
    ("ab Donnerstag 3 Tage", DI, iso(date(2026, 11, 26), FR, date(2026, 11, 30))),   # Wochenende übersprungen
    ("am 3.12.", DI, iso(date(2026, 12, 3))),
    ("3. Dezember", DI, iso(date(2026, 12, 3))),
    ("am 15.1.", DI, iso(date(2027, 1, 15))),                            # Datum ohne Jahr in der Vergangenheit → nächstes Jahr
    ("jeden Tag", DI, iso(DI, MI, date(2026, 11, 26), FR)),
    ("irgendwann", DI, []),
])
def test_01_tage(zeitraum, heute, erwartet):
    tage, _ = sp.tage_berechnen(zeitraum, heute)
    assert tage == erwartet


def test_01b_hinweise_bei_annahmen():
    assert "nicht heute" in sp.tage_berechnen("Mittwoch", MI)[1][0] and sp.tage_berechnen("Mittwoch", MI)[0] == iso(date(2026, 12, 2))
    assert "nächste Woche" in sp.tage_berechnen("die ganze Woche", FR)[1][0]


@pytest.mark.parametrize("roh, erwartet", [("7", "07:00"), ("7 Uhr", "07:00"), ("07:00", "07:00"), ("16.30", "16:30"), ("sieben", "07:00"),
                                           ("halb acht", "07:30"), ("sechzehn", "16:00"), ("25", None), ("", None), ("bald", None)])
def test_02_uhrzeit(roh, erwartet):
    assert sp.uhrzeit(roh) == erwartet


def test_02b_nachmittag_und_nachtschicht():
    assert sp.zeiten_ordnen("07:00", "04:00") == ("07:00", "16:00")      # „sieben bis vier“
    assert sp.zeiten_ordnen("06:30", "03:30") == ("06:30", "15:30")
    assert sp.zeiten_ordnen("22:00", "06:00") == ("22:00", "06:00")      # Nachtschicht bleibt


# ---------------------------------------------------------------- Zerlegen mit festen Regeln (Rückfall ohne KI)

@pytest.mark.parametrize("satz, mitarbeiter, projekt, standort, start, ende, zeitraum", [
    ("Teile Nils an die Hauptstraße ein, Projekt Müller, 7 bis 16 Uhr die ganze Woche", ["Nils"], "Müller", "Hauptstraße", "07:00", "16:00", "die ganze woche"),
    ("Nils morgen von sieben bis vier bei Müller", ["Nils"], "Müller", None, "07:00", "16:00", "morgen"),
    ("Nils und Tom ab Montag drei Tage Badsanierung Müller", ["Nils", "Tom"], "Badsanierung Müller", None, None, None, "ab montag drei tage"),
    ("Nils nächste Woche Mittwoch bei Schmidt", ["Nils"], "Schmidt", None, None, None, "naechste woche mittwoch"),
    ("nils becker morgen 6:30 bis 15 uhr dachsanierung schmidt", ["nils becker"], "dachsanierung schmidt", None, "06:30", "15:00", "morgen"),
    ("Tom Wagner Montag bis Mittwoch Projekt Dachsanierung Schmidt von halb sieben bis halb vier", ["Tom Wagner"], "Dachsanierung Schmidt", None, "06:30", "15:30", "montag bis mittwoch"),
    ("Plane Karl am 3.12. bei Müller ein, Lindenweg 12", ["Karl"], "Müller", "Lindenweg 12", None, None, "am 3.12."),
])
def test_03_regeln_zerlegen(satz, mitarbeiter, projekt, standort, start, ende, zeitraum):
    f = sp.regeln_zerlegen(satz, NAMEN, PROJEKTE)
    assert (f["mitarbeiter"], f["projekt"], f["standort"], f["startzeit"], f["endzeit"], f["zeitraum"]) == (mitarbeiter, projekt, standort, start, ende, zeitraum)


def test_03b_felder_pruefen_aus_ki():
    f = sp.felder_pruefen({"mitarbeiter": "Nils und Tom", "projekt": "Müller", "startzeit": "7", "endzeit": "4", "zeitraum": "morgen",
                           "unsicher": ["projekt", "erfunden"], "boese": "x"})
    assert f["mitarbeiter"] == ["Nils", "Tom"] and (f["startzeit"], f["endzeit"]) == ("07:00", "16:00") and f["unsicher"] == ["projekt"] and "boese" not in f
    assert sp.felder_pruefen("kein dict")["mitarbeiter"] == []


# ---------------------------------------------------------------- Zuordnen

NUTZER = [{"id": "k", "name": "Karl Chef"}, {"id": "nb", "name": "Nils Becker"}, {"id": "nw", "name": "Nils Wagner"}, {"id": "tw", "name": "Tom Wagner"}]
PROJ = [{"id": "m", "name": "Badsanierung Müller", "address": "Hauptstraße 5, 30159 Hannover", "customer_name": "Familie Müller"},
        {"id": "s", "name": "Dachsanierung Schmidt", "address": "Lindenweg 12, 30655 Hannover", "customer_name": ""}]


def test_04_mitarbeiter_finden():
    assert [u["id"] for u in sp.mitarbeiter_finden("Nils", NUTZER)] == ["nb", "nw"]       # Rückfrage
    assert [u["id"] for u in sp.mitarbeiter_finden("Nils Becker", NUTZER)] == ["nb"]
    assert [u["id"] for u in sp.mitarbeiter_finden("Becker", NUTZER)] == ["nb"]
    assert [u["id"] for u in sp.mitarbeiter_finden("Nills Beker", NUTZER)] == ["nb"]       # verhört
    assert [u["id"] for u in sp.mitarbeiter_finden("Tom", NUTZER)] == ["tw"]
    assert [u["id"] for u in sp.mitarbeiter_finden("Wagner", NUTZER)] == ["nw", "tw"]
    assert sp.mitarbeiter_finden("Zoe", NUTZER) == []


def test_04b_projekt_finden():
    assert [p["id"] for p in sp.projekt_finden("Müller", None, PROJ)] == ["m"]
    assert [p["id"] for p in sp.projekt_finden("Mueller", None, PROJ)] == ["m"]
    assert [p["id"] for p in sp.projekt_finden("Badsanierung", None, PROJ)] == ["m"]
    assert [p["id"] for p in sp.projekt_finden(None, "Lindenweg", PROJ)] == ["s"]          # nur Standort
    assert [p["id"] for p in sp.projekt_finden("Sanierung", None, PROJ)] == ["m", "s"]      # passt auf beide → Rückfrage
    assert sp.projekt_finden("Meier", None, PROJ) == []


# ---------------------------------------------------------------- Route

def _aufbau(client, monkeypatch, sprachplanung=True):
    monkeypatch.setenv("FEATURE_SPRACHPLANUNG", "1" if sprachplanung else "0")
    chef, _ = registrieren(client, email="chef@sprache-test.de", firma="Sprache Test GmbH", name="Karl Chef")
    _, nb = einladen(client, chef, name="Nils Becker", email="nb@sprache-test.de")
    _, nw = einladen(client, chef, name="Nils Wagner", email="nw@sprache-test.de", passwort="geheim4567")
    tom, tw = einladen(client, chef, name="Tom Wagner", email="tw@sprache-test.de", passwort="geheim7890")
    m = projekt(client, chef, name="Badsanierung Müller", address="Hauptstraße 5, 30159 Hannover")
    s = projekt(client, chef, name="Dachsanierung Schmidt", address="Lindenweg 12, 30655 Hannover")
    return {"chef": chef, "tom": tom, "nb": nb["user"]["id"], "nw": nw["user"]["id"], "tw": tw["user"]["id"], "m": m, "s": s}


def _vorschlag(client, kopf, **body):
    r = client.post("/api/sprachplanung/vorschlag", json=body, headers=kopf)
    assert r.status_code == 200, r.text
    return r.json()["vorschlag"]


def test_05_flag_und_rechte(client, monkeypatch):
    s = _aufbau(client, monkeypatch, sprachplanung=False)
    assert client.post("/api/sprachplanung/vorschlag", json={"text": "Nils morgen"}, headers=s["chef"]).status_code == 404
    monkeypatch.setenv("FEATURE_SPRACHPLANUNG", "1")
    assert client.post("/api/sprachplanung/vorschlag", json={"text": "Nils morgen"}, headers=s["tom"]).status_code == 403
    assert client.post("/api/sprachplanung/vorschlag", json={"text": "  "}, headers=s["chef"]).status_code == 400
    assert client.get("/api/sprachplanung/status", headers=s["chef"]).json()["server_ki"] is None


def test_06_rueckfrage_dann_vollstaendiger_entwurf_nichts_gespeichert(client, monkeypatch):
    s = _aufbau(client, monkeypatch)
    heute = lokal_jetzt().date()
    morgen = (heute + timedelta(days=1)).isoformat()
    v = _vorschlag(client, s["chef"], text="Nils morgen von sieben bis vier bei Müller")
    assert v["quelle"] == "regeln" and v["entwurf"] is None
    frage = next(r for r in v["rueckfragen"] if r["feld"] == "mitarbeiter")
    assert frage["frage"] == "Meinst du Nils Becker oder Nils Wagner?" and {o["id"] for o in frage["optionen"]} == {s["nb"], s["nw"]}
    assert v["projekt"]["id"] == s["m"]["id"] and v["tage"] == [morgen] and (v["start_time"], v["end_time"]) == ("07:00", "16:00")
    # Mit vollem Namen eindeutig → Entwurf, der direkt in die Plantafel passt
    v = _vorschlag(client, s["chef"], text="Nils Becker morgen von sieben bis vier bei Müller")
    e = v["entwurf"]
    assert e == {"project_id": s["m"]["id"], "user_ids": [s["nb"]], "dates": [morgen], "start_time": "07:00", "end_time": "16:00", "pause_minutes": 30, "address": ""}
    # Vorschlag speichert nichts
    assert client.get(f"/api/einsatzplan?von={morgen}&bis={morgen}", headers=s["chef"]).json()["einsaetze"] == []
    assert client.post("/api/einsatzplan", json=e, headers=s["chef"]).status_code == 200
    # jetzt meldet der nächste Vorschlag die Überschneidung
    v = _vorschlag(client, s["chef"], text="Nils Becker morgen 8 bis 12 Uhr bei Schmidt")
    assert [k["art"] for k in v["konflikte"]] == ["ueberschneidung"] and "schon 07:00–16:00 eingeteilt" in v["konflikte"][0]["text"]


def test_07_mehrere_mitarbeiter_standardzeit_urlaub(client, monkeypatch):
    s = _aufbau(client, monkeypatch)
    heute = lokal_jetzt().date()
    montag = heute + timedelta(days=7 - heute.weekday())
    assert client.post("/api/abwesenheiten", json={"user_id": s["tw"], "type": "urlaub", "from_date": montag.isoformat(), "to_date": montag.isoformat()}, headers=s["chef"]).status_code == 200
    v = _vorschlag(client, s["chef"], text="Nils Becker und Tom ab Montag drei Tage Badsanierung Müller")
    assert [p["id"] for p in v["mitarbeiter"]] == [s["nb"], s["tw"]] and v["tage"] == [(montag + timedelta(days=i)).isoformat() for i in range(3)]
    assert (v["start_time"], v["end_time"]) == ("07:00", "16:00") and {"startzeit", "endzeit"} <= set(v["unsicher"])
    assert any("Standardzeit" in h for h in v["hinweise"])
    assert [(k["art"], k["user_id"], k["datum"]) for k in v["konflikte"]] == [("abwesenheit", s["tw"], montag.isoformat())] and "Urlaub" in v["konflikte"][0]["text"]
    assert v["entwurf"]["user_ids"] == [s["nb"], s["tw"]]   # Konflikt ist ein Hinweis – entscheiden tut der Planer


def test_08_standort_und_unbekanntes(client, monkeypatch):
    s = _aufbau(client, monkeypatch)
    # Standort passt zur Projektadresse → keine Sonderadresse
    v = _vorschlag(client, s["chef"], text="Teile Tom an die Hauptstraße ein, Projekt Müller, 7 bis 16 Uhr die ganze Woche")
    assert v["projekt"]["id"] == s["m"]["id"] and v["adresse"] == "Hauptstraße 5, 30159 Hannover" and "standort" not in v["unsicher"]
    # anderer Standort → als Einsatzadresse übernommen und markiert
    v = _vorschlag(client, s["chef"], text="Tom morgen bei Müller, Bahnhofstraße 3")
    assert v["adresse"] == "Bahnhofstraße 3" and "standort" in v["unsicher"] and v["entwurf"]["address"] == "Bahnhofstraße 3"
    # Unbekanntes Projekt und unbekannte Person → Rückfragen mit Auswahl
    v = _vorschlag(client, s["chef"], text="Zoe morgen bei Meier")
    felder = {r["feld"] for r in v["rueckfragen"]}
    assert {"mitarbeiter", "projekt"} <= felder and v["entwurf"] is None
    assert len(next(r for r in v["rueckfragen"] if r["feld"] == "projekt")["optionen"]) == 2


def test_09_felder_vom_geraet(client, monkeypatch):
    """iPhone: Apples Modell hat schon zerlegt – der Server rechnet nur Tage aus und ordnet zu."""
    s = _aufbau(client, monkeypatch)
    heute = lokal_jetzt().date()
    mittwoch = heute + timedelta(days=7 - heute.weekday() + 2)
    v = _vorschlag(client, s["chef"], felder={"mitarbeiter": ["Tom"], "projekt": "Schmidt", "zeitraum": "nächste Woche Mittwoch", "unsicher": ["projekt"]}, quelle="apple")
    assert v["quelle"] == "apple" and v["tage"] == [mittwoch.isoformat()] and v["projekt"]["id"] == s["s"]["id"] and "projekt" in v["unsicher"]
    assert v["entwurf"]["user_ids"] == [s["tw"]]


def test_10_protokoll_ohne_text(client, monkeypatch):
    s = _aufbau(client, monkeypatch)
    _vorschlag(client, s["chef"], text="Tom morgen bei Müller GEHEIMWORT")
    import db as dbmodul

    async def lesen():
        return [x async for x in dbmodul.db().protokoll.find({"aktion": "sprachplanung.vorschlag"}, {"_id": 0})]
    eintraege = asyncio.run(lesen())
    assert eintraege and "GEHEIMWORT" not in json.dumps(eintraege) and eintraege[0]["details"]["zeichen"] > 0


def test_11_mistral_anfrage_und_rueckfall(client, monkeypatch):
    anfragen = []

    def antwort(request: httpx.Request) -> httpx.Response:
        anfragen.append(request)
        inhalt = json.dumps({"mitarbeiter": ["Tom"], "projekt": "Müller", "standort": None, "startzeit": "07:00", "endzeit": "16:00", "zeitraum": "morgen", "unsicher": []})
        return httpx.Response(200, json={"choices": [{"message": {"content": inhalt}}]})
    monkeypatch.setenv("MISTRAL_API_KEY", "test-schluessel")
    f = asyncio.run(sp.mistral_zerlegen("Tom morgen bei Müller", transport=httpx.MockTransport(antwort)))
    assert f["mitarbeiter"] == ["Tom"] and f["zeitraum"] == "morgen"
    r = anfragen[0]
    koerper = json.loads(r.content)
    assert r.url.host == "api.mistral.ai" and r.headers["authorization"] == "Bearer test-schluessel"
    assert koerper["model"] == "mistral-small-latest" and koerper["response_format"] == {"type": "json_object"} and koerper["messages"][1]["content"] == "Tom morgen bei Müller"
    with pytest.raises(RuntimeError):
        asyncio.run(sp.mistral_zerlegen("x", transport=httpx.MockTransport(lambda req: httpx.Response(401, json={}))))
    # Route: Flag ki an + Schlüssel → Mistral; fällt Mistral aus → feste Regeln mit Hinweis
    s = _aufbau(client, monkeypatch)
    monkeypatch.setenv("FEATURE_KI", "1")
    assert client.get("/api/sprachplanung/status", headers=s["chef"]).json()["server_ki"] == "mistral"

    async def ersatz(text, transport=None):
        return sp.felder_pruefen({"mitarbeiter": ["Tom"], "projekt": "Müller", "zeitraum": "morgen", "startzeit": "8", "endzeit": "12"})
    monkeypatch.setattr(sp, "mistral_zerlegen", ersatz)
    v = _vorschlag(client, s["chef"], text="Tom morgen acht bis zwölf bei Müller")
    assert v["quelle"] == "mistral" and (v["start_time"], v["end_time"]) == ("08:00", "12:00")

    async def kaputt(text, transport=None):
        raise RuntimeError("Mistral 503")
    monkeypatch.setattr(sp, "mistral_zerlegen", kaputt)
    v = _vorschlag(client, s["chef"], text="Tom morgen bei Müller")
    assert v["quelle"] == "regeln" and "nicht erreichbar" in v["hinweise"][0] and v["entwurf"] is not None
