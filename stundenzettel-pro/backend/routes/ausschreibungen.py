"""Ausschreibungen, Einladungen, Marktplatz, Angebote mit Positionspreisen, Rückfragen, Vergleich/Bewertung und mehrstufige Vergabe.
Rechtemodell und Konstanten: ausschreibung.py. Nach der verbindlichen Annahme entsteht die Beteiligung am Projekt (Phase 4/5-Funktionen)."""
from __future__ import annotations

import csv
import io
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response

import gaeb
from ausschreibung import (ABRECHNUNGSARTEN, ANGEBOT_STATUS_NAMEN, ANNAHME_TEXT, AUSSCHREIBUNG_STATUS_NAMEN, BEWERTUNGSKRITERIEN, EINGEREICHT,
                           KATEGORIEN_ANGEBOT, KATEGORIEN_AUSSCHREIBUNG, KATEGORIEN_VERGABE, NACHFRIST_TAGE, SICHTBARKEIT_NAMEN, VERGABE_STATUS_NAMEN,
                           angebot_anreichern, angebot_summe, angebot_zugang, auftraggeber_info, ausschreibung_zugang, eigenes_angebot,
                           einladung_der_firma, frist_offen, frist_tage, heute, interessierte_firmen, leitung_benachrichtigen, leitung_noetig,
                           neue_vergabe_pruefen, nummer_vergeben, oeffentliche_ansicht, positionen_berechnen, schritt, vergabe_schritt,
                           vergabe_zugang, zweites_augenpaar)
from abo import gu_abo_aktivieren, gu_freigeschaltet, ist_auftraggeber
from auth import aktueller_nutzer, firma_laden, hat_rolle, jetzt_iso, rolle_noetig, schreibend
from preise import PREISE
from dateien import datei_speichern, speicher_belegt, speicher_grenze, version_verknuepfen
from db import db
from gemeinsam import neue_id, projekt_normalisieren
from models import (AngebotIn, AngebotPruefungIn, AntwortIn, AusschreibungEinladungIn, AusschreibungIn, BewertungIn, FrageIn, PositionenTextIn,
                    VergabeAntwortIn, VergabeMitteilungIn, VergabeVorschlagIn)
from plattform import GEWERKE, benachrichtigen, firma_kurz, zugang
from plattform import leitung_noetig as projekt_leitung_noetig
from protokoll import protokollieren
import config
import mail

router = APIRouter(tags=["Ausschreibungen"])

AUSSCHREIBUNG_FELDER = ("titel", "gewerk", "leistungsart", "beschreibung", "leistungsumfang", "ausfuehrungsort", "sichtbarkeit", "bewerbungsfrist", "angebotsfrist",
                        "ausfuehrung_von", "ausfuehrung_bis", "anforderungen", "kaufmaennisch", "freigabe", "positionen", "intern")
ANGEBOT_FELDER = ("nummer", "ansprechpartner", "preisart", "preis_netto", "stundensatz", "stunden_geschaetzt", "ust_satz", "reverse_charge", "positionen",
                  "leistungsbeschreibung", "ausfuehrung_von", "ausfuehrung_bis", "verfuegbarkeit", "kapazitaet", "material", "zusatzleistungen", "bemerkungen", "gueltig_bis")


def _link(a_id: str) -> str:
    return f"/ausschreibungen/{a_id}"


async def _auftraggeber_noetig(user: dict) -> dict:
    """Formale Ausschreibungen (Bieterliste, Vergleich, Vergabe) gibt es nur für Auftraggeber-Konten."""
    firma = user.get("_firma") or await firma_laden(user["firma_id"])
    if not ist_auftraggeber(firma):
        raise HTTPException(403, "Formale Ausschreibungen können nur Auftraggeber-Konten anlegen und veröffentlichen (Firma → Firmendaten → Firmenart „Auftraggeber“ oder „Beides“). "
                                 "Partnerfirmen lassen sich weiterhin direkt unter „Zusammenarbeit“ zum Projekt einladen.")
    if not gu_freigeschaltet(firma):
        raise HTTPException(403, "Nach der Testphase brauchen formale Ausschreibungen die GU-Freischaltung durch den Anbieter "
                                 "(Projektabo 50,99 € netto je aktivem Bauprojekt). Bitte den Anbieter kontaktieren – Partnerfirmen lassen sich weiterhin unter „Zusammenarbeit“ einladen.")
    user["_firma"] = firma
    return firma


def _datei(inhalt: bytes, name: str, typ: str) -> Response:
    return Response(content=inhalt, media_type=typ, headers={"Content-Disposition": f'attachment; filename="{name}"'})


async def _dokumente(scope: str, ref_id: str) -> list[dict]:
    return [d async for d in db().documents.find({"scope": scope, "ref_id": ref_id}, {"_id": 0, "path": 0}).sort("created_at", 1)]


async def _projekt_oeffentlich(a: dict) -> dict:
    """Projektangaben, die Bieter sehen dürfen (keine internen Dokumente, Adresse nur mit Freigabe)."""
    p = await db().projects.find_one({"id": a["project_id"]}, {"_id": 0})
    if not p:
        return {}
    p = projekt_normalisieren(p)
    aus = {k: p.get(k) for k in ("name", "projektart", "baubeginn", "bauende", "beschreibung", "projektnummer", "auftraggeber", "generalunternehmer", "gewerke",
                                 "projektstatus", "phasen", "bauabschnitte")}
    aus["address"] = p.get("address") if (a.get("freigabe") or {}).get("adresse", True) else ""
    aus["id"] = p["id"]
    return aus


async def _zaehler(a_id: str) -> dict:
    status = [g["status"] async for g in db().angebote.find({"ausschreibung_id": a_id}, {"_id": 0, "status": 1})]
    eingereicht = [s for s in status if s in EINGEREICHT]
    return {"angebote": len(eingereicht), "neu": sum(1 for s in eingereicht if s in ("eingereicht", "ueberarbeitet")),
            "in_pruefung": sum(1 for s in eingereicht if s == "in_pruefung"), "rueckfragen": sum(1 for s in eingereicht if s == "rueckfrage"),
            "abgelehnt": sum(1 for s in eingereicht if s == "abgelehnt"), "angenommen": sum(1 for s in eingereicht if s == "angenommen"),
            "einladungen": await db().ausschreibung_einladungen.count_documents({"ausschreibung_id": a_id}),
            "fragen_offen": await db().ausschreibung_fragen.count_documents({"ausschreibung_id": a_id, "antwort": None})}


async def _karte(a: dict, user: dict, einladung: Optional[dict] = None, angebot: Optional[dict] = None) -> dict:
    """Kurzfassung für Listen und den Marktplatz."""
    p = await _projekt_oeffentlich(a)
    ag = await auftraggeber_info(a)
    k = a.get("kaufmaennisch") or {}
    aus = {"id": a["id"], "nummer": a.get("nummer"), "titel": a.get("titel"), "gewerk": a.get("gewerk"), "leistungsart": a.get("leistungsart"),
           "status": a.get("status"), "status_name": AUSSCHREIBUNG_STATUS_NAMEN.get(a.get("status"), a.get("status")), "sichtbarkeit": a.get("sichtbarkeit"),
           "sichtbarkeit_name": SICHTBARKEIT_NAMEN.get(a.get("sichtbarkeit"), ""), "angebotsfrist": a.get("angebotsfrist"), "bewerbungsfrist": a.get("bewerbungsfrist"),
           "frist_tage": frist_tage(a), "frist_offen": frist_offen(a), "ausfuehrung_von": a.get("ausfuehrung_von"), "ausfuehrung_bis": a.get("ausfuehrung_bis"),
           "ausfuehrungsort": a.get("ausfuehrungsort") or p.get("address") or "", "abrechnungsart": k.get("abrechnungsart"), "abrechnungsart_name": ABRECHNUNGSARTEN.get(k.get("abrechnungsart"), ""),
           "budget": k.get("budget") if (a.get("freigabe") or {}).get("budget") or a["firma_id"] == user["firma_id"] else None,
           "projekt": {"id": a["project_id"], "name": p.get("name"), "projektart": p.get("projektart")}, "auftraggeber": ag, "veroeffentlicht_am": a.get("veroeffentlicht_am"),
           "eingeladen": bool(einladung), "einladung_status": (einladung or {}).get("status"),
           "angebot": {"id": angebot["id"], "status": angebot["status"], "status_name": ANGEBOT_STATUS_NAMEN.get(angebot["status"])} if angebot else None}
    if a["firma_id"] == user["firma_id"]:
        aus["zaehler"] = await _zaehler(a["id"])
        aus["verantwortlich_name"] = a.get("verantwortlich_name")
    return aus


async def _fragen(a: dict, zg: dict, user: dict) -> list[dict]:
    aus = []
    async for f in db().ausschreibung_fragen.find({"ausschreibung_id": a["id"]}, {"_id": 0}).sort("created_at", 1):
        if zg["rolle"] == "leitung":
            aus.append(f)
        elif f.get("firma_id") == user["firma_id"]:
            aus.append({**f, "eigene": True})
        elif f.get("oeffentlich") and f.get("antwort"):
            aus.append({**f, "firma_id": None, "firma_name": "Ein Bieter", "user_name": None, "eigene": False})
    return aus


