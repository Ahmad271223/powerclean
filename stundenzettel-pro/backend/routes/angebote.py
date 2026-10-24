"""Kundenangebote: Anfrage → Entwurf → gesendet (PDF-Snapshot, E-Mail mit Anhang und Antwortlink) → Annahme/Ablehnung → Auftrag (Projekt).
Vorlagen, Kopien, Versionen, interne Kalkulation (Recht „kalkulation“), öffentlicher Antwortlink für den Kunden."""
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response

import angebote as ang
import config
import mail
import pdfs
from auth import aktueller_nutzer, firma_laden, firmenabo_noetig, hat_recht, jetzt_iso, recht_noetig
from db import db
from gemeinsam import kunde_laden, kundenadresse, neue_id, nutzernamen, projekt_laden, projekt_normalisieren
from models import (AngebotAnnahmeIn, AngebotAntwortIn, AngebotAuftragIn, AngebotGrundIn, AngebotKundeIn, AngebotSendenIn, AngebotVorlageIn, KalkulationIn,
                    ProjektIn)
from plattform import benachrichtigen
from protokoll import protokollieren
from zeiten import datum_pruefen, lokal_jetzt

router = APIRouter(tags=["Kundenangebote"])
LISTENFELDER = {"_id": 0, "verlauf": 0, "versand": 0, "einleitung": 0, "schluss": 0, "zahlungsbedingungen": 0, "intern": 0}


async def _firma(user: dict) -> dict:
    return user.get("_firma") or await firma_laden(user["firma_id"])


async def _laden(user: dict, angebot_id: str) -> dict:
    a = await db().kundenangebote.find_one({"id": angebot_id, "firma_id": user["firma_id"]}, {"_id": 0})
    if not a:
        raise HTTPException(404, "Angebot nicht gefunden.")
    if ang.abgelaufen(a):
        aenderung = {"status": "abgelaufen", "verlauf": (a.get("verlauf") or []) + [ang.schritt(None, "abgelaufen", f"Gültigkeit bis {a.get('gueltig_bis')} verstrichen")]}
        await db().kundenangebote.update_one({"id": a["id"]}, {"$set": aenderung})
        a.update(aenderung)
    return a


def _bearbeitbar(a: dict) -> None:
    if a.get("status") not in ("anfrage", "entwurf"):
        raise HTTPException(409, f"Das Angebot ist „{ang.STATUS_NAMEN.get(a.get('status'), a.get('status'))}“ und wird nicht mehr geändert. Lege eine neue Version an.")


def _kalkulation_normalisieren(k: Optional[dict]) -> Optional[dict]:
    if not k:
        return None
    aus = {}
    for f in ang.KALKULATION_FELDER:
        v = k.get(f)
        if v in (None, ""):
            continue
        try:
            aus[f] = max(0.0, float(v))
        except (TypeError, ValueError):
            continue
    return aus or None


def _positionen_normalisieren(positionen: list, alte: Optional[list[dict]] = None) -> list[dict]:
    """Eingaben in die gespeicherte Form bringen; die Kalkulation bleibt erhalten, wenn die Oberfläche sie nicht mitschickt."""
    alt = {p.get("id"): p for p in (alte or [])}
    aus = []
    for p in positionen:
        d = p.model_dump() if hasattr(p, "model_dump") else dict(p)
        pid = d.get("id") or neue_id()
        kalk = _kalkulation_normalisieren(d.get("kalkulation")) if "kalkulation" in d and d.get("kalkulation") is not None else (alt.get(pid) or {}).get("kalkulation")
        aus.append({"id": pid, "art": d.get("art") or "leistung", "text": (d.get("text") or "").strip()[:300], "beschreibung": (d.get("beschreibung") or "")[:4000],
                    "menge": float(d.get("menge") or 0), "einheit": (d.get("einheit") or "Stk.")[:20], "einzelpreis": float(d.get("einzelpreis") or 0),
                    "rabatt_prozent": float(d.get("rabatt_prozent") or 0), "alternativ": bool(d.get("alternativ")), "eventual": bool(d.get("eventual")),
                    "leistung_id": d.get("leistung_id") or None, "artikel_id": d.get("artikel_id") or None, "import_nr": (d.get("import_nr") or "")[:40], "kalkulation": kalk})
    return aus


async def _artikel_vorbelegen(firma_id: str, positionen: list[dict]) -> list[dict]:
    """Positionen aus dem Artikelstamm: Einkaufspreis × Menge als Material-Einkauf in die Kalkulation übernehmen, solange keine eigene Angabe da ist."""
    for p in positionen:
        if not p.get("artikel_id") or (p.get("kalkulation") or {}).get("material_ek") not in (None, ""):
            continue
        a = await db().artikel.find_one({"id": p["artikel_id"], "firma_id": firma_id}, {"_id": 0, "einkaufspreis": 1})
        if a and a.get("einkaufspreis") is not None:
            p["kalkulation"] = {**(p.get("kalkulation") or {}), "material_ek": ang.rund(float(a["einkaufspreis"]) * float(p.get("menge") or 0))}
    return positionen


def _berechnen(a: dict, firma: dict) -> dict:
    steuer = ang.steuer_bestimmen(firma, a.get("kunde"), a.get("reverse_charge"))
    s = ang.summen(a.get("positionen") or [], a.get("zuschlaege") or [], a.get("rabatt_prozent") or 0, steuer)
    a["positionen"] = s.pop("positionen")
    a["summen"] = s
    return a


