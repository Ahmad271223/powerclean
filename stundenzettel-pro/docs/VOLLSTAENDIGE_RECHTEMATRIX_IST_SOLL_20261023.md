# STUNDENZETTEL PRO – VOLLSTÄNDIGE RECHTEMATRIX, IST/SOLL, CODEAUDIT (23.10.2026)

**Wichtig:** Dieses Dokument prüft den **neuen** main-Stand vom 23.10.2026 (nach f487941, inkl. Plattform-/Ausschreibungs-/GU-Abo-Code). Es ist eine Quellcodeprüfung, kein produktiver E2E-/Pentest und keine belastbare Browser-/Lasttest-Abnahme. Der ältere Architektur-Entwurfsbranch enthält nur Dokumente und ist gegenüber main in Codebasis veraltet. Nicht unkontrolliert mergen.

## 0. Legende und zweistufige Rechte
- IST = Backend-Endpunkte und Logik aktuell vorhanden; nutzbar nur wenn Firma, Rolle, Projekt und Plan erlauben.
- BEDINGT = nur bei expliziter Projektzuordnung, aktiver Beteiligung oder Firmenabo.
- FEHLT = nicht als vollständiger Workflow/API nachgewiesen; nicht als produktiv behaupten.
- Firmenarten: betrieb | auftraggeber | beides. Aktuell vom Inhaber unter /api/firma (art) selbst veränderbar; KEINE Plattformbetreiber-Verifizierung der GU-Eigenschaft. Formale Ausschreibung nur bei auftraggeber/beides über _auftraggeber_noetig, aber Geschäftsfreigabe kann so umgangen werden.
- Firmenrollen: mitarbeiter < vorarbeiter < buero < inhaber; zusätzlich project.leiter_ids. Rollen nicht mit Kundentyp verwechseln.
- Firma in der API ist an user.firma_id gebunden; ein persönliches Konto für mehrere Firmen / Organisationsswitcher NICHT vorhanden.
- Projekt: Eigentümerfirma und mögliche Beteiligungen anderer Firmen, pro Partner verknüpftes eigenes lokales Projekt. Umfang/Personaldaten nur der eigenen Firma; GU sieht explizite gemeinsame Baustellenelemente und freigegebene Wochenzeiten.

