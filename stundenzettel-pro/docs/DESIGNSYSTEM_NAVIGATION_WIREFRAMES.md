# Stundenzettel Pro – Designsystem, vollständige Anordnung und Wireframes
Status: Zielbild/Design-Spezifikation, keine bereits implementierte Änderung. Grundlage: das aktuelle Apple-inspirierte Design in index.css und ui.jsx und statischer Seitenreview vom 23.10.2026.

## 1. Visuelle Strategie
Marke erhalten: Akzentrot #C41E3A, Hauptschrift #1D1D1F, Hintergrund #F5F5F7, weiße Arbeitskarten. Nicht alles neu färben; visuelle Konsistenz und Vertrauen wichtiger als modische Effekte.
Neue semantische Tokens:
- --brand-primary: #C41E3A; --brand-primary-hover: #AD1A33
- --text-primary: #1D1D1F; --text-secondary: #606067 (lesbarer als sehr blasses Grau)
- --surface: #FFFFFF; --canvas: #F5F5F7; --border: #E3E3E7
- --success: #187A42; --success-bg: #EAF7ED; --warning: #995600; --warning-bg: #FFF4E5; --danger: #B3261E; --danger-bg: #FDEDEC
- Erzwungene Mindestkontraste prüfen, besonders kleine graue Texte, Badges, Disabled Controls; nicht Rot allein als Statusunterscheidung.
Schrift: System-UI (vorhanden), keine neue Font-Abhängigkeit. Desktop H1 28–30 px; Screen-H2 20–22; Card-H3 16–18; Body 15–16; Metadaten nicht unter 12 außer irrelevante Fußnoten. Zahlen tabellarisch.
Spacing: 4/8/12/16/24/32; Form-Gruppen 24 Abstand; Grid-Gap Desktop 20 und mobil 12.
Radius: Karten 18–22, Eingaben 12, Modals 20, Buttons 12–999 je Kontext; kein optischer Wildwuchs.
Interaktiv: Hover nur als Zusatz, mobile min. 44x44 px Touch-Fläche, Tab-Reihenfolge logisch, sichtbarer Fokus, bei Loading keine Jumping Layouts.
Animationen 120–180 ms, respektieren prefers-reduced-motion. Keine Automatik-Scrollsprünge bei Stempelung oder Nachrichten.
Dark Mode kein P0. Professioneller Light Mode mit sicheren Kontrasten zuerst.

## 2. Responsive Raster
Breakpoints:
- 320–599 px: Mobile; Page Padding 16; max. 4 primäre Tabs + Mehr, bei langen Listen kartenbasierte Zeilen.
- 600–1023 px: Tablet; Page Padding 24; einspaltige Detailstruktur oder 2 KPI-Spalten; optionaler Drawer.
- ab 1024 px: Desktop; linke Seitenleiste 248–264 px, Hauptbereich max-width 1400 px für GU-Tabellen, max-width ~1180 px für normale Firma.
- ab 1440 px: Hauptinhalt 12-Column-Grid, Hauptspalte 8, rechte Aktionsspalte 4.
Safe Areas für iOS (env safe-area-inset) und Browserchrome mit svh/dvh beibehalten, Dialoge nie über sichtbare Viewportgrenze.
Dialoge: mobil Bottom Sheet für 1–5 Felder, komplexe Erstellung als eigene Seite/Wizard; Desktop modales Fenster bis max 720 px, Seiten-Panels für Details.
Tabellen: mobil als Karte/Summary mit Drilldown, nicht Desktop-Tabelle verkleinern.
Navigation und Rollenwechsel nicht an Scrollposition verlieren; ungelesene Nachrichten global erreichbar.

## 3. Shared Desktop-App-Shell (Wireframe)
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│ SIDEBAR 248px               │ Firmen-/Projekt-Kontext ↓    Suche [⌕]     🔔   Profil      │
│ Logo + aktive Firma         ├───────────────────────────────────────────────────────────────┤
│ Übersicht                   │ Seitenüberschrift                     [eine Hauptaktion]        │
│ Projekte                    │ Kontext/Untertitel + Status                                    │
│ Aufträge / Ausschreibungen  │                                                               │
│ Nachrichten                 │ Aufgabenblock mit 2–4 sofortigen Entscheidungen               │
│ Rechnungen                  │                                                               │
│ Team & Zeiten               │ [ KPI 1 ] [ KPI 2 ] [ KPI 3 ] [ KPI 4 ]                       │
│ Firmeneinstellungen         │                                                               │
│ Mehr / Hilfe                │ [ Liste / Hauptinhalt 8 Spalten ] [ Nächste Schritte 4 Sp. ] │
└─────────────────────────────────────────────────────────────────────────────────────────────┘

