"""Bauabwicklung zwischen Auftraggeber und beauftragter Firma: Nachträge (zusätzliche Leistungen mit dokumentierter Zustimmung) und
Abnahmen (Protokoll mit offenen Mängeln, Bestätigung oder Widerspruch der Firma).

Rechte: Die Projektleitung der Eigentümerfirma sieht und entscheidet alles; die beauftragte Firma (Büro/Inhaber oder Leitung ihres
verknüpften Projekts) sieht nur ihre eigenen Nachträge und Abnahmen. Fremde: 404. Ursprünglicher Auftrag (Vergabe), Nachtrag,
Zustimmung und spätere Rechnung bleiben getrennte Datensätze; der Auftragswert ändert sich erst mit der Freigabe."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

import mail
from auth import aktueller_nutzer, firma_laden, hat_rolle, jetzt_iso, schreibend
from dateien import datei_speichern
from db import db
from gemeinsam import neue_id
from models import AbnahmeAntwortIn, AbnahmeIn, NachtragEntscheidungIn, NachtragIn
from plattform import MANGEL_STATUS_NAMEN, benachrichtigen, eigentuemer_benachrichtigen, firma_kurz, partner_leitung, zugang
from protokoll import protokollieren
from zeiten import datum_pruefen, lokal_jetzt

router = APIRouter(tags=["Bauabwicklung"])

NACHTRAG_STATUS_NAMEN = {"angefragt": "Vom Auftraggeber angefragt", "entwurf": "Entwurf", "eingereicht": "Eingereicht – wartet auf Freigabe",
                         "freigegeben": "Freigegeben", "abgelehnt": "Abgelehnt", "zurueckgezogen": "Zurückgezogen"}
ABNAHME_ART_NAMEN = {"teilabnahme": "Teilabnahme", "abnahme": "Abnahme", "endabnahme": "Endabnahme"}
ABNAHME_ERGEBNIS_NAMEN = {"abgenommen": "Abgenommen", "abgenommen_mit_maengeln": "Abgenommen unter Vorbehalt (Mängel)", "verweigert": "Abnahme verweigert"}
ABNAHME_STATUS_NAMEN = {"angefordert": "Von der Firma angefordert", "entwurf": "Entwurf", "erstellt": "Erstellt – wartet auf Bestätigung",
                        "bestaetigt": "Von der Firma bestätigt", "widersprochen": "Von der Firma widersprochen"}


def _datei(inhalt: bytes, name: str, typ: str) -> Response:
    return Response(content=inhalt, media_type=typ, headers={"Content-Disposition": f'attachment; filename="{name}"'})


def _schritt(user: dict, firma_name: str, status: str, kommentar: str = "") -> dict:
    return {"status": status, "user_id": user["id"], "user_name": user.get("name"), "firma_id": user["firma_id"], "firma_name": firma_name,
            "kommentar": (kommentar or "")[:1000], "at": jetzt_iso()}


async def _nummer(sammlung: str, project_id: str, praefix: str) -> str:
    n = await db()[sammlung].count_documents({"project_id": project_id})
    return f"{praefix}-{n + 1:03d}"


async def _beteiligung(project_id: str, firma_id: str) -> dict:
    b = await db().beteiligungen.find_one({"project_id": project_id, "firma_id": firma_id, "status": "aktiv"}, {"_id": 0})
    if not b:
        raise HTTPException(400, "Diese Firma ist nicht aktiv am Projekt beteiligt.")
    return b


def _rolle(z: dict, user: dict, eintrag: dict) -> str:
    """'leitung' (Eigentümer-Projektleitung), 'firma' (beauftragte Firma mit Leitung) oder ''."""
    if z["eigentuemer"]:
        return "leitung" if z["leitung"] else ""
    if eintrag.get("firma_id") == user["firma_id"] and partner_leitung(z, user):
        return "firma"
    return ""


async def _laden(sammlung: str, user: dict, eintrag_id: str) -> tuple[dict, dict, str]:
    e = await db()[sammlung].find_one({"id": eintrag_id}, {"_id": 0})
    if not e:
        raise HTTPException(404, "Eintrag nicht gefunden.")
    z = await zugang(user, e["project_id"])
    rolle = _rolle(z, user, e)
    if not rolle:
        raise HTTPException(404, "Eintrag nicht gefunden.")
    return e, z, rolle


async def _auftragswert_basis(b: dict) -> Optional[float]:
    """Ursprünglicher Auftragswert: Summe des angenommenen Angebots (Vergabe) oder ein von Hand gesetzter Wert an der Beteiligung."""
    if b.get("vergabe_id"):
        v = await db().vergaben.find_one({"id": b["vergabe_id"]}, {"_id": 0, "summe_netto": 1})
        if v and v.get("summe_netto") is not None:
            return float(v["summe_netto"])
    if b.get("auftragswert") is not None:
        return float(b["auftragswert"])
    return None


async def _nachtraege_summe(beteiligung_id: str) -> float:
    s = 0.0
    async for n in db().nachtraege.find({"beteiligung_id": beteiligung_id, "status": "freigegeben"}, {"_id": 0, "betrag_netto": 1}):
        s += float(n.get("betrag_netto") or 0)
    return round(s, 2)


async def _partner_link(b: dict) -> str:
    return f"/projekte/{b['lokales_project_id']}" if b.get("lokales_project_id") else "/zusammenarbeit"


def _dokumente_filter(scope: str, ref_id: str) -> dict:
    return {"scope": scope, "ref_id": ref_id}


async def _dokumente(scope: str, ref_id: str) -> list[dict]:
    return [d async for d in db().documents.find(_dokumente_filter(scope, ref_id), {"_id": 0, "path": 0}).sort("created_at", 1)]


# ================================================================ Nachträge

async def _nachtrag_anreichern(n: dict) -> dict:
    n["status_name"] = NACHTRAG_STATUS_NAMEN.get(n.get("status"), n.get("status"))
    n["dokumente"] = await _dokumente("nachtrag", n["id"])
    return n


@router.get("/api/projekte/{project_id}/nachtraege")
async def nachtraege_liste(project_id: str, user: dict = Depends(aktueller_nutzer)):
    z = await zugang(user, project_id)
    leitung = bool(z["eigentuemer"] and z["leitung"])
    if z["eigentuemer"] and not leitung:
        raise HTTPException(404, "Projekt nicht gefunden.")
    if not z["eigentuemer"] and not partner_leitung(z, user):
        raise HTTPException(404, "Projekt nicht gefunden.")
    filt = {"project_id": project_id} if leitung else {"project_id": project_id, "firma_id": user["firma_id"]}
    aus = [await _nachtrag_anreichern(n) async for n in db().nachtraege.find(filt, {"_id": 0}).sort("created_at", -1)]
    firmen = []
    if leitung:
        async for b in db().beteiligungen.find({"project_id": project_id, "status": "aktiv"}, {"_id": 0}):
            firmen.append({"id": b["firma_id"], "name": b.get("firma_name"), "gewerk": b.get("gewerk"), "beteiligung_id": b["id"],
                           "auftragswert": await _auftragswert_basis(b), "nachtraege_summe": await _nachtraege_summe(b["id"])})
    else:
        b = z["beteiligung"]
        firmen.append({"id": user["firma_id"], "name": b.get("firma_name"), "gewerk": b.get("gewerk"), "beteiligung_id": b["id"],
                       "auftragswert": await _auftragswert_basis(b), "nachtraege_summe": await _nachtraege_summe(b["id"])})
    return {"nachtraege": aus, "firmen": firmen, "status": NACHTRAG_STATUS_NAMEN, "rolle": "leitung" if leitung else "firma",
            "summe_freigegeben": round(sum(float(n.get("betrag_netto") or 0) for n in aus if n.get("status") == "freigegeben"), 2)}


@router.post("/api/projekte/{project_id}/nachtraege")
async def nachtrag_anlegen(project_id: str, body: NachtragIn, user: dict = Depends(schreibend("mitarbeiter"))):
    z = await zugang(user, project_id)
    p = z["projekt"]
    if z["eigentuemer"]:
        if not z["leitung"]:
            raise HTTPException(403, "Das darf nur die Projektleitung.")
        if not body.firma_id:
            raise HTTPException(400, "Bitte die beauftragte Firma angeben.")
        b = await _beteiligung(project_id, body.firma_id)
        status, firma_id = "angefragt", body.firma_id
    else:
        if not partner_leitung(z, user):
            raise HTTPException(403, "Das darf nur Büro, Inhaber oder die Projektleitung eurer Firma.")
        b = z["beteiligung"]
        status, firma_id = "entwurf", user["firma_id"]
    eigene = await firma_kurz(user["firma_id"])
    n = {"id": neue_id(), "nummer": await _nummer("nachtraege", project_id, "N"), "project_id": project_id, "owner_firma_id": p["firma_id"], "firma_id": firma_id,
         "firma_name": b.get("firma_name"), "beteiligung_id": b["id"], "vergabe_id": b.get("vergabe_id"), "gewerk": (body.gewerk or b.get("gewerk") or "")[:60],
         "titel": body.titel.strip(), "beschreibung": (body.beschreibung or "").strip(), "grund": (body.grund or "").strip(),
         "betrag_netto": float(body.betrag_netto) if body.betrag_netto is not None else None, "ust_satz": float(body.ust_satz if body.ust_satz is not None else 19),
         "status": status, "erstellt_von": {"id": user["id"], "name": user.get("name"), "firma_id": user["firma_id"], "firma_name": eigene["name"]},
         "eingereicht_at": None, "entschieden_at": None, "entschieden_von": None, "entscheidung_begruendung": "", "auftragswert_vorher": None, "auftragswert_nachher": None,
         "verlauf": [_schritt(user, eigene["name"], status, body.grund or "")], "created_at": jetzt_iso(), "updated_at": jetzt_iso()}
    await db().nachtraege.insert_one(dict(n))
    if status == "angefragt":
        await benachrichtigen(firma_id, "nachtrag_angefragt", f"{eigene['name']} fragt einen Nachtrag an: „{n['titel']}“ im Projekt „{p['name']}“ – bitte Preis einreichen.", await _partner_link(b))
        await mail.firma_informieren(firma_id, f"Nachtrag angefragt: {n['titel']} – {p['name']}",
                                     f"{eigene['name']} hat im Projekt „{p['name']}“ einen Nachtrag angefragt:\n\n{n['titel']}\n{n['beschreibung']}\n\nBitte den Preis im Projekt eintragen und einreichen: {mail.link(await _partner_link(b))}",
                                     "nachtrag", n["id"], project_id)
    await protokollieren(user, "nachtrag.angelegt", n["titel"], details={"projekt": p["name"], "nummer": n["nummer"], "status": status})
    return {"nachtrag": await _nachtrag_anreichern(n)}


@router.get("/api/nachtraege/{nachtrag_id}")
async def nachtrag_lesen(nachtrag_id: str, user: dict = Depends(aktueller_nutzer)):
    n, z, rolle = await _laden("nachtraege", user, nachtrag_id)
    return {"nachtrag": await _nachtrag_anreichern(n), "rolle": rolle, "projekt": {"id": z["projekt"]["id"], "name": z["projekt"]["name"]}}


@router.put("/api/nachtraege/{nachtrag_id}")
async def nachtrag_aendern(nachtrag_id: str, body: NachtragIn, user: dict = Depends(schreibend("mitarbeiter"))):
    n, z, rolle = await _laden("nachtraege", user, nachtrag_id)
    if n.get("status") not in ("angefragt", "entwurf"):
        raise HTTPException(400, "Nur angefragte Nachträge und Entwürfe lassen sich ändern.")
    aenderung = {"titel": body.titel.strip(), "beschreibung": (body.beschreibung or "").strip(), "grund": (body.grund or "").strip(), "updated_at": jetzt_iso()}
    if body.gewerk is not None:
        aenderung["gewerk"] = body.gewerk[:60]
    if rolle == "firma":
        if body.betrag_netto is not None:
            aenderung["betrag_netto"] = float(body.betrag_netto)
        if body.ust_satz is not None:
            aenderung["ust_satz"] = float(body.ust_satz)
    await db().nachtraege.update_one({"id": nachtrag_id}, {"$set": aenderung})
    return {"nachtrag": await _nachtrag_anreichern({**n, **aenderung})}


@router.post("/api/nachtraege/{nachtrag_id}/einreichen")
async def nachtrag_einreichen(nachtrag_id: str, user: dict = Depends(schreibend("mitarbeiter"))):
    n, z, rolle = await _laden("nachtraege", user, nachtrag_id)
    if rolle != "firma":
        raise HTTPException(403, "Einreichen kann nur die beauftragte Firma.")
    if n.get("status") not in ("angefragt", "entwurf"):
        raise HTTPException(400, "Dieser Nachtrag ist bereits eingereicht oder entschieden.")
    if not n.get("betrag_netto") or float(n["betrag_netto"]) <= 0:
        raise HTTPException(400, "Bitte zuerst den Nachtragsbetrag (netto) eintragen.")
    eigene = await firma_kurz(user["firma_id"])
    aenderung = {"status": "eingereicht", "eingereicht_at": jetzt_iso(), "updated_at": jetzt_iso()}
    await db().nachtraege.update_one({"id": nachtrag_id}, {"$set": aenderung, "$push": {"verlauf": _schritt(user, eigene["name"], "eingereicht")}})
    p = z["projekt"]
    text = f"{eigene['name']} hat den Nachtrag {n['nummer']} „{n['titel']}“ über {float(n['betrag_netto']):.2f} € netto eingereicht – bitte prüfen und freigeben."
    await eigentuemer_benachrichtigen(p, "nachtrag_eingereicht", text, f"/projekte/{p['id']}")
    await mail.firma_informieren(p["firma_id"], f"Nachtrag {n['nummer']} eingereicht – {p['name']}", text + f"\n\nZum Projekt: {mail.link('/projekte/' + p['id'])}", "nachtrag", nachtrag_id, p["id"])
    await protokollieren(user, "nachtrag.eingereicht", n["titel"], details={"nummer": n["nummer"], "betrag_netto": n["betrag_netto"]})
    await protokollieren(user, "nachtrag.eingegangen", n["titel"], details={"nummer": n["nummer"], "firma": eigene["name"], "betrag_netto": n["betrag_netto"]}, firma_id=p["firma_id"])
    return {"nachtrag": await _nachtrag_anreichern({**n, **aenderung})}


@router.post("/api/nachtraege/{nachtrag_id}/entscheiden")
async def nachtrag_entscheiden(nachtrag_id: str, body: NachtragEntscheidungIn, user: dict = Depends(schreibend("mitarbeiter"))):
    n, z, rolle = await _laden("nachtraege", user, nachtrag_id)
    if rolle != "leitung":
        raise HTTPException(403, "Freigeben oder ablehnen darf nur die Projektleitung des Auftraggebers.")
    if n.get("status") != "eingereicht":
        raise HTTPException(400, "Nur eingereichte Nachträge lassen sich entscheiden.")
    if not body.freigeben and not (body.begruendung or "").strip():
        raise HTTPException(400, "Bitte eine Begründung für die Ablehnung angeben.")
    eigene = await firma_kurz(user["firma_id"])
    b = await db().beteiligungen.find_one({"id": n["beteiligung_id"]}, {"_id": 0})
    aenderung = {"status": "freigegeben" if body.freigeben else "abgelehnt", "entschieden_at": jetzt_iso(), "entschieden_von": {"id": user["id"], "name": user.get("name")},
                 "entscheidung_begruendung": (body.begruendung or "").strip(), "updated_at": jetzt_iso()}
    if body.freigeben and b:
        basis = await _auftragswert_basis(b)
        vorher = (basis or 0.0) + await _nachtraege_summe(b["id"])
        aenderung["auftragswert_vorher"] = round(vorher, 2)
        aenderung["auftragswert_nachher"] = round(vorher + float(n["betrag_netto"]), 2)
    await db().nachtraege.update_one({"id": nachtrag_id}, {"$set": aenderung, "$push": {"verlauf": _schritt(user, eigene["name"], aenderung["status"], body.begruendung or "")}})
    if body.freigeben and b:
        summe = await _nachtraege_summe(b["id"])
        basis = await _auftragswert_basis(b)
        await db().beteiligungen.update_one({"id": b["id"]}, {"$set": {"nachtraege_summe": summe, "auftragswert_aktuell": round((basis or 0.0) + summe, 2)}})
    p = z["projekt"]
    text = (f"Nachtrag {n['nummer']} „{n['titel']}“ wurde von {eigene['name']} {'freigegeben' if body.freigeben else 'abgelehnt'}"
            f"{(' – ' + body.begruendung.strip()) if body.begruendung and body.begruendung.strip() else ''}.")
    if b:
        await benachrichtigen(n["firma_id"], "nachtrag_" + aenderung["status"], text, await _partner_link(b))
        await mail.firma_informieren(n["firma_id"], f"Nachtrag {n['nummer']} {'freigegeben' if body.freigeben else 'abgelehnt'} – {p['name']}", text + f"\n\nZum Projekt: {mail.link(await _partner_link(b))}", "nachtrag", nachtrag_id, p["id"])
    await protokollieren(user, "nachtrag." + aenderung["status"], n["titel"], details={"nummer": n["nummer"], "firma": n.get("firma_name"), "betrag_netto": n.get("betrag_netto"), "begruendung": body.begruendung or ""})
    await protokollieren(user, "nachtrag." + aenderung["status"], n["titel"], details={"nummer": n["nummer"], "auftraggeber": eigene["name"], "betrag_netto": n.get("betrag_netto")}, firma_id=n["firma_id"])
    return {"nachtrag": await _nachtrag_anreichern({**n, **aenderung})}


@router.post("/api/nachtraege/{nachtrag_id}/zurueckziehen")
async def nachtrag_zurueckziehen(nachtrag_id: str, user: dict = Depends(schreibend("mitarbeiter"))):
    n, z, rolle = await _laden("nachtraege", user, nachtrag_id)
    if rolle != "firma":
        raise HTTPException(403, "Zurückziehen kann nur die beauftragte Firma.")
    if n.get("status") not in ("entwurf", "eingereicht"):
        raise HTTPException(400, "Dieser Nachtrag ist bereits entschieden.")
    eigene = await firma_kurz(user["firma_id"])
    await db().nachtraege.update_one({"id": nachtrag_id}, {"$set": {"status": "zurueckgezogen", "updated_at": jetzt_iso()}, "$push": {"verlauf": _schritt(user, eigene["name"], "zurueckgezogen")}})
    await protokollieren(user, "nachtrag.zurueckgezogen", n["titel"], details={"nummer": n["nummer"]})
    return {"nachtrag": await _nachtrag_anreichern({**n, "status": "zurueckgezogen"})}


@router.post("/api/nachtraege/{nachtrag_id}/dokumente")
async def nachtrag_dokument(nachtrag_id: str, datei: UploadFile = File(...), note: str = Form(""), user: dict = Depends(schreibend("mitarbeiter"))):
    n, z, rolle = await _laden("nachtraege", user, nachtrag_id)
    meta = await datei_speichern(user["firma_id"], datei, user["id"])
    doc = {**meta, "firma_id": user["firma_id"], "scope": "nachtrag", "ref_id": nachtrag_id, "project_id": n["project_id"], "category": "Nachtrag", "note": note[:500],
           "uploaded_by": user["id"], "uploaded_by_name": user.get("name"), "created_at": jetzt_iso()}
    await db().documents.insert_one(dict(doc))
    doc.pop("path", None)
    return {"dokument": doc}


@router.get("/api/nachtraege/{nachtrag_id}/pdf")
async def nachtrag_pdf(nachtrag_id: str, user: dict = Depends(aktueller_nutzer)):
    import pdfs
    n, z, rolle = await _laden("nachtraege", user, nachtrag_id)
    ag = await firma_kurz(n["owner_firma_id"])
    an = await firma_kurz(n["firma_id"])
    pdf = pdfs.nachtrag_pdf(n, z["projekt"], ag, an, NACHTRAG_STATUS_NAMEN.get(n.get("status"), n.get("status")))
    return _datei(pdf, f"Nachtrag_{n['nummer']}.pdf", "application/pdf")


# ================================================================ Abnahmen

async def _maengel_snapshot(project_id: str, firma_id: str, ids: list[str]) -> list[dict]:
    filt = {"project_id": project_id, "firma_id": firma_id, "status": {"$ne": "abgenommen"}}
    if ids:
        filt = {"project_id": project_id, "id": {"$in": ids}}
    aus = []
    async for m in db().maengel.find(filt, {"_id": 0, "id": 1, "beschreibung": 1, "bereich": 1, "status": 1, "frist": 1}):
        aus.append({**m, "status_name": MANGEL_STATUS_NAMEN.get(m.get("status"), m.get("status"))})
    return aus


async def _abnahme_anreichern(a: dict) -> dict:
    a["status_name"] = ABNAHME_STATUS_NAMEN.get(a.get("status"), a.get("status"))
    a["art_name"] = ABNAHME_ART_NAMEN.get(a.get("art"), a.get("art"))
    a["ergebnis_name"] = ABNAHME_ERGEBNIS_NAMEN.get(a.get("ergebnis"), "") if a.get("ergebnis") else ""
    a["dokumente"] = await _dokumente("abnahme", a["id"])
    return a


@router.get("/api/projekte/{project_id}/abnahmen")
async def abnahmen_liste(project_id: str, user: dict = Depends(aktueller_nutzer)):
    z = await zugang(user, project_id)
    leitung = bool(z["eigentuemer"] and z["leitung"])
    if z["eigentuemer"] and not leitung:
        raise HTTPException(404, "Projekt nicht gefunden.")
    if not z["eigentuemer"] and not partner_leitung(z, user):
        raise HTTPException(404, "Projekt nicht gefunden.")
    filt = {"project_id": project_id} if leitung else {"project_id": project_id, "firma_id": user["firma_id"]}
    aus = [await _abnahme_anreichern(a) async for a in db().abnahmen.find(filt, {"_id": 0}).sort("created_at", -1)]
    firmen = []
    if leitung:
        async for b in db().beteiligungen.find({"project_id": project_id, "status": "aktiv"}, {"_id": 0, "firma_id": 1, "firma_name": 1, "gewerk": 1}):
            offen = await db().maengel.count_documents({"project_id": project_id, "firma_id": b["firma_id"], "status": {"$ne": "abgenommen"}})
            firmen.append({"id": b["firma_id"], "name": b.get("firma_name"), "gewerk": b.get("gewerk"), "maengel_offen": offen})
    return {"abnahmen": aus, "firmen": firmen, "arten": ABNAHME_ART_NAMEN, "ergebnisse": ABNAHME_ERGEBNIS_NAMEN, "status": ABNAHME_STATUS_NAMEN, "rolle": "leitung" if leitung else "firma"}


@router.post("/api/projekte/{project_id}/abnahmen")
async def abnahme_anlegen(project_id: str, body: AbnahmeIn, user: dict = Depends(schreibend("mitarbeiter"))):
    z = await zugang(user, project_id)
    p = z["projekt"]
    if body.datum:
        datum_pruefen(body.datum)
    if body.nachbesserung_bis:
        datum_pruefen(body.nachbesserung_bis)
    eigene = await firma_kurz(user["firma_id"])
    if z["eigentuemer"]:
        if not z["leitung"]:
            raise HTTPException(403, "Das darf nur die Projektleitung.")
        if not body.firma_id:
            raise HTTPException(400, "Bitte die beauftragte Firma angeben.")
        b = await _beteiligung(project_id, body.firma_id)
        status, firma_id = "entwurf", body.firma_id
        maengel = await _maengel_snapshot(project_id, firma_id, body.maengel_ids or [])
    else:
        if not partner_leitung(z, user):
            raise HTTPException(403, "Das darf nur Büro, Inhaber oder die Projektleitung eurer Firma.")
        b = z["beteiligung"]
        status, firma_id = "angefordert", user["firma_id"]
        maengel = []
    a = {"id": neue_id(), "nummer": await _nummer("abnahmen", project_id, "A"), "project_id": project_id, "owner_firma_id": p["firma_id"], "firma_id": firma_id,
         "firma_name": b.get("firma_name"), "beteiligung_id": b["id"], "art": body.art, "gewerk": (body.gewerk or b.get("gewerk") or "")[:60], "bereich": (body.bereich or "")[:120],
         "datum": body.datum or lokal_jetzt().date().isoformat(), "teilnehmer": (body.teilnehmer or "")[:500], "ergebnis": body.ergebnis if status == "entwurf" else None,
         "vorbehalte": (body.vorbehalte or "")[:4000], "nachbesserung_bis": body.nachbesserung_bis or None, "bemerkung": (body.bemerkung or "")[:2000], "maengel": maengel,
         "status": status, "antwort": None, "erstellt_von": {"id": user["id"], "name": user.get("name"), "firma_id": user["firma_id"], "firma_name": eigene["name"]},
         "abgeschlossen_at": None, "verlauf": [_schritt(user, eigene["name"], status, body.bemerkung or "")], "created_at": jetzt_iso(), "updated_at": jetzt_iso()}
    await db().abnahmen.insert_one(dict(a))
    if status == "angefordert":
        await eigentuemer_benachrichtigen(p, "abnahme_angefordert", f"{eigene['name']} bittet um {ABNAHME_ART_NAMEN.get(a['art'], 'Abnahme')} ({a['gewerk'] or 'Leistung'}) im Projekt „{p['name']}“{' zum ' + a['datum'] if body.datum else ''}.", f"/projekte/{p['id']}")
        await mail.firma_informieren(p["firma_id"], f"Abnahme angefordert – {p['name']}", f"{eigene['name']} bittet um {ABNAHME_ART_NAMEN.get(a['art'], 'Abnahme')} im Projekt „{p['name']}“.\n{a['bemerkung']}\n\nZum Projekt: {mail.link('/projekte/' + p['id'])}", "abnahme", a["id"], project_id)
    await protokollieren(user, "abnahme.angelegt", p["name"], details={"nummer": a["nummer"], "status": status, "firma": a["firma_name"]})
    return {"abnahme": await _abnahme_anreichern(a)}


@router.get("/api/abnahmen/{abnahme_id}")
async def abnahme_lesen(abnahme_id: str, user: dict = Depends(aktueller_nutzer)):
    a, z, rolle = await _laden("abnahmen", user, abnahme_id)
    offen = await _maengel_snapshot(a["project_id"], a["firma_id"], []) if rolle == "leitung" and a.get("status") in ("angefordert", "entwurf") else []
    return {"abnahme": await _abnahme_anreichern(a), "rolle": rolle, "maengel_offen": offen, "projekt": {"id": z["projekt"]["id"], "name": z["projekt"]["name"]}}


@router.put("/api/abnahmen/{abnahme_id}")
async def abnahme_aendern(abnahme_id: str, body: AbnahmeIn, user: dict = Depends(schreibend("mitarbeiter"))):
    a, z, rolle = await _laden("abnahmen", user, abnahme_id)
    if rolle != "leitung":
        raise HTTPException(403, "Das Protokoll führt die Projektleitung des Auftraggebers.")
    if a.get("status") not in ("angefordert", "entwurf"):
        raise HTTPException(400, "Eine erstellte Abnahme lässt sich nicht mehr ändern.")
    if body.datum:
        datum_pruefen(body.datum)
    if body.nachbesserung_bis:
        datum_pruefen(body.nachbesserung_bis)
    aenderung = {"art": body.art, "gewerk": (body.gewerk or a.get("gewerk") or "")[:60], "bereich": (body.bereich or "")[:120], "datum": body.datum or a.get("datum"),
                 "teilnehmer": (body.teilnehmer or "")[:500], "ergebnis": body.ergebnis, "vorbehalte": (body.vorbehalte or "")[:4000], "nachbesserung_bis": body.nachbesserung_bis or None,
                 "bemerkung": (body.bemerkung or "")[:2000], "maengel": await _maengel_snapshot(a["project_id"], a["firma_id"], body.maengel_ids or []), "status": "entwurf", "updated_at": jetzt_iso()}
    await db().abnahmen.update_one({"id": abnahme_id}, {"$set": aenderung})
    return {"abnahme": await _abnahme_anreichern({**a, **aenderung})}


@router.post("/api/abnahmen/{abnahme_id}/abschliessen")
async def abnahme_abschliessen(abnahme_id: str, user: dict = Depends(schreibend("mitarbeiter"))):
    a, z, rolle = await _laden("abnahmen", user, abnahme_id)
    if rolle != "leitung":
        raise HTTPException(403, "Abschließen darf nur die Projektleitung des Auftraggebers.")
    if a.get("status") not in ("angefordert", "entwurf"):
        raise HTTPException(400, "Diese Abnahme ist bereits erstellt.")
    if not a.get("ergebnis"):
        raise HTTPException(400, "Bitte zuerst das Ergebnis der Abnahme eintragen.")
    if a["ergebnis"] == "abgenommen_mit_maengeln" and not a.get("maengel"):
        raise HTTPException(400, "Für eine Abnahme unter Vorbehalt bitte mindestens einen Mangel aufnehmen.")
    eigene = await firma_kurz(user["firma_id"])
    aenderung = {"status": "erstellt", "abgeschlossen_at": jetzt_iso(), "updated_at": jetzt_iso()}
    await db().abnahmen.update_one({"id": abnahme_id}, {"$set": aenderung, "$push": {"verlauf": _schritt(user, eigene["name"], "erstellt")}})
    b = await db().beteiligungen.find_one({"id": a["beteiligung_id"]}, {"_id": 0})
    p = z["projekt"]
    text = f"{eigene['name']} hat das Abnahmeprotokoll {a['nummer']} ({ABNAHME_ERGEBNIS_NAMEN.get(a['ergebnis'], a['ergebnis'])}) im Projekt „{p['name']}“ erstellt – bitte bestätigen oder widersprechen."
    link = await _partner_link(b) if b else "/zusammenarbeit"
    await benachrichtigen(a["firma_id"], "abnahme_erstellt", text, link)
    await mail.firma_informieren(a["firma_id"], f"Abnahmeprotokoll {a['nummer']} – {p['name']}", text + f"\n\nZum Projekt: {mail.link(link)}", "abnahme", abnahme_id, p["id"])
    await protokollieren(user, "abnahme.erstellt", p["name"], details={"nummer": a["nummer"], "ergebnis": a["ergebnis"], "firma": a["firma_name"], "maengel": len(a.get("maengel") or [])})
    await protokollieren(user, "abnahme.erhalten", p["name"], details={"nummer": a["nummer"], "ergebnis": a["ergebnis"], "auftraggeber": eigene["name"]}, firma_id=a["firma_id"])
    return {"abnahme": await _abnahme_anreichern({**a, **aenderung})}


@router.post("/api/abnahmen/{abnahme_id}/antwort")
async def abnahme_antwort(abnahme_id: str, body: AbnahmeAntwortIn, user: dict = Depends(schreibend("mitarbeiter"))):
    a, z, rolle = await _laden("abnahmen", user, abnahme_id)
    if rolle != "firma":
        raise HTTPException(403, "Bestätigen oder widersprechen kann nur die beauftragte Firma.")
    if a.get("status") != "erstellt":
        raise HTTPException(400, "Nur ein erstelltes Protokoll lässt sich beantworten.")
    if not body.bestaetigen and not (body.kommentar or "").strip():
        raise HTTPException(400, "Bitte den Widerspruch begründen.")
    eigene = await firma_kurz(user["firma_id"])
    status = "bestaetigt" if body.bestaetigen else "widersprochen"
    antwort = {"bestaetigt": bool(body.bestaetigen), "kommentar": (body.kommentar or "").strip()[:2000], "user_id": user["id"], "user_name": user.get("name"), "at": jetzt_iso()}
    await db().abnahmen.update_one({"id": abnahme_id}, {"$set": {"status": status, "antwort": antwort, "updated_at": jetzt_iso()}, "$push": {"verlauf": _schritt(user, eigene["name"], status, body.kommentar or "")}})
    p = z["projekt"]
    text = f"{eigene['name']} hat das Abnahmeprotokoll {a['nummer']} {'bestätigt' if body.bestaetigen else 'widersprochen'}{(': ' + antwort['kommentar']) if antwort['kommentar'] else ''}."
    await eigentuemer_benachrichtigen(p, "abnahme_" + status, text, f"/projekte/{p['id']}")
    await mail.firma_informieren(p["firma_id"], f"Abnahme {a['nummer']} {'bestätigt' if body.bestaetigen else 'widersprochen'} – {p['name']}", text + f"\n\nZum Projekt: {mail.link('/projekte/' + p['id'])}", "abnahme", abnahme_id, p["id"])
    await protokollieren(user, "abnahme." + status, p["name"], details={"nummer": a["nummer"], "kommentar": antwort["kommentar"]})
    await protokollieren(user, "abnahme." + status, p["name"], details={"nummer": a["nummer"], "firma": eigene["name"], "kommentar": antwort["kommentar"]}, firma_id=p["firma_id"])
    return {"abnahme": await _abnahme_anreichern({**a, "status": status, "antwort": antwort})}


@router.post("/api/abnahmen/{abnahme_id}/dokumente")
async def abnahme_dokument(abnahme_id: str, datei: UploadFile = File(...), note: str = Form(""), user: dict = Depends(schreibend("mitarbeiter"))):
    a, z, rolle = await _laden("abnahmen", user, abnahme_id)
    meta = await datei_speichern(user["firma_id"], datei, user["id"])
    doc = {**meta, "firma_id": user["firma_id"], "scope": "abnahme", "ref_id": abnahme_id, "project_id": a["project_id"], "category": "Abnahme", "note": note[:500],
           "uploaded_by": user["id"], "uploaded_by_name": user.get("name"), "created_at": jetzt_iso()}
    await db().documents.insert_one(dict(doc))
    doc.pop("path", None)
    return {"dokument": doc}


@router.get("/api/abnahmen/{abnahme_id}/pdf")
async def abnahme_pdf(abnahme_id: str, user: dict = Depends(aktueller_nutzer)):
    import pdfs
    a, z, rolle = await _laden("abnahmen", user, abnahme_id)
    ag = await firma_kurz(a["owner_firma_id"])
    an = await firma_kurz(a["firma_id"])
    pdf = pdfs.abnahme_pdf(a, z["projekt"], ag, an, ABNAHME_ART_NAMEN.get(a.get("art"), ""), ABNAHME_ERGEBNIS_NAMEN.get(a.get("ergebnis"), ""), ABNAHME_STATUS_NAMEN.get(a.get("status"), ""))
    return _datei(pdf, f"Abnahmeprotokoll_{a['nummer']}.pdf", "application/pdf")


async def dokument_zugang(user: dict, scope: str, ref_id: str) -> None:
    """Dateizugriff für die Scopes nachtrag / abnahme – über den Eintrag selbst (404 ohne Zugang)."""
    if scope == "nachtrag":
        await _laden("nachtraege", user, ref_id)
    elif scope == "abnahme":
        await _laden("abnahmen", user, ref_id)
    else:
        raise HTTPException(404, "Dokument nicht gefunden.")


def ist_buero_oder_leitung(user: dict) -> bool:
    return hat_rolle(user, "buero")


async def firma_anschrift(firma_id: str) -> dict:
    """Für PDFs: Name und Anschrift (ohne Lizenz- oder Bankdaten)."""
    f = await firma_laden(firma_id)
    return {k: f.get(k) for k in ("id", "name", "street", "zip_code", "city", "email", "phone")}
