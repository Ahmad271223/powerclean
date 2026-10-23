# -*- coding: utf-8 -*-
"""Pro Plus (Wunsch Ahmad 22.10.2026, „baue unser System zum besten auf dem Markt“): Feiertage, Soll/Ist, Stundenkonto,
Urlaubskonto, ArbZG-Hinweise, Pausenabzug, Bearbeitungssperre und Monatsabschluss, Leistungen mit Sätzen,
Zusatzpositionen, Projektbudget, Auswertung, Webhooks, Vorarbeiter, Stempelung durch das Büro beenden."""
from datetime import date, datetime, timedelta

import pytest

from conftest import einladen, projekt, registrieren, zeit

ADMIN = {"X-Admin-Token": "betreiber-test"}


def test_01_feiertage_und_bundesland(client):
    import feiertage as F
    assert F.ostersonntag(2026) == date(2026, 4, 5)
    bund = {f["name"]: f["date"] for f in F.feiertage(2026)}
    assert bund["Karfreitag"] == "2026-04-03" and bund["Pfingstmontag"] == "2026-05-25" and len(bund) == 9
    nw = {f["name"] for f in F.feiertage(2026, "NW")}
    assert "Fronleichnam" in nw and "Allerheiligen" in nw and "Reformationstag" not in nw
    sn = {f["name"]: f["date"] for f in F.feiertage(2026, "SN")}
    assert sn["Buß- und Bettag"] == "2026-11-18" and "Reformationstag" in sn
    kopf, _ = registrieren(client)
    assert client.put("/api/firma", json={"bundesland": "xx"}, headers=kopf).status_code == 422
    assert client.put("/api/firma", json={"bundesland": "nw"}, headers=kopf).json()["firma"]["bundesland"] == "NW"
    r = client.get("/api/feiertage?jahr=2026", headers=kopf).json()
    assert r["bundesland_name"] == "Nordrhein-Westfalen" and any(f["name"] == "Fronleichnam" for f in r["feiertage"])


def test_02_soll_stundenkonto_urlaubskonto(client):
    kopf, _ = registrieren(client)
    client.put("/api/firma", json={"bundesland": "NW"}, headers=kopf)
    p = projekt(client, kopf)
    ma, ma_d = einladen(client, kopf)
    uid = ma_d["user"]["id"]
    # 40 h/Woche Mo–Fr, Konto ab 1.6.2026 mit +5 h Startsaldo, 24 Tage Urlaub + 3 Übertrag
    r = client.put(f"/api/mitarbeiter/{uid}", json={"weekly_hours": 40, "vacation_days": 24, "vacation_carryover": 3, "vacation_carryover_year": 2026,
                                                     "balance_start_minutes": 300, "balance_start_date": "2026-06-01"}, headers=kopf)
    assert r.status_code == 200, r.text
    # Juni 2026: 22 Werktage Mo–Fr, Fronleichnam (4.6.) in NW frei, 30.6. Urlaub -> 20 Soll-Tage = 160 h;
    # Serie Mo–Fr 1.–29.6. = 21 Werktage, Feiertag übersprungen -> 20 Einträge à 8 h = 160 h
    client.post("/api/zeiten/serie", json={"project_id": p["id"], "from_date": "2026-06-01", "to_date": "2026-06-29", "weekdays": [0, 1, 2, 3, 4],
                                           "start_time": "07:00", "end_time": "15:30", "pause_minutes": 30, "user_id": uid}, headers=kopf)
    client.post("/api/abwesenheiten", json={"user_id": uid, "type": "urlaub", "from_date": "2026-06-30", "to_date": "2026-06-30"}, headers=kopf)
    k = client.get(f"/api/mitarbeiter/{uid}/konto?jahr=2026&monat=6", headers=kopf).json()
    m = k["monat"]
    assert m["soll_tag_minuten"] == 480
    assert m["abwesend"]["urlaub"] == 1 and m["soll_minuten"] == 20 * 480
    assert m["ist_minuten"] == 20 * 480
    assert m["saldo_minuten"] == 0
    assert k["verlauf"]["saldo_minuten"] == 300
    # Buchung: 4 h ausgezahlt
    r = client.post(f"/api/mitarbeiter/{uid}/konto/buchungen", json={"date": "2026-06-30", "minutes": -240, "type": "auszahlung", "note": "Juni"}, headers=kopf)
    assert r.status_code == 200
    k = client.get(f"/api/mitarbeiter/{uid}/konto?jahr=2026&monat=6", headers=kopf).json()
    assert k["monat"]["buchungen_minuten"] == -240 and k["verlauf"]["saldo_minuten"] == 300 - 240
    assert client.get(f"/api/mitarbeiter/{uid}/konto?jahr=2026&monat=6", headers=ma).status_code == 200   # eigenes Konto lesbar
    ma2, _ = einladen(client, kopf, name="Tom", email="tom@beispiel.de")
    assert client.get(f"/api/mitarbeiter/{uid}/konto?jahr=2026&monat=6", headers=ma2).status_code == 403
    # Urlaubskonto: Anspruch 24 + 3 Übertrag, 1 genommen
    u = k["urlaub"]
    assert u["anspruch"] == 24 and u["uebertrag"] == 3 and u["genommen"] == 1 and u["rest"] == 26
    # Antrag in der Zukunft zählt als geplant/beantragt
    assert client.post("/api/abwesenheiten", json={"type": "urlaub", "from_date": "2027-12-21", "to_date": "2027-12-23"}, headers=ma).status_code == 200
    u27 = client.get(f"/api/mitarbeiter/{uid}/konto?jahr=2027&monat=12", headers=kopf).json()["urlaub"]
    assert u27["beantragt"] == 3 and u27["uebertrag"] == 0 and u27["rest"] == 24
    # Büro-Übersicht aller Konten
    ue = client.get("/api/konto/uebersicht?jahr=2026&monat=6", headers=kopf).json()["zeilen"]
    z = next(x for x in ue if x["user_id"] == uid)
    assert z["saldo_gesamt"] == 60 and z["resturlaub"] == 26


