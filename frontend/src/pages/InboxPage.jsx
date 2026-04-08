// Inbox page — ticket list with status tabs, pagination, and priority badges
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, ChevronLeft, ChevronRight, Mail, MessageSquare, FileText } from 'lucide-react';
import api from '../api/client';
import SLABadge from '../components/SLABadge';
import clsx from 'clsx';

// ── Tag color helper — deterministic color from tag name hash ──
const TAG_PALETTE = [
  'bg-blue-100 text-blue-800', 'bg-green-100 text-green-800',
  'bg-purple-100 text-purple-800', 'bg-amber-100 text-amber-800',
  'bg-pink-100 text-pink-800', 'bg-teal-100 text-teal-800',
  'bg-indigo-100 text-indigo-800', 'bg-rose-100 text-rose-800',
];
function tagColor(name) {
  const hash = [...(name || '').toLowerCase()].reduce((a, c) => a + c.charCodeAt(0), 0);
  return TAG_PALETTE[hash % TAG_PALETTE.length];
}

const STATUSES = ['open', 'pending', 'resolved', 'closed'];
const TICKET_TYPES = [
  { value: '', label: 'All Types' },
  { value: 'refund', label: 'Refund' },
  { value: 'return', label: 'Return' },
  { value: 'shipping', label: 'Shipping' },
  { value: 'order_status', label: 'Order Status' },
  { value: 'billing', label: 'Billing' },
  { value: 'product_inquiry', label: 'Product Inquiry' },
  { value: 'technical', label: 'Technical' },
  { value: 'replacement', label: 'Replacement' },
  { value: 'general', label: 'General' },
];
const CHANNELS = [
  { value: '', label: 'All Channels' },
  { value: 'email', label: 'Email', icon: Mail },
  { value: 'whatsapp', label: 'WhatsApp', icon: MessageSquare },
  { value: 'manual', label: 'Manual', icon: FileText },
];
const TYPE_COLORS = {
  refund: 'bg-red-100 text-red-700',
  return: 'bg-orange-100 text-orange-700',
  shipping: 'bg-cyan-100 text-cyan-700',
  order_status: 'bg-purple-100 text-purple-700',
  billing: 'bg-yellow-100 text-yellow-700',
  product_inquiry: 'bg-indigo-100 text-indigo-700',
  technical: 'bg-pink-100 text-pink-700',
  replacement: 'bg-teal-100 text-teal-700',
  general: 'bg-gray-100 text-gray-600',
};
const CHANNEL_ICONS = { email: Mail, whatsapp: MessageSquare, manual: FileText };
const PRIORITY_COLORS = {
  low: 'bg-gray-100 text-gray-700',
  normal: 'bg-blue-100 text-blue-700',
  high: 'bg-orange-100 text-orange-700',
  urgent: 'bg-red-100 text-red-700',
};
const FINANCIAL_COLORS = {
  paid: 'bg-green-100 text-green-700',
  pending: 'bg-yellow-100 text-yellow-700',
  refunded: 'bg-red-100 text-red-700',
  voided: 'bg-gray-100 text-gray-600',
};
const FULFILLMENT_COLORS = {
  fulfilled: 'bg-green-100 text-green-700',
  partial: 'bg-yellow-100 text-yellow-700',
  unfulfilled: 'bg-orange-100 text-orange-700',
};

