"""Testdaten für eine lokale Instanz (z. B. nach `python dev.py`): Firma mit Inhaber, eine Mitarbeiterin,
zwei Kunden (einer mit § 13b), zwei Projekte, Zeiten, Abwesenheiten, Rechnungen, Checkliste, Notiz.

    python testdaten.py                 # gegen http://127.0.0.1:8010
    python testdaten.py http://host:port

Zugangsdaten danach: Inhaber CHEF_EMAIL / CHEF_PASSWORT, Mitarbeiterin MIA_EMAIL / MIA_PASSWORT (siehe unten).
Läuft die Datei ein zweites Mal gegen dieselbe Datenbank, meldet sie sich nur an und legt nichts Neues an.
"""
import sys

import httpx

BASIS = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8010"
CHEF_EMAIL, CHEF_PASSWORT = "chef@beispiel.de", "testpasswort123"
MIA_EMAIL, MIA_PASSWORT = "mia@beispiel.de", "miapasswort123"

c = httpx.Client(base_url=BASIS, timeout=30)


def ok(r):
    if r.status_code >= 300:
        print("FEHLER", r.request.method, r.request.url, r.status_code, r.text[:300])
        sys.exit(1)
    return r.json()


r = c.post("/api/auth/registrieren", json={"firma_name": "PowerClean Test GmbH", "name": "Ahmad Test", "email": CHEF_EMAIL, "password": CHEF_PASSWORT})
if r.status_code == 409:
    print("Firma gibt es schon – nur Anmeldung geprüft.")
    ok(c.post("/api/auth/login", json={"email": CHEF_EMAIL, "password": CHEF_PASSWORT}))
    sys.exit(0)
chef = ok(r)
H = {"Authorization": f"Bearer {chef['token']}"}
ok(c.put("/api/firma", json={"default_hourly_rate": 30, "street": "Teststraße 1", "zip_code": "12345", "city": "Musterstadt",
                            "iban": "DE89 3704 0044 0532 0130 00", "bic": "COBADEFFXXX", "bank_name": "Testbank", "tax_number": "12/345/6789",
                            "vat_id": "DE123456789", "phone": "0211 123456", "email": "buero@powerclean-test.de", "owner": "Ahmad Test", "payment_days": 14,
                            "bundesland": "NW", "auto_pause": True, "sperre_tage_mitarbeiter": 365,
                            "lohn_export": {"berater_nr": "1234567", "mandanten_nr": "12345", "lohnarten": {"normal": "100", "ueberstunden": "200", "nacht": "300", "urlaub": "400", "krank": "500"}}}, headers=H))
mia = ok(c.post("/api/mitarbeiter", json={"name": "Mia Muster", "email": MIA_EMAIL, "role": "mitarbeiter", "personalnummer": "7"}, headers=H))
token = mia["einladung_link"].rsplit("/", 1)[-1]
mia_login = ok(c.post(f"/api/auth/einladung/{token}", json={"password": MIA_PASSWORT}))
HM = {"Authorization": f"Bearer {mia_login['token']}"}
mia_id = mia_login["user"]["id"]
ok(c.put(f"/api/mitarbeiter/{mia_id}", json={"weekly_hours": 30, "vacation_days": 24, "vacation_carryover": 2, "vacation_carryover_year": 2026, "balance_start_date": "2026-10-01"}, headers=H))
glas = ok(c.post("/api/leistungen", json={"name": "Glasreinigung", "hourly_rate": 45, "sort": 2}, headers=H))["leistung"]
ok(c.post("/api/leistungen", json={"name": "Unterhaltsreinigung", "hourly_rate": 0, "sort": 1}, headers=H))
ok(c.post("/api/leistungen", json={"name": "Grundreinigung", "hourly_rate": 38, "sort": 3}, headers=H))
kunde = ok(c.post("/api/kunden", json={"name": "Sparkasse Musterstadt", "contact": "Frau Richter", "street": "Marktplatz 2", "zip_code": "12345", "city": "Musterstadt",
                                        "email": "rechnungen@sparkasse-test.de", "leitweg_id": "05111-12345-67", "customer_number": "K-100"}, headers=H))["kunde"]
