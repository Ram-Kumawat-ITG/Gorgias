// Order detail page — full order info + all action buttons for draft and regular orders
import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import {
  ArrowLeft, Truck, Ban, DollarSign, RefreshCw, Send, Trash2, RotateCcw,
  CheckCircle, X, Package, CreditCard, FileText, Pencil, Search, Plus, Save, XCircle,
} from 'lucide-react';
import api from '../api/client';
import clsx from 'clsx';
import { useToast, ToastContainer } from '../components/Toast';
import InitiateReturnModal from '../components/InitiateReturnModal';

const FIN = {
  paid: 'bg-green-100 text-green-700', pending: 'bg-yellow-100 text-yellow-700',
  refunded: 'bg-red-100 text-red-700', partially_refunded: 'bg-orange-100 text-orange-700',
  voided: 'bg-gray-100 text-gray-600', authorized: 'bg-blue-100 text-blue-700',
};
const DRAFT_STATUS = {
  open: 'bg-yellow-100 text-yellow-700', invoice_sent: 'bg-blue-100 text-blue-700',
  completed: 'bg-green-100 text-green-700',
};

export default function OrderDetailPage() {
  const { id } = useParams();
  const [searchParams] = useSearchParams();
  const isDraft = searchParams.get('type') === 'draft';
  const navigate = useNavigate();
  const [order, setOrder] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState('');
  const [customer, setCustomer] = useState(null);
  const [customerLoading, setCustomerLoading] = useState(false);
  const { toasts, addToast, addConfirmToast, removeToast } = useToast();

  const [hasReturn, setHasReturn] = useState(false);

  // Modal states
  const [cancelModal, setCancelModal] = useState(false);
  const [refundModal, setRefundModal] = useState(false);
  const [fulfillModal, setFulfillModal] = useState(false);
  const [invoiceModal, setInvoiceModal] = useState(false);
  const [returnModal, setReturnModal] = useState(false);

  // Cancel form
  const [cancelReason, setCancelReason] = useState('other');
  const [cancelRestock, setCancelRestock] = useState(true);

  // Refund form
  const [refundItems, setRefundItems] = useState([]);
  const [refundShipping, setRefundShipping] = useState(false);
  const [refundNote, setRefundNote] = useState('');

  // Fulfill form
  const [trackingNumber, setTrackingNumber] = useState('');
  const [trackingUrl, setTrackingUrl] = useState('');
  const [trackingCompany, setTrackingCompany] = useState('');

  // Invoice form
  const [invoiceTo, setInvoiceTo] = useState('');
  const [invoiceMessage, setInvoiceMessage] = useState('');

  // ── Edit mode state ──
  const [editMode, setEditMode] = useState(false);
  const [editItems, setEditItems] = useState([]);
  const [editNote, setEditNote] = useState('');
  const [editTags, setEditTags] = useState('');
  const [editSaving, setEditSaving] = useState(false);
  const [productSearch, setProductSearch] = useState('');
  const [productResults, setProductResults] = useState([]);
  const [productLoading, setProductLoading] = useState(false);
  const [showProductDropdown, setShowProductDropdown] = useState(false);
  const productSearchRef = useRef(null);

  async function loadOrder() {
    setLoading(true);
    try {
      const endpoint = isDraft ? `/orders/drafts/${id}` : `/orders/${id}`;
      const res = await api.get(endpoint);
      setOrder(res.data);
      // Pre-fill refund items
      if (res.data.line_items && res.data.line_items.length > 0) {
        setRefundItems(res.data.line_items.map(li => ({ line_item_id: li.id, quantity: 0, max: li.quantity })));
      } else {
        setRefundItems([]);
      }
      if (res.data.email) setInvoiceTo(res.data.email);
    } catch {
      setOrder(null);
    } finally { setLoading(false); }
  }

  useEffect(() => { loadOrder(); }, [id, isDraft]);

  // Check if a return request exists for this order (regular orders only)
  useEffect(() => {
    if (!id || isDraft) return;
    api.get(`/returns/order/${id}`)
      .then(res => setHasReturn((res.data || []).length > 0))
      .catch(() => setHasReturn(false));
  }, [id, isDraft]);

  // Fetch full customer profile once order is loaded and customer_id is known
  useEffect(() => {
    if (!order?.customer_id) { setCustomer(null); return; }
    setCustomerLoading(true);
    api.get(`/customers/${order.customer_id}`)
      .then(res => setCustomer(res.data))
      .catch(() => setCustomer(null))
      .finally(() => setCustomerLoading(false));
  }, [order?.customer_id]);

  async function doAction(label, fn) {
    setActionLoading(label);
    try {
      await fn();
      addToast(`${label} successful`);
      await loadOrder();
    } catch (err) {
      addToast(err.response?.data?.detail || `${label} failed`, 'error');
    } finally { setActionLoading(''); }
  }

  // ── Actions ──
  const handleCancel = () => doAction('Cancel order', async () => {
    await api.post(`/orders/${id}/cancel`, { reason: cancelReason, restock: cancelRestock });
    setCancelModal(false);
  });

  const handleRefund = () => doAction('Refund', async () => {
    const items = refundItems.filter(i => i.quantity > 0);
    await api.post(`/orders/${id}/refund`, {
      line_items: items.map(i => ({ line_item_id: i.line_item_id, quantity: i.quantity, restock: true })),
      shipping_full_refund: refundShipping, note: refundNote || undefined,
    });
    setRefundModal(false);
  });

  const handleFulfill = () => doAction('Fulfillment', async () => {
    await api.post(`/orders/${id}/fulfill`, {
      tracking_number: trackingNumber || undefined,
      tracking_url: trackingUrl || undefined,
      tracking_company: trackingCompany || undefined,
    });
    setFulfillModal(false);
  });

  const handleMarkPaid = () => doAction('Mark as paid', () => api.post(`/orders/${id}/mark-paid`));

  const handleComplete = () => doAction('Complete draft', async () => {
    await api.post(`/orders/drafts/${id}/complete`);
  });

  const handleDeleteDraft = () => {
    addConfirmToast('Permanently delete this draft order?', async () => {
      await doAction('Delete draft', async () => {
        await api.delete(`/orders/drafts/${id}`);
        setTimeout(() => navigate('/orders'), 400);
      });
    });
  };

  const handleSendInvoice = () => doAction('Send invoice', async () => {
    await api.post(`/orders/drafts/${id}/send-invoice`, {
      to: invoiceTo || undefined, custom_message: invoiceMessage || undefined,
    });
    setInvoiceModal(false);
  });

  const handleCancelFulfillment = (fId) => doAction('Cancel fulfillment', () =>
    api.post(`/orders/fulfillments/${fId}/cancel`)
  );

  // ── Edit mode handlers ──
  function enterEditMode() {
    setEditItems(order.line_items.map(li => ({
      id: li.id, title: li.title, variant_title: li.variant_title,
      quantity: li.quantity, price: li.price,
      variant_id: li.variant_id, sku: li.sku, isNew: false,
    })));
    setEditNote(order.note || '');
    setEditTags(order.tags || '');
    setEditMode(true);
  }

  function discardEdit() {
    setEditMode(false);
    setEditItems([]);
    setProductSearch('');
    setShowProductDropdown(false);
  }

  function editUpdateQty(idx, qty) {
    setEditItems(items => items.map((it, i) => i === idx ? { ...it, quantity: Math.max(1, Number(qty)) } : it));
  }

  function editRemoveItem(idx) {
    setEditItems(items => items.filter((_, i) => i !== idx));
  }

  function editAddProduct(product) {
    const existing = editItems.findIndex(i => i.variant_id === product.variant_id);
    if (existing >= 0) {
      editUpdateQty(existing, editItems[existing].quantity + 1);
    } else {
      setEditItems(prev => [...prev, {
        id: null, title: product.title, variant_title: '',
        quantity: 1, price: product.price,
        variant_id: product.variant_id, sku: product.sku || '', isNew: true,
        image: product.image,
      }]);
    }
    setProductSearch('');
    setShowProductDropdown(false);
  }

  // Product search with debounce
  useEffect(() => {
    if (!editMode) return;
    const timer = setTimeout(async () => {
      setProductLoading(true);
      try {
        const res = await api.get('/orders/products/search', { params: { q: productSearch, limit: 20 } });
        setProductResults(res.data.products || []);
      } catch {} finally { setProductLoading(false); }
    }, 300);
    return () => clearTimeout(timer);
  }, [productSearch, editMode]);

  // Close product dropdown on outside click
  useEffect(() => {
    if (!editMode) return;
    function handle(e) {
      if (productSearchRef.current && !productSearchRef.current.contains(e.target)) setShowProductDropdown(false);
    }
    document.addEventListener('mousedown', handle);
    return () => document.removeEventListener('mousedown', handle);
  }, [editMode]);

  function lineItemsChanged() {
    if (!order.line_items) return editItems.length > 0;
    if (editItems.length !== order.line_items.length) return true;
    for (let i = 0; i < editItems.length; i++) {
      const e = editItems[i];
      const o = order.line_items[i];
      if (e.isNew) return true;
      if (e.variant_id !== o.variant_id) return true;
      if (e.quantity !== o.quantity) return true;
    }
    return false;
  }

  async function saveEdit() {
    if (editItems.length === 0) { addToast('Order must have at least one item', 'error'); return; }
    setEditSaving(true);
    try {
      const itemsPayload = editItems.map(li => ({
        title: li.title, quantity: li.quantity, price: li.price,
        variant_id: li.variant_id || undefined,
      }));

      if (isDraft) {
        // Draft: single PUT replaces everything
        await api.put(`/orders/drafts/${id}/edit`, {
          line_items: itemsPayload,
          note: editNote || undefined,
          tags: editTags || undefined,
        });
        setEditMode(false);
        addToast('Draft order updated');
        await loadOrder();
      } else {
        // Regular order
        const hasLineChanges = lineItemsChanged();
        if (hasLineChanges) {
          // Line items changed — backend will create a replacement order
          const res = await api.post(`/orders/${id}/edit/commit`, {
            note: editNote || undefined,
            tags: editTags || undefined,
            line_items: itemsPayload,
            customer_id: order.customer_id || undefined,
          });
          setEditMode(false);
          const newId = res.data?.id;
          const msg = res.data?.message || 'Order replaced with updated version';
          addToast(msg);
          if (newId && newId !== id) {
            // Navigate to the new replacement order
            navigate(`/orders/${newId}`, { replace: true });
          } else {
            await loadOrder();
          }
        } else {
          // Only note/tags changed
          await api.post(`/orders/${id}/edit/commit`, {
            note: editNote || undefined,
            tags: editTags || undefined,
          });
          setEditMode(false);
          addToast('Changes saved');
          await loadOrder();
        }
      }
    } catch (err) {
      addToast(err.response?.data?.detail || 'Failed to save changes', 'error');
    } finally { setEditSaving(false); }
  }

  if (loading) return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <div className="w-8 h-8 border-4 border-gray-200 border-t-brand-600 rounded-full animate-spin" />
    </div>
  );
  if (!order) return <div className="p-8 text-center text-gray-400">Order not found</div>;

  const isOrder = order.type === 'order';
  const isPaid = order.financial_status === 'paid';
  const isCancelled = !!order.cancelled_at;
  const isFulfilled = order.fulfillment_status === 'fulfilled';
  const isRefunded = order.financial_status === 'refunded';
  // Shipped = any fulfillment exists (partial or full) — cancel is blocked once shipped
  const isShipped = isFulfilled || order.fulfillment_status === 'partial';
  const isDraftOpen = !isOrder && order.status === 'open';
  const isDraftInvoiced = !isOrder && order.status === 'invoice_sent';
  const isDraftCompleted = !isOrder && order.status === 'completed';
  // Draft: editable only when open or invoice_sent (NOT completed)
  // Regular: note/tags always editable if not cancelled; line items only if unpaid+unfulfilled
  const canEdit = isDraft
    ? (isDraftOpen || isDraftInvoiced)
    : (isOrder && !isCancelled);
  const canEditLineItems = isDraft
    ? (isDraftOpen || isDraftInvoiced)
    : (isOrder && !isCancelled && !isFulfilled);

  return (
    <div>
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <button onClick={() => navigate('/orders')} className="p-2 rounded-lg hover:bg-gray-100 text-gray-500">
          <ArrowLeft size={20} />
        </button>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-semibold text-gray-900">{order.name || `#${order.order_number || order.id}`}</h1>
            {isOrder ? (
              <>
                <span className={clsx('badge', FIN[order.financial_status] || 'bg-gray-100 text-gray-600')}>
                  {order.financial_status}
                </span>
                <span className={clsx('badge', {
                  'bg-green-100 text-green-700': isFulfilled,
                  'bg-yellow-100 text-yellow-700': order.fulfillment_status === 'partial',
                  'bg-gray-100 text-gray-600': !order.fulfillment_status,
                })}>
                  {order.fulfillment_status || 'unfulfilled'}
                </span>
                {isCancelled && <span className="badge bg-red-100 text-red-700">Cancelled</span>}
              </>
            ) : (
              <>
                <span className="badge bg-purple-100 text-purple-700">Draft</span>
                <span className={clsx('badge', DRAFT_STATUS[order.status] || 'bg-gray-100 text-gray-600')}>
                  {order.status}
                </span>
              </>
            )}
          </div>
          <p className="text-sm text-gray-500 mt-0.5">{order.email} · {order.customer_name}</p>
        </div>
        {canEdit && !editMode && (
          <button onClick={enterEditMode} className="btn-secondary flex items-center gap-2 shrink-0">
            <Pencil size={15} /> Edit Order
          </button>
        )}
        {editMode && (
          <div className="flex items-center gap-2 shrink-0">
            <button onClick={discardEdit} disabled={editSaving}
              className="btn-secondary flex items-center gap-2 text-sm">
              <XCircle size={15} /> Discard
            </button>
            <button onClick={saveEdit} disabled={editSaving}
              className="btn-primary flex items-center gap-2 text-sm">
              <Save size={15} /> {editSaving ? 'Saving...' : isDraft ? 'Save Changes' : 'Commit Changes'}
            </button>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* ── Left: Order details ── */}
        <div className="lg:col-span-2 space-y-6">
          {/* Line items — VIEW or EDIT mode */}
          <div className="card">
            <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">Line Items</h2>
              {editMode && <span className="badge bg-yellow-100 text-yellow-700">Editing</span>}
            </div>

            {editMode ? (
              /* ═══ EDIT MODE ═══ */
              <div>
                {/* Warning for regular orders */}
                {isOrder && canEditLineItems && (
                  <div className="mx-5 mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg text-xs text-yellow-800">
                    <strong>Note:</strong> Shopify does not allow editing line items on confirmed orders.
                    If you add, remove, or change quantities, a <strong>new replacement order</strong> will
                    be created and this order will be cancelled. Note and tags can be updated directly.
                  </div>
                )}
                {isOrder && !canEditLineItems && (
                  <div className="mx-5 mt-4 p-3 bg-gray-50 border border-gray-200 rounded-lg text-xs text-gray-600">
                    <strong>Line items are locked.</strong> This order is {isFulfilled ? 'fulfilled' : 'in a state'} where
                    line items cannot be changed. You can still edit notes and tags below.
                  </div>
                )}
                {/* Product search to add items (only if line items editable) */}
                {canEditLineItems && <div className="px-5 pt-4 pb-2" ref={productSearchRef}>
                  <div className="relative">
                    <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                    <input type="text" value={productSearch}
                      onChange={e => setProductSearch(e.target.value)}
                      onFocus={() => setShowProductDropdown(true)}
                      placeholder="Search products to add..."
                      className="w-full pl-9 pr-4 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                    {showProductDropdown && (
                      <div className="absolute left-0 right-0 top-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-20 max-h-52 overflow-y-auto">
                        {productLoading ? (
                          <p className="px-4 py-3 text-sm text-gray-400">Searching...</p>
                        ) : productResults.length === 0 ? (
                          <p className="px-4 py-3 text-sm text-gray-400">No products found</p>
                        ) : productResults.map(p => (
                          <button key={p.variant_id} onClick={() => editAddProduct(p)}
                            className="w-full text-left flex items-center gap-3 px-4 py-2 hover:bg-gray-50 border-b border-gray-50 last:border-0">
                            <div className="w-8 h-8 rounded bg-gray-100 shrink-0 overflow-hidden">
                              {p.image ? <img src={p.image} alt="" className="w-full h-full object-cover" />
                                : <div className="w-full h-full flex items-center justify-center text-gray-300 text-[10px]">N/A</div>}
                            </div>
                            <div className="flex-1 min-w-0">
                              <p className="text-sm font-medium text-gray-900 truncate">{p.title}</p>
                              <p className="text-xs text-gray-500">${p.price} · {p.inventory_quantity > 0 ? `${p.inventory_quantity} in stock` : 'Out of stock'}</p>
                            </div>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </div>}

                {/* Editable line items */}
                <div className="divide-y divide-gray-50">
                  {editItems.length === 0 ? (
                    <p className="px-5 py-6 text-sm text-gray-400 text-center">No items — search above to add products</p>
                  ) : editItems.map((li, idx) => (
                    <div key={li.variant_id || idx} className="flex items-center gap-3 px-5 py-3">
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-900">{li.title}</p>
                        {li.variant_title && <p className="text-xs text-gray-500">{li.variant_title}</p>}
                        {li.isNew && <span className="badge bg-blue-100 text-blue-700 text-xs mt-0.5">New</span>}
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <span className="text-xs text-gray-400">Qty:</span>
                        {canEditLineItems ? (
                          <input type="number" min="1" value={li.quantity}
                            onChange={e => editUpdateQty(idx, e.target.value)}
                            className="w-16 border border-gray-200 rounded px-2 py-1 text-sm text-center focus:outline-none focus:ring-1 focus:ring-brand-500" />
                        ) : (
                          <span className="text-sm text-gray-700 w-16 text-center">{li.quantity}</span>
                        )}
                        <span className="text-sm text-gray-500">x ${li.price}</span>
                        <span className="text-sm font-medium text-gray-900 w-20 text-right">
                          ${(li.quantity * parseFloat(li.price)).toFixed(2)}
                        </span>
                        {canEditLineItems && (
                          <button onClick={() => editRemoveItem(idx)}
                            className="p-1 text-gray-300 hover:text-red-500 transition-colors">
                            <Trash2 size={14} />
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>

                {/* Edit note + tags */}
                <div className="px-5 py-4 border-t border-gray-100 space-y-3">
                  <div>
                    <label className="text-xs font-medium text-gray-600 block mb-1">Note</label>
                    <textarea value={editNote} onChange={e => setEditNote(e.target.value)} rows={2}
                      className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none" />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-gray-600 block mb-1">Tags</label>
                    <input type="text" value={editTags} onChange={e => setEditTags(e.target.value)}
                      className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                  </div>
                </div>

                {/* Edit subtotal */}
                <div className="px-5 py-3 border-t border-gray-100">
                  <div className="flex justify-between text-sm font-semibold text-gray-900">
                    <span>Subtotal</span>
                    <span>${editItems.reduce((s, i) => s + i.quantity * parseFloat(i.price), 0).toFixed(2)}</span>
                  </div>
                </div>
              </div>
            ) : (
              /* ═══ VIEW MODE (original) ═══ */
              <>
                <div className="divide-y divide-gray-50">
                  {order.line_items?.map(li => (
                    <div key={li.id} className="flex items-center gap-4 px-5 py-3">
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-900">{li.title}</p>
                        {li.variant_title && <p className="text-xs text-gray-500">{li.variant_title}</p>}
                        {li.sku && <p className="text-xs text-gray-400">SKU: {li.sku}</p>}
                      </div>
                      <div className="text-right shrink-0">
                        <p className="text-sm text-gray-900">{li.quantity} x ${li.price}</p>
                        <p className="text-sm font-medium text-gray-900">${(li.quantity * parseFloat(li.price)).toFixed(2)}</p>
                      </div>
                      {isOrder && li.fulfillment_status && (
                        <span className={clsx('badge text-xs', li.fulfillment_status === 'fulfilled' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600')}>
                          {li.fulfillment_status}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
                <div className="px-5 py-3 border-t border-gray-100 space-y-1 text-sm">
                  {order.subtotal_price && (
                    <div className="flex justify-between"><span className="text-gray-500">Subtotal</span><span>${order.subtotal_price}</span></div>
                  )}
                  {order.total_tax && order.total_tax !== '0.00' && (
                    <div className="flex justify-between"><span className="text-gray-500">Tax</span><span>${order.total_tax}</span></div>
                  )}
                  {order.total_discounts && order.total_discounts !== '0.00' && (
                    <div className="flex justify-between"><span className="text-gray-500">Discount</span><span className="text-red-600">-${order.total_discounts}</span></div>
                  )}
                  <div className="flex justify-between font-semibold text-gray-900 pt-1 border-t border-gray-100">
                    <span>Total</span><span>${order.total_price} {order.currency}</span>
                  </div>
                </div>
              </>
            )}
          </div>

          {/* Fulfillments (regular orders only) */}
          {isOrder && order.fulfillments?.length > 0 && (
            <div className="card">
              <div className="px-5 py-3 border-b border-gray-100">
                <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">Fulfillments</h2>
              </div>
              {order.fulfillments.map(f => (
                <div key={f.id} className="px-5 py-3 border-b border-gray-50 last:border-0">
                  <div className="flex items-center justify-between">
                    <div>
                      <span className={clsx('badge text-xs', f.status === 'success' ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700')}>
                        {f.status}
                      </span>
                      {f.tracking_number && <span className="text-xs text-gray-500 ml-2">#{f.tracking_number}</span>}
                      {f.tracking_company && <span className="text-xs text-gray-400 ml-1">({f.tracking_company})</span>}
                    </div>
                    <div className="flex items-center gap-2">
                      {f.tracking_url && (
                        <a href={f.tracking_url} target="_blank" rel="noopener noreferrer" className="text-xs text-brand-600 hover:underline">Track</a>
                      )}
                      {f.status === 'success' && (
                        <button onClick={() => handleCancelFulfillment(f.id)}
                          className="text-xs text-red-500 hover:underline" disabled={!!actionLoading}>Cancel</button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Refunds */}
          {isOrder && order.refunds?.length > 0 && (
            <div className="card">
              <div className="px-5 py-3 border-b border-gray-100">
                <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">Refunds</h2>
              </div>
              {order.refunds.map(r => (
                <div key={r.id} className="px-5 py-3 border-b border-gray-50 last:border-0 text-sm">
                  <p className="text-gray-700">{r.note || 'Refund processed'}</p>
                  <p className="text-xs text-gray-400">{r.created_at ? new Date(r.created_at).toLocaleString() : ''}</p>
                </div>
              ))}
            </div>
          )}

          {/* Notes */}
          {order.note && (
            <div className="card p-5">
              <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-2">Notes</h2>
              <p className="text-sm text-gray-700">{order.note}</p>
            </div>
          )}
        </div>

        {/* ── Right: Sidebar ── */}
        <div className="space-y-4">
          {/* Actions */}
          <div className="card p-4 space-y-2">
            <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-2">Actions</h2>

            {/* Draft order actions */}
            {!isOrder && (isDraftOpen || isDraftInvoiced) && (
              <>
                <button onClick={handleComplete} disabled={!!actionLoading}
                  className="btn-primary w-full flex items-center justify-center gap-2 text-sm">
                  <CheckCircle size={15} /> Complete Draft Order
                </button>
                <button onClick={() => setInvoiceModal(true)} disabled={!!actionLoading}
                  className="btn-secondary w-full flex items-center justify-center gap-2 text-sm">
                  <Send size={15} /> Send Invoice
                </button>
                <button onClick={handleDeleteDraft} disabled={!!actionLoading}
                  className="btn-secondary w-full flex items-center justify-center gap-2 text-sm text-red-600 border-red-200 hover:bg-red-50">
                  <Trash2 size={15} /> Delete Draft
                </button>
              </>
            )}
            {!isOrder && isDraftCompleted && (
              <p className="text-sm text-green-600 text-center py-2">This draft has been completed into an order.</p>
            )}

            {/* Regular order actions */}
            {isOrder && !isCancelled && (
              <>
                {!isFulfilled && !isRefunded && (
                  <button onClick={() => setFulfillModal(true)} disabled={!!actionLoading}
                    className="btn-primary w-full flex items-center justify-center gap-2 text-sm">
                    <Truck size={15} /> Fulfill Items
                  </button>
                )}
                {!isPaid && !isRefunded && (
                  <button onClick={handleMarkPaid} disabled={!!actionLoading}
                    className="btn-secondary w-full flex items-center justify-center gap-2 text-sm">
                    <CreditCard size={15} /> Mark as Paid
                  </button>
                )}

                {/* Refund — only after a return has been initiated */}
                {isPaid && !isRefunded && isFulfilled && hasReturn && (
                  <button onClick={() => setRefundModal(true)} disabled={!!actionLoading}
                    className="btn-secondary w-full flex items-center justify-center gap-2 text-sm">
                    <DollarSign size={15} /> Refund
                  </button>
                )}
                {isPaid && !isRefunded && isFulfilled && !hasReturn && (
                  <p className="text-xs text-gray-400 text-center py-1">Refund available after a return is initiated</p>
                )}

                {/* Cancel — only before any item has shipped */}
                {!isShipped ? (
                  <button onClick={() => setCancelModal(true)} disabled={!!actionLoading}
                    className="btn-secondary w-full flex items-center justify-center gap-2 text-sm text-red-600 border-red-200 hover:bg-red-50">
                    <Ban size={15} /> Cancel Order
                  </button>
                ) : (
                  <p className="text-xs text-gray-400 text-center py-1">Cannot cancel — order has already shipped. Initiate a return instead.</p>
                )}

                {/* Return — only after order is fully delivered */}
                {isPaid && isFulfilled && (
                  <button onClick={() => setReturnModal(true)} disabled={!!actionLoading}
                    className="btn-secondary w-full flex items-center justify-center gap-2 text-sm">
                    <RotateCcw size={15} /> Initiate Return
                  </button>
                )}
              </>
            )}
            {isOrder && isCancelled && (
              <>
                <p className="text-sm text-red-500 text-center py-2">Order cancelled{order.cancel_reason ? `: ${order.cancel_reason}` : ''}</p>
                {/* Refund still available after cancellation if order was paid */}
                {isPaid && !isRefunded && (
                  <button onClick={() => setRefundModal(true)} disabled={!!actionLoading}
                    className="btn-secondary w-full flex items-center justify-center gap-2 text-sm">
                    <DollarSign size={15} /> Refund
                  </button>
                )}
              </>
            )}

            {actionLoading && <p className="text-xs text-gray-400 text-center animate-pulse">{actionLoading}...</p>}
          </div>

          {/* Customer info */}
          <div className="card p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">Customer</h2>
              {order.customer_id && (
                <button onClick={() => navigate(`/customers/${order.customer_id}`)}
                  className="text-xs text-brand-600 hover:underline">
                  View profile →
                </button>
              )}
            </div>

            {/* Name + email — always from order */}
            <div className="flex items-center gap-2 mb-3">
              <div className="w-8 h-8 rounded-full bg-brand-100 text-brand-700 flex items-center justify-center text-sm font-semibold shrink-0">
                {(order.customer_name || order.email || '?')[0].toUpperCase()}
              </div>
              <div className="min-w-0">
                <p className="text-sm font-semibold text-gray-900 truncate">{order.customer_name || '—'}</p>
                <p className="text-xs text-blue-600 truncate">{order.email}</p>
              </div>
            </div>

            {customerLoading && (
              <div className="flex items-center gap-2 text-xs text-gray-400 py-1">
                <div className="w-3 h-3 border-2 border-gray-200 border-t-gray-400 rounded-full animate-spin" />
                Loading customer data…
              </div>
            )}

            {customer && !customerLoading && (() => {
              const c = customer.customer;
              const orders = customer.orders || [];
              const stats = customer.ticket_stats || {};
              return (
                <div className="space-y-2 border-t border-gray-100 pt-3">
                  {/* Key stats */}
                  <div className="grid grid-cols-2 gap-2">
                    <div className="bg-gray-50 rounded-lg px-3 py-2 text-center">
                      <p className="text-sm font-bold text-gray-900">{c?.orders_count ?? '—'}</p>
                      <p className="text-xs text-gray-400">Orders</p>
                    </div>
                    <div className="bg-gray-50 rounded-lg px-3 py-2 text-center">
                      <p className="text-sm font-bold text-gray-900">${c?.total_spent ?? '—'}</p>
                      <p className="text-xs text-gray-400">Spent</p>
                    </div>
                  </div>

                  {/* Location */}
                  {(c?.city || c?.country_code) && (
                    <div className="flex items-center gap-1.5 text-xs text-gray-500">
                      <svg className="w-3 h-3 shrink-0 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                      </svg>
                      {[c.city, c.country_code].filter(Boolean).join(', ')}
                    </div>
                  )}

                  {/* Company */}
                  {c?.company && (
                    <div className="flex items-center gap-1.5 text-xs text-gray-500">
                      <svg className="w-3 h-3 shrink-0 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                      </svg>
                      {c.company}
                    </div>
                  )}

                  {/* Ticket stats */}
                  {(stats.total > 0) && (
                    <div className="flex items-center gap-1.5 text-xs text-gray-500">
                      <svg className="w-3 h-3 shrink-0 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z" />
                      </svg>
                      {stats.total} support ticket{stats.total !== 1 ? 's' : ''}
                      {stats.open > 0 && <span className="text-orange-500">({stats.open} open)</span>}
                    </div>
                  )}

                  {/* Tags */}
                  {c?.tags && (
                    <div className="flex flex-wrap gap-1 pt-1">
                      {c.tags.split(',').map(t => t.trim()).filter(Boolean).map(t => (
                        <span key={t} className="badge bg-gray-100 text-gray-500 text-xs">{t}</span>
                      ))}
                    </div>
                  )}

                  {/* Recent orders from this customer */}
                  {orders.length > 1 && (
                    <div className="border-t border-gray-100 pt-2 mt-1">
                      <p className="text-xs font-medium text-gray-500 mb-1.5">Recent orders</p>
                      <div className="space-y-1">
                        {orders.slice(0, 3).map(o => (
                          <div
                            key={o.id}
                            onClick={() => navigate(`/orders/${o.id}`)}
                            className={clsx(
                              'flex items-center justify-between text-xs rounded px-2 py-1 cursor-pointer transition-colors',
                              o.id === id ? 'bg-brand-50 text-brand-700' : 'hover:bg-gray-50 text-gray-600'
                            )}
                          >
                            <span className="font-medium">#{o.order_number}</span>
                            <span className={clsx(
                              'badge text-xs',
                              o.financial_status === 'paid' ? 'bg-green-100 text-green-700' :
                              o.financial_status === 'pending' ? 'bg-yellow-100 text-yellow-700' :
                              'bg-gray-100 text-gray-500'
                            )}>{o.financial_status}</span>
                            <span>${o.total_price}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              );
            })()}
          </div>

          {/* Shipping address */}
          {order.shipping_address && (
            <div className="card p-4">
              <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-2">Shipping</h2>
              <p className="text-sm text-gray-700">{order.shipping_address.name}</p>
              <p className="text-sm text-gray-500">{order.shipping_address.address1}</p>
              <p className="text-sm text-gray-500">
                {[order.shipping_address.city, order.shipping_address.province, order.shipping_address.zip].filter(Boolean).join(', ')}
              </p>
              <p className="text-sm text-gray-500">{order.shipping_address.country}</p>
            </div>
          )}

          {/* Tags & meta */}
          <div className="card p-4 text-xs space-y-2">
            {order.tags && (
              <div>
                <span className="text-gray-500">Tags: </span>
                {order.tags.split(',').map(t => t.trim()).filter(Boolean).map(t => (
                  <span key={t} className="badge bg-gray-100 text-gray-600 mr-1">{t}</span>
                ))}
              </div>
            )}
            <div className="text-gray-400">Created: {order.created_at ? new Date(order.created_at).toLocaleString() : '—'}</div>
            <div className="text-gray-400">ID: {order.id}</div>
          </div>
        </div>
      </div>

      {/* ═══════ MODALS ═══════ */}

      {/* Cancel Modal */}
      {cancelModal && (
        <Modal title="Cancel Order" onClose={() => setCancelModal(false)}>
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium text-gray-700 block mb-1">Reason</label>
              <select value={cancelReason} onChange={e => setCancelReason(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500">
                <option value="customer">Customer changed/cancelled</option>
                <option value="inventory">Items unavailable</option>
                <option value="fraud">Fraudulent order</option>
                <option value="declined">Payment declined</option>
                <option value="other">Other</option>
              </select>
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={cancelRestock} onChange={e => setCancelRestock(e.target.checked)} />
              Restock items
            </label>
          </div>
          <ModalFooter onClose={() => setCancelModal(false)} onAction={handleCancel}
            loading={actionLoading === 'Cancel order'} label="Cancel Order" danger />
        </Modal>
      )}

      {/* Refund Modal */}
      {refundModal && (
        <Modal title="Refund Order" onClose={() => setRefundModal(false)}>
          <div className="space-y-3">
            <p className="text-sm text-gray-500">Select items and quantities to refund:</p>
            {refundItems.map((ri, idx) => {
              const li = order.line_items?.find(l => l.id === ri.line_item_id);
              return (
                <div key={ri.line_item_id} className="flex items-center justify-between text-sm">
                  <span className="text-gray-700 flex-1 truncate">{li?.title || ri.line_item_id}</span>
                  <div className="flex items-center gap-2">
                    <input type="number" min="0" max={ri.max} value={ri.quantity}
                      onChange={e => {
                        const items = [...refundItems];
                        items[idx] = { ...items[idx], quantity: Math.min(Number(e.target.value), ri.max) };
                        setRefundItems(items);
                      }}
                      className="w-16 border border-gray-200 rounded px-2 py-1 text-sm text-center focus:outline-none focus:ring-1 focus:ring-brand-500" />
                    <span className="text-gray-400">/ {ri.max}</span>
                  </div>
                </div>
              );
            })}
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={refundShipping} onChange={e => setRefundShipping(e.target.checked)} />
              Refund shipping
            </label>
            <div>
              <label className="text-sm font-medium text-gray-700 block mb-1">Note (optional)</label>
              <input type="text" value={refundNote} onChange={e => setRefundNote(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
            </div>
          </div>
          <ModalFooter onClose={() => setRefundModal(false)} onAction={handleRefund}
            loading={actionLoading === 'Refund'} label="Process Refund" danger />
        </Modal>
      )}

      {/* Fulfill Modal */}
      {fulfillModal && (
        <Modal title="Fulfill Order" onClose={() => setFulfillModal(false)}>
          <div className="space-y-4">
            <p className="text-sm text-gray-500">This will fulfill all unfulfilled items.</p>
            <div>
              <label className="text-sm font-medium text-gray-700 block mb-1">Tracking Number</label>
              <input type="text" value={trackingNumber} onChange={e => setTrackingNumber(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
            </div>
            <div>
              <label className="text-sm font-medium text-gray-700 block mb-1">Tracking URL</label>
              <input type="text" value={trackingUrl} onChange={e => setTrackingUrl(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
            </div>
            <div>
              <label className="text-sm font-medium text-gray-700 block mb-1">Carrier</label>
              <input type="text" value={trackingCompany} onChange={e => setTrackingCompany(e.target.value)}
                placeholder="e.g. USPS, FedEx, DHL"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
            </div>
          </div>
          <ModalFooter onClose={() => setFulfillModal(false)} onAction={handleFulfill}
            loading={actionLoading === 'Fulfillment'} label="Fulfill Items" />
        </Modal>
      )}

      {/* Send Invoice Modal (drafts) */}
      {invoiceModal && (
        <Modal title="Send Invoice" onClose={() => setInvoiceModal(false)}>
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium text-gray-700 block mb-1">To Email</label>
              <input type="email" value={invoiceTo} onChange={e => setInvoiceTo(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
            </div>
            <div>
              <label className="text-sm font-medium text-gray-700 block mb-1">Custom Message (optional)</label>
              <textarea value={invoiceMessage} onChange={e => setInvoiceMessage(e.target.value)} rows={3}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none" />
            </div>
          </div>
          <ModalFooter onClose={() => setInvoiceModal(false)} onAction={handleSendInvoice}
            loading={actionLoading === 'Send invoice'} label="Send Invoice" />
        </Modal>
      )}

      {/* Initiate Return Modal */}
      {returnModal && isOrder && (
        <InitiateReturnModal
          order={order}
          onClose={() => setReturnModal(false)}
          onSuccess={() => {
            setReturnModal(false);
            addToast('Return request created');
            navigate('/returns');
          }}
        />
      )}

      <ToastContainer toasts={toasts} removeToast={removeToast} />
    </div>
  );
}


// ── Reusable modal shell ──
function Modal({ title, onClose, children }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative bg-white rounded-xl shadow-xl w-full max-w-md mx-4">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <h2 className="text-lg font-semibold text-gray-900">{title}</h2>
          <button onClick={onClose} className="p-1 text-gray-400 hover:text-gray-600"><X size={18} /></button>
        </div>
        <div className="px-5 py-4">{children}</div>
      </div>
    </div>
  );
}

function ModalFooter({ onClose, onAction, loading, label, danger = false }) {
  return (
    <div className="flex items-center justify-end gap-2 mt-4 pt-4 border-t border-gray-100">
      <button onClick={onClose} className="btn-secondary" disabled={loading}>Cancel</button>
      <button onClick={onAction} disabled={loading}
        className={clsx('px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50',
          danger ? 'bg-red-600 text-white hover:bg-red-700' : 'bg-brand-600 text-white hover:bg-brand-700')}>
        {loading ? 'Processing...' : label}
      </button>
    </div>
  );
}
