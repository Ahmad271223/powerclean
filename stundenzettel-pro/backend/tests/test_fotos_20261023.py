"""Fotos am Arbeitstag: Upload mit Datum, Fotos im Monatsabruf, verkleinertes Bild, Rechte, Datum ändern – 2026-10-23."""
import io
from datetime import date

from PIL import Image

from conftest import einladen, projekt, registrieren, zeit


def _png(breite=640, hoehe=320, farbe=(200, 30, 60)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (breite, hoehe), farbe).save(buf, "PNG")
    return buf.getvalue()


def _hochladen(client, kopf, project_id, datum="", note="", name="vorher.png"):
    daten = {"kategorie": "Fotos", "note": note}
    if datum:
        daten["date"] = datum
    r = client.post(f"/api/projekte/{project_id}/dateien", data=daten, files={"datei": (name, _png(), "image/png")}, headers=kopf)
    assert r.status_code == 200, r.text
    return r.json()["dokument"]


def test_01_fotos_haengen_am_arbeitstag(client):
    kopf, chef = registrieren(client)
    p = projekt(client, kopf)
    zeit(client, kopf, p["id"], date="2026-10-07", start="08:00", ende="10:00")
    f1 = _hochladen(client, kopf, p["id"], datum="2026-10-07", note="Vorher Treppenhaus")
    f2 = _hochladen(client, kopf, p["id"], note="ohne Datum")      # fällt auf den Upload-Tag zurück
    assert f1["date"] == "2026-10-07" and f1["note"] == "Vorher Treppenhaus" and f2["date"] is None
    m = client.get(f"/api/projekte/{p['id']}/monat?jahr=2026&monat=10", headers=kopf).json()
    tage = {f["id"]: f["tag"] for f in m["fotos"]}
    assert tage[f1["id"]] == "2026-10-07"
    heute = date.today().isoformat()
    if m["raster"]["von"] <= heute <= m["raster"]["bis"]:
        assert tage[f2["id"]] == heute
    assert all("path" not in f for f in m["fotos"])
    # Datum/Notiz nachträglich ändern → Foto wandert auf den anderen Tag
    r = client.put(f"/api/dokumente/{f1['id']}", json={"date": "2026-10-09", "note": "Nachher"}, headers=kopf)
    assert r.status_code == 200 and r.json()["dokument"]["date"] == "2026-10-09"
    m2 = client.get(f"/api/projekte/{p['id']}/monat?jahr=2026&monat=10", headers=kopf).json()
    assert next(f for f in m2["fotos"] if f["id"] == f1["id"])["tag"] == "2026-10-09"
    assert client.put(f"/api/dokumente/{f1['id']}", json={"date": "2020-01-01"}, headers=kopf).status_code == 422
    # Rechnungsdaten liefern die Fotos ebenfalls (für die PDF-Auswahl auf der Rechnungsseite)
    inv = client.post("/api/rechnungen/anlegen", json={"project_id": p["id"], "year": 2026, "month": 10}, headers=kopf).json()["rechnung"]
    d = client.get(f"/api/rechnungen/{inv['id']}/daten", headers=kopf).json()
    assert any(f["id"] == f1["id"] for f in d["fotos"])


def test_02_bild_verkleinert_und_rechte(client):
    kopf, chef = registrieren(client)
    mia_kopf, mia = einladen(client, kopf)
    p = projekt(client, kopf, employee_ids=[chef["user"]["id"]])     # Mia ist dem Projekt nicht zugeordnet
    f = _hochladen(client, kopf, p["id"], datum="2026-10-07")
    r = client.get(f"/api/dokumente/{f['id']}/bild?max=200", headers=kopf)
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    bild = Image.open(io.BytesIO(r.content))
    assert bild.format == "JPEG" and max(bild.size) == 200 and bild.size == (200, 100)
    assert len(r.content) < len(_png())
    assert client.get(f"/api/dokumente/{f['id']}/bild", headers=mia_kopf).status_code == 403
    assert client.put(f"/api/dokumente/{f['id']}", json={"note": "x"}, headers=mia_kopf).status_code == 403
    # keine Bilddatei → 400
    r2 = client.post(f"/api/projekte/{p['id']}/dateien", data={"kategorie": "Protokolle"}, files={"datei": ("p.txt", b"Protokoll", "text/plain")}, headers=kopf)
    assert r2.status_code == 200
    assert client.get(f"/api/dokumente/{r2.json()['dokument']['id']}/bild", headers=kopf).status_code == 400
    # Mitarbeiterin im Projekt darf eigene Fotos hochladen und ändern, fremde nicht
    p2 = projekt(client, kopf, name="Objekt Mia", employee_ids=[mia["user"]["id"]])
    eigenes = _hochladen(client, mia_kopf, p2["id"], datum="2026-10-08", note="Nachher")
    assert client.put(f"/api/dokumente/{eigenes['id']}", json={"note": "Nachher Küche"}, headers=mia_kopf).status_code == 200
    fremdes = _hochladen(client, kopf, p2["id"], datum="2026-10-08")
    assert client.put(f"/api/dokumente/{fremdes['id']}", json={"note": "x"}, headers=mia_kopf).status_code == 403
    assert client.get(f"/api/dokumente/{fremdes['id']}/bild?max=120", headers=mia_kopf).status_code == 200
