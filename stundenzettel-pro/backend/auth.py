"""Anmeldung, Passwörter, Rollen und Lizenzprüfung.

Rollen: inhaber (alles) > buero (alles außer Lizenz/API-Schlüssel/Firma löschen) > mitarbeiter
(eigene Zeiten, Stempeluhr, zugewiesene Projekte, eigene Abwesenheiten, eigene Akte lesen).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, Header, HTTPException

import config
from db import db

ROLLEN = {"mitarbeiter": 1, "vorarbeiter": 2, "buero": 3, "inhaber": 4}
ROLLEN_NAMEN = {"mitarbeiter": "Mitarbeiter", "vorarbeiter": "Vorarbeiter", "buero": "Büro", "inhaber": "Inhaber"}


def jetzt() -> datetime:
    return datetime.now(timezone.utc)


def jetzt_iso() -> str:
    return jetzt().isoformat()


# ---------------------------------------------------------------- Passwörter
def passwort_hash(passwort: str) -> str:
    salt = os.urandom(16)
    h = hashlib.pbkdf2_hmac("sha256", passwort.encode("utf-8"), salt, 200_000)
    return "pbkdf2$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(h).decode()


def passwort_pruefen(passwort: str, gespeichert: Optional[str]) -> bool:
    try:
        art, salt_b64, hash_b64 = (gespeichert or "").split("$")
        if art != "pbkdf2":
            return False
        salt = base64.b64decode(salt_b64)
        erwartet = base64.b64decode(hash_b64)
        h = hashlib.pbkdf2_hmac("sha256", passwort.encode("utf-8"), salt, 200_000)
        return hmac.compare_digest(h, erwartet)
    except Exception:  # noqa: BLE001
        return False


def passwort_regel(passwort: str) -> None:
    if len(passwort or "") < 8:
        raise HTTPException(400, "Das Passwort braucht mindestens 8 Zeichen.")


# ---------------------------------------------------------------- Token
def token_erzeugen(user: dict) -> str:
    nutzlast = {
        "sub": user["id"], "firma": user["firma_id"], "rolle": user["role"],
        "exp": jetzt() + timedelta(days=config.JWT_TAGE), "iat": jetzt(),
    }
    return jwt.encode(nutzlast, config.JWT_SECRET, algorithm="HS256")


def _token_lesen(authorization: Optional[str]) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Bitte anmelden.")
    roh = authorization.split(" ", 1)[1].strip()
    try:
        return jwt.decode(roh, config.JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Die Anmeldung ist abgelaufen, bitte neu anmelden.")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Ungültige Anmeldung.")


def nutzer_oeffentlich(u: dict) -> dict:
    """Nutzer ohne Geheimnisse (für die Oberfläche)."""
    verboten = {"_id", "pw_hash", "einladung_token", "einladung_bis", "pin_hash", "lohndaten"}  # Lohndaten nur über eigene Route
    aus = {k: v for k, v in u.items() if k not in verboten}
    aus["eingeladen"] = bool(u.get("einladung_token")) and not u.get("pw_hash")
    aus["rolle_name"] = ROLLEN_NAMEN.get(u.get("role"), u.get("role"))
    aus["rechte"] = rechte_von(u)
    return aus


async def aktueller_nutzer(authorization: Optional[str] = Header(None)) -> dict:
    """Angemeldeter Nutzer (aus der Datenbank, damit Sperren sofort greifen)."""
    daten = _token_lesen(authorization)
    u = await db().users.find_one({"id": daten.get("sub")}, {"_id": 0})
    if not u or not u.get("active", True):
        raise HTTPException(401, "Dieses Konto ist nicht mehr aktiv.")
    return u


def rolle_noetig(mindestens: str):
    """Abhängigkeit: Nutzer braucht mindestens diese Rolle."""
    async def pruefen(user: dict = Depends(aktueller_nutzer)) -> dict:
        if ROLLEN.get(user.get("role"), 0) < ROLLEN[mindestens]:
            raise HTTPException(403, "Dafür fehlt die Berechtigung.")
        return user
    return pruefen


def hat_rolle(user: dict, mindestens: str) -> bool:
    return ROLLEN.get(user.get("role"), 0) >= ROLLEN[mindestens]


# ---------------------------------------------------------------- Vergebbare Rechte (nur für Büro-Konten; der Inhaber hat alle, Mitarbeiter keine)
RECHTE = {
    "projekte": "Projekte anlegen und ändern",
    "personal": "Zeiten, Stempelungen, Konten, Personalakten und Fotografen aller Mitarbeiter sehen und korrigieren",
    "lohn": "Lohnvorbereitung, Lohndaten und DATEV-Export",
    "rechnungen": "Rechnungen, E-Rechnungen und Zahlungen",
    "plantafel": "Plantafel: Einsätze planen und Arbeitszeiten freigeben",
    "kalkulation": "Angebote kalkulieren, Nachkalkulation und Deckungsbeiträge sehen",
    "kostensaetze": "Interne Stundensätze, Einkaufspreise und Mitarbeiterkosten sehen",
}
RECHTE_BUERO_STANDARD = {"projekte": True, "personal": True, "lohn": True, "rechnungen": True, "plantafel": True, "kalkulation": False, "kostensaetze": False}


def rechte_von(user: dict) -> dict:
    """Wirksame Rechte eines Nutzers: Inhaber alles; Büro Standard plus vom Inhaber gesetzte Abweichungen; andere nichts."""
    rolle = user.get("role")
    if rolle == "inhaber":
        return {k: True for k in RECHTE}
    if rolle == "buero":
        eigene = user.get("rechte") or {}
        return {k: bool(eigene.get(k, RECHTE_BUERO_STANDARD[k])) for k in RECHTE}
    return {k: False for k in RECHTE}


def hat_recht(user: dict, recht: str) -> bool:
    return bool(rechte_von(user).get(recht))


def recht_fehlt(recht: str) -> str:
    return f"Dafür fehlt das Recht „{RECHTE.get(recht, recht)}“ – der Inhaber vergibt es unter Mitarbeiter → Rechte."


def recht_noetig(recht: str):
    """Abhängigkeit: Nutzer braucht dieses Recht (Inhaber immer, Büro je Vergabe)."""
    async def pruefen(user: dict = Depends(aktueller_nutzer)) -> dict:
        if not hat_recht(user, recht):
            raise HTTPException(403, recht_fehlt(recht))
        return user
    return pruefen


def schreibend_mit_recht(recht: str):
    async def pruefen(user: dict = Depends(schreibender_nutzer)) -> dict:
        if not hat_recht(user, recht):
            raise HTTPException(403, recht_fehlt(recht))
        return user
    return pruefen


# ---------------------------------------------------------------- Vergebbare Rechte (nur für Büro-Konten; der Inhaber hat alle, Mitarbeiter keine)
RECHTE = {
    "projekte": "Projekte anlegen und ändern",
    "personal": "Zeiten, Stempelungen, Konten, Personalakten und Fotografen aller Mitarbeiter sehen und korrigieren",
    "lohn": "Lohnvorbereitung, Lohndaten und DATEV-Export",
    "rechnungen": "Rechnungen, E-Rechnungen und Zahlungen",
    "plantafel": "Plantafel: Einsätze planen und Arbeitszeiten freigeben",
    "kalkulation": "Angebote kalkulieren, Nachkalkulation und Deckungsbeiträge sehen",
    "kostensaetze": "Interne Stundensätze, Einkaufspreise und Mitarbeiterkosten sehen",
}
RECHTE_BUERO_STANDARD = {"projekte": True, "personal": True, "lohn": True, "rechnungen": True, "plantafel": True, "kalkulation": False, "kostensaetze": False}


def rechte_von(user: dict) -> dict:
    """Wirksame Rechte eines Nutzers: Inhaber alles; Büro Standard plus vom Inhaber gesetzte Abweichungen; andere nichts."""
    rolle = user.get("role")
    if rolle == "inhaber":
        return {k: True for k in RECHTE}
    if rolle == "buero":
        eigene = user.get("rechte") or {}
        return {k: bool(eigene.get(k, RECHTE_BUERO_STANDARD[k])) for k in RECHTE}
    return {k: False for k in RECHTE}


def hat_recht(user: dict, recht: str) -> bool:
    return bool(rechte_von(user).get(recht))


def recht_fehlt(recht: str) -> str:
    return f"Dafür fehlt das Recht „{RECHTE.get(recht, recht)}“ – der Inhaber vergibt es unter Mitarbeiter → Rechte."


def recht_noetig(recht: str):
    """Abhängigkeit: Nutzer braucht dieses Recht (Inhaber immer, Büro je Vergabe)."""
    async def pruefen(user: dict = Depends(aktueller_nutzer)) -> dict:
        if not hat_recht(user, recht):
            raise HTTPException(403, recht_fehlt(recht))
        return user
    return pruefen


def schreibend_mit_recht(recht: str):
    async def pruefen(user: dict = Depends(schreibender_nutzer)) -> dict:
        if not hat_recht(user, recht):
            raise HTTPException(403, recht_fehlt(recht))
        return user
    return pruefen


# ---------------------------------------------------------------- Vergebbare Rechte (nur für Büro-Konten; der Inhaber hat alle, Mitarbeiter keine)
RECHTE = {
    "projekte": "Projekte anlegen und ändern",
    "personal": "Zeiten, Stempelungen, Konten, Personalakten und Fotografen aller Mitarbeiter sehen und korrigieren",
    "lohn": "Lohnvorbereitung, Lohndaten und DATEV-Export",
    "rechnungen": "Rechnungen, E-Rechnungen und Zahlungen",
    "plantafel": "Plantafel: Einsätze planen und Arbeitszeiten freigeben",
    "kalkulation": "Angebote kalkulieren, Nachkalkulation und Deckungsbeiträge sehen",
    "kostensaetze": "Interne Stundensätze, Einkaufspreise und Mitarbeiterkosten sehen",
}
RECHTE_BUERO_STANDARD = {"projekte": True, "personal": True, "lohn": True, "rechnungen": True, "plantafel": True, "kalkulation": False, "kostensaetze": False}


def rechte_von(user: dict) -> dict:
    """Wirksame Rechte eines Nutzers: Inhaber alles; Büro Standard plus vom Inhaber gesetzte Abweichungen; andere nichts."""
    rolle = user.get("role")
    if rolle == "inhaber":
        return {k: True for k in RECHTE}
    if rolle == "buero":
        eigene = user.get("rechte") or {}
        return {k: bool(eigene.get(k, RECHTE_BUERO_STANDARD[k])) for k in RECHTE}
    return {k: False for k in RECHTE}


def hat_recht(user: dict, recht: str) -> bool:
    return bool(rechte_von(user).get(recht))


def recht_fehlt(recht: str) -> str:
    return f"Dafür fehlt das Recht „{RECHTE.get(recht, recht)}“ – der Inhaber vergibt es unter Mitarbeiter → Rechte."


def recht_noetig(recht: str):
    """Abhängigkeit: Nutzer braucht dieses Recht (Inhaber immer, Büro je Vergabe)."""
    async def pruefen(user: dict = Depends(aktueller_nutzer)) -> dict:
        if not hat_recht(user, recht):
            raise HTTPException(403, recht_fehlt(recht))
        return user
    return pruefen


def schreibend_mit_recht(recht: str):
    async def pruefen(user: dict = Depends(schreibender_nutzer)) -> dict:
        if not hat_recht(user, recht):
            raise HTTPException(403, recht_fehlt(recht))
        return user
    return pruefen


# ---------------------------------------------------------------- Lizenz
def plan_status(firma: dict) -> dict:
    """Stand der Lizenz: test (mit Resttagen), aktiv, abgelaufen, gesperrt."""
    plan = firma.get("plan") or {}
    status = plan.get("status") or "test"
    stufe = plan.get("stufe") or "firma"
    if stufe in ("pro", "plus"):   # frühere Stufenbezeichnungen
        stufe = "firma"
    heute = jetzt()
    aus = {"status": status, "stufe": stufe, "test_bis": plan.get("test_bis"), "nutzer_max": plan.get("nutzer_max") or 0,
           "gueltig_bis": plan.get("gueltig_bis"), "tage_rest": None, "schreiben": True, "hinweis": ""}
    if status == "gesperrt":
        aus.update(schreiben=False, hinweis="Dieses Konto ist gesperrt. Bitte den Anbieter kontaktieren.")
    elif status == "test":
        bis = plan.get("test_bis")
        try:
            bis_dt = datetime.fromisoformat(bis) if bis else heute
        except ValueError:
            bis_dt = heute
        rest = (bis_dt - heute).days
        aus["tage_rest"] = max(0, rest)
        if bis_dt < heute:
            aus.update(status="abgelaufen", schreiben=False,
                       hinweis="Die Testphase ist abgelaufen. Lesen geht weiter, zum Eintragen bitte freischalten lassen.")
        else:
            aus["hinweis"] = f"Testphase: noch {max(0, rest)} Tage."
    elif status == "aktiv":
        bis = plan.get("gueltig_bis")
        if bis:
            try:
                if datetime.fromisoformat(bis) < heute:
                    aus.update(status="abgelaufen", schreiben=False,
                               hinweis="Die Lizenz ist abgelaufen. Lesen geht weiter, zum Eintragen bitte verlängern.")
            except ValueError:
                pass
    if aus["status"] == "abgelaufen" and config.TEILNAHME_KOSTENLOS:
        # Kein Vollstopp: die Firma bleibt mit der kostenlosen Projektteilnahme arbeitsfähig; Firmenfunktionen brauchen das Firmenabo
        aus.update(status="teilnahme", stufe="teilnahme", schreiben=True,
                   hinweis="Testphase vorbei – ihr nutzt die kostenlose Projektteilnahme (Ausschreibungen, Angebote, Mitarbeit in Projekten der Auftraggeber). "
                           "Für Mitarbeiter, eigene Projekte, Stundenzettel und Rechnungen bitte das Firmenabo freischalten lassen.")
    elif aus["status"] in ("aktiv", "test") and stufe == "teilnahme":
        aus["hinweis"] = "Kostenlose Projektteilnahme. Für Mitarbeiter, eigene Projekte, Stundenzettel und Rechnungen bitte das Firmenabo freischalten lassen."
    return aus


FIRMENABO_HINWEIS = ("Dafür ist das Firmenabo nötig ({firma:.2f} € je Firma und Monat, {nutzer:.2f} € je weiterem Nutzer). Die kostenlose Projektteilnahme umfasst "
                     "Ausschreibungen, Angebote, Rückfragen und die Mitarbeit in Projekten der Auftraggeber.")


def firmenabo_pruefen(firma: dict) -> None:
    from preise import PREISE
    if plan_status(firma).get("stufe") == "teilnahme":
        raise HTTPException(402, FIRMENABO_HINWEIS.format(firma=PREISE["firma"], nutzer=PREISE["nutzer"]))


def firmenabo_noetig(mindestens: str, recht: Optional[str] = None):
    """Abhängigkeit: schreibender Nutzer mit Mindestrolle (und Recht) UND Firmenabo (Mitarbeiter, eigene Projekte, Rechnungen, Lohn, Schnittstellen)."""
    async def pruefen(user: dict = Depends(schreibend(mindestens))) -> dict:
        if recht and not hat_recht(user, recht):
            raise HTTPException(403, recht_fehlt(recht))
        firmenabo_pruefen(user["_firma"])
        return user
    return pruefen


def firmenabo_lesend(mindestens: str, recht: Optional[str] = None):
    """Abhängigkeit für lesende Firmenfunktionen (z. B. Lohnvorbereitung), die das Firmenabo (und ein Recht) brauchen."""
    async def pruefen(user: dict = Depends(rolle_noetig(mindestens))) -> dict:
        if recht and not hat_recht(user, recht):
            raise HTTPException(403, recht_fehlt(recht))
        firma = await firma_laden(user["firma_id"])
        firmenabo_pruefen(firma)
        user["_firma"] = firma
        return user
    return pruefen


async def firma_laden(firma_id: str) -> dict:
    f = await db().firmen.find_one({"id": firma_id}, {"_id": 0})
    if not f:
        raise HTTPException(404, "Firma nicht gefunden.")
    return f


async def schreibender_nutzer(user: dict = Depends(aktueller_nutzer)) -> dict:
    """Nutzer darf Daten ändern: Konto aktiv UND Lizenz der Firma erlaubt Schreiben."""
    firma = await firma_laden(user["firma_id"])
    st = plan_status(firma)
    if not st["schreiben"]:
        raise HTTPException(402, st["hinweis"])
    user["_firma"] = firma
    return user


def schreibend(mindestens: str):
    """Abhängigkeit: schreibender Nutzer mit Mindestrolle."""
    async def pruefen(user: dict = Depends(schreibender_nutzer)) -> dict:
        if ROLLEN.get(user.get("role"), 0) < ROLLEN[mindestens]:
            raise HTTPException(403, "Dafür fehlt die Berechtigung.")
        return user
    return pruefen


# ---------------------------------------------------------------- API-Schlüssel (externe Schnittstelle)
def api_token_neu() -> tuple[str, str]:
    roh = "sz_" + secrets.token_urlsafe(30)
    return roh, hashlib.sha256(roh.encode()).hexdigest()


API_RECHTE = ("projekte", "kunden", "mitarbeiter", "zeiten", "abwesenheiten", "rechnungen")


async def api_schluessel(authorization: Optional[str] = Header(None)) -> dict:
    """API-Schlüssel prüfen (Authorization: Bearer sz_…): vorhanden, nicht abgelaufen, Firma nicht gesperrt."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "API-Schlüssel fehlt.")
    roh = authorization.split(" ", 1)[1].strip()
    t = await db().api_tokens.find_one({"token_hash": hashlib.sha256(roh.encode()).hexdigest()}, {"_id": 0})
    if not t:
        raise HTTPException(401, "API-Schlüssel ungültig.")
    if t.get("gueltig_bis") and t["gueltig_bis"] < jetzt_iso():
        raise HTTPException(401, "API-Schlüssel ist abgelaufen – bitte in der Firma einen neuen erzeugen.")
    firma = await db().firmen.find_one({"id": t["firma_id"]}, {"_id": 0, "plan": 1})
    if not firma or plan_status(firma)["status"] == "gesperrt":
        raise HTTPException(403, "Das Konto der Firma ist gesperrt.")
    await db().api_tokens.update_one({"id": t["id"]}, {"$set": {"last_used_at": jetzt_iso()}})
    return t


def api_recht(recht: str):
    """Abhängigkeit: Firma eines API-Schlüssels, der das Recht trägt (Schlüssel ohne Rechteliste aus früheren Versionen: voller Lesezugriff)."""
    async def pruefen(t: dict = Depends(api_schluessel)) -> str:
        rechte = t.get("rechte") or ["*"]
        if "*" not in rechte and recht not in rechte:
            raise HTTPException(403, f"Der API-Schlüssel hat kein Recht „{recht}“.")
        return t["firma_id"]
    return pruefen


async def api_firma(t: dict = Depends(api_schluessel)) -> str:
    """Firma zu einem API-Schlüssel (ohne Rechteprüfung – nur für Routen, die kein eigenes Recht brauchen)."""
    return t["firma_id"]


def betreiber_pruefen(x_admin_token: Optional[str] = Header(None)) -> None:
    if not config.ADMIN_TOKEN or not x_admin_token or not hmac.compare_digest(x_admin_token, config.ADMIN_TOKEN):
        raise HTTPException(403, "Betreiber-Schlüssel fehlt oder stimmt nicht.")
