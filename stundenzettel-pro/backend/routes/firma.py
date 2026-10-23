"""Firmendaten, Lizenz, API-Schlüssel, Sicherheitsprotokoll, Betreiber-Freischaltung."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from auth import hat_rolle, aktueller_nutzer, api_token_neu, betreiber_pruefen, firma_laden, jetzt_iso, plan_status, rolle_noetig, schreibend
from datetime import timedelta

from auth import API_RECHTE, jetzt
from db import db
from gemeinsam import firma_oeffentlich, neue_id
from models import ApiTokenIn, FirmaIn, FirmaLoeschenIn, PlanIn, WebhookIn
from protokoll import protokollieren

router = APIRouter(tags=["Firma"])


@router.get("/api/firma")
async def firma_lesen(user: dict = Depends(aktueller_nutzer)):
    firma = await firma_laden(user["firma_id"])
    return {"firma": firma_oeffentlich(firma, user), "plan": plan_status(firma)}


@router.put("/api/firma")
async def firma_aendern(body: FirmaIn, user: dict = Depends(schreibend("buero"))):
    aenderung = {k: v for k, v in body.model_dump(exclude_unset=True).items()}
    if "name" in aenderung and not (aenderung["name"] or "").strip():
        raise HTTPException(400, "Der Firmenname darf nicht leer sein.")
    if aenderung.get("art") is None:
        aenderung.pop("art", None)
    elif not hat_rolle(user, "inhaber"):
        raise HTTPException(403, "Die Firmenart ändert nur der Inhaber.")
    if not aenderung:
        return await firma_lesen(user)
    aenderung["updated_at"] = jetzt_iso()
    await db().firmen.update_one({"id": user["firma_id"]}, {"$set": aenderung})
    felder = [k for k in aenderung if k not in ("logo", "stamp", "stamp_config", "updated_at")]
    await protokollieren(user, "firma.geaendert", details={"felder": felder, "logo": "logo" in aenderung, "stempel": "stamp" in aenderung})
    firma = await firma_laden(user["firma_id"])
    return {"firma": firma_oeffentlich(firma, user), "plan": plan_status(firma)}


@router.get("/api/firma/plan")
async def plan_lesen(user: dict = Depends(rolle_noetig("buero"))):
    firma = await firma_laden(user["firma_id"])
    nutzer = await db().users.count_documents({"firma_id": user["firma_id"], "active": True})
    st = plan_status(firma)
    st["nutzer_aktiv"] = nutzer
    st["hinweis_betreiber"] = (firma.get("plan") or {}).get("hinweis") or ""
    return st


@router.delete("/api/firma")
async def firma_loeschen(body: FirmaLoeschenIn, user: dict = Depends(rolle_noetig("inhaber"))):
    """Firma mit ALLEN Daten unwiderruflich löschen (Store-Pflicht „Konto löschen“ für den Inhaber)."""
    from auth import passwort_pruefen
    from dateien import datei_loeschen
    firma = await firma_laden(user["firma_id"])
    if not passwort_pruefen(body.password, user.get("pw_hash")):
        raise HTTPException(400, "Das Passwort stimmt nicht.")
    if body.name.strip() != (firma.get("name") or "").strip():
        raise HTTPException(400, "Der Firmenname stimmt nicht überein – nichts gelöscht.")
    f = user["firma_id"]
    async for d in db().documents.find({"firma_id": f}, {"_id": 0, "path": 1}):
        datei_loeschen(d)
    for sammlung in ("entries", "projects", "customers", "absences", "invoices", "comments", "checklists", "signatures", "documents",
                     "stempel", "services", "zeitkonto", "webhooks", "abschluesse", "api_tokens", "protokoll", "users"):
        await db()[sammlung].delete_many({"firma_id": f})
    await db().firmen.delete_one({"id": f})
    return {"ok": True, "hinweis": "Die Firma und alle Daten wurden gelöscht."}


# ---------------------------------------------------------------- API-Schlüssel (nur Inhaber)
@router.get("/api/firma/api-tokens")
async def api_tokens(user: dict = Depends(rolle_noetig("inhaber"))):
    aus = []
    async for t in db().api_tokens.find({"firma_id": user["firma_id"]}, {"_id": 0, "token_hash": 0}):
        aus.append(t)
    return {"tokens": aus}


@router.post("/api/firma/api-tokens")
async def api_token_anlegen(body: ApiTokenIn, user: dict = Depends(schreibend("inhaber"))):
    roh, h = api_token_neu()
    rechte = [r for r in dict.fromkeys(body.rechte) if r in API_RECHTE] or ["zeiten"]
    t = {"id": neue_id(), "firma_id": user["firma_id"], "name": body.name.strip(), "token_hash": h, "rechte": rechte,
         "gueltig_bis": (jetzt() + timedelta(days=body.tage)).isoformat(), "created_at": jetzt_iso(), "created_by": user["id"], "last_used_at": None}
    await db().api_tokens.insert_one(dict(t))
    await protokollieren(user, "api_token.angelegt", t["name"], details={"rechte": rechte, "tage": body.tage})
    t.pop("token_hash")
    return {"token": roh, "eintrag": t, "hinweis": "Der Schlüssel wird nur jetzt einmal angezeigt."}


@router.delete("/api/firma/api-tokens/{token_id}")
async def api_token_loeschen(token_id: str, user: dict = Depends(rolle_noetig("inhaber"))):
    r = await db().api_tokens.delete_one({"id": token_id, "firma_id": user["firma_id"]})
    if not r.deleted_count:
        raise HTTPException(404, "Schlüssel nicht gefunden.")
    await protokollieren(user, "api_token.geloescht", token_id)
    return {"ok": True}


# ---------------------------------------------------------------- Webhooks (nur Inhaber)
@router.get("/api/firma/webhooks")
async def webhooks_liste(user: dict = Depends(rolle_noetig("inhaber"))):
    import webhooks as wh
    stand = await wh.ausgang_stand(user["firma_id"])
    aus = [{**h, "ausgang": stand.get(h["id"], {"offen": 0, "fehlgeschlagen": 0})} async for h in db().webhooks.find({"firma_id": user["firma_id"]}, {"_id": 0, "secret": 0})]
    return {"webhooks": aus, "ereignisse": wh.EREIGNISSE}


@router.post("/api/firma/webhooks")
async def webhook_anlegen(body: WebhookIn, user: dict = Depends(schreibend("inhaber"))):
    import secrets
    import webhooks as wh
    events = [e for e in body.events if e == "*" or e in wh.EREIGNISSE] or ["*"]
    try:
        url = wh.url_pruefen(body.url)   # SSRF-Schutz: nur öffentliche https-Ziele
    except wh.UnsichereAdresse as exc:
        raise HTTPException(400, str(exc))
    h = {"id": neue_id(), "firma_id": user["firma_id"], "name": (body.name or "").strip() or url[:60], "url": url,
         "events": events, "active": body.active, "secret": secrets.token_hex(24), "created_at": jetzt_iso(), "last_status": None, "last_at": None}
    await db().webhooks.insert_one(dict(h))
    await protokollieren(user, "webhook.angelegt", h["url"], details={"ereignisse": events})
    geheim = h.pop("secret")
    return {"webhook": h, "secret": geheim, "hinweis": "Das Geheimnis für die Signatur wird nur jetzt angezeigt."}


@router.delete("/api/firma/webhooks/{webhook_id}")
async def webhook_loeschen(webhook_id: str, user: dict = Depends(rolle_noetig("inhaber"))):
    r = await db().webhooks.delete_one({"id": webhook_id, "firma_id": user["firma_id"]})
    if not r.deleted_count:
        raise HTTPException(404, "Webhook nicht gefunden.")
    await protokollieren(user, "webhook.geloescht", webhook_id)
    return {"ok": True}


@router.post("/api/firma/webhooks/{webhook_id}/test")
async def webhook_test(webhook_id: str, user: dict = Depends(rolle_noetig("inhaber"))):
    import webhooks as wh
    h = await db().webhooks.find_one({"id": webhook_id, "firma_id": user["firma_id"]}, {"_id": 0, "id": 1})
    if not h:
        raise HTTPException(404, "Webhook nicht gefunden.")
    ergebnisse = await wh.senden(user["firma_id"], "test", {"hinweis": "Testereignis aus Stundenzettel Pro", "von": user.get("name")})
    status = next((e["status"] for e in ergebnisse if e["id"] == webhook_id), 0)
    return {"status": status, "ok": 200 <= status < 300}


# ---------------------------------------------------------------- Protokoll
@router.get("/api/protokoll")
async def protokoll_lesen(limit: int = Query(200, ge=1, le=2000), user: dict = Depends(rolle_noetig("buero"))):
    aus = []
    async for p in db().protokoll.find({"firma_id": user["firma_id"]}, {"_id": 0}).sort("created_at", -1).limit(limit):
        aus.append(p)
    return {"eintraege": aus}


# ---------------------------------------------------------------- Betreiber: Firma freischalten / sperren
@router.post("/api/admin/plan", dependencies=[Depends(betreiber_pruefen)])
async def plan_setzen(body: PlanIn):
    """Betreiber schaltet eine Firma frei (bis Zahlung automatisch läuft). Firma über id oder E-Mail des Inhabers."""
    firma = None
    if body.firma_id:
        firma = await db().firmen.find_one({"id": body.firma_id}, {"_id": 0})
    elif body.email:
        u = await db().users.find_one({"email": body.email.lower()}, {"_id": 0, "firma_id": 1})
        if u:
            firma = await db().firmen.find_one({"id": u["firma_id"]}, {"_id": 0})
    if not firma:
        raise HTTPException(404, "Firma nicht gefunden.")
    plan = {"status": body.status, "nutzer_max": body.nutzer_max, "gueltig_bis": body.gueltig_bis,
            "test_bis": body.test_bis or (firma.get("plan") or {}).get("test_bis"), "hinweis": body.hinweis or "",
            "stufe": body.stufe or (firma.get("plan") or {}).get("stufe") or "plus", "gesetzt_am": jetzt_iso()}
    await db().firmen.update_one({"id": firma["id"]}, {"$set": {"plan": plan}})
    await protokollieren(None, "plan.gesetzt", firma["name"], details=plan, firma_id=firma["id"])
    return {"ok": True, "firma_id": firma["id"], "plan": plan_status({**firma, "plan": plan})}


@router.get("/api/admin/firmen", dependencies=[Depends(betreiber_pruefen)])
async def firmen_liste():
    aus = []
    async for f in db().firmen.find({}, {"_id": 0, "id": 1, "name": 1, "email": 1, "created_at": 1, "plan": 1}):
        f["nutzer"] = await db().users.count_documents({"firma_id": f["id"], "active": True})
        f["status"] = plan_status(f)
        aus.append(f)
    return {"firmen": aus}
