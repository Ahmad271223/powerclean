"""Plattform-Kern (23.10.2026): laufende Stempelungen beim Deaktivieren/Löschen abschließen statt löschen, GU-Abo-Zustände mit Kündigung
zum Periodenende, E-Mail-Ausgang mit Nachweisen, Nachträge mit Freigabe, Abnahmen mit Bestätigung, ZIP-Projektakte für jede Firma,
Startseiten-Aufgabenliste, Projektleiter-Übersicht, Firmenverifizierung, Unteraufträge über verknüpfte Projekte."""
import asyncio
import io
import zipfile
from datetime import date, timedelta

import config
import db as dbmodul
import mail
from auth import jetzt
from conftest import einladen, projekt, registrieren, zeit

ADMIN = {"X-Admin-Token": "betreiber-test"}
TENDER = {"titel": "Elektro", "gewerk": "Elektro", "beschreibung": "x", "sichtbarkeit": "oeffentlich", "angebotsfrist": "2026-12-20"}


def _png() -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (200, 120), (120, 80, 40)).save(buf, "PNG")
    return buf.getvalue()


def _aufbau(client):
    """GU (Auftraggeber) mit Projekt, Elektro-Firma als beauftragte Partnerin (verknüpftes Projekt), fremde Firma."""
    gu, gu_d = registrieren(client, email="admin@gu-kern.de", firma="GU Kern GmbH", name="Gabi Leitung")
    assert client.put("/api/firma", json={"art": "auftraggeber", "street": "Bauweg 1", "zip_code": "30159", "city": "Hannover"}, headers=gu).status_code == 200
    p = projekt(client, gu, name="Logistikhalle Nord", address="Industrieweg 1, Hannover")
    el, el_d = registrieren(client, email="chef@elektro-kern.de", firma="Elektro Kern GmbH", name="Erik Elektro")
    el_buero, _ = einladen(client, el, name="Bea Büro", email="bea@elektro-kern.de", role="buero")
    el_ma, el_ma_d = einladen(client, el, name="Milan Monteur", email="milan@elektro-kern.de", role="mitarbeiter")
    bet = client.post(f"/api/projekte/{p['id']}/beteiligungen", json={"firma_id": el_d["firma"]["id"], "gewerk": "Elektro"}, headers=gu).json()["beteiligung"]
    lokal_id = client.post(f"/api/beteiligungen/{bet['id']}/antwort", json={"annehmen": True}, headers=el).json()["beteiligung"]["lokales_project_id"]
    client.put(f"/api/projekte/{lokal_id}", json={"name": "GU Kern: Logistikhalle", "employee_ids": [el_ma_d["user"]["id"]]}, headers=el)
    fremd, _ = registrieren(client, email="x@fremd-kern.de", firma="Fremd Kern", name="Frank")
    return {"gu": gu, "gu_d": gu_d, "p": p, "el": el, "el_d": el_d, "el_firma": el_d["firma"]["id"], "el_buero": el_buero, "el_ma": el_ma, "el_ma_d": el_ma_d,
            "lokal_id": lokal_id, "bet": bet, "fremd": fremd}


def test_01_stempelung_bleibt_beim_deaktivieren_und_kontoloeschen(client):
    chef, _ = registrieren(client, email="chef@stempel-kern.de", firma="Stempel Kern", name="Anna")
    p = projekt(client, chef, name="Objekt A")
    ma, ma_d = einladen(client, chef, name="Mia", email="mia@stempel-kern.de", role="mitarbeiter")
    ma2, ma2_d = einladen(client, chef, name="Max", email="max@stempel-kern.de", role="mitarbeiter", passwort="geheim456")
    start = (jetzt() - timedelta(hours=2)).isoformat()
    assert client.post("/api/stempel/start", json={"project_id": p["id"], "start_at": start, "pausen": []}, headers=ma).status_code == 200
    assert client.post("/api/stempel/start", json={"project_id": p["id"], "start_at": start, "pausen": []}, headers=ma2).status_code == 200
    # Deaktivieren: die Stempelung wird als Eintrag gesichert (Vermerk im Eintrag und Protokoll), nicht gelöscht
    assert client.delete(f"/api/mitarbeiter/{ma_d['user']['id']}", headers=chef).status_code == 200
    heute = date.today().isoformat()
    zeiten = client.get(f"/api/zeiten?von={(date.today() - timedelta(days=1)).isoformat()}&bis={heute}&user_id={ma_d['user']['id']}", headers=chef).json()["eintraege"]
    assert len(zeiten) == 1 and zeiten[0]["source"] == "stempel" and zeiten[0]["net_minutes"] >= 115 and zeiten[0]["beendet_durch"]
    assert client.get("/api/stempel/aktiv", headers=chef).json()["aktiv"][0]["user_name"] == "Max"
    assert any(e["aktion"] == "stempel.stop" and e["details"].get("grund") for e in client.get("/api/protokoll?limit=50", headers=chef).json()["eintraege"])
    # Konto löschen: dito – die Zeit bleibt beim Arbeitgeber
    assert client.request("DELETE", "/api/auth/konto", json={"password": "geheim456"}, headers=ma2).status_code == 200
    zeiten = client.get(f"/api/zeiten?von={(date.today() - timedelta(days=1)).isoformat()}&bis={heute}&user_id={ma2_d['user']['id']}", headers=chef).json()["eintraege"]
    assert len(zeiten) == 1 and zeiten[0]["net_minutes"] >= 115
    assert client.get("/api/stempel/aktiv", headers=chef).json()["aktiv"] == []


