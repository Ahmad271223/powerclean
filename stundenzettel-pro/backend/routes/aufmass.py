"""Digitales Aufmaß (Stufe F): Aufmaße je Projekt und Position, Formelrechnung ohne eval, Fotos, Prüfung, Übernahme geprüfter Mengen
in Angebots- oder Auftragspositionen, Aufmaßblatt als PDF."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

import aufmass as am
import pdfs
from auth import aktueller_nutzer, firma_laden, hat_recht, hat_rolle, jetzt_iso, schreibend, schreibend_mit_recht
from dateien import datei_speichern
from db import db
from gemeinsam import foto_fuer_nutzer, neue_id, projekt_laden
from models import AufmassIn, AufmassUebernahmeIn, FormelIn
from protokoll import protokollieren
from zeiten import datum_pruefen, lokal_jetzt

router = APIRouter(tags=["Aufmaß"])


def _fuer_nutzer(a: dict, user: dict) -> dict:
    aus = {k: v for k, v in a.items() if k != "_id"}
    if not (hat_rolle(user, "buero") and hat_recht(user, "personal")) and a.get("user_id") != user["id"]:
        aus.pop("user_name", None)   # Mitarbeiterbezug nur mit Personalrecht (oder eigenes Aufmaß)
    aus["status_name"] = am.STATUS_NAMEN.get(a.get("status"), a.get("status"))
    return aus


async def _positionen_des_projekts(user: dict, p: dict) -> list[dict]:
    """Positionen, denen ein Aufmaß zugeordnet werden kann: Auftragspositionen, sonst Positionen des jüngsten Kundenangebots (Entwurf/gesendet)."""
    auftrag = p.get("auftrag") or {}
    if auftrag.get("positionen"):
        return [{"quelle": "auftrag", "nr": x.get("nr") or "", "text": x.get("text") or "", "einheit": x.get("einheit") or "", "menge": x.get("menge")} for x in auftrag["positionen"] if x.get("art") not in ("titel", "text")]
    a = await db().kundenangebote.find_one({"firma_id": user["firma_id"], "project_id": p["id"], "status": {"$in": ["entwurf", "gesendet", "angenommen"]}}, {"_id": 0, "id": 1, "positionen": 1, "nummer": 1}, sort=[("created_at", -1)])
    if a:
        return [{"quelle": "angebot", "angebot_id": a["id"], "angebot_nummer": a.get("nummer"), "position_id": x.get("id"), "nr": x.get("nr") or "", "text": x.get("text") or "", "einheit": x.get("einheit") or "", "menge": x.get("menge")}
                for x in a.get("positionen") or [] if x.get("art") not in ("titel", "text")]
    return []


@router.post("/api/aufmass/formel")
async def formel(body: FormelIn, user: dict = Depends(aktueller_nutzer)):
    """Live-Berechnung für die Oberfläche: Formel → Menge oder Fehlertext (400)."""
    try:
        return {"menge": am.berechnen(body.formel)}
    except am.FormelFehler as exc:
        raise HTTPException(400, str(exc))


@router.get("/api/projekte/{project_id}/aufmasse")
async def liste(project_id: str, user: dict = Depends(aktueller_nutzer)):
    p = await projekt_laden(user, project_id)
    aufmasse = [x async for x in db().aufmasse.find({"firma_id": user["firma_id"], "project_id": p["id"]}, {"_id": 0}).sort([("messdatum", -1), ("created_at", -1)])]
    return {"aufmasse": [_fuer_nutzer(a, user) for a in aufmasse], "summen": list(am.summen_je_position(aufmasse).values()), "positionen": await _positionen_des_projekts(user, p),
            "typen": {k: {"name": v[0], "einheit": v[1], "vorlage": am.VORLAGEN.get(k, "")} for k, v in am.TYPEN.items()}, "kann_pruefen": hat_rolle(user, "buero"),
            "abrechnungsart": p.get("abrechnungsart_projekt") or "stunden"}


@router.post("/api/projekte/{project_id}/aufmasse")
async def anlegen(project_id: str, body: AufmassIn, user: dict = Depends(schreibend("mitarbeiter"))):
    p = await projekt_laden(user, project_id, schreiben=True)
    try:
        menge = am.berechnen(body.formel)
    except am.FormelFehler as exc:
        raise HTTPException(400, str(exc))
    position = None
    if body.position_nr:
        kandidaten = await _positionen_des_projekts(user, p)
        position = next((x for x in kandidaten if x["nr"] == body.position_nr), None)
        if not position:
            raise HTTPException(404, f"Position {body.position_nr} gibt es weder im Auftrag noch im Angebot dieses Projekts.")
    a = {"id": neue_id(), "firma_id": user["firma_id"], "project_id": p["id"], "bezeichnung": body.bezeichnung.strip()[:200], "raum": (body.raum or "").strip()[:120],
         "typ": body.typ, "formel": body.formel.strip()[:500], "menge": menge, "einheit": am.einheit_fuer(body.typ, body.einheit),
         "position": position, "messdatum": body.messdatum or lokal_jetzt().date().isoformat(), "note": (body.note or "")[:500], "user_id": user["id"], "user_name": user.get("name"),
         "status": "erfasst", "geprueft_von": None, "geprueft_at": None, "fotos": [], "created_at": jetzt_iso(), "updated_at": jetzt_iso()}
    await db().aufmasse.insert_one(dict(a))
    await protokollieren(user, "aufmass.erfasst", p["name"], details={"bezeichnung": a["bezeichnung"], "menge": menge, "einheit": a["einheit"], "position": body.position_nr or ""})
    return {"aufmass": _fuer_nutzer(a, user)}


async def _laden(user: dict, aufmass_id: str) -> dict:
    a = await db().aufmasse.find_one({"id": aufmass_id, "firma_id": user["firma_id"]}, {"_id": 0})
    if not a:
        raise HTTPException(404, "Aufmaß nicht gefunden.")
    await projekt_laden(user, a["project_id"])   # Sichtbarkeit über das Projekt
    return a


def _bearbeitbar(a: dict, user: dict) -> None:
    if a.get("status") == "geprueft" and not hat_rolle(user, "buero"):
        raise HTTPException(409, "Geprüfte Aufmaße ändert nur noch das Büro.")
    if not hat_rolle(user, "buero") and a.get("user_id") != user["id"]:
        raise HTTPException(403, "Fremde Aufmaße ändert nur das Büro.")


@router.put("/api/aufmasse/{aufmass_id}")
async def aendern(aufmass_id: str, body: AufmassIn, user: dict = Depends(schreibend("mitarbeiter"))):
    a = await _laden(user, aufmass_id)
    _bearbeitbar(a, user)
    try:
        menge = am.berechnen(body.formel)
    except am.FormelFehler as exc:
        raise HTTPException(400, str(exc))
    position = a.get("position")
    if body.position_nr != ((position or {}).get("nr") or ""):
        p = await projekt_laden(user, a["project_id"])
        position = next((x for x in await _positionen_des_projekts(user, p) if x["nr"] == body.position_nr), None) if body.position_nr else None
        if body.position_nr and not position:
            raise HTTPException(404, f"Position {body.position_nr} nicht gefunden.")
    neu = {**a, "bezeichnung": body.bezeichnung.strip()[:200], "raum": (body.raum or "").strip()[:120], "typ": body.typ, "formel": body.formel.strip()[:500], "menge": menge,
           "einheit": am.einheit_fuer(body.typ, body.einheit), "position": position, "messdatum": body.messdatum or a.get("messdatum"),
           "note": (body.note or "")[:500], "updated_at": jetzt_iso()}
    if a.get("status") == "geprueft" and (menge != a.get("menge") or body.formel.strip() != a.get("formel")):
        neu.update({"status": "erfasst", "geprueft_von": None, "geprueft_at": None})   # geänderte Menge muss neu geprüft werden
    await db().aufmasse.update_one({"id": aufmass_id}, {"$set": {k: v for k, v in neu.items() if k != "id"}})
    return {"aufmass": _fuer_nutzer(neu, user)}


@router.delete("/api/aufmasse/{aufmass_id}")
async def loeschen(aufmass_id: str, user: dict = Depends(schreibend("mitarbeiter"))):
    a = await _laden(user, aufmass_id)
    _bearbeitbar(a, user)
    await db().aufmasse.delete_one({"id": aufmass_id})
    await protokollieren(user, "aufmass.geloescht", a.get("bezeichnung", ""), details={"menge": a.get("menge")})
    return {"ok": True}


@router.post("/api/aufmasse/{aufmass_id}/fotos")
async def foto(aufmass_id: str, datei: UploadFile = File(...), note: str = Form(""), user: dict = Depends(schreibend("mitarbeiter"))):
    a = await _laden(user, aufmass_id)
    _bearbeitbar(a, user)
    meta = await datei_speichern(user["firma_id"], datei, user["id"])
    if not (meta.get("mime") or "").startswith("image/") and meta.get("mime") != "application/pdf":
        raise HTTPException(400, "Bitte ein Foto (oder eine PDF-Skizze) hochladen.")
    doc = {**meta, "firma_id": user["firma_id"], "scope": "aufmass", "ref_id": a["id"], "category": "Aufmaß", "note": note[:500], "date": a.get("messdatum"),
           "uploaded_by": user["id"], "uploaded_by_name": user.get("name"), "created_at": jetzt_iso()}
    await db().documents.insert_one(dict(doc))
    doc.pop("path", None)
    await db().aufmasse.update_one({"id": aufmass_id}, {"$push": {"fotos": {"id": doc["id"], "filename": doc["filename"], "note": doc["note"]}}, "$set": {"updated_at": jetzt_iso()}})
    return {"dokument": foto_fuer_nutzer(user, doc)}


@router.post("/api/aufmasse/{aufmass_id}/pruefen")
async def pruefen(aufmass_id: str, user: dict = Depends(schreibend("buero"))):
    a = await _laden(user, aufmass_id)
    aenderung = {"status": "geprueft", "geprueft_von": user.get("name"), "geprueft_at": jetzt_iso(), "updated_at": jetzt_iso()}
    await db().aufmasse.update_one({"id": aufmass_id}, {"$set": aenderung})
    await protokollieren(user, "aufmass.geprueft", a.get("bezeichnung", ""), details={"menge": a.get("menge"), "position": (a.get("position") or {}).get("nr")})
    return {"aufmass": _fuer_nutzer({**a, **aenderung}, user)}


@router.post("/api/projekte/{project_id}/aufmasse/uebernehmen")
async def uebernehmen(project_id: str, body: AufmassUebernahmeIn, user: dict = Depends(schreibend_mit_recht("angebote"))):
    """Geprüfte Mengen je Position in das Angebot (nur Entwurf) oder in die Auftragspositionen übernehmen (Einheitspreis-Aufträge)."""
    p = await projekt_laden(user, project_id, schreiben=True)
    aufmasse = [x async for x in db().aufmasse.find({"firma_id": user["firma_id"], "project_id": p["id"], "status": "geprueft"}, {"_id": 0})]
    summen = am.summen_je_position(aufmasse)
    if not summen:
        raise HTTPException(400, "Keine geprüften Aufmaße mit Positionsbezug vorhanden.")

    def einheit_passt(pos: dict, s: dict) -> bool:
        """Mengen nur in Positionen gleicher Einheit übernehmen (m² ≠ Psch.); Schreibweisen wie m2/qm/Stück werden angeglichen."""
        norm = lambda e: str(e or "").lower().replace(".", "").replace("²", "2").replace("qm", "m2").replace("stück", "stk").replace("stck", "stk").strip()  # noqa: E731
        return norm(pos.get("einheit")) == norm(s.get("einheit"))
    if body.ziel == "angebot":
        a = await db().kundenangebote.find_one({"id": body.angebot_id, "firma_id": user["firma_id"]}, {"_id": 0}) if body.angebot_id else \
            await db().kundenangebote.find_one({"firma_id": user["firma_id"], "project_id": p["id"], "status": "entwurf"}, {"_id": 0}, sort=[("created_at", -1)])
        if not a:
            raise HTTPException(404, "Kein Angebotsentwurf für dieses Projekt gefunden.")
        if a.get("status") != "entwurf":
            raise HTTPException(409, "Mengen lassen sich nur in einen Angebotsentwurf übernehmen – gesendete Angebote bekommen eine neue Version.")
        from routes.angebote import _berechnen
        n = 0
        for pos in a.get("positionen") or []:
            s = summen.get(pos.get("nr") or "")
            if s and pos.get("art") not in ("titel", "text") and einheit_passt(pos, s):
                pos["menge"] = s["geprueft"]
                n += 1
        if not n:
            raise HTTPException(400, "Keine Angebotsposition passt zu den Positionsnummern der Aufmaße.")
        _berechnen(a, user.get("_firma") or await firma_laden(user["firma_id"]))
        a["verlauf"] = (a.get("verlauf") or []) + [{"aktion": "aufmass", "user_id": user["id"], "user_name": user.get("name"), "at": jetzt_iso(), "text": f"Mengen aus {n} geprüften Aufmaßpositionen übernommen"}]
        a["updated_at"] = jetzt_iso()
        await db().kundenangebote.update_one({"id": a["id"]}, {"$set": {k: v for k, v in a.items() if k != "id"}})
        await protokollieren(user, "aufmass.uebernommen", a.get("nummer", ""), details={"ziel": "angebot", "positionen": n})
        return {"uebernommen": n, "angebot": {"id": a["id"], "nummer": a.get("nummer"), "netto": (a.get("summen") or {}).get("netto")}}
    # Ziel Auftrag: Mengen und Gesamtbeträge der Auftragspositionen (Einheitspreise bleiben), Auftragswert folgt
    auftrag = p.get("auftrag")
    if not auftrag or not auftrag.get("positionen"):
        raise HTTPException(404, "Das Projekt hat keinen Auftrag mit Positionen.")
    if (p.get("abrechnungsart_projekt") or "stunden") == "pauschal" and not body.erzwingen:
        raise HTTPException(409, "Pauschalauftrag: Mengen ändern den Preis nicht. Mit erzwingen=true trotzdem übernehmen (Auftragswert wird neu gerechnet).")
    n = 0
    positionen, falsche_einheit = [], []
    for pos in auftrag["positionen"]:
        s = summen.get(pos.get("nr") or "")
        if s and pos.get("art") not in ("titel", "text"):
            if einheit_passt(pos, s):
                pos = {**pos, "menge": s["geprueft"], "gesamt": round(s["geprueft"] * float(pos.get("einzelpreis") or 0), 2), "aufmass": True}
                n += 1
            else:
                falsche_einheit.append(f"{pos.get('nr')} ({pos.get('einheit')} ≠ {s.get('einheit')})")
        positionen.append(pos)
    if not n:
        raise HTTPException(400, "Keine Auftragsposition passt zu den Positionsnummern der Aufmaße." + (f" Einheit passt nicht bei: {', '.join(falsche_einheit)}." if falsche_einheit else ""))
    netto = round(sum(float(x.get("gesamt") or 0) for x in positionen if x.get("art") not in ("titel", "text")), 2)
    neu = {**auftrag, "positionen": positionen, "netto_vor_aufmass": auftrag.get("netto_vor_aufmass", auftrag.get("netto")), "netto": netto, "aufmass_am": lokal_jetzt().date().isoformat(), "aufmass_von": user.get("name")}
    await db().projects.update_one({"id": p["id"]}, {"$set": {"auftrag": neu, **({"pauschale_netto": netto} if (p.get("abrechnungsart_projekt") or "stunden") == "pauschal" else {})}})
    await protokollieren(user, "aufmass.uebernommen", p["name"], details={"ziel": "auftrag", "positionen": n, "netto": netto})
    return {"uebernommen": n, "auftrag": neu}


@router.get("/api/projekte/{project_id}/aufmass.pdf")
async def aufmassblatt(project_id: str, user: dict = Depends(aktueller_nutzer)):
    p = await projekt_laden(user, project_id)
    firma = await firma_laden(user["firma_id"])
    aufmasse = [_fuer_nutzer(x, user) async for x in db().aufmasse.find({"firma_id": user["firma_id"], "project_id": p["id"]}, {"_id": 0}).sort([("position.nr", 1), ("messdatum", 1)])]
    if not aufmasse:
        raise HTTPException(404, "Noch keine Aufmaße in diesem Projekt.")
    pdf = pdfs.aufmass_pdf(firma, p, aufmasse, list(am.summen_je_position(aufmasse).values()))
    return Response(content=pdf, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="Aufmass_{(p.get("name") or "Projekt")[:40]}.pdf"'})
