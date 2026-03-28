// Returns page — list all return requests with filters
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronRight, RotateCcw } from 'lucide-react';
import api from '../api/client';
import clsx from 'clsx';

const STATUS_COLORS = {
  requested: 'bg-yellow-100 text-yellow-700',
  approved: 'bg-blue-100 text-blue-700',
  shipped: 'bg-purple-100 text-purple-700',
  received: 'bg-orange-100 text-orange-700',
  resolved: 'bg-green-100 text-green-700',
  rejected: 'bg-red-100 text-red-700',
};

const STATUSES = ['', 'requested', 'approved', 'shipped', 'received', 'resolved', 'rejected'];

export default function ReturnsPage() {
  const navigate = useNavigate();
  const [returns, setReturns] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState('');
  const [resolution, setResolution] = useState('');
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState(null);
  const limit = 20;

  async function loadReturns() {
    setLoading(true);
    try {
      const res = await api.get('/returns', { params: { status, resolution, page, limit } });
      setReturns(res.data.returns);
      setTotal(res.data.total);
    } catch {} finally { setLoading(false); }
  }

  async function loadStats() {
    try {
      const res = await api.get('/returns/stats/overview');
      setStats(res.data);
    } catch {}
  }

  useEffect(() => { loadReturns(); }, [status, resolution, page]);
  useEffect(() => { loadStats(); }, []);

  const totalPages = Math.ceil(total / limit);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <RotateCcw size={24} className="text-brand-600" />
          <h1 className="text-2xl font-semibold text-gray-900">Returns</h1>
        </div>
      </div>

      {/* Stats cards */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3 mb-6">
          <div className="card p-3 text-center">
            <p className="text-2xl font-semibold text-gray-900">{stats.total || 0}</p>
            <p className="text-xs text-gray-500">Total</p>
          </div>
          {['requested', 'approved', 'shipped', 'received', 'resolved', 'rejected'].map(s => (
            <div key={s} className="card p-3 text-center">
              <p className="text-2xl font-semibold text-gray-900">{stats.by_status?.[s] || 0}</p>
              <p className="text-xs text-gray-500 capitalize">{s}</p>
            </div>
          ))}
        </div>
      )}

      {/* Filters */}
      <div className="flex items-center gap-3 mb-4">
        <select value={status} onChange={e => { setStatus(e.target.value); setPage(1); }}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500">
          <option value="">All statuses</option>
          {STATUSES.filter(Boolean).map(s => <option key={s} value={s} className="capitalize">{s}</option>)}
        </select>
        <select value={resolution} onChange={e => { setResolution(e.target.value); setPage(1); }}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500">
          <option value="">All resolutions</option>
          <option value="refund">Refund</option>
          <option value="replacement">Replacement</option>
        </select>
      </div>

      {/* Returns list */}
      <div className="card divide-y divide-gray-50">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="w-7 h-7 border-4 border-gray-200 border-t-brand-600 rounded-full animate-spin" />
          </div>
        ) : returns.length === 0 ? (
          <div className="p-8 text-center text-gray-400">No return requests found</div>
        ) : returns.map(r => (
          <div key={r.id} onClick={() => navigate(`/returns/${r.id}`)}
            className="flex items-center justify-between px-4 py-3 hover:bg-gray-50 cursor-pointer transition-colors group">
            <div className="flex items-center gap-4 min-w-0 flex-1">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className={clsx('badge', STATUS_COLORS[r.status] || 'bg-gray-100 text-gray-600')}>
                    {r.status}
                  </span>
                  <span className="badge bg-gray-100 text-gray-600 capitalize">{r.resolution}</span>
                  <span className="text-sm font-medium text-gray-900">Order #{r.order_number}</span>
                </div>
                <p className="text-xs text-gray-500 mt-0.5">
                  {r.customer_name || r.customer_email} ·
                  {r.items?.length || 0} item{r.items?.length !== 1 ? 's' : ''} ·
                  {r.reason?.replace(/_/g, ' ')} ·
                  Initiated by {r.initiated_by}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-3 shrink-0">
              <span className="text-xs text-gray-400">
                {r.created_at ? new Date(r.created_at).toLocaleDateString() : ''}
              </span>
              <ChevronRight size={16} className="text-gray-300 group-hover:text-gray-500" />
            </div>
          </div>
        ))}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-4">
          <p className="text-sm text-gray-500">{(page - 1) * limit + 1}–{Math.min(page * limit, total)} of {total}</p>
          <div className="flex gap-2">
            <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} className="btn-secondary text-sm">Prev</button>
            <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages} className="btn-secondary text-sm">Next</button>
          </div>
        </div>
      )}
    </div>
  );
}