export default function InboxPage() {
  const [status, setStatus] = useState('open');
  const [channel, setChannel] = useState('');
  const [ticketType, setTicketType] = useState('');
  const [tickets, setTickets] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();
  const limit = 20;

  function loadTickets() {
    setLoading(true);
    const params = { status, page, limit };
    if (channel) params.channel = channel;
    if (ticketType) params.ticket_type = ticketType;
    api.get('/tickets', { params })
      .then(res => {
        setTickets(res.data.tickets ?? []);
        setTotal(res.data.total);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    loadTickets();
  }, [status, page, channel, ticketType]);

  // Silent background poll — checks for new inbound tickets every 10 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      const params = { status, page, limit };
      if (channel) params.channel = channel;
      if (ticketType) params.ticket_type = ticketType;
      api.get('/tickets', { params })
        .then(res => {
          setTickets(res.data.tickets ?? []);
          setTotal(res.data.total);
        })
        .catch(() => {});
    }, 10000);
    return () => clearInterval(interval);
  }, [status, page, channel, ticketType]);

  async function handleSyncShopify() {
    setSyncing(true);
    setSyncResult(null);
    try {
      const res = await shopifyApi.syncOrders(50);
      setSyncResult(res.data);
      loadTickets();
    } catch {
      setSyncResult({ status: 'error', detail: 'Failed to sync Shopify orders.' });
    } finally {
      setSyncing(false);
    }
  }

  const totalPages = Math.ceil(total / limit);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold text-gray-900">Inbox</h1>
        <button onClick={() => navigate('/tickets/new')} className="btn-primary flex items-center gap-2">
          <Plus size={16} /> New Ticket
        </button>
      </div>

      {/* Status tabs */}
      <div className="flex flex-wrap gap-1 mb-4">
        {STATUSES.map(s => (
          <button
            key={s}
            onClick={() => { setStatus(s); setPage(1); }}
            className={clsx(
              'px-4 py-2 rounded-lg text-sm font-medium capitalize transition-colors',
              status === s ? 'bg-brand-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            )}
          >
            {s}
          </button>
        ))}
        {/* Channel + Type filters */}
        <div className="ml-auto flex gap-2">
          <select
            value={ticketType}
            onChange={e => { setTicketType(e.target.value); setPage(1); }}
            className="px-3 py-2 rounded-lg text-sm border border-gray-200 bg-white text-gray-600 focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            {TICKET_TYPES.map(tt => (
              <option key={tt.value} value={tt.value}>{tt.label}</option>
            ))}
          </select>
          <select
            value={channel}
            onChange={e => { setChannel(e.target.value); setPage(1); }}
            className="px-3 py-2 rounded-lg text-sm border border-gray-200 bg-white text-gray-600 focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            {CHANNELS.map(ch => (
              <option key={ch.value} value={ch.value}>{ch.label}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Ticket list */}
      <div className="card divide-y divide-gray-100">
        {loading ? (
          <div className="flex items-center justify-center py-12"><div className="w-7 h-7 border-4 border-gray-200 border-t-brand-600 rounded-full animate-spin" /></div>
        ) : tickets.length === 0 ? (
          <div className="p-8 text-center text-gray-400">No tickets found</div>
        ) : (
          tickets.map(t => (
            <div
              key={t.id}
              onClick={() => navigate(`/tickets/${t.id}`)}
              className="flex flex-col sm:flex-row sm:items-center sm:justify-between px-4 py-3 hover:bg-gray-50 cursor-pointer transition-colors gap-2 sm:gap-0"
            >
              <div className="min-w-0 flex-1 flex items-center gap-2">
                {(() => {
                  const Icon = CHANNEL_ICONS[t.channel];
                  return Icon ? <Icon size={14} className={t.channel === 'whatsapp' ? 'text-green-500 shrink-0' : 'text-gray-400 shrink-0'} /> : null;
                })()}
                <div className="min-w-0">
                  <p className="text-sm font-medium text-gray-900 truncate">{t.subject}</p>
                  <p className="text-xs text-gray-500 mt-0.5">{t.customer_email}</p>
                </div>
              </div>
              <div className="flex items-center flex-wrap gap-2 sm:ml-4 shrink-0">
                {t.ticket_type && t.ticket_type !== 'general' && (
                  <span className={clsx('badge', TYPE_COLORS[t.ticket_type] || TYPE_COLORS.general)}>
                    {t.ticket_type.replace('_', ' ')}
                  </span>
                )}
                {(() => {
                  const tags = [...new Set((t.tags || []).map(g => g.trim()).filter(Boolean))];
                  const visible = tags.slice(0, 2);
                  const extra = tags.length - visible.length;
                  return <>
                    {visible.map(tag => <span key={tag} className={clsx('badge', tagColor(tag))}>{tag}</span>)}
                    {extra > 0 && <span className="badge bg-gray-100 text-gray-500">+{extra}</span>}
                  </>;
                })()}
                {t.images?.length > 0 && (
                  <span className="badge bg-gray-100 text-gray-500">📎 {t.images.length}</span>
                )}
                <span className={clsx('badge', PRIORITY_COLORS[t.priority] || PRIORITY_COLORS.normal)}>
                  {t.priority}
                </span>
                {t.sla_status && t.sla_status !== 'ok' && (
                  <SLABadge slaStatus={t.sla_status} slaDueAt={t.sla_due_at} />
                )}
              </div>
            </div>
          ))
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-4">
          <p className="text-sm text-gray-500">
            Showing {(page - 1) * limit + 1}–{Math.min(page * limit, total)} of {total}
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1}
              className="btn-secondary flex items-center gap-1"
            >
              <ChevronLeft size={14} /> Previous
            </button>
            <button
              onClick={() => setPage(p => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="btn-secondary flex items-center gap-1"
            >
              Next <ChevronRight size={14} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
