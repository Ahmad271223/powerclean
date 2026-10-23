# Stundenzettel Pro — Gesamtaudit der Oberflächen, Rollen, API und Vereinfachungen

Stand 23.10.2026, statischer Review des GitHub-Codes auf main f487941. **Keine Browser-/Lasttests durchgeführt.** Die Hinweise unterscheiden bestätigte Codepfade von nicht verifizierten Risiken.

## 1. Navigation nach Nutzer statt nach technischen Modulen
Chef kleiner Handwerksfirma: Start (heute, offene Antworten, Geld) / Aufträge & Ausschreibungen / Projekte / Nachrichten / Rechnungen; weitere Funktionen unter Mehr.
GU-Projektleiter: Meine Bauvorhaben / Ausschreibungen / Projektkommunikation / Entscheidungen / Mehr.
Mitarbeiter: Heute (Stempeluhr) / Meine Zeiten / Meine Projekte / Nachrichten / Profil.
Büro: Dashboard / Personal / Projekte / Rechnungen / Mehr.
Vorarbeiter: Meine Baustellen / Mitarbeiterzeiten im freigegebenen Projekt / Aufgaben & Fotos / Nachrichten.
Rollen sind für Multi-Company-Kontexte keine globale numerische Hierarchie; dieselbe Person kann in Firma A Geschäftsführer und in Firma B Projektmitglied sein.
Derzeit Layout.jsx verwendet NAV_BUERO/NAV_MITARBEITER, jeweils erste vier als feste mobile Tabs. Bei Ausbau auf GU + Bieter muss kontext-/capability-basiert sortiert werden.

## 2. Seite für Seite: aktueller Code und Verbesserungen
| Seite/Datei | Heute | Ziel / Vereinfachung | Priorität |
|---|---|---|---|
| App.jsx + LoginPage | HashRouter, Anmeldung, Einladung | Onboarding als «Firma erstellen» oder «Einladung annehmen»; aktive Organisation explizit, bei GU mit Teamwechsel | Hoch |
| DashboardPage | 8 KPIs + Abwesenheit, Budgets, Abschluss | Rolle-spezifisches Cockpit mit max. 3-5 Hauptkennzahlen, «Was muss ich heute tun?»; z. B. 2 Nachrichten, 3 Angebote zu prüfen | Hoch |
| StempeluhrPage | Serverstempel + lokaler Tick/Offline-Queue | Reale UTC-Timestamps, idempotente Stempelaktionen, belastbares Offline-Outbox; kein Reset nach Seitenwechsel; einfacher Start/Pause/Ende | P0 |
| MeineZeitenPage | Eigene Zeitliste | «Heute», «Diese Woche», «Nachtragen»; klare Warnungen statt technischer Felder; bearbeitbare Einträge nur wenn zulässig | Mittel |
| ProjektePage | Firmenprojekte und Archiv | Einfache Filter Aktiv / Abgeschlossen, «Von uns» vs «Wir arbeiten mit», Suchfunktion, Zugehörigkeit zu Aufträgen | Hoch |
| ProjektPage | Monolith ca. 36 kB, Kalender/Akte/Checklisten/PDF | Komponenten/Unterseiten für Übersicht, Tageserfassung, Auftrag, Kommunikation, Dokumente, Archiv; mobiles Kalenderlayout ohne breite Tabelle | Hoch |
| EntryDialog + TagFotos | Eintrag + Foto getrennt | Zusammenführung zur Tageserfassung mit Tätigkeit, Start, Ende, Pause, Fotos, einem primären Speichern-Button; häufige Tätigkeiten | Hoch |
| RechnungenPage | Viele technische Aktionen PDF, Monatspaket, E-Rechnung, Status, Extras | Einfache Rechnungsliste, Entwurf → prüfen → ausstellen → bezahlt; Exporte in «Herunterladen» bündeln; Rechnung nicht bei Vorschau anlegen | Hoch |
| ExportePage | Lohn, DATEV, MiLoG, Monatsabschluss nebeneinander | Lohn & Gehalt / Projektarchiv / Monatsabschluss / Technische Formate logisch trennen, Detailoptionen einklappen | Mittel |
| MitarbeiterPage | Mitarbeiterverwaltung, Rollen | Mitarbeiter + Einladungsstatus + zugeordnete Projekte; Chef sieht Team, Projektleiter nur freigegebenes Team | Hoch |
| MitarbeiterDetailPage | Akten, Lohndaten, Konto | Rechtlich sensible Personalakte strikt privat; kein Zugriff des GU auf Subunternehmer-Lohndaten | P0 |
| KundenPage | Kundenstamm | Firmenverzeichnis für B2B-Kontakte **separat** vom privaten Kundenstamm; keine automatische Veröffentlichung der Kunden | Hoch |
| AbwesenheitenPage | Urlaub/Krankheit, Freigaben | Für Mitarbeiter 1 Antrag-Flow; für Büro Filter «offen», Teamkalender und eindeutige Entscheidungen | Mittel |
| AuswertungPage | Gruppen nach Kunde/Projekt/Mitarbeiter/Leistung | Einfache voreingestellte Berichte; Details nach Rolle, keine Preis-/Kostenkennzahlen für Arbeitskräfte | Mittel |
| FirmaPage | Firmendaten, Leistungen, Lizenz plus API/Webhooks/Import für Inhaber | Gruppen «Firmendaten», «Team», «Abrechnung», «Erweitert», «Datenschutz & Daten»; API/Webhook hinter Erweitert | Mittel |
| ProtokollPage | Sicherheitsprotokoll | Nur Adminbereich; sinnvoll lesbare Aktionen und sensible Daten redigieren, nicht in normalen Chat mischen | Hoch |
| ProfilPage | Eigenes Profil, Zeiten, Konto | Ich / Einstellungen / Benachrichtigungen; E-Mail-Präferenzen und aktive Firma | Mittel |
| PDFs pdf.js/pdfbasis.py | gemischte Monatsmappe und Rechnungs-/Stundenzettel-Generierung | drei Vorlagen: Leistungsnachweis, Rechnung, vollständige Projektakte; klare Versionsstände und optionale Fotos | Hoch |
| AusschreibungenPage NEU | nicht vorhanden | Entdecken/Eingeladen/Meine Angebote/Von uns, klare Frist/Status/Hauptaktion | Hoch |
| TenderDetailPage NEU | nicht vorhanden | Gewerk, LV, Unterlagen, private Fragen, Einreichen; GU-Vergabeprüfung getrennt | Hoch |
| MessagesPage NEU | nicht vorhanden | Posteingang mit Vorgangsfilter, Kontext, zulässiger Leserschaft; Chat nicht zum Rechnungsdokument mutieren | Hoch |
| ProjektarchivPage NEU | nicht vorhanden | Umfang auswählen, Status, Vorschau, ZIP-Download, Bestätigung, Archivfrist; nicht automatisch löschen | Hoch |

