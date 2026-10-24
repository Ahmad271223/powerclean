"""Stufe A (24.10.2026): Fotoschutz für Kollegen, vergebbare Rechte je Büro-Nutzer, GU-Freischaltung nach der Testphase."""
import asyncio
import io
from datetime import timedelta

import db as dbmodul
from auth import jetzt
from conftest import einladen, projekt, registrieren, zeit

ADMIN = {"X-Admin-Token": "betreiber-test"}
TENDER = {"titel": "Elektro", "gewerk": "Elektro", "beschreibung": "x", "sichtbarkeit": "oeffentlich", "angebotsfrist": "2026-12-20"}


def _jpeg_mit_exif() -> bytes:
    from PIL import Image
    bild = Image.new("RGB", (120, 90), (200, 120, 40))
    exif = Image.Exif()
    exif[0x010F] = "Testkamera"          # Make
    exif[0x013B] = "Fotograf Ben"        # Artist
    buf = io.BytesIO()
    bild.save(buf, "JPEG", exif=exif.tobytes())
    return buf.getvalue()


def test_01_fotos_kollegen_ohne_fotograf_dateiname_und_exif(client):
    chef, _ = registrieren(client, email="chef@foto-a.de", firma="Foto A", name="Chef")
    buero, _ = einladen(client, chef, name="Bea Büro", email="bea@foto-a.de", role="buero")
    ma1, d1 = einladen(client, chef, name="Anna", email="anna@foto-a.de", role="mitarbeiter")
    ma2, d2 = einladen(client, chef, name="Ben", email="ben@foto-a.de", role="mitarbeiter", passwort="geheim456")
    p = projekt(client, chef, name="Objekt")
    r = client.post(f"/api/projekte/{p['id']}/dateien", data={"kategorie": "Fotos", "date": "2026-10-05", "note": "Verteiler"},
                    files={"datei": ("ben-handy-IMG_0042.jpg", _jpeg_mit_exif(), "image/jpeg")}, headers=ma2)
    assert r.status_code == 200, r.text
    foto = r.json()["dokument"]
    assert foto["uploaded_by"] == d2["user"]["id"] and foto["filename"].startswith("ben-handy")   # der Fotograf sieht sein eigenes Foto vollständig
    # Kollegin: Foto sichtbar, aber ohne Fotograf, ohne Originaldateiname; Download ist eine EXIF-freie JPEG-Kopie
    monat = client.get(f"/api/projekte/{p['id']}/monat?jahr=2026&monat=10", headers=ma1).json()
    sicht = next(f for f in monat["fotos"] if f["id"] == foto["id"])
    assert "uploaded_by" not in sicht and "uploaded_by_name" not in sicht and sicht["filename"] == "Projektfoto.jpg" and sicht["note"] == "Verteiler"
    akte = client.get(f"/api/projekte/{p['id']}/akte", headers=ma1).json()
    assert next(d for d in akte["dateien"] if d["id"] == foto["id"]).get("uploaded_by_name") is None
    datei = client.get(f"/api/dokumente/{foto['id']}/datei", headers=ma1)
    assert datei.status_code == 200 and datei.headers["content-type"].startswith("image/jpeg") and b"Fotograf Ben" not in datei.content and b"Testkamera" not in datei.content
    assert "ben-handy" not in datei.headers.get("content-disposition", "")
    original = client.get(f"/api/dokumente/{foto['id']}/datei", headers=ma2)
    assert b"Fotograf Ben" in original.content   # der Fotograf selbst bekommt das Original
    # Inhaber und Büro (Personalrecht) sehen den Fotografen
    chef_sicht = next(f for f in client.get(f"/api/projekte/{p['id']}/monat?jahr=2026&monat=10", headers=chef).json()["fotos"] if f["id"] == foto["id"])
    assert chef_sicht["uploaded_by_name"] == "Ben"
    assert next(f for f in client.get(f"/api/projekte/{p['id']}/monat?jahr=2026&monat=10", headers=buero).json()["fotos"] if f["id"] == foto["id"])["uploaded_by_name"] == "Ben"
    # Löschen: Kollegin nein, Fotograf ja
    assert client.delete(f"/api/dokumente/{foto['id']}", headers=ma1).status_code == 403
    assert client.delete(f"/api/dokumente/{foto['id']}", headers=ma2).status_code == 200


