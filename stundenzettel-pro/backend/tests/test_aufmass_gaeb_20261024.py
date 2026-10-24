"""Stufe F (24.10.2026): sicherer Formelparser, Aufmaße je Projekt und Position mit Foto, Prüfung und Übernahme in Angebot/Auftrag, Aufmaßblatt;
GAEB DA XML X83-Import und X84-Export (Ausschreibung und Kundenangebot); Positionsimport aus CSV/Excel; DATANORM- und Excel-Artikelimport."""
import io

import pytest
from lxml import etree

import aufmass
import gaeb
from conftest import einladen, projekt, registrieren

X83 = b"""<?xml version="1.0" encoding="UTF-8"?>
<GAEB xmlns="http://www.gaeb.de/GAEB_DA_XML/DA83/3.2">
  <GAEBInfo><Version>3.2</Version><VersDate>2013-10</VersDate><Date>2026-10-24</Date><ProgSystem>Fremdsystem</ProgSystem></GAEBInfo>
  <PrjInfo><NamePrj>Sanierung Sparkasse</NamePrj></PrjInfo>
  <Award><DP>83</DP><AwardInfo><Cur>EUR</Cur></AwardInfo>
    <BoQ><BoQInfo><Name>LV</Name></BoQInfo>
      <BoQBody>
        <BoQCtgy RNoPart="01"><LblTx><p>Elektroarbeiten</p></LblTx>
          <BoQBody><Itemlist>
            <Item RNoPart="0010"><Qty>48.000</Qty><QU>Stck</QU>
              <Description><CompleteText><DetailTxt><Text><p>LED-Panel 60x60 liefern und montieren,</p><p>inkl. Anschluss.</p></Text></DetailTxt>
                <OutlineText><OutlTxt><TextOutlTxt>LED-Panel 60x60</TextOutlTxt></OutlTxt></OutlineText></CompleteText></Description></Item>
            <Item RNoPart="0020"><Qty>320.500</Qty><QU>m</QU>
              <Description><CompleteText><DetailTxt><Text><p>Datenleitung Cat.7 verlegen</p></Text></DetailTxt></CompleteText></Description></Item>
            <Remark><p>Hinweis ohne Bedeutung</p></Remark>
          </Itemlist></BoQBody>
        </BoQCtgy>
        <BoQCtgy RNoPart="02"><LblTx><p>Nebenarbeiten</p></LblTx>
          <BoQBody><Itemlist>
            <Item RNoPart="0010"><Qty>1.000</Qty><QU>psch</QU><Description><CompleteText><OutlineText><OutlTxt><TextOutlTxt>Baustelleneinrichtung</TextOutlTxt></OutlTxt></OutlineText></CompleteText></Description></Item>
          </Itemlist></BoQBody>
        </BoQCtgy>
      </BoQBody>
    </BoQ>
  </Award>
</GAEB>"""

DATANORM = ("V;040000;20261024;Reinigungsbedarf Nord;DATANORM 4.0\r\n"
            "A;N;RM-100;0;Allzweckreiniger 10 l;Zitrone;2;0;Kan;1890;01;Reinigung;\r\n"
            "A;N;RM-210;0;Glasreiniger 5 l;;1;0;Kan;1990;01;Reinigung;\r\n"
            "T;N;RM-100;1;Konzentrat, Dosierung 1:100\r\n"
            "P;N;RM-210;2;12,40;RM-999;2;500\r\n"
            "Z;N;unbekannt\r\n").encode("cp850")


def test_01_formelparser_sicher():
    assert aufmass.berechnen("3,20 x 2,60; 1,10 x 2,60") == 11.18
    assert aufmass.berechnen("12,4 + 8,75 + 3,1") == 24.25
    assert aufmass.berechnen("(2 + 3) * 4 / 2") == 10
    assert aufmass.berechnen("-2 + 5") == 3 and aufmass.berechnen("2 × 3") == 6 and aufmass.berechnen("1.5*2") == 3
    for schlecht in ("__import__('os')", "2 ** 8", "a + 1", "2 +", "(2 + 3", "1,2.3", "5 / 0", "", "2 3", "1e9999"):
        with pytest.raises(aufmass.FormelFehler):
            aufmass.berechnen(schlecht)


