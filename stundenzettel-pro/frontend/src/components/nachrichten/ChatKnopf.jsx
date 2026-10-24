import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { MessageSquare } from 'lucide-react';
import { toast } from 'sonner';
import { Btn } from '../ui';
import { api } from '../../lib/api';
import { useAuth } from '../../lib/auth';

/** Öffnet (oder findet) den passenden Chat und springt zu „Nachrichten“. `koerper` = Body für POST /api/chats/oeffnen. */
export default function ChatKnopf({ koerper, children = 'Chat', size = 'sm', variant = 'soft', className = '' }) {
  const { feature } = useAuth();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  if (!feature('chat')) return null;
  const oeffnen = async () => {
    setBusy(true);
    try { const r = await api.post('/api/chats/oeffnen', koerper); navigate(`/nachrichten?chat=${r.chat.id}`); }
    catch (err) { toast.error(err.message); } finally { setBusy(false); }
  };
  return <Btn size={size} variant={variant} className={className} onClick={oeffnen} loading={busy}><MessageSquare size={15} /> {children}</Btn>;
}
