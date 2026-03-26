// Macros management page — list, create, edit, delete canned responses
import { useState, useEffect } from 'react';
import { Pencil, Trash2, Plus } from 'lucide-react';
import api from '../api/client';

export default function MacrosPage() {
  const [macros, setMacros] = useState([]);
  const [name, setName] = useState('');
  const [body, setBody] = useState('');
  const [tags, setTags] = useState('');
  const [editingId, setEditingId] = useState(null);
  const [loading, setLoading] = useState(true);

  async function loadMacros() {
    try {
      const res = await api.get('/macros');
      setMacros(res.data);
    } catch {} finally { setLoading(false); }
  }

  useEffect(() => { loadMacros(); }, []);

  async function handleSubmit(e) {
    e.preventDefault();
    const data = { name, body, tags: tags ? tags.split(',').map(t => t.trim()) : [] };
    try {
      if (editingId) {
        await api.patch(`/macros/${editingId}`, data);
      } else {
        await api.post('/macros', data);
      }
      setName(''); setBody(''); setTags(''); setEditingId(null);
      await loadMacros();
    } catch {}
  }

  async function deleteMacro(id) {
    try {
      await api.delete(`/macros/${id}`);
      await loadMacros();
    } catch {}
  }

  function startEdit(macro) {
    setEditingId(macro.id);
    setName(macro.name);
    setBody(macro.body);
    setTags(macro.tags?.join(', ') || '');
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold text-gray-900 mb-6">Macros</h1>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Form */}
        <form onSubmit={handleSubmit} className="card p-6 space-y-4 h-fit">
          <h2 className="text-lg font-medium">{editingId ? 'Edit Macro' : 'New Macro'}</h2>
          <div>
            <label className="text-sm font-medium text-gray-700 block mb-1">Name</label>
            <input type="text" value={name} onChange={e => setName(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              required />
          </div>
          <div>
            <label className="text-sm font-medium text-gray-700 block mb-1">Body</label>
            <textarea value={body} onChange={e => setBody(e.target.value)} rows={5}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none font-mono"
              placeholder="Hi {{customer.first_name}}, ..." required />
            <p className="text-xs text-gray-400 mt-1">
              Variables: {'{{customer.first_name}}'}, {'{{customer.email}}'}, {'{{order.number}}'}, {'{{order.tracking_url}}'}
            </p>
          </div>
          <div>
            <label className="text-sm font-medium text-gray-700 block mb-1">Tags (comma-separated)</label>
            <input type="text" value={tags} onChange={e => setTags(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
          </div>
          <div className="flex gap-2">
            <button type="submit" className="btn-primary flex items-center gap-1">
              <Plus size={14} /> {editingId ? 'Update' : 'Create'}
            </button>
            {editingId && (
              <button type="button" className="btn-secondary"
                onClick={() => { setEditingId(null); setName(''); setBody(''); setTags(''); }}>
                Cancel
              </button>
            )}
          </div>
        </form>

        {/* List */}
        <div className="card divide-y divide-gray-100">
          {loading ? (
            <div className="p-8 text-center text-gray-400">Loading...</div>
          ) : macros.length === 0 ? (
            <div className="p-8 text-center text-gray-400">No macros yet</div>
          ) : (
            macros.map(m => (
              <div key={m.id} className="px-4 py-3">
                <div className="flex items-center justify-between">
                  <span className="font-medium text-sm text-gray-900">{m.name}</span>
                  <div className="flex gap-1">
                    <button onClick={() => startEdit(m)} className="p-1 text-gray-400 hover:text-gray-600">
                      <Pencil size={14} />
                    </button>
                    <button onClick={() => deleteMacro(m.id)} className="p-1 text-gray-400 hover:text-red-500">
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
                <p className="text-xs text-gray-500 mt-1 line-clamp-2">{m.body}</p>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
