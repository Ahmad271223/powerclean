"""Lizenz- und Abrechnungsmodell: nur Auftraggeber schreiben formal aus, GU-Projektabo je aktivem Projekt, kostenlose Projektteilnahme
für Betriebe nach der Testphase, Firmenabo für Firmenfunktionen, Preisliste und Betreiber-Abrechnungsliste – 2026-10-23."""
import asyncio
from datetime import timedelta

import db as dbmodul
from auth import jetzt
from conftest import einladen, projekt, registrieren, zeit

TENDER = {"titel": "Elektro", "gewerk": "Elektro", "beschreibung": "x", "sichtbarkeit": "oeffentlich", "angebotsfrist": "2026-12-20"}


def test_01_nur_auftraggeber_und_gu_projektabo(client):
    chef, chef_d = registrieren(client, email="chef@abo-test.de", firma="Bau Abo GmbH", name="Anna")
    buero, _ = einladen(client, chef, name="Bea", email="bea@abo-test.de", role="buero")
    p = projekt(client, chef, name="Halle A")
    # Ausführender Betrieb (Standard): keine formale Ausschreibung
    r = client.post(f"/api/projekte/{p['id']}/ausschreibungen", json=TENDER, headers=chef)
    assert r.status_code == 403 and "Auftraggeber" in r.json()["detail"]
    assert client.get(f"/api/projekte/{p['id']}", headers=chef).json()["projekt"]["gu_abo"] is None
    # Als „beides“: anlegen (Entwurf kostenlos), veröffentlichen aktiviert das GU-Projekt genau einmal
    assert client.put("/api/firma", json={"art": "beides"}, headers=chef).status_code == 200
    a = client.post(f"/api/projekte/{p['id']}/ausschreibungen", json=TENDER, headers=chef).json()["ausschreibung"]
    assert client.get(f"/api/projekte/{p['id']}", headers=chef).json()["projekt"]["gu_abo"] is None
    assert client.get(f"/api/firma/abos", headers=chef).json()["gu_projekte_aktiv"] == 0
    assert client.post(f"/api/ausschreibungen/{a['id']}/veroeffentlichen", headers=chef).status_code == 200
    abo = client.get(f"/api/projekte/{p['id']}", headers=chef).json()["projekt"]["gu_abo"]
    assert abo["status"] == "aktiv" and abo["preis_monat"] == 50.99 and abo["aktiviert_am"] and len(abo["zeitraeume"]) == 1
    a2 = client.post(f"/api/projekte/{p['id']}/ausschreibungen", json={**TENDER, "titel": "Trockenbau", "gewerk": "Trockenbau"}, headers=chef).json()["ausschreibung"]
    assert client.post(f"/api/ausschreibungen/{a2['id']}/veroeffentlichen", headers=chef).status_code == 200
    assert len(client.get(f"/api/projekte/{p['id']}", headers=chef).json()["projekt"]["gu_abo"]["zeitraeume"]) == 1   # ein Projekt, ein Abo
    abos = client.get("/api/firma/abos", headers=chef).json()
    assert abos["gu_projekte_aktiv"] == 1 and abos["kosten_projekte_monat"] == 50.99 and abos["preise"]["projekt_gu"] == 50.99
    assert abos["plan"]["status"] == "test" and abos["firmenabo"] is True and abos["kosten_firma_monat"] == round(4.99 + 3.99, 2)
    # Beenden nur Inhaber; eine spätere Veröffentlichung aktiviert wieder (neuer Zeitraum); Detailseite zeigt den Stand
    assert client.post(f"/api/projekte/{p['id']}/gu-abo", json={"aktiv": False}, headers=buero).status_code == 403
    r = client.post(f"/api/projekte/{p['id']}/gu-abo", json={"aktiv": False}, headers=chef)
    abo = r.json()["gu_abo"]
    assert r.status_code == 200 and abo["status"] == "gekuendigt" and abo["endet_am"] and abo["zeitraeume"][0]["bis"] == abo["endet_am"]
    assert client.get("/api/firma/abos", headers=chef).json()["gu_projekte_aktiv"] == 1   # bis zum Periodenende (Monatsende) kostenpflichtig
    gestern = (jetzt() - timedelta(days=1)).date().isoformat()
    asyncio.run(dbmodul.db().projects.update_one({"id": p["id"]}, {"$set": {"gu_abo.endet_am": gestern}}))
    assert client.get("/api/firma/abos", headers=chef).json()["gu_projekte_aktiv"] == 0   # Periodenende vorbei → beendet
    a3 = client.post(f"/api/projekte/{p['id']}/ausschreibungen", json={**TENDER, "titel": "Maler", "gewerk": "Maler"}, headers=chef).json()["ausschreibung"]
    assert client.post(f"/api/ausschreibungen/{a3['id']}/veroeffentlichen", headers=chef).status_code == 200
    d = client.get(f"/api/ausschreibungen/{a3['id']}", headers=chef).json()["ausschreibung"]
    assert d["gu_abo"]["status"] == "aktiv" and len(d["gu_abo"]["zeitraeume"]) == 2 and d["preise"]["projekt_gu"] == 50.99
    # Einladung einer Firma zum Projekt aktiviert ebenfalls – aber nur bei Auftraggeber-Konten
    el, el_d = registrieren(client, email="chef@elektro-abo.de", firma="Elektro Abo", name="Erika")
    p2 = projekt(client, chef, name="Halle B")
    assert client.post(f"/api/projekte/{p2['id']}/beteiligungen", json={"firma_id": el_d["firma"]["id"], "gewerk": "Elektro"}, headers=chef).status_code == 200
    assert client.get(f"/api/projekte/{p2['id']}", headers=chef).json()["projekt"]["gu_abo"]["status"] == "aktiv"
    betrieb, _ = registrieren(client, email="chef@reinigung-abo.de", firma="Reinigung Abo", name="Rita")
    p3 = projekt(client, betrieb, name="Objekt")
    assert client.post(f"/api/projekte/{p3['id']}/beteiligungen", json={"firma_id": el_d["firma"]["id"], "gewerk": "Elektro"}, headers=betrieb).status_code == 200
    assert client.get(f"/api/projekte/{p3['id']}", headers=betrieb).json()["projekt"]["gu_abo"] is None
    # Mitarbeiter sehen kein Abo-Feld
    ma, _ = einladen(client, chef, name="Milan", email="milan@abo-test.de", role="mitarbeiter")
    client.put(f"/api/projekte/{p['id']}", json={"name": "Halle A", "employee_ids": [client.get('/api/auth/ich', headers=ma).json()['user']['id']]}, headers=chef)
    assert "gu_abo" not in client.get(f"/api/projekte/{p['id']}", headers=ma).json()["projekt"]