async def _detail(user: dict, zg: dict) -> dict:
    a = zg["ausschreibung"]
    leitung = zg["rolle"] == "leitung"
    aus = dict(a) if leitung else oeffentliche_ansicht(a)
    aus["rolle"] = zg["rolle"]
    aus["status_name"] = AUSSCHREIBUNG_STATUS_NAMEN.get(a.get("status"), a.get("status"))
    aus["sichtbarkeit_name"] = SICHTBARKEIT_NAMEN.get(a.get("sichtbarkeit"), "")
    aus["abrechnungsart_name"] = ABRECHNUNGSARTEN.get((a.get("kaufmaennisch") or {}).get("abrechnungsart"), "")
    aus["frist_offen"] = frist_offen(a)
    aus["frist_tage"] = frist_tage(a)
    aus["auftraggeber"] = await auftraggeber_info(a)
    aus["projekt"] = await _projekt_oeffentlich(a)
    aus["dokumente"] = await _dokumente("ausschreibung", a["id"])
    aus["fragen"] = await _fragen(a, zg, user)
    aus["kategorien"] = {"ausschreibung": KATEGORIEN_AUSSCHREIBUNG, "angebot": KATEGORIEN_ANGEBOT, "vergabe": KATEGORIEN_VERGABE}
    aus["gewerke"] = GEWERKE
    aus["kriterien"] = list(BEWERTUNGSKRITERIEN)
    if leitung:
        aus["zaehler"] = await _zaehler(a["id"])
        aus["gu_abo"] = ((zg.get("zugang") or {}).get("projekt") or {}).get("gu_abo")   # Stand des GU-Projektabos für die Leitung
        aus["preise"] = PREISE
        aus["einladungen"] = [e async for e in db().ausschreibung_einladungen.find({"ausschreibung_id": a["id"]}, {"_id": 0}).sort("created_at", 1)]
        aus["vergabe"] = await db().vergaben.find_one({"ausschreibung_id": a["id"], "status": {"$in": ["vorgeschlagen", "freigegeben", "mitgeteilt", "angenommen"]}}, {"_id": 0})
        aus["vergaben_verlauf"] = [v async for v in db().vergaben.find({"ausschreibung_id": a["id"]}, {"_id": 0}).sort("created_at", 1)]
    else:
        aus["einladung"] = zg.get("einladung")
        aus["angebot"] = await angebot_anreichern(zg["angebot"], a, False) if zg.get("angebot") else None
        aus["kann_bieten"] = a.get("status") == "veroeffentlicht" and (frist_offen(a) or ((zg.get("angebot") or {}).get("status") == "rueckfrage"))
        v = await db().vergaben.find_one({"ausschreibung_id": a["id"], "firma_id": user["firma_id"], "status": {"$in": ["mitgeteilt", "angenommen", "abgelehnt_firma"]}}, {"_id": 0})
        aus["vergabe"] = {**v, "status_name": VERGABE_STATUS_NAMEN.get(v["status"]), "dokumente": await _dokumente("vergabe", v["id"]), "annahme_text": ANNAHME_TEXT} if v else None
    return aus


async def _firmen_benachrichtigen(a: dict, art: str, text: str, nur_bieter: bool = False) -> None:
    """Eingeladene Firmen und Firmen mit Angebot informieren (einmal je Firma)."""
    ids = set()
    if not nur_bieter:
        async for e in db().ausschreibung_einladungen.find({"ausschreibung_id": a["id"]}, {"_id": 0, "firma_id": 1}):
            ids.add(e["firma_id"])
    async for g in db().angebote.find({"ausschreibung_id": a["id"], "status": {"$nin": ["abgelehnt", "zurueckgezogen"]}}, {"_id": 0, "firma_id": 1}):
        ids.add(g["firma_id"])
    for fid in ids:
        await benachrichtigen(fid, art, text, _link(a["id"]))


def _csv_lesen(text: str) -> list[dict]:
    text = text.lstrip("﻿")
    erste = text.splitlines()[0] if text.strip() else ""
    trenner = ";" if ";" in erste else "\t" if "\t" in erste else ","
    aus, gesehen = [], set()
    for zeile in csv.reader(io.StringIO(text), delimiter=trenner):
        if not zeile or not any(z.strip() for z in zeile):
            continue
        nr = zeile[0].strip()
        if nr.lower() in ("nr", "nr.", "pos", "pos.", "position", "positionsnummer", "oz"):
            continue
        if len(zeile) < 2 or not zeile[1].strip():
            raise HTTPException(400, f"Zeile „{';'.join(zeile)[:60]}“: Leistung fehlt (Format Nr;Leistung;Menge;Einheit).")
        menge_text = (zeile[2] if len(zeile) > 2 else "0").strip().replace(".", "").replace(",", ".") if "," in (zeile[2] if len(zeile) > 2 else "") else (zeile[2] if len(zeile) > 2 else "0").strip()
        try:
            menge = float(menge_text or 0)
        except ValueError:
            raise HTTPException(400, f"Position {nr}: Menge „{zeile[2]}“ ist keine Zahl.")
        if nr in gesehen:
            raise HTTPException(400, f"Position {nr} kommt doppelt vor.")
        gesehen.add(nr)
        aus.append({"nr": nr[:20], "leistung": zeile[1].strip()[:300], "menge": menge, "einheit": (zeile[3].strip() if len(zeile) > 3 else "Stück")[:20] or "Stück",
                    "beschreibung": (zeile[4].strip() if len(zeile) > 4 else "")[:2000]})
    if not aus:
        raise HTTPException(400, "Keine Positionen gefunden.")
    if len(aus) > 500:
        raise HTTPException(400, "Höchstens 500 Positionen.")
    return aus


def _csv_schreiben(positionen: list[dict], preise: Optional[dict] = None) -> str:
    buf = io.StringIO()
    from csvsicher import Writer
    w = Writer(buf, delimiter=";", lineterminator="\r\n")
    kopf = ["Nr", "Leistung", "Menge", "Einheit", "Beschreibung"] + (["Einzelpreis", "Gesamt"] if preise is not None else [])
    w.writerow(kopf)
    for p in positionen:
        zeile = [p.get("nr"), p.get("leistung"), str(p.get("menge") or 0).replace(".", ","), p.get("einheit"), p.get("beschreibung") or ""]
        if preise is not None:
            z = preise.get(p.get("nr")) or {}
            zeile += [str(z.get("einzelpreis") if z.get("einzelpreis") is not None else "").replace(".", ","), str(z.get("gesamt") if z.get("gesamt") is not None else "").replace(".", ",")]
        w.writerow(zeile)
    return "﻿" + buf.getvalue()


# ================================================================ Eigentümerseite: Ausschreibungen je Projekt

@router.get("/api/projekte/{project_id}/ausschreibungen")
async def projekt_ausschreibungen(project_id: str, user: dict = Depends(aktueller_nutzer)):
    z = await zugang(user, project_id)
    projekt_leitung_noetig(z)
    aus = [await _karte(a, user) async for a in db().ausschreibungen.find({"project_id": project_id}, {"_id": 0}).sort("created_at", -1)]
    return {"ausschreibungen": aus, "gewerke": GEWERKE, "abrechnungsarten": ABRECHNUNGSARTEN, "sichtbarkeiten": SICHTBARKEIT_NAMEN}


@router.post("/api/projekte/{project_id}/ausschreibungen")
async def ausschreibung_anlegen(project_id: str, body: AusschreibungIn, user: dict = Depends(schreibend("mitarbeiter"))):
    z = await zugang(user, project_id)
    projekt_leitung_noetig(z)
    await _auftraggeber_noetig(user)
    p = z["projekt"]
    daten = body.model_dump()
    verantwortlich = user
    if body.verantwortlich_user_id and body.verantwortlich_user_id != user["id"]:
        v = await db().users.find_one({"id": body.verantwortlich_user_id, "firma_id": user["firma_id"], "active": {"$ne": False}}, {"_id": 0, "id": 1, "name": 1})
        if not v:
            raise HTTPException(400, "Verantwortlicher Projektleiter nicht gefunden.")
        verantwortlich = v
    a = {"id": neue_id(), "nummer": await nummer_vergeben(user["firma_id"], "ausschreibungen", "A"), "project_id": project_id, "firma_id": user["firma_id"],
         **{k: daten[k] for k in AUSSCHREIBUNG_FELDER}, "status": "entwurf", "veroeffentlicht_am": None, "verantwortlich_user_id": verantwortlich["id"],
         "verantwortlich_name": verantwortlich.get("name"), "verlauf": [schritt(user, "angelegt")], "created_at": jetzt_iso(), "updated_at": jetzt_iso()}
    await db().ausschreibungen.insert_one(dict(a))
    await protokollieren(user, "ausschreibung.angelegt", a["titel"], details={"projekt": p["name"], "nummer": a["nummer"]})
    return {"ausschreibung": await _detail(user, {"ausschreibung": a, "rolle": "leitung", "zugang": z})}


# ================================================================ Übersicht und Marktplatz (alle Firmen, Büro/Inhaber)

@router.get("/api/ausschreibungen/uebersicht")
async def uebersicht(user: dict = Depends(rolle_noetig("buero"))):
    """Für die Seite „Ausschreibungen“: Einladungen, eigene Angebote, erhaltene Aufträge, eigene Ausschreibungen, laufende Vergaben."""
    fid = user["firma_id"]
    einladungen, angebote, vergaben, eigene, vergaben_eigene, fristen_bald = [], [], [], [], [], []
    async for e in db().ausschreibung_einladungen.find({"firma_id": fid}, {"_id": 0}).sort("created_at", -1).limit(200):
        a = await db().ausschreibungen.find_one({"id": e["ausschreibung_id"]}, {"_id": 0})
        if not a or a.get("status") not in ("veroeffentlicht", "in_vergabe", "vergeben", "aufgehoben"):
            continue
        g = await eigenes_angebot(a["id"], fid)
        karte = await _karte(a, user, e, g)
        einladungen.append({**karte, "nachricht": e.get("nachricht"), "eingeladen_am": e.get("created_at")})
        if a.get("status") == "veroeffentlicht" and not g and karte["frist_tage"] is not None and 0 <= karte["frist_tage"] <= 3:
            fristen_bald.append(karte)
    async for g in db().angebote.find({"firma_id": fid}, {"_id": 0}).sort("updated_at", -1).limit(200):
        a = await db().ausschreibungen.find_one({"id": g["ausschreibung_id"]}, {"_id": 0})
        if not a:
            continue
        karte = await _karte(a, user, await einladung_der_firma(a["id"], fid), g)
        angebote.append({**karte, "angebot": {**karte["angebot"], "summe_netto": angebot_summe(a, g), "version": g.get("version", 0), "eingereicht_at": g.get("eingereicht_at"), "nachreichen_bis": g.get("nachreichen_bis")}})
        if g.get("status") == "entwurf" and a.get("status") == "veroeffentlicht" and karte["frist_tage"] is not None and 0 <= karte["frist_tage"] <= 3 and karte["id"] not in [f["id"] for f in fristen_bald]:
            fristen_bald.append(karte)
    async for v in db().vergaben.find({"firma_id": fid, "status": {"$in": ["mitgeteilt", "angenommen", "abgelehnt_firma"]}}, {"_id": 0}).sort("created_at", -1).limit(100):
        a = await db().ausschreibungen.find_one({"id": v["ausschreibung_id"]}, {"_id": 0})
        if a:
            vergaben.append({**v, "status_name": VERGABE_STATUS_NAMEN.get(v["status"]), "ausschreibung": await _karte(a, user), "auftraggeber": await auftraggeber_info(a)})
    async for a in db().ausschreibungen.find({"firma_id": fid}, {"_id": 0}).sort("created_at", -1).limit(300):
        z = await zugang(user, a["project_id"]) if not hat_rolle(user, "buero") else None
        if z is not None and not z["leitung"]:
            continue
        eigene.append(await _karte(a, user))
    async for v in db().vergaben.find({"owner_firma_id": fid, "status": {"$in": ["vorgeschlagen", "freigegeben", "mitgeteilt"]}}, {"_id": 0}).sort("created_at", -1).limit(100):
        a = await db().ausschreibungen.find_one({"id": v["ausschreibung_id"]}, {"_id": 0})
        if a:
            vergaben_eigene.append({**v, "status_name": VERGABE_STATUS_NAMEN.get(v["status"]), "ausschreibung": await _karte(a, user)})
    return {"einladungen": einladungen, "angebote": angebote, "vergaben": vergaben, "eigene": eigene, "vergaben_eigene": vergaben_eigene,
            "fristen_bald": fristen_bald, "gewerke": GEWERKE, "abrechnungsarten": ABRECHNUNGSARTEN, "annahme_text": ANNAHME_TEXT}


