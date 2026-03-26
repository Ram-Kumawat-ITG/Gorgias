// Ticket detail page — message thread, reply composer, customer sidebar
import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import api from '../api/client';
import CustomerSidebar from '../components/CustomerSidebar';
import AISuggestion from '../components/AISuggestion';
import MacroPicker from '../components/MacroPicker';
import clsx from 'clsx';

const MSG_COLORS = {
  customer: 'bg-gray-50',
  agent: 'bg-blue-50',
  system: 'bg-yellow-50',
  ai: 'bg-green-50',
};

export default function TicketDetailPage() {
  const { id } = useParams();
  const [ticket, setTicket] = useState(null);
  const [messages, setMessages] = useState([]);
  const [reply, setReply] = useState('');
  const [sending, setSending] = useState(false);
  const [loading, setLoading] = useState(true);

  async function loadTicket() {
    try {
      const [tRes, mRes] = await Promise.all([
        api.get(`/tickets/${id}`),
        api.get(`/tickets/${id}/messages`),
      ]);
      setTicket(tRes.data);
      setMessages(mRes.data);
    } catch {
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadTicket(); }, [id]);

  async function sendMessage(isNote = false) {
    if (!reply.trim()) return;
    setSending(true);
    try {
      await api.post(`/tickets/${id}/messages`, {
        body: reply,
        sender_type: 'agent',
        is_internal_note: isNote,
      });
      setReply('');
      await loadTicket();
    } catch {
    } finally {
      setSending(false);
    }
  }

  async function resolveTicket() {
    try {
      await api.patch(`/tickets/${id}`, { status: 'resolved' });
      await loadTicket();
    } catch {}
  }

  if (loading) return <div className="p-8 text-center text-gray-400">Loading...</div>;
  if (!ticket) return <div className="p-8 text-center text-gray-400">Ticket not found</div>;

  return (
    <div className="flex gap-6">
      {/* Left: messages + composer */}
      <div className="flex-1 min-w-0">
        <div className="mb-4">
          <h1 className="text-xl font-semibold text-gray-900">{ticket.subject}</h1>
          <div className="flex items-center gap-2 mt-1">
            <span className="badge bg-gray-100 text-gray-600 capitalize">{ticket.status}</span>
            <span className="badge bg-blue-100 text-blue-700 capitalize">{ticket.priority}</span>
            <span className="text-xs text-gray-400">{ticket.channel}</span>
          </div>
        </div>

        {/* Message thread */}
        <div className="space-y-3 mb-6">
          {messages.map(m => (
            <div
              key={m.id}
              className={clsx(
                'rounded-lg p-4 text-sm',
                m.is_internal_note ? 'bg-yellow-50 border-l-4 border-yellow-400' : MSG_COLORS[m.sender_type] || 'bg-gray-50'
              )}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="font-medium text-gray-700 capitalize">
                  {m.is_internal_note ? 'Internal Note' : m.sender_type}
                  {m.ai_generated && ' (AI)'}
                </span>
                <span className="text-xs text-gray-400">
                  {new Date(m.created_at).toLocaleString()}
                </span>
              </div>
              <p className="text-gray-800 whitespace-pre-wrap">{m.body}</p>
            </div>
          ))}
        </div>

        {/* AI Suggestion */}
        <AISuggestion ticketId={id} onUse={text => setReply(text)} />

        {/* Reply composer */}
        <div className="card p-4 mt-4">
          <div className="flex items-center gap-2 mb-2">
            <MacroPicker ticketId={id} onInsert={text => setReply(text)} />
          </div>
          <textarea
            value={reply}
            onChange={e => setReply(e.target.value)}
            rows={4}
            placeholder="Type your reply..."
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm
                       focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
          />
          <div className="flex items-center gap-2 mt-2">
            <button onClick={() => sendMessage(false)} className="btn-primary" disabled={sending || !reply.trim()}>
              {sending ? 'Sending...' : 'Send Reply'}
            </button>
            <button onClick={() => sendMessage(true)} className="btn-secondary" disabled={sending || !reply.trim()}>
              Add Internal Note
            </button>
            {ticket.status !== 'resolved' && (
              <button onClick={resolveTicket} className="btn-secondary ml-auto">
                Resolve
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Right: customer sidebar */}
      <div className="w-80 shrink-0">
        <CustomerSidebar ticket={ticket} />
      </div>
    </div>
  );
}
