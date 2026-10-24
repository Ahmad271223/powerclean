"""KI-Entwürfe (Stufe H, optional, Feature-Flag `ki`, Standard aus).

Grundsatz: Die KI liefert nur Vorschläge als Text/JSON. Nichts wird gespeichert, bis ein Mensch den Vorschlag in der Oberfläche prüft und
ausdrücklich übernimmt. Eingaben werden nicht protokolliert (nur Längen und Dauer), Preise und Kundendaten verlassen die Firma nur in dem Text,
den der Nutzer bewusst eingibt. Zugang: Anthropic-Schlüssel `ANTHROPIC_API_KEY` (nie im Code, nie in der Antwort), Modell `KI_MODELL`
(Standard claude-opus-5-5). Ohne Schlüssel oder ohne Paket `anthropic` antwortet das Modul mit 503 und Klartext.
"""
from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Optional

from fastapi import HTTPException

MODELL = os.environ.get("KI_MODELL", "claude-opus-5-5")
MAX_ZEICHEN = 20000
EINHEITEN = ("Stk.", "Stück", "m", "m²", "m³", "h", "Std.", "psch", "pauschal", "kg", "t", "l", "lfm", "Tag", "Monat")

ANGEBOT_ANWEISUNG = (
    "Du hilfst einem deutschen Handwerks- oder Reinigungsbetrieb, aus einer formlosen Beschreibung einen Angebotsentwurf zu machen. "
    "Antworte ausschließlich mit einem JSON-Objekt (ohne Markdown): {\"positionen\": [...], \"hinweise\": [...]}. "
    "Jede Position: {\"art\": \"titel|leistung|stunden|material|pauschal|text\", \"text\": \"kurz\", \"beschreibung\": \"optional\", "
    "\"menge\": Zahl, \"einheit\": \"Stk.|m|m²|m³|h|psch|kg|lfm\", \"einzelpreis\": Zahl oder null, \"unsicher\": true|false}. "
    "Erfinde keine Preise: einzelpreis nur, wenn er in der Beschreibung steht oder die Firmendaten ihn liefern, sonst null und unsicher=true. "
    "Nutze die Stundensätze oder Artikelpreise aus den Firmendaten, wenn sie passen. Mengen, die nicht genannt sind, als 1 mit unsicher=true. "
    "In hinweise: was der Mensch prüfen muss (fehlende Maße, Annahmen, Nachträge). Deutsch, nüchtern, keine Marketingtexte."
)
BELEG_ANWEISUNG = (
    "Du liest den Text einer Eingangsrechnung (Lieferantenrechnung) für einen deutschen Betrieb aus. Antworte ausschließlich mit einem JSON-Objekt "
    "(ohne Markdown): {\"lieferant\": str|null, \"lieferant_ustid\": str|null, \"rechnungsnummer\": str|null, \"rechnungsdatum\": \"YYYY-MM-DD\"|null, "
    "\"faellig_am\": \"YYYY-MM-DD\"|null, \"netto\": Zahl|null, \"ust\": Zahl|null, \"brutto\": Zahl|null, \"waehrung\": str|null, "
    "\"positionen\": [{\"text\": str, \"menge\": Zahl|null, \"einheit\": str|null, \"betrag\": Zahl|null}], \"hinweise\": [str]}. "
    "Beträge als Zahl mit Punkt. Was nicht eindeutig im Text steht, bleibt null – nichts raten. Prüfe netto + ust = brutto und nenne Abweichungen in hinweise."
)


def eingerichtet() -> dict:
    """Ob das Modul benutzbar ist – ohne den Schlüssel preiszugeben."""
    schluessel = bool(os.environ.get("ANTHROPIC_API_KEY"))
    try:
        import anthropic  # noqa: F401
        paket = True
    except ImportError:
        paket = False
    return {"schluessel": schluessel, "paket": paket, "modell": MODELL, "bereit": schluessel and paket}