async def _kunde_setzen(user: dict, a: dict, body: AngebotKundeIn) -> None:
    if body.customer_id:
        k = await kunde_laden(user["firma_id"], body.customer_id)
        if not k:
            raise HTTPException(404, "Kunde nicht gefunden.")
        a["customer_id"], a["kunde"] = k["id"], ang.kunden_snapshot(k)
    elif body.kunde_frei is not None:
        a["customer_id"], a["kunde"] = None, ang.kunden_snapshot(None, body.kunde_frei)
    elif "kunde" not in a:
        a["customer_id"], a["kunde"] = None, ang.kunden_snapshot(None, {})


async def _projekt_setzen(user: dict, a: dict, project_id: Optional[str]) -> None:
    if not project_id:
        a["project_id"], a["projekt_name"] = None, ""
        return
    p = await projekt_laden(user, project_id)
    a["project_id"], a["projekt_name"] = p["id"], p.get("name") or ""
    if not a.get("customer_id") and p.get("customer_id") and not (a.get("kunde") or {}).get("name"):
        k = await kunde_laden(user["firma_id"], p["customer_id"])
        if k:
            a["customer_id"], a["kunde"] = k["id"], ang.kunden_snapshot(k)


def _texte_aus_firma(firma: dict) -> dict:
    return {"einleitung": firma.get("angebot_einleitung") or "", "schluss": firma.get("angebot_schluss") or "",
            "zahlungsbedingungen": firma.get("angebot_zahlungsbedingungen") or ""}


async def _pdf_bytes(firma: dict, a: dict) -> bytes:
    pfad = a.get("pdf_pfad")
    if pfad and a.get("status") not in ("anfrage", "entwurf"):
        try:
            return (config.DATA_DIR / pfad).read_bytes()
        except OSError:
            pass
    return pdfs.angebot_pdf(ang.pdf_daten(firma, a))


