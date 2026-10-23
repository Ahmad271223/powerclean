"""Startseite: Zahlen des Tages und des Monats, Hinweise (ArbZG, Budgets, vergessene Stempelungen, Abschluss), je nach Rolle."""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends

from auth import aktueller_nutzer, firma_laden, hat_rolle, plan_status
from db import db
from gemeinsam import budget_info, nutzernamen, projekt_normalisieren, projekt_sichtbar
from konten import kontoverlauf, urlaubskonto
from zeiten import eintrag_minuten, eintrag_satz, lokal_jetzt, monatsletzter, montag_von

router = APIRouter(prefix="/api/dashboard", tags=["Übersicht"])


@router.get("")
async def dashboard(user: dict = Depends(aktueller_nutzer)):
    f = user["firma_id"]
    heute_d = lokal_jetzt().date()
    heute = heute_d.isoformat()
    montag = montag_von(heute_d).isoformat()
    sonntag = (montag_von(heute_d) + timedelta(days=6)).isoformat()
    monat_von = heute_d.replace(day=1).isoformat()
    monat_bis = monatsletzter(heute_d.year, heute_d.month).isoformat()
    firma = await firma_laden(f)
    aus = {"heute": heute, "plan": plan_status(firma), "rolle": user.get("role")}

    if hat_rolle(user, "buero"):
        projekte = {}
        async for p in db().projects.find({"firma_id": f}, {"_id": 0}):
            projekte[p["id"]] = projekt_normalisieren(p)
        minuten_monat, umsatz, tage_heute = 0, 0.0, 0
        je_projekt: dict[str, int] = {}
        warn_tage = set()
        async for e in db().entries.find({"firma_id": f, "date": {"$gte": monat_von, "$lte": monat_bis}}, {"_id": 0, "project_id": 1, "net_minutes": 1, "workers": 1, "date": 1, "user_id": 1, "service_id": 1, "service_rate": 1, "warnungen": 1}):
            m = eintrag_minuten(e)
            minuten_monat += m
            p = projekte.get(e.get("project_id"), {})
            umsatz += m / 60 * eintrag_satz(e, p, firma)
            je_projekt[e.get("project_id")] = je_projekt.get(e.get("project_id"), 0) + m
            if e.get("date") == heute:
                tage_heute += 1
            if e.get("warnungen"):
                warn_tage.add((e.get("user_id"), e.get("date")))
        offen_antraege = await db().absences.count_documents({"firma_id": f, "status": "beantragt"})
        rech_offen, rech_summe = 0, 0.0
        async for r in db().invoices.find({"firma_id": f, "status": "offen"}, {"_id": 0, "gross": 1}):
            rech_offen += 1
            rech_summe += float(r.get("gross") or 0)
        namen = await nutzernamen(f)
        gestempelt, lange = 0, []
        async for s in db().stempel.find({"firma_id": f}, {"_id": 0}):
            gestempelt += 1
            from routes.zeiten_routes import _stempel_oeffentlich
            o = _stempel_oeffentlich(s, projekte)
            if o["lange"]:
                lange.append({"id": s["id"], "user_name": namen.get(s.get("user_id"), ""), "project_name": o["project_name"], "minuten": o["minuten"], "start_at": s["start_at"]})
        mitarbeiter = await db().users.count_documents({"firma_id": f, "active": True})
        aktiv = [p for p in projekte.values() if not p.get("archived")]
        aktiv.sort(key=lambda p: (p.get("last_activity_at") or "", p.get("name")), reverse=True)
        budgets = []
        for p in aktiv:
            b = budget_info(p, je_projekt.get(p["id"], 0))
            if b and b["warnung"]:
                budgets.append({"project_id": p["id"], "name": p["name"], **b})
        budgets.sort(key=lambda b: -b["prozent"])
        abwesend = []
        async for a in db().absences.find({"firma_id": f, "from_date": {"$lte": heute}, "to_date": {"$gte": heute}, "status": "genehmigt"}, {"_id": 0}):
            abwesend.append({"user_name": namen.get(a["user_id"], ""), "type": a["type"], "to_date": a["to_date"]})
        vormonat = (heute_d.replace(day=1) - timedelta(days=1))
        vormonat_zu = await db().abschluesse.find_one({"firma_id": f, "year": vormonat.year, "month": vormonat.month}) is not None
        aus.update({
            "heute_eintraege": tage_heute, "gestempelt": gestempelt, "mitarbeiter_aktiv": mitarbeiter, "projekte_aktiv": len(aktiv),
            "monat": {"minuten": minuten_monat, "umsatz_netto": round(umsatz, 2)},
            "antraege_offen": offen_antraege, "rechnungen_offen": {"anzahl": rech_offen, "summe": round(rech_summe, 2)},
            "letzte_projekte": aktiv[:6], "abwesend_heute": abwesend,
            "arbzg_warnungen": len(warn_tage), "budget_warnungen": budgets, "lange_stempelungen": lange,
            "vormonat": {"jahr": vormonat.year, "monat": vormonat.month, "abgeschlossen": vormonat_zu},
        })
    else:
        woche, monat = 0, 0
        letzte = []
        async for e in db().entries.find({"firma_id": f, "user_id": user["id"], "date": {"$gte": min(monat_von, montag), "$lte": max(monat_bis, sonntag)}}, {"_id": 0}).sort([("date", -1), ("start_time", -1)]):
            if montag <= e["date"] <= sonntag:
                woche += int(e.get("net_minutes") or 0)
            if monat_von <= e["date"] <= monat_bis:
                monat += int(e.get("net_minutes") or 0)
            if len(letzte) < 5:
                letzte.append(e)
        s = await db().stempel.find_one({"firma_id": f, "user_id": user["id"]}, {"_id": 0})
        antraege = await db().absences.count_documents({"firma_id": f, "user_id": user["id"], "status": "beantragt"})
        sichtbar = 0
        async for p in db().projects.find({"firma_id": f, "archived": False}, {"_id": 0, "employee_ids": 1, "leiter_ids": 1}):
            if projekt_sichtbar(user, p):
                sichtbar += 1
        konto = await kontoverlauf(firma, user, heute_d.year, heute_d.month) if user.get("weekly_hours") else None
        urlaub = await urlaubskonto(firma, user, heute_d.year)
        aus.update({"gestempelt": bool(s), "woche_minuten": woche, "monat_minuten": monat, "letzte_eintraege": letzte,
                    "antraege_offen": antraege, "projekte_sichtbar": sichtbar,
                    "saldo_minuten": konto["saldo_minuten"] if konto else None, "resturlaub": urlaub["rest"], "urlaub": urlaub})
    return aus
