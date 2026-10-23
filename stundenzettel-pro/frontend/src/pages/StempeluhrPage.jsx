import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Play, Square, Pause, MapPin, MapPinOff, Coffee, Clock, Users, WifiOff, QrCode, AlertTriangle, Tag, RefreshCw, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import Layout, { Ladeanzeige } from '../components/Layout';
import MicButton from '../components/MicButton';
import { AppIcon, Btn, Card, Chip, Sheet, TextArea, Toggle } from '../components/ui';
import { api } from '../lib/api';
import { useAuth } from '../lib/auth';
import { addDays, fmtDate, fmtHours, fromKey, toKey } from '../lib/dates';
import { initials } from '../lib/utils';

const GPS_KEY = 'szpro-gps';
const pad = (n) => String(n).padStart(2, '0');
const fmtClock = (sek) => `${pad(Math.floor(sek / 3600))}:${pad(Math.floor((sek % 3600) / 60))}:${pad(sek % 60)}`;
const hhmm = (d) => `${pad(d.getHours())}:${pad(d.getMinutes())}`;
const lesen = (k, fallback) => { try { return JSON.parse(localStorage.getItem(k) || 'null') ?? fallback; } catch { return fallback; } };
const merken = (k, v) => { try { if (v == null) localStorage.removeItem(k); else localStorage.setItem(k, JSON.stringify(v)); } catch { /* ignore */ } };
const neueId = () => (window.crypto?.randomUUID ? window.crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`);

/** Offline-Daten liegen je Nutzer im Browser (gemeinsam genutzte Geräte); alte Schlüssel ohne Nutzer werden einmalig übernommen. */
function schluessel(userId) {
  const k = { stempel: `szpro-offline-stempel:${userId}`, queue: `szpro-offline-queue:${userId}`, status: `szpro-stempel-status:${userId}` };
  try {
    for (const [alt, neu] of [['szpro-offline-stempel', k.stempel], ['szpro-offline-queue', k.queue]]) {
      const v = localStorage.getItem(alt);
      if (v && !localStorage.getItem(neu)) localStorage.setItem(neu, v);
      if (v) localStorage.removeItem(alt);
    }
  } catch { /* ignore */ }
  return k;
}

function standort(aktiv) {
  if (!aktiv || !navigator.geolocation) return Promise.resolve(null);
  return new Promise((resolve) => {
    navigator.geolocation.getCurrentPosition(
      (p) => resolve({ lat: p.coords.latitude, lng: p.coords.longitude, accuracy: p.coords.accuracy }),
      () => resolve(null), { enableHighAccuracy: true, timeout: 8000, maximumAge: 60000 },
    );
  });
}

/** Sekundengenauer Stand einer Stempelung aus Zeitstempeln: Start, Pausen (laufende Pause bis jetzt), optional Server-Uhr. */
export function stempelStand(s, jetztMs = Date.now()) {
  const start = new Date(s.start_at).getTime();
  let pauseSek = 0;
  let laeuft = false;
  for (const p of s.pausen || []) {
    const von = new Date(p.von).getTime();
    const bis = p.bis ? new Date(p.bis).getTime() : jetztMs;
    if (!p.bis) laeuft = true;
    pauseSek += Math.max(0, Math.floor((bis - von) / 1000));
  }
  const brutto = Math.max(0, Math.floor((jetztMs - start) / 1000));
  const sekunden = Math.max(0, brutto - pauseSek);
  return { sekunden, minuten: Math.floor(sekunden / 60), pause_minuten: Math.floor(pauseSek / 60), pause_laeuft: laeuft };
}

/** Wartende Offline-Einträge an den Server schicken. Fehlgeschlagene Einträge bleiben mit Fehlergrund erhalten (nie stilles Verwerfen);
 *  jeder Eintrag trägt eine eindeutige offline_id, der Server legt ihn höchstens einmal an. */
export async function offlineSynchronisieren(queueKey) {
  const queue = lesen(queueKey, []);
  if (!queue.length) return { ok: 0, offen: 0 };
  const rest = [];
  let ok = 0;
  for (const eintrag of queue) {
    const payload = { ...eintrag };
    delete payload.fehler; delete payload.versuche;
    try { await api.post('/api/zeiten', { ...payload, offline: true }); ok += 1; }
    catch (err) {
      if (err.status === 0) rest.push(eintrag);                      // kein Netz: unverändert warten
      else rest.push({ ...eintrag, fehler: err.message, versuche: (eintrag.versuche || 0) + 1, fehler_at: new Date().toISOString() });
    }
  }
  merken(queueKey, rest.length ? rest : null);
  if (ok) toast.success(`${ok} Offline-Eintrag${ok > 1 ? 'e' : ''} nachgetragen`);
  return { ok, offen: rest.length };
}

/** Stempeluhr: Projekt wählen, Start/Pause/Stop. Anzeige aus Zeitstempeln (Server-Uhr), läuft ohne Netz weiter und holt den Stand nach. */
export default function StempeluhrPage() {
  const { isBuero, user } = useAuth();
  const { projectId: qrProjekt } = useParams();
  const K = schluessel(user?.id || 'anonym');
  const [status, setStatus] = useState(() => lesen(K.status, null));
  const [serverOffset, setServerOffset] = useState(0);   // Server-Uhr minus Geräte-Uhr in ms
  const [verbunden, setVerbunden] = useState(true);
  const [projekt, setProjekt] = useState(qrProjekt || '');
  const [gps, setGps] = useState(() => { try { return localStorage.getItem(GPS_KEY) === '1'; } catch { return false; } });
  const [tick, setTick] = useState(0);
  const [stopDialog, setStopDialog] = useState(false);
  const [activity, setActivity] = useState('');
  const [service, setService] = useState('');
  const [busy, setBusy] = useState('');
  const [letzte, setLetzte] = useState([]);
  const [imEinsatz, setImEinsatz] = useState([]);
  const [offline, setOffline] = useState(() => lesen(K.stempel, null));
  const [queue, setQueue] = useState(() => lesen(K.queue, []));
  const timer = useRef(null);
  const uebernahme = useRef(false);

  /** Offline gestartete Stempelung bei Netz in eine Server-Stempelung überführen (Startzeit und Pausen bleiben erhalten). */
  const offlineUebernehmen = useCallback(async () => {
    const s = lesen(K.stempel, null);
    if (!s || uebernahme.current) return;
    uebernahme.current = true;
    try {
      await api.post('/api/stempel/start', { project_id: s.project_id, gps: s.gps_start, start_at: s.start_at, pausen: s.pausen || [] });
      merken(K.stempel, null); setOffline(null);
      toast.success('Offline-Stempelung an den Server übergeben – die Uhr läuft weiter.');
    } catch (err) {
      if (err.status === 0) return;
      if (err.status === 409) { merken(K.stempel, null); setOffline(null); toast.info('Auf dem Server läuft bereits eine Stempelung – die Offline-Stempelung wurde verworfen.'); }
      else toast.error(`Offline-Stempelung konnte nicht übernommen werden: ${err.message}`);
    } finally { uebernahme.current = false; }
  }, [K.stempel]);

  const laden = useCallback(async () => {
    try {
      await offlineSynchronisieren(K.queue);
      setQueue(lesen(K.queue, []));
      await offlineUebernehmen();
      const vorher = Date.now();
      const s = await api.get('/api/stempel/status');
      const nachher = Date.now();
      if (s.jetzt) setServerOffset(new Date(s.jetzt).getTime() - Math.round((vorher + nachher) / 2));
      setStatus(s); setVerbunden(true);
      merken(K.status, { ...s, gespeichert_at: new Date().toISOString() });
      setProjekt((p) => p || (s.projekte.length === 1 ? s.projekte[0].id : ''));
      const heute = new Date();
      const z = await api.get(`/api/zeiten/meine?von=${toKey(addDays(heute, -6))}&bis=${toKey(heute)}`);
      setLetzte(z.eintraege.slice().reverse().slice(0, 8));
      if (isBuero) setImEinsatz((await api.get('/api/stempel/aktiv')).aktiv);
    } catch (err) {
      if (err.status === 0) {
        setVerbunden(false);
        // Ohne Netz: zuletzt bekannten Stand zeigen (eine laufende Server-Stempelung bleibt sichtbar, nichts springt auf Null)
        setStatus((s) => s || lesen(K.status, null) || { aktiv: null, projekte: [], minuten_heute: 0, leistungen: [] });
      } else toast.error(err.message);
    }
  }, [isBuero, K.queue, K.status, offlineUebernehmen]);

  useEffect(() => { laden(); }, [laden]);
  useEffect(() => {
    timer.current = setInterval(() => setTick((t) => t + 1), 1000);
    const refresh = setInterval(laden, 60000);
    const online = () => laden();
    const sichtbar = () => { if (document.visibilityState === 'visible') laden(); };
    window.addEventListener('online', online);
    document.addEventListener('visibilitychange', sichtbar);
    return () => { clearInterval(timer.current); clearInterval(refresh); window.removeEventListener('online', online); document.removeEventListener('visibilitychange', sichtbar); };
  }, [laden]);
  useEffect(() => { try { localStorage.setItem(GPS_KEY, gps ? '1' : '0'); } catch { /* ignore */ } }, [gps]);

  const aktiv = status?.aktiv;
  const jetztServer = Date.now() + serverOffset;
  const stand = offline ? stempelStand(offline) : aktiv ? stempelStand(aktiv, jetztServer) : null;
  const sekunden = stand ? stand.sekunden : 0;
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
        const s = { project_id: projekt, project_name: projektObj?.name || '', project_color: projektObj?.color || '', start_at: new Date().toISOString(), pausen: [], gps_start: pos, user_id: user?.id };
        merken(K.stempel, s); setOffline(s);
        toast.info('Kein Netz – offline eingestempelt. Sobald Netz da ist, übernimmt der Server die laufende Uhr.');
      }
    } catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };
  const pause = async (weiter) => {
    if (offline) {
      const s = { ...offline, pausen: [...(offline.pausen || [])] };
      if (weiter) { const l = s.pausen[s.pausen.length - 1]; if (l && !l.bis) s.pausen[s.pausen.length - 1] = { ...l, bis: new Date().toISOString() }; }
      else s.pausen.push({ von: new Date().toISOString(), bis: null });
      merken(K.stempel, s); setOffline(s); return;
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
        const st = stempelStand({ ...offline, pausen: (offline.pausen || []).map((p) => ({ ...p, bis: p.bis || jetzt.toISOString() })) }, jetzt.getTime());
        const payload = { offline_id: neueId(), project_id: offline.project_id, date: toKey(startD), start_time: hhmm(startD), end_time: hhmm(jetzt), pause_minutes: st.pause_minuten, activity, service_id: service || null, workers: 1, start_at: offline.start_at, end_at: jetzt.toISOString() };
        if (st.minuten >= 1) { const q = [...lesen(K.queue, []), payload]; merken(K.queue, q); setQueue(q); }
        merken(K.stempel, null); setOffline(null);
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
        if (r.eintrag.hinweise?.length) toast.warning(r.eintrag.hinweise.map((w) => w.text).join(' · '), { duration: 10000 });
      }
      await laden();
    } catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };
  const beenden = async (s) => {
    if (!window.confirm(`Stempelung von ${s.user_name} jetzt beenden? Der Eintrag endet mit der aktuellen Uhrzeit.`)) return;
    try { await api.post(`/api/stempel/${s.id}/beenden`, { activity: 'vom Büro beendet' }); toast.success('Beendet'); laden(); } catch (err) { toast.error(err.message); }
  };
  const queueVerwerfen = (eintrag) => {
    if (!window.confirm(`Offline-Eintrag vom ${fmtDate(fromKey(eintrag.date))} (${eintrag.start_time}–${eintrag.end_time}) endgültig verwerfen? Die Zeit müsste dann von Hand eingetragen werden.`)) return;
    const q = lesen(K.queue, []).filter((x) => x.offline_id !== eintrag.offline_id);
    merken(K.queue, q.length ? q : null); setQueue(q);
  };

  const laufend = offline ? { ...stand, project_name: offline.project_name, project_color: offline.project_color, start_at: offline.start_at, gps_start: offline.gps_start, lange: stand.minuten >= 600 } : aktiv ? { ...aktiv, ...stand, lange: stand.minuten >= 600 } : null;
  const fehlerhaft = queue.filter((e) => e.fehler);

  return (
    <Layout title="Stempeluhr" subtitle={status ? `Heute ${fmtHours(status.minuten_heute)} erfasst` : undefined}>
      {!verbunden && <div className="mb-4 rounded-2xl bg-black/[0.06] px-4 py-3 text-[13px] text-[#6E6E73] flex items-center gap-2"><WifiOff size={16} /> Kein Netz – angezeigt wird der zuletzt bekannte Stand{status?.gespeichert_at ? ` (${new Date(status.gespeichert_at).toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' })} Uhr)` : ''}. Stempeln geht offline weiter.</div>}
      {queue.length > 0 && (
        <div className="mb-4 rounded-2xl bg-[#FFF4E5] px-4 py-3 text-[14px] text-[#7A4100] space-y-2">
          <div className="flex items-center gap-3 flex-wrap"><WifiOff size={18} /> {queue.length} Offline-Eintrag{queue.length > 1 ? 'e warten' : ' wartet'} auf Übertragung. <Btn size="sm" variant="dark" onClick={laden}><RefreshCw size={14} /> Jetzt senden</Btn></div>
          {fehlerhaft.length > 0 && (
            <ul className="text-[13px] space-y-1">
              {fehlerhaft.map((e) => <li key={e.offline_id} className="flex items-start gap-2 flex-wrap"><AlertTriangle size={14} className="mt-0.5 shrink-0" /><span className="flex-1 min-w-[200px]">{fmtDate(fromKey(e.date))} {e.start_time}–{e.end_time}: vom Server abgelehnt – {e.fehler} (Versuch {e.versuche}). Der Eintrag bleibt gespeichert; bitte im Büro klären oder erneut senden.</span><Btn size="sm" variant="ghost" onClick={() => queueVerwerfen(e)}><Trash2 size={13} /> Verwerfen</Btn></li>)}
            </ul>
          )}
        </div>
      )}
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
                <div className="text-[13px] text-[#6E6E73] flex items-center gap-2 flex-wrap justify-center"><AppIcon color={laufend.project_color || '#C41E3A'} text={initials(laufend.project_name)} size={28} className="rounded-lg" /> {laufend.project_name} · seit {new Date(laufend.start_at).toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' })} Uhr{offline && <span className="inline-flex items-center gap-1 text-[11px] font-medium bg-[#FFF4E5] text-[#B25E00] rounded-full px-2 py-0.5"><WifiOff size={11} /> offline</span>}{!offline && laufend.offline_uebernommen && <span className="text-[11px] text-[#86868B]">offline gestartet</span>}</div>
                <div className={`text-[56px] font-bold tracking-tight tabular-nums leading-none ${laufend.pause_laeuft ? 'text-[#B25E00]' : ''}`} data-testid="stempel-uhr">{fmtClock(sekunden)}</div>
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
                  {letzte.map((e) => <li key={e.id} className="py-2"><div className="flex justify-between gap-2"><span className="font-medium">{fmtDate(fromKey(e.date))} · {e.start_time}–{e.end_time}</span><span className="text-[#C41E3A] font-semibold">{fmtHours(e.net_minutes)}</span></div><div className="text-[12px] text-[#6E6E73] truncate">{e.project_name}{e.service_name ? ` · ${e.service_name}` : ''}{e.activity ? ` · ${e.activity}` : ''}{e.warnungen?.length ? ' · ⚠ ArbZG' : ''}{e.pruefen ? ' · ⚠ bitte prüfen' : ''}</div></li>)}
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
