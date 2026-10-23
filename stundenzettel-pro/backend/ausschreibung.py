"""Ausschreibungen, Angebote und Vergabe auf der Plattform-Ebene – Rechtemodell und Hilfsfunktionen.

Grundsätze:
- Eine Ausschreibung gehört zum Projekt einer Eigentümerfirma; nur deren Projektleitung legt an, ändert, veröffentlicht, vergleicht und vergibt.
- Andere Firmen sehen eine Ausschreibung nur, wenn sie veröffentlicht ist UND (plattformweit sichtbar ODER die Firma eingeladen ist
  ODER die Firma bereits ein Angebot abgegeben hat). Entwürfe bleiben vertraulich. Fremde Projekt-/Ausschreibungs-IDs antworten 404.
- Angebote sieht nur die bietende Firma (Büro/Inhaber) selbst und – erst ab Einreichung – die Projektleitung der Eigentümerfirma.
  Bieter sehen niemals Angebote, Preise, Dokumente oder Bewertungen anderer Bieter. Bewertungen sieht nur die Eigentümerfirma.
- Fristen werden serverseitig geprüft (Datum in der Zeitzone der Anwendung). Nach der Angebotsfrist ist nur noch eine ausdrücklich
  angeforderte Nachreichung (Status „rueckfrage“ mit Nachreichfrist) möglich.
- Die Vergabe ist ein mehrstufiger Prozess (vorgeschlagen → freigegeben → mitgeteilt → angenommen). Die verbindliche Annahme erfordert
  den Inhaber der beauftragten Firma und eine ausdrückliche Bestätigung; erst dann entstehen Beteiligung und verknüpftes Projekt.
"""
from __future__ import annotations

from typing import Optional

from fastapi import HTTPException

from auth import hat_rolle, jetzt_iso
from db import db
from plattform import benachrichtigen, firma_kurz, zugang
from zeiten import lokal_jetzt

SICHTBARKEIT = ("oeffentlich", "privat", "kombiniert")
SICHTBARKEIT_NAMEN = {"oeffentlich": "Plattformweit sichtbar", "privat": "Nur eingeladene Firmen", "kombiniert": "Sichtbar + Einladungen"}
AUSSCHREIBUNG_STATUS = ("entwurf", "veroeffentlicht", "in_vergabe", "vergeben", "aufgehoben")
AUSSCHREIBUNG_STATUS_NAMEN = {"entwurf": "Entwurf", "veroeffentlicht": "Veröffentlicht", "in_vergabe": "In Vergabe", "vergeben": "Vergeben", "aufgehoben": "Aufgehoben"}
ABRECHNUNGSARTEN = {"pauschal": "Pauschalpreis", "einheitspreise": "Einheitspreise (Leistungsverzeichnis)", "stunden": "Nach Stunden", "gemischt": "Gemischt"}
PREISARTEN = ("pauschal", "einheitspreise", "stunden")
ANGEBOT_STATUS = ("entwurf", "eingereicht", "in_pruefung", "rueckfrage", "ueberarbeitet", "angenommen", "abgelehnt", "zurueckgezogen")
ANGEBOT_STATUS_NAMEN = {"entwurf": "Entwurf", "eingereicht": "Eingereicht", "in_pruefung": "In Prüfung", "rueckfrage": "Rückfrage / Nachforderung",
                        "ueberarbeitet": "Überarbeitet eingereicht", "angenommen": "Angenommen", "abgelehnt": "Abgelehnt", "zurueckgezogen": "Zurückgezogen"}
EINGEREICHT = ("eingereicht", "in_pruefung", "rueckfrage", "ueberarbeitet", "angenommen", "abgelehnt")   # für die Eigentümerfirma sichtbar
BEWERTUNGSKRITERIEN = ("preis", "leistung", "termin", "verfuegbarkeit", "qualifikation", "vollstaendigkeit", "mindestanforderungen")
VERGABE_STATUS = ("vorgeschlagen", "freigegeben", "mitgeteilt", "angenommen", "abgelehnt_firma", "zurueckgezogen")
VERGABE_STATUS_NAMEN = {"vorgeschlagen": "Zur Freigabe vorgeschlagen", "freigegeben": "Intern freigegeben", "mitgeteilt": "Firma benachrichtigt – Annahme offen",
                        "angenommen": "Verbindlich angenommen", "abgelehnt_firma": "Von der Firma abgelehnt", "zurueckgezogen": "Zurückgezogen"}
