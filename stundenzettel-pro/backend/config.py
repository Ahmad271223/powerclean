"""Konfiguration der Server-Version (alles über Umgebungsvariablen, siehe .env.example)."""
import os
from pathlib import Path

BASIS = Path(__file__).resolve().parent


def env(name: str, standard: str = "") -> str:
    return os.environ.get(name, standard)


# Anmeldung
JWT_SECRET = env("JWT_SECRET", "nur-entwicklung-bitte-in-env-setzen")
JWT_TAGE = int(env("JWT_TAGE", "30"))

# Datenbank: "mongo" (Betrieb) oder "memory" (Entwicklung/Tests ohne MongoDB)
DB_MODE = env("DB_MODE", "mongo")
MONGO_URL = env("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = env("DB_NAME", "stundenzettel_pro")

# Dateien (Personalakte, Projektakte) liegen auf der Platte, Metadaten in der Datenbank
DATA_DIR = Path(env("DATA_DIR", str(BASIS / "daten")))
MAX_DATEI_MB = int(env("MAX_DATEI_MB", "25"))
SPEICHER_GB = float(env("SPEICHER_GB", "5"))            # Speicherplatz je Firma (Standard; je Firma über plan.speicher_gb anpassbar)
UPLOADS_JE_10_MIN = int(env("UPLOADS_JE_10_MIN", "120"))  # Uploadrate je Nutzer

# Oberfläche
FRONTEND_DIST = Path(env("FRONTEND_DIST", str(BASIS.parent / "frontend" / "dist")))
# Browser-Herkünfte: Entwicklung plus die nativen Apps (Capacitor: iOS capacitor://localhost, Android https://localhost)
CORS_ORIGINS = [o.strip() for o in env("CORS_ORIGINS", "http://localhost:5175,http://127.0.0.1:5175,capacitor://localhost,https://localhost,http://localhost").split(",") if o.strip()]
BASE_URL = env("BASE_URL", "").rstrip("/")  # öffentliche Adresse, z. B. https://pro.stundenzettel.app (für Einladungslinks)

# Impressum / Datenschutz (Pflichtseiten für die Stores: /impressum und /datenschutz)
ANBIETER_NAME = env("ANBIETER_NAME", "")
ANBIETER_ANSCHRIFT = env("ANBIETER_ANSCHRIFT", "")
ANBIETER_EMAIL = env("ANBIETER_EMAIL", "")
ANBIETER_TELEFON = env("ANBIETER_TELEFON", "")

# Native Apps (Deep Links für QR-Codes: /.well-known/assetlinks.json und apple-app-site-association)
ANDROID_PACKAGE = env("ANDROID_PACKAGE", "de.stundenzettelpro.app")
ANDROID_SHA256 = [s.strip().upper() for s in env("ANDROID_SHA256", "").split(",") if s.strip()]  # Signatur-Fingerabdrücke
IOS_BUNDLE_ID = env("IOS_BUNDLE_ID", "de.stundenzettelpro.app")
APPLE_TEAM_ID = env("APPLE_TEAM_ID", "")

# Lizenz
TEST_TAGE = int(env("TEST_TAGE", "14"))
ADMIN_TOKEN = env("ADMIN_TOKEN", "")
# Fernet-Schluessel fuer verschluesselte Personaldaten (Steuer-ID, SV-Nummer, IBAN); leer = aus JWT_SECRET abgeleitet (nur Entwicklung)
DATEN_SCHLUESSEL = env("DATEN_SCHLUESSEL", "")  # Betreiber-Schlüssel zum Freischalten von Firmen (POST /api/admin/plan)

# Zeitzone für die Stempeluhr (Datum/Uhrzeit des Eintrags)
ZEITZONE = env("ZEITZONE", "Europe/Berlin")

MIN_JAHR = 2025

# Webhooks: nur https und Standardports; http nur bewusst für Tests (WEBHOOK_HTTP_ERLAUBEN=1)
WEBHOOK_HTTP_ERLAUBEN = env("WEBHOOK_HTTP_ERLAUBEN", "") == "1"
WEBHOOK_PORTS = {int(p) for p in env("WEBHOOK_PORTS", "80,443,8443").split(",") if p.strip().isdigit()}

# Lizenzmodell: nach der Testphase kostenlose Projektteilnahme (Ausschreibungen, Angebote, Mitarbeit in GU-Projekten) statt Vollsperre
TEILNAHME_KOSTENLOS = env("TEILNAHME_KOSTENLOS", "1") == "1"
