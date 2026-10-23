"""Baustellenfunktionen auf der Plattform-Ebene: Lieferungen, Mängel, Bautagesberichte (mit PDF), Meilensteine,
geteilte Projektdokumente und der Kalenderabruf. Rechte wie bei Aufgaben: Eigentümer-Projektleitung plant und nimmt ab,
die zuständige Partnerfirma (Büro/Vorarbeiter ihres verknüpften Projekts) meldet Status, Fotos und Kommentare."""
from __future__ import annotations

import io
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response

from auth import aktueller_nutzer, hat_rolle, jetzt_iso, schreibend
from dateien import bild_verkleinern, datei_speichern, version_verknuepfen
from db import db
from gemeinsam import neue_id
from models import (DokumentFreigabeIn, KommentarIn, LieferungIn, LieferungStatusIn, LieferungUpdateIn, MangelIn, MangelStatusIn, MangelUpdateIn,
                    MeilensteinIn, TagesberichtIn, TagesberichtStatusIn)
from plattform import (zuteilungs_filter, LIEFERUNG_FIRMA_STATUS, LIEFERUNG_STATUS, LIEFERUNG_STATUS_NAMEN, MANGEL_FIRMA_STATUS, MANGEL_STATUS, MANGEL_STATUS_NAMEN, OFFEN,
                       STATUS_NAMEN, benachrichtigen, eigentuemer_benachrichtigen, eintrag_laden, firma_am_projekt, firma_kurz, leitung_noetig,
                       partner_leitung, zugang)
from protokoll import protokollieren
from zeiten import datum_pruefen, lokal_jetzt, zeit_pruefen

router = APIRouter(tags=["Baustelle"])

KATEGORIEN_DOKUMENTE = ["Baupläne", "Verträge & Aufträge", "Protokolle", "Sicherheit", "Sonstiges"]


def _datei(inhalt: bytes, name: str, typ: str) -> Response:
    return Response(content=inhalt, media_type=typ, headers={"Content-Disposition": f'attachment; filename="{name}"'})


async def _fotos(scope: str, ref_id: str) -> list[dict]:
    return [d async for d in db().documents.find({"scope": scope, "ref_id": ref_id}, {"_id": 0, "path": 0}).sort("created_at", 1)]


async def _foto_speichern(user: dict, scope: str, eintrag: dict, datei: UploadFile, note: str) -> dict:
    meta = await datei_speichern(user["firma_id"], datei)
    if not meta["mime"].startswith("image/"):
        raise HTTPException(400, "Bitte ein Foto hochladen.")
    doc = {**meta, "firma_id": user["firma_id"], "scope": scope, "ref_id": eintrag["id"], "project_id": eintrag["project_id"], "category": "Fotos",
           "note": note[:500], "date": eintrag.get("datum") or eintrag.get("geplant_am") or lokal_jetzt().date().isoformat(), "uploaded_by": user["id"],
           "uploaded_by_name": user.get("name"), "created_at": jetzt_iso()}
    await db().documents.insert_one(dict(doc))
    doc.pop("path", None)
    return doc


def _schritt(user: dict, status: str, kommentar: str = "") -> dict:
    return {"status": status, "user_name": user.get("name"), "firma_id": user["firma_id"], "at": jetzt_iso(), "kommentar": (kommentar or "").strip()[:500]}


# ================================================================ Lieferungen

async def _lieferung_anreichern(l: dict) -> dict:
    l = dict(l)
    l["firma_name"] = (await firma_kurz(l.get("firma_id")))["name"]
    l["status_name"] = LIEFERUNG_STATUS_NAMEN.get(l.get("status"), l.get("status"))
    l["fotos_anzahl"] = await db().documents.count_documents({"scope": "lieferung", "ref_id": l["id"]})
    return l


@router.get("/api/projekte/{project_id}/lieferungen")
async def lieferungen_liste(project_id: str, von: Optional[str] = None, bis: Optional[str] = None, user: dict = Depends(aktueller_nutzer)):
    z = await zugang(user, project_id)
    if z["eigentuemer"] and not z["leitung"]:
        raise HTTPException(404, "Projekt nicht gefunden.")
    filt: dict = {"project_id": project_id}
    if von and bis:
        filt["geplant_am"] = {"$gte": von, "$lte": bis}
    if not z["eigentuemer"]:
        filt["firma_id"] = user["firma_id"]
    aus = [await _lieferung_anreichern(l) async for l in db().lieferungen.find(filt, {"_id": 0}).sort([("geplant_am", 1), ("zeitfenster_von", 1)]).limit(2000)]
    firmen = [{"id": z["projekt"]["firma_id"], "name": (await firma_kurz(z["projekt"]["firma_id"]))["name"], "eigentuemer": True}]
    if z["eigentuemer"]:
        async for b in db().beteiligungen.find({"project_id": project_id, "status": "aktiv"}, {"_id": 0}):
            firmen.append({"id": b["firma_id"], "name": b.get("firma_name"), "gewerk": b.get("gewerk"), "eigentuemer": False})
    return {"lieferungen": aus, "firmen": firmen, "status": LIEFERUNG_STATUS_NAMEN, "leitung": bool(z["eigentuemer"] and z["leitung"]),
            "heute": lokal_jetzt().date().isoformat()}