ANNAHME_TEXT = "Ich nehme den Auftrag verbindlich an"
KATEGORIEN_AUSSCHREIBUNG = ["Bilder", "Pläne", "Leistungsverzeichnis", "Technische Beschreibung", "Terminplan", "Sicherheit", "Vertragsentwurf", "Sonstiges"]
KATEGORIEN_ANGEBOT = ["Angebot (PDF)", "Leistungsverzeichnis", "Preisaufstellung", "Referenzen", "Zertifikate", "Versicherungsnachweis", "Qualifikationsnachweis", "Sonstiges"]
KATEGORIEN_VERGABE = ["Auftragsschreiben", "Vertrag", "Verhandlungsprotokoll", "Sonstiges"]
NACHFRIST_TAGE = 7


def heute() -> str:
    return lokal_jetzt().date().isoformat()


def schritt(user: dict, aktion: str, text: str = "", **extra) -> dict:
    return {"at": jetzt_iso(), "user_id": user["id"], "user_name": user.get("name"), "firma_id": user["firma_id"], "aktion": aktion, "text": (text or "")[:500], **extra}


def frist_offen(a: dict) -> bool:
    """Angebotsfrist läuft noch (einschließlich des Fristtags)."""
    return bool(a.get("angebotsfrist")) and heute() <= a["angebotsfrist"]


def frist_tage(a: dict) -> Optional[int]:
    from datetime import date
    try:
        return (date.fromisoformat(a["angebotsfrist"]) - date.fromisoformat(heute())).days
    except (TypeError, ValueError):
        return None


async def nummer_vergeben(firma_id: str, sammlung: str, praefix: str) -> str:
    """Laufende Nummer je Firma und Jahr (A-2026-0001 / AN-2026-0001)."""
    jahr = lokal_jetzt().year
    anzahl = await db()[sammlung].count_documents({"firma_id": firma_id, "nummer": {"$regex": f"^{praefix}-{jahr}-"}})
    for versuch in range(1, 50):
        nummer = f"{praefix}-{jahr}-{anzahl + versuch:04d}"
        if not await db()[sammlung].find_one({"firma_id": firma_id, "nummer": nummer}, {"_id": 0, "id": 1}):
            return nummer
    raise HTTPException(500, "Nummernvergabe fehlgeschlagen.")


async def ausschreibung_laden(ausschreibung_id: str) -> dict:
    a = await db().ausschreibungen.find_one({"id": ausschreibung_id}, {"_id": 0})
    if not a:
        raise HTTPException(404, "Ausschreibung nicht gefunden.")
    return a


async def einladung_der_firma(ausschreibung_id: str, firma_id: str) -> Optional[dict]:
    return await db().ausschreibung_einladungen.find_one({"ausschreibung_id": ausschreibung_id, "firma_id": firma_id}, {"_id": 0})


async def eigenes_angebot(ausschreibung_id: str, firma_id: str) -> Optional[dict]:
    """Je Firma gibt es höchstens ein Angebot je Ausschreibung (Überarbeitungen sind Versionen desselben Angebots)."""
    return await db().angebote.find_one({"ausschreibung_id": ausschreibung_id, "firma_id": firma_id}, {"_id": 0})


async def ausschreibung_zugang(user: dict, ausschreibung_id: str) -> dict:
    """Zugang zu einer Ausschreibung: 'leitung' (Projektleitung der Eigentümerfirma) oder 'bieter' (andere Firma, Büro/Inhaber).
    Alles andere: 404."""
    a = await ausschreibung_laden(ausschreibung_id)
    if a["firma_id"] == user["firma_id"]:
        z = await zugang(user, a["project_id"])
        if not z["leitung"]:
            raise HTTPException(404, "Ausschreibung nicht gefunden.")
        return {"ausschreibung": a, "rolle": "leitung", "zugang": z, "einladung": None, "angebot": None}
    if not hat_rolle(user, "buero"):
        raise HTTPException(403, "Ausschreibungen dürfen nur Büro oder Inhaber der Firma einsehen und bearbeiten.")
    einladung = await einladung_der_firma(a["id"], user["firma_id"])
    angebot = await eigenes_angebot(a["id"], user["firma_id"])
    sichtbar = a.get("status") in ("veroeffentlicht", "in_vergabe", "vergeben", "aufgehoben") and (
        (a.get("sichtbarkeit") in ("oeffentlich", "kombiniert") and a.get("status") != "aufgehoben") or einladung or angebot)
    if not sichtbar:
        raise HTTPException(404, "Ausschreibung nicht gefunden.")
    return {"ausschreibung": a, "rolle": "bieter", "zugang": None, "einladung": einladung, "angebot": angebot}


def leitung_noetig(zg: dict) -> None:
    if zg["rolle"] != "leitung":
        raise HTTPException(403, "Das darf nur die Projektleitung der ausschreibenden Firma.")


