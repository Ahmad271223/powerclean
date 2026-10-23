import React, { useEffect, useState } from 'react';
import { ImageOff } from 'lucide-react';
import { fetchBlob } from '../lib/api';
import { bildPfad } from '../lib/fotos';

/** Foto aus der Akte mit Anmeldung laden (verkleinert) – normale <img>-Adressen tragen kein Token. */
export default function Bild({ id, max = 400, alt = '', className = '' }) {
  const [url, setUrl] = useState(null);
  const [fehler, setFehler] = useState(false);
  useEffect(() => {
    let aktiv = true;
    let objekt = null;
    setUrl(null); setFehler(false);
    fetchBlob(bildPfad(id, max)).then((blob) => { if (!aktiv) return; objekt = URL.createObjectURL(blob); setUrl(objekt); }).catch(() => { if (aktiv) setFehler(true); });
    return () => { aktiv = false; if (objekt) URL.revokeObjectURL(objekt); };
  }, [id, max]);
  if (fehler) return <div className={`flex items-center justify-center bg-black/[0.06] text-[#A1A1A6] ${className}`}><ImageOff size={18} /></div>;
  if (!url) return <div className={`animate-pulse bg-black/[0.06] ${className}`} />;
  return <img src={url} alt={alt} className={`object-cover ${className}`} loading="lazy" />;
}
