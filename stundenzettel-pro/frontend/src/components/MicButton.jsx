import React, { useEffect, useRef, useState } from 'react';
import { Mic, MicOff } from 'lucide-react';
import { toast } from 'sonner';

const Recognition = typeof window !== 'undefined' ? (window.SpeechRecognition || window.webkitSpeechRecognition) : null;
export const sprachEingabeMoeglich = !!Recognition;

/** Spracheingabe (Web Speech API, Chrome/Android, Safari): erkannter Text geht an `onText`. */
export default function MicButton({ onText, lang = 'de-DE', className = '' }) {
  const [aktiv, setAktiv] = useState(false);
  const ref = useRef(null);
  useEffect(() => () => { try { ref.current?.stop(); } catch { /* ignore */ } }, []);
  if (!Recognition) return null;
  const toggle = () => {
    if (aktiv) { try { ref.current?.stop(); } catch { /* ignore */ } setAktiv(false); return; }
    try {
      const r = new Recognition();
      r.lang = lang;
      r.interimResults = false;
      r.maxAlternatives = 1;
      r.onresult = (e) => { const t = Array.from(e.results).map((x) => x[0]?.transcript || '').join(' ').trim(); if (t) onText?.(t); };
      r.onerror = (e) => { if (e.error !== 'aborted') toast.error('Spracheingabe nicht möglich'); setAktiv(false); };
      r.onend = () => setAktiv(false);
      ref.current = r;
      r.start();
      setAktiv(true);
    } catch { toast.error('Spracheingabe nicht möglich'); setAktiv(false); }
  };
  return (
    <button type="button" onClick={toggle} title={aktiv ? 'Aufnahme beenden' : 'Tätigkeit einsprechen'} aria-pressed={aktiv}
      className={`inline-flex items-center justify-center w-9 h-9 rounded-full transition-colors ${aktiv ? 'bg-[#C41E3A] text-white animate-pulse' : 'bg-black/[0.05] text-[#1D1D1F] hover:bg-black/[0.09]'} ${className}`}>
      {aktiv ? <MicOff size={16} /> : <Mic size={16} />}
    </button>
  );
}
