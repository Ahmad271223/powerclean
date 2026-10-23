import React, { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react';
import { Btn, Field, Sheet, TextArea, TextInput } from './ui';

const DialogContext = createContext(null);

/**
 * Eigene Dialoge statt window.prompt/confirm: funktionieren in jedem Browser (auch in eingebetteten Ansichten und in der App) und
 * sehen auf dem Handy aus wie der Rest der Oberfläche.
 *   const { fragen, bestaetigen } = useDialoge();
 *   const grund = await fragen({ titel: 'Zurückziehen', text: 'Grund:', pflicht: true });   // string oder null (abgebrochen)
 *   if (await bestaetigen({ titel: 'Löschen?', text: '…', gefaehrlich: true })) …          // true/false
 */
export function DialogProvider({ children }) {
  const [dialog, setDialog] = useState(null);
  const [wert, setWert] = useState('');
  const aufloesen = useRef(null);

  const schliessen = useCallback((ergebnis) => {
    const fn = aufloesen.current;
    aufloesen.current = null;
    setDialog(null);
    if (fn) fn(ergebnis);
  }, []);

  const fragen = useCallback((optionen) => new Promise((resolve) => {
    if (aufloesen.current) aufloesen.current(null);
    aufloesen.current = resolve;
    setWert(optionen.vorgabe || '');
    setDialog({ art: 'frage', ...optionen });
  }), []);

  const bestaetigen = useCallback((optionen) => new Promise((resolve) => {
    if (aufloesen.current) aufloesen.current(false);
    aufloesen.current = resolve;
    setDialog({ art: 'bestaetigung', ...optionen });
  }), []);

  const value = useMemo(() => ({ fragen, bestaetigen }), [fragen, bestaetigen]);
  const frage = dialog?.art === 'frage';
  const abbrechen = () => schliessen(frage ? null : false);
  const ok = (e) => {
    e?.preventDefault?.();
    if (frage) {
      if (dialog.pflicht && !wert.trim()) return;
      schliessen(wert.trim());
    } else schliessen(true);
  };
  return (
    <DialogContext.Provider value={value}>
      {children}
      <Sheet open={!!dialog} onOpenChange={(o) => { if (!o) abbrechen(); }} title={dialog?.titel || (frage ? 'Eingabe' : 'Bestätigen')} subtitle={dialog?.text} width="sm:max-w-md">
        {dialog && (
          <form onSubmit={ok} className="space-y-4">
            {frage && (
              <Field label={dialog.feld || ''} hint={dialog.hinweis}>
                {dialog.mehrzeilig
                  ? <TextArea rows={3} value={wert} onChange={(e) => setWert(e.target.value)} placeholder={dialog.platzhalter || ''} autoFocus />
                  : <TextInput type={dialog.passwort ? 'password' : 'text'} value={wert} onChange={(e) => setWert(e.target.value)} placeholder={dialog.platzhalter || ''} autoFocus autoComplete={dialog.passwort ? 'current-password' : 'off'} />}
              </Field>
            )}
            <div className="flex justify-end gap-2">
              <Btn type="button" variant="soft" onClick={abbrechen}>{dialog.abbrechen || 'Abbrechen'}</Btn>
              <Btn type="submit" variant={dialog.gefaehrlich ? 'danger' : 'primary'} disabled={frage && dialog.pflicht && !wert.trim()}>{dialog.ok || (frage ? 'Weiter' : 'Ja')}</Btn>
            </div>
          </form>
        )}
      </Sheet>
    </DialogContext.Provider>
  );
}

export function useDialoge() {
  const ctx = useContext(DialogContext);
  if (!ctx) {
    // Ohne Provider (z. B. in Tests): auf Browserdialoge zurückfallen
    return {
      fragen: async (o) => { try { return window.prompt(`${o.titel || ''}${o.text ? `\n${o.text}` : ''}`, o.vorgabe || ''); } catch { return null; } },
      bestaetigen: async (o) => { try { return window.confirm(`${o.titel || ''}${o.text ? `\n${o.text}` : ''}`); } catch { return false; } },
    };
  }
  return ctx;
}