@router.post("/api/projekte/{project_id}/lieferungen")
async def lieferung_anlegen(project_id: str, body: LieferungIn, user: dict = Depends(schreibend("mitarbeiter"))):
    z = await zugang(user, project_id)
    leitung_noetig(z)
    daten = body.model_dump()
    datum_pruefen(daten["geplant_am"])
    for k in ("zeitfenster_von", "zeitfenster_bis"):
        if daten.get(k):
            daten[k] = zeit_pruefen(daten[k])
    firma_id, _ = await firma_am_projekt(project_id, z["projekt"], daten.get("firma_id"))
    l = {**daten, "id": neue_id(), "project_id": project_id, "owner_firma_id": z["projekt"]["firma_id"], "firma_id": firma_id, "status": "angefragt",
         "tatsaechlich_am": None, "verlauf": [_schritt(user, "angefragt")], "erstellt_von": user.get("name"), "created_at": jetzt_iso(), "updated_at": jetzt_iso()}
    await db().lieferungen.insert_one(dict(l))
    if firma_id != z["projekt"]["firma_id"]:
        await benachrichtigen(firma_id, "lieferung_neu", f"Lieferung geplant im Projekt „{z['projekt']['name']}“: {l['material']} am {l['geplant_am']}.", "/zusammenarbeit", mindestens="vorarbeiter")
    await protokollieren(user, "lieferung.angelegt", l["material"], details={"projekt": z["projekt"]["name"], "datum": l["geplant_am"]})
    return {"lieferung": await _lieferung_anreichern(l)}


@router.get("/api/lieferungen/{lieferung_id}")
async def lieferung_lesen(lieferung_id: str, user: dict = Depends(aktueller_nutzer)):
    l, z = await eintrag_laden("lieferungen", user, lieferung_id)
    leitung = z["eigentuemer"] and z["leitung"]
    firma = (not z["eigentuemer"]) and partner_leitung(z, user) and l.get("firma_id") == user["firma_id"]
    erlaubt = list(LIEFERUNG_STATUS) if leitung else sorted(LIEFERUNG_FIRMA_STATUS) if firma else []
    return {"lieferung": await _lieferung_anreichern(l), "fotos": await _fotos("lieferung", lieferung_id), "status_erlaubt": [s for s in LIEFERUNG_STATUS if s in erlaubt], "rolle": "leitung" if leitung else "firma" if firma else "lesen"}


@router.put("/api/lieferungen/{lieferung_id}")
async def lieferung_aendern(lieferung_id: str, body: LieferungUpdateIn, user: dict = Depends(schreibend("mitarbeiter"))):
    l, z = await eintrag_laden("lieferungen", user, lieferung_id)
    leitung_noetig(z)
    daten = body.model_dump(exclude_unset=True)
    for k in ("geplant_am", "tatsaechlich_am"):
        if daten.get(k):
            datum_pruefen(daten[k])
    for k in ("zeitfenster_von", "zeitfenster_bis"):
        if daten.get(k):
            daten[k] = zeit_pruefen(daten[k])
    if "firma_id" in daten:
        daten["firma_id"], _ = await firma_am_projekt(l["project_id"], z["projekt"], daten.get("firma_id"))
    daten["updated_at"] = jetzt_iso()
    await db().lieferungen.update_one({"id": lieferung_id}, {"$set": daten})
    await protokollieren(user, "lieferung.geaendert", l["material"], details={"felder": sorted(k for k in daten if k != "updated_at")})
    return {"lieferung": await _lieferung_anreichern({**l, **daten})}


@router.delete("/api/lieferungen/{lieferung_id}")
async def lieferung_loeschen(lieferung_id: str, user: dict = Depends(schreibend("mitarbeiter"))):
    l, z = await eintrag_laden("lieferungen", user, lieferung_id)
    leitung_noetig(z)
    await db().lieferungen.delete_one({"id": lieferung_id})
    await protokollieren(user, "lieferung.geloescht", l["material"])
    return {"ok": True}


@router.post("/api/lieferungen/{lieferung_id}/status")
async def lieferung_status(lieferung_id: str, body: LieferungStatusIn, user: dict = Depends(aktueller_nutzer)):
    l, z = await eintrag_laden("lieferungen", user, lieferung_id)
    leitung = z["eigentuemer"] and z["leitung"]
    firma = (not z["eigentuemer"]) and partner_leitung(z, user) and l.get("firma_id") == user["firma_id"]
    erlaubt = set(LIEFERUNG_STATUS) if leitung else LIEFERUNG_FIRMA_STATUS if firma else set()
    if body.status not in erlaubt:
        raise HTTPException(403, "Diesen Status darfst du hier nicht setzen.")
    aenderung = {"status": body.status, "updated_at": jetzt_iso()}
    if body.status in ("eingetroffen", "entladen", "abgeschlossen") and not l.get("tatsaechlich_am"):
        aenderung["tatsaechlich_am"] = body.tatsaechlich_am or lokal_jetzt().date().isoformat()
    await db().lieferungen.update_one({"id": lieferung_id}, {"$set": aenderung, "$push": {"verlauf": _schritt(user, body.status, body.kommentar)}})
    if body.status == "verspaetet":
        await eigentuemer_benachrichtigen(z["projekt"], "lieferung_verspaetet", f"Lieferung „{l['material']}“ ({l['geplant_am']}) verspätet sich.", f"/projekte/{l['project_id']}")
        if l.get("firma_id") != z["projekt"]["firma_id"]:
            await benachrichtigen(l["firma_id"], "lieferung_verspaetet", f"Lieferung „{l['material']}“ ({l['geplant_am']}) verspätet sich.", "/zusammenarbeit", mindestens="vorarbeiter")
    elif body.status in ("eingetroffen", "entladen") and not leitung:
        await eigentuemer_benachrichtigen(z["projekt"], "lieferung_status", f"Lieferung „{l['material']}“ ist {LIEFERUNG_STATUS_NAMEN[body.status].lower()} ({user.get('name')}).", f"/projekte/{l['project_id']}")
    await protokollieren(user, "lieferung.status", l["material"], details={"status": body.status})
    return {"lieferung": await _lieferung_anreichern({**l, **aenderung})}


