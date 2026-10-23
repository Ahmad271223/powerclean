"""Tests laufen ohne MongoDB: DB_MODE=memory (mongomock_motor), jede Testfunktion bekommt eine leere Datenbank."""
import os
import sys
from pathlib import Path

os.environ["DB_MODE"] = "memory"
os.environ["JWT_SECRET"] = "test-geheimnis-mit-mindestens-zweiunddreissig-zeichen"
os.environ["ADMIN_TOKEN"] = "betreiber-test"
os.environ["BASE_URL"] = "https://pro.beispiel.de"
os.environ["DATA_DIR"] = str(Path(__file__).resolve().parent / "_daten")
os.environ["FRONTEND_DIST"] = str(Path(__file__).resolve().parent / "_kein_dist")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import db as dbmodul  # noqa: E402
from server import app  # noqa: E402


@pytest.fixture()
def client():
    dbmodul.zuruecksetzen()
    with TestClient(app) as c:
        yield c
    dbmodul.zuruecksetzen()


def registrieren(client, email="chef@beispiel.de", firma="PowerClean Test", name="Ahmad Chef", passwort="geheim123", sperre_tage=365):
    """Firma anlegen. Die Mitarbeiter-Frist (Standard 7 Tage) wird für Tests mit festen Daten weit gesetzt;
    Tests der Frist selbst setzen sie zurück."""
    r = client.post("/api/auth/registrieren", json={"firma_name": firma, "name": name, "email": email, "password": passwort})
    assert r.status_code == 200, r.text
    daten = r.json()
    kopf = {"Authorization": f"Bearer {daten['token']}"}
    if sperre_tage is not None:
        assert client.put("/api/firma", json={"sperre_tage_mitarbeiter": sperre_tage}, headers=kopf).status_code == 200
    return kopf, daten


def einladen(client, kopf, name="Mia Mitarbeiterin", email="mia@beispiel.de", role="mitarbeiter", passwort="mitarbeit123"):
    r = client.post("/api/mitarbeiter", json={"name": name, "email": email, "role": role}, headers=kopf)
    assert r.status_code == 200, r.text
    link = r.json()["einladung_link"]
    token = link.rsplit("/", 1)[-1]
    r2 = client.post(f"/api/auth/einladung/{token}", json={"password": passwort})
    assert r2.status_code == 200, r2.text
    return {"Authorization": f"Bearer {r2.json()['token']}"}, r2.json()


def projekt(client, kopf, name="Objekt Sparkasse", **extra):
    r = client.post("/api/projekte", json={"name": name, "hourly_rate": 30, **extra}, headers=kopf)
    assert r.status_code == 200, r.text
    return r.json()["projekt"]


def zeit(client, kopf, project_id, date="2026-10-05", start="08:00", ende="12:00", pause=0, **extra):
    r = client.post("/api/zeiten", json={"project_id": project_id, "date": date, "start_time": start, "end_time": ende,
                                         "pause_minutes": pause, **extra}, headers=kopf)
    assert r.status_code == 200, r.text
    return r.json()["eintrag"]
