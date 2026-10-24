"""Rechnungsprozesse (Stufe E): Rechnung aus dem Auftrag, Abschläge, Schlussrechnung, Storno, Gutschrift, Zahlungen, Versand, Mahnwesen."""
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pymongo.errors import DuplicateKeyError

import config
import erechnung
import mail
import pdfbasis
import pdfs
import rechnungslauf as rl
from auth import firma_laden, firmenabo_noetig, hat_rolle, jetzt_iso, recht_noetig, schreibend_mit_recht
from db import db
from gemeinsam import kunde_laden, neue_id, projekt_laden
from models import GutschriftIn, MahnungIn, RechnungAuftragIn, RechnungSendenIn, StornoIn, ZahlungIn
from protokoll import protokollieren
from routes.rechnungen import _erechnung, _festschreiben, _laden, _naechste_nummer, festgeschrieben
from zeiten import datum_pruefen, lokal_jetzt

router = APIRouter(tags=["Rechnungsprozesse"])


async def _firma(user: dict) -> dict:
    return user.get("_firma") or await firma_laden(user["firma_id"])


def _mit_stand(r: dict) -> dict:
    stand = rl.zahlungsstand(r)
    return {**r, "bezahlt_betrag": stand["bezahlt_betrag"], "offen_betrag": stand["offen_betrag"], "art_name": rl.ARTEN.get(r.get("art") or "monat", "Rechnung"),
            "status_name": rl.STATUS_NAMEN.get(r.get("status"), r.get("status"))}


async def _anlegen(user: dict, firma: dict, art: str, zeilen: list[dict], reverse_charge: bool, project_id: Optional[str], customer_id: Optional[str],
                   invoice_date: Optional[str], felder: dict) -> dict:
    """Neue Rechnung mit nächster Nummer (gleicher Zähler wie die Monatsrechnung); `month = -seq` hält den Index (Firma, Projekt, Jahr, Monat) eindeutig."""
    datum = invoice_date or lokal_jetzt().date().isoformat()
    datum_pruefen(datum)
    jahr = int(datum[:4])
    summen = rl.zeilen_summen(firma, reverse_charge, zeilen)
    for _ in range(6):
        seq = await _naechste_nummer(user["firma_id"], jahr)
        r = {"id": neue_id(), "firma_id": user["firma_id"], "project_id": project_id, "customer_id": customer_id, "year": jahr, "month": -seq, "seq": seq,
             "number": f"{firma.get('invoice_prefix') or 'RE-'}{jahr}-{seq:04d}", "invoice_date": datum, "faellig_am": rl.faellig_am({"invoice_date": datum}, firma),
             "status": "offen", "paid_at": None, "art": art, "zahlungen": [], "bezahlt_betrag": 0.0, "mahnstufe": 0, "mahnungen": [], "versand": [],
             "created_by": user["id"], "created_at": jetzt_iso(), **summen, "totals_at": jetzt_iso(), **felder}
        try:
            await db().invoices.insert_one(dict(r))
            return r
        except DuplicateKeyError:
            continue
    raise HTTPException(503, "Rechnungsnummer konnte nicht vergeben werden, bitte noch einmal versuchen.")


# ---------------------------------------------------------------- Abrechnung eines Projekts