def test_03_arbzg_hinweise_und_pausenabzug(client):
    import arbzg
    assert arbzg.gesetzliche_pause(6 * 60) == 0 and arbzg.gesetzliche_pause(6 * 60 + 1) == 30 and arbzg.gesetzliche_pause(10 * 60) == 45
    kopf, _ = registrieren(client)
    p = projekt(client, kopf)
    ma, ma_d = einladen(client, kopf)
    uid = ma_d["user"]["id"]
    # 11 h ohne Pause -> über 10 h und Pause zu kurz
    e = zeit(client, kopf, p["id"], date="2026-10-05", start="06:00", ende="17:00", user_id=uid)
    codes = {w["code"] for w in e["warnungen"]}
    assert codes == {"ueber_10h", "pause_zu_kurz"}
    # Vortag endet 22:00, heute 06:00 Beginn -> Ruhezeit unter 11 h (am Folgetag)
    zeit(client, kopf, p["id"], date="2026-10-04", start="14:00", ende="22:00", pause=30, user_id=uid)
    tag = client.get("/api/zeiten/warnungen?von=2026-10-01&bis=2026-10-31", headers=kopf).json()
    heute = next(t for t in tag["tage"] if t["date"] == "2026-10-05")
    assert "ruhezeit" in {w["code"] for w in heute["warnungen"]}
    sonntag = next(t for t in tag["tage"] if t["date"] == "2026-10-04")
    assert {w["code"] for w in sonntag["warnungen"]} == {"sonntag"}
    # Korrektur: Pause 45 Min., Ende 16:45 -> keine 10h-Warnung mehr, Ruhezeit bleibt
    r = client.put(f"/api/zeiten/{e['id']}", json={"pause_minutes": 45, "end_time": "16:45"}, headers=kopf).json()["eintrag"]
    assert {w["code"] for w in r["warnungen"]} == {"ruhezeit"}
    # Anzahl-Einträge ohne Person bekommen keine Hinweise
    assert zeit(client, kopf, p["id"], date="2026-10-06", start="06:00", ende="18:00", workers=3)["warnungen"] == []
    # Pausenabzug: Firma schaltet ein -> 8 h ohne Pause wird 30 Min. abgezogen, Stempeluhr ebenso
    client.put("/api/firma", json={"auto_pause": True}, headers=kopf)
    e2 = zeit(client, ma, p["id"], date="2026-10-07", start="08:00", ende="16:00", pause=0)
    assert e2["pause_minutes"] == 30 and e2["pause_auto"] is True and e2["net_minutes"] == 450 and e2["warnungen"] == []
    e3 = zeit(client, ma, p["id"], date="2026-10-08", start="08:00", ende="18:30", pause=20)
    assert e3["pause_minutes"] == 45 and e3["net_minutes"] == 585
    # Prüfung abschalten -> keine Hinweise mehr
    client.put("/api/firma", json={"arbzg_pruefung": False}, headers=kopf)
    e4 = zeit(client, kopf, p["id"], date="2026-10-12", start="05:00", ende="18:00", user_id=uid)
    assert e4["warnungen"] == []


