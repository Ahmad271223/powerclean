"""
Stundenzettel & Rechnungen (Timesheets & Invoices)

Router for the project based timesheet app:
  * Firmen (own companies)         -> ts_companies   (logo, address, bank, invoice settings)
  * Projekte (projects)            -> ts_projects    (belong to one company)
  * Einträge (work entries)        -> ts_entries
  * Rechnungen (invoice numbers)   -> ts_invoices    (own number sequence per company)

PDFs (weekly Stundenzettel, monthly bundle + Rechnung) are generated on demand
with reportlab, so they always reflect the current entries. Every PDF carries the
company logo (top left) and the company data next to it.
"""
from __future__ import annotations

import base64
import html
import io
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    Image as RLImage,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

MIN_DATE = date(2025, 1, 1)
# always at least ten years ahead of today
MAX_DATE = date(max(2035, date.today().year + 10), 12, 31)
MAX_LOGO_BYTES = 2 * 1024 * 1024
RED = colors.HexColor("#C41E3A")
BLACK = colors.HexColor("#0A0A0A")
GREY = colors.HexColor("#71717A")
LIGHT = colors.HexColor("#F4F4F5")
BORDER = colors.HexColor("#A1A1AA")

WEEKDAYS_DE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
MONTHS_DE = [
    "", "Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
    "August", "September", "Oktober", "November", "Dezember",
]


# ============= MODELS =============

class CompanyCreate(BaseModel):
    name: str = ""
    owner: str = ""
    street: str = ""
    zip_code: str = ""
    city: str = ""
    phone: str = ""
    email: str = ""
    website: str = ""
    tax_number: str = ""
    vat_id: str = ""
    bank_name: str = ""
    iban: str = ""
    bic: str = ""
    default_hourly_rate: float = 0.0
    vat_rate: float = 19.0
    small_business: bool = False  # §19 UStG Kleinunternehmer -> keine USt.
    invoice_prefix: str = "RE-"
    payment_days: int = 14
    invoice_text: str = "Reinigungsarbeiten laut beiliegenden Stundenzetteln"


class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    owner: Optional[str] = None
    street: Optional[str] = None
    zip_code: Optional[str] = None
    city: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    tax_number: Optional[str] = None
    vat_id: Optional[str] = None
    bank_name: Optional[str] = None
    iban: Optional[str] = None
    bic: Optional[str] = None
    default_hourly_rate: Optional[float] = None
    vat_rate: Optional[float] = None
    small_business: Optional[bool] = None
    invoice_prefix: Optional[str] = None
    payment_days: Optional[int] = None
    invoice_text: Optional[str] = None


class LogoUpload(BaseModel):
    data_url: str  # data:image/png;base64,....


class ProjectCreate(BaseModel):
    company_id: str
    name: str
    customer_name: str = ""
    customer_address: str = ""
    employee_name: str = ""
    hourly_rate: float = 0.0
    color: str = "#C41E3A"
    notes: str = ""


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    customer_name: Optional[str] = None
    customer_address: Optional[str] = None
    employee_name: Optional[str] = None
    hourly_rate: Optional[float] = None
    color: Optional[str] = None
    notes: Optional[str] = None


class EntryCreate(BaseModel):
    project_id: str
    date: str  # YYYY-MM-DD
    activity: str = ""
    start_time: str  # HH:MM
    end_time: str  # HH:MM
    pause_minutes: int = 0

    @field_validator("date")
    @classmethod
    def _check_date(cls, v: str) -> str:
        try:
            d = date.fromisoformat(v)
        except (TypeError, ValueError):
            raise ValueError("Ungültiges Datum (YYYY-MM-DD)")
        if d < MIN_DATE or d > MAX_DATE:
            raise ValueError(f"Datum muss zwischen {MIN_DATE.year} und {MAX_DATE.year} liegen")
        return v

    @field_validator("start_time", "end_time")
    @classmethod
    def _check_time(cls, v: str) -> str:
        parse_time(v)
        return v

    @field_validator("pause_minutes")
    @classmethod
    def _check_pause(cls, v: int) -> int:
        if v < 0 or v > 24 * 60:
            raise ValueError("Pause ungültig")
        return v


class EntryUpdate(BaseModel):
    date: Optional[str] = None
    activity: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    pause_minutes: Optional[int] = None


# ============= HELPERS =============

def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Ungültiges Datum (YYYY-MM-DD)")


def parse_time(value: str) -> int:
    """'HH:MM' -> minutes since midnight."""
    try:
        h, m = value.split(":")
        h, m = int(h), int(m)
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError
        return h * 60 + m
    except (AttributeError, ValueError):
        raise ValueError("Uhrzeit muss im Format HH:MM sein")


def net_minutes(start_time: str, end_time: str, pause_minutes: int) -> int:
    start = parse_time(start_time)
    end = parse_time(end_time)
    if end < start:  # over midnight
        end += 24 * 60
    return max(0, end - start - int(pause_minutes or 0))


def fmt_hours(minutes: int) -> str:
    """Minutes -> '7:30 h'."""
    return f"{minutes // 60}:{minutes % 60:02d} h"


def fmt_decimal(value: float, digits: int = 2) -> str:
    """German number format 1.234,56"""
    s = f"{value:,.{digits}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_eur(value: float) -> str:
    return f"{fmt_decimal(value)} €"


def fmt_date(d: date) -> str:
    return d.strftime("%d.%m.%Y")