@router.get("/api/projekte/{project_id}/abrechnung")
async def abrechnung(project_id: str, user: dict = Depends(recht_noetig("rechnungen"))):
    """Auftragswert, Nachträge, gestellte Abschläge, Schlussrechnung, Pauschal- und Monatsrechnungen mit Zahlungsstand."""
    p = await projekt_laden(user, project_id)
    basis = await rl.auftragsbasis(user["firma_id"], p)
    rechnungen = []
    async for r in db().invoices.find({"firma_id": user["firma_id"], "project_id": p["id"]}, {"_id": 0, "positions": 0, "extras": 0}).sort([("year", 1), ("seq", 1)]):
        rechnungen.append(_mit_stand(r))
    abschlaege = [r for r in rechnungen if r.get("art") == "abschlag" and r["status"] != "storniert"]
    schluss = next((r for r in rechnungen if r.get("art") == "schluss" and r["status"] != "storniert"), None)
    gestellt = rl.rund(sum(r["net"] for r in rechnungen if r["status"] != "storniert" and r.get("art") in ("abschlag", "schluss", "pauschal")))
    gueltig = [r for r in rechnungen if r["status"] != "storniert" and r.get("art") not in ("storno", "gutschrift")]
    return {"basis": basis, "rechnungen": rechnungen, "abschlaege": abschlaege, "schluss": schluss,
            "summen": {"gestellt_netto": gestellt, "rest_netto": rl.rund(basis["basis_netto"] - gestellt) if basis["basis_netto"] else None,
                       "bezahlt_brutto": rl.rund(sum(r["bezahlt_betrag"] for r in gueltig)), "offen_brutto": rl.rund(sum(r["offen_betrag"] for r in gueltig))},
            "naechster_abschlag_nr": len(abschlaege) + 1, "kann_abschlag": bool(basis["basis_netto"]) and schluss is None,
            "kann_schluss": bool(basis["basis_netto"]) and schluss is None, "kann_pauschal": bool(basis["basis_netto"]) and not abschlaege and schluss is None,
            "arten": rl.ARTEN, "zahlungsarten": rl.ZAHLUNGSARTEN}


@router.post("/api/rechnungen/auftrag")
async def rechnung_aus_auftrag(body: RechnungAuftragIn, user: dict = Depends(firmenabo_noetig("buero", "rechnungen"))):
    """Rechnung aus dem Auftrag: pauschal (Gesamtleistung), abschlag (pauschaler Betrag oder kumulativ nach Leistungsstand) oder schluss (abzüglich Abschläge)."""
    p = await projekt_laden(user, body.project_id)
    firma = await _firma(user)
    basis = await rl.auftragsbasis(user["firma_id"], p)
    if not basis["basis_netto"]:
        raise HTTPException(400, "Das Projekt hat keinen Auftragswert – erst ein Angebot als Auftrag anlegen oder eine Pauschale im Projekt hinterlegen.")
    vorherige = await rl.abschlaege_bisher(user["firma_id"], p["id"])
    schluss = await rl.schlussrechnung_bisher(user["firma_id"], p["id"])
    if schluss:
        raise HTTPException(409, f"Für dieses Projekt gibt es schon die Schlussrechnung {schluss.get('number')}. Änderungen laufen über Storno und neue Rechnung.")
    info: dict = {}
    felder: dict = {"leistung_von": body.leistung_von, "leistung_bis": body.leistung_bis, "rechnungstext": (body.text or "")[:1000], "auftrag_nummer": (basis.get("auftrag") or {}).get("nummer")}
    if body.art == "abschlag":
        if body.leistungsstand_prozent is None and not body.betrag_netto:
            raise HTTPException(400, "Für einen Abschlag entweder den Leistungsstand in Prozent (kumulativ) oder einen Betrag angeben.")
        zeilen, info = rl.abschlag_zeilen(basis, vorherige, body.betrag_netto, body.leistungsstand_prozent, len(vorherige) + 1)
        if info["neu_netto"] <= 0:
            raise HTTPException(400, f"Der Leistungsstand liegt nicht über den bereits gestellten Abschlägen ({info.get('bisher_netto', 0):,.2f} € netto).".replace(",", "X").replace(".", ",").replace("X", "."))
        if vorherige and any(v.get("kumulativ") for v in vorherige) != info["kumulativ"] and vorherige:
            raise HTTPException(409, "Abschlagsart nicht mischen: bisherige Abschläge sind " + ("kumulativ (Leistungsstand)." if vorherige[0].get("kumulativ") else "pauschale Beträge."))
        felder.update({"abschlag_nr": len(vorherige) + 1, "kumulativ": info["kumulativ"], "leistungsstand_prozent": info.get("leistungsstand_prozent"), "vorherige": [v["id"] for v in vorherige]})
    elif body.art == "schluss":
        zeilen, info = rl.schluss_zeilen(basis, vorherige)
        felder.update({"vorherige": [v["id"] for v in vorherige], "abschlaege_netto": info["abschlaege_netto"], "offen_aus_abschlaegen_brutto": info["offen_aus_abschlaegen_brutto"]})
    else:
        if vorherige:
            raise HTTPException(409, "Dieses Projekt wird über Abschläge abgerechnet – bitte die Schlussrechnung stellen.")
        if body.positionen:
            zeilen = [rl.zeile(x.text, x.quantity * x.unit_price, x.quantity, x.unit or "Psch.", x.unit_price) for x in body.positionen]
        else:
            zeilen, _ = rl.schluss_zeilen(basis, [])
    summen = rl.zeilen_summen(firma, bool(p.get("reverse_charge")), zeilen)
    if body.nur_pruefen:
        return {"vorschau": {"art": body.art, "zeilen": zeilen, "info": info, **{k: summen[k] for k in ("net", "vat_rate", "vat", "gross")}}}
    r = await _anlegen(user, firma, body.art, zeilen, bool(p.get("reverse_charge")), p["id"], p.get("customer_id"), body.invoice_date, felder)
    await protokollieren(user, f"rechnung.{body.art}", r["number"], details={"projekt": p["name"], "netto": r["net"], **({"leistungsstand": info.get("leistungsstand_prozent")} if info.get("kumulativ") else {})})
    return {"rechnung": _mit_stand(r), "info": info}