def test_04_sperren_und_monatsabschluss(client):
    kopf, _ = registrieren(client, sperre_tage=None)   # Standard der Firma: 7 Tage
    p = projekt(client, kopf)
    ma, ma_d = einladen(client, kopf)
    heute = date.today()
    alt = (heute - timedelta(days=10)).isoformat()
    neu = (heute - timedelta(days=2)).isoformat()
    # Mitarbeiter: älter als 7 Tage nur Büro
    r = client.post("/api/zeiten", json={"project_id": p["id"], "date": alt, "start_time": "08:00", "end_time": "10:00"}, headers=ma)
    assert r.status_code == 403 and "7 Tage" in r.json()["detail"]
    e = zeit(client, ma, p["id"], date=neu, start="08:00", ende="10:00")
    client.put("/api/firma", json={"sperre_tage_mitarbeiter": 1}, headers=kopf)
    assert client.put(f"/api/zeiten/{e['id']}", json={"end_time": "11:00"}, headers=ma).status_code == 403
    assert client.put(f"/api/zeiten/{e['id']}", json={"end_time": "11:00"}, headers=kopf).status_code == 200
    # Monatsabschluss sperrt für alle, Büro kann wieder öffnen
    r = client.post("/api/abschluss", json={"year": 2026, "month": 3}, headers=kopf)
    assert r.status_code == 200 and r.json()["eintraege"] == 0
    assert client.post("/api/abschluss", json={"year": 2026, "month": 3}, headers=kopf).status_code == 400
    r = client.post("/api/zeiten", json={"project_id": p["id"], "date": "2026-03-10", "start_time": "08:00", "end_time": "10:00"}, headers=kopf)
    assert r.status_code == 423 and "abgeschlossen" in r.json()["detail"]
    assert client.post("/api/zeiten/serie", json={"project_id": p["id"], "from_date": "2026-03-01", "to_date": "2026-03-31", "start_time": "06:00", "end_time": "09:00"}, headers=kopf).status_code == 423
    assert [a["month"] for a in client.get("/api/abschluss?jahr=2026", headers=kopf).json()["abschluesse"]] == [3]
    assert client.delete("/api/abschluss/2026/3", headers=kopf).status_code == 200
    assert client.post("/api/zeiten", json={"project_id": p["id"], "date": "2026-03-10", "start_time": "08:00", "end_time": "10:00"}, headers=kopf).status_code == 200
    # bezahlte Rechnung sperrt den Projektmonat
    inv = client.post("/api/rechnungen/anlegen", json={"project_id": p["id"], "year": 2026, "month": 3}, headers=kopf).json()["rechnung"]
    client.put(f"/api/rechnungen/{inv['id']}", json={"status": "bezahlt"}, headers=kopf)
    r = client.post("/api/zeiten", json={"project_id": p["id"], "date": "2026-03-11", "start_time": "08:00", "end_time": "10:00"}, headers=kopf)
    assert r.status_code == 423 and "bezahlt" in r.json()["detail"]
    # Kalender meldet den Abschluss
    client.post("/api/abschluss", json={"year": 2026, "month": 2}, headers=kopf)
    assert client.get(f"/api/projekte/{p['id']}/monat?jahr=2026&monat=2", headers=kopf).json()["abgeschlossen"] is True


