"""Plattform: Zusammenarbeit mehrerer Firmen – Definition-of-Done-Szenario, Einladungen, Projektleiter, Berechtigungen (2026-10-23)."""
import io

from PIL import Image

from conftest import einladen, projekt, registrieren, zeit


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (320, 200), (30, 90, 160)).save(buf, "PNG")
    return buf.getvalue()


def test_01_definition_of_done_szenario(client):
    # 1–2: GOLDBECK registriert sich, Administratorin meldet sich an (Token aus der Registrierung)
    gu, gu_daten = registrieren(client, email="admin@goldbeck-test.de", firma="GOLDBECK Test GmbH", name="Gabi Admin")
    assert client.put("/api/firma", json={"city": "Bielefeld", "street": "Ummelner Str. 4", "zip_code": "33649"}, headers=gu).status_code == 200
    # 3: zwei Projektleiter anlegen (Büro-Rolle und Vorarbeiter-Rolle), dazu ein dritter, der NICHT zugeordnet wird
    pl1_kopf, pl1 = einladen(client, gu, name="Max Müller", email="mueller@goldbeck-test.de", role="buero", passwort="leitung12345")
    pl2_kopf, pl2 = einladen(client, gu, name="Thomas Schmidt", email="schmidt@goldbeck-test.de", role="vorarbeiter", passwort="leitung12345")
    pl3_kopf, pl3 = einladen(client, gu, name="Peter Weber", email="weber@goldbeck-test.de", role="vorarbeiter", passwort="leitung12345")
    # 4: Projektleiter 1 erstellt das Projekt
    p = projekt(client, pl1_kopf, name="Logistikzentrum Hannover", address="Hafenstraße 1, Hannover")
    # 5: beide Projektleiter zuordnen
    assert client.post(f"/api/projekte/{p['id']}/leiter", json={"user_id": pl1["user"]["id"], "funktion": "Hauptprojektleiter"}, headers=gu).status_code == 200
    assert client.post(f"/api/projekte/{p['id']}/leiter", json={"user_id": pl2["user"]["id"], "funktion": "Bauleiter"}, headers=gu).status_code == 200
    assert [l["user_name"] for l in client.get(f"/api/projekte/{p['id']}/leiter", headers=gu).json()["leiter"]] == ["Max Müller", "Thomas Schmidt"]
    assert client.post(f"/api/projekte/{p['id']}/leiter", json={"user_id": "gibt-es-nicht"}, headers=gu).status_code == 400

    # Elektrofirma registriert sich, schaltet sich im Verzeichnis sichtbar, hat Vorarbeiter und Mitarbeiter
    el, el_daten = registrieren(client, email="chef@elektro-mustermann.de", firma="Elektro Mustermann GmbH", name="Erika Mustermann")
    client.put("/api/firma", json={"city": "Hannover"}, headers=el)
    assert client.put("/api/firma/verzeichnis", json={"sichtbar": True, "gewerke": ["Elektro"], "beschreibung": "Elektroinstallation Industrie", "ort": "Hannover"}, headers=el).status_code == 200
    el_vor_kopf, el_vor = einladen(client, el, name="Ali Yilmaz", email="yilmaz@elektro-mustermann.de", role="vorarbeiter", passwort="vorarbeit123")
    el_ma_kopf, el_ma = einladen(client, el, name="Jonas Koch", email="koch@elektro-mustermann.de", role="mitarbeiter", passwort="mitarbeit123")

    # 6: Firmensuche im Verzeichnis (nur sichtbare Firmen, nur freigegebene Felder)
    treffer = client.get("/api/verzeichnis/firmen?q=mustermann", headers=pl1_kopf).json()["firmen"]
    assert [t["name"] for t in treffer] == ["Elektro Mustermann GmbH"] and treffer[0]["gewerke"] == ["Elektro"] and set(treffer[0]) == {"id", "name", "ort", "gewerke", "beschreibung", "art"}
    assert client.get("/api/verzeichnis/firmen?q=goldbeck", headers=el).json()["firmen"] == []     # GOLDBECK ist nicht sichtbar geschaltet

    # 7: Projektleiter 2 (Vorarbeiter-Rolle, aber Projektleitung) lädt die Firma ein; doppelt geht nicht
    r = client.post(f"/api/projekte/{p['id']}/beteiligungen", json={"firma_id": treffer[0]["id"], "gewerk": "Elektro", "rolle": "subunternehmer"}, headers=pl2_kopf)
    assert r.status_code == 200, r.text
    bet = r.json()["beteiligung"]
    assert bet["status"] == "eingeladen" and "token" not in bet and "/projekteinladung/" in bet["einladung_link"]
    assert client.post(f"/api/projekte/{p['id']}/beteiligungen", json={"firma_id": treffer[0]["id"]}, headers=pl2_kopf).status_code == 409
    assert client.post(f"/api/projekte/{p['id']}/beteiligungen", json={"firma_id": treffer[0]["id"]}, headers=pl3_kopf).status_code == 404   # nicht zugeordnet

    # 8: Firmenadministratorin sieht die Einladung und nimmt an
    offen = client.get("/api/beteiligungen", headers=el).json()
    assert len(offen["einladungen"]) == 1 and offen["einladungen"][0]["projekt"]["name"] == "Logistikzentrum Hannover"
    assert offen["einladungen"][0]["auftraggeber"]["name"] == "GOLDBECK Test GmbH"
    assert client.post(f"/api/beteiligungen/{bet['id']}/antwort", json={"annehmen": True}, headers=el_ma_kopf).status_code == 403   # Mitarbeiter darf nicht
    r = client.post(f"/api/beteiligungen/{bet['id']}/antwort", json={"annehmen": True}, headers=el)
    assert r.status_code == 200, r.text
    lokal_id = r.json()["beteiligung"]["lokales_project_id"]

    # 9: Das Projekt erscheint im Konto der Elektrofirma als verknüpftes eigenes Projekt
    lokal = next(x for x in client.get("/api/projekte", headers=el).json()["projekte"] if x["id"] == lokal_id)
    assert lokal["name"] == "GOLDBECK Test GmbH: Logistikzentrum Hannover" and lokal["verknuepft"]["project_id"] == p["id"]
    assert lokal["customer_name"] == "GOLDBECK Test GmbH" and "Bielefeld" in lokal["customer_address"]
    assert [b["status"] for b in client.get(f"/api/projekte/{p['id']}/beteiligungen", headers=pl1_kopf).json()["beteiligungen"]] == ["aktiv"]

    # 10: Die Elektrofirma ordnet dem Projekt eigene Mitarbeiter zu und setzt ihren Stundensatz
    r = client.put(f"/api/projekte/{lokal_id}", json={"name": lokal["name"], "customer_name": lokal["customer_name"], "customer_address": lokal["customer_address"],
                                                      "employee_ids": [el_vor["user"]["id"], el_ma["user"]["id"]], "hourly_rate": 42}, headers=el)
    assert r.status_code == 200, r.text
    assert r.json()["projekt"]["verknuepft"]["project_id"] == p["id"]   # Verknüpfung bleibt beim Bearbeiten erhalten

    # 11: GOLDBECK erstellt eine Aufgabe für die Elektrofirma
    r = client.post(f"/api/projekte/{p['id']}/aufgaben", json={"titel": "Kabeltrassen in Halle B montieren", "beschreibung": "Trasse 3 bis 7", "gewerk": "Elektro",
                                                               "firma_id": el_daten["firma"]["id"], "datum": "2026-10-26", "start_time": "07:00", "end_time": "15:30",
                                                               "prioritaet": "hoch", "bereich": "Halle B"}, headers=pl1_kopf)
    assert r.status_code == 200, r.text
    aufgabe = r.json()["aufgabe"]
    assert aufgabe["status"] == "zugewiesen" and aufgabe["firma_name"] == "Elektro Mustermann GmbH"
    assert client.post(f"/api/projekte/{p['id']}/aufgaben", json={"titel": "x", "datum": "2026-10-26", "firma_id": "fremd"}, headers=pl1_kopf).status_code == 400

    # 12: Der Vorarbeiter der Elektrofirma sieht die Aufgabe und teilt den Mitarbeiter zu
    meine = client.get("/api/aufgaben/meine", headers=el_vor_kopf).json()["aufgaben"]
    assert [a["titel"] for a in meine] == ["Kabeltrassen in Halle B montieren"] and meine[0]["projekt"]["auftraggeber"] == "GOLDBECK Test GmbH"
    assert client.post(f"/api/aufgaben/{aufgabe['id']}/zuteilung", json={"vorarbeiter_user_id": el_vor["user"]["id"], "mitarbeiter_ids": [el_ma["user"]["id"]]}, headers=el_vor_kopf).status_code == 200
    assert client.post(f"/api/aufgaben/{aufgabe['id']}/zuteilung", json={"mitarbeiter_ids": [pl1["user"]["id"]]}, headers=el_vor_kopf).status_code == 400   # fremde Nutzer nicht
    assert client.get("/api/aufgaben/meine", headers=el_ma_kopf).json()["aufgaben"][0]["id"] == aufgabe["id"]

    # 13: Mitarbeiter dokumentiert: Status, Foto, Einreichen; Partner darf nicht abnehmen
    assert client.post(f"/api/aufgaben/{aufgabe['id']}/status", json={"status": "in_bearbeitung"}, headers=el_ma_kopf).status_code == 200
    r = client.post(f"/api/aufgaben/{aufgabe['id']}/fotos", data={"note": "Trasse 3 fertig"}, files={"datei": ("t3.png", _png(), "image/png")}, headers=el_ma_kopf)
    assert r.status_code == 200, r.text
    foto = r.json()["dokument"]
    assert client.post(f"/api/aufgaben/{aufgabe['id']}/status", json={"status": "eingereicht", "kommentar": "Fertig"}, headers=el_ma_kopf).status_code == 200
    assert client.post(f"/api/aufgaben/{aufgabe['id']}/status", json={"status": "abgenommen"}, headers=el_vor_kopf).status_code == 403

    # 14: Zeiten im lokalen Projekt der Elektrofirma (Woche ab Montag 19.10.)
    zeit(client, el_ma_kopf, lokal_id, date="2026-10-19", start="07:00", ende="15:30", pause=30)
    zeit(client, el_vor_kopf, lokal_id, date="2026-10-20", start="07:00", ende="12:00", user_id=el_vor["user"]["id"])

    # 15–16: Wochenstundenzettel-Daten wie bisher, Freigabe der Woche für GOLDBECK, Projektleitung sieht den Nachweis
    m = client.get(f"/api/projekte/{lokal_id}/monat?jahr=2026&monat=10", headers=el).json()
    assert len([e for e in m["eintraege"] if e["date"] in ("2026-10-19", "2026-10-20")]) == 2
    assert client.post(f"/api/projekte/{lokal_id}/freigaben", json={"week_monday": "2026-10-20"}, headers=el).status_code == 400        # kein Montag
    assert client.post(f"/api/projekte/{lokal_id}/freigaben", json={"week_monday": "2026-10-19"}, headers=el).status_code == 200
    assert client.get(f"/api/projekte/{p['id']}/nachweise", headers=gu).json()["nachweise"][0]["minuten"] == 480 + 300
    n = client.get(f"/api/projekte/{p['id']}/nachweise", headers=pl2_kopf).json()["nachweise"]
    assert len(n) == 1 and n[0]["firma_name"] == "Elektro Mustermann GmbH" and {z["user_name"] for z in n[0]["zeiten"]} == {"Jonas Koch", "Ali Yilmaz"}
    assert client.get(f"/api/projekte/{p['id']}/nachweise", headers=el).status_code == 403   # Partner sieht nur eigene Freigabe-Liste
    assert len(client.get(f"/api/projekte/{lokal_id}/freigaben", headers=el).json()["freigaben"]) == 1

    # Projektleitung nimmt die Aufgabe ab, sieht Verlauf und Foto
    assert client.post(f"/api/aufgaben/{aufgabe['id']}/status", json={"status": "abgenommen"}, headers=pl2_kopf).status_code == 200
    detail = client.get(f"/api/aufgaben/{aufgabe['id']}", headers=pl1_kopf).json()
    assert detail["aufgabe"]["status"] == "abgenommen" and len(detail["fotos"]) == 1
    assert [s["status"] for s in detail["aufgabe"]["verlauf"]] == ["zugewiesen", "in_bearbeitung", "eingereicht", "abgenommen"]
    assert client.get(f"/api/dokumente/{foto['id']}/bild?max=100", headers=pl1_kopf).status_code == 200
    assert client.delete(f"/api/dokumente/{foto['id']}", headers=gu).status_code == 403          # fremdes Foto löschen geht nicht

    # Anwesenheit: Zahlen immer, Namen fremder Firmen erst nach Freigabe
    a = client.get(f"/api/projekte/{p['id']}/anwesenheit", headers=pl1_kopf).json()
    el_zeile = next(f for f in a["firmen"] if f["name"] == "Elektro Mustermann GmbH")
    assert el_zeile["namen_freigegeben"] is False and el_zeile["namen_heute"] == [] and a["gesamt"]["geplant"] == 0
    assert client.put(f"/api/beteiligungen/{bet['id']}/freigaben", json={"namen": True}, headers=el).status_code == 200
    assert next(f for f in client.get(f"/api/projekte/{p['id']}/anwesenheit", headers=pl1_kopf).json()["firmen"] if f["name"] == "Elektro Mustermann GmbH")["namen_freigegeben"] is True

    # 17: Die Elektrofirma stellt ihre Monatsrechnung im eigenen Konto (Kunde = GOLDBECK), GOLDBECK sieht sie nicht
    inv = client.post("/api/rechnungen/anlegen", json={"project_id": lokal_id, "year": 2026, "month": 10}, headers=el).json()["rechnung"]
    assert inv["net"] == round((480 + 300) / 60 * 42, 2)
    assert client.get("/api/rechnungen", headers=gu).json()["rechnungen"] == []

    # 18: Personal- und Lohndaten der Elektrofirma bleiben für GOLDBECK unsichtbar
    assert client.get(f"/api/mitarbeiter/{el_ma['user']['id']}/lohndaten", headers=gu).status_code == 404
    assert client.get(f"/api/mitarbeiter/{el_ma['user']['id']}", headers=gu).status_code == 404
    assert client.get(f"/api/projekte/{lokal_id}/monat?jahr=2026&monat=10", headers=gu).status_code == 404
    assert all(x["name"] != "Jonas Koch" for x in client.get("/api/lohn/vorbereitung?jahr=2026&monat=10", headers=gu).json()["mitarbeiter"])

    # 19: Ein nicht zugeordneter Projektleiter sieht das Projekt nicht
    assert client.get(f"/api/projekte/{p['id']}/aufgaben", headers=pl3_kopf).status_code == 404
    assert client.get(f"/api/projekte/{p['id']}/monat?jahr=2026&monat=10", headers=pl3_kopf).status_code == 404
    assert all(x["id"] != p["id"] for x in client.get("/api/projekte", headers=pl3_kopf).json()["projekte"])
    assert any(x["id"] == p["id"] for x in client.get("/api/projekte", headers=pl2_kopf).json()["projekte"])

    # 20: Eine unbeteiligte Firma kommt an keine Projektdaten, auch nicht mit bekannten IDs
    fremd, _ = registrieren(client, email="chef@abc-trockenbau.de", firma="ABC Trockenbau", name="Bodo Bauer")
    for pfad in (f"/api/projekte/{p['id']}/aufgaben", f"/api/projekte/{p['id']}/anwesenheit", f"/api/projekte/{p['id']}/nachweise",
                 f"/api/aufgaben/{aufgabe['id']}", f"/api/projekte/{p['id']}/beteiligungen", f"/api/projekte/{p['id']}/leiter"):
        assert client.get(pfad, headers=fremd).status_code == 404, pfad
    assert client.get(f"/api/dokumente/{foto['id']}/bild", headers=fremd).status_code == 404
    assert client.post(f"/api/aufgaben/{aufgabe['id']}/status", json={"status": "in_bearbeitung"}, headers=fremd).status_code == 404
    assert client.post(f"/api/projekte/{p['id']}/aufgaben", json={"titel": "x", "datum": "2026-10-26"}, headers=fremd).status_code == 404

    # Übersicht und Benachrichtigungen
    ue = client.get("/api/plattform/uebersicht", headers=gu).json()
    assert ue["projekte"][0]["firmen"] == 1 and ue["projekte"][0]["leiter"] == 2 and ue["projekte"][0]["aufgaben_offen"] == 0
    arten = {x["art"] for x in client.get("/api/benachrichtigungen", headers=el).json()["benachrichtigungen"]}
    assert {"projekteinladung", "aufgabe_neu", "aufgabe_abgenommen"} <= arten
    arten_gu = {x["art"] for x in client.get("/api/benachrichtigungen", headers=pl1_kopf).json()["benachrichtigungen"]}
    assert {"projektleitung", "einladung_angenommen", "aufgabe_eingereicht", "nachweis_freigegeben"} <= arten_gu
    assert client.post("/api/benachrichtigungen/alle-gelesen", headers=pl1_kopf).status_code == 200
    assert client.get("/api/benachrichtigungen", headers=pl1_kopf).json()["ungelesen"] == 0
    prot = client.get("/api/exporte/protokoll.csv", headers=gu).text
    assert "projekt.firma_eingeladen" in prot and "projekt.firma_beigetreten" in prot


