"""Phase 5: Lieferungen, Mängel, Bautagesberichte (PDF), Meilensteine, geteilte Dokumente, Plattform-Kalender – 2026-10-23."""
import io

from PIL import Image

from conftest import einladen, projekt, registrieren


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (300, 200), (90, 140, 60)).save(buf, "PNG")
    return buf.getvalue()


def _aufbau(client):
    """GU mit Projekt, Partnerfirma mit Vorarbeiter, Beteiligung aktiv."""
    gu, gu_daten = registrieren(client, email="admin@gu-test.de", firma="GU Bau GmbH", name="Gabi Leitung")
    p = projekt(client, gu, name="Produktionshalle Wolfsburg", address="Werkstraße 9")
    el, el_daten = registrieren(client, email="chef@elektro-test.de", firma="Elektro Test GmbH", name="Erik Elektro")
    vor_kopf, vor = einladen(client, el, name="Vera Vorarbeiterin", email="vera@elektro-test.de", role="vorarbeiter")
    ma_kopf, ma = einladen(client, el, name="Milan Monteur", email="milan@elektro-test.de", role="mitarbeiter")
    bet = client.post(f"/api/projekte/{p['id']}/beteiligungen", json={"firma_id": el_daten["firma"]["id"], "gewerk": "Elektro"}, headers=gu).json()["beteiligung"]
    lokal_id = client.post(f"/api/beteiligungen/{bet['id']}/antwort", json={"annehmen": True}, headers=el).json()["beteiligung"]["lokales_project_id"]
    client.put(f"/api/projekte/{lokal_id}", json={"name": "GU: Halle", "employee_ids": [vor["user"]["id"], ma["user"]["id"]]}, headers=el)
    fremd, _ = registrieren(client, email="x@fremd-test.de", firma="Fremd", name="Frank")
    return {"gu": gu, "p": p, "el": el, "el_firma": el_daten["firma"]["id"], "vor": vor_kopf, "ma": ma_kopf, "lokal_id": lokal_id, "fremd": fremd}


def test_01_lieferungen(client):
    s = _aufbau(client)
    r = client.post(f"/api/projekte/{s['p']['id']}/lieferungen", json={"material": "Kabeltrassen 200 m", "menge": "20 Paletten", "lieferant": "OBO", "firma_id": s["el_firma"],
                                                                        "geplant_am": "2026-10-27", "zeitfenster_von": "07:00", "zeitfenster_bis": "09:00", "entladeort": "Tor 3"}, headers=s["gu"])
    assert r.status_code == 200, r.text
    l = r.json()["lieferung"]
    assert l["status"] == "angefragt" and l["firma_name"] == "Elektro Test GmbH"
    # Partnerfirma (Vorarbeiterin) sieht die Lieferung, bestätigt, meldet Verspätung, lädt Lieferschein hoch; abschließen darf nur die Leitung
    liste = client.get(f"/api/projekte/{s['p']['id']}/lieferungen?von=2026-10-01&bis=2026-10-31", headers=s["vor"]).json()
    assert [x["id"] for x in liste["lieferungen"]] == [l["id"]] and liste["leitung"] is False
    assert client.post(f"/api/lieferungen/{l['id']}/status", json={"status": "bestaetigt"}, headers=s["vor"]).status_code == 200
    assert client.post(f"/api/lieferungen/{l['id']}/status", json={"status": "abgeschlossen"}, headers=s["vor"]).status_code == 403
    assert client.post(f"/api/lieferungen/{l['id']}/status", json={"status": "verspaetet", "kommentar": "LKW im Stau"}, headers=s["vor"]).status_code == 200
    assert client.post(f"/api/lieferungen/{l['id']}/fotos", data={"note": "Lieferschein"}, files={"datei": ("ls.png", _png(), "image/png")}, headers=s["vor"]).status_code == 200
    r = client.post(f"/api/lieferungen/{l['id']}/status", json={"status": "eingetroffen"}, headers=s["vor"])
    assert r.status_code == 200 and r.json()["lieferung"]["tatsaechlich_am"]
    d = client.get(f"/api/lieferungen/{l['id']}", headers=s["gu"]).json()
    assert d["lieferung"]["status"] == "eingetroffen" and len(d["fotos"]) == 1 and [v["status"] for v in d["lieferung"]["verlauf"]] == ["angefragt", "bestaetigt", "verspaetet", "eingetroffen"]
    assert client.post(f"/api/lieferungen/{l['id']}/status", json={"status": "abgeschlossen"}, headers=s["gu"]).status_code == 200
    # Mitarbeiter ohne Leitung, fremde Firma: kein Zugriff; Leitung bekommt Verspätungs-Benachrichtigung
    assert client.get(f"/api/lieferungen/{l['id']}", headers=s["ma"]).status_code == 404
    assert client.get(f"/api/lieferungen/{l['id']}", headers=s["fremd"]).status_code == 404
    assert client.get(f"/api/projekte/{s['p']['id']}/lieferungen", headers=s["fremd"]).status_code == 404
    assert any(n["art"] == "lieferung_verspaetet" for n in client.get("/api/benachrichtigungen", headers=s["gu"]).json()["benachrichtigungen"])
    assert any(n["art"] == "lieferung_neu" for n in client.get("/api/benachrichtigungen", headers=s["el"]).json()["benachrichtigungen"])


