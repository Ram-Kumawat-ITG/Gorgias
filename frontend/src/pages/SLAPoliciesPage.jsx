// SLA policies management page — create and list SLA policies
import { useState, useEffect } from 'react';
import { Trash2, Plus } from 'lucide-react';
import api from '../api/client';

export default function SLAPoliciesPage() {
  const [policies, setPolicies] = useState([]);
  const [name, setName] = useState('');
  const [priority, setPriority] = useState('normal');
  const [firstResponse, setFirstResponse] = useState(1);
  const [resolution, setResolution] = useState(24);
  const [channels, setChannels] = useState('email, manual');
  const [loading, setLoading] = useState(true);

  async function loadPolicies() {
    try {
      const res = await api.get('/sla-policies');
      setPolicies(res.data);
    } catch {} finally { setLoading(false); }
  }

  useEffect(() => { loadPolicies(); }, []);

  async function handleSubmit(e) {
    e.preventDefault();
    try {
      await api.post('/sla-policies', {
        name, priority,
        first_response_hours: Number(firstResponse),
        resolution_hours: Number(resolution),
        applies_to_channels: channels.split(',').map(c => c.trim()),
      });
      setName('');
      await loadPolicies();
    } catch {}
  }

  async function deletePolicy(id) {
    try { await api.delete(`/sla-policies/${id}`); await loadPolicies(); } catch {}
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold text-gray-900 mb-6">SLA Policies</h1>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <form onSubmit={handleSubmit} className="card p-6 space-y-4 h-fit">
          <h2 className="text-lg font-medium">New Policy</h2>
          <div>
            <label className="text-sm font-medium text-gray-700 block mb-1">Name</label>
            <input type="text" value={name} onChange={e => setName(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              required />
          </div>
          <div>
            <label className="text-sm font-medium text-gray-700 block mb-1">Priority</label>
            <select value={priority} onChange={e => setPriority(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500">
              <option value="low">Low</option>
              <option value="normal">Normal</option>
              <option value="high">High</option>
              <option value="urgent">Urgent</option>
            </select>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-medium text-gray-700 block mb-1">First Response (hrs)</label>
              <input type="number" step="0.5" value={firstResponse} onChange={e => setFirstResponse(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                required />
            </div>
            <div>
              <label className="text-sm font-medium text-gray-700 block mb-1">Resolution (hrs)</label>
              <input type="number" step="0.5" value={resolution} onChange={e => setResolution(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                required />
            </div>
          </div>
          <div>
            <label className="text-sm font-medium text-gray-700 block mb-1">Channels (comma-separated)</label>
            <input type="text" value={channels} onChange={e => setChannels(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
          </div>
          <button type="submit" className="btn-primary flex items-center gap-1">
            <Plus size={14} /> Create Policy
          </button>
        </form>

        <div className="card divide-y divide-gray-100">
          {loading ? (
            <div className="flex items-center justify-center py-12"><div className="w-7 h-7 border-4 border-gray-200 border-t-brand-600 rounded-full animate-spin" /></div>
          ) : policies.length === 0 ? (
            <div className="p-8 text-center text-gray-400">No policies yet</div>
          ) : (
            policies.map(p => (
              <div key={p.id} className="px-4 py-3">
                <div className="flex items-center justify-between">
                  <div>
                    <span className="font-medium text-sm text-gray-900">{p.name}</span>
                    <span className="ml-2 badge bg-blue-100 text-blue-700 capitalize">{p.priority}</span>
                  </div>
                  <button onClick={() => deletePolicy(p.id)} className="p-1 text-gray-400 hover:text-red-500">
                    <Trash2 size={14} />
                  </button>
                </div>
                <p className="text-xs text-gray-500 mt-1">
                  Response: {p.first_response_hours}h | Resolution: {p.resolution_hours}h | Channels: {p.applies_to_channels?.join(', ')}
                </p>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