# ---------------------------------------------------------------- Storno und Gutschrift

@router.post("/api/rechnungen/{rechnung_id}/storno")
async def storno(rechnung_id: str, body: StornoIn, user: dict = Depends(firmenabo_noetig("buero", "rechnungen"))):
    """Korrekturbeleg: Stornorechnung mit eigener Nummer und negativen Beträgen; die Originalrechnung bleibt als Beleg und wird „storniert“."""
    r = await _laden(user, rechnung_id)
    if r.get("art") == "storno":
        raise HTTPException(409, "Eine Stornorechnung wird nicht storniert.")
    if r.get("status") == "storniert":
        raise HTTPException(409, "Die Rechnung ist schon storniert.")
    if not festgeschrieben(r):
        raise HTTPException(409, "Ein Entwurf braucht keinen Storno – einfach zurücksetzen (Nummer wird nicht neu vergeben).")
    firma = await _firma(user)
    zeilen = rl.storno_zeilen(r)
    felder = {"storno_von": {"id": r["id"], "number": r["number"], "invoice_date": r.get("invoice_date")}, "rechnungstext": f"Storno der Rechnung {r['number']} vom {rl._de(r.get('invoice_date'))}. Grund: {body.grund.strip()}",
              "leistung_von": r.get("leistung_von"), "leistung_bis": r.get("leistung_bis"), "storno_monat": r.get("month") if (r.get("art") or "monat") == "monat" else None}
    s = await _anlegen(user, firma, "storno", zeilen, bool(r.get("reverse_charge")), r.get("project_id"), r.get("customer_id"), None, felder)
    s = await _festschreiben(user, s, "storno")
    await db().invoices.update_one({"id": r["id"]}, {"$set": {"status": "storniert", "storno_id": s["id"], "storno_nummer": s["number"], "storniert_at": jetzt_iso(), "storno_grund": body.grund.strip(), "updated_at": jetzt_iso()}})
    await protokollieren(user, "rechnung.storno", r["number"], details={"storno": s["number"], "grund": body.grund.strip()})
    return {"storno": _mit_stand(s), "rechnung": _mit_stand({**r, "status": "storniert", "storno_id": s["id"], "storno_nummer": s["number"]})}


