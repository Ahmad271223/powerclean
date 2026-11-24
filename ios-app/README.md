# Stundenzettel Pro – iPhone-App (SwiftUI) · Prototyp, nicht weitergeführt

> **Stand 24.11.2026:** Entscheidung „Eine App für alle“ – die bestehende App unter `stundenzettel-pro/frontend` (React + Capacitor)
> ist die Haupt-App für iPhone und Android. Dieser Ordner bleibt als Vorlage (Datumsregeln, Tests); neue Funktionen kommen in die
> bestehende App, iPhone-Besonderheiten (WhisperKit, Apple-KI) als nativer Swift-Baustein darin.

Native iPhone-App für die Plantafel von Stundenzettel Pro. Kennung `de.stundenzettelpro.ios`, ab iOS 17.
Die bisherige Capacitor-App unter `stundenzettel-pro/frontend/ios` bleibt unverändert.

## Aufbau

| Ordner | Inhalt |
|---|---|
| `Kern/` | Swift-Paket ohne Oberfläche: Modelle, Server-Zugriff, Schlüsselbund, Datumsregeln, Lizenzliste. Tests mit `swift test`. |
| `App/` | SwiftUI-Oberfläche: Anmeldung, Meine Einsätze, Einsatz mit „Gelesen & bestätigt“, Plantafel-Woche, Einstellungen, Über / Lizenzen. |
| `UITests/` | Durchklick-Tests gegen einen lokalen Server mit Demo-Daten. |
| `project.yml` | Projektbeschreibung für XcodeGen; das erzeugte `StundenzettelPro.xcodeproj` liegt mit im Repo. |

Regeln: Token nur im Schlüsselbund (nur dieses Gerät), keine Zugangsschlüssel für Dienste Dritter in der App, nur Bausteine
mit MIT-, Apache- oder BSD-Lizenz (Liste in `Kern/Sources/StundenzettelKern/Lizenzen.swift`, ein Test prüft sie).
Der Mikrofon-Knopf erscheint nur mit dem Feature-Flag `sprachplanung` (`FEATURE_SPRACHPLANUNG=1` auf dem Server).

## Lokal starten

Einmalig muss Xcode die aktive Entwicklerumgebung sein:

```bash
sudo xcode-select -s /Applications/Xcode.app/Contents/Developer
```

Server mit Demo-Daten (zweites Terminal, ohne MongoDB):

```bash
cd stundenzettel-pro/backend && DB_MODE=memory FEATURE_SPRACHPLANUNG=1 python -m uvicorn server:app --port 8010
```

```bash
cd stundenzettel-pro/backend && python testdaten_app.py
```

Zugangsdaten der Demo stehen in `stundenzettel-pro/backend/testdaten_app.py`. Dann `ios-app/StundenzettelPro.xcodeproj` in Xcode
öffnen, ein iPhone-Simulator wählen, ▶︎. Der Simulator erreicht den Mac unter `http://localhost:8010` (Standard in Debug-Builds).
Auf einem echten iPhone unter „Server-Adresse“ die Adresse des Macs im WLAN eintragen (z. B. `http://192.168.1.20:8010`, Server
dann mit `--host 0.0.0.0` starten) oder den Testserver mit https.

## Tests

```bash
cd ios-app/Kern && swift test
```

```bash
cd ios-app && xcodebuild test -project StundenzettelPro.xcodeproj -scheme StundenzettelPro -destination 'platform=iOS Simulator,name=iPhone 17' CODE_SIGN_IDENTITY=-
```

Die UI-Tests brauchen den lokalen Server mit Demo-Daten (sonst werden sie übersprungen).

Nach Änderungen an `project.yml`: `cd ios-app && xcodegen`.