def week_monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def month_last_day(year: int, month: int) -> date:
    return date(year + (month // 12), (month % 12) + 1, 1) - timedelta(days=1)


def month_weeks(year: int, month: int) -> List[date]:
    """Mondays of all ISO weeks that overlap the month, ascending."""
    first = date(year, month, 1)
    last = month_last_day(year, month)
    mondays = []
    cur = week_monday(first)
    while cur <= last:
        mondays.append(cur)
        cur += timedelta(days=7)
    return mondays


def esc(text: str) -> str:
    return html.escape(text or "").replace("\n", "<br/>")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def decode_logo(data_url: str) -> tuple[bytes, str]:
    """'data:image/png;base64,...' -> (bytes, mime). Raises HTTPException on bad input."""
    try:
        header, payload = data_url.split(",", 1)
        mime = header[5:].split(";")[0].lower()
        if mime not in ("image/png", "image/jpeg"):
            raise ValueError("Nur PNG oder JPG")
        raw = base64.b64decode(payload, validate=True)
    except (ValueError, IndexError) as exc:
        raise HTTPException(status_code=400, detail=f"Ungültiges Logo: {exc}")
    if len(raw) > MAX_LOGO_BYTES:
        raise HTTPException(status_code=400, detail="Logo ist zu groß (max. 2 MB)")
    try:
        ImageReader(io.BytesIO(raw)).getSize()
    except Exception:
        raise HTTPException(status_code=400, detail="Logo konnte nicht gelesen werden")
    return raw, mime


def company_rate(project: dict, company: dict) -> float:
    return float(project.get("hourly_rate") or 0) or float(company.get("default_hourly_rate") or 0)


def compute_invoice(project: dict, company: dict, year: int, month: int, entries: List[dict]) -> dict:
    """Positions + totals of a monthly invoice (only days inside the month)."""
    first = date(year, month, 1)
    last = month_last_day(year, month)
    rate = company_rate(project, company)
    positions = []
    total_minutes = 0
    for monday in month_weeks(year, month):
        sunday = monday + timedelta(days=6)
        lo, hi = max(monday, first), min(sunday, last)
        minutes = sum(int(e.get("net_minutes", 0)) for e in entries if lo.isoformat() <= e["date"] <= hi.isoformat())
        if minutes == 0:
            continue
        total_minutes += minutes
        positions.append({
            "week": monday.isocalendar()[1],
            "from": lo, "to": hi,
            "minutes": minutes,
            "hours": minutes / 60,
            "amount": round(minutes / 60 * rate, 2),
        })
    net = round(total_minutes / 60 * rate, 2)
    vat_rate = 0.0 if company.get("small_business") else float(company.get("vat_rate") or 0)
    vat = round(net * vat_rate / 100, 2)
    return {
        "rate": rate, "positions": positions, "total_minutes": total_minutes,
        "net": net, "vat_rate": vat_rate, "vat": vat, "gross": round(net + vat, 2),
    }


# ============= PDF BUILDING =============

_styles = getSampleStyleSheet()
STYLE_BODY = ParagraphStyle("ts_body", parent=_styles["Normal"], fontName="Helvetica", fontSize=9, leading=11, textColor=BLACK)
STYLE_SMALL = ParagraphStyle("ts_small", parent=STYLE_BODY, fontSize=7.5, leading=9, textColor=GREY)
STYLE_CELL = ParagraphStyle("ts_cell", parent=STYLE_BODY, fontSize=8.5, leading=10.5)
STYLE_CELL_CENTER = ParagraphStyle("ts_cell_c", parent=STYLE_CELL, alignment=TA_CENTER)
STYLE_CELL_RIGHT = ParagraphStyle("ts_cell_r", parent=STYLE_CELL, alignment=TA_RIGHT)
STYLE_HEAD = ParagraphStyle("ts_head", parent=STYLE_BODY, fontName="Helvetica-Bold", fontSize=8.5, leading=10, textColor=colors.white, alignment=TA_CENTER)
STYLE_TITLE = ParagraphStyle("ts_title", parent=STYLE_BODY, fontName="Helvetica-Bold", fontSize=20, leading=24, textColor=BLACK, alignment=TA_RIGHT)
STYLE_BRAND = ParagraphStyle("ts_brand", parent=STYLE_BODY, fontName="Helvetica-Bold", fontSize=13, leading=16, textColor=RED)
STYLE_LABEL = ParagraphStyle("ts_label", parent=STYLE_BODY, fontSize=8, leading=10, textColor=GREY)
STYLE_LABEL_RIGHT = ParagraphStyle("ts_label_r", parent=STYLE_LABEL, alignment=TA_RIGHT)
STYLE_VALUE = ParagraphStyle("ts_value", parent=STYLE_BODY, fontName="Helvetica-Bold", fontSize=10, leading=12)
STYLE_RIGHT = ParagraphStyle("ts_right", parent=STYLE_BODY, alignment=TA_RIGHT)
STYLE_H2 = ParagraphStyle("ts_h2", parent=STYLE_BODY, fontName="Helvetica-Bold", fontSize=12, leading=15)


def company_address_line(company: dict) -> str:
    place = " ".join(p for p in [company.get("zip_code", ""), company.get("city", "")] if p)
    return " · ".join(p for p in [company.get("owner", ""), company.get("street", ""), place] if p)


def company_contact_line(company: dict) -> str:
    parts = []
    if company.get("phone"):
        parts.append(f"Tel. {company['phone']}")
    if company.get("email"):
        parts.append(company["email"])
    if company.get("website"):
        parts.append(company["website"])
    return " · ".join(parts)


def _page_footer(company: dict):
    footer_line = " · ".join(p for p in [company.get("name", ""), company_address_line(company), company_contact_line(company)] if p)

    def draw(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(BORDER)
        canvas.setLineWidth(0.4)
        canvas.line(doc.leftMargin, 14 * mm, A4[0] - doc.rightMargin, 14 * mm)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(GREY)
        canvas.drawString(doc.leftMargin, 10 * mm, footer_line[:160])
        canvas.drawRightString(A4[0] - doc.rightMargin, 10 * mm, f"Seite {doc.page}")
        canvas.restoreState()

    return draw


def _logo_flowable(company: dict, max_w=38 * mm, max_h=18 * mm):
    data_url = company.get("logo")
    if not data_url:
        return None
    try:
        raw, _ = decode_logo(data_url)
        iw, ih = ImageReader(io.BytesIO(raw)).getSize()
    except Exception:
        return None
    scale = min(max_w / iw, max_h / ih)
    img = RLImage(io.BytesIO(raw), width=iw * scale, height=ih * scale)
    img.hAlign = "LEFT"
    return img


def _header_block(company: dict, title: str, subtitle: str) -> Table:
    text = [
        Paragraph(esc(company.get("name", "")), STYLE_BRAND),
        Paragraph(esc(company_address_line(company)), STYLE_SMALL),
        Paragraph(esc(company_contact_line(company)), STYLE_SMALL),
    ]
    logo = _logo_flowable(company)
    if logo:
        left = Table([[logo, text]], colWidths=[42 * mm, 68 * mm])
        left.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (0, 0), 4 * mm),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
    else:
        left = text
    right = [
        Paragraph(esc(title), STYLE_TITLE),
        Paragraph(esc(subtitle), STYLE_LABEL_RIGHT),
    ]
    t = Table([[left, right]], colWidths=[110 * mm, 76 * mm])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, 0), 1.2, RED),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return t


