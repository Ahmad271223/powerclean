import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Download, FileText, Gavel, Megaphone, MessageCircleQuestion, Paperclip, Pencil, Scale, Send, Trash2, Users, X } from 'lucide-react';
import { toast } from 'sonner';
import Layout, { Ladeanzeige } from '../components/Layout';
import Bild from '../components/Bild';
import AusschreibungDialog from '../components/ausschreibung/AusschreibungDialog';
import FirmenEinladenDialog from '../components/ausschreibung/FirmenEinladenDialog';
import AngebotBereich from '../components/ausschreibung/AngebotBereich';
import AngeboteVergleich from '../components/ausschreibung/AngeboteVergleich';
import VergabeBereich from '../components/ausschreibung/VergabeBereich';
import { Btn, Card, Empty, Field, IconBtn, Segmented, Select, TextArea, TextInput, Toggle } from '../components/ui';
import { api, download, openFile } from '../lib/api';
import { ANFORDERUNGEN, STATUS_CLS, fmtGeld, fmtTag, fmtZeit, fristText } from '../lib/ausschreibung';

const chip = (d) => <span className={`text-[11px] font-semibold rounded-full px-2 py-0.5 ${STATUS_CLS[d.status] || ''}`}>{d.status_name}</span>;
const Zeile = ({ l, children }) => (children || children === 0 ? <div className="flex gap-3 text-[13px] py-1"><span className="w-36 shrink-0 text-[#6E6E73]">{l}</span><span className="min-w-0 flex-1 whitespace-pre-wrap">{children}</span></div> : null);
const EINLADUNG_STATUS = { eingeladen: 'eingeladen', angesehen: 'angesehen', angebot: 'Angebot abgegeben', abgelehnt: 'abgelehnt' };