@router.get("/api/ausschreibungen")
async def marktplatz(q: str = Query("", max_length=120), gewerk: str = Query("", max_length=60), ort: str = Query("", max_length=120),
                     auftraggeber: str = Query("", max_length=120), projektart: str = Query("", max_length=120), abrechnungsart: str = Query("", max_length=30),
                     von: str = Query("", max_length=10), bis: str = Query("", max_length=10), frist_bis: str = Query("", max_length=10),
                     volumen_max: Optional[float] = Query(None, ge=0), status: str = Query("", max_length=30), nur_einladungen: bool = False,
                     user: dict = Depends(rolle_noetig("buero"))):
    """Ausschreibungen entdecken: plattformweit sichtbare und solche, zu denen die eigene Firma eingeladen ist (nie eigene, nie Entwürfe)."""
    fid = user["firma_id"]
    eingeladen = {e["ausschreibung_id"]: e async for e in db().ausschreibung_einladungen.find({"firma_id": fid}, {"_id": 0})}
    aus = []
    filt = {"firma_id": {"$ne": fid}, "status": {"$in": [status] if status in ("veroeffentlicht", "in_vergabe", "vergeben") else ["veroeffentlicht", "in_vergabe"]}}
    async for a in db().ausschreibungen.find(filt, {"_id": 0}).sort("angebotsfrist", 1).limit(2000):
        e = eingeladen.get(a["id"])
        if not (a.get("sichtbarkeit") in ("oeffentlich", "kombiniert") or e):
            continue
        if nur_einladungen and not e:
            continue
        karte = await _karte(a, user, e, await eigenes_angebot(a["id"], fid))
        text = " ".join(str(x or "") for x in (a.get("titel"), a.get("beschreibung"), a.get("leistungsumfang"), a.get("gewerk"), a.get("leistungsart"), karte["projekt"].get("name"))).lower()
        if q and q.lower() not in text:
            continue
        if gewerk and (a.get("gewerk") or "").lower() != gewerk.lower():
            continue
        if ort and ort.lower() not in f"{karte['ausfuehrungsort']} {karte['auftraggeber'].get('city') or ''}".lower():
            continue
        if auftraggeber and (karte["auftraggeber"].get("anonym") or auftraggeber.lower() not in (karte["auftraggeber"].get("name") or "").lower()):
            continue
        if projektart and projektart.lower() not in (karte["projekt"].get("projektart") or "").lower():
            continue
        if abrechnungsart and karte["abrechnungsart"] != abrechnungsart:
            continue
        if von and a.get("ausfuehrung_bis") and a["ausfuehrung_bis"] < von:
            continue
        if bis and a.get("ausfuehrung_von") and a["ausfuehrung_von"] > bis:
            continue
        if frist_bis and (a.get("angebotsfrist") or "9999") > frist_bis:
            continue
        if volumen_max is not None and karte["budget"] is not None and karte["budget"] > volumen_max:
            continue
        aus.append(karte)
    return {"ausschreibungen": aus, "gewerke": GEWERKE, "abrechnungsarten": ABRECHNUNGSARTEN}


@router.get("/api/firma/speicher")
async def speicher(user: dict = Depends(rolle_noetig("buero"))):
    belegt, grenze = await speicher_belegt(user["firma_id"]), await speicher_grenze(user["firma_id"])
    return {"belegt_bytes": belegt, "grenze_bytes": grenze, "belegt_mb": round(belegt / 1024 / 1024, 1), "grenze_gb": round(grenze / 1024 / 1024 / 1024, 2),
            "max_datei_mb": config.MAX_DATEI_MB, "uploads_je_10_min": config.UPLOADS_JE_10_MIN}


# ================================================================ Einzelne Ausschreibung

@router.get("/api/ausschreibungen/{ausschreibung_id}")
async def ausschreibung_lesen(ausschreibung_id: str, user: dict = Depends(aktueller_nutzer)):
    zg = await ausschreibung_zugang(user, ausschreibung_id)
    if zg["rolle"] == "bieter" and zg.get("einladung") and zg["einladung"].get("status") == "eingeladen":
        await db().ausschreibung_einladungen.update_one({"id": zg["einladung"]["id"]}, {"$set": {"status": "angesehen", "angesehen_at": jetzt_iso()}})
        zg["einladung"] = {**zg["einladung"], "status": "angesehen"}
    return {"ausschreibung": await _detail(user, zg)}


@router.put("/api/ausschreibungen/{ausschreibung_id}")
async def ausschreibung_aendern(ausschreibung_id: str, body: AusschreibungIn, user: dict = Depends(schreibend("mitarbeiter"))):
    zg = await ausschreibung_zugang(user, ausschreibung_id)
    leitung_noetig(zg)
    a = zg["ausschreibung"]
    if a.get("status") in ("vergeben", "aufgehoben"):
        raise HTTPException(400, "Vergebene oder aufgehobene Ausschreibungen lassen sich nicht mehr ändern.")
    daten = body.model_dump()
    neu = {k: daten[k] for k in AUSSCHREIBUNG_FELDER}
    if a.get("status") != "entwurf" and neu["angebotsfrist"] and neu["angebotsfrist"] < heute():
        raise HTTPException(400, "Die Angebotsfrist einer veröffentlichten Ausschreibung kann nicht in die Vergangenheit gelegt werden.")
    if body.verantwortlich_user_id and body.verantwortlich_user_id != a.get("verantwortlich_user_id"):
        v = await db().users.find_one({"id": body.verantwortlich_user_id, "firma_id": user["firma_id"], "active": {"$ne": False}}, {"_id": 0, "id": 1, "name": 1})
        if not v:
            raise HTTPException(400, "Verantwortlicher Projektleiter nicht gefunden.")
        neu["verantwortlich_user_id"], neu["verantwortlich_name"] = v["id"], v.get("name")
    geaendert = [k for k in neu if neu[k] != a.get(k)]
    if not geaendert:
        return {"ausschreibung": await _detail(user, zg)}
    neu["updated_at"] = jetzt_iso()
    await db().ausschreibungen.update_one({"id": ausschreibung_id}, {"$set": neu, "$push": {"verlauf": schritt(user, "geaendert", ", ".join(geaendert), felder=geaendert)}})
    if a.get("status") in ("veroeffentlicht", "in_vergabe") and any(k != "intern" for k in geaendert):
        await _firmen_benachrichtigen(a, "ausschreibung_aktualisiert", f"Die Ausschreibung „{a['titel']}“ wurde aktualisiert ({', '.join(k for k in geaendert if k != 'intern')}).")
    await protokollieren(user, "ausschreibung.geaendert", a["titel"], details={"felder": geaendert})
    zg["ausschreibung"] = {**a, **neu, "verlauf": a.get("verlauf", []) + [schritt(user, "geaendert", "", felder=geaendert)]}
    return {"ausschreibung": await _detail(user, zg)}


@router.delete("/api/ausschreibungen/{ausschreibung_id}")
async def ausschreibung_loeschen(ausschreibung_id: str, user: dict = Depends(schreibend("mitarbeiter"))):
    zg = await ausschreibung_zugang(user, ausschreibung_id)
    leitung_noetig(zg)
    if zg["ausschreibung"].get("status") != "entwurf":
        raise HTTPException(400, "Nur Entwürfe lassen sich löschen – veröffentlichte Ausschreibungen bitte aufheben.")
    await db().ausschreibungen.delete_one({"id": ausschreibung_id})
    await db().ausschreibung_einladungen.delete_many({"ausschreibung_id": ausschreibung_id})
    await protokollieren(user, "ausschreibung.geloescht", zg["ausschreibung"]["titel"])
    return {"ok": True}


