# Stundenzettel Pro – kompletter Produkt-Workflow, Informationsarchitektur und Screen-Audit
Stand: 23.10.2026. Quelle: statischer Review aller React-Seiten im Ordner frontend/src/pages und zentraler Komponenten, Layout, Auth, API-Routen; main f487941. **Entwurf, kein implementiertes Redesign und keine echten Browser-/Lasttests.**

## 0. Verbindliche Leitplanken
- EIN persönlicher Account pro Mensch, EIN Firmenkonto pro Organisation, Projektleiter haben individuelle Logins und mehrere explizite Projektzuordnungen; keine eigenen Logins für jeden Projektleiter je Baustelle.
- EINE technische Web-/iOS-/Android-Plattform. Gleiche Daten, Rechte und Abonnements; optimierte Anzeige nach Nutzungskontext. Kein identischer komplexer Desktop-Screen auf dem Smartphone.
- Normale Firmen: eigene Projekte, Mitarbeiter, Zeiten, Angebote und Rechnungen, freigegebene Subunternehmenssuche/Anfragen, Bieter-Teilnahme. **Keine formale GU-Ausschreibung veröffentlichen**.
- Verifizierte GU: freigegebene Bauprojekte, Ausschreibungen, Bieterlisten, Angebote, Zuschläge, Vertrags-, Bau- und Abnahmeverwaltung.
- Preisvorschlag GU: 50,99 EUR netto/aktivem übergeordnetem Bauprojekt/Monat, einmal pro Baustelle und nicht je Gewerk, Bieter oder PM. Einladung und Basis-Bieter-/Projektgastzugriff kostenlos. Volles Firmenabo gemäß Produktmodell separat, keine doppelte Sitzabrechnung.
- Mitarbeiter: Stempeluhr, eigene Zeit, Fotos, eigene Einsätze, erlaubte Aufgaben und Nachrichten. Keine GU-Vergabe, fremden Kosten, interne Budgets, Personalakten oder Rechnungen.
- Jedes Datenobjekt hat Besitzerorganisation, ggf. Projekt/Los, Sichtbarkeit und differenzierte Berechtigungen. Exporte/ZIP nur für tatsächlich erlaubten Umfang.
- **Bestehende kritische Zeitverlust-/Datenlöschpfade zuerst reparieren**, kein Rollout der neuen Module davor.

## 1. Informationsarchitektur: Desktop
### Normaler Handwerksbetrieb – Hauptnavigation
1. Übersicht
2. Aufträge & Angebote (erhaltene GU-Einladungen, eigene direkte Anfragen, Angebote)
3. Meine Projekte (eigene Einsätze und beauftragte GU-Lose)
4. Nachrichten
5. Rechnungen
6. Team & Zeiten (Mitarbeiter, Zeiten, Urlaub, Lohn- und Stundenkonten)
7. Subunternehmen finden (separate opt-in-Firmensuche)
8. Berichte & Exporte (nur Büro/Inhaber)
9. Firma & Abo / Erweitert (nur Berechtigte)
Der Firmenchef braucht keine Menüeinträge «Ausschreibung veröffentlichen», «Bietervergleich» und «GU-Projektabo».

### GU/Projektleiter – Hauptnavigation
1. Übersicht (persönliche Entscheidungen, Fristen, offene Nachrichten)
2. Bauprojekte
3. Ausschreibungen (erstellen, Lose, Unterlagen, Einladungen)
4. Angebote prüfen (Fristen, erlaubte Öffnung, Vergleich, Zuschlag)
5. Nachrichten
6. Aufgaben, Mängel & Abnahmen
7. Teams & Projektleiter (nur GU-Admin / projektzuständiger Rollenmanager)
8. Abrechnung / Projektabos (GU-Admin)
9. Archiv & Berichte
GU-Projektleiter sehen nur zugewiesene Projekte und nicht zwingend GU-Finanz-/Adminfunktionen.

