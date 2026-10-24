"""Kundenangebote (normale Angebote eines Betriebs an seine Kunden) mit Positionen, Versionen und interner Kalkulation.

Nicht zu verwechseln mit den Bieterangeboten der GU-Ausschreibungen (`ausschreibung.py`, Sammlung `angebote`): Kundenangebote liegen in
`kundenangebote`, brauchen keine Bieterliste und laufen Kundenanfrage → Entwurf → gesendet → angenommen → Auftrag (Projekt).

Status: anfrage (nur die Kundenanfrage ist erfasst) → entwurf → gesendet → angenommen | abgelehnt | zurueckgezogen | abgelaufen;
ersetzt = durch eine neue Version abgelöst (die Nummer bleibt, die Version zählt hoch). Ein gesendetes Angebot wird nie mehr geändert.

Positionen (gemeinsame fachliche Struktur, auch für Rechnungen und Aufmaß gedacht):
  {id, art: titel|leistung|stunden|material|pauschal|text, text, beschreibung, menge, einheit, einzelpreis, rabatt_prozent,
   alternativ, eventual, leistung_id, kalkulation{…}}
Titel gliedern die Liste (alle folgenden Positionen bis zum nächsten Titel gehören dazu); Alternativ- und Eventualpositionen werden
ausgewiesen, aber nicht in die Summe gerechnet. Die Kalkulation je Position ist vertraulich (Recht „kalkulation“) und geht nie an Kunden,
Mitarbeiter oder GU-Partner.
"""
from __future__ import annotations

import secrets
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from fastapi import HTTPException

from auth import hat_recht, jetzt_iso
from db import db

STATUS_NAMEN = {"anfrage": "Kundenanfrage", "entwurf": "Entwurf", "gesendet": "Gesendet – Antwort offen", "angenommen": "Angenommen",
                "abgelehnt": "Abgelehnt", "zurueckgezogen": "Zurückgezogen", "abgelaufen": "Abgelaufen", "ersetzt": "Durch neue Version ersetzt"}
OFFEN = ("anfrage", "entwurf", "gesendet")
POSITIONSARTEN = {"titel": "Titel / Gruppe", "leistung": "Leistung", "stunden": "Stundenposition", "material": "Material", "pauschal": "Pauschale", "text": "Textzeile"}
EINHEITEN = ["Stk.", "Std.", "m", "m²", "m³", "lfm", "kg", "l", "Psch.", "Tag", "Monat", "Fahrt"]
KALKULATION_FELDER = ("stunden", "stundensatz", "material_ek", "fremd", "geraete", "transport", "sonstige", "gemeinkosten_prozent", "risiko_prozent", "gewinn_prozent")
KALKULATION_STANDARD = {"stundensatz": 0.0, "gemeinkosten_prozent": 15.0, "risiko_prozent": 3.0, "gewinn_prozent": 10.0}


