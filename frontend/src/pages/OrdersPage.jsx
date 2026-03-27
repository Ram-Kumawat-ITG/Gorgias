// Orders page — lists both regular orders and draft orders, links to detail page
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, ChevronRight } from 'lucide-react';
import api from '../api/client';
import clsx from 'clsx';

const FIN = {
  paid: 'bg-green-100 text-green-700', pending: 'bg-yellow-100 text-yellow-700',
  refunded: 'bg-red-100 text-red-700', partially_refunded: 'bg-orange-100 text-orange-700',
};
const DRAFT_STATUS = {
  open: 'bg-yellow-100 text-yellow-700', invoice_sent: 'bg-blue-100 text-blue-700',
  completed: 'bg-green-100 text-green-700',
};

export default function OrdersPage() {
  const navigate = useNavigate();
  const [tab, setTab] = useState('orders');
  const [orders, setOrders] = useState([]);
  const [drafts, setDrafts] = useState([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);

  async function loadOrders() {
    setLoading(true);
    try {
      const res = await api.get('/orders', { params: { search, limit: 50 } });
      setOrders(res.data.orders);
    } catch {} finally { setLoading(false); }
  }

  async function loadDrafts() {
    setLoading(true);
    try {
      const res = await api.get('/orders/drafts/list');
      setDrafts(res.data.drafts);
    } catch {} finally { setLoading(false); }
  }

  useEffect(() => {
    if (tab === 'orders') loadOrders();
    else loadDrafts();
  }, [tab, search]);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold text-gray-900">Orders</h1>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-4">
        {['orders', 'drafts'].map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={clsx('px-4 py-2 rounded-lg text-sm font-medium capitalize transition-colors',
              tab === t ? 'bg-brand-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200')}>
            {t === 'orders' ? 'Orders' : 'Draft Orders'}
          </button>
        ))}
      </div>

      {/* Search (orders only) */}
      {tab === 'orders' && (
        <div className="relative mb-4">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input type="text" value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search by order number, email, or name..."
            className="w-full pl-10 pr-4 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
        </div>
      )}

      {/* Orders list */}
      {tab === 'orders' && (
        <div className="card divide-y divide-gray-50">
          {loading ? (
            <div className="p-8 text-center text-gray-400">Loading orders...</div>
          ) : orders.length === 0 ? (
            <div className="p-8 text-center text-gray-400">No orders found</div>
          ) : orders.map(o => (
            <div key={o.id} onClick={() => navigate(`/orders/${o.id}`)}
              className="flex items-center justify-between px-4 py-3 hover:bg-gray-50 cursor-pointer transition-colors group">
              <div className="flex items-center gap-3 min-w-0 flex-1">
                <span className="text-sm font-semibold text-gray-900 w-20">{o.name || `#${o.order_number}`}</span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-gray-700 truncate">{o.customer_name || '—'}</p>
                  <p className="text-xs text-gray-400">{o.email}</p>
                </div>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                <span className={clsx('badge', FIN[o.financial_status] || 'bg-gray-100 text-gray-600')}>{o.financial_status}</span>
                <span className={clsx('badge', {
                  'bg-green-100 text-green-700': o.fulfillment_status === 'fulfilled',
                  'bg-yellow-100 text-yellow-700': o.fulfillment_status === 'partial',
                  'bg-gray-100 text-gray-600': !o.fulfillment_status,
                })}>{o.fulfillment_status || 'unfulfilled'}</span>
                <span className="text-sm font-medium text-gray-900 w-20 text-right">${o.total_price}</span>
                <span className="text-xs text-gray-400 w-24 text-right">
                  {o.created_at ? new Date(o.created_at).toLocaleDateString() : ''}
                </span>
                <ChevronRight size={16} className="text-gray-300 group-hover:text-gray-500" />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Draft orders list */}
      {tab === 'drafts' && (
        <div className="card divide-y divide-gray-50">
          {loading ? (
            <div className="p-8 text-center text-gray-400">Loading drafts...</div>
          ) : drafts.length === 0 ? (
            <div className="p-8 text-center text-gray-400">No draft orders</div>
          ) : drafts.map(d => (
            <div key={d.id} onClick={() => navigate(`/orders/${d.id}?type=draft`)}
              className="flex items-center justify-between px-4 py-3 hover:bg-gray-50 cursor-pointer transition-colors group">
              <div className="flex items-center gap-3 min-w-0 flex-1">
                <span className="text-sm font-semibold text-gray-900 w-20">{d.name || d.id}</span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-gray-700 truncate">{d.customer_name || '—'}</p>
                  <p className="text-xs text-gray-400">{d.email}</p>
                </div>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                <span className="badge bg-purple-100 text-purple-700">Draft</span>
                <span className={clsx('badge', DRAFT_STATUS[d.status] || 'bg-gray-100 text-gray-600')}>{d.status}</span>
                <span className="text-sm font-medium text-gray-900 w-20 text-right">${d.total_price}</span>
                <span className="text-xs text-gray-400 w-24 text-right">
                  {d.created_at ? new Date(d.created_at).toLocaleDateString() : ''}
                </span>
                <ChevronRight size={16} className="text-gray-300 group-hover:text-gray-500" />
              </div>
            </div>
          ))}
        </div>
      )}

      <p className="text-xs text-gray-400 mt-3 text-center">Data fetched live from Shopify</p>
    </div>
  );
}
