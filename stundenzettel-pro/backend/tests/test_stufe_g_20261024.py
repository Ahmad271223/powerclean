"""Stufe G (24.10.2026): Feature-Flags, Nachrichten (Projektchat intern/Partner, Bieterchat, Kontakt, Aufgabe) mit strikten Rechten und
E-Mail-Ankündigung, Regieberichte mit Vorlagen und Kundenunterschrift, Projektakte mit Manifest/Index und Hintergrundlauf."""
import asyncio
import base64
import hashlib
import io
import json
import time
import zipfile
from datetime import datetime, timedelta, timezone

from PIL import Image

import db as dbmodul
import mail
import nachrichten as nm
from conftest import einladen, projekt, registrieren


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (120, 80), (30, 90, 160)).save(buf, "PNG")
    return buf.getvalue()


def _unterschrift() -> str:
    return "data:image/png;base64," + base64.b64encode(_png()).decode()


def _aufbau(client):
    """GU (Gabi, Mitarbeiter Gerd am Projekt), Partnerfirma Elektro (Erik Büro, Vera Vorarbeiterin, Milan Monteur), Fremdfirma; Beteiligung aktiv."""
    gu, gu_d = registrieren(client, email="admin@gu-test.de", firma="GU Bau GmbH", name="Gabi Leitung")
    gerd_kopf, gerd = einladen(client, gu, name="Gerd Mitarbeiter", email="gerd@gu-test.de", role="mitarbeiter")
    p = projekt(client, gu, name="Produktionshalle Wolfsburg", address="Werkstraße 9", employee_ids=[gerd["user"]["id"]])
    el, el_d = registrieren(client, email="chef@elektro-test.de", firma="Elektro Test GmbH", name="Erik Elektro")
    vera_kopf, vera = einladen(client, el, name="Vera Vorarbeiterin", email="vera@elektro-test.de", role="vorarbeiter")
    milan_kopf, milan = einladen(client, el, name="Milan Monteur", email="milan@elektro-test.de", role="mitarbeiter")
    bet = client.post(f"/api/projekte/{p['id']}/beteiligungen", json={"firma_id": el_d["firma"]["id"], "gewerk": "Elektro"}, headers=gu).json()["beteiligung"]
    lokal_id = client.post(f"/api/beteiligungen/{bet['id']}/antwort", json={"annehmen": True}, headers=el).json()["beteiligung"]["lokales_project_id"]
    client.put(f"/api/projekte/{lokal_id}", json={"name": "GU: Halle", "employee_ids": [vera["user"]["id"], milan["user"]["id"]]}, headers=el)
    fremd, fremd_d = registrieren(client, email="x@fremd-test.de", firma="Fremd GmbH", name="Frank Fremd")
    return {"gu": gu, "gu_firma": gu_d["firma"]["id"], "gerd": gerd_kopf, "gerd_id": gerd["user"]["id"], "p": p, "el": el, "el_firma": el_d["firma"]["id"],
            "vera": vera_kopf, "milan": milan_kopf, "milan_id": milan["user"]["id"], "lokal_id": lokal_id, "fremd": fremd, "fremd_firma": fremd_d["firma"]["id"]}