def test_02_gu_abo_kuendigung_zum_periodenende(client):
    s = _aufbau(client)
    abo = client.get(f"/api/projekte/{s['p']['id']}", headers=s["gu"]).json()["projekt"]["gu_abo"]
    assert abo["status"] == "aktiv"   # durch die Einladung der Firma aktiviert
    r = client.post(f"/api/projekte/{s['p']['id']}/gu-abo", json={"aktiv": False}, headers=s["gu"])
    assert r.status_code == 200
    abo = r.json()["gu_abo"]
    monatsende = date.today().replace(day=28) + timedelta(days=4)
    monatsende = monatsende - timedelta(days=monatsende.day)
    assert abo["status"] == "gekuendigt" and abo["endet_am"] == monatsende.isoformat() and abo["zeitraeume"][-1]["bis"] == monatsende.isoformat()
    abos = client.get("/api/firma/abos", headers=s["gu"]).json()
    assert abos["gu_projekte_aktiv"] == 1 and abos["kosten_projekte_monat"] == 50.99 and abos["periode"] == "Kalendermonat"   # bis zum Periodenende kostenpflichtig
    assert client.post(f"/api/projekte/{s['p']['id']}/gu-abo", json={"aktiv": False}, headers=s["gu"]).status_code == 400
    # Kündigung zurücknehmen: wieder aktiv, kein neuer Zeitraum
    r = client.post(f"/api/projekte/{s['p']['id']}/gu-abo", json={"aktiv": True}, headers=s["gu"])
    assert r.status_code == 200 and r.json()["gu_abo"]["status"] == "aktiv" and len(r.json()["gu_abo"]["zeitraeume"]) == 1 and r.json()["gu_abo"]["endet_am"] is None
    # Periodenende überschritten → beendet, nicht mehr kostenpflichtig; Veröffentlichen aktiviert erneut (zweiter Zeitraum)
    client.post(f"/api/projekte/{s['p']['id']}/gu-abo", json={"aktiv": False}, headers=s["gu"])
    gestern = (date.today() - timedelta(days=1)).isoformat()
    asyncio.run(dbmodul.db().projects.update_one({"id": s["p"]["id"]}, {"$set": {"gu_abo.endet_am": gestern}}))
    abos = client.get("/api/firma/abos", headers=s["gu"]).json()
    assert abos["gu_projekte_aktiv"] == 0 and abos["projekte"][0]["gu_abo"]["status"] == "beendet"
    assert client.get(f"/api/projekte/{s['p']['id']}", headers=s["gu"]).json()["projekt"]["gu_abo"]["status"] == "beendet"
    a = client.post(f"/api/projekte/{s['p']['id']}/ausschreibungen", json=TENDER, headers=s["gu"]).json()["ausschreibung"]
    assert client.post(f"/api/ausschreibungen/{a['id']}/veroeffentlichen", headers=s["gu"]).status_code == 200
    abo = client.get(f"/api/projekte/{s['p']['id']}", headers=s["gu"]).json()["projekt"]["gu_abo"]
    assert abo["status"] == "aktiv" and len(abo["zeitraeume"]) == 2 and abo["zeitraeume"][0]["bis"] == gestern
    assert client.get("/api/firma/abos", headers=s["gu"]).json()["fair_use"]["speicher_gb"] == 5


