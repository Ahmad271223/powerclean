"""Firmenart: Auftraggeber (GU) und ausführende Betriebe sind getrennte Kontoarten mit eigener Sicht – 2026-10-23."""
from conftest import einladen, projekt, registrieren


def test_firmenart_registrierung_sitzung_und_benachrichtigung(client):
    # Standard ist der ausführende Betrieb; Auftraggeber wählen die Art bei der Registrierung
    r = client.post("/api/auth/registrieren", json={"firma_name": "GOLDBECK Test", "name": "Gerd GU", "email": "gu@firmenart-test.de", "password": "geheim123", "art": "auftraggeber"})
    assert r.status_code == 200, r.text
    gu = {"Authorization": f"Bearer {r.json()['token']}"}
    assert r.json()["firma"]["art"] == "auftraggeber"
    assert client.post("/api/auth/registrieren", json={"firma_name": "x", "name": "x", "email": "x@firmenart-test.de", "password": "geheim123", "art": "konzern"}).status_code == 422
    el, el_d = registrieren(client, email="chef@elektro-firmenart.de", firma="Elektro Firmenart", name="Erika")
    assert client.get("/api/auth/ich", headers=el).json()["firma"]["art"] == "betrieb"
    # Mitarbeiter sehen die Art (für Menü und Startseite), aber keine Bankdaten
    ma, _ = einladen(client, el, name="Milan", email="milan@elektro-firmenart.de", role="mitarbeiter")
    f = client.get("/api/auth/ich", headers=ma).json()["firma"]
    assert f["art"] == "betrieb" and "iban" not in f
    # Nur der Inhaber ändert die Art; ungültige Werte werden abgewiesen
    assert client.put("/api/firma", json={"art": "beides"}, headers=el).status_code == 200
    assert client.get("/api/firma", headers=el).json()["firma"]["art"] == "beides"
    assert client.put("/api/firma", json={"art": "irgendwas"}, headers=el).status_code == 422
    assert client.put("/api/firma", json={"art": "betrieb"}, headers=ma).status_code == 403
    # Verzeichnis zeigt die Art; ein reiner Auftraggeber bekommt keine „neue passende Ausschreibung“, ein Betrieb schon
    client.put("/api/firma/verzeichnis", json={"sichtbar": True, "gewerke": ["Elektro"]}, headers=el)
    client.put("/api/firma/verzeichnis", json={"sichtbar": True, "gewerke": ["Elektro"]}, headers=gu)
    assert client.get("/api/firma/verzeichnis", headers=gu).json()["art"] == "auftraggeber"
    eintraege = {x["name"]: x["art"] for x in client.get("/api/verzeichnis/firmen?q=", headers=el).json()["firmen"]}
    assert eintraege["GOLDBECK Test"] == "auftraggeber"
    p = projekt(client, gu, name="Logistikhalle")
    a = client.post(f"/api/projekte/{p['id']}/ausschreibungen", json={"titel": "Elektro", "gewerk": "Elektro", "beschreibung": "x", "sichtbarkeit": "oeffentlich", "angebotsfrist": "2026-12-20"}, headers=gu).json()["ausschreibung"]
    assert client.post(f"/api/ausschreibungen/{a['id']}/veroeffentlichen", headers=gu).status_code == 200
    assert "ausschreibung_neu" in [n["art"] for n in client.get("/api/benachrichtigungen", headers=el).json()["benachrichtigungen"]]
    assert "ausschreibung_neu" not in [n["art"] for n in client.get("/api/benachrichtigungen", headers=gu).json()["benachrichtigungen"]]
    # Der Betrieb (jetzt „beides“) kann weiterhin finden und bieten; der Auftraggeber sieht die Ausschreibung als Eigentümer
    assert [x["id"] for x in client.get("/api/ausschreibungen", headers=el).json()["ausschreibungen"]] == [a["id"]]
    assert client.get(f"/api/ausschreibungen/{a['id']}", headers=gu).json()["ausschreibung"]["rolle"] == "leitung"
