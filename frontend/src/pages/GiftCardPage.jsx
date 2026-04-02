// Gift card management — fetch from Shopify, assign to customers, send via channel
import { useState, useEffect } from 'react';
import { Gift, Send, RefreshCw, History, Ban } from 'lucide-react';
import api from '../api/client';

const STATUS_COLORS = {
  active: 'bg-green-100 text-green-800',
  disabled: 'bg-red-100 text-red-800',
};

export default function GiftCardPage() {
  const [tab, setTab] = useState('shopify'); // 'shopify' or 'history'
  // Shopify cards state
  const [shopifyCards, setShopifyCards] = useState([]);
  const [shopifyLoading, setShopifyLoading] = useState(true);
  const [shopifyFilter, setShopifyFilter] = useState('enabled');
  // Assignment history state
  const [assignments, setAssignments] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyTotal, setHistoryTotal] = useState(0);
  // Assign modal state
  const [assignModal, setAssignModal] = useState(null); // null or card object
  const [assignForm, setAssignForm] = useState({ customer_email: '', channel: 'email' });
  const [assigning, setAssigning] = useState(false);
  // Toast
  const [toast, setToast] = useState(null);

  function showToast(msg, type = 'success') {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 4000);
  }

  // ── Fetch Shopify gift cards ────────────────────────────────────────
  async function loadShopifyCards() {
    setShopifyLoading(true);
    try {
      const res = await api.get('/gift-cards/shopify', { params: { status: shopifyFilter, limit: 50 } });
      setShopifyCards(res.data.gift_cards || []);
    } catch (err) {
      console.error('Failed to fetch Shopify gift cards:', err);
      showToast('Failed to fetch gift cards from Shopify', 'error');
    } finally {
      setShopifyLoading(false);
    }
  }

  // ── Fetch assignment history ────────────────────────────────────────
  async function loadHistory() {
    setHistoryLoading(true);
    try {
      const res = await api.get('/gift-cards/assignments');
      setAssignments(res.data.assignments || []);
      setHistoryTotal(res.data.total || 0);
    } catch (err) {
      console.error('Failed to fetch assignment history:', err);
    } finally {
      setHistoryLoading(false);
    }
  }

  useEffect(() => {
    if (tab === 'shopify') loadShopifyCards();
    else loadHistory();
  }, [tab, shopifyFilter]);

  // ── Assign + Send ──────────────────────────────────────────────────
  async function handleAssign(e) {
    e.preventDefault();
    if (!assignModal) return;
    setAssigning(true);
    try {
      // Step 1: Create assignment
      const assignRes = await api.post('/gift-cards/assign', {
        shopify_gift_card_id: assignModal.id,
        code: assignModal.code,
        balance: assignModal.balance,
        currency: assignModal.currency || 'INR',
        customer_email: assignForm.customer_email,
        channels: [assignForm.channel],
        type: 'manual',
        expires_at: assignModal.expires_on || null,
      });
      const assignmentId = assignRes.data.id;

      // Step 2: Send notification
      try {
        await api.post(`/gift-cards/assignments/${assignmentId}/notify`);
        showToast(`Gift card sent to ${assignForm.customer_email} via ${assignForm.channel}!`);
      } catch (notifyErr) {
        showToast(`Assigned but notification failed: ${notifyErr.response?.data?.detail || notifyErr.message}`, 'error');
      }

      setAssignModal(null);
      setAssignForm({ customer_email: '', channel: 'email' });
    } catch (err) {
      showToast('Assign failed: ' + (err.response?.data?.detail || err.message), 'error');
    } finally {
      setAssigning(false);
    }
  }

  // ── Resend notification ────────────────────────────────────────────
  async function handleResend(assignmentId) {
    try {
      await api.post(`/gift-cards/assignments/${assignmentId}/notify`);
      showToast('Notification resent!');
      loadHistory();
    } catch (err) {
      showToast('Resend failed: ' + (err.response?.data?.detail || err.message), 'error');
    }
  }

  // ── Expire gift card ────────────────────────────────────────────────
  async function handleExpire(assignmentId) {
    if (!confirm('Are you sure you want to expire this gift card? This will disable it on Shopify and cannot be undone.')) return;
    try {
      await api.post(`/gift-cards/assignments/${assignmentId}/expire`);
      showToast('Gift card expired successfully');
      loadHistory();
    } catch (err) {
      showToast('Expire failed: ' + (err.response?.data?.detail || err.message), 'error');
    }
  }

  // ── Format code with spaces (XXXX XXXX XXXX XXXX) ─────────────────
  function formatCode(code) {
    if (!code || code === 'pending' || code.startsWith('ending in')) return code || '—';
    // Remove existing spaces and group into 4-char blocks
    const clean = code.replace(/\s+/g, '');
    return clean.match(/.{1,4}/g)?.join(' ') || code;
  }

  // ── Message preview ────────────────────────────────────────────────
  function getPreviewMessage(card) {
    if (!card) return '';
    const expiry = card.expires_on ? `\nValid till: ${card.expires_on}` : '\nNo expiry date.';
    return `You've received a Gift Card!\n\nCode: ${formatCode(card.code)}\nBalance: ${card.currency || 'INR'} ${card.balance}${expiry}\n\nUse this code at checkout to redeem your gift.`;
  }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Gift size={24} /> Gift Cards
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Manage Shopify gift cards and assign them to customers
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 border-b border-gray-200">
        <button
          onClick={() => setTab('shopify')}
          className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
            tab === 'shopify'
              ? 'border-brand-600 text-brand-600'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          <span className="flex items-center gap-2"><Gift size={16} /> Shopify Gift Cards</span>
        </button>
        <button
          onClick={() => setTab('history')}
          className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
            tab === 'history'
              ? 'border-brand-600 text-brand-600'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          <span className="flex items-center gap-2"><History size={16} /> Assigned History</span>
        </button>
      </div>

      {/* ── TAB 1: Shopify Gift Cards ──────────────────────────────── */}
      {tab === 'shopify' && (
        <>
          {/* Filters + Refresh */}
          <div className="flex items-center justify-between mb-4">
            <div className="flex gap-2">
              {[
                { value: 'enabled', label: 'Active' },
                { value: 'disabled', label: 'Disabled' },
                { value: '', label: 'All' },
              ].map(f => (
                <button
                  key={f.value}
                  onClick={() => setShopifyFilter(f.value)}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                    shopifyFilter === f.value
                      ? 'bg-brand-600 text-white'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  {f.label}
                </button>
              ))}
            </div>
            <button
              onClick={loadShopifyCards}
              disabled={shopifyLoading}
              className="flex items-center gap-2 px-3 py-1.5 text-sm text-gray-600 hover:text-gray-900 border border-gray-300 rounded-lg hover:bg-gray-50"
            >
              <RefreshCw size={14} className={shopifyLoading ? 'animate-spin' : ''} />
              Refresh
            </button>
          </div>

          {/* Gift Cards Table */}
          {shopifyLoading ? (
            <div className="flex items-center justify-center h-48">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600"></div>
            </div>
          ) : (
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <table className="w-full">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Code</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Balance</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Initial Value</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Expires</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Created</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {shopifyCards.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="px-4 py-12 text-center text-gray-400">
                        No gift cards found on Shopify
                      </td>
                    </tr>
                  ) : (
                    shopifyCards.map(card => (
                      <tr key={card.id} className="hover:bg-gray-50">
                        <td className="px-4 py-3 text-sm font-mono text-gray-700">{formatCode(card.code)}</td>
                        <td className="px-4 py-3 text-sm font-semibold text-gray-900">
                          {card.currency} {card.balance}
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-500">
                          {card.currency} {card.initial_value}
                        </td>
                        <td className="px-4 py-3">
                          <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium capitalize ${STATUS_COLORS[card.status] || 'bg-gray-100'}`}>
                            {card.status}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-500">
                          {card.expires_on ? new Date(card.expires_on).toLocaleDateString() : 'Never'}
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-500">
                          {card.created_at ? new Date(card.created_at).toLocaleDateString() : '—'}
                        </td>
                        <td className="px-4 py-3 text-right">
                          {card.status === 'active' && parseFloat(card.balance) > 0 && (
                            <button
                              onClick={() => {
                                setAssignModal(card);
                                setAssignForm({ customer_email: '', channel: 'email' });
                              }}
                              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-white bg-brand-600 rounded-lg hover:bg-brand-700 transition-colors"
                            >
                              <Send size={14} /> Assign & Send
                            </button>
                          )}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {/* ── TAB 2: Assigned History ────────────────────────────────── */}
      {tab === 'history' && (
        <>
          {historyLoading ? (
            <div className="flex items-center justify-center h-48">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600"></div>
            </div>
          ) : (
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <table className="w-full">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Customer</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Gift Card Code</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Balance</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Channel</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Sent</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Assigned</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {assignments.length === 0 ? (
                    <tr>
                      <td colSpan={8} className="px-4 py-12 text-center text-gray-400">
                        No gift cards have been assigned yet
                      </td>
                    </tr>
                  ) : (
                    assignments.map(a => (
                      <tr key={a.id} className="hover:bg-gray-50">
                        <td className="px-4 py-3 text-sm text-gray-900">{a.customer_email}</td>
                        <td className="px-4 py-3 text-sm font-mono text-gray-600">
                          {a.code === 'pending' ? '(pending)' : formatCode(a.code)}
                        </td>
                        <td className="px-4 py-3 text-sm font-medium text-gray-900">
                          {a.currency || ''} {a.balance}
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-600 capitalize">{a.channel}</td>
                        <td className="px-4 py-3 text-sm text-gray-600 capitalize">{a.type}</td>
                        <td className="px-4 py-3">
                          {a.notified ? (
                            <span className="inline-block px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                              Sent {a.notified_at ? new Date(a.notified_at).toLocaleDateString() : ''}
                            </span>
                          ) : (
                            <span className="inline-block px-2 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                              Not sent
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-500">
                          {a.assigned_at ? new Date(a.assigned_at).toLocaleDateString() : '—'}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <div className="flex items-center justify-end gap-1">
                            {!a.notified && a.code !== 'pending' && (
                              <button
                                onClick={() => handleResend(a.id)}
                                className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-brand-600 border border-brand-200 rounded-lg hover:bg-brand-50"
                              >
                                <Send size={12} /> Send
                              </button>
                            )}
                            {!a.expired && a.shopify_gift_card_id !== 'pending' && (
                              <button
                                onClick={() => handleExpire(a.id)}
                                className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-red-600 border border-red-200 rounded-lg hover:bg-red-50"
                              >
                                <Ban size={12} /> Expire
                              </button>
                            )}
                            {a.expired && (
                              <span className="inline-block px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
                                Expired
                              </span>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
              {historyTotal > 0 && (
                <div className="px-4 py-3 border-t border-gray-100 text-sm text-gray-500">
                  {historyTotal} total assignments
                </div>
              )}
            </div>
          )}
        </>
      )}

      {/* ── Assign & Send Modal ────────────────────────────────────── */}
      {assignModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-lg p-6">
            <h2 className="text-lg font-semibold mb-1">Assign & Send Gift Card</h2>
            <p className="text-sm text-gray-500 mb-4">
              Code: <span className="font-mono font-bold text-gray-700">{formatCode(assignModal.code)}</span> — Balance: {assignModal.currency} {assignModal.balance}
            </p>

            <form onSubmit={handleAssign} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Customer Email</label>
                <input
                  type="email"
                  required
                  value={assignForm.customer_email}
                  onChange={e => setAssignForm({ ...assignForm, customer_email: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
                  placeholder="customer@example.com"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Send via</label>
                <select
                  value={assignForm.channel}
                  onChange={e => setAssignForm({ ...assignForm, channel: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
                >
                  <option value="email">Email</option>
                  <option value="whatsapp">WhatsApp</option>
                  <option value="instagram">Instagram</option>
                </select>
              </div>

              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setAssignModal(null)}
                  className="flex-1 px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={assigning}
                  className="flex-1 px-4 py-2 bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50 flex items-center justify-center gap-2"
                >
                  {assigning ? (
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                  ) : (
                    <><Send size={16} /> Assign & Send</>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Toast */}
      {toast && (
        <div className={`fixed bottom-6 right-6 z-50 px-4 py-3 rounded-lg shadow-lg text-sm font-medium ${
          toast.type === 'error' ? 'bg-red-600 text-white' : 'bg-green-600 text-white'
        }`}>
          {toast.msg}
        </div>
      )}
    </div>
  );
}
