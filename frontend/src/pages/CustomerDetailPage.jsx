// Customer detail — Gorgias-style layout: left tickets + right sidebar with Shopify data
import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft, Pencil, Trash2, ExternalLink, Mail, Phone, StickyNote,
  ShoppingBag, DollarSign, X, Plus, Ban, ChevronDown, ChevronUp,
} from 'lucide-react';
import api from '../api/client';
import clsx from 'clsx';
import CreateOrderModal from '../components/CreateOrderModal';
import { useToast, ToastContainer } from '../components/Toast';

const FIN_COLORS = {
  paid: 'bg-green-100 text-green-700',
  pending: 'bg-yellow-100 text-yellow-700',
  refunded: 'bg-red-100 text-red-700',
  partially_refunded: 'bg-orange-100 text-orange-700',
  voided: 'bg-gray-100 text-gray-600',
};

export default function CustomerDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const { toasts, addToast, addConfirmToast, removeToast } = useToast();

  // Modals
  const [editModal, setEditModal] = useState(false);
  const [editForm, setEditForm] = useState(null);
  const [saving, setSaving] = useState(false);
  const [orderModal, setOrderModal] = useState(false);

  // Sidebar collapse sections
  const [shopifyOpen, setShopifyOpen] = useState(true);

  // Tickets for this customer
  const [tickets, setTickets] = useState([]);
  const [ticketsLoading, setTicketsLoading] = useState(true);

  async function loadCustomer() {
    setLoading(true);
    try {
      const res = await api.get(`/customers/${id}`);
      setData(res.data);
      // Load tickets for this customer
      if (res.data.customer?.email) {
        loadTickets(res.data.customer.email);
      }
    } catch {
      setData(null);
    } finally { setLoading(false); }
  }

  async function loadTickets(email) {
    setTicketsLoading(true);
    try {
      const res = await api.get('/tickets', { params: { limit: 50 } });
      // Filter by customer email client-side (backend doesn't have email filter param)
      const filtered = (res.data.tickets || []).filter(t => t.customer_email === email);
      setTickets(filtered);
    } catch {
      setTickets([]);
    } finally { setTicketsLoading(false); }
  }

  useEffect(() => { loadCustomer(); }, [id]);

  // ── Edit ──
  function openEditModal() {
    const c = data.customer;
    setEditForm({
      first_name: c.first_name || '', last_name: c.last_name || '',
      company: c.company || '', address: c.address || '',
      city: c.city || '', state: c.state || '',
      zip: c.zip || '', country_code: c.country_code || 'IN',
      tags: c.tags || '', notes: c.notes || '',
    });
    setEditModal(true);
  }

  async function handleEditSubmit(e) {
    e.preventDefault();
    setSaving(true);
    try {
      await api.patch(`/customers/${id}`, editForm);
      setEditModal(false);
      addToast('Customer updated on Shopify');
      await loadCustomer();
    } catch (err) {
      addToast(err.response?.data?.detail || 'Failed to update', 'error');
    } finally { setSaving(false); }
  }

  // ── Delete ──
  function requestDelete() {
    addConfirmToast('Delete this customer from Shopify? This cannot be undone.', async () => {
      try {
        await api.delete(`/customers/${id}`);
        addToast('Customer deleted from Shopify');
        navigate('/customers');
      } catch (err) {
        addToast(err.response?.data?.detail || 'Failed to delete', 'error');
      }
    });
  }


  if (loading) return <div className="flex items-center justify-center min-h-[60vh]"><div className="w-8 h-8 border-4 border-gray-200 border-t-brand-600 rounded-full animate-spin" /></div>;
  if (!data) return <div className="p-8 text-center text-gray-400">Customer not found</div>;

  const { customer, orders, ticket_stats } = data;
  const fullName = [customer.first_name, customer.last_name].filter(Boolean).join(' ') || 'Unnamed Customer';
  const initials = ((customer.first_name?.[0] || '') + (customer.last_name?.[0] || '')).toUpperCase() || '?';

  return (
    <div className="flex flex-col lg:flex-row gap-0 -m-6 min-h-screen">

      {/* ═══════ LEFT: Main content ═══════ */}
      <div className="flex-1 p-6 overflow-auto">
        {/* Header */}
        <div className="flex items-center gap-3 mb-6">
          <button onClick={() => navigate('/customers')}
            className="p-2 rounded-lg hover:bg-gray-100 transition-colors text-gray-500">
            <ArrowLeft size={20} />
          </button>
          <h1 className="text-2xl font-semibold text-gray-900 flex-1">{fullName}</h1>
          <button onClick={() => navigate('/tickets/new')}
            className="btn-secondary text-sm">Create ticket</button>
        </div>

        {/* Ticket list */}
        <div className="card">
          <div className="px-5 py-3 border-b border-gray-100">
            <div className="flex items-center gap-4 text-xs text-gray-500">
              <span className="font-medium text-gray-700">Tickets</span>
              <span>{ticket_stats.total} total, {ticket_stats.open} open</span>
            </div>
          </div>

          {ticketsLoading ? (
            <div className="flex items-center justify-center py-8"><div className="w-6 h-6 border-3 border-gray-200 border-t-brand-600 rounded-full animate-spin" /></div>
          ) : tickets.length === 0 ? (
            <div className="p-8 text-center text-gray-400 text-sm">No tickets for this customer</div>
          ) : (
            <div className="divide-y divide-gray-50">
              {tickets.map(t => (
                <div key={t.id} onClick={() => navigate(`/tickets/${t.id}`)}
                  className="flex items-center justify-between px-5 py-3 hover:bg-gray-50 cursor-pointer transition-colors">
                  <div className="flex items-center gap-3 min-w-0">
                    <Mail size={16} className="text-gray-400 shrink-0" />
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className={clsx('badge text-xs', {
                          'bg-green-100 text-green-700': t.status === 'open',
                          'bg-yellow-100 text-yellow-700': t.status === 'pending',
                          'bg-blue-100 text-blue-700': t.status === 'resolved',
                          'bg-gray-100 text-gray-600': t.status === 'closed',
                        })}>
                          {t.status?.toUpperCase()}
                        </span>
                        <span className="text-sm text-gray-900 truncate">{t.subject}</span>
                      </div>
                      <p className="text-xs text-gray-400 mt-0.5">ID: {t.id?.slice(0, 8)}</p>
                    </div>
                  </div>
                  <span className="text-xs text-gray-400 shrink-0">
                    {t.created_at ? new Date(t.created_at).toLocaleDateString() : ''}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Orders table */}
        <div className="card mt-6">
          <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between">
            <span className="text-sm font-medium text-gray-700">Orders ({orders.length})</span>
          </div>
          {orders.length === 0 ? (
            <div className="p-6 text-center text-gray-400 text-sm">No orders</div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50 text-left">
                  <th className="px-5 py-2 text-xs font-medium text-gray-500 uppercase">Order</th>
                  <th className="px-5 py-2 text-xs font-medium text-gray-500 uppercase">Items</th>
                  <th className="px-5 py-2 text-xs font-medium text-gray-500 uppercase">Status</th>
                  <th className="px-5 py-2 text-xs font-medium text-gray-500 uppercase">Total</th>
                  <th className="px-5 py-2 text-xs font-medium text-gray-500 uppercase">Date</th>
                  <th className="px-5 py-2 text-xs font-medium text-gray-500 uppercase w-16"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {orders.map(o => (
                  <tr key={o.id} onClick={() => navigate(`/orders/${o.id}`)}
                    className="hover:bg-gray-50 transition-colors cursor-pointer">
                    <td className="px-5 py-2.5 text-sm font-semibold text-brand-600">#{o.order_number}</td>
                    <td className="px-5 py-2.5">
                      <div className="text-xs text-gray-600 max-w-xs">
                        {o.line_items?.slice(0, 2).map((li, j) => (
                          <span key={j}>{j > 0 && ', '}{li.quantity}x {li.title}</span>
                        ))}
                        {o.line_items?.length > 2 && <span className="text-gray-400"> +{o.line_items.length - 2}</span>}
                      </div>
                    </td>
                    <td className="px-5 py-2.5">
                      <span className={clsx('badge', FIN_COLORS[o.financial_status] || 'bg-gray-100 text-gray-600')}>
                        {o.financial_status || 'unknown'}
                      </span>
                    </td>
                    <td className="px-5 py-2.5 text-sm font-medium text-gray-900">${o.total_price || '0.00'}</td>
                    <td className="px-5 py-2.5 text-xs text-gray-500">
                      {o.created_at ? new Date(o.created_at).toLocaleDateString() : '—'}
                    </td>
                    <td className="px-5 py-2.5">
                      <span className="text-xs text-gray-400">View</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* ═══════ RIGHT: Sidebar ═══════ */}
      <div className="w-full lg:w-80 border-t lg:border-t-0 lg:border-l border-gray-200 bg-white p-5 overflow-y-auto shrink-0">
        {/* Customer header */}
        <div className="flex items-center gap-3 mb-5">
          <div className="w-10 h-10 rounded-full bg-gray-200 flex items-center justify-center text-sm font-semibold text-gray-600">
            {initials}
          </div>
          <div className="flex-1 min-w-0">
            <p className="font-semibold text-gray-900 truncate">{fullName}</p>
          </div>
          <div className="flex gap-1">
            <button onClick={openEditModal} className="p-1.5 text-gray-400 hover:text-gray-600 rounded hover:bg-gray-100" title="Edit">
              <Pencil size={14} />
            </button>
            <button onClick={requestDelete} className="p-1.5 text-gray-400 hover:text-red-500 rounded hover:bg-gray-100" title="Delete">
              <Trash2 size={14} />
            </button>
          </div>
        </div>

        {/* Customer Fields */}
        <div className="mb-5">
          <p className="text-xs font-semibold text-gray-700 uppercase tracking-wider mb-3">Customer Fields</p>
          <div className="space-y-2.5">
            {customer.notes ? (
              <div className="flex items-start gap-2">
                <StickyNote size={14} className="text-gray-400 mt-0.5 shrink-0" />
                <span className="text-sm text-gray-600">{customer.notes}</span>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <StickyNote size={14} className="text-gray-400" />
                <span className="text-sm text-gray-400 italic">This customer has no note.</span>
              </div>
            )}
            <div className="flex items-center gap-2">
              <Mail size={14} className="text-gray-400 shrink-0" />
              <span className="text-sm text-blue-600">{customer.email}</span>
            </div>
            {(customer.address || customer.city || customer.state) && (
              <div className="flex items-start gap-2">
                <span className="w-[14px] shrink-0" />
                <span className="text-sm text-gray-600">
                  {[customer.address, customer.city, customer.state, customer.zip].filter(Boolean).join(', ')}
                </span>
              </div>
            )}
            {customer.company && (
              <div className="flex items-center gap-2">
                <span className="w-[14px] shrink-0" />
                <span className="text-sm text-gray-600">{customer.company}</span>
              </div>
            )}
          </div>
        </div>

        {/* Ticket stats */}
        <div className="mb-5 flex items-center gap-2 text-sm">
          <ShoppingBag size={14} className="text-gray-400" />
          <span className="text-gray-600">
            {ticket_stats.total} ticket{ticket_stats.total !== 1 ? 's' : ''}, {ticket_stats.open} open
          </span>
        </div>

        <div className="border-t border-gray-100 pt-4 mb-4" />

        {/* Shopify section */}
        <div>
          <button onClick={() => setShopifyOpen(!shopifyOpen)}
            className="flex items-center justify-between w-full mb-3">
            <div className="flex items-center gap-2">
              <img src="https://cdn.shopify.com/shopifycloud/web/assets/v1/favicon-default-large.png"
                alt="" className="w-4 h-4" />
              <span className="text-sm font-semibold text-brand-600">{fullName}</span>
            </div>
            {shopifyOpen ? <ChevronUp size={14} className="text-gray-400" /> : <ChevronDown size={14} className="text-gray-400" />}
          </button>

          {shopifyOpen && (
            <div className="space-y-3">
              <button onClick={() => setOrderModal(true)}
                className="btn-secondary w-full flex items-center justify-center gap-1.5 text-sm">
                <Plus size={14} /> Create order
              </button>

              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-500">Total spent:</span>
                  <span className="font-medium text-gray-900">
                    {customer.total_spent && customer.total_spent !== '0.00' ? `$${customer.total_spent}` : '—'}
                  </span>
                </div>
                <div>
                  <span className="text-gray-500">Orders:</span>
                  {orders.length > 0 ? (
                    <div className="mt-1.5 space-y-1.5">
                      {orders.slice(0, 5).map(o => (
                        <div key={o.id} onClick={() => navigate(`/orders/${o.id}`)}
                          className="flex items-center justify-between text-xs bg-gray-50 rounded px-2 py-1.5 cursor-pointer hover:bg-gray-100 transition-colors">
                          <span className="font-medium text-brand-600">#{o.order_number}</span>
                          <div className="flex items-center gap-1.5">
                            <span className={clsx('badge text-xs', FIN_COLORS[o.financial_status] || 'bg-gray-100 text-gray-600')}>
                              {o.financial_status}
                            </span>
                            <span className="text-gray-500">${o.total_price}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <span className="text-gray-400 ml-2">—</span>
                  )}
                </div>
              </div>

              <div className="border-t border-gray-100 pt-3 space-y-2 text-xs text-gray-500">
                <div className="flex justify-between">
                  <span>Shopify ID:</span>
                  <span className="font-mono text-gray-700">{customer.id}</span>
                </div>
                <div className="flex justify-between">
                  <span>Created at:</span>
                  <span className="text-gray-700">
                    {customer.created_at ? new Date(customer.created_at).toLocaleString() : '—'}
                  </span>
                </div>
                {customer.tags && (
                  <div>
                    <span>Tags:</span>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {customer.tags.split(',').map(t => t.trim()).filter(Boolean).map(t => (
                        <span key={t} className="badge bg-gray-100 text-gray-600">{t}</span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ═══════ MODALS ═══════ */}

      {/* Edit Customer Modal */}
      {editModal && editForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/40" onClick={() => setEditModal(false)} />
          <div className="relative bg-white rounded-xl shadow-xl w-full max-w-lg mx-4">
            <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
              <h2 className="text-lg font-semibold text-gray-900">Edit Customer</h2>
              <button onClick={() => setEditModal(false)} className="p-1 text-gray-400 hover:text-gray-600"><X size={18} /></button>
            </div>
            <form onSubmit={handleEditSubmit}>
              <div className="px-5 py-4 grid grid-cols-2 gap-4 max-h-[70vh] overflow-y-auto">
                <div className="col-span-2">
                  <label className="text-sm font-medium text-gray-700 block mb-1">Email</label>
                  <input type="email" value={customer.email} disabled
                    className="w-full border border-gray-100 rounded-lg px-3 py-2 text-sm bg-gray-50 text-gray-500 cursor-not-allowed" />
                  <p className="text-xs text-gray-400 mt-1">Email cannot be changed</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-700 block mb-1">First Name</label>
                  <input type="text" value={editForm.first_name}
                    onChange={e => setEditForm({ ...editForm, first_name: e.target.value })}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-700 block mb-1">Last Name</label>
                  <input type="text" value={editForm.last_name}
                    onChange={e => setEditForm({ ...editForm, last_name: e.target.value })}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                </div>
                <div className="col-span-2">
                  <label className="text-sm font-medium text-gray-700 block mb-1">Company</label>
                  <input type="text" value={editForm.company}
                    onChange={e => setEditForm({ ...editForm, company: e.target.value })}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                </div>
                <div className="col-span-2">
                  <label className="text-sm font-medium text-gray-700 block mb-1">Address</label>
                  <input type="text" value={editForm.address}
                    onChange={e => setEditForm({ ...editForm, address: e.target.value })}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-700 block mb-1">City</label>
                  <input type="text" value={editForm.city}
                    onChange={e => setEditForm({ ...editForm, city: e.target.value })}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-700 block mb-1">State / Province</label>
                  <input type="text" value={editForm.state}
                    onChange={e => setEditForm({ ...editForm, state: e.target.value })}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-700 block mb-1">ZIP Code</label>
                  <input type="text" value={editForm.zip}
                    onChange={e => setEditForm({ ...editForm, zip: e.target.value })}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-700 block mb-1">Country Code</label>
                  <input type="text" value={editForm.country_code}
                    onChange={e => setEditForm({ ...editForm, country_code: e.target.value })}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                </div>
                <div className="col-span-2">
                  <label className="text-sm font-medium text-gray-700 block mb-1">Tags</label>
                  <input type="text" value={editForm.tags}
                    onChange={e => setEditForm({ ...editForm, tags: e.target.value })}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                </div>
                <div className="col-span-2">
                  <label className="text-sm font-medium text-gray-700 block mb-1">Notes</label>
                  <textarea value={editForm.notes} rows={2}
                    onChange={e => setEditForm({ ...editForm, notes: e.target.value })}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none" />
                </div>
              </div>
              <div className="flex items-center justify-end gap-2 px-5 py-4 border-t border-gray-100 bg-gray-50">
                <button type="button" className="btn-secondary" onClick={() => setEditModal(false)}>Cancel</button>
                <button type="submit" className="btn-primary" disabled={saving}>
                  {saving ? 'Saving...' : 'Save to Shopify'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Create Order Modal */}
      {orderModal && (
        <CreateOrderModal
          customerId={id}
          customerName={fullName}
          customerEmail={customer.email}
          onClose={() => setOrderModal(false)}
          onSuccess={() => {
            setOrderModal(false);
            addToast('Order created on Shopify');
            loadCustomer();
          }}
        />
      )}

      <ToastContainer toasts={toasts} removeToast={removeToast} />
    </div>
  );
}
