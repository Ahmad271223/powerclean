"""E-Mail-Ausgang mit Nachweis.

Jede E-Mail wird zuerst als Datensatz in `email_ausgang` gespeichert (Empfänger, Betreff, Text, Anlass, Projekt) und dann – sobald SMTP
eingerichtet ist (SMTP_HOST, SMTP_ABSENDER) – zugestellt; bei Fehlern mit Wiederholungen nach 1, 5, 15, 60 und 240 Minuten, auch nach
einem Neustart (Hintergrunddienst). Ohne SMTP bleibt der Datensatz mit Status `nicht_konfiguriert` erhalten: die Oberfläche zeigt
Einladungslinks weiterhin an, und der Nachweis, was wann an wen gegangen wäre, geht nicht verloren.

Spam vermeiden: E-Mails gibt es nur für wenige Anlässe (Einladungen, Einreichungsnachweise, Zuschlag/Absage, Nachträge, Abnahmen),
nie für jede Statusänderung. Firmen (Firma → Firmendaten) und Nutzer (Profil) können den Versand abschalten.
"""
from __future__ import annotations

import asyncio
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import formataddr
from typing import Optional

import config
from auth import jetzt_iso
from db import db
from gemeinsam import neue_id

WIEDERHOLUNG_MINUTEN = (1, 5, 15, 60, 240)
MAX_VERSUCHE = len(WIEDERHOLUNG_MINUTEN) + 1
STATUS_NAMEN = {"offen": "Wartet auf Versand", "gesendet": "Gesendet", "fehlgeschlagen": "Endgültig fehlgeschlagen",
                "nicht_konfiguriert": "Kein E-Mail-Versand eingerichtet (nur Nachweis)"}
ARTEN = {"mitarbeiter_einladung": "Einladung Mitarbeiter", "projekt_einladung": "Einladung zum Projekt", "ausschreibung_einladung": "Einladung zur Ausschreibung",
         "angebot_nachweis": "Einreichungsnachweis Angebot", "angebot_eingegangen": "Angebot eingegangen", "zuschlag": "Zuschlag", "absage": "Absage",
         "auftrag_angenommen": "Auftrag angenommen", "nachtrag": "Nachtrag", "abnahme": "Abnahme", "einsatz_erinnerung": "Einsatz morgen",
         "einsatz_aenderung": "Planänderung", "allgemein": "Allgemein"}
SOFORT_ZUSTELLEN = True   # Tests schalten die sofortige Zustellung ab und arbeiten den Ausgang gezielt ab


def eingerichtet() -> bool:
    return bool(config.SMTP_HOST and config.SMTP_ABSENDER)


def _smtp_senden(an: str, betreff: str, text: str) -> None:
    """Synchroner Versand über SMTP (läuft in einem Hilfsthread)."""
    msg = EmailMessage()
    msg["From"] = formataddr((config.SMTP_ABSENDER_NAME or "Stundenzettel Pro", config.SMTP_ABSENDER))
    msg["To"] = an
    msg["Subject"] = betreff
    msg.set_content(text)
    kontext = ssl.create_default_context()
    if config.SMTP_TLS == "ssl":
        with smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, timeout=20, context=kontext) as s:
            if config.SMTP_USER:
                s.login(config.SMTP_USER, config.SMTP_PASSWORT)
            s.send_message(msg)
        return
    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=20) as s:
        s.ehlo()
        if config.SMTP_TLS == "starttls":
            s.starttls(context=kontext)
            s.ehlo()
        if config.SMTP_USER:
            s.login(config.SMTP_USER, config.SMTP_PASSWORT)
        s.send_message(msg)


VERSAND = _smtp_senden   # in Tests austauschbar


def fusszeile() -> str:
    link = f"{config.BASE_URL}/" if config.BASE_URL else ""
    return f"\n\n–\nDiese E-Mail wurde automatisch von Stundenzettel Pro versendet. {link}".rstrip()


def _jetzt() -> datetime:
    return datetime.now(timezone.utc)


async def senden(firma_id: Optional[str], an: str, betreff: str, text: str, art: str = "allgemein", ref_id: str = "",
                 project_id: str = "", absender_firma_id: Optional[str] = None) -> Optional[dict]:
    """E-Mail in den Ausgang stellen (Nachweis) und – wenn eingerichtet – sofort zustellen."""
    an = (an or "").strip().lower()
    if not an or "@" not in an or an.endswith("@konto.geloescht"):
        return None
    e = {"id": neue_id(), "firma_id": firma_id, "an": an, "betreff": (betreff or "")[:200], "text": ((text or "") + fusszeile())[:20000],
         "absender_firma_id": absender_firma_id or firma_id, "art": art if art in ARTEN else "allgemein", "ref_id": ref_id or "", "project_id": project_id or "",
         "status": "offen" if eingerichtet() else "nicht_konfiguriert", "versuche": 0, "fehler": "",
         "naechster_versuch_at": _jetzt().isoformat(), "gesendet_at": None, "created_at": jetzt_iso()}
    await db().email_ausgang.insert_one(dict(e))
    if e["status"] == "offen" and SOFORT_ZUSTELLEN:
        try:
            asyncio.get_running_loop().create_task(zustellen(e))
        except RuntimeError:
            pass
    return e


