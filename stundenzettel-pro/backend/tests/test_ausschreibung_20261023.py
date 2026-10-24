"""Ausschreibungen, Angebote, Rückfragen, Vergleich, Vergabe und Anbindung an die Baustellenplattform – 2026-10-23.
Beispielablauf: GOLDBECK Test GmbH – Neubau Logistikzentrum Hannover."""
import asyncio
from datetime import date, timedelta

import db as dbmodul
from conftest import einladen, projekt, registrieren, zeit

ANNAHME = "Ich nehme den Auftrag verbindlich an"
LV = [{"nr": "001", "leistung": "Kabeltrassen montieren", "menge": 450, "einheit": "m"},
      {"nr": "002", "leistung": "Leitungen verlegen", "menge": 1200, "einheit": "m"},
      {"nr": "003", "leistung": "Verteiler installieren", "menge": 12, "einheit": "Stück"}]
BODY = {"titel": "Elektroinstallation", "gewerk": "Elektro", "leistungsart": "Neubau", "beschreibung": "Komplette Elektroinstallation Halle A",
        "leistungsumfang": "Trassen, Leitungen, Verteiler", "sichtbarkeit": "kombiniert", "angebotsfrist": "2026-12-15", "ausfuehrung_von": "2027-01-11",
        "ausfuehrung_bis": "2027-03-31", "positionen": LV, "kaufmaennisch": {"abrechnungsart": "einheitspreise", "budget": 250000, "zahlungsbedingungen": "30 Tage netto"},
        "freigabe": {"budget": False, "auftraggeber": True, "adresse": True}, "anforderungen": {"qualifikationen": "Elektrofachbetrieb", "versicherungen": "Betriebshaftpflicht 5 Mio. €"},
        "intern": "Zielpreis 220.000 €"}


def _arten(client, kopf):
    return [n["art"] for n in client.get("/api/benachrichtigungen", headers=kopf).json()["benachrichtigungen"]]


def _aufbau(client):
    """GOLDBECK mit Admin, zwei Büro-Nutzern (Projektleiterin, Prokurist), Projekt mit Bauvorhaben-Daten und internem Plan;
    drei Elektrofirmen, eine Trockenbaufirma, eine fremde Firma."""
    gu, gu_d = registrieren(client, email="admin@goldbeck-test.de", firma="GOLDBECK Test GmbH", name="Gerd Admin")
    assert client.put("/api/firma", json={"art": "auftraggeber"}, headers=gu).status_code == 200   # nur Auftraggeber-Konten schreiben formal aus
    pl, pl_d = einladen(client, gu, name="Paula Projektleiterin", email="paula@goldbeck-test.de", role="buero")
    pl2, _ = einladen(client, gu, name="Peter Prokurist", email="peter@goldbeck-test.de", role="buero")
    p = projekt(client, pl, name="Logistikzentrum Hannover", address="Industrieweg 1, 30179 Hannover", projektnummer="LZ-HAN-01", projektart="Logistikzentrum",
                baubeginn="2027-01-11", bauende="2027-09-30", phasen=["Rohbau", "Ausbau"], bauabschnitte=["Halle A", "Halle B"], gewerke=["Elektro", "Trockenbau"],
                beschreibung="Neubau Logistikzentrum mit 12.000 m²", projektstatus="ausschreibung", volumen=18500000, lat=52.42, lon=9.74)
    assert p["projektnummer"] == "LZ-HAN-01" and p["phasen"] == ["Rohbau", "Ausbau"]
    assert client.post(f"/api/projekte/{p['id']}/leiter", json={"user_id": pl_d["user"]["id"], "funktion": "Projektleitung"}, headers=gu).status_code == 200
    r = client.post(f"/api/projekte/{p['id']}/dateien", data={"kategorie": "Skizzen & Pläne", "note": "Grundriss EG", "ordner": "Pläne/EG"},
                    files={"datei": ("grundriss.pdf", b"%PDF-1.4 intern", "application/pdf")}, headers=pl)
    assert r.status_code == 200, r.text
    intern = r.json()["dokument"]
    el, el_d = registrieren(client, email="chef@elektro-mustermann-test.de", firma="Elektro Mustermann GmbH", name="Erika Mustermann")
    assert client.put("/api/firma/verzeichnis", json={"sichtbar": True, "gewerke": ["Elektro"], "ort": "Hannover", "regionen": ["Hannover"]}, headers=el).status_code == 200
    el_buero, _ = einladen(client, el, name="Bernd Büro", email="bernd@elektro-mustermann-test.de", role="buero")
    el_vor, el_vor_d = einladen(client, el, name="Vera Vorarbeiterin", email="vera@elektro-mustermann-test.de", role="vorarbeiter")
    el_ma, el_ma_d = einladen(client, el, name="Milan Monteur", email="milan@elektro-mustermann-test.de", role="mitarbeiter")
    e2, e2_d = registrieren(client, email="chef@elektrotechnik-hannover-test.de", firma="Elektrotechnik Hannover GmbH", name="Hans Hannover")
    client.put("/api/firma/verzeichnis", json={"sichtbar": True, "gewerke": ["Elektro"], "ort": "Hannover"}, headers=e2)
    e3, e3_d = registrieren(client, email="chef@nord-elektro-test.de", firma="Nord Elektroservice GmbH", name="Nora Nord")
    client.put("/api/firma/verzeichnis", json={"sichtbar": True, "gewerke": ["Elektro"], "regionen": ["Hamburg"]}, headers=e3)
    tb, tb_d = registrieren(client, email="chef@trockenbau-test.de", firma="Trockenbau Meier", name="Tom Trockenbau")
    client.put("/api/firma/verzeichnis", json={"sichtbar": True, "gewerke": ["Trockenbau"]}, headers=tb)
    fremd, _ = registrieren(client, email="x@fremd-test.de", firma="Fremd GmbH", name="Frank Fremd")
    return {"gu": gu, "gu_firma": gu_d["firma"]["id"], "pl": pl, "pl2": pl2, "p": p, "intern": intern,
            "el": el, "el_firma": el_d["firma"]["id"], "el_buero": el_buero, "el_vor": el_vor, "el_vor_id": el_vor_d["user"]["id"], "el_ma": el_ma, "el_ma_id": el_ma_d["user"]["id"],
            "e2": e2, "e2_firma": e2_d["firma"]["id"], "e3": e3, "e3_firma": e3_d["firma"]["id"], "tb": tb, "tb_firma": tb_d["firma"]["id"], "fremd": fremd}


