// Customer activity timeline — filterable by entity type
import { useState, useEffect } from 'react';
import api from '../api/client';
import clsx from 'clsx';

const EVENT_COLORS = {
  'ticket.created': 'bg-blue-100 text-blue-700',
  'ticket.status_changed': 'bg-purple-100 text-purple-700',
  'message.sent': 'bg-gray-100 text-gray-700',
  'message.received': 'bg-gray-100 text-gray-700',
  'order.created': 'bg-green-100 text-green-700',
  'order.fulfilled': 'bg-teal-100 text-teal-700',
  'sla.breached': 'bg-red-100 text-red-700',
};

const FILTERS = [
  { label: 'All', value: '' },
  { label: 'Tickets', value: 'ticket' },
  { label: 'Messages', value: 'message' },
  { label: 'Orders', value: 'order' },
];

export default function CustomerHistory({ customerEmail }) {
  const [events, setEvents] = useState([]);
  const [filter, setFilter] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!customerEmail) return;
    setLoading(true);
    const params = { days: 90, limit: 50 };
    if (filter) params.event_types = filter;
    api.get(`/history/customer/${encodeURIComponent(customerEmail)}`, { params })
      .then(res => setEvents(res.data.events || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [customerEmail, filter]);

  function formatTime(iso) {
    const d = new Date(iso);
    const now = new Date();
    const diff = Math.floor((now - d) / 60000);
    if (diff < 60) return `${diff}m ago`;
    if (diff < 1440) return `${Math.floor(diff / 60)}h ago`;
    return d.toLocaleDateString();
  }

  return (
    <div className="card p-4">
      <h3 className="text-sm font-semibold text-gray-900 mb-3">Activity</h3>

      <div className="flex gap-1 mb-3">
        {FILTERS.map(f => (
          <button
            key={f.value}
            onClick={() => setFilter(f.value)}
            className={clsx(
              'px-2 py-0.5 rounded text-xs font-medium transition-colors',
              filter === f.value ? 'bg-brand-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            )}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="max-h-64 overflow-y-auto space-y-2">
        {loading ? (
          <div className="flex items-center justify-center py-4"><div className="w-5 h-5 border-2 border-gray-200 border-t-brand-600 rounded-full animate-spin" /></div>
        ) : events.length === 0 ? (
          <p className="text-xs text-gray-400 text-center py-4">No activity found</p>
        ) : (
          events.map(e => (
            <div key={e.id} className="flex items-start gap-2 text-xs">
              <span className={clsx('badge shrink-0 mt-0.5', EVENT_COLORS[e.event] || 'bg-gray-100 text-gray-600')}>
                {e.event}
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-gray-700 truncate">{e.description}</p>
                <p className="text-gray-400">{formatTime(e.created_at)}</p>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
