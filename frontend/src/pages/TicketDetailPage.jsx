// Ticket detail page — message thread, reply composer, customer sidebar
import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import api from '../api/client';
import CustomerSidebar from '../components/CustomerSidebar';

import MacroPicker from '../components/MacroPicker';
import { Mail, MessageSquare, FileText, Check, CheckCheck, Clock, AlertCircle, Camera } from 'lucide-react';
import clsx from 'clsx';

const MSG_COLORS = {
  customer: 'bg-gray-50',
  agent: 'bg-blue-50',
  system: 'bg-yellow-50',
  ai: 'bg-green-50',
};

const TICKET_TYPES = [
  { value: 'refund', label: 'Refund' },
  { value: 'return', label: 'Return' },
  { value: 'shipping', label: 'Shipping' },
  { value: 'order_status', label: 'Order Status' },
  { value: 'billing', label: 'Billing' },
  { value: 'product_inquiry', label: 'Product Inquiry' },
  { value: 'technical', label: 'Technical' },
  { value: 'general', label: 'General' },
];
const TYPE_COLORS = {
  refund: 'bg-red-100 text-red-700',
  return: 'bg-orange-100 text-orange-700',
  shipping: 'bg-cyan-100 text-cyan-700',
  order_status: 'bg-purple-100 text-purple-700',
  billing: 'bg-yellow-100 text-yellow-700',
  product_inquiry: 'bg-indigo-100 text-indigo-700',
  technical: 'bg-pink-100 text-pink-700',
  general: 'bg-gray-100 text-gray-600',
};

