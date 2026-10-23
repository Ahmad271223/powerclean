import React, { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { CalendarDays, LogIn, Building2, KeyRound } from 'lucide-react';
import { toast } from 'sonner';
import { api } from '../lib/api';
import { useAuth } from '../lib/auth';
import { Btn, Card, Field, TextInput } from '../components/ui';

function Rahmen({ title, text, children }) {
  return (
    <div className="ts-app safe-top min-h-screen flex items-center justify-center p-5">
      <Card className="w-full max-w-md p-7 sm:p-9">
        <div className="flex items-center gap-3 mb-6">
          <span className="w-11 h-11 rounded-2xl bg-[#C41E3A] text-white flex items-center justify-center"><CalendarDays size={22} /></span>
          <div><div className="font-bold text-[18px] leading-tight">Stundenzettel Pro</div><div className="text-[12px] text-[#6E6E73]">Zeiterfassung für Reinigung und Handwerk</div></div>
        </div>
        <h1 className="text-[26px] leading-none">{title}</h1>
        {text && <p className="text-[14px] text-[#6E6E73] mt-2">{text}</p>}
        <div className="mt-6">{children}</div>
      </Card>
    </div>
  );
}

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: '', password: '' });
  const [busy, setBusy] = useState(false);
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try { await login(form.email.trim(), form.password); navigate('/', { replace: true }); }
    catch (err) { toast.error(err.message); } finally { setBusy(false); }
  };
  return (
    <Rahmen title="Anmelden">
      <form onSubmit={submit} className="space-y-4">
        <Field label="E-Mail"><TextInput type="email" autoComplete="username" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required /></Field>
        <Field label="Passwort"><TextInput type="password" autoComplete="current-password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required /></Field>
        <Btn type="submit" size="lg" className="w-full" loading={busy}><LogIn size={18} /> Anmelden</Btn>
      </form>
      <p className="text-[13px] text-[#6E6E73] mt-6 text-center">Neue Firma? <Link to="/registrieren" className="text-[#C41E3A] font-medium">14 Tage kostenlos testen</Link></p>
    </Rahmen>
  );
}

export function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ firma_name: '', name: '', email: '', password: '' });
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => { const v = e.target.value; setForm((f) => ({ ...f, [k]: v })); };
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try { await register({ ...form, firma_name: form.firma_name.trim(), name: form.name.trim(), email: form.email.trim() }); toast.success('Willkommen! Deine Firma ist angelegt.'); navigate('/firma', { replace: true }); }
    catch (err) { toast.error(err.message); } finally { setBusy(false); }
  };
  return (
    <Rahmen title="Firma registrieren" text="Du bist Inhaber. Danach lädst du dein Team ein, jeder stempelt am Handy, du bekommst Stundenzettel, Rechnungen und den Lohnexport.">
      <form onSubmit={submit} className="space-y-4">
        <Field label="Firmenname"><TextInput value={form.firma_name} onChange={set('firma_name')} required placeholder="z. B. PowerCleanService" /></Field>
        <Field label="Dein Name"><TextInput value={form.name} onChange={set('name')} required autoComplete="name" /></Field>
        <Field label="E-Mail"><TextInput type="email" value={form.email} onChange={set('email')} required autoComplete="username" /></Field>
        <Field label="Passwort (mindestens 8 Zeichen)"><TextInput type="password" value={form.password} onChange={set('password')} required minLength={8} autoComplete="new-password" /></Field>
        <Btn type="submit" size="lg" className="w-full" loading={busy}><Building2 size={18} /> Kostenlos starten</Btn>
      </form>
      <p className="text-[13px] text-[#6E6E73] mt-6 text-center">Schon ein Konto? <Link to="/login" className="text-[#C41E3A] font-medium">Anmelden</Link></p>
    </Rahmen>
  );
}

export function EinladungPage() {
  const { token } = useParams();
  const { acceptInvite } = useAuth();
  const navigate = useNavigate();
  const [info, setInfo] = useState(null);
  const [fehler, setFehler] = useState('');
  const [pw, setPw] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => { api.get(`/api/auth/einladung/${token}`).then(setInfo).catch((err) => setFehler(err.message)); }, [token]);
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try { await acceptInvite(token, pw); toast.success('Konto eingerichtet'); navigate('/', { replace: true }); }
    catch (err) { toast.error(err.message); } finally { setBusy(false); }
  };
  return (
    <Rahmen title="Einladung" text={info ? `Hallo ${info.name}, ${info.firma_name} hat dich eingeladen. Vergib ein Passwort für deinen Zugang (${info.email}).` : undefined}>
      {fehler ? <p className="text-[14px] text-[#C41E3A]">{fehler}</p> : (
        <form onSubmit={submit} className="space-y-4">
          <Field label="Passwort (mindestens 8 Zeichen)"><TextInput type="password" value={pw} onChange={(e) => setPw(e.target.value)} required minLength={8} autoComplete="new-password" /></Field>
          <Btn type="submit" size="lg" className="w-full" loading={busy} disabled={!info}><KeyRound size={18} /> Zugang einrichten</Btn>
        </form>
      )}
      <p className="text-[13px] text-[#6E6E73] mt-6 text-center"><Link to="/login" className="text-[#C41E3A] font-medium">Zur Anmeldung</Link></p>
    </Rahmen>
  );
}
