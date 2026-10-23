import React, { useEffect, useState } from 'react';
import { KeyRound, LogOut, Clock, Palmtree } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import Layout from '../components/Layout';
import { Personalakte } from './MitarbeiterDetailPage';
import { Btn, Card, Field, TextInput } from '../components/ui';
import { api } from '../lib/api';
import { useAuth } from '../lib/auth';
import { fmtHours, fmtSigned, MONTHS_DE } from '../lib/dates';

/** Eigenes Konto: Daten, Stundenkonto und Resturlaub, Passwort, eigene Personalakte (nur lesen). */
export default function ProfilPage() {
  const { user, firma, logout } = useAuth();
  const navigate = useNavigate();
  const [pw, setPw] = useState({ alt: '', neu: '' });
  const [busy, setBusy] = useState(false);
  const [konto, setKonto] = useState(null);
  useEffect(() => { api.get('/api/konto/meins').then(setKonto).catch(() => {}); }, []);
  const aendern = async (e) => {
    e.preventDefault();
    setBusy(true);
    try { await api.put('/api/auth/passwort', pw); toast.success('Passwort geändert'); setPw({ alt: '', neu: '' }); } catch (err) { toast.error(err.message); } finally { setBusy(false); }
  };
  const m = konto?.monat;
  return (
    <Layout title="Profil" subtitle={`${user?.name} · ${user?.rolle_name} bei ${firma?.name}`}>
      {konto && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-5">
          <Card className="p-4"><div className="text-[12px] text-[#6E6E73] flex items-center gap-1"><Clock size={13} /> Stundenkonto</div><div className={`text-[22px] font-bold tracking-tight ${konto.verlauf.saldo_minuten < 0 ? 'text-[#C41E3A]' : 'text-[#1B7F3B]'}`}>{konto.mitarbeiter.weekly_hours ? fmtSigned(konto.verlauf.saldo_minuten) : '–'}</div><div className="text-[11px] text-[#86868B]">{konto.mitarbeiter.weekly_hours ? `Soll ${konto.mitarbeiter.weekly_hours} Std./Woche` : 'keine Sollstunden hinterlegt'}</div></Card>
          <Card className="p-4"><div className="text-[12px] text-[#6E6E73]">{MONTHS_DE[m.monat - 1]}: Ist / Soll</div><div className="text-[22px] font-bold tracking-tight">{fmtHours(m.ist_minuten)}</div><div className="text-[11px] text-[#86868B]">von {fmtHours(m.soll_minuten)} · {fmtSigned(m.saldo_minuten)}</div></Card>
          <Card className="p-4"><div className="text-[12px] text-[#6E6E73] flex items-center gap-1"><Palmtree size={13} /> Resturlaub {konto.urlaub.jahr}</div><div className="text-[22px] font-bold tracking-tight">{String(konto.urlaub.rest).replace('.', ',')} Tage</div><div className="text-[11px] text-[#86868B]">{konto.urlaub.genommen} genommen · {konto.urlaub.geplant} geplant{konto.urlaub.beantragt ? ` · ${konto.urlaub.beantragt} beantragt` : ''}</div></Card>
          <Card className="p-4"><div className="text-[12px] text-[#6E6E73]">Anspruch</div><div className="text-[22px] font-bold tracking-tight">{String(konto.urlaub.anspruch + konto.urlaub.uebertrag).replace('.', ',')} Tage</div><div className="text-[11px] text-[#86868B]">{konto.urlaub.anspruch} + {konto.urlaub.uebertrag} Übertrag</div></Card>
        </div>
      )}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Card className="p-5 space-y-4">
          <h2 className="text-[16px]">Meine Daten</h2>
          <div className="text-[14px] space-y-1"><div><span className="text-[#6E6E73]">E-Mail:</span> {user?.email}</div><div><span className="text-[#6E6E73]">Personalnummer:</span> {user?.personalnummer || '–'}</div><div><span className="text-[#6E6E73]">Telefon:</span> {user?.phone || '–'}</div></div>
          <form onSubmit={aendern} className="space-y-3 pt-2 border-t border-black/[0.06]">
            <h3 className="text-[14px] font-semibold flex items-center gap-2"><KeyRound size={15} /> Passwort ändern</h3>
            <Field label="Bisheriges Passwort"><TextInput type="password" value={pw.alt} onChange={(e) => setPw({ ...pw, alt: e.target.value })} required autoComplete="current-password" /></Field>
            <Field label="Neues Passwort (mindestens 8 Zeichen)"><TextInput type="password" value={pw.neu} onChange={(e) => setPw({ ...pw, neu: e.target.value })} required minLength={8} autoComplete="new-password" /></Field>
            <div className="flex justify-between"><Btn type="button" variant="ghost" size="sm" onClick={() => { logout(); navigate('/login'); }}><LogOut size={15} /> Abmelden</Btn><Btn type="submit" size="sm" loading={busy}>Speichern</Btn></div>
          </form>
        </Card>
        <div><h2 className="text-[16px] mb-2">Meine Personalakte</h2>{user && <Personalakte userId={user.id} readOnly />}</div>
      </div>
    </Layout>
  );
}
