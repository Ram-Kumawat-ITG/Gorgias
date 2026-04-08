// Customers page — real-time Shopify data, create customer syncs to Shopify
import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, Plus, ChevronRight as Arrow, X, ChevronLeft, ChevronRight } from 'lucide-react';
import api from '../api/client';
import { useToast, ToastContainer } from '../components/Toast';

const LIMIT = 20;

export default function CustomersPage() {
  const navigate = useNavigate();
  const [customers, setCustomers] = useState([]);
  const [total, setTotal] = useState(0);
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const debounceRef = useRef(null);

  // Create modal
  const [showCreate, setShowCreate] = useState(false);
  const [createForm, setCreateForm] = useState({
    email: '', first_name: '', last_name: '', company: '',
    address: '', city: '', state: '', zip: '', country_code: 'IN', tags: '', notes: '',
  });
  const [creating, setCreating] = useState(false);

  const { toasts, addToast, removeToast } = useToast();

  async function loadCustomers() {
    setLoading(true);
    try {
      const res = await api.get('/customers', { params: { search, limit: LIMIT, page } });
      setCustomers(res.data.customers ?? []);
      setTotal(res.data.total ?? 0);
    } catch (err) {
      addToast(err.response?.data?.detail || 'Failed to load customers from Shopify', 'error');
    } finally { setLoading(false); }
  }

  // Debounce searchInput → search (300ms)
  useEffect(() => {
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setSearch(searchInput);
      setPage(1);
    }, 300);
    return () => clearTimeout(debounceRef.current);
  }, [searchInput]);

  useEffect(() => { loadCustomers(); }, [search, page]);

  async function handleCreate(e) {
    e.preventDefault();
    setCreating(true);
    try {
      const res = await api.post('/customers', {
        email: createForm.email,
        first_name: createForm.first_name || null,
        last_name: createForm.last_name || null,
        company: createForm.company || null,
        address: createForm.address || null,
        city: createForm.city || null,
        state: createForm.state || null,
        zip: createForm.zip || null,
        country_code: createForm.country_code || 'IN',
        tags: createForm.tags || null,
        notes: createForm.notes || null,
      });
      setCreateForm({
        email: '', first_name: '', last_name: '', company: '',
        address: '', city: '', state: '', zip: '', country_code: 'IN', tags: '', notes: '',
      });
      setShowCreate(false);
      addToast('Customer created on Shopify');
      navigate(`/customers/${res.data.id}`);
    } catch (err) {
      addToast(err.response?.data?.detail || 'Failed to create customer', 'error');
    } finally { setCreating(false); }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold text-gray-900">Customers</h1>
        <button onClick={() => setShowCreate(true)} className="btn-primary flex items-center gap-2">
          <Plus size={16} /> Create Customer
        </button>
      </div>

      {/* Search */}
      <div className="relative mb-4">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
        <input
          type="text"
          value={searchInput}
          onChange={e => setSearchInput(e.target.value)}
          placeholder="Search by name, email, or tag..."
          className="w-full pl-10 pr-4 py-2 border border-gray-200 rounded-lg text-sm
                     focus:outline-none focus:ring-2 focus:ring-brand-500"
        />
      </div>

      {/* Customer list — client-side pagination over Shopify results */}
      {(() => {
        const totalCount = customers.length;
        const totalPages = Math.ceil(totalCount / LIMIT);
        const paged = customers.slice((page - 1) * LIMIT, page * LIMIT);
        return (
          <>
            <div className="card divide-y divide-gray-100">
              {loading ? (
                <div className="flex items-center justify-center py-12"><div className="w-7 h-7 border-4 border-gray-200 border-t-brand-600 rounded-full animate-spin" /></div>
              ) : paged.length === 0 ? (
                <div className="p-8 text-center text-gray-400">
                  {search ? 'No customers match your search' : 'No customers in Shopify yet'}
                </div>
              ) : (
                paged.map(c => (
                  <div
                    key={c.id}
                    onClick={() => navigate(`/customers/${c.id}`)}
                    className="flex items-center justify-between px-4 py-3 hover:bg-gray-50 cursor-pointer transition-colors group"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-gray-900">
                        {c.first_name || ''} {c.last_name || ''}
                        {!c.first_name && !c.last_name && <span className="text-gray-400 italic">No name</span>}
                      </p>
                      <p className="text-xs text-gray-500">{c.email}</p>
                    </div>
                    <div className="flex items-center gap-4 shrink-0 ml-4">
                      <div className="text-right">
                        <p className="text-sm font-medium text-gray-900">${c.total_spent || '0.00'}</p>
                        <p className="text-xs text-gray-400">{c.orders_count || 0} orders</p>
                      </div>
                      <Arrow size={16} className="text-gray-300 group-hover:text-gray-500 transition-colors" />
                    </div>
                  </div>
                ))
              )}
            </div>
            {totalPages > 1 && (
              <div className="flex items-center justify-between mt-4">
                <p className="text-sm text-gray-500">
                  Showing {(page - 1) * LIMIT + 1}–{Math.min(page * LIMIT, totalCount)} of {totalCount}
                </p>
                <div className="flex gap-2">
                  <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
                    className="btn-secondary flex items-center gap-1">
                    <ChevronLeft size={14} /> Previous
                  </button>
                  <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}
                    className="btn-secondary flex items-center gap-1">
                    Next <ChevronRight size={14} />
                  </button>
                </div>
              </div>
            )}
            {totalPages <= 1 && !loading && (
              <p className="text-xs text-gray-400 mt-3 text-center">
                Showing {paged.length} of {totalCount} customers — data fetched live from Shopify
              </p>
            )}
          </>
        );
      })()}

      {/* Create customer modal */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/40" onClick={() => setShowCreate(false)} />
          <div className="relative bg-white rounded-xl shadow-xl w-full max-w-lg mx-4">
            <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
              <h2 className="text-lg font-semibold text-gray-900">New Customer</h2>
              <button type="button" onClick={() => setShowCreate(false)}
                className="p-1 text-gray-400 hover:text-gray-600"><X size={18} /></button>
            </div>
            <form onSubmit={handleCreate}>
              <div className="px-5 py-4 grid grid-cols-2 gap-4 max-h-[70vh] overflow-y-auto">
                <div className="col-span-2">
                  <label className="text-sm font-medium text-gray-700 block mb-1">Email *</label>
                  <input type="email" required value={createForm.email}
                    onChange={e => setCreateForm({ ...createForm, email: e.target.value })}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-700 block mb-1">First Name</label>
                  <input type="text" value={createForm.first_name}
                    onChange={e => setCreateForm({ ...createForm, first_name: e.target.value })}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-700 block mb-1">Last Name</label>
                  <input type="text" value={createForm.last_name}
                    onChange={e => setCreateForm({ ...createForm, last_name: e.target.value })}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                </div>
                <div className="col-span-2">
                  <label className="text-sm font-medium text-gray-700 block mb-1">Company</label>
                  <input type="text" value={createForm.company}
                    onChange={e => setCreateForm({ ...createForm, company: e.target.value })}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                </div>
                <div className="col-span-2">
                  <label className="text-sm font-medium text-gray-700 block mb-1">Address</label>
                  <input type="text" value={createForm.address}
                    onChange={e => setCreateForm({ ...createForm, address: e.target.value })}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-700 block mb-1">City</label>
                  <input type="text" value={createForm.city}
                    onChange={e => setCreateForm({ ...createForm, city: e.target.value })}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-700 block mb-1">State / Province</label>
                  <input type="text" value={createForm.state}
                    onChange={e => setCreateForm({ ...createForm, state: e.target.value })}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-700 block mb-1">ZIP Code</label>
                  <input type="text" value={createForm.zip}
                    onChange={e => setCreateForm({ ...createForm, zip: e.target.value })}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-700 block mb-1">Country Code</label>
                  <input type="text" value={createForm.country_code}
                    onChange={e => setCreateForm({ ...createForm, country_code: e.target.value })}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                    placeholder="IN" />
                </div>
                <div className="col-span-2">
                  <label className="text-sm font-medium text-gray-700 block mb-1">Tags (comma-separated)</label>
                  <input type="text" value={createForm.tags}
                    onChange={e => setCreateForm({ ...createForm, tags: e.target.value })}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                </div>
                <div className="col-span-2">
                  <label className="text-sm font-medium text-gray-700 block mb-1">Notes</label>
                  <input type="text" value={createForm.notes}
                    onChange={e => setCreateForm({ ...createForm, notes: e.target.value })}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                </div>
              </div>
              <div className="flex items-center justify-end gap-2 px-5 py-4 border-t border-gray-100 bg-gray-50">
                <button type="button" className="btn-secondary" onClick={() => setShowCreate(false)}>Cancel</button>
                <button type="submit" className="btn-primary" disabled={creating}>
                  {creating ? 'Creating...' : 'Create on Shopify'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      <ToastContainer toasts={toasts} removeToast={removeToast} />
    </div>
  );
}