def test_02_aufmass_erfassen_pruefen_uebernehmen(client):
    chef, cd = registrieren(client, email="chef@aufmass-f.de", firma="Aufmaß F", name="Chef")
    anna, ad = einladen(client, chef, name="Anna", email="anna@aufmass-f.de", role="mitarbeiter")
    ben, _ = einladen(client, chef, name="Ben", email="ben@aufmass-f.de", role="mitarbeiter", passwort="geheim456")
    k = client.post("/api/kunden", json={"name": "Kunde F"}, headers=chef).json()["kunde"]
    # Angebot mit Einheitspreisen (Entwurf) → Projekt; Aufmaße der Mitarbeiterin mit Positionsbezug
    ag = client.post("/api/kundenangebote", json={"titel": "Glas", "customer_id": k["id"], "positionen": [
        {"art": "titel", "text": "Reinigung"}, {"art": "leistung", "text": "Glasfläche reinigen", "menge": 100, "einheit": "m²", "einzelpreis": 2.5},
        {"art": "leistung", "text": "Sockelleisten", "menge": 10, "einheit": "m", "einzelpreis": 4}]}, headers=chef).json()["angebot"]
    p = projekt(client, chef, name="Objekt F", employee_ids=[ad["user"]["id"]], customer_id=k["id"])
    assert client.put(f"/api/kundenangebote/{ag['id']}", json={"project_id": p["id"]}, headers=chef).status_code == 200
    assert client.post("/api/aufmass/formel", json={"formel": "3,2 x 2,6"}, headers=anna).json()["menge"] == 8.32
    assert client.post("/api/aufmass/formel", json={"formel": "3,2 ** 2"}, headers=anna).status_code == 400
    liste = client.get(f"/api/projekte/{p['id']}/aufmasse", headers=anna).json()
    assert [x["nr"] for x in liste["positionen"]] == ["1.1", "1.2"] and liste["positionen"][0]["quelle"] == "angebot" and liste["kann_pruefen"] is False
    r = client.post(f"/api/projekte/{p['id']}/aufmasse", json={"bezeichnung": "Fenster Süd", "raum": "EG", "typ": "flaeche", "formel": "3,20 x 2,60; 1,10 x 2,60", "position_nr": "1.1"}, headers=anna)
    assert r.status_code == 200, r.text
    a1 = r.json()["aufmass"]
    assert a1["menge"] == 11.18 and a1["einheit"] == "m²" and a1["status"] == "erfasst" and a1["position"]["nr"] == "1.1" and a1["user_name"] == "Anna"
    a2 = client.post(f"/api/projekte/{p['id']}/aufmasse", json={"bezeichnung": "Fenster Nord", "typ": "flaeche", "formel": "2 x 2,6", "position_nr": "1.1"}, headers=anna).json()["aufmass"]
    a3 = client.post(f"/api/projekte/{p['id']}/aufmasse", json={"bezeichnung": "Leisten", "typ": "laenge", "formel": "12,4 + 8,75", "position_nr": "1.2"}, headers=anna).json()["aufmass"]
    assert client.post(f"/api/projekte/{p['id']}/aufmasse", json={"bezeichnung": "x", "typ": "flaeche", "formel": "1", "position_nr": "9.9"}, headers=anna).status_code == 404
    assert client.post(f"/api/projekte/{p['id']}/aufmasse", json={"bezeichnung": "x", "typ": "flaeche", "formel": "1 +"}, headers=anna).status_code == 400
    assert client.post(f"/api/projekte/{p['id']}/aufmasse", json={"bezeichnung": "x", "typ": "flaeche", "formel": "1"}, headers=ben).status_code in (403, 404)   # nicht zugeteilt
    # Foto, Sichtbarkeit des Mitarbeiterbezugs, Prüfung nur Büro, Änderung nach Prüfung setzt zurück
    foto = client.post(f"/api/aufmasse/{a1['id']}/fotos", files={"datei": ("skizze.png", b"\x89PNG\r\n\x1a\n" + b"0" * 100, "image/png")}, headers=anna)
    assert foto.status_code == 200 and client.get(f"/api/dokumente/{foto.json()['dokument']['id']}/datei", headers=chef).status_code == 200
    assert client.get(f"/api/dokumente/{foto.json()['dokument']['id']}/datei", headers=ben).status_code in (403, 404)
    assert client.post(f"/api/aufmasse/{a1['id']}/pruefen", headers=anna).status_code == 403
    assert client.post(f"/api/aufmasse/{a1['id']}/pruefen", headers=chef).json()["aufmass"]["status"] == "geprueft"
    assert client.post(f"/api/aufmasse/{a2['id']}/pruefen", headers=chef).status_code == 200
    assert client.put(f"/api/aufmasse/{a1['id']}", json={"bezeichnung": "Fenster Süd", "typ": "flaeche", "formel": "3 x 2,6", "position_nr": "1.1"}, headers=anna).status_code == 409
    g = client.put(f"/api/aufmasse/{a2['id']}", json={"bezeichnung": "Fenster Nord", "typ": "flaeche", "formel": "2,5 x 2,6", "position_nr": "1.1"}, headers=chef).json()["aufmass"]
    assert g["status"] == "erfasst" and g["menge"] == 6.5
    assert client.post(f"/api/aufmasse/{a2['id']}/pruefen", headers=chef).status_code == 200
    s = client.get(f"/api/projekte/{p['id']}/aufmasse", headers=chef).json()
    summe11 = next(x for x in s["summen"] if x["nr"] == "1.1")
    assert summe11["gesamt"] == 17.68 and summe11["geprueft"] == 17.68 and next(x for x in s["summen"] if x["nr"] == "1.2")["geprueft"] == 0
    # Übernahme in den Angebotsentwurf: nur geprüfte Mengen (1.1 → 17,68; 1.2 bleibt 10)
    u = client.post(f"/api/projekte/{p['id']}/aufmasse/uebernehmen", json={"ziel": "angebot"}, headers=chef)
    assert u.status_code == 200, u.text
    assert u.json()["uebernommen"] == 1
    ag2 = client.get(f"/api/kundenangebote/{ag['id']}", headers=chef).json()["angebot"]
    assert [p_["menge"] for p_ in ag2["positionen"] if p_["art"] == "leistung"] == [17.68, 10] and ag2["summen"]["netto"] == 84.2
    # Auftrag (Einheitspreise): Übernahme in Auftragspositionen rechnet den Auftragswert neu; Pauschalauftrag wehrt ab
    assert client.post(f"/api/kundenangebote/{ag['id']}/senden", json={"ohne_email": True}, headers=chef).status_code == 200
    assert client.post(f"/api/kundenangebote/{ag['id']}/annahme", json={"von_name": "Kunde"}, headers=chef).status_code == 200
    assert client.post(f"/api/kundenangebote/{ag['id']}/auftrag", json={"project_id": p["id"]}, headers=chef).status_code == 200
    assert client.post(f"/api/aufmasse/{a3['id']}/pruefen", headers=chef).status_code == 200
    assert client.post(f"/api/projekte/{p['id']}/aufmasse/uebernehmen", json={"ziel": "auftrag"}, headers=chef).status_code == 409   # pauschal (keine Stundenposition)
    u = client.post(f"/api/projekte/{p['id']}/aufmasse/uebernehmen", json={"ziel": "auftrag", "erzwingen": True}, headers=chef).json()
    assert u["uebernommen"] == 2 and u["auftrag"]["netto"] == 128.8 and u["auftrag"]["netto_vor_aufmass"] == 84.2   # 17,68×2,5 + 21,15×4
    pr = client.get(f"/api/projekte/{p['id']}", headers=chef).json()["projekt"]
    p11 = next(x for x in pr["auftrag"]["positionen"] if x["nr"] == "1.1")
    assert p11["menge"] == 17.68 and p11["aufmass"] is True and pr["pauschale_netto"] == 128.8
    assert client.get(f"/api/projekte/{p['id']}/aufmass.pdf", headers=chef).content.startswith(b"%PDF")
    akte = client.post(f"/api/projekte/{p['id']}/projektakte", headers=chef).json()["projektakte"]
    import zipfile
    namen = zipfile.ZipFile(io.BytesIO(client.get(f"/api/projektakten/{akte['id']}.zip", headers=chef).content)).namelist()
    assert "10_Aufmass/aufmasse.csv" in namen and "10_Aufmass/Aufmassblatt.pdf" in namen and any(n.startswith("10_Aufmass/Fotos/") for n in namen)
    assert client.delete(f"/api/aufmasse/{a3['id']}", headers=anna).status_code == 409   # geprüft: nur Büro
    assert client.delete(f"/api/aufmasse/{a3['id']}", headers=chef).status_code == 200


