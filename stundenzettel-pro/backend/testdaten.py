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
                            "iban": "DE00 1234 5678", "bank_name": "Testbank", "tax_number": "12/345/6789",
                            "bundesland": "NW", "auto_pause": True, "sperre_tage_mitarbeiter": 365}, headers=H))
mia = ok(c.post("/api/mitarbeiter", json={"name": "Mia Muster", "email": MIA_EMAIL, "role": "mitarbeiter", "personalnummer": "7"}, headers=H))
token = mia["einladung_link"].rsplit("/", 1)[-1]
mia_login = ok(c.post(f"/api/auth/einladung/{token}", json={"password": MIA_PASSWORT}))
HM = {"Authorization": f"Bearer {mia_login['token']}"}
mia_id = mia_login["user"]["id"]
ok(c.put(f"/api/mitarbeiter/{mia_id}", json={"weekly_hours": 30, "vacation_days": 24, "vacation_carryover": 2, "vacation_carryover_year": 2026, "balance_start_date": "2026-10-01"}, headers=H))
glas = ok(c.post("/api/leistungen", json={"name": "Glasreinigung", "hourly_rate": 45, "sort": 2}, headers=H))["leistung"]
ok(c.post("/api/leistungen", json={"name": "Unterhaltsreinigung", "hourly_rate": 0, "sort": 1}, headers=H))
ok(c.post("/api/leistungen", json={"name": "Grundreinigung", "hourly_rate": 38, "sort": 3}, headers=H))
kunde = ok(c.post("/api/kunden", json={"name": "Sparkasse Musterstadt", "contact": "Frau Richter", "street": "Marktplatz 2", "zip_code": "12345", "city": "Musterstadt"}, headers=H))["kunde"]
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