def anfragen(anweisung: str, text: str) -> str:
    """Eine Anfrage an Claude; liefert den Antworttext. Tests ersetzen diese Funktion (kein Netz in Tests)."""
    import anthropic
    client = anthropic.Anthropic(timeout=120.0, max_retries=1)
    try:
        antwort = client.beta.messages.create(
            model=MODELL, max_tokens=16000, system=anweisung, messages=[{"role": "user", "content": text}],
            betas=["server-side-fallback-2026-07-01"], fallbacks="default",   # lehnt das Modell ab, übernimmt ein Ersatzmodell innerhalb derselben Anfrage
            output_config={"effort": "medium"},
        )
    except anthropic.AuthenticationError as exc:
        raise HTTPException(503, "Der KI-Schlüssel wird vom Anbieter abgelehnt. Bitte ANTHROPIC_API_KEY prüfen.") from exc
    except anthropic.RateLimitError as exc:
        raise HTTPException(503, "Der KI-Anbieter ist gerade ausgelastet (Rate-Limit). Bitte in einer Minute noch einmal versuchen.") from exc
    except anthropic.APIStatusError as exc:
        raise HTTPException(503, f"Der KI-Anbieter hat die Anfrage abgelehnt ({exc.status_code}).") from exc
    except anthropic.APIConnectionError as exc:
        raise HTTPException(503, "Keine Verbindung zum KI-Anbieter.") from exc
    if antwort.stop_reason == "refusal":
        raise HTTPException(422, "Die KI hat diese Anfrage abgelehnt. Bitte den Text prüfen oder den Entwurf von Hand anlegen.")
    return "".join(b.text for b in antwort.content if b.type == "text")


def _json_aus_text(roh: str) -> dict:
    s = (roh or "").strip()
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s, flags=re.S)
    anfang, ende = s.find("{"), s.rfind("}")
    if anfang < 0 or ende < 0:
        raise HTTPException(502, "Die KI-Antwort war kein lesbarer Entwurf. Bitte noch einmal versuchen.")
    try:
        daten = json.loads(s[anfang:ende + 1])
    except json.JSONDecodeError as exc:
        raise HTTPException(502, "Die KI-Antwort war kein lesbares JSON. Bitte noch einmal versuchen.") from exc
    if not isinstance(daten, dict):
        raise HTTPException(502, "Die KI-Antwort hatte eine unerwartete Form.")
    return daten


def _zahl(x: Any) -> Optional[float]:
    """Zahl aus JSON oder deutschem Text („1.000,00“, „38,5“, „1190“)."""
    if x is None or x == "":
        return None
    if isinstance(x, (int, float)) and not isinstance(x, bool):
        return round(float(x), 4)
    s = str(x).strip().replace(" ", "").replace("€", "")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    elif re.fullmatch(r"-?\d{1,3}(\.\d{3})+", s):
        s = s.replace(".", "")
    try:
        return round(float(s), 4)
    except (TypeError, ValueError):
        return None


def _text(x: Any, laenge: int) -> str:
    return str(x if x is not None else "").strip()[:laenge]


def _vorbereiten(text: str) -> str:
    text = (text or "").strip()
    if not text:
        raise HTTPException(400, "Bitte einen Text eingeben.")
    if len(text) > MAX_ZEICHEN:
        raise HTTPException(400, f"Der Text ist zu lang (max. {MAX_ZEICHEN} Zeichen).")
    return text


def _bereit_pruefen() -> None:
    st = eingerichtet()
    if not st["paket"]:
        raise HTTPException(503, "Das Paket `anthropic` ist auf dem Server nicht installiert (pip install anthropic).")
    if not st["schluessel"]:
        raise HTTPException(503, "Für KI-Entwürfe fehlt der Schlüssel ANTHROPIC_API_KEY in der Umgebung des Servers.")


