import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Plus, ShieldCheck, Trash2, UserCog } from 'lucide-react';
import { toast } from 'sonner';
import Layout, { Ladeanzeige } from '../components/Layout';
import { Btn, Card, Field, Select, TextInput } from '../components/ui';
import { api } from '../lib/api';
import { useAuth } from '../lib/auth';

const RECHTE = [
  ['Angebote und Preise der Bieter', 'Projektleitung des Bauprojekts (Inhaber, Büro mit Eintrag)', 'nie andere Bieter, nie Mitarbeiter'],
  ['Interne Kalkulation, Zielpreis, Budget', 'Projektleitung der eigenen Firma', 'nie beteiligte Firmen'],
  ['Stundenlöhne, Personal- und Lohndaten', 'Büro und Inhaber der jeweiligen Firma', 'nie Auftraggeber, nie Partnerfirmen'],
  ['Rechnungen', 'Büro und Inhaber der ausstellenden Firma', 'nie Auftraggeber über die Plattform'],
  ['Aufgaben, Lieferungen, Mängel, Berichte', 'Projektleitung sieht alles; beteiligte Firmen nur ihre eigenen', 'Mitarbeiter nur zugeteilte Aufgaben'],
  ['Nachträge und Abnahmen', 'Projektleitung entscheidet; die beauftragte Firma reicht ein und bestätigt', 'Mitarbeiter nicht'],
  ['Namen der Mitarbeiter anderer Firmen', 'nur nach ausdrücklicher Freigabe der Partnerfirma', 'sonst nur Anzahlen'],
];

