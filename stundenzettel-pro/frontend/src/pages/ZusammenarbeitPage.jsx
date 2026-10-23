import React, { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Bell, Building2, Check, ChevronRight, Handshake, X } from 'lucide-react';
import { toast } from 'sonner';
import Layout, { Ladeanzeige } from '../components/Layout';
import { Btn, Card, Chip, Empty, Field, TextArea, TextInput, Toggle } from '../components/ui';
import { api } from '../lib/api';
import { useAuth } from '../lib/auth';

const TOKEN_KEY = 'szpro-projekteinladung';
const fmtZeit = (iso) => new Date(iso).toLocaleString('de-DE', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });

/** Zusammenarbeit: Einladungen, eigene Plattform-Projekte, Beteiligungen bei anderen Firmen, Firmenverzeichnis, Benachrichtigungen. */
export default function ZusammenarbeitPage() {
  const navigate = useNavigate();
  const { isInhaber } = useAuth();
  const [d, setD] = useState(null);
  const [verz, setVerz] = useState(null);
  const [ben, setBen] = useState(null);
  const [busy, setBusy] = useState('');
  const laden = useCallback(() => Promise.all([api.get('/api/plattform/uebersicht'), api.get('/api/firma/verzeichnis'), api.get('/api/benachrichtigungen')]).then(([u, v, b]) => { setD(u); setVerz(v); setBen(b); }).catch((err) => toast.error(err.message)), []);
  useEffect(() => { laden(); }, [laden]);
  useEffect(() => {
    let token = null;
    try { token = localStorage.getItem(TOKEN_KEY); } catch { /* ignore */ }
    if (!token) return;
    api.post('/api/beteiligungen/token', { token }).then((r) => { toast.success(`Einladung angenommen: ${r.beteiligung.projekt?.name || 'Projekt'}`); laden(); }).catch((err) => toast.error(err.message)).finally(() => { try { localStorage.removeItem(TOKEN_KEY); } catch { /* ignore */ } });
  }, [laden]);

  const antwort = async (b, annehmen) => {
    setBusy(b.id);
    try { const r = await api.post(`/api/beteiligungen/${b.id}/antwort`, { annehmen }); toast.success(annehmen ? 'Einladung angenommen – das Projekt ist jetzt in euren Projekten' : 'Einladung abgelehnt'); laden(); if (annehmen && r.beteiligung.lokales_project_id) navigate(`/projekte/${r.beteiligung.lokales_project_id}`); }
    catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };
  const verzSpeichern = async () => { setBusy('verz'); try { await api.put('/api/firma/verzeichnis', verz.verzeichnis); toast.success('Verzeichnis-Eintrag gespeichert'); } catch (err) { toast.error(err.message); } finally { setBusy(''); } };
  const alleGelesen = async () => { try { await api.post('/api/benachrichtigungen/alle-gelesen'); laden(); } catch (err) { toast.error(err.message); } };
  const toggleGewerk = (g) => setVerz((v) => { const liste = v.verzeichnis.gewerke.includes(g) ? v.verzeichnis.gewerke.filter((x) => x !== g) : [...v.verzeichnis.gewerke, g]; return { ...v, verzeichnis: { ...v.verzeichnis, gewerke: liste } }; });

  if (!d || !verz || !ben) return <Layout title="Zusammenarbeit"><Ladeanzeige /></Layout>;
  return (
    <Layout title="Zusammenarbeit" subtitle="Projekte gemeinsam mit anderen Firmen: Auftraggeber laden ein, Subunternehmer nehmen an. Jede Firma behält ihre eigenen Daten.">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {d.einladungen.length > 0 && (
          <Card className="p-5 space-y-3 lg:col-span-2 border-2 border-[#C41E3A]/30">
            <h2 className="text-[16px] flex items-center gap-2"><Handshake size={16} /> Offene Einladungen</h2>
            {d.einladungen.map((b) => (
              <div key={b.id} className="rounded-2xl bg-[#FFF4E5] px-4 py-3 flex flex-wrap items-center gap-3">
                <div className="flex-1 min-w-[220px]"><div className="font-semibold">{b.projekt.name}</div><div className="text-[13px] text-[#6E6E73]">{b.auftraggeber.name}{b.auftraggeber.city ? ` · ${b.auftraggeber.city}` : ''} · {[b.gewerk, b.rolle_name].filter(Boolean).join(' · ')}{b.nachricht ? ` · „${b.nachricht}“` : ''}</div></div>
                <Btn onClick={() => antwort(b, true)} loading={busy === b.id}><Check size={15} /> Annehmen</Btn>
                <Btn variant="soft" onClick={() => antwort(b, false)} disabled={busy === b.id}><X size={15} /> Ablehnen</Btn>
              </div>
            ))}
          </Card>
        )}

        <Card className="p-5 space-y-3">
          <h2 className="text-[16px] flex items-center gap-2"><Building2 size={16} /> Unsere Projekte mit anderen Firmen</h2>
          {d.projekte.length === 0 ? <p className="text-[13px] text-[#6E6E73]">Noch keins. Öffne ein Projekt und lade unter „Firmen“ Subunternehmer ein oder trage Projektleiter ein.</p> : (
            <ul className="divide-y divide-black/[0.06]">{d.projekte.map((p) => (
              <li key={p.id}><Link to={`/projekte/${p.id}`} className="py-2.5 flex items-center gap-3 text-[14px]">
                <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: p.color || '#C41E3A' }} />
                <div className="flex-1 min-w-0"><div className="font-semibold truncate">{p.name}</div><div className="text-[12px] text-[#6E6E73]">{p.address ? `${p.address} · ` : ''}{p.leiter} Projektleiter · {p.firmen} Firmen{p.eingeladen ? ` (+${p.eingeladen} eingeladen)` : ''} · {p.aufgaben_offen} offene Aufgaben{p.aufgaben_heute ? `, ${p.aufgaben_heute} heute` : ''}</div></div>
                <ChevronRight size={16} className="text-[#A1A1A6]" />
              </Link></li>
            ))}</ul>
          )}
        </Card>

        <Card className="p-5 space-y-3">
          <h2 className="text-[16px] flex items-center gap-2"><Handshake size={16} /> Projekte, an denen wir beteiligt sind</h2>
          {d.beteiligungen.length === 0 ? <p className="text-[13px] text-[#6E6E73]">Noch keine. Sobald ein Auftraggeber euch einlädt und ihr annehmt, erscheint das Projekt hier und unter Projekte.</p> : (
            <ul className="divide-y divide-black/[0.06]">{d.beteiligungen.map((b) => (
              <li key={b.id}><Link to={`/projekte/${b.lokales_project_id}`} className="py-2.5 flex items-center gap-3 text-[14px]">
                <div className="flex-1 min-w-0"><div className="font-semibold truncate">{b.projekt.name}</div><div className="text-[12px] text-[#6E6E73]">{b.auftraggeber.name} · {[b.gewerk, b.rolle_name].filter(Boolean).join(' · ')}</div></div>
                <ChevronRight size={16} className="text-[#A1A1A6]" />
              </Link></li>
            ))}</ul>
          )}
        </Card>

        <Card className="p-5 space-y-3">
          <h2 className="text-[16px]">Firmenverzeichnis</h2>
          <p className="text-[13px] text-[#6E6E73]">Sichtbare Firmen können von Auftraggebern gefunden und eingeladen werden. Sichtbar sind nur Name, Ort, Gewerke und Beschreibung.</p>
          <div className="rounded-2xl bg-[#F5F5F7] px-4"><Toggle checked={!!verz.verzeichnis.sichtbar} onChange={(v) => setVerz((x) => ({ ...x, verzeichnis: { ...x.verzeichnis, sichtbar: v } }))} label="Im Verzeichnis sichtbar" /></div>
          <div><span className="block text-[13px] font-medium text-[#6E6E73] mb-2">Gewerke</span><div className="flex flex-wrap gap-2">{[...new Set([...verz.gewerke_vorschlaege, ...verz.verzeichnis.gewerke])].map((g) => <Chip key={g} active={verz.verzeichnis.gewerke.includes(g)} onClick={() => toggleGewerk(g)}>{g}</Chip>)}</div></div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Field label="Ort"><TextInput value={verz.verzeichnis.ort} onChange={(e) => { const v = e.target.value; setVerz((x) => ({ ...x, verzeichnis: { ...x.verzeichnis, ort: v } })); }} /></Field>
            <Field label="Beschreibung" className="sm:col-span-2"><TextArea rows={2} value={verz.verzeichnis.beschreibung} onChange={(e) => { const v = e.target.value; setVerz((x) => ({ ...x, verzeichnis: { ...x.verzeichnis, beschreibung: v } })); }} /></Field>
          </div>
          {isInhaber ? <Btn onClick={verzSpeichern} loading={busy === 'verz'}>Speichern</Btn> : <p className="text-[12px] text-[#86868B]">Ändern kann das nur der Inhaber.</p>}
        </Card>

        <Card className="p-5 space-y-3">
          <div className="flex items-center justify-between gap-2"><h2 className="text-[16px] flex items-center gap-2"><Bell size={16} /> Benachrichtigungen {ben.ungelesen > 0 && <span className="text-[11px] font-semibold rounded-full bg-[#C41E3A] text-white px-2 py-0.5">{ben.ungelesen}</span>}</h2>{ben.ungelesen > 0 && <Btn size="sm" variant="ghost" onClick={alleGelesen}>Alle gelesen</Btn>}</div>
          {ben.benachrichtigungen.length === 0 ? <Empty icon={Bell} title="Nichts Neues" text="Einladungen, Aufgaben und Freigaben erscheinen hier." /> : (
            <ul className="divide-y divide-black/[0.06]">{ben.benachrichtigungen.slice(0, 30).map((n) => <li key={n.id} className={`py-2 text-[13px] ${n.gelesen ? 'text-[#6E6E73]' : 'font-medium'}`}>{n.link ? <Link to={n.link}>{n.text}</Link> : n.text}<span className="block text-[11px] text-[#A1A1A6] font-normal">{fmtZeit(n.created_at)}</span></li>)}</ul>
          )}
        </Card>
      </div>
    </Layout>
  );
}

