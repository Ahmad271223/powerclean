"""Push-Nachrichten aufs Handy: iPhone über Apple (APNs), Android über Google (Firebase Cloud Messaging, HTTP v1). Beides kostenlos.

Ablauf wie beim E-Mail-Ausgang: Jede Nachricht wird zuerst je Gerät in `push_ausgang` gespeichert (Nachweis: was, an wen, wann, Status)
und dann zugestellt – bei Fehlern mit Wiederholungen nach 1, 5, 15 und 60 Minuten (Hintergrunddienst, auch nach Neustart).
Meldet Apple/Google ein Gerät als abgemeldet, wird es deaktiviert.

Betriebsart (`PUSH_MODUS`):
- leer/„auto“: zustellen, wenn Zugangsdaten vorhanden sind (APNS_* bzw. FCM_*); sonst Status `nicht_konfiguriert` (nur Nachweis).
- „test“: Testersatz – jede Nachricht gilt als zugestellt, nichts verlässt den Server (lokale Entwicklung, Tests ohne Netz).
- „aus“: keine Push-Nachrichten, nur Nachweis.

Zugangsdaten (nur auf dem Server, nie in der App):
- iPhone: APNS_TEAM_ID, APNS_KEY_ID, APNS_SCHLUESSEL (Inhalt der .p8-Datei) oder APNS_SCHLUESSEL_DATEI, APNS_BUNDLE_ID (Standard IOS_BUNDLE_ID),
  APNS_UMGEBUNG = auto | produktion | entwicklung (auto: erst Produktion, bei „BadDeviceToken“ Entwicklung – Xcode-Builds nutzen Entwicklung,
  TestFlight und App Store Produktion).
- Android: FCM_DIENSTKONTO (Inhalt der Dienstkonto-JSON aus Firebase) oder FCM_DIENSTKONTO_DATEI; die Projekt-ID steht in der Datei.

Datenschutz: Der Text läuft über Apple bzw. Google. Er enthält nur Projekt, Straße, Tage und Uhrzeit, nie Kundendaten oder Preise.
Mit PUSH_OHNE_DETAILS=1 steht nur „Neue Einteilung – in der App ansehen“ darin.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import config
from auth import jetzt_iso
from db import db
from gemeinsam import neue_id

WIEDERHOLUNG_MINUTEN = (1, 5, 15, 60)
MAX_VERSUCHE = len(WIEDERHOLUNG_MINUTEN) + 1
PLATTFORMEN = ("ios", "android")
STATUS_NAMEN = {"offen": "Wartet auf Zustellung", "zugestellt": "Zugestellt", "fehlgeschlagen": "Zustellung fehlgeschlagen",
                "nicht_konfiguriert": "Push nicht eingerichtet", "aus": "Push abgeschaltet"}
SOFORT_ZUSTELLEN = True   # Tests schalten das ab und arbeiten den Ausgang gezielt ab
TEST_GESENDET: list[dict] = []   # Testersatz: was „zugestellt“ worden wäre


class GeraetAbgemeldet(Exception):
    """Apple/Google kennen das Gerät nicht mehr (App gelöscht, Token abgelaufen) – Gerät deaktivieren, nicht wiederholen."""


# ---------------------------------------------------------------- Einrichtung

def modus() -> str:
    return (os.environ.get("PUSH_MODUS") or "auto").strip().lower()


def _apns_schluessel() -> str:
    roh = os.environ.get("APNS_SCHLUESSEL", "")
    datei = os.environ.get("APNS_SCHLUESSEL_DATEI", "")
    if not roh and datei:
        try:
            roh = open(datei, encoding="utf-8").read()
        except OSError:
            roh = ""
    return roh.replace("\\n", "\n").strip()


def _fcm_konto() -> Optional[dict]:
    roh = os.environ.get("FCM_DIENSTKONTO", "")
    datei = os.environ.get("FCM_DIENSTKONTO_DATEI", "")
    try:
        if not roh and datei:
            roh = open(datei, encoding="utf-8").read()
        konto = json.loads(roh) if roh else None
    except (OSError, ValueError):
        return None
    if not konto or not all(konto.get(k) for k in ("project_id", "client_email", "private_key")):
        return None
    return konto


def eingerichtet(plattform: str) -> bool:
    m = modus()
    if m == "test":
        return True
    if m == "aus":
        return False
    if plattform == "ios":
        return bool(os.environ.get("APNS_TEAM_ID") and os.environ.get("APNS_KEY_ID") and _apns_schluessel())
    if plattform == "android":
        return _fcm_konto() is not None
    return False


def stand() -> dict:
    """Für die Oberfläche (ohne Geheimnisse)."""
    return {"modus": modus(), "ios": eingerichtet("ios"), "android": eingerichtet("android")}


# ---------------------------------------------------------------- Zustellung Apple (APNs, HTTP/2, Token-Anmeldung mit ES256)

_apns_jwt: dict = {}


def apns_jwt() -> str:
    """Anmelde-Token für APNs; Apple erlaubt eine Erneuerung höchstens alle 20 Minuten, gültig bis 60 Minuten – wir erneuern nach 45."""
    import jwt
    if _apns_jwt.get("token") and time.time() - _apns_jwt["iat"] < 45 * 60:
        return _apns_jwt["token"]
    iat = int(time.time())
    token = jwt.encode({"iss": os.environ.get("APNS_TEAM_ID", ""), "iat": iat}, _apns_schluessel(), algorithm="ES256",
                       headers={"kid": os.environ.get("APNS_KEY_ID", "")})
    _apns_jwt.update(token=token, iat=iat)
    return token


def apns_anfrage(token: str, titel: str, text: str, link: str, sandbox: bool) -> tuple[str, dict, bytes]:
    host = "https://api.sandbox.push.apple.com" if sandbox else "https://api.push.apple.com"
    kopf = {"authorization": f"bearer {apns_jwt()}", "apns-topic": os.environ.get("APNS_BUNDLE_ID") or config.IOS_BUNDLE_ID,
            "apns-push-type": "alert", "apns-priority": "10", "apns-expiration": str(int(time.time()) + 7 * 24 * 3600)}
    koerper = {"aps": {"alert": {"title": titel, "body": text}, "sound": "default"}, "link": link}
    return f"{host}/3/device/{token}", kopf, json.dumps(koerper, ensure_ascii=False).encode()


async def apns_senden(token: str, titel: str, text: str, link: str, transport=None) -> None:
    import httpx
    umgebung = (os.environ.get("APNS_UMGEBUNG") or "auto").lower()
    versuche = [True] if umgebung == "entwicklung" else ([False] if umgebung == "produktion" else [False, True])
    async with httpx.AsyncClient(http2=transport is None, transport=transport, timeout=15) as c:
        for i, sandbox in enumerate(versuche):
            url, kopf, koerper = apns_anfrage(token, titel, text, link, sandbox)
            r = await c.post(url, headers=kopf, content=koerper)
            if r.status_code == 200:
                return
            grund = ""
            try:
                grund = r.json().get("reason", "")
            except ValueError:
                pass
            if grund == "BadDeviceToken" and i + 1 < len(versuche):
                continue   # Xcode-Build: Token gehört zur Entwicklungsumgebung
            if r.status_code == 410 or grund in ("Unregistered", "BadDeviceToken", "DeviceTokenNotForTopic"):
                raise GeraetAbgemeldet(grund or str(r.status_code))
            raise RuntimeError(f"APNs {r.status_code} {grund}".strip())


# ---------------------------------------------------------------- Zustellung Google (FCM HTTP v1, OAuth mit Dienstkonto RS256)

_fcm_zugang: dict = {}


async def fcm_zugang(c, konto: dict) -> str:
    import jwt
    if _fcm_zugang.get("token") and _fcm_zugang.get("bis", 0) > time.time() + 60:
        return _fcm_zugang["token"]
    jetzt = int(time.time())
    ziel = konto.get("token_uri") or "https://oauth2.googleapis.com/token"
    nachweis = jwt.encode({"iss": konto["client_email"], "scope": "https://www.googleapis.com/auth/firebase.messaging", "aud": ziel,
                           "iat": jetzt, "exp": jetzt + 3600}, konto["private_key"], algorithm="RS256")
    r = await c.post(ziel, data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": nachweis})
    if r.status_code != 200:
        raise RuntimeError(f"FCM-Anmeldung {r.status_code}")
    daten = r.json()
    _fcm_zugang.update(token=daten["access_token"], bis=jetzt + int(daten.get("expires_in", 3600)))
    return _fcm_zugang["token"]


async def fcm_senden(token: str, titel: str, text: str, link: str, transport=None) -> None:
    import httpx
    konto = _fcm_konto()
    if not konto:
        raise RuntimeError("FCM-Dienstkonto fehlt")
    async with httpx.AsyncClient(transport=transport, timeout=15) as c:
        zugang = await fcm_zugang(c, konto)
        nachricht = {"message": {"token": token, "notification": {"title": titel, "body": text}, "data": {"link": link},
                                 "android": {"priority": "high", "ttl": f"{7 * 24 * 3600}s", "notification": {"sound": "default"}}}}
        r = await c.post(f"https://fcm.googleapis.com/v1/projects/{konto['project_id']}/messages:send",
                         headers={"Authorization": f"Bearer {zugang}"}, json=nachricht)
        if r.status_code == 200:
            return
        status = ""
        try:
            status = r.json().get("error", {}).get("status", "")
        except ValueError:
            pass
        if r.status_code == 404 or status in ("NOT_FOUND", "UNREGISTERED"):
            raise GeraetAbgemeldet(status or "404")
        raise RuntimeError(f"FCM {r.status_code} {status}".strip())


async def _versand(geraet: dict, titel: str, text: str, link: str) -> None:
    if modus() == "test":
        TEST_GESENDET.append({"plattform": geraet["plattform"], "token": geraet["token"], "titel": titel, "text": text, "link": link})
        return
    if geraet["plattform"] == "ios":
        await apns_senden(geraet["token"], titel, text, link)
    else:
        await fcm_senden(geraet["token"], titel, text, link)


VERSAND = _versand   # in Tests austauschbar


# ---------------------------------------------------------------- Geräte

async def geraet_registrieren(user: dict, plattform: str, token: str, app_version: str = "") -> dict:
    """Ein Token gehört immer genau einem Nutzer: meldet sich jemand anderes auf dem Gerät an, wandert es mit."""
    jetzt = jetzt_iso()
    vorhanden = await db().geraete.find_one({"token": token}, {"_id": 0})
    felder = {"firma_id": user["firma_id"], "user_id": user["id"], "plattform": plattform, "aktiv": True, "app_version": app_version[:40], "updated_at": jetzt}
    if vorhanden:
        await db().geraete.update_one({"id": vorhanden["id"]}, {"$set": felder})
        return {**vorhanden, **felder}
    g = {"id": neue_id(), "token": token, "created_at": jetzt, **felder}
    await db().geraete.insert_one(dict(g))
    return g


async def geraet_abmelden(user: dict, token: str) -> bool:
    r = await db().geraete.update_one({"token": token, "user_id": user["id"]}, {"$set": {"aktiv": False, "updated_at": jetzt_iso()}})
    return r.modified_count > 0


# ---------------------------------------------------------------- Ausgang

def _jetzt() -> datetime:
    return datetime.now(timezone.utc)


async def senden(firma_id: str, user_id: str, titel: str, text: str, link: str, art: str, einsaetze: Optional[list[dict]] = None) -> list[dict]:
    """Nachricht an alle aktiven Geräte eines Nutzers in den Ausgang stellen. Ohne Gerät entsteht ein Nachweis mit Status kein_geraet."""
    m = modus()
    bezug = [{"id": e["id"], "version": e.get("version", 1)} for e in einsaetze or []]
    gemeinsam = {"firma_id": firma_id, "user_id": user_id, "titel": titel[:120], "text": text[:300], "link": link[:300], "art": art,
                 "einsaetze": bezug, "einsatz_ids": [b["id"] for b in bezug], "versuche": 0, "fehler": "",
                 "naechster_versuch_at": _jetzt().isoformat(), "zugestellt_at": None, "created_at": jetzt_iso()}
    geraete = [g async for g in db().geraete.find({"user_id": user_id, "aktiv": True}, {"_id": 0})]
    if not geraete:
        e = {"id": neue_id(), "geraet_id": None, "plattform": None, "status": "kein_geraet", **gemeinsam}
        await db().push_ausgang.insert_one(dict(e))
        return [e]
    aus = []
    for g in geraete:
        status = "aus" if m == "aus" else ("offen" if eingerichtet(g["plattform"]) else "nicht_konfiguriert")
        e = {"id": neue_id(), "geraet_id": g["id"], "plattform": g["plattform"], "status": status, **gemeinsam}
        await db().push_ausgang.insert_one(dict(e))
        aus.append(e)
        if status == "offen" and SOFORT_ZUSTELLEN:
            try:
                asyncio.get_running_loop().create_task(zustellen(e))
            except RuntimeError:
                pass
    return aus


async def zustellen(e: dict) -> bool:
    g = await db().geraete.find_one({"id": e["geraet_id"]}, {"_id": 0})
    if not g or not g.get("aktiv"):
        await db().push_ausgang.update_one({"id": e["id"]}, {"$set": {"status": "fehlgeschlagen", "fehler": "Gerät abgemeldet"}})
        return False
    versuche = int(e.get("versuche") or 0) + 1
    try:
        await VERSAND(g, e["titel"], e["text"], e["link"])
    except GeraetAbgemeldet as exc:
        await db().geraete.update_one({"id": g["id"]}, {"$set": {"aktiv": False, "updated_at": jetzt_iso(), "abgemeldet_grund": str(exc)[:80]}})
        await db().push_ausgang.update_one({"id": e["id"]}, {"$set": {"status": "fehlgeschlagen", "versuche": versuche, "fehler": f"Gerät abgemeldet ({exc})"[:300]}})
        return False
    except Exception as exc:  # noqa: BLE001 – jeder Fehler wird gespeichert, nie geworfen
        if versuche >= MAX_VERSUCHE:
            aenderung = {"status": "fehlgeschlagen", "versuche": versuche, "fehler": str(exc)[:300]}
        else:
            naechster = _jetzt() + timedelta(minutes=WIEDERHOLUNG_MINUTEN[versuche - 1])
            aenderung = {"status": "offen", "versuche": versuche, "fehler": str(exc)[:300], "naechster_versuch_at": naechster.isoformat()}
        await db().push_ausgang.update_one({"id": e["id"]}, {"$set": aenderung})
        return False
    await db().push_ausgang.update_one({"id": e["id"]}, {"$set": {"status": "zugestellt", "zugestellt_at": jetzt_iso(), "versuche": versuche, "fehler": ""}})
    return True


async def ausgang_abarbeiten(limit: int = 100) -> int:
    jetzt = _jetzt().isoformat()
    faellig = [e async for e in db().push_ausgang.find({"status": "offen", "naechster_versuch_at": {"$lte": jetzt}}, {"_id": 0}).sort("naechster_versuch_at", 1).limit(limit)]
    n = 0
    for e in faellig:
        if await zustellen(e):
            n += 1
    return n


async def hintergrunddienst(intervall: int = 20) -> None:
    while True:
        try:
            await ausgang_abarbeiten()
        except Exception:  # noqa: BLE001 – der Dienst darf nie sterben
            pass
        await asyncio.sleep(intervall)


# ---------------------------------------------------------------- Texte für Einteilungen

WOCHENTAGE = ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So")


def uhrzeit(hhmm: str) -> str:
    """„07:00“ → „7“, „06:30“ → „6:30“."""
    h, m = hhmm.split(":")
    return f"{int(h)}" if m == "00" else f"{int(h)}:{m}"


def tage_text(tage: list[str]) -> str:
    """Kompakte Tagesangabe: „Mi 02.12.“, „Mo–Fr 30.11.–04.12.“, „Mo 30.11., Mi 02.12.“ (höchstens drei, dann „+ n“)."""
    d = sorted({date.fromisoformat(t) for t in tage})
    if not d:
        return ""
    kurz = lambda x: f"{WOCHENTAGE[x.weekday()]} {x.strftime('%d.%m.')}"  # noqa: E731
    if len(d) == 1:
        return kurz(d[0])
    lueckenlos = all((b - a).days == 1 or (a.weekday() == 4 and b.weekday() == 0 and (b - a).days == 3) for a, b in zip(d, d[1:]))
    if lueckenlos:
        return f"{WOCHENTAGE[d[0].weekday()]}–{WOCHENTAGE[d[-1].weekday()]} {d[0].strftime('%d.%m.')}–{d[-1].strftime('%d.%m.')}"
    teile = [kurz(x) for x in d[:3]]
    return ", ".join(teile) + (f" + {len(d) - 3}" if len(d) > 3 else "")


def _ort(adresse: str) -> str:
    """Nur die Straße („Hauptstraße 5, 30159 Hannover“ → „Hauptstraße 5“)."""
    return (adresse or "").split(",")[0].strip()[:60]


ARTEN = {"neu": ("📅 Neue Einteilung", "Neue Einteilung"), "geaendert": ("✏️ Einteilung geändert", "Einteilung geändert"),
         "abgesagt": ("❌ Einteilung abgesagt", "Einteilung abgesagt")}


def einteilungs_text(art: str, projekt: str, adresse: str, einsaetze: list[dict]) -> tuple[str, str]:
    titel, kurz = ARTEN.get(art, ARTEN["neu"])
    if os.environ.get("PUSH_OHNE_DETAILS") == "1":
        return kurz, "In der App ansehen."
    zeiten = {(e["start_time"], e["end_time"]) for e in einsaetze}
    zeit = f" {uhrzeit(next(iter(zeiten))[0])}–{uhrzeit(next(iter(zeiten))[1])} Uhr" if len(zeiten) == 1 and art != "abgesagt" else ""
    teile = [projekt, _ort(adresse), tage_text([e["date"] for e in einsaetze]) + zeit]
    return titel, ", ".join(t for t in teile if t)


async def einsaetze_melden(einsaetze: list[dict], art: str, heute: Optional[str] = None) -> int:
    """Eine Push-Nachricht je Person und Projekt für einen Vorgang (Serie = eine Nachricht). Vergangene Tage und Planer-Kopien ohne Bezug
    zu heute werden nicht gemeldet. Gibt die Anzahl der Nachrichten zurück."""
    from zeiten import lokal_jetzt
    heute = heute or lokal_jetzt().date().isoformat()
    gruppen: dict = {}
    for e in einsaetze:
        if e["date"] < heute:
            continue
        gruppen.setdefault((e["firma_id"], e["user_id"], e["project_id"]), []).append(e)
    n = 0
    for (firma_id, user_id, project_id), liste in gruppen.items():
        liste.sort(key=lambda e: (e["date"], e["start_time"]))
        p = await db().projects.find_one({"id": project_id}, {"_id": 0, "name": 1, "address": 1}) or {}
        titel, text = einteilungs_text(art, p.get("name") or "Projekt", liste[0].get("address") or p.get("address") or "", liste)
        await senden(firma_id, user_id, titel, text, f"/einsaetze?einsatz={liste[0]['id']}", f"einsatz_{art}", liste)
        n += 1
    return n


async def zustellstand(einsaetze: list[dict]) -> dict:
    """Zustellstand je Einsatz für die aktuelle Version: zugestellt | offen | fehlgeschlagen | kein_geraet | nicht_konfiguriert | None."""
    if not einsaetze:
        return {}
    version = {e["id"]: e.get("version", 1) for e in einsaetze}
    rang = {"zugestellt": 5, "offen": 4, "fehlgeschlagen": 3, "nicht_konfiguriert": 2, "aus": 1, "kein_geraet": 1}
    aus: dict = {}
    async for p in db().push_ausgang.find({"einsatz_ids": {"$in": list(version)}}, {"_id": 0, "einsaetze": 1, "status": 1}):
        for b in p.get("einsaetze") or []:
            if b["id"] in version and b.get("version") == version[b["id"]]:
                if rang.get(p["status"], 0) > rang.get(aus.get(b["id"]), 0):
                    aus[b["id"]] = p["status"]
    return aus