def test_01_features_und_projektchats(client, monkeypatch):
    s = _aufbau(client)
    f = client.get("/api/features").json()
    assert f["features"]["chat"] is True and f["features"]["ki"] is False and f["features"]["projektakte_async"] is False and "beschreibung" in f
    # Interner Projektchat der GU: Gabi und Gerd (zugewiesen) – Elektro/Fremd sehen ihn nie, auch nicht mit der Chat-ID
    r = client.post("/api/chats/oeffnen", json={"art": "projekt_intern", "project_id": s["p"]["id"]}, headers=s["gu"])
    assert r.status_code == 200, r.text
    ch = r.json()["chat"]
    assert ch["art"] == "projekt_intern" and ch["rolle"] == "buero"
    assert client.post("/api/chats/oeffnen", json={"art": "projekt_intern", "project_id": s["p"]["id"]}, headers=s["gerd"]).json()["chat"]["id"] == ch["id"]
    assert client.post(f"/api/chats/{ch['id']}/nachrichten", json={"text": "Morgen 7 Uhr Halle B."}, headers=s["gu"]).status_code == 200
    assert client.post(f"/api/chats/{ch['id']}/nachrichten", json={"text": "   "}, headers=s["gu"]).status_code == 400
    for fremd in ("el", "milan", "fremd"):
        assert client.get(f"/api/chats/{ch['id']}", headers=s[fremd]).status_code == 404
        assert client.post(f"/api/chats/{ch['id']}/nachrichten", json={"text": "hallo"}, headers=s[fremd]).status_code == 404
    assert client.post("/api/chats/oeffnen", json={"art": "projekt_intern", "project_id": s["p"]["id"]}, headers=s["milan"]).status_code == 404
    # Gerd: ungelesen 1 → lesen → 0; Antwort; Chef-Dashboard nennt ungelesene Nachrichten
    assert client.get("/api/chats/ungelesen", headers=s["gerd"]).json()["ungelesen"] == 1
    d = client.get(f"/api/chats/{ch['id']}", headers=s["gerd"]).json()
    assert [n["text"] for n in d["nachrichten"]] == ["Morgen 7 Uhr Halle B."] and d["nachrichten"][0]["eigene"] is False and d["chat"]["schreiben"] is True
    assert client.get("/api/chats/ungelesen", headers=s["gerd"]).json()["ungelesen"] == 0
    assert client.post(f"/api/chats/{ch['id']}/nachrichten", json={"text": "Bin da."}, headers=s["gerd"]).status_code == 200
    punkte = client.get("/api/dashboard/aufgaben", headers=s["gu"]).json()["punkte"]
    assert any(x["art"] == "nachrichten" and x["anzahl"] == 1 and x["link"] == "/nachrichten" for x in punkte)
    assert any(n["art"] == "nachricht" for n in client.get("/api/benachrichtigungen", headers=s["gu"]).json()["benachrichtigungen"])
    # Anhang: Datei mit scope chat – nur Teilnehmer laden sie
    r = client.post(f"/api/chats/{ch['id']}/anhaenge", data={"text": "Plan"}, files={"datei": ("plan.png", _png(), "image/png")}, headers=s["gerd"])
    assert r.status_code == 200, r.text
    dok = r.json()["nachricht"]["anhaenge"][0]
    assert client.get(f"/api/dokumente/{dok['id']}/datei", headers=s["gu"]).status_code == 200
    assert client.get(f"/api/dokumente/{dok['id']}/datei", headers=s["el"]).status_code == 404
    # Chef schließt den internen Chat des Elektro-Projekts: Milan kommt nicht mehr hinein, Büro schon
    r = client.post("/api/chats/oeffnen", json={"art": "projekt_intern", "project_id": s["lokal_id"]}, headers=s["milan"])
    assert r.status_code == 200, r.text
    el_chat = r.json()["chat"]["id"]
    assert client.put(f"/api/projekte/{s['lokal_id']}/chat", json={"chat_intern": False}, headers=s["milan"]).status_code == 403
    assert client.put(f"/api/projekte/{s['lokal_id']}/chat", json={"chat_intern": False}, headers=s["el"]).status_code == 200
    assert client.post("/api/chats/oeffnen", json={"art": "projekt_intern", "project_id": s["lokal_id"]}, headers=s["milan"]).status_code == 403
    assert client.get(f"/api/chats/{el_chat}", headers=s["milan"]).status_code == 404
    assert client.get(f"/api/chats/{el_chat}", headers=s["el"]).status_code == 200
    assert client.get(f"/api/projekte/{s['lokal_id']}", headers=s["el"]).json()["projekt"]["chat_intern"] is False
    # Partnerchat: GU-Leitung, Elektro-Büro und Vera (Vorarbeiterin des verknüpften Projekts); Milan und Gerd nicht
    r = client.post("/api/chats/oeffnen", json={"art": "projekt_gu", "project_id": s["p"]["id"]}, headers=s["gu"])
    assert r.status_code == 200, r.text
    gu_chat = r.json()["chat"]
    assert client.post(f"/api/chats/{gu_chat['id']}/nachrichten", json={"text": "Wann kommen die Panels?"}, headers=s["gu"]).status_code == 200
    assert client.post("/api/chats/oeffnen", json={"art": "projekt_gu", "project_id": s["p"]["id"]}, headers=s["vera"]).json()["chat"]["id"] == gu_chat["id"]
    assert client.post(f"/api/chats/{gu_chat['id']}/nachrichten", json={"text": "Donnerstag."}, headers=s["el"]).status_code == 200
    assert client.post("/api/chats/oeffnen", json={"art": "projekt_gu", "project_id": s["p"]["id"]}, headers=s["milan"]).status_code == 403
    assert client.get(f"/api/chats/{gu_chat['id']}", headers=s["gerd"]).status_code == 404
    assert client.get(f"/api/chats/{gu_chat['id']}", headers=s["fremd"]).status_code == 404
    liste = client.get("/api/chats", headers=s["el"]).json()
    assert [c["art"] for c in liste["chats"]] == ["projekt_gu", "projekt_intern"] and liste["chats"][0]["ungelesen"] == 1 and liste["ungelesen"] == 1
    assert all(c["art"] != "projekt_gu" for c in client.get("/api/chats", headers=s["gerd"]).json()["chats"])
    # E-Mail-Ankündigung: getrennter Dienst, erst nach Wartezeit, nur fremde ungelesene Nachrichten, einmal je Nachricht
    monkeypatch.setattr(mail, "SOFORT_ZUSTELLEN", False)
    spaeter = datetime.now(timezone.utc) + timedelta(minutes=5)
    assert asyncio.run(nm.einmal_pruefen(jetzt=datetime.now(timezone.utc))) == 0   # noch innerhalb der Wartezeit
    n = asyncio.run(nm.einmal_pruefen(jetzt=spaeter))
    ausgang = asyncio.run(dbmodul.db().email_ausgang.find({"art": "nachricht"}, {"_id": 0}).to_list(100))
    an = sorted(e["an"] for e in ausgang)
    assert n == len(ausgang) >= 3, (n, an)
    assert "milan@elektro-test.de" not in an and "x@fremd-test.de" not in an     # Milan ist nicht im Partnerchat, Fremd nirgends
    assert "vera@elektro-test.de" in an and "admin@gu-test.de" in an and "gerd@gu-test.de" not in an   # Gerd hat gelesen
    assert all("Antworten in Stundenzettel Pro" in e["text"] and "/#/nachrichten?chat=" in e["text"] for e in ausgang)
    assert asyncio.run(nm.einmal_pruefen(jetzt=spaeter + timedelta(minutes=10))) == 0   # nichts doppelt
    # Feature-Flag aus: Modul antwortet 404 mit Klartext
    monkeypatch.setenv("FEATURE_CHAT", "0")
    r = client.get("/api/chats", headers=s["gu"])
    assert r.status_code == 404 and "nicht freigeschaltet" in r.json()["detail"]
    assert client.get("/api/features").json()["features"]["chat"] is False


