# P0: Formulare/CSV sowie Chef-Einsatzplanung und datensparsame Projektansichten

Stand 23.10.2026. **Entwicklungsbranch: Änderungen NICHT produktiv ausgerollt; Backend- und Frontend-E2E in Staging vor Merge ausführen.** Main wurde während dieses Branches weiterentwickelt. Vor Merge mit dem neuesten `main` konfliktbewusst abgleichen.

## 1. User Stories und Abnahmekriterien
1. Chef (Firmeninhaber) legt **allein** Firmenprojekte an. Büro/Vorarbeiter/Mitarbeiter dürfen weder per UI noch per POST neue Projekte erstellen. Eigene Firmenprojekte dürfen später an GU-Projekten teilnehmen; GU-Rechte separat.
2. Chef plant für einen oder mehrere Mitarbeiter Datum/Wochentage, Beginn, Ende, Pause, Adresse, Hinweis und Projekt. Plan sichtbar nur Chef und betroffener Nutzer; Mitarbeiter dürfen nicht die Zeiten fremder Mitarbeiter lesen oder Summen der Kollegen im Projekt abrufen.
3. Mitarbeiter stempelt selbst. Ein geplanter Beginn 08:00 gegenüber einem tatsächlichen Stempel 08:10 ergibt Hinweis «10 Minuten später eingestempelt», keine automatische Feststellung einer schuldhaften Verspätung. Ende 15:00 gegenüber geplant 16:00 wird als 60 Minuten früher ausgestempelt angezeigt.
4. Chef kann geleistete Zeiten **als separate genehmigte Zeit** mit Begründung freigeben, ohne Original-Stempel-Logs zu überschreiben. Fehlender Stempel darf nie unbemerkt als tatsächlich geleistete Zeit ausgegeben werden. Bei nicht übereinstimmendem/fehlendem Stempel muss Chef bestätigten Arbeitsnachweis und Grund angeben; zukünftige oder aktive Schichten nicht freigeben.
5. Projektleiter-PDF: ausschließlich Chef-freigegebene Zeitspannen; offene Einsätze als fehlend kennzeichnen. Originalpunches weiterhin getrennt für Compliance/Lohn.
6. Mitarbeiter sieht alle Fotos des **eigenen Projekts**, sofern sie in dessen freigegebenem Kontext liegen, aber bei fremden Fotos keinen Namen/Uploaduser/Originaldateinamen/EXIF. Chef sieht, wer sie aufgenommen hat, eigener Fotograf sieht sein eigenes Foto. GU-Projektfotos müssen künftig explizit gemeinschaftlich freigegeben sein.
7. Pauschal-Projektpreis auf Firmenprojekt speichern und Schätzung: eigene geplante, gestempelte, genehmigte Stunden, geschätzter direkter Lohnaufwand, pauschaler Netto-Auftragswert minus direkter Lohnaufwand. **Kein endgültiger Gewinn**, Material, AG-Nebenkosten, Gemeinkosten/Mehrwertsteuer und andere Zeiträume fehlen.
8. Bei inländischer täglicher Arbeitszeitdokumentation muss Beginn, Ende und Dauer **geleisteter** Arbeitszeit erfasst sein; Plan =/= Ist. BMAS FAQ zur Arbeitszeiterfassung: https://www.bmas.de/DE/Arbeit/Arbeitsrecht/Arbeitnehmerrechte/Regelungen-zur-Arbeitszeit/Fragen-und-Antworten/faq-arbeitszeiterfassung.html

## 2. Im separaten Branch implementierte Teilschritte
- ui.Btn, IconBtn, Segmented haben Default `type="button"` in Formularen (Pauschal/Stunden/Positionen versehentlich Submit verhindert); AngebotPreisart ist bewusst disabled nach verbindlicher Einreichung und erklärt warum.
- «Angebot zurückziehen» und «Vergabe zurückziehen» ohne browserabhängiges `window.prompt`: eigene Bestätigungsdialoge.
- CSV-/Excel-Eingaben robust(er): Semikolon, Tab, Komma; quotierte Zellen; Dezimalkomma; Kopfzeilen; präzise Fehler pro Zeile. ExportePage meldet genaue Datei und Serverfehlermeldung anstatt nur rot/unspezifisch. **Nicht jede CSV-Ursache nachgewiesen**; ohne exakten UI-Fehler bzw. Netzwerkanalyse nicht als vollständig behoben behaupten.
- `routes/einsatzplan.py`: Chef plant tägliche/wöchentliche Einsätze, Beschäftigte sehen nur eigene, Chef genehmigt mit Begründung, Differenzen gegenüber Stempeln, nur Chef sieht Auswertung, PDF ausschließlich aus genehmigten Einträgen.
- `einsatzplan_worker.py`: nach 18 Uhr serverlokaler DE-Zeit morgige Schicht als in-app-Benachrichtigung an Nutzer, eindeutige ID pro Version. **Keine Betriebssystem-Push-Einbindung oder verifizierte SMTP-/E-Mail-Zustellung.**
- `frontend/src/pages/EinsatzplanPage.jsx`: Chefplant-Form und Teamübersicht, Chef-Freigaben, Mitarbeiteransicht, PDF-Download, pauschale Kostenschätzung.
- Projetkosten: `projects.abrechnungsart_projekt` stunden/pauschal, `pauschale_netto`. Nur Kalkulation; alte Rechnungslogik ist bislang stundenbasiert. Pauschalrechnung gesondert realisieren.
- Zeitdatenschutz: alle Projektzeit-Einträge nur Chef oder betroffenem Mitarbeiter; Kollegen-Listenzugriff über Zeiten, Mitarbeiterauswertung, allgemeine Exporte, Lohnübersicht, Konten, Dashboard weitgehend auf Chef beschränkt.
- Foto-Metadaten für Kollegen in Projekt-Kalender und Projektakte verborgen; Originalbild über Projekt-Dokumentendpoint nur als EXIF-freie JPEG-Kopie für Nicht-Chef/Nicht-Uploader; eigenes Foto löschbar.
- Regressionstests `backend/tests/test_einsatzplan_20261023.py` für Manager-/Mitarbeiterrechte, Fotoanonymisierung und Chef-Zeitfreigabe **geschrieben, nicht lokal ausgeführt**.

