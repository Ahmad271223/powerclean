import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Play, Square, Pause, MapPin, MapPinOff, Coffee, Clock, Users, WifiOff, QrCode, AlertTriangle, Tag } from 'lucide-react';
import { toast } from 'sonner';
import Layout, { Ladeanzeige } from '../components/Layout';
import MicButton from '../components/MicButton';
import { AppIcon, Btn, Card, Chip, Sheet, TextArea, Toggle } from '../components/ui';
import { api } from '../lib/api';
import { useAuth } from '../lib/auth';
import { addDays, fmtDate, fmtHours, fromKey, toKey } from '../lib/dates';
import { initials } from '../lib/utils';

const GPS_KEY = 'szpro-gps';
const OFFLINE_KEY = 'szpro-offline-stempel';
const QUEUE_KEY = 'szpro-offline-queue';
const pad = (n) => String(n).padStart(2, '0');
const fmtClock = (sek) => `${pad(Math.floor(sek / 3600))}:${pad(Math.floor((sek % 3600) / 60))}:${pad(sek % 60)}`;
const hhmm = (d) => `${pad(d.getHours())}:${pad(d.getMinutes())}`;
const lesen = (k, fallback) => { try { return JSON.parse(localStorage.getItem(k) || 'null') ?? fallback; } catch { return fallback; } };
const merken = (k, v) => { try { if (v == null) localStorage.removeItem(k); else localStorage.setItem(k, JSON.stringify(v)); } catch { /* ignore */ } };

function standort(aktiv) {
  if (!aktiv || !navigator.geolocation) return Promise.resolve(null);
  return new Promise((resolve) => {
    navigator.geolocation.getCurrentPosition(
      (p) => resolve({ lat: p.coords.latitude, lng: p.coords.longitude, accuracy: p.coords.accuracy }),
      () => resolve(null), { enableHighAccuracy: true, timeout: 8000, maximumAge: 60000 },
    );
  });
}

/** Offline-Sitzung: Minuten und Pausenstand wie der Server berechnen. */
function offlineStand(s) {
  const start = new Date(s.start_at);
  const jetzt = new Date();
  let pause = 0;
  let laeuft = false;
  for (const p of s.pausen || []) {
    const bis = p.bis ? new Date(p.bis) : jetzt;
    if (!p.bis) laeuft = true;
    pause += Math.max(0, Math.floor((bis - new Date(p.von)) / 60000));
  }
  return { minuten: Math.max(0, Math.floor((jetzt - start) / 60000) - pause), pause_minuten: pause, pause_laeuft: laeuft };
}

/** Wartende Offline-Einträge an den Server schicken (bei Netz). */
export async function offlineSynchronisieren() {
  const queue = lesen(QUEUE_KEY, []);
  if (!queue.length) return 0;
  const rest = [];
  let ok = 0;
  for (const payload of queue) {
    try { await api.post('/api/zeiten', { ...payload, offline: true }); ok += 1; }
    catch (err) {
      if (err.status === 0) rest.push(payload);
      else toast.error(`Offline-Eintrag vom ${fmtDate(fromKey(payload.date))} abgelehnt: ${err.message}`);
    }
  }
  merken(QUEUE_KEY, rest.length ? rest : null);
  if (ok) toast.success(`${ok} Offline-Eintrag${ok > 1 ? 'e' : ''} nachgetragen`);
  return ok;
}