def _ausschreibung(client, s, **extra):
    """Elektroinstallation anlegen, drei Elektrofirmen einladen, veröffentlichen."""
    r = client.post(f"/api/projekte/{s['p']['id']}/ausschreibungen", json={**BODY, **extra}, headers=s["pl"])
    assert r.status_code == 200, r.text
    a = r.json()["ausschreibung"]
    assert client.post(f"/api/ausschreibungen/{a['id']}/einladungen", json={"firma_ids": [s["el_firma"], s["e2_firma"], s["e3_firma"]]}, headers=s["pl"]).status_code == 200
    r = client.post(f"/api/ausschreibungen/{a['id']}/veroeffentlichen", headers=s["pl"])
    assert r.status_code == 200, r.text
    return r.json()["ausschreibung"]


def _angebot(client, kopf, aid, **daten):
    r = client.post(f"/api/ausschreibungen/{aid}/angebot", json={"preisart": "pauschal", "preis_netto": 57000, "ausfuehrung_von": "2027-01-11", "ausfuehrung_bis": "2027-03-15", **daten}, headers=kopf)
    assert r.status_code == 200, r.text
    g = r.json()["angebot"]
    r = client.post(f"/api/angebote/{g['id']}/einreichen", headers=kopf)
    assert r.status_code == 200, r.text
    return r.json()["angebot"]