### Mitarbeiter – Hauptnavigation
1. Heute / Stempeluhr
2. Meine Einsätze
3. Meine Zeiten
4. Fotos & Aufgaben
5. Nachrichten
6. Abwesenheit
7. Profil
Am Desktop ggf. Profil/Abwesenheit unter «Mehr», mobil maximal vier primäre Tabs und Mehr.

### Kontext-Navigation innerhalb GU-Projekt
Übersicht | Gewerke & Firmen | Ausschreibungen | Bauablauf | Kommunikation | Dokumente | Nachträge & Abnahmen | Rechnungen | Archiv.
Für Auftragnehmer im GU-Projekt stattdessen: Mein Auftrag | Heute/Kalender | Kommunikation | Fotos & Dokumente | Abnahmen | Rechnung | Meine Projektakte.

## 2. Allgemeine Design-/Interaktionsregeln
- Eine **primäre Aktion je Screen** oben rechts am Desktop, fest unten in langen mobilen Formularen; sekundäre Aktionen als Menü.
- Suchfeld nur bei Listen, darunter filterbare Statuschips und Sortierung; keine 7 losen Buttons in Kopfzeilen.
- Startseiten zeigen zuerst «Braucht deine Aktion», dann maximal 4 Kern-KPIs, dann «Zuletzt bearbeitet» und Schnellaktionen. Alle Detailmetriken in Reports.
- Trennung zwischen Task (z. B. Angebot prüfen) und Datensatz (Ausschreibung lesen).
- Kontext sichtbar: Firmenswitcher (nur bei mehreren Mitgliedschaften), Projektname/Breadcrumb, Gewerke/Los, eigene Rolle, Auftragsstatus und Zahlungs-/Archivstatus.
- Detailseiten Desktop: Inhaltskopf, Tabs, Hauptbereich 2/3, rechts Aufgaben/Fristen/Aktivität 1/3. Tablet einspaltig mit optionalem Sidepanel; mobil ausschließlich primäre Tageskarte plus Tabs/sekundäre Menüs.
- Kritische Zustandswechsel bestätigen mit Konsequenzen und ggf. erneuter Authentifizierung: Zuschlag, Vertrag, Rechnungsfreigabe, Projektabschluss, Datenlöschung.
- Keine kostenpflichtige Aktivierung allein durch «Speichern», «Projekt erstellen», Download oder Öffnen einer Seite.
- Status und Benachrichtigungen in sinnvoller Geschäftssprache, nicht Fehlercodes ohne Handlungshinweis.
- Leere Zustände mit nächstem erlaubtem Schritt. Bei offline/401/403/409/422/500 unterscheiden: Retry, Login, Zugriffsgrund, Konflikt, Eingabefehler, Support-/Job-ID.
- Zeit- und Geldwerte lokal DE formatiert; interne UTC-Timestamps und eindeutige Fristen.
- Bearbeitungen an Angebot nach Einreichung, Signaturen, Rechnungen und Zuschlägen als neue Revision / Storno statt stiller Überschreibung.
- Server prüft jedes Entitlement/ACL; ausgeblendeter Button ist keine Security.

## 3. End-to-End-Nutzerreisen
### A. Firmenregistrierung/Onboarding (normal)
Landing → «Als Handwerksbetrieb starten» → E-Mail verifizieren → Firmenstammdaten minimal (Name, Gewerk, Region) → Abo/Teststatus klar → erstes eigenes Projekt ODER GU-Einladung öffnen → 1. Mitarbeiter einladen → Einsatz/Zeiterfassung.
Optionen «Bestehender Firmenaccount» und «Einladung annehmen», nicht für jeden Invite eine neue Firma anlegen.
Später Finanzdaten, Steuersatz, Logo, Lohnregeln unter Einstellungen vervollständigen. Fortschrittsanzeige 3 von 5 statt 20 Pflichtfelder.