def test_02_rechte_je_buero_nutzer(client):
    chef, _ = registrieren(client, email="chef@rechte-a.de", firma="Rechte A", name="Chef")
    buero, bd = einladen(client, chef, name="Bea Büro", email="bea@rechte-a.de", role="buero")
    ma, md = einladen(client, chef, name="Anna", email="anna@rechte-a.de", role="mitarbeiter")
    p = projekt(client, chef, name="Objekt")
    zeit(client, ma, p["id"], date="2026-10-05")
    # Standard: Büro hat Projekte, Personal, Lohn, Rechnungen, Plantafel – nicht Kalkulation/Kostensätze
    ich = client.get("/api/auth/ich", headers=buero).json()["user"]
    assert ich["rechte"]["personal"] is True and ich["rechte"]["lohn"] is True and ich["rechte"]["kalkulation"] is False
    assert client.get("/api/zeiten?von=2026-10-01&bis=2026-10-31", headers=buero).status_code == 200
    assert client.get("/api/exporte/lohn.csv?jahr=2026&monat=10", headers=buero).status_code == 200
    # Inhaber entzieht Personal- und Lohnrecht → Zeiten aller, Exporte, Konten, Mitarbeiterübersicht gesperrt; Projekte weiter erlaubt
    assert client.put(f"/api/mitarbeiter/{bd['user']['id']}", json={"rechte": {"personal": False, "lohn": False}}, headers=buero).status_code == 403   # nur der Inhaber vergibt Rechte
    r = client.put(f"/api/mitarbeiter/{bd['user']['id']}", json={"rechte": {"personal": False, "lohn": False}}, headers=chef)
    assert r.status_code == 200 and r.json()["mitarbeiter"]["rechte"]["personal"] is False and r.json()["mitarbeiter"]["rechte"]["projekte"] is True
    assert client.get("/api/zeiten?von=2026-10-01&bis=2026-10-31", headers=buero).status_code == 403
    assert client.get("/api/exporte/lohn.csv?jahr=2026&monat=10", headers=buero).status_code == 403
    assert client.get("/api/lohn/vorbereitung?jahr=2026&monat=10", headers=buero).status_code == 403
    assert client.get(f"/api/mitarbeiter/{md['user']['id']}/uebersicht?jahr=2026&monat=10", headers=buero).status_code == 403
    assert client.get("/api/konto/uebersicht?jahr=2026&monat=10", headers=buero).status_code == 403
    assert client.get("/api/auswertung?von=2026-10-01&bis=2026-10-31&gruppe=mitarbeiter", headers=buero).status_code == 403
    assert client.get("/api/auswertung?von=2026-10-01&bis=2026-10-31&gruppe=projekt", headers=buero).status_code == 200
    assert client.post("/api/projekte", json={"name": "Neu", "hourly_rate": 30}, headers=buero).status_code == 200
    # Büro ohne Personalrecht sieht im Projektkalender nur eigene Zeiten und keine Fotografen
    monat = client.get(f"/api/projekte/{p['id']}/monat?jahr=2026&monat=10", headers=buero).json()
    assert monat["eintraege"] == []
    assert client.put(f"/api/mitarbeiter/{bd['user']['id']}", json={"rechte": {"projekte": False}}, headers=chef).status_code == 200
    assert client.post("/api/projekte", json={"name": "Neu 2", "hourly_rate": 30}, headers=buero).status_code == 403
    # Mitarbeiter und Vorarbeiter haben keine vergebbaren Rechte; der Inhaber hat alle
    assert client.get("/api/auth/ich", headers=ma).json()["user"]["rechte"]["personal"] is False
    assert client.get("/api/auth/ich", headers=chef).json()["user"]["rechte"]["kostensaetze"] is True


def test_03_gu_freischaltung_nach_testphase(client):
    gu, gd = registrieren(client, email="chef@gu-frei.de", firma="GU Frei", name="Gerd")
    client.put("/api/firma", json={"art": "auftraggeber"}, headers=gu)
    p = projekt(client, gu, name="Halle")
    a = client.post(f"/api/projekte/{p['id']}/ausschreibungen", json=TENDER, headers=gu).json()["ausschreibung"]   # Testphase: erlaubt
    asyncio.run(dbmodul.db().firmen.update_one({"id": gd["firma"]["id"]}, {"$set": {"plan": {"status": "aktiv", "stufe": "firma"}}}))
    r = client.post(f"/api/ausschreibungen/{a['id']}/veroeffentlichen", headers=gu)
    assert r.status_code == 403 and "Freischaltung" in r.json()["detail"]
    assert client.post("/api/admin/plan", json={"email": "chef@gu-frei.de", "status": "aktiv", "stufe": "firma", "gu": True}, headers=ADMIN).status_code == 200
    assert client.post(f"/api/ausschreibungen/{a['id']}/veroeffentlichen", headers=gu).status_code == 200
    assert client.get("/api/firma/abos", headers=gu).json()["gu_freigeschaltet"] is True