@router.post("/api/lieferungen/{lieferung_id}/fotos")
async def lieferung_foto(lieferung_id: str, datei: UploadFile = File(...), note: str = Form(""), user: dict = Depends(aktueller_nutzer)):
    l, z = await eintrag_laden("lieferungen", user, lieferung_id)
    if not ((z["eigentuemer"] and z["leitung"]) or (partner_leitung(z, user) and l.get("firma_id") == user["firma_id"])):
        raise HTTPException(403, "Dafür fehlt die Berechtigung.")
    return {"dokument": await _foto_speichern(user, "lieferung", l, datei, note)}


# ================================================================ Mängel

async def _mangel_anreichern(m: dict) -> dict:
    m = dict(m)
    m["firma_name"] = (await firma_kurz(m.get("firma_id")))["name"] if m.get("firma_id") else ""
    m["status_name"] = MANGEL_STATUS_NAMEN.get(m.get("status"), m.get("status"))
    m["fotos_anzahl"] = await db().documents.count_documents({"scope": "mangel", "ref_id": m["id"]})
    m["ueberfaellig"] = bool(m.get("frist") and m["frist"] < lokal_jetzt().date().isoformat() and m.get("status") not in ("abgenommen",))
    return m


@router.get("/api/projekte/{project_id}/maengel")
async def maengel_liste(project_id: str, offen: bool = False, user: dict = Depends(aktueller_nutzer)):
    z = await zugang(user, project_id)
    if z["eigentuemer"] and not z["leitung"]:
        raise HTTPException(404, "Projekt nicht gefunden.")
    filt: dict = {"project_id": project_id}
    if offen:
        filt["status"] = {"$ne": "abgenommen"}
    if not z["eigentuemer"]:
        filt["firma_id"] = user["firma_id"]
    aus = [await _mangel_anreichern(m) async for m in db().maengel.find(filt, {"_id": 0}).sort([("status", 1), ("frist", 1), ("created_at", -1)]).limit(2000)]
    firmen = [{"id": z["projekt"]["firma_id"], "name": (await firma_kurz(z["projekt"]["firma_id"]))["name"], "eigentuemer": True}]
    if z["eigentuemer"]:
        async for b in db().beteiligungen.find({"project_id": project_id, "status": "aktiv"}, {"_id": 0}):
            firmen.append({"id": b["firma_id"], "name": b.get("firma_name"), "gewerk": b.get("gewerk"), "eigentuemer": False})
    return {"maengel": aus, "firmen": firmen, "status": MANGEL_STATUS_NAMEN, "leitung": bool(z["eigentuemer"] and z["leitung"])}


@router.post("/api/projekte/{project_id}/maengel")
async def mangel_anlegen(project_id: str, body: MangelIn, user: dict = Depends(aktueller_nutzer)):
    """Mängel melden darf die Eigentümer-Projektleitung und die Leitung beteiligter Firmen (z. B. Vorfinden eines Schadens)."""
    z = await zugang(user, project_id)
    if not ((z["eigentuemer"] and z["leitung"]) or (not z["eigentuemer"] and partner_leitung(z, user))):
        raise HTTPException(403, "Mängel melden darf die Projektleitung oder die Leitung einer beteiligten Firma.")
    daten = body.model_dump()
    if daten.get("frist"):
        datum_pruefen(daten["frist"])
    firma_id = None
    if daten.get("firma_id"):
        if not (z["eigentuemer"] and z["leitung"]):
            raise HTTPException(403, "Eine verantwortliche Firma bestimmt die Projektleitung.")
        firma_id, _ = await firma_am_projekt(project_id, z["projekt"], daten["firma_id"])
    status = "zugewiesen" if firma_id else "offen"
    m = {**daten, "id": neue_id(), "project_id": project_id, "owner_firma_id": z["projekt"]["firma_id"], "firma_id": firma_id, "status": status,
         "gemeldet_von": user.get("name"), "gemeldet_firma_id": user["firma_id"], "kommentare": [], "verlauf": [_schritt(user, status)],
         "created_at": jetzt_iso(), "updated_at": jetzt_iso()}
    await db().maengel.insert_one(dict(m))
    if firma_id and firma_id != z["projekt"]["firma_id"]:
        await benachrichtigen(firma_id, "mangel_zugewiesen", f"Mangel im Projekt „{z['projekt']['name']}“: {m['beschreibung'][:80]}" + (f" (Frist {m['frist']})" if m.get("frist") else ""), "/zusammenarbeit", mindestens="vorarbeiter")
    if not z["eigentuemer"]:
        await eigentuemer_benachrichtigen(z["projekt"], "mangel_gemeldet", f"{user.get('name')} ({(await firma_kurz(user['firma_id']))['name']}) hat einen Mangel gemeldet: {m['beschreibung'][:80]}", f"/projekte/{project_id}")
    await protokollieren(user, "mangel.gemeldet", m["beschreibung"][:80], details={"projekt": z["projekt"]["name"], "firma_id": firma_id})
    return {"mangel": await _mangel_anreichern(m)}


@router.get("/api/maengel/{mangel_id}")
async def mangel_lesen(mangel_id: str, user: dict = Depends(aktueller_nutzer)):
    m, z = await eintrag_laden("maengel", user, mangel_id)
    leitung = z["eigentuemer"] and z["leitung"]
    firma = (not z["eigentuemer"]) and partner_leitung(z, user) and m.get("firma_id") == user["firma_id"]
    erlaubt = list(MANGEL_STATUS) if leitung else sorted(MANGEL_FIRMA_STATUS) if firma else []
    return {"mangel": await _mangel_anreichern(m), "fotos": await _fotos("mangel", mangel_id), "status_erlaubt": [s for s in MANGEL_STATUS if s in erlaubt], "rolle": "leitung" if leitung else "firma" if firma else "lesen"}