def test_03_email_ausgang_mit_nachweisen(client, monkeypatch):
    gesendet = []
    monkeypatch.setattr(mail, "SOFORT_ZUSTELLEN", False)
    monkeypatch.setattr(mail, "VERSAND", lambda an, betreff, text: gesendet.append((an, betreff, text)))
    chef, chef_d = registrieren(client, email="chef@mail-kern.de", firma="Mail Kern GmbH", name="Anna")
    # Ohne SMTP: Nachweis mit Status nicht_konfiguriert, Einladungslink bleibt in der Antwort
    r = client.post("/api/mitarbeiter", json={"name": "Mia", "email": "mia@mail-kern.de", "role": "mitarbeiter"}, headers=chef)
    assert r.status_code == 200 and r.json()["einladung_link"]
    liste = client.get("/api/firma/emails", headers=chef).json()["emails"]
    assert len(liste) == 1 and liste[0]["an"] == "mia@mail-kern.de" and liste[0]["status"] == "nicht_konfiguriert" and liste[0]["art"] == "mitarbeiter_einladung"
    assert r.json()["einladung_link"].rsplit("/", 1)[-1] in liste[0]["text"]
    # Mit SMTP: Ausgang wird zugestellt; Fehler werden mit Wiederholung gespeichert
    monkeypatch.setattr(config, "SMTP_HOST", "smtp.test")
    monkeypatch.setattr(config, "SMTP_ABSENDER", "noreply@test.de")
    client.post("/api/mitarbeiter", json={"name": "Max", "email": "max@mail-kern.de", "role": "mitarbeiter"}, headers=chef)
    assert asyncio.run(mail.ausgang_abarbeiten()) == 1 and gesendet[-1][0] == "max@mail-kern.de" and "Einladung" in gesendet[-1][1]
    liste = client.get("/api/firma/emails", headers=chef).json()["emails"]
    assert liste[0]["status"] == "gesendet" and liste[0]["gesendet_at"]

    def kaputt(an, betreff, text):
        raise OSError("Verbindung abgelehnt")
    monkeypatch.setattr(mail, "VERSAND", kaputt)
    client.post("/api/mitarbeiter", json={"name": "Moritz", "email": "moritz@mail-kern.de", "role": "mitarbeiter"}, headers=chef)
    assert asyncio.run(mail.ausgang_abarbeiten()) == 0
    e = client.get("/api/firma/emails", headers=chef).json()["emails"][0]
    assert e["status"] == "offen" and e["versuche"] == 1 and "abgelehnt" in e["fehler"]
    # Ausschreibung: Einladung und Einreichungsnachweis per E-Mail; Firma kann den Versand abschalten
    monkeypatch.setattr(mail, "VERSAND", lambda an, betreff, text: gesendet.append((an, betreff, text)))
    assert client.put("/api/firma", json={"art": "beides"}, headers=chef).status_code == 200
    p = projekt(client, chef, name="Halle")
    el, el_d = registrieren(client, email="chef@elektro-mail.de", firma="Elektro Mail", name="Erika")
    a = client.post(f"/api/projekte/{p['id']}/ausschreibungen", json=TENDER, headers=chef).json()["ausschreibung"]
    assert client.post(f"/api/ausschreibungen/{a['id']}/einladungen", json={"firma_ids": [el_d["firma"]["id"]]}, headers=chef).status_code == 200
    assert client.post(f"/api/ausschreibungen/{a['id']}/veroeffentlichen", headers=chef).status_code == 200
    asyncio.run(mail.ausgang_abarbeiten())
    assert any(an == "chef@elektro-mail.de" and "Ausschreibung" in betreff for an, betreff, _ in gesendet)
    g = client.post(f"/api/ausschreibungen/{a['id']}/angebot", json={"preisart": "pauschal", "preis_netto": 1000}, headers=el).json()["angebot"]
    assert client.post(f"/api/angebote/{g['id']}/einreichen", headers=el).status_code == 200
    asyncio.run(mail.ausgang_abarbeiten())
    nachweis = [x for x in client.get("/api/firma/emails", headers=el).json()["emails"] if x["art"] == "angebot_nachweis"]
    assert len(nachweis) == 1 and "1.000,00" in nachweis[0]["text"] and nachweis[0]["status"] == "gesendet"
    assert any(an == "chef@mail-kern.de" and "Angebot" in betreff for an, betreff, _ in gesendet)   # Auftraggeber erfährt vom Angebot
    assert any(x["art"] == "angebot_eingegangen" for x in client.get("/api/firma/emails", headers=chef).json()["emails"])   # Nachweis auch beim Absender
    # Firma schaltet den Versand ab: keine E-Mail mehr an sie (Einladung zu einer zweiten Ausschreibung)
    assert client.put("/api/firma", json={"email_benachrichtigungen": False}, headers=el).status_code == 200
    vorher = len(client.get("/api/firma/emails", headers=el).json()["emails"])
    a2 = client.post(f"/api/projekte/{p['id']}/ausschreibungen", json={**TENDER, "titel": "Sanitär", "gewerk": "Sanitär / Heizung"}, headers=chef).json()["ausschreibung"]
    client.post(f"/api/ausschreibungen/{a2['id']}/einladungen", json={"firma_ids": [el_d["firma"]["id"]]}, headers=chef)
    assert client.post(f"/api/ausschreibungen/{a2['id']}/veroeffentlichen", headers=chef).status_code == 200
    assert len(client.get("/api/firma/emails", headers=el).json()["emails"]) == vorher
    assert client.get("/api/firma/emails", headers={"Authorization": "Bearer x"}).status_code == 401