def rund(x) -> float:
    return float(Decimal(str(x or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _f(x, standard: float = 0.0) -> float:
    try:
        return float(x) if x not in (None, "") else standard
    except (TypeError, ValueError):
        return standard


# ---------------------------------------------------------------- Positionen

def nummerieren(positionen: list[dict]) -> list[dict]:
    """Laufende Nummern: Titel und freie Positionen zählen oben (1, 2, 3), Positionen unter einem Titel 2.1, 2.2 …; Textzeilen ohne Nummer."""
    oben, unter, titel_nr = 0, 0, None
    aus = []
    for p in positionen:
        p = dict(p)
        art = p.get("art") or "leistung"
        if art == "titel":
            oben += 1
            titel_nr, unter = oben, 0
            p["nr"] = str(oben)
        elif art == "text":
            p["nr"] = ""
        elif titel_nr is None:
            oben += 1
            p["nr"] = str(oben)
        else:
            unter += 1
            p["nr"] = f"{titel_nr}.{unter}"
        aus.append(p)
    return aus


def position_betrag(p: dict) -> float:
    if (p.get("art") or "leistung") in ("titel", "text"):
        return 0.0
    menge = _f(p.get("menge"))
    preis = _f(p.get("einzelpreis"))
    rabatt = max(0.0, min(100.0, _f(p.get("rabatt_prozent"))))
    return rund(menge * preis * (1 - rabatt / 100))


def steuer_bestimmen(firma: dict, kunde: Optional[dict], reverse_charge: Optional[bool] = None) -> dict:
    umkehr = bool(reverse_charge) if reverse_charge is not None else bool((kunde or {}).get("reverse_charge"))
    if umkehr:
        return {"kategorie": "AE", "satz": 0.0, "hinweis": "Steuerschuldnerschaft des Leistungsempfängers (§ 13b UStG)"}
    if firma.get("small_business"):
        return {"kategorie": "E", "satz": 0.0, "hinweis": "Keine Umsatzsteuer gemäß § 19 UStG (Kleinunternehmerregelung)"}
    return {"kategorie": "S", "satz": _f(firma.get("vat_rate"), 19.0), "hinweis": ""}


def summen(positionen: list[dict], zuschlaege: list[dict], rabatt_prozent: float, steuer: dict) -> dict:
    """Netto aus den Positionen (ohne Alternativ-/Eventualpositionen) → Zuschläge in Prozent → Angebotsrabatt → USt → Brutto."""
    positionen = nummerieren(positionen)
    netto_pos, alternativ, eventual = 0.0, 0.0, 0.0
    titel: list[dict] = []
    for p in positionen:
        betrag = position_betrag(p)
        p["gesamt"] = betrag
        if p.get("art") == "titel":
            titel.append({"nr": p["nr"], "text": p.get("text") or "", "netto": 0.0})
            continue
        if p.get("alternativ"):
            alternativ += betrag
            p["zaehlt"] = False
        elif p.get("eventual"):
            eventual += betrag
            p["zaehlt"] = False
        else:
            netto_pos += betrag
            p["zaehlt"] = True
            if titel and "." in (p.get("nr") or ""):
                titel[-1]["netto"] = rund(titel[-1]["netto"] + betrag)
    netto_pos = rund(netto_pos)
    zu_aus, zu_summe = [], 0.0
    for z in zuschlaege or []:
        prozent = _f(z.get("prozent"))
        betrag = rund(netto_pos * prozent / 100)
        zu_summe += betrag
        zu_aus.append({"text": str(z.get("text") or "Zuschlag")[:120], "prozent": prozent, "betrag": betrag})
    zwischen = rund(netto_pos + zu_summe)
    rabatt_prozent = max(0.0, min(100.0, _f(rabatt_prozent)))
    rabatt = rund(zwischen * rabatt_prozent / 100)
    netto = rund(zwischen - rabatt)
    satz = _f(steuer.get("satz"))
    ust = rund(netto * satz / 100)
    return {"positionen": positionen, "titel": titel, "positionen_netto": netto_pos, "zuschlaege": zu_aus, "zuschlaege_netto": rund(zu_summe),
            "rabatt_prozent": rabatt_prozent, "rabatt_betrag": rabatt, "netto": netto, "ust_satz": satz, "ust": ust, "brutto": rund(netto + ust),
            "alternativ_netto": rund(alternativ), "eventual_netto": rund(eventual), "steuer": steuer}


# ---------------------------------------------------------------- Kalkulation (vertraulich)

def firmen_kalkulation(firma: dict) -> dict:
    k = {**KALKULATION_STANDARD, **{kk: _f(v) for kk, v in (firma.get("kalkulation") or {}).items() if kk in KALKULATION_STANDARD}}
    return k


def kalkulation_position(p: dict, firma_k: dict) -> Optional[dict]:
    """Selbstkosten, Preisvorschlag und Kennzahlen einer Position. Unterscheidet ausdrücklich Aufschlag (auf die Kosten),
    Marge (am Verkaufspreis) und Deckungsbeitrag (Verkauf minus direkte Kosten, vor Gemeinkosten)."""
    k = p.get("kalkulation") or {}
    if (p.get("art") or "leistung") in ("titel", "text") or not any(_f(k.get(f)) for f in ("stunden", "material_ek", "fremd", "geraete", "transport", "sonstige")):
        return None
    stunden = _f(k.get("stunden"))
    stundensatz = _f(k.get("stundensatz")) or _f(firma_k.get("stundensatz"))
    lohn = rund(stunden * stundensatz)
    material = rund(_f(k.get("material_ek")))
    fremd, geraete, transport, sonstige = rund(_f(k.get("fremd"))), rund(_f(k.get("geraete"))), rund(_f(k.get("transport"))), rund(_f(k.get("sonstige")))
    direkt = rund(lohn + material + fremd + geraete + transport + sonstige)
    gk_prozent = _f(k.get("gemeinkosten_prozent"), firma_k.get("gemeinkosten_prozent", 0)) if k.get("gemeinkosten_prozent") not in (None, "") else _f(firma_k.get("gemeinkosten_prozent"))
    risiko_prozent = _f(k.get("risiko_prozent")) if k.get("risiko_prozent") not in (None, "") else _f(firma_k.get("risiko_prozent"))
    gewinn_prozent = _f(k.get("gewinn_prozent")) if k.get("gewinn_prozent") not in (None, "") else _f(firma_k.get("gewinn_prozent"))
    gemeinkosten = rund(direkt * gk_prozent / 100)
    risiko = rund((direkt + gemeinkosten) * risiko_prozent / 100)
    selbstkosten = rund(direkt + gemeinkosten + risiko)
    vk_vorschlag = rund(selbstkosten * (1 + gewinn_prozent / 100))
    vk = position_betrag(p)
    gewinn = rund(vk - selbstkosten)
    aus = {"stunden": stunden, "stundensatz": stundensatz, "lohn": lohn, "material_ek": material, "fremd": fremd, "geraete": geraete, "transport": transport,
           "sonstige": sonstige, "direkt": direkt, "gemeinkosten_prozent": gk_prozent, "gemeinkosten": gemeinkosten, "risiko_prozent": risiko_prozent, "risiko": risiko,
           "selbstkosten": selbstkosten, "gewinn_prozent": gewinn_prozent, "vk_vorschlag": vk_vorschlag, "vk": vk, "gewinn": gewinn,
           "aufschlag_prozent": rund(gewinn / selbstkosten * 100) if selbstkosten else None,
           "marge_prozent": rund(gewinn / vk * 100) if vk else None,
           "deckungsbeitrag": rund(vk - direkt), "stundenverrechnungssatz": rund(vk / stunden) if stunden else None,
           "ohne_stundensatz": stunden > 0 and not stundensatz}
    return aus


def kalkulation_angebot(a: dict, firma: dict) -> dict:
    """Kalkulation des ganzen Angebots über die zählenden Positionen; Verkauf = Netto nach Zuschlägen und Rabatt."""
    firma_k = firmen_kalkulation(firma)
    s = a.get("summen") or {}
    positionen = s.get("positionen") or a.get("positionen") or []
    felder = {f: 0.0 for f in ("lohn", "material_ek", "fremd", "geraete", "transport", "sonstige", "direkt", "gemeinkosten", "risiko", "selbstkosten", "stunden", "vk_vorschlag")}
    kalkuliert, zaehlend, ohne_satz = 0, 0, 0
    je_position = {}
    for p in positionen:
        if (p.get("art") or "leistung") in ("titel", "text"):
            continue
        k = kalkulation_position(p, firma_k)
        if k:
            je_position[p.get("id")] = k
        if not p.get("zaehlt", not (p.get("alternativ") or p.get("eventual"))):
            continue
        zaehlend += 1
        if not k:
            continue
        kalkuliert += 1
        if k["ohne_stundensatz"]:
            ohne_satz += 1
        for f in felder:
            felder[f] = rund(felder[f] + _f(k.get(f)))
    netto = _f(s.get("netto"))
    gewinn = rund(netto - felder["selbstkosten"])
    hinweise = []
    if zaehlend and kalkuliert < zaehlend:
        hinweise.append(f"{zaehlend - kalkuliert} von {zaehlend} Positionen ohne Kalkulation – Gewinn und Marge sind unvollständig.")
    if ohne_satz:
        hinweise.append("Interner Stundensatz fehlt (Firma → Kalkulation) – Lohnkosten sind mit 0 € gerechnet.")
    return {**felder, "netto": netto, "gewinn": gewinn, "vollstaendig": bool(zaehlend) and kalkuliert == zaehlend and not ohne_satz,
            "kalkuliert": kalkuliert, "zaehlend": zaehlend, "hinweise": hinweise,
            "aufschlag_prozent": rund(gewinn / felder["selbstkosten"] * 100) if felder["selbstkosten"] else None,
            "marge_prozent": rund(gewinn / netto * 100) if netto else None,
            "deckungsbeitrag": rund(netto - felder["direkt"]),
            "stundenverrechnungssatz": rund(netto / felder["stunden"]) if felder["stunden"] else None,
            "firma": firma_k, "je_position": je_position,
            "erklaerung": {"aufschlag": "Aufschlag = Gewinn ÷ Selbstkosten (bezogen auf die Kosten).",
                           "marge": "Marge = Gewinn ÷ Verkaufspreis (bezogen auf den Umsatz). 25 % Aufschlag sind nur 20 % Marge.",
                           "deckungsbeitrag": "Deckungsbeitrag = Verkauf − direkte Kosten (Lohn, Material, Fremdleistung, Geräte, Transport); deckt Gemeinkosten und Gewinn.",
                           "selbstkosten": "Selbstkosten = direkte Kosten + Gemeinkostenzuschlag + Risikozuschlag."}}


# ---------------------------------------------------------------- Sichten

def ohne_kalkulation(a: dict) -> dict:
    aus = {k: v for k, v in a.items() if k not in ("kalkulation",)}
    aus["positionen"] = [{k: v for k, v in p.items() if k != "kalkulation"} for p in a.get("positionen") or []]
    if aus.get("summen"):
        aus["summen"] = {**aus["summen"], "positionen": [{k: v for k, v in p.items() if k != "kalkulation"} for p in aus["summen"].get("positionen") or []]}
    return aus


def fuer_nutzer(a: dict, user: dict, firma: dict) -> dict:
    """Angebot für die Oberfläche: Kalkulation nur mit Recht; Status „abgelaufen“ wird aus der Gültigkeit abgeleitet."""
    a = {k: v for k, v in a.items() if k != "_id"}
    a["status_name"] = STATUS_NAMEN.get(a.get("status"), a.get("status"))
    if hat_recht(user, "kalkulation"):
        a["kalkulation"] = kalkulation_angebot(a, firma)
        return a
    return ohne_kalkulation(a)


def oeffentlich(a: dict, firma: dict) -> dict:
    """Was der Kunde über den Angebotslink sieht: keine Kalkulation, keine internen Vermerke, kein Verlauf."""
    s = a.get("summen") or {}
    return {"nummer": a.get("nummer"), "version": a.get("version"), "titel": a.get("titel"), "datum": a.get("datum"), "gueltig_bis": a.get("gueltig_bis"),
            "status": a.get("status"), "status_name": STATUS_NAMEN.get(a.get("status"), a.get("status")), "kunde": a.get("kunde"),
            "einleitung": a.get("einleitung"), "schluss": a.get("schluss"), "zahlungsbedingungen": a.get("zahlungsbedingungen"),
            "positionen": [{k: v for k, v in p.items() if k not in ("kalkulation", "leistung_id", "artikel_id")} for p in a.get("positionen") or []],
            "summen": {k: v for k, v in s.items() if k != "positionen"}, "annahme": a.get("annahme"), "ablehnung": a.get("ablehnung"),
            "firma": {k: firma.get(k) or "" for k in ("name", "owner", "street", "zip_code", "city", "phone", "email", "website", "logo")},
            "antwort_moeglich": a.get("status") == "gesendet" and not abgelaufen(a)}


def abgelaufen(a: dict, heute: Optional[str] = None) -> bool:
    heute = heute or date.today().isoformat()
    return a.get("status") == "gesendet" and bool(a.get("gueltig_bis")) and a["gueltig_bis"] < heute


# ---------------------------------------------------------------- Nummern, Verlauf, Snapshot

async def naechste_nummer(firma_id: str, jahr: int) -> int:
    """Laufende Angebotsnummer je Firma und Jahr (Zähler zählt nie zurück, siehe Rechnungen)."""
    letzte = await db().kundenangebote.find_one({"firma_id": firma_id, "jahr": jahr}, {"_id": 0, "seq": 1}, sort=[("seq", -1)])
    hoechste = int((letzte or {}).get("seq") or 0)
    feld = f"angebotszaehler.{jahr}"
    for _ in range(10):
        f = await db().firmen.find_one({"id": firma_id}, {"_id": 0, "angebotszaehler": 1})
        stand = int(((f or {}).get("angebotszaehler") or {}).get(str(jahr)) or 0)
        neu = max(stand, hoechste) + 1
        filt = {"id": firma_id, feld: stand} if stand else {"id": firma_id, "$or": [{feld: {"$exists": False}}, {feld: 0}, {feld: None}]}
        r = await db().firmen.update_one(filt, {"$set": {feld: neu}})
        if r.matched_count:
            return neu
    raise HTTPException(503, "Angebotsnummer konnte nicht vergeben werden, bitte noch einmal versuchen.")


def schritt(user: Optional[dict], aktion: str, text: str = "") -> dict:
    return {"aktion": aktion, "user_id": (user or {}).get("id"), "user_name": (user or {}).get("name") or "Kunde", "at": jetzt_iso(), "text": (text or "")[:500]}


def kunden_snapshot(k: Optional[dict], frei: Optional[dict] = None) -> dict:
    """Kundendaten als Momentaufnahme im Angebot (spätere Änderungen am Kunden ändern gesendete Angebote nicht)."""
    q = k or frei or {}
    return {"id": (k or {}).get("id"), "name": q.get("name") or "", "contact": q.get("contact") or "", "street": q.get("street") or "", "zip_code": q.get("zip_code") or "",
            "city": q.get("city") or "", "email": q.get("email") or "", "phone": q.get("phone") or "", "customer_number": q.get("customer_number") or "",
            "reverse_charge": bool(q.get("reverse_charge"))}


def neuer_token() -> str:
    return secrets.token_urlsafe(24)


def gueltig_bis_standard(firma: dict, datum: Optional[str] = None) -> str:
    tage = int(firma.get("angebot_gueltig_tage") or 30)
    start = date.fromisoformat(datum) if datum else date.today()
    return (start + timedelta(days=tage)).isoformat()


def pdf_daten(firma: dict, a: dict) -> dict:
    """Flache Struktur für das Angebots-PDF (gleicher Briefkopf wie die Rechnung)."""
    s = a.get("summen") or {}
    return {"art": "Angebot", "nummer": a.get("nummer") or "", "version": int(a.get("version") or 1), "titel": a.get("titel") or "", "datum": a.get("datum") or "",
            "gueltig_bis": a.get("gueltig_bis") or "", "kunde": a.get("kunde") or {}, "projekt": a.get("projekt_name") or "", "anfrage": (a.get("anfrage") or {}).get("text") or "",
            "einleitung": a.get("einleitung") or "", "schluss": a.get("schluss") or "", "zahlungsbedingungen": a.get("zahlungsbedingungen") or "",
            "positionen": a.get("positionen") or [], "summen": {k: v for k, v in s.items() if k != "positionen"}, "status": a.get("status"),
            "firma": {k: firma.get(k) or "" for k in ("name", "owner", "street", "zip_code", "city", "phone", "email", "website", "tax_number", "vat_id", "bank_name", "iban", "bic")},
            "logo": firma.get("logo") or "", "stempel": firma.get("stamp") if firma.get("stamp_on_invoice") else "", "stempel_scale": int(firma.get("stamp_scale") or 100),
            "annahme": a.get("annahme")}
