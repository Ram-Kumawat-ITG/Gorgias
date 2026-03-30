// Create Order modal — product search with images, infinite scroll, draft + confirm buttons
import { useState, useEffect, useRef, useCallback } from 'react';
import { X, Search, Trash2 } from 'lucide-react';
import api from '../api/client';

export default function CreateOrderModal({ customerId, customerName, customerEmail, onClose, onSuccess }) {
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [lastProductId, setLastProductId] = useState(null);
  const [loadingMore, setLoadingMore] = useState(false);

  const [items, setItems] = useState([]);
  const [note, setNote] = useState('');
  const [tags, setTags] = useState('');
  const [isLoadingPaid, setIsLoadingPaid] = useState(false);
  const [isLoadingPending, setIsLoadingPending] = useState(false);
  const [creatingDraft, setCreatingDraft] = useState(false);
  const [error, setError] = useState('');

  const searchRef = useRef(null);
  const dropdownRef = useRef(null);

  // ── Fetch products (initial or search) ──
  async function fetchProducts(query = '', sinceId = '') {
    if (sinceId) {
      setLoadingMore(true);
    } else {
      setSearchLoading(true);
    }
    try {
      const res = await api.get('/orders/products/search', {
        params: { q: query, limit: 250, since_id: sinceId },
      });
      const data = res.data;
      if (sinceId) {
        setSearchResults(prev => [...prev, ...data.products]);
      } else {
        setSearchResults(data.products);
      }
      setHasMore(data.has_more);
      setLastProductId(data.last_product_id);
      setShowDropdown(true);
    } catch {} finally {
      setSearchLoading(false);
      setLoadingMore(false);
    }
  }

  // Load products on mount
  useEffect(() => { fetchProducts(''); }, []);

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => {
      setLastProductId(null);
      fetchProducts(searchQuery);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Close dropdown on outside click
  useEffect(() => {
    function handle(e) {
      if (searchRef.current && !searchRef.current.contains(e.target)) setShowDropdown(false);
    }
    document.addEventListener('mousedown', handle);
    return () => document.removeEventListener('mousedown', handle);
  }, []);

  // ── Infinite scroll in dropdown ──
  const handleDropdownScroll = useCallback(() => {
    const el = dropdownRef.current;
    if (!el || loadingMore || !hasMore) return;
    if (el.scrollTop + el.clientHeight >= el.scrollHeight - 40) {
      fetchProducts(searchQuery, lastProductId);
    }
  }, [loadingMore, hasMore, lastProductId, searchQuery]);

  // ── Add product to order ──
  function addProduct(product) {
    const existing = items.find(i => i.variant_id === product.variant_id);
    if (existing) {
      setItems(items.map(i => i.variant_id === product.variant_id ? { ...i, quantity: i.quantity + 1 } : i));
    } else {
      setItems([...items, {
        variant_id: product.variant_id,
        title: product.title,
        price: product.price,
        quantity: 1,
        inventory_quantity: product.inventory_quantity,
        image: product.image,
      }]);
    }
    setSearchQuery('');
    setShowDropdown(false);
  }

  function updateItemQty(idx, qty) {
    setItems(items.map((item, i) => i === idx ? { ...item, quantity: Math.max(1, Number(qty)) } : item));
  }

  function removeItem(idx) {
    setItems(items.filter((_, i) => i !== idx));
  }

  const subtotal = items.reduce((sum, i) => sum + (parseFloat(i.price) || 0) * i.quantity, 0);

  // ── Build payload ──
  function buildPayload() {
    return {
      customer_id: customerId,
      line_items: items.map(i => ({
        title: i.title,
        quantity: i.quantity,
        price: i.price,
        variant_id: i.variant_id || undefined,
      })),
      note: note || undefined,
      tags: tags || undefined,
    };
  }

  // ── Create confirmed order ──
  async function handleCreateOrder(financial_status) {
    if (items.length === 0) { setError('Add at least one item'); return; }
    const setLoader = financial_status === 'paid' ? setIsLoadingPaid : setIsLoadingPending;
    setLoader(true);
    setError('');
    try {
      await api.post('/orders', { ...buildPayload(), financial_status });
      onSuccess(`Order created as ${financial_status} on Shopify`);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create order');
    } finally { setLoader(false); }
  }

  // ── Create draft order + send Shopify invoice ──
  async function handleCreateDraft() {
    if (items.length === 0) { setError('Add at least one item'); return; }
    setCreatingDraft(true);
    setError('');
    try {
      const res = await api.post('/orders/drafts', buildPayload());
      const draftId = res.data.id;
      if (draftId) {
        try { await api.post(`/orders/drafts/${draftId}/send-invoice`); } catch {}
      }
      onSuccess(`Draft order ${res.data.name || ''} created & invoice sent`);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create draft order');
    } finally { setCreatingDraft(false); }
  }

  const busy = isLoadingPaid || isLoadingPending || creatingDraft;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative bg-white rounded-xl shadow-2xl w-full max-w-3xl mx-4 max-h-[90vh] flex flex-col">

        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <h2 className="text-xl font-semibold text-gray-900">Create order</h2>
          <button onClick={onClose} className="p-1 text-gray-400 hover:text-gray-600"><X size={20} /></button>
        </div>

        <div className="flex-1 overflow-y-auto">
          <div className="flex">
            {/* Left column — items */}
            <div className="flex-1 px-6 py-5 border-r border-gray-100">

              {/* Product search */}
              <div className="relative mb-4" ref={searchRef}>
                <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                  onFocus={() => setShowDropdown(true)}
                  placeholder="Search products..."
                  className="w-full pl-10 pr-4 py-2.5 border border-gray-200 rounded-lg text-sm
                             focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
                {showDropdown && (
                  <div ref={dropdownRef} onScroll={handleDropdownScroll}
                    className="absolute left-0 right-0 top-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-20 max-h-72 overflow-y-auto">
                    {searchLoading && searchResults.length === 0 ? (
                      <div className="flex items-center justify-center py-3"><div className="w-5 h-5 border-2 border-gray-200 border-t-brand-600 rounded-full animate-spin" /></div>
                    ) : searchResults.length === 0 ? (
                      <p className="px-4 py-3 text-sm text-gray-400">No products found</p>
                    ) : (
                      <>
                        {searchResults.map(p => (
                          <button key={p.variant_id} onClick={() => addProduct(p)}
                            className="w-full text-left flex items-center gap-3 px-4 py-2.5 hover:bg-gray-50 border-b border-gray-50 last:border-0 transition-colors">
                            {/* Product image */}
                            <div className="w-10 h-10 rounded bg-gray-100 shrink-0 overflow-hidden">
                              {p.image ? (
                                <img src={p.image} alt="" className="w-full h-full object-cover" />
                              ) : (
                                <div className="w-full h-full flex items-center justify-center text-gray-300 text-xs">N/A</div>
                              )}
                            </div>
                            <div className="flex-1 min-w-0">
                              <p className="text-sm font-medium text-gray-900 truncate">{p.title}</p>
                              <p className="text-xs text-gray-500">
                                ${p.price}
                                <span className="mx-1">·</span>
                                <span className={p.inventory_quantity > 0 ? 'text-green-600' : 'text-red-500'}>
                                  {p.inventory_quantity > 0 ? `${p.inventory_quantity} in stock` : 'Out of stock'}
                                </span>
                                {p.sku && <span className="ml-1 text-gray-400">· {p.sku}</span>}
                              </p>
                            </div>
                          </button>
                        ))}
                        {loadingMore && (
                          <p className="px-4 py-2 text-xs text-gray-400 text-center">Loading more...</p>
                        )}
                        {hasMore && !loadingMore && (
                          <p className="px-4 py-2 text-xs text-gray-300 text-center">Scroll for more</p>
                        )}
                      </>
                    )}
                  </div>
                )}
              </div>

              {/* Items table */}
              <table className="w-full">
                <thead>
                  <tr className="border-b border-gray-200">
                    <th className="text-left py-2 text-xs font-semibold text-gray-500 uppercase tracking-wider">Product</th>
                    <th className="text-center py-2 text-xs font-semibold text-gray-500 uppercase tracking-wider w-20">In Stock</th>
                    <th className="text-right py-2 text-xs font-semibold text-gray-500 uppercase tracking-wider w-24">Item Price</th>
                    <th className="text-center py-2 text-xs font-semibold text-gray-500 uppercase tracking-wider w-16">Qty</th>
                    <th className="text-right py-2 text-xs font-semibold text-gray-500 uppercase tracking-wider w-24">Item Total</th>
                    <th className="w-8"></th>
                  </tr>
                </thead>
                <tbody>
                  {items.length === 0 ? (
                    <tr><td colSpan={6} className="py-6 text-center text-sm text-gray-400">No items</td></tr>
                  ) : (
                    items.map((item, idx) => (
                      <tr key={idx} className="border-b border-gray-50">
                        <td className="py-3">
                          <div className="flex items-center gap-2">
                            <div className="w-8 h-8 rounded bg-gray-100 shrink-0 overflow-hidden">
                              {item.image ? (
                                <img src={item.image} alt="" className="w-full h-full object-cover" />
                              ) : (
                                <div className="w-full h-full flex items-center justify-center text-gray-300 text-[10px]">N/A</div>
                              )}
                            </div>
                            <span className="text-sm text-gray-900 truncate">{item.title}</span>
                          </div>
                        </td>
                        <td className="py-3 text-center text-sm text-gray-500">
                          <span className={item.inventory_quantity > 0 ? 'text-green-600' : 'text-red-500'}>
                            {item.inventory_quantity !== null ? item.inventory_quantity : '—'}
                          </span>
                        </td>
                        <td className="py-3 text-right text-sm text-gray-900">${item.price}</td>
                        <td className="py-3 text-center">
                          <input type="number" min="1" value={item.quantity}
                            onChange={e => updateItemQty(idx, e.target.value)}
                            className="w-14 text-center border border-gray-200 rounded px-1 py-0.5 text-sm focus:outline-none focus:ring-1 focus:ring-brand-500" />
                        </td>
                        <td className="py-3 text-right text-sm font-medium text-gray-900">
                          ${(parseFloat(item.price) * item.quantity).toFixed(2)}
                        </td>
                        <td className="py-3 text-center">
                          <button onClick={() => removeItem(idx)}
                            className="p-1 text-gray-300 hover:text-red-500 transition-colors">
                            <Trash2 size={14} />
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>

              {/* Notes & Tags */}
              <div className="mt-6 space-y-4">
                <div>
                  <label className="text-sm font-semibold text-gray-900 block mb-1.5">Notes</label>
                  <textarea value={note} onChange={e => setNote(e.target.value)}
                    rows={2} placeholder="Add a note..."
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none" />
                </div>
                <div>
                  <label className="text-sm font-semibold text-gray-900 block mb-1.5">Tags</label>
                  <input type="text" value={tags} onChange={e => setTags(e.target.value)}
                    placeholder="Add tags..."
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                </div>
              </div>
            </div>

            {/* Right column — summary */}
            <div className="w-56 px-5 py-5 space-y-3">
              <div className="flex justify-between text-sm">
                <span className="text-gray-500">Subtotal</span>
                <span className="font-medium text-gray-900">{items.length > 0 ? `$${subtotal.toFixed(2)}` : '—'}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-500">Taxes</span>
                <span className="text-gray-400">—</span>
              </div>
              <div className="border-t border-gray-200 pt-3 flex justify-between text-sm">
                <span className="font-semibold text-gray-900">Total</span>
                <span className="font-semibold text-gray-900">{items.length > 0 ? `$${subtotal.toFixed(2)}` : '—'}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-200 bg-gray-50 rounded-b-xl space-y-3">
          {error && <p className="text-sm text-red-600">{error}</p>}

          {/* Top row — draft + invoice */}
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-500">Create draft order &amp; send Shopify invoice</p>
            <button onClick={handleCreateDraft} disabled={busy || items.length === 0}
              className="btn-primary text-sm">
              {creatingDraft ? 'Creating...' : 'Create Draft Order'}
            </button>
          </div>

          {/* Bottom row — cancel + paid/pending */}
          <div className="flex items-center justify-between">
            <button onClick={onClose} className="btn-secondary text-sm" disabled={busy}>Cancel</button>
            <div className="flex gap-2">
              <button onClick={() => handleCreateOrder('paid')} disabled={busy || items.length === 0}
                className="btn-primary text-sm">
                {isLoadingPaid ? 'Creating...' : 'Create order as paid'}
              </button>
              <button onClick={() => handleCreateOrder('pending')} disabled={busy || items.length === 0}
                className="btn-primary text-sm">
                {isLoadingPending ? 'Creating...' : 'Create order as pending'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