@router.put("/api/maengel/{mangel_id}")
async def mangel_aendern(mangel_id: str, body: MangelUpdateIn, user: dict = Depends(schreibend("mitarbeiter"))):
    m, z = await eintrag_laden("maengel", user, mangel_id)
    leitung_noetig(z)
    daten = body.model_dump(exclude_unset=True)
    if daten.get("frist"):
        datum_pruefen(daten["frist"])
    if "firma_id" in daten:
        if daten["firma_id"]:
            daten["firma_id"], _ = await firma_am_projekt(m["project_id"], z["projekt"], daten["firma_id"])
            if m.get("status") == "offen":
                daten["status"] = "zugewiesen"
            if daten["firma_id"] != m.get("firma_id") and daten["firma_id"] != z["projekt"]["firma_id"]:
                await benachrichtigen(daten["firma_id"], "mangel_zugewiesen", f"Mangel im Projekt „{z['projekt']['name']}“: {m['beschreibung'][:80]}", "/zusammenarbeit", mindestens="vorarbeiter")
        else:
            daten["firma_id"] = None
    daten["updated_at"] = jetzt_iso()
    await db().maengel.update_one({"id": mangel_id}, {"$set": daten})
    await protokollieren(user, "mangel.geaendert", m["beschreibung"][:80], details={"felder": sorted(k for k in daten if k != "updated_at")})
    return {"mangel": await _mangel_anreichern({**m, **daten})}


@router.post("/api/maengel/{mangel_id}/status")
async def mangel_status(mangel_id: str, body: MangelStatusIn, user: dict = Depends(aktueller_nutzer)):
    m, z = await eintrag_laden("maengel", user, mangel_id)
    leitung = z["eigentuemer"] and z["leitung"]
    firma = (not z["eigentuemer"]) and partner_leitung(z, user) and m.get("firma_id") == user["firma_id"]
    erlaubt = set(MANGEL_STATUS) if leitung else MANGEL_FIRMA_STATUS if firma else set()
    if body.status not in erlaubt:
        raise HTTPException(403, "Diesen Status darfst du hier nicht setzen.")
    await db().maengel.update_one({"id": mangel_id}, {"$set": {"status": body.status, "updated_at": jetzt_iso()}, "$push": {"verlauf": _schritt(user, body.status, body.kommentar)}})
    if body.status == "behoben_gemeldet":
        await eigentuemer_benachrichtigen(z["projekt"], "mangel_behoben", f"Mangel „{m['beschreibung'][:60]}“ wurde als behoben gemeldet ({user.get('name')}).", f"/projekte/{m['project_id']}")
    elif body.status in ("abgenommen", "erneut_geoeffnet") and m.get("firma_id") and m["firma_id"] != z["projekt"]["firma_id"]:
        await benachrichtigen(m["firma_id"], "mangel_" + body.status, f"Mangel „{m['beschreibung'][:60]}“: {MANGEL_STATUS_NAMEN[body.status]}.", "/zusammenarbeit", mindestens="vorarbeiter")
    await protokollieren(user, "mangel.status", m["beschreibung"][:80], details={"status": body.status})
    return {"mangel": await _mangel_anreichern({**m, "status": body.status})}


@router.post("/api/maengel/{mangel_id}/kommentare")
async def mangel_kommentar(mangel_id: str, body: KommentarIn, user: dict = Depends(aktueller_nutzer)):
    m, z = await eintrag_laden("maengel", user, mangel_id)
    if not ((z["eigentuemer"] and z["leitung"]) or (partner_leitung(z, user) and m.get("firma_id") == user["firma_id"])):
        raise HTTPException(403, "Dafür fehlt die Berechtigung.")
    k = {"id": neue_id(), "user_name": user.get("name"), "firma_name": (await firma_kurz(user["firma_id"]))["name"], "text": body.text.strip(), "at": jetzt_iso()}
    await db().maengel.update_one({"id": mangel_id}, {"$push": {"kommentare": k}, "$set": {"updated_at": jetzt_iso()}})
    return {"kommentar": k}


@router.post("/api/maengel/{mangel_id}/fotos")
async def mangel_foto(mangel_id: str, datei: UploadFile = File(...), note: str = Form(""), user: dict = Depends(aktueller_nutzer)):
    m, z = await eintrag_laden("maengel", user, mangel_id)
    if not ((z["eigentuemer"] and z["leitung"]) or (partner_leitung(z, user) and m.get("firma_id") == user["firma_id"])):
        raise HTTPException(403, "Dafür fehlt die Berechtigung.")
    return {"dokument": await _foto_speichern(user, "mangel", m, datei, note)}


# ================================================================ Bautagesberichte

BERICHT_STATUS_NAMEN = {"entwurf": "Entwurf", "eingereicht": "Zur Freigabe eingereicht", "freigegeben": "Freigegeben"}


async def _bericht_anreichern(b: dict) -> dict:
    b = dict(b)
    b["firma_name"] = (await firma_kurz(b.get("firma_id")))["name"]
    b["status_name"] = BERICHT_STATUS_NAMEN.get(b.get("status"), b.get("status"))
    b["fotos_anzahl"] = await db().documents.count_documents({"scope": "tagesbericht", "ref_id": b["id"]})
    return b