def _info_grid(items: List[tuple]) -> Table:
    """items: list of (label, value) rendered as 2 columns x n rows."""
    rows = []
    for i in range(0, len(items), 2):
        pair = items[i:i + 2]
        row = []
        for label, value in pair:
            row.append([Paragraph(esc(label), STYLE_LABEL), Paragraph(esc(value) or "–", STYLE_VALUE)])
        while len(row) < 2:
            row.append("")
        rows.append(row)
    t = Table(rows, colWidths=[93 * mm, 93 * mm])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def build_week_sheet(story: list, project: dict, company: dict, monday: date, entries: List[dict]):
    """Append one weekly Stundenzettel (one page) to the story."""
    sunday = monday + timedelta(days=6)
    iso_year, iso_week, _ = monday.isocalendar()

    story.append(_header_block(company, "Stundenzettel", f"Kalenderwoche {iso_week} / {iso_year}"))
    story.append(Spacer(1, 5 * mm))
    story.append(_info_grid([
        ("Projekt / Objekt", project.get("name", "")),
        ("Auftraggeber", project.get("customer_name", "")),
        ("Mitarbeiter", project.get("employee_name", "")),
        ("Zeitraum", f"{fmt_date(monday)} – {fmt_date(sunday)}"),
    ]))
    story.append(Spacer(1, 4 * mm))

    head = ["Datum", "Tätigkeit", "Anfang", "Arbeitsende", "Netto Arbeitszeit", "Unterschrift"]
    data = [[Paragraph(h, STYLE_HEAD) for h in head]]
    row_heights = [9 * mm]

    by_day = {}
    for e in entries:
        by_day.setdefault(e["date"], []).append(e)

    total = 0
    for i in range(7):
        d = monday + timedelta(days=i)
        key = d.isoformat()
        label = f"{WEEKDAYS_DE[d.weekday()]}, {d.strftime('%d.%m.%Y')}"
        day_entries = sorted(by_day.get(key, []), key=lambda x: x["start_time"])
        if not day_entries:
            data.append([
                Paragraph(label, STYLE_CELL), Paragraph("–", STYLE_CELL_CENTER), Paragraph("–", STYLE_CELL_CENTER),
                Paragraph("–", STYLE_CELL_CENTER), Paragraph("–", STYLE_CELL_CENTER), "",
            ])
            row_heights.append(11 * mm)
            continue
        for e in day_entries:
            minutes = int(e.get("net_minutes", 0))
            total += minutes
            activity = esc(e.get("activity", ""))
            if e.get("pause_minutes"):
                activity += f'<br/><font color="#71717A" size="7">Pause: {int(e["pause_minutes"])} Min.</font>'
            data.append([
                Paragraph(label, STYLE_CELL),
                Paragraph(activity or "–", STYLE_CELL),
                Paragraph(e["start_time"], STYLE_CELL_CENTER),
                Paragraph(e["end_time"], STYLE_CELL_CENTER),
                Paragraph(fmt_hours(minutes), STYLE_CELL_CENTER),
                "",
            ])
            row_heights.append(12 * mm)

    data.append([
        "", Paragraph("<b>Gesamt Netto-Arbeitszeit</b>", STYLE_CELL_RIGHT), "", "",
        Paragraph(f"<b>{fmt_hours(total)}</b>", STYLE_CELL_CENTER),
        Paragraph(f"<b>{fmt_decimal(total / 60)} Std.</b>", STYLE_CELL_CENTER),
    ])
    row_heights.append(9 * mm)

    col_widths = [27 * mm, 56 * mm, 18 * mm, 22 * mm, 28 * mm, 35 * mm]
    t = Table(data, colWidths=col_widths, rowHeights=row_heights, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BLACK),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -2), 0.5, BORDER),
        ("BOX", (0, 0), (-1, -1), 0.8, BLACK),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, LIGHT]),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#E4E4E7")),
        ("LINEABOVE", (0, -1), (-1, -1), 1.0, BLACK),
        ("SPAN", (1, -1), (3, -1)),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t)
    story.append(Spacer(1, 14 * mm))

    sig = Table([
        ["", "", ""],
        [Paragraph("Datum / Unterschrift Mitarbeiter", STYLE_LABEL), "", Paragraph("Datum / Unterschrift Auftraggeber", STYLE_LABEL)],
    ], colWidths=[78 * mm, 30 * mm, 78 * mm], rowHeights=[12 * mm, 6 * mm])
    sig.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (0, 0), 0.8, BLACK),
        ("LINEBELOW", (2, 0), (2, 0), 0.8, BLACK),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(sig)


