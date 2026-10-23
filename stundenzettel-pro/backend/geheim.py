"""Verschlüsselung sensibler Personaldaten (Steuer-ID, Sozialversicherungsnummer, IBAN) in der Datenbank.

Schlüssel: DATEN_SCHLUESSEL in der .env (Fernet-Schlüssel, erzeugen mit
`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`).
Fehlt er, wird ein Schlüssel aus JWT_SECRET abgeleitet – reicht für Entwicklung und Tests; im Betrieb bitte eigenen Schlüssel setzen
und sicher aufbewahren (ohne Schlüssel sind die Felder nicht mehr lesbar)."""
import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

import config

PRAEFIX = "enc:"


def _fernet() -> Fernet:
    schluessel = config.DATEN_SCHLUESSEL
    if not schluessel:
        schluessel = base64.urlsafe_b64encode(hashlib.sha256(("daten:" + config.JWT_SECRET).encode()).digest()).decode()
    return Fernet(schluessel.encode() if isinstance(schluessel, str) else schluessel)


def verschluesseln(text) -> str:
    if text is None or str(text) == "":
        return ""
    return PRAEFIX + _fernet().encrypt(str(text).encode()).decode()


def entschluesseln(wert) -> str:
    if not wert:
        return ""
    wert = str(wert)
    if not wert.startswith(PRAEFIX):
        return wert  # unverschlüsselter Altbestand
    try:
        return _fernet().decrypt(wert[len(PRAEFIX):].encode()).decode()
    except InvalidToken:
        return "(nicht lesbar – Schlüssel passt nicht)"


def ist_verschluesselt(wert) -> bool:
    return isinstance(wert, str) and wert.startswith(PRAEFIX)