@router.post("/api/ausschreibungen/{ausschreibung_id}/veroeffentlichen")
async def veroeffentlichen(ausschreibung_id: str, user: dict = Depends(schreibend("mitarbeiter"))):
    zg = await ausschreibung_zugang(user, ausschreibung_id)
    leitung_noetig(zg)
    a = zg["ausschreibung"]
    if a.get("status") != "entwurf":
        raise HTTPException(400, "Diese Ausschreibung ist bereits veröffentlicht.")
    fehler = []
    if not (a.get("titel") or "").strip():
        fehler.append("Titel")
    if not (a.get("gewerk") or "").strip():
        fehler.append("Gewerk")
    if not a.get("angebotsfrist"):
        fehler.append("Angebotsfrist")
    elif a["angebotsfrist"] < heute():
        fehler.append("Angebotsfrist liegt in der Vergangenheit")
    if not ((a.get("beschreibung") or "").strip() or (a.get("leistungsumfang") or "").strip()):
        fehler.append("Beschreibung oder Leistungsumfang")
    if fehler:
        raise HTTPException(400, "Vor der Veröffentlichung fehlt: " + ", ".join(fehler) + ".")
    await _auftraggeber_noetig(user)
    aenderung = {"status": "veroeffentlicht", "veroeffentlicht_am": heute(), "updated_at": jetzt_iso()}
    await db().ausschreibungen.update_one({"id": ausschreibung_id}, {"$set": aenderung, "$push": {"verlauf": schritt(user, "veroeffentlicht", SICHTBARKEIT_NAMEN.get(a.get("sichtbarkeit"), ""))}})
    a = {**a, **aenderung}
    await gu_abo_aktivieren(user, zg["zugang"]["projekt"], f"Ausschreibung „{a['titel']}“ veröffentlicht")   # ab jetzt kostenpflichtiges GU-Projekt
    ag = await firma_kurz(a["firma_id"])
    eingeladen = set()
    async for e in db().ausschreibung_einladungen.find({"ausschreibung_id": ausschreibung_id}, {"_id": 0, "firma_id": 1}):
        eingeladen.add(e["firma_id"])
        await benachrichtigen(e["firma_id"], "ausschreibung_einladung", f"{ag['name']} lädt euch zur Ausschreibung „{a['titel']}“ ein (Angebotsfrist {a['angebotsfrist']}).", _link(ausschreibung_id))
        await mail.firma_informieren(e["firma_id"], f"Einladung zur Ausschreibung: {a['titel']}", f"{ag['name']} lädt euch zur Ausschreibung „{a['titel']}“ ein (Angebotsfrist {a['angebotsfrist']}).\n\nZur Ausschreibung: {mail.link(_link(ausschreibung_id))}",
                                     "ausschreibung_einladung", ausschreibung_id, a["project_id"], absender_firma_id=user["firma_id"])
    if a.get("sichtbarkeit") in ("oeffentlich", "kombiniert"):
        p = await db().projects.find_one({"id": a["project_id"]}, {"_id": 0, "address": 1})
        for fid in await interessierte_firmen({**a, "_projekt_adresse": (p or {}).get("address") or ""}):
            if fid not in eingeladen:
                await benachrichtigen(fid, "ausschreibung_neu", f"Neue passende Ausschreibung: „{a['titel']}“ ({a.get('gewerk')}) von {ag['name']} – Angebotsfrist {a['angebotsfrist']}.", _link(ausschreibung_id))
    await protokollieren(user, "ausschreibung.veroeffentlicht", a["titel"], details={"sichtbarkeit": a.get("sichtbarkeit"), "eingeladen": len(eingeladen)})
    return {"ausschreibung": await _detail(user, {**zg, "ausschreibung": a})}


@router.post("/api/ausschreibungen/{ausschreibung_id}/aufheben")
async def aufheben(ausschreibung_id: str, body: VergabeMitteilungIn, user: dict = Depends(schreibend("mitarbeiter"))):
    zg = await ausschreibung_zugang(user, ausschreibung_id)
    leitung_noetig(zg)
    a = zg["ausschreibung"]
    if a.get("status") in ("vergeben", "aufgehoben"):
        raise HTTPException(400, "Diese Ausschreibung ist bereits abgeschlossen.")
    await db().ausschreibungen.update_one({"id": ausschreibung_id}, {"$set": {"status": "aufgehoben", "updated_at": jetzt_iso()}, "$push": {"verlauf": schritt(user, "aufgehoben", body.nachricht or "")}})
    await db().vergaben.update_many({"ausschreibung_id": ausschreibung_id, "status": {"$in": ["vorgeschlagen", "freigegeben", "mitgeteilt"]}},
                                    {"$set": {"status": "zurueckgezogen"}, "$push": {"verlauf": vergabe_schritt(user, "zurueckgezogen", "Ausschreibung aufgehoben")}})
    await _firmen_benachrichtigen(a, "ausschreibung_aufgehoben", f"Die Ausschreibung „{a['titel']}“ wurde aufgehoben.{(' ' + body.nachricht) if body.nachricht else ''}")
    await protokollieren(user, "ausschreibung.aufgehoben", a["titel"], details={"grund": body.nachricht or ""})
    return {"ok": True}


# ---------------------------------------------------------------- Einladungen

@router.post("/api/ausschreibungen/{ausschreibung_id}/einladungen")
async def firmen_einladen(ausschreibung_id: str, body: AusschreibungEinladungIn, user: dict = Depends(schreibend("mitarbeiter"))):
    zg = await ausschreibung_zugang(user, ausschreibung_id)
    leitung_noetig(zg)
    await _auftraggeber_noetig(user)
    a = zg["ausschreibung"]
    if a.get("status") in ("vergeben", "aufgehoben"):
        raise HTTPException(400, "Diese Ausschreibung ist abgeschlossen.")
    ag = await firma_kurz(a["firma_id"])
    neu, uebersprungen = [], []
    for fid in dict.fromkeys(body.firma_ids):
        if fid == user["firma_id"]:
            uebersprungen.append({"firma_id": fid, "grund": "eigene Firma"})
            continue
        f = await db().firmen.find_one({"id": fid}, {"_id": 0, "id": 1, "name": 1})
        if not f:
            uebersprungen.append({"firma_id": fid, "grund": "nicht gefunden"})
            continue
        if await einladung_der_firma(ausschreibung_id, fid):
            uebersprungen.append({"firma_id": fid, "name": f["name"], "grund": "bereits eingeladen"})
            continue
        e = {"id": neue_id(), "ausschreibung_id": ausschreibung_id, "project_id": a["project_id"], "owner_firma_id": a["firma_id"], "firma_id": fid, "firma_name": f["name"],
             "nachricht": (body.nachricht or "").strip(), "status": "eingeladen", "eingeladen_von": user.get("name"), "created_at": jetzt_iso()}
        await db().ausschreibung_einladungen.insert_one(dict(e))
        neu.append(e)
        if a.get("status") in ("veroeffentlicht", "in_vergabe"):
            await benachrichtigen(fid, "ausschreibung_einladung", f"{ag['name']} lädt euch zur Ausschreibung „{a['titel']}“ ein (Angebotsfrist {a.get('angebotsfrist')}).", _link(ausschreibung_id))
            await mail.firma_informieren(fid, f"Einladung zur Ausschreibung: {a['titel']}", f"{ag['name']} lädt euch zur Ausschreibung „{a['titel']}“ ein (Angebotsfrist {a.get('angebotsfrist')}).{(' Nachricht: ' + e['nachricht']) if e.get('nachricht') else ''}\n\nZur Ausschreibung: {mail.link(_link(ausschreibung_id))}",
                                         "ausschreibung_einladung", ausschreibung_id, a["project_id"], absender_firma_id=user["firma_id"])
    if neu:
        await db().ausschreibungen.update_one({"id": ausschreibung_id}, {"$push": {"verlauf": schritt(user, "eingeladen", ", ".join(e["firma_name"] for e in neu))}})
        await protokollieren(user, "ausschreibung.eingeladen", a["titel"], details={"firmen": [e["firma_name"] for e in neu]})
        await gu_abo_aktivieren(user, zg["zugang"]["projekt"], f"Firmen zur Ausschreibung „{a['titel']}“ eingeladen")   # ab jetzt kostenpflichtiges GU-Projekt
    return {"einladungen": neu, "uebersprungen": uebersprungen}


@router.delete("/api/ausschreibungen/{ausschreibung_id}/einladungen/{einladung_id}")
async def einladung_entfernen(ausschreibung_id: str, einladung_id: str, user: dict = Depends(schreibend("mitarbeiter"))):
    zg = await ausschreibung_zugang(user, ausschreibung_id)
    leitung_noetig(zg)
    e = await db().ausschreibung_einladungen.find_one({"id": einladung_id, "ausschreibung_id": ausschreibung_id}, {"_id": 0})
    if not e:
        raise HTTPException(404, "Einladung nicht gefunden.")
    await db().ausschreibung_einladungen.delete_one({"id": einladung_id})
    await db().ausschreibungen.update_one({"id": ausschreibung_id}, {"$push": {"verlauf": schritt(user, "einladung_entfernt", e.get("firma_name", ""))}})
    return {"ok": True}


# ---------------------------------------------------------------- Unterlagen und Leistungsverzeichnis

@router.post("/api/ausschreibungen/{ausschreibung_id}/dokumente")
async def unterlage_hochladen(ausschreibung_id: str, datei: UploadFile = File(...), kategorie: str = Form("Sonstiges"), note: str = Form(""), ordner: str = Form(""),
                              ersetzt_id: str = Form(""), user: dict = Depends(schreibend("mitarbeiter"))):
    zg = await ausschreibung_zugang(user, ausschreibung_id)
    leitung_noetig(zg)
    a = zg["ausschreibung"]
    meta = await datei_speichern(user["firma_id"], datei, user["id"])
    doc = {**meta, "firma_id": user["firma_id"], "scope": "ausschreibung", "ref_id": ausschreibung_id, "project_id": a["project_id"],
           "category": kategorie if kategorie in KATEGORIEN_AUSSCHREIBUNG else "Sonstiges", "note": note[:500], "ordner": ordner.strip()[:120],
           "uploaded_by": user["id"], "uploaded_by_name": user.get("name"), "created_at": jetzt_iso()}
    doc = await version_verknuepfen(doc, ersetzt_id.strip() or None, user["firma_id"])
    await db().documents.insert_one(dict(doc))
    await db().ausschreibungen.update_one({"id": ausschreibung_id}, {"$push": {"verlauf": schritt(user, "dokument", f"{doc['filename']} (v{doc['version']})")}})
    if a.get("status") in ("veroeffentlicht", "in_vergabe"):
        await _firmen_benachrichtigen(a, "ausschreibung_dokument", f"Neues Dokument zur Ausschreibung „{a['titel']}“: {doc['filename']}")
    doc.pop("path", None)
    return {"dokument": doc}