@router.post("/api/rechnungen/gutschrift")
async def gutschrift(body: GutschriftIn, user: dict = Depends(firmenabo_noetig("buero", "rechnungen"))):
    """Gutschrift (kaufmännisch: Rechnungskorrektur zugunsten des Kunden) mit negativen Beträgen und eigener Nummer."""
    firma = await _firma(user)
    p = await projekt_laden(user, body.project_id) if body.project_id else None
    customer_id = body.customer_id or (p or {}).get("customer_id")
    if not customer_id and not p:
        raise HTTPException(400, "Bitte Kunde oder Projekt angeben.")
    kunde = await kunde_laden(user["firma_id"], customer_id)
    umkehr = bool((kunde or {}).get("reverse_charge") if kunde else (p or {}).get("reverse_charge"))
    zeilen = [rl.zeile(x.text, -(x.quantity * x.unit_price), x.quantity, x.unit or "Psch.", -x.unit_price) for x in body.positionen]
    felder = {"rechnungstext": (body.text or "")[:1000], "gutschrift_grund": (body.grund or "")[:500], "bezug_nummer": (body.bezug_nummer or "")[:40]}
    r = await _anlegen(user, firma, "gutschrift", zeilen, umkehr, (p or {}).get("id"), customer_id, body.invoice_date, felder)
    await protokollieren(user, "rechnung.gutschrift", r["number"], details={"netto": r["net"], "grund": body.grund})
    return {"rechnung": _mit_stand(r)}


# ---------------------------------------------------------------- Zahlungen

@router.post("/api/rechnungen/{rechnung_id}/zahlungen")
async def zahlung_erfassen(rechnung_id: str, body: ZahlungIn, user: dict = Depends(schreibend_mit_recht("rechnungen"))):
    r = await _laden(user, rechnung_id)
    if r.get("art") in ("storno", "gutschrift"):
        raise HTTPException(409, "Auf Storno und Gutschrift werden keine Zahlungen gebucht – sie werden mit offenen Rechnungen verrechnet oder erstattet.")
    if r.get("status") == "storniert":
        raise HTTPException(409, "Die Rechnung ist storniert.")
    stand = rl.zahlungsstand(r)
    if body.betrag > stand["offen_betrag"] + 0.01:
        raise HTTPException(400, f"Die Zahlung ({body.betrag:,.2f} €) übersteigt den offenen Betrag ({stand['offen_betrag']:,.2f} €).".replace(",", "X").replace(".", ",").replace("X", "."))
    am = body.am or lokal_jetzt().date().isoformat()
    datum_pruefen(am)
    z = {"id": neue_id(), "am": am, "betrag": rl.rund(body.betrag), "art": body.art, "notiz": (body.notiz or "")[:300], "erfasst_von": user.get("name"), "at": jetzt_iso()}
    zahlungen = (r.get("zahlungen") or []) + [z]
    neu = {**r, "zahlungen": zahlungen}
    stand = rl.zahlungsstand(neu)
    aenderung = {"zahlungen": zahlungen, "bezahlt_betrag": stand["bezahlt_betrag"], "status": stand["status"], "paid_at": am if stand["status"] == "bezahlt" else None, "updated_at": jetzt_iso()}
    await db().invoices.update_one({"id": r["id"]}, {"$set": aenderung})
    await protokollieren(user, "rechnung.zahlung", r["number"], details={"betrag": z["betrag"], "am": am, "art": body.art, "status": stand["status"]})
    return {"rechnung": _mit_stand({**r, **aenderung})}


