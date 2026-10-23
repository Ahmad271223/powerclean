/**
 * PDF documents generated on the device with jsPDF:
 *  - weekly Stundenzettel (Datum · Tätigkeit · Anfang · Arbeitsende · Netto Arbeitszeit · Unterschrift)
 *  - monthly overview
 *  - invoice
 *  - month bundle (all weekly sheets + overview + invoice)
 * Company logo top left, company data next to it, on every page.
 */
import { jsPDF } from 'jspdf';
import autoTable from 'jspdf-autotable';
import { addDays, entryMinutes, entryWorkers, fmtDate, fmtDecimal, fmtEur, fmtHours, isoWeek, monthLastDay, monthWeeks, toKey, MONTHS_DE, WEEKDAYS_DE } from './dates';
import { companyAddress } from './utils';

const RED = [196, 30, 58];
const BLACK = [10, 10, 10];
const GREY = [113, 113, 122];
const LIGHT = [244, 244, 245];
const BORDER = [161, 161, 170];
const PAGE_W = 210;
const PAGE_H = 297;
const M = 12; // margin mm
const CONTENT_W = PAGE_W - 2 * M;

const contactLine = (c) => [c.phone && `Tel. ${c.phone}`, c.email, c.website].filter(Boolean).join(' · ');
const addressLine = (c) => [c.owner, companyAddress(c)].filter(Boolean).join(' · ');
const rate = (project, company) => Number(project.hourly_rate) || Number(company.default_hourly_rate) || 0;

const logoCache = new Map();

/** Fill the size cache for logos saved without dimensions (older records). Resolves immediately otherwise. */
export function preloadLogo(company) {
  const dataUrl = company?.logo;
  if (!dataUrl || (company.logo_w && company.logo_h) || logoCache.has(dataUrl)) return Promise.resolve();
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => { logoCache.set(dataUrl, { w: img.naturalWidth, h: img.naturalHeight }); resolve(); };
    img.onerror = () => { logoCache.set(dataUrl, null); resolve(); };
    img.src = dataUrl;
  });
}

/** Logo size without any async work, so PDFs can be generated inside a tap gesture. */
function logoFor(company) {
  if (!company?.logo) return null;
  if (company.logo_w && company.logo_h) return { w: company.logo_w, h: company.logo_h };
  return logoCache.get(company.logo) || null;
}

function newDoc(title, company) {
  const doc = new jsPDF({ unit: 'mm', format: 'a4', compress: true });
  doc.setProperties({ title, author: company.name || '' });
  return doc;
}

/** Stamp image (with signature) for a document type, scaled by the company's "Größe auf dem PDF" setting. */
const STAMP_BASE = { sheet: { w: 62, h: 36 }, invoice: { w: 72, h: 44 } };
function stampFor(company, kind) {
  if (!company?.stamp || !company.stamp_w || !company.stamp_h) return null;
  if (kind === 'sheet' && company.stamp_on_sheet === false) return null;
  if (kind === 'invoice' && company.stamp_on_invoice === false) return null;
  const f = Math.min(2, Math.max(0.3, (Number(company.stamp_scale) || 100) / 100));
  const base = STAMP_BASE[kind];
  let w = base.w * f;
  let h = w * company.stamp_h / company.stamp_w;
  const maxH = base.h * f;
  if (h > maxH) { h = maxH; w = h * company.stamp_w / company.stamp_h; }
  return { dataUrl: company.stamp, w, h };
}

/** Header block: logo + company (left), title + subtitle (right). Returns y below the header. */
function header(doc, company, logo, title, subtitle) {
  let x = M;
  const top = 14;
  if (logo) {
    const scale = Math.min(38 / logo.w, 18 / logo.h);
    const w = logo.w * scale;
    const h = logo.h * scale;
    doc.addImage(company.logo, 'PNG', M, top + (18 - h) / 2, w, h);
    x = M + 42;
  }
  doc.setFont('helvetica', 'bold').setFontSize(13).setTextColor(...RED);
  doc.text(company.name || '', x, top + 6);
  doc.setFont('helvetica', 'normal').setFontSize(7.5).setTextColor(...GREY);
  doc.text(addressLine(company), x, top + 10.5);
  doc.text(contactLine(company), x, top + 14);

  doc.setFont('helvetica', 'bold').setFontSize(20).setTextColor(...BLACK);
  doc.text(title, PAGE_W - M, top + 8, { align: 'right' });
  doc.setFont('helvetica', 'normal').setFontSize(8).setTextColor(...GREY);
  doc.text(subtitle, PAGE_W - M, top + 13.5, { align: 'right' });

  doc.setDrawColor(...RED).setLineWidth(0.5);
  doc.line(M, top + 20, PAGE_W - M, top + 20);
  return top + 27;
}

