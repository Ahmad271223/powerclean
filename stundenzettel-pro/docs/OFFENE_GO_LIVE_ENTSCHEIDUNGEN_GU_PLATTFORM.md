# Weitere verbindliche Produktentscheidungen und Go-live-Checkliste
Stand: 23.10.2026. Ergänzung zu PRODUKTMODELL_GU_FIRMEN_PROJEKTPREIS.md auf Draft-Branch. **Nur Konzept, keine implementierten Funktionen.**

## A. Firmen und Gäste: Grenzen explizit definieren
1. **Anonymes Profil**: Darf nur freiwillig veröffentlichte Firmendaten sehen; keine privaten E-Mail-Adressen oder Team-/Kundendaten.
2. **Eingeladener Bieter (gratis)**: Ausschreibungsunterlagen, private Fragen, Angebotsentwurf/-abgabe, Quittung, Zu-/Absage, eigenen Vorgangsexport. Keine eigenen Mitarbeiterstempelungen/Rechnungen.
3. **Beauftragter Projektgast (gratis)**: Freigegebene Bauunterlagen/Termine, Projektchat, Aufgaben und erforderliche Rückmeldungen; limitierte Dokumente, keine fremden Bieterangebote; kein vollständiges internes Stundenkonto.
4. **Zahlende Handwerksfirma**: Eigene Projekte, Mitarbeiter, Zeiterfassung, Abwesenheiten, Fotos im vereinbarten Kontingent, eigene Rechnungen, vollständige eigenberechtigte Archive.
5. **GU-Projektleiter**: Nur zugewiesene Projekte, Lose und freigegebene Vorgänge. Seine Sicht auf Preise kann durch GU-Admin eingeschränkt werden.
6. **GU-Firmenadmin**: Projekte, Team, Abo/Rechnung und Rollen; nicht automatisch Personalakten anderer Unternehmen.

Entitlements (Feature-Paket) sind getrennt von Authorization (wer darf welches Objekt sehen). Server prüft beides bei **jeder** API und beim Download.

## B. Verifizierungen
- Firma darf Gewerke/Regionen erst nach Opt-in sichtbar veröffentlichen.
- E-Mail verifizieren, Firmendaten/Stammdaten validieren, bei Bedarf Handelsregister/USt-ID manuell oder über geprüften Dienst validieren; keine falschen amtlichen Prüfsiegel.
- Unternehmensadmin muss Einladungen/Rechte und Freigaben verwalten, entlassene Projektleiter umgehend entfernen können.
- Missbrauchsschutz für Direktanfragen, Massen-E-Mails, Spam und Fake-Ausschreibungen; Sperr-/Melde-/Supportprozess.
- Projektdaten dürfen nicht über Firmennamen, freie URLs oder erratbare IDs zugänglich sein.

## C. Abrechnung 50,99 Euro netto/Monat
- Definition: genau **ein übergeordnetes reales GU-Bauvorhaben** mit eindeutiger Projekt-ID, Standort und Abrechnungseigner; mehrere Lose/Bieter/Ausschreibungen im selben Projekt sind inklusive.
- Kostenloser Entwurf bis expliziter Aktivierung/erster Veröffentlichung mit Kostenbestätigung.
- Projektbezogene Subscription getrennt vom normalen Firmen-Mitarbeiter-Abo.
- Beendigung zum Periodenende, keine rückwirkende Zerstörung der Projektdaten. Details zu anteiligen Abrechnungen und Pausen vor Verkaufsstart festlegen.
- Bei fehlgeschlagener Zahlung: klarer Hinweis, Retry/Dunning und definierte Grace Period. Zugang zu bestehenden Daten/Export nach vertraglicher Regel, keine unkontrollierte Löschung.
- Projektleiter zählt nicht mehrfach, wenn er 10 Projekte verwaltet. Einladung/Bieter-/Gastnutzung ist ohne zusätzliche Bezahlung möglich.
- **Nicht garantiert**: externe Firmen konvertieren zu kostenpflichtigen Abos. Finanzplanung konservativ mit 0 %, 10 %, 25 % Conversion.
- Abomissbrauch verhindern: dieselbe Baustelle nicht mehrfach gratis, aber keine Doppelberechnung für einzelne Bauabschnitte ohne klare Kundeneinwilligung.
- Optional Enterprise Add-ons: SSO, dedizierter Support/SLA, große Medienkontingente, Schnittstellen, zusätzliche Speicher-/Downloadkontingente. Bei 50,99 € keine unbegrenzte Datennutzung versprechen.
- Steuer-/Abrechnungsdetails und AGB von Fachleuten prüfen; Nettopreis oder Bruttopreis vertraglich eindeutig.

