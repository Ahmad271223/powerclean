"""Demo-Daten für die iPhone-App (ios-app/) gegen eine lokale Instanz – nur Entwicklung, nie gegen den Produktivserver.

    DB_MODE=memory FEATURE_SPRACHPLANUNG=1 python -m uvicorn server:app --port 8010    # Server ohne MongoDB
    python testdaten_app.py                                                             # gegen http://127.0.0.1:8010

Legt eine Firma mit Chef, drei Mitarbeitern (zwei heißen Nils – für Rückfragen der Spracheinteilung), zwei Projekten, Einsätzen
in dieser und der nächsten Woche und einem Urlaub an. Zugangsdaten unten; ein zweiter Lauf meldet sich nur an.
"""
import sys
from datetime import date, timedelta

import httpx

BASIS = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8010"
CHEF = ("karl@demo-bau.de", "demo-chef-2026")
MITARBEITER = [("Nils Becker", "nils.becker@demo-bau.de", "demo-nils-2026"), ("Nils Wagner", "nils.wagner@demo-bau.de", "demo-nils-2026"),
               ("Tom Wagner", "tom@demo-bau.de", "demo-tom-2026")]

c = httpx.Client(base_url=BASIS, timeout=30)


def ok(r):
    if r.status_code >= 300:
        print("FEHLER", r.request.method, r.request.url, r.status_code, r.text[:300])
        sys.exit(1)
    return r.json()


r = c.post("/api/auth/registrieren", json={"firma_name": "Müller Bau Demo GmbH", "name": "Karl Chef", "email": CHEF[0], "password": CHEF[1]})
if r.status_code == 409:
    ok(c.post("/api/auth/login", json={"email": CHEF[0], "password": CHEF[1]}))
    print("Demo-Firma gibt es schon – Anmeldung geprüft.")
    sys.exit(0)
H = {"Authorization": f"Bearer {ok(r)['token']}"}
ok(c.put("/api/firma", json={"bundesland": "NI", "sperre_tage_mitarbeiter": 365}, headers=H))
ids = {}
for name, email, passwort in MITARBEITER:
    link = ok(c.post("/api/mitarbeiter", json={"name": name, "email": email, "role": "mitarbeiter"}, headers=H))["einladung_link"]
    ids[name] = ok(c.post(f"/api/auth/einladung/{link.rsplit('/', 1)[-1]}", json={"password": passwort}))["user"]["id"]
mueller = ok(c.post("/api/projekte", json={"name": "Badsanierung Müller", "address": "Hauptstraße 5, 30159 Hannover", "hourly_rate": 52}, headers=H))["projekt"]
schmidt = ok(c.post("/api/projekte", json={"name": "Dachsanierung Schmidt", "address": "Lindenweg 12, 30655 Hannover", "hourly_rate": 55, "color": "#1D4ED8"}, headers=H))["projekt"]
montag = date.today() - timedelta(days=date.today().weekday())
woche = lambda m, n: [(m + timedelta(days=i)).isoformat() for i in range(n)]  # noqa: E731
ok(c.post("/api/einsatzplan", json={"project_id": mueller["id"], "user_ids": [ids["Nils Becker"]], "dates": woche(montag, 5), "start_time": "07:00", "end_time": "16:00",
                                    "note": "Schlüssel beim Hausmeister, Eingang Hof", "taetigkeit": "Fliesen Bad OG"}, headers=H))
ok(c.post("/api/einsatzplan", json={"project_id": schmidt["id"], "user_ids": [ids["Tom Wagner"], ids["Nils Wagner"]], "dates": woche(montag, 4), "start_time": "06:30", "end_time": "15:00"}, headers=H))
ok(c.post("/api/einsatzplan", json={"project_id": schmidt["id"], "user_ids": [ids["Nils Becker"]], "dates": woche(montag + timedelta(days=7), 3), "start_time": "07:00", "end_time": "15:30"}, headers=H))
ok(c.post("/api/abwesenheiten", json={"user_id": ids["Tom Wagner"], "type": "urlaub", "from_date": (montag + timedelta(days=4)).isoformat(), "to_date": (montag + timedelta(days=4)).isoformat()}, headers=H))
print(f"Fertig. Chef: {CHEF[0]}, Mitarbeiter: {', '.join(m[1] for m in MITARBEITER)} (Passwörter in dieser Datei).")