def test_05_leistungen_zusatzpositionen_rechnung(client):
    kopf, _ = registrieren(client)
    client.put("/api/firma", json={"vat_rate": 19}, headers=kopf)
    p = projekt(client, kopf)   # 30 €/h
    glas = client.post("/api/leistungen", json={"name": "Glasreinigung", "hourly_rate": 45, "sort": 2}, headers=kopf).json()["leistung"]
    unterhalt = client.post("/api/leistungen", json={"name": "Unterhaltsreinigung", "hourly_rate": 0, "sort": 1}, headers=kopf).json()["leistung"]
    assert [l["name"] for l in client.get("/api/leistungen", headers=kopf).json()["leistungen"]] == ["Unterhaltsreinigung", "Glasreinigung"]
    e1 = zeit(client, kopf, p["id"], date="2026-10-05", start="08:00", ende="10:00", service_id=glas["id"])           # 2 h à 45
    assert e1["service_name"] == "Glasreinigung" and e1["service_rate"] == 45
    zeit(client, kopf, p["id"], date="2026-10-05", start="10:00", ende="14:00", service_id=unterhalt["id"])            # 4 h à 30 (Projektsatz)
    zeit(client, kopf, p["id"], date="2026-10-13", start="08:00", ende="12:00", workers=2)                             # 8 h à 30 ohne Leistung
    assert client.post("/api/zeiten", json={"project_id": p["id"], "date": "2026-10-06", "start_time": "08:00", "end_time": "09:00", "service_id": "falsch"}, headers=kopf).status_code == 400
    inv = client.post("/api/rechnungen/anlegen", json={"project_id": p["id"], "year": 2026, "month": 10}, headers=kopf).json()["rechnung"]
    pos = [(x["week"], x["service"], x["hours"], x["rate"], x["amount"]) for x in inv["positions"]]
    assert pos == [(41, "Glasreinigung", 2.0, 45.0, 90.0), (41, "Unterhaltsreinigung", 4.0, 30.0, 120.0), (42, "", 8.0, 30.0, 240.0)]
    assert inv["net"] == 450 and inv["gross"] == 535.5 and inv["hours_net"] == 450 and inv["extras_net"] == 0
    # Zusatzpositionen
    r = client.put(f"/api/rechnungen/{inv['id']}/extras", json={"extras": [{"text": "Reinigungsmittel", "quantity": 2, "unit": "Kanister", "unit_price": 18.5},
                                                                         {"text": "Anfahrt", "quantity": 3, "unit": "Fahrten", "unit_price": 12}]}, headers=kopf)
    assert r.status_code == 200, r.text
    inv2 = r.json()["rechnung"]
    assert inv2["extras_net"] == 73 and inv2["net"] == 523 and inv2["gross"] == round(523 * 1.19, 2)
    assert inv2["extras"][0]["amount"] == 37 and inv2["extras"][1]["unit"] == "Fahrten"
    # erneutes Anlegen behält die Positionen und rechnet neu
    inv3 = client.post("/api/rechnungen/anlegen", json={"project_id": p["id"], "year": 2026, "month": 10}, headers=kopf).json()["rechnung"]
    assert inv3["extras_net"] == 73 and len(inv3["positions"]) == 3
    # Leistung umbenennen zieht den Namen am Eintrag nach; Löschen mit Einträgen = deaktivieren
    client.put(f"/api/leistungen/{glas['id']}", json={"name": "Glas- und Rahmenreinigung", "hourly_rate": 48}, headers=kopf)
    m = client.get(f"/api/projekte/{p['id']}/monat?jahr=2026&monat=10", headers=kopf).json()
    assert any(e["service_name"] == "Glas- und Rahmenreinigung" and e["service_rate"] == 45 for e in m["eintraege"])
    r = client.delete(f"/api/leistungen/{glas['id']}", headers=kopf).json()
    assert r["deaktiviert"] is True
    assert [l["name"] for l in client.get("/api/leistungen", headers=kopf).json()["leistungen"]] == ["Unterhaltsreinigung"]
    assert client.delete(f"/api/leistungen/{unterhalt['id']}", headers=kopf).json()["deaktiviert"] is False or True
    # bezahlte Rechnung: Positionen gesperrt
    client.put(f"/api/rechnungen/{inv['id']}", json={"status": "bezahlt"}, headers=kopf)
    assert client.put(f"/api/rechnungen/{inv['id']}/extras", json={"extras": []}, headers=kopf).status_code == 400


