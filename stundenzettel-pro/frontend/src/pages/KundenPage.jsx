import React, { useEffect, useState } from 'react';
import { Plus, Pencil, Contact, MapPin, Phone, Mail } from 'lucide-react';
import { toast } from 'sonner';
import Layout, { Ladeanzeige } from '../components/Layout';
import KundeDialog from '../components/KundeDialog';
import { Btn, Card, Empty, IconBtn } from '../components/ui';
import { api } from '../lib/api';

export default function KundenPage() {
  const [kunden, setKunden] = useState(null);
  const [dialog, setDialog] = useState(false);
  const [edit, setEdit] = useState(null);
  const laden = () => api.get('/api/kunden').then((r) => setKunden(r.kunden)).catch((err) => toast.error(err.message));
  useEffect(() => { laden(); }, []);

  return (
    <Layout title="Kunden" subtitle="Auftraggeber mit Rechnungsadresse. Projekte werden einem Kunden zugeordnet." action={<Btn onClick={() => { setEdit(null); setDialog(true); }}><Plus size={18} /> <span className="hidden sm:inline">Neuer Kunde</span><span className="sm:hidden">Neu</span></Btn>}>
      {!kunden ? <Ladeanzeige /> : kunden.length === 0 ? (
        <Card><Empty icon={Contact} title="Noch keine Kunden" text="Lege deine Auftraggeber an. Bei Subunternehmer-Kunden den § 13b-Schalter setzen." action={<Btn onClick={() => { setEdit(null); setDialog(true); }}><Plus size={18} /> Ersten Kunden anlegen</Btn>} /></Card>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {kunden.map((k) => (
            <Card key={k.id} className="p-5 flex gap-3">
              <div className="flex-1 min-w-0">
                <div className="text-[16px] font-semibold truncate">{k.name}{k.reverse_charge && <span className="ml-2 text-[10px] font-semibold uppercase tracking-wide bg-black/[0.06] rounded-full px-2 py-0.5">§ 13b</span>}</div>
                {k.contact && <div className="text-[13px] text-[#6E6E73] truncate">{k.contact}</div>}
                <div className="text-[13px] text-[#6E6E73] mt-1 space-y-0.5">
                  {(k.street || k.city) && <div className="flex items-center gap-1.5"><MapPin size={13} /> {[k.street, [k.zip_code, k.city].filter(Boolean).join(' ')].filter(Boolean).join(', ')}</div>}
                  {k.phone && <div className="flex items-center gap-1.5"><Phone size={13} /> {k.phone}</div>}
                  {k.email && <div className="flex items-center gap-1.5"><Mail size={13} /> {k.email}</div>}
                </div>
                <div className="text-[12px] text-[#86868B] mt-2">{k.projekte} {k.projekte === 1 ? 'Projekt' : 'Projekte'}</div>
              </div>
              <IconBtn size={32} onClick={() => { setEdit(k); setDialog(true); }} title="Bearbeiten" className="text-[#86868B]"><Pencil size={15} /></IconBtn>
            </Card>
          ))}
        </div>
      )}
      <KundeDialog open={dialog} onOpenChange={setDialog} kunde={edit} onSaved={laden} onDeleted={laden} />
    </Layout>
  );
}