@router.get("/api/projekte/{project_id}/tagesberichte")
async def berichte_liste(project_id: str, user: dict = Depends(aktueller_nutzer)):
    z = await zugang(user, project_id)
    if z["eigentuemer"] and not z["leitung"]:
        raise HTTPException(404, "Projekt nicht gefunden.")
    filt: dict = {"project_id": project_id}
    if not z["eigentuemer"]:
        filt["firma_id"] = user["firma_id"]
    aus = [await _bericht_anreichern(b) async for b in db().tagesberichte.find(filt, {"_id": 0}).sort([("datum", -1), ("created_at", -1)]).limit(1000)]
    return {"berichte": aus, "status": BERICHT_STATUS_NAMEN, "leitung": bool(z["eigentuemer"] and z["leitung"]), "schreiben": bool((z["eigentuemer"] and z["leitung"]) or partner_leitung(z, user))}


@router.get("/api/projekte/{project_id}/tagesbericht-vorschlag")
async def bericht_vorschlag(project_id: str, datum: str, user: dict = Depends(aktueller_nutzer)):
    """Vorbelegung für einen Tagesbericht aus Aufgaben, Lieferungen, Mängeln und Anwesenheit des Tages."""
    z = await zugang(user, project_id)
    datum_pruefen(datum)
    filt_firma = {} if z["eigentuemer"] else {"firma_id": user["firma_id"]}
    aufgaben = [a async for a in db().aufgaben.find({"project_id": project_id, "datum": datum, **filt_firma}, {"_id": 0, "titel": 1, "firma_id": 1, "status": 1, "bereich": 1})]
    lieferungen = [l async for l in db().lieferungen.find({"project_id": project_id, "geplant_am": datum, **filt_firma}, {"_id": 0, "material": 1, "lieferant": 1, "status": 1})]
    maengel_offen = await db().maengel.count_documents({"project_id": project_id, "status": {"$ne": "abgenommen"}, **filt_firma})
    namen = {}
    for f in {a.get("firma_id") for a in aufgaben}:
        namen[f] = (await firma_kurz(f))["name"]
    firmen = sorted({namen[a.get("firma_id")] for a in aufgaben if a.get("firma_id") in namen})
    taetigkeiten = "\n".join(f"- {a['titel']}{' (' + a['bereich'] + ')' if a.get('bereich') else ''} – {namen.get(a.get('firma_id'), '')} [{STATUS_NAMEN.get(a.get('status'), a.get('status'))}]" for a in aufgaben)
    liefer_text = "\n".join(f"- {l['material']}{' von ' + l['lieferant'] if l.get('lieferant') else ''} [{LIEFERUNG_STATUS_NAMEN.get(l.get('status'), l.get('status'))}]" for l in lieferungen)
    anwesend = len({e.get("user_id") async for e in db().entries.find({"project_id": (z["lokal"] or z["projekt"])["id"], "date": datum}, {"_id": 0, "user_id": 1}) if e.get("user_id")})
    return {"firmen": firmen, "taetigkeiten": taetigkeiten, "lieferungen": liefer_text, "mitarbeiter_anzahl": anwesend, "maengel_offen": maengel_offen}


@router.post("/api/projekte/{project_id}/tagesberichte")
async def bericht_anlegen(project_id: str, body: TagesberichtIn, user: dict = Depends(aktueller_nutzer)):
    z = await zugang(user, project_id)
    if not ((z["eigentuemer"] and z["leitung"]) or (not z["eigentuemer"] and partner_leitung(z, user))):
        raise HTTPException(403, "Tagesberichte schreibt die Projektleitung oder die Leitung einer beteiligten Firma.")
    daten = body.model_dump()
    datum_pruefen(daten["datum"])
    b = {**daten, "id": neue_id(), "project_id": project_id, "owner_firma_id": z["projekt"]["firma_id"], "firma_id": user["firma_id"], "status": "entwurf",
         "verfasser": user.get("name"), "verfasser_id": user["id"], "verlauf": [_schritt(user, "entwurf")], "created_at": jetzt_iso(), "updated_at": jetzt_iso()}
    await db().tagesberichte.insert_one(dict(b))
    await protokollieren(user, "tagesbericht.angelegt", b["datum"], details={"projekt": z["projekt"]["name"]})
    return {"bericht": await _bericht_anreichern(b)}


@router.get("/api/tagesberichte/{bericht_id}")
async def bericht_lesen(bericht_id: str, user: dict = Depends(aktueller_nutzer)):
    b, z = await eintrag_laden("tagesberichte", user, bericht_id)
    leitung = z["eigentuemer"] and z["leitung"]
    eigener = b.get("firma_id") == user["firma_id"] and ((z["eigentuemer"] and z["leitung"]) or partner_leitung(z, user))
    erlaubt = []
    if eigener and b.get("status") == "entwurf":
        erlaubt.append("eingereicht")
    if leitung and b.get("status") == "eingereicht":
        erlaubt += ["freigegeben", "entwurf"]
    if leitung and b.get("status") == "entwurf" and b.get("firma_id") == user["firma_id"]:
        erlaubt = ["eingereicht", "freigegeben"]
    return {"bericht": await _bericht_anreichern(b), "fotos": await _fotos("tagesbericht", bericht_id), "status_erlaubt": sorted(set(erlaubt)), "bearbeiten": eigener and b.get("status") != "freigegeben"}


