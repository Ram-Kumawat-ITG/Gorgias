// Inbox page — ticket list with status tabs, pagination, and priority badges
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, ChevronLeft, ChevronRight, RefreshCw } from 'lucide-react';
import api from '../api/client';
import { shopifyApi } from '../api/client';
import SLABadge from '../components/SLABadge';
import clsx from 'clsx';

const STATUSES = ['open', 'pending', 'resolved', 'closed'];
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
  const [tickets, setTickets] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState(null);
  const navigate = useNavigate();
  const limit = 20;

  function loadTickets() {
    setLoading(true);
    api.get('/tickets', { params: { status, page, limit } })
      .then(res => {
        setTickets(res.data.tickets);
        setTotal(res.data.total);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    loadTickets();
  }, [status, page]);

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
        <div className="flex items-center gap-2">
          <button
            onClick={handleSyncShopify}
            disabled={syncing}
            className="btn-secondary flex items-center gap-2"
          >
            <RefreshCw size={16} className={syncing ? 'animate-spin' : ''} />
            {syncing ? 'Syncing...' : 'Sync Shopify'}
          </button>
          <button onClick={() => navigate('/tickets/new')} className="btn-primary flex items-center gap-2">
            <Plus size={16} /> New Ticket
          </button>
        </div>
      </div>

      {/* Sync result banner */}
      {syncResult && (
        <div className={clsx(
          'mb-4 px-4 py-3 rounded-lg text-sm',
          syncResult.status === 'error'
            ? 'bg-red-50 text-red-700 border border-red-200'
            : 'bg-green-50 text-green-700 border border-green-200'
        )}>
          {syncResult.status === 'error' ? (
            syncResult.detail
          ) : (
            <>
              Synced {syncResult.created} new order{syncResult.created !== 1 ? 's' : ''} from Shopify.
              {syncResult.skipped > 0 && ` ${syncResult.skipped} already existed.`}
            </>
          )}
          <button onClick={() => setSyncResult(null)} className="ml-2 underline hover:no-underline">
            Dismiss
          </button>
        </div>
      )}

      {/* Status tabs */}
      <div className="flex gap-1 mb-4">
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
              className="flex items-center justify-between px-4 py-3 hover:bg-gray-50 cursor-pointer transition-colors"
            >
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-gray-900 truncate">{t.subject}</p>
                <div className="flex items-center gap-2 mt-0.5">
                  <p className="text-xs text-gray-500">{t.customer_email}</p>
                  {t.channel === 'shopify' && t.shopify_total_price && (
                    <>
                      <span className="text-xs text-gray-300">|</span>
                      <span className="text-xs font-medium text-gray-700">
                        ${t.shopify_total_price} {t.shopify_currency || 'USD'}
                      </span>
                    </>
                  )}
                </div>
                {t.channel === 'shopify' && t.shopify_line_items?.length > 0 && (
                  <p className="text-xs text-gray-400 mt-0.5 truncate">
                    {t.shopify_line_items.map(li => `${li.title} x${li.quantity}`).join(', ')}
                  </p>
                )}
              </div>
              <div className="flex items-center gap-2 ml-4 shrink-0">
                {t.channel && (
                  <span className="badge bg-gray-50 text-gray-500 capitalize text-xs">{t.channel}</span>
                )}
                {t.shopify_financial_status && (
                  <span className={clsx('badge text-xs', FINANCIAL_COLORS[t.shopify_financial_status] || 'bg-gray-100 text-gray-600')}>
                    {t.shopify_financial_status}
                  </span>
                )}
                {t.shopify_fulfillment_status && (
                  <span className={clsx('badge text-xs', FULFILLMENT_COLORS[t.shopify_fulfillment_status] || 'bg-gray-100 text-gray-600')}>
                    {t.shopify_fulfillment_status}
                  </span>
                )}
                {!t.shopify_financial_status && t.tags?.map(tag => (
                  <span key={tag} className="badge bg-gray-100 text-gray-600">{tag}</span>
                ))}
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