/** Ausschreibungsdetail: Übersicht, Positionen, Unterlagen, Anforderungen, Rückfragen, Angebot (Bieter) bzw. Angebote/Vergabe (Projektleitung). */
export default function AusschreibungPage() {
  const { ausschreibungId } = useParams();
  const navigate = useNavigate();
  const [d, setD] = useState(null);
  const [tab, setTab] = useState('uebersicht');
  const [edit, setEdit] = useState(false);
  const [einladen, setEinladen] = useState(false);
  const [busy, setBusy] = useState('');
  const laden = useCallback(() => api.get(`/api/ausschreibungen/${ausschreibungId}`).then((r) => setD(r.ausschreibung)).catch((err) => { toast.error(err.message); if (err.status === 404) navigate('/ausschreibungen', { replace: true }); }), [ausschreibungId, navigate]);
  useEffect(() => { laden(); }, [laden]);
  if (!d) return <Layout title="Ausschreibung"><Ladeanzeige /></Layout>;
  const leitung = d.rolle === 'leitung';
  const aktion = async (pfad, body, erfolg, bestaetigen) => {
    if (bestaetigen && !window.confirm(bestaetigen)) return;
    setBusy(pfad);
    try { await api.post(pfad, body); toast.success(erfolg); laden(); } catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };
  const loeschen = async () => { if (!window.confirm('Entwurf löschen?')) return; try { await api.del(`/api/ausschreibungen/${d.id}`); toast.success('Entwurf gelöscht'); navigate(`/projekte/${d.project_id}`); } catch (err) { toast.error(err.message); } };
  const tabs = [
    { value: 'uebersicht', label: 'Übersicht', icon: FileText }, { value: 'positionen', label: `Positionen${d.positionen?.length ? ` (${d.positionen.length})` : ''}`, icon: Scale },
    { value: 'unterlagen', label: `Unterlagen (${d.dokumente.length})`, icon: Paperclip }, { value: 'anforderungen', label: 'Anforderungen', icon: Users },
    { value: 'fragen', label: `Rückfragen (${d.fragen.length})`, icon: MessageCircleQuestion },
    ...(leitung ? [{ value: 'angebote', label: `Angebote (${d.zaehler?.angebote ?? 0})`, icon: Gavel }] : [{ value: 'angebot', label: d.angebot ? `Mein Angebot` : 'Angebot abgeben', icon: Send }]),
    ...(d.vergabe ? [{ value: 'vergabe', label: 'Vergabe', icon: Gavel }] : []),
  ];
  return (
    <Layout wide title={d.titel} subtitle={`${d.nummer} · ${d.auftraggeber?.name || ''}${d.projekt?.name ? ` · ${d.projekt.name}` : ''} · Angebotsfrist ${fristText(d)}`}
      action={(
        <div className="flex flex-wrap gap-2 justify-end">
          <IconBtn variant="soft" onClick={() => navigate(leitung ? `/projekte/${d.project_id}` : '/ausschreibungen')} title="Zurück"><ArrowLeft size={18} /></IconBtn>
          {leitung && !['vergeben', 'aufgehoben'].includes(d.status) && <Btn size="sm" variant="soft" onClick={() => setEdit(true)}><Pencil size={15} /> Bearbeiten</Btn>}
          {leitung && d.status === 'entwurf' && <Btn size="sm" onClick={() => aktion(`/api/ausschreibungen/${d.id}/veroeffentlichen`, {}, 'Ausschreibung veröffentlicht', 'Jetzt veröffentlichen? Eingeladene und passende Firmen werden benachrichtigt.')} loading={busy.endsWith('veroeffentlichen')}><Megaphone size={15} /> Veröffentlichen</Btn>}
          {leitung && !['vergeben', 'aufgehoben'].includes(d.status) && <Btn size="sm" variant="dark" onClick={() => setEinladen(true)}><Send size={15} /> Firmen einladen</Btn>}
          {leitung && ['veroeffentlicht', 'in_vergabe'].includes(d.status) && <Btn size="sm" variant="ghost" onClick={() => { const g = window.prompt('Ausschreibung aufheben – Grund (wird den Bietern mitgeteilt):'); if (g !== null) aktion(`/api/ausschreibungen/${d.id}/aufheben`, { nachricht: g }, 'Ausschreibung aufgehoben'); }}><X size={15} /> Aufheben</Btn>}
          {leitung && d.status === 'entwurf' && <IconBtn variant="danger" onClick={loeschen} title="Entwurf löschen"><Trash2 size={16} /></IconBtn>}
          {!leitung && d.kann_bieten && tab !== 'angebot' && <Btn size="sm" onClick={() => setTab('angebot')}><Send size={15} /> {d.angebot ? 'Mein Angebot' : 'Angebot abgeben'}</Btn>}
        </div>
      )}>
      <div className="flex flex-wrap items-center gap-2 mb-4">{chip(d)}{leitung && <span className="text-[12px] text-[#6E6E73]">{d.sichtbarkeit_name}</span>}{d.gewerk && <span className="text-[11px] font-semibold rounded-full px-2 py-0.5 bg-black/[0.06]">{d.gewerk}</span>}{d.vergabe && !leitung && d.vergabe.status === 'mitgeteilt' && <span className="text-[11px] font-semibold rounded-full px-2 py-0.5 bg-[#1B7F3B] text-white">Vergabe erhalten – Annahme offen</span>}</div>
      <div className="flex justify-center mb-5 overflow-x-auto no-scrollbar"><Segmented value={tab} onChange={setTab} options={tabs} /></div>

      {tab === 'uebersicht' && (
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-5">
          <div className="space-y-5">
            <Card className="p-5 space-y-4">
              {d.beschreibung && <div><h2 className="text-[15px] mb-1">Beschreibung</h2><p className="text-[14px] whitespace-pre-wrap">{d.beschreibung}</p></div>}
              {d.leistungsumfang && <div><h2 className="text-[15px] mb-1">Leistungsumfang</h2><p className="text-[14px] whitespace-pre-wrap">{d.leistungsumfang}</p></div>}
              {!d.beschreibung && !d.leistungsumfang && <p className="text-[13px] text-[#86868B]">Noch keine Beschreibung.</p>}
            </Card>
            {d.projekt?.name && (
              <Card className="p-5"><h2 className="text-[15px] mb-2">Projekt</h2>
                <Zeile l="Projekt">{d.projekt.name}{d.projekt.projektnummer ? ` (${d.projekt.projektnummer})` : ''}</Zeile><Zeile l="Adresse">{d.projekt.address}</Zeile><Zeile l="Projektart">{d.projekt.projektart}</Zeile>
                <Zeile l="Bauzeit">{d.projekt.baubeginn ? `${fmtTag(d.projekt.baubeginn)} – ${fmtTag(d.projekt.bauende)}` : null}</Zeile><Zeile l="Bauabschnitte">{(d.projekt.bauabschnitte || []).join(', ')}</Zeile><Zeile l="Beschreibung">{d.projekt.beschreibung}</Zeile>
                {d.projekt.lat && d.projekt.lon ? <Zeile l="Karte"><a className="underline" href={`https://www.openstreetmap.org/?mlat=${d.projekt.lat}&mlon=${d.projekt.lon}#map=15/${d.projekt.lat}/${d.projekt.lon}`} target="_blank" rel="noreferrer">Standort auf OpenStreetMap öffnen</a></Zeile> : null}
              </Card>
            )}
            {leitung && (
              <Card className="p-5 space-y-3">
                <div className="flex items-center justify-between gap-2"><h2 className="text-[15px]">Eingeladene Firmen ({d.einladungen.length})</h2><Btn size="sm" variant="soft" onClick={() => setEinladen(true)}><Send size={14} /> Einladen</Btn></div>
                {d.einladungen.length === 0 ? <p className="text-[13px] text-[#86868B]">{d.sichtbarkeit === 'privat' ? 'Private Ausschreibung – ohne Einladungen sieht sie niemand.' : 'Noch keine direkten Einladungen (plattformweit sichtbar).'}</p> : (
                  <ul className="divide-y divide-black/[0.06] text-[13px]">{d.einladungen.map((e) => <li key={e.id} className="py-2 flex items-center gap-2"><span className="flex-1 font-medium">{e.firma_name}</span><span className="text-[#6E6E73]">{EINLADUNG_STATUS[e.status] || e.status} · {fmtTag((e.created_at || '').slice(0, 10))}</span>{!['vergeben', 'aufgehoben'].includes(d.status) && <IconBtn size={28} variant="danger" title="Einladung entfernen" onClick={async () => { try { await api.del(`/api/ausschreibungen/${d.id}/einladungen/${e.id}`); laden(); } catch (err) { toast.error(err.message); } }}><X size={13} /></IconBtn>}</li>)}</ul>
                )}
              </Card>
            )}
            {leitung && d.intern && <Card className="p-5"><h2 className="text-[15px] mb-1">Interne Vermerke</h2><p className="text-[13px] whitespace-pre-wrap text-[#6E6E73]">{d.intern}</p></Card>}
            {leitung && (d.verlauf || []).length > 0 && <Card className="p-5"><h2 className="text-[15px] mb-1">Änderungsverlauf</h2><ul className="text-[12px] text-[#6E6E73] space-y-0.5">{d.verlauf.slice().reverse().map((v, i) => <li key={i}>{fmtZeit(v.at)} · {v.aktion}{v.felder ? ` (${v.felder.join(', ')})` : ''} · {v.user_name}{v.text && !v.felder ? ` · ${v.text}` : ''}</li>)}</ul></Card>}
          </div>
          <aside className="space-y-5">
            <Card className="p-5"><h2 className="text-[15px] mb-2">Eckdaten</h2>
              <Zeile l="Auftraggeber">{d.auftraggeber?.name}{d.auftraggeber?.city ? `, ${d.auftraggeber.city}` : ''}</Zeile><Zeile l="Verantwortlich">{d.verantwortlich_name}</Zeile><Zeile l="Gewerk">{d.gewerk}</Zeile><Zeile l="Leistungsart">{d.leistungsart}</Zeile>
              <Zeile l="Ausführungsort">{d.ausfuehrungsort || d.projekt?.address}</Zeile><Zeile l="Veröffentlicht">{fmtTag(d.veroeffentlicht_am)}</Zeile><Zeile l="Bewerbungsfrist">{d.bewerbungsfrist ? fmtTag(d.bewerbungsfrist) : null}</Zeile>
              <Zeile l="Angebotsfrist">{fristText(d)}</Zeile><Zeile l="Ausführung">{d.ausfuehrung_von ? `${fmtTag(d.ausfuehrung_von)} – ${fmtTag(d.ausfuehrung_bis)}` : null}</Zeile>
            </Card>
            <Card className="p-5"><h2 className="text-[15px] mb-2">Kaufmännisch</h2>
              <Zeile l="Abrechnungsart">{d.abrechnungsart_name}</Zeile><Zeile l="Budgetrahmen">{d.kaufmaennisch?.budget !== undefined && d.kaufmaennisch?.budget !== null ? fmtGeld(d.kaufmaennisch.budget) : null}</Zeile>
              <Zeile l="Zahlung">{d.kaufmaennisch?.zahlungsbedingungen}</Zeile><Zeile l="Vertrag">{d.kaufmaennisch?.vertragsbedingungen}</Zeile><Zeile l="Preisaufschlüsselung">{d.kaufmaennisch?.preisaufschluesselung}</Zeile>
            </Card>
          </aside>
        </div>
      )}

      {tab === 'positionen' && (
        <Card className="p-5 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2"><h2 className="text-[15px]">Leistungsverzeichnis</h2><div className="flex gap-2">{(d.positionen || []).length > 0 && <Btn size="sm" variant="soft" onClick={() => download(`/api/ausschreibungen/${d.id}/positionen.csv`).catch((err) => toast.error(err.message))}><Download size={14} /> CSV</Btn>}{leitung && !['vergeben', 'aufgehoben'].includes(d.status) && <Btn size="sm" variant="soft" onClick={() => setEdit(true)}><Pencil size={14} /> Bearbeiten</Btn>}</div></div>
          {(d.positionen || []).length === 0 ? <p className="text-[13px] text-[#86868B]">Kein Leistungsverzeichnis – Angebote erfolgen pauschal oder nach Stunden.</p> : (
            <div className="overflow-x-auto"><table className="w-full text-[13px]"><thead><tr className="text-left text-[11px] uppercase tracking-wider text-[#86868B]"><th className="py-1 pr-3">Nr</th><th className="py-1 pr-3">Leistung</th><th className="py-1 pr-3 text-right">Menge</th><th className="py-1">Einheit</th></tr></thead>
              <tbody>{d.positionen.map((p) => <tr key={p.nr} className="border-t border-black/[0.06]"><td className="py-1.5 pr-3 font-mono">{p.nr}</td><td className="py-1.5 pr-3">{p.leistung}{p.beschreibung ? <span className="block text-[12px] text-[#6E6E73]">{p.beschreibung}</span> : null}</td><td className="py-1.5 pr-3 text-right">{p.menge}</td><td className="py-1.5">{p.einheit}</td></tr>)}</tbody></table></div>
          )}
        </Card>
      )}

      {tab === 'unterlagen' && <Unterlagen d={d} leitung={leitung} onChanged={laden} />}

      {tab === 'anforderungen' && (
        <Card className="p-5 space-y-3">
          {ANFORDERUNGEN.filter(([k]) => d.anforderungen?.[k]).length === 0 ? <p className="text-[13px] text-[#86868B]">Keine besonderen Anforderungen hinterlegt.</p>
            : ANFORDERUNGEN.filter(([k]) => d.anforderungen?.[k]).map(([k, l]) => <div key={k}><span className="block text-[12px] font-semibold text-[#6E6E73]">{l}</span><p className="text-[14px] whitespace-pre-wrap">{d.anforderungen[k]}</p></div>)}
        </Card>
      )}

      {tab === 'fragen' && <Fragen d={d} leitung={leitung} onChanged={laden} />}
      {tab === 'angebot' && !leitung && <AngebotBereich ausschreibung={d} onChanged={laden} />}
      {tab === 'angebote' && leitung && <AngeboteVergleich ausschreibung={d} onChanged={laden} />}
      {tab === 'vergabe' && d.vergabe && <VergabeBereich ausschreibung={d} rolle={d.rolle} onChanged={laden} kategorien={d.kategorien?.vergabe} />}

      <AusschreibungDialog open={edit} onOpenChange={setEdit} ausschreibung={d} gewerke={d.gewerke} onSaved={laden} />
      <FirmenEinladenDialog open={einladen} onOpenChange={setEinladen} ausschreibungId={d.id} bereits={(d.einladungen || []).map((e) => e.firma_id)} gewerk={d.gewerk} onDone={laden} />
    </Layout>
  );
}

