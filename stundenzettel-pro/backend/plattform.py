"""Zusammenarbeit mehrerer Firmen an einem Projekt (Generalunternehmer ↔ Subunternehmer).

Grundsatz: Jede Firma behält ihre eigene Datenwelt (`firma_id`). Ein Projekt gehört genau einer Firma (Eigentümerin).
Andere Firmen nehmen über eine *Beteiligung* teil. Bei Annahme entsteht in der Partnerfirma ein verknüpftes lokales Projekt,
auf dem alle bestehenden Funktionen (Stempeluhr, Stundenzettel, Rechnungen, Lohn) unverändert und getrennt laufen.
Zwischen den Firmen fließen nur: Aufgaben, Fotos zu Aufgaben, Anwesenheitszahlen (Namen nur nach Freigabe) und ausdrücklich
freigegebene Wochen-Nachweise. Personalakten, Lohndaten, Stundenkonten und Rechnungen bleiben immer in der eigenen Firma.

Rechte werden hier für jede Anfrage serverseitig aus Datenbankzuständen abgeleitet (Eigentümerfirma, Projektleitung,
aktive Beteiligung, Zuteilung), nie aus einer mitgeschickten Firmen-ID.
"""
from __future__ import annotations

from typing import Optional

from fastapi import HTTPException

from auth import hat_rolle, jetzt_iso
from db import db
from gemeinsam import neue_id, projekt_leitung, projekt_normalisieren, projekt_sichtbar

AUFGABEN_STATUS = ("geplant", "zugewiesen", "in_bearbeitung", "blockiert", "eingereicht", "abgeschlossen", "abgenommen")
STATUS_NAMEN = {"geplant": "Geplant", "zugewiesen": "Zugewiesen", "in_bearbeitung": "In Bearbeitung", "blockiert": "Blockiert",
                "eingereicht": "Zur Prüfung eingereicht", "abgeschlossen": "Abgeschlossen", "abgenommen": "Abgenommen"}
OFFEN = ("geplant", "zugewiesen", "in_bearbeitung", "blockiert", "eingereicht")
PARTNER_STATUS = {"in_bearbeitung", "blockiert", "eingereicht"}       # darf die beauftragte Firma (Büro/Vorarbeiter) setzen
MITARBEITER_STATUS = {"in_bearbeitung", "eingereicht"}               # darf ein zugeteilter Mitarbeiter setzen
ROLLEN_BETEILIGUNG = {"subunternehmer": "Subunternehmer", "nachunternehmer": "Nachunternehmer", "dienstleister": "Dienstleister",
                      "lieferant": "Lieferant"}
GEWERKE = ["Reinigung", "Elektro", "Sanitär / Heizung", "Trockenbau", "Maler", "Boden", "Rohbau", "Dach", "Fenster / Glas",
           "Garten / Außenanlagen", "Logistik", "Sicherheit", "Sonstiges"]
EINLADUNG_TAGE = 30


async def firma_kurz(firma_id: Optional[str]) -> dict:
    """Öffentlich unkritische Firmendaten für Partner (Name, Ort, Kontakt), nie Lizenz, Bank oder Einstellungen."""
    f = await db().firmen.find_one({"id": firma_id}, {"_id": 0, "id": 1, "name": 1, "city": 1, "zip_code": 1, "street": 1, "email": 1, "phone": 1, "logo": 1}) if firma_id else None
    if not f:
        return {"id": firma_id, "name": "Unbekannte Firma", "city": ""}
    return f


async def zugang(user: dict, project_id: str) -> dict:
    """Zugang zu einem Plattform-Projekt.

    Eigentümerfirma: Büro/Inhaber immer, Projektleiter (leiter_ids) und zugewiesene Mitarbeiter wie bisher.
    Partnerfirma: nur mit aktiver Beteiligung; Mitarbeiter der Partnerfirma zusätzlich nur, wenn sie dem verknüpften lokalen Projekt
    zugewiesen sind. Alles andere: 404 (die Existenz fremder Projekte wird nicht verraten)."""
    p = await db().projects.find_one({"id": project_id}, {"_id": 0})
    if not p:
        raise HTTPException(404, "Projekt nicht gefunden.")
    p = projekt_normalisieren(p)
    if p["firma_id"] == user["firma_id"]:
        if not projekt_sichtbar(user, p):
            raise HTTPException(404, "Projekt nicht gefunden.")
        return {"projekt": p, "eigentuemer": True, "leitung": projekt_leitung(user, p), "beteiligung": None, "lokal": p}
    b = await db().beteiligungen.find_one({"project_id": project_id, "firma_id": user["firma_id"], "status": "aktiv"}, {"_id": 0})
    if not b:
        raise HTTPException(404, "Projekt nicht gefunden.")
    lokal = None
    if b.get("lokales_project_id"):
        lokal = await db().projects.find_one({"id": b["lokales_project_id"], "firma_id": user["firma_id"]}, {"_id": 0})
        lokal = projekt_normalisieren(lokal) if lokal else None
    if lokal and not projekt_sichtbar(user, lokal):
        raise HTTPException(404, "Projekt nicht gefunden.")
    return {"projekt": p, "eigentuemer": False, "leitung": bool(lokal and projekt_leitung(user, lokal)) or hat_rolle(user, "buero"),
            "beteiligung": b, "lokal": lokal}