function footer(doc, company) {
  const pages = doc.getNumberOfPages();
  const line = [company.name, addressLine(company), contactLine(company)].filter(Boolean).join(' · ');
  for (let p = 1; p <= pages; p++) {
    doc.setPage(p);
    doc.setDrawColor(...BORDER).setLineWidth(0.2);
    doc.line(M, PAGE_H - 14, PAGE_W - M, PAGE_H - 14);
    doc.setFont('helvetica', 'normal').setFontSize(7).setTextColor(...GREY);
    doc.text(line.slice(0, 150), M, PAGE_H - 10);
    doc.text(`Seite ${p}`, PAGE_W - M, PAGE_H - 10, { align: 'right' });
  }
}

/** Two-column label/value grid. Returns y below. */
function infoGrid(doc, y, items) {
  const colW = CONTENT_W / 2;
  for (let i = 0; i < items.length; i += 2) {
    for (let j = 0; j < 2 && i + j < items.length; j++) {
      const [label, value] = items[i + j];
      const x = M + j * colW;
      doc.setFont('helvetica', 'normal').setFontSize(8).setTextColor(...GREY);
      doc.text(label, x, y);
      doc.setFont('helvetica', 'bold').setFontSize(10).setTextColor(...BLACK);
      doc.text(String(value || '–'), x, y + 4.5);
    }
    y += 10;
  }
  return y;
}

const tableBase = {
  margin: { left: M, right: M },
  theme: 'grid',
  styles: { font: 'helvetica', fontSize: 8.5, textColor: BLACK, lineColor: BORDER, lineWidth: 0.2, cellPadding: 2, valign: 'middle' },
  headStyles: { fillColor: BLACK, textColor: 255, fontStyle: 'bold', halign: 'center', minCellHeight: 9 },
  alternateRowStyles: { fillColor: LIGHT },
};

// ---------- weekly sheet ----------
function weekSheet(doc, project, company, logo, monday, entries) {
  const sunday = addDays(monday, 6);
  const { week, year } = isoWeek(monday);
  let y = header(doc, company, logo, 'Stundenzettel', `Kalenderwoche ${week} / ${year}`);
  y = infoGrid(doc, y, [
    ['Projekt / Objekt', project.name],
    ['Auftraggeber', project.customer_name],
    ['Mitarbeiter', project.employee_name],
    ['Zeitraum', `${fmtDate(monday)} – ${fmtDate(sunday)}`],
  ]);

  const byDay = {};
  for (const e of entries) (byDay[e.date] ||= []).push(e);
  const body = [];
  let total = 0;
  for (let i = 0; i < 7; i++) {
    const d = addDays(monday, i);
    const label = `${WEEKDAYS_DE[i]}, ${fmtDate(d)}`;
    const dayEntries = (byDay[toKey(d)] || []).sort((a, b) => a.start_time.localeCompare(b.start_time));
    if (!dayEntries.length) {
      body.push([label, '–', '–', '–', '–', '–', '']);
      continue;
    }
    for (const e of dayEntries) {
      const workers = entryWorkers(e);
      const mins = entryMinutes(e);
      total += mins;
      const activity = (e.activity || '–') + (e.pause_minutes ? `\nPause: ${e.pause_minutes} Min.` : '');
      const netto = workers > 1 ? `${fmtHours(mins)}\n${workers} × ${fmtHours(e.net_minutes || 0)}` : fmtHours(e.net_minutes || 0);
      body.push([label, activity, e.start_time, e.end_time, String(workers), netto, '']);
    }
  }
  body.push([{ content: '', styles: { fillColor: [228, 228, 231] } },
    { content: 'Gesamt Netto-Arbeitszeit', colSpan: 4, styles: { halign: 'right', fontStyle: 'bold', fillColor: [228, 228, 231] } },
    { content: fmtHours(total), styles: { fontStyle: 'bold', fillColor: [228, 228, 231] } },
    { content: `${fmtDecimal(total / 60)} Std.`, styles: { fontStyle: 'bold', fillColor: [228, 228, 231] } }]);

  autoTable(doc, {
    ...tableBase,
    startY: y,
    head: [['Datum', 'Tätigkeit', 'Anfang', 'Arbeitsende', 'Anzahl', 'Netto Arbeitszeit', 'Unterschrift']],
    body,
    bodyStyles: { minCellHeight: 11.5 },
    columnStyles: {
      0: { cellWidth: 27 },
      1: { cellWidth: 49 },
      2: { cellWidth: 17, halign: 'center' },
      3: { cellWidth: 21, halign: 'center' },
      4: { cellWidth: 14, halign: 'center' },
      5: { cellWidth: 29, halign: 'center' },
      6: { cellWidth: 33 },
    },
    didParseCell: (data) => {
      if (data.section === 'body' && data.column.index > 1 && data.column.index < 6 && data.cell.raw === '–') data.cell.styles.halign = 'center';
      if (data.section === 'body' && data.column.index === 1 && data.cell.raw === '–') data.cell.styles.halign = 'center';
    },
  });

  const stamp = stampFor(company, 'sheet');
  let sy = doc.lastAutoTable.finalY + (stamp ? Math.max(26, stamp.h + 10) : 26);
  if (sy > PAGE_H - 30) { doc.addPage(); sy = 40 + (stamp ? stamp.h : 0); }
  if (stamp) doc.addImage(stamp.dataUrl, 'PNG', M, sy - stamp.h + 3, stamp.w, stamp.h);
  doc.setDrawColor(...BLACK).setLineWidth(0.3);
  doc.line(M, sy, M + 78, sy);
  doc.line(PAGE_W - M - 78, sy, PAGE_W - M, sy);
  doc.setFont('helvetica', 'normal').setFontSize(8).setTextColor(...GREY);
  doc.text('Datum / Unterschrift Mitarbeiter', M, sy + 4);
  doc.text('Datum / Unterschrift Auftraggeber', PAGE_W - M - 78, sy + 4);
}

