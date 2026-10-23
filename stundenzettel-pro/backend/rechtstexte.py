"""Datenschutzerklärung und Impressum als Seiten des Servers (Pflicht für Play Store und App Store).
Anbieterdaten kommen aus der Umgebung (ANBIETER_NAME, ANBIETER_ANSCHRIFT, ANBIETER_EMAIL, ANBIETER_TELEFON).
Vorlage – vor der Veröffentlichung von einem Anwalt oder Datenschutzbeauftragten prüfen lassen."""
from __future__ import annotations

import html

import config

_STIL = """<style>body{font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;max-width:760px;margin:0 auto;padding:32px 20px;color:#1d1d1f;line-height:1.55}
h1{font-size:28px}h2{font-size:19px;margin-top:28px}p,li{font-size:15px}a{color:#c41e3a}.hinweis{background:#fff4e5;padding:12px 16px;border-radius:12px;font-size:14px}</style>"""


def _anbieter() -> dict:
    return {
        "name": html.escape(config.ANBIETER_NAME or "[Anbieter: Name der Firma]"),
        "anschrift": html.escape(config.ANBIETER_ANSCHRIFT or "[Anbieter: Straße, PLZ Ort]").replace("\\n", "<br>"),
        "email": html.escape(config.ANBIETER_EMAIL or "[E-Mail des Anbieters]"),
        "telefon": html.escape(config.ANBIETER_TELEFON or ""),
        "app": "Stundenzettel Pro",
    }


def _seite(titel: str, inhalt: str) -> str:
    return f"<!doctype html><html lang=\"de\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>{html.escape(titel)}</title>{_STIL}</head><body>{inhalt}</body></html>"


def impressum() -> str:
    a = _anbieter()
    tel = f"<p>Telefon: {a['telefon']}</p>" if a["telefon"] else ""
    return _seite("Impressum", f"""
<h1>Impressum</h1>
<p>Angaben gemäß § 5 DDG</p>
<p><strong>{a['name']}</strong><br>{a['anschrift']}</p>
<p>E-Mail: <a href="mailto:{a['email']}">{a['email']}</a></p>{tel}
<p>Verantwortlich für den Inhalt: {a['name']}</p>
<h2>Haftung für Inhalte</h2>
<p>Die Inhalte dieser App wurden mit größter Sorgfalt erstellt. Für die Richtigkeit, Vollständigkeit und Aktualität der von Nutzern eingetragenen Daten (Arbeitszeiten, Rechnungen) ist die jeweilige Firma verantwortlich.</p>
<p><a href="/datenschutz">Datenschutzerklärung</a></p>
""")