## 1. Rechte der vier aktuellen Firmenrollen
| Funktion | Inhaber | Büro | Vorarbeiter | Mitarbeiter | Bemerkung |
|---|---|---|---|---|---|
| Login, eigenes Profil, Stempelstatus | Ja | Ja | Ja | Ja | Auth validiert aktiven Nutzer in DB |
| Eigene Zeiten/Stempel Start/Pause/Stop | Ja | Ja | Ja | Ja | Auf sichtbarem eigenen oder bezahltem/zugeordnetem verknüpftem Projekt |
| Eigene Zeiten nachtragen/ändern | Ja | Ja | Ja | Ja | Datums-/Sperrregeln, nicht beliebig fremde |
| Mitarbeiterzeiten & eigene Mitarbeiter verwalten | Ja | Ja | Bedingt projektbezogen | Nein | Vorarbeiter kein Firmen-Personaladmin |
| Firmenprojekt erstellen | Ja | Ja | Nein | Nein | Firmenabo |
| Eigene Projektleitung zuweisen | Ja | Ja | Nein | Nein | `/projekte/{id}/leiter` |
| Teammitglied einladen | Ja | Ja | Nein | Nein | Firmenabo; Rolle Inhaber nur vom Inhaber vergebbar |
| Mitarbeiterkonto deaktivieren | Ja | Ja (nicht letzten Inhaber) | Nein | Nein | aktive Stempelungen nicht verlieren |
| Eigene Abwesenheit beantragen | Ja | Ja | Ja | Ja | beantragte eigene bearbeiten |
| Abwesenheit anderer genehmigen | Ja | Ja | Nein | Nein | in-app/status |
| Eigene Personalakte/Lohndaten lesen | Ja | Ja | Ja | Ja | nur Selbst |
| Fremde Personalakten/Lohndaten | Ja | Ja | Nein | Nein | strikt innerhalb eigener Firma |
| Rechnungen ansehen/anlegen/ausstellen/bezahlen | Ja | Ja | Nein | Nein | eigene Firma, Firmenabo für Anlegen |
| Lohn/DATEV/Zeiten-Firmenexport | Ja | Ja | Nein | Nein | keine GU-Zugriffe auf Fremdlohn |
| Firmenstammdaten | Ja | Ja | Nein | Nein | Firmenart nur Inhaber |
| Firmenart wechseln | Ja | Nein | Nein | Nein | IST sicherheitstechnisch zu offen (GU-Verifizierung fehlt) |
| Firmenverzeichnis pflegen/sichtbar machen | Ja | Nein | Nein | Nein | Suche ab Büro |
| Projektpartner einladen/entfernen | Bei Projektleitung | Bei Projektleitung | Wenn projektleiter | Wenn explizit projektleiter | Bedingung owner & projekt_leitung |
| Partner-Einladung annehmen/ablehnen | Ja | Ja | Nein | Nein | gratis möglich |
| Projektaufgaben zuweisen | Ja | Ja | Bedingt lokaler Partner-Projektleitung | Nein | externe Firmenmitarbeiter nicht direkt durch GU zuteilen |
| Eigene Aufgabe annehmen / Status / Foto | Ja | Ja | Ja, berechtigt | Ja, zugeteilt/offen | Statusrechte nach konkreter Rolle |
| Projektbericht erstellen | Wenn Projektleitung | Wenn Projektleitung | Bei Partner-Leitung | Ohne Leitung nein | Eigene Firma, jeweiliger Kontext |
| Ausschreibung als GU erstellen/veröffentlichen | Mit owner-project-Leitung | Mit owner-project-Leitung | Als explizit zugeteilter Projektleiter | Als explizit zugeteilter Projektleiter | Zusätzlich Firma art auftraggeber/beides, Vorsicht zu weite Vergaberechte |
| Angebote als bietende Firma | Ja | Ja | Nein | Nein | Einreichen, Fragen, Dokumente |
| Fremde Bieterangebote vergleichen | Nur owner-Projektleitung | Nur owner-Projektleitung | Bei owner-Projektleitung | Bei owner-Projektleitung | Ausschreibungen: angebot lesen ab Einreichung |
| Vergabe vorschlagen/mitteilen | Owner-Projektleitung | Owner-Projektleitung | Zugeordnete Owner-Projektleitung | Zugeordnete Owner-Projektleitung | VORSICHT: Vergaberechte stark weit |
| Vergabe intern freigeben | Ja | Ja | Nein | Nein | Vier-Augen-Regel wenn zweite freigabeberechtigte Person |
| Verbindlichen Zuschlag annehmen | Ja | Nein | Nein | Nein | explizite Annahmebestätigung |
| Firmenabo / GU-Abo sehen | Ja | Ja | Nein | Nein | GU-Abo an/aus nur Inhaber |
| API-Keys/Webhooks | Ja | Nein | Nein | Nein | Scopes beachten |
| Protokoll | Ja | Ja | Nein | Nein | Firmenbezogen |
| Projektarchiv mit Index, eigener Angebot/Chat/Rechnung | FEHLT | FEHLT | FEHLT | FEHLT | Im Ziel: Inhaber/Büro jeder normalen Firma und GU mit berechtigungsspezifischem Umfang; NICHT durch globales Datei-Backup ersetzen |
| Alle Firmendateien als ZIP-Backup | Ja | Nein | Nein | Nein | /api/exporte/dateien.zip – NICHT Projektakte |
| Firma vollständig löschen | Ja | Nein | Nein | Nein | bei aktiven GU-Beteiligungen, Archiv/Retention P0 prüfen |