// ---------- month overview ----------
function monthOverview(doc, project, company, logo, year, month0, entries) {
  let y = header(doc, company, logo, 'Monatsübersicht', `${MONTHS_DE[month0]} ${year}`);
  y = infoGrid(doc, y, [
    ['Projekt / Objekt', project.name],
    ['Auftraggeber', project.customer_name],
    ['Mitarbeiter', project.employee_name],
    ['Stundensatz', fmtEur(rate(project, company))],
  ]);
  const body = [];
  let total = 0;
  for (const monday of monthWeeks(year, month0)) {
    const lo = toKey(monday);
    const hi = toKey(addDays(monday, 6));
    const we = entries.filter((e) => e.date >= lo && e.date <= hi);
    const minutes = we.reduce((s, e) => s + entryMinutes(e), 0);
    total += minutes;
    body.push([String(isoWeek(monday).week), `${fmtDate(monday)} – ${fmtDate(addDays(monday, 6))}`, String(new Set(we.map((e) => e.date)).size), fmtHours(minutes), fmtDecimal(minutes / 60)]);
  }
  body.push(['', { content: 'Gesamt im Monat', styles: { fontStyle: 'bold' } }, '', { content: fmtHours(total), styles: { fontStyle: 'bold' } }, { content: fmtDecimal(total / 60), styles: { fontStyle: 'bold' } }]);
  autoTable(doc, {
    ...tableBase,
    startY: y,
    head: [['KW', 'Zeitraum', 'Arbeitstage', 'Netto Arbeitszeit (MA-Std.)', 'Stunden (dezimal)']],
    body,
    columnStyles: { 0: { cellWidth: 15, halign: 'center' }, 1: { cellWidth: 70 }, 2: { cellWidth: 30, halign: 'center' }, 3: { cellWidth: 40, halign: 'center' }, 4: { cellWidth: 31, halign: 'right' } },
    didParseCell: (d) => { if (d.row.index === body.length - 1) d.cell.styles.fillColor = [228, 228, 231]; },
  });
  doc.setFont('helvetica', 'normal').setFontSize(7.5).setTextColor(...GREY);
  doc.text('Hinweis: Die Stundenzettel zeigen jeweils die komplette Kalenderwoche. Für die Monatsübersicht und die Rechnung werden nur Tage innerhalb des Monats berücksichtigt.', M, doc.lastAutoTable.finalY + 6, { maxWidth: CONTENT_W });
}

