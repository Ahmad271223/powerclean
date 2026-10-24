import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { CheckCircle2, FileDown, XCircle } from 'lucide-react';
import { toast } from 'sonner';
import { Btn, Card, Field, TextArea, TextInput } from '../components/ui';
import { API_BASE, api } from '../lib/api';
import { STATUS_CLS, STATUS_NAMEN, fmtGeld, fmtMenge } from '../lib/angebot';
import { fmtDate, fromKey } from '../lib/dates';

/** Öffentliche Angebotsseite für den Kunden (Antwortlink aus der E-Mail): Angebot lesen, PDF laden, annehmen oder ablehnen. Keine Anmeldung. */
export default function AngebotOeffentlichPage() {
  const { token } = useParams();
  const [a, setA] = useState(null);
  const [fehler, setFehler] = useState('');
  const [name, setName] = useState('');
  const [text, setText] = useState('');
  const [busy, setBusy] = useState('');
  useEffect(() => {
    api.get(`/api/oeffentlich/angebot/${token}`).then((r) => setA(r.angebot)).catch((err) => setFehler(err.status === 404 ? 'Dieses Angebot gibt es nicht oder der Link ist nicht mehr gültig.' : err.message));
  }, [token]);
  const antworten = async (entscheidung) => {
    if (name.trim().length < 2) { toast.error('Bitte Ihren Namen eingeben'); return; }
    setBusy(entscheidung);
    try {
      const r = await api.post(`/api/oeffentlich/angebot/${token}/antwort`, { entscheidung, name: name.trim(), text });
      setA(r.angebot);
      toast.success(entscheidung === 'angenommen' ? 'Vielen Dank – das Angebot ist angenommen.' : 'Ihre Antwort wurde übermittelt.');
    } catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };
  const pdf = `${API_BASE}/api/oeffentlich/angebot/${token}/angebot.pdf`;
  return (
    <div className="ts-app min-h-screen bg-[#F5F5F7] px-4 py-6 sm:py-10">
      <div className="max-w-3xl mx-auto space-y-4">
        {fehler && <Card className="p-6 text-[15px]">{fehler}</Card>}
        {!a && !fehler && <Card className="p-6 text-[14px] text-[#6E6E73]">Angebot wird geladen …</Card>}
        {a && (
          <>
            <Card className="p-5 sm:p-8">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="text-[13px] text-[#6E6E73]">{a.firma?.name}</div>
                  <h1 className="text-[22px] font-semibold leading-tight mt-1">Angebot {a.nummer}{a.version > 1 ? ` (Version ${a.version})` : ''}</h1>
                  {a.titel && <div className="text-[16px] mt-0.5">{a.titel}</div>}
                  <div className="text-[13px] text-[#6E6E73] mt-2">Datum {a.datum ? fmtDate(fromKey(a.datum)) : '–'}{a.gueltig_bis ? ` · gültig bis ${fmtDate(fromKey(a.gueltig_bis))}` : ''}{a.kunde?.name ? ` · für ${a.kunde.name}` : ''}</div>
                  <span className={`inline-block mt-2 text-[11px] font-semibold rounded-full px-2 py-0.5 ${STATUS_CLS[a.status] || ''}`}>{STATUS_NAMEN[a.status] || a.status}</span>
                </div>
                {a.firma?.logo && <img src={a.firma.logo} alt="" className="max-h-16 max-w-[160px] object-contain" />}
              </div>
              {a.einleitung && <p className="text-[14px] mt-4 whitespace-pre-line">{a.einleitung}</p>}
              <div className="overflow-x-auto mt-4">
                <table className="w-full text-[13px] min-w-[560px]">
                  <thead><tr className="text-left text-[#6E6E73] text-[12px]"><th className="py-2 pr-2 w-12">Pos.</th><th className="py-2 pr-2">Leistung</th><th className="py-2 pr-2 text-right">Menge</th><th className="py-2 pr-2">Einheit</th><th className="py-2 pr-2 text-right">Einzelpreis</th><th className="py-2 text-right">Gesamt</th></tr></thead>
                  <tbody>
                    {a.positionen.map((p) => (
                      <tr key={p.id} className={`border-t border-black/[0.06] align-top ${p.art === 'titel' ? 'bg-[#FAFAFA] font-semibold' : ''}`}>
                        <td className="py-2 pr-2 text-[#6E6E73]">{p.nr}</td>
                        <td className="py-2 pr-2" colSpan={p.art === 'titel' || p.art === 'text' ? 5 : 1}>
                          <div>{p.text}</div>
                          {p.beschreibung && <div className="text-[12px] text-[#6E6E73] whitespace-pre-line">{p.beschreibung}</div>}
                          {p.alternativ && <div className="text-[11px] text-[#B25E00] font-semibold">Alternativposition – nicht in der Summe</div>}
                          {p.eventual && <div className="text-[11px] text-[#B25E00] font-semibold">Eventualposition – nur bei Bedarf</div>}
                        </td>
                        {p.art !== 'titel' && p.art !== 'text' && (<>
                          <td className="py-2 pr-2 text-right">{fmtMenge(p.menge)}</td><td className="py-2 pr-2">{p.einheit}</td>
                          <td className="py-2 pr-2 text-right">{fmtGeld(p.einzelpreis)}</td><td className={`py-2 text-right ${p.zaehlt === false ? 'text-[#6E6E73]' : 'font-medium'}`}>{fmtGeld(p.gesamt)}</td>
                        </>)}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="mt-4 ml-auto max-w-sm text-[14px] space-y-1">
                <div className="flex justify-between"><span>Summe netto</span><span>{fmtGeld(a.summen?.positionen_netto)}</span></div>
                {(a.summen?.zuschlaege || []).map((z, i) => <div key={i} className="flex justify-between"><span>zzgl. {z.text} ({fmtMenge(z.prozent)} %)</span><span>{fmtGeld(z.betrag)}</span></div>)}
                {a.summen?.rabatt_betrag > 0 && <div className="flex justify-between"><span>abzüglich Rabatt ({fmtMenge(a.summen.rabatt_prozent)} %)</span><span>– {fmtGeld(a.summen.rabatt_betrag)}</span></div>}
                <div className="flex justify-between"><span>Nettobetrag</span><span>{fmtGeld(a.summen?.netto)}</span></div>
                <div className="flex justify-between"><span>{a.summen?.steuer?.kategorie === 'S' ? `zzgl. ${fmtMenge(a.summen.ust_satz)} % USt.` : 'Umsatzsteuer'}</span><span>{fmtGeld(a.summen?.ust)}</span></div>
                <div className="flex justify-between font-semibold text-[16px] border-t border-black/20 pt-1"><span>Angebotssumme</span><span>{fmtGeld(a.summen?.brutto)}</span></div>
                {a.summen?.steuer?.hinweis && <div className="text-[12px] text-[#6E6E73]">{a.summen.steuer.hinweis}.</div>}
              </div>
              {a.zahlungsbedingungen && <p className="text-[13px] mt-4"><span className="font-semibold">Zahlungsbedingungen:</span> {a.zahlungsbedingungen}</p>}
              {a.schluss && <p className="text-[14px] mt-2 whitespace-pre-line">{a.schluss}</p>}
              <div className="mt-5"><a href={pdf} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 h-10 px-4 rounded-full bg-[#1D1D1F] text-white text-[14px] font-semibold"><FileDown size={16} /> Angebot als PDF</a></div>
            </Card>
            <Card className="p-5 sm:p-8">
              {a.status === 'angenommen' ? (
                <div className="flex items-start gap-3 text-[15px]"><CheckCircle2 size={22} className="text-[#1B7F3B] shrink-0" /><div><div className="font-semibold">Angebot angenommen</div><div className="text-[#6E6E73] text-[14px]">{a.annahme?.von_name ? `durch ${a.annahme.von_name}` : ''}{a.annahme?.am ? ` am ${fmtDate(fromKey(a.annahme.am))}` : ''}. {a.firma?.name} meldet sich zu den nächsten Schritten.</div></div></div>
              ) : a.status === 'abgelehnt' ? (
                <div className="flex items-start gap-3 text-[15px]"><XCircle size={22} className="text-[#C41E3A] shrink-0" /><div><div className="font-semibold">Angebot abgelehnt</div><div className="text-[#6E6E73] text-[14px]">Vielen Dank für Ihre Rückmeldung.</div></div></div>
              ) : !a.antwort_moeglich ? (
                <p className="text-[14px] text-[#6E6E73]">{a.status === 'abgelaufen' ? 'Dieses Angebot ist abgelaufen. Bitte fragen Sie bei Interesse ein neues Angebot an.' : 'Dieses Angebot kann nicht mehr online beantwortet werden.'}</p>
              ) : (
                <>
                  <h2 className="text-[17px]">Angebot online beantworten</h2>
                  <p className="text-[13px] text-[#6E6E73] mt-1 mb-3">Mit „Angebot annehmen“ erteilen Sie {a.firma?.name} den Auftrag zu den genannten Bedingungen. Ihr Name wird als Auftraggeber festgehalten.</p>
                  <Field label="Ihr Name"><TextInput value={name} onChange={(e) => setName(e.target.value)} placeholder="Vor- und Nachname" /></Field>
                  <Field label="Nachricht (optional)" className="mt-3"><TextArea rows={2} value={text} onChange={(e) => setText(e.target.value)} placeholder="z. B. gewünschter Starttermin oder Rückfragen" /></Field>
                  <div className="flex flex-wrap gap-2 mt-4">
                    <Btn onClick={() => antworten('angenommen')} loading={busy === 'angenommen'}><CheckCircle2 size={16} /> Angebot annehmen</Btn>
                    <Btn variant="soft" onClick={() => antworten('abgelehnt')} loading={busy === 'abgelehnt'}><XCircle size={16} /> Ablehnen</Btn>
                  </div>
                </>
              )}
            </Card>
            <p className="text-[11px] text-[#86868B] text-center">Erstellt mit Stundenzettel Pro. {a.firma?.name}{a.firma?.street ? ` · ${a.firma.street}, ${a.firma.zip_code} ${a.firma.city}` : ''}{a.firma?.email ? ` · ${a.firma.email}` : ''}</p>
          </>
        )}
      </div>
    </div>
  );
}