## 2. Rechte auf der Bauplattform
| Vorgang | Auftraggeber-Projektleitung | Partnerfirma Büro/Inhaber | Partner-Vorarbeiter | Partner-Mitarbeiter |
|---|---|---|---|---|
| GU-Projektstamm und Teamleitung verwalten | Ja* | Nein | Nein | Nein |
| Ausschreibung/Einladung/Vergabe | Ja* | Eigene Gebote beantworten | Nein | Nein |
| Eigene Angebotsunterlagen | GU sieht eingereichte berechtigte | Eigene nur | Nein | Nein |
| Partner am Projekt einladen/entfernen | Ja* | Einladung annehmen/ablehnen | Nein | Nein |
| Aufgaben erstellen und Gewerken zuweisen | Ja* | Nur eigene Mitarbeiter intern zuteilen | Eigene Mitarbeiter projektbezogen zuteilen | Zugewiesene Aufgaben bedienen |
| Aufgabenstatus | Alle erlaubten | Einschränkung auf eigene Firma | Einschränkung auf eigene Firma | in_bearbeitung/eingereicht |
| Lieferungen/Status | Anlegen/bearbeiten | Eigene Lieferungen – Status | Projektbezogen bedingt | nicht beliebig |
| Mängel | Anlegen, zuweisen, Freigeben/Prüfen | Eigene bearbeiten/melden | Je lokale Leitung | Nur ausdrücklich freigegebene Vorgänge |
| Bautagesberichte | Alle berechtigten bearbeiten/prüfen | Eigene Firma | Bei Projektleitung | Keine eigenen Firmenberichte ohne Projektleitung |
| Meilensteine | Erstellen/bearbeiten | Lesen | Lesen | Leserecht je Projekt |
| Plattform-Dokumente | Freigabe steuern | Eigene oder an alle freigegebene | Bedingt | Nur ausdrücklich freigegebene |
| Anwesenheitsübersicht | Alle Firmen, Namen nur mit Partnerfreigabe | Eigene Daten | Eigene Daten | Nicht die GU-Gesamtübersicht |
| Wochenstundenzettel freigeben | GU sieht genehmigte | Eigene Freigabe/Rücknahme | Nein | Nein |
* zusätzlich serverseitiger owner/project_leitung-Check. Nicht jeder GU-Nutzer hat automatisch jede Projektberechtigung.

## 3. Funktionen nach Kundentyp und Abo
| Funktion | Betrieb mit Firmenabo | GU/Auftraggeber | Kostenlose Teilnahme |
|---|---|---|---|
| Eigene Firmenprojekte | Ja | Mit Firmenabo; GU-Projekte können an GU-Plan gekoppelt sein | Nein, nur verknüpfte Projekte |
| Eigene Angestellte & Lohn | Ja | Mit Firmenabo | Nein |
| Arbeitszeiten/Stempel im eigenen Projekt | Ja | Mit Firmenabo | Nein |
| Arbeitszeiten/Fotos im beauftragten GU-Projekt | Ja | Ja, soweit berechtigt | Ja im verknüpften Projekt |
| Eigene Rechnungen / DATEV | Ja | Mit Firmenabo | Nein |
| Firmenverzeichnis & Subunternehmersuche | Büro/Inhaber | Büro/Inhaber | Büro/Inhaber soweit Konto |
| Eigene Projektpartner direkt einladen | Ja | Ja | Nur bei existierendem berechtigten Projekt |
| Formale Ausschreibungen veröffentlichen | Nein (API art-Check) | Ja, Firma=auftraggeber/beides | Nein solange betrieb |
| Angebote/Rückfragen/Einreichung | Ja | falls selbst als fremder Bieter berechtigt und art=beides | Ja |
| Vollständiger Projekt-ZIP-Export | **FEHLT** | **FEHLT** | **FEHLT** |
| Datei-Komplettbackup ZIP | Nur Inhaber, mit vorhandenem Zugang | Nur Inhaber | Nicht als Projektarchiv |
| Echte Zahlungsabwicklung | **FEHLT** | **FEHLT** | Kostenfrei als Planstatus |
| Automatische E-Mails + vollständiger Projektchat | **FEHLT / nicht als produktiver Vollworkflow belegt** | identisch | in-app Benachrichtigungen und Fragen vorhanden |