/** Einladungslink /#/projekteinladung/<token>: merken, dann anmelden oder registrieren; die Zusammenarbeit-Seite löst ihn ein. */
export function ProjektEinladungPage() {
  const { token } = useParams();
  const { ready, user, isBuero } = useAuth();
  const navigate = useNavigate();
  useEffect(() => {
    try { if (token) localStorage.setItem(TOKEN_KEY, token); } catch { /* ignore */ }
    if (ready && user && isBuero) navigate('/zusammenarbeit', { replace: true });
  }, [token, ready, user, isBuero, navigate]);
  return (
    <div className="ts-app safe-top min-h-screen flex items-center justify-center p-6">
      <Card className="p-7 max-w-md w-full space-y-4">
        <h1 className="text-[24px] font-bold tracking-tight flex items-center gap-2"><Handshake size={22} /> Einladung zur Zusammenarbeit</h1>
        {ready && user && !isBuero ? <p className="text-[14px] text-[#6E6E73]">Diese Einladung kann nur Büro oder Inhaber eurer Firma annehmen. Bitte den Link weitergeben.</p> : (
          <>
            <p className="text-[14px] text-[#6E6E73]">Ein Auftraggeber lädt eure Firma zu einem Projekt ein. Melde dich mit dem Firmenkonto an oder registriere eure Firma. Danach wird die Einladung automatisch angenommen.</p>
            <div className="flex gap-2"><Btn className="flex-1" onClick={() => navigate('/login')}>Anmelden</Btn><Btn className="flex-1" variant="soft" onClick={() => navigate('/registrieren')}>Firma registrieren</Btn></div>
          </>
        )}
      </Card>
    </div>
  );
}