export default function TicketDetailPage() {
  const { id } = useParams();
  const [ticket, setTicket] = useState(null);
  const [messages, setMessages] = useState([]);
  const [reply, setReply] = useState('');
  const [sending, setSending] = useState(false);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [rejectReason, setRejectReason] = useState('');
  const [showRejectInput, setShowRejectInput] = useState(false);

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

  // Silent background poll — refreshes messages every 4 seconds without showing the loading spinner
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const mRes = await api.get(`/tickets/${id}/messages`);
        setMessages(mRes.data);
      } catch {}
    }, 4000);
    return () => clearInterval(interval);
  }, [id]);

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

  async function approveAction() {
    setActionLoading(true);
    try {
      await api.post(`/ai/approve-action/${id}`);
      await loadTicket();
    } catch {}
    setActionLoading(false);
  }

  async function rejectAction() {
    setActionLoading(true);
    try {
      await api.post(`/ai/reject-action/${id}`, { rejection_reason: rejectReason });
      setShowRejectInput(false);
      setRejectReason('');
      await loadTicket();
    } catch {}
    setActionLoading(false);
  }

  if (loading) return <div className="flex items-center justify-center min-h-[60vh]"><div className="w-8 h-8 border-4 border-gray-200 border-t-brand-600 rounded-full animate-spin" /></div>;
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
            <select
              value={ticket.ticket_type || 'general'}
              onChange={async (e) => {
                try {
                  await api.patch(`/tickets/${id}`, { ticket_type: e.target.value });
                  await loadTicket();
                } catch {}
              }}
              className={clsx(
                'badge border-0 cursor-pointer text-xs font-medium rounded-full px-2 py-0.5 focus:outline-none focus:ring-2 focus:ring-brand-500',
                TYPE_COLORS[ticket.ticket_type] || TYPE_COLORS.general
              )}
            >
              {TICKET_TYPES.map(tt => (
                <option key={tt.value} value={tt.value}>{tt.label}</option>
              ))}
            </select>
            {ticket.channel === 'whatsapp' ? (
              <span className="badge bg-green-100 text-green-700 flex items-center gap-1">
                <MessageSquare size={12} /> WhatsApp
              </span>
            ) : ticket.channel === 'instagram' ? (
              <span className="badge bg-pink-100 text-pink-700 flex items-center gap-1">
                <Camera size={12} /> Instagram
              </span>
            ) : ticket.channel === 'twitter' ? (
              <span className="badge bg-sky-100 text-sky-700 flex items-center gap-1">
                <svg width={12} height={12} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" /></svg>
                {ticket.twitter_type === 'mention' ? 'Twitter @mention' : 'Twitter DM'}
              </span>
            ) : ticket.channel === 'email' ? (
              <span className="badge bg-gray-100 text-gray-600 flex items-center gap-1">
                <Mail size={12} /> Email
              </span>
            ) : (
              <span className="badge bg-gray-100 text-gray-600 flex items-center gap-1">
                <FileText size={12} /> {ticket.channel}
              </span>
            )}
            {ticket.channel === 'whatsapp' && ticket.whatsapp_phone && (
              <span className="text-xs text-gray-400">+{ticket.whatsapp_phone}</span>
            )}
            {ticket.channel === 'instagram' && ticket.instagram_user_id && (
              <span className="text-xs text-gray-400">ID: {ticket.instagram_user_id}</span>
            )}
            {ticket.channel === 'twitter' && ticket.twitter_username && (
              <span className="text-xs text-gray-400">@{ticket.twitter_username}</span>
            )}
          </div>
          {ticket.channel === 'whatsapp' && ticket.whatsapp_last_customer_msg_at && (
            <div className="mt-1">
              {(() => {
                const lastMsg = new Date(ticket.whatsapp_last_customer_msg_at);
                const hoursLeft = Math.max(0, 24 - (Date.now() - lastMsg.getTime()) / 3600000);
                if (hoursLeft <= 0) return (
                  <span className="text-xs text-orange-600 flex items-center gap-1">
                    <AlertCircle size={12} /> 24h window expired — replies will use template messages
                  </span>
                );
                return (
                  <span className="text-xs text-green-600 flex items-center gap-1">
                    <Clock size={12} /> {hoursLeft.toFixed(1)}h left in messaging window
                  </span>
                );
              })()}
            </div>
          )}
          {ticket.channel === 'instagram' && ticket.instagram_last_customer_msg_at && (
            <div className="mt-1">
              {(() => {
                const lastMsg = new Date(ticket.instagram_last_customer_msg_at);
                const hoursLeft = Math.max(0, 24 - (Date.now() - lastMsg.getTime()) / 3600000);
                if (hoursLeft <= 0) return (
                  <span className="text-xs text-orange-600 flex items-center gap-1">
                    <AlertCircle size={12} /> 24h window expired — customer must message first
                  </span>
                );
                return (
                  <span className="text-xs text-green-600 flex items-center gap-1">
                    <Clock size={12} /> {hoursLeft.toFixed(1)}h left in messaging window
                  </span>
                );
              })()}
            </div>
          )}
        </div>

        {/* Ticket Images */}
        {ticket.images && ticket.images.length > 0 && (
          <div className="mb-4">
            <p className="text-xs font-semibold text-gray-500 mb-1.5">📎 Attachments ({ticket.images.length})</p>
            <div className="flex flex-wrap gap-2">
              {ticket.images.map((url, idx) => (
                <img
                  key={idx}
                  src={url}
                  alt={`Attachment ${idx + 1}`}
                  className="w-24 h-24 rounded-lg object-cover border border-gray-200 cursor-pointer hover:opacity-80 transition-opacity"
                  onClick={() => window.open(url, '_blank')}
                />
              ))}
            </div>
          </div>
        )}

        {/* Pending Admin Action Banner */}
        {ticket.status === 'pending_admin_action' && (
          <div className="mb-4 rounded-xl border border-orange-200 bg-orange-50 p-4">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-orange-600 font-semibold text-sm">⏳ Pending Admin Approval</span>
              <span className="badge bg-orange-100 text-orange-700 text-xs uppercase">
                {ticket.pending_action_type || 'request'}
              </span>
              <span className="badge bg-gray-50 text-gray-500 capitalize text-xs">
                {ticket.channel || 'unknown'}
              </span>
            </div>
            <div className="bg-white border border-orange-100 rounded-lg p-3 text-sm space-y-1.5 mb-3">
              {ticket.pending_action_order_number && (
                <div className="flex gap-2">
                  <span className="text-gray-500 w-24 shrink-0">Order</span>
                  <span className="font-semibold text-gray-900">#{ticket.pending_action_order_number}</span>
                </div>
              )}
              {ticket.customer_name && (
                <div className="flex gap-2">
                  <span className="text-gray-500 w-24 shrink-0">Customer</span>
                  <span className="text-gray-800">{ticket.customer_name}</span>
                </div>
              )}
              {ticket.pending_action_email && (
                <div className="flex gap-2">
                  <span className="text-gray-500 w-24 shrink-0">Contact</span>
                  <span className="text-gray-800">{ticket.pending_action_email}</span>
                </div>
              )}
              {ticket.pending_action_issue && (
                <div className="flex gap-2">
                  <span className="text-gray-500 w-24 shrink-0">Issue</span>
                  <span className="text-gray-800 capitalize">{ticket.pending_action_issue.replace(/_/g, ' ')}</span>
                </div>
              )}
              {ticket.pending_action_description && (
                <div className="flex gap-2">
                  <span className="text-gray-500 w-24 shrink-0">Description</span>
                  <span className="text-gray-700">{ticket.pending_action_description}</span>
                </div>
              )}
              {ticket.created_at && (
                <div className="flex gap-2">
                  <span className="text-gray-500 w-24 shrink-0">Submitted</span>
                  <span className="text-gray-700">{new Date(ticket.created_at).toLocaleString()}</span>
                </div>
              )}
            </div>
            {/* Proof images & videos — from ticket fields or message thread */}
            {(() => {
              const apiBase = import.meta.env.VITE_API_BASE_URL.replace(/\/$/, '')
              const images = ticket.pending_action_images || []
              const videos = ticket.pending_action_videos || []
              // Also scan messages for any media the ticket fields missed
              const msgMedia = messages
                .filter(m => m.sender_type === 'customer' && (m.whatsapp_media_url || m.whatsapp_media_id || m.instagram_media_url))
                .map(m => ({
                  id: m.id,
                  type: m.whatsapp_media_type || m.instagram_media_type || '',
                  isWa: !!(m.whatsapp_media_url || m.whatsapp_media_id),
                }))
              const hasProof = images.length > 0 || videos.length > 0 || msgMedia.length > 0
              if (!hasProof) return null
              return (
                <div className="mb-3">
                  <p className="text-xs font-semibold text-gray-500 mb-1.5">📸 Proof Uploaded ({images.length + videos.length} file{images.length + videos.length !== 1 ? 's' : ''})</p>
                  <div className="flex flex-wrap gap-2">
                    {/* Ticket-level images (media IDs — proxy through backend) */}
                    {images.map((ref, idx) => {
                      const msgMatch = messages.find(m => m.whatsapp_media_id === ref || m.whatsapp_media_url === ref)
                      const src = msgMatch
                        ? `${apiBase}/media/whatsapp/${msgMatch.id}`
                        : `${apiBase}/media/whatsapp/${ref}`
                      return (
                        <img key={`img-${idx}`} src={src} alt={`Proof ${idx + 1}`}
                          className="w-20 h-20 rounded-lg object-cover border border-gray-200 cursor-pointer hover:opacity-80 transition-opacity"
                          onClick={() => window.open(src, '_blank')} />
                      )
                    })}
                    {/* Ticket-level videos */}
                    {videos.map((ref, idx) => {
                      const msgMatch = messages.find(m => m.whatsapp_media_id === ref || m.whatsapp_media_url === ref)
                      const src = msgMatch
                        ? `${apiBase}/media/whatsapp/${msgMatch.id}`
                        : `${apiBase}/media/whatsapp/${ref}`
                      return (
                        <video key={`vid-${idx}`} src={src} controls
                          className="w-32 h-20 rounded-lg border border-gray-200 object-cover" />
                      )
                    })}
                    {/* Fallback: message-thread media not in ticket fields */}
                    {images.length === 0 && videos.length === 0 && msgMedia.map((m, idx) => {
                      const src = m.isWa
                        ? `${apiBase}/media/whatsapp/${m.id}`
                        : null
                      if (!src) return null
                      const isImg = m.type === 'image' || m.type.startsWith('image/')
                      return isImg ? (
                        <img key={`msg-${idx}`} src={src} alt="Proof"
                          className="w-20 h-20 rounded-lg object-cover border border-gray-200 cursor-pointer hover:opacity-80"
                          onClick={() => window.open(src, '_blank')} />
                      ) : (
                        <video key={`msg-${idx}`} src={src} controls
                          className="w-32 h-20 rounded-lg border border-gray-200" />
                      )
                    })}
                  </div>
                </div>
              )
            })()}
            {!showRejectInput ? (
              <div className="flex gap-2">
                <button
                  onClick={approveAction}
                  disabled={actionLoading}
                  className="px-4 py-2 rounded-lg bg-green-600 text-white text-sm font-medium hover:bg-green-700 disabled:opacity-50"
                >
                  {actionLoading ? 'Processing...' : '✅ Approve Request'}
                </button>
                <button
                  onClick={() => setShowRejectInput(true)}
                  disabled={actionLoading}
                  className="px-4 py-2 rounded-lg bg-red-100 text-red-700 text-sm font-medium hover:bg-red-200 disabled:opacity-50"
                >
                  ❌ Reject Request
                </button>
              </div>
            ) : (
              <div className="space-y-2">
                <input
                  type="text"
                  value={rejectReason}
                  onChange={e => setRejectReason(e.target.value)}
                  placeholder="Rejection reason (optional)"
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-400"
                />
                <div className="flex gap-2">
                  <button
                    onClick={rejectAction}
                    disabled={actionLoading}
                    className="px-4 py-2 rounded-lg bg-red-600 text-white text-sm font-medium hover:bg-red-700 disabled:opacity-50"
                  >
                    {actionLoading ? 'Rejecting...' : 'Confirm Reject'}
                  </button>
                  <button
                    onClick={() => { setShowRejectInput(false); setRejectReason(''); }}
                    className="px-4 py-2 rounded-lg bg-gray-100 text-gray-600 text-sm font-medium hover:bg-gray-200"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

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
              {(() => {
                const waUrl = m.whatsapp_media_url;
                const waType = m.whatsapp_media_type || '';
                const hasMedia = waUrl && (waType === 'image' || waType === 'video' || waType.startsWith('image/') || waType.startsWith('video/'));
                const isPlaceholder = hasMedia && /^\[.* received\]$/.test((m.body || '').trim());
                return !isPlaceholder && m.body
                  ? <p className="text-gray-800 whitespace-pre-wrap">{m.body}</p>
                  : null;
              })()}
              {(m.whatsapp_media_url || m.whatsapp_media_id) && (() => {
                const mediaType = m.whatsapp_media_type || '';

                // Always proxy WhatsApp media through backend — Meta URLs expire
                // and require Authorization header the browser doesn't have
                const src = `${import.meta.env.VITE_API_BASE_URL.replace(/\/$/, '')}/media/whatsapp/${m.id}`;

                if (mediaType === 'image' || mediaType.startsWith('image/')) {
                  return <img src={src} alt="WhatsApp image" className="mt-2 max-w-xs rounded-lg" />;
                }
                if (mediaType === 'video' || mediaType.startsWith('video/')) {
                  return <video src={src} controls className="mt-2 max-w-xs rounded-lg" />;
                }
                return (
                  <a href={src} target="_blank" rel="noopener noreferrer"
                     className="text-xs text-brand-600 hover:underline mt-1 inline-block">
                    View {mediaType || 'media'}
                  </a>
                );
              })()}
              {m.whatsapp_status && m.sender_type === 'agent' && (
                <span className="flex items-center gap-1 text-xs text-gray-400 mt-1">
                  {m.whatsapp_status === 'sent' && <><Check size={12} /> Sent</>}
                  {m.whatsapp_status === 'delivered' && <><CheckCheck size={12} /> Delivered</>}
                  {m.whatsapp_status === 'read' && <><CheckCheck size={12} className="text-blue-500" /> Read</>}
                  {m.whatsapp_status === 'failed' && <><AlertCircle size={12} className="text-red-500" /> Failed</>}
                </span>
              )}
              {m.twitter_media_url && (
                <a href={m.twitter_media_url} target="_blank" rel="noopener noreferrer"
                   className="text-xs text-brand-600 hover:underline mt-1 inline-block">
                  View {m.twitter_media_type || 'media'}
                </a>
              )}
              {m.twitter_status && m.sender_type === 'agent' && (
                <span className="flex items-center gap-1 text-xs text-gray-400 mt-1">
                  {m.twitter_status === 'sent' && <><Check size={12} /> Sent</>}
                  {m.twitter_status === 'failed' && <><AlertCircle size={12} className="text-red-500" /> Failed</>}
                </span>
              )}
              {m.instagram_media_url && (
                <a href={m.instagram_media_url} target="_blank" rel="noopener noreferrer"
                   className="text-xs text-brand-600 hover:underline mt-1 inline-block">
                  View {m.instagram_media_type || 'media'}
                </a>
              )}
              {m.instagram_status && m.sender_type === 'agent' && (
                <span className="flex items-center gap-1 text-xs text-gray-400 mt-1">
                  {m.instagram_status === 'sent' && <><Check size={12} /> Sent</>}
                  {m.instagram_status === 'read' && <><CheckCheck size={12} className="text-pink-500" /> Seen</>}
                </span>
              )}
            </div>
          ))}
        </div>

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