## D. Verbindliche fachliche Abläufe
1. Direkte private Subunternehmeranfrage durch normale Firma: kein öffentlicher Ausschreibungsmarkt, keine formale Vergabeoberfläche.
2. GU-Ausschreibung: Entwurf, versionierte Freigabe, Fristen, Auswahl beteiligter Firmen, strukturierte Angebote.
3. Nach Zuschlag: beauftragten Umfang als vertraglichen Snapshot übernehmen; keine rückwirkende Änderung des Siegerangebots.
4. **Nachträge**: Auftragnehmer beantragt Änderung von Leistung/Preis/Termin, GU gibt schriftlich in-App frei oder lehnt begründet ab; jeder Nachtrag versioniert, separat abrechenbar.
5. **Aufgaben und Mängel**: Zuweisung an zuständige Organisation, Fälligkeit, Fotos, Status offen/in Bearbeitung/zur Prüfung/abgenommen; nichts ungeprüft als abgenommen markieren.
6. **Abnahmen**: explizite verantwortliche Person, Zeitpunkt, Leistungsumfang, Signatur-/Belegreferenz, versionierte Unterlagen.
7. **Mail-/Chat-Nachweis**: Append-only Ereignisse, Outbox, Empfänger, Provider-Status, Nachrichtenversion. "Gesendet" nicht mit "zugestellt" oder rechtssicherem Zugang gleichsetzen.
8. **GU- und Nachunternehmer-Archiv**: Daten nach Berechtigung; GU-Gesamtakte und einzelne Auftragnehmerakte haben unterschiedliche Inhalte; kein fremdes Angebot/Personalblatt.
9. **Exit/Offboarding**: Firmenwechsel, Entzug eines Projektleiters, Ausstieg eines GU, Kündigung, Streitfall und Projektabschluss dürfen keine gesetzlichen/verbindlichen Nachweise löschen.

## E. Architekturänderungen
- Identity + Membership per Organisation und Projekt; Migration des aktuellen user.firma_id ohne Datenverlust.
- Product tiers (regular/verified_GU), Entitlements, serverseitige Capability-Checks.
- GU project umbrella plus subcontractor workspaces; bestehende normale Einzelprojekte bleiben bestehen.
- Firmenverzeichnis und Suchfilter (Gewerke/Region), Einwilligung und Kontaktanfragen.
- Monetarisierung: payment_provider_customer/subscription IDs, gu_project_subscriptions, seat_subscriptions, billing_event_ledger, signierte/idempotente Webhooks.
- Tender, offer revision, award, contract snapshot, change request, task/defect, acceptance, messages/outbox.
- Storage und Dokument-ACL, Background-Worker für Bilder/ZIP/E-Mail, Archiv-/Retention-Service.

## F. Vor Pilotstart: wichtigste Blocker im Code
- backend/routes/zeiten_routes.py: Beim Stempelende vorzeitig gelöscht — atomare Finalisierung.
- frontend/src/pages/StempeluhrPage.jsx: Offline-Queue verwirft Einträge bei nicht-0 HTTP-Status — dauerhafte Failed/Retry-Queue und Idempotenz.
- backend/routes/projekte.py: Kaskadenlöschung aktiver Zeit-/Belegdaten — Soft-Delete + Sperren.
- backend/routes/auth_routes.py: Registrierung erzeugt exklusiv eine Firma, Nutzer ist an eine Firma gebunden; später Memberships.
- backend/routes/firma.py: Lizenz durch Betreiber manuell; echte Zahlungsintegration und Projektabos fehlen.
- backend/db.py: Indexerstellung schlägt nur Log-Warnung aus; kritische Unique-Indizes als Startbedingung.
- Frontend App.jsx/Layout.jsx: nur isBuero-Branch, neue GU-/Gast-/Firmen-UX benötigt.
- Versicherte Dateien/Signaturen/Rechnungen: unveränderliche Snapshots statt überschriebener Quelle.
Nur statischer Code-Review; keine Laufzeit-/Lasttest-Ergebnisse.

## G. Testfälle vor Release
- User darf als normaler Firmeninhaber keine Ausschreibung veröffentlichen (403), aber private Angebotsanfrage senden.
- Eingeladener Bieter ohne Abo kann annehmen, fragen, Angebot einreichen; ohne fremde Angebotsdaten.
- Firma A und B auf demselben GU-Projekt: kein Cross-Org-Datenleck in Chat, PDFs, Bildern, ZIP oder Kosten.
- GU-Admin weist Projektleiter A und B unterschiedliche Projekte zu, entzieht Rechte, alle Sitzungen reagieren.
- Ein Mitarbeiter auf fünf Projekten nur einmal als Sitz bei seiner Firma berechnet.
- Ein aktives GU-Projekt mit 10 Ausschreibungen nur einmal 50,99 € pro Periode; mehrfacher Aktivierungs-Webhook erzeugt kein zweites Abo.
- 3 Konversionsfälle (0, 10, 25 %) monetär separat prüfen, Conversion nie garantieren.
- Zahlung fällt aus, vorhandene Dokumente/Archive bleiben gemäß Vertrags- und Aufbewahrungsregeln verfügbar.
- Nachtrag mit Preisänderung erst nach Zustimmung wirksam, ursprüngliche Vertragsversion erhalten.
- Mehrere gleichzeitige Uploads: 20 Fotos pro Mitarbeiter je Arbeitstag atomar; Worker-Fehler ohne Datenverlust.
- 5.000 Testfirmen, 100 aktive GU-Projekte, 50.000 Mitarbeiterkonten simulieren/realistische Verteilung; Messwerte P95/P99, Kosten und Zeit bis ZIP-Fertigstellung.
- Backup/Restore inklusive Chat, Vergabe-, Foto-, Vertrags- und Rechnungsdaten.

## H. UX-Entscheidung
Startseite GU: Aufgaben, offene Antworten, Projekte, Kosten, Vergaben; Aktionsknopf "Projekt anlegen".
Startseite normale Firma: Heute, Aufträge, Mitarbeiter, Rechnungen, Subunternehmen finden.
Startseite Mitarbeiter: Start/Pause/Stop, Tätigkeit, Fotos, Nachrichten.
Menüs auf Web und Mobile nach Capability, aber Account und Daten identisch; gemeinsame Codebasis erlaubt Rolle-spezifische Darstellungen.