/** Stempeluhr: Projekt wählen, Start/Pause/Stop. Optional mit Standort, Leistung und Spracheingabe. Läuft ohne Netz weiter. */
export default function StempeluhrPage() {
  const { isBuero } = useAuth();
  const { projectId: qrProjekt } = useParams();
  const [status, setStatus] = useState(null);
  const [fetchedAt, setFetchedAt] = useState(Date.now());
  const [projekt, setProjekt] = useState(qrProjekt || '');
  const [gps, setGps] = useState(() => { try { return localStorage.getItem(GPS_KEY) === '1'; } catch { return false; } });
  const [tick, setTick] = useState(0);
  const [stopDialog, setStopDialog] = useState(false);
  const [activity, setActivity] = useState('');
  const [service, setService] = useState('');
  const [busy, setBusy] = useState('');
  const [letzte, setLetzte] = useState([]);
  const [imEinsatz, setImEinsatz] = useState([]);
  const [offline, setOffline] = useState(() => lesen(OFFLINE_KEY, null));
  const [queue, setQueue] = useState(() => lesen(QUEUE_KEY, []));
  const timer = useRef(null);

  const laden = useCallback(async () => {
    try {
      await offlineSynchronisieren();
      setQueue(lesen(QUEUE_KEY, []));
      const s = await api.get('/api/stempel/status');
      setStatus(s); setFetchedAt(Date.now());
      setProjekt((p) => p || (s.projekte.length === 1 ? s.projekte[0].id : ''));
      const heute = new Date();
      const z = await api.get(`/api/zeiten/meine?von=${toKey(addDays(heute, -6))}&bis=${toKey(heute)}`);
      setLetzte(z.eintraege.slice().reverse().slice(0, 8));
      if (isBuero) setImEinsatz((await api.get('/api/stempel/aktiv')).aktiv);
    } catch (err) {
      if (err.status === 0) { setStatus((s) => s || { aktiv: null, projekte: lesen('szpro-projekte', []), minuten_heute: 0, leistungen: [] }); }
      else toast.error(err.message);
    }
  }, [isBuero]);

  useEffect(() => { laden(); }, [laden]);
  useEffect(() => { if (status?.projekte?.length) merken('szpro-projekte', status.projekte); }, [status]);
  useEffect(() => {
    timer.current = setInterval(() => setTick((t) => t + 1), 1000);
    const refresh = setInterval(laden, 60000);
    const online = () => laden();
    window.addEventListener('online', online);
    return () => { clearInterval(timer.current); clearInterval(refresh); window.removeEventListener('online', online); };
  }, [laden]);
  useEffect(() => { try { localStorage.setItem(GPS_KEY, gps ? '1' : '0'); } catch { /* ignore */ } }, [gps]);

  const aktiv = status?.aktiv;
  const offlineStandJetzt = offline ? offlineStand(offline) : null;
  const sekunden = offline ? offlineStandJetzt.minuten * 60 + (offlineStandJetzt.pause_laeuft ? 0 : Math.floor((Date.now() - new Date(offline.start_at)) / 1000) % 60)
    : aktiv ? aktiv.minuten * 60 + (aktiv.pause_laeuft ? 0 : Math.floor((Date.now() - fetchedAt) / 1000)) : 0;
  void tick;
  const projektObj = (status?.projekte || []).find((p) => p.id === projekt);

  const start = async () => {
    if (!projekt) { toast.error('Bitte zuerst ein Projekt wählen'); return; }
    setBusy('start');
    try {
      const pos = await standort(gps);
      try {
        await api.post('/api/stempel/start', { project_id: projekt, gps: pos });
        toast.success('Eingestempelt');
        await laden();
      } catch (err) {
        if (err.status !== 0) throw err;
        const s = { project_id: projekt, project_name: projektObj?.name || '', project_color: projektObj?.color || '', start_at: new Date().toISOString(), pausen: [], gps_start: pos };
        merken(OFFLINE_KEY, s); setOffline(s);
        toast.info('Kein Netz – offline eingestempelt. Der Eintrag wird nachgetragen, sobald Netz da ist.');
      }
    } catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };
  const pause = async (weiter) => {
    if (offline) {
      const s = { ...offline, pausen: [...(offline.pausen || [])] };
      if (weiter) { const l = s.pausen[s.pausen.length - 1]; if (l && !l.bis) l.bis = new Date().toISOString(); }
      else s.pausen.push({ von: new Date().toISOString(), bis: null });
      merken(OFFLINE_KEY, s); setOffline(s); return;
    }
    setBusy('pause');
    try { await api.post(weiter ? '/api/stempel/weiter' : '/api/stempel/pause'); await laden(); }
    catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };
  const stop = async () => {
    setBusy('stop');
    try {
      const pos = await standort(gps);
      if (offline) {
        const startD = new Date(offline.start_at);
        const jetzt = new Date();
        const st = offlineStand({ ...offline, pausen: (offline.pausen || []).map((p) => ({ ...p, bis: p.bis || jetzt.toISOString() })) });
        const payload = { project_id: offline.project_id, date: toKey(startD), start_time: hhmm(startD), end_time: hhmm(jetzt), pause_minutes: st.pause_minuten, activity, service_id: service || null, workers: 1 };
        merken(OFFLINE_KEY, null); setOffline(null);
        if (st.minuten >= 1) { const q = [...lesen(QUEUE_KEY, []), payload]; merken(QUEUE_KEY, q); setQueue(q); }
        setStopDialog(false); setActivity(''); setService('');
        toast.success(st.minuten >= 1 ? `Ausgestempelt (offline): ${fmtHours(st.minuten)} – wird nachgetragen` : 'Weniger als eine Minute, nichts eingetragen');
        await laden();
        return;
      }
      const r = await api.post('/api/stempel/stop', { activity, gps: pos, service_id: service || null });
      setStopDialog(false); setActivity(''); setService('');
      if (r.verworfen) toast.info(r.hinweis);
      else {
        toast.success(`Ausgestempelt: ${fmtHours(r.eintrag.net_minutes)} eingetragen${r.eintrag.pause_auto ? ` (Pause ${r.eintrag.pause_minutes} Min. abgezogen)` : ''}`);
        if (r.eintrag.warnungen?.length) toast.warning(r.eintrag.warnungen.map((w) => w.text).join(' · '));
      }
      await laden();
    } catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };
  const beenden = async (s) => {
    if (!window.confirm(`Stempelung von ${s.user_name} jetzt beenden? Der Eintrag endet mit der aktuellen Uhrzeit.`)) return;
    try { await api.post(`/api/stempel/${s.id}/beenden`, { activity: 'vom Büro beendet' }); toast.success('Beendet'); laden(); } catch (err) { toast.error(err.message); }
  };

  const laufend = offline ? { ...offlineStandJetzt, project_name: offline.project_name, project_color: offline.project_color, start_at: offline.start_at, gps_start: offline.gps_start, lange: offlineStandJetzt.minuten >= 600 } : aktiv;

  return (
    <Layout title="Stempeluhr" subtitle={status ? `Heute ${fmtHours(status.minuten_heute)} erfasst` : undefined}>
      {queue.length > 0 && <div className="mb-4 rounded-2xl bg-[#FFF4E5] px-4 py-3 text-[14px] text-[#7A4100] flex items-center gap-3"><WifiOff size={18} /> {queue.length} Offline-Eintrag{queue.length > 1 ? 'e warten' : ' wartet'} auf Netz. <Btn size="sm" variant="dark" onClick={laden}>Jetzt senden</Btn></div>}
      {!status ? <Ladeanzeige /> : (
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_340px] gap-5">
          <Card className="p-5 sm:p-7">
            {!laufend ? (
              <>
                <h2 className="text-[17px] mb-3 flex items-center gap-2">Projekt wählen {qrProjekt && projektObj && <span className="inline-flex items-center gap-1 text-[11px] font-medium bg-[#E8F8EC] text-[#1B7F3B] rounded-full px-2 py-0.5"><QrCode size={11} /> per QR-Code erkannt</span>}</h2>
                {status.projekte.length === 0 ? <p className="text-[14px] text-[#6E6E73]">Dir ist noch kein Projekt zugewiesen. Bitte im Büro nachfragen.</p> : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {status.projekte.map((p) => (
                      <button key={p.id} type="button" onClick={() => setProjekt(p.id)} className={`flex items-center gap-3 rounded-2xl p-3 text-left transition-all ${projekt === p.id ? 'ring-2 ring-[#C41E3A] bg-[#C41E3A]/5' : 'bg-[#F5F5F7] hover:bg-black/[0.06]'}`}>
                        <AppIcon color={p.color} text={initials(p.name)} size={40} className="rounded-xl" />
                        <div className="min-w-0"><div className="font-semibold text-[15px] truncate">{p.name}</div><div className="text-[12px] text-[#6E6E73] truncate">{p.address || p.customer_name || ''}</div></div>
                      </button>
                    ))}
                  </div>
                )}
                <div className="mt-6 flex flex-col items-center gap-4">
                  <button type="button" onClick={start} disabled={!projekt || !!busy} className="w-44 h-44 rounded-full bg-[#C41E3A] text-white shadow-[0_20px_50px_-15px_rgba(196,30,58,0.7)] flex flex-col items-center justify-center gap-1 text-[18px] font-bold active:scale-95 transition-transform disabled:opacity-40">
                    <Play size={40} /> Start
                  </button>
                  <div className="rounded-2xl bg-[#F5F5F7] px-4 w-full max-w-sm"><Toggle checked={gps} onChange={setGps} label="Standort mitspeichern" hint="Beim Ein- und Ausstempeln (Nachweis für den Auftraggeber)" /></div>
                </div>
              </>
            ) : (
              <div className="flex flex-col items-center gap-5">
                <div className="text-[13px] text-[#6E6E73] flex items-center gap-2"><AppIcon color={laufend.project_color || '#C41E3A'} text={initials(laufend.project_name)} size={28} className="rounded-lg" /> {laufend.project_name} · seit {new Date(laufend.start_at).toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' })} Uhr{offline && <span className="inline-flex items-center gap-1 text-[11px] font-medium bg-[#FFF4E5] text-[#B25E00] rounded-full px-2 py-0.5"><WifiOff size={11} /> offline</span>}</div>
                <div className={`text-[56px] font-bold tracking-tight tabular-nums leading-none ${laufend.pause_laeuft ? 'text-[#B25E00]' : ''}`}>{fmtClock(sekunden)}</div>
                <div className="text-[13px] text-[#6E6E73] flex items-center gap-1.5">{laufend.pause_laeuft ? <><Coffee size={14} /> Pause läuft</> : `Pause bisher ${laufend.pause_minuten} Min.`}{laufend.gps_start ? <span className="inline-flex items-center gap-1 ml-2"><MapPin size={13} /> Standort</span> : null}</div>
                {laufend.lange && <div className="rounded-2xl bg-[#FFF4E5] px-4 py-2 text-[13px] text-[#7A4100] flex items-center gap-2"><AlertTriangle size={15} /> Schon über 10 Stunden eingestempelt – vergessen auszustempeln?</div>}
                <div className="flex gap-3">
                  <Btn variant="soft" size="lg" onClick={() => pause(laufend.pause_laeuft)} loading={busy === 'pause'}>{laufend.pause_laeuft ? <><Play size={18} /> Weiter</> : <><Pause size={18} /> Pause</>}</Btn>
                  <Btn variant="dark" size="lg" onClick={() => setStopDialog(true)}><Square size={18} /> Ausstempeln</Btn>
                </div>
              </div>
            )}
          </Card>

          <div className="space-y-4">
            {isBuero && (
              <Card className="p-5">
                <h2 className="text-[16px] mb-2 flex items-center gap-2"><Users size={16} /> Gerade im Einsatz</h2>
                {imEinsatz.length === 0 ? <p className="text-[13px] text-[#6E6E73]">Niemand eingestempelt.</p> : (
                  <ul className="divide-y divide-black/[0.06] text-[14px]">{imEinsatz.map((s) => <li key={s.id} className="py-2 flex items-center justify-between gap-2"><span className="min-w-0"><span className="font-medium">{s.user_name}</span><span className="block text-[12px] text-[#6E6E73] truncate">{s.project_name} · {fmtHours(s.minuten)}{s.pause_laeuft ? ' · Pause' : ''}{s.lange ? ' · über 10 h!' : ''}</span></span>{s.lange && <Btn size="sm" variant="soft" onClick={() => beenden(s)}>Beenden</Btn>}</li>)}</ul>
                )}
              </Card>
            )}
            <Card className="p-5">
              <h2 className="text-[16px] mb-2 flex items-center gap-2"><Clock size={16} /> Meine letzten Zeiten</h2>
              {letzte.length === 0 ? <p className="text-[13px] text-[#6E6E73]">Noch nichts erfasst.</p> : (
                <ul className="divide-y divide-black/[0.06] text-[14px]">
                  {letzte.map((e) => <li key={e.id} className="py-2"><div className="flex justify-between gap-2"><span className="font-medium">{fmtDate(fromKey(e.date))} · {e.start_time}–{e.end_time}</span><span className="text-[#C41E3A] font-semibold">{fmtHours(e.net_minutes)}</span></div><div className="text-[12px] text-[#6E6E73] truncate">{e.project_name}{e.service_name ? ` · ${e.service_name}` : ''}{e.activity ? ` · ${e.activity}` : ''}{e.warnungen?.length ? ' · ⚠ ArbZG' : ''}</div></li>)}
                </ul>
              )}
            </Card>
          </div>
        </div>
      )}

      <Sheet open={stopDialog} onOpenChange={setStopDialog} title="Ausstempeln" subtitle={laufend ? `${laufend.project_name} · ${fmtClock(sekunden)}` : ''}>
        <div className="space-y-4">
          {status?.leistungen?.length > 0 && (
            <div>
              <span className="block text-[13px] font-medium text-[#6E6E73] mb-2 flex items-center gap-1.5"><Tag size={14} /> Leistung</span>
              <div className="flex gap-2 flex-wrap"><Chip active={!service} onClick={() => setService('')}>Keine</Chip>{status.leistungen.map((l) => <Chip key={l.id} active={service === l.id} onClick={() => setService(l.id)}>{l.name}</Chip>)}</div>
            </div>
          )}
          <div className="flex items-center justify-between"><span className="text-[13px] font-medium text-[#6E6E73]">Was wurde gemacht? (optional)</span><MicButton onText={(t) => setActivity((a) => [a, t].filter(Boolean).join(' '))} /></div>
          <TextArea rows={2} value={activity} onChange={(e) => setActivity(e.target.value)} placeholder="z. B. Unterhaltsreinigung EG, Treppenhaus" />
          <div className="flex gap-2 flex-wrap">{['Unterhaltsreinigung', 'Grundreinigung', 'Glasreinigung', 'Treppenhaus'].map((t) => <Chip key={t} active={activity === t} onClick={() => setActivity(t)}>{t}</Chip>)}</div>
          <div className="flex justify-end gap-2"><Btn variant="soft" onClick={() => setStopDialog(false)}>Abbrechen</Btn><Btn variant="dark" onClick={stop} loading={busy === 'stop'}>{gps ? <MapPin size={16} /> : <MapPinOff size={16} />} Jetzt ausstempeln</Btn></div>
        </div>
      </Sheet>
    </Layout>
  );
}