def test_01_anlegen_entwurf_veroeffentlichen_finden_privat_protokoll(client):
    s = _aufbau(client)
    pid = s["p"]["id"]
    r = client.post(f"/api/projekte/{pid}/ausschreibungen", json=BODY, headers=s["pl"])
    assert r.status_code == 200, r.text
    a = r.json()["ausschreibung"]
    assert a["status"] == "entwurf" and a["nummer"].startswith("A-") and a["verantwortlich_name"] == "Paula Projektleiterin"
    assert client.post(f"/api/projekte/{pid}/ausschreibungen", json=BODY, headers=s["fremd"]).status_code == 404
    assert client.post(f"/api/projekte/{pid}/ausschreibungen", json=BODY, headers=s["el"]).status_code == 404
    tba = client.post(f"/api/projekte/{pid}/ausschreibungen", json={"titel": "Trockenbau", "gewerk": "Trockenbau", "beschreibung": "Trennwände Büro", "sichtbarkeit": "privat", "angebotsfrist": "2026-12-20"}, headers=s["pl"]).json()["ausschreibung"]
    client.post(f"/api/projekte/{pid}/ausschreibungen", json={"titel": "Heizungs- und Sanitärinstallation", "gewerk": "Sanitär / Heizung", "beschreibung": "HLS komplett", "sichtbarkeit": "oeffentlich", "angebotsfrist": "2026-12-20"}, headers=s["pl"])
    assert len(client.get(f"/api/projekte/{pid}/ausschreibungen", headers=s["pl"]).json()["ausschreibungen"]) == 3
    # Entwurf: für keine andere Firma sichtbar, auch nicht im Marktplatz
    assert client.get(f"/api/ausschreibungen/{a['id']}", headers=s["el"]).status_code == 404
    assert client.get("/api/ausschreibungen", headers=s["el"]).json()["ausschreibungen"] == []
    # Unterlagen und Einladungen vor der Veröffentlichung (Dubletten werden übersprungen)
    r = client.post(f"/api/ausschreibungen/{a['id']}/dokumente", data={"kategorie": "Pläne", "note": "Trassenplan"}, files={"datei": ("trassen.pdf", b"%PDF-1.4 trassen", "application/pdf")}, headers=s["pl"])
    assert r.status_code == 200, r.text
    plan_id = r.json()["dokument"]["id"]
    r = client.post(f"/api/ausschreibungen/{a['id']}/einladungen", json={"firma_ids": [s["el_firma"], s["e2_firma"], s["e3_firma"], s["el_firma"]]}, headers=s["pl"])
    assert r.status_code == 200 and len(r.json()["einladungen"]) == 3 and r.json()["uebersprungen"] == []
    r = client.post(f"/api/ausschreibungen/{a['id']}/einladungen", json={"firma_ids": [s["el_firma"], s["gu_firma"]]}, headers=s["pl"])
    assert r.json()["einladungen"] == [] and [u["grund"] for u in r.json()["uebersprungen"]] == ["bereits eingeladen", "eigene Firma"]
    assert _arten(client, s["el"]) == []          # Einladung wird erst mit der Veröffentlichung gemeldet
    # Veröffentlichen: Pflichtangaben
    leer = client.post(f"/api/projekte/{pid}/ausschreibungen", json={"titel": "Malerarbeiten", "gewerk": "Maler", "sichtbarkeit": "oeffentlich"}, headers=s["pl"]).json()["ausschreibung"]
    r = client.post(f"/api/ausschreibungen/{leer['id']}/veroeffentlichen", headers=s["pl"])
    assert r.status_code == 400 and "Angebotsfrist" in r.json()["detail"]
    r = client.post(f"/api/ausschreibungen/{a['id']}/veroeffentlichen", headers=s["pl"])
    assert r.status_code == 200 and r.json()["ausschreibung"]["status"] == "veroeffentlicht"
    assert client.post(f"/api/ausschreibungen/{a['id']}/veroeffentlichen", headers=s["pl"]).status_code == 400
    client.post(f"/api/ausschreibungen/{tba['id']}/einladungen", json={"firma_ids": [s["tb_firma"]]}, headers=s["pl"])
    assert client.post(f"/api/ausschreibungen/{tba['id']}/veroeffentlichen", headers=s["pl"]).status_code == 200
    # Benachrichtigungen: Eingeladene bekommen die Einladung, passende Firmen „neue Ausschreibung“, fremde ohne Interessen nichts
    assert "ausschreibung_einladung" in _arten(client, s["el"]) and "ausschreibung_einladung" in _arten(client, s["e3"])
    assert "ausschreibung_einladung" in _arten(client, s["tb"]) and "ausschreibung_neu" not in _arten(client, s["tb"])
    assert _arten(client, s["fremd"]) == []
    # Marktplatz: kombiniert sichtbar für alle registrierten Firmen, privat nur für Eingeladene; Budget ohne Freigabe verborgen
    liste = client.get("/api/ausschreibungen", headers=s["el"]).json()["ausschreibungen"]
    assert [x["titel"] for x in liste] == ["Elektroinstallation"] and liste[0]["eingeladen"] is True and liste[0]["budget"] is None and liste[0]["auftraggeber"]["name"] == "GOLDBECK Test GmbH"
    assert [x["titel"] for x in client.get("/api/ausschreibungen?gewerk=Trockenbau", headers=s["tb"]).json()["ausschreibungen"]] == ["Trockenbau"]
    assert [x["titel"] for x in client.get("/api/ausschreibungen", headers=s["fremd"]).json()["ausschreibungen"]] == ["Elektroinstallation"]
    assert client.get("/api/ausschreibungen?ort=Hannover&abrechnungsart=einheitspreise", headers=s["fremd"]).json()["ausschreibungen"][0]["id"] == a["id"]
    assert client.get("/api/ausschreibungen?ort=München", headers=s["fremd"]).json()["ausschreibungen"] == []
    assert client.get(f"/api/ausschreibungen/{tba['id']}", headers=s["fremd"]).status_code == 404
    assert client.get(f"/api/ausschreibungen/{tba['id']}", headers=s["tb"]).status_code == 200
    assert client.get(f"/api/ausschreibungen/{a['id']}", headers=s["el_ma"]).status_code == 403   # nur Firmenvertreter (Büro/Inhaber)
    # Bieteransicht: keine internen Vermerke, kein Budget, Unterlagen abrufbar – interne Projektunterlagen nicht
    d = client.get(f"/api/ausschreibungen/{a['id']}", headers=s["el"]).json()["ausschreibung"]
    assert "intern" not in d and "budget" not in d["kaufmaennisch"] and d["rolle"] == "bieter" and d["einladung"]["status"] == "angesehen"
    assert d["projekt"]["name"] == "Logistikzentrum Hannover" and d["projekt"]["projektart"] == "Logistikzentrum" and [x["id"] for x in d["dokumente"]] == [plan_id]
    assert client.get(f"/api/dokumente/{plan_id}/datei", headers=s["el"]).status_code == 200
    assert client.get(f"/api/dokumente/{plan_id}/datei", headers=s["fremd"]).status_code == 200      # öffentlich sichtbare Ausschreibung
    assert client.get(f"/api/dokumente/{s['intern']['id']}/datei", headers=s["el"]).status_code == 404
    assert client.get(f"/api/dokumente/{s['intern']['id']}/datei", headers=s["pl"]).status_code == 200
    # Eigentümer sieht alles inklusive Verlauf und Zähler
    e = client.get(f"/api/ausschreibungen/{a['id']}", headers=s["pl"]).json()["ausschreibung"]
    assert e["intern"] == "Zielpreis 220.000 €" and e["zaehler"]["einladungen"] == 3 and [v["aktion"] for v in e["verlauf"]][:3] == ["angelegt", "dokument", "eingeladen"]
    # Änderungen werden protokolliert und Bietern gemeldet; Frist nicht in die Vergangenheit
    r = client.put(f"/api/ausschreibungen/{a['id']}", json={**BODY, "angebotsfrist": "2026-12-18"}, headers=s["pl"])
    assert r.status_code == 200
    v = r.json()["ausschreibung"]["verlauf"]
    assert v[-1]["aktion"] == "geaendert" and v[-1]["felder"] == ["angebotsfrist"]
    assert "ausschreibung_aktualisiert" in _arten(client, s["el"])
    assert client.put(f"/api/ausschreibungen/{a['id']}", json={**BODY, "angebotsfrist": "2026-01-01"}, headers=s["pl"]).status_code == 400
    assert client.put(f"/api/ausschreibungen/{a['id']}", json=BODY, headers=s["el"]).status_code == 403
    aktionen = {e["aktion"] for e in client.get("/api/protokoll", headers=s["gu"]).json()["eintraege"]}
    assert {"ausschreibung.angelegt", "ausschreibung.eingeladen", "ausschreibung.veroeffentlicht", "ausschreibung.geaendert"} <= aktionen
    ue = client.get("/api/ausschreibungen/uebersicht", headers=s["pl"]).json()
    assert len(ue["eigene"]) == 4 and ue["eigene"][0]["zaehler"]["angebote"] == 0
    assert len(client.get("/api/ausschreibungen/uebersicht", headers=s["el"]).json()["einladungen"]) == 1
    csv_r = client.get(f"/api/ausschreibungen/{a['id']}/positionen.csv", headers=s["el"])
    assert csv_r.status_code == 200 and "Kabeltrassen montieren" in csv_r.text
    # Aufheben: Bieter werden informiert, Marktplatz zeigt sie nicht mehr
    assert client.post(f"/api/ausschreibungen/{tba['id']}/aufheben", json={"nachricht": "Leistung entfällt"}, headers=s["pl"]).status_code == 200
    assert "ausschreibung_aufgehoben" in _arten(client, s["tb"])
    assert client.get("/api/ausschreibungen?gewerk=Trockenbau", headers=s["tb"]).json()["ausschreibungen"] == []