@router.delete("/api/rechnungen/{rechnung_id}/zahlungen/{zahlung_id}")
async def zahlung_loeschen(rechnung_id: str, zahlung_id: str, user: dict = Depends(schreibend_mit_recht("rechnungen"))):
    r = await _laden(user, rechnung_id)
    zahlungen = [z for z in r.get("zahlungen") or [] if z.get("id") != zahlung_id]
    if len(zahlungen) == len(r.get("zahlungen") or []):
        raise HTTPException(404, "Zahlung nicht gefunden.")
    stand = rl.zahlungsstand({**r, "zahlungen": zahlungen, "status": "offen" if r.get("status") != "storniert" else "storniert"})
    aenderung = {"zahlungen": zahlungen, "bezahlt_betrag": stand["bezahlt_betrag"], "status": stand["status"], "paid_at": None if stand["status"] != "bezahlt" else r.get("paid_at"), "updated_at": jetzt_iso()}
    await db().invoices.update_one({"id": r["id"]}, {"$set": aenderung})
    await protokollieren(user, "rechnung.zahlung_geloescht", r["number"], details={"zahlung": zahlung_id})
    return {"rechnung": _mit_stand({**r, **aenderung})}


# ---------------------------------------------------------------- Versand an den Kunden

async def _rechnung_pdf_bytes(user: dict, r: dict) -> tuple[bytes, str]:
    daten, firma, r = await _erechnung(user, r["id"])
    xml = erechnung.cii_xml(daten, "zugferd") if erechnung.pruefen(daten, "zugferd")["ok"] else None
    return pdfbasis.pdfa3_mit_xml(erechnung.rechnung_pdf(daten), xml, f"{daten.get('art_name', 'Rechnung')} {daten['nummer']}", firma.get("name") or ""), ("zugferd" if xml else "pdf")


@router.post("/api/rechnungen/{rechnung_id}/senden")
async def senden(rechnung_id: str, body: RechnungSendenIn, user: dict = Depends(firmenabo_noetig("buero", "rechnungen"))):
    """Rechnung per E-Mail an den Kunden (PDF, mit ZUGFeRD-XML wenn die Kundendaten vollständig sind); stellt die Rechnung aus."""
    r = await _laden(user, rechnung_id)
    if r.get("status") == "storniert" and r.get("art") != "storno":
        raise HTTPException(409, "Stornierte Rechnungen werden nicht versendet.")
    firma = await _firma(user)
    p = await projekt_laden(user, r["project_id"]) if r.get("project_id") else None
    kunde = await kunde_laden(user["firma_id"], r.get("customer_id") or (p or {}).get("customer_id"))
    an = (body.an or (kunde or {}).get("email") or "").strip().lower()
    if not an or "@" not in an:
        raise HTTPException(400, "Keine E-Mail-Adresse des Kunden – bitte angeben oder beim Kunden hinterlegen.")
    r = await _festschreiben(user, r, "versand")
    pdf, profil = await _rechnung_pdf_bytes(user, r)
    art_name = rl.ARTEN.get(r.get("art") or "monat", "Rechnung")
    text = (f"Guten Tag {(kunde or {}).get('contact') or (kunde or {}).get('name') or ''},\n\nanbei erhalten Sie unsere {art_name} {r['number']} vom {rl._de(r.get('invoice_date'))} "
            f"über {pdfs.geld(r.get('gross'))}" + (f", zahlbar bis {rl._de(r.get('faellig_am') or rl.faellig_am(r, firma))}" if r.get("art") not in ("storno", "gutschrift") else "") + "."
            + (f"\n\n{body.nachricht.strip()}" if body.nachricht and body.nachricht.strip() else "") + f"\n\nMit freundlichen Grüßen\n{firma.get('owner') or ''}\n{firma.get('name') or ''}")
    e = await mail.senden(user["firma_id"], an, f"{art_name} {r['number']} von {firma.get('name') or ''}", text, art="rechnung", ref_id=r["id"], project_id=r.get("project_id") or "",
                          anhaenge=[(f"{art_name}_{r['number']}.pdf", pdf)])
    eintrag = {"an": an, "at": jetzt_iso(), "user_name": user.get("name"), "email_id": (e or {}).get("id"), "profil": profil}
    await db().invoices.update_one({"id": r["id"]}, {"$push": {"versand": eintrag}, "$set": {"updated_at": jetzt_iso()}})
    await protokollieren(user, "rechnung.gesendet", r["number"], details={"an": an, "profil": profil})
    return {"rechnung": _mit_stand({**r, "versand": (r.get("versand") or []) + [eintrag]}), "profil": profil}