def test_02_bieter_kontakt_aufgabe(client):
    s = _aufbau(client)
    frist = (datetime.now().date() + timedelta(days=14)).isoformat()
    assert client.put("/api/firma", json={"art": "beides"}, headers=s["gu"]).status_code == 200   # Ausschreibungen nur mit Auftraggeber-Konto
    body = {"titel": "Beleuchtung Halle", "gewerk": "Elektro", "leistungsart": "Sanierung", "beschreibung": "LED-Umrüstung", "leistungsumfang": "Demontage, Montage", "sichtbarkeit": "oeffentlich",
            "angebotsfrist": frist, "ausfuehrung_von": (datetime.now().date() + timedelta(days=30)).isoformat(), "ausfuehrung_bis": (datetime.now().date() + timedelta(days=60)).isoformat(),
            "positionen": [{"nr": "001", "leistung": "LED-Panel", "menge": 40, "einheit": "Stück"}], "kaufmaennisch": {"abrechnungsart": "einheitspreise"}, "freigabe": {"adresse": True}}
    r = client.post(f"/api/projekte/{s['p']['id']}/ausschreibungen", json=body, headers=s["gu"])
    assert r.status_code == 200, r.text
    a = r.json()["ausschreibung"]
    assert client.post(f"/api/ausschreibungen/{a['id']}/veroeffentlichen", headers=s["gu"]).status_code == 200
    # Zwei Bieter (Elektro, Fremd): jeder hat seinen eigenen Chat mit der Leitung; Bieter sehen einander nie
    r = client.post("/api/chats/oeffnen", json={"art": "bieter", "ausschreibung_id": a["id"]}, headers=s["el"])
    assert r.status_code == 200, r.text
    c_el = r.json()["chat"]
    assert c_el["bieter_firma_id"] == s["el_firma"] and c_el["rolle"] == "bieter"
    c_fr = client.post("/api/chats/oeffnen", json={"art": "bieter", "ausschreibung_id": a["id"]}, headers=s["fremd"]).json()["chat"]
    assert c_fr["id"] != c_el["id"]
    assert client.post(f"/api/chats/{c_el['id']}/nachrichten", json={"text": "Gilt die Frist auch für Nachlieferungen?"}, headers=s["el"]).status_code == 200
    assert client.post(f"/api/chats/{c_fr['id']}/nachrichten", json={"text": "Wir bieten 10 % günstiger."}, headers=s["fremd"]).status_code == 200
    assert client.get(f"/api/chats/{c_fr['id']}", headers=s["el"]).status_code == 404
    assert client.get(f"/api/chats/{c_el['id']}", headers=s["fremd"]).status_code == 404
    assert client.get(f"/api/chats/{c_el['id']}", headers=s["vera"]).status_code == 404   # Vorarbeiterin: keine Ausschreibungen
    gu_liste = client.get("/api/chats", headers=s["gu"]).json()["chats"]
    assert {c["id"] for c in gu_liste if c["art"] == "bieter"} == {c_el["id"], c_fr["id"]} and all(c["rolle"] == "leitung" for c in gu_liste)
    d = client.get(f"/api/chats/{c_el['id']}", headers=s["gu"]).json()
    assert [n["text"] for n in d["nachrichten"]] == ["Gilt die Frist auch für Nachlieferungen?"]
    assert client.post(f"/api/chats/{c_el['id']}/nachrichten", json={"text": "Ja."}, headers=s["gu"]).status_code == 200
    # Leitung eröffnet einen Bieterchat nur mit beteiligten Firmen
    assert client.post("/api/chats/oeffnen", json={"art": "bieter", "ausschreibung_id": a["id"], "bieter_firma_id": s["el_firma"]}, headers=s["gu"]).json()["chat"]["id"] == c_el["id"]
    dritte, dritte_d = registrieren(client, email="d@dritte-test.de", firma="Dritte GmbH", name="Dora")
    assert client.post("/api/chats/oeffnen", json={"art": "bieter", "ausschreibung_id": a["id"], "bieter_firma_id": dritte_d["firma"]["id"]}, headers=s["gu"]).status_code == 404
    # Kontaktanfrage: nur an Firmen im Verzeichnis, nur Büro/Inhaber beider Seiten
    assert client.post("/api/chats/oeffnen", json={"art": "kontakt", "firma_id": s["el_firma"]}, headers=s["gu"]).status_code == 404
    assert client.put("/api/firma/verzeichnis", json={"sichtbar": True, "gewerke": ["Elektro"], "beschreibung": "Elektro", "ort": "Wolfsburg"}, headers=s["el"]).status_code == 200
    r = client.post("/api/chats/oeffnen", json={"art": "kontakt", "firma_id": s["el_firma"]}, headers=s["gu"])
    assert r.status_code == 200, r.text
    kt = r.json()["chat"]
    assert client.post(f"/api/chats/{kt['id']}/nachrichten", json={"text": "Kapazität im November?"}, headers=s["gu"]).status_code == 200
    assert client.get(f"/api/chats/{kt['id']}", headers=s["el"]).status_code == 200
    assert client.get(f"/api/chats/{kt['id']}", headers=s["vera"]).status_code == 404
    assert client.get(f"/api/chats/{kt['id']}", headers=s["fremd"]).status_code == 404
    assert client.post("/api/chats/oeffnen", json={"art": "kontakt", "firma_id": s["gu_firma"]}, headers=s["vera"]).status_code == 403
    assert client.post("/api/chats/oeffnen", json={"art": "kontakt", "firma_id": s["gu_firma"]}, headers=s["el"]).json()["chat"]["id"] == kt["id"]   # dieselbe Verbindung, auch rückwärts
    # Aufgabenchat: Leitung, beauftragte Firma (Büro/Vorarbeiterin) und zugeteilter Monteur – Gerd (GU-Mitarbeiter) und Fremd nicht
    heute = datetime.now().date().isoformat()
    auf = client.post(f"/api/projekte/{s['p']['id']}/aufgaben", json={"titel": "Trassen Halle B", "beschreibung": "Trassen auf 3,20 m montieren", "firma_id": s["el_firma"], "datum": heute}, headers=s["gu"]).json()["aufgabe"]
    assert client.post(f"/api/aufgaben/{auf['id']}/zuteilung", json={"mitarbeiter_ids": [s["milan_id"]]}, headers=s["el"]).status_code == 200
    r = client.post("/api/chats/oeffnen", json={"art": "aufgabe", "aufgabe_id": auf["id"]}, headers=s["milan"])
    assert r.status_code == 200, r.text
    ac = r.json()["chat"]
    assert client.post(f"/api/chats/{ac['id']}/nachrichten", json={"text": "Trasse fehlt noch 2 m Material."}, headers=s["milan"]).status_code == 200
    assert client.get(f"/api/chats/{ac['id']}", headers=s["gu"]).status_code == 200
    assert client.get(f"/api/chats/{ac['id']}", headers=s["vera"]).status_code == 200
    assert client.get(f"/api/chats/{ac['id']}", headers=s["gerd"]).status_code == 404
    assert client.get(f"/api/chats/{ac['id']}", headers=s["fremd"]).status_code == 404
    assert any(n["art"] == "nachricht" for n in client.get("/api/benachrichtigungen", headers=s["gu"]).json()["benachrichtigungen"])
    milan_liste = client.get("/api/chats", headers=s["milan"]).json()["chats"]
    assert [c["art"] for c in milan_liste] == ["aufgabe"]   # kein Bieter-, Kontakt- oder Partnerchat für den Monteur