def test_02_angebote_positionen_fristen_rueckfragen_vergleich(client):
    s = _aufbau(client)
    a = _ausschreibung(client, s)
    aid = a["id"]
    pos = [{"nr": "001", "einzelpreis": 45.5}, {"nr": "002", "einzelpreis": 12}, {"nr": "003", "einzelpreis": 1850}]
    r = client.post(f"/api/ausschreibungen/{aid}/angebot", json={"preisart": "einheitspreise", "positionen": pos, "ansprechpartner": "Erika Mustermann", "ausfuehrung_von": "2027-01-11",
                                                                 "ausfuehrung_bis": "2027-03-15", "gueltig_bis": "2027-01-31", "kapazitaet": "6 Monteure"}, headers=s["el_buero"])
    assert r.status_code == 200, r.text
    g1 = r.json()["angebot"]
    assert g1["status"] == "entwurf" and g1["summe_netto"] == 57075.0 and g1["berechnung"]["vollstaendig"] is True and g1["summe_brutto"] == round(57075 * 1.19, 2)
    assert client.post(f"/api/ausschreibungen/{aid}/angebot", json={"preisart": "pauschal", "preis_netto": 1}, headers=s["el_ma"]).status_code == 403
    assert client.post(f"/api/ausschreibungen/{aid}/angebot", json={"preisart": "pauschal", "preis_netto": 1}, headers=s["pl"]).status_code == 400
    # Entwürfe sieht der Eigentümer nicht
    assert client.get(f"/api/ausschreibungen/{aid}/angebote", headers=s["pl"]).json()["angebote"] == []
    assert client.get(f"/api/angebote/{g1['id']}", headers=s["pl"]).status_code == 404
    assert client.post(f"/api/angebote/{g1['id']}/dokumente", data={"kategorie": "Angebot (PDF)"}, files={"datei": ("angebot.pdf", b"%PDF-1.4 a", "application/pdf")}, headers=s["el_buero"]).status_code == 200
    r = client.post(f"/api/angebote/{g1['id']}/einreichen", headers=s["el_buero"])
    assert r.status_code == 200 and r.json()["angebot"]["status"] == "eingereicht" and r.json()["angebot"]["version"] == 1
    assert "angebot_eingereicht" in _arten(client, s["pl"]) and "angebot_bestaetigung" in _arten(client, s["el"])
    # Kein zweites Angebot derselben Firma
    assert client.post(f"/api/ausschreibungen/{aid}/angebot", json={"preisart": "pauschal", "preis_netto": 1}, headers=s["el"]).status_code == 409
    # Unvollständige Positionen → kein Einreichen; dann Pauschalpreis
    g2 = client.post(f"/api/ausschreibungen/{aid}/angebot", json={"preisart": "einheitspreise", "positionen": [{"nr": "001", "einzelpreis": 40}]}, headers=s["e2"]).json()["angebot"]
    r = client.post(f"/api/angebote/{g2['id']}/einreichen", headers=s["e2"])
    assert r.status_code == 400 and "002" in r.json()["detail"]
    assert client.put(f"/api/angebote/{g2['id']}", json={"preisart": "pauschal", "preis_netto": 61000}, headers=s["e2"]).status_code == 200
    assert client.post(f"/api/angebote/{g2['id']}/einreichen", headers=s["e2"]).status_code == 200
    g3 = _angebot(client, s["e3"], aid, preis_netto=54900)
    # Konkurrenten sehen weder Angebote noch Anhänge; Eigentümer schon, fremde nie
    assert client.get(f"/api/angebote/{g1['id']}", headers=s["e2"]).status_code == 404
    doc_id = client.get(f"/api/angebote/{g1['id']}", headers=s["el"]).json()["angebot"]["dokumente"][0]["id"]
    assert client.get(f"/api/dokumente/{doc_id}/datei", headers=s["e2"]).status_code == 404
    assert client.get(f"/api/dokumente/{doc_id}/datei", headers=s["fremd"]).status_code == 404
    assert client.get(f"/api/dokumente/{doc_id}/datei", headers=s["pl"]).status_code == 200
    assert client.get(f"/api/angebote/{g1['id']}", headers=s["el_ma"]).status_code == 403
    # Vergleich für die Projektleitung: sortiert nach Preis, keine automatische Entscheidung
    v = client.get(f"/api/ausschreibungen/{aid}/angebote", headers=s["pl"]).json()
    assert [x["firma_name"] for x in v["vergleich"]] == ["Nord Elektroservice GmbH", "Elektro Mustermann GmbH", "Elektrotechnik Hannover GmbH"]
    assert v["guenstigstes"] == 54900 and v["vergleich"][1]["positionen_vollstaendig"] is True and v["vergleich"][1]["dokumente"] == 1
    assert client.get(f"/api/ausschreibungen/{aid}/angebote", headers=s["el"]).status_code == 403
    # Bewertung: nur Leitung, für Bieter unsichtbar
    r = client.put(f"/api/angebote/{g1['id']}/bewertung", json={"kriterien": {"preis": 4, "qualifikation": 5, "termin": 5, "vollstaendigkeit": 5}, "notiz": "Referenzen sehr gut", "mindestanforderungen_erfuellt": True}, headers=s["pl"])
    assert r.status_code == 200
    assert client.put(f"/api/angebote/{g1['id']}/bewertung", json={"kriterien": {"preis": 1}}, headers=s["el"]).status_code == 403
    assert "bewertung" not in client.get(f"/api/angebote/{g1['id']}", headers=s["el"]).json()["angebot"]
    v = client.get(f"/api/ausschreibungen/{aid}/angebote", headers=s["pl"]).json()["vergleich"][1]
    assert v["bewertung_punkte"] == 19 and v["bewertung_max"] == 20 and v["mindestanforderungen"] is True
    # Rückfragen: öffentlich beantwortete Fragen sehen alle Bieter anonymisiert, private nur der Fragende
    f1 = client.post(f"/api/ausschreibungen/{aid}/fragen", json={"text": "Ist die Leitungslänge inkl. Reserve?", "position_nr": "002"}, headers=s["el"]).json()["frage"]
    assert "rueckfrage_neu" in _arten(client, s["pl"])
    assert client.post(f"/api/fragen/{f1['id']}/antwort", json={"antwort": "Ja, inkl. 10 % Reserve.", "oeffentlich": True}, headers=s["pl"]).status_code == 200
    assert client.post(f"/api/fragen/{f1['id']}/antwort", json={"antwort": "x"}, headers=s["e2"]).status_code == 403
    f2 = client.post(f"/api/ausschreibungen/{aid}/fragen", json={"text": "Können wir später anfangen?"}, headers=s["e2"]).json()["frage"]
    client.post(f"/api/fragen/{f2['id']}/antwort", json={"antwort": "Nein.", "oeffentlich": False}, headers=s["pl"])
    fragen_el = client.get(f"/api/ausschreibungen/{aid}", headers=s["el"]).json()["ausschreibung"]["fragen"]
    assert [x["id"] for x in fragen_el] == [f1["id"]] and fragen_el[0]["eigene"] is True
    fragen_e2 = client.get(f"/api/ausschreibungen/{aid}", headers=s["e2"]).json()["ausschreibung"]["fragen"]
    assert [x["id"] for x in fragen_e2] == [f1["id"], f2["id"]] and fragen_e2[0]["firma_name"] == "Ein Bieter" and fragen_e2[1]["eigene"] is True
    assert "rueckfrage_antwort" in _arten(client, s["el"]) and "rueckfrage_antwort" in _arten(client, s["e2"])
    assert len(client.get(f"/api/ausschreibungen/{aid}", headers=s["pl"]).json()["ausschreibung"]["fragen"]) == 2
    # Angebotsfrist serverseitig: nach Ablauf keine neuen Angebote, keine Änderungen eingereichter Angebote
    gestern = (date.today() - timedelta(days=1)).isoformat()
    asyncio.run(dbmodul.db().ausschreibungen.update_one({"id": aid}, {"$set": {"angebotsfrist": gestern}}))
    assert client.post(f"/api/ausschreibungen/{aid}/angebot", json={"preisart": "pauschal", "preis_netto": 1000}, headers=s["tb"]).status_code == 400
    assert client.put(f"/api/angebote/{g3['id']}", json={"preisart": "pauschal", "preis_netto": 1}, headers=s["e3"]).status_code == 409
    assert client.get(f"/api/ausschreibungen/{aid}", headers=s["tb"]).json()["ausschreibung"]["kann_bieten"] is False
    # Nachforderung durch die Leitung öffnet eine Nachreichfrist: Überarbeitung wird Version 2
    r = client.post(f"/api/angebote/{g1['id']}/pruefung", json={"status": "rueckfrage", "nachricht": "Bitte Versicherungsnachweis nachreichen"}, headers=s["pl"])
    assert r.status_code == 200 and r.json()["angebot"]["nachreichen_bis"] >= date.today().isoformat()
    assert "angebot_nachforderung" in _arten(client, s["el"])
    assert client.get(f"/api/ausschreibungen/{aid}", headers=s["el"]).json()["ausschreibung"]["kann_bieten"] is True
    assert client.put(f"/api/angebote/{g1['id']}", json={"preisart": "einheitspreise", "positionen": [{"nr": "001", "einzelpreis": 44}, {"nr": "002", "einzelpreis": 12}, {"nr": "003", "einzelpreis": 1850}]}, headers=s["el"]).status_code == 200
    assert client.post(f"/api/angebote/{g1['id']}/dokumente", data={"kategorie": "Versicherungsnachweis"}, files={"datei": ("hv.pdf", b"%PDF-1.4 hv", "application/pdf")}, headers=s["el"]).status_code == 200
    r = client.post(f"/api/angebote/{g1['id']}/einreichen", headers=s["el"])
    assert r.status_code == 200 and r.json()["angebot"]["status"] == "ueberarbeitet" and r.json()["angebot"]["version"] == 2
    g1b = client.get(f"/api/angebote/{g1['id']}", headers=s["pl"]).json()["angebot"]
    assert len(g1b["versionen"]) == 2 and g1b["versionen"][0]["summe_netto"] == 57075.0 and g1b["summe_netto"] == 56400.0
    assert client.post(f"/api/angebote/{g2['id']}/pruefung", json={"status": "in_pruefung"}, headers=s["pl"]).status_code == 200
    assert "angebot_in_pruefung" in _arten(client, s["e2"])
    # Rücknahme wird protokolliert
    assert client.post(f"/api/angebote/{g3['id']}/zurueckziehen", json={"nachricht": "Kapazität nicht mehr frei"}, headers=s["e3"]).status_code == 200
    assert client.post(f"/api/angebote/{g3['id']}/zurueckziehen", json={}, headers=s["e3"]).status_code == 400
    assert "angebot_zurueckgezogen" in _arten(client, s["pl"])
    assert "angebot.zurueckgezogen" in {e["aktion"] for e in client.get("/api/protokoll", headers=s["e3"]).json()["eintraege"]}
    assert [x["firma_name"] for x in client.get(f"/api/ausschreibungen/{aid}/angebote", headers=s["pl"]).json()["vergleich"]] == ["Elektro Mustermann GmbH", "Elektrotechnik Hannover GmbH"]
    assert "44" in client.get(f"/api/angebote/{g1['id']}/positionen.csv", headers=s["el"]).text
    ue = client.get("/api/ausschreibungen/uebersicht", headers=s["el"]).json()
    assert len(ue["angebote"]) == 1 and ue["angebote"][0]["angebot"]["summe_netto"] == 56400.0