def test_04_nachtraege(client):
    s = _aufbau(client)
    pid = s["p"]["id"]
    # Firma legt einen Nachtrag an, reicht ihn ein; Auftraggeber sieht ihn, Büro der Firma darf nicht freigeben, Fremde sehen nichts
    r = client.post(f"/api/projekte/{pid}/nachtraege", json={"titel": "Zusätzliche Leitungen Halle B", "beschreibung": "120 m NYM 5x2,5", "grund": "Planänderung AG", "betrag_netto": 2500}, headers=s["el"])
    assert r.status_code == 200, r.text
    n = r.json()["nachtrag"]
    assert n["status"] == "entwurf" and n["nummer"] == "N-001" and n["firma_name"] == "Elektro Kern GmbH"
    assert client.post(f"/api/nachtraege/{n['id']}/entscheiden", json={"freigeben": True}, headers=s["el"]).status_code == 403
    assert client.post(f"/api/nachtraege/{n['id']}/einreichen", headers=s["el_buero"]).status_code == 200
    assert client.get(f"/api/nachtraege/{n['id']}", headers=s["fremd"]).status_code == 404
    assert client.get(f"/api/nachtraege/{n['id']}", headers=s["el_ma"]).status_code == 404
    liste = client.get(f"/api/projekte/{pid}/nachtraege", headers=s["gu"]).json()
    assert liste["rolle"] == "leitung" and liste["nachtraege"][0]["status"] == "eingereicht" and liste["firmen"][0]["name"] == "Elektro Kern GmbH"
    assert any(x["art"] == "nachtrag_eingereicht" for x in client.get("/api/benachrichtigungen", headers=s["gu"]).json()["benachrichtigungen"])
    # Auftraggeber gibt frei: Auftragswert der Beteiligung steigt, Nachtrag trägt vorher/nachher; PDF für beide Seiten
    r = client.post(f"/api/nachtraege/{n['id']}/entscheiden", json={"freigeben": True, "begruendung": "ok"}, headers=s["gu"])
    assert r.status_code == 200 and r.json()["nachtrag"]["status"] == "freigegeben" and r.json()["nachtrag"]["auftragswert_nachher"] == 2500
    liste = client.get(f"/api/projekte/{pid}/nachtraege", headers=s["el"]).json()
    assert liste["rolle"] == "firma" and liste["summe_freigegeben"] == 2500 and liste["firmen"][0]["nachtraege_summe"] == 2500
    pdf = client.get(f"/api/nachtraege/{n['id']}/pdf", headers=s["el"])
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF") and client.get(f"/api/nachtraege/{n['id']}/pdf", headers=s["gu"]).status_code == 200
    assert client.post(f"/api/nachtraege/{n['id']}/entscheiden", json={"freigeben": False, "begruendung": "x"}, headers=s["gu"]).status_code == 400
    # Auftraggeber fragt einen Nachtrag an: Firma trägt den Preis ein und reicht ein; Ablehnung braucht eine Begründung
    r = client.post(f"/api/projekte/{pid}/nachtraege", json={"firma_id": s["el_firma"], "titel": "Notbeleuchtung Treppenhaus", "beschreibung": "6 Leuchten"}, headers=s["gu"])
    assert r.status_code == 200 and r.json()["nachtrag"]["status"] == "angefragt" and r.json()["nachtrag"]["nummer"] == "N-002"
    n2 = r.json()["nachtrag"]
    assert client.post(f"/api/nachtraege/{n2['id']}/einreichen", headers=s["el"]).status_code == 400   # noch kein Betrag
    assert client.put(f"/api/nachtraege/{n2['id']}", json={"titel": n2["titel"], "beschreibung": n2["beschreibung"], "betrag_netto": 900}, headers=s["el"]).status_code == 200
    assert client.post(f"/api/nachtraege/{n2['id']}/einreichen", headers=s["el"]).status_code == 200
    assert client.post(f"/api/nachtraege/{n2['id']}/entscheiden", json={"freigeben": False}, headers=s["gu"]).status_code == 400
    assert client.post(f"/api/nachtraege/{n2['id']}/entscheiden", json={"freigeben": False, "begruendung": "zu teuer"}, headers=s["gu"]).status_code == 200
    assert client.get(f"/api/projekte/{pid}/nachtraege", headers=s["gu"]).json()["summe_freigegeben"] == 2500
    assert client.post(f"/api/nachtraege/{n2['id']}/dokumente", data={"note": "Angebot"}, files={"datei": ("angebot.pdf", b"%PDF-1.4 x", "application/pdf")}, headers=s["el"]).status_code == 200
    d = client.get(f"/api/nachtraege/{n2['id']}", headers=s["gu"]).json()["nachtrag"]["dokumente"][0]
    assert client.get(f"/api/dokumente/{d['id']}/datei", headers=s["gu"]).status_code == 200
    assert client.get(f"/api/dokumente/{d['id']}/datei", headers=s["fremd"]).status_code == 404