/** Projektleiter & Rechte: Büro-Konten den Bauprojekten zuordnen; ein Projekt mit eingetragenen Leitern sehen nur diese und zugewiesene Mitarbeiter. */
export default function ProjektleiterPage() {
  const { isBuero } = useAuth();
  const [d, setD] = useState(null);
  const [form, setForm] = useState({ user_id: '', project_id: '', funktion: 'Projektleitung' });
  const [busy, setBusy] = useState('');
  const laden = useCallback(() => api.get('/api/firma/projektleiter').then((r) => { setD(r); setForm((f) => ({ ...f, user_id: f.user_id || r.nutzer[0]?.id || '', project_id: f.project_id || r.projekte.find((p) => !p.verknuepft)?.id || '' })); }).catch((err) => toast.error(err.message)), []);
  useEffect(() => { laden(); }, [laden]);
  const zuordnen = async (e) => {
    e.preventDefault();
    if (!form.user_id || !form.project_id) return;
    setBusy('zuordnen');
    try { await api.post(`/api/projekte/${form.project_id}/leiter`, { user_id: form.user_id, funktion: form.funktion || 'Projektleitung' }); toast.success('Projektleitung eingetragen'); laden(); }
    catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };
  const entfernen = async (projectId, userId) => {
    if (!window.confirm('Projektleitung entfernen?')) return;
    setBusy(`${projectId}-${userId}`);
    try { await api.del(`/api/projekte/${projectId}/leiter/${userId}`); toast.success('Entfernt'); laden(); } catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };
  if (!isBuero) return null;
  if (!d) return <Layout title="Projektleiter & Rechte"><Ladeanzeige /></Layout>;
  const eigene = d.projekte.filter((p) => !p.verknuepft);
  return (
    <Layout title="Projektleiter & Rechte" subtitle="Persönliche Logins für Projektleiter: Jeder sieht nur die Bauprojekte, für die er eingetragen ist. Rechte werden serverseitig geprüft.">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Card className="p-5 space-y-3">
          <h2 className="text-[17px] flex items-center gap-2"><UserCog size={17} /> Projektleitung zuordnen</h2>
          <form onSubmit={zuordnen} className="grid grid-cols-1 sm:grid-cols-[1fr_1fr_1fr_auto] gap-3 items-end">
            <Field label="Nutzer (Büro/Inhaber)"><Select value={form.user_id} onChange={(e) => setForm({ ...form, user_id: e.target.value })} className="w-full">{d.nutzer.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}</Select></Field>
            <Field label="Bauprojekt"><Select value={form.project_id} onChange={(e) => setForm({ ...form, project_id: e.target.value })} className="w-full">{eigene.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</Select></Field>
            <Field label="Funktion"><TextInput value={form.funktion} onChange={(e) => setForm({ ...form, funktion: e.target.value })} placeholder="Projektleitung" /></Field>
            <Btn type="submit" loading={busy === 'zuordnen'} disabled={!eigene.length}><Plus size={15} /> Eintragen</Btn>
          </form>
          <p className="text-[12px] text-[#86868B]">{d.hinweis} Neue Projektleiter lädst du unter „Mitarbeiter“ mit der Rolle Büro ein.</p>
          <ul className="divide-y divide-black/[0.06]">
            {d.nutzer.map((u) => (
              <li key={u.id} className="py-2.5 text-[14px]">
                <div className="font-semibold">{u.name} <span className="text-[12px] text-[#6E6E73] font-normal">· {u.rolle_name} · {u.email}</span></div>
                {u.projekte.length === 0 ? <div className="text-[12px] text-[#86868B]">{u.role === 'inhaber' ? 'Inhaber sehen alle Projekte.' : 'Kein Projekt eingetragen – sieht nur Projekte ohne Projektleiter-Eintrag.'}</div> : (
                  <ul className="mt-1 flex flex-wrap gap-1.5">{u.projekte.map((p) => <li key={p.id} className="inline-flex items-center gap-1 text-[12px] bg-[#F5F5F7] rounded-full pl-3 pr-1 py-0.5"><Link to={`/projekte/${p.id}`} className="font-medium">{p.name}</Link>{p.funktion ? <span className="text-[#6E6E73]">· {p.funktion}</span> : null}<button type="button" className="w-6 h-6 rounded-full hover:bg-black/[0.06] flex items-center justify-center text-[#86868B]" title="Entfernen" onClick={() => entfernen(p.id, u.id)} disabled={busy === `${p.id}-${u.id}`}><Trash2 size={12} /></button></li>)}</ul>
                )}
              </li>
            ))}
          </ul>
        </Card>
        <div className="space-y-5">
          <Card className="p-5">
            <h2 className="text-[17px] flex items-center gap-2 mb-2">Bauprojekte und ihre Leitung</h2>
            {eigene.length === 0 ? <p className="text-[14px] text-[#6E6E73]">Noch keine Bauprojekte.</p> : (
              <ul className="divide-y divide-black/[0.06] text-[14px]">
                {eigene.map((p) => <li key={p.id} className="py-2 flex items-center gap-2"><Link to={`/projekte/${p.id}`} className="flex-1 min-w-0 truncate font-medium">{p.name}</Link>{p.gu_abo === 'aktiv' && <span className="text-[11px] font-medium text-[#1B7F3B] bg-[#E8F8EC] rounded-full px-2 py-0.5">GU-Projekt</span>}<span className="text-[12px] text-[#6E6E73]">{p.leiter_ids.length ? `${p.leiter_ids.length} Leiter` : 'alle Büro-Konten'}</span></li>)}
              </ul>
            )}
          </Card>
          <Card className="p-5">
            <h2 className="text-[17px] flex items-center gap-2 mb-2"><ShieldCheck size={17} /> Wer sieht was</h2>
            <table className="w-full text-[13px]">
              <thead><tr className="text-left text-[#6E6E73]"><th className="py-1 pr-2 font-medium">Daten</th><th className="py-1 pr-2 font-medium">Sehen dürfen</th><th className="py-1 font-medium">Nie</th></tr></thead>
              <tbody>{RECHTE.map(([a, b, c]) => <tr key={a} className="border-t border-black/[0.06] align-top"><td className="py-1.5 pr-2 font-medium">{a}</td><td className="py-1.5 pr-2">{b}</td><td className="py-1.5 text-[#6E6E73]">{c}</td></tr>)}</tbody>
            </table>
          </Card>
        </div>
      </div>
    </Layout>
  );
}
