// Return detail page — full return info, timeline, tracking, admin actions
import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft, CheckCircle, Truck, Package, XCircle, RotateCcw, X as XIcon, Ban, BarChart2,
} from 'lucide-react';
import api from '../api/client';
import clsx from 'clsx';
import { useToast, ToastContainer } from '../components/Toast';

const STATUS_COLORS = {
  requested: 'bg-yellow-100 text-yellow-700', approved: 'bg-blue-100 text-blue-700',
  shipped: 'bg-purple-100 text-purple-700', received: 'bg-orange-100 text-orange-700',
  resolved: 'bg-green-100 text-green-700', rejected: 'bg-red-100 text-red-700',
  cancelled: 'bg-gray-100 text-gray-600',
};
const TIMELINE_ICONS = {
  requested: RotateCcw, approved: CheckCircle, shipped: Truck,
  received: Package, resolved: CheckCircle, rejected: XCircle, cancelled: Ban,
};
const VALID_TRANSITIONS = {
  requested: ['approved', 'rejected'],
  approved: ['shipped', 'rejected', 'cancelled'],
  shipped: ['received', 'cancelled'],
  received: [], resolved: [], rejected: [], cancelled: [],
};

export default function ReturnDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [ret, setRet] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState('');
  const [statusNote, setStatusNote] = useState('');
  const [trackingNumber, setTrackingNumber] = useState('');
  const [courier, setCourier] = useState('');
  const [inventoryData, setInventoryData] = useState(null);   // null = not loaded
  const [inventoryLoading, setInventoryLoading] = useState(false);
  const { toasts, addToast, addConfirmToast, removeToast } = useToast();

  async function loadReturn() {
    setLoading(true);
    try {
      const res = await api.get(`/returns/${id}`);
      setRet(res.data);
    } catch { setRet(null); } finally { setLoading(false); }
  }
  useEffect(() => { loadReturn(); }, [id]);

  async function updateStatus(newStatus) {
    setActionLoading(newStatus);
    try {
      const res = await api.post(`/returns/${id}/status`, { status: newStatus, note: statusNote || undefined });
      setStatusNote('');
      if (newStatus === 'received' && res.data.resolution_result) {
        const rr = res.data.resolution_result;
        if (rr.error) addToast(`Received but resolution failed: ${rr.error}`, 'error');
        else addToast('Item received — resolution processed!');
      } else {
        addToast(`Status → ${newStatus}`);
      }
      await loadReturn();
    } catch (err) {
      addToast(err.response?.data?.detail || 'Failed', 'error');
    } finally { setActionLoading(''); }
  }

  async function addTracking() {
    if (!trackingNumber || !courier) { addToast('Enter tracking number and courier', 'error'); return; }
    setActionLoading('tracking');
    try {
      await api.post(`/returns/${id}/tracking`, { tracking_number: trackingNumber, courier });
      setTrackingNumber(''); setCourier('');
      addToast('Tracking added — status updated to shipped');
      await loadReturn();
    } catch (err) {
      addToast(err.response?.data?.detail || 'Failed', 'error');
    } finally { setActionLoading(''); }
  }

  async function cancelReturn() {
    addConfirmToast('Cancel this return request?', async () => {
      try {
        await api.post(`/returns/${id}/cancel`);
        addToast('Return cancelled');
        await loadReturn();
      } catch (err) {
        addToast(err.response?.data?.detail || 'Failed', 'error');
      }
    });
  }

  async function loadInventory() {
    setInventoryLoading(true);
    try {
      const res = await api.get(`/returns/${id}/inventory`);
      setInventoryData(res.data.items);
    } catch (err) {
      addToast(err.response?.data?.detail || 'Failed to fetch inventory', 'error');
    } finally { setInventoryLoading(false); }
  }

  function handleDelete() {
    addConfirmToast('Delete this return?', async () => {
      try {
        await api.delete(`/returns/${id}`);
        addToast('Deleted');
        setTimeout(() => navigate('/returns'), 500);
      } catch (err) {
        addToast(err.response?.data?.detail || 'Failed', 'error');
      }
    });
  }

  if (loading) return <div className="flex items-center justify-center min-h-[60vh]"><div className="w-8 h-8 border-4 border-gray-200 border-t-brand-600 rounded-full animate-spin" /></div>;
  if (!ret) return <div className="p-8 text-center text-gray-400">Return not found</div>;

  const nextStatuses = VALID_TRANSITIONS[ret.status] || [];
  const canCancel = ['requested', 'approved', 'shipped'].includes(ret.status);
  const needsTracking = ret.status === 'approved' && !ret.tracking_number;

  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <button onClick={() => navigate('/returns')} className="p-2 rounded-lg hover:bg-gray-100 text-gray-500"><ArrowLeft size={20} /></button>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-semibold text-gray-900">Return Request</h1>
            <span className={clsx('badge', STATUS_COLORS[ret.status])}>{ret.status}</span>
            <span className="badge bg-gray-100 text-gray-600 capitalize">{ret.resolution}</span>
          </div>
          <p className="text-sm text-gray-500 mt-0.5">Order #{ret.order_number} · {ret.customer_name || ret.customer_email}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          {/* Items */}
          <div className="card">
            <div className="px-5 py-3 border-b border-gray-100">
              <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">Returned Items</h2>
            </div>
            <div className="divide-y divide-gray-50">
              {ret.items?.map((item, i) => (
                <div key={i} className="flex items-center justify-between px-5 py-3">
                  <div><p className="text-sm font-medium text-gray-900">{item.title}</p>
                    {item.variant_title && <p className="text-xs text-gray-500">{item.variant_title}</p>}
                    {item.sku && <p className="text-xs text-gray-400">SKU: {item.sku}</p>}
                  </div>
                  <div className="text-right"><p className="text-sm">{item.quantity} x ${item.price}</p>
                    <p className="text-sm font-medium">${(item.quantity * parseFloat(item.price)).toFixed(2)}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Reason */}
          <div className="card p-5">
            <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-2">Reason</h2>
            <p className="text-sm text-gray-900 capitalize">{ret.reason?.replace(/_/g, ' ')}</p>
            {ret.reason_notes && <p className="text-sm text-gray-500 mt-1">{ret.reason_notes}</p>}
          </div>

          {/* Customer-submitted product images (from WhatsApp / chatbot) */}
          {ret.images && ret.images.length > 0 && (
            <div className="card p-5">
              <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-3">
                Product Images ({ret.images.length})
              </h2>
              <div className="grid grid-cols-3 gap-2">
                {ret.images.map((url, i) => (
                  <a key={i} href={url} target="_blank" rel="noreferrer"
                    className="block rounded-lg overflow-hidden border border-gray-200 hover:border-brand-400 transition-colors aspect-square bg-gray-50">
                    <img src={url} alt={`Return image ${i + 1}`}
                      className="w-full h-full object-cover"
                      onError={e => { e.target.style.display = 'none'; e.target.parentElement.classList.add('flex', 'items-center', 'justify-center'); e.target.parentElement.innerHTML = '<span class="text-xs text-gray-400">No preview</span>'; }}
                    />
                  </a>
                ))}
              </div>

              {/* Verify & decide — shown only when admin hasn't acted yet */}
              {ret.status === 'requested' && (
                <div className="mt-4 pt-4 border-t border-gray-100">
                  <p className="text-xs text-gray-500 mb-3">
                    Review the images above, then approve or reject this return.
                  </p>
                  <div className="flex gap-2">
                    <button
                      onClick={() => updateStatus('approved')}
                      disabled={!!actionLoading}
                      className="flex-1 flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-brand-600 text-white hover:bg-brand-700 transition-colors disabled:opacity-50"
                    >
                      <CheckCircle size={14} />
                      {actionLoading === 'approved' ? 'Approving...' : 'Approve Return'}
                    </button>
                    <button
                      onClick={() => updateStatus('rejected')}
                      disabled={!!actionLoading}
                      className="flex-1 flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-red-50 text-red-700 border border-red-200 hover:bg-red-100 transition-colors disabled:opacity-50"
                    >
                      <XIcon size={14} />
                      {actionLoading === 'rejected' ? 'Rejecting...' : 'Reject Return'}
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Tracking info */}
          {ret.tracking_number && (
            <div className="card p-5">
              <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-2">Shipment Tracking</h2>
              <div className="flex items-center gap-4 text-sm">
                <div><span className="text-gray-500">Courier:</span> <span className="font-medium">{ret.courier}</span></div>
                <div><span className="text-gray-500">Tracking #:</span> <span className="font-mono font-medium">{ret.tracking_number}</span></div>
                <span className="badge bg-purple-100 text-purple-700">{ret.tracking_status || 'pending'}</span>
              </div>
            </div>
          )}

          {/* Timeline */}
          <div className="card p-5">
            <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-4">Timeline</h2>
            <div className="space-y-4">
              {(ret.status_history || []).map((entry, i) => {
                const Icon = TIMELINE_ICONS[entry.status] || RotateCcw;
                const isLast = i === ret.status_history.length - 1;
                return (
                  <div key={i} className="flex gap-3">
                    <div className="flex flex-col items-center">
                      <div className={clsx('w-8 h-8 rounded-full flex items-center justify-center', isLast ? 'bg-brand-100 text-brand-700' : 'bg-gray-100 text-gray-500')}>
                        <Icon size={14} />
                      </div>
                      {i < ret.status_history.length - 1 && <div className="w-px h-full bg-gray-200 my-1" />}
                    </div>
                    <div className="flex-1 pb-4">
                      <div className="flex items-center gap-2">
                        <span className={clsx('badge text-xs', STATUS_COLORS[entry.status])}>{entry.status}</span>
                        <span className="text-xs text-gray-400">{entry.actor_type}{entry.actor_name ? ` (${entry.actor_name})` : ''}</span>
                      </div>
                      {entry.note && <p className="text-sm text-gray-600 mt-1">{entry.note}</p>}
                      <p className="text-xs text-gray-400 mt-0.5">{entry.timestamp ? new Date(entry.timestamp).toLocaleString() : ''}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Resolution result */}
          {ret.status === 'resolved' && (
            <div className="card p-5 bg-green-50 border-green-200">
              <h2 className="text-sm font-semibold text-green-800 uppercase tracking-wide mb-2">Resolution Complete</h2>
              {ret.resolution === 'refund' && ret.refund_id && <p className="text-sm text-green-700">Refund ID: {ret.refund_id}</p>}
              {ret.resolution === 'replacement' && ret.replacement_order_id && (
                <div>
                  <p className="text-sm text-green-700">Replacement order created (zero charge).</p>
                  <button onClick={() => navigate(`/orders/${ret.replacement_order_id}`)} className="text-sm text-brand-600 hover:underline mt-1">View replacement order →</button>
                </div>
              )}
            </div>
          )}
          {/* Inventory check — shown after item is received/resolved */}
          {['received', 'resolved'].includes(ret.status) && (
            <div className="card p-5">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">Shopify Inventory Status</h2>
                <button onClick={loadInventory} disabled={inventoryLoading}
                  className="flex items-center gap-1.5 text-xs text-brand-600 hover:text-brand-700 font-medium disabled:opacity-50">
                  <BarChart2 size={13} />
                  {inventoryLoading ? 'Checking...' : inventoryData ? 'Refresh' : 'Check Inventory'}
                </button>
              </div>
              {inventoryData === null ? (
                <p className="text-xs text-gray-400">Click "Check Inventory" to verify restocking in Shopify.</p>
              ) : (
                <div className="space-y-2">
                  {inventoryData.map((item, i) => (
                    <div key={i} className="flex items-center justify-between text-sm py-2 border-b border-gray-50 last:border-0">
                      <div>
                        <p className="font-medium text-gray-900">{item.title}</p>
                        {item.variant_title && <p className="text-xs text-gray-500">{item.variant_title}</p>}
                        {item.sku && <p className="text-xs text-gray-400">SKU: {item.sku}</p>}
                      </div>
                      <div className="text-right shrink-0 ml-4">
                        {item.error ? (
                          <span className="text-xs text-red-500">{item.error}</span>
                        ) : (
                          <>
                            <span className={clsx(
                              'font-semibold text-base',
                              item.inventory_quantity > 0 ? 'text-green-600' : 'text-red-500'
                            )}>
                              {item.inventory_quantity ?? '—'}
                            </span>
                            <p className="text-xs text-gray-400">in stock</p>
                            {!item.inventory_policy && (
                              <p className="text-xs text-gray-300">untracked</p>
                            )}
                          </>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Right sidebar */}
        <div className="space-y-4">
          {/* Tracking input (shown after approval, before tracking is added) */}
          {needsTracking && (
            <div className="card p-4 space-y-3">
              <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">Add Return Tracking</h2>
              <div>
                <label className="text-xs text-gray-500 block mb-1">Courier</label>
                <select value={courier} onChange={e => setCourier(e.target.value)}
                  className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500">
                  <option value="">Select courier...</option>
                  {['FedEx', 'UPS', 'USPS', 'DHL', 'BlueDart', 'DTDC', 'Delhivery', 'India Post', 'Other'].map(c =>
                    <option key={c} value={c}>{c}</option>
                  )}
                </select>
              </div>
              <div>
                <label className="text-xs text-gray-500 block mb-1">Tracking Number</label>
                <input type="text" value={trackingNumber} onChange={e => setTrackingNumber(e.target.value)}
                  className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
              </div>
              <button onClick={addTracking} disabled={!!actionLoading}
                className="btn-primary w-full text-sm flex items-center justify-center gap-2">
                <Truck size={14} /> {actionLoading === 'tracking' ? 'Adding...' : 'Add Tracking & Mark Shipped'}
              </button>
            </div>
          )}

          {/* Status actions */}
          {nextStatuses.length > 0 && (
            <div className="card p-4 space-y-3">
              <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">Actions</h2>
              <div>
                <label className="text-xs text-gray-500 block mb-1">Note (optional)</label>
                <input type="text" value={statusNote} onChange={e => setStatusNote(e.target.value)}
                  placeholder="Add a note..."
                  className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
              </div>
              <div className="space-y-2">
                {nextStatuses.filter(s => s !== 'cancelled').map(ns => (
                  <button key={ns} onClick={() => updateStatus(ns)} disabled={!!actionLoading}
                    className={clsx('w-full flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50',
                      ns === 'rejected' ? 'bg-red-50 text-red-700 border border-red-200 hover:bg-red-100'
                        : ns === 'received' ? 'bg-brand-600 text-white hover:bg-brand-700'
                        : 'bg-white text-gray-700 border border-gray-200 hover:bg-gray-50')}>
                    {actionLoading === ns ? 'Processing...' :
                      ns === 'approved' ? 'Approve Return' :
                      ns === 'rejected' ? 'Reject Return' :
                      ns === 'shipped' ? 'Mark as Shipped' :
                      ns === 'received' ? 'Mark as Received at Warehouse' : ns}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Cancel return */}
          {canCancel && (
            <button onClick={cancelReturn} disabled={!!actionLoading}
              className="btn-secondary w-full text-sm text-red-600 border-red-200 hover:bg-red-50 flex items-center justify-center gap-2">
              <Ban size={14} /> Cancel Return
            </button>
          )}

          {/* Info */}
          <div className="card p-4 space-y-2 text-sm">
            <h2 className="text-xs font-semibold text-gray-700 uppercase tracking-wide mb-2">Details</h2>
            <div className="flex justify-between"><span className="text-gray-500">Customer</span><span>{ret.customer_name || '—'}</span></div>
            <div className="flex justify-between"><span className="text-gray-500">Email</span><span className="text-blue-600 text-xs">{ret.customer_email}</span></div>
            <div className="flex justify-between"><span className="text-gray-500">Order</span>
              <button onClick={() => navigate(`/orders/${ret.order_id}`)} className="text-brand-600 hover:underline text-xs">#{ret.order_number}</button>
            </div>
            <div className="flex justify-between"><span className="text-gray-500">Resolution</span><span className="capitalize">{ret.resolution}</span></div>
            <div className="flex justify-between"><span className="text-gray-500">Initiated by</span><span className="capitalize">{ret.initiated_by}</span></div>
            <div className="flex justify-between"><span className="text-gray-500">Created</span><span className="text-xs">{ret.created_at ? new Date(ret.created_at).toLocaleString() : '—'}</span></div>
            {ret.return_tag && <div className="flex justify-between"><span className="text-gray-500">Shopify Tag</span><span className="badge bg-gray-100 text-gray-600">{ret.return_tag}</span></div>}
            <div className="text-xs text-gray-400 pt-2 border-t border-gray-100">ID: {ret.id}</div>
          </div>

          {ret.status !== 'resolved' && (
            <button onClick={handleDelete} className="btn-secondary w-full text-sm text-gray-500 hover:text-red-600">Delete Return</button>
          )}
        </div>
      </div>

      <ToastContainer toasts={toasts} removeToast={removeToast} />
    </div>
  );
}