### B. GU-Onboarding
Verifizierten GU-Account beantragen/vertraglich freigeben → Unternehmensadmin mit MFA → Rechnungsadresse/Zahlungsmittel → Projektleiter mit individueller Mail einladen → GU-Projektentwurf kostenlos erstellen → Rollen/Projektleiter zuordnen → Preisübersicht «50,99 EUR netto je aktivem Bauprojekt/Monat» → explizit kostenpflichtig aktivieren → Ausschreibung veröffentlichen und Bieter einladen.
Eine Bauprojekt-ID mit vielen Gewerken, nicht pro Gewerk abrechnen. Projektleiter A sieht nur A/B, B nur C. Ein Login bei vielen Projekten.

### C. Ausschreibung / Gebot / Zuschlag
GU: Projekt → Los definieren → Leistungsbeschreibung/LV+Dateiversionen → Frist → Empfänger/Gewerk/Region → Kontrollvorschau → Veröffentlichung → Quittung/Audit.
Bieter: kostenlose Anmeldung/Einladung annehmen → Unterlagen → private Rückfrage; GU kann separate anonymisierte Antwort an alle veröffentlichen → Angebot Entwurf in 4–5 Schritten → Preise/Anlagen prüfen → einreichen → revisionsfeste Quittung per App+E-Mail-Metadaten.
GU: während Angebotsphase keine unzulässige Einsicht → Angebot öffnen/gegenüberstellen → Entscheidung/Freigaben → Zuschlag/Absage mit korrekten Empfängern → Vertragsannahme → automatisch projektbezogene Teilnahme und Auftragnehmer-Arbeitsbereich.
Keine normalen Firmen als Herausgeber von offenen GU-Ausschreibungen; normale Firmen dürfen private direkte Subunternehmer-Anfragen auslösen.

### D. Tagesarbeit Mitarbeiter
App öffnen → «Heute: Projekt A» prominent → Projekt auswählen falls mehrere → Start; sichtbare laufende Uhr (server/Offline-Snapshot) → Pause/Weiter → Tätigkeiten und Fotos (20/Tag falls vereinbart) → Enden → Ergebnisbestätigung + ggf. Offline-Warteschlange.
Anforderung: alle Einträge genau einmal gespeichert, auch bei Tap-Duplikaten, Seitenwechsel, Offline/401/500, Wechsel Geräte.
Nachtragen: Tag öffnen → Start/Ende/Pause → Tätigkeit → Speichern. Foto und Arbeitszeit im gleichen Tageskontext, aber technisch getrennte Assets.

### E. GU-Baukoordination / Nachträge
GU-Projektübersicht → offene Aufgaben/Meilensteine → Firma/Gewerk → Freigaben → Chat/Anlage.
Nachtrag: Auftragnehmer erstellt Änderungsantrag mit Preis, Zeit, Leistungsbeschreibung, versionierten Anlagen → zuständiger GU-Projektleiter prüft → explizit genehmigen/ablehnen → Vertragssnapshot aktualisiert neue Version; alte Version bleibt → Rechnung referenziert genehmigte Nachträge.
Mangel: mit Datum/Fotos/Gewerk/fälligem Termin erfassen → verantwortliche Firma → in Bearbeitung → zur Prüfung → abgenommen oder erneut offen.
Abnahme: benannte berechtigte Person, Umfang, Uhrzeit, Signatur und Dokumentversion; keine stille Bildüberschreibung.

### F. Rechnungen und Monatsabschluss
Büro: Leistungen/Zeiten prüfen → Rechnung ENTWURF → Pflichtfelder/Steuer/Positionen prüfen → ausdrücklich ausstellen → PDF/XRechnung/ZUGFeRD aus unveränderlichem Snapshot erzeugen → senden und Versandstatus → bezahlt markieren → Korrektur nur per Storno/Neubeleg, keine wiederverwendete Nummer.
Monatsabschluss ist separater Payroll-Vorgang, kein Nebeneffekt eines PDF-Downloads; laufende Stempelungen, ausstehende Offline-Buchungen und Warnungen vorher abgleichen.