def test_05_abnahmen(client):
    s = _aufbau(client)
    pid = s["p"]["id"]
    m = client.post(f"/api/projekte/{pid}/maengel", json={"beschreibung": "Abdeckung fehlt", "bereich": "Halle B", "firma_id": s["el_firma"], "frist": "2026-11-15"}, headers=s["gu"]).json()["mangel"]
    # Firma fordert die Abnahme an; Auftraggeber führt das Protokoll mit offenen Mängeln und schließt ab
    r = client.post(f"/api/projekte/{pid}/abnahmen", json={"art": "teilabnahme", "gewerk": "Elektro", "datum": "2026-11-20", "bemerkung": "Halle B ist fertig"}, headers=s["el"])
    assert r.status_code == 200, r.text
    a = r.json()["abnahme"]
    assert a["status"] == "angefordert" and a["nummer"] == "A-001"
    assert any(x["art"] == "abnahme_angefordert" for x in client.get("/api/benachrichtigungen", headers=s["gu"]).json()["benachrichtigungen"])
    assert client.post(f"/api/abnahmen/{a['id']}/abschliessen", headers=s["gu"]).status_code == 400   # ohne Ergebnis
    d = client.get(f"/api/abnahmen/{a['id']}", headers=s["gu"]).json()
    assert d["rolle"] == "leitung" and [x["id"] for x in d["maengel_offen"]] == [m["id"]]
    r = client.put(f"/api/abnahmen/{a['id']}", json={"art": "teilabnahme", "gewerk": "Elektro", "bereich": "Halle B", "datum": "2026-11-20", "teilnehmer": "G. Leitung, E. Elektro",
                                                   "ergebnis": "abgenommen_mit_maengeln", "vorbehalte": "Abdeckung nachrüsten", "nachbesserung_bis": "2026-11-30", "maengel_ids": [m["id"]]}, headers=s["gu"])
    assert r.status_code == 200 and r.json()["abnahme"]["maengel"][0]["beschreibung"] == "Abdeckung fehlt"
    assert client.put(f"/api/abnahmen/{a['id']}", json={"art": "abnahme", "ergebnis": "abgenommen"}, headers=s["el"]).status_code == 403
    assert client.post(f"/api/abnahmen/{a['id']}/abschliessen", headers=s["gu"]).status_code == 200
    assert client.put(f"/api/abnahmen/{a['id']}", json={"art": "abnahme", "ergebnis": "abgenommen"}, headers=s["gu"]).status_code == 400   # erstellt = unveränderlich
    # Firma bestätigt (Vorarbeiter/Mitarbeiter dürfen nicht), PDF für beide, Fremde 404
    assert client.post(f"/api/abnahmen/{a['id']}/antwort", json={"bestaetigen": True}, headers=s["el_ma"]).status_code == 404
    assert client.post(f"/api/abnahmen/{a['id']}/antwort", json={"bestaetigen": False}, headers=s["el"]).status_code == 400   # Widerspruch ohne Begründung
    r = client.post(f"/api/abnahmen/{a['id']}/antwort", json={"bestaetigen": True, "kommentar": "Nachbesserung bis 30.11."}, headers=s["el_buero"])
    assert r.status_code == 200 and r.json()["abnahme"]["status"] == "bestaetigt"
    pdf = client.get(f"/api/abnahmen/{a['id']}/pdf", headers=s["el"])
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert client.get(f"/api/abnahmen/{a['id']}/pdf", headers=s["fremd"]).status_code == 404
    liste = client.get(f"/api/projekte/{pid}/abnahmen", headers=s["gu"]).json()
    assert liste["abnahmen"][0]["status"] == "bestaetigt" and liste["firmen"][0]["maengel_offen"] == 1