@router.put("/api/tagesberichte/{bericht_id}")
async def bericht_aendern(bericht_id: str, body: TagesberichtIn, user: dict = Depends(aktueller_nutzer)):
    b, z = await eintrag_laden("tagesberichte", user, bericht_id)
    if b.get("firma_id") != user["firma_id"] or not ((z["eigentuemer"] and z["leitung"]) or partner_leitung(z, user)):
        raise HTTPException(403, "Nur die verfassende Firma darf den Bericht ändern.")
    if b.get("status") == "freigegeben":
        raise HTTPException(400, "Freigegebene Berichte lassen sich nicht mehr ändern.")
    daten = body.model_dump()
    datum_pruefen(daten["datum"])
    daten["updated_at"] = jetzt_iso()
    await db().tagesberichte.update_one({"id": bericht_id}, {"$set": daten})
    return {"bericht": await _bericht_anreichern({**b, **daten})}


@router.post("/api/tagesberichte/{bericht_id}/status")
async def bericht_status(bericht_id: str, body: TagesberichtStatusIn, user: dict = Depends(aktueller_nutzer)):
    daten = await bericht_lesen(bericht_id, user)
    if body.status not in daten["status_erlaubt"]:
        raise HTTPException(403, "Diesen Schritt darfst du hier nicht setzen.")
    b = daten["bericht"]
    await db().tagesberichte.update_one({"id": bericht_id}, {"$set": {"status": body.status, "updated_at": jetzt_iso()}, "$push": {"verlauf": _schritt(user, body.status, body.kommentar)}})
    p = await db().projects.find_one({"id": b["project_id"]}, {"_id": 0})
    if body.status == "eingereicht" and p:
        await eigentuemer_benachrichtigen(p, "bericht_eingereicht", f"Tagesbericht vom {b['datum']} ({b['firma_name']}) wartet auf Freigabe.", f"/projekte/{b['project_id']}")
    elif body.status == "freigegeben" and b.get("firma_id") != (p or {}).get("firma_id"):
        await benachrichtigen(b["firma_id"], "bericht_freigegeben", f"Tagesbericht vom {b['datum']} wurde freigegeben.", "/zusammenarbeit", mindestens="vorarbeiter")
    await protokollieren(user, "tagesbericht.status", b["datum"], details={"status": body.status})
    return {"bericht": await _bericht_anreichern({**b, "status": body.status})}


@router.post("/api/tagesberichte/{bericht_id}/fotos")
async def bericht_foto(bericht_id: str, datei: UploadFile = File(...), note: str = Form(""), user: dict = Depends(aktueller_nutzer)):
    daten = await bericht_lesen(bericht_id, user)
    if not daten["bearbeiten"]:
        raise HTTPException(403, "Dafür fehlt die Berechtigung.")
    return {"dokument": await _foto_speichern(user, "tagesbericht", daten["bericht"], datei, note)}


@router.delete("/api/tagesberichte/{bericht_id}")
async def bericht_loeschen(bericht_id: str, user: dict = Depends(aktueller_nutzer)):
    daten = await bericht_lesen(bericht_id, user)
    if not daten["bearbeiten"]:
        raise HTTPException(403, "Dafür fehlt die Berechtigung.")
    await db().tagesberichte.delete_one({"id": bericht_id})
    return {"ok": True}