// ---------- invoice ----------
export function computeInvoice(project, company, year, month0, entries) {
  const first = new Date(year, month0, 1);
  const last = monthLastDay(year, month0);
  const r = rate(project, company);
  const positions = [];
  let totalMinutes = 0;
  for (const monday of monthWeeks(year, month0)) {
    const lo = monday < first ? first : monday;
    const sunday = addDays(monday, 6);
    const hi = sunday > last ? last : sunday;
    const loK = toKey(lo);
    const hiK = toKey(hi);
    const minutes = entries.filter((e) => e.date >= loK && e.date <= hiK).reduce((s, e) => s + entryMinutes(e), 0);
    if (!minutes) continue;
    totalMinutes += minutes;
    positions.push({ week: isoWeek(monday).week, from: lo, to: hi, minutes, hours: minutes / 60, amount: Math.round((minutes / 60) * r * 100) / 100 });
  }
  const net = Math.round((totalMinutes / 60) * r * 100) / 100;
  const vatRate = company.small_business ? 0 : Number(company.vat_rate) || 0;
  const vat = Math.round(net * vatRate) / 100;
  return { rate: r, positions, totalMinutes, net, vatRate, vat, gross: Math.round((net + vat) * 100) / 100 };
}

function invoicePage(doc, project, company, logo, year, month0, entries, invoice) {
  const first = new Date(year, month0, 1);
  const last = monthLastDay(year, month0);
  const calc = computeInvoice(project, company, year, month0, entries);
  const invDate = new Date(invoice.invoice_date + 'T00:00:00');
  let y = header(doc, company, logo, 'Rechnung', `Nr. ${invoice.number}`);

  // sender + recipient
  doc.setFont('helvetica', 'normal').setFontSize(7.5).setTextColor(...GREY);
  doc.text([company.name, addressLine(company)].filter(Boolean).join(' · '), M, y + 2);
  doc.setFontSize(9.5).setTextColor(...BLACK);
  const recipient = [project.customer_name, ...(project.customer_address || '').split('\n')].filter(Boolean);
  doc.text(recipient.length ? recipient : ['–'], M, y + 9);

  // meta
  const metaX = M + 100;
  const meta = [['Rechnungsnummer', invoice.number], ['Rechnungsdatum', fmtDate(invDate)], ['Leistungszeitraum', `${fmtDate(first)} – ${fmtDate(last)}`], ['Projekt / Objekt', project.name]];
  meta.forEach(([k, v], i) => {
    doc.setFontSize(8).setTextColor(...GREY).text(k, metaX, y + 2 + i * 5.5);
    doc.setFontSize(9).setTextColor(...BLACK).text(String(v || '–'), metaX + 36, y + 2 + i * 5.5);
  });

  y += 34;
  doc.setFont('helvetica', 'bold').setFontSize(12).setTextColor(...BLACK);
  doc.text(`Rechnung Nr. ${invoice.number}`, M, y);
  y += 5;
  doc.setFont('helvetica', 'normal').setFontSize(9);
  doc.text(`${company.invoice_text || ''} – Leistungszeitraum ${MONTHS_DE[month0]} ${year}. Die Stundenzettel der einzelnen Kalenderwochen liegen dieser Rechnung bei.`, M, y, { maxWidth: CONTENT_W });
  y += 10;

  const body = calc.positions.map((p, i) => [String(i + 1), `Reinigungsarbeiten KW ${p.week} (${fmtDate(p.from)} – ${fmtDate(p.to)})`, fmtDecimal(p.hours), fmtEur(calc.rate), fmtEur(p.amount)]);
  if (!body.length) body.push(['–', 'Keine Arbeitszeiten im Leistungszeitraum erfasst', '0,00', fmtEur(calc.rate), fmtEur(0)]);
  autoTable(doc, {
    ...tableBase,
    startY: y,
    head: [['Pos.', 'Beschreibung', 'Menge (Std.)', 'Einzelpreis', 'Gesamt']],
    body,
    columnStyles: { 0: { cellWidth: 12, halign: 'center' }, 1: { cellWidth: 89 }, 2: { cellWidth: 25, halign: 'right' }, 3: { cellWidth: 28, halign: 'right' }, 4: { cellWidth: 32, halign: 'right' } },
  });

  y = doc.lastAutoTable.finalY + 6;
  const labelX = PAGE_W - M - 38;
  const valueX = PAGE_W - M;
  doc.setFont('helvetica', 'normal').setFontSize(8).setTextColor(...GREY);
  doc.text(`Gesamtstunden: ${fmtDecimal(calc.totalMinutes / 60)} Std.`, M, y);
  doc.setFontSize(9).setTextColor(...BLACK);
  doc.text('Nettobetrag', labelX, y, { align: 'right' });
  doc.text(fmtEur(calc.net), valueX, y, { align: 'right' });
  y += 6;
  const vatLabel = company.small_business ? 'Umsatzsteuer' : `zzgl. ${fmtDecimal(calc.vatRate, Number.isInteger(calc.vatRate) ? 0 : 1)} % USt.`;
  doc.text(vatLabel, labelX, y, { align: 'right' });
  doc.text(fmtEur(calc.vat), valueX, y, { align: 'right' });
  y += 3;
  doc.setDrawColor(...BLACK).setLineWidth(0.3).line(labelX - 45, y, valueX, y);
  y += 5;
  doc.setFont('helvetica', 'bold');
  doc.text('Rechnungsbetrag', labelX, y, { align: 'right' });
  doc.text(fmtEur(calc.gross), valueX, y, { align: 'right' });
  y += 12;

  doc.setFont('helvetica', 'normal').setFontSize(9);
  if (company.small_business) { doc.text('Gemäß § 19 UStG wird keine Umsatzsteuer berechnet.', M, y); y += 6; }
  const due = addDays(invDate, Number(company.payment_days) || 14);
  doc.text(`Bitte überweisen Sie den Rechnungsbetrag von ${fmtEur(calc.gross)} bis zum ${fmtDate(due)} unter Angabe der Rechnungsnummer auf das unten genannte Konto. Vielen Dank für Ihren Auftrag.`, M, y, { maxWidth: CONTENT_W });
  y += 16;

  const bank = [['Bank', company.bank_name], ['IBAN', company.iban], ['BIC', company.bic], ['Steuernummer', company.tax_number], ['USt-IdNr.', company.vat_id]].filter(([, v]) => v);
  if (bank.length) y = infoGrid(doc, y, bank) + 4;
  y += 6;
  const stamp = stampFor(company, 'invoice');
  if (y + 10 + (stamp ? stamp.h + 10 : 12) + 8 > PAGE_H - 20) { doc.addPage(); y = 40; }
  doc.setFont('helvetica', 'normal').setFontSize(9).setTextColor(...BLACK).text('Mit freundlichen Grüßen', M, y);
  if (stamp) { doc.addImage(stamp.dataUrl, 'PNG', M, y + 4, stamp.w, stamp.h); y += stamp.h + 10; } else { y += 12; }
  doc.setFont('helvetica', 'normal').setFontSize(9).setTextColor(...BLACK).text(company.owner || '', M, y);
  doc.setFontSize(7.5).setTextColor(...GREY).text(company.name || '', M, y + 4);
}