def test_03_regieberichte_vorlagen_unterschrift(client, monkeypatch):
    s = _aufbau(client)
    heute = datetime.now().date().isoformat()
    # Vorlage (nur Büro, Felder werden wie der Bericht geprüft)
    r = client.post("/api/berichtsvorlagen", json={"name": "Regie Elektro", "art": "regiebericht", "felder": {"bereich": "Halle B", "regie_geraete": [{"bezeichnung": "Bühne", "stunden": 4}], "unbekannt": 1}}, headers=s["el"])
    assert r.status_code == 200, r.text
    v = r.json()["vorlage"]
    assert v["felder"] == {"bereich": "Halle B", "regie_geraete": [{"bezeichnung": "Bühne", "stunden": 4.0}]} and v["art_name"] == "Regiebericht"
    assert client.post("/api/berichtsvorlagen", json={"name": "x", "felder": {"regie_stunden": [{"name": "a", "stunden": 30}]}}, headers=s["el"]).status_code == 422
    assert client.post("/api/berichtsvorlagen", json={"name": "x"}, headers=s["vera"]).status_code == 403
    assert [x["name"] for x in client.get("/api/berichtsvorlagen", headers=s["vera"]).json()["vorlagen"]] == ["Regie Elektro"]
    assert client.get("/api/berichtsvorlagen", headers=s["gu"]).json()["vorlagen"] == []   # je Firma
    # Vorschlag: Arbeitsanweisungen aus Aufgaben des Tages, Materialliste aus Buchungen
    auf = client.post(f"/api/projekte/{s['p']['id']}/aufgaben", json={"titel": "Trassen Halle B", "beschreibung": "Trassen auf 3,20 m montieren", "firma_id": s["el_firma"], "datum": heute}, headers=s["gu"]).json()["aufgabe"]
    assert client.post(f"/api/projekte/{s['lokal_id']}/material", json={"bezeichnung": "Kabeltrasse 200 mm", "menge": 24, "einheit": "m", "date": heute}, headers=s["vera"]).status_code == 200
    vs = client.get(f"/api/projekte/{s['p']['id']}/tagesbericht-vorschlag?datum={heute}", headers=s["vera"]).json()
    assert vs["arbeitsanweisungen"] == ["Trassen Halle B: Trassen auf 3,20 m montieren"] and vs["materialliste"][0]["bezeichnung"] == "Kabeltrasse 200 mm"
    # Regiebericht mit Stunden/Material/Geräten; Kundenunterschrift sperrt den Inhalt; PDF nennt Regie und Unterschrift
    daten = {"datum": heute, "art": "regiebericht", "vorlage_id": v["id"], **v["felder"], "firmen": ["Elektro Test GmbH"], "mitarbeiter_anzahl": 2, "taetigkeiten": "Zusatzleuchten montiert",
             "auftraggeber_name": "GU – Gabi Leitung", "regie_stunden": [{"name": "Vera", "taetigkeit": "Montage", "stunden": 3.5}, {"name": "Milan", "stunden": 3.5}],
             "regie_material": [{"bezeichnung": "LED-Panel", "menge": 2, "einheit": "Stück"}]}
    r = client.post(f"/api/projekte/{s['p']['id']}/tagesberichte", json=daten, headers=s["vera"])
    assert r.status_code == 200, r.text
    b = r.json()["bericht"]
    assert b["art"] == "regiebericht" and b["art_name"] == "Regiebericht" and b["regie_geraete"][0]["bezeichnung"] == "Bühne"
    d = client.get(f"/api/tagesberichte/{b['id']}", headers=s["vera"]).json()
    assert d["bearbeiten"] is True and d["unterschreiben"] is True
    assert client.post(f"/api/tagesberichte/{b['id']}/unterschrift", json={"signer_name": "Gabi Leitung", "image": "data:image/jpeg;base64,xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"}, headers=s["vera"]).status_code == 422
    assert client.post(f"/api/tagesberichte/{b['id']}/unterschrift", json={"signer_name": "Gabi Leitung", "image": _unterschrift()}, headers=s["milan"]).status_code == 404
    r = client.post(f"/api/tagesberichte/{b['id']}/unterschrift", json={"signer_name": "Gabi Leitung", "image": _unterschrift()}, headers=s["vera"])
    assert r.status_code == 200, r.text
    assert r.json()["bericht"]["unterschrieben"] is True and "image" not in r.json()["bericht"]["unterschrift"]
    d = client.get(f"/api/tagesberichte/{b['id']}", headers=s["vera"]).json()
    assert d["bearbeiten"] is False and d["bericht"]["unterschrift"]["signer_name"] == "Gabi Leitung"
    assert client.put(f"/api/tagesberichte/{b['id']}", json=daten, headers=s["vera"]).status_code == 400
    pdf = client.get(f"/api/tagesberichte/{b['id']}/pdf", headers=s["gu"])
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF") and "Regiebericht" in pdf.headers["content-disposition"]
    assert client.delete(f"/api/tagesberichte/{b['id']}/unterschrift", headers=s["el"]).status_code == 400          # Grund fehlt
    assert client.delete(f"/api/tagesberichte/{b['id']}/unterschrift?grund=Name+falsch", headers=s["gu"]).status_code == 403   # nicht die verfassende Firma
    assert client.delete(f"/api/tagesberichte/{b['id']}/unterschrift?grund=Name+falsch", headers=s["el"]).status_code == 200
    assert client.get(f"/api/tagesberichte/{b['id']}", headers=s["vera"]).json()["bearbeiten"] is True
    assert [x["status"] for x in client.get(f"/api/tagesberichte/{b['id']}", headers=s["gu"]).json()["bericht"]["verlauf"]] == ["entwurf", "unterschrieben", "unterschrift_entfernt"]
    # Normaler Tagesbericht bleibt wie bisher (art Standard)
    b2 = client.post(f"/api/projekte/{s['p']['id']}/tagesberichte", json={"datum": heute, "taetigkeiten": "Reinigung"}, headers=s["gu"]).json()["bericht"]
    assert b2["art"] == "tagesbericht" and b2["art_name"] == "Bautagesbericht"
    # Feature-Flag aus: Vorlagen 404, Berichte selbst bleiben erreichbar
    monkeypatch.setenv("FEATURE_BERICHTSVORLAGEN", "0")
    assert client.get("/api/berichtsvorlagen", headers=s["el"]).status_code == 404
    assert client.get(f"/api/tagesberichte/{b['id']}", headers=s["vera"]).status_code == 200