def angebot_entwurf(text: str, firma: dict, artikel: list[dict], leistungen: list[dict]) -> dict:
    """Positionen aus einer Beschreibung – als geprüfte, aber ungespeicherte Vorschlagsliste."""
    text = _vorbereiten(text)
    _bereit_pruefen()
    kalk = firma.get("kalkulation") or {}
    kontext = {"firma": firma.get("name"), "stundensatz_vk": kalk.get("stundensatz"),
               "leistungen": [{"text": l.get("name"), "stundensatz": l.get("hourly_rate")} for l in leistungen[:60]],
               "artikel": [{"name": a.get("name"), "einheit": a.get("einheit"), "verkaufspreis": a.get("verkaufspreis")} for a in artikel[:120]]}
    start = time.monotonic()
    roh = anfragen(ANGEBOT_ANWEISUNG, f"Firmendaten (JSON): {json.dumps(kontext, ensure_ascii=False)}\n\nBeschreibung des Auftrags:\n{text}")
    daten = _json_aus_text(roh)
    positionen = []
    for p in (daten.get("positionen") or [])[:200]:
        if not isinstance(p, dict):
            continue
        art = p.get("art") if p.get("art") in ("titel", "leistung", "stunden", "material", "pauschal", "text") else "leistung"
        einheit = _text(p.get("einheit"), 20) or ("h" if art == "stunden" else "Stk.")
        positionen.append({"art": art, "text": _text(p.get("text"), 300) or "Position", "beschreibung": _text(p.get("beschreibung"), 2000),
                           "menge": _zahl(p.get("menge")) if art not in ("titel", "text") else 0, "einheit": einheit, "einzelpreis": _zahl(p.get("einzelpreis")),
                           "unsicher": bool(p.get("unsicher")) or _zahl(p.get("einzelpreis")) is None and art not in ("titel", "text")})
    return {"positionen": positionen, "hinweise": [_text(h, 300) for h in (daten.get("hinweise") or [])[:20] if isinstance(h, str) and _text(h, 300)],
            "modell": MODELL, "dauer_s": round(time.monotonic() - start, 1),
            "hinweis": "KI-Entwurf – nichts ist gespeichert. Preise und Mengen prüfen, dann „Positionen übernehmen“."}


def beleg_vorschlag(text: str) -> dict:
    """Felder einer Eingangsrechnung aus Text (z. B. OCR) – als Vorschlag zum Vorausfüllen."""
    text = _vorbereiten(text)
    _bereit_pruefen()
    start = time.monotonic()
    daten = _json_aus_text(anfragen(BELEG_ANWEISUNG, text))
    datum = lambda v: v if isinstance(v, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", v) else None  # noqa: E731
    vorschlag = {"lieferant": _text(daten.get("lieferant"), 160) or None, "lieferant_ustid": _text(daten.get("lieferant_ustid"), 20) or None,
                 "rechnungsnummer": _text(daten.get("rechnungsnummer"), 60) or None, "rechnungsdatum": datum(daten.get("rechnungsdatum")), "faellig_am": datum(daten.get("faellig_am")),
                 "netto": _zahl(daten.get("netto")), "ust": _zahl(daten.get("ust")), "brutto": _zahl(daten.get("brutto")), "waehrung": _text(daten.get("waehrung"), 3) or None,
                 "positionen": [{"text": _text(p.get("text"), 200), "menge": _zahl(p.get("menge")), "einheit": _text(p.get("einheit"), 20), "betrag": _zahl(p.get("betrag"))}
                                for p in (daten.get("positionen") or [])[:100] if isinstance(p, dict)]}
    hinweise = [_text(h, 300) for h in (daten.get("hinweise") or [])[:20] if isinstance(h, str) and _text(h, 300)]
    if vorschlag["netto"] is not None and vorschlag["ust"] is not None and vorschlag["brutto"] is not None and abs(vorschlag["netto"] + vorschlag["ust"] - vorschlag["brutto"]) > 0.02:
        hinweise.append("Netto + USt ergibt nicht den Bruttobetrag – Beträge prüfen.")
    return {"vorschlag": vorschlag, "hinweise": hinweise, "modell": MODELL, "dauer_s": round(time.monotonic() - start, 1),
            "hinweis": "KI-Vorschlag – nichts ist gespeichert. Alle Felder gegen den Beleg prüfen."}