def test_02_maengel(client):
    s = _aufbau(client)
    r = client.post(f"/api/projekte/{s['p']['id']}/maengel", json={"beschreibung": "Kabelkanal in Halle B lose", "bereich": "Halle B", "kategorie": "Elektro",
                                                                    "firma_id": s["el_firma"], "frist": "2026-10-30", "prioritaet": "hoch"}, headers=s["gu"])
    assert r.status_code == 200, r.text
    m = r.json()["mangel"]
    assert m["status"] == "zugewiesen" and m["firma_name"] == "Elektro Test GmbH"
    # Partnerfirma: sehen, kommentieren, Foto, behoben melden; abnehmen nur die Leitung; erneut öffnen → wieder bei der Firma
    assert [x["id"] for x in client.get(f"/api/projekte/{s['p']['id']}/maengel", headers=s["vor"]).json()["maengel"]] == [m["id"]]
    assert client.post(f"/api/maengel/{m['id']}/kommentare", json={"text": "Wird morgen früh befestigt."}, headers=s["vor"]).status_code == 200
    assert client.post(f"/api/maengel/{m['id']}/status", json={"status": "in_bearbeitung"}, headers=s["vor"]).status_code == 200
    assert client.post(f"/api/maengel/{m['id']}/fotos", data={"note": "Nachher"}, files={"datei": ("n.png", _png(), "image/png")}, headers=s["vor"]).status_code == 200
    assert client.post(f"/api/maengel/{m['id']}/status", json={"status": "behoben_gemeldet"}, headers=s["vor"]).status_code == 200
    assert client.post(f"/api/maengel/{m['id']}/status", json={"status": "abgenommen"}, headers=s["vor"]).status_code == 403
    assert client.post(f"/api/maengel/{m['id']}/status", json={"status": "erneut_geoeffnet", "kommentar": "Nur zur Hälfte befestigt"}, headers=s["gu"]).status_code == 200
    assert client.post(f"/api/maengel/{m['id']}/status", json={"status": "behoben_gemeldet"}, headers=s["vor"]).status_code == 200
    assert client.post(f"/api/maengel/{m['id']}/status", json={"status": "abgenommen"}, headers=s["gu"]).status_code == 200
    d = client.get(f"/api/maengel/{m['id']}", headers=s["gu"]).json()
    assert d["mangel"]["status"] == "abgenommen" and len(d["mangel"]["kommentare"]) == 1 and len(d["fotos"]) == 1 and d["mangel"]["ueberfaellig"] is False
    # Partnerfirma darf selbst einen Mangel melden (ohne Firma zuzuweisen); fremde Firma nicht
    r = client.post(f"/api/projekte/{s['p']['id']}/maengel", json={"beschreibung": "Wasserschaden Decke EG", "bereich": "EG"}, headers=s["vor"])
    assert r.status_code == 200 and r.json()["mangel"]["status"] == "offen"
    assert client.post(f"/api/projekte/{s['p']['id']}/maengel", json={"beschreibung": "x", "firma_id": s["el_firma"]}, headers=s["vor"]).status_code == 403
    assert client.get(f"/api/projekte/{s['p']['id']}/maengel", headers=s["fremd"]).status_code == 404
    assert client.get(f"/api/maengel/{m['id']}", headers=s["ma"]).status_code == 404
    assert any(n["art"] == "mangel_gemeldet" for n in client.get("/api/benachrichtigungen", headers=s["gu"]).json()["benachrichtigungen"])
    offen = client.get(f"/api/projekte/{s['p']['id']}/maengel?offen=true", headers=s["gu"]).json()["maengel"]
    assert [x["beschreibung"] for x in offen] == ["Wasserschaden Decke EG"]


