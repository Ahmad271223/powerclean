"""Rechnungen: eine je Projekt und Monat, fortlaufende Nummer je Firma und Jahr, Status offen/bezahlt/storniert,
Positionen je Woche und Leistung, Zusatzpositionen (Material, Anfahrt, Pauschalen).
Das PDF entsteht in der Oberfläche (jsPDF) aus den Daten von GET /api/rechnungen/{id}/daten."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pymongo.errors import DuplicateKeyError

from auth import firma_laden, jetzt_iso, rolle_noetig, schreibend
from auth import hat_rolle
from db import db
import erechnung
import pdfbasis
from gemeinsam import eintrag_anreichern, firma_oeffentlich, kunde_laden, neue_id, nutzernamen, projekt_fotos, projekt_laden
from models import ExtrasIn, RechnungAnlegenIn, RechnungStatusIn
from protokoll import protokollieren
from zeiten import datum_pruefen, lokal_jetzt, monatsletzter, rasterbereich, rechnung_berechnen

router = APIRouter(prefix="/api/rechnungen", tags=["Rechnungen"])


async def _monatseintraege(firma_id: str, project_id: str, jahr: int, monat: int) -> list[dict]:
    von = f"{jahr:04d}-{monat:02d}-01"
    bis = monatsletzter(jahr, monat).isoformat()
    aus = []
    async for e in db().entries.find({"firma_id": firma_id, "project_id": project_id, "date": {"$gte": von, "$lte": bis}}, {"_id": 0}):
        aus.append(e)
    return aus


def _summen(calc: dict) -> dict:
    return {"total_minutes": calc["total_minutes"], "rate": calc["rate"], "hours_net": calc["hours_net"], "extras_net": calc["extras_net"],
            "net": calc["net"], "vat_rate": calc["vat_rate"], "vat": calc["vat"], "gross": calc["gross"], "reverse_charge": calc["reverse_charge"],
            "positions": calc["positions"], "extras": calc["extras"], "totals_at": jetzt_iso()}


@router.get("")
async def liste(jahr: Optional[int] = Query(None, ge=2025, le=2100), status: Optional[str] = None, limit: int = Query(500, ge=1, le=3000),
                offset: int = Query(0, ge=0), user: dict = Depends(rolle_noetig("buero"))):
    filt = {"firma_id": user["firma_id"]}
    if jahr:
        filt["year"] = jahr
    if status:
        filt["status"] = status
    projekte = {}
    async for p in db().projects.find({"firma_id": user["firma_id"]}, {"_id": 0, "id": 1, "name": 1, "customer_name": 1, "color": 1}):
        projekte[p["id"]] = p
    aus = []
    async for r in db().invoices.find(filt, {"_id": 0, "positions": 0}).sort([("year", -1), ("seq", -1)]).skip(offset).limit(limit + 1):
        p = projekte.get(r.get("project_id"), {})
        r["project_name"] = p.get("name", "Projekt gelöscht")
        r["customer_name"] = p.get("customer_name", "")
        r["project_color"] = p.get("color", "")
        r["extras_anzahl"] = len(r.get("extras") or [])
        aus.append(r)
    hat_mehr = len(aus) > limit
    aus = aus[:limit]
    jahre = sorted({r["year"] async for r in db().invoices.find({"firma_id": user["firma_id"]}, {"_id": 0, "year": 1})}, reverse=True)
    return {"rechnungen": aus, "jahre": jahre, "hat_mehr": hat_mehr, "offset": offset, "limit": limit, "gesamt": await db().invoices.count_documents(filt)}


async def _naechste_nummer(firma_id: str, jahr: int) -> int:
    """Laufende Rechnungsnummer je Firma und Jahr aus einem Zähler, der nie zurückgezählt wird – eine zurückgesetzte oder
    gelöschte Nummer wird nicht noch einmal vergeben (Nachvollziehbarkeit des Nummernkreises)."""
    letzte = await db().invoices.find_one({"firma_id": firma_id, "year": jahr}, {"_id": 0, "seq": 1}, sort=[("seq", -1)])
    hoechste = int((letzte or {}).get("seq") or 0)
    feld = f"rechnungszaehler.{jahr}"
    for _ in range(10):
        f = await db().firmen.find_one({"id": firma_id}, {"_id": 0, "rechnungszaehler": 1})
        stand = int(((f or {}).get("rechnungszaehler") or {}).get(str(jahr)) or 0)
        neu = max(stand, hoechste) + 1
        filt = {"id": firma_id, feld: stand} if stand else {"id": firma_id, "$or": [{feld: {"$exists": False}}, {feld: 0}, {feld: None}]}
        r = await db().firmen.update_one(filt, {"$set": {feld: neu}})
        if r.matched_count:
            return neu
    raise HTTPException(503, "Rechnungsnummer konnte nicht vergeben werden, bitte noch einmal versuchen.")


def festgeschrieben(r: dict) -> bool:
    return bool(r.get("festgeschrieben_at"))


async def _festschreiben(user: dict, r: dict, anlass: str) -> dict:
    """Rechnung ausstellen: ab jetzt werden Summen nicht mehr stillschweigend neu berechnet (erst wieder nach Storno oder ausdrücklich durch den Inhaber)."""
    if festgeschrieben(r) or r.get("status", "offen") != "offen":
        return r
    aenderung = {"festgeschrieben_at": jetzt_iso(), "festgeschrieben_von": user.get("name"), "festgeschrieben_anlass": anlass}
    await db().invoices.update_one({"id": r["id"]}, {"$set": aenderung})
    await protokollieren(user, "rechnung.ausgestellt", r["number"], details={"anlass": anlass, "brutto": r.get("gross")})
    return {**r, **aenderung}


@router.post("/anlegen")
async def anlegen(body: RechnungAnlegenIn, user: dict = Depends(schreibend("buero"))):
    """Bestehende Rechnung des Monats zurückgeben (nur Entwürfe werden neu berechnet, ausgestellte nie) oder mit nächster Nummer anlegen.
    Mit nur_pruefen wird nichts angelegt und keine Nummer vergeben."""
    p = await projekt_laden(user, body.project_id)
    firma = user["_firma"]
    eintraege = await _monatseintraege(user["firma_id"], p["id"], body.year, body.month)
    vorhanden = await db().invoices.find_one({"firma_id": user["firma_id"], "project_id": p["id"], "year": body.year, "month": body.month}, {"_id": 0})
    if vorhanden:
        if vorhanden.get("status", "offen") == "offen" and not festgeschrieben(vorhanden) and not body.nur_pruefen:
            calc = rechnung_berechnen(p, firma, body.year, body.month, eintraege, vorhanden.get("extras") or [])
            await db().invoices.update_one({"id": vorhanden["id"]}, {"$set": _summen(calc)})
            vorhanden.update(_summen(calc))
        return {"rechnung": vorhanden, "neu": False}
    calc = rechnung_berechnen(p, firma, body.year, body.month, eintraege)
    if not calc["total_minutes"]:
        raise HTTPException(400, "In diesem Monat sind keine Arbeitszeiten eingetragen.")
    if body.nur_pruefen:
        return {"rechnung": None, "neu": False, "vorschau": {"prefix": firma.get("invoice_prefix") or "RE-", "year": body.year, **_summen(calc)}}
    for _ in range(6):
        seq = await _naechste_nummer(user["firma_id"], body.year)
        r = {"id": neue_id(), "firma_id": user["firma_id"], "project_id": p["id"], "customer_id": p.get("customer_id"),
             "year": body.year, "month": body.month, "seq": seq,
             "number": f"{firma.get('invoice_prefix') or 'RE-'}{body.year}-{seq:04d}",
             "invoice_date": lokal_jetzt().date().isoformat(), "status": "offen", "paid_at": None,
             "created_by": user["id"], "created_at": jetzt_iso(), **_summen(calc)}
        try:
            await db().invoices.insert_one(dict(r))
            break
        except DuplicateKeyError:
            continue
    else:
        raise HTTPException(503, "Rechnungsnummer konnte nicht vergeben werden, bitte noch einmal versuchen.")
    await protokollieren(user, "rechnung.angelegt", r["number"], details={"projekt": p["name"], "monat": f"{body.year}-{body.month:02d}", "brutto": r["gross"]})
    return {"rechnung": r, "neu": True}


async def _laden(user: dict, rechnung_id: str) -> dict:
    r = await db().invoices.find_one({"id": rechnung_id, "firma_id": user["firma_id"]}, {"_id": 0})
    if not r:
        raise HTTPException(404, "Rechnung nicht gefunden.")
    return r


@router.get("/{rechnung_id}/daten")
async def daten(rechnung_id: str, user: dict = Depends(rolle_noetig("buero"))):
    """Alles für das PDF: Firma, Projekt, Rechnung, Einträge des Wochenrasters, Kunden-Unterschriften."""
    r = await _laden(user, rechnung_id)
    r = await _festschreiben(user, r, "pdf")
    p = await projekt_laden(user, r["project_id"])
    firma = await firma_laden(user["firma_id"])
    von, bis = rasterbereich(r["year"], r["month"])
    namen = await nutzernamen(user["firma_id"])
    eintraege = []
    async for e in db().entries.find({"firma_id": user["firma_id"], "project_id": p["id"], "date": {"$gte": von, "$lte": bis}}, {"_id": 0}).sort([("date", 1), ("start_time", 1)]):
        eintraege.append(eintrag_anreichern(e, namen))
    unterschriften = []
    async for s in db().signatures.find({"firma_id": user["firma_id"], "project_id": p["id"], "week_monday": {"$gte": von, "$lte": bis}, "ersetzt": {"$ne": True}}, {"_id": 0}):
        unterschriften.append(s)
    return {"firma": firma_oeffentlich(firma, user), "projekt": p, "rechnung": r, "eintraege": eintraege, "unterschriften": unterschriften,
            "fotos": await projekt_fotos(user["firma_id"], p["id"], von, bis)}


@router.put("/{rechnung_id}/extras")
async def extras(rechnung_id: str, body: ExtrasIn, user: dict = Depends(schreibend("buero"))):
    """Zusatzpositionen (Material, Anfahrt, Pauschalen) setzen – nur bei offenen Rechnungen; Summen werden neu berechnet."""
    r = await _laden(user, rechnung_id)
    if r.get("status", "offen") != "offen":
        raise HTTPException(400, "Positionen lassen sich nur bei offenen Rechnungen ändern.")
    if festgeschrieben(r):
        raise HTTPException(400, "Die Rechnung ist ausgestellt. Positionen lassen sich nicht mehr ändern – bitte stornieren und neu anlegen.")
    p = await projekt_laden(user, r["project_id"])
    calc = rechnung_berechnen(p, user["_firma"], r["year"], r["month"], await _monatseintraege(user["firma_id"], p["id"], r["year"], r["month"]),
                              [x.model_dump() for x in body.extras])
    await db().invoices.update_one({"id": rechnung_id}, {"$set": _summen(calc)})
    await protokollieren(user, "rechnung.positionen", r["number"], details={"anzahl": len(body.extras), "zusatz_netto": calc["extras_net"]})
    return {"rechnung": {**r, **_summen(calc)}}


@router.put("/{rechnung_id}")
async def status(rechnung_id: str, body: RechnungStatusIn, user: dict = Depends(schreibend("buero"))):
    r = await _laden(user, rechnung_id)
    aenderung = {"status": body.status, "updated_at": jetzt_iso()}
    if body.status == "bezahlt":
        aenderung["paid_at"] = body.paid_at or lokal_jetzt().date().isoformat()
        try:
            datum_pruefen(aenderung["paid_at"])
        except ValueError as exc:
            raise HTTPException(400, str(exc))
    else:
        aenderung["paid_at"] = None
    if body.invoice_date:
        if r.get("status", "offen") != "offen":
            raise HTTPException(400, "Das Datum lässt sich nur bei offenen Rechnungen ändern.")
        if festgeschrieben(r) and body.invoice_date != r.get("invoice_date"):
            raise HTTPException(400, "Die Rechnung ist ausgestellt – das Rechnungsdatum lässt sich nicht mehr ändern.")
        try:
            datum_pruefen(body.invoice_date)
        except ValueError as exc:
            raise HTTPException(400, str(exc))
        aenderung["invoice_date"] = body.invoice_date
    await db().invoices.update_one({"id": rechnung_id}, {"$set": aenderung})
    await protokollieren(user, "rechnung.status", r["number"], details=aenderung)
    return {"rechnung": {**r, **aenderung}}


@router.post("/{rechnung_id}/neu-berechnen")
async def neu_berechnen(rechnung_id: str, erzwingen: bool = False, user: dict = Depends(schreibend("buero"))):
    """Entwürfe neu berechnen. Ausgestellte Rechnungen nur ausdrücklich durch den Inhaber (erzwingen) – mit Korrekturvermerk und alten Summen."""
    r = await _laden(user, rechnung_id)
    if r.get("status", "offen") != "offen":
        raise HTTPException(400, "Nur offene Rechnungen lassen sich neu berechnen.")
    if festgeschrieben(r):
        if not erzwingen:
            raise HTTPException(400, "Die Rechnung ist ausgestellt und wird nicht stillschweigend neu berechnet. Bitte stornieren und neu anlegen – oder als Inhaber ausdrücklich neu berechnen.")
        if not hat_rolle(user, "inhaber"):
            raise HTTPException(403, "Eine ausgestellte Rechnung darf nur der Inhaber neu berechnen.")
    p = await projekt_laden(user, r["project_id"])
    calc = rechnung_berechnen(p, user["_firma"], r["year"], r["month"], await _monatseintraege(user["firma_id"], p["id"], r["year"], r["month"]), r.get("extras") or [])
    aenderung = _summen(calc)
    if festgeschrieben(r):
        korrektur = {"at": jetzt_iso(), "user_name": user.get("name"), "vorher": {k: r.get(k) for k in ("net", "vat", "gross", "total_minutes")}, "nachher": {k: aenderung.get(k) for k in ("net", "vat", "gross", "total_minutes")}}
        await db().invoices.update_one({"id": rechnung_id}, {"$set": aenderung, "$push": {"korrekturen": korrektur}})
        await protokollieren(user, "rechnung.neu_berechnet_erzwungen", r["number"], details=korrektur)
        return {"rechnung": {**r, **aenderung, "korrekturen": (r.get("korrekturen") or []) + [korrektur]}}
    await db().invoices.update_one({"id": rechnung_id}, {"$set": aenderung})
    return {"rechnung": {**r, **aenderung}}


@router.post("/{rechnung_id}/festschreiben")
async def festschreiben(rechnung_id: str, user: dict = Depends(schreibend("buero"))):
    """Rechnung ausdrücklich ausstellen (z. B. nachdem die PDF im Browser erzeugt wurde)."""
    r = await _laden(user, rechnung_id)
    return {"rechnung": await _festschreiben(user, r, "ausgestellt")}


@router.delete("/{rechnung_id}")
async def loeschen(rechnung_id: str, user: dict = Depends(schreibend("buero"))):
    """Rechnungsnummer zurücksetzen (nur offene Rechnungen; bezahlte/stornierte bleiben als Beleg)."""
    r = await _laden(user, rechnung_id)
    if r.get("status", "offen") != "offen":
        raise HTTPException(400, "Bezahlte oder stornierte Rechnungen bleiben als Beleg erhalten.")
    if festgeschrieben(r):
        raise HTTPException(400, "Die Rechnung ist ausgestellt und bleibt als Beleg erhalten – bitte stornieren. Die Nummer wird nicht neu vergeben.")
    await db().invoices.delete_one({"id": rechnung_id})
    await protokollieren(user, "rechnung.zurueckgesetzt", r["number"])
    return {"ok": True}


# ---------- E-Rechnung: XRechnung 3.0 (XML) und ZUGFeRD/Factur-X EN 16931 (PDF/A-3) ----------

async def _erechnung(user: dict, rechnung_id: str) -> tuple[dict, dict, dict]:
    r = await _laden(user, rechnung_id)
    p = await projekt_laden(user, r["project_id"])
    firma = await firma_laden(user["firma_id"])
    k = await kunde_laden(user["firma_id"], r.get("customer_id") or p.get("customer_id"))
    return erechnung.rechnungsdaten(firma, p, k, r), firma, r


def _datei(inhalt: bytes, name: str, typ: str) -> Response:
    return Response(content=inhalt, media_type=typ, headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/{rechnung_id}/erechnung")
async def erechnung_status(rechnung_id: str, user: dict = Depends(rolle_noetig("buero"))):
    """Vorab-Prüfung: Was fehlt noch für XRechnung bzw. ZUGFeRD? Nichts wird erzeugt."""
    daten, _, r = await _erechnung(user, rechnung_id)
    k = daten["kaeufer"]
    return {"xrechnung": erechnung.pruefen(daten, "xrechnung"), "zugferd": erechnung.pruefen(daten, "zugferd"), "erzeugt": r.get("erechnung") or {},
            "faellig": daten["faellig"], "kaeufer": {"name": k["name"], "leitweg_id": k["leitweg_id"], "email": k["email"], "zip_code": k["zip_code"], "city": k["city"]},
            "steuer": daten["steuer"]["category"]}


async def _freigeben(user: dict, rechnung_id: str, profil: str) -> tuple[dict, dict, dict]:
    daten, firma, r = await _erechnung(user, rechnung_id)
    pr = erechnung.pruefen(daten, profil)
    if not pr["ok"]:
        raise HTTPException(422, f"Für {pr['bezeichnung']} fehlt: " + "; ".join(pr["fehlt"]))
    r = await _festschreiben(user, r, profil)
    await db().invoices.update_one({"id": r["id"]}, {"$set": {f"erechnung.{profil}_at": jetzt_iso()}})
    await protokollieren(user, "rechnung.erechnung", r["number"], details={"format": profil})
    return daten, firma, r


@router.get("/{rechnung_id}/xrechnung.xml")
async def xrechnung_xml(rechnung_id: str, user: dict = Depends(rolle_noetig("buero"))):
    daten, _, _ = await _freigeben(user, rechnung_id, "xrechnung")
    return _datei(erechnung.cii_xml(daten, "xrechnung"), "XRechnung_" + erechnung.dateiname(daten, "xml"), "application/xml")


@router.get("/{rechnung_id}/zugferd.pdf")
async def zugferd_pdf(rechnung_id: str, user: dict = Depends(rolle_noetig("buero"))):
    daten, firma, _ = await _freigeben(user, rechnung_id, "zugferd")
    pdf = pdfbasis.pdfa3_mit_xml(erechnung.rechnung_pdf(daten), erechnung.cii_xml(daten, "zugferd"), f"Rechnung {daten['nummer']}", firma.get("name") or "")
    return _datei(pdf, "ZUGFeRD_" + erechnung.dateiname(daten, "pdf"), "application/pdf")


@router.get("/{rechnung_id}/rechnung.pdf")
async def rechnung_pdf(rechnung_id: str, user: dict = Depends(rolle_noetig("buero"))):
    """Serverseitige Rechnung ohne XML (PDF/A-3b), gleicher Aufbau wie die ZUGFeRD-Rechnung."""
    daten, firma, r = await _erechnung(user, rechnung_id)
    await _festschreiben(user, r, "pdf")
    pdf = pdfbasis.pdfa3_mit_xml(erechnung.rechnung_pdf(daten), None, f"Rechnung {daten['nummer']}", firma.get("name") or "")
    return _datei(pdf, "Rechnung_" + erechnung.dateiname(daten, "pdf"), "application/pdf")
