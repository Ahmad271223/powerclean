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
MAX_DATEI_MB = int(env("MAX_DATEI_MB", "15"))

# Oberfläche
FRONTEND_DIST = Path(env("FRONTEND_DIST", str(BASIS.parent / "frontend" / "dist")))
CORS_ORIGINS = [o.strip() for o in env("CORS_ORIGINS", "http://localhost:5175,http://127.0.0.1:5175").split(",") if o.strip()]
BASE_URL = env("BASE_URL", "").rstrip("/")  # öffentliche Adresse, z. B. https://pro.stundenzettel.app (für Einladungslinks)

# Lizenz
TEST_TAGE = int(env("TEST_TAGE", "14"))
ADMIN_TOKEN = env("ADMIN_TOKEN", "")  # Betreiber-Schlüssel zum Freischalten von Firmen (POST /api/admin/plan)

# Zeitzone für die Stempeluhr (Datum/Uhrzeit des Eintrags)
ZEITZONE = env("ZEITZONE", "Europe/Berlin")

MIN_JAHR = 2025