# ---------------------------------------------------------------- Mahnwesen

async def _kunde_der_rechnung(user: dict, r: dict) -> Optional[dict]:
    p = await db().projects.find_one({"id": r.get("project_id"), "firma_id": user["firma_id"]}, {"_id": 0, "customer_id": 1, "customer_name": 1, "customer_address": 1}) if r.get("project_id") else None
    kunde = await kunde_laden(user["firma_id"], r.get("customer_id") or (p or {}).get("customer_id"))
    if kunde:
        return kunde
    if p and p.get("customer_name"):
        return {"name": p["customer_name"], **erechnung.adresse_aus_text(p.get("customer_address") or ""), "email": "", "contact": ""}
    return None


@router.get("/api/mahnwesen")
async def mahnwesen(user: dict = Depends(recht_noetig("rechnungen"))):
    """Alle überfälligen, ausgestellten Rechnungen mit Mahnstand und Vorschlag für den nächsten Schritt – versendet wird nur von Hand."""
    firma = await _firma(user)
    heute = lokal_jetzt().date()
    projekte = {p["id"]: p["name"] async for p in db().projects.find({"firma_id": user["firma_id"]}, {"_id": 0, "id": 1, "name": 1})}
    aus, summe = [], 0.0
    async for r in db().invoices.find({"firma_id": user["firma_id"], "status": {"$in": ["offen", "teilbezahlt"]}}, {"_id": 0, "positions": 0, "extras": 0}):
        v = rl.mahn_vorschlag(r, firma, heute)
        if not v:
            continue
        kunde = await _kunde_der_rechnung(user, r)
        summe += v["offen_betrag"]
        aus.append({**_mit_stand(r), **v, "projekt_name": projekte.get(r.get("project_id"), ""), "kunde_name": (kunde or {}).get("name", ""), "kunde_email": (kunde or {}).get("email", "")})
    aus.sort(key=lambda x: -x["tage_ueberfaellig"])
    return {"rechnungen": aus, "offen_brutto": rl.rund(summe), "regeln": rl.mahn_regeln(firma), "stufen": rl.MAHNSTUFEN, "jetzt_faellig": sum(1 for x in aus if x["jetzt_faellig"])}


