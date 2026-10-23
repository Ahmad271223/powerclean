"""Datenbankzugriff. Betrieb: MongoDB über Motor. Entwicklung/Tests: In-Memory-Nachbildung (mongomock_motor)."""
from __future__ import annotations

import config

_client = None
_db = None


def db():
    """Aktuelle Datenbank (wird beim ersten Aufruf verbunden)."""
    global _client, _db
    if _db is not None:
        return _db
    if config.DB_MODE == "memory":
        from mongomock_motor import AsyncMongoMockClient
        _client = AsyncMongoMockClient()
    else:
        from motor.motor_asyncio import AsyncIOMotorClient
        _client = AsyncIOMotorClient(config.MONGO_URL, uuidRepresentation="standard")
    _db = _client[config.DB_NAME]
    return _db


def zuruecksetzen() -> None:
    """Verbindung verwerfen (Tests bekommen so eine leere Datenbank)."""
    global _client, _db
    _client = None
    _db = None


async def indizes_anlegen(d) -> None:
    """Indizes für Mandantentrennung und schnelle Abfragen. Fehler brechen den Start nicht ab."""
    aufgaben = [
        ("users", [("email", 1)], {"unique": True, "name": "email_eindeutig"}),
        ("users", [("firma_id", 1), ("active", 1)], {"name": "firma_aktiv"}),
        ("users", [("einladung_token", 1)], {"name": "einladung", "sparse": True}),
        ("customers", [("firma_id", 1), ("name", 1)], {"name": "firma_name"}),
        ("projects", [("firma_id", 1), ("archived", 1)], {"name": "firma_archiv"}),
        ("entries", [("firma_id", 1), ("project_id", 1), ("date", 1)], {"name": "projekt_datum"}),
        ("entries", [("firma_id", 1), ("user_id", 1), ("date", 1)], {"name": "nutzer_datum"}),
        ("stempel", [("firma_id", 1), ("user_id", 1)], {"unique": True, "name": "ein_stempel_je_nutzer"}),
        ("absences", [("firma_id", 1), ("user_id", 1), ("from_date", 1)], {"name": "nutzer_von"}),
        ("documents", [("firma_id", 1), ("scope", 1), ("ref_id", 1)], {"name": "akte"}),
        ("comments", [("firma_id", 1), ("project_id", 1), ("created_at", -1)], {"name": "projekt_zeit"}),
        ("checklists", [("firma_id", 1), ("project_id", 1)], {"name": "projekt"}),
        ("signatures", [("firma_id", 1), ("project_id", 1), ("week_monday", 1)], {"name": "projekt_woche"}),
        ("invoices", [("firma_id", 1), ("year", 1), ("seq", 1)], {"unique": True, "name": "nummer_je_firma_jahr"}),
        ("invoices", [("firma_id", 1), ("project_id", 1), ("year", 1), ("month", 1)], {"unique": True, "name": "eine_je_projekt_monat"}),
        ("protokoll", [("firma_id", 1), ("created_at", -1)], {"name": "firma_zeit"}),
        ("api_tokens", [("token_hash", 1)], {"unique": True, "name": "token"}),
        ("services", [("firma_id", 1), ("sort", 1)], {"name": "firma_sort"}),
        ("zeitkonto", [("firma_id", 1), ("user_id", 1), ("date", 1)], {"name": "nutzer_datum"}),
        ("webhooks", [("firma_id", 1), ("active", 1)], {"name": "firma_aktiv"}),
        ("abschluesse", [("firma_id", 1), ("year", 1), ("month", 1)], {"unique": True, "name": "firma_monat"}),
    ]
    for sammlung, schluessel, optionen in aufgaben:
        try:
            await d[sammlung].create_index(schluessel, **optionen)
        except Exception as exc:  # noqa: BLE001 — Abfragen laufen auch ohne Index, nur langsamer
            print(f"Index {sammlung}.{optionen.get('name')} nicht angelegt: {exc}")