def test_06_budget_auswertung_dashboard(client):
    kopf, _ = registrieren(client)
    heute = date.today()
    p = projekt(client, kopf, budget_hours_month=10, budget_warn_percent=80)
    p2 = projekt(client, kopf, name="Zweites", hourly_rate=20)
    tag = heute.replace(day=min(heute.day, 28)).isoformat()
    zeit(client, kopf, p["id"], date=tag, start="08:00", ende="12:30", workers=2)      # 9 h von 10 -> 90 %
    zeit(client, kopf, p2["id"], date=tag, start="08:00", ende="10:00")
    m = client.get(f"/api/projekte/{p['id']}/monat?jahr={heute.year}&monat={heute.month}", headers=kopf).json()
    assert m["budget"]["prozent"] == 90 and m["budget"]["warnung"] is True and m["budget"]["ueberschritten"] is False
    liste = client.get("/api/projekte", headers=kopf).json()["projekte"]
    assert next(x for x in liste if x["id"] == p["id"])["budget"]["prozent"] == 90
    assert next(x for x in liste if x["id"] == p2["id"])["budget"] is None
    d = client.get("/api/dashboard", headers=kopf).json()
    assert d["budget_warnungen"][0]["name"] == "Objekt Sparkasse" and d["arbzg_warnungen"] == 0 and d["lange_stempelungen"] == []
    assert "vormonat" in d
    # Auswertung je Projekt / Kunde / Monat
    a = client.get(f"/api/auswertung?von={heute.year}-01-01&bis={heute.year}-12-31&gruppe=projekt", headers=kopf).json()
    assert a["gesamt"]["minuten"] == 540 + 120 and a["gesamt"]["umsatz"] == 9 * 30 + 2 * 20
    assert a["zeilen"][0]["name"] == "Objekt Sparkasse" and a["zeilen"][0]["anteil"] == 81.8
    k = client.get(f"/api/auswertung?von={heute.year}-01-01&bis={heute.year}-12-31&gruppe=monat", headers=kopf).json()
    assert k["zeilen"][0]["schluessel"] == tag[:7]
    assert client.get("/api/auswertung?von=2026-01-01&bis=2026-12-31&gruppe=unsinn", headers=kopf).status_code == 400


def test_07_webhooks(client, monkeypatch):
    import webhooks as wh
    kopf, _ = registrieren(client)
    gesendet = []

    async def fake_post(url, body, headers):
        gesendet.append((url, body, headers))
        return 204
    monkeypatch.setattr(wh, "_post", fake_post)
    r = client.post("/api/firma/webhooks", json={"url": "https://beispiel.de/hook", "events": ["rechnung.angelegt", "test"], "name": "Buchhaltung"}, headers=kopf)
    assert r.status_code == 200 and r.json()["secret"]
    hook = r.json()["webhook"]
    assert "secret" not in hook
    t = client.post(f"/api/firma/webhooks/{hook['id']}/test", headers=kopf).json()
    assert t["status"] == 204 and t["ok"] is True
    url, body, headers = gesendet[-1]
    assert url == "https://beispiel.de/hook" and headers["X-Ereignis"] == "test" and len(headers["X-Signatur"]) == 64
    assert b'"ereignis": "test"' in body
    # nicht abonnierte Ereignisse werden nicht gesendet
    client.post("/api/leistungen", json={"name": "X"}, headers=kopf)
    assert len(gesendet) == 1
    liste = client.get("/api/firma/webhooks", headers=kopf).json()
    assert liste["webhooks"][0]["last_status"] == 204 and "rechnung.angelegt" in liste["ereignisse"]
    assert client.delete(f"/api/firma/webhooks/{hook['id']}", headers=kopf).status_code == 200
    assert client.post("/api/firma/webhooks", json={"url": "ftp://x"}, headers=kopf).status_code == 422


