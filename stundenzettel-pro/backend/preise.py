"""Preisliste (netto je Monat) – einzige Quelle für Oberfläche, Lizenzprüfung und Abrechnungslisten.

Zwei Kundentypen, eine Plattform:
- Auftraggeber (GU, Bauherr): 50,99 € je aktivem GU-Projekt und Monat. Ein Projekt darf beliebig viele Gewerke und Ausschreibungen enthalten.
  Die Abrechnung beginnt mit der Aktivierung (erste Veröffentlichung einer Ausschreibung oder erste Einladung einer Firma), Entwürfe sind kostenlos.
- Ausführende Betriebe: Firmenabo 4,99 € je Firma und Monat plus 3,99 € je weiterem Nutzer (der Inhaber ist enthalten).
- Eingeladene Bieter: kostenlose Projektteilnahme (Ausschreibungen ansehen, Angebote abgeben, Rückfragen, Mitarbeit in Projekten der Auftraggeber).
Die Zahlung selbst läuft bis zur Anbindung eines Zahlungsdienstes über Rechnungen des Anbieters (siehe /api/admin/abos).
"""
from __future__ import annotations

PREISE = {"projekt_gu": 50.99, "firma": 4.99, "nutzer": 3.99}
STUFEN = {"firma": "Firmenabo", "teilnahme": "Kostenlose Projektteilnahme"}
TEXTE = {
    "projekt_gu": "je aktivem GU-Projekt und Monat – beliebig viele Gewerke, Ausschreibungen, Projektleiter und beteiligte Firmen; Entwürfe kostenlos",
    "firma": "je Firma und Monat – Mitarbeiter, Stempeluhr, Stundenzettel, Rechnungen, Lohnvorbereitung, eigene Projekte",
    "nutzer": "je weiterem Nutzer und Monat (Inhaber enthalten)",
    "teilnahme": "kostenlos – Ausschreibungen finden, Angebote abgeben, Rückfragen, Mitarbeit in Projekten der Auftraggeber (Aufgaben, Fotos, Zeiten, Berichte)",
}
# Funktionen, die das Firmenabo brauchen (für Hinweistexte und GO-LIVE.md)
FIRMENABO_FUNKTIONEN = ["Mitarbeiter einladen", "eigene Projekte anlegen", "Rechnungen und E-Rechnung", "Lohnvorbereitung/DATEV", "API-Schlüssel und Webhooks"]


def firmenabo_kosten(nutzer_aktiv: int) -> float:
    return round(PREISE["firma"] + PREISE["nutzer"] * max(0, int(nutzer_aktiv or 0) - 1), 2)