### G. Projektschluss und ZIP
Projektabschluss-Checkliste (laufende Einsätze, fehlende Zeiten, offene Mängel, Nachträge, Unterschriften, Rechnungen, nicht zugestellte Nachrichten) → Abschlussfreigabe → Berechtigungsspezifische ZIP-Auswahl → asynchroner Archivjob → PDF-Index, Originalangebot, Ausschreibung, Einreichungsquittung, Zuschlag, Kommunikation+E-Mail-Events, Fotos, Zeiten, Abnahmen, Rechnungen, SHA256 → Download + optionale Empfangsbestätigung → separate Aufbewahrungs-/Löschprüfung nach Datenklasse. GU-Gesamtakte ≠ Nachunternehmerakte.

## 4. Dashboard-Spezifikationen
### Handwerkschef (Desktop)
Kopf: «Guten Morgen» + Firmenswitcher falls relevant + [+ Projekt] + Benachrichtigungen.
A. Handlungsblock (höchste Stelle): [2 neue GU-Anfragen] [1 offene Antwort] [3 Zeiten zu prüfen] – nur wenn tatsächlich offen; direkte Links.
B. Vier KPI-Cards: Im Einsatz, Stunden Monat, Rechnungen offen, Aufträge aktiv.
C. Zweispaltig: links laufende Projekte/Status/Fortschritt, rechts nächste Termine und ungelesene Chats.
D. «Neu & Schnell»: Mitarbeiter einladen, Zeit nachtragen, Subunternehmen finden.
Mobile: A zuerst; dann eigene Projekte, nicht acht quadratische KPIs untereinander.

### GU-Projektleiter (Desktop)
Kopf: «Meine Bauprojekte» + [Neues GU-Projekt] nur falls berechtigt.
A. Arbeitseingang: Angebote zur Prüfung, Rückfragen, Freigaben, Fristen in 7 Tagen, offene Mängel. Jede Zeile Firma/Projekt/Aufgabe/Fälligkeit und primäre Aktion.
B. 3-4 Zahlen: Projekte aktiv, Ausschreibungen offen, Entscheidungen offen, unerledigte Aufgaben.
C. Projektliste mit Status/Phase, verantwortlichem PM, nächste Aktion, Fortschritt und möglichem Blocker.
D. Aktuelle Nachrichten nach Projekt; interne Konzernfinanzen nur für Admin.
GU-Admin zusätzlich separater Bereich «Abos»: aktive Projekte × 50,99 €, nächste Abbuchung, Mitarbeiterberechtigungen, Rechnungsdokumente und Zahlungsstörungen.

### Mitarbeiter (mobil)
Kopf: Name, Datum, Internet/Sync-Zustand.
Großes Projektfeld (letztes Projekt, Einsatzort, Wechsel), aktiver Timer + genau eine große Aktion Start oder Pause/Weiter/Ende.
Danach: Tätigkeit, Fotos 0/20 (mit Uploadfortschritt), letzte Buchung und Tagesstunden.
Ganz unten: nächste Einsätze, Nachrichten; keine Buchhaltungszahlen.

### GU-Unternehmensadministrator
Kopf: Organisation, Projekte, Zahlung. To-do: PM-Anfragen, auslaufende Zugriffe, Projekte ohne Verantwortliche, Zahlungsfehler.
KPIs: Aktive GU-Projekte, Kostenperiode, gebuchte Projekte, Firmenbeteiligungen. Eine Seite «Team & Berechtigungen» mit PM-Matrix.
Nur Admin darf Abos kündigen/Änderung autorisieren. Projektleiter nicht allein wegen Projektberechtigung.

