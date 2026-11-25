"""Einteilung per Sprache – Fehler aus dem Satz-Test vom 25.11.2026 (echte Chef-Sätze gegen den Demo-Server):
„7-16“, „16 bis 7“, „Hauptstraße 5 morgen“, „in zwei Wochen“, „KW 50“, „am Wochenende“, „Dach“ für „Dachsanierung“."""
from datetime import date, timedelta

import pytest

import sprachplanung as sp

MI = date(2026, 11, 25)    # Mittwoch
SA = date(2026, 11, 28)
NAMEN = ["Karl Chef", "Nils Becker", "Nils Wagner", "Tom Wagner"]
PROJEKTE = [{"name": "Badsanierung Müller", "address": "Hauptstraße 5, 30159 Hannover"},
            {"name": "Dachsanierung Schmidt", "address": "Lindenweg 12, 30655 Hannover"}]


def iso(*tage):
    return [d.isoformat() for d in tage]


def woche(montag, n=5):
    return [(montag + timedelta(days=i)).isoformat() for i in range(n)]


# ---------------------------------------------------------------- Uhrzeit mit Bindestrich und Nachtschicht

@pytest.mark.parametrize("satz, start, ende", [
    ("Karl morgen 7-16 Müller", "07:00", "16:00"),
    ("Karl morgen 7 - 16 Uhr Müller", "07:00", "16:00"),
    ("Karl morgen 6:30-15:30 Müller", "06:30", "15:30"),
    ("Karl morgen 7-4 Müller", "07:00", "16:00"),          # wie „sieben bis vier“
])
def test_01_uhrzeit_mit_bindestrich(satz, start, ende):
    f = sp.regeln_zerlegen(satz, NAMEN, PROJEKTE)
    assert (f["startzeit"], f["endzeit"]) == (start, ende)
    assert f["mitarbeiter"] == ["Karl"] and f["zeitraum"] == "morgen"


def test_01b_bindestrich_im_datum_ist_keine_uhrzeit():
    f = sp.regeln_zerlegen("Tom 30.11.-4.12. bei Schmidt", NAMEN, PROJEKTE)
    assert f["startzeit"] is None and f["endzeit"] is None
    assert sp.tage_berechnen(f["zeitraum"], MI)[0] == woche(date(2026, 11, 30))


def test_02_ende_vor_beginn_bleibt_nachtschicht():
    # früher wurde aus „16 bis 7“ still 16–19 Uhr
    assert sp.zeiten_ordnen("16:00", "07:00") == ("16:00", "07:00")
    assert sp.zeiten_ordnen("13:00", "05:00") == ("13:00", "05:00")
    assert sp.zeiten_ordnen("07:00", "04:00") == ("07:00", "16:00")      # vormittags begonnen: Nachmittag gemeint
    assert sp.zeiten_ordnen("09:00", "05:00") == ("09:00", "17:00")
    f = sp.regeln_zerlegen("Nils Becker morgen von 16 bis 7 Uhr Müller", NAMEN, PROJEKTE)
    assert (f["startzeit"], f["endzeit"]) == ("16:00", "07:00")


# ---------------------------------------------------------------- Standort mit Hausnummer

@pytest.mark.parametrize("satz, standort", [
    ("Tom Hauptstraße 5 morgen 7 bis 16", "Hauptstraße 5"),       # früher „Hauptstraße 5 m“
    ("Tom Hauptstraße 5a morgen", "Hauptstraße 5a"),
    ("Tom Hauptstraße 5 a morgen", "Hauptstraße 5 a"),
    ("Tom morgen Lindenweg 12", "Lindenweg 12"),
])
def test_03_standort_hausnummer(satz, standort):
    assert sp.regeln_zerlegen(satz, NAMEN, PROJEKTE)["standort"] == standort


def test_03b_projekt_ueber_adresse_mit_hausnummer():
    f = sp.regeln_zerlegen("Tom Hauptstraße 5 morgen 7 bis 16", NAMEN, PROJEKTE)
    assert [p["name"] for p in sp.projekt_finden(f["projekt"], f["standort"], PROJEKTE)] == ["Badsanierung Müller"]


# ---------------------------------------------------------------- Zeiträume

