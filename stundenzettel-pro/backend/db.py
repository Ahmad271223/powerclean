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
        ("entries", [("firma_id", 1), ("offline_id", 1)], {"name": "offline_kennung"}),   # Eindeutigkeit prüft die Route (Speicher-DB kennt kein sparse)
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
        # Plattform (Zusammenarbeit mehrerer Firmen)
        ("firmen", [("verzeichnis.sichtbar", 1)], {"name": "verzeichnis"}),
        ("beteiligungen", [("project_id", 1), ("firma_id", 1), ("status", 1)], {"name": "projekt_firma"}),
        ("beteiligungen", [("firma_id", 1), ("status", 1)], {"name": "firma_status"}),
        ("beteiligungen", [("token", 1)], {"name": "token", "sparse": True}),
        ("projekt_leiter", [("project_id", 1), ("user_id", 1)], {"name": "projekt_nutzer"}),
        ("aufgaben", [("project_id", 1), ("datum", 1)], {"name": "projekt_datum"}),
        ("aufgaben", [("firma_id", 1), ("status", 1), ("datum", 1)], {"name": "firma_status_datum"}),
        ("freigaben", [("project_id", 1), ("week_monday", -1)], {"name": "projekt_woche"}),
        ("freigaben", [("beteiligung_id", 1), ("week_monday", 1)], {"name": "beteiligung_woche"}),
        ("benachrichtigungen", [("firma_id", 1), ("created_at", -1)], {"name": "firma_zeit"}),
        ("lieferungen", [("project_id", 1), ("geplant_am", 1)], {"name": "projekt_datum"}),
        ("maengel", [("project_id", 1), ("status", 1)], {"name": "projekt_status"}),
        ("tagesberichte", [("project_id", 1), ("datum", -1)], {"name": "projekt_datum"}),
        ("meilensteine", [("project_id", 1), ("datum", 1)], {"name": "projekt_datum"}),
        # Ausschreibungen und Vergabe
        ("ausschreibungen", [("firma_id", 1), ("status", 1)], {"name": "firma_status"}),
        ("ausschreibungen", [("project_id", 1)], {"name": "projekt"}),
        ("ausschreibungen", [("status", 1), ("sichtbarkeit", 1), ("angebotsfrist", 1)], {"name": "marktplatz"}),
        ("ausschreibungen", [("firma_id", 1), ("nummer", 1)], {"unique": True, "name": "nummer_je_firma"}),
        ("ausschreibung_einladungen", [("ausschreibung_id", 1), ("firma_id", 1)], {"unique": True, "name": "eine_je_firma"}),
        ("ausschreibung_einladungen", [("firma_id", 1), ("status", 1)], {"name": "firma_status"}),
        ("angebote", [("ausschreibung_id", 1), ("firma_id", 1)], {"unique": True, "name": "ein_angebot_je_firma"}),
        ("angebote", [("firma_id", 1), ("status", 1)], {"name": "firma_status"}),
        ("ausschreibung_fragen", [("ausschreibung_id", 1), ("created_at", 1)], {"name": "ausschreibung_zeit"}),
        ("vergaben", [("ausschreibung_id", 1), ("status", 1)], {"name": "ausschreibung_status"}),
        ("vergaben", [("firma_id", 1), ("status", 1)], {"name": "firma_status"}),
        ("webhook_ausgang", [("status", 1), ("naechster_versuch_at", 1)], {"name": "faellig"}),
        # E-Mail-Ausgang, Bauabwicklung, Projektakten
        ("email_ausgang", [("status", 1), ("naechster_versuch_at", 1)], {"name": "faellig"}),
        ("email_ausgang", [("firma_id", 1), ("created_at", -1)], {"name": "firma_zeit"}),
        ("email_ausgang", [("absender_firma_id", 1), ("created_at", -1)], {"name": "absender_zeit"}),
        ("nachtraege", [("project_id", 1), ("firma_id", 1), ("status", 1)], {"name": "projekt_firma_status"}),
        ("nachtraege", [("owner_firma_id", 1), ("status", 1)], {"name": "eigentuemer_status"}),
        ("abnahmen", [("project_id", 1), ("firma_id", 1), ("status", 1)], {"name": "projekt_firma_status"}),
        ("abnahmen", [("owner_firma_id", 1), ("status", 1)], {"name": "eigentuemer_status"}),
        ("projektakten", [("firma_id", 1), ("project_id", 1), ("created_at", -1)], {"name": "firma_projekt_zeit"}),
        # Plantafel
        ("einsaetze", [("firma_id", 1), ("date", 1), ("user_id", 1)], {"name": "firma_datum_person"}),
        ("einsaetze", [("firma_id", 1), ("user_id", 1), ("date", 1), ("status", 1)], {"name": "person_datum"}),
        ("einsaetze", [("date", 1), ("status", 1)], {"name": "erinnerung_faellig"}),
        ("kolonnen", [("firma_id", 1), ("name", 1)], {"name": "firma_name"}),
        ("erinnerungen", [("id", 1)], {"unique": True, "name": "kennung"}),
        ("benachrichtigungen", [("id", 1)], {"name": "kennung"}),
        ("webhook_ausgang", [("firma_id", 1), ("webhook_id", 1), ("status", 1)], {"name": "firma_hook"}),
    ]
    for sammlung, schluessel, optionen in aufgaben:
        try:
            await d[sammlung].create_index(schluessel, **optionen)
        except Exception as exc:  # noqa: BLE001 — Abfragen laufen auch ohne Index, nur langsamer
            print(f"Index {sammlung}.{optionen.get('name')} nicht angelegt: {exc}")