def build_month_overview(story: list, project: dict, company: dict, year: int, month: int, entries: List[dict]):
    story.append(_header_block(company, "Monatsübersicht", f"{MONTHS_DE[month]} {year}"))
    story.append(Spacer(1, 5 * mm))
    story.append(_info_grid([
        ("Projekt / Objekt", project.get("name", "")),
        ("Auftraggeber", project.get("customer_name", "")),
        ("Mitarbeiter", project.get("employee_name", "")),
        ("Stundensatz", fmt_eur(company_rate(project, company))),
    ]))
    story.append(Spacer(1, 4 * mm))

    data = [[Paragraph(h, STYLE_HEAD) for h in ["KW", "Zeitraum", "Arbeitstage", "Netto Arbeitszeit", "Stunden (dezimal)"]]]
    total = 0
    for monday in month_weeks(year, month):
        sunday = monday + timedelta(days=6)
        week_entries = [e for e in entries if monday.isoformat() <= e["date"] <= sunday.isoformat()]
        minutes = sum(int(e.get("net_minutes", 0)) for e in week_entries)
        days = len({e["date"] for e in week_entries})
        total += minutes
        data.append([
            Paragraph(str(monday.isocalendar()[1]), STYLE_CELL_CENTER),
            Paragraph(f"{fmt_date(monday)} – {fmt_date(sunday)}", STYLE_CELL),
            Paragraph(str(days), STYLE_CELL_CENTER),
            Paragraph(fmt_hours(minutes), STYLE_CELL_CENTER),
            Paragraph(fmt_decimal(minutes / 60), STYLE_CELL_RIGHT),
        ])
    data.append([
        "", Paragraph("<b>Gesamt im Monat</b>", STYLE_CELL), "",
        Paragraph(f"<b>{fmt_hours(total)}</b>", STYLE_CELL_CENTER),
        Paragraph(f"<b>{fmt_decimal(total / 60)}</b>", STYLE_CELL_RIGHT),
    ])
    t = Table(data, colWidths=[15 * mm, 70 * mm, 30 * mm, 40 * mm, 31 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BLACK),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, LIGHT]),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#E4E4E7")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t)
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        "Hinweis: Die Stundenzettel zeigen jeweils die komplette Kalenderwoche. "
        "Für die Monatsübersicht und die Rechnung werden nur Tage innerhalb des Monats berücksichtigt.",
        STYLE_SMALL,
    ))


