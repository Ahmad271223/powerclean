"""Stundenzettel Pro – Server-Version (FastAPI).

Start (Entwicklung ohne MongoDB):  DB_MODE=memory python -m uvicorn server:app --reload --port 8010
Start (Betrieb):                   docker compose up -d   (siehe README)
API-Dokumentation:                 /api/docs
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import config
from db import db, indizes_anlegen
from routes import (abschluss, api_v1, auth_routes, auswertung, dashboard, exporte, firma, import_free, konten, kunden,
                    leistungen, mitarbeiter, projekte, rechnungen, zeiten_routes)

VERSION = "1.1.0"


@asynccontextmanager
async def lebenszyklus(app: FastAPI):
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    await indizes_anlegen(db())
    yield


app = FastAPI(title="Stundenzettel Pro", version=VERSION, docs_url="/api/docs", openapi_url="/api/openapi.json",
              redoc_url=None, lifespan=lebenszyklus)
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

for modul in (auth_routes, firma, mitarbeiter, kunden, projekte, zeiten_routes, rechnungen, exporte, import_free, api_v1, dashboard,
              konten, leistungen, auswertung, abschluss):
    app.include_router(modul.router)


@app.exception_handler(RequestValidationError)
async def eingabefehler(_: Request, exc: RequestValidationError):
    """Eine verständliche Meldung statt der rohen Fehlerliste."""
    fehler = exc.errors()
    erster = fehler[0] if fehler else {}
    feld = ".".join(str(x) for x in erster.get("loc", []) if x not in ("body", "query", "path"))
    text = str(erster.get("msg", "Eingabe ungültig")).replace("Value error, ", "")
    kurz = [{"feld": ".".join(str(x) for x in e.get("loc", [])), "text": str(e.get("msg", ""))} for e in fehler]
    return JSONResponse(status_code=422, content={"detail": f"{feld}: {text}" if feld else text, "fehler": kurz})


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": VERSION, "db": config.DB_MODE}


# ---------------------------------------------------------------- Oberfläche (gebautes Frontend)
dist = config.FRONTEND_DIST
if dist.exists() and (dist / "index.html").exists():
    if (dist / "assets").exists():
        app.mount("/assets", StaticFiles(directory=str(dist / "assets")), name="assets")

    @app.get("/{pfad:path}", include_in_schema=False)
    async def oberflaeche(pfad: str):
        if pfad.startswith("api/"):
            return JSONResponse(status_code=404, content={"detail": "Nicht gefunden."})
        ziel = (dist / pfad).resolve()
        if pfad and ziel.is_file() and str(ziel).startswith(str(dist.resolve())):
            return FileResponse(str(ziel))
        return FileResponse(str(dist / "index.html"))
