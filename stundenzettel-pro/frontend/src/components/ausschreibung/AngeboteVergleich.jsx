import React, { useCallback, useEffect, useState } from 'react';
import { ChevronDown, ChevronUp, FileText, Gavel, Scale } from 'lucide-react';
import { toast } from 'sonner';
import { Btn, Card, Chip, Empty, Field, Sheet, TextArea, TextInput, Toggle } from '../ui';
import { api, openFile } from '../../lib/api';
import { ANGEBOT_CLS, ANGEBOT_NAMEN, KRITERIEN, PREISARTEN, fmtGeld, fmtTag, fmtZeit } from '../../lib/ausschreibung';

const chip = (st) => <span className={`text-[11px] font-semibold rounded-full px-2 py-0.5 ${ANGEBOT_CLS[st] || ''}`}>{ANGEBOT_NAMEN[st] || st}</span>;

/** Eigentümerseite: eingegangene Angebote vergleichen (Preis, Termin, Vollständigkeit, Bewertung), prüfen, Rückfragen, ablehnen, Vergabe vorschlagen. */
export default function AngeboteVergleich({ ausschreibung: a, onChanged }) {
  const [d, setD] = useState(null);
  const [offen, setOffen] = useState(null);
  const [dialog, setDialog] = useState(null);   // { art: 'rueckfrage'|'abgelehnt'|'vergabe', angebot }
  const [text, setText] = useState('');
  const [frist, setFrist] = useState('');
  const [busy, setBusy] = useState('');
  const laden = useCallback(() => api.get(`/api/ausschreibungen/${a.id}/angebote`).then(setD).catch((err) => toast.error(err.message)), [a.id]);
  useEffect(() => { laden(); }, [laden]);
  const pruefung = async (g, status, nachricht = '', nachreichen_bis = null) => {
    setBusy(g.id + status);
    try { await api.post(`/api/angebote/${g.id}/pruefung`, { status, nachricht, nachreichen_bis: nachreichen_bis || null }); toast.success('Gespeichert – die Firma wurde benachrichtigt'); setDialog(null); setText(''); laden(); onChanged?.(); }
    catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };
  const vergabe = async (g) => {
    setBusy('vergabe');
    try { await api.post(`/api/ausschreibungen/${a.id}/vergabe`, { angebot_id: g.id, begruendung: text }); toast.success('Vergabe vorgeschlagen – wartet auf interne Freigabe'); setDialog(null); setText(''); laden(); onChanged?.(); }
    catch (err) { toast.error(err.message); } finally { setBusy(''); }
  };
  if (!d) return <Card className="p-8 text-center text-[#A1A1A6]">Wird geladen …</Card>;
  const vergabeMoeglich = ['veroeffentlicht', 'in_vergabe'].includes(a.status) && !a.vergabe;
  return (
    <div className="space-y-4">
      <Card className="p-4 flex flex-wrap items-center gap-4 text-[13px]">
        <span className="font-semibold text-[15px] flex items-center gap-2"><Scale size={16} /> {d.vergleich.length} Angebote</span>
        <span className="text-[#6E6E73]">Neu {a.zaehler?.neu ?? 0} · In Prüfung {a.zaehler?.in_pruefung ?? 0} · Rückfragen {a.zaehler?.rueckfragen ?? 0} · Abgelehnt {a.zaehler?.abgelehnt ?? 0}</span>
        {d.guenstigstes !== null && <span className="ml-auto text-[#6E6E73]">Spanne {fmtGeld(d.guenstigstes)} – {fmtGeld(d.teuerstes)}</span>}
      </Card>
      {d.vergleich.length === 0 ? <Card><Empty icon={Gavel} title="Noch keine Angebote" text="Eingereichte Angebote erscheinen hier mit Preis, Termin, Vollständigkeit und Bewertung. Entwürfe der Bieter sind nicht sichtbar." /></Card> : (
        <Card className="overflow-x-auto">
          <table className="w-full text-[13px] min-w-[760px]">
            <thead><tr className="text-left text-[11px] uppercase tracking-wider text-[#86868B] border-b border-black/[0.06]"><th className="px-4 py-2">Firma</th><th className="px-2 py-2 text-right">Netto</th><th className="px-2 py-2">Preisart</th><th className="px-2 py-2">Ausführung</th><th className="px-2 py-2">Eingang</th><th className="px-2 py-2 text-center">LV</th><th className="px-2 py-2 text-center">Dok.</th><th className="px-2 py-2 text-center">Punkte</th><th className="px-2 py-2">Status</th><th className="px-2 py-2" /></tr></thead>
            <tbody>
              {d.vergleich.map((z) => {
                const g = d.angebote.find((x) => x.id === z.angebot_id);
                const auf = offen === z.angebot_id;
                return (
                  <React.Fragment key={z.angebot_id}>
                    <tr className={`border-b border-black/[0.06] ${z.summe_netto === d.guenstigstes ? 'bg-[#E8F8EC]/60' : ''}`}>
                      <td className="px-4 py-2.5 font-medium">{z.firma_name}<span className="block text-[11px] text-[#6E6E73] font-normal">{z.firma_ort}{z.version > 1 ? ` · Version ${z.version}` : ''}</span></td>
                      <td className="px-2 py-2.5 text-right font-semibold whitespace-nowrap">{fmtGeld(z.summe_netto)}</td>
                      <td className="px-2 py-2.5">{PREISARTEN[z.preisart] || z.preisart}</td>
                      <td className="px-2 py-2.5 whitespace-nowrap">{z.ausfuehrung_von ? `${fmtTag(z.ausfuehrung_von)} – ${fmtTag(z.ausfuehrung_bis)}` : '–'}</td>
                      <td className="px-2 py-2.5 whitespace-nowrap">{fmtZeit(z.eingereicht_at)}</td>
                      <td className="px-2 py-2.5 text-center">{z.positionen_vollstaendig === null ? '–' : z.positionen_vollstaendig ? '✓' : '✗'}</td>
                      <td className="px-2 py-2.5 text-center">{z.dokumente}</td>
                      <td className="px-2 py-2.5 text-center">{z.bewertung_punkte !== null ? `${z.bewertung_punkte}/${z.bewertung_max}` : '–'}{z.mindestanforderungen === false && <span className="block text-[10px] text-[#C41E3A]">Mindestanf. nicht erfüllt</span>}</td>
                      <td className="px-2 py-2.5">{chip(z.status)}</td>
                      <td className="px-2 py-2.5"><button type="button" className="text-[#6E6E73]" onClick={() => setOffen(auf ? null : z.angebot_id)}>{auf ? <ChevronUp size={16} /> : <ChevronDown size={16} />}</button></td>
                    </tr>
                    {auf && g && (
                      <tr className="border-b border-black/[0.06] bg-[#FAFAFA]"><td colSpan={10} className="px-4 py-4">
                        <AngebotDetails g={g} a={a} kriterien={d.kriterien} onGespeichert={() => { laden(); onChanged?.(); }} />
                        {!['angenommen', 'abgelehnt', 'zurueckgezogen'].includes(g.status) && (
                          <div className="flex flex-wrap gap-2 mt-4">
                            {g.status !== 'in_pruefung' && <Btn size="sm" variant="soft" onClick={() => pruefung(g, 'in_pruefung')} loading={busy === g.id + 'in_pruefung'}>In Prüfung nehmen</Btn>}
                            <Btn size="sm" variant="soft" onClick={() => { setDialog({ art: 'rueckfrage', angebot: g }); setText(''); setFrist(''); }}>Rückfrage / Nachforderung</Btn>
                            <Btn size="sm" variant="danger" onClick={() => { setDialog({ art: 'abgelehnt', angebot: g }); setText(''); }}>Ablehnen</Btn>
                            {vergabeMoeglich && <Btn size="sm" onClick={() => { setDialog({ art: 'vergabe', angebot: g }); setText(''); }}><Gavel size={14} /> Zur Vergabe vorschlagen</Btn>}
                          </div>
                        )}
                      </td></tr>
                    )}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        </Card>
      )}
      <p className="text-[12px] text-[#86868B]">{d.hinweis}</p>
      <Sheet open={!!dialog} onOpenChange={(o) => { if (!o) setDialog(null); }} title={dialog?.art === 'vergabe' ? 'Zur Vergabe vorschlagen' : dialog?.art === 'rueckfrage' ? 'Rückfrage / Nachforderung' : 'Angebot ablehnen'} subtitle={dialog ? `${dialog.angebot.firma?.name} · ${fmtGeld(dialog.angebot.summe_netto)} netto` : ''}>
        {dialog && (
          <div className="space-y-4">
            {dialog.art === 'vergabe' && <p className="text-[13px] text-[#6E6E73]">Der Vorschlag muss danach von einer zweiten Person aus Büro/Inhaber freigegeben und der Firma mitgeteilt werden. Verbindlich wird der Auftrag erst mit der Annahme durch die Firma.</p>}
            <Field label={dialog.art === 'vergabe' ? 'Begründung (intern, für die Vergabeakte)' : 'Nachricht an die Firma'}><TextArea rows={3} value={text} onChange={(e) => setText(e.target.value)} /></Field>
            {dialog.art === 'rueckfrage' && <Field label="Nachreichung möglich bis" hint="Leer = 7 Tage ab heute."><TextInput type="date" value={frist} onChange={(e) => setFrist(e.target.value)} /></Field>}
            <div className="flex justify-end gap-2"><Btn variant="soft" onClick={() => setDialog(null)}>Abbrechen</Btn>
              {dialog.art === 'vergabe' ? <Btn onClick={() => vergabe(dialog.angebot)} loading={busy === 'vergabe'}>Vorschlagen</Btn>
                : <Btn variant={dialog.art === 'abgelehnt' ? 'danger' : 'primary'} onClick={() => pruefung(dialog.angebot, dialog.art, text, frist)} loading={busy === dialog.angebot.id + dialog.art}>{dialog.art === 'abgelehnt' ? 'Ablehnen und mitteilen' : 'Senden'}</Btn>}
            </div>
          </div>
        )}
      </Sheet>
    </div>
  );
}

function AngebotDetails({ g, a, kriterien, onGespeichert }) {
  const [bew, setBew] = useState({ kriterien: g.bewertung?.kriterien || {}, notiz: g.bewertung?.notiz || '', mindestanforderungen_erfuellt: g.bewertung?.mindestanforderungen_erfuellt ?? null });
  const [busy, setBusy] = useState(false);
  const speichern = async () => { setBusy(true); try { await api.put(`/api/angebote/${g.id}/bewertung`, bew); toast.success('Bewertung gespeichert'); onGespeichert?.(); } catch (err) { toast.error(err.message); } finally { setBusy(false); } };
  const felder = [['leistungsbeschreibung', 'Leistungsbeschreibung'], ['verfuegbarkeit', 'Verfügbarkeit'], ['kapazitaet', 'Kapazität'], ['material', 'Material'], ['zusatzleistungen', 'Zusatzleistungen'], ['bemerkungen', 'Bemerkungen']].filter(([k]) => g[k]);
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 text-[13px]">
      <div className="space-y-3">
        <div className="text-[#6E6E73]">{g.nummer} · {g.ansprechpartner || '–'} · gültig bis {fmtTag(g.gueltig_bis)} · USt {g.reverse_charge ? '§ 13b' : `${g.ust_satz} %`} · brutto {fmtGeld(g.summe_brutto)}</div>
        {felder.map(([k, l]) => <div key={k}><span className="block text-[11px] font-semibold uppercase tracking-wider text-[#86868B]">{l}</span><p className="whitespace-pre-wrap">{g[k]}</p></div>)}
        {g.berechnung && (
          <table className="w-full text-[12px]"><thead><tr className="text-left text-[#86868B]"><th className="py-1">Nr</th><th>Leistung</th><th className="text-right">Menge</th><th className="text-right">EP</th><th className="text-right">Gesamt</th></tr></thead>
            <tbody>{g.berechnung.zeilen.map((z) => <tr key={z.nr} className="border-t border-black/[0.06]"><td className="py-1 font-mono">{z.nr}</td><td>{z.leistung}</td><td className="text-right">{z.menge} {z.einheit}</td><td className="text-right">{z.einzelpreis === null ? '–' : fmtGeld(z.einzelpreis)}</td><td className="text-right">{z.gesamt === null ? '–' : fmtGeld(z.gesamt)}</td></tr>)}</tbody></table>
        )}
        {(g.dokumente || []).length > 0 && <ul className="space-y-1">{g.dokumente.map((dok) => <li key={dok.id} className="flex items-center gap-2"><FileText size={14} className="text-[#6E6E73]" /><button type="button" className="underline-offset-2 hover:underline" onClick={() => openFile(`/api/dokumente/${dok.id}/datei`).catch((err) => toast.error(err.message))}>{dok.filename}</button><span className="text-[#86868B]">{dok.category}</span></li>)}</ul>}
        {(g.versionen || []).length > 1 && <div className="text-[12px] text-[#6E6E73]">Versionen: {g.versionen.map((v) => `v${v.version} ${fmtGeld(v.summe_netto)} (${fmtZeit(v.eingereicht_at)})`).join(' · ')}</div>}
      </div>
      <div className="space-y-3">
        <span className="block text-[11px] font-semibold uppercase tracking-wider text-[#86868B]">Bewertung (0–5 je Kriterium)</span>
        {kriterien.map((k) => (
          <div key={k} className="flex items-center gap-2 flex-wrap"><span className="w-40 text-[13px]">{KRITERIEN[k] || k}</span><div className="flex gap-1">{[0, 1, 2, 3, 4, 5].map((p) => <Chip key={p} active={bew.kriterien[k] === p} onClick={() => setBew((b) => ({ ...b, kriterien: { ...b.kriterien, [k]: p } }))} className="px-2.5">{p}</Chip>)}</div></div>
        ))}
        <div className="rounded-2xl bg-white px-4"><Toggle checked={bew.mindestanforderungen_erfuellt === true} onChange={(v) => setBew((b) => ({ ...b, mindestanforderungen_erfuellt: v }))} label="Mindestanforderungen erfüllt" /></div>
        <TextArea rows={2} value={bew.notiz} onChange={(e) => setBew((b) => ({ ...b, notiz: e.target.value }))} placeholder="Begründung, Auffälligkeiten (intern)" />
        <div className="flex items-center gap-3"><Btn size="sm" variant="dark" onClick={speichern} loading={busy}>Bewertung speichern</Btn>{g.bewertung && <span className="text-[12px] text-[#86868B]">zuletzt {g.bewertung.bewertet_von}, {fmtZeit(g.bewertung.at)}</span>}</div>
      </div>
    </div>
  );
}