## 5. Audit UND Zielzustand aller bestehenden React-Seiten
| Screen / heutige Datei | Gesicherter Istzustand im Code | Zielanordnung | Priorität |
|---|---|---|---|
| LoginPage | Login, Registrierung und Einladung in derselben Datei | 3 Einstiege: Handwerker, GU-Anfrage, Einladung; persönliches Konto + Firmenswitch bei Mehrfachrollen | Hoch |
| DashboardPage | Acht Kennzahlen und verschiedene Schnellaktionen | Handlungsblock → maximal 4 KPIs → Projekte → News; GU/Mitarbeiter eigene Startseiten | Hoch |
| StempeluhrPage | Projektwahl, großer Startkreis, Pause/Stop, offline, letzte Zeiten | Heute → aktives Projekt → Timer → Pause/Stop → Tätigkeit/Fotos; Offline-Outbox sichtbar | P0 |
| MeineZeitenPage | Monatsnavigation, Arbeitszeitnachweis, Tageskarten | Woche zuerst → Tag → Korrektur/Export; Monatsbericht sekundär | Mittel |
| ProjektePage | Aktiv/Archiv, Suche, neue Projekte | Eigene Projekte und GU-Aufträge klar als unterschiedliche Projektarten kennzeichnen, Liste/Status/Filter | Hoch |
| ProjektPage | Monolith mit Kalender/Akte/Checklisten und PDF-Buttons | Eigene Unterseiten mit Kontexttabs, mobile Tagesliste; Projekt-ZIP unter Abschluss | Hoch |
| KundenPage | Kundenstamm für Rechnungsadressen | Kundenstamm intern getrennt von opt-in-Firmenverzeichnis | Hoch |
| MitarbeiterPage | Liste inkl. deaktivierte + Einladung | Team, Einladungen, Einsatzzuordnung, klare aktive Rollen; Projektleiter nur freigegebene Arbeitskräfte | Hoch |
| MitarbeiterDetailPage | Daten, Stundenkonten, Abwesenheit, Personalakte, Lohndaten | Links Teamprofile; vertrauliche Personalakte und Lohn als separat autorisierte Sektion, nicht GU sichtbar | P0 |
| AbwesenheitenPage | Liste und Teamkalender, Anträge | Mitarbeiter einfacher Antrag, Büro «Zu entscheiden» zuerst, danach Teamkalender | Mittel |
| RechnungenPage | Offene/bezahlt/storniert, PDF, Extras, E-Rechnung | Entwurf → Prüfung → Ausstellung → Zahlung; eindeutige Detailseite, Download nie anlegen/mutieren | P0 |
| AuswertungPage | Zeiten/Umsatz und Stundenkonten | Zusammenfassung mit Zeitraum/Vorlage; tiefe Berichte sekundär; paginierte Ergebnisse | Mittel |
| ExportePage | Lohn, DATEV, Monatsabschluss, MiLoG, Sicherung im selben Screen | Lohn & DATEV / Monatsabschluss / Projektarchiv / Datenexport / Sicherung getrennte Bereiche | Hoch |
| FirmaPage | Logo, Leistungsstamm, Lizenz, API, Webhooks, Import | Grunddaten / Team/Abrechnung / Projekte/Abo / Datenschutz / Erweitert für Schnittstellen | Mittel |
| ProfilPage | Passwort, Stundenkonto, Löschoption, eigene Personalakte | Persönliche Daten / Benachrichtigungen / Sicherheit (MFA) / aktive Organisation / Datenschutz | Mittel |
| ProtokollPage | Sicherheitseinträge und CSV | verständliche Filter nach Mensch/Zeit/Vorgang, redigierte sens. Daten, Export mit Recht | Hoch |
| Dialog ProjectDialog | viele Felder auf einmal; employee_ids leer bedeutet alle sichtbar | 3 Schritte: Basis → Team & Sichtbarkeit → Abrechnung, ausdrücklich «alle» oder «nur zugewiesene» | P0 |
| Dialog EntryDialog | Tag, Start/Ende, Pause, Person, Leistung, Tätigkeit, Serien | Kernfelder sichtbar, Zusatzoptionen aufklappen; Zwischenstände persistieren, Fehlerfeld markieren | Hoch |
| TagFotos | Tagesfoto-Upload mit Liste und Notizen, sequenziell | Kamera/Galerie, tägliche Quote, Fortschritt, Retry, Fotoalbum; keine unerwartete Löschung | Hoch |
| CompanyForm | Logo, Stempel, steuerliche und Zeitregeln in langer Maske | thematische Einstellungen in kleinen Screens, automatische Speicherung nur bei unkritischem Entwurf | Mittel |
| ui.jsx/Layout.jsx | Apple-ähnliche Cards, Chips, Segmented, 2 Navigationsblöcke und 4 Tabs + Mehr | konsistentes Designsystem, zugängliches Tabs/Focus, capability-spezifische Navigation | Hoch |

