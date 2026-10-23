"""Webhooks: Ereignisse der Firma (zeit.eingetragen, rechnung.angelegt, …) an fremde Adressen schicken.
Signatur: X-Signatur = HMAC-SHA256(secret, body) als Hex.

Sicherheit (SSRF): Adressen werden beim Anlegen und vor jedem Senden geprüft – nur https (http nur per WEBHOOK_HTTP_ERLAUBEN),
nur erlaubte Ports, keine Zugangsdaten in der Adresse, keine internen Namen; alle aufgelösten IP-Adressen müssen öffentlich sein
(keine privaten, Loopback-, Link-local-, Multicast- oder Metadaten-Adressen); Weiterleitungen werden nicht verfolgt.

Zuverlässigkeit: Jedes Ereignis landet zuerst im Ausgang (`webhook_ausgang`) und wird dann zugestellt. Schlägt die Zustellung fehl,
wiederholt der Hintergrunddienst mit wachsendem Abstand (1, 5, 15, 60, 240 Minuten); nach einem Neustart werden offene Einträge
weiter zugestellt. Nach dem letzten Versuch gilt der Eintrag als fehlgeschlagen und bleibt zur Ansicht erhalten.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import ipaddress
import json
import socket
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import httpx

import config
from db import db
from gemeinsam import neue_id

EREIGNISSE = [
    "zeit.eingetragen", "zeit.geaendert", "zeit.geloescht", "zeit.serie", "stempel.start", "stempel.stop",
    "abwesenheit.angelegt", "abwesenheit.entschieden", "rechnung.angelegt", "rechnung.status",
    "mitarbeiter.eingeladen", "unterschrift.erfasst", "monat.abgeschlossen", "test",
]
GESPERRTE_NAMEN = {"localhost", "localhost.localdomain", "metadata.google.internal", "metadata", "instance-data"}
GESPERRTE_ENDUNGEN = (".local", ".localhost", ".internal", ".lan", ".home", ".corp", ".intranet", ".arpa")
WIEDERHOLUNG_MINUTEN = [1, 5, 15, 60, 240]
MAX_VERSUCHE = len(WIEDERHOLUNG_MINUTEN) + 1
AUFBEWAHRUNG_TAGE = 14


class UnsichereAdresse(ValueError):
    pass


def _jetzt() -> datetime:
    return datetime.now(timezone.utc)


def ip_erlaubt(text: str) -> bool:
    """Nur öffentliche Adressen. IPv4-mapped-IPv6 wird auf die IPv4-Adresse zurückgeführt."""
    try:
        a = ipaddress.ip_address(text)
    except ValueError:
        return False
    if a.version == 6 and a.ipv4_mapped is not None:
        return ip_erlaubt(str(a.ipv4_mapped))
    if a.version == 4 and a in ipaddress.ip_network("100.64.0.0/10"):   # Carrier-Grade NAT
        return False
    if a.version == 6 and a.is_site_local:
        return False
    return not (a.is_private or a.is_loopback or a.is_link_local or a.is_multicast or a.is_reserved or a.is_unspecified)


def url_pruefen(url: str) -> str:
    """Formale Prüfung ohne Netzwerk (beim Anlegen): Schema, Port, Zugangsdaten, interne Namen, IP-Literale."""
    u = urlparse((url or "").strip())
    if u.scheme not in ("https", "http") or not u.hostname:
        raise UnsichereAdresse("Bitte eine vollständige https-Adresse angeben.")
    if u.scheme == "http" and not config.WEBHOOK_HTTP_ERLAUBEN:
        raise UnsichereAdresse("Nur https-Adressen sind erlaubt.")
    if u.username or u.password:
        raise UnsichereAdresse("Zugangsdaten in der Adresse sind nicht erlaubt – bitte die Signatur (X-Signatur) prüfen.")
    host = u.hostname.lower().rstrip(".")
    if host in GESPERRTE_NAMEN or host.endswith(GESPERRTE_ENDUNGEN) or "." not in host and not _ist_ip(host):
        raise UnsichereAdresse("Interne Adressen sind nicht erlaubt.")
    port = u.port or (443 if u.scheme == "https" else 80)
    if port not in config.WEBHOOK_PORTS:
        raise UnsichereAdresse(f"Port {port} ist nicht erlaubt (erlaubt: {', '.join(str(p) for p in sorted(config.WEBHOOK_PORTS))}).")
    if _ist_ip(host) and not ip_erlaubt(host):
        raise UnsichereAdresse("Interne oder reservierte IP-Adressen sind nicht erlaubt.")
    return u.geturl()


def _ist_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


async def adressen_pruefen(url: str) -> None:
    """Vor jedem Senden: Hostnamen auflösen und jede Adresse prüfen (gegen DNS-Rebinding und nachträgliche Umleitung)."""
    url_pruefen(url)
    host = urlparse(url).hostname.lower().rstrip(".")
    if _ist_ip(host):
        return
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except (socket.gaierror, OSError) as exc:
        raise UnsichereAdresse("Der Hostname lässt sich nicht auflösen.") from exc
    adressen = {info[4][0] for info in infos}
    if not adressen or not all(ip_erlaubt(a) for a in adressen):
        raise UnsichereAdresse("Die Adresse zeigt auf ein internes Netz.")


async def _post(url: str, body: bytes, headers: dict) -> int:
    await adressen_pruefen(url)
    async with httpx.AsyncClient(timeout=8, follow_redirects=False) as c:
        r = await c.post(url, content=body, headers=headers)
        return r.status_code


def _nutzlast(firma_id: str, ereignis: str, daten: dict) -> bytes:
    return json.dumps({"ereignis": ereignis, "firma_id": firma_id, "zeitpunkt": _jetzt().isoformat(), "daten": daten}, ensure_ascii=False, default=str).encode("utf-8")


async def zustellen(a: dict) -> int:
    """Einen Ausgangseintrag zustellen; Ergebnis und nächsten Versuch fortschreiben. Liefert den HTTP-Status (0 = kein Kontakt, -1 = Hook weg, -2 = unsichere Adresse)."""
    h = await db().webhooks.find_one({"id": a["webhook_id"]}, {"_id": 0})
    status = -1
    if h and h.get("active"):
        nutzlast = a["nutzlast"].encode("utf-8")
        sig = hmac.new((h.get("secret") or "").encode(), nutzlast, hashlib.sha256).hexdigest()
        try:
            status = await _post(h["url"], nutzlast, {"Content-Type": "application/json", "X-Signatur": sig, "X-Ereignis": a["ereignis"], "X-Lieferung": a["id"]})
        except UnsichereAdresse:
            status = -2
        except Exception:  # noqa: BLE001 – Netzfehler, Zeitüberschreitung
            status = 0
    versuche = int(a.get("versuche") or 0) + 1
    ok = 200 <= status < 300
    jetzt = _jetzt()
    if ok or status in (-1, -2) or versuche >= MAX_VERSUCHE:
        neu = {"status": "zugestellt" if ok else "fehlgeschlagen", "erledigt_at": jetzt.isoformat(), "naechster_versuch_at": None}
    else:
        neu = {"status": "offen", "naechster_versuch_at": (jetzt + timedelta(minutes=WIEDERHOLUNG_MINUTEN[versuche - 1])).isoformat()}
    try:
        await db().webhook_ausgang.update_one({"id": a["id"]}, {"$set": {**neu, "versuche": versuche, "letzter_status": status, "letzter_versuch_at": jetzt.isoformat()}})
        if h:
            await db().webhooks.update_one({"id": h["id"]}, {"$set": {"last_status": status, "last_at": jetzt.isoformat(), "last_event": a["ereignis"]}})
    except Exception:  # noqa: BLE001
        pass
    return status


async def senden(firma_id: str, ereignis: str, daten: dict) -> list[dict]:
    """Ereignis für alle passenden Hooks in den Ausgang stellen und sofort zustellen; liefert [{id, status}] (für den Test-Knopf)."""
    aus = []
    try:
        hooks = [h async for h in db().webhooks.find({"firma_id": firma_id, "active": True}, {"_id": 0})]
    except Exception:  # noqa: BLE001
        return aus
    nutzlast = _nutzlast(firma_id, ereignis, daten).decode("utf-8")
    for h in hooks:
        events = h.get("events") or ["*"]
        if "*" not in events and ereignis not in events:
            continue
        a = {"id": neue_id(), "firma_id": firma_id, "webhook_id": h["id"], "ereignis": ereignis, "nutzlast": nutzlast, "status": "offen", "versuche": 0,
             "naechster_versuch_at": _jetzt().isoformat(), "letzter_status": None, "created_at": _jetzt().isoformat()}
        try:
            await db().webhook_ausgang.insert_one(dict(a))
        except Exception:  # noqa: BLE001
            continue
        aus.append({"id": h["id"], "status": await zustellen(a)})
    return aus


async def ausgang_abarbeiten(limit: int = 50) -> int:
    """Fällige offene Einträge erneut zustellen (Hintergrunddienst, auch nach Neustart); alte erledigte Einträge aufräumen."""
    jetzt = _jetzt().isoformat()
    n = 0
    faellig = [a async for a in db().webhook_ausgang.find({"status": "offen", "naechster_versuch_at": {"$lte": jetzt}}, {"_id": 0}).limit(limit)]
    for a in faellig:
        await zustellen(a)
        n += 1
    grenze = (_jetzt() - timedelta(days=AUFBEWAHRUNG_TAGE)).isoformat()
    await db().webhook_ausgang.delete_many({"status": {"$in": ["zugestellt", "fehlgeschlagen"]}, "erledigt_at": {"$lt": grenze}})
    return n


async def hintergrunddienst(intervall: int = 30) -> None:
    while True:
        try:
            await ausgang_abarbeiten()
        except Exception:  # noqa: BLE001 – der Dienst darf nie sterben
            pass
        await asyncio.sleep(intervall)


async def ausgang_stand(firma_id: str) -> dict:
    """Je Webhook: wie viele Lieferungen offen bzw. endgültig fehlgeschlagen sind (für die Oberfläche)."""
    aus: dict = {}
    async for a in db().webhook_ausgang.find({"firma_id": firma_id, "status": {"$in": ["offen", "fehlgeschlagen"]}}, {"_id": 0, "webhook_id": 1, "status": 1}):
        eintrag = aus.setdefault(a["webhook_id"], {"offen": 0, "fehlgeschlagen": 0})
        eintrag[a["status"]] += 1
    return aus


def ausloesen(firma_id: str | None, ereignis: str, daten: dict) -> None:
    if not firma_id or ereignis not in EREIGNISSE:
        return
    try:
        asyncio.get_running_loop().create_task(senden(firma_id, ereignis, daten))
    except RuntimeError:
        pass