Desktop Designpriorität: freie Fläche nicht mit acht gleich wichtigen Kacheln füllen. Handlungsrelevanz zuerst. Firmen-/Projektkontext ist sichtbar, besonders wenn Nutzer mehrere Firmen hat.

## 4. Mobile App Shell
┌────────────────────────────────────┐
│ Firma wechseln ↓       🔔   Profil │
│ Guten Morgen                        │
│ Heute / Freitag                     │
│ [ Wichtigste Aufgabe ]             │
│ [ Hauptaktion: Start / Angebot ]   │
│ [ Aktiver Vorgang / Projekt ]       │
│ [ Nächster Termin ]                 │
│ ...                                  │
├────────────────────────────────────┤
│ Start  Projekte  Chat  Zeiten  Mehr │
└────────────────────────────────────┘
Mitarbeiter: Start, Einsätze, Zeiten, Nachrichten, Mehr. Handwerkschef: Start, Projekte, Nachrichten, Rechnungen, Mehr. GU-PM: Start, Bauprojekte, Ausschreibungen, Nachrichten, Mehr. Capabilities entscheiden Sichtbarkeit, nicht bloß isBuero.
Unteres Menü safe area und Tastatur beachten. Kontextbezogene Hauptaktion oberhalb der Tabbar, aber keine verdeckten Formularfelder.

## 5. Screen-Wireframes (größte Seiten)
### Handwerkschef Dashboard
┌ Willkommen zurück                 [ + Projekt ] ┐
│ Braucht deine Entscheidung:                         │
│ ! Angebot bis morgen abgeben  [Öffnen]              │
│ ! 2 Mitarbeiterzeiten prüfen  [Prüfen]              │
│ [Im Einsatz] [Aktive Projekte] [Offene €] [Anfragen] │
│ LÄUFT GERADE                   NÄCHSTES             │
│ Projektliste mit Status        Fristen              │
│ Teamstatus                    Nachrichten           │
└─────────────────────────────────────────────────────┘
Fehlt ein Ereignis: keinen leeren Warnblock zeigen. Uhrzeit/früheste Deadline sichtbar.

### GU-Projektleiter Dashboard
┌ Meine Bauprojekte                 [ + Bauprojekt ] ┐
│ ZU ERLEDIGEN                                           │
│ 3 Angebote zu prüfen [Prüfen]     2 Rückfragen [Antworten]│
│ 4 Mängel fällig [Ansehen]         1 Nachtrag [Freigeben]│
│ [Aktive] [Offene Ausschreibungen] [Entscheidungen]    │
│ Meine Projekte: Projekt | Status | PM | Termin | Aktion│
│ Nachrichten rechts, nicht darunter als 9. KPI.        │
└─────────────────────────────────────────────────────┘

### Mitarbeiter Tageserfassung
┌ HEUTE 23.10.26               [Offline/Synced] ┐
│ [ Objekt auswählen ▼ ]                        │
│ [ 02:14:37 Arbeitszeit ]                      │
│ [ Pause ]      [ Arbeit beenden ]             │
│ Tätigkeit: Kabelverlegung                     │
│ Fotos [ + aufnehmen ]  3/20                   │
│ [ ▢ ▢ ▢ ]                                    │
│ Heute erfasst: 6:45 h | Letzte Buchung ...    │
└───────────────────────────────────────────────┘
Startzustand: großer Startknopf. Offlinezustand zeigt Zahl noch nicht synchronisierter Ereignisse und Retry-Aktion, nicht «gespeichert» vor Serverbestätigung.

### Projekt Detail – normaler Betrieb
[← Projekte] Projekt Müller | Aktiv | Kunde | Einsatzort    [Aktion …]
Tabs: Übersicht | Kalender | Zeiten | Fotos | Dokumente | Rechnung | Abschluss
Übersicht: Heute, nächste Arbeit, Team, offene Aufgaben, letzten 5 Nachrichten.
Kalender: mobil Tages-/Wochenliste statt voller Monatsgrid; Desktop Monatskalender + rechter Tagesslider.
Zeiten und Fotos eines Tages werden gemeinsam angezeigt.
Rechnung separate Freigabe; Archiv im Abschluss.

### GU Bauprojekt Detail
[← Projekte] Bauvorhaben A / Standort / Status / Verantwortlicher
oben: Warnungen «3 Gewerke warten auf Vergabe»; Milestone und Budget nur wenn berechtigt.
Tabs: Übersicht | Gewerke | Ausschreibungen | Plan & Aufgaben | Chat | Dokumente | Mängel & Abnahmen | Archiv.
Ansicht Gewerk: Firma, verantwortlicher Kontakt, geplanter Termin, Status, offenen Nachtrag, eigene freigegebene Dokumente. Kein Datenleck von Lohnunterlagen.