// ---------- public API ----------
const output = (doc, filename) => ({ blob: doc.output('blob'), filename });

export function weekPdf(project, company, monday, entries) {
  const logo = logoFor(company);
  const { week, year } = isoWeek(monday);
  const doc = newDoc(`Stundenzettel KW ${week} ${year} – ${project.name}`, company);
  weekSheet(doc, project, company, logo, monday, entries);
  footer(doc, company);
  return output(doc, `Stundenzettel_${safe(project.name)}_KW${String(week).padStart(2, '0')}_${year}.pdf`);
}

export function invoicePdf(project, company, year, month0, entries, invoice) {
  const logo = logoFor(company);
  const doc = newDoc(`Rechnung ${invoice.number}`, company);
  invoicePage(doc, project, company, logo, year, month0, entries, invoice);
  footer(doc, company);
  return output(doc, `Rechnung_${invoice.number}_${safe(project.name)}.pdf`);
}

/** All weekly sheets of the month + overview + invoice. `allEntries` must cover the whole week grid. */
export function monthPdf(project, company, year, month0, allEntries, invoice) {
  const logo = logoFor(company);
  const doc = newDoc(`Stundenzettel & Rechnung ${MONTHS_DE[month0]} ${year} – ${project.name}`, company);
  const firstK = toKey(new Date(year, month0, 1));
  const lastK = toKey(monthLastDay(year, month0));
  const monthEntries = allEntries.filter((e) => e.date >= firstK && e.date <= lastK);
  monthWeeks(year, month0).forEach((monday, i) => {
    if (i > 0) doc.addPage();
    const lo = toKey(monday);
    const hi = toKey(addDays(monday, 6));
    weekSheet(doc, project, company, logo, monday, allEntries.filter((e) => e.date >= lo && e.date <= hi));
  });
  doc.addPage();
  monthOverview(doc, project, company, logo, year, month0, monthEntries);
  doc.addPage();
  invoicePage(doc, project, company, logo, year, month0, monthEntries, invoice);
  footer(doc, company);
  return output(doc, `Monat_${year}-${String(month0 + 1).padStart(2, '0')}_${safe(project.name)}.pdf`);
}

const safe = (t) => (t || '').trim().replace(/[^\p{L}\p{N}_-]+/gu, '_').slice(0, 40) || 'projekt';
