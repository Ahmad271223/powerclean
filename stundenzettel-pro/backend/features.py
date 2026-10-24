"""Feature-Flags (Stufe G): unfertige oder optionale Module lassen sich je Installation ein- und ausschalten.

Standardwerte unten; Umgebung überschreibt mit FEATURE_<NAME>=1|0 (z. B. FEATURE_KI=1). `GET /api/features` liefert den Stand an die
Oberfläche, `feature_noetig("chat")` schützt Routen (404 mit Klartext, damit abgeschaltete Module nicht erraten werden können)."""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException

import config

STANDARD = {
    "chat": True,                 # Projektchat, Bieterchat, Kontaktanfragen
    "berichtsvorlagen": True,     # Vorlagen und Regieberichte
    "projektakte_async": config.DB_MODE != "memory",   # Projektakte im Hintergrund erzeugen (Tests: synchron)
    "ki": False,                  # KI-Entwürfe (Stufe H) – aus, bis ein Schlüssel hinterlegt und die Freigabe geregelt ist
    "lager": False,               # Lagerverwaltung (nicht gebaut)
}
BESCHREIBUNG = {
    "chat": "Nachrichten in Projekten, mit Bietern und zwischen Firmen",
    "berichtsvorlagen": "Berichtsvorlagen und Regieberichte",
    "projektakte_async": "Projektakten im Hintergrund erzeugen (mit Fortschritt)",
    "ki": "KI-Entwürfe für Angebote und Belege (nur mit Freigabe durch Menschen)",
    "lager": "Lagerbestände, Ein-/Ausgang, Inventur",
}


def alle() -> dict[str, bool]:
    aus = {}
    for name, standard in STANDARD.items():
        wert = os.environ.get(f"FEATURE_{name.upper()}")
        aus[name] = standard if wert is None else wert.strip() in ("1", "true", "ja", "on")
    return aus


def aktiv(name: str) -> bool:
    return alle().get(name, False)


def feature_noetig(name: str):
    async def pruefen() -> None:
        if not aktiv(name):
            raise HTTPException(404, f"Die Funktion „{BESCHREIBUNG.get(name, name)}“ ist in dieser Installation nicht freigeschaltet.")
    return Depends(pruefen)


router = APIRouter(tags=["Features"])


@router.get("/api/features")
async def features_lesen():
    """Öffentlich (keine Geheimnisse): welche Module die Oberfläche anzeigen soll."""
    return {"features": alle(), "beschreibung": BESCHREIBUNG}