@pytest.mark.parametrize("zeitraum, heute, erwartet", [
    ("in zwei wochen montag", MI, iso(date(2026, 12, 7))),
    ("in einer woche freitag", MI, iso(date(2026, 12, 4))),
    ("in zwei wochen", MI, woche(date(2026, 12, 7))),
    ("kw 50", MI, woche(date(2026, 12, 7))),
    ("kalenderwoche 49 dienstag", MI, iso(date(2026, 12, 1))),
    ("kw 2", MI, woche(date(2027, 1, 11))),                  # KW 2 schon vorbei → nächstes Jahr
    ("kw 48", MI, iso(MI, date(2026, 11, 26), date(2026, 11, 27))),   # diese Woche: ab heute
    ("kw 50 montag bis mittwoch", MI, woche(date(2026, 12, 7), 3)),
    ("am wochenende", MI, iso(SA, date(2026, 11, 29))),
    ("naechstes wochenende", MI, iso(SA, date(2026, 11, 29))),
    ("wochenende", date(2026, 11, 29), iso(date(2026, 11, 29))),   # Sonntag: nur noch heute
    ("naechste woche wochenende", MI, iso(date(2026, 12, 5), date(2026, 12, 6))),
])
def test_04_zeitraeume(zeitraum, heute, erwartet):
    assert sp.tage_berechnen(zeitraum, heute)[0] == erwartet


def test_04b_unbekannte_kalenderwoche():
    tage, hinweise = sp.tage_berechnen("kw 60", MI)
    assert tage == [] and "Kalenderwoche 60" in hinweise[0]


@pytest.mark.parametrize("satz, zeitraum", [
    ("Nils Becker in zwei Wochen Montag Müller", "in zwei wochen montag"),
    ("Nils Becker KW 50 Müller", "kw 50"),
    ("Teile Tom Wagner am Wochenende bei Müller ein", "am wochenende"),
])
def test_04c_zeitraum_aus_dem_satz(satz, zeitraum):
    assert sp.regeln_zerlegen(satz, NAMEN, PROJEKTE)["zeitraum"] == zeitraum


# ---------------------------------------------------------------- Projekt über Wortanfang

def test_05_projekt_wortanfang():
    f = sp.regeln_zerlegen("Becker Dach morgen", NAMEN, PROJEKTE)
    assert f["projekt"] == "Dach" and f["mitarbeiter"] == ["Becker"]
    assert [p["name"] for p in sp.projekt_finden("Dach", None, PROJEKTE)] == ["Dachsanierung Schmidt"]
    # drei Buchstaben reichen nicht (zu viele Zufallstreffer)
    assert sp.projekt_finden("Bad", None, PROJEKTE) == []


def test_05b_mitarbeitername_wird_kein_projekt():
    projekte = [{"name": "Tomatenhaus Umbau"}]
    f = sp.regeln_zerlegen("Tomas morgen Umbau", ["Tomas Klein"], projekte)
    assert f["mitarbeiter"] == ["Tomas"] and f["projekt"] == "Umbau"


# ---------------------------------------------------------------- ganzer Vorschlag über die Route

def test_06_vorschlag_route_neue_saetze(client, monkeypatch):
    from test_sprachplanung_20261124 import _aufbau, _vorschlag
    s = _aufbau(client, monkeypatch)
    v = _vorschlag(client, s["chef"], text="Tom Wagner morgen von 16 bis 7 Uhr Dachsanierung Schmidt")
    assert (v["start_time"], v["end_time"]) == ("16:00", "07:00")
    assert {"startzeit", "endzeit"} <= set(v["unsicher"]) and any("Nachtschicht" in h for h in v["hinweise"])
    v = _vorschlag(client, s["chef"], text="Tom Hauptstraße 5 morgen 7 bis 16")
    assert v["projekt"]["id"] == s["m"]["id"] and v["adresse"] == "Hauptstraße 5, 30159 Hannover" and v["entwurf"]
    v = _vorschlag(client, s["chef"], text="Tom Wagner am Wochenende bei Müller")
    assert len(v["tage"]) in (1, 2) and all(k["art"] in ("wochenende", "feiertag") for k in v["konflikte"]) and v["konflikte"]