def test_02_kostenlose_teilnahme_und_firmenabo(client):
    gu, gu_d = registrieren(client, email="chef@gu-teilnahme.de", firma="GU Teilnahme", name="Gerd")
    client.put("/api/firma", json={"art": "auftraggeber"}, headers=gu)
    p = projekt(client, gu, name="Logistikhalle")
    el, el_d = registrieren(client, email="chef@elektro-teilnahme.de", firma="Elektro Teilnahme", name="Erika")
    eigenes = projekt(client, el, name="Eigenes Objekt vorher")   # in der Testphase angelegt
    # Testphase vorbei → kostenlose Projektteilnahme statt Vollsperre
    asyncio.run(dbmodul.db().firmen.update_one({"id": el_d["firma"]["id"]}, {"$set": {"plan.test_bis": (jetzt() - timedelta(days=1)).isoformat()}}))
    plan = client.get("/api/firma/plan", headers=el).json()
    assert plan["status"] == "teilnahme" and plan["stufe"] == "teilnahme" and plan["schreiben"] is True
    # Firmenfunktionen brauchen das Firmenabo (402 mit Preis)
    for methode, pfad, body in (("POST", "/api/mitarbeiter", {"name": "X", "email": "x@elektro-teilnahme.de", "role": "mitarbeiter"}),
                                ("POST", "/api/projekte", {"name": "Eigenes Objekt", "hourly_rate": 30}),
                                ("POST", "/api/rechnungen/anlegen", {"project_id": p["id"], "year": 2026, "month": 10}),
                                ("POST", "/api/firma/api-tokens", {"name": "x"}), ("POST", "/api/firma/webhooks", {"url": "https://hooks.example.com/x"})):
        r = client.request(methode, pfad, json=body, headers=el)
        assert r.status_code == 402 and "Firmenabo" in r.json()["detail"], (pfad, r.status_code, r.text)
    assert client.get("/api/lohn/vorbereitung?jahr=2026&monat=10", headers=el).status_code == 402
    # Zeiten und Stempeluhr auf eigenen Projekten gehören zum Firmenabo; Lesen geht weiter
    r = client.post("/api/zeiten", json={"project_id": eigenes["id"], "date": "2026-10-05", "start_time": "08:00", "end_time": "12:00"}, headers=el)
    assert r.status_code == 402 and "Firmenabo" in r.json()["detail"]
    assert client.post("/api/stempel/start", json={"project_id": eigenes["id"]}, headers=el).status_code == 402
    assert client.get("/api/projekte", headers=el).status_code == 200
    # Teilnahme funktioniert: Ausschreibung finden, bieten, fragen; Projektbeteiligung annehmen, Zeiten auf dem verknüpften Projekt erfassen
    a = client.post(f"/api/projekte/{p['id']}/ausschreibungen", json=TENDER, headers=gu).json()["ausschreibung"]
    assert client.post(f"/api/ausschreibungen/{a['id']}/veroeffentlichen", headers=gu).status_code == 200
    assert [x["id"] for x in client.get("/api/ausschreibungen", headers=el).json()["ausschreibungen"]] == [a["id"]]
    assert client.post(f"/api/ausschreibungen/{a['id']}/angebot", json={"preisart": "pauschal", "preis_netto": 1000}, headers=el).status_code == 200
    assert client.post(f"/api/ausschreibungen/{a['id']}/fragen", json={"text": "Frage?"}, headers=el).status_code == 200
    b = client.post(f"/api/projekte/{p['id']}/beteiligungen", json={"firma_id": el_d["firma"]["id"], "gewerk": "Elektro"}, headers=gu).json()["beteiligung"]
    r = client.post(f"/api/beteiligungen/{b['id']}/antwort", json={"annehmen": True}, headers=el)
    assert r.status_code == 200
    lokal = r.json()["beteiligung"]["lokales_project_id"]
    zeit(client, el, lokal, date="2026-10-05")
    # Preise öffentlich; Betreiber schaltet das Firmenabo frei → Firmenfunktionen gehen wieder; Abrechnungsliste
    preise = client.get("/api/preise").json()
    assert preise["preise"] == {"projekt_gu": 50.99, "firma": 4.99, "nutzer": 3.99}
    assert client.post("/api/admin/plan", json={"email": "chef@elektro-teilnahme.de", "status": "aktiv", "stufe": "firma"}, headers={"X-Admin-Token": "betreiber-test"}).status_code == 200
    assert client.post("/api/projekte", json={"name": "Eigenes Objekt", "hourly_rate": 30}, headers=el).status_code == 200
    assert client.get("/api/firma/plan", headers=el).json()["stufe"] == "firma"
    liste = client.get("/api/admin/abos", headers={"X-Admin-Token": "betreiber-test"}).json()
    je_firma = {f["name"]: f for f in liste["firmen"]}
    assert je_firma["GU Teilnahme"]["gu_projekte_aktiv"] == 1 and je_firma["GU Teilnahme"]["kosten_projekte_monat"] == 50.99
    assert je_firma["Elektro Teilnahme"]["stufe"] == "firma" and je_firma["Elektro Teilnahme"]["kosten_firma_monat"] == 4.99
    assert liste["summe_monat"] >= 50.99 + 4.99
    assert client.get("/api/admin/abos").status_code == 403
