"""Mitarbeiter: Einladen, Rollen, Personalakte (Dokumente), Stundenübersicht."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

import config
from auth import aktueller_nutzer, hat_rolle, jetzt_iso, nutzer_oeffentlich, rolle_noetig, schreibend
from dateien import KATEGORIEN_PERSONAL, KATEGORIEN_PROJEKT, datei_loeschen, datei_speichern
from db import db
from gemeinsam import neue_id
from models import MitarbeiterIn, MitarbeiterUpdateIn
from protokoll import protokollieren
from routes.auth_routes import einladungs_token
from zeiten import eintrag_minuten, tage_zwischen

router = APIRouter(tags=["Mitarbeiter"])


def _link(token: str) -> str:
    return f"{config.BASE_URL}/#/einladung/{token}"


def _kurz(u: dict) -> dict:
    return {"id": u["id"], "name": u.get("name"), "role": u.get("role"), "active": u.get("active", True),
            "personalnummer": u.get("personalnummer", "")}


@router.get("/api/mitarbeiter")
async def liste(alle: bool = False, user: dict = Depends(aktueller_nutzer)):
    filt = {"firma_id": user["firma_id"]}
    if not alle:
        filt["active"] = True
    aus = []
    async for u in db().users.find(filt, {"_id": 0}).sort("name", 1):
        aus.append(nutzer_oeffentlich(u) if hat_rolle(user, "buero") else _kurz(u))
    return {"mitarbeiter": aus, "kategorien": KATEGORIEN_PERSONAL}


@router.post("/api/mitarbeiter")
async def einladen(body: MitarbeiterIn, user: dict = Depends(schreibend("buero"))):
    email = body.email.lower().strip()
    if await db().users.find_one({"email": email}):
        raise HTTPException(409, "Diese E-Mail-Adresse ist schon vergeben.")
    if body.role == "inhaber" and not hat_rolle(user, "inhaber"):
        raise HTTPException(403, "Nur der Inhaber kann weitere Inhaber anlegen.")
    plan = user["_firma"].get("plan") or {}
    maximum = int(plan.get("nutzer_max") or 0)
    if maximum:
        aktiv = await db().users.count_documents({"firma_id": user["firma_id"], "active": True})
        if aktiv >= maximum:
            raise HTTPException(402, f"Die Lizenz umfasst {maximum} Nutzer. Bitte erweitern lassen.")
    token, bis = einladungs_token()
    n = await db().users.count_documents({"firma_id": user["firma_id"]})
    neu = {"id": neue_id(), "firma_id": user["firma_id"], "email": email, "name": body.name.strip(), "role": body.role,
           "personalnummer": (body.personalnummer or "").strip() or str(n + 1), "phone": body.phone or "",
           "notes": body.notes or "", "active": True, "pw_hash": None, "einladung_token": token, "einladung_bis": bis,
           "weekly_hours": 0, "vacation_days": 0, "created_at": jetzt_iso(), "invited_by": user["id"]}
    await db().users.insert_one(dict(neu))
    await protokollieren(user, "mitarbeiter.eingeladen", neu["name"], details={"email": email, "rolle": body.role})
    return {"mitarbeiter": nutzer_oeffentlich(neu), "einladung_link": _link(token)}


async def _laden(user: dict, user_id: str) -> dict:
    u = await db().users.find_one({"id": user_id, "firma_id": user["firma_id"]}, {"_id": 0})
    if not u:
        raise HTTPException(404, "Mitarbeiter nicht gefunden.")
    return u


def _selbst_oder_buero(user: dict, user_id: str) -> None:
    if user["id"] != user_id and not hat_rolle(user, "buero"):
        raise HTTPException(403, "Dafür fehlt die Berechtigung.")


@router.get("/api/mitarbeiter/{user_id}")
async def lesen(user_id: str, user: dict = Depends(aktueller_nutzer)):
    _selbst_oder_buero(user, user_id)
    u = await _laden(user, user_id)
    return {"mitarbeiter": nutzer_oeffentlich(u)}


@router.put("/api/mitarbeiter/{user_id}")
async def aendern(user_id: str, body: MitarbeiterUpdateIn, user: dict = Depends(schreibend("buero"))):
    u = await _laden(user, user_id)
    aenderung = body.model_dump(exclude_unset=True)
    if "role" in aenderung:
        if (u.get("role") == "inhaber" or aenderung["role"] == "inhaber") and not hat_rolle(user, "inhaber"):
            raise HTTPException(403, "Rollen von Inhabern kann nur der Inhaber ändern.")
        if u["id"] == user["id"] and aenderung["role"] != user["role"]:
            raise HTTPException(400, "Die eigene Rolle lässt sich nicht ändern.")
    if aenderung.get("active") is False and u["id"] == user["id"]:
        raise HTTPException(400, "Das eigene Konto lässt sich nicht deaktivieren.")
    if aenderung.get("active") is False and u.get("role") == "inhaber":
        n = await db().users.count_documents({"firma_id": user["firma_id"], "role": "inhaber", "active": True})
        if n <= 1:
            raise HTTPException(400, "Der letzte Inhaber kann nicht deaktiviert werden.")
    if not aenderung:
        return {"mitarbeiter": nutzer_oeffentlich(u)}
    aenderung["updated_at"] = jetzt_iso()
    await db().users.update_one({"id": user_id}, {"$set": aenderung})
    if aenderung.get("active") is False:
        await db().stempel.delete_many({"firma_id": user["firma_id"], "user_id": user_id})
    await protokollieren(user, "mitarbeiter.geaendert", u.get("name", ""), details=aenderung)
    return {"mitarbeiter": nutzer_oeffentlich(await _laden(user, user_id))}


@router.post("/api/mitarbeiter/{user_id}/einladung")
async def einladung_neu(user_id: str, user: dict = Depends(schreibend("buero"))):
    u = await _laden(user, user_id)
    if u.get("pw_hash"):
        raise HTTPException(400, "Dieses Konto ist schon eingerichtet.")
    token, bis = einladungs_token()
    await db().users.update_one({"id": user_id}, {"$set": {"einladung_token": token, "einladung_bis": bis}})
    await protokollieren(user, "mitarbeiter.einladung_erneuert", u.get("name", ""))
    return {"einladung_link": _link(token)}


@router.delete("/api/mitarbeiter/{user_id}")
async def deaktivieren(user_id: str, user: dict = Depends(schreibend("buero"))):
    body = MitarbeiterUpdateIn(active=False)
    return await aendern(user_id, body, user)


# ---------------------------------------------------------------- Stundenübersicht je Mitarbeiter
@router.get("/api/mitarbeiter/{user_id}/uebersicht")
async def uebersicht(user_id: str, jahr: int = Query(..., ge=2025, le=2100), monat: int = Query(..., ge=1, le=12),
                     user: dict = Depends(aktueller_nutzer)):
    _selbst_oder_buero(user, user_id)
    u = await _laden(user, user_id)
    von = f"{jahr:04d}-{monat:02d}-01"
    bis = f"{jahr:04d}-{monat:02d}-31"
    projekte = {}
    async for p in db().projects.find({"firma_id": user["firma_id"]}, {"_id": 0, "id": 1, "name": 1}):
        projekte[p["id"]] = p["name"]
    eintraege = []
    minuten = 0
    async for e in db().entries.find({"firma_id": user["firma_id"], "user_id": user_id, "date": {"$gte": von, "$lte": bis}},
                                      {"_id": 0}).sort([("date", 1), ("start_time", 1)]):
        e["project_name"] = projekte.get(e.get("project_id"), "")
        minuten += eintrag_minuten(e)
        eintraege.append(e)
    abwesenheiten = []
    async for a in db().absences.find({"firma_id": user["firma_id"], "user_id": user_id, "from_date": {"$lte": bis},
                                        "to_date": {"$gte": von}}, {"_id": 0}).sort("from_date", 1):
        abwesenheiten.append(a)
    tage = len({e["date"] for e in eintraege})
    urlaub = sum(tage_zwischen(max(a["from_date"], von), min(a["to_date"], bis)) for a in abwesenheiten
                 if a["type"] == "urlaub" and a.get("status") == "genehmigt")
    krank = sum(tage_zwischen(max(a["from_date"], von), min(a["to_date"], bis)) for a in abwesenheiten
                if a["type"] == "krank" and a.get("status") in ("genehmigt", "beantragt"))
    return {"mitarbeiter": nutzer_oeffentlich(u), "eintraege": eintraege, "abwesenheiten": abwesenheiten,
            "summe": {"minuten": minuten, "arbeitstage": tage, "urlaubstage": urlaub, "kranktage": krank}}


# ---------------------------------------------------------------- Personalakte
@router.get("/api/mitarbeiter/{user_id}/dokumente")
async def dokumente(user_id: str, user: dict = Depends(aktueller_nutzer)):
    _selbst_oder_buero(user, user_id)
    await _laden(user, user_id)
    aus = []
    async for d in db().documents.find({"firma_id": user["firma_id"], "scope": "user", "ref_id": user_id},
                                        {"_id": 0, "path": 0}).sort("created_at", -1):
        aus.append(d)
    return {"dokumente": aus, "kategorien": KATEGORIEN_PERSONAL}


@router.post("/api/mitarbeiter/{user_id}/dokumente")
async def dokument_hochladen(user_id: str, datei: UploadFile = File(...), kategorie: str = Form("Sonstiges"),
                             note: str = Form(""), user: dict = Depends(schreibend("buero"))):
    u = await _laden(user, user_id)
    meta = await datei_speichern(user["firma_id"], datei)
    doc = {**meta, "firma_id": user["firma_id"], "scope": "user", "ref_id": user_id,
           "category": kategorie if kategorie in KATEGORIEN_PERSONAL else "Sonstiges", "note": note[:500],
           "uploaded_by": user["id"], "uploaded_by_name": user.get("name"), "created_at": jetzt_iso()}
    await db().documents.insert_one(dict(doc))
    await protokollieren(user, "personalakte.datei", u.get("name", ""), details={"datei": meta["filename"], "kategorie": doc["category"]})
    doc.pop("path", None)
    return {"dokument": doc}


async def _dokument_zugriff(user: dict, dokument_id: str) -> dict:
    d = await db().documents.find_one({"id": dokument_id, "firma_id": user["firma_id"]}, {"_id": 0})
    if not d:
        raise HTTPException(404, "Dokument nicht gefunden.")
    if d["scope"] == "user":
        _selbst_oder_buero(user, d["ref_id"])
    elif d["scope"] == "project" and not hat_rolle(user, "buero"):
        p = await db().projects.find_one({"id": d["ref_id"], "firma_id": user["firma_id"]}, {"_id": 0, "employee_ids": 1})
        ids = (p or {}).get("employee_ids") or []
        if not p or (ids and user["id"] not in ids):
            raise HTTPException(403, "Dafür fehlt die Berechtigung.")
    return d


@router.get("/api/dokumente/{dokument_id}/datei")
async def dokument_datei(dokument_id: str, user: dict = Depends(aktueller_nutzer)):
    d = await _dokument_zugriff(user, dokument_id)
    return FileResponse(d["path"], media_type=d.get("mime") or "application/octet-stream", filename=d.get("filename") or "datei")


@router.delete("/api/dokumente/{dokument_id}")
async def dokument_loeschen(dokument_id: str, user: dict = Depends(schreibend("buero"))):
    d = await _dokument_zugriff(user, dokument_id)
    await db().documents.delete_one({"id": dokument_id})
    datei_loeschen(d)
    await protokollieren(user, "dokument.geloescht", d.get("filename", ""), details={"scope": d["scope"], "ref": d["ref_id"]})
    return {"ok": True}


@router.get("/api/dokumente/kategorien")
async def kategorien(user: dict = Depends(aktueller_nutzer)):
    return {"personal": KATEGORIEN_PERSONAL, "projekt": KATEGORIEN_PROJEKT}
