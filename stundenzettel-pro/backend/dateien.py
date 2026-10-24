"""Dateiablage für Personal- und Projektakten: Datei auf der Platte, Metadaten in `documents`."""
from __future__ import annotations

import re
import time
import uuid
from collections import deque
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, UploadFile

import config

ERLAUBT = {
    "application/pdf": ".pdf", "image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp",
    "image/heic": ".heic", "text/plain": ".txt", "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.ms-excel": ".xls", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/xml": ".xml", "text/xml": ".xml", "text/csv": ".csv",
}

KATEGORIEN_PERSONAL = [
    "Arbeitsvertrag", "Arbeitszeugnisse", "Abmahnungen", "Allgemeiner Schriftverkehr",
    "Amtliche Urkunden & Dokumente", "Bewerbungsunterlagen", "Sozialversicherung", "Steuern & Finanzamt", "Sonstiges",
]
KATEGORIEN_PROJEKT = ["Fotos", "Skizzen & Pläne", "Auftrag & Angebot", "Protokolle", "Sonstiges"]


def _sicherer_name(name: str) -> str:
    name = re.sub(r"[^\w.\- ]+", "_", name or "datei", flags=re.UNICODE).strip() or "datei"
    return name[:120]


def ablageort(firma_id: str, dokument_id: str, endung: str) -> Path:
    ordner = config.DATA_DIR / "dateien" / re.sub(r"[^a-zA-Z0-9\-]", "", firma_id)
    ordner.mkdir(parents=True, exist_ok=True)
    return ordner / f"{dokument_id}{endung}"


_uploads: dict[str, deque] = {}


def uploadrate_pruefen(user_id: Optional[str]) -> None:
    """Einfache Uploadrate je Nutzer (gleitendes 10-Minuten-Fenster) gegen Massen-Uploads."""
    if not user_id:
        return
    jetzt = time.monotonic()
    q = _uploads.setdefault(user_id, deque())
    while q and jetzt - q[0] > 600:
        q.popleft()
    if len(q) >= config.UPLOADS_JE_10_MIN:
        raise HTTPException(429, "Zu viele Uploads in kurzer Zeit. Bitte in ein paar Minuten weitermachen.")
    q.append(jetzt)


async def speicher_belegt(firma_id: str) -> int:
    """Belegter Speicher der Firma in Bytes (Summe aller Dateien in `documents`)."""
    from db import db
    gesamt = 0
    async for d in db().documents.find({"firma_id": firma_id}, {"_id": 0, "size": 1}):
        gesamt += int(d.get("size") or 0)
    return gesamt


async def speicher_grenze(firma_id: str) -> int:
    from db import db
    f = await db().firmen.find_one({"id": firma_id}, {"_id": 0, "plan": 1})
    gb = ((f or {}).get("plan") or {}).get("speicher_gb")
    return int(float(gb if gb is not None else config.SPEICHER_GB) * 1024 * 1024 * 1024)


async def datei_speichern(firma_id: str, datei: UploadFile, user_id: Optional[str] = None) -> dict:
    """Prüft Typ, Größe, Uploadrate und Speicherkontingent, schreibt die Datei und liefert die Metadaten."""
    typ = (datei.content_type or "").split(";")[0].strip().lower()
    endung = ERLAUBT.get(typ)
    if not endung:
        raise HTTPException(400, "Dateityp nicht erlaubt (PDF, Bilder, Word, Excel, Text).")
    uploadrate_pruefen(user_id)
    inhalt = await datei.read()
    if len(inhalt) > config.MAX_DATEI_MB * 1024 * 1024:
        raise HTTPException(413, f"Datei ist zu groß (max. {config.MAX_DATEI_MB} MB).")
    if not inhalt:
        raise HTTPException(400, "Die Datei ist leer.")
    grenze = await speicher_grenze(firma_id)
    if await speicher_belegt(firma_id) + len(inhalt) > grenze:
        raise HTTPException(413, f"Der Speicherplatz der Firma ({grenze / 1024 / 1024 / 1024:g} GB) ist erschöpft. Bitte Dateien löschen oder den Tarif erweitern.")
    dokument_id = str(uuid.uuid4())
    pfad = ablageort(firma_id, dokument_id, endung)
    pfad.write_bytes(inhalt)
    return {"id": dokument_id, "filename": _sicherer_name(datei.filename or f"datei{endung}"), "mime": typ,
            "size": len(inhalt), "path": str(pfad)}


async def version_verknuepfen(doc: dict, ersetzt_id: Optional[str], firma_id: str) -> dict:
    """Neue Version einer vorhandenen Datei: Versionsnummer hochzählen, Vorgänger als nicht mehr aktuell markieren."""
    from db import db
    doc.setdefault("version", 1)
    doc.setdefault("aktuell", True)
    if not ersetzt_id:
        return doc
    alt = await db().documents.find_one({"id": ersetzt_id, "firma_id": firma_id, "scope": doc.get("scope"), "ref_id": doc.get("ref_id")}, {"_id": 0})
    if not alt:
        raise HTTPException(404, "Die zu ersetzende Datei wurde nicht gefunden.")
    doc["version"] = int(alt.get("version") or 1) + 1
    doc["vorgaenger_id"] = alt["id"]
    doc["ordner"] = doc.get("ordner") or alt.get("ordner") or ""
    doc["category"] = doc.get("category") or alt.get("category")
    if not doc.get("note"):
        doc["note"] = alt.get("note") or ""
    await db().documents.update_one({"id": ersetzt_id}, {"$set": {"aktuell": False, "ersetzt_von": doc["id"]}})
    return doc


def datei_loeschen(meta: dict) -> None:
    try:
        Path(meta.get("path", "")).unlink(missing_ok=True)
    except Exception:  # noqa: BLE001
        pass


try:  # iPhone-Fotos (HEIC) lesbar machen, wenn pillow-heif installiert ist
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:  # pragma: no cover
    pass


def bild_verkleinern(pfad: str, max_seite: int = 1400) -> bytes:
    """Foto als JPEG mit höchstens max_seite Pixeln Kantenlänge (Vorschau und PDF-Anhang), EXIF-Drehung berücksichtigt."""
    import io as _io
    from PIL import Image, ImageOps
    with Image.open(pfad) as bild:
        bild = ImageOps.exif_transpose(bild)
        bild.thumbnail((max_seite, max_seite))
        if bild.mode not in ("RGB", "L"):
            bild = bild.convert("RGB")
        puffer = _io.BytesIO()
        bild.save(puffer, "JPEG", quality=82, optimize=True)
        return puffer.getvalue()
