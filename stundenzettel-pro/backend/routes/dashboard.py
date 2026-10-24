"""Startseite: Zahlen des Tages und des Monats, Hinweise (ArbZG, Budgets, vergessene Stempelungen, Abschluss), je nach Rolle."""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends

from auth import aktueller_nutzer, firma_laden, hat_recht, hat_rolle, plan_status
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
        if not hat_recht(user, "personal"):   # Büro ohne Personalrecht: keine Namen und Stempelungen einzelner Personen
            lange, abwesend = [], []
        vormonat = (heute_d.replace(day=1) - timedelta(days=1))
        vormonat_zu = await db().abschluesse.find_one({"firma_id": f, "year": vormonat.year, "month": vormonat.month}) is not None
        aus.update({
            "heute_eintraege": tage_heute, "gestempelt": gestempelt, "mitarbeiter_aktiv": mitarbeiter, "projekte_aktiv": len(aktiv),
            "monat": {"minuten": minuten_monat, "umsatz_netto": round(umsatz, 2)},
            "antraege_offen": offen_antraege, "rechnungen_offen": {"anzahl": rech_offen, "summe": round(rech_summe, 2)},
            "angebote_offen": await _angebote_offen(f) if hat_recht(user, "angebote") else None,
            "kostenabweichungen": await _kostenabweichungen(firma) if hat_recht(user, "kalkulation") else None,
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


async def _kostenabweichungen(firma: dict) -> dict:
    """Projekte mit Auftragswert, deren Ist-Kosten den Plan um mehr als 10 % übersteigen oder deren Deckungsbeitrag negativ ist."""
    import material as mat
    warnungen, gesamt = [], 0
    async for p in db().projects.find({"firma_id": firma["id"], "archived": {"$ne": True}}, {"_id": 0}):
        if not (p.get("auftrag") or float(p.get("pauschale_netto") or 0)):
            continue
        gesamt += 1
        try:
            n = await mat.nachkalkulation(firma, p)
        except Exception:  # noqa: BLE001 – die Startseite darf an einer Nachkalkulation nicht scheitern
            continue
        db_akt = n["deckungsbeitrag"]["aktuell"]
        if (n["abweichung"] is not None and n["plan"]["gesamt"] and n["abweichung"] > 0.1 * n["plan"]["gesamt"]) or (db_akt is not None and db_akt < 0):
            warnungen.append({"project_id": p["id"], "name": p["name"], "abweichung": n["abweichung"], "deckungsbeitrag": db_akt})
    return {"anzahl": len(warnungen), "projekte": gesamt, "liste": warnungen[:5]}


async def _angebote_offen(firma_id: str) -> dict:
    """Entwürfe und gesendete Kundenangebote: Anzahl, Netto, davon in den nächsten 7 Tagen ablaufend; neue Anfragen."""
    from angebote import abgelaufen
    heute = lokal_jetzt().date()
    bald = (heute + timedelta(days=7)).isoformat()
    n, summe, ablaufend, anfragen = 0, 0.0, 0, 0
    async for a in db().kundenangebote.find({"firma_id": firma_id, "status": {"$in": ["anfrage", "entwurf", "gesendet"]}}, {"_id": 0, "status": 1, "gueltig_bis": 1, "summen.netto": 1}):
        if a["status"] == "anfrage":
            anfragen += 1
            continue
        if abgelaufen(a, heute.isoformat()):
            continue
        n += 1
        summe += float((a.get("summen") or {}).get("netto") or 0)
        if a["status"] == "gesendet" and (a.get("gueltig_bis") or "") <= bald:
            ablaufend += 1
    return {"anzahl": n, "summe": round(summe, 2), "ablaufend": ablaufend, "anfragen": anfragen}


@router.get("/aufgaben")
async def aufgaben(user: dict = Depends(aktueller_nutzer)):
    """Offene Punkte für die Startseite – was jetzt eine Entscheidung oder Handlung braucht, je Rolle, mit Link und Dringlichkeit (1 = zuerst)."""
    from datetime import datetime
    from auth import jetzt_iso
    from plattform import OFFEN, zuteilungs_filter
    f = user["firma_id"]
    heute_d = lokal_jetzt().date()
    heute = heute_d.isoformat()
    punkte: list[dict] = []

    def punkt(art: str, text: str, anzahl: int, link: str, prio: int = 2) -> None:
        if anzahl:
            punkte.append({"art": art, "text": text, "anzahl": int(anzahl), "link": link, "prio": prio})

    if hat_rolle(user, "buero"):
        firma = await firma_laden(f)
        art = firma.get("art") or "betrieb"
        punkt("antraege", "Abwesenheitsanträge entscheiden", await db().absences.count_documents({"firma_id": f, "status": "beantragt"}), "/abwesenheiten", 2)
        lange = 0
        async for s in db().stempel.find({"firma_id": f}, {"_id": 0, "start_at": 1}):
            try:
                start = datetime.fromisoformat(s["start_at"])
                jetzt_l = lokal_jetzt() if start.tzinfo else lokal_jetzt().replace(tzinfo=None)
                if (jetzt_l - start).total_seconds() >= 10 * 3600:
                    lange += 1
            except (ValueError, TypeError):
                continue
        punkt("stempelungen", "Stempelungen über 10 Stunden beenden", lange, "/stempeluhr", 1)
        punkt("pruefen", "Zeiteinträge mit Prüfhinweis klären", await db().entries.count_documents({"firma_id": f, "pruefen": True, "date": {"$gte": (heute_d - timedelta(days=60)).isoformat()}}), "/auswertung", 2)
        if art != "auftraggeber":
            vormonat = heute_d.replace(day=1) - timedelta(days=1)
            zu = await db().abschluesse.find_one({"firma_id": f, "year": vormonat.year, "month": vormonat.month})
            hat_zeiten = await db().entries.count_documents({"firma_id": f, "date": {"$gte": vormonat.replace(day=1).isoformat(), "$lte": vormonat.isoformat()}}) > 0
            punkt("abschluss", f"Monatsabschluss {vormonat.month:02d}/{vormonat.year} fehlt", 1 if (hat_zeiten and not zu) else 0, "/exporte", 3)
        # Partnerseite: Einladungen, Ausschreibungen, Aufträge, Nachträge, Abnahmen
        punkt("projekt_einladungen", "Projekteinladungen beantworten", await db().beteiligungen.count_documents({"firma_id": f, "status": "eingeladen"}), "/zusammenarbeit", 1)
        offen_einladungen = 0
        async for e in db().ausschreibung_einladungen.find({"firma_id": f, "status": {"$in": ["eingeladen", "angesehen"]}}, {"_id": 0, "ausschreibung_id": 1}):
            a = await db().ausschreibungen.find_one({"id": e["ausschreibung_id"]}, {"_id": 0, "status": 1, "angebotsfrist": 1})
            if a and a.get("status") == "veroeffentlicht" and (a.get("angebotsfrist") or heute) >= heute:
                offen_einladungen += 1
        punkt("ausschreibung_einladungen", "Einladungen zu Ausschreibungen: Angebot abgeben", offen_einladungen, "/ausschreibungen", 2)
        punkt("vergaben_annehmen", "Erhaltene Aufträge verbindlich annehmen", await db().vergaben.count_documents({"firma_id": f, "status": "mitgeteilt"}), "/ausschreibungen", 1)
        punkt("nachtraege_angefragt", "Angefragte Nachträge bepreisen und einreichen", await db().nachtraege.count_documents({"firma_id": f, "status": "angefragt"}), "/zusammenarbeit", 2)
        punkt("abnahmen_bestaetigen", "Abnahmeprotokolle bestätigen oder widersprechen", await db().abnahmen.count_documents({"firma_id": f, "status": "erstellt"}), "/zusammenarbeit", 1)
        if hat_recht(user, "plantafel"):
            punkt("zeiten_freigeben", "Arbeitszeiten prüfen und freigeben (Plantafel)",
                  await db().einsaetze.count_documents({"firma_id": f, "status": "geplant", "freigabe": None, "date": {"$gte": (heute_d - timedelta(days=30)).isoformat(), "$lt": heute}}), "/plantafel?abgleich=1", 2)
            punkt("heute_geplant", "Heute eingeplante Einsätze", await db().einsaetze.count_documents({"firma_id": f, "status": "geplant", "date": heute}), "/plantafel", 3)
        if hat_recht(user, "angebote"):
            punkt("anfragen", "Neue Kundenanfragen in Angebote umsetzen", await db().kundenangebote.count_documents({"firma_id": f, "status": "anfrage"}), "/angebote?status=anfrage", 2)
            punkt("angebote_nachfassen", "Gesendete Angebote laufen in 7 Tagen ab – nachfassen",
                  await db().kundenangebote.count_documents({"firma_id": f, "status": "gesendet", "gueltig_bis": {"$gte": heute, "$lte": (heute_d + timedelta(days=7)).isoformat()}}), "/angebote?status=gesendet", 2)
            punkt("auftraege_anlegen", "Angenommene Angebote als Auftrag anlegen", await db().kundenangebote.count_documents({"firma_id": f, "status": "angenommen", "auftrag": None}), "/angebote?status=angenommen", 1)
        if hat_recht(user, "rechnungen"):
            punkt("eingangsrechnungen_pruefen", "Eingangsrechnungen prüfen", await db().eingangsrechnungen.count_documents({"firma_id": f, "status": "erfasst"}), "/eingangsrechnungen?status=erfasst", 2)
            punkt("eingangsrechnungen_faellig", "Überfällige Eingangsrechnungen bezahlen", await db().eingangsrechnungen.count_documents({"firma_id": f, "status": {"$in": ["erfasst", "geprueft"]}, "faellig_am": {"$lt": heute}}), "/eingangsrechnungen", 1)
        if hat_recht(user, "kalkulation"):
            punkt("material_pruefen", "Materialbuchungen prüfen", await db().materialverbrauch.count_documents({"firma_id": f, "status": "erfasst"}), "/projekte", 3)
        punkt("maengel_firma", "Überfällige Mängel beheben", await db().maengel.count_documents({"firma_id": f, "status": {"$nin": ["abgenommen"]}, "frist": {"$lt": heute}}), "/zusammenarbeit", 2)
        # Eigentümerseite: Vergaben, Angebote, Rückfragen, Fristen, Nachträge, Abnahmen, Berichte
        punkt("vergaben_freigeben", "Vergabevorschläge freigeben", await db().vergaben.count_documents({"owner_firma_id": f, "status": "vorgeschlagen"}), "/ausschreibungen", 1)
        punkt("vergaben_mitteilen", "Freigegebene Vergaben den Firmen mitteilen", await db().vergaben.count_documents({"owner_firma_id": f, "status": "freigegeben"}), "/ausschreibungen", 2)
        laufend = [a async for a in db().ausschreibungen.find({"firma_id": f, "status": {"$in": ["veroeffentlicht", "in_vergabe"]}}, {"_id": 0, "id": 1, "angebotsfrist": 1, "titel": 1})]
        ids = [a["id"] for a in laufend]
        if ids:
            punkt("angebote_neu", "Eingereichte Angebote prüfen", await db().angebote.count_documents({"ausschreibung_id": {"$in": ids}, "status": {"$in": ["eingereicht", "ueberarbeitet"]}}), "/ausschreibungen", 2)
            fragen = 0
            async for fr in db().ausschreibung_fragen.find({"ausschreibung_id": {"$in": ids}}, {"_id": 0, "antwort": 1}):
                if not fr.get("antwort"):
                    fragen += 1
            punkt("fragen_offen", "Rückfragen von Bietern beantworten", fragen, "/ausschreibungen", 2)
            bald = (heute_d + timedelta(days=3)).isoformat()
            punkt("fristen", "Angebotsfristen enden in den nächsten 3 Tagen", sum(1 for a in laufend if a.get("angebotsfrist") and heute <= a["angebotsfrist"] <= bald), "/ausschreibungen", 3)
        punkt("nachtraege_eingereicht", "Nachträge freigeben oder ablehnen", await db().nachtraege.count_documents({"owner_firma_id": f, "status": "eingereicht"}), "/projekte", 1)
        punkt("abnahmen_angefordert", "Angeforderte Abnahmen durchführen", await db().abnahmen.count_documents({"owner_firma_id": f, "status": "angefordert"}), "/projekte", 2)
        punkt("abnahmen_widersprochen", "Widersprochene Abnahmen klären", await db().abnahmen.count_documents({"owner_firma_id": f, "status": "widersprochen"}), "/projekte", 1)
        eigene_ids = [p["id"] async for p in db().projects.find({"firma_id": f, "archived": False, "verknuepft": None}, {"_id": 0, "id": 1})]
        if eigene_ids:
            punkt("berichte_freigeben", "Bautagesberichte freigeben", await db().tagesberichte.count_documents({"project_id": {"$in": eigene_ids}, "status": "eingereicht"}), "/projekte", 3)
            punkt("maengel_ueberfaellig", "Überfällige Mängel in eigenen Projekten", await db().maengel.count_documents({"project_id": {"$in": eigene_ids}, "status": {"$nin": ["abgenommen"]}, "frist": {"$lt": heute}}), "/projekte", 2)
    else:
        punkt("aufgaben_heute", "Aufgaben für heute", await db().aufgaben.count_documents({"firma_id": f, "datum": heute, "status": {"$in": list(OFFEN)}, "$or": zuteilungs_filter(user["id"])}), "/aufgaben", 1)
        punkt("antraege_eigene", "Offene Abwesenheitsanträge", await db().absences.count_documents({"firma_id": f, "user_id": user["id"], "status": "beantragt"}), "/abwesenheiten", 3)
        punkt("pruefen_eigene", "Zeiteinträge mit Prüfhinweis", await db().entries.count_documents({"firma_id": f, "user_id": user["id"], "pruefen": True}), "/meine-zeiten", 2)
    punkte.sort(key=lambda x: (x["prio"], x["text"]))
    return {"punkte": punkte, "stand": jetzt_iso()}
