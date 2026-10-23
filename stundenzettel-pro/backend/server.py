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
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import config
from db import db, indizes_anlegen
from routes import (abschluss, api_v1, ausschreibungen, auth_routes, auswertung, baustelle, dashboard, exporte, firma, import_free, konten, kunden,
                    leistungen, lohn, mitarbeiter, plattform, projekte, rechnungen, zeiten_routes)

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
              konten, leistungen, auswertung, abschluss, lohn, plattform, baustelle, ausschreibungen):
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


# ---------------------------------------------------------------- Pflichtseiten und Deep Links (Stores)
@app.get("/datenschutz", include_in_schema=False)
async def datenschutz():
    import rechtstexte
    return HTMLResponse(rechtstexte.datenschutz())


@app.get("/impressum", include_in_schema=False)
async def impressum():
    import rechtstexte
    return HTMLResponse(rechtstexte.impressum())


@app.get("/.well-known/assetlinks.json", include_in_schema=False)
async def assetlinks():
    """Android App Links: QR-Codes und Einladungslinks öffnen die installierte App (Signatur-Fingerabdrücke aus ANDROID_SHA256)."""
    if not config.ANDROID_SHA256:
        return JSONResponse(status_code=404, content={"detail": "ANDROID_SHA256 nicht gesetzt."})
    return JSONResponse([{"relation": ["delegate_permission/common.handle_all_urls"],
                          "target": {"namespace": "android_app", "package_name": config.ANDROID_PACKAGE, "sha256_cert_fingerprints": config.ANDROID_SHA256}}])


@app.get("/.well-known/apple-app-site-association", include_in_schema=False)
async def apple_app_site_association():
    """iOS Universal Links (APPLE_TEAM_ID + IOS_BUNDLE_ID)."""
    if not config.APPLE_TEAM_ID:
        return JSONResponse(status_code=404, content={"detail": "APPLE_TEAM_ID nicht gesetzt."})
    app_id = f"{config.APPLE_TEAM_ID}.{config.IOS_BUNDLE_ID}"
    return JSONResponse({"applinks": {"apps": [], "details": [{"appID": app_id, "paths": ["/", "/#*"]}]},
                         "webcredentials": {"apps": [app_id]}}, media_type="application/json")


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