## 4. Wichtigste Bestandslücken und Abweichungen
P0 – **GU-Verifizierung:** /api/firma erlaubt jedem Inhaber, art=auftraggeber/beides selbst zu setzen; damit werden GU-Funktionen und Kosten ausgelöst. Betreiberfreigabe/Subscription-Entitlement getrennt von frei editierbarer Profilklassifizierung; serverseitig.
P0 – **Kostenpflichtige Aktivierung:** /api/ausschreibungen/{id}/veroeffentlichen und /einladungen sowie Projektpartner-Einladung aktivieren GU-Abo automatisch. Der Code prüft auf Firmaart, aber keine durchgängige, transaktionsgesicherte explizite Checkout-Zustimmung pro Projekt. Der Firmenart-Dialog und einfacher window.confirm reichen für rechtlich/operativ robusten Billing-Lifecycle nicht.
P0 – **Projekt-ZIP für Handwerker UND GU:** /api/exporte/dateien.zip ist Firmen-Datensicherungs-Download, nicht vollständige auftragsspezifische Akte. Neuer Projektarchive-Worker, ACL-Snapshot, Revisions-/Dokumentenliste mit eigener Ausschreibung/Angebot/Zuschlag/Korrespondenz/Fotos/Zeiten/Abnahmen/Rechnungen, PDF-Index, Checksums, rechtliche Aufbewahrung. Für **alle** Firmenabonnenten ohne GU-Projekt-Preis.
P0 – **Projektleiter mit finanziellen Tenderdaten:** project.leiter_ids kann beliebige Mitarbeitende (auch einfache Mitarbeiter) enthalten. Wegen `projekt_leitung` erhalten diese dann auch Ausschreibungs-/Vergabeaktionen sowie vollständige eingereichte Bieterangebote. Saubere fachliche Capabilities statt nur Leitung, z.B. tender_view, tender_draft, tender_publish, bid_open, bid_evaluate, award_propose, award_approve.
P0 – **Firmenlöschung** in routes/firma.py durchläuft vor allem alte Sammlungen; neue plattformbezogene Collections, fremde Beteiligungen, Angebots-/Bauakten müssen speziell berücksichtigt werden. Außerdem dürfen Aufbewahrungspflichten nicht durch globales Delete unterlaufen werden.
P1 – **Kein organisationsübergreifendes Login:** User gehört einer einzigen Firma per user.firma_id an. GU-Projektleiter können mehrere Projekte derselben Firma verwalten; dieselbe Person in zwei Firmen braucht aktuell getrennte Identitäten. Einladungslogik bei bereits verwendeter E-Mail beachten.
P1 – **Vollständiger Chat/Mail**: privater Bieter-Q&A, Projektkommentare und In-App-Benachrichtigungen vorhanden; kein vollständiger projekt-/firmengetrennter Thread-Chat mit dauerhafter E-Mail-Delivery-Historie nachgewiesen. Einladungslink-Rückgabe ≠ automatisch nachweislich versendete E-Mail.
P1 – **Angebotsöffnung**: eingereichte Angebote sind unmittelbar für Owner-Projektleitung lesbar; keine getrennte versiegelte Öffnung nach Angebotsfrist. Für öffentliche/formalisierte Vergabe zusätzliche Verfahrens-Compliance erforderlich.
P1 – **Foto 20/Tag**: keine durchgängige atomare Quote pro Mitarbeiter/Arbeitstag in heutigen Upload-Routen verifiziert; bisher Speicherquoten in dateien.py, aber nicht Photo-Daily-Limit.
P1 – **Archiv-Zugang in Normalfirma:** bestehendes archived=true bedeutet Listenarchivierung, NICHT Projekt-ZIP oder geregelte Retention. Zwei Zugänge: Meine Projekte → Archiv sowie Berichte & Exporte → Projektarchive.
P1 – **Zahlungs-Integration**: manuelle Betreiberabrechnung über /api/admin/abos, keine verifizierten Zahlungen, Steuer-/Rechnungs-/Mahnläufe.
P1 – **UI**: aktuelle App.jsx teilt primär isBuero; Layout hat drei Menüs (buero, auftraggeber, mitarbeiter). Projektleiter-Fähigkeiten, Zahlungs-ACL und Menü müssen feiner granular sein.
P1 – **Dokument-Freigaben** nur gezielt, nicht GU-Generalschlüssel. Keine fremden Lohndaten, Personalakten, internen Rechnungsvorschauen oder Konkurrentenpreise in Partner-ZIP.
P1 – **Backup-Restore/Lasttest** laut GO-LIVE.md vor Produktionsfreigabe noch manuell offen; nicht behaupten, 5000-Firmen-Last sei nachgewiesen.
P2 – Stundenzettel und PDFs klar unterscheiden (schon vorhanden) vs Gesamtprojekt-ZIP, e-Rechnung-Freigabe, Kundenkommunikation, Chat. Alle Seiten nach Rolle verständlich gruppieren.