### Ausschreibungsliste – bietendes Unternehmen
[ Suche ] [Gewerk] [Region] [Frist]
Tabs Eingeladen (3) / Meine Angebote (2) / Entdecken / Archiv
Karte: Auftraggeber · Gewerke · Ort · Angebotsfrist (lokal) · Version Unterlagen · [Ansehen / Angebot starten]
Nur Berechtigte können die Daten sehen; GU Erstellungsschaltfläche fehlt vollständig und API verweigert Publikation.

### GU Ausschreibungsassistent
1 Projekt & Gewerk → 2 LV/Unterlagen → 3 Fristen & Fragen → 4 Firmen einladen → 5 Prüfen & Veröffentlichen.
Rechte Seite Desktop: automatische Vorschau Fristen, veröffentlichte Version und Bieterzahl; mobil als oberes Summary.
Veröffentlichen ist irreversibel versionierter Vorgang mit Quittung und expliziter Bestätigung. Änderung nach Veröffentlichung erzeugt neue Version und benachrichtigt Bieter.

### GU Angebotsvergleich
Filter Gewerk, Angebotsstatus, erlaubte Öffnung.
Desktop: Tabellenkopf fixiert, Bieterzeilen, Summen, Termin, Vorbehalte; Detail-Ausklappung, dokumentierter Zuschlags-Flow mit Freigaben. Mobile nur Gegenüberstellung für wenige Bieter, keine horizontale 15-Spalten-Matrix.
Datensicht streng nach tender/lot/role.

### Nachrichten
Desktop: links Threads nach Kontext, mittig Gespräche, rechts ausgewählter Thread/Details. Mobile: Startliste → vollständiger Thread.
Oben «Privat: GU ↔ Elektro Müller» und Teilnehmer avatars/names; separates Label «An alle Bieter» für Gruppeninformationen.
Chatblasen je Nachricht mit Zustandsindikator: App gespeichert, Mail in Warteschlange, an Provider, zugestellt, fehlgeschlagen. App-Nachricht kann erfolgreich sein, obwohl Mail fehlschlägt.
Anhänge mit erlaubter Sichtbarkeit, Version und Download.
Benachrichtigungsvoreinstellungen: kritisch (Zuschlag/Frist) sofort; normale Chatnachrichten bündelbar. Keine E-Mail an fremde Adresse ohne Verifikation.

### Firmen- und Mitarbeiterverwaltung
Firmenprofil: öffentliches Geschäftsfeld Opt-in getrennt von internen Rechnungs-/Lohn-/Kontaktdaten.
Team: Tabelle/Mobile-Karten (Name, Rolle, Status, nächste Einladung); Add Wizard Name/E-Mail/Rolle/Projekt – Verifizierung/MFA.
Mitarbeiterdetail: Basis / Zeiten / Abwesenheit / Stundensaldo / Personalakte / Lohn; Personalakte/Lohn nur individuell befugte Rolle, niemals GU.
Vor Deaktivieren laufende Stempelung sichern und offene Übergaben anzeigen.

### Rechnungen
Status-Pipeline «Entwurf» → «Zu prüfen» → «Ausgestellt» → «Bezahlt» oder «Storniert».
Liste zeigt Firma/Kunde, Rechnungsnummer, Betrag, Fälligkeit, Status, Projekt; Aktion «Prüfen» vor «Ausstellen».
Detail: Positionen | Anhänge | E-Rechnung | Zustellung | Zahlungshistorie.
PDF-Download nie implizit Rechnung anlegen/umschreiben.
Storno als Korrekturbeleg, nie Nummer zurücksetzen.

### GU-Abo
Liste je GU-Bauvorhaben: Projektname, Aktivierung, 50,99 EUR netto/Monat, Zahlungsperioden, offenes/aktiv/gekündigt, [Abo verwalten].
VOR Aktivieren eigene Vorschau: welches Projekt, Preis zzgl. USt, erster Zahlungstermin, Kündigungsregel, Zahlart, explizites [Kostenpflichtig aktivieren].
Nach Zahlungsproblem: Gelber Hinweis, Zahlungsart aktualisieren, Schonfrist/Read-only, keine stille Datenlöschung.

### Projektabschluss / ZIP
Schritt 1: offene Vorgänge prüfen (Stempel, Zeiten, Fotos, Nachträge, Mängel, Abnahmen, Rechnungen).
Schritt 2: Archivinhalt mit erlaubter Sichtbarkeit bestätigen (GU-Gesamtprojekt vs Auftragnehmer-eigene Akte).
Schritt 3: Hintergrundjob mit Fortschritt, Status/Fehler und Integritätsprüfung.
Schritt 4: Sicherer Download + SHA-256 + optionale Empfangsbestätigung.
Schritt 5: Getrennter Archiv-/Löschstatus nach Datenkategorie und Legal Hold; Download niemals Löschsignal.

