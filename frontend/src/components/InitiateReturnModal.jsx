// Initiate Return modal — select items, reason, resolution from an order
import { useState } from 'react';
import { X } from 'lucide-react';
import api from '../api/client';

const REASONS = [
  { value: 'defective', label: 'Defective / Not working' },
  { value: 'wrong_item', label: 'Wrong item received' },
  { value: 'not_as_described', label: 'Not as described' },
  { value: 'changed_mind', label: 'Changed mind' },
  { value: 'size_issue', label: 'Size / fit issue' },
  { value: 'damaged_in_shipping', label: 'Damaged in shipping' },
  { value: 'late_delivery', label: 'Late delivery' },
  { value: 'other', label: 'Other' },
];

export default function InitiateReturnModal({ order, onClose, onSuccess, ticketId = null }) {
  const [selectedItems, setSelectedItems] = useState(
    (order.line_items || []).map(li => ({ ...li, selected: false, returnQty: li.quantity }))
  );
  const [reason, setReason] = useState('');
  const [reasonNotes, setReasonNotes] = useState('');
  const [resolution, setResolution] = useState('refund');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  function toggleItem(idx) {
    setSelectedItems(items => items.map((it, i) =>
      i === idx ? { ...it, selected: !it.selected } : it
    ));
  }

  function updateQty(idx, qty) {
    setSelectedItems(items => items.map((it, i) =>
      i === idx ? { ...it, returnQty: Math.min(Math.max(1, Number(qty)), it.quantity) } : it
    ));
  }

  async function handleSubmit() {
    const items = selectedItems.filter(i => i.selected);
    if (items.length === 0) { setError('Select at least one item'); return; }
    if (!reason) { setError('Select a reason'); return; }

    setSubmitting(true);
    setError('');
    try {
      await api.post('/returns', {
        order_id: order.id,
        items: items.map(i => ({
          line_item_id: i.id,
          title: i.title,
          variant_title: i.variant_title || '',
          quantity: i.returnQty,
          price: i.price,
          sku: i.sku || '',
        })),
        reason,
        reason_notes: reasonNotes || undefined,
        resolution,
        ticket_id: ticketId || undefined,
      });
      onSuccess();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create return');
    } finally { setSubmitting(false); }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative bg-white rounded-xl shadow-xl w-full max-w-lg mx-4 max-h-[85vh] flex flex-col">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <h2 className="text-lg font-semibold text-gray-900">Initiate Return</h2>
          <button onClick={onClose} className="p-1 text-gray-400 hover:text-gray-600"><X size={18} /></button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
          {/* Order ref */}
          <div className="text-sm text-gray-500">
            Order <span className="font-medium text-gray-900">{order.name || `#${order.order_number}`}</span>
          </div>

          {/* Select items */}
          <div>
            <label className="text-sm font-medium text-gray-700 block mb-2">Items to return</label>
            <div className="space-y-2">
              {selectedItems.map((li, idx) => (
                <div key={li.id} className="flex items-center gap-3 p-2 rounded-lg border border-gray-100 hover:bg-gray-50">
                  <input type="checkbox" checked={li.selected} onChange={() => toggleItem(idx)}
                    className="rounded border-gray-300" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-gray-900 truncate">{li.title}</p>
                    {li.variant_title && <p className="text-xs text-gray-500">{li.variant_title}</p>}
                  </div>
                  {li.selected && (
                    <div className="flex items-center gap-1">
                      <span className="text-xs text-gray-400">Qty:</span>
                      <input type="number" min="1" max={li.quantity} value={li.returnQty}
                        onChange={e => updateQty(idx, e.target.value)}
                        className="w-14 border border-gray-200 rounded px-2 py-0.5 text-sm text-center focus:outline-none focus:ring-1 focus:ring-brand-500" />
                      <span className="text-xs text-gray-400">/ {li.quantity}</span>
                    </div>
                  )}
                  <span className="text-sm text-gray-500 shrink-0">${li.price}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Reason */}
          <div>
            <label className="text-sm font-medium text-gray-700 block mb-1">Reason for return *</label>
            <select value={reason} onChange={e => setReason(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500">
              <option value="">Select a reason...</option>
              {REASONS.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
            </select>
          </div>

          <div>
            <label className="text-sm font-medium text-gray-700 block mb-1">Additional notes</label>
            <textarea value={reasonNotes} onChange={e => setReasonNotes(e.target.value)} rows={2}
              placeholder="Optional details..."
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none" />
          </div>

          {/* Resolution */}
          <div>
            <label className="text-sm font-medium text-gray-700 block mb-2">Preferred resolution *</label>
            <div className="flex gap-3">
              <label className={`flex-1 p-3 rounded-lg border-2 cursor-pointer transition-colors ${
                resolution === 'refund' ? 'border-brand-500 bg-brand-50' : 'border-gray-200 hover:border-gray-300'
              }`}>
                <input type="radio" value="refund" checked={resolution === 'refund'}
                  onChange={e => setResolution(e.target.value)} className="sr-only" />
                <p className="text-sm font-medium text-gray-900">Refund</p>
                <p className="text-xs text-gray-500 mt-0.5">Get money back once item is received</p>
              </label>
              <label className={`flex-1 p-3 rounded-lg border-2 cursor-pointer transition-colors ${
                resolution === 'replacement' ? 'border-brand-500 bg-brand-50' : 'border-gray-200 hover:border-gray-300'
              }`}>
                <input type="radio" value="replacement" checked={resolution === 'replacement'}
                  onChange={e => setResolution(e.target.value)} className="sr-only" />
                <p className="text-sm font-medium text-gray-900">Replacement</p>
                <p className="text-xs text-gray-500 mt-0.5">New order shipped once item is received</p>
              </label>
            </div>
          </div>

          {error && <p className="text-sm text-red-600">{error}</p>}
        </div>

        <div className="flex items-center justify-end gap-2 px-5 py-4 border-t border-gray-100 bg-gray-50">
          <button onClick={onClose} className="btn-secondary" disabled={submitting}>Cancel</button>
          <button onClick={handleSubmit} disabled={submitting} className="btn-primary">
            {submitting ? 'Submitting...' : 'Submit Return Request'}
          </button>
        </div>
      </div>
    </div>
  );
}