def leitung_noetig(z: dict) -> None:
    if not (z["eigentuemer"] and z["leitung"]):
        raise HTTPException(403, "Das darf nur die Projektleitung der Eigentümerfirma.")


async def aufgabe_laden(user: dict, aufgabe_id: str) -> tuple[dict, dict]:
    """Aufgabe plus Zugang. Partnerfirmen sehen nur Aufgaben, die ihrer Firma zugeordnet sind; Mitarbeiter nur ihre zugeteilten."""
    a = await db().aufgaben.find_one({"id": aufgabe_id}, {"_id": 0})
    if not a:
        raise HTTPException(404, "Aufgabe nicht gefunden.")
    z = await zugang(user, a["project_id"])
    eigene_firma = a.get("firma_id") == user["firma_id"]
    if not z["eigentuemer"] and not eigene_firma:
        raise HTTPException(404, "Aufgabe nicht gefunden.")
    if not z["leitung"] and not hat_rolle(user, "buero"):
        zugeteilt = a.get("mitarbeiter_ids") or []
        if not eigene_firma or (zugeteilt and user["id"] not in zugeteilt and a.get("vorarbeiter_user_id") != user["id"]):
            raise HTTPException(404, "Aufgabe nicht gefunden.")
    return a, z


def rolle_fuer_aufgabe(user: dict, a: dict, z: dict) -> str:
    """'leitung' (Eigentümer-Projektleitung), 'firma' (Büro/Vorarbeiter der beauftragten Firma), 'mitarbeiter' (zugeteilt) oder ''."""
    if z["eigentuemer"] and z["leitung"]:
        return "leitung"
    if a.get("firma_id") == user["firma_id"]:
        lokal = z.get("lokal")
        if hat_rolle(user, "buero") or (lokal and projekt_leitung(user, lokal)):
            return "firma"
        zugeteilt = a.get("mitarbeiter_ids") or []
        if user["id"] in zugeteilt or a.get("vorarbeiter_user_id") == user["id"] or not zugeteilt:
            return "mitarbeiter"
    return ""


async def benachrichtigen(firma_id: str, art: str, text: str, link: str = "", user_ids: Optional[list[str]] = None,
                          mindestens: str = "buero") -> None:
    """In-App-Benachrichtigung: an bestimmte Nutzer einer Firma oder an alle ab einer Rolle (Standard: Büro/Inhaber)."""
    await db().benachrichtigungen.insert_one({"id": neue_id(), "firma_id": firma_id, "user_ids": user_ids, "mindestens": mindestens,
                                              "art": art, "text": text[:300], "link": link, "gelesen_von": [], "created_at": jetzt_iso()})


async def meine_benachrichtigungen(user: dict, limit: int = 50) -> list[dict]:
    aus = []
    async for n in db().benachrichtigungen.find({"firma_id": user["firma_id"]}, {"_id": 0}).sort("created_at", -1).limit(400):
        if n.get("user_ids"):
            if user["id"] not in n["user_ids"]:
                continue
        elif not hat_rolle(user, n.get("mindestens") or "buero"):
            continue
        n["gelesen"] = user["id"] in (n.get("gelesen_von") or [])
        n.pop("gelesen_von", None)
        aus.append(n)
        if len(aus) >= limit:
            break
    return aus


async def leiter_ids(project_id: str) -> list[str]:
    p = await db().projects.find_one({"id": project_id}, {"_id": 0, "leiter_ids": 1})
    return list((p or {}).get("leiter_ids") or [])


async def eigentuemer_benachrichtigen(projekt: dict, art: str, text: str, link: str = "") -> None:
    """Projektleitung der Eigentümerfirma informieren: eingetragene Projektleiter plus Büro/Inhaber."""
    ids = list(projekt.get("leiter_ids") or [])
    async for u in db().users.find({"firma_id": projekt["firma_id"], "role": {"$in": ["buero", "inhaber"]}, "active": {"$ne": False}}, {"_id": 0, "id": 1}):
        if u["id"] not in ids:
            ids.append(u["id"])
    await benachrichtigen(projekt["firma_id"], art, text, link, user_ids=ids or None)