sub = ok(c.post("/api/kunden", json={"name": "Gebäudeservice Groß GmbH", "street": "Industriestraße 9", "zip_code": "12345", "city": "Musterstadt", "reverse_charge": True}, headers=H))["kunde"]
p1 = ok(c.post("/api/projekte", json={"name": "Sparkasse Hauptstelle", "customer_id": kunde["id"], "address": "Marktplatz 2", "schedule": "Mo–Fr 06:00–09:00", "hourly_rate": 30, "budget_hours_month": 70, "budget_warn_percent": 80}, headers=H))["projekt"]
p2 = ok(c.post("/api/projekte", json={"name": "Bürokomplex Nord (Subunternehmer)", "customer_id": sub["id"], "hourly_rate": 26, "color": "#1D4ED8"}, headers=H))["projekt"]
ok(c.post("/api/zeiten/serie", json={"project_id": p1["id"], "from_date": "2026-10-01", "to_date": "2026-10-23", "weekdays": [0, 1, 2, 3, 4],
                                     "start_time": "06:00", "end_time": "09:00", "user_id": mia_id, "activity": "Unterhaltsreinigung"}, headers=H))
ok(c.post("/api/zeiten", json={"project_id": p2["id"], "date": "2026-10-20", "start_time": "08:00", "end_time": "16:30", "pause_minutes": 30, "workers": 3, "activity": "Grundreinigung"}, headers=H))
ok(c.post("/api/zeiten", json={"project_id": p1["id"], "date": "2026-10-22", "start_time": "10:00", "end_time": "12:00", "activity": "Glasreinigung", "service_id": glas["id"]}, headers=HM))
# ein zu langer Tag ohne Pause -> ArbZG-Hinweise auf der Übersicht
ok(c.post("/api/zeiten", json={"project_id": p1["id"], "date": "2026-10-21", "start_time": "10:00", "end_time": "21:30", "pause_minutes": 0, "user_id": mia_id, "activity": "Sonderreinigung nach Wasserschaden"}, headers=H))
ok(c.post("/api/abwesenheiten", json={"type": "urlaub", "from_date": "2026-11-02", "to_date": "2026-11-06", "note": "Herbstferien"}, headers=HM))
ok(c.post("/api/abwesenheiten", json={"user_id": mia_id, "type": "krank", "from_date": "2026-10-12", "to_date": "2026-10-13"}, headers=H))
ok(c.post("/api/rechnungen/anlegen", json={"project_id": p1["id"], "year": 2026, "month": 10}, headers=H))
ok(c.post("/api/rechnungen/anlegen", json={"project_id": p2["id"], "year": 2026, "month": 10}, headers=H))
ok(c.post(f"/api/projekte/{p1['id']}/checklisten", json={"name": "Unterhaltsreinigung EG", "items": [{"text": "Böden wischen"}, {"text": "Mülleimer leeren"}, {"text": "Sanitär reinigen"}]}, headers=H))
ok(c.post(f"/api/projekte/{p1['id']}/kommentare", json={"text": "Schlüssel liegt beim Hausmeister (Herr Kurt)."}, headers=HM))
print(f"Testdaten angelegt unter {BASIS}. Anmelden als Inhaber ({CHEF_EMAIL}) oder Mitarbeiterin ({MIA_EMAIL}), Passwörter stehen in dieser Datei.")