## 3. Codebasierte Defekte/Risiken vor neuer Funktion beheben
1. frontend/src/pages/StempeluhrPage.jsx: Online-Sekunden aus gerundeten Serverminuten + fetchedAt; springender Countdown möglich. Offline-Synchronisation entfernt HTTP-Fehlerstatus != 0 aus Queue statt dauerhafter Aufbewahrung.
2. backend/routes/zeiten_routes.py: _stempel_beenden löscht laufenden Datensatz VOR Abschlussvalidierung/Insert → möglicher Verlust.
3. backend/routes/projekte.py: Projektlöschung löscht auch laufende Stempelungen und Projektdateien, bevor vollständige Archiv-/Retention-Freigabe vorliegt.
4. backend/routes/projekte.py: gleiche Wochenunterschrift wird durch delete_many/insert_one ersetzt; unveränderliche Historie fehlt.
5. frontend/src/pages/ProjektPage.jsx: monthDoc benutzt rechnungHolen() = POST /api/rechnungen/anlegen. PDF-Aufruf kann Rechnung erzeugen.
6. backend/routes/rechnungen.py: offener Rechnungsdatensatz wird beim erneuten /anlegen neu berechnet; nach Versand Status/Revision und dokumentiertes Festschreiben erforderlich.
7. backend/routes/abschluss.py: offene Stempelungen nur gezählt, Abschluss trotzdem möglich.
8. backend/routes/projekte.py: nicht leitender Mitarbeiter kann Checklisten-Punkte durch Weglassen des gesendeten Arrays aus dem Bestand entfernen.
9. backend/config.py: JWT_SECRET hat bekannten Entwicklungsfallback, Produktionsstart darf ihn nicht zulassen.
10. backend/protokoll.py: Ereignisdetails werden gekürzt, nicht sensitivitätsbewusst geschwärzt; werden teils an Webhooks weitergereicht.
11. backend/webhooks.py: Hintergrund-Tasks nicht dauerhaft; keine robuste E-Mail-Ereignisverarbeitung ableiten.
12. backend/routes/firma.py: Webhook-Zielauswahl ohne ausreichende gegen SSRF belegte Netzbeschränkung.
13. backend/routes/exporte.py: Sicherungs-JSON enthält nicht sämtliche Collections und keine Dateiinhalte; nicht als vollständiges Restore behaupten.
14. backend/routes/auswertung.py: Limit 200000 Einträge kann lange Zeiträume still begrenzen; Endnutzer muss vollständige/paginierte Daten erhalten.
15. backend/db.py: Unique-Indexfehler führen nicht zum Fail-Fast; bei Ausschreibungsangeboten/Rechnungsnummern kritisch.
16. backend/dateien.py: Upload prüft content_type, aber nicht hinreichend Datei-Signatur und Schadinhalt.
17. backend/routes/leistungen.py: Leistungsnamen werden in historischen Einträgen rückwirkend geändert.
18. backend/routes/api_v1.py: API-Schlüssel haben breite Leserechte; Scopes/Rotation/Ablauf vor größerem B2B-Portal.
19. frontend/src/pages/RechnungenPage.jsx: generische Materialvorschläge aus Reinigung; je Gewerk/Branche eigene Vorschläge, nicht hartkodiert.
20. frontend/src/pages/ProjektPage.jsx: breite Kalenderansicht; mobile Tagesliste statt horizontales Scrollen.
Nur bestätigte Codebefunde als solche behandeln; tatsächliche Ausfallraten verlangen reproduzierbare Tests.