def datenschutz() -> str:
    a = _anbieter()
    return _seite("Datenschutzerklärung", f"""
<h1>Datenschutzerklärung</h1>
<p class="hinweis">Diese Erklärung gilt für die App <strong>{a['app']}</strong> (Web, Android und iOS) und den zugehörigen Server.</p>
<h2>1. Verantwortlicher</h2>
<p>{a['name']}<br>{a['anschrift']}<br>E-Mail: <a href="mailto:{a['email']}">{a['email']}</a></p>
<h2>2. Was die App ist</h2>
<p>{a['app']} ist eine Zeiterfassung für Firmen. Eine Firma (der Arbeitgeber) legt ein Konto an und lädt Mitarbeiter ein. Der Arbeitgeber ist für die Verarbeitung der Daten seiner Mitarbeiter Verantwortlicher im Sinne der DSGVO; {a['name']} betreibt die App als Auftragsverarbeiter (Art. 28 DSGVO). Firmen erhalten auf Anfrage einen Auftragsverarbeitungsvertrag.</p>
<h2>3. Welche Daten verarbeitet werden</h2>
<ul>
<li><strong>Konto:</strong> Name, E-Mail-Adresse, Rolle, Passwort (nur als Hash), Personalnummer, optional Telefon.</li>
<li><strong>Zeiterfassung:</strong> Beginn, Ende, Pausen, Projekt, Tätigkeit, Leistung; bei Nutzung der Stempeluhr Zeitpunkte des Ein- und Ausstempelns.</li>
<li><strong>Standort (freiwillig):</strong> Nur wenn der Nutzer „Standort mitspeichern“ einschaltet, wird beim Ein- und Ausstempeln die Position gespeichert. Ohne Zustimmung wird kein Standort erfasst; die Funktion lässt sich jederzeit abschalten.</li>
<li><strong>Fotos und Dateien (freiwillig):</strong> Fotos und Dokumente, die Nutzer in Projekt- oder Personalakten hochladen.</li>
<li><strong>Abwesenheiten, Stundenkonten, Urlaubskonten</strong> sowie Unterschriften von Auftraggebern auf Stundenzetteln.</li>
<li><strong>Protokoll:</strong> Wer wann welche Daten geändert hat (Nachweispflichten).</li>
<li><strong>Technisch:</strong> IP-Adresse und Zeitpunkt von Anfragen in Server-Logs (kurzfristig, zur Fehlersuche und Absicherung).</li>
</ul>
<h2>4. Zwecke und Rechtsgrundlagen</h2>
<ul>
<li>Erfüllung des Nutzungsvertrags mit der Firma (Art. 6 Abs. 1 lit. b DSGVO).</li>
<li>Gesetzliche Aufzeichnungspflichten des Arbeitgebers, insbesondere § 17 Mindestlohngesetz und § 16 Arbeitszeitgesetz (Art. 6 Abs. 1 lit. c DSGVO, § 26 BDSG).</li>
<li>Standort und Fotos: Einwilligung des Nutzers (Art. 6 Abs. 1 lit. a DSGVO), jederzeit widerrufbar.</li>
<li>Sicherheit und Fehlersuche: berechtigtes Interesse (Art. 6 Abs. 1 lit. f DSGVO).</li>
</ul>
<h2>5. Speicherdauer</h2>
<p>Arbeitszeitaufzeichnungen bewahrt der Arbeitgeber mindestens zwei Jahre auf (§ 17 MiLoG), Rechnungen zehn Jahre (§ 147 AO). Konten werden auf Wunsch gelöscht beziehungsweise anonymisiert (siehe Punkt 8); gesetzlich aufzubewahrende Aufzeichnungen bleiben beim Arbeitgeber erhalten. Server-Logs werden nach spätestens 14 Tagen gelöscht.</p>
<h2>6. Wo die Daten liegen, Weitergabe</h2>
<p>Die Daten werden auf Servern in Deutschland gespeichert. Eine Weitergabe an Dritte findet nur statt, wenn die Firma dies selbst einrichtet (zum Beispiel Exporte an das Lohnbüro, API-Schlüssel oder Webhooks an von der Firma gewählte Systeme). Es werden keine Werbe- oder Tracking-Dienste eingesetzt; die App enthält keine Werbung.</p>
<h2>7. Berechtigungen der App</h2>
<ul>
<li><strong>Standort:</strong> nur für die freiwillige Standortspeicherung beim Stempeln.</li>
<li><strong>Kamera/Fotos:</strong> nur zum Hochladen von Fotos in Akten.</li>
<li><strong>Mikrofon:</strong> nur für die freiwillige Spracheingabe von Tätigkeitstexten (sofern vom Gerät unterstützt).</li>
<li><strong>Internet:</strong> Verbindung zum Server der Firma.</li>
</ul>
<h2>8. Rechte der Nutzer, Kontolöschung</h2>
<p>Nutzer haben die Rechte auf Auskunft, Berichtigung, Löschung, Einschränkung, Datenübertragbarkeit und Widerspruch (Art. 15 bis 21 DSGVO) sowie das Recht auf Beschwerde bei einer Datenschutz-Aufsichtsbehörde.</p>
<p><strong>Konto in der App löschen:</strong> Unter „Profil → Konto löschen“ (Mitarbeiter) beziehungsweise „Firma → Lizenz → Firma und alle Daten löschen“ (Inhaber). Beim Löschen eines Mitarbeiterkontos werden Anmeldedaten, E-Mail, Telefon und Notizen entfernt; Zeitaufzeichnungen bleiben wegen der gesetzlichen Aufbewahrung beim Arbeitgeber, bis dieser sie löscht. Beim Löschen der Firma werden alle Daten der Firma unwiderruflich entfernt.</p>
<h2>9. Kontakt</h2>
<p>Fragen zum Datenschutz: <a href="mailto:{a['email']}">{a['email']}</a></p>
<p><a href="/impressum">Impressum</a></p>
""")