@router.get("/api/ausschreibungen/{ausschreibung_id}/positionen.csv")
async def positionen_csv(ausschreibung_id: str, user: dict = Depends(aktueller_nutzer)):
    zg = await ausschreibung_zugang(user, ausschreibung_id)
    a = zg["ausschreibung"]
    return _datei(_csv_schreiben(a.get("positionen") or []).encode("utf-8"), f"LV-{a.get('nummer')}.csv", "text/csv; charset=utf-8")


@router.post("/api/ausschreibungen/{ausschreibung_id}/positionen/import")
async def positionen_import(ausschreibung_id: str, body: PositionenTextIn, user: dict = Depends(schreibend("mitarbeiter"))):
    zg = await ausschreibung_zugang(user, ausschreibung_id)
    leitung_noetig(zg)
    a = zg["ausschreibung"]
    if a.get("status") in ("vergeben", "aufgehoben"):
        raise HTTPException(400, "Diese Ausschreibung ist abgeschlossen.")
    positionen = _csv_lesen(body.csv)
    await db().ausschreibungen.update_one({"id": ausschreibung_id}, {"$set": {"positionen": positionen, "updated_at": jetzt_iso()}, "$push": {"verlauf": schritt(user, "positionen_import", f"{len(positionen)} Positionen")}})
    if a.get("status") in ("veroeffentlicht", "in_vergabe"):
        await _firmen_benachrichtigen(a, "ausschreibung_aktualisiert", f"Das Leistungsverzeichnis der Ausschreibung „{a['titel']}“ wurde aktualisiert.")
    return {"positionen": positionen}


@router.post("/api/ausschreibungen/{ausschreibung_id}/positionen/gaeb")
async def positionen_gaeb(ausschreibung_id: str, datei: UploadFile = File(...), user: dict = Depends(schreibend("mitarbeiter"))):
    zg = await ausschreibung_zugang(user, ausschreibung_id)
    leitung_noetig(zg)
    inhalt = await datei.read()
    try:
        positionen = gaeb.lesen(inhalt, datei.filename or "")
    except gaeb.GaebNichtUnterstuetzt as exc:
        raise HTTPException(501, str(exc))
    await db().ausschreibungen.update_one({"id": ausschreibung_id}, {"$set": {"positionen": positionen, "updated_at": jetzt_iso()}})
    return {"positionen": positionen}


# ---------------------------------------------------------------- Rückfragen

@router.post("/api/ausschreibungen/{ausschreibung_id}/fragen")
async def frage_stellen(ausschreibung_id: str, body: FrageIn, user: dict = Depends(schreibend("buero"))):
    zg = await ausschreibung_zugang(user, ausschreibung_id)
    a = zg["ausschreibung"]
    if zg["rolle"] != "bieter":
        raise HTTPException(400, "Rückfragen stellen Bieter; die Projektleitung antwortet.")
    if a.get("status") != "veroeffentlicht":
        raise HTTPException(400, "Rückfragen sind nur zu veröffentlichten Ausschreibungen möglich.")
    f = await firma_kurz(user["firma_id"])
    frage = {"id": neue_id(), "ausschreibung_id": ausschreibung_id, "owner_firma_id": a["firma_id"], "firma_id": user["firma_id"], "firma_name": f["name"], "user_name": user.get("name"),
             "text": body.text.strip(), "position_nr": (body.position_nr or "").strip(), "antwort": None, "beantwortet_von": None, "beantwortet_at": None, "oeffentlich": False,
             "created_at": jetzt_iso()}
    await db().ausschreibung_fragen.insert_one(dict(frage))
    await leitung_benachrichtigen(a, "rueckfrage_neu", f"Rückfrage von {f['name']} zur Ausschreibung „{a['titel']}“{(' (Position ' + frage['position_nr'] + ')') if frage['position_nr'] else ''}.")
    return {"frage": frage}


@router.post("/api/fragen/{frage_id}/antwort")
async def frage_beantworten(frage_id: str, body: AntwortIn, user: dict = Depends(schreibend("mitarbeiter"))):
    frage = await db().ausschreibung_fragen.find_one({"id": frage_id}, {"_id": 0})
    if not frage:
        raise HTTPException(404, "Rückfrage nicht gefunden.")
    zg = await ausschreibung_zugang(user, frage["ausschreibung_id"])
    leitung_noetig(zg)
    a = zg["ausschreibung"]
    aenderung = {"antwort": body.antwort.strip(), "beantwortet_von": user.get("name"), "beantwortet_at": jetzt_iso(), "oeffentlich": bool(body.oeffentlich)}
    await db().ausschreibung_fragen.update_one({"id": frage_id}, {"$set": aenderung})
    await benachrichtigen(frage["firma_id"], "rueckfrage_antwort", f"Antwort auf eure Rückfrage zur Ausschreibung „{a['titel']}“.", _link(a["id"]))
    if body.oeffentlich:
        ids = set()
        async for e in db().ausschreibung_einladungen.find({"ausschreibung_id": a["id"]}, {"_id": 0, "firma_id": 1}):
            ids.add(e["firma_id"])
        async for g in db().angebote.find({"ausschreibung_id": a["id"]}, {"_id": 0, "firma_id": 1}):
            ids.add(g["firma_id"])
        for fid in ids - {frage["firma_id"]}:
            await benachrichtigen(fid, "rueckfrage_antwort", f"Neue Antwort für alle Bieter zur Ausschreibung „{a['titel']}“.", _link(a["id"]))
    await protokollieren(user, "ausschreibung.rueckfrage_beantwortet", a["titel"], details={"oeffentlich": bool(body.oeffentlich)})
    return {"frage": {**frage, **aenderung}}


# ================================================================ Angebote (Bieterseite)

def _angebot_pruefen(a: dict, g: dict) -> None:
    art = g.get("preisart") or "pauschal"
    if art == "pauschal" and not (g.get("preis_netto") or 0) > 0:
        raise HTTPException(400, "Bitte einen Angebotspreis (netto) eintragen.")
    if art == "stunden" and not (g.get("stundensatz") or 0) > 0:
        raise HTTPException(400, "Bitte einen Stundensatz eintragen.")
    if art == "einheitspreise":
        if not a.get("positionen"):
            raise HTTPException(400, "Diese Ausschreibung hat kein Leistungsverzeichnis – bitte Pauschalpreis oder Stunden wählen.")
        b = positionen_berechnen(a, g)
        if not b["vollstaendig"]:
            raise HTTPException(400, f"Für folgende Positionen fehlt der Einzelpreis: {', '.join(b['fehlend'][:20])}.")


def _nachreichung_offen(g: dict) -> bool:
    return g.get("status") == "rueckfrage" and bool(g.get("nachreichen_bis")) and g["nachreichen_bis"] >= heute()


async def _angebot_speichern(user: dict, zg: dict, body: AngebotIn, vorhanden: Optional[dict]) -> dict:
    a = zg["ausschreibung"]
    if a.get("status") != "veroeffentlicht":
        raise HTTPException(400, "Angebote sind nur zu veröffentlichten Ausschreibungen möglich.")
    if vorhanden and vorhanden.get("status") not in ("entwurf", "rueckfrage", "zurueckgezogen"):
        raise HTTPException(409, "Euer Angebot ist bereits eingereicht. Änderungen sind nur nach einer Rückfrage des Auftraggebers möglich.")
    if not frist_offen(a) and not (vorhanden and _nachreichung_offen(vorhanden)):
        raise HTTPException(400, "Die Angebotsfrist ist abgelaufen.")
    daten = body.model_dump()
    nrn = {p["nr"] for p in a.get("positionen") or []}
    daten["positionen"] = [p for p in daten["positionen"] if p["nr"] in nrn]
    f = await firma_kurz(user["firma_id"])
    if vorhanden:
        aenderung = {**{k: daten[k] for k in ANGEBOT_FELDER}, "updated_at": jetzt_iso()}
        if vorhanden.get("status") == "zurueckgezogen":
            aenderung["status"] = "entwurf"
        if not aenderung.get("nummer"):
            aenderung["nummer"] = vorhanden.get("nummer")
        await db().angebote.update_one({"id": vorhanden["id"]}, {"$set": aenderung, "$push": {"verlauf": schritt(user, "bearbeitet")}})
        return {**vorhanden, **aenderung}
    g = {"id": neue_id(), "ausschreibung_id": a["id"], "project_id": a["project_id"], "owner_firma_id": a["firma_id"], "firma_id": user["firma_id"], "firma_name": f["name"],
         **{k: daten[k] for k in ANGEBOT_FELDER}, "status": "entwurf", "version": 0, "versionen": [], "eingereicht_at": None, "nachreichen_bis": None,
         "verlauf": [schritt(user, "angelegt")], "created_at": jetzt_iso(), "updated_at": jetzt_iso()}
    if not g["nummer"]:
        g["nummer"] = await nummer_vergeben(user["firma_id"], "angebote", "AN")
    await db().angebote.insert_one(dict(g))
    return g


@router.post("/api/ausschreibungen/{ausschreibung_id}/angebot")
async def angebot_anlegen(ausschreibung_id: str, body: AngebotIn, user: dict = Depends(schreibend("buero"))):
    zg = await ausschreibung_zugang(user, ausschreibung_id)
    if zg["rolle"] != "bieter":
        raise HTTPException(400, "Die ausschreibende Firma kann kein eigenes Angebot abgeben.")
    g = await _angebot_speichern(user, zg, body, zg.get("angebot"))
    return {"angebot": await angebot_anreichern(g, zg["ausschreibung"], False)}


@router.get("/api/angebote/{angebot_id}")
async def angebot_lesen(angebot_id: str, user: dict = Depends(aktueller_nutzer)):
    g, zg = await angebot_zugang(user, angebot_id)
    return {"angebot": await angebot_anreichern(g, zg["ausschreibung"], zg["rolle"] == "leitung"), "ausschreibung": await _karte(zg["ausschreibung"], user)}


@router.put("/api/angebote/{angebot_id}")
async def angebot_aendern(angebot_id: str, body: AngebotIn, user: dict = Depends(schreibend("buero"))):
    g, zg = await angebot_zugang(user, angebot_id)
    if zg["rolle"] != "bieter":
        raise HTTPException(403, "Angebote ändert nur die bietende Firma.")
    g = await _angebot_speichern(user, zg, body, g)
    return {"angebot": await angebot_anreichern(g, zg["ausschreibung"], False)}