def test_02_einladung_per_link_ablehnen_und_entfernen(client):
    gu, _ = registrieren(client, email="admin@gu-test.de", firma="GU Test", name="Gabi")
    p = projekt(client, gu, name="Bürogebäude Braunschweig")
    # Einladung an eine noch nicht registrierte Firma per E-Mail → Link
    r = client.post(f"/api/projekte/{p['id']}/beteiligungen", json={"firma_name": "Montage Nord", "email": "chef@montage-nord.de", "gewerk": "Montage"}, headers=gu)
    assert r.status_code == 200, r.text
    token = r.json()["beteiligung"]["einladung_link"].rsplit("/", 1)[-1]
    assert client.post(f"/api/projekte/{p['id']}/beteiligungen", json={"firma_name": "Montage Nord", "email": "chef@montage-nord.de"}, headers=gu).status_code == 409
    assert client.post(f"/api/projekte/{p['id']}/beteiligungen", json={"firma_name": "Ohne Mail"}, headers=gu).status_code == 422
    # Firma registriert sich später und löst den Link ein; danach ist er verbraucht
    mn, _ = registrieren(client, email="chef@montage-nord.de", firma="Montage Nord GmbH", name="Nina Nord")
    r = client.post("/api/beteiligungen/token", json={"token": token}, headers=mn)
    assert r.status_code == 200 and r.json()["beteiligung"]["status"] == "aktiv" and r.json()["beteiligung"]["firma"]["name"] == "Montage Nord GmbH"
    assert client.post("/api/beteiligungen/token", json={"token": token}, headers=mn).status_code == 404
    lokal_id = r.json()["beteiligung"]["lokales_project_id"]
    assert client.get(f"/api/projekte/{p['id']}/aufgaben", headers=mn).status_code == 200
    # Einladung an eine registrierte Firma per E-Mail bindet die Firma; andere Firmen können den Link nicht nutzen; Ablehnen
    dach, _ = registrieren(client, email="chef@dach-test.de", firma="Dach AG", name="Dora Dach")
    r = client.post(f"/api/projekte/{p['id']}/beteiligungen", json={"firma_name": "Dach", "email": "chef@dach-test.de", "gewerk": "Dach"}, headers=gu)
    assert r.status_code == 200 and r.json()["beteiligung"]["firma"]["name"] == "Dach AG"
    token2 = r.json()["beteiligung"]["einladung_link"].rsplit("/", 1)[-1]
    fremd, _ = registrieren(client, email="x@fremd-test.de", firma="Fremd GmbH", name="Frank Fremd")
    assert client.post("/api/beteiligungen/token", json={"token": token2}, headers=fremd).status_code == 403
    bid = r.json()["beteiligung"]["id"]
    assert client.post(f"/api/beteiligungen/{bid}/antwort", json={"annehmen": False}, headers=dach).status_code == 200
    stati = {b["firma"]["name"]: b["status"] for b in client.get(f"/api/projekte/{p['id']}/beteiligungen", headers=gu).json()["beteiligungen"]}
    assert stati == {"Montage Nord GmbH": "aktiv", "Dach AG": "abgelehnt"}
    # Entfernen: Zugriff endet, lokales Projekt bleibt der Partnerfirma erhalten, Freigaben gehen nicht mehr
    aktiv = client.get(f"/api/projekte/{p['id']}/beteiligungen", headers=gu).json()["beteiligungen"]
    mn_bid = next(b["id"] for b in aktiv if b["status"] == "aktiv")
    assert client.delete(f"/api/projekte/{p['id']}/beteiligungen/{mn_bid}", headers=gu).status_code == 200
    assert client.get(f"/api/projekte/{p['id']}/aufgaben", headers=mn).status_code == 404
    lokal = client.get(f"/api/projekte/{lokal_id}/monat?jahr=2026&monat=10", headers=mn)
    assert lokal.status_code == 200 and lokal.json()["projekt"]["verknuepft"]["status"] == "entfernt"
    assert client.post(f"/api/projekte/{lokal_id}/freigaben", json={"week_monday": "2026-10-19"}, headers=mn).status_code == 400
    assert client.get("/api/beteiligungen", headers=mn).json()["aktiv"] == []


