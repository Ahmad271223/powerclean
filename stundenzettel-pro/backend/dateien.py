"""Dateiablage für Personal- und Projektakten: Datei auf der Platte, Metadaten in `documents`."""
from __future__ import annotations

import re
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile

import config

ERLAUBT = {
    "application/pdf": ".pdf", "image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp",
    "image/heic": ".heic", "text/plain": ".txt", "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.ms-excel": ".xls", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
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


async def datei_speichern(firma_id: str, datei: UploadFile) -> dict:
    """Prüft Typ und Größe, schreibt die Datei und liefert die Metadaten (ohne id-Verweis auf die Akte)."""
    typ = (datei.content_type or "").split(";")[0].strip().lower()
    endung = ERLAUBT.get(typ)
    if not endung:
        raise HTTPException(400, "Dateityp nicht erlaubt (PDF, Bilder, Word, Excel, Text).")
    inhalt = await datei.read()
    if len(inhalt) > config.MAX_DATEI_MB * 1024 * 1024:
        raise HTTPException(413, f"Datei ist zu groß (max. {config.MAX_DATEI_MB} MB).")
    if not inhalt:
        raise HTTPException(400, "Die Datei ist leer.")
    dokument_id = str(uuid.uuid4())
    pfad = ablageort(firma_id, dokument_id, endung)
    pfad.write_bytes(inhalt)
    return {"id": dokument_id, "filename": _sicherer_name(datei.filename or f"datei{endung}"), "mime": typ,
            "size": len(inhalt), "path": str(pfad)}


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