async def angebot_zugang(user: dict, angebot_id: str) -> tuple[dict, dict]:
    """Angebot plus Rolle: bietende Firma (Büro/Inhaber) oder Eigentümer-Leitung (nur eingereichte Angebote)."""
    g = await db().angebote.find_one({"id": angebot_id}, {"_id": 0})
    if not g:
        raise HTTPException(404, "Angebot nicht gefunden.")
    if g["firma_id"] == user["firma_id"]:
        if not hat_rolle(user, "buero"):
            raise HTTPException(403, "Angebote dürfen nur Büro oder Inhaber der Firma bearbeiten.")
        zg = await ausschreibung_zugang(user, g["ausschreibung_id"])
        return g, {**zg, "rolle": "bieter"}
    zg = await ausschreibung_zugang(user, g["ausschreibung_id"])
    if zg["rolle"] != "leitung" or g.get("status") not in EINGEREICHT:
        raise HTTPException(404, "Angebot nicht gefunden.")
    return g, zg


async def vergabe_zugang(user: dict, vergabe_id: str) -> tuple[dict, str]:
    v = await db().vergaben.find_one({"id": vergabe_id}, {"_id": 0})
    if not v:
        raise HTTPException(404, "Vergabe nicht gefunden.")
    if v["owner_firma_id"] == user["firma_id"]:
        z = await zugang(user, v["project_id"])
        if not z["leitung"]:
            raise HTTPException(404, "Vergabe nicht gefunden.")
        return v, "leitung"
    if v["firma_id"] == user["firma_id"] and hat_rolle(user, "buero") and v.get("status") in ("mitgeteilt", "angenommen", "abgelehnt_firma", "zurueckgezogen"):
        return v, "firma"
    raise HTTPException(404, "Vergabe nicht gefunden.")


async def dokument_zugang(user: dict, scope: str, ref_id: str) -> None:
    """Dateizugriff für die Scopes ausschreibung / angebot / vergabe – immer über den zugehörigen Eintrag."""
    if scope == "ausschreibung":
        await ausschreibung_zugang(user, ref_id)
    elif scope == "angebot":
        await angebot_zugang(user, ref_id)
    elif scope == "vergabe":
        await vergabe_zugang(user, ref_id)
    else:
        raise HTTPException(404, "Dokument nicht gefunden.")


def positionen_berechnen(ausschreibung: dict, angebot: dict) -> dict:
    """Einzelpreise des Angebots mit den Mengen der Ausschreibung verrechnen; Summe und Vollständigkeit ermitteln."""
    vorgaben = {p["nr"]: p for p in ausschreibung.get("positionen") or []}
    preise = {p["nr"]: p for p in angebot.get("positionen") or []}
    zeilen, summe, fehlend = [], 0.0, []
    for nr, v in vorgaben.items():
        ep = preise.get(nr, {}).get("einzelpreis")
        gesamt = round(float(v.get("menge") or 0) * float(ep), 2) if ep is not None else None
        if ep is None:
            fehlend.append(nr)
        else:
            summe += gesamt
        zeilen.append({"nr": nr, "leistung": v.get("leistung"), "menge": v.get("menge"), "einheit": v.get("einheit"), "einzelpreis": ep, "gesamt": gesamt,
                       "bemerkung": preise.get(nr, {}).get("bemerkung", "")})
    return {"zeilen": zeilen, "summe": round(summe, 2), "fehlend": fehlend, "vollstaendig": not fehlend and bool(vorgaben)}


def angebot_summe(ausschreibung: dict, angebot: dict) -> float:
    art = angebot.get("preisart") or "pauschal"
    if art == "einheitspreise":
        return positionen_berechnen(ausschreibung, angebot)["summe"]
    if art == "stunden":
        return round(float(angebot.get("stundensatz") or 0) * float(angebot.get("stunden_geschaetzt") or 0), 2)
    return round(float(angebot.get("preis_netto") or 0), 2)


def oeffentliche_ansicht(a: dict) -> dict:
    """Die Felder einer Ausschreibung, die Bieter sehen dürfen (Budget nur mit Freigabe, nie interne Vermerke/Verlauf)."""
    frei = a.get("freigabe") or {}
    aus = {k: a.get(k) for k in ("id", "nummer", "titel", "gewerk", "leistungsart", "beschreibung", "leistungsumfang", "ausfuehrungsort", "sichtbarkeit", "status",
                                 "veroeffentlicht_am", "bewerbungsfrist", "angebotsfrist", "ausfuehrung_von", "ausfuehrung_bis", "anforderungen", "positionen",
                                 "project_id", "firma_id", "verantwortlich_name", "updated_at")}
    k = dict(a.get("kaufmaennisch") or {})
    if not frei.get("budget"):
        k.pop("budget", None)
    aus["kaufmaennisch"] = k
    aus["status_name"] = AUSSCHREIBUNG_STATUS_NAMEN.get(a.get("status"), a.get("status"))
    aus["frist_offen"] = frist_offen(a)
    aus["frist_tage"] = frist_tage(a)
    return aus