def test_03_gaeb_import_export_und_tabellenimporte(client):
    chef, cd = registrieren(client, email="chef@gaeb-f.de", firma="GAEB F", name="Chef")
    assert client.put("/api/firma", json={"art": "beides"}, headers=chef).status_code == 200
    # GAEB X83 lesen: Hierarchie, Kurz-/Langtext, Mengen, Einheiten, Hinweise
    g = gaeb.lesen(X83, "lv.x83")
    assert g["phase"] == "83" and g["projekt"] == "Sanierung Sparkasse"
    pos = g["positionen"]
    assert [(p["nr"], p["art"]) for p in pos] == [("01", "titel"), ("01.0010", "leistung"), ("01.0020", "leistung"), ("02", "titel"), ("02.0010", "leistung")]
    assert pos[1]["leistung"] == "LED-Panel 60x60" and "inkl. Anschluss" in pos[1]["beschreibung"] and pos[1]["menge"] == 48.0 and pos[1]["einheit"] == "Stck"
    assert pos[2]["leistung"] == "Datenleitung Cat.7 verlegen" and pos[2]["menge"] == 320.5 and any("übersprungen" in h for h in g["hinweise"])
    with pytest.raises(gaeb.GaebNichtUnterstuetzt):
        gaeb.lesen(b"00 GAEB90", "lv.d83")
    with pytest.raises(gaeb.GaebNichtUnterstuetzt):
        gaeb.lesen(b"<GAEB><Award/></GAEB>", "lv.x83")
    # Ausschreibung: X83 importieren (Vorschau und Übernahme), LV als X83 exportieren und wieder lesen
    p = projekt(client, chef, name="Bauvorhaben")
    a = client.post(f"/api/projekte/{p['id']}/ausschreibungen", json={"titel": "Elektro", "gewerk": "Elektro", "beschreibung": "x", "sichtbarkeit": "oeffentlich", "angebotsfrist": "2026-12-20"}, headers=chef).json()["ausschreibung"]
    v = client.post(f"/api/ausschreibungen/{a['id']}/positionen/gaeb", data={"vorschau": "1"}, files={"datei": ("lv.x83", X83, "application/xml")}, headers=chef)
    assert v.status_code == 200, v.text
    assert v.json()["vorschau"] is True and [x["nr"] for x in v.json()["positionen"]] == ["01.0010", "01.0020", "02.0010"]
    i = client.post(f"/api/ausschreibungen/{a['id']}/positionen/datei", data={"vorschau": "0"}, files={"datei": ("lv.x83", X83, "application/xml")}, headers=chef).json()
    assert i["quelle"] == "gaeb-x83" and len(i["positionen"]) == 3
    x83 = client.get(f"/api/ausschreibungen/{a['id']}/lv.x83", headers=chef)
    assert x83.status_code == 200 and b"GAEB_DA_XML/DA83" in x83.content
    zurueck = gaeb.lesen(x83.content, "export.x83")["positionen"]
    assert [x["nr"] for x in zurueck if x["art"] == "leistung"] == ["01.0010", "01.0020", "02.0010"] and zurueck[1]["menge"] == 48.0
    # Bieter: Angebot mit Einheitspreisen → X84 mit UP/IT und Summe
    assert client.post(f"/api/ausschreibungen/{a['id']}/veroeffentlichen", headers=chef).status_code == 200
    bieter, bd = registrieren(client, email="chef@bieter-f.de", firma="Bieter F", name="Bea")
    g2 = client.post(f"/api/ausschreibungen/{a['id']}/angebot", json={"preisart": "einheitspreise", "positionen": [{"nr": "01.0010", "einzelpreis": 185}, {"nr": "01.0020", "einzelpreis": 9.5}, {"nr": "02.0010", "einzelpreis": 1200}]}, headers=bieter)
    assert g2.status_code == 200, g2.text
    x84 = client.get(f"/api/angebote/{g2.json()['angebot']['id']}/angebot.x84", headers=bieter)
    assert x84.status_code == 200 and b"GAEB_DA_XML/DA84" in x84.content
    wurzel = etree.fromstring(x84.content)
    ups = [e.text for e in wurzel.iter("{*}UP")]
    assert ups == ["185.00", "9.50", "1200.00"] and next(wurzel.iter("{*}Total")).text == f"{48 * 185 + 320.5 * 9.5 + 1200:.2f}"
    # Kundenangebot: Positionen aus CSV mit Kopfzeilen-Synonymen und Excel, Fehlerzeilen; danach X84-Export
    k = client.post("/api/kunden", json={"name": "Kunde G"}, headers=chef).json()["kunde"]
    ag = client.post("/api/kundenangebote", json={"titel": "Import", "customer_id": k["id"]}, headers=chef).json()["angebot"]
    csv = "Pos;Bezeichnung;Menge;Einheit;Preis;Art\n1;Reinigung;;Titel;;Titel\n1.1;Grundreinigung;120,5;m²;2,20;\n1.2;Glas;abc;m²;3;\n1.3;;5;Stk;1;\n".encode("utf-8")
    v = client.post(f"/api/kundenangebote/{ag['id']}/positionen/datei", data={"vorschau": "1"}, files={"datei": ("lv.csv", csv, "text/csv")}, headers=chef).json()
    assert v["vorschau"] is True and [x["art"] for x in v["positionen"]] == ["titel", "leistung"] and v["positionen"][1]["menge"] == 120.5 and v["positionen"][1]["einzelpreis"] == 2.2
    assert [f["zeile"] for f in v["fehler"]] == [4, 5]
    r = client.post(f"/api/kundenangebote/{ag['id']}/positionen/datei", data={"vorschau": "0"}, files={"datei": ("lv.csv", csv, "text/csv")}, headers=chef).json()
    assert r["angebot"]["summen"]["netto"] == 265.1 and r["angebot"]["positionen"][1]["import_nr"] == "1.1"
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Nr", "Leistung", "Menge", "Einheit", "Einzelpreis"])
    ws.append(["2.1", "Sockelleisten", 24.25, "m", 4])
    buf = io.BytesIO()
    wb.save(buf)
    r = client.post(f"/api/kundenangebote/{ag['id']}/positionen/datei", data={"vorschau": "0", "modus": "anhaengen"}, files={"datei": ("lv.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}, headers=chef).json()
    assert r["quelle"] == "xlsx" and len(r["angebot"]["positionen"]) == 3 and r["angebot"]["summen"]["netto"] == 362.1
    x84k = client.get(f"/api/kundenangebote/{ag['id']}/angebot.x84", headers=chef)
    assert x84k.status_code == 200 and [e.text for e in etree.fromstring(x84k.content).iter("{*}UP")] == ["2.20", "4.00"]
    # GAEB X83 direkt ins Kundenangebot (Titel bleiben Titel), gesendete Angebote sind gesperrt
    r = client.post(f"/api/kundenangebote/{ag['id']}/positionen/datei", data={"vorschau": "0"}, files={"datei": ("lv.x83", X83, "application/xml")}, headers=chef).json()
    assert [x["art"] for x in r["angebot"]["positionen"]] == ["titel", "leistung", "leistung", "titel", "leistung"] and r["angebot"]["positionen"][1]["menge"] == 48
    assert client.post(f"/api/kundenangebote/{ag['id']}/senden", json={"ohne_email": True}, headers=chef).status_code == 200
    assert client.post(f"/api/kundenangebote/{ag['id']}/positionen/datei", data={"vorschau": "0"}, files={"datei": ("lv.csv", csv, "text/csv")}, headers=chef).status_code == 409
    # Artikel: DATANORM (A-/P-/T-Sätze, Cent-Preise, cp850) und Excel
    d = client.post("/api/artikel/import", data={"vorschau": "1"}, files={"datei": ("katalog.001", DATANORM, "application/octet-stream")}, headers=chef).json()
    assert d["anzahl"] == 3 and any("Z" in f["grund"] for f in d["fehler"])
    rm100 = next(x for x in d["artikel"] if x["nummer"] == "RM-100")
    assert rm100["einkaufspreis"] == 18.9 and rm100["name"] == "Allzweckreiniger 10 l Zitrone" and rm100["einheit"] == "Kan" and "Dosierung" in rm100["beschreibung"] and rm100["lieferant"] == "Reinigungsbedarf Nord"
    rm210 = next(x for x in d["artikel"] if x["nummer"] == "RM-210")
    assert rm210["verkaufspreis"] == 19.9 and rm210["einkaufspreis"] == 12.4
    assert next(x for x in d["artikel"] if x["nummer"] == "RM-999")["einkaufspreis"] == 5.0
    i2 = client.post("/api/artikel/import", data={"vorschau": "0"}, files={"datei": ("katalog.001", DATANORM, "application/octet-stream")}, headers=chef).json()
    assert i2["angelegt"] == 3
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Artikelnummer", "Bezeichnung", "Einheit", "EK", "VK"])
    ws.append(["XL-1", "Excel-Artikel", "Stk.", 1.5, 2.75])
    ws.append(["", "ohne Nummer", "Stk.", 1, 2])
    buf = io.BytesIO()
    wb.save(buf)
    e = client.post("/api/artikel/import", data={"vorschau": "0"}, files={"datei": ("artikel.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}, headers=chef).json()
    assert e["angelegt"] == 1 and e["fehler"][0]["zeile"] == 3
    assert next(x for x in client.get("/api/artikel", headers=chef).json()["artikel"] if x["nummer"] == "XL-1")["einkaufspreis"] == 1.5