@router.get("/api/tagesberichte/{bericht_id}/pdf")
async def bericht_pdf(bericht_id: str, user: dict = Depends(aktueller_nutzer)):
    """Bautagesbericht als PDF (A4, eingebettete Schrift, bis zu sechs Fotos)."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from pdfbasis import SCHRIFT, SCHRIFT_FETT, schrift_registrieren
    b, z = await eintrag_laden("tagesberichte", user, bericht_id)
    b = await _bericht_anreichern(b)
    fotos = await _fotos("tagesbericht", bericht_id)
    schrift_registrieren()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
                            title=f"Bautagesbericht {b['datum']} – {z['projekt']['name']}", author=b["firma_name"], creator="Stundenzettel Pro")
    h1 = ParagraphStyle("h1", fontName=SCHRIFT_FETT, fontSize=15, leading=19)
    h2 = ParagraphStyle("h2", fontName=SCHRIFT_FETT, fontSize=10, leading=13, spaceBefore=6)
    norm = ParagraphStyle("n", fontName=SCHRIFT, fontSize=9.5, leading=13)
    klein = ParagraphStyle("k", fontName=SCHRIFT, fontSize=8, leading=10, textColor=colors.HexColor("#666666"))
    esc = lambda t: (t or "–").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")  # noqa: E731
    teile = [Paragraph(f"Bautagesbericht {b['datum']}", h1), Paragraph(f"{esc(z['projekt']['name'])}{' · ' + esc(z['projekt'].get('address')) if z['projekt'].get('address') else ''}", norm),
             Paragraph(f"Verfasser: {esc(b.get('verfasser'))} ({esc(b['firma_name'])}) · Status: {esc(b['status_name'])}{' · Bauabschnitt ' + esc(b.get('bereich')) if b.get('bereich') else ''}{' · Wetter: ' + esc(b.get('wetter')) if b.get('wetter') else ''}", klein), Spacer(1, 4 * mm)]
    kopf = [["Beteiligte Firmen", esc(", ".join(b.get("firmen") or []))], ["Mitarbeiter vor Ort", str(b.get("mitarbeiter_anzahl") or 0)], ["Fortschritt", esc(b.get("fortschritt"))]]
    t = Table([[Paragraph(k, h2), Paragraph(v, norm)] for k, v in kopf], colWidths=[45 * mm, 125 * mm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#DDDDDD"))]))
    teile.append(t)
    for titel, feld in (("Tätigkeiten", "taetigkeiten"), ("Lieferungen", "lieferungen"), ("Behinderungen", "behinderungen"), ("Mängel", "maengel"),
                        ("Besondere Vorkommnisse", "besondere_vorkommnisse"), ("Notizen", "notizen")):
        if b.get(feld):
            teile += [Paragraph(titel, h2), Paragraph(esc(b[feld]), norm)]
    if fotos:
        teile.append(Paragraph("Fotos", h2))
        zellen = []
        for f in fotos[:6]:
            d = await db().documents.find_one({"id": f["id"]}, {"_id": 0, "path": 1})
            try:
                bild = ImageReader(io.BytesIO(bild_verkleinern(d["path"], 700)))
                bw, bh = bild.getSize()
                w = 82 * mm
                h = w * bh / bw
                if h > 60 * mm:
                    h, w = 60 * mm, 60 * mm * bw / bh
                zellen.append([Image(io.BytesIO(bild_verkleinern(d["path"], 700)), width=w, height=h), Paragraph(esc(f.get("note") or f.get("uploaded_by_name") or ""), klein)])
            except Exception:  # noqa: BLE001 – defektes Bild auslassen
                continue
        zeilen = [zellen[i:i + 2] for i in range(0, len(zellen), 2)]
        for zeile in zeilen:
            while len(zeile) < 2:
                zeile.append("")
            teile.append(Table([[z_[0] if z_ else "" for z_ in zeile], [z_[1] if z_ else "" for z_ in zeile]], colWidths=[88 * mm, 88 * mm]))
    teile += [Spacer(1, 8 * mm), Paragraph("Erstellt mit Stundenzettel Pro · Freigabe: " + ("erteilt" if b.get("status") == "freigegeben" else "offen"), klein)]
    doc.build(teile)
    await protokollieren(user, "tagesbericht.pdf", b["datum"])
    return _datei(buf.getvalue(), f"Bautagesbericht_{b['datum']}.pdf", "application/pdf")


# ================================================================ Meilensteine

@router.get("/api/projekte/{project_id}/meilensteine")
async def meilensteine(project_id: str, user: dict = Depends(aktueller_nutzer)):
    z = await zugang(user, project_id)
    liste = [m async for m in db().meilensteine.find({"project_id": project_id}, {"_id": 0}).sort("datum", 1)]
    return {"meilensteine": liste, "leitung": bool(z["eigentuemer"] and z["leitung"])}


@router.post("/api/projekte/{project_id}/meilensteine")
async def meilenstein_anlegen(project_id: str, body: MeilensteinIn, user: dict = Depends(schreibend("mitarbeiter"))):
    z = await zugang(user, project_id)
    leitung_noetig(z)
    datum_pruefen(body.datum)
    m = {**body.model_dump(), "id": neue_id(), "project_id": project_id, "created_at": jetzt_iso()}
    await db().meilensteine.insert_one(dict(m))
    return {"meilenstein": m}


@router.put("/api/meilensteine/{meilenstein_id}")
async def meilenstein_aendern(meilenstein_id: str, body: MeilensteinIn, user: dict = Depends(schreibend("mitarbeiter"))):
    m = await db().meilensteine.find_one({"id": meilenstein_id}, {"_id": 0})
    if not m:
        raise HTTPException(404, "Meilenstein nicht gefunden.")
    z = await zugang(user, m["project_id"])
    leitung_noetig(z)
    datum_pruefen(body.datum)
    await db().meilensteine.update_one({"id": meilenstein_id}, {"$set": body.model_dump()})
    return {"meilenstein": {**m, **body.model_dump()}}


@router.delete("/api/meilensteine/{meilenstein_id}")
async def meilenstein_loeschen(meilenstein_id: str, user: dict = Depends(schreibend("mitarbeiter"))):
    m = await db().meilensteine.find_one({"id": meilenstein_id}, {"_id": 0})
    if not m:
        raise HTTPException(404, "Meilenstein nicht gefunden.")
    z = await zugang(user, m["project_id"])
    leitung_noetig(z)
    await db().meilensteine.delete_one({"id": meilenstein_id})
    return {"ok": True}


# ================================================================ Geteilte Projektdokumente

def _dokument_sichtbar(d: dict, z: dict, user: dict) -> bool:
    if z["eigentuemer"] and z["leitung"]:
        return True
    return d.get("firma_id") == user["firma_id"] or bool(d.get("freigabe_alle"))


@router.get("/api/projekte/{project_id}/dokumente")
async def dokumente_liste(project_id: str, user: dict = Depends(aktueller_nutzer)):
    z = await zugang(user, project_id)
    if z["eigentuemer"] and not z["leitung"]:
        raise HTTPException(404, "Projekt nicht gefunden.")
    aus = []
    async for d in db().documents.find({"scope": "plattform", "ref_id": project_id}, {"_id": 0, "path": 0}).sort("created_at", -1):
        if _dokument_sichtbar(d, z, user):
            d["firma_name"] = (await firma_kurz(d.get("firma_id")))["name"]
            aus.append(d)
    return {"dokumente": aus, "kategorien": KATEGORIEN_DOKUMENTE, "leitung": bool(z["eigentuemer"] and z["leitung"]), "hochladen": bool((z["eigentuemer"] and z["leitung"]) or partner_leitung(z, user))}


@router.post("/api/projekte/{project_id}/dokumente")
async def dokument_hochladen(project_id: str, datei: UploadFile = File(...), kategorie: str = Form("Sonstiges"), note: str = Form(""),
                             fuer_alle: bool = Form(False), ordner: str = Form(""), ersetzt_id: str = Form(""), user: dict = Depends(aktueller_nutzer)):
    z = await zugang(user, project_id)
    if not ((z["eigentuemer"] and z["leitung"]) or partner_leitung(z, user)):
        raise HTTPException(403, "Dafür fehlt die Berechtigung.")
    meta = await datei_speichern(user["firma_id"], datei, user["id"])
    doc = {**meta, "firma_id": user["firma_id"], "scope": "plattform", "ref_id": project_id, "project_id": project_id,
           "category": kategorie if kategorie in KATEGORIEN_DOKUMENTE else "Sonstiges", "note": note[:500], "freigabe_alle": bool(fuer_alle) and z["eigentuemer"],
           "ordner": ordner.strip()[:120], "uploaded_by": user["id"], "uploaded_by_name": user.get("name"), "created_at": jetzt_iso()}
    doc = await version_verknuepfen(doc, ersetzt_id.strip() or None, user["firma_id"])
    if doc.get("vorgaenger_id"):
        alt = await db().documents.find_one({"id": doc["vorgaenger_id"]}, {"_id": 0, "freigabe_alle": 1})
        doc["freigabe_alle"] = doc["freigabe_alle"] or bool((alt or {}).get("freigabe_alle"))
    await db().documents.insert_one(dict(doc))
    if doc["freigabe_alle"]:
        async for b in db().beteiligungen.find({"project_id": project_id, "status": "aktiv"}, {"_id": 0, "firma_id": 1}):
            await benachrichtigen(b["firma_id"], "dokument_freigegeben", f"Neues Dokument im Projekt „{z['projekt']['name']}“: {doc['filename']}", "/zusammenarbeit", mindestens="vorarbeiter")
    elif not z["eigentuemer"]:
        await eigentuemer_benachrichtigen(z["projekt"], "dokument_hochgeladen", f"{(await firma_kurz(user['firma_id']))['name']} hat ein Dokument hochgeladen: {doc['filename']}", f"/projekte/{project_id}")
    await protokollieren(user, "projektdokument.hochgeladen", doc["filename"], details={"projekt": z["projekt"]["name"], "fuer_alle": doc["freigabe_alle"]})
    doc.pop("path", None)
    return {"dokument": doc}


@router.put("/api/projektdokumente/{dokument_id}")
async def dokument_freigabe(dokument_id: str, body: DokumentFreigabeIn, user: dict = Depends(aktueller_nutzer)):
    d = await db().documents.find_one({"id": dokument_id, "scope": "plattform"}, {"_id": 0})
    if not d:
        raise HTTPException(404, "Dokument nicht gefunden.")
    z = await zugang(user, d["ref_id"])
    leitung_noetig(z)
    await db().documents.update_one({"id": dokument_id}, {"$set": {"freigabe_alle": body.fuer_alle, "updated_at": jetzt_iso()}})
    if body.fuer_alle and not d.get("freigabe_alle"):
        async for b in db().beteiligungen.find({"project_id": d["ref_id"], "status": "aktiv"}, {"_id": 0, "firma_id": 1}):
            await benachrichtigen(b["firma_id"], "dokument_freigegeben", f"Dokument freigegeben im Projekt „{z['projekt']['name']}“: {d['filename']}", "/zusammenarbeit", mindestens="vorarbeiter")
    return {"ok": True}


# ================================================================ Kalender (Aufgaben, Lieferungen, Meilensteine, Fristen)

@router.get("/api/projekte/{project_id}/plattform-kalender")
async def plattform_kalender(project_id: str, von: str, bis: str, user: dict = Depends(aktueller_nutzer)):
    """Alles mit Datum für die Kalenderansicht, gefiltert nach Zugang: Aufgaben, Lieferungen, Meilensteine, Mängel-Fristen."""
    z = await zugang(user, project_id)
    datum_pruefen(von)
    datum_pruefen(bis)
    leitung = z["eigentuemer"] and z["leitung"]
    filt_firma = {} if leitung else {"firma_id": user["firma_id"]}
    aufgaben_filt = {"project_id": project_id, "datum": {"$gte": von, "$lte": bis}, **filt_firma}
    if not leitung and not hat_rolle(user, "vorarbeiter"):
        aufgaben_filt["$or"] = zuteilungs_filter(user["id"])
    namen: dict = {}

    async def name(fid):
        if fid not in namen:
            namen[fid] = (await firma_kurz(fid))["name"]
        return namen[fid]

    aufgaben = [{"id": a["id"], "datum": a["datum"], "titel": a["titel"], "firma_name": await name(a.get("firma_id")), "status": a.get("status"), "start_time": a.get("start_time"), "bereich": a.get("bereich")}
                async for a in db().aufgaben.find(aufgaben_filt, {"_id": 0}).sort([("datum", 1), ("start_time", 1)])]
    lieferungen = []
    if leitung or partner_leitung(z, user):
        lieferungen = [{"id": l["id"], "datum": l["geplant_am"], "material": l["material"], "firma_name": await name(l.get("firma_id")), "status": l.get("status"), "zeitfenster_von": l.get("zeitfenster_von")}
                       async for l in db().lieferungen.find({"project_id": project_id, "geplant_am": {"$gte": von, "$lte": bis}, **filt_firma}, {"_id": 0}).sort("geplant_am", 1)]
    meilensteine = [m async for m in db().meilensteine.find({"project_id": project_id, "datum": {"$gte": von, "$lte": bis}}, {"_id": 0}).sort("datum", 1)]
    fristen = []
    if leitung or partner_leitung(z, user):
        fristen = [{"id": m["id"], "datum": m["frist"], "beschreibung": m["beschreibung"][:80], "status": m.get("status"), "firma_name": await name(m.get("firma_id")) if m.get("firma_id") else ""}
                   async for m in db().maengel.find({"project_id": project_id, "frist": {"$gte": von, "$lte": bis}, "status": {"$ne": "abgenommen"}, **filt_firma}, {"_id": 0})]
    return {"aufgaben": aufgaben, "lieferungen": lieferungen, "meilensteine": meilensteine, "fristen": fristen}
