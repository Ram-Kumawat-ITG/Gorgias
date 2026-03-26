// Macro picker — searchable dropdown to insert canned responses into the reply composer
import { useState, useEffect, useRef } from 'react';
import { FileText } from 'lucide-react';
import api from '../api/client';

export default function MacroPicker({ ticketId, onInsert }) {
  const [open, setOpen] = useState(false);
  const [macros, setMacros] = useState([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    api.get('/macros', { params: { search } })
      .then(res => setMacros(res.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [open, search]);

  useEffect(() => {
    function handleClickOutside(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  async function selectMacro(macro) {
    try {
      const res = await api.post(`/macros/${macro.id}/preview?ticket_id=${ticketId}`);
      onInsert(res.data.rendered);
    } catch {
      onInsert(macro.body);
    }
    setOpen(false);
  }

  return (
    <div className="relative" ref={ref}>
      <button onClick={() => setOpen(!open)} className="btn-secondary flex items-center gap-1 text-xs">
        <FileText size={14} /> Macros
      </button>
      {open && (
        <div className="absolute left-0 top-full mt-1 w-72 bg-white border border-gray-200 rounded-lg shadow-lg z-10">
          <div className="p-2 border-b border-gray-100">
            <input
              type="text"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search macros..."
              className="w-full border border-gray-200 rounded px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-brand-500"
              autoFocus
            />
          </div>
          <div className="max-h-48 overflow-y-auto">
            {loading ? (
              <p className="p-3 text-xs text-gray-400 text-center">Loading...</p>
            ) : macros.length === 0 ? (
              <p className="p-3 text-xs text-gray-400 text-center">No macros found</p>
            ) : (
              macros.map(m => (
                <button
                  key={m.id}
                  onClick={() => selectMacro(m)}
                  className="w-full text-left px-3 py-2 hover:bg-gray-50 transition-colors border-b border-gray-50 last:border-0"
                >
                  <p className="text-sm font-medium text-gray-800">{m.name}</p>
                  <p className="text-xs text-gray-400 truncate">{m.body}</p>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