@router.post("/api/rechnungen/{rechnung_id}/mahnung")
async def mahnung(rechnung_id: str, body: MahnungIn, user: dict = Depends(firmenabo_noetig("buero", "rechnungen"))):
    """Zahlungserinnerung / Mahnung / letzte Mahnung als PDF erzeugen und (wenn gewünscht und möglich) per E-Mail schicken – immer von Hand ausgelöst."""
    r = await _laden(user, rechnung_id)
    firma = await _firma(user)
    v = rl.mahn_vorschlag(r, firma, lokal_jetzt().date())
    if not v:
        raise HTTPException(409, "Die Rechnung ist nicht überfällig, nicht ausgestellt oder schon bezahlt.")
    stufe = body.stufe or v["naechste_stufe"]
    if not stufe or stufe != v["naechste_stufe"]:
        raise HTTPException(409, f"Nächste Stufe ist {v['naechste_stufe'] or 'keine mehr'} ({v['naechste_name'] or 'alle drei Stufen sind durch'}).")
    if not v["jetzt_faellig"] and not body.erzwingen:
        raise HTTPException(409, f"Die Frist für die {v['naechste_name']} läuft noch bis {rl._de(v['faellig_ab'])}. Mit erzwingen=true trotzdem senden.")
    regeln = rl.mahn_regeln(firma)
    gebuehr = rl.rund(body.gebuehr) if body.gebuehr is not None else rl.mahn_gebuehr(stufe, regeln)
    text = (body.text or rl.mahn_text(stufe, regeln)).strip()[:4000]
    kunde = await _kunde_der_rechnung(user, r)
    m = {"id": neue_id(), "stufe": stufe, "name": rl.MAHNSTUFEN[stufe], "am": lokal_jetzt().date().isoformat(), "text": text, "gebuehr": gebuehr, "offen_betrag": v["offen_betrag"],
         "gesamt": rl.rund(v["offen_betrag"] + gebuehr), "von_name": user.get("name"), "email_id": None, "an": "", "pdf_pfad": None, "at": jetzt_iso()}
    pdf = pdfs.mahnung_pdf(firma, kunde or {}, _mit_stand(r), m, rl.ARTEN.get(r.get("art") or "monat", "Rechnung"), rl.faellig_am(r, firma))
    pfad = f"mahnungen/{user['firma_id']}/{r['id']}_m{stufe}.pdf"
    ziel = config.DATA_DIR / pfad
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_bytes(pdf)
    m["pdf_pfad"] = pfad
    an = ((kunde or {}).get("email") or "").strip().lower()
    if body.per_email and an and "@" in an:
        mailtext = (f"Guten Tag {(kunde or {}).get('contact') or (kunde or {}).get('name') or ''},\n\n{text}\n\nRechnung {r['number']} vom {rl._de(r.get('invoice_date'))}, "
                    f"offen: {pdfs.geld(v['offen_betrag'])}" + (f" zzgl. Mahngebühr {pdfs.geld(gebuehr)}" if gebuehr else "") + f".\n\nMit freundlichen Grüßen\n{firma.get('owner') or ''}\n{firma.get('name') or ''}")
        e = await mail.senden(user["firma_id"], an, f"{rl.MAHNSTUFEN[stufe]} zur Rechnung {r['number']}", mailtext, art="mahnung", ref_id=r["id"], project_id=r.get("project_id") or "",
                              anhaenge=[(f"{rl.MAHNSTUFEN[stufe].replace(' ', '_')}_{r['number']}.pdf", pdf)])
        m["email_id"], m["an"] = (e or {}).get("id"), an
    mahnungen = (r.get("mahnungen") or []) + [m]
    await db().invoices.update_one({"id": r["id"]}, {"$set": {"mahnungen": mahnungen, "mahnstufe": stufe, "mahngebuehren": rl.rund(sum(_m.get("gebuehr") or 0 for _m in mahnungen)), "updated_at": jetzt_iso()}})
    await protokollieren(user, "rechnung.mahnung", r["number"], details={"stufe": stufe, "gebuehr": gebuehr, "an": m["an"], "offen": v["offen_betrag"]})
    return {"mahnung": m, "rechnung": _mit_stand({**r, "mahnungen": mahnungen, "mahnstufe": stufe})}


@router.get("/api/rechnungen/{rechnung_id}/mahnung/{stufe}.pdf")
async def mahnung_pdf(rechnung_id: str, stufe: int, user: dict = Depends(recht_noetig("rechnungen"))):
    r = await _laden(user, rechnung_id)
    m = next((x for x in r.get("mahnungen") or [] if int(x.get("stufe") or 0) == stufe), None)
    if not m:
        raise HTTPException(404, "Mahnung nicht gefunden.")
    inhalt = None
    if m.get("pdf_pfad") and (config.DATA_DIR / m["pdf_pfad"]).is_file():
        inhalt = (config.DATA_DIR / m["pdf_pfad"]).read_bytes()
    if inhalt is None:
        firma = await _firma(user)
        inhalt = pdfs.mahnung_pdf(firma, await _kunde_der_rechnung(user, r) or {}, _mit_stand(r), m, rl.ARTEN.get(r.get("art") or "monat", "Rechnung"), rl.faellig_am(r, firma))
    return Response(content=inhalt, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{rl.MAHNSTUFEN.get(stufe, "Mahnung").replace(" ", "_")}_{r["number"]}.pdf"'})
