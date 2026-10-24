"""Stufe H (24.10.2026): optionales KI-Modul hinter dem Flag `ki` (Standard aus) – nur Entwürfe, nie ohne Mensch gespeichert, kein Netz in Tests."""
import asyncio
import json

import db as dbmodul
import ki
from conftest import einladen, registrieren


def test_01_flag_aus_und_nicht_eingerichtet(client, monkeypatch):
    chef, _ = registrieren(client)
    assert client.get("/api/features").json()["features"]["ki"] is False
    r = client.get("/api/ki/status", headers=chef)
    assert r.status_code == 404 and "nicht freigeschaltet" in r.json()["detail"]
    assert client.post("/api/ki/angebot-entwurf", json={"text": "Fenster putzen"}, headers=chef).status_code == 404
    # Flag an, aber kein Schlüssel: Status sagt es, Entwürfe antworten 503 mit Klartext – nie ein Netzaufruf
    monkeypatch.setenv("FEATURE_KI", "1")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(ki, "anfragen", lambda *a, **k: (_ for _ in ()).throw(AssertionError("kein Netz erlaubt")))
    st = client.get("/api/ki/status", headers=chef).json()
    assert st["bereit"] is False and st["schluessel"] is False and "modell" in st and "key" not in json.dumps(st).lower()
    r = client.post("/api/ki/angebot-entwurf", json={"text": "Fenster putzen"}, headers=chef)
    assert r.status_code == 503 and "ANTHROPIC_API_KEY" in r.json()["detail"]
    assert client.post("/api/ki/angebot-entwurf", json={"text": ""}, headers=chef).status_code == 422
    assert client.post("/api/ki/angebot-entwurf", json={"text": "x" * 20001}, headers=chef).status_code == 422


def test_02_entwuerfe_nur_vorschlag(client, monkeypatch):
    chef, _ = registrieren(client)
    mia, _ = einladen(client, chef)
    monkeypatch.setenv("FEATURE_KI", "1")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-schluessel-nicht-echt")
    gesendet = {}

    def fake(anweisung, text):
        gesendet["anweisung"], gesendet["text"] = anweisung, text
        if "Eingangsrechnung" in anweisung:
            return '```json\n{"lieferant": "Elektro Nord GmbH", "rechnungsnummer": "RE-2026-0815", "rechnungsdatum": "2026-10-20", "faellig_am": "2026-11-19", "netto": "1.000,00", "ust": 190, "brutto": 1190, "positionen": [{"text": "LED-Panel", "menge": 10, "einheit": "Stück", "betrag": 1000}], "hinweise": ["Skonto 2 % bei Zahlung in 10 Tagen"]}\n```'
        return json.dumps({"positionen": [
            {"art": "titel", "text": "Grundreinigung Bürogebäude"},
            {"art": "leistung", "text": "Grundreinigung Böden", "beschreibung": "inkl. Grundreiniger", "menge": 1200, "einheit": "m²", "einzelpreis": None, "unsicher": True},
            {"art": "stunden", "text": "Glasreinigung", "menge": 16, "einheit": "h", "einzelpreis": 38.5},
            {"art": "unbekannt", "text": "Anfahrt", "menge": "40", "einheit": "km", "einzelpreis": "0,65"},
            "kaputt",
        ], "hinweise": ["Fläche der Glasflächen fehlt", 42]})
    monkeypatch.setattr(ki, "anfragen", fake)
    client.put("/api/firma", json={"kalkulation": {"stundensatz": 42}}, headers=chef)
    vorher = asyncio.run(dbmodul.db().kundenangebote.count_documents({}))
    r = client.post("/api/ki/angebot-entwurf", json={"text": "Grundreinigung Bürogebäude 1.200 m² mit Glasflächen, 2 Mitarbeiter"}, headers=chef)
    assert r.status_code == 200, r.text
    e = r.json()
    assert "Firmendaten" in gesendet["text"] and "42" in gesendet["text"] and "Grundreinigung" in gesendet["text"]
    assert [p["art"] for p in e["positionen"]] == ["titel", "leistung", "stunden", "leistung"]
    assert e["positionen"][1]["unsicher"] is True and e["positionen"][1]["einzelpreis"] is None and e["positionen"][1]["menge"] == 1200
    assert e["positionen"][2]["einzelpreis"] == 38.5 and e["positionen"][2]["unsicher"] is False
    assert e["positionen"][3]["einzelpreis"] == 0.65 and e["positionen"][3]["menge"] == 40.0
    assert e["hinweise"] == ["Fläche der Glasflächen fehlt"] and "nichts ist gespeichert" in e["hinweis"]
    assert asyncio.run(dbmodul.db().kundenangebote.count_documents({})) == vorher   # kein Angebot entstanden
    # Protokoll ohne Inhalt, nur Längen
    eintraege = client.get("/api/protokoll?limit=20", headers=chef).json()
    liste = eintraege.get("eintraege") or eintraege.get("protokoll") or []
    ki_eintraege = [x for x in liste if x.get("aktion") == "ki.angebot_entwurf"]
    assert ki_eintraege and "Grundreinigung" not in json.dumps(ki_eintraege) and ki_eintraege[0]["details"]["positionen"] == 4
    # Übernahme läuft über die normale Angebotsroute – erst damit entsteht ein Angebot
    uebernahme = [{k: v for k, v in p.items() if k != "unsicher"} for p in e["positionen"]]
    for p in uebernahme:
        p["einzelpreis"] = p["einzelpreis"] or 0
        p["menge"] = p["menge"] or 0
    r = client.post("/api/kundenangebote", json={"titel": "Grundreinigung Bürogebäude", "positionen": uebernahme}, headers=chef)
    assert r.status_code == 200, r.text
    assert asyncio.run(dbmodul.db().kundenangebote.count_documents({})) == vorher + 1
    # Belegvorschlag: Zahlen mit Komma, Code-Zaun, Rechenprüfung; Mitarbeiterin ohne Recht: 403
    r = client.post("/api/ki/beleg-vorschlag", json={"text": "Elektro Nord GmbH Rechnung RE-2026-0815 vom 20.10.2026 … Netto 1.000,00 USt 190,00 Brutto 1.190,00"}, headers=chef)
    assert r.status_code == 200, r.text
    v = r.json()["vorschlag"]
    assert v["lieferant"] == "Elektro Nord GmbH" and v["netto"] == 1000.0 and v["brutto"] == 1190.0 and v["faellig_am"] == "2026-11-19" and v["positionen"][0]["menge"] == 10.0
    assert r.json()["hinweise"] == ["Skonto 2 % bei Zahlung in 10 Tagen"]
    assert asyncio.run(dbmodul.db().eingangsrechnungen.count_documents({})) == 0
    assert client.post("/api/ki/beleg-vorschlag", json={"text": "Rechnung"}, headers=mia).status_code == 403
    # Unlesbare Antwort → 502 mit Klartext, Ablehnung → 422
    monkeypatch.setattr(ki, "anfragen", lambda a, t: "Das kann ich leider nicht.")
    r = client.post("/api/ki/beleg-vorschlag", json={"text": "Rechnung"}, headers=chef)
    assert r.status_code == 502 and "kein lesbarer" in r.json()["detail"]
    monkeypatch.setattr(ki, "anfragen", lambda a, t: '{"netto": 100, "ust": 19, "brutto": 200}')
    r = client.post("/api/ki/beleg-vorschlag", json={"text": "Rechnung"}, headers=chef)
    assert r.status_code == 200 and any("Bruttobetrag" in h for h in r.json()["hinweise"])