def _pdf_antwort(inhalt: bytes, a: dict) -> Response:
    name = f"Angebot_{a.get('nummer', '')}".replace("/", "-") + (f"_v{a.get('version')}" if int(a.get("version") or 1) > 1 else "") + ".pdf"
    return Response(content=inhalt, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{name}"'})


# ---------------------------------------------------------------- Vorlagen (vor /{id}, sonst fängt die Detailroute „vorlagen“)

@router.get("/api/kundenangebote/vorlagen")
async def vorlagen(user: dict = Depends(recht_noetig("angebote"))):
    return {"vorlagen": [v async for v in db().angebotsvorlagen.find({"firma_id": user["firma_id"]}, {"_id": 0}).sort("name", 1)]}


@router.post("/api/kundenangebote/vorlagen")
async def vorlage_anlegen(body: AngebotVorlageIn, user: dict = Depends(firmenabo_noetig("buero", "angebote"))):
    v = {**body.model_dump(), "id": neue_id(), "firma_id": user["firma_id"], "created_at": jetzt_iso(), "created_by": user["id"]}
    v["positionen"] = _positionen_normalisieren(body.positionen)
    await db().angebotsvorlagen.insert_one(dict(v))
    await protokollieren(user, "angebotsvorlage.angelegt", v["name"])
    return {"vorlage": v}


@router.put("/api/kundenangebote/vorlagen/{vorlage_id}")
async def vorlage_aendern(vorlage_id: str, body: AngebotVorlageIn, user: dict = Depends(firmenabo_noetig("buero", "angebote"))):
    v = await db().angebotsvorlagen.find_one({"id": vorlage_id, "firma_id": user["firma_id"]}, {"_id": 0})
    if not v:
        raise HTTPException(404, "Vorlage nicht gefunden.")
    neu = {**v, **body.model_dump(), "positionen": _positionen_normalisieren(body.positionen, v.get("positionen")), "updated_at": jetzt_iso()}
    await db().angebotsvorlagen.update_one({"id": vorlage_id}, {"$set": {k: val for k, val in neu.items() if k != "id"}})
    return {"vorlage": neu}


@router.delete("/api/kundenangebote/vorlagen/{vorlage_id}")
async def vorlage_loeschen(vorlage_id: str, user: dict = Depends(firmenabo_noetig("buero", "angebote"))):
    r = await db().angebotsvorlagen.delete_one({"id": vorlage_id, "firma_id": user["firma_id"]})
    if not r.deleted_count:
        raise HTTPException(404, "Vorlage nicht gefunden.")
    return {"ok": True}


# ---------------------------------------------------------------- Liste und Anlage

@router.get("/api/kundenangebote")
async def liste(status: Optional[str] = None, project_id: Optional[str] = None, customer_id: Optional[str] = None, alle: bool = False,
                limit: int = Query(500, ge=1, le=3000), user: dict = Depends(recht_noetig("angebote"))):
    filt: dict = {"firma_id": user["firma_id"]}
    if status:
        filt["status"] = status
    elif not alle:
        filt["status"] = {"$ne": "ersetzt"}
    if project_id:
        filt["project_id"] = project_id
    if customer_id:
        filt["customer_id"] = customer_id
    heute = date.today().isoformat()
    aus, zaehler, offen_netto, angenommen_netto = [], {}, 0.0, 0.0
    async for a in db().kundenangebote.find(filt, LISTENFELDER).sort([("jahr", -1), ("seq", -1), ("version", -1)]).limit(limit):
        if ang.abgelaufen(a, heute):
            a["status"] = "abgelaufen"
        a["status_name"] = ang.STATUS_NAMEN.get(a["status"], a["status"])
        a["netto"] = (a.get("summen") or {}).get("netto", 0)
        a["brutto"] = (a.get("summen") or {}).get("brutto", 0)
        a["kunde_name"] = (a.get("kunde") or {}).get("name", "")
        a.pop("positionen", None)
        a.pop("summen", None)
        a.pop("kalkulation", None)
        zaehler[a["status"]] = zaehler.get(a["status"], 0) + 1
        if a["status"] in ("entwurf", "gesendet"):
            offen_netto += float(a["netto"] or 0)
        elif a["status"] == "angenommen":
            angenommen_netto += float(a["netto"] or 0)
        aus.append(a)
    return {"angebote": aus, "zaehler": zaehler, "offen_netto": ang.rund(offen_netto), "angenommen_netto": ang.rund(angenommen_netto),
            "status_namen": ang.STATUS_NAMEN, "positionsarten": ang.POSITIONSARTEN, "einheiten": ang.EINHEITEN}


@router.post("/api/kundenangebote")
async def anlegen(body: AngebotKundeIn, user: dict = Depends(firmenabo_noetig("buero", "angebote"))):
    firma = await _firma(user)
    heute = lokal_jetzt().date()
    jahr = int((body.datum or heute.isoformat())[:4])
    a: dict = {"id": neue_id(), "firma_id": user["firma_id"], "status": body.status or "entwurf", "version": 1, "vorgaenger_id": None, "ersetzt_durch": None,
               "titel": (body.titel or "").strip(), "datum": body.datum or heute.isoformat(), "anfrage": body.anfrage or None,
               "zuschlaege": [z.model_dump() for z in body.zuschlaege], "rabatt_prozent": body.rabatt_prozent, "reverse_charge": body.reverse_charge,
               "intern": body.intern or "", "token": None, "pdf_pfad": None, "versand": [], "annahme": None, "ablehnung": None, "auftrag": None,
               "created_by": user["id"], "created_by_name": user.get("name"), "created_at": jetzt_iso(), "updated_at": jetzt_iso(),
               **_texte_aus_firma(firma)}
    if body.vorlage_id:
        v = await db().angebotsvorlagen.find_one({"id": body.vorlage_id, "firma_id": user["firma_id"]}, {"_id": 0})
        if not v:
            raise HTTPException(404, "Vorlage nicht gefunden.")
        a.update({"titel": a["titel"] or v.get("titel") or "", "einleitung": v.get("einleitung") or a["einleitung"], "schluss": v.get("schluss") or a["schluss"],
                  "zahlungsbedingungen": v.get("zahlungsbedingungen") or a["zahlungsbedingungen"], "positionen": v.get("positionen") or [],
                  "zuschlaege": v.get("zuschlaege") or [], "rabatt_prozent": float(v.get("rabatt_prozent") or 0)})
        if v.get("gueltig_tage"):
            a["gueltig_bis"] = ang.gueltig_bis_standard({"angebot_gueltig_tage": v["gueltig_tage"]}, a["datum"])
    for feld in ("einleitung", "schluss", "zahlungsbedingungen"):
        if getattr(body, feld) is not None:
            a[feld] = getattr(body, feld)
    if body.positionen or not body.vorlage_id:
        a["positionen"] = await _artikel_vorbelegen(user["firma_id"], _positionen_normalisieren(body.positionen))
    a["gueltig_bis"] = body.gueltig_bis or a.get("gueltig_bis") or ang.gueltig_bis_standard(firma, a["datum"])
    await _kunde_setzen(user, a, body)
    await _projekt_setzen(user, a, body.project_id)
    for _ in range(6):
        seq = await ang.naechste_nummer(user["firma_id"], jahr)
        a.update({"jahr": jahr, "seq": seq, "nummer": f"{firma.get('angebot_prefix') or 'AN-'}{jahr}-{seq:04d}"})
        try:
            await db().kundenangebote.insert_one(dict(_berechnen(a, firma)))
            break
        except Exception as exc:  # noqa: BLE001 – Doppelte Nummer (seltener Wettlauf): nächste Nummer versuchen
            if "duplicate" not in str(exc).lower():
                raise
    else:
        raise HTTPException(503, "Angebotsnummer konnte nicht vergeben werden, bitte noch einmal versuchen.")
    a["verlauf"] = [ang.schritt(user, "angelegt", "aus Vorlage" if body.vorlage_id else "")]
    await db().kundenangebote.update_one({"id": a["id"]}, {"$set": {"verlauf": a["verlauf"]}})
    await protokollieren(user, "angebot.angelegt", a["nummer"], details={"titel": a["titel"], "status": a["status"]})
    return {"angebot": ang.fuer_nutzer(a, user, firma)}


# ---------------------------------------------------------------- Einzelnes Angebot

@router.get("/api/kundenangebote/{angebot_id}")
async def lesen(angebot_id: str, user: dict = Depends(recht_noetig("angebote"))):
    a = await _laden(user, angebot_id)
    firma = await _firma(user)
    versionen = [v async for v in db().kundenangebote.find({"firma_id": user["firma_id"], "nummer": a["nummer"]}, {"_id": 0, "id": 1, "version": 1, "status": 1, "datum": 1}).sort("version", 1)]
    projekt = await db().projects.find_one({"id": a.get("project_id"), "firma_id": user["firma_id"]}, {"_id": 0, "id": 1, "name": 1, "auftrag": 1}) if a.get("project_id") else None
    return {"angebot": ang.fuer_nutzer(a, user, firma), "versionen": versionen, "projekt": projekt,
            "antwortlink": mail.link(f"/angebot/{a['token']}") if a.get("token") else None, "status_namen": ang.STATUS_NAMEN,
            "positionsarten": ang.POSITIONSARTEN, "einheiten": ang.EINHEITEN, "kann_kalkulation": hat_recht(user, "kalkulation")}


@router.put("/api/kundenangebote/{angebot_id}")
async def aendern(angebot_id: str, body: AngebotKundeIn, user: dict = Depends(firmenabo_noetig("buero", "angebote"))):
    a = await _laden(user, angebot_id)
    _bearbeitbar(a)
    firma = await _firma(user)
    felder = body.model_dump(exclude_unset=True)
    for feld in ("titel", "datum", "gueltig_bis", "anfrage", "einleitung", "schluss", "zahlungsbedingungen", "rabatt_prozent", "reverse_charge", "intern"):
        if feld in felder:
            a[feld] = felder[feld] if feld != "titel" else (felder[feld] or "").strip()
    if "zuschlaege" in felder:
        a["zuschlaege"] = [z.model_dump() for z in body.zuschlaege]
    if "positionen" in felder:
        a["positionen"] = await _artikel_vorbelegen(user["firma_id"], _positionen_normalisieren(body.positionen, a.get("positionen")))
    if "customer_id" in felder or "kunde_frei" in felder:
        await _kunde_setzen(user, a, body)
    if "project_id" in felder:
        await _projekt_setzen(user, a, body.project_id)
    if body.status == "entwurf" and a["status"] == "anfrage":
        a["status"] = "entwurf"
        a["verlauf"] = (a.get("verlauf") or []) + [ang.schritt(user, "entwurf", "Angebot wird ausgearbeitet")]
    if a.get("datum"):
        datum_pruefen(a["datum"])
    if a.get("gueltig_bis"):
        datum_pruefen(a["gueltig_bis"])
    a["updated_at"] = jetzt_iso()
    _berechnen(a, firma)
    await db().kundenangebote.update_one({"id": a["id"]}, {"$set": {k: v for k, v in a.items() if k != "id"}})
    return {"angebot": ang.fuer_nutzer(a, user, firma)}


@router.delete("/api/kundenangebote/{angebot_id}")
async def loeschen(angebot_id: str, user: dict = Depends(firmenabo_noetig("buero", "angebote"))):
    a = await _laden(user, angebot_id)
    _bearbeitbar(a)
    await db().kundenangebote.delete_one({"id": a["id"]})
    if a.get("vorgaenger_id"):   # die vorherige Version wird wieder die aktuelle
        await db().kundenangebote.update_one({"id": a["vorgaenger_id"]}, {"$set": {"ersetzt_durch": None, "status": a.get("vorgaenger_status") or "gesendet"}})
    await protokollieren(user, "angebot.geloescht", a["nummer"], details={"version": a.get("version")})
    return {"ok": True, "hinweis": "Die Angebotsnummer wird nicht noch einmal vergeben."}


@router.post("/api/kundenangebote/{angebot_id}/kopieren")
async def kopieren(angebot_id: str, user: dict = Depends(firmenabo_noetig("buero", "angebote"))):
    a = await _laden(user, angebot_id)
    body = AngebotKundeIn(titel=a.get("titel") or "", customer_id=a.get("customer_id"), kunde_frei=None if a.get("customer_id") else a.get("kunde"), project_id=a.get("project_id"),
                          einleitung=a.get("einleitung"), schluss=a.get("schluss"), zahlungsbedingungen=a.get("zahlungsbedingungen"),
                          positionen=[{k: v for k, v in p.items() if k not in ("nr", "gesamt", "zaehlt")} for p in a.get("positionen") or []],
                          zuschlaege=a.get("zuschlaege") or [], rabatt_prozent=float(a.get("rabatt_prozent") or 0), reverse_charge=a.get("reverse_charge"), intern=a.get("intern") or "")
    r = await anlegen(body, user)
    await db().kundenangebote.update_one({"id": r["angebot"]["id"]}, {"$push": {"verlauf": ang.schritt(user, "kopiert", f"Kopie von {a['nummer']}")}})
    return r


@router.post("/api/kundenangebote/{angebot_id}/als-vorlage")
async def als_vorlage(angebot_id: str, body: AngebotVorlageIn, user: dict = Depends(firmenabo_noetig("buero", "angebote"))):
    a = await _laden(user, angebot_id)
    v = {"id": neue_id(), "firma_id": user["firma_id"], "name": body.name, "titel": body.titel or a.get("titel") or "", "einleitung": a.get("einleitung") or "",
         "schluss": a.get("schluss") or "", "zahlungsbedingungen": a.get("zahlungsbedingungen") or "", "gueltig_tage": body.gueltig_tage,
         "positionen": [{k: val for k, val in p.items() if k not in ("nr", "gesamt", "zaehlt")} for p in a.get("positionen") or []],
         "zuschlaege": a.get("zuschlaege") or [], "rabatt_prozent": float(a.get("rabatt_prozent") or 0), "created_at": jetzt_iso(), "created_by": user["id"]}
    await db().angebotsvorlagen.insert_one(dict(v))
    await protokollieren(user, "angebotsvorlage.angelegt", v["name"], details={"aus": a["nummer"]})
    return {"vorlage": v}


@router.post("/api/kundenangebote/{angebot_id}/positionen/datei")
async def positionen_datei(angebot_id: str, datei: UploadFile = File(...), vorschau: str = Form("0"), modus: str = Form("ersetzen"), user: dict = Depends(firmenabo_noetig("buero", "angebote"))):
    """Positionen aus CSV, Excel oder GAEB X83 in einen Angebotsentwurf übernehmen (Titel bleiben Titel) – mit Vorschau und Fehlerzeilen."""
    import importe
    a = await _laden(user, angebot_id)
    _bearbeitbar(a)
    try:
        ergebnis = importe.positionen_aus_datei(await datei.read(), datei.filename or "")
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    neu = []
    for p in ergebnis["positionen"]:
        art = p.get("art") or "leistung"
        neu.append({"art": art if art in ang.POSITIONSARTEN else "leistung", "text": p.get("leistung") or p.get("text") or "", "beschreibung": p.get("beschreibung") or "", "menge": float(p.get("menge") or 0) if art not in ("titel", "text") else 0,
                    "einheit": p.get("einheit") or "Stk.", "einzelpreis": float(p.get("einzelpreis") or 0), "rabatt_prozent": 0, "alternativ": bool(p.get("alternativ")), "eventual": bool(p.get("eventual")), "import_nr": p.get("nr") or ""})
    if vorschau == "1" or not neu:
        return {"positionen": neu, "fehler": ergebnis["fehler"], "quelle": ergebnis.get("quelle"), "vorschau": True}
    firma = await _firma(user)
    bestehend = a.get("positionen") or [] if modus == "anhaengen" else []
    a["positionen"] = bestehend + _positionen_normalisieren(neu)
    a["verlauf"] = (a.get("verlauf") or []) + [ang.schritt(user, "import", f"{len(neu)} Positionen aus {ergebnis.get('quelle')} ({modus})")]
    a["updated_at"] = jetzt_iso()
    _berechnen(a, firma)
    await db().kundenangebote.update_one({"id": a["id"]}, {"$set": {k: v for k, v in a.items() if k != "id"}})
    return {"angebot": ang.fuer_nutzer(a, user, firma), "fehler": ergebnis["fehler"], "quelle": ergebnis.get("quelle"), "vorschau": False}


@router.get("/api/kundenangebote/{angebot_id}/angebot.x84")
async def angebot_x84(angebot_id: str, user: dict = Depends(recht_noetig("angebote"))):
    """Kundenangebot als GAEB DA XML X84 (Angebotsabgabe) – für Auftraggeber, die ein X83 geschickt haben."""
    import gaeb
    a = await _laden(user, angebot_id)
    firma = await _firma(user)
    positionen = [{"nr": p.get("import_nr") or p.get("nr"), "leistung": p.get("text"), "beschreibung": p.get("beschreibung"), "menge": p.get("menge"), "einheit": p.get("einheit"), "einzelpreis": p.get("einzelpreis"), "art": p.get("art")}
                  for p in a.get("positionen") or [] if not p.get("alternativ") and not p.get("eventual")]
    inhalt = gaeb.schreiben(positionen, "84", {"titel": a.get("titel") or a.get("nummer"), "projekt": a.get("projekt_name") or a.get("titel"), "auftraggeber": (a.get("kunde") or {}).get("name"), "bieter": firma.get("name")})
    return Response(content=inhalt, media_type="application/xml", headers={"Content-Disposition": f'attachment; filename="Angebot_{a.get("nummer", "")}.x84"'})


@router.get("/api/kundenangebote/{angebot_id}/angebot.pdf")
async def angebot_pdf(angebot_id: str, user: dict = Depends(recht_noetig("angebote"))):
    a = await _laden(user, angebot_id)
    firma = await _firma(user)
    return _pdf_antwort(await _pdf_bytes(firma, a), a)


# ---------------------------------------------------------------- Senden, Versionen, Antworten, Auftrag

@router.post("/api/kundenangebote/{angebot_id}/senden")
async def senden(angebot_id: str, body: AngebotSendenIn, user: dict = Depends(firmenabo_noetig("buero", "angebote"))):
    """Angebot festschreiben (PDF-Snapshot), Antwortlink erzeugen und – außer bei ohne_email – mit PDF-Anhang an den Kunden schicken."""
    a = await _laden(user, angebot_id)
    if a["status"] not in ("entwurf", "gesendet"):
        _bearbeitbar(a)
    firma = await _firma(user)
    if not [p for p in a.get("positionen") or [] if p.get("art") not in ("titel", "text")]:
        raise HTTPException(400, "Das Angebot hat noch keine Positionen.")
    if not (a.get("kunde") or {}).get("name"):
        raise HTTPException(400, "Bitte zuerst einen Kunden eintragen.")
    an = (body.an or (a.get("kunde") or {}).get("email") or "").strip().lower()
    if not body.ohne_email and (not an or "@" not in an):
        raise HTTPException(400, "Der Kunde hat keine E-Mail-Adresse. Trage eine ein oder markiere das Angebot als ohne E-Mail übergeben.")
    erstmals = a["status"] == "entwurf"
    if erstmals:
        a["token"] = a.get("token") or ang.neuer_token()
        a["status"] = "gesendet"
        a["gesendet_at"] = jetzt_iso()
        pdf = pdfs.angebot_pdf(ang.pdf_daten(firma, a))
        pfad = f"angebote/{user['firma_id']}/{a['id']}_v{int(a.get('version') or 1)}.pdf"
        ziel = config.DATA_DIR / pfad
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_bytes(pdf)
        a["pdf_pfad"] = pfad
    else:
        pdf = await _pdf_bytes(firma, a)
    link = mail.link(f"/angebot/{a['token']}")
    eintrag = {"an": an if not body.ohne_email else "", "at": jetzt_iso(), "user_name": user.get("name"), "art": "ohne_email" if body.ohne_email else "email", "email_id": None}
    if not body.ohne_email:
        text = (f"Guten Tag {(a.get('kunde') or {}).get('contact') or (a.get('kunde') or {}).get('name')},\n\n"
                f"anbei erhalten Sie unser Angebot {a['nummer']}{' (Version ' + str(a['version']) + ')' if int(a.get('version') or 1) > 1 else ''}"
                f"{' – ' + a['titel'] if a.get('titel') else ''} über {pdfs.geld((a.get('summen') or {}).get('brutto', 0))} brutto."
                f"{chr(10) + chr(10) + body.nachricht.strip() if body.nachricht and body.nachricht.strip() else ''}\n\n"
                f"Das Angebot ist gültig bis {pdfs.de(a['gueltig_bis']) if a.get('gueltig_bis') else 'auf Widerruf'}. "
                f"Sie können es online ansehen und annehmen: {link}\n\nMit freundlichen Grüßen\n{firma.get('owner') or ''}\n{firma.get('name') or ''}")
        e = await mail.senden(user["firma_id"], an, f"Angebot {a['nummer']}{' – ' + a['titel'] if a.get('titel') else ''} von {firma.get('name') or ''}", text,
                              art="angebot_kunde", ref_id=a["id"], project_id=a.get("project_id") or "", anhaenge=[(f"Angebot_{a['nummer']}.pdf", pdf)])
        eintrag["email_id"] = (e or {}).get("id")
    a["versand"] = (a.get("versand") or []) + [eintrag]
    a["verlauf"] = (a.get("verlauf") or []) + [ang.schritt(user, "gesendet", f"an {an}" if not body.ohne_email else "ohne E-Mail übergeben (Druck/persönlich)")]
    a["updated_at"] = jetzt_iso()
    await db().kundenangebote.update_one({"id": a["id"]}, {"$set": {k: v for k, v in a.items() if k != "id"}})
    await protokollieren(user, "angebot.gesendet", a["nummer"], details={"an": an, "ohne_email": body.ohne_email, "brutto": (a.get("summen") or {}).get("brutto")})
    return {"angebot": ang.fuer_nutzer(a, user, firma), "antwortlink": link}


@router.post("/api/kundenangebote/{angebot_id}/version")
async def neue_version(angebot_id: str, user: dict = Depends(firmenabo_noetig("buero", "angebote"))):
    a = await _laden(user, angebot_id)
    if a["status"] in ("anfrage", "entwurf"):
        raise HTTPException(409, "Ein Entwurf wird direkt bearbeitet – eine neue Version braucht es erst nach dem Senden.")
    if a["status"] == "angenommen":
        raise HTTPException(409, "Ein angenommenes Angebot ändert sich nicht mehr – zusätzliche Leistungen laufen über einen Nachtrag.")
    if a.get("ersetzt_durch"):
        raise HTTPException(409, "Dieses Angebot wurde bereits durch eine neue Version ersetzt.")
    firma = await _firma(user)
    neu = {**{k: v for k, v in a.items() if k not in ("_id",)}, "id": neue_id(), "version": int(a.get("version") or 1) + 1, "vorgaenger_id": a["id"], "vorgaenger_status": a["status"],
           "ersetzt_durch": None, "status": "entwurf", "token": None, "pdf_pfad": None, "versand": [], "annahme": None, "ablehnung": None, "auftrag": None,
           "gesendet_at": None, "datum": lokal_jetzt().date().isoformat(), "created_at": jetzt_iso(), "updated_at": jetzt_iso(), "created_by": user["id"], "created_by_name": user.get("name"),
           "verlauf": [ang.schritt(user, "version", f"Version {int(a.get('version') or 1) + 1} aus Version {a.get('version') or 1} ({ang.STATUS_NAMEN.get(a['status'])})")]}
    neu["gueltig_bis"] = ang.gueltig_bis_standard(firma, neu["datum"])
    neu["positionen"] = [{k: v for k, v in p.items() if k not in ("nr", "gesamt", "zaehlt")} for p in a.get("positionen") or []]
    _berechnen(neu, firma)
    await db().kundenangebote.insert_one(dict(neu))
    await db().kundenangebote.update_one({"id": a["id"]}, {"$set": {"status": "ersetzt", "ersetzt_durch": neu["id"], "verlauf": (a.get("verlauf") or []) + [ang.schritt(user, "ersetzt", f"durch Version {neu['version']}")]}})
    await protokollieren(user, "angebot.version", a["nummer"], details={"version": neu["version"]})
    return {"angebot": ang.fuer_nutzer(neu, user, firma)}


async def _antwort_speichern(a: dict, aenderung: dict, schritt: dict) -> dict:
    aenderung = {**aenderung, "updated_at": jetzt_iso(), "verlauf": (a.get("verlauf") or []) + [schritt]}
    await db().kundenangebote.update_one({"id": a["id"]}, {"$set": aenderung})
    return {**a, **aenderung}


@router.post("/api/kundenangebote/{angebot_id}/annahme")
async def annahme(angebot_id: str, body: AngebotAnnahmeIn, user: dict = Depends(firmenabo_noetig("buero", "angebote"))):
    """Annahme durch den Kunden erfassen (schriftlich, telefonisch, unterschrieben) – nur für gesendete Angebote."""
    a = await _laden(user, angebot_id)
    if a["status"] not in ("gesendet", "abgelaufen"):
        raise HTTPException(409, "Nur ein gesendetes Angebot kann angenommen werden.")
    am = body.am or lokal_jetzt().date().isoformat()
    datum_pruefen(am)
    annahme = {"art": body.art or "schriftlich", "am": am, "von_name": body.von_name.strip(), "text": (body.text or "")[:1000], "erfasst_von": user.get("name"), "erfasst_at": jetzt_iso()}
    a = await _antwort_speichern(a, {"status": "angenommen", "annahme": annahme}, ang.schritt(user, "angenommen", f"{annahme['art']} durch {annahme['von_name']} am {pdfs.de(am)}"))
    await protokollieren(user, "angebot.angenommen", a["nummer"], details=annahme)
    return {"angebot": ang.fuer_nutzer(a, user, await _firma(user))}


@router.post("/api/kundenangebote/{angebot_id}/ablehnen")
async def ablehnen(angebot_id: str, body: AngebotGrundIn, user: dict = Depends(firmenabo_noetig("buero", "angebote"))):
    a = await _laden(user, angebot_id)
    if a["status"] not in ("gesendet", "abgelaufen", "entwurf", "anfrage"):
        raise HTTPException(409, "Dieses Angebot kann nicht mehr abgelehnt werden.")
    ablehnung = {"grund": body.grund.strip(), "am": lokal_jetzt().date().isoformat(), "erfasst_von": user.get("name")}
    a = await _antwort_speichern(a, {"status": "abgelehnt", "ablehnung": ablehnung}, ang.schritt(user, "abgelehnt", body.grund))
    await protokollieren(user, "angebot.abgelehnt", a["nummer"], details=ablehnung)
    return {"angebot": ang.fuer_nutzer(a, user, await _firma(user))}


@router.post("/api/kundenangebote/{angebot_id}/zurueckziehen")
async def zurueckziehen(angebot_id: str, body: AngebotGrundIn, user: dict = Depends(firmenabo_noetig("buero", "angebote"))):
    a = await _laden(user, angebot_id)
    if a["status"] != "gesendet":
        raise HTTPException(409, "Nur ein gesendetes, noch offenes Angebot kann zurückgezogen werden.")
    a = await _antwort_speichern(a, {"status": "zurueckgezogen"}, ang.schritt(user, "zurueckgezogen", body.grund))
    await protokollieren(user, "angebot.zurueckgezogen", a["nummer"], details={"grund": body.grund})
    return {"angebot": ang.fuer_nutzer(a, user, await _firma(user))}


@router.post("/api/kundenangebote/{angebot_id}/auftrag")
async def auftrag(angebot_id: str, body: AngebotAuftragIn, user: dict = Depends(firmenabo_noetig("buero", "angebote"))):
    """Aus dem angenommenen Angebot wird der Auftrag: ein neues Kundenprojekt (oder ein bestehendes) trägt Auftragswert und Abrechnungsart."""
    from routes.projekte import _projektdaten
    a = await _laden(user, angebot_id)
    if a["status"] != "angenommen":
        raise HTTPException(409, "Erst die Annahme des Kunden erfassen, dann den Auftrag anlegen.")
    if a.get("auftrag"):
        raise HTTPException(409, "Zu diesem Angebot gibt es schon einen Auftrag.")
    firma = await _firma(user)
    positionen = [p for p in a.get("positionen") or [] if p.get("zaehlt")]
    stunden = [p for p in positionen if p.get("art") == "stunden"]
    pauschal = not stunden
    s = a.get("summen") or {}
    kunde = a.get("kunde") or {}
    project_id = body.project_id or a.get("project_id")
    if project_id:
        p = await projekt_laden(user, project_id, schreiben=True)
        if p.get("auftrag"):
            raise HTTPException(409, f"Das Projekt „{p['name']}“ hat schon den Auftrag {p['auftrag'].get('nummer')}.")
    else:
        eingabe = ProjektIn(name=(body.name or a.get("titel") or f"Auftrag {a['nummer']}")[:160], customer_id=a.get("customer_id"), customer_name=kunde.get("name") or "",
                            customer_address=kundenadresse(kunde), address=(body.address or kunde.get("street") and f"{kunde.get('street')}, {kunde.get('zip_code')} {kunde.get('city')}".strip(", ") or "")[:300],
                            reverse_charge=bool(kunde.get("reverse_charge")), hourly_rate=float(stunden[0].get("einzelpreis") or 0) if stunden else 0,
                            abrechnungsart_projekt="pauschal" if pauschal else "stunden", pauschale_netto=float(s.get("netto") or 0) if pauschal else 0,
                            kostenlos=False, notes="")
        daten = await _projektdaten(user, eingabe)
        p = {**daten, "id": neue_id(), "firma_id": user["firma_id"], "created_at": jetzt_iso(), "total_minutes": 0, "entry_count": 0, "last_activity_at": None}
        await db().projects.insert_one(dict(p))
        await protokollieren(user, "projekt.angelegt", p["name"], details={"aus_angebot": a["nummer"]})
    auftrag = {"angebot_id": a["id"], "nummer": a["nummer"], "version": a.get("version"), "titel": a.get("titel"), "netto": s.get("netto"), "brutto": s.get("brutto"),
               "abrechnungsart": "pauschal" if pauschal else "stunden", "am": lokal_jetzt().date().isoformat(), "von_name": user.get("name"),
               "positionen": [{k: p_.get(k) for k in ("nr", "art", "text", "menge", "einheit", "einzelpreis", "gesamt")} for p_ in positionen]}
    await db().projects.update_one({"id": p["id"]}, {"$set": {"auftrag": auftrag, "abrechnungsart_projekt": "pauschal" if pauschal else "stunden",
                                                               **({"pauschale_netto": float(s.get("netto") or 0)} if pauschal else {})}})
    a = await _antwort_speichern(a, {"auftrag": {"project_id": p["id"], "projekt_name": p["name"], "am": auftrag["am"], "von_name": user.get("name")}, "project_id": p["id"], "projekt_name": p["name"]},
                                 ang.schritt(user, "auftrag", f"Auftrag im Projekt „{p['name']}“ angelegt"))
    await protokollieren(user, "angebot.auftrag", a["nummer"], details={"projekt": p["name"], "netto": s.get("netto")})
    p = await db().projects.find_one({"id": p["id"]}, {"_id": 0})
    return {"angebot": ang.fuer_nutzer(a, user, firma), "projekt": projekt_normalisieren(p)}


# ---------------------------------------------------------------- Kalkulation (vertraulich)

@router.get("/api/kundenangebote/{angebot_id}/kalkulation")
async def kalkulation(angebot_id: str, user: dict = Depends(recht_noetig("kalkulation"))):
    a = await _laden(user, angebot_id)
    return {"kalkulation": ang.kalkulation_angebot(a, await _firma(user)), "positionen": [{k: p.get(k) for k in ("id", "nr", "art", "text", "menge", "einheit", "einzelpreis", "gesamt", "zaehlt", "kalkulation")} for p in a.get("positionen") or []]}


@router.put("/api/kundenangebote/{angebot_id}/kalkulation")
async def kalkulation_setzen(angebot_id: str, body: KalkulationIn, user: dict = Depends(firmenabo_noetig("buero", "kalkulation"))):
    """Interne Kalkulation je Position – auch nach dem Senden erlaubt (ändert das Kundendokument nicht)."""
    a = await _laden(user, angebot_id)
    firma = await _firma(user)
    for p in a.get("positionen") or []:
        if p["id"] in body.positionen:
            p["kalkulation"] = _kalkulation_normalisieren(body.positionen[p["id"]])
    await db().kundenangebote.update_one({"id": a["id"]}, {"$set": {"positionen": a["positionen"], "updated_at": jetzt_iso()}})
    return {"kalkulation": ang.kalkulation_angebot(a, firma), "angebot": ang.fuer_nutzer(a, user, firma)}


@router.post("/api/kundenangebote/{angebot_id}/kalkulation/uebernehmen")
async def preis_uebernehmen(angebot_id: str, position_id: Optional[str] = None, user: dict = Depends(firmenabo_noetig("buero", "kalkulation"))):
    """Kalkulationsassistent: den Preisvorschlag (Selbstkosten + Gewinnzuschlag) als Einzelpreis übernehmen – nur im Entwurf."""
    a = await _laden(user, angebot_id)
    _bearbeitbar(a)
    firma = await _firma(user)
    firma_k = ang.firmen_kalkulation(firma)
    n = 0
    for p in a.get("positionen") or []:
        if position_id and p["id"] != position_id:
            continue
        k = ang.kalkulation_position(p, firma_k)
        if not k or not float(p.get("menge") or 0):
            continue
        p["einzelpreis"] = ang.rund(k["vk_vorschlag"] / float(p["menge"]))
        p["rabatt_prozent"] = 0.0
        n += 1
    if not n:
        raise HTTPException(400, "Keine Position mit Kalkulation gefunden.")
    _berechnen(a, firma)
    a["updated_at"] = jetzt_iso()
    await db().kundenangebote.update_one({"id": a["id"]}, {"$set": {k: v for k, v in a.items() if k != "id"}})
    return {"angebot": ang.fuer_nutzer(a, user, firma), "uebernommen": n}


# ---------------------------------------------------------------- Öffentlicher Antwortlink (ohne Anmeldung)

async def _oeffentlich_laden(token: str) -> tuple[dict, dict]:
    if not token or len(token) < 16:
        raise HTTPException(404, "Angebot nicht gefunden.")
    a = await db().kundenangebote.find_one({"token": token}, {"_id": 0})
    if not a:
        raise HTTPException(404, "Angebot nicht gefunden.")
    if a.get("status") == "ersetzt" and a.get("ersetzt_durch"):
        neu = await db().kundenangebote.find_one({"id": a["ersetzt_durch"]}, {"_id": 0})
        if neu and neu.get("token"):
            a = neu
    if ang.abgelaufen(a):
        await db().kundenangebote.update_one({"id": a["id"]}, {"$set": {"status": "abgelaufen"}})
        a["status"] = "abgelaufen"
    firma = await firma_laden(a["firma_id"])
    return a, firma


@router.get("/api/oeffentlich/angebot/{token}")
async def oeffentlich(token: str):
    a, firma = await _oeffentlich_laden(token)
    return {"angebot": ang.oeffentlich(a, firma)}


@router.get("/api/oeffentlich/angebot/{token}/angebot.pdf")
async def oeffentlich_pdf(token: str):
    a, firma = await _oeffentlich_laden(token)
    return _pdf_antwort(await _pdf_bytes(firma, a), a)


@router.post("/api/oeffentlich/angebot/{token}/antwort")
async def oeffentlich_antwort(token: str, body: AngebotAntwortIn):
    a, firma = await _oeffentlich_laden(token)
    if a.get("status") != "gesendet":
        raise HTTPException(409, "Dieses Angebot kann nicht mehr beantwortet werden." if a.get("status") != "abgelaufen" else "Das Angebot ist abgelaufen – bitte fragen Sie ein neues an.")
    name = body.name.strip()
    heute = lokal_jetzt().date().isoformat()
    if body.entscheidung == "angenommen":
        annahme = {"art": "online", "am": heute, "von_name": name, "text": (body.text or "")[:1000], "erfasst_von": "Kunde (Antwortlink)", "erfasst_at": jetzt_iso()}
        a = await _antwort_speichern(a, {"status": "angenommen", "annahme": annahme}, ang.schritt(None, "angenommen", f"online durch {name}"))
        text = f"{name} hat das Angebot {a['nummer']}{' – ' + a['titel'] if a.get('titel') else ''} online angenommen."
        art = "angebot_angenommen"
    else:
        ablehnung = {"grund": (body.text or "").strip()[:1000] or "ohne Angabe", "am": heute, "erfasst_von": f"Kunde: {name}"}
        a = await _antwort_speichern(a, {"status": "abgelehnt", "ablehnung": ablehnung}, ang.schritt(None, "abgelehnt", f"online durch {name}: {ablehnung['grund']}"))
        text = f"{name} hat das Angebot {a['nummer']}{' – ' + a['titel'] if a.get('titel') else ''} abgelehnt: {ablehnung['grund']}"
        art = "angebot_abgelehnt"
    await benachrichtigen(a["firma_id"], art, text, link=f"/angebote/{a['id']}")
    await mail.firma_informieren(a["firma_id"], f"Antwort auf Angebot {a['nummer']}", text + f"\n\nAngebot öffnen: {mail.link('/angebote/' + a['id'])}", art, ref_id=a["id"], project_id=a.get("project_id") or "")
    await protokollieren(None, "angebot." + ("angenommen" if body.entscheidung == "angenommen" else "abgelehnt"), a["nummer"], details={"online": True, "name": name}, firma_id=a["firma_id"])
    return {"angebot": ang.oeffentlich(a, firma)}