def build_invoice(story: list, project: dict, company: dict, year: int, month: int,
                  entries: List[dict], invoice_number: str, invoice_date: date):
    first = date(year, month, 1)
    last = month_last_day(year, month)
    calc = compute_invoice(project, company, year, month, entries)

    story.append(_header_block(company, "Rechnung", f"Nr. {invoice_number}"))
    story.append(Spacer(1, 8 * mm))

    sender = Paragraph(esc(" · ".join(p for p in [company.get("name", ""), company_address_line(company)] if p)), STYLE_SMALL)
    recipient_lines = [project.get("customer_name", "") or "", project.get("customer_address", "") or ""]
    recipient = Paragraph("<br/>".join(esc(line) for line in recipient_lines if line) or "–", STYLE_BODY)

    meta_rows = [
        ("Rechnungsnummer", invoice_number),
        ("Rechnungsdatum", fmt_date(invoice_date)),
        ("Leistungszeitraum", f"{fmt_date(first)} – {fmt_date(last)}"),
        ("Projekt / Objekt", project.get("name", "")),
    ]
    meta = Table([[Paragraph(esc(k), STYLE_LABEL), Paragraph(esc(v), STYLE_BODY)] for k, v in meta_rows],
                 colWidths=[35 * mm, 51 * mm])
    meta.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))

    addr = Table([[[sender, Spacer(1, 3 * mm), recipient], meta]], colWidths=[100 * mm, 86 * mm])
    addr.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    story.append(addr)
    story.append(Spacer(1, 10 * mm))

    story.append(Paragraph(f"<b>Rechnung Nr. {esc(invoice_number)}</b>", STYLE_H2))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        esc(company.get("invoice_text", "")) + f" – Leistungszeitraum {MONTHS_DE[month]} {year}. "
        "Die Stundenzettel der einzelnen Kalenderwochen liegen dieser Rechnung bei.",
        STYLE_BODY,
    ))
    story.append(Spacer(1, 5 * mm))

    data = [[Paragraph(h, STYLE_HEAD) for h in ["Pos.", "Beschreibung", "Menge (Std.)", "Einzelpreis", "Gesamt"]]]
    for i, pos in enumerate(calc["positions"], start=1):
        data.append([
            Paragraph(str(i), STYLE_CELL_CENTER),
            Paragraph(f"Reinigungsarbeiten KW {pos['week']} ({fmt_date(pos['from'])} – {fmt_date(pos['to'])})", STYLE_CELL),
            Paragraph(fmt_decimal(pos["hours"]), STYLE_CELL_RIGHT),
            Paragraph(fmt_eur(calc["rate"]), STYLE_CELL_RIGHT),
            Paragraph(fmt_eur(pos["amount"]), STYLE_CELL_RIGHT),
        ])
    if not calc["positions"]:
        data.append([
            Paragraph("–", STYLE_CELL_CENTER),
            Paragraph("Keine Arbeitszeiten im Leistungszeitraum erfasst", STYLE_CELL),
            Paragraph("0,00", STYLE_CELL_RIGHT), Paragraph(fmt_eur(calc["rate"]), STYLE_CELL_RIGHT), Paragraph(fmt_eur(0), STYLE_CELL_RIGHT),
        ])

    t = Table(data, colWidths=[12 * mm, 89 * mm, 25 * mm, 28 * mm, 32 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BLACK),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t)

    vat_rate = calc["vat_rate"]
    vat_label = f"zzgl. {fmt_decimal(vat_rate, 0 if vat_rate == int(vat_rate) else 1)} % USt."
    totals = [
        [Paragraph(f"Gesamtstunden: {fmt_decimal(calc['total_minutes'] / 60)} Std.", STYLE_LABEL), Paragraph("Nettobetrag", STYLE_RIGHT), Paragraph(fmt_eur(calc["net"]), STYLE_RIGHT)],
        ["", Paragraph("Umsatzsteuer" if company.get("small_business") else vat_label, STYLE_RIGHT), Paragraph(fmt_eur(calc["vat"]), STYLE_RIGHT)],
        ["", Paragraph("<b>Rechnungsbetrag</b>", STYLE_RIGHT), Paragraph(f"<b>{fmt_eur(calc['gross'])}</b>", STYLE_RIGHT)],
    ]
    tt = Table(totals, colWidths=[101 * mm, 53 * mm, 32 * mm])
    tt.setStyle(TableStyle([
        ("LINEABOVE", (1, -1), (-1, -1), 1.0, BLACK),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(tt)
    story.append(Spacer(1, 8 * mm))

    if company.get("small_business"):
        story.append(Paragraph("Gemäß § 19 UStG wird keine Umsatzsteuer berechnet.", STYLE_BODY))
        story.append(Spacer(1, 2 * mm))

    due = invoice_date + timedelta(days=int(company.get("payment_days") or 14))
    story.append(Paragraph(
        f"Bitte überweisen Sie den Rechnungsbetrag von <b>{fmt_eur(calc['gross'])}</b> bis zum <b>{fmt_date(due)}</b> "
        f"unter Angabe der Rechnungsnummer auf das unten genannte Konto. Vielen Dank für Ihren Auftrag.",
        STYLE_BODY,
    ))
    story.append(Spacer(1, 10 * mm))

    bank_lines = [(label, company.get(key)) for label, key in [
        ("Bank", "bank_name"), ("IBAN", "iban"), ("BIC", "bic"), ("Steuernummer", "tax_number"), ("USt-IdNr.", "vat_id"),
    ] if company.get(key)]
    if bank_lines:
        story.append(_info_grid(bank_lines))
    story.append(Spacer(1, 12 * mm))
    story.append(Paragraph("Mit freundlichen Grüßen", STYLE_BODY))
    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph(esc(company.get("owner", "")), STYLE_BODY))
    story.append(Paragraph(esc(company.get("name", "")), STYLE_SMALL))


def render_pdf(story: list, company: dict, title: str) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=12 * mm, rightMargin=12 * mm, topMargin=14 * mm, bottomMargin=20 * mm,
        title=title, author=company.get("name", ""),
    )
    footer = _page_footer(company)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()


def pdf_response(data: bytes, filename: str) -> StreamingResponse:
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


def safe_filename(text: str) -> str:
    keep = "".join(c if c.isalnum() or c in "-_" else "_" for c in (text or "").strip())
    return keep[:40] or "projekt"


async def ensure_indexes(db):
    """Indexes so the timesheet collections stay fast with many projects and years of entries."""
    await db.ts_projects.create_index([("company_id", 1), ("created_at", 1)])
    await db.ts_entries.create_index([("project_id", 1), ("date", 1), ("start_time", 1)])
    await db.ts_invoices.create_index([("company_id", 1), ("year", 1), ("seq", 1)])
    await db.ts_invoices.create_index([("project_id", 1), ("year", 1), ("month", 1)])
    await db.ts_companies.create_index([("created_at", 1)])


# ============= ROUTER FACTORY =============

def create_router(db, get_admin_user) -> APIRouter:
    router = APIRouter(prefix="/ts", tags=["stundenzettel"])

    async def auth(authorization: Optional[str]):
        await get_admin_user(authorization)

    async def load_company(company_id: str) -> dict:
        company = await db.ts_companies.find_one({"id": company_id}, {"_id": 0})
        if not company:
            raise HTTPException(status_code=404, detail="Firma nicht gefunden")
        return company

    async def load_project(project_id: str) -> dict:
        project = await db.ts_projects.find_one({"id": project_id}, {"_id": 0})
        if not project:
            raise HTTPException(status_code=404, detail="Projekt nicht gefunden")
        return project

    async def load_project_with_company(project_id: str) -> tuple[dict, dict]:
        project = await load_project(project_id)
        company = await db.ts_companies.find_one({"id": project.get("company_id")}, {"_id": 0})
        if not company:
            company = CompanyCreate().model_dump()
        return project, company

    async def entries_between(project_id: str, start: date, end: date) -> List[dict]:
        cursor = db.ts_entries.find(
            {"project_id": project_id, "date": {"$gte": start.isoformat(), "$lte": end.isoformat()}},
            {"_id": 0},
        ).sort([("date", 1), ("start_time", 1)])
        return await cursor.to_list(length=None)

    async def migrate_legacy():
        """First run after the company feature: turn the old global settings into a company
        and attach existing projects / invoices to it."""
        if await db.ts_companies.count_documents({}) == 0:
            legacy = await db.ts_settings.find_one({"id": "company"}, {"_id": 0})
            has_projects = await db.ts_projects.count_documents({}) > 0
            if legacy or has_projects:
                legacy = legacy or {}
                place = (legacy.get("city") or "").strip()
                zip_code, city = "", place
                if place[:5].isdigit():
                    zip_code, _, city = place.partition(" ")
                doc = CompanyCreate(**{k: v for k, v in legacy.items() if k in CompanyCreate.model_fields and k != "city"}).model_dump()
                doc["name"] = legacy.get("company_name") or "Meine Firma"
                doc["zip_code"], doc["city"] = zip_code, city
                doc["id"] = str(uuid.uuid4())
                doc["logo"] = None
                doc["created_at"] = now_utc().isoformat()
                await db.ts_companies.insert_one(dict(doc))
        first = await db.ts_companies.find_one({}, {"_id": 0, "id": 1}, sort=[("created_at", 1)])
        if first:
            await db.ts_projects.update_many({"company_id": {"$in": [None, ""]}}, {"$set": {"company_id": first["id"]}})
            await db.ts_projects.update_many({"company_id": {"$exists": False}}, {"$set": {"company_id": first["id"]}})
            await db.ts_invoices.update_many({"company_id": {"$exists": False}}, {"$set": {"company_id": first["id"]}})

    # ---------- companies ----------

    @router.get("/companies")
    async def list_companies(authorization: str = Header(None)):
        await auth(authorization)
        await migrate_legacy()
        companies = await db.ts_companies.find({}, {"_id": 0}).sort("created_at", 1).to_list(length=None)
        counts = {c["_id"]: c["n"] async for c in db.ts_projects.aggregate([{"$group": {"_id": "$company_id", "n": {"$sum": 1}}}])}
        for c in companies:
            c["project_count"] = int(counts.get(c["id"], 0))
        return {"companies": companies}

    @router.post("/companies")
    async def create_company(input: CompanyCreate, authorization: str = Header(None)):
        await auth(authorization)
        if not input.name.strip():
            raise HTTPException(status_code=400, detail="Firmenname fehlt")
        doc = input.model_dump()
        doc["name"] = doc["name"].strip()
        doc["id"] = str(uuid.uuid4())
        doc["logo"] = None
        doc["created_at"] = now_utc().isoformat()
        await db.ts_companies.insert_one(dict(doc))
        doc["project_count"] = 0
        return doc

    @router.get("/companies/{company_id}")
    async def get_company(company_id: str, authorization: str = Header(None)):
        await auth(authorization)
        return await load_company(company_id)

    @router.patch("/companies/{company_id}")
    async def update_company(company_id: str, input: CompanyUpdate, authorization: str = Header(None)):
        await auth(authorization)
        update = {k: v for k, v in input.model_dump().items() if v is not None}
        if "name" in update and not update["name"].strip():
            raise HTTPException(status_code=400, detail="Firmenname fehlt")
        if not update:
            raise HTTPException(status_code=400, detail="Keine Daten")
        result = await db.ts_companies.update_one({"id": company_id}, {"$set": update})
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Firma nicht gefunden")
        return await load_company(company_id)

    @router.put("/companies/{company_id}/logo")
    async def upload_logo(company_id: str, input: LogoUpload, authorization: str = Header(None)):
        await auth(authorization)
        await load_company(company_id)
        decode_logo(input.data_url)
        await db.ts_companies.update_one({"id": company_id}, {"$set": {"logo": input.data_url}})
        return {"message": "Logo gespeichert"}

    @router.delete("/companies/{company_id}/logo")
    async def delete_logo(company_id: str, authorization: str = Header(None)):
        await auth(authorization)
        await load_company(company_id)
        await db.ts_companies.update_one({"id": company_id}, {"$set": {"logo": None}})
        return {"message": "Logo entfernt"}

    @router.delete("/companies/{company_id}")
    async def delete_company(company_id: str, authorization: str = Header(None)):
        """Deletes the company with ALL its projects, entries and invoices."""
        await auth(authorization)
        result = await db.ts_companies.delete_one({"id": company_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Firma nicht gefunden")
        project_ids = [p["id"] async for p in db.ts_projects.find({"company_id": company_id}, {"_id": 0, "id": 1})]
        if project_ids:
            await db.ts_entries.delete_many({"project_id": {"$in": project_ids}})
        await db.ts_projects.delete_many({"company_id": company_id})
        await db.ts_invoices.delete_many({"company_id": company_id})
        return {"message": "Firma gelöscht"}

    @router.get("/companies/{company_id}/projects")
    async def list_company_projects(company_id: str, authorization: str = Header(None)):
        await auth(authorization)
        await load_company(company_id)
        projects = await db.ts_projects.find({"company_id": company_id}, {"_id": 0}).sort("created_at", 1).to_list(length=None)
        pipeline = [{"$group": {"_id": "$project_id", "minutes": {"$sum": "$net_minutes"}, "count": {"$sum": 1}}}]
        stats = {s["_id"]: s async for s in db.ts_entries.aggregate(pipeline)}
        for p in projects:
            s = stats.get(p["id"], {})
            p["total_minutes"] = int(s.get("minutes", 0))
            p["entry_count"] = int(s.get("count", 0))
        return {"projects": projects}

    @router.get("/companies/{company_id}/invoices")
    async def list_company_invoices(company_id: str, authorization: str = Header(None)):
        """Rechnungsübersicht: every issued invoice of the company with current totals."""
        await auth(authorization)
        company = await load_company(company_id)
        invoices = await db.ts_invoices.find({"company_id": company_id}, {"_id": 0}).sort([("year", -1), ("month", -1), ("seq", -1)]).to_list(length=None)
        projects = {p["id"]: p async for p in db.ts_projects.find({"company_id": company_id}, {"_id": 0})}
        result = []
        for inv in invoices:
            project = projects.get(inv["project_id"])
            if not project:
                continue
            entries = await entries_between(project["id"], date(inv["year"], inv["month"], 1), month_last_day(inv["year"], inv["month"]))
            calc = compute_invoice(project, company, inv["year"], inv["month"], entries)
            result.append({
                **inv,
                "project_name": project["name"],
                "customer_name": project.get("customer_name", ""),
                "total_minutes": calc["total_minutes"],
                "net": calc["net"], "vat": calc["vat"], "gross": calc["gross"],
            })
        return {"invoices": result}

    # ---------- projects ----------

    @router.post("/projects")
    async def create_project(input: ProjectCreate, authorization: str = Header(None)):
        await auth(authorization)
        company = await load_company(input.company_id)
        if not input.name.strip():
            raise HTTPException(status_code=400, detail="Projektname fehlt")
        doc = input.model_dump()
        doc["name"] = doc["name"].strip()
        if not doc["hourly_rate"]:
            doc["hourly_rate"] = float(company.get("default_hourly_rate") or 0)
        doc["id"] = str(uuid.uuid4())
        doc["created_at"] = now_utc().isoformat()
        await db.ts_projects.insert_one(dict(doc))
        doc["total_minutes"] = 0
        doc["entry_count"] = 0
        return doc

    @router.get("/projects/{project_id}")
    async def get_project(project_id: str, authorization: str = Header(None)):
        await auth(authorization)
        return await load_project(project_id)

    @router.patch("/projects/{project_id}")
    async def update_project(project_id: str, input: ProjectUpdate, authorization: str = Header(None)):
        await auth(authorization)
        update = {k: v for k, v in input.model_dump().items() if v is not None}
        if "name" in update and not update["name"].strip():
            raise HTTPException(status_code=400, detail="Projektname fehlt")
        if not update:
            raise HTTPException(status_code=400, detail="Keine Daten")
        result = await db.ts_projects.update_one({"id": project_id}, {"$set": update})
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Projekt nicht gefunden")
        return await load_project(project_id)

    @router.delete("/projects/{project_id}")
    async def delete_project(project_id: str, authorization: str = Header(None)):
        await auth(authorization)
        result = await db.ts_projects.delete_one({"id": project_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Projekt nicht gefunden")
        await db.ts_entries.delete_many({"project_id": project_id})
        await db.ts_invoices.delete_many({"project_id": project_id})
        return {"message": "Projekt gelöscht"}

    # ---------- entries ----------

    @router.get("/projects/{project_id}/entries")
    async def list_entries(project_id: str, start: Optional[str] = None, end: Optional[str] = None,
                           authorization: str = Header(None)):
        await auth(authorization)
        await load_project(project_id)
        s = parse_date(start) if start else MIN_DATE
        e = parse_date(end) if end else MAX_DATE
        return {"entries": await entries_between(project_id, s, e)}

    @router.post("/entries")
    async def create_entry(input: EntryCreate, authorization: str = Header(None)):
        await auth(authorization)
        await load_project(input.project_id)
        doc = input.model_dump()
        doc["activity"] = doc["activity"].strip()
        doc["net_minutes"] = net_minutes(doc["start_time"], doc["end_time"], doc["pause_minutes"])
        doc["id"] = str(uuid.uuid4())
        doc["created_at"] = now_utc().isoformat()
        await db.ts_entries.insert_one(dict(doc))
        return doc

    @router.patch("/entries/{entry_id}")
    async def update_entry(entry_id: str, input: EntryUpdate, authorization: str = Header(None)):
        await auth(authorization)
        entry = await db.ts_entries.find_one({"id": entry_id}, {"_id": 0})
        if not entry:
            raise HTTPException(status_code=404, detail="Eintrag nicht gefunden")
        update = {k: v for k, v in input.model_dump().items() if v is not None}
        if not update:
            raise HTTPException(status_code=400, detail="Keine Daten")
        merged = {**entry, **update}
        try:
            EntryCreate(**{k: merged.get(k) for k in EntryCreate.model_fields})
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        if "activity" in update:
            update["activity"] = update["activity"].strip()
        update["net_minutes"] = net_minutes(merged["start_time"], merged["end_time"], merged.get("pause_minutes", 0))
        await db.ts_entries.update_one({"id": entry_id}, {"$set": update})
        return await db.ts_entries.find_one({"id": entry_id}, {"_id": 0})

    @router.delete("/entries/{entry_id}")
    async def delete_entry(entry_id: str, authorization: str = Header(None)):
        await auth(authorization)
        result = await db.ts_entries.delete_one({"id": entry_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Eintrag nicht gefunden")
        return {"message": "Eintrag gelöscht"}

    # ---------- invoices ----------

    async def get_or_create_invoice(project: dict, company: dict, year: int, month: int) -> dict:
        existing = await db.ts_invoices.find_one({"project_id": project["id"], "year": year, "month": month}, {"_id": 0})
        if existing:
            return existing
        # own sequence per company and year
        last = await db.ts_invoices.find({"company_id": company.get("id"), "year": year}, {"_id": 0, "seq": 1}).sort("seq", -1).limit(1).to_list(1)
        seq = (last[0]["seq"] + 1) if last else 1
        number = f"{company.get('invoice_prefix') or 'RE-'}{year}-{seq:04d}"
        doc = {
            "id": str(uuid.uuid4()),
            "company_id": company.get("id"),
            "project_id": project["id"],
            "year": year,
            "month": month,
            "seq": seq,
            "number": number,
            "invoice_date": date.today().isoformat(),
            "created_at": now_utc().isoformat(),
        }
        await db.ts_invoices.insert_one(dict(doc))
        return doc

    @router.get("/projects/{project_id}/invoices")
    async def list_invoices(project_id: str, authorization: str = Header(None)):
        await auth(authorization)
        invoices = await db.ts_invoices.find({"project_id": project_id}, {"_id": 0}).sort([("year", 1), ("month", 1)]).to_list(length=None)
        return {"invoices": invoices}

    @router.delete("/invoices/{invoice_id}")
    async def delete_invoice(invoice_id: str, authorization: str = Header(None)):
        """Removes the stored invoice number so the next PDF gets a fresh number/date."""
        await auth(authorization)
        result = await db.ts_invoices.delete_one({"id": invoice_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Rechnung nicht gefunden")
        return {"message": "Rechnungsnummer zurückgesetzt"}

    # ---------- PDFs ----------

    def check_month(year: int, month: int):
        if not (MIN_DATE.year <= year <= MAX_DATE.year) or not (1 <= month <= 12):
            raise HTTPException(status_code=400, detail=f"Monat außerhalb {MIN_DATE.year}–{MAX_DATE.year}")

    @router.get("/projects/{project_id}/pdf/week")
    async def week_pdf(project_id: str, date: str, authorization: str = Header(None)):
        await auth(authorization)
        project, company = await load_project_with_company(project_id)
        monday = week_monday(parse_date(date))
        entries = await entries_between(project_id, monday, monday + timedelta(days=6))
        story: list = []
        build_week_sheet(story, project, company, monday, entries)
        iso = monday.isocalendar()
        data = render_pdf(story, company, f"Stundenzettel KW {iso[1]} {iso[0]} – {project['name']}")
        return pdf_response(data, f"Stundenzettel_{safe_filename(project['name'])}_KW{iso[1]:02d}_{iso[0]}.pdf")

    @router.get("/projects/{project_id}/pdf/month")
    async def month_pdf(project_id: str, year: int, month: int, authorization: str = Header(None)):
        """Bundle: all weekly sheets of the month + overview + invoice."""
        await auth(authorization)
        check_month(year, month)
        project, company = await load_project_with_company(project_id)
        mondays = month_weeks(year, month)
        all_entries = await entries_between(project_id, mondays[0], mondays[-1] + timedelta(days=6))
        first = date(year, month, 1)
        last = month_last_day(year, month)
        month_entries = [e for e in all_entries if first.isoformat() <= e["date"] <= last.isoformat()]

        invoice = await get_or_create_invoice(project, company, year, month)
        story: list = []
        for i, monday in enumerate(mondays):
            sunday = monday + timedelta(days=6)
            week_entries = [e for e in all_entries if monday.isoformat() <= e["date"] <= sunday.isoformat()]
            if i > 0:
                story.append(PageBreak())
            build_week_sheet(story, project, company, monday, week_entries)
        story.append(PageBreak())
        build_month_overview(story, project, company, year, month, month_entries)
        story.append(PageBreak())
        build_invoice(story, project, company, year, month, month_entries, invoice["number"], date.fromisoformat(invoice["invoice_date"]))
        data = render_pdf(story, company, f"Stundenzettel & Rechnung {MONTHS_DE[month]} {year} – {project['name']}")
        return pdf_response(data, f"Monat_{year}-{month:02d}_{safe_filename(project['name'])}.pdf")

    @router.get("/projects/{project_id}/pdf/invoice")
    async def invoice_pdf(project_id: str, year: int, month: int, authorization: str = Header(None)):
        await auth(authorization)
        check_month(year, month)
        project, company = await load_project_with_company(project_id)
        entries = await entries_between(project_id, date(year, month, 1), month_last_day(year, month))
        invoice = await get_or_create_invoice(project, company, year, month)
        story: list = []
        build_invoice(story, project, company, year, month, entries, invoice["number"], date.fromisoformat(invoice["invoice_date"]))
        data = render_pdf(story, company, f"Rechnung {invoice['number']}")
        return pdf_response(data, f"Rechnung_{invoice['number']}_{safe_filename(project['name'])}.pdf")

    return router
