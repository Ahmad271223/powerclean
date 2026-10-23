"""Entwicklungsstart ohne MongoDB: Datenbank im Speicher, Oberfläche aus frontend/dist (falls gebaut).

    python dev.py            # http://localhost:8010  (API + gebaute Oberfläche)
    python dev.py --reload   # mit Neuladen bei Codeänderungen (Daten gehen dabei verloren)
"""
import os
import sys

os.environ.setdefault("DB_MODE", "memory")
os.environ.setdefault("JWT_SECRET", "nur-entwicklung-" + "x" * 40)
os.environ.setdefault("ADMIN_TOKEN", "dev-betreiber")
os.environ.setdefault("BASE_URL", "http://localhost:8010")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5175,http://127.0.0.1:5175,http://localhost:8010")

if __name__ == "__main__":
    import uvicorn
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    uvicorn.run("server:app", host="127.0.0.1", port=int(os.environ.get("PORT", "8010")), reload="--reload" in sys.argv)
