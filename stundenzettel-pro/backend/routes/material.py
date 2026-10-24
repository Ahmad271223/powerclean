"""Artikel, Materialverbrauch, Eingangsrechnungen und Nachkalkulation (Stufe D)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

import material as mat
from auth import aktueller_nutzer, firma_laden, hat_recht, hat_rolle, jetzt_iso, recht_fehlt, recht_noetig, schreibend, schreibend_mit_recht
from dateien import datei_speichern
from db import db
from gemeinsam import neue_id, nutzernamen, projekt_laden
from models import ArtikelIn, EingangBezahltIn, EingangsrechnungIn, EingangStornoIn, MaterialIn, MaterialPruefenIn
from protokoll import protokollieren
from zeiten import datum_pruefen, lokal_jetzt

router = APIRouter(tags=["Material"])


async def _firma(user: dict) -> dict:
    return user.get("_firma") or await firma_laden(user["firma_id"])


# ---------------------------------------------------------------- Artikel

@router.get("/api/artikel")
async def artikel_liste(q: Optional[str] = None, kategorie: Optional[str] = None, aktiv: Optional[bool] = None, user: dict = Depends(recht_noetig("angebote"))):
    filt: dict = {"firma_id": user["firma_id"]}
    if kategorie:
        filt["kategorie"] = kategorie
    if aktiv is not None:
        filt["aktiv"] = aktiv
    ek = hat_recht(user, "kostensaetze")
    aus, kategorien = [], set()
    suche = (q or "").strip().lower()
    async for a in db().artikel.find(filt, {"_id": 0}).sort([("kategorie", 1), ("name", 1)]):
        if a.get("kategorie"):
            kategorien.add(a["kategorie"])
        if suche and suche not in f"{a.get('nummer', '')} {a.get('name', '')} {a.get('hersteller', '')} {a.get('lieferant', '')}".lower():
            continue
        aus.append(mat.artikel_fuer_nutzer(a, ek))
    return {"artikel": aus, "kategorien": sorted(kategorien), "ek_sichtbar": ek}


@router.get("/api/artikel/auswahl")
async def artikel_auswahl(user: dict = Depends(aktueller_nutzer)):
    """Für die Materialbuchung der Mitarbeiter: nur Nummer, Name, Einheit und Kategorie – keine Preise."""
    aus = [a async for a in db().artikel.find({"firma_id": user["firma_id"], "aktiv": True}, {"_id": 0, "id": 1, "nummer": 1, "name": 1, "einheit": 1, "kategorie": 1}).sort("name", 1)]
    return {"artikel": aus}


def _artikel_pruefen(body: ArtikelIn, user: dict) -> dict:
    a = body.model_dump()
    a["nummer"], a["name"] = a["nummer"].strip(), a["name"].strip()
    if a.get("einkaufspreis") is not None and not hat_recht(user, "kostensaetze"):
        raise HTTPException(403, recht_fehlt("kostensaetze"))
    return a


@router.post("/api/artikel")
async def artikel_anlegen(body: ArtikelIn, user: dict = Depends(schreibend_mit_recht("angebote"))):
    a = _artikel_pruefen(body, user)
    if await db().artikel.find_one({"firma_id": user["firma_id"], "nummer": a["nummer"]}, {"_id": 0, "id": 1}):
        raise HTTPException(409, f"Artikelnummer {a['nummer']} gibt es schon.")
    a.update({"id": neue_id(), "firma_id": user["firma_id"], "quelle": "manuell", "created_at": jetzt_iso(), "updated_at": jetzt_iso()})
    await db().artikel.insert_one(dict(a))
    await protokollieren(user, "artikel.angelegt", a["nummer"], details={"name": a["name"]})
    return {"artikel": mat.artikel_fuer_nutzer(a, hat_recht(user, "kostensaetze"))}


@router.put("/api/artikel/{artikel_id}")
async def artikel_aendern(artikel_id: str, body: ArtikelIn, user: dict = Depends(schreibend_mit_recht("angebote"))):
    alt = await db().artikel.find_one({"id": artikel_id, "firma_id": user["firma_id"]}, {"_id": 0})
    if not alt:
        raise HTTPException(404, "Artikel nicht gefunden.")
    a = _artikel_pruefen(body, user)
    if not hat_recht(user, "kostensaetze"):
        a["einkaufspreis"] = alt.get("einkaufspreis")   # ohne Recht bleibt der Einkaufspreis unverändert
    if a["nummer"] != alt["nummer"] and await db().artikel.find_one({"firma_id": user["firma_id"], "nummer": a["nummer"]}, {"_id": 0, "id": 1}):
        raise HTTPException(409, f"Artikelnummer {a['nummer']} gibt es schon.")
    neu = {**alt, **a, "updated_at": jetzt_iso()}
    await db().artikel.update_one({"id": artikel_id}, {"$set": {k: v for k, v in neu.items() if k != "id"}})
    await protokollieren(user, "artikel.geaendert", neu["nummer"], details={"name": neu["name"]})
    return {"artikel": mat.artikel_fuer_nutzer(neu, hat_recht(user, "kostensaetze"))}


@router.delete("/api/artikel/{artikel_id}")
async def artikel_loeschen(artikel_id: str, user: dict = Depends(schreibend_mit_recht("angebote"))):
    a = await db().artikel.find_one({"id": artikel_id, "firma_id": user["firma_id"]}, {"_id": 0})
    if not a:
        raise HTTPException(404, "Artikel nicht gefunden.")
    verwendet = await db().materialverbrauch.count_documents({"artikel_id": artikel_id}) + await db().kundenangebote.count_documents({"firma_id": user["firma_id"], "positionen.artikel_id": artikel_id})
    if verwendet:
        await db().artikel.update_one({"id": artikel_id}, {"$set": {"aktiv": False, "updated_at": jetzt_iso()}})
        return {"ok": True, "deaktiviert": True, "hinweis": f"Der Artikel wird in {verwendet} Buchungen/Angeboten verwendet und wurde deaktiviert statt gelöscht."}
    await db().artikel.delete_one({"id": artikel_id})
    await protokollieren(user, "artikel.geloescht", a["nummer"])
    return {"ok": True, "deaktiviert": False}


@router.post("/api/artikel/import")
async def artikel_import(datei: UploadFile = File(...), vorschau: str = Form("0"), user: dict = Depends(schreibend_mit_recht("angebote"))):
    """Import aus CSV (Semikolon/Komma/Tab, Anführungszeichen, Dezimalkomma, UTF-8/Windows), Excel (.xlsx) oder DATANORM (A-/P-Sätze). Mit vorschau=1 wird nur gelesen."""
    roh = await datei.read()
    if len(roh) > 10 * 1024 * 1024:
        raise HTTPException(413, "Die Datei ist zu groß (max. 10 MB).")
    try:
        ergebnis = mat.artikel_aus_datei(roh, datei.filename or "")
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    if not hat_recht(user, "kostensaetze"):
        for a in ergebnis["artikel"]:
            a["einkaufspreis"] = None
        if ergebnis["artikel"]:
            ergebnis["fehler"].append({"zeile": 0, "grund": "Einkaufspreise wurden nicht übernommen – dafür fehlt das Recht „Kostensätze“."})
    if vorschau == "1" or not ergebnis["artikel"]:
        return {**ergebnis, "artikel": ergebnis["artikel"][:2000], "anzahl": len(ergebnis["artikel"]), "angelegt": 0, "aktualisiert": 0, "vorschau": True}
    angelegt = aktualisiert = 0
    for a in ergebnis["artikel"]:
        alt = await db().artikel.find_one({"firma_id": user["firma_id"], "nummer": a["nummer"]}, {"_id": 0})
        if alt:
            neu = {k: v for k, v in a.items() if v not in (None, "")}
            if not hat_recht(user, "kostensaetze"):
                neu.pop("einkaufspreis", None)
            await db().artikel.update_one({"id": alt["id"]}, {"$set": {**neu, "updated_at": jetzt_iso(), "quelle": "csv"}})
            aktualisiert += 1
        else:
            await db().artikel.insert_one({**a, "id": neue_id(), "firma_id": user["firma_id"], "aktiv": True, "quelle": "csv", "created_at": jetzt_iso(), "updated_at": jetzt_iso()})
            angelegt += 1
    await protokollieren(user, "artikel.import", datei.filename or "csv", details={"angelegt": angelegt, "aktualisiert": aktualisiert, "fehler": len(ergebnis["fehler"])})
    return {**ergebnis, "artikel": [], "anzahl": len(ergebnis["artikel"]), "angelegt": angelegt, "aktualisiert": aktualisiert, "vorschau": False}


# ---------------------------------------------------------------- Materialverbrauch

def _material_fuer_nutzer(v: dict, preise: bool) -> dict:
    aus = {k: val for k, val in v.items() if k != "_id"}
    if not preise:
        for k in ("einkaufspreis", "verkaufspreis", "kosten"):
            aus.pop(k, None)
    return aus


@router.get("/api/projekte/{project_id}/material")
async def material_liste(project_id: str, von: Optional[str] = None, bis: Optional[str] = None, user: dict = Depends(aktueller_nutzer)):
    """Büro: alle Buchungen mit Kosten; Mitarbeiter: nur die eigenen, ohne Preise."""
    p = await projekt_laden(user, project_id)
    buero = hat_rolle(user, "buero")
    filt: dict = {"firma_id": user["firma_id"], "project_id": p["id"]}
    if not buero:
        filt["user_id"] = user["id"]
    if von or bis:
        filt["date"] = {k: v for k, v in (("$gte", von), ("$lte", bis)) if v}
    preise = buero and hat_recht(user, "kostensaetze")
    aus, summe, ungeprueft = [], 0.0, 0
    async for v in db().materialverbrauch.find(filt, {"_id": 0}).sort([("date", -1), ("created_at", -1)]):
        summe += float(v.get("kosten") or 0)
        if v.get("status") != "geprueft":
            ungeprueft += 1
        aus.append(_material_fuer_nutzer(v, preise))
    return {"material": aus, "kosten_summe": mat.rund(summe) if preise else None, "ungeprueft": ungeprueft if buero else None, "preise_sichtbar": preise}


@router.post("/api/projekte/{project_id}/material")
async def material_buchen(project_id: str, body: MaterialIn, user: dict = Depends(schreibend("mitarbeiter"))):
    p = await projekt_laden(user, project_id, schreiben=True)
    buero = hat_rolle(user, "buero")
    artikel = await db().artikel.find_one({"id": body.artikel_id, "firma_id": user["firma_id"]}, {"_id": 0}) if body.artikel_id else None
    if body.artikel_id and not artikel:
        raise HTTPException(404, "Artikel nicht gefunden.")
    bezeichnung = (body.bezeichnung or (artikel or {}).get("name") or "").strip()
    if not bezeichnung:
        raise HTTPException(400, "Bitte einen Artikel wählen oder das Material benennen.")
    ek = (artikel or {}).get("einkaufspreis")
    if body.einkaufspreis is not None:
        if not (buero and hat_recht(user, "kostensaetze")):
            raise HTTPException(403, recht_fehlt("kostensaetze"))
        ek = body.einkaufspreis
    v = {"id": neue_id(), "firma_id": user["firma_id"], "project_id": p["id"], "user_id": user["id"], "user_name": user.get("name"),
         "date": body.date or lokal_jetzt().date().isoformat(), "artikel_id": (artikel or {}).get("id"), "artikel_nummer": (artikel or {}).get("nummer"),
         "bezeichnung": bezeichnung[:200], "menge": float(body.menge), "einheit": (body.einheit or (artikel or {}).get("einheit") or "Stk.")[:20],
         "einkaufspreis": ek, "verkaufspreis": (artikel or {}).get("verkaufspreis"), "kosten": mat.rund(float(body.menge) * float(ek)) if ek is not None else None,
         "note": (body.note or "")[:500], "quelle": "buero" if buero else "mitarbeiter", "status": "erfasst", "geprueft_von": None, "geprueft_at": None,
         "created_at": jetzt_iso(), "updated_at": jetzt_iso()}
    await db().materialverbrauch.insert_one(dict(v))
    await protokollieren(user, "material.gebucht", p["name"], details={"material": v["bezeichnung"], "menge": v["menge"], "einheit": v["einheit"]})
    return {"material": _material_fuer_nutzer(v, buero and hat_recht(user, "kostensaetze"))}


async def _material_laden(user: dict, material_id: str) -> dict:
    v = await db().materialverbrauch.find_one({"id": material_id, "firma_id": user["firma_id"]}, {"_id": 0})
    if not v:
        raise HTTPException(404, "Materialbuchung nicht gefunden.")
    if not hat_rolle(user, "buero") and v.get("user_id") != user["id"]:
        raise HTTPException(404, "Materialbuchung nicht gefunden.")
    return v


@router.put("/api/material/{material_id}")
async def material_aendern(material_id: str, body: MaterialIn, user: dict = Depends(schreibend("mitarbeiter"))):
    v = await _material_laden(user, material_id)
    buero = hat_rolle(user, "buero")
    if v.get("status") == "geprueft" and not buero:
        raise HTTPException(409, "Die Buchung ist schon geprüft – Änderungen macht jetzt das Büro.")
    artikel = await db().artikel.find_one({"id": body.artikel_id, "firma_id": user["firma_id"]}, {"_id": 0}) if body.artikel_id else None
    ek = v.get("einkaufspreis") if (body.artikel_id == v.get("artikel_id") or not body.artikel_id) else (artikel or {}).get("einkaufspreis")
    if body.einkaufspreis is not None:
        if not (buero and hat_recht(user, "kostensaetze")):
            raise HTTPException(403, recht_fehlt("kostensaetze"))
        ek = body.einkaufspreis
    neu = {**v, "date": body.date or v["date"], "artikel_id": (artikel or {}).get("id") if body.artikel_id else v.get("artikel_id"),
           "bezeichnung": (body.bezeichnung or (artikel or {}).get("name") or v.get("bezeichnung") or "")[:200], "menge": float(body.menge),
           "einheit": (body.einheit or v.get("einheit") or "Stk.")[:20], "einkaufspreis": ek, "kosten": mat.rund(float(body.menge) * float(ek)) if ek is not None else None,
           "note": (body.note if body.note is not None else v.get("note") or "")[:500], "updated_at": jetzt_iso()}
    await db().materialverbrauch.update_one({"id": material_id}, {"$set": {k: val for k, val in neu.items() if k != "id"}})
    return {"material": _material_fuer_nutzer(neu, buero and hat_recht(user, "kostensaetze"))}


@router.delete("/api/material/{material_id}")
async def material_loeschen(material_id: str, user: dict = Depends(schreibend("mitarbeiter"))):
    v = await _material_laden(user, material_id)
    if v.get("status") == "geprueft" and not hat_rolle(user, "buero"):
        raise HTTPException(409, "Geprüfte Buchungen löscht nur das Büro.")
    await db().materialverbrauch.delete_one({"id": material_id})
    await protokollieren(user, "material.geloescht", v.get("bezeichnung", ""), details={"menge": v.get("menge")})
    return {"ok": True}


@router.post("/api/material/{material_id}/pruefen")
async def material_pruefen(material_id: str, body: MaterialPruefenIn, user: dict = Depends(schreibend_mit_recht("kalkulation"))):
    """Büro bestätigt Menge und Einkaufspreis – erst dann zählt die Buchung in der Nachkalkulation."""
    v = await _material_laden(user, material_id)
    ek = v.get("einkaufspreis")
    if body.einkaufspreis is not None:
        if not hat_recht(user, "kostensaetze"):
            raise HTTPException(403, recht_fehlt("kostensaetze"))
        ek = body.einkaufspreis
    menge = float(body.menge) if body.menge is not None else float(v.get("menge") or 0)
    if ek is None:
        raise HTTPException(400, "Ohne Einkaufspreis lässt sich die Buchung nicht prüfen – Preis angeben oder den Artikel bepreisen.")
    aenderung = {"menge": menge, "einkaufspreis": ek, "kosten": mat.rund(menge * float(ek)), "status": "geprueft", "geprueft_von": user.get("name"), "geprueft_at": jetzt_iso(),
                 "updated_at": jetzt_iso(), **({"note": body.note[:500]} if body.note is not None else {})}
    await db().materialverbrauch.update_one({"id": material_id}, {"$set": aenderung})
    return {"material": _material_fuer_nutzer({**v, **aenderung}, hat_recht(user, "kostensaetze"))}


# ---------------------------------------------------------------- Eingangsrechnungen

def _eingang_summen(r: dict) -> dict:
    zugeordnet = mat.rund(sum(float(z.get("betrag_netto") or 0) for z in r.get("zuordnungen") or []))
    return {**r, "zugeordnet_netto": zugeordnet, "nicht_zugeordnet_netto": mat.rund(float(r.get("netto") or 0) - zugeordnet),
            "status_name": mat.EINGANG_STATUS.get(r.get("status"), r.get("status")), "ueberfaellig": r.get("status") in ("erfasst", "geprueft") and bool(r.get("faellig_am")) and r["faellig_am"] < lokal_jetzt().date().isoformat()}


@router.get("/api/eingangsrechnungen")
async def eingang_liste(status: Optional[str] = None, project_id: Optional[str] = None, von: Optional[str] = None, bis: Optional[str] = None,
                        limit: int = Query(500, ge=1, le=3000), user: dict = Depends(recht_noetig("rechnungen"))):
    filt: dict = {"firma_id": user["firma_id"]}
    if status:
        filt["status"] = status
    if project_id:
        filt["zuordnungen.project_id"] = project_id
    if von or bis:
        filt["rechnungsdatum"] = {k: v for k, v in (("$gte", von), ("$lte", bis)) if v}
    projekte = {p["id"]: p["name"] async for p in db().projects.find({"firma_id": user["firma_id"]}, {"_id": 0, "id": 1, "name": 1})}
    aus, zaehler, offen, ueberfaellig = [], {}, 0.0, 0
    async for r in db().eingangsrechnungen.find(filt, {"_id": 0, "verlauf": 0}).sort([("rechnungsdatum", -1), ("created_at", -1)]).limit(limit):
        r = _eingang_summen(r)
        r["projekte"] = sorted({projekte.get(z.get("project_id"), "?") for z in r.get("zuordnungen") or []})
        zaehler[r["status"]] = zaehler.get(r["status"], 0) + 1
        if r["status"] in ("erfasst", "geprueft"):
            offen += float(r.get("brutto") or 0)
            if r["ueberfaellig"]:
                ueberfaellig += 1
        aus.append(r)
    return {"eingangsrechnungen": aus, "zaehler": zaehler, "offen_brutto": mat.rund(offen), "ueberfaellig": ueberfaellig, "kostenarten": mat.KOSTENARTEN, "status_namen": mat.EINGANG_STATUS}


@router.post("/api/eingangsrechnungen/datei")
async def eingang_datei(datei: UploadFile = File(...), user: dict = Depends(schreibend_mit_recht("rechnungen"))):
    """Beleg hochladen (PDF, Bild, XML). Aus XRechnung-XML oder ZUGFeRD-PDF wird ein Vorschlag gelesen – ungeprüft, nur zum Vorausfüllen."""
    inhalt = await datei.read()
    await datei.seek(0)
    vorschlag = None
    typ = (datei.content_type or "").split(";")[0].strip().lower()
    if typ in ("application/xml", "text/xml") or (datei.filename or "").lower().endswith(".xml"):
        vorschlag = mat.erechnung_auslesen(inhalt)
        if vorschlag is None:
            raise HTTPException(400, "Die XML-Datei ist keine E-Rechnung (CII/XRechnung).")
        datei.file.seek(0)
    elif typ == "application/pdf":
        xml = mat.zugferd_xml_aus_pdf(inhalt)
        if xml:
            vorschlag = mat.erechnung_auslesen(xml)
            if vorschlag:
                vorschlag["quelle"] = "zugferd"
    meta = await datei_speichern(user["firma_id"], datei, user["id"])
    doc = {**meta, "firma_id": user["firma_id"], "scope": "eingangsrechnung", "ref_id": "", "category": "Eingangsrechnung", "note": "", "date": None,
           "uploaded_by": user["id"], "uploaded_by_name": user.get("name"), "created_at": jetzt_iso()}
    await db().documents.insert_one(dict(doc))
    doc.pop("path", None)
    return {"dokument": doc, "vorschlag": vorschlag}


async def _zuordnungen_pruefen(user: dict, body: EingangsrechnungIn) -> list[dict]:
    aus, summe = [], 0.0
    for z in body.zuordnungen:
        p = await db().projects.find_one({"id": z.project_id, "firma_id": user["firma_id"]}, {"_id": 0, "id": 1, "name": 1})
        if not p:
            raise HTTPException(404, "Projekt der Aufteilung nicht gefunden.")
        summe += float(z.betrag_netto)
        aus.append({"project_id": p["id"], "projekt_name": p["name"], "betrag_netto": mat.rund(z.betrag_netto), "kostenart": z.kostenart})
    if summe > float(body.netto) + 0.011:
        raise HTTPException(400, f"Die Aufteilung ({mat.rund(summe)} €) übersteigt den Nettobetrag ({mat.rund(body.netto)} €).")
    return aus


@router.post("/api/eingangsrechnungen")
async def eingang_anlegen(body: EingangsrechnungIn, user: dict = Depends(schreibend_mit_recht("rechnungen"))):
    schluessel = mat.dublette_schluessel(body.lieferant, body.rechnungsnummer)
    doppelt = await db().eingangsrechnungen.find_one({"firma_id": user["firma_id"], "dublette": schluessel, "status": {"$ne": "storniert"}}, {"_id": 0, "id": 1, "rechnungsdatum": 1, "brutto": 1})
    if doppelt and not body.erzwingen:
        raise HTTPException(409, f"Eine Rechnung {body.rechnungsnummer} von {body.lieferant} ist schon erfasst ({doppelt.get('rechnungsdatum')}, {doppelt.get('brutto')} €). Mit erzwingen=true trotzdem anlegen.")
    zuordnungen = await _zuordnungen_pruefen(user, body)
    r = {"id": neue_id(), "firma_id": user["firma_id"], "lieferant": body.lieferant.strip(), "lieferant_ustid": (body.lieferant_ustid or "").strip(), "rechnungsnummer": body.rechnungsnummer.strip(),
         "rechnungsdatum": body.rechnungsdatum, "faellig_am": body.faellig_am, "netto": mat.rund(body.netto), "ust": mat.rund(body.ust), "brutto": mat.rund(body.brutto),
         "zuordnungen": zuordnungen, "kostenart": body.kostenart, "notiz": (body.notiz or "")[:2000], "dokument_id": body.dokument_id, "status": "erfasst", "bezahlt_am": None,
         "zahlungsart": "", "dublette": schluessel, "dublette_hinweis": bool(doppelt), "created_by": user["id"], "created_by_name": user.get("name"), "created_at": jetzt_iso(),
         "updated_at": jetzt_iso(), "verlauf": [{"aktion": "erfasst", "user_name": user.get("name"), "at": jetzt_iso(), "text": ""}]}
    if body.dokument_id:
        res = await db().documents.update_one({"id": body.dokument_id, "firma_id": user["firma_id"], "scope": "eingangsrechnung"}, {"$set": {"ref_id": r["id"]}})
        if not res.matched_count:
            raise HTTPException(404, "Beleg nicht gefunden – bitte neu hochladen.")
    await db().eingangsrechnungen.insert_one(dict(r))
    await protokollieren(user, "eingangsrechnung.erfasst", r["rechnungsnummer"], details={"lieferant": r["lieferant"], "brutto": r["brutto"]})
    return {"eingangsrechnung": _eingang_summen(r)}


async def _eingang_laden(user: dict, rechnung_id: str) -> dict:
    r = await db().eingangsrechnungen.find_one({"id": rechnung_id, "firma_id": user["firma_id"]}, {"_id": 0})
    if not r:
        raise HTTPException(404, "Eingangsrechnung nicht gefunden.")
    return r


@router.get("/api/eingangsrechnungen/{rechnung_id}")
async def eingang_lesen(rechnung_id: str, user: dict = Depends(recht_noetig("rechnungen"))):
    r = await _eingang_laden(user, rechnung_id)
    dok = await db().documents.find_one({"id": r.get("dokument_id")}, {"_id": 0, "path": 0}) if r.get("dokument_id") else None
    return {"eingangsrechnung": _eingang_summen(r), "dokument": dok, "kostenarten": mat.KOSTENARTEN}


@router.put("/api/eingangsrechnungen/{rechnung_id}")
async def eingang_aendern(rechnung_id: str, body: EingangsrechnungIn, user: dict = Depends(schreibend_mit_recht("rechnungen"))):
    r = await _eingang_laden(user, rechnung_id)
    if r["status"] in ("bezahlt", "storniert"):
        raise HTTPException(409, "Bezahlte oder stornierte Eingangsrechnungen werden nicht mehr geändert.")
    zuordnungen = await _zuordnungen_pruefen(user, body)
    schluessel = mat.dublette_schluessel(body.lieferant, body.rechnungsnummer)
    if schluessel != r.get("dublette"):
        doppelt = await db().eingangsrechnungen.find_one({"firma_id": user["firma_id"], "dublette": schluessel, "id": {"$ne": r["id"]}, "status": {"$ne": "storniert"}}, {"_id": 0, "id": 1})
        if doppelt and not body.erzwingen:
            raise HTTPException(409, f"Eine Rechnung {body.rechnungsnummer} von {body.lieferant} ist schon erfasst.")
    neu = {**r, "lieferant": body.lieferant.strip(), "lieferant_ustid": (body.lieferant_ustid or "").strip(), "rechnungsnummer": body.rechnungsnummer.strip(), "rechnungsdatum": body.rechnungsdatum,
           "faellig_am": body.faellig_am, "netto": mat.rund(body.netto), "ust": mat.rund(body.ust), "brutto": mat.rund(body.brutto), "zuordnungen": zuordnungen, "kostenart": body.kostenart,
           "notiz": (body.notiz or "")[:2000], "dublette": schluessel, "updated_at": jetzt_iso(),
           "verlauf": (r.get("verlauf") or []) + [{"aktion": "geaendert", "user_name": user.get("name"), "at": jetzt_iso(), "text": ""}]}
    if body.dokument_id and body.dokument_id != r.get("dokument_id"):
        res = await db().documents.update_one({"id": body.dokument_id, "firma_id": user["firma_id"], "scope": "eingangsrechnung"}, {"$set": {"ref_id": r["id"]}})
        if not res.matched_count:
            raise HTTPException(404, "Beleg nicht gefunden – bitte neu hochladen.")
        neu["dokument_id"] = body.dokument_id
    await db().eingangsrechnungen.update_one({"id": r["id"]}, {"$set": {k: v for k, v in neu.items() if k != "id"}})
    return {"eingangsrechnung": _eingang_summen(neu)}


@router.delete("/api/eingangsrechnungen/{rechnung_id}")
async def eingang_loeschen(rechnung_id: str, user: dict = Depends(schreibend_mit_recht("rechnungen"))):
    r = await _eingang_laden(user, rechnung_id)
    if r["status"] != "erfasst":
        raise HTTPException(409, "Nur erfasste (ungeprüfte) Eingangsrechnungen lassen sich löschen – sonst stornieren.")
    await db().eingangsrechnungen.delete_one({"id": r["id"]})
    await protokollieren(user, "eingangsrechnung.geloescht", r["rechnungsnummer"], details={"lieferant": r["lieferant"]})
    return {"ok": True}


async def _eingang_status(user: dict, r: dict, aenderung: dict, aktion: str, text: str = "") -> dict:
    aenderung = {**aenderung, "updated_at": jetzt_iso(), "verlauf": (r.get("verlauf") or []) + [{"aktion": aktion, "user_name": user.get("name"), "at": jetzt_iso(), "text": text}]}
    await db().eingangsrechnungen.update_one({"id": r["id"]}, {"$set": aenderung})
    await protokollieren(user, f"eingangsrechnung.{aktion}", r["rechnungsnummer"], details={"lieferant": r["lieferant"], "text": text})
    return _eingang_summen({**r, **aenderung})


@router.post("/api/eingangsrechnungen/{rechnung_id}/pruefen")
async def eingang_pruefen(rechnung_id: str, user: dict = Depends(schreibend_mit_recht("rechnungen"))):
    """Geprüft: Beträge und Aufteilung bestätigt – ab jetzt zählt die Rechnung in der Nachkalkulation."""
    r = await _eingang_laden(user, rechnung_id)
    if r["status"] != "erfasst":
        raise HTTPException(409, "Nur erfasste Eingangsrechnungen werden geprüft.")
    return {"eingangsrechnung": await _eingang_status(user, r, {"status": "geprueft", "geprueft_von": user.get("name"), "geprueft_at": jetzt_iso()}, "geprueft")}


@router.post("/api/eingangsrechnungen/{rechnung_id}/bezahlt")
async def eingang_bezahlt(rechnung_id: str, body: EingangBezahltIn, user: dict = Depends(schreibend_mit_recht("rechnungen"))):
    r = await _eingang_laden(user, rechnung_id)
    if r["status"] not in ("erfasst", "geprueft"):
        raise HTTPException(409, "Diese Eingangsrechnung ist schon bezahlt oder storniert.")
    am = body.am or lokal_jetzt().date().isoformat()
    datum_pruefen(am)
    aenderung = {"status": "bezahlt", "bezahlt_am": am, "zahlungsart": (body.zahlungsart or "")[:60], "bezahlt_betrag": mat.rund(body.betrag) if body.betrag is not None else r.get("brutto")}
    if r["status"] == "erfasst":
        aenderung.update({"geprueft_von": user.get("name"), "geprueft_at": jetzt_iso()})
    return {"eingangsrechnung": await _eingang_status(user, r, aenderung, "bezahlt", f"am {am}")}


@router.post("/api/eingangsrechnungen/{rechnung_id}/storno")
async def eingang_storno(rechnung_id: str, body: EingangStornoIn, user: dict = Depends(schreibend_mit_recht("rechnungen"))):
    r = await _eingang_laden(user, rechnung_id)
    if r["status"] == "storniert":
        raise HTTPException(409, "Schon storniert.")
    return {"eingangsrechnung": await _eingang_status(user, r, {"status": "storniert", "storno_grund": body.grund.strip()}, "storniert", body.grund.strip())}


# ---------------------------------------------------------------- Nachkalkulation

@router.get("/api/projekte/{project_id}/nachkalkulation")
async def projekt_nachkalkulation(project_id: str, user: dict = Depends(recht_noetig("kalkulation"))):
    p = await projekt_laden(user, project_id)
    if p.get("verknuepft"):
        pass   # verknüpfte Projekte (Aufträge eines GU): die eigenen Zeiten und Kosten gehören trotzdem zur eigenen Firma
    firma = await _firma(user)
    n = await mat.nachkalkulation(firma, p)
    if not hat_recht(user, "kostensaetze"):
        n["je_person"] = []   # individuelle Mitarbeiterkosten nur mit Recht „kostensaetze“
        n["kostenmodell"] = {**n["kostenmodell"], "firmensatz": None}
    return {"nachkalkulation": n, "kostenarten": mat.KOSTENARTEN}


@router.get("/api/nachkalkulation")
async def nachkalkulation_uebersicht(user: dict = Depends(recht_noetig("kalkulation"))):
    """Alle aktiven Projekte mit Auftragswert: Umsatz, Ist-Kosten, Plan, Abweichung – Grundlage für „Projekte mit Kostenabweichung“."""
    firma = await _firma(user)
    aus = []
    async for p in db().projects.find({"firma_id": user["firma_id"], "archived": {"$ne": True}}, {"_id": 0}):
        if not (p.get("auftrag") or float(p.get("pauschale_netto") or 0)):
            continue
        n = await mat.nachkalkulation(firma, p)
        aus.append({"project_id": p["id"], "name": p["name"], "umsatz": n["umsatz_vereinbart"], "ist": n["ist"]["gesamt"], "plan": n["plan"]["gesamt"], "abweichung": n["abweichung"],
                    "deckungsbeitrag": n["deckungsbeitrag"]["aktuell"], "vollstaendig": n["vollstaendig"], "hinweise": len(n["hinweise"]),
                    "warnung": bool(n["abweichung"] is not None and n["plan"]["gesamt"] and n["abweichung"] > 0.1 * n["plan"]["gesamt"]) or bool(n["deckungsbeitrag"]["aktuell"] is not None and n["deckungsbeitrag"]["aktuell"] < 0)})
    aus.sort(key=lambda x: (not x["warnung"], -(x["abweichung"] or 0)))
    return {"projekte": aus}