# ---- Plattform: zweite Firma im Verzeichnis, Einladung zum Sparkassen-Projekt, Aufgabe ----
r = c.post("/api/auth/registrieren", json={"firma_name": "Elektro Mustermann GmbH", "name": "Erika Mustermann", "email": "chef@elektro-mustermann.de", "password": CHEF_PASSWORT})
if r.status_code == 200:
    el = r.json()
    HE = {"Authorization": f"Bearer {el['token']}"}
    ok(c.put("/api/firma", json={"city": "Musterstadt", "street": "Werkstraße 7", "zip_code": "12345", "sperre_tage_mitarbeiter": 365}, headers=HE))
    ok(c.put("/api/firma/verzeichnis", json={"sichtbar": True, "gewerke": ["Elektro"], "beschreibung": "Elektroinstallation für Gewerbe", "ort": "Musterstadt"}, headers=HE))
    ok(c.post("/api/projekte/" + p1["id"] + "/leiter", json={"user_id": chef["user"]["id"], "funktion": "Hauptprojektleiter"}, headers=H))
    einladung = ok(c.post("/api/projekte/" + p1["id"] + "/beteiligungen", json={"firma_id": el["firma"]["id"], "gewerk": "Elektro"}, headers=H))["beteiligung"]
    b = ok(c.post("/api/beteiligungen/" + einladung["id"] + "/antwort", json={"annehmen": True}, headers=HE))["beteiligung"]
    heute = __import__("datetime").date.today().isoformat()
    ok(c.post("/api/projekte/" + p1["id"] + "/aufgaben", json={"titel": "Leuchten im Foyer tauschen", "beschreibung": "12 Panels, Leiter mitbringen", "gewerk": "Elektro",
                                                               "firma_id": el["firma"]["id"], "datum": heute, "start_time": "07:00", "end_time": "11:00", "prioritaet": "hoch", "bereich": "Foyer EG"}, headers=H))
    ok(c.post("/api/projekte/" + p1["id"] + "/aufgaben", json={"titel": "Treppenhaus Grundreinigung", "datum": heute, "start_time": "06:00", "end_time": "09:00", "bereich": "Treppenhaus A"}, headers=H))
    # Phase 5: Lieferung heute, Mangel mit Frist, Meilenstein, Bautagesbericht (Entwurf der Partnerfirma), geteilter Bauplan
    from datetime import date, timedelta
    frist = (date.fromisoformat(heute) + timedelta(days=3)).isoformat()
    meilenstein = (date.fromisoformat(heute) + timedelta(days=10)).isoformat()
    ok(c.post("/api/projekte/" + p1["id"] + "/lieferungen", json={"material": "LED-Panels 12 Stück", "menge": "2 Paletten", "lieferant": "Elektro-Großhandel Nord", "firma_id": el["firma"]["id"],
                                                                 "geplant_am": heute, "zeitfenster_von": "07:00", "zeitfenster_bis": "09:00", "entladeort": "Hof, Tor 2", "ansprechpartner": "Erika Mustermann"}, headers=H))
    m = ok(c.post("/api/projekte/" + p1["id"] + "/maengel", json={"beschreibung": "Kabelkanal im Foyer lose, Abdeckung fehlt", "bereich": "Foyer", "kategorie": "Elektro",
                                                               "firma_id": el["firma"]["id"], "frist": frist, "prioritaet": "hoch"}, headers=H))["mangel"]
    ok(c.post("/api/maengel/" + m["id"] + "/kommentare", json={"text": "Abdeckung ist bestellt, Montage am Freitag."}, headers=HE))
    ok(c.post("/api/projekte/" + p1["id"] + "/meilensteine", json={"titel": "Elektro Foyer fertig", "datum": meilenstein, "notiz": "Abnahme mit Hausverwaltung"}, headers=H))
    v = ok(c.get("/api/projekte/" + p1["id"] + "/tagesbericht-vorschlag?datum=" + heute, headers=HE))
    ok(c.post("/api/projekte/" + p1["id"] + "/tagesberichte", json={"datum": heute, "bereich": "Foyer", "wetter": "bedeckt, 11 °C", "firmen": v["firmen"], "mitarbeiter_anzahl": max(1, v["mitarbeiter_anzahl"]),
                                                                   "taetigkeiten": v["taetigkeiten"] or "Leuchten im Foyer getauscht", "lieferungen": v["lieferungen"], "fortschritt": "8 von 12 Panels montiert"}, headers=HE))
    ok(c.post("/api/projekte/" + p1["id"] + "/dokumente", data={"kategorie": "Baupläne", "note": "Grundriss EG mit Leuchtenplan", "fuer_alle": "true"},
              files={"datei": ("Grundriss-EG.pdf", b"%PDF-1.4\n% Demo-Bauplan Stundenzettel Pro\n", "application/pdf")}, headers=H))
    # Ausschreibung im Sparkassen-Projekt: kombiniert sichtbar + Einladung an Elektro Mustermann, Unterlage, eingereichtes Angebot, beantwortete Rückfrage; dazu ein Entwurf
    frist = (date.fromisoformat(heute) + timedelta(days=14)).isoformat()
    von, bis = (date.fromisoformat(heute) + timedelta(days=30)).isoformat(), (date.fromisoformat(heute) + timedelta(days=75)).isoformat()
    a = ok(c.post("/api/projekte/" + p1["id"] + "/ausschreibungen", json={
        "titel": "Elektro-Nachrüstung Foyer und Schalterhalle", "gewerk": "Elektro", "leistungsart": "Sanierung", "sichtbarkeit": "kombiniert", "angebotsfrist": frist,
        "ausfuehrung_von": von, "ausfuehrung_bis": bis, "beschreibung": "Austausch der Beleuchtung auf LED, neue Unterverteilung Schalterhalle, Datenverkabelung der Beratungsplätze.",
        "leistungsumfang": "Demontage Altbestand, Montage, Prüfung nach DIN VDE 0100-600, Dokumentation und Einweisung.",
        "positionen": [{"nr": "001", "leistung": "LED-Panel 60×60 inkl. Montage", "menge": 48, "einheit": "Stück"}, {"nr": "002", "leistung": "Unterverteilung Schalterhalle", "menge": 1, "einheit": "Stück"},
                       {"nr": "003", "leistung": "Datenleitung Cat.7 verlegen", "menge": 320, "einheit": "m"}],
        "kaufmaennisch": {"abrechnungsart": "einheitspreise", "budget": 48000, "zahlungsbedingungen": "30 Tage netto, Abschlag nach Montage", "vertragsbedingungen": "VOB/B, 5 % Sicherheitseinbehalt"},
        "freigabe": {"budget": True, "auftraggeber": True, "adresse": True},
        "anforderungen": {"qualifikationen": "Eingetragener Elektrofachbetrieb", "versicherungen": "Betriebshaftpflicht mind. 3 Mio. €", "sicherheit": "Arbeiten im laufenden Betrieb, Sicherheitsunterweisung vor Beginn"},
        "intern": "Zielpreis 42.000 €"}, headers=H))["ausschreibung"]
    ok(c.post("/api/ausschreibungen/" + a["id"] + "/dokumente", data={"kategorie": "Pläne", "note": "Leuchtenplan EG"}, files={"datei": ("leuchtenplan.pdf", b"%PDF-1.4\n% Demo-Leuchtenplan\n", "application/pdf")}, headers=H))
    ok(c.post("/api/ausschreibungen/" + a["id"] + "/einladungen", json={"firma_ids": [el["firma"]["id"]], "nachricht": "Wir würden uns über Ihr Angebot freuen."}, headers=H))
    ok(c.post("/api/ausschreibungen/" + a["id"] + "/veroeffentlichen", headers=H))
    g = ok(c.post("/api/ausschreibungen/" + a["id"] + "/angebot", json={"preisart": "einheitspreise", "positionen": [{"nr": "001", "einzelpreis": 185}, {"nr": "002", "einzelpreis": 4200}, {"nr": "003", "einzelpreis": 95}],
                                                                          "ansprechpartner": "Erika Mustermann", "ausfuehrung_von": von, "ausfuehrung_bis": bis, "kapazitaet": "4 Monteure, 1 Meister",
                                                                          "leistungsbeschreibung": "Komplettleistung inkl. Prüfprotokoll und Bestandsplan.", "gueltig_bis": bis}, headers=HE))["angebot"]
    ok(c.post("/api/angebote/" + g["id"] + "/einreichen", headers=HE))
    fr = ok(c.post("/api/ausschreibungen/" + a["id"] + "/fragen", json={"text": "Sind Notlichtleuchten im Leuchtenplan enthalten?", "position_nr": "001"}, headers=HE))["frage"]
    ok(c.post("/api/fragen/" + fr["id"] + "/antwort", json={"antwort": "Ja, sechs Notlichtleuchten sind in Position 001 enthalten.", "oeffentlich": True}, headers=H))
    ok(c.post("/api/projekte/" + p1["id"] + "/ausschreibungen", json={"titel": "Glasreinigung Fassade", "gewerk": "Reinigung", "beschreibung": "Quartalsweise Glasreinigung der Fassade", "sichtbarkeit": "oeffentlich", "angebotsfrist": frist}, headers=H))
    print("Plattform-Testdaten: Elektro Mustermann GmbH (chef@elektro-mustermann.de, gleiches Passwort wie Inhaber) ist am Projekt Sparkasse beteiligt.")