@router.post("/api/angebote/{angebot_id}/einreichen")
async def angebot_einreichen(angebot_id: str, user: dict = Depends(schreibend("buero"))):
    g, zg = await angebot_zugang(user, angebot_id)
    a = zg["ausschreibung"]
    if zg["rolle"] != "bieter":
        raise HTTPException(403, "Einreichen kann nur die bietende Firma.")
    if a.get("status") != "veroeffentlicht":
        raise HTTPException(400, "Die Ausschreibung nimmt keine Angebote mehr an.")
    if g.get("status") not in ("entwurf", "rueckfrage", "zurueckgezogen"):
        raise HTTPException(409, "Dieses Angebot ist bereits eingereicht.")
    if not frist_offen(a) and not _nachreichung_offen(g):
        raise HTTPException(400, "Die Angebotsfrist ist abgelaufen – eine Einreichung ist nicht mehr möglich.")
    _angebot_pruefen(a, g)
    version = int(g.get("version") or 0) + 1
    snapshot = {"version": version, "eingereicht_at": jetzt_iso(), "summe_netto": angebot_summe(a, g), "daten": {k: g.get(k) for k in ANGEBOT_FELDER},
                "dokumente": [d["id"] for d in await _dokumente("angebot", g["id"])]}
    status = "ueberarbeitet" if g.get("version") else "eingereicht"
    aenderung = {"status": status, "version": version, "eingereicht_at": snapshot["eingereicht_at"], "nachreichen_bis": None, "updated_at": jetzt_iso()}
    await db().angebote.update_one({"id": angebot_id}, {"$set": aenderung, "$push": {"versionen": snapshot, "verlauf": schritt(user, status, f"Version {version}")}})
    await db().ausschreibung_einladungen.update_one({"ausschreibung_id": a["id"], "firma_id": user["firma_id"]}, {"$set": {"status": "angebot"}})
    f = await firma_kurz(user["firma_id"])
    await leitung_benachrichtigen(a, "angebot_eingereicht", f"{f['name']} hat ein Angebot zur Ausschreibung „{a['titel']}“ {'überarbeitet ' if status == 'ueberarbeitet' else ''}eingereicht ({snapshot['summe_netto']:.2f} € netto).")
    await benachrichtigen(user["firma_id"], "angebot_bestaetigung", f"Euer Angebot zur Ausschreibung „{a['titel']}“ wurde eingereicht (Version {version}).", _link(a["id"]))
    summe_text = f"{snapshot['summe_netto']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    await mail.firma_informieren(user["firma_id"], f"Einreichungsnachweis: Angebot zu „{a['titel']}“",
                                 f"Euer Angebot zur Ausschreibung „{a['titel']}“ von {(await auftraggeber_info(a)).get('name') or 'Auftraggeber'} wurde am {snapshot['eingereicht_at'][:16].replace('T', ' ')} eingereicht.\nVersion {version} · Summe {summe_text} € netto\n\nZum Angebot: {mail.link(_link(a['id']))}",
                                 "angebot_nachweis", g["id"], a["project_id"])
    await mail.firma_informieren(a["firma_id"], f"Neues Angebot zu „{a['titel']}“",
                                 f"{f['name']} hat ein Angebot zur Ausschreibung „{a['titel']}“ {'überarbeitet ' if status == 'ueberarbeitet' else ''}eingereicht ({summe_text} € netto).\n\nZur Ausschreibung: {mail.link(_link(a['id']))}",
                                 "angebot_eingegangen", g["id"], a["project_id"], absender_firma_id=user["firma_id"])
    await protokollieren(user, "angebot.eingereicht", a["titel"], details={"version": version, "summe_netto": snapshot["summe_netto"]})
    return {"angebot": await angebot_anreichern({**g, **aenderung}, a, False)}


@router.post("/api/angebote/{angebot_id}/zurueckziehen")
async def angebot_zurueckziehen(angebot_id: str, body: VergabeMitteilungIn, user: dict = Depends(schreibend("buero"))):
    g, zg = await angebot_zugang(user, angebot_id)
    a = zg["ausschreibung"]
    if zg["rolle"] != "bieter":
        raise HTTPException(403, "Zurückziehen kann nur die bietende Firma.")
    if g.get("status") in ("angenommen",):
        raise HTTPException(400, "Ein angenommenes Angebot kann nicht mehr zurückgezogen werden.")
    if g.get("status") in ("entwurf", "zurueckgezogen", "abgelehnt"):
        raise HTTPException(400, "Dieses Angebot ist nicht eingereicht.")
    await db().angebote.update_one({"id": angebot_id}, {"$set": {"status": "zurueckgezogen", "updated_at": jetzt_iso()}, "$push": {"verlauf": schritt(user, "zurueckgezogen", body.nachricht or "")}})
    f = await firma_kurz(user["firma_id"])
    await leitung_benachrichtigen(a, "angebot_zurueckgezogen", f"{f['name']} hat das Angebot zur Ausschreibung „{a['titel']}“ zurückgezogen.")
    await protokollieren(user, "angebot.zurueckgezogen", a["titel"], details={"grund": body.nachricht or ""})
    return {"ok": True}


@router.post("/api/angebote/{angebot_id}/dokumente")
async def angebot_dokument(angebot_id: str, datei: UploadFile = File(...), kategorie: str = Form("Sonstiges"), note: str = Form(""), user: dict = Depends(schreibend("buero"))):
    g, zg = await angebot_zugang(user, angebot_id)
    a = zg["ausschreibung"]
    if zg["rolle"] != "bieter":
        raise HTTPException(403, "Anhänge fügt nur die bietende Firma hinzu.")
    if not (g.get("status") in ("entwurf", "rueckfrage", "zurueckgezogen") or frist_offen(a)):
        raise HTTPException(400, "Nach Einreichung und Fristende sind keine weiteren Anhänge möglich.")
    meta = await datei_speichern(user["firma_id"], datei, user["id"])
    doc = {**meta, "firma_id": user["firma_id"], "scope": "angebot", "ref_id": angebot_id, "project_id": a["project_id"], "category": kategorie if kategorie in KATEGORIEN_ANGEBOT else "Sonstiges",
           "note": note[:500], "version": 1, "aktuell": True, "uploaded_by": user["id"], "uploaded_by_name": user.get("name"), "created_at": jetzt_iso()}
    await db().documents.insert_one(dict(doc))
    await db().angebote.update_one({"id": angebot_id}, {"$push": {"verlauf": schritt(user, "dokument", doc["filename"])}})
    doc.pop("path", None)
    return {"dokument": doc}


@router.get("/api/angebote/{angebot_id}/positionen.csv")
async def angebot_positionen_csv(angebot_id: str, user: dict = Depends(aktueller_nutzer)):
    g, zg = await angebot_zugang(user, angebot_id)
    a = zg["ausschreibung"]
    b = positionen_berechnen(a, g)
    return _datei(_csv_schreiben(a.get("positionen") or [], {z["nr"]: z for z in b["zeilen"]}).encode("utf-8"), f"Angebot-{g.get('nummer')}.csv", "text/csv; charset=utf-8")


# ================================================================ Angebote (Eigentümerseite): Übersicht, Prüfung, Bewertung, Vergleich

@router.get("/api/ausschreibungen/{ausschreibung_id}/angebote")
async def angebote_liste(ausschreibung_id: str, user: dict = Depends(aktueller_nutzer)):
    zg = await ausschreibung_zugang(user, ausschreibung_id)
    leitung_noetig(zg)
    a = zg["ausschreibung"]
    angebote = []
    async for g in db().angebote.find({"ausschreibung_id": ausschreibung_id, "status": {"$in": list(EINGEREICHT)}}, {"_id": 0}).sort("eingereicht_at", 1):
        angebote.append(await angebot_anreichern(g, a, True))
    vergleich = []
    for g in angebote:
        bew = g.get("bewertung") or {}
        punkte = bew.get("kriterien") or {}
        vergleich.append({"angebot_id": g["id"], "firma_name": g["firma"]["name"], "firma_ort": g["firma"].get("city"), "status": g["status"], "status_name": g["status_name"],
                          "version": g.get("version"), "eingereicht_at": g.get("eingereicht_at"), "preisart": g.get("preisart"), "summe_netto": g["summe_netto"], "summe_brutto": g["summe_brutto"],
                          "ausfuehrung_von": g.get("ausfuehrung_von"), "ausfuehrung_bis": g.get("ausfuehrung_bis"), "verfuegbarkeit": g.get("verfuegbarkeit"), "kapazitaet": g.get("kapazitaet"),
                          "gueltig_bis": g.get("gueltig_bis"), "dokumente": len(g.get("dokumente") or []), "positionen_vollstaendig": (g.get("berechnung") or {}).get("vollstaendig") if g.get("berechnung") else None,
                          "bewertung_punkte": sum(punkte.values()) if punkte else None, "bewertung_max": 5 * len(punkte) if punkte else None,
                          "mindestanforderungen": bew.get("mindestanforderungen_erfuellt"), "kriterien": punkte})
    vergleich.sort(key=lambda x: (x["summe_netto"] or 0))
    preise = [x["summe_netto"] for x in vergleich if x["summe_netto"]]
    return {"angebote": angebote, "vergleich": vergleich, "kriterien": list(BEWERTUNGSKRITERIEN),
            "guenstigstes": min(preise) if preise else None, "teuerstes": max(preise) if preise else None,
            "hinweis": "Die Vergabe entscheidet die verantwortliche Projektleitung. Die Punkte sind eine Hilfe für den Vergleich, keine automatische Entscheidung."}