def test_04_projektakte_manifest_index_hintergrund(client, monkeypatch):
    s = _aufbau(client)
    ch = client.post("/api/chats/oeffnen", json={"art": "projekt_gu", "project_id": s["p"]["id"]}, headers=s["gu"]).json()["chat"]
    client.post(f"/api/chats/{ch['id']}/nachrichten", json={"text": "Bitte Panels bis Donnerstag."}, headers=s["gu"])
    client.post(f"/api/chats/{ch['id']}/anhaenge", data={"text": "Plan"}, files={"datei": ("plan.png", _png(), "image/png")}, headers=s["el"])
    ci = client.post("/api/chats/oeffnen", json={"art": "projekt_intern", "project_id": s["p"]["id"]}, headers=s["gu"]).json()["chat"]
    client.post(f"/api/chats/{ci['id']}/nachrichten", json={"text": "Intern: Nachkalkulation prüfen."}, headers=s["gu"])
    # synchron (Speicher-Modus): fertig mit Manifest, Index, Nachrichten; Prüfsummen stimmen
    r = client.post(f"/api/projekte/{s['p']['id']}/projektakte", headers=s["gu"])
    assert r.status_code == 200, r.text
    a = r.json()["projektakte"]
    assert a["status"] == "fertig" and a["manifest_eintraege"] > 5 and a["inhalt"]["nachrichten"] == 4 and a["inhalt"]["nachrichten_anhaenge"] == 1 and a["inhalt"]["index"] == 1
    z = zipfile.ZipFile(io.BytesIO(client.get(f"/api/projektakten/{a['id']}.zip", headers=s["gu"]).content))
    namen = z.namelist()
    assert "manifest.json" in namen and "00_Index.pdf" in namen and "00_LIESMICH.txt" in namen
    assert sum(1 for n in namen if n.startswith("12_Nachrichten/")) == 5
    manifest = json.loads(z.read("manifest.json"))
    assert manifest["algorithmus"] == "SHA-256" and len(manifest["dateien"]) == len(namen) - 1
    for m in manifest["dateien"]:
        assert hashlib.sha256(z.read(m["datei"])).hexdigest() == m["sha256"] and m["bytes"] == len(z.read(m["datei"]))
    assert z.read("00_Index.pdf").startswith(b"%PDF") and "12_Nachrichten" in z.read("00_LIESMICH.txt").decode("utf-8")
    assert client.get(f"/api/projektakten/{a['id']}", headers=s["gu"]).json()["projektakte"]["status"] == "fertig"
    # Elektro (beteiligt): nur eigener interner Chat + Partnerchat, nie der interne GU-Chat
    ak = client.post(f"/api/projekte/{s['lokal_id']}/projektakte", headers=s["el"]).json()["projektakte"]
    z2 = zipfile.ZipFile(io.BytesIO(client.get(f"/api/projektakten/{ak['id']}.zip", headers=s["el"]).content))
    inhalt = "".join(z2.read(n).decode("utf-8") for n in z2.namelist() if n.startswith("12_Nachrichten/") and n.endswith(".json"))
    assert "Bitte Panels bis Donnerstag." in inhalt and "Nachkalkulation" not in inhalt
    # Hintergrund: Status laeuft → fertig, Download erst danach
    monkeypatch.setenv("FEATURE_PROJEKTAKTE_ASYNC", "1")
    r = client.post(f"/api/projekte/{s['p']['id']}/projektakte", headers=s["gu"])
    assert r.status_code == 200, r.text
    b = r.json()["projektakte"]
    assert b["status"] == "laeuft" and b["size"] == 0
    stand = b
    for _ in range(100):
        stand = client.get(f"/api/projektakten/{b['id']}", headers=s["gu"]).json()["projektakte"]
        if stand["status"] != "laeuft":
            break
        time.sleep(0.1)
    assert stand["status"] == "fertig", stand
    assert stand["size"] > 0 and stand["fertig_at"] and stand["fortschritt"] == "Fertig"
    assert client.get(f"/api/projektakten/{b['id']}.zip", headers=s["gu"]).status_code == 200
    liste = client.get(f"/api/projekte/{s['p']['id']}/projektakten", headers=s["gu"]).json()["projektakten"]
    assert len(liste) == 2 and all(x["status"] == "fertig" for x in liste)