## 6. Neue Screens und Detailanordnung
### CompanyDirectoryPage – Subunternehmen finden
Header «Betriebe finden»; links Desktop Filter Gewerke/Region/Entfernung/Verfügbarkeit (nur bestätigte Angaben); rechts kompakte Karten Firmenname, Gewerke, Region, geprüfte Kontaktoption.
Primär: «Kontakt anfragen». Sekundär Profil. Normale Firmen dürfen private Angebotsanfragen senden, keine formalen Ausschreibungen veröffentlichen.
Privacy by design: nur opt-in veröffentlichte Daten; Anti-Spam und Limits.

### Tend ersPage / Ausschreibungen
Normalfirma sieht «Eingeladen», «Meine Angebote», «Gefunden»; GU «Von uns erstellt», «Laufend», «Prüfen», «Vergeben». Kein falsches gemeinsames «Neue Ausschreibung» für normale Firmen.
Karte: Frist, Gewerk, Ort, Auftraggeber, Veröffentlichungs-/Fragenstatus, ein CTA.
Detail: Überblick, LV/Unterlagen, private Rückfragen, eigenes Angebot, Versionsstand.
Einreichen: Preis, Frist, Anlagen, unterschriebenes Dokument falls erforderlich, endgültiger Check; quittierter Status.

### BidComparisonPage – nur GU mit Vergaberechten
Sticky Tabellenkopf, vergleichbare Positionen, Gesamtsumme, Änderungs-/Vorbehaltslisten; private Anbieterinformationen schützen. Vergleich erst nach zulässiger Öffnung. Freigabe und Zuschlag separat von «Ansehen».
Auf Mobile nur Zusammenfassungen und freigegebene Entscheidungen, keine unlesbare 15-Spalten-Tabelle.

### MessagesPage
Desktop 3-Spalten: Ordner/Kontexte (links 240 px), Gespräche (Mitte ~320 px), ausgewählter Thread (Rest); bei kleineren Breiten Liste → Thread.
Chatkopf: Ausschreibung/Projekt, exakte Teilnehmer und Sichtbarkeit (Privat an Firma / Projektteam / alle Bieter).
Komponieren: Nachricht, sichere Anhänge, Sichtbarkeitskontrolle vor Senden. Sichtbarer Persistenz-/Zustellstatus, Offline-Fall «Noch nicht versendet».
Systemereignisse wie Zuschlag/Einladung als separate Timeline-Meldung statt normaler Benutzernachricht.
Automatische E-Mails aus persistenter Outbox. Nachrichten sind zuerst in App gespeichert; Mail ist zusätzliche, fehlertolerante Benachrichtigung.

### GUProjectPage
Header: Projektname, Ort, Bauphase, PM, Abostatus und Kosten nur Admin.
Tabs: Übersicht / Gewerke & Firmen / Ausschreibungen / Zeitplan & Aufgaben / Nachrichten / Dokumente / Mängel & Abnahmen / Archiv.
Übersicht Priorität: Blocker, fällige Aufgaben, offene Freigaben, Fortschritt pro Gewerk, Nachrichten.
Beteiligte Auftragnehmer nur eigenes Los, berechtigte gemeinsame Daten.

### ProjectBillingPage (GU Admin)
Transparente Projektliste: Name, aktiv seit, nächster Termin, monatlicher Preis, aktueller Status, Zahlungsart, «Abo verwalten».
Kostenvorschau: 1 × 50,99 €, 5 × 50,99 €, keine automatische Berechnung pro eingeladenem Bieter.
Aktivierung Step 1 Auswahl des GU-Projekts, Step 2 Kostenübersicht, Step 3 ausdrückliche Zustimmung/Zahlung, Step 4 Erfolg/Beleg.
Ausfall: Lesbarkeit/Export nach Vertrag, Schonfrist, klare Zahlungsoption, niemals sofort löschen.