def test_06_projektakte_zip_fuer_beide_seiten(client):
    s = _aufbau(client)
    pid, lokal = s["p"]["id"], s["lokal_id"]
    # Daten auf beiden Seiten: Zeiten + Foto + Rechnung bei der Firma, Aufgabe/Mangel/Bericht/Dokument/Nachtrag/Abnahme auf der Plattform
    zeit(client, s["el_ma"], lokal, date="2026-10-05")
    zeit(client, s["el"], lokal, date="2026-10-06", start="07:00", ende="15:00", pause=30)
    assert client.post(f"/api/projekte/{lokal}/dateien", data={"kategorie": "Fotos", "note": "Verteiler", "date": "2026-10-05"}, files={"datei": ("v.png", _png(), "image/png")}, headers=s["el_ma"]).status_code == 200
    assert client.post(f"/api/projekte/{lokal}/dateien", data={"kategorie": "Auftrag & Angebot", "note": "Auftrag", "ordner": "Vertrag"}, files={"datei": ("auftrag.pdf", b"%PDF-1.4 auftrag", "application/pdf")}, headers=s["el"]).status_code == 200
    assert client.post("/api/rechnungen/anlegen", json={"project_id": lokal, "year": 2026, "month": 10}, headers=s["el"]).status_code == 200
    assert client.post(f"/api/projekte/{pid}/aufgaben", json={"titel": "Trassen Halle B", "firma_id": s["el_firma"], "datum": "2026-10-05"}, headers=s["gu"]).status_code == 200
    client.post(f"/api/projekte/{pid}/maengel", json={"beschreibung": "Abdeckung fehlt", "firma_id": s["el_firma"]}, headers=s["gu"])
    client.post(f"/api/projekte/{pid}/tagesberichte", json={"datum": "2026-10-05", "taetigkeiten": "Trassen montiert", "mitarbeiter_anzahl": 2, "firmen": ["Elektro Kern GmbH"]}, headers=s["el"])
    client.post(f"/api/projekte/{pid}/dokumente", data={"kategorie": "Baupläne", "note": "Grundriss", "fuer_alle": "true"}, files={"datei": ("plan.pdf", b"%PDF-1.4 plan", "application/pdf")}, headers=s["gu"])
    client.post(f"/api/projekte/{pid}/dokumente", data={"kategorie": "Sonstiges", "note": "intern"}, files={"datei": ("intern.pdf", b"%PDF-1.4 intern", "application/pdf")}, headers=s["gu"])
    n = client.post(f"/api/projekte/{pid}/nachtraege", json={"titel": "Mehr Leitungen", "beschreibung": "x", "betrag_netto": 500}, headers=s["el"]).json()["nachtrag"]
    client.post(f"/api/nachtraege/{n['id']}/einreichen", headers=s["el"])
    client.post(f"/api/nachtraege/{n['id']}/entscheiden", json={"freigeben": True}, headers=s["gu"])
    a = client.post(f"/api/projekte/{pid}/abnahmen", json={"firma_id": s["el_firma"], "art": "abnahme", "datum": "2026-11-20", "ergebnis": "abgenommen"}, headers=s["gu"]).json()["abnahme"]
    client.post(f"/api/abnahmen/{a['id']}/abschliessen", headers=s["gu"])
    # Firma (Partnerseite): eigene Daten plus eigene Plattform-Unterlagen – das interne Dokument des Auftraggebers fehlt
    assert client.post(f"/api/projekte/{lokal}/projektakte", headers=s["el_ma"]).status_code == 403
    r = client.post(f"/api/projekte/{lokal}/projektakte", headers=s["el"])
    assert r.status_code == 200, r.text
    akte = r.json()["projektakte"]
    assert akte["rolle"] == "beteiligt" and akte["size"] > 0 and akte["aufbewahren_bis"][:4] == str(date.today().year + 10)
    z = client.get(f"/api/projektakten/{akte['id']}.zip", headers=s["el"])
    assert z.status_code == 200
    namen = zipfile.ZipFile(io.BytesIO(z.content)).namelist()
    assert "00_LIESMICH.txt" in namen and "02_Zeiten/zeiten.csv" in namen and "02_Zeiten/Stundennachweis_2026-10.pdf" in namen
    assert any(x.startswith("03_Fotos/Milan Monteur/2026-10-05/") for x in namen) and "04_Dokumente/Vertrag/auftrag.pdf" in namen
    assert any(x.startswith("05_Rechnungen/") and x.endswith(".pdf") for x in namen) and "05_Rechnungen/rechnungen.csv" in namen
    assert "08_Zusammenarbeit/aufgaben.csv" in namen and "08_Zusammenarbeit/maengel.csv" in namen and "08_Zusammenarbeit/Dokumente/Baupläne/plan.pdf" in namen
    assert not any("intern.pdf" in x for x in namen) and "08_Zusammenarbeit/beteiligte_firmen.csv" not in namen
    assert any(x.startswith("09_Nachtraege/N-001") and x.endswith(".pdf") for x in namen) and any(x.startswith("10_Abnahmen/A-001") and x.endswith(".pdf") for x in namen)
    assert any(x.startswith("08_Zusammenarbeit/Bautagesberichte/") for x in namen) and "11_Protokoll/protokoll.csv" in namen
    csvtext = zipfile.ZipFile(io.BytesIO(z.content)).read("02_Zeiten/zeiten.csv").decode("utf-8")
    assert "Milan Monteur" in csvtext and "2026-10-06" in csvtext
    # Auftraggeber: alle für ihn sichtbaren Unterlagen der Firmen, aber keine Zeiten/Rechnungen der Partnerfirma
    r = client.post(f"/api/projekte/{pid}/projektakte", headers=s["gu"])
    assert r.status_code == 200, r.text
    namen = zipfile.ZipFile(io.BytesIO(client.get(f"/api/projektakten/{r.json()['projektakte']['id']}.zip", headers=s["gu"]).content)).namelist()
    assert "08_Zusammenarbeit/beteiligte_firmen.csv" in namen and any("intern.pdf" in x for x in namen) and "08_Zusammenarbeit/aufgaben.csv" in namen
    assert not any(x.startswith("05_Rechnungen/") for x in namen) and "02_Zeiten/zeiten.csv" not in namen
    # Liste, Löschen (nur Inhaber; vor Ablauf nur ausdrücklich), kostenlose Teilnahme ohne GU-Abo → 402
    liste = client.get("/api/projektakten", headers=s["el"]).json()
    assert len(liste["projektakten"]) == 1 and liste["aufbewahrung_jahre"] == 10
    assert client.get(f"/api/projekte/{lokal}/projektakten", headers=s["el_buero"]).json()["projektakten"][0]["id"] == akte["id"]
    assert client.delete(f"/api/projektakten/{akte['id']}", headers=s["el_buero"]).status_code == 403
    assert client.delete(f"/api/projektakten/{akte['id']}", headers=s["el"]).status_code == 400
    assert client.delete(f"/api/projektakten/{akte['id']}?erzwingen=true", headers=s["el"]).status_code == 200
    assert client.get(f"/api/projektakten/{akte['id']}.zip", headers=s["el"]).status_code == 404
    asyncio.run(dbmodul.db().firmen.update_one({"id": s["el_firma"]}, {"$set": {"plan.test_bis": (jetzt() - timedelta(days=1)).isoformat()}}))
    assert client.post(f"/api/projekte/{lokal}/projektakte", headers=s["el"]).status_code == 402
    assert client.post(f"/api/projekte/{pid}/projektakte", headers=s["gu"]).status_code == 200   # GU-Projekt: auch ohne Firmenabo