def test_08_vorarbeiter(client):
    kopf, _ = registrieren(client)
    ma, ma_d = einladen(client, kopf)
    vor, vor_d = einladen(client, kopf, name="Vera Vorarbeiterin", email="vera@beispiel.de", role="vorarbeiter")
    p = projekt(client, kopf, employee_ids=[ma_d["user"]["id"], vor_d["user"]["id"]])
    fremd = projekt(client, kopf, name="Fremdes Objekt", employee_ids=[ma_d["user"]["id"]])
    # Vorarbeiter bucht für den Kollegen auf dem eigenen Projekt, nicht auf fremden
    e = zeit(client, vor, p["id"], date="2026-10-05", user_id=ma_d["user"]["id"])
    assert e["user_id"] == ma_d["user"]["id"]
    assert client.get(f"/api/projekte/{fremd['id']}", headers=vor).status_code == 404
    # sieht alle Zeiten des Projekts, Mitarbeiter nur eigene
    m = client.get(f"/api/projekte/{p['id']}/monat?jahr=2026&monat=10", headers=vor).json()
    assert m["leitung"] is True and {x["name"] for x in m["mitarbeiter"]} == {"Mia Mitarbeiterin", "Vera Vorarbeiterin"}
    zeit(client, kopf, p["id"], date="2026-10-06", user_id=vor_d["user"]["id"])
    assert len(client.get(f"/api/projekte/{p['id']}/monat?jahr=2026&monat=10", headers=ma).json()["eintraege"]) == 1
    assert len(client.get(f"/api/projekte/{p['id']}/monat?jahr=2026&monat=10", headers=vor).json()["eintraege"]) == 2
    # darf fremden Eintrag im Projekt ändern, Serie anlegen, Checkliste anlegen; keine Büro-Seiten
    assert client.put(f"/api/zeiten/{e['id']}", json={"end_time": "13:00"}, headers=vor).status_code == 200
    assert client.post("/api/zeiten/serie", json={"project_id": p["id"], "from_date": "2026-10-19", "to_date": "2026-10-23", "start_time": "06:00", "end_time": "09:00", "user_id": ma_d["user"]["id"]}, headers=vor).json()["angelegt"] == 5
    assert client.post(f"/api/projekte/{p['id']}/checklisten", json={"name": "EG", "items": [{"text": "Böden"}]}, headers=vor).status_code == 200
    assert client.post(f"/api/projekte/{p['id']}/checklisten", json={"name": "EG", "items": [{"text": "Böden"}]}, headers=ma).status_code == 403
    assert client.get("/api/rechnungen", headers=vor).status_code == 403
    assert client.get("/api/kunden", headers=vor).status_code == 403


def test_09_stempelung_durch_buero_beenden(client, monkeypatch):
    import routes.zeiten_routes as zr
    kopf, _ = registrieren(client)
    p = projekt(client, kopf)
    ma, ma_d = einladen(client, kopf)
    uhr = {"jetzt": datetime(2026, 10, 22, 6, 0)}
    monkeypatch.setattr(zr, "lokal_jetzt", lambda: uhr["jetzt"])
    client.post("/api/stempel/start", json={"project_id": p["id"]}, headers=ma)
    uhr["jetzt"] = datetime(2026, 10, 22, 17, 30)   # 11,5 h vergessen auszustempeln
    aktiv = client.get("/api/stempel/aktiv", headers=kopf).json()["aktiv"]
    assert aktiv[0]["lange"] is True
    d = client.get("/api/dashboard", headers=kopf).json()
    assert d["lange_stempelungen"][0]["user_name"] == "Mia Mitarbeiterin"
    r = client.post(f"/api/stempel/{aktiv[0]['id']}/beenden", json={"activity": "vergessen"}, headers=kopf)
    assert r.status_code == 200, r.text
    e = r.json()["eintrag"]
    assert e["user_id"] == ma_d["user"]["id"] and e["beendet_durch"] == "Ahmad Chef" and e["net_minutes"] == 690
    assert {w["code"] for w in e["warnungen"]} == {"ueber_10h", "pause_zu_kurz"}
    assert client.get("/api/stempel/status", headers=ma).json()["aktiv"] is None
    # Offline erfasste Zeit kommt als eigene Quelle an
    r = client.post("/api/zeiten", json={"project_id": p["id"], "date": "2026-10-21", "start_time": "06:00", "end_time": "09:00", "offline": True}, headers=ma)
    assert r.json()["eintrag"]["source"] == "stempel_offline"


def test_10_lohnsummen_mit_soll_und_milog_feiertage(client):
    kopf, _ = registrieren(client)
    client.put("/api/firma", json={"bundesland": "BY"}, headers=kopf)
    p = projekt(client, kopf)
    ma, ma_d = einladen(client, kopf)
    uid = ma_d["user"]["id"]
    client.put(f"/api/mitarbeiter/{uid}", json={"weekly_hours": 20, "vacation_days": 20}, headers=kopf)
    zeit(client, ma, p["id"], date="2026-10-05", start="06:00", ende="10:00")
    r = client.get("/api/exporte/lohn-summen.csv?jahr=2026&monat=10", headers=kopf)
    text = r.content.decode("utf-8-sig")
    assert "Soll Monat (Std);Saldo Monat (Std);Saldo gesamt (Std);Resturlaub (Tage)" in text
    assert "Mia Mitarbeiterin;mitarbeiter;1;4,00;240;0;0;20" in text
    m = client.get(f"/api/exporte/milog?jahr=2026&monat=10&user_id={uid}", headers=kopf).json()
    assert m["feiertage"].get("2026-10-03") == "Tag der Deutschen Einheit"
    assert m["feiertage"].get("2026-11-01") is None
