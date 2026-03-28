// Analytics dashboard — charts and stat cards for helpdesk metrics
import { useState, useEffect } from 'react';
import { LineChart, Line, PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import api from '../api/client';

const STATUS_COLORS = { open: '#3b82f6', pending: '#f59e0b', resolved: '#22c55e', closed: '#6b7280' };
const CHART_COLORS = ['#16a34a', '#3b82f6', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316', '#06b6d4', '#84cc16'];

export default function AnalyticsPage() {
  const [days, setDays] = useState(30);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api.get('/analytics/overview', { params: { days } })
      .then(res => setData(res.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [days]);

  if (loading) return <div className="flex items-center justify-center min-h-[60vh]"><div className="w-8 h-8 border-4 border-gray-200 border-t-brand-600 rounded-full animate-spin" /></div>;
  if (!data) return <div className="p-8 text-center text-gray-400">Failed to load analytics</div>;

  const totalTickets = Object.values(data.tickets_by_status || {}).reduce((a, b) => a + b, 0);
  const resolved = (data.tickets_by_status?.resolved || 0) + (data.tickets_by_status?.closed || 0);
  const resolvedRate = totalTickets > 0 ? Math.round((resolved / totalTickets) * 100) : 0;
  const breaches = data.sla_compliance?.breached || 0;

  const statusPieData = Object.entries(data.tickets_by_status || {}).map(([name, value]) => ({ name, value }));
  const channelBarData = Object.entries(data.tickets_by_channel || {}).map(([name, value]) => ({ name, value }));
  const topCustomers = (data.top_customers || []).slice(0, 8);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold text-gray-900">Analytics</h1>
        <select value={days} onChange={e => setDays(Number(e.target.value))}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500">
          <option value={7}>Last 7 days</option>
          <option value={30}>Last 30 days</option>
          <option value={90}>Last 90 days</option>
        </select>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <div className="card p-4">
          <p className="text-sm text-gray-500">Total Tickets</p>
          <p className="text-2xl font-semibold text-gray-900">{totalTickets}</p>
        </div>
        <div className="card p-4">
          <p className="text-sm text-gray-500">Resolved</p>
          <p className="text-2xl font-semibold text-gray-900">{resolved} <span className="text-sm text-gray-400">({resolvedRate}%)</span></p>
        </div>
        <div className="card p-4">
          <p className="text-sm text-gray-500">Avg. Response Time</p>
          <p className="text-2xl font-semibold text-gray-900">{data.avg_first_response_minutes || 0} <span className="text-sm text-gray-400">min</span></p>
        </div>
        <div className="card p-4">
          <p className="text-sm text-gray-500">SLA Breaches</p>
          <p className="text-2xl font-semibold text-red-600">{breaches}</p>
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Daily volume line chart */}
        <div className="card p-4">
          <h3 className="text-sm font-medium text-gray-700 mb-4">Daily Ticket Volume</h3>
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={data.daily_volume || []}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Line type="monotone" dataKey="count" stroke="#16a34a" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Status pie chart */}
        <div className="card p-4">
          <h3 className="text-sm font-medium text-gray-700 mb-4">Tickets by Status</h3>
          <ResponsiveContainer width="100%" height={250}>
            <PieChart>
              <Pie data={statusPieData} cx="50%" cy="50%" outerRadius={90} dataKey="value" label={({ name, value }) => `${name}: ${value}`}>
                {statusPieData.map((entry, i) => (
                  <Cell key={entry.name} fill={STATUS_COLORS[entry.name] || CHART_COLORS[i % CHART_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Channel bar chart */}
        <div className="card p-4">
          <h3 className="text-sm font-medium text-gray-700 mb-4">Tickets by Channel</h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={channelBarData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="name" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="value" fill="#16a34a" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Top customers bar chart */}
        <div className="card p-4">
          <h3 className="text-sm font-medium text-gray-700 mb-4">Top Customers</h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={topCustomers} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis type="number" tick={{ fontSize: 11 }} />
              <YAxis type="category" dataKey="email" tick={{ fontSize: 10 }} width={150} />
              <Tooltip />
              <Bar dataKey="count" fill="#3b82f6" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
