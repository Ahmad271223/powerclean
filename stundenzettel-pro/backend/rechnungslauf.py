"""Rechnungsprozesse (Stufe E): Rechnung aus dem Auftrag, Abschlags- und kumulative Abschlagsrechnungen, Schlussrechnung, Storno/Korrekturbeleg,
Gutschrift, Teilzahlungen und Mahnwesen – alles in der bestehenden Sammlung `invoices` mit demselben Nummernkreis (`firmen.rechnungszaehler`),
derselben Festschreibung und denselben E-Rechnungsformaten.

Rechnungsarten (`art`): monat (bisherige Monatsrechnung aus Zeiten), pauschal (Rechnung aus dem Auftrag), abschlag, schluss, storno, gutschrift.
Nicht-Monatsrechnungen tragen `month = -seq` (negativ, |month| = laufende Nummer), damit der eindeutige Index (Firma, Projekt, Jahr, Monat) nicht kollidiert;
ihre Positionen liegen als freie Zeilen in `extras` (text, quantity, unit, unit_price, amount), die PDF und XML schon kennen.

Kumulative Abschläge: Leistungsstand in Prozent des Auftragswerts (plus freigegebene Nachträge) abzüglich bereits gestellter Abschläge (netto);
die Umsatzsteuer entsteht auf den Differenzbetrag. Die Schlussrechnung stellt die Gesamtleistung dar und zieht alle Abschläge (gestellte Nettobeträge)
ab – Zahlungen werden nicht abgezogen, sondern informativ ausgewiesen (offene Abschläge bleiben offen).
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from angebote import rund
from db import db

ARTEN = {"monat": "Rechnung", "pauschal": "Rechnung", "abschlag": "Abschlagsrechnung", "schluss": "Schlussrechnung", "storno": "Stornorechnung", "gutschrift": "Gutschrift"}
TYPECODES = {"monat": "380", "pauschal": "380", "abschlag": "326", "schluss": "380", "storno": "384", "gutschrift": "381"}
STATUS_NAMEN = {"offen": "Offen", "teilbezahlt": "Teilweise bezahlt", "bezahlt": "Bezahlt", "storniert": "Storniert"}
ZAHLUNGSARTEN = {"ueberweisung": "Überweisung", "bar": "Bar", "karte": "Karte", "lastschrift": "Lastschrift", "verrechnung": "Verrechnung", "skonto": "Skonto / Nachlass"}
MAHNSTUFEN = {1: "Zahlungserinnerung", 2: "Mahnung", 3: "Letzte Mahnung"}
MAHNWESEN_STANDARD = {
    "erinnerung_tage": 3, "mahnung_tage": 14, "letzte_mahnung_tage": 14, "gebuehr_mahnung": 0.0, "gebuehr_letzte": 0.0,
    "text_erinnerung": "sicher ist es Ihrer Aufmerksamkeit entgangen, dass die unten aufgeführte Rechnung noch nicht beglichen ist. Wir bitten Sie, den offenen Betrag in den nächsten Tagen zu überweisen. Sollte sich Ihre Zahlung mit diesem Schreiben überschnitten haben, betrachten Sie es bitte als gegenstandslos.",
    "text_mahnung": "trotz unserer Zahlungserinnerung ist die unten aufgeführte Rechnung noch offen. Wir bitten Sie, den Betrag innerhalb von 10 Tagen zu begleichen.",
    "text_letzte": "leider ist die unten aufgeführte Rechnung trotz Erinnerung und Mahnung weiterhin offen. Wir fordern Sie letztmalig auf, den Betrag innerhalb von 7 Tagen zu überweisen. Danach behalten wir uns weitere Schritte vor.",
}


def _f(x, standard: float = 0.0) -> float:
    try:
        return float(x) if x not in (None, "") else standard
    except (TypeError, ValueError):
        return standard


# ---------------------------------------------------------------- Summen freier Zeilen (wie rechnung_berechnen, nur ohne Zeiten)

def zeile(text: str, betrag: float, menge: float = 1, einheit: str = "Psch.", einzelpreis: Optional[float] = None) -> dict:
    menge = float(menge or 1)
    ep = rund(einzelpreis if einzelpreis is not None else (betrag / menge if menge else betrag))
    return {"text": str(text)[:200], "quantity": menge, "unit": str(einheit or "Psch.")[:20], "unit_price": ep, "amount": rund(betrag)}


def zeilen_summen(firma: dict, reverse_charge: bool, zeilen: list[dict]) -> dict:
    """Summenblock in der Form von `_summen()` der Monatsrechnung: Zeiten 0, alle Beträge aus den freien Zeilen."""
    netto = rund(sum(_f(z.get("amount")) for z in zeilen))
    ust_satz = 0.0 if (firma.get("small_business") or reverse_charge) else _f(firma.get("vat_rate"), 19.0)
    ust = rund(netto * ust_satz / 100)
    return {"total_minutes": 0, "rate": 0, "hours_net": 0.0, "extras_net": netto, "net": netto, "vat_rate": ust_satz, "vat": ust, "gross": rund(netto + ust),
            "reverse_charge": bool(reverse_charge), "positions": [], "extras": zeilen}


# ---------------------------------------------------------------- Auftrag, Abschläge, Schlussrechnung

async def auftragsbasis(firma_id: str, projekt: dict) -> dict:
    """Auftragswert (Auftrag aus Angebot oder Pauschale) plus freigegebene Nachträge der eigenen Firma zu diesem Projekt."""
    auftrag = projekt.get("auftrag") or {}
    wert = _f(auftrag.get("netto")) if auftrag else _f(projekt.get("pauschale_netto"))
    nachtraege = []
    async for n in db().nachtraege.find({"firma_id": firma_id, "status": "freigegeben", "$or": [{"project_id": projekt["id"]}, {"project_id": (projekt.get("verknuepft") or {}).get("project_id") or "-"}]}, {"_id": 0}):
        nachtraege.append({"id": n["id"], "titel": n.get("titel"), "betrag_netto": rund(n.get("betrag_netto")), "nummer": n.get("nummer")})
    return {"auftragswert_netto": rund(wert), "auftrag": auftrag or None, "nachtraege": nachtraege, "nachtraege_netto": rund(sum(n["betrag_netto"] for n in nachtraege)),
            "basis_netto": rund(wert + sum(n["betrag_netto"] for n in nachtraege))}


async def abschlaege_bisher(firma_id: str, project_id: str) -> list[dict]:
    """Gestellte (nicht stornierte) Abschlagsrechnungen des Projekts, älteste zuerst."""
    aus = []
    async for r in db().invoices.find({"firma_id": firma_id, "project_id": project_id, "art": "abschlag", "status": {"$ne": "storniert"}}, {"_id": 0}).sort([("year", 1), ("seq", 1)]):
        aus.append(r)
    return aus


async def schlussrechnung_bisher(firma_id: str, project_id: str) -> Optional[dict]:
    return await db().invoices.find_one({"firma_id": firma_id, "project_id": project_id, "art": "schluss", "status": {"$ne": "storniert"}}, {"_id": 0})


def abschlag_zeilen(basis: dict, vorherige: list[dict], betrag_netto: Optional[float], prozent: Optional[float], nr: int) -> tuple[list[dict], dict]:
    auftrag_nr = (basis.get("auftrag") or {}).get("nummer")
    bezug = f"Auftrag {auftrag_nr}" if auftrag_nr else "Auftrag"
    if prozent is not None:
        kumuliert = rund(basis["basis_netto"] * prozent / 100)
        bisher = rund(sum(_f(v.get("net")) for v in vorherige))
        zeilen = [zeile(f"{nr}. Abschlagsrechnung – Leistungsstand {prozent:g} % der Auftragssumme von {basis['basis_netto']:,.2f} € ({bezug})".replace(",", "X").replace(".", ",").replace("X", "."), kumuliert)]
        for v in vorherige:
            zeilen.append(zeile(f"abzüglich Abschlagsrechnung {v.get('number')} vom {_de(v.get('invoice_date'))} (netto)", -_f(v.get("net"))))
        info = {"kumulativ": True, "leistungsstand_prozent": prozent, "kumuliert_netto": kumuliert, "bisher_netto": bisher, "neu_netto": rund(kumuliert - bisher)}
        return zeilen, info
    zeilen = [zeile(f"{nr}. Abschlagszahlung auf {bezug}", _f(betrag_netto))]
    return zeilen, {"kumulativ": False, "neu_netto": rund(betrag_netto)}


def schluss_zeilen(basis: dict, vorherige: list[dict]) -> tuple[list[dict], dict]:
    auftrag = basis.get("auftrag") or {}
    zeilen = []
    if auftrag.get("positionen"):
        for p in auftrag["positionen"]:
            if p.get("art") in ("titel", "text"):
                continue
            zeilen.append(zeile(f"{p.get('nr') + ' ' if p.get('nr') else ''}{p.get('text') or 'Leistung'}", _f(p.get("gesamt")), _f(p.get("menge"), 1), p.get("einheit") or "Psch.", _f(p.get("einzelpreis"))))
        differenz = rund(basis["auftragswert_netto"] - sum(z["amount"] for z in zeilen))
        if abs(differenz) >= 0.01:
            zeilen.append(zeile("Zuschläge / Rabatt laut Auftrag", differenz))
    else:
        zeilen.append(zeile(f"Gesamtleistung laut {('Auftrag ' + auftrag['nummer']) if auftrag.get('nummer') else 'Auftrag / Pauschale'}", basis["auftragswert_netto"]))
    for n in basis.get("nachtraege") or []:
        zeilen.append(zeile(f"Nachtrag {n.get('nummer') or ''} {n.get('titel') or ''}".strip(), n["betrag_netto"]))
    for v in vorherige:
        zeilen.append(zeile(f"abzüglich Abschlagsrechnung {v.get('number')} vom {_de(v.get('invoice_date'))} (netto)", -_f(v.get("net"))))
    abschlaege_netto = rund(sum(_f(v.get("net")) for v in vorherige))
    offen_abschlaege = rund(sum(_f(v.get("gross")) - _f(v.get("bezahlt_betrag")) for v in vorherige if v.get("status") != "bezahlt"))
    return zeilen, {"abschlaege_netto": abschlaege_netto, "rest_netto": rund(basis["basis_netto"] - abschlaege_netto), "offen_aus_abschlaegen_brutto": offen_abschlaege}


def storno_zeilen(original: dict) -> list[dict]:
    """Gegenbuchung: alle Positionen und Zusatzzeilen der Originalrechnung mit negativen Beträgen."""
    zeilen = []
    for p in original.get("positions") or []:
        name = f"{p.get('service') or 'Arbeiten'} KW {p.get('week')} ({_de(p.get('from'))} – {_de(p.get('to'))})"
        zeilen.append({"text": name[:200], "quantity": _f(p.get("hours")), "unit": "Std.", "unit_price": -_f(p.get("rate")), "amount": -_f(p.get("amount"))})
    for x in original.get("extras") or []:
        zeilen.append({"text": str(x.get("text") or "")[:200], "quantity": _f(x.get("quantity"), 1), "unit": x.get("unit") or "Psch.", "unit_price": -_f(x.get("unit_price")), "amount": -_f(x.get("amount"))})
    return zeilen


# ---------------------------------------------------------------- Zahlungen

def zahlungsstand(r: dict) -> dict:
    bezahlt = rund(sum(_f(z.get("betrag")) for z in r.get("zahlungen") or []))
    brutto = _f(r.get("gross"))
    offen = rund(brutto - bezahlt)
    if r.get("status") == "storniert":
        status = "storniert"
    elif brutto > 0 and offen <= 0.005:
        status = "bezahlt"
    elif bezahlt > 0:
        status = "teilbezahlt"
    else:
        status = "offen"
    return {"bezahlt_betrag": bezahlt, "offen_betrag": max(0.0, offen) if brutto >= 0 else offen, "status": status}


def faellig_am(r: dict, firma: dict) -> Optional[str]:
    if r.get("faellig_am"):
        return r["faellig_am"]
    datum = r.get("invoice_date")
    if not datum:
        return None
    try:
        return (date.fromisoformat(str(datum)[:10]) + timedelta(days=int(firma.get("payment_days") or 14))).isoformat()
    except ValueError:
        return None


# ---------------------------------------------------------------- Mahnwesen

def mahn_regeln(firma: dict) -> dict:
    return {**MAHNWESEN_STANDARD, **{k: v for k, v in (firma.get("mahnwesen") or {}).items() if v not in (None, "")}}


def mahn_vorschlag(r: dict, firma: dict, heute: Optional[date] = None) -> Optional[dict]:
    """Nächste Mahnstufe und ob sie fällig ist (Fristen aus den Firmenregeln); None, wenn nichts offen oder nicht überfällig."""
    heute = heute or date.today()
    if r.get("art") in ("storno", "gutschrift") or not r.get("festgeschrieben_at"):
        return None
    stand = zahlungsstand(r)
    if stand["status"] in ("bezahlt", "storniert") or stand["offen_betrag"] <= 0.005:
        return None
    faellig = faellig_am(r, firma)
    if not faellig or faellig >= heute.isoformat():
        return None
    regeln = mahn_regeln(firma)
    tage = (heute - date.fromisoformat(faellig)).days
    stufe = int(r.get("mahnstufe") or 0)
    naechste = stufe + 1 if stufe < 3 else None
    letzte = (r.get("mahnungen") or [{}])[-1].get("am") if r.get("mahnungen") else None
    if naechste == 1:
        faellig_ab = date.fromisoformat(faellig) + timedelta(days=int(regeln["erinnerung_tage"]))
    elif naechste in (2, 3) and letzte:
        faellig_ab = date.fromisoformat(letzte) + timedelta(days=int(regeln["mahnung_tage"] if naechste == 2 else regeln["letzte_mahnung_tage"]))
    else:
        faellig_ab = None
    return {"tage_ueberfaellig": tage, "offen_betrag": stand["offen_betrag"], "mahnstufe": stufe, "naechste_stufe": naechste,
            "naechste_name": MAHNSTUFEN.get(naechste) if naechste else None, "faellig_ab": faellig_ab.isoformat() if faellig_ab else None,
            "jetzt_faellig": bool(naechste and faellig_ab and faellig_ab <= heute), "letzte_mahnung_am": letzte, "faellig_am": faellig}


def mahn_gebuehr(stufe: int, regeln: dict) -> float:
    return rund(regeln["gebuehr_mahnung"] if stufe == 2 else regeln["gebuehr_letzte"] if stufe == 3 else 0)


def mahn_text(stufe: int, regeln: dict) -> str:
    return regeln["text_erinnerung"] if stufe == 1 else regeln["text_mahnung"] if stufe == 2 else regeln["text_letzte"]


def _de(iso) -> str:
    try:
        return date.fromisoformat(str(iso)[:10]).strftime("%d.%m.%Y")
    except (ValueError, TypeError):
        return str(iso or "–")
