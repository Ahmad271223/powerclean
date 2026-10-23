import React, { useState } from 'react';
import { CalendarDays } from 'lucide-react';
import { toast } from 'sonner';
import { login } from '@/lib/ts';
import { Btn, Card, Field, TextInput } from './ui';

/** Login screen for the Stundenzettel app (uses the admin account). */
export default function TsLogin({ onLogin }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await login(username, password);
      onLogin();
    } catch (error) {
      console.error('Login error:', error);
      toast.error('Ungültige Anmeldedaten');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="ts-app min-h-screen flex items-center justify-center p-6" data-testid="ts-login">
      <Card className="w-full max-w-[400px] p-8 sm:p-10">
        <div className="flex flex-col items-center text-center mb-8">
          <span className="w-16 h-16 rounded-[20px] bg-[#C41E3A] text-white flex items-center justify-center shadow-[0_12px_28px_-10px_rgba(196,30,58,0.6)]">
            <CalendarDays size={30} />
          </span>
          <h1 className="text-[28px] mt-5 leading-none">Stundenzettel</h1>
          <p className="text-[14px] text-[#6E6E73] mt-2">Projekte · Kalender · Rechnungen</p>
        </div>

        <form onSubmit={submit} className="space-y-4">
          <Field label="Benutzername">
            <TextInput value={username} onChange={(e) => setUsername(e.target.value)} placeholder="admin" required autoComplete="username" className="h-12" data-testid="ts-username" />
          </Field>
          <Field label="Passwort">
            <TextInput type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" required autoComplete="current-password" className="h-12" data-testid="ts-password" />
          </Field>
          <Btn type="submit" size="lg" loading={busy} className="w-full mt-2" data-testid="ts-login-button">Anmelden</Btn>
        </form>
      </Card>
    </div>
  );
}