def test_03_tagesberichte_pdf_meilensteine_dokumente_kalender(client):
    s = _aufbau(client)
    p = s["p"]
    client.post(f"/api/projekte/{p['id']}/aufgaben", json={"titel": "Trassen Halle B", "datum": "2026-10-27", "firma_id": s["el_firma"], "bereich": "Halle B"}, headers=s["gu"])
    client.post(f"/api/projekte/{p['id']}/lieferungen", json={"material": "Kabel", "lieferant": "OBO", "firma_id": s["el_firma"], "geplant_am": "2026-10-27"}, headers=s["gu"])
    # Vorschlag füllt den Bericht aus Aufgaben und Lieferungen des Tages
    v = client.get(f"/api/projekte/{p['id']}/tagesbericht-vorschlag?datum=2026-10-27", headers=s["vor"]).json()
    assert "Trassen Halle B" in v["taetigkeiten"] and "Kabel" in v["lieferungen"] and v["firmen"] == ["Elektro Test GmbH"]
    # Partner-Vorarbeiterin schreibt Entwurf mit Foto, reicht ein; GU gibt frei; danach nicht mehr änderbar
    r = client.post(f"/api/projekte/{p['id']}/tagesberichte", json={"datum": "2026-10-27", "bereich": "Halle B", "wetter": "trocken, 12 °C", "firmen": v["firmen"], "mitarbeiter_anzahl": 4,
                                                                      "taetigkeiten": v["taetigkeiten"], "fortschritt": "Trasse 3–5 fertig", "lieferungen": v["lieferungen"], "behinderungen": "Tor 3 zeitweise gesperrt"}, headers=s["vor"])
    assert r.status_code == 200, r.text
    b = r.json()["bericht"]
    assert b["status"] == "entwurf" and b["verfasser"] == "Vera Vorarbeiterin"
    assert client.post(f"/api/tagesberichte/{b['id']}/fotos", data={"note": "Trasse 3"}, files={"datei": ("t.png", _png(), "image/png")}, headers=s["vor"]).status_code == 200
    assert client.get(f"/api/tagesberichte/{b['id']}", headers=s["vor"]).json()["status_erlaubt"] == ["eingereicht"]
    assert client.post(f"/api/tagesberichte/{b['id']}/status", json={"status": "freigegeben"}, headers=s["vor"]).status_code == 403
    assert client.post(f"/api/tagesberichte/{b['id']}/status", json={"status": "eingereicht"}, headers=s["vor"]).status_code == 200
    assert client.get(f"/api/tagesberichte/{b['id']}", headers=s["gu"]).json()["status_erlaubt"] == ["entwurf", "freigegeben"]
    assert client.post(f"/api/tagesberichte/{b['id']}/status", json={"status": "freigegeben"}, headers=s["gu"]).status_code == 200
    assert client.put(f"/api/tagesberichte/{b['id']}", json={"datum": "2026-10-27", "taetigkeiten": "x"}, headers=s["vor"]).status_code == 400
    pdf = client.get(f"/api/tagesberichte/{b['id']}/pdf", headers=s["gu"])
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF") and len(pdf.content) > 5000
    assert client.get(f"/api/tagesberichte/{b['id']}/pdf", headers=s["fremd"]).status_code == 404
    assert [x["id"] for x in client.get(f"/api/projekte/{p['id']}/tagesberichte", headers=s["gu"]).json()["berichte"]] == [b["id"]]
    # Meilensteine: Leitung legt an, Partner sieht sie im Kalender
    r = client.post(f"/api/projekte/{p['id']}/meilensteine", json={"titel": "Elektro Rohinstallation fertig", "datum": "2026-10-31"}, headers=s["gu"])
    assert r.status_code == 200
    assert client.post(f"/api/projekte/{p['id']}/meilensteine", json={"titel": "x", "datum": "2026-10-31"}, headers=s["vor"]).status_code == 403
    # Geteilte Dokumente: GU lädt Bauplan für alle hoch und ein internes Dokument; Partner sieht nur den freigegebenen
    r = client.post(f"/api/projekte/{p['id']}/dokumente", data={"kategorie": "Baupläne", "note": "Halle B EG", "fuer_alle": "true"}, files={"datei": ("plan.pdf", b"%PDF-1.4 test", "application/pdf")}, headers=s["gu"])
    assert r.status_code == 200 and r.json()["dokument"]["freigabe_alle"] is True
    plan_id = r.json()["dokument"]["id"]
    r = client.post(f"/api/projekte/{p['id']}/dokumente", data={"kategorie": "Verträge & Aufträge"}, files={"datei": ("intern.pdf", b"%PDF-1.4 intern", "application/pdf")}, headers=s["gu"])
    intern_id = r.json()["dokument"]["id"]
    partner_docs = client.get(f"/api/projekte/{p['id']}/dokumente", headers=s["vor"]).json()["dokumente"]
    assert [d["id"] for d in partner_docs] == [plan_id]
    assert client.get(f"/api/dokumente/{plan_id}/datei", headers=s["vor"]).status_code == 200
    assert client.get(f"/api/dokumente/{intern_id}/datei", headers=s["vor"]).status_code == 404
    assert client.put(f"/api/projektdokumente/{intern_id}", json={"fuer_alle": True}, headers=s["gu"]).status_code == 200
    assert client.get(f"/api/dokumente/{intern_id}/datei", headers=s["vor"]).status_code == 200
    # Partner lädt ein eigenes Dokument hoch; GU sieht alle drei
    assert client.post(f"/api/projekte/{p['id']}/dokumente", data={"kategorie": "Sicherheit"}, files={"datei": ("unterweisung.pdf", b"%PDF-1.4 u", "application/pdf")}, headers=s["vor"]).status_code == 200
    assert len(client.get(f"/api/projekte/{p['id']}/dokumente", headers=s["gu"]).json()["dokumente"]) == 3
    assert client.get(f"/api/projekte/{p['id']}/dokumente", headers=s["fremd"]).status_code == 404
    # Kalender: GU sieht Aufgabe, Lieferung, Meilenstein; Partner-Vorarbeiterin sieht ihre Aufgabe/Lieferung und den Meilenstein; Mitarbeiter nur Aufgaben
    k = client.get(f"/api/projekte/{p['id']}/plattform-kalender?von=2026-10-01&bis=2026-10-31", headers=s["gu"]).json()
    assert len(k["aufgaben"]) == 1 and len(k["lieferungen"]) == 1 and len(k["meilensteine"]) == 1
    kv = client.get(f"/api/projekte/{p['id']}/plattform-kalender?von=2026-10-01&bis=2026-10-31", headers=s["vor"]).json()
    assert len(kv["aufgaben"]) == 1 and len(kv["lieferungen"]) == 1 and len(kv["meilensteine"]) == 1
    km = client.get(f"/api/projekte/{p['id']}/plattform-kalender?von=2026-10-01&bis=2026-10-31", headers=s["ma"]).json()
    assert len(km["aufgaben"]) == 1 and km["lieferungen"] == [] and len(km["meilensteine"]) == 1
    assert client.get(f"/api/projekte/{p['id']}/plattform-kalender?von=2026-10-01&bis=2026-10-31", headers=s["fremd"]).status_code == 404
    ue = client.get("/api/plattform/uebersicht", headers=s["gu"]).json()["projekte"][0]
    assert ue["maengel_offen"] == 0 and ue["berichte_offen"] == 0 and ue["aufgaben_offen"] == 1