function Unterlagen({ d, leitung, onChanged }) {
  const [kat, setKat] = useState('Pläne');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const eingabe = useRef(null);
  const upload = async (file) => { if (!file) return; setBusy(true); try { const fd = new FormData(); fd.append('datei', file); fd.append('kategorie', kat); fd.append('note', note); await api.upload(`/api/ausschreibungen/${d.id}/dokumente`, fd); toast.success('Unterlage hochgeladen'); setNote(''); onChanged?.(); } catch (err) { toast.error(err.message); } finally { setBusy(false); } };
  const bilder = d.dokumente.filter((x) => (x.mime || '').startsWith('image/'));
  const dateien = d.dokumente.filter((x) => !(x.mime || '').startsWith('image/'));
  return (
    <div className="space-y-4">
      {leitung && !['vergeben', 'aufgehoben'].includes(d.status) && (
        <Card className="p-4 flex flex-wrap gap-2 items-center">
          <Select value={kat} onChange={(e) => setKat(e.target.value)}>{(d.kategorien?.ausschreibung || ['Sonstiges']).map((k) => <option key={k} value={k}>{k}</option>)}</Select>
          <TextInput value={note} onChange={(e) => setNote(e.target.value)} placeholder="Bezeichnung, z. B. Trassenplan EG" className="flex-1 min-w-[180px]" />
          <input ref={eingabe} type="file" accept="application/pdf,image/*,.doc,.docx,.xls,.xlsx,.txt" className="hidden" onChange={(e) => { upload(e.target.files?.[0]); e.target.value = ''; }} />
          <Btn variant="dark" onClick={() => eingabe.current?.click()} loading={busy}><Paperclip size={15} /> Hochladen</Btn>
          <span className="w-full text-[12px] text-[#86868B]">Bilder, Pläne, Leistungsverzeichnisse, technische Beschreibungen, Terminpläne, Sicherheitsunterlagen, Vertragsentwürfe. Sichtbar für alle Firmen mit Zugang zur Ausschreibung – nie für andere.</span>
        </Card>
      )}
      {bilder.length > 0 && <Card className="p-4"><h2 className="text-[15px] mb-2">Bilder ({bilder.length})</h2><div className="grid grid-cols-2 sm:grid-cols-4 gap-2">{bilder.map((b) => <button key={b.id} type="button" className="relative rounded-xl overflow-hidden aspect-[4/3]" onClick={() => openFile(`/api/dokumente/${b.id}/datei`).catch((err) => toast.error(err.message))}><Bild id={b.id} max={500} className="w-full h-full" alt={b.note || b.filename} />{(b.note || b.category) && <span className="absolute inset-x-0 bottom-0 bg-black/55 text-white text-[11px] px-2 py-1 truncate text-left">{b.note || b.category}</span>}</button>)}</div></Card>}
      <Card className="p-4">
        <h2 className="text-[15px] mb-2">Dokumente ({dateien.length})</h2>
        {dateien.length === 0 ? <Empty icon={Paperclip} title="Noch keine Dokumente" text={leitung ? 'Lade Pläne, Leistungsverzeichnisse und Bedingungen hoch, damit Bieter kalkulieren können.' : 'Der Auftraggeber hat noch keine Unterlagen bereitgestellt.'} /> : (
          <ul className="divide-y divide-black/[0.06] text-[14px]">{dateien.map((x) => <li key={x.id} className="py-2.5 flex items-center gap-3"><FileText size={16} className="text-[#6E6E73] shrink-0" /><button type="button" className="flex-1 min-w-0 text-left" onClick={() => openFile(`/api/dokumente/${x.id}/datei`).catch((err) => toast.error(err.message))}><span className="block font-medium truncate">{x.note || x.filename}</span><span className="block text-[12px] text-[#86868B]">{x.category}{x.ordner ? ` · ${x.ordner}` : ''} · v{x.version || 1} · {Math.max(1, Math.round((x.size || 0) / 1024))} KB · {x.uploaded_by_name} · {fmtZeit(x.created_at)}</span></button></li>)}</ul>
        )}
      </Card>
    </div>
  );
}