## 5. Ziel-Rechtemodell (umsetzbar)
User Account (verified personal identity) → active Organization Membership → Account Tier/Entitlement (firm_subscription, gu_project_subscription, guest) → Project Membership (owner/PM/contractor/local_worker) → Capability (lesen/anlegen/freigeben/finanziell/archivieren) → Document ACL and purpose. Grundsatz: `allow` nur wenn alle Prüfschritte positiv sind.
Bereiche:
- Inhaber: Firmenstamm, Team, Billing, vertrauliche Finanzen, Archiv.
- Büro: Firmenprojekte, Personal- und Rechnungsoperationen, Einladungen, Archiv nach Firmenfreigabe; keine Firmaart-/API-Owner-Verwaltung ohne Sonderrecht.
- GU Firmenadmin: GU-Plan und zentrale Projektleitungszuordnung, Billing; darf nicht fremde Subfirma-Personalakten sehen.
- GU Projektleiter (eigene Capability-Rolle, nicht bloße Projektmitgliedschaft): Projektdaten, Ausschreibungen/Einladungen/Angebote unter freigegebenen Einzelrechten, keine ungeprüfte Vergabe- oder Konzernfinanzfunktion.
- Vergabe-Freigeber: gesondertes bid_evaluate + award_approve, falls Vier-Augen-Verfahren; nicht jedes Projektleiterkonto.
- Nachunternehmer-Büro: eigene Angebote/Nachträge/Rechnungen, eigene Teamaufgaben, freigegebene GU-Unterlagen, eigenes ZIP.
- Vorarbeiter: eigene Teamaufgaben, Bau-Fotos und Status, keine fremden Angebote, fremden Preise oder Personalakten.
- Mitarbeiter: eigene Stempeluhr/Zeiten, Projektfotos, Aufgabe/Chat mit freigegebenen Teilnehmern, eigene Personalakte; keine Angebote, Rechnungen, Firmenarchive oder Team-Export.
- Kostenloser Bieter: nur Sicht auf eigene Ausschreibung, eigene Rückfragen und Angebot, begrenzte Projektnachrichten nach Zuschlag; kein Zahlungszwang für Angebotsabgabe.
- Plattformbetreiber: administratives Rechnungslauf-/Plan- und Support-Tool, kein routinemäßiger fremder Dateiinhalt.

## 6. Abnahmetests (muss in CI)
- Betrieb auf `art=betrieb` darf keine GU-Ausschreibung veröffentlichen; Wechsel zu `auftraggeber` ohne Betreiberfreigabe darf **nicht** GU-Publisherrechte öffnen.
- GU Inhaber vs GU PM A/B vs Vergabe-Freigeber: unterschiedliche Ausschreibungen/Projektlisten, Angebotsdaten, Zuschlag.
- Partner A/B: kein Lesen von Konkurrenz-Angebot, GU-internen Bieterfragen, Lohn, Rechnungsentwurf, Personaldokument.
- Gratis-Bieter / Büro: Angebot einreichen, Frage stellen, Einladung annehmen – ohne kostenpflichtiges Firmenabo.
- Eigene normale Handwerksfirma: ZIP Projektakte mit Zeiten/Fotos/Rechnung, auch ohne GU-Bezug und ohne 50,99 €.
- E-Mail-Provider aus, Postfach falsch, Wiederholung: Nachricht nicht weg; Zustellstatus nachvollziehbar.
- Projekt 50,99 €: mehrfach klicken/gleichzeitige Veröffentlichung -> maximal eine Abo-Aktivierung und nur nach expliziter Zustimmung.
- Firma löschen: kein Verwaisen von aktiven GU-Projekten oder Entfernen fremder Bauakten; Legal Hold blockiert unzulässiges Löschen.
- 20 Fotos/Arbeitstag: atomar unter Parallel-Uploads, wiederholter Upload korrekt behandelt.
- Mobile/Web: sichtbare Controls entsprechen Backend-Rechten. 401/403/402/404 sauber unterscheiden.
- Backup inkl. neue Collections und Dateien nachgewiesen wiederherstellbar.