## 6. Wiederverwendbare Komponenten
AppShell, OrganizationSwitcher, ContextBreadcrumb, CapabilityGate (nur UX, Backend immer autoritativ), PageHeader, PrimaryAction, TaskInbox, MetricCard, EmptyStateWithAction, StatusBadge, FilterBar, DataList, ResponsiveTable, DetailSplit, EntityTimeline, AssetUploader, UploadQuota, AttachmentPreview, SafeConfirm, RevisionHistory, CurrencyAmount, DateTimeLocal, NotificationBell, ChatThread, ChatComposer, ExportJobProgress, PaymentStatusCard.
Gemeinsame Zustandskonvention für jede Async-Komponente: idle/loading/empty/success/error/offline/forbidden; niemals ein unendlicher Spinner ohne Fehlermeldung.

## 7. Exakte Bedienregeln
- Primäraktionen: Desktop rechts im Seitenkopf, mobil Sticky-Footer bei Formularen.
- Buttontexte konkret («Angebot verbindlich einreichen» statt «OK», «Kostenpflichtig aktivieren» statt «Starten», «Nur dieses Projekt archivieren»).
- Suchleiste max 460 px; Chips darunter; Filtersheet mobil.
- Bestätigungen: Fehlende Felder inline mit Hilfe, nicht nur toast. Konflikt 409 zeigt Veränderungen und erneuten Abruf an.
- Datenlisten paginiert/infinite-scroll mit deutlichem Endstatus und vollständigem Export.
- Kein destructive click in einer Projektkarte; Löschen in Danger Zone mit expliziter Trennung Archiv/Löschen.
- Textgrößen und Kontraste für echten Einsatz im Freien; Timer-Buttons breit und mit großen Touch-Flächen.
- Offline-Stempelanzeige persistent bei Seitenwechsel, offensichtlicher «wird synchronisiert» Zustand. Serverzustand nach Wiederverbindung abgleichen, keine stillen Verwerfungen.
- Fotos bis 20/Arbeitstag, Quote serverseitig atomar, empfohlene Optimierung 0,5–1 MB, originale Beweisqualität optional gesondert; Notizen/Person/Datum bei jedem Foto.
- Mobile Fotos per Kamera oder Galerie, kein hover-exklusives Löschsymbol (heute in TagFotos sichtbar nur bei hover/focus).
- E-Mail-Threads dürfen private Bieterangebote nicht in Gruppen-E-Mail verlinken oder beifügen. Zustellstatus getrennt von rechtsverbindlichem Zugang.

## 8. Barrierefreiheit / Plattformqualität
- Tastatur und Screenreader: Radix-Dialoge, Focus-Trap, sinnvolle aria-describedby, Tabs mit Pfeiltasten und Tabpanel-Rollen; bestehendes Segmented hat role=tablist/tab aber keine vollständige Tastaturnavigation.
- Immer sichtbarer Fokus, keine globale Unterdrückung auf Inputs. Kontrastprüfung WCAG AA für kleine Texte, rote Buttons und Status.
- Große dynamische Schrift in iOS/Android, Touch >=44px, safe areas, Screenreader-Namen aller Iconbuttons.
- Ladezeiten optimieren, Projekt-/Chatlisten paginieren, nur notwendige Bilder als Thumbnails, keine 10.000 Fotos direkt in React laden.
- Mobilnetz: Retry, lokale Entwürfe/Queue mit Datentrennung je Benutzer+Org, klare Konfliktlösung; Download von großen ZIPs mit Hinweis.
- Datenschutz: EXIF/GPS nur mit erlaubtem Zweck, Benachrichtigungen ohne vertrauliche Vorschautexte auf gesperrten Geräten.
- QA Matrix: 320/375/390/768/1024/1440 px, iPhone/Android, VoiceOver/TalkBack, Tab-Tastatur, Offline/401/403/409/500, 200% Zoom und Landschaftsformat.

## 9. Implementierungsreihenfolge Design
D0 Design-Tokens + Layout/Nav und Rollen/FeatureFlags; Screenshot-basierte Regressionstests.
D1 Kritische Kernjourneys: Stempeluhr, Tageserfassung, Projekt-Erstellung; Datenverlustfehler zuvor beheben.
D2 Firmen-Dashboard, GU-Dashboard, Mitarbeiter-Dashboard und Untermenüs je Kontext.
D3 Ausschreibungs-Wizard, Angebote, Vergleich, private Bieter-Q&A.
D4 Nachrichten/Posteingang und Projekt-Gewerke-/Aufgabenseiten.
D5 Rechnungswizard, GU-Projektabo, Nachträge/Abnahmen.
D6 Archiv-, Upload- und Löschseiten; End-to-End-Test, Accessibility, Performance.

Vor jeder Produktivänderung Desktop und mobile Screenaufnahme als Baseline, funktionale E2E-Tests und Rollentestmatrix. Kein automatischer Merge des reinen Designs.