## 3. Noch NICHT vollständig umgesetzt / Go-live-Sperren
- Lohn/DATEV/Monatsabschluss und bestehende Rechnungs-PDFs beziehen derzeit weiterhin `entries`; ein genehmigter `einsatzplaene.freigabe`-Wert aktualisiert diese Alt-Exports **noch nicht**. Unbedingt eine deduplizierte verbindliche Projektions-/Ledger-Lösung umsetzen, statt zweite Zeiten zu addieren und versehentlich doppelt zu vergüten. Projektleiter-PDF ist ein gesonderter neuer Export.
- Arbeitszeitkorrekturen mehrfach versionieren mit Ursache und altem Wert; Rücknahme nach Abschluss, Genehmigung durch Vertreter/Urlaubsregel, aktiver Stempel, Überlappungen und Urlaub kontrollieren.
- Night push echte APNs/FCM, verifizierte Adressen und E-Mail-Outbox; Mitarbeiterpräferenzen, stille Nachtzeiten und Zustellstatus.
- Fotoanlage: projektübergreifende Task-/Mängelfotos und GU-Dokumentfreigaben brauchen konsistente Berechtigungen und EXIF-Entfernung. Foto 20/Arbeitstag serverseitig atomar fehlt noch.
- Komplettes Projektarchiv/ZIP für **jede reguläre Firma** ebenso GU noch nicht implementiert.
- Volle Pauschalabrechnung inkl. Rechnungserstellung, Nachträge, Preisaufteilung, Materialkosten, Lohnnebenkosten und Umsatzsteuereinstellungen noch offen.
- Ohne exakten Wortlaut der roten CSV-Fehlermeldung noch keine sichere Ursachenbestätigung; im Test die genaue Datei, Eingabe, HTTP-Status und Antwort erfassen.
- Rechtebehandlung für GU-Projektleiter getrennt von Firmeninhaber: Chef-only Zeitsicht bedeutet, dass GU nur ausdrücklich freigegebene Zeiten erhält, niemals lokale Mitarbeiter-Lohn-Personalakten.
- Bestehende alt-/neu-Tests müssen nach geändertem Inhaber-only-Rechtemodell angepasst werden. Keine Produktivfreigabe ohne Staging E2E auf Browser/iOS/Android, CSV-Import, Buchhaltung, Wechseldaten, Datenschutz, Backup-Restore und MongoDB-Transaktionen/Unique-Indizes.

## 4. Geplanter kompletter Nutzerfluss
Chef: Firmenprojekt anlegen → Zeitraum/Woche wählen → Mitarbeiter auswählen → Adresse/8–16/30 Min speichern → App zeigt jedem Mitarbeitenden nur seinen Dienstplan → Erinnerung nach 18 Uhr für Folgetag → Mitarbeiter stempelt, lädt Fotos hoch → Chef sieht Abweichung geplante vs echte Start-/Endzeit → nach Ende belegen und freigeben → Projektleitung-/Kundenstundenzettel-PDF aus genehmigten Zeiten → Monats-/Lohnexport erst nach gesonderter geprüfter Integration → (Pauschalprojekt) geschätzte Deckung plus Einzelkosten → vollständiger ZIP-Projektexport später.

## 5. Beispiel
Plan 08:00–16:00, 30-Minuten-Pause = **7h30 Soll**.
Stempel 08:10–15:00, 30 Min = **6h20 tatsächlich registriert**.
Hinweise: 10 min später eingestempelt, 60 min früher ausgestempelt.
Chef bestätigt nach Prüfung tatsächlichen Beginn 08:00 bei weiterhin Ende 15:00, 30 Min Pause → **6h30 freigegeben**. Die originalen 08:10–15:00 Stempelzeiten bleiben dokumentiert. Auf 16:00 freigeben ist nur vertretbar, wenn diese Zeit tatsächlich gearbeitet wurde. Ohne Stempelung: Plan bleibt «noch zu prüfen» bis aktive Chefbestätigung der geleisteten Arbeitszeit.