def test_07_startseite_aufgaben_projektleiter_verifizierung_unterauftrag(client):
    s = _aufbau(client)
    pid = s["p"]["id"]
    n = client.post(f"/api/projekte/{pid}/nachtraege", json={"titel": "x", "beschreibung": "x", "betrag_netto": 100}, headers=s["el"]).json()["nachtrag"]
    client.post(f"/api/nachtraege/{n['id']}/einreichen", headers=s["el"])
    a = client.post(f"/api/projekte/{pid}/abnahmen", json={"firma_id": s["el_firma"], "art": "abnahme", "datum": "2026-11-20", "ergebnis": "abgenommen"}, headers=s["gu"]).json()["abnahme"]
    client.post(f"/api/abnahmen/{a['id']}/abschliessen", headers=s["gu"])
    punkte = client.get("/api/dashboard/aufgaben", headers=s["gu"]).json()["punkte"]
    assert any(p["art"] == "nachtraege_eingereicht" and p["anzahl"] == 1 for p in punkte)
    punkte = client.get("/api/dashboard/aufgaben", headers=s["el"]).json()["punkte"]
    assert any(p["art"] == "abnahmen_bestaetigen" and p["anzahl"] == 1 for p in punkte)
    assert client.get("/api/dashboard/aufgaben", headers=s["el_ma"]).status_code == 200
    # Projektleiter-Übersicht: Büro-Nutzer mit ihren Projekten
    pl, pl_d = einladen(client, s["gu"], name="Paula Projektleiterin", email="paula@gu-kern.de", role="buero")
    assert client.post(f"/api/projekte/{pid}/leiter", json={"user_id": pl_d["user"]["id"], "funktion": "Projektleitung"}, headers=s["gu"]).status_code == 200
    u = client.get("/api/firma/projektleiter", headers=s["gu"]).json()
    paula = next(x for x in u["nutzer"] if x["name"] == "Paula Projektleiterin")
    assert paula["projekte"][0]["name"] == "Logistikhalle Nord" and u["projekte"][0]["leiter_ids"] == [pl_d["user"]["id"]]
    assert client.get("/api/firma/projektleiter", headers=s["el_ma"]).status_code == 403
    # Verifizierung durch den Betreiber: sichtbar im Verzeichnis und bei der Firma
    assert client.post("/api/admin/verifizieren", json={"email": "chef@elektro-kern.de", "verifiziert": True, "hinweis": "Handelsregister geprüft"}, headers=ADMIN).status_code == 200
    assert client.post("/api/admin/verifizieren", json={"email": "chef@elektro-kern.de", "verifiziert": True}).status_code == 403
    assert client.get("/api/auth/ich", headers=s["el"]).json()["firma"]["verifiziert"]["status"] is True
    client.put("/api/firma/verzeichnis", json={"sichtbar": True, "gewerke": ["Elektro"]}, headers=s["el"])
    eintrag = next(f for f in client.get("/api/verzeichnis/firmen?q=Elektro", headers=s["gu"]).json()["firmen"] if f["name"] == "Elektro Kern GmbH")
    assert eintrag["verifiziert"] is True
    # Unterauftrag: die beauftragte Firma lädt zu ihrem verknüpften Projekt eine eigene Subfirma ein (Kette), der Auftraggeber sieht davon nichts
    sub, sub_d = registrieren(client, email="chef@sub-kern.de", firma="Sub Kern", name="Sven")
    r = client.post(f"/api/projekte/{s['lokal_id']}/beteiligungen", json={"firma_id": sub_d["firma"]["id"], "gewerk": "Elektro"}, headers=s["el"])
    assert r.status_code == 200, r.text
    r2 = client.post(f"/api/beteiligungen/{r.json()['beteiligung']['id']}/antwort", json={"annehmen": True}, headers=sub)
    assert r2.status_code == 200 and r2.json()["beteiligung"]["lokales_project_id"]
    assert client.get(f"/api/projekte/{s['lokal_id']}", headers=s["gu"]).status_code == 404
    assert client.get(f"/api/projekte/{s['lokal_id']}", headers=s["el"]).json()["projekt"]["gu_abo"] is None   # Betriebe zahlen für Unteraufträge nichts