async def zustellen(e: dict) -> bool:
    """Einen Ausgangseintrag zustellen; bei Fehlern den nächsten Versuch planen."""
    try:
        await asyncio.to_thread(VERSAND, e["an"], e["betreff"], e["text"])
    except Exception as exc:  # noqa: BLE001 – jeder Fehler wird gespeichert, nie geworfen
        versuche = int(e.get("versuche") or 0) + 1
        if versuche >= MAX_VERSUCHE:
            aenderung = {"status": "fehlgeschlagen", "versuche": versuche, "fehler": str(exc)[:300]}
        else:
            naechster = _jetzt() + timedelta(minutes=WIEDERHOLUNG_MINUTEN[min(versuche - 1, len(WIEDERHOLUNG_MINUTEN) - 1)])
            aenderung = {"status": "offen", "versuche": versuche, "fehler": str(exc)[:300], "naechster_versuch_at": naechster.isoformat()}
        await db().email_ausgang.update_one({"id": e["id"]}, {"$set": aenderung})
        return False
    await db().email_ausgang.update_one({"id": e["id"]}, {"$set": {"status": "gesendet", "gesendet_at": jetzt_iso(), "versuche": int(e.get("versuche") or 0) + 1, "fehler": ""}})
    return True


async def ausgang_abarbeiten(limit: int = 50) -> int:
    """Fällige, noch offene E-Mails zustellen (Hintergrunddienst und Tests)."""
    if not eingerichtet():
        return 0
    jetzt = _jetzt().isoformat()
    faellig = [e async for e in db().email_ausgang.find({"status": "offen", "naechster_versuch_at": {"$lte": jetzt}}, {"_id": 0}).sort("naechster_versuch_at", 1).limit(limit)]
    n = 0
    for e in faellig:
        if await zustellen(e):
            n += 1
    return n


async def hintergrunddienst(intervall: int = 30) -> None:
    while True:
        try:
            await ausgang_abarbeiten()
        except Exception:  # noqa: BLE001 – der Dienst darf nie sterben
            pass
        await asyncio.sleep(intervall)


async def adressen(firma_id: str, mindestens: str = "buero") -> list[str]:
    """E-Mail-Adressen der Nutzer einer Firma ab einer Rolle – nur wenn Firma und Nutzer den Versand nicht abgeschaltet haben."""
    from auth import ROLLEN
    f = await db().firmen.find_one({"id": firma_id}, {"_id": 0, "email_benachrichtigungen": 1})
    if f is None or f.get("email_benachrichtigungen") is False:
        return []
    stufe = ROLLEN.get(mindestens, 3)
    aus = []
    async for u in db().users.find({"firma_id": firma_id, "active": True}, {"_id": 0, "email": 1, "role": 1, "email_benachrichtigungen": 1}):
        if ROLLEN.get(u.get("role"), 0) < stufe or u.get("email_benachrichtigungen") is False:
            continue
        adresse = (u.get("email") or "").lower()
        if "@" in adresse and not adresse.endswith("@konto.geloescht"):
            aus.append(adresse)
    return sorted(set(aus))


async def firma_informieren(firma_id: str, betreff: str, text: str, art: str, ref_id: str = "", project_id: str = "",
                            mindestens: str = "buero", absender_firma_id: Optional[str] = None) -> int:
    """E-Mail an alle zuständigen Nutzer einer Firma (Standard: Büro und Inhaber). Der Nachweis erscheint bei Empfänger- und Absenderfirma."""
    n = 0
    for an in await adressen(firma_id, mindestens):
        if await senden(firma_id, an, betreff, text, art, ref_id, project_id, absender_firma_id):
            n += 1
    return n


async def nachweise(firma_id: str, project_id: Optional[str] = None, limit: int = 300) -> list[dict]:
    filt: dict = {"$or": [{"firma_id": firma_id}, {"absender_firma_id": firma_id}]}
    if project_id:
        filt["project_id"] = project_id
    aus = []
    async for e in db().email_ausgang.find(filt, {"_id": 0}).sort("created_at", -1).limit(limit):
        e["status_name"] = STATUS_NAMEN.get(e.get("status"), e.get("status"))
        e["art_name"] = ARTEN.get(e.get("art"), e.get("art"))
        aus.append(e)
    return aus


def link(pfad: str) -> str:
    """Absoluter Link in die Oberfläche (HashRouter)."""
    return f"{config.BASE_URL}/#{pfad}" if config.BASE_URL else f"/#{pfad}"