### CompanyGuestPortal
Einladung → kostenlosen persönlichen Account erstellen oder anmelden → Einladung ansehen, private Frage, Angebot, Zuschlag, freigegebene Unterlagen/Chat.
Upgrade-CTA erst für volle eigene Mitarbeiter-, Zeit-, Rechnung- und Archivfunktionen; nicht im verpflichtenden Angebotsprozess.

### ChangeOrders / Defects / Acceptance
Je eigener Vorgang + Status und vollständige Ereignischronologie. Genehmigte Nachträge ändern Vertragssnapshot, nicht altes Gebot.
Mangelkarte: Priorität/Fällig, Gewerk, Fotos, Verantwortliche, Bearbeitung, Prüfung, Abnahme.
Abnahme: Verantwortlicher, Umfang, Signatur, Zeitpunkt, revisionsfester Beleg.

### ArchivePage
Inhalt wählen → Berechtigungs-/Vollständigkeitsvorschau → asynchron erstellen → Fortschritt/Job-ID → ZIP herunterladen → SHA256 prüfen → optionale Empfangsbestätigung. Temporäres ZIP nach 7 Tagen entfernen, nicht die Originaldateien. Separate Retention-/Legal-Hold-/Löschfreigabe.

## 7. MVP-Abfolge und DoD
Gate 0: Sourcebugs P0 (Zeiterfassung, Offline-Queue, Projekte löschen, Signaturen, Rechnungsnebenwirkungen, Server-JWT, Mandantentrennung) mit Regressionstests.
Gate 1: Einheitliche Organisation/Membership/Entitlements, alle heutigen Seiten migriert, kein Datenleck, Legacy-Projekte laufen.
Gate 2: Neue Dashboards + rollenbasierte Navigation und mobile Mitarbeiterseiten; Projektformular vereinfachen.
Gate 3: GU-Konto, Projektleiter-Einladungen, Projektsubscriptions 50,99 EUR netto, saubere Zahlungen/Dunning.
Gate 4: Firmenverzeichnis/Anfragen, GU-Ausschreibungen, kostenlose Bieteraufnahme, Angebot, Quittung.
Gate 5: Chat/Benachrichtigungen/E-Mail-Outbox, Zuschlag/Projektbezug und Vertragsversionen.
Gate 6: Nachträge/Mängel/Abnahmen + ZIP-Gesamtarchiv + Aufbewahrung.
Gate 7: Berechtigungs-E2E, Web/iOS/Android, Datensicherung/Restore, Staging-Lasttests; erst dann öffentliche Kunden.

## 8. Abnahme über den kompletten Nutzerfluss
- Handwerksbetrieb kann ein Projekt in höchstens drei Kernschritten erstellen und Mitarbeiter einladen.
- Projektleiter eines GU sieht nur berechtigte Baustellen, hat dennoch ein einziges Login; GU-Admin kann Zugriffe sofort widerrufen.
- Normale Firma kann keine GU-Ausschreibung veröffentlichen, darf aber eingehende Ausschreibung ohne Bezahlhürde beantworten.
- Zeitstempel erhalten über Navigation/Offline/Mehrfach-Tap ihren fachlich korrekten Status; nie verloren oder doppelt verbucht.
- Einer Ausschreibung mit zehn Bietern können private Nachrichten zugeordnet werden, ohne fremde Angebote zu offenbaren.
- Projekt-Snapshot nach Zuschlag hat gleichen Vertragsumfang und eine nachvollziehbare Historie.
- GU-Abrechnung einmal pro aktivem Bauvorhaben, nicht pro Los/Mitarbeiter; fremdes Firmenabo niemals ungefragt abrechnen.
- ZIP eines Auftragnehmers enthält eigenes Angebot + Chat + Bau-/Rechnungsunterlagen, nicht die sensiblen Dateien fremder Firmen.
- Mindestens drei explizite Rollen (GU PM, Firmenchef, Mitarbeiter) bedienen ihre Kernaktion mobil ohne horizontales Scrollen oder technischen Sonderweg.