function Fragen({ d, leitung, onChanged }) {
  const [text, setText] = useState('');
  const [pos, setPos] = useState('');
  const [antworten, setAntworten] = useState({});
  const [busy, setBusy] = useState('');
  const fragen = async () => { if (!text.trim()) return; setBusy('frage'); try { await api.post(`/api/ausschreibungen/${d.id}/fragen`, { text, position_nr: pos }); toast.success('Rückfrage gesendet'); setText(''); setPos(''); onChanged?.(); } catch (err) { toast.error(err.message); } finally { setBusy(''); } };
  const antworten_ = async (f) => { const a = antworten[f.id] || {}; if (!a.text?.trim()) return; setBusy(f.id); try { await api.post(`/api/fragen/${f.id}/antwort`, { antwort: a.text, oeffentlich: !!a.oeffentlich }); toast.success('Antwort gesendet'); onChanged?.(); } catch (err) { toast.error(err.message); } finally { setBusy(''); } };
  return (
    <div className="space-y-4">
      {!leitung && d.status === 'veroeffentlicht' && (
        <Card className="p-4 space-y-2">
          <h2 className="text-[15px]">Rückfrage stellen</h2>
          <div className="grid grid-cols-1 sm:grid-cols-[1fr_140px] gap-2"><TextArea rows={2} value={text} onChange={(e) => setText(e.target.value)} placeholder="Frage zur Leistung, zu Terminen oder Bedingungen" /><TextInput value={pos} onChange={(e) => setPos(e.target.value)} placeholder="Position (optional)" /></div>
          <div className="flex justify-end"><Btn size="sm" onClick={fragen} loading={busy === 'frage'}><Send size={14} /> Senden</Btn></div>
        </Card>
      )}
      {d.fragen.length === 0 ? <Card><Empty icon={MessageCircleQuestion} title="Keine Rückfragen" text={leitung ? 'Fragen der Bieter erscheinen hier. Antworten können für alle Bieter freigegeben werden.' : 'Du kannst Rückfragen stellen; Antworten für alle Bieter erscheinen ebenfalls hier.'} /></Card> : (
        <Card className="p-4 divide-y divide-black/[0.06]">
          {d.fragen.map((f) => (
            <div key={f.id} className="py-3 space-y-2 text-[14px]">
              <div><span className="font-semibold">{f.firma_name}</span><span className="text-[12px] text-[#86868B]"> · {fmtZeit(f.created_at)}{f.position_nr ? ` · Position ${f.position_nr}` : ''}{f.oeffentlich ? ' · für alle Bieter' : ''}</span><p className="whitespace-pre-wrap">{f.text}</p></div>
              {f.antwort ? <div className="rounded-2xl bg-[#F5F5F7] px-4 py-2.5"><span className="text-[12px] text-[#6E6E73]">Antwort {f.beantwortet_von ? `von ${f.beantwortet_von}` : ''} · {fmtZeit(f.beantwortet_at)}</span><p className="whitespace-pre-wrap">{f.antwort}</p></div>
                : leitung ? (
                  <div className="rounded-2xl bg-[#FFF4E5] p-3 space-y-2"><TextArea rows={2} value={antworten[f.id]?.text || ''} onChange={(e) => { const v = e.target.value; setAntworten((x) => ({ ...x, [f.id]: { ...x[f.id], text: v } })); }} placeholder="Antwort" />
                    <div className="flex flex-wrap items-center justify-between gap-2"><Toggle checked={!!antworten[f.id]?.oeffentlich} onChange={(v) => setAntworten((x) => ({ ...x, [f.id]: { ...x[f.id], oeffentlich: v } }))} label="Antwort allen Bietern zeigen (ohne Nennung der Firma)" /><Btn size="sm" onClick={() => antworten_(f)} loading={busy === f.id}>Antworten</Btn></div></div>
                ) : <p className="text-[12px] text-[#86868B]">Noch unbeantwortet.</p>}
            </div>
          ))}
        </Card>
      )}
    </div>
  );
}