def test_03_projektleiter_sichtbarkeit_und_bestand(client):
    kopf, chef = registrieren(client)
    vor_kopf, vor = einladen(client, kopf, name="Vera Vorarbeiterin", email="vera@beispiel.de", role="vorarbeiter")
    p = projekt(client, kopf, name="Objekt A", employee_ids=[chef["user"]["id"]])    # Vera ist nicht zugewiesen
    assert client.get(f"/api/projekte/{p['id']}/monat?jahr=2026&monat=10", headers=vor_kopf).status_code == 404
    assert client.post(f"/api/projekte/{p['id']}/leiter", json={"user_id": vor["user"]["id"], "funktion": "Bauleitung"}, headers=kopf).status_code == 200
    assert client.get(f"/api/projekte/{p['id']}/monat?jahr=2026&monat=10", headers=vor_kopf).status_code == 200      # als Projektleitung sichtbar
    assert client.post(f"/api/projekte/{p['id']}/aufgaben", json={"titel": "Begehung", "datum": "2026-10-28"}, headers=vor_kopf).status_code == 200
    assert client.delete(f"/api/projekte/{p['id']}/leiter/{vor['user']['id']}", headers=kopf).status_code == 200
    assert client.get(f"/api/projekte/{p['id']}/monat?jahr=2026&monat=10", headers=vor_kopf).status_code == 404      # Zugriff endet
    # Bestand: normales Projekt ohne Plattformbezug funktioniert wie bisher (keine Übersichtskarte, keine Beteiligungen)
    assert client.get("/api/plattform/uebersicht", headers=kopf).json()["projekte"] == []
    assert client.get(f"/api/projekte/{p['id']}/beteiligungen", headers=kopf).json()["beteiligungen"] == []