def test_03_vergabe_projektzuordnung_bestehende_funktionen(client):
    s = _aufbau(client)
    a = _ausschreibung(client, s)
    aid, pid = a["id"], s["p"]["id"]
    g1 = _angebot(client, s["el_buero"], aid, preis_netto=57000)
    g2 = _angebot(client, s["e2"], aid, preis_netto=61000)
    # Vergabe vorschlagen: nur Projektleitung, nur eingereichte Angebote, nur eine laufende Vergabe
    assert client.post(f"/api/ausschreibungen/{aid}/vergabe", json={"angebot_id": g1["id"]}, headers=s["el"]).status_code == 403
    r = client.post(f"/api/ausschreibungen/{aid}/vergabe", json={"angebot_id": g1["id"], "begruendung": "Bestes Preis-Leistungs-Verhältnis, Referenzen geprüft"}, headers=s["pl"])
    assert r.status_code == 200, r.text
    v = r.json()["vergabe"]
    assert v["status"] == "vorgeschlagen" and v["summe_netto"] == 57000
    assert client.post(f"/api/ausschreibungen/{aid}/vergabe", json={"angebot_id": g2["id"]}, headers=s["pl"]).status_code == 409
    assert client.get(f"/api/ausschreibungen/{aid}", headers=s["pl"]).json()["ausschreibung"]["status"] == "in_vergabe"
    assert "vergabe_freigabe" in _arten(client, s["gu"])
    # Freigabe: Vier-Augen-Prinzip, nur berechtigte Personen der ausschreibenden Firma
    assert client.post(f"/api/vergaben/{v['id']}/freigabe", headers=s["pl"]).status_code == 409
    assert client.post(f"/api/vergaben/{v['id']}/freigabe", headers=s["el"]).status_code == 404
    assert client.post(f"/api/vergaben/{v['id']}/mitteilen", json={}, headers=s["pl"]).status_code == 400
    assert client.post(f"/api/vergaben/{v['id']}/freigabe", headers=s["pl2"]).status_code == 200
    assert client.post(f"/api/vergaben/{v['id']}/freigabe", headers=s["pl2"]).status_code == 400
    # Vertragsdokument bereitstellen, Vergabemitteilung an die Firma
    assert client.post(f"/api/vergaben/{v['id']}/dokumente", data={"kategorie": "Auftragsschreiben"}, files={"datei": ("auftrag.pdf", b"%PDF-1.4 auftrag", "application/pdf")}, headers=s["pl"]).status_code == 200
    assert client.get(f"/api/vergaben/{v['id']}", headers=s["el"]).status_code == 404      # vor der Mitteilung nicht sichtbar
    assert client.post(f"/api/vergaben/{v['id']}/mitteilen", json={"nachricht": "Wir freuen uns auf die Zusammenarbeit."}, headers=s["pl"]).status_code == 200
    assert "vergabe_erhalten" in _arten(client, s["el"])
    d = client.get(f"/api/vergaben/{v['id']}", headers=s["el"]).json()["vergabe"]
    assert d["status"] == "mitgeteilt" and len(d["dokumente"]) == 1 and d["annahme_text"] == ANNAHME and d["auftraggeber"]["name"] == "GOLDBECK Test GmbH"
    assert client.get(f"/api/dokumente/{d['dokumente'][0]['id']}/datei", headers=s["el"]).status_code == 200
    assert client.get(f"/api/dokumente/{d['dokumente'][0]['id']}/datei", headers=s["e2"]).status_code == 404
    assert client.get(f"/api/vergaben/{v['id']}", headers=s["e2"]).status_code == 404
    assert len(client.get("/api/ausschreibungen/uebersicht", headers=s["el"]).json()["vergaben"]) == 1
    # Verbindliche Annahme: kein einfacher Statuswechsel – nur Inhaber, nur mit ausdrücklicher Bestätigung
    assert client.post(f"/api/vergaben/{v['id']}/antwort", json={"annehmen": True, "bestaetigung": ANNAHME, "name": "Bernd Büro"}, headers=s["el_buero"]).status_code == 403
    assert client.post(f"/api/vergaben/{v['id']}/antwort", json={"annehmen": True, "bestaetigung": "ok", "name": "Erika Mustermann"}, headers=s["el"]).status_code == 400
    assert client.post(f"/api/vergaben/{v['id']}/antwort", json={"annehmen": True, "bestaetigung": ANNAHME, "name": "Erika Mustermann"}, headers=s["e2"]).status_code == 404
    r = client.post(f"/api/vergaben/{v['id']}/antwort", json={"annehmen": True, "bestaetigung": ANNAHME + ".", "name": "Erika Mustermann"}, headers=s["el"])
    assert r.status_code == 200, r.text
    lokal_id = r.json()["lokales_project_id"]
    assert lokal_id and r.json()["vergabe"]["status"] == "angenommen" and r.json()["vergabe"]["bestaetigung"]["name"] == "Erika Mustermann"
    assert client.post(f"/api/vergaben/{v['id']}/antwort", json={"annehmen": True, "bestaetigung": ANNAHME, "name": "Erika"}, headers=s["el"]).status_code == 400
    # Folgen: Beteiligung aktiv, Ausschreibung vergeben, Konkurrent abgelehnt mit Absage, Projektleitung informiert
    bet = client.get(f"/api/projekte/{pid}/beteiligungen", headers=s["pl"]).json()["beteiligungen"]
    assert [(b["firma"]["name"], b["status"], b["gewerk"]) for b in bet] == [("Elektro Mustermann GmbH", "aktiv", "Elektro")]
    assert client.get(f"/api/ausschreibungen/{aid}", headers=s["pl"]).json()["ausschreibung"]["status"] == "vergeben"
    assert client.get(f"/api/angebote/{g2['id']}", headers=s["e2"]).json()["angebot"]["status"] == "abgelehnt" and "absage" in _arten(client, s["e2"])
    assert "vergabe_angenommen" in _arten(client, s["pl"])
    lokal = client.get(f"/api/projekte/{lokal_id}", headers=s["el"]).json()["projekt"]
    assert lokal["verknuepft"]["project_id"] == pid and lokal["customer_name"] == "GOLDBECK Test GmbH"
    # Die Elektrofirma ordnet fünf Mitarbeiter zu, GOLDBECK erstellt die erste Tagesaufgabe, die Vorarbeiterin sieht sie
    ids = [s["el_vor_id"], s["el_ma_id"]]
    for i in range(3):
        ids.append(einladen(client, s["el"], name=f"Monteur {i}", email=f"monteur{i}@elektro-mustermann-test.de", role="mitarbeiter")[1]["user"]["id"])
    assert client.put(f"/api/projekte/{lokal_id}", json={**{k: lokal[k] for k in ("name", "hourly_rate", "color")}, "employee_ids": ids}, headers=s["el"]).status_code == 200
    heute = date.today().isoformat()
    r = client.post(f"/api/projekte/{pid}/aufgaben", json={"titel": "Kabeltrassen Halle A", "datum": heute, "firma_id": s["el_firma"], "start_time": "07:00", "end_time": "15:00", "bereich": "Halle A"}, headers=s["pl"])
    assert r.status_code == 200, r.text
    assert [x["titel"] for x in client.get("/api/aufgaben/meine", headers=s["el_vor"]).json()["aufgaben"]] == ["Kabeltrassen Halle A"]
    assert [x["titel"] for x in client.get("/api/aufgaben/meine", headers=s["el_ma"]).json()["aufgaben"]] == ["Kabeltrassen Halle A"]
    # Arbeitszeiten, Monatsdaten, Rechnung und Rechnungs-PDF der Elektrofirma funktionieren weiterhin – nur für sie sichtbar
    zeit(client, s["el_vor"], lokal_id, date=heute, start="07:00", ende="15:00", pause=30)
    jahr, monat = int(heute[:4]), int(heute[5:7])
    m = client.get(f"/api/projekte/{lokal_id}/monat?jahr={jahr}&monat={monat}", headers=s["el"])
    assert m.status_code == 200 and len(m.json()["eintraege"]) == 1
    r = client.post("/api/rechnungen/anlegen", json={"project_id": lokal_id, "year": jahr, "month": monat}, headers=s["el"])
    assert r.status_code == 200, r.text
    rid = r.json()["rechnung"]["id"]
    pdf = client.get(f"/api/rechnungen/{rid}/rechnung.pdf", headers=s["el"])
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert client.get(f"/api/rechnungen/{rid}/rechnung.pdf", headers=s["pl"]).status_code == 404
    anwesend = client.get(f"/api/projekte/{pid}/anwesenheit", headers=s["pl"])
    assert anwesend.status_code == 200
    # Revisionssichere Spur: Vergabeschritte im Verlauf und im Sicherheitsprotokoll beider Firmen
    vg = client.get(f"/api/vergaben/{v['id']}", headers=s["pl"]).json()["vergabe"]
    assert [x["status"] for x in vg["verlauf"]][:3] == ["vorgeschlagen", "freigegeben", "freigegeben"] and vg["verlauf"][-1]["status"] == "angenommen"
    gu_aktionen = {e["aktion"] for e in client.get("/api/protokoll", headers=s["gu"]).json()["eintraege"]}
    assert {"vergabe.vorgeschlagen", "vergabe.freigegeben", "vergabe.mitgeteilt", "vergabe.angenommen_durch_firma"} <= gu_aktionen
    assert "vergabe.angenommen" in {e["aktion"] for e in client.get("/api/protokoll", headers=s["el"]).json()["eintraege"]}