@router.post("/api/angebote/{angebot_id}/pruefung")
async def angebot_pruefung(angebot_id: str, body: AngebotPruefungIn, user: dict = Depends(schreibend("mitarbeiter"))):
    g, zg = await angebot_zugang(user, angebot_id)
    if zg["rolle"] != "leitung":
        raise HTTPException(403, "Das darf nur die Projektleitung der ausschreibenden Firma.")
    a = zg["ausschreibung"]
    if g.get("status") in ("angenommen", "abgelehnt", "zurueckgezogen"):
        raise HTTPException(400, "Dieses Angebot ist bereits abschließend entschieden.")
    aenderung = {"status": body.status, "updated_at": jetzt_iso()}
    if body.status == "rueckfrage":
        aenderung["nachreichen_bis"] = body.nachreichen_bis or (date.fromisoformat(heute()) + timedelta(days=NACHFRIST_TAGE)).isoformat()
        text = f"Rückfrage/Nachforderung zu eurem Angebot für „{a['titel']}“ – Nachreichung bis {aenderung['nachreichen_bis']}.{(' ' + body.nachricht) if body.nachricht else ''}"
        art = "angebot_nachforderung"
    elif body.status == "in_pruefung":
        text = f"Euer Angebot zur Ausschreibung „{a['titel']}“ wurde zur Prüfung geöffnet."
        art = "angebot_in_pruefung"
    else:
        text = f"Entscheidung zur Ausschreibung „{a['titel']}“: Euer Angebot wurde nicht berücksichtigt.{(' ' + body.nachricht) if body.nachricht else ''}"
        art = "angebot_entscheidung"
    await db().angebote.update_one({"id": angebot_id}, {"$set": aenderung, "$push": {"verlauf": schritt(user, body.status, body.nachricht or "")}})
    await benachrichtigen(g["firma_id"], art, text, _link(a["id"]))
    await protokollieren(user, f"angebot.{body.status}", a["titel"], details={"firma": g.get("firma_name"), "nachricht": body.nachricht or ""})
    return {"angebot": await angebot_anreichern({**g, **aenderung}, a, True)}


@router.put("/api/angebote/{angebot_id}/bewertung")
async def angebot_bewerten(angebot_id: str, body: BewertungIn, user: dict = Depends(schreibend("mitarbeiter"))):
    g, zg = await angebot_zugang(user, angebot_id)
    if zg["rolle"] != "leitung":
        raise HTTPException(403, "Bewerten darf nur die Projektleitung der ausschreibenden Firma.")
    bewertung = {"kriterien": body.kriterien, "notiz": (body.notiz or "").strip(), "mindestanforderungen_erfuellt": body.mindestanforderungen_erfuellt,
                 "bewertet_von": user.get("name"), "bewertet_von_id": user["id"], "at": jetzt_iso()}
    await db().angebote.update_one({"id": angebot_id}, {"$set": {"bewertung": bewertung}, "$push": {"verlauf": schritt(user, "bewertet", f"{sum(body.kriterien.values())} Punkte")}})
    await protokollieren(user, "angebot.bewertet", zg["ausschreibung"]["titel"], details={"firma": g.get("firma_name"), "punkte": sum(body.kriterien.values())})
    return {"bewertung": bewertung}


# ================================================================ Vergabe

@router.post("/api/ausschreibungen/{ausschreibung_id}/vergabe")
async def vergabe_vorschlagen(ausschreibung_id: str, body: VergabeVorschlagIn, user: dict = Depends(schreibend("mitarbeiter"))):
    zg = await ausschreibung_zugang(user, ausschreibung_id)
    leitung_noetig(zg)
    a = zg["ausschreibung"]
    if a.get("status") not in ("veroeffentlicht", "in_vergabe"):
        raise HTTPException(400, "Diese Ausschreibung ist nicht in der Vergabe.")
    g = await db().angebote.find_one({"id": body.angebot_id, "ausschreibung_id": ausschreibung_id}, {"_id": 0})
    if not g or g.get("status") not in ("eingereicht", "in_pruefung", "ueberarbeitet", "rueckfrage"):
        raise HTTPException(400, "Nur ein eingereichtes, nicht abgelehntes Angebot kann vergeben werden.")
    await neue_vergabe_pruefen(a)
    v = {"id": neue_id(), "ausschreibung_id": ausschreibung_id, "project_id": a["project_id"], "owner_firma_id": a["firma_id"], "angebot_id": g["id"], "firma_id": g["firma_id"],
         "firma_name": g.get("firma_name"), "summe_netto": angebot_summe(a, g), "begruendung": (body.begruendung or "").strip(), "status": "vorgeschlagen",
         "vorgeschlagen_von": {"id": user["id"], "name": user.get("name")}, "freigegeben_von": None, "mitgeteilt_at": None, "antwort_at": None, "bestaetigung": None,
         "beteiligung_id": None, "lokales_project_id": None, "verlauf": [vergabe_schritt(user, "vorgeschlagen", body.begruendung or "")], "created_at": jetzt_iso()}
    await db().vergaben.insert_one(dict(v))
    await db().ausschreibungen.update_one({"id": ausschreibung_id}, {"$set": {"status": "in_vergabe", "updated_at": jetzt_iso()}, "$push": {"verlauf": schritt(user, "vergabe_vorgeschlagen", g.get("firma_name", ""))}})
    await benachrichtigen(a["firma_id"], "vergabe_freigabe", f"Vergabe „{a['titel']}“ an {g.get('firma_name')} wartet auf interne Freigabe.", _link(ausschreibung_id))
    await protokollieren(user, "vergabe.vorgeschlagen", a["titel"], details={"firma": g.get("firma_name"), "summe_netto": v["summe_netto"]})
    return {"vergabe": v}


@router.post("/api/vergaben/{vergabe_id}/freigabe")
async def vergabe_freigeben(vergabe_id: str, user: dict = Depends(schreibend("buero"))):
    """Interne Freigabe durch Büro/Inhaber der Eigentümerfirma – Vier-Augen-Prinzip, sobald es eine zweite freigabeberechtigte Person gibt."""
    v, rolle = await vergabe_zugang(user, vergabe_id)
    if rolle != "leitung" or v["owner_firma_id"] != user["firma_id"]:
        raise HTTPException(403, "Freigeben darf nur Büro oder Inhaber der ausschreibenden Firma.")
    if v.get("status") != "vorgeschlagen":
        raise HTTPException(400, "Diese Vergabe wartet nicht auf Freigabe.")
    if v["vorgeschlagen_von"]["id"] == user["id"] and await zweites_augenpaar(user["firma_id"], user["id"]):
        raise HTTPException(409, "Vier-Augen-Prinzip: Die Freigabe muss eine andere Person aus Büro/Inhaber erteilen.")
    aenderung = {"status": "freigegeben", "freigegeben_von": {"id": user["id"], "name": user.get("name"), "at": jetzt_iso()}}
    await db().vergaben.update_one({"id": vergabe_id}, {"$set": aenderung, "$push": {"verlauf": vergabe_schritt(user, "freigegeben")}})
    a = await db().ausschreibungen.find_one({"id": v["ausschreibung_id"]}, {"_id": 0, "titel": 1})
    await protokollieren(user, "vergabe.freigegeben", (a or {}).get("titel", ""), details={"firma": v.get("firma_name")})
    return {"vergabe": {**v, **aenderung}}


@router.post("/api/vergaben/{vergabe_id}/dokumente")
async def vergabe_dokument(vergabe_id: str, datei: UploadFile = File(...), kategorie: str = Form("Auftragsschreiben"), note: str = Form(""), user: dict = Depends(schreibend("mitarbeiter"))):
    v, rolle = await vergabe_zugang(user, vergabe_id)
    if rolle != "leitung":
        raise HTTPException(403, "Vertrags- und Auftragsdokumente stellt die ausschreibende Firma bereit.")
    meta = await datei_speichern(user["firma_id"], datei, user["id"])
    doc = {**meta, "firma_id": user["firma_id"], "scope": "vergabe", "ref_id": vergabe_id, "project_id": v["project_id"], "category": kategorie if kategorie in KATEGORIEN_VERGABE else "Sonstiges",
           "note": note[:500], "version": 1, "aktuell": True, "uploaded_by": user["id"], "uploaded_by_name": user.get("name"), "created_at": jetzt_iso()}
    await db().documents.insert_one(dict(doc))
    await db().vergaben.update_one({"id": vergabe_id}, {"$push": {"verlauf": vergabe_schritt(user, v["status"], f"Dokument: {doc['filename']}")}})
    if v.get("status") == "mitgeteilt":
        await benachrichtigen(v["firma_id"], "vergabe_dokument", f"Neues Vertragsdokument zur Vergabe: {doc['filename']}", _link(v["ausschreibung_id"]))
    doc.pop("path", None)
    return {"dokument": doc}


@router.post("/api/vergaben/{vergabe_id}/mitteilen")
async def vergabe_mitteilen(vergabe_id: str, body: VergabeMitteilungIn, user: dict = Depends(schreibend("mitarbeiter"))):
    v, rolle = await vergabe_zugang(user, vergabe_id)
    if rolle != "leitung":
        raise HTTPException(403, "Das darf nur die Projektleitung der ausschreibenden Firma.")
    if v.get("status") != "freigegeben":
        raise HTTPException(400, "Die Vergabe muss zuerst intern freigegeben werden.")
    a = await db().ausschreibungen.find_one({"id": v["ausschreibung_id"]}, {"_id": 0})
    aenderung = {"status": "mitgeteilt", "mitgeteilt_at": jetzt_iso(), "nachricht": (body.nachricht or "").strip()}
    await db().vergaben.update_one({"id": vergabe_id}, {"$set": aenderung, "$push": {"verlauf": vergabe_schritt(user, "mitgeteilt", body.nachricht or "")}})
    ag = await firma_kurz(v["owner_firma_id"])
    await benachrichtigen(v["firma_id"], "vergabe_erhalten", f"Vergabe erhalten: {ag['name']} beauftragt euch für „{a['titel']}“. Bitte die Auftragsannahme bestätigen.", _link(a["id"]), mindestens="buero")
    await mail.firma_informieren(v["firma_id"], f"Zuschlag: {a['titel']} – {ag['name']}", f"{ag['name']} beauftragt euch für „{a['titel']}“.{(' Nachricht: ' + aenderung['nachricht']) if aenderung.get('nachricht') else ''}\n\nBitte die Auftragsannahme in Stundenzettel Pro verbindlich bestätigen (nur Inhaber): {mail.link(_link(a['id']))}",
                                 "zuschlag", vergabe_id, a["project_id"], absender_firma_id=user["firma_id"])
    await protokollieren(user, "vergabe.mitgeteilt", a["titel"], details={"firma": v.get("firma_name")})
    return {"vergabe": {**v, **aenderung}}