## 4. Was der Handwerkschef in einem echten Beispiel tut
1. Einladung per Mail: «Elektroinstallation – Projekt Hannover, Angebot bis 03.11.»
2. Klick öffnet Ausschreibung in der App; wenn nicht angemeldet: sicherer Login/Registrierung mit zurückgehaltenem Einladungsziel.
3. «Unterlagen ansehen» und «Frage stellen» sind direkt sichtbar; Chat zeigt, dass Antworten privat oder an alle gehen.
4. «Angebot erstellen» besitzt Entwurfsspeicherung, Summenprüfung und verbindliche Einreichung mit Empfangsbeleg.
5. «Meine Angebote» zeigt eingereicht, Rückfrage offen, Vergeben/Nicht berücksichtigt; kein unnötiger Statusdschungel.
6. Nach Zuschlag: «Neuer Auftrag – Jetzt Projekt öffnen»; Angebot und Auftrag bereits hinterlegt.
7. Mitarbeiter erhalten nur Einsatz-Projekt, Stempeluhr, Tätigkeit, Fotos. Keine Einkaufskonditionen.
8. Nach Auftrag: Chef sieht Nachrichten, Abnahmen, Rechnungsstatus.
9. Projektabschluss: «Projektakte erstellen» bündelt genau die vertragsrelevanten Daten; danach herunterladen, Prüfsumme und separat Empfang bestätigen.

## 5. Testreihenfolge / Abnahme
A. Sicherheitsmatrix: GU-Inhaber, GU-Projektleiter1/2, Chef Firmen A/B, Büro Firma A, Mitarbeiter Firma A, deaktivierter User. Für jede API und ZIP Datei Zugriff erlauben/verbieten prüfen.
B. Fachfluss: Ausschreibung private/public-private, Einladung, Änderung Unterlagen, private/allgemeine Frage, Angebote 2 Bieter, Frist, Zuschlag, Ablehnung, Vertragsannahme, Projekt, Fotos, Zeiten, Rechnungen, vollständiges ZIP.
C. Störungen: Doppel-Klick, 401, 409, 422, Netzverlust, Mailprovider Down, Worker Down, Retry, 2 Tabs, 2 Geräte, parallele Ausschreibungseinreichungen, Offline-Zeiten, Backup-/Restore.
D. Last: 5.000 Unternehmen als Testdaten, mehrere Projektleiter pro GU, 20 Fotos/Mitarbeiter/Tag als Worst Case, mehr als 10 Mio. Fotoobjekte simulieren/gesondert messen; Metriken P50/P95/P99, RAM, I/O, Queue, MongoDB-Slow-Query.
E. Compliance: Datenschutzerklärung/AVV, Lösch- und Aufbewahrungsregeln, öffentliche Vergabe separat.

## 6. Lieferstrategie
Erst P0-Fixes und Migration → Organisationsmodell → private Ausschreibung/MVP → Angebote/Einreichung → Chat+E-Mail-Outbox → Zuschlag+Projektverknüpfung → Projekt-ZIP mit Vergabeunterlagen → kontrollierte Archivierung → Last-/Sicherheitstests. Jedes Modul hinter Feature Flag bis Abnahme.