async def auftraggeber_info(a: dict) -> dict:
    frei = a.get("freigabe") or {}
    f = await firma_kurz(a["firma_id"])
    if frei.get("auftraggeber", True):
        return {"name": f.get("name"), "city": f.get("city"), "anonym": False}
    return {"name": "Auftraggeber (auf Anfrage)", "city": f.get("city"), "anonym": True}


async def leitung_benachrichtigen(a: dict, art: str, text: str, link: str = "") -> None:
    """Verantwortlichen Projektleiter plus Projektleitung der Eigentümerfirma informieren."""
    from plattform import eigentuemer_benachrichtigen
    p = await db().projects.find_one({"id": a["project_id"]}, {"_id": 0})
    if p:
        await eigentuemer_benachrichtigen(p, art, text, link or f"/ausschreibungen/{a['id']}")
    else:
        await benachrichtigen(a["firma_id"], art, text, link or f"/ausschreibungen/{a['id']}")


async def interessierte_firmen(a: dict) -> list[str]:
    """Firmen, deren Verzeichnis-Interessen (Gewerke, Regionen) zur Ausschreibung passen – für „neue passende Ausschreibung“."""
    gewerk = (a.get("gewerk") or "").strip().lower()
    ort = " ".join(t for t in [a.get("ausfuehrungsort") or "", a.get("_projekt_adresse") or ""] if t).lower()
    aus = []
    async for f in db().firmen.find({"id": {"$ne": a["firma_id"]}, "verzeichnis.gewerke": {"$exists": True}}, {"_id": 0, "id": 1, "verzeichnis": 1, "art": 1}):
        v = f.get("verzeichnis") or {}
        if v.get("ausschreibungen_benachrichtigen") is False or f.get("art") == "auftraggeber":
            continue
        gewerke = [g.lower() for g in v.get("gewerke") or []]
        if gewerk and gewerk not in gewerke:
            continue
        regionen = [r.strip().lower() for r in v.get("regionen") or [] if r and r.strip()]
        if regionen and ort and not any(r in ort for r in regionen):
            continue
        aus.append(f["id"])
    return aus


async def angebot_anreichern(g: dict, a: dict, fuer_leitung: bool) -> dict:
    g = dict(g)
    g["firma"] = await firma_kurz(g["firma_id"])
    g["status_name"] = ANGEBOT_STATUS_NAMEN.get(g.get("status"), g.get("status"))
    g["berechnung"] = positionen_berechnen(a, g) if a.get("positionen") else None
    g["summe_netto"] = angebot_summe(a, g)
    ust = float(g.get("ust_satz") if g.get("ust_satz") is not None else 19)
    g["summe_brutto"] = round(g["summe_netto"] * (1 + ust / 100), 2) if not g.get("reverse_charge") else g["summe_netto"]
    g["dokumente"] = [d async for d in db().documents.find({"scope": "angebot", "ref_id": g["id"]}, {"_id": 0, "path": 0}).sort("created_at", 1)]
    if not fuer_leitung:
        g.pop("bewertung", None)
        g.pop("intern", None)
    return g


async def neue_vergabe_pruefen(a: dict) -> None:
    offen = await db().vergaben.find_one({"ausschreibung_id": a["id"], "status": {"$in": ["vorgeschlagen", "freigegeben", "mitgeteilt", "angenommen"]}}, {"_id": 0, "id": 1})
    if offen:
        raise HTTPException(409, "Für diese Ausschreibung läuft bereits eine Vergabe.")


def vergabe_schritt(user: dict, status: str, text: str = "") -> dict:
    return {"status": status, "at": jetzt_iso(), "user_id": user["id"], "user_name": user.get("name"), "firma_id": user["firma_id"], "text": (text or "")[:500]}


async def zweites_augenpaar(firma_id: str, user_id: str) -> bool:
    """Gibt es in der Firma eine weitere freigabeberechtigte Person (Büro/Inhaber)? Dann gilt das Vier-Augen-Prinzip."""
    andere = await db().users.find_one({"firma_id": firma_id, "id": {"$ne": user_id}, "role": {"$in": ["buero", "inhaber"]}, "active": {"$ne": False}}, {"_id": 0, "id": 1})
    return bool(andere)