def test_04_ablehnung_versionen_speicher_csv_gaeb(client):
    s = _aufbau(client)
    pid = s["p"]["id"]
    a = _ausschreibung(client, s)
    aid = a["id"]
    # Firma lehnt die Vergabe ab → Ausschreibung wieder offen, zweite Vergabe möglich
    g1 = _angebot(client, s["el"], aid, preis_netto=57000)
    g2 = _angebot(client, s["e2"], aid, preis_netto=61000)
    v = client.post(f"/api/ausschreibungen/{aid}/vergabe", json={"angebot_id": g1["id"]}, headers=s["pl"]).json()["vergabe"]
    assert client.post(f"/api/vergaben/{v['id']}/freigabe", headers=s["gu"]).status_code == 200
    assert client.post(f"/api/vergaben/{v['id']}/mitteilen", json={}, headers=s["pl"]).status_code == 200
    assert client.post(f"/api/vergaben/{v['id']}/antwort", json={"annehmen": False, "grund": "Kapazität ausgelastet"}, headers=s["el_buero"]).status_code == 200
    assert client.get(f"/api/ausschreibungen/{aid}", headers=s["pl"]).json()["ausschreibung"]["status"] == "veroeffentlicht"
    assert "vergabe_abgelehnt" in _arten(client, s["pl"])
    v2 = client.post(f"/api/ausschreibungen/{aid}/vergabe", json={"angebot_id": g2["id"]}, headers=s["pl"]).json()["vergabe"]
    assert v2["status"] == "vorgeschlagen"
    assert client.post(f"/api/vergaben/{v2['id']}/zurueckziehen", json={"nachricht": "Neu ausschreiben"}, headers=s["pl"]).status_code == 200
    assert client.get(f"/api/ausschreibungen/{aid}", headers=s["pl"]).json()["ausschreibung"]["status"] == "veroeffentlicht"
    # Leistungsverzeichnis per CSV importieren (Dezimalkomma), GAEB ehrlich abgewiesen
    r = client.post(f"/api/ausschreibungen/{aid}/positionen/import", json={"csv": "Nr;Leistung;Menge;Einheit\n010;Kabeltrassen montieren;450,5;m\n020;Verteiler;12;Stück\n"}, headers=s["pl"])
    assert r.status_code == 200 and r.json()["positionen"][0]["menge"] == 450.5 and len(r.json()["positionen"]) == 2
    assert client.post(f"/api/ausschreibungen/{aid}/positionen/import", json={"csv": "010;A;1;m\n010;B;1;m\n"}, headers=s["pl"]).status_code == 400
    r = client.post(f"/api/ausschreibungen/{aid}/positionen/gaeb", files={"datei": ("lv.x83", b"<?xml version='1.0'?><GAEB xmlns='http://www.gaeb.de/GAEB_DA_XML/DA83/3.2'></GAEB>", "application/xml")}, headers=s["pl"])
    assert r.status_code == 400 and "Leistungsverzeichnis" in r.json()["detail"]   # seit Stufe F echter Import: leere GAEB-Datei wird mit Klartext abgewiesen
    # Dokumentversionen in der Projektakte (Ordner wird übernommen, Vorgänger nicht mehr aktuell)
    v1 = s["intern"]
    r = client.post(f"/api/projekte/{pid}/dateien", data={"kategorie": "Skizzen & Pläne", "ersetzt_id": v1["id"]}, files={"datei": ("grundriss-v2.pdf", b"%PDF-1.4 v2", "application/pdf")}, headers=s["pl"])
    assert r.status_code == 200, r.text
    d2 = r.json()["dokument"]
    assert d2["version"] == 2 and d2["vorgaenger_id"] == v1["id"] and d2["ordner"] == "Pläne/EG" and d2["note"] == "Grundriss EG"
    akte = {d["id"]: d for d in client.get(f"/api/projekte/{pid}/akte", headers=s["pl"]).json()["dateien"]}
    assert akte[v1["id"]]["aktuell"] is False and akte[v1["id"]]["ersetzt_von"] == d2["id"] and akte[d2["id"]]["aktuell"] is True
    # Versionen bei geteilten Plattform-Dokumenten; Speicherstand und Speichergrenze je Firma
    r = client.post(f"/api/projekte/{pid}/dokumente", data={"kategorie": "Baupläne", "note": "Leuchtenplan", "fuer_alle": "true", "ordner": "Elektro"}, files={"datei": ("l1.pdf", b"%PDF-1.4 l1", "application/pdf")}, headers=s["pl"])
    p1 = r.json()["dokument"]
    r = client.post(f"/api/projekte/{pid}/dokumente", data={"kategorie": "Baupläne", "ersetzt_id": p1["id"]}, files={"datei": ("l2.pdf", b"%PDF-1.4 l2", "application/pdf")}, headers=s["pl"])
    assert r.status_code == 200 and r.json()["dokument"]["version"] == 2 and r.json()["dokument"]["freigabe_alle"] is True and r.json()["dokument"]["ordner"] == "Elektro"
    sp = client.get("/api/firma/speicher", headers=s["gu"]).json()
    assert sp["belegt_bytes"] > 0 and sp["grenze_gb"] == 5 and sp["max_datei_mb"] >= 15
    assert client.get("/api/firma/speicher", headers=s["el_ma"]).status_code == 403
    asyncio.run(dbmodul.db().firmen.update_one({"id": s["gu_firma"]}, {"$set": {"plan.speicher_gb": 0.00001}}))
    r = client.post(f"/api/projekte/{pid}/dateien", data={"kategorie": "Fotos"}, files={"datei": ("gross.pdf", b"%PDF-1.4 " + b"x" * 20000, "application/pdf")}, headers=s["pl"])
    assert r.status_code == 413 and "Speicherplatz" in r.json()["detail"]
    # Entwürfe löschen nur solange unveröffentlicht
    e = client.post(f"/api/projekte/{pid}/ausschreibungen", json={"titel": "Malerarbeiten", "gewerk": "Maler", "beschreibung": "x", "angebotsfrist": "2026-12-20"}, headers=s["pl"]).json()["ausschreibung"]
    assert client.delete(f"/api/ausschreibungen/{e['id']}", headers=s["pl"]).status_code == 200
    assert client.delete(f"/api/ausschreibungen/{aid}", headers=s["pl"]).status_code == 400