@router.post("/api/vergaben/{vergabe_id}/zurueckziehen")
async def vergabe_zurueckziehen(vergabe_id: str, body: VergabeMitteilungIn, user: dict = Depends(schreibend("mitarbeiter"))):
    v, rolle = await vergabe_zugang(user, vergabe_id)
    if rolle != "leitung":
        raise HTTPException(403, "Das darf nur die Projektleitung der ausschreibenden Firma.")
    if v.get("status") not in ("vorgeschlagen", "freigegeben", "mitgeteilt"):
        raise HTTPException(400, "Diese Vergabe lässt sich nicht mehr zurückziehen.")
    a = await db().ausschreibungen.find_one({"id": v["ausschreibung_id"]}, {"_id": 0})
    await db().vergaben.update_one({"id": vergabe_id}, {"$set": {"status": "zurueckgezogen"}, "$push": {"verlauf": vergabe_schritt(user, "zurueckgezogen", body.nachricht or "")}})
    await db().ausschreibungen.update_one({"id": v["ausschreibung_id"]}, {"$set": {"status": "veroeffentlicht", "updated_at": jetzt_iso()}, "$push": {"verlauf": schritt(user, "vergabe_zurueckgezogen", v.get("firma_name", ""))}})
    if v.get("status") == "mitgeteilt":
        await benachrichtigen(v["firma_id"], "vergabe_zurueckgezogen", f"Die Vergabe für „{a['titel']}“ wurde zurückgezogen.{(' ' + body.nachricht) if body.nachricht else ''}", _link(a["id"]))
    await protokollieren(user, "vergabe.zurueckgezogen", a["titel"], details={"firma": v.get("firma_name"), "grund": body.nachricht or ""})
    return {"ok": True}


@router.get("/api/vergaben/{vergabe_id}")
async def vergabe_lesen(vergabe_id: str, user: dict = Depends(aktueller_nutzer)):
    v, rolle = await vergabe_zugang(user, vergabe_id)
    a = await db().ausschreibungen.find_one({"id": v["ausschreibung_id"]}, {"_id": 0})
    g = await db().angebote.find_one({"id": v["angebot_id"]}, {"_id": 0})
    return {"vergabe": {**v, "status_name": VERGABE_STATUS_NAMEN.get(v["status"]), "rolle": rolle, "dokumente": await _dokumente("vergabe", vergabe_id), "annahme_text": ANNAHME_TEXT,
                        "ausschreibung": await _karte(a, user) if a else None, "angebot": await angebot_anreichern(g, a, rolle == "leitung") if g and a else None,
                        "auftraggeber": await firma_kurz(v["owner_firma_id"])}}


@router.post("/api/vergaben/{vergabe_id}/antwort")
async def vergabe_antwort(vergabe_id: str, body: VergabeAntwortIn, user: dict = Depends(schreibend("buero"))):
    """Verbindliche Auftragsannahme (nur Inhaber, mit ausdrücklicher Bestätigung) oder Ablehnung durch die beauftragte Firma.
    Erst die Annahme erzeugt die Beteiligung am Projekt und das verknüpfte lokale Projekt."""
    v, rolle = await vergabe_zugang(user, vergabe_id)
    if rolle != "firma":
        raise HTTPException(403, "Antworten kann nur die beauftragte Firma.")
    if v.get("status") != "mitgeteilt":
        raise HTTPException(400, "Diese Vergabe wartet nicht auf eure Antwort.")
    a = await db().ausschreibungen.find_one({"id": v["ausschreibung_id"]}, {"_id": 0})
    if not a:
        raise HTTPException(404, "Ausschreibung nicht gefunden.")
    ag = await firma_kurz(v["owner_firma_id"])
    if not body.annehmen:
        await db().vergaben.update_one({"id": vergabe_id}, {"$set": {"status": "abgelehnt_firma", "antwort_at": jetzt_iso(), "grund": (body.grund or "").strip()}},
                                       )
        await db().vergaben.update_one({"id": vergabe_id}, {"$push": {"verlauf": vergabe_schritt(user, "abgelehnt_firma", body.grund or "")}})
        await db().angebote.update_one({"id": v["angebot_id"]}, {"$set": {"status": "zurueckgezogen", "updated_at": jetzt_iso()}, "$push": {"verlauf": schritt(user, "zurueckgezogen", "Vergabe abgelehnt")}})
        await db().ausschreibungen.update_one({"id": a["id"]}, {"$set": {"status": "veroeffentlicht", "updated_at": jetzt_iso()}, "$push": {"verlauf": schritt(user, "vergabe_abgelehnt", v.get("firma_name", ""))}})
        await leitung_benachrichtigen(a, "vergabe_abgelehnt", f"{v.get('firma_name')} hat die Vergabe für „{a['titel']}“ abgelehnt.{(' ' + body.grund) if body.grund else ''}")
        await protokollieren(user, "vergabe.abgelehnt", a["titel"], details={"auftraggeber": ag["name"], "grund": body.grund or ""})
        await protokollieren(user, "vergabe.abgelehnt_durch_firma", a["titel"], details={"firma": v.get("firma_name")}, firma_id=v["owner_firma_id"])
        return {"vergabe": {**v, "status": "abgelehnt_firma"}}
    if not hat_rolle(user, "inhaber"):
        raise HTTPException(403, "Die verbindliche Auftragsannahme darf nur der Inhaber der Firma erklären.")
    if (body.bestaetigung or "").strip().rstrip(".") != ANNAHME_TEXT or not (body.name or "").strip():
        raise HTTPException(400, f"Bitte zur Bestätigung den Satz „{ANNAHME_TEXT}“ eingeben und den Namen angeben.")
    from routes.plattform import _annehmen
    b = {"id": neue_id(), "project_id": a["project_id"], "owner_firma_id": a["firma_id"], "firma_id": user["firma_id"], "firma_name": v.get("firma_name"), "email": "",
         "gewerk": a.get("gewerk") or "", "rolle": "subunternehmer", "nachricht": f"Vergabe {a.get('nummer')}: {a['titel']}", "status": "eingeladen", "token": None, "token_bis": None,
         "eingeladen_von": ag["name"], "eingeladen_von_id": None, "lokales_project_id": None, "freigaben": {"namen": False}, "vergabe_id": vergabe_id, "created_at": jetzt_iso()}
    vorhanden = await db().beteiligungen.find_one({"project_id": a["project_id"], "firma_id": user["firma_id"], "status": "aktiv"}, {"_id": 0})
    if vorhanden:
        b = vorhanden
    else:
        await db().beteiligungen.insert_one(dict(b))
        b = await _annehmen(user, b)
    bestaetigung = {"name": body.name.strip(), "text": ANNAHME_TEXT, "user_id": user["id"], "user_name": user.get("name"), "at": jetzt_iso()}
    aenderung = {"status": "angenommen", "antwort_at": jetzt_iso(), "bestaetigung": bestaetigung, "beteiligung_id": b["id"], "lokales_project_id": b.get("lokales_project_id")}
    await db().vergaben.update_one({"id": vergabe_id}, {"$set": aenderung, "$push": {"verlauf": vergabe_schritt(user, "angenommen", f"{bestaetigung['name']}: {ANNAHME_TEXT}")}})
    await db().angebote.update_one({"id": v["angebot_id"]}, {"$set": {"status": "angenommen", "updated_at": jetzt_iso()}, "$push": {"verlauf": schritt(user, "angenommen")}})
    await db().ausschreibungen.update_one({"id": a["id"]}, {"$set": {"status": "vergeben", "vergeben_an": v.get("firma_name"), "updated_at": jetzt_iso()}, "$push": {"verlauf": schritt(user, "vergeben", v.get("firma_name", ""))}})
    async for g in db().angebote.find({"ausschreibung_id": a["id"], "id": {"$ne": v["angebot_id"]}, "status": {"$in": ["eingereicht", "in_pruefung", "rueckfrage", "ueberarbeitet"]}}, {"_id": 0}):
        await db().angebote.update_one({"id": g["id"]}, {"$set": {"status": "abgelehnt", "updated_at": jetzt_iso()}, "$push": {"verlauf": schritt(user, "abgelehnt", "Vergabe an anderen Bieter")}})
        await benachrichtigen(g["firma_id"], "absage", f"Absage: Die Ausschreibung „{a['titel']}“ von {ag['name']} wurde an einen anderen Bieter vergeben.", _link(a["id"]))
        await mail.firma_informieren(g["firma_id"], f"Absage: {a['titel']}", f"Die Ausschreibung „{a['titel']}“ von {ag['name']} wurde an einen anderen Bieter vergeben. Vielen Dank für euer Angebot.\n\nZur Ausschreibung: {mail.link(_link(a['id']))}",
                                     "absage", a["id"], a["project_id"], absender_firma_id=v["owner_firma_id"])
    await leitung_benachrichtigen(a, "vergabe_angenommen", f"{v.get('firma_name')} hat die Vergabe für „{a['titel']}“ verbindlich angenommen und ist jetzt am Projekt beteiligt.", f"/projekte/{a['project_id']}")
    await mail.firma_informieren(a["firma_id"], f"Auftrag angenommen: {a['titel']} – {v.get('firma_name')}", f"{v.get('firma_name')} hat die Vergabe für „{a['titel']}“ verbindlich angenommen ({bestaetigung['name']}, {bestaetigung['at'][:16].replace('T', ' ')}) und ist jetzt am Projekt beteiligt.\n\nZum Projekt: {mail.link('/projekte/' + a['project_id'])}",
                                 "auftrag_angenommen", vergabe_id, a["project_id"], absender_firma_id=user["firma_id"])
    await protokollieren(user, "vergabe.angenommen", a["titel"], details={"auftraggeber": ag["name"], "bestaetigt_von": bestaetigung["name"]})
    await protokollieren(user, "vergabe.angenommen_durch_firma", a["titel"], details={"firma": v.get("firma_name"), "bestaetigt_von": bestaetigung["name"]}, firma_id=v["owner_firma_id"])
    return {"vergabe": {**v, **aenderung, "status_name": VERGABE_STATUS_NAMEN["angenommen"]}, "lokales_project_id": b.get("lokales_project_id")}
