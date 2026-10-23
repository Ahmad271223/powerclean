"""Lohnvorbereitung für Lohnbüro/Steuerberater/DATEV – ohne eigene Lohnberechnung (siehe lohn.py)."""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

import lohn
from auth import firma_laden, firmenabo_lesend, rolle_noetig
from db import db
from protokoll import protokollieren

router = APIRouter(prefix="/api/lohn", tags=["lohn"])


async def _daten(user: dict, jahr: int, monat: int) -> tuple[dict, dict]:
    firma = await firma_laden(user["firma_id"])
    return firma, await lohn.lohnvorbereitung(firma, jahr, monat)


def _datei(inhalt: bytes, name: str, typ: str) -> Response:
    return Response(content=inhalt, media_type=typ, headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/vorbereitung")
async def vorbereitung(jahr: int = Query(..., ge=2025, le=2100), monat: int = Query(..., ge=1, le=12), user: dict = Depends(firmenabo_lesend("buero"))):
    _, daten = await _daten(user, jahr, monat)
    return daten


@router.get("/vorbereitung.csv")
async def vorbereitung_csv(jahr: int = Query(..., ge=2025, le=2100), monat: int = Query(..., ge=1, le=12), user: dict = Depends(firmenabo_lesend("buero"))):
    _, daten = await _daten(user, jahr, monat)
    await protokollieren(user, "export.lohnvorbereitung", f"{jahr}-{monat:02d}", details={"format": "csv", "mitarbeiter": len(daten["mitarbeiter"])})
    return _datei(lohn.vorbereitung_csv(daten), f"Lohnvorbereitung_{jahr}-{monat:02d}.csv", "text/csv; charset=utf-8")


@router.get("/lodas.txt")
async def lodas(jahr: int = Query(..., ge=2025, le=2100), monat: int = Query(..., ge=1, le=12), user: dict = Depends(firmenabo_lesend("buero"))):
    _, daten = await _daten(user, jahr, monat)
    einst = daten.get("lohn_export") or {}
    if not any((einst.get("lohnarten") or {}).values()):
        raise HTTPException(422, "Keine Lohnarten-Nummern hinterlegt. Unter Exporte → Lohnvorbereitung → DATEV-Einstellungen mindestens "
                                 "„Stunden gesamt“ eintragen – die Nummern gibt der Steuerberater vor.")
    text, hinweise = lohn.lodas_text(daten)
    if not any(z.startswith("100;") for z in text.split("[Bewegungsdaten]")[-1].splitlines()):
        raise HTTPException(422, "Die LODAS-Datei wäre leer: " + (" ".join(hinweise) if hinweise else "keine Stunden oder Abwesenheiten in diesem Monat."))
    await protokollieren(user, "export.lohnvorbereitung", f"{jahr}-{monat:02d}", details={"format": "lodas", "hinweise": hinweise[:5]})
    return Response(content=text.encode("cp1252", errors="replace"), media_type="text/plain; charset=windows-1252",
                    headers={"Content-Disposition": f'attachment; filename="LODAS_{jahr}-{monat:02d}.txt"', "X-Hinweise": str(len(hinweise))})


@router.get("/lodas-pruefung")
async def lodas_pruefung(jahr: int = Query(..., ge=2025, le=2100), monat: int = Query(..., ge=1, le=12), user: dict = Depends(firmenabo_lesend("buero"))):
    """Vorschau der LODAS-Datei und Hinweise (fehlende Lohnarten/Personalnummern), bevor sie verschickt wird."""
    _, daten = await _daten(user, jahr, monat)
    text, hinweise = lohn.lodas_text(daten)
    return {"zeilen": len([z for z in text.split("[Bewegungsdaten]")[-1].splitlines() if z.startswith("100;")]), "hinweise": hinweise, "vorschau": text[:3000]}


@router.get("/vorbereitung.pdf")
async def vorbereitung_pdf(jahr: int = Query(..., ge=2025, le=2100), monat: int = Query(..., ge=1, le=12), user: dict = Depends(firmenabo_lesend("buero"))):
    firma, daten = await _daten(user, jahr, monat)
    await protokollieren(user, "export.lohnvorbereitung", f"{jahr}-{monat:02d}", details={"format": "pdf"})
    return _datei(lohn.vorbereitung_pdf(firma, daten), f"Lohnvorbereitung_{jahr}-{monat:02d}.pdf", "application/pdf")


@router.get("/stammdaten.csv")
async def stammdaten(user: dict = Depends(firmenabo_lesend("buero"))):
    """Personal-, Steuer- und SV-Daten aller aktiven Mitarbeiter für die Anlage beim Steuerberater (wird protokolliert)."""
    nutzer = [u async for u in db().users.find({"firma_id": user["firma_id"], "active": {"$ne": False}}, {"_id": 0, "pw_hash": 0, "pin_hash": 0, "einladung_token": 0})]
    nutzer = [u for u in nutzer if not u.get("deleted_at")]
    nutzer.sort(key=lambda u: (u.get("name") or "").lower())
    await protokollieren(user, "export.stammdaten", details={"mitarbeiter": len(nutzer)})
    return _datei(lohn.stammdaten_csv(nutzer), "Stammdaten_Lohn.csv", "text/csv; charset=utf-8")
