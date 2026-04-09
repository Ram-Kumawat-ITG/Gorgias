/**
 * QuickActionPanel — admin action popup for pending_admin_action tickets.
 *
 * Layout matches the Gorgias-style action panel:
 *   • Header  — ticket # / intent, customer name, order #, autonomous badge
 *   • Stats   — order value, order date, refund window, customer orders
 *   • Tracking + Inventory (two-column)
 *   • Policy eligibility checks
 *   • Action buttons (dynamic per intent)
 */

import { useState, useEffect } from 'react';
import { Loader2, AlertTriangle, CheckCircle, RefreshCw } from 'lucide-react';
import api from '../api/client';
import clsx from 'clsx';

const _REFUND_WINDOW_DAYS = 7;

// ── Colour helpers ────────────────────────────────────────────────────────────

const COLOR_CLASS = {
  green:  'text-green-600',
  amber:  'text-amber-500',
  yellow: 'text-yellow-500',
  red:    'text-red-500',
  gray:   'text-gray-400',
};

function PolicyRow({ label, value, color }) {
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-gray-50 last:border-0 text-sm">
      <span className="text-gray-500">{label}</span>
      <span className={clsx('font-medium', COLOR_CLASS[color] || 'text-gray-700')}>{value}</span>
    </div>
  );
}

function TrackingDot({ done }) {
  return (
    <span
      className={clsx(
        'inline-block w-2 h-2 rounded-full shrink-0',
        done ? 'bg-green-500' : 'bg-gray-200',
      )}
    />
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function QuickActionPanel({ ticket, messages, onActionComplete }) {
  const [details, setDetails]         = useState(null);
  const [detailsLoading, setDL]       = useState(true);
  const [detailsError, setDE]         = useState(null);

  const [actionLoading, setActionL]   = useState(false);
  const [actionSuccess, setActionS]   = useState(null);
  const [actionError, setActionE]     = useState(null);

  const [showPartial, setShowPartial] = useState(false);
  const [partialAmt, setPartialAmt]   = useState('');
  const [showReject, setShowReject]   = useState(false);
  const [rejectReason, setRR]         = useState('');

  const ticketId  = ticket?.id;
  const pat       = ticket?.pending_action_type;    // refund | return | replace | cancel
  const hasOrderId = !!ticket?.pending_action_order_id;

  // ── Fetch order details ───────────────────────────────────────────────────
  async function loadDetails() {
    setDL(true); setDE(null);
    try {
      const res = await api.get(`/shopify-action/${ticketId}/order-details`);
      setDetails(res.data);
    } catch (err) {
      setDE(err.response?.data?.detail || 'Failed to load order details.');
    } finally { setDL(false); }
  }

  useEffect(() => {
    if (ticketId && hasOrderId) loadDetails();
    else setDL(false);
  }, [ticketId]);

  // ── Execute action ────────────────────────────────────────────────────────
  async function handleAction(action) {
    setActionL(true); setActionE(null);
    try {
      if (action === 'reject') {
        await api.post(`/ai/reject-action/${ticketId}`, {
          rejection_reason: rejectReason || undefined,
        });
        setActionS({ label: 'Rejected', message: 'Request rejected. Customer has been notified.' });
      } else {
        const res = await api.post(`/shopify-action/${ticketId}`, {
          action,
          partial_amount: action === 'partial-refund' ? parseFloat(partialAmt) : undefined,
        });
        setActionS({ label: action, message: res.data.message || 'Action completed.' });
      }
      setTimeout(() => { if (onActionComplete) onActionComplete(); }, 2000);
    } catch (err) {
      setActionE(err.response?.data?.detail || err.message || 'Action failed. Please try again.');
    } finally { setActionL(false); }
  }

  // ── Currency formatter ────────────────────────────────────────────────────
  const currency = details?.order?.currency || 'USD';
  const fmt = (amt) => {
    const n = parseFloat(amt || 0);
    return new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(n);
  };

  // ── Action button definitions per intent ──────────────────────────────────
  const isAutoChannel = ticket?.channel === 'whatsapp' || ticket?.channel === 'instagram';
  const orderNum = ticket?.pending_action_order_number || details?.order?.name?.replace('#', '') || '—';
  const refundableAmt = details?.refundable_amount || '0.00';

  function renderActionButtons() {
    if (actionSuccess) {
      return (
        <div className="flex items-start gap-3 rounded-lg bg-green-50 border border-green-200 p-3">
          <CheckCircle size={16} className="text-green-600 mt-0.5 shrink-0" />
          <div>
            <p className="text-sm font-semibold text-green-700">Action completed</p>
            <p className="text-sm text-green-600">{actionSuccess.message}</p>
          </div>
        </div>
      );
    }

    const disabled = !hasOrderId || actionLoading;
    const disabledTip = !hasOrderId
      ? 'No Shopify order ID linked to this ticket'
      : actionLoading ? 'Processing…' : undefined;

    const btnPrimary = (label, action, extra = '') => (
      <button
        key={action}
        onClick={() => handleAction(action)}
        disabled={disabled}
        title={disabledTip}
        className={clsx(
          'flex-1 py-2.5 rounded-lg text-sm font-medium transition-colors flex items-center justify-center gap-1.5',
          'bg-green-600 text-white hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed',
          extra,
        )}
      >
        {actionLoading
          ? <><Loader2 size={13} className="animate-spin" /> Processing…</>
          : label}
      </button>
    );

    const btnSecondary = (label, onClick, colorClass = '') => (
      <button
        key={label}
        onClick={onClick}
        disabled={disabled && label !== 'Reject' && label !== 'Reject Cancel'}
        title={disabled && label !== 'Reject' ? disabledTip : undefined}
        className={clsx(
          'flex-1 py-2.5 rounded-lg text-sm font-medium border border-gray-200 text-gray-600',
          'bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors',
          colorClass,
        )}
      >
        {label}
      </button>
    );

    // Partial refund input state
    if (showPartial) {
      return (
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm text-gray-600 font-medium shrink-0">Refund amount:</span>
          <input
            type="number" min="0.01" step="0.01"
            value={partialAmt}
            onChange={e => setPartialAmt(e.target.value)}
            placeholder="0.00"
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm w-28 focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
          <button
            onClick={() => handleAction('partial-refund')}
            disabled={!partialAmt || isNaN(parseFloat(partialAmt)) || parseFloat(partialAmt) <= 0}
            className="px-4 py-2 rounded-lg bg-orange-600 text-white text-sm font-medium hover:bg-orange-700 disabled:opacity-50 flex items-center gap-1.5"
          >
            {actionLoading ? <><Loader2 size={13} className="animate-spin" /> Processing…</> : 'Confirm'}
          </button>
          <button
            onClick={() => { setShowPartial(false); setPartialAmt(''); }}
            className="px-3 py-2 rounded-lg border border-gray-200 text-gray-600 text-sm hover:bg-gray-50"
          >
            Cancel
          </button>
        </div>
      );
    }

    // Reject reason input state
    if (showReject) {
      return (
        <div className="space-y-2">
          <input
            type="text" value={rejectReason} onChange={e => setRR(e.target.value)}
            placeholder="Rejection reason (optional)"
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-400"
          />
          <div className="flex gap-2">
            <button
              onClick={() => handleAction('reject')} disabled={actionLoading}
              className="px-4 py-2 rounded-lg bg-red-600 text-white text-sm font-medium hover:bg-red-700 disabled:opacity-50 flex items-center gap-1.5"
            >
              {actionLoading ? <><Loader2 size={13} className="animate-spin" /> Rejecting…</> : 'Confirm Reject'}
            </button>
            <button
              onClick={() => { setShowReject(false); setRR(''); }}
              className="px-3 py-2 rounded-lg border border-gray-200 text-gray-600 text-sm hover:bg-gray-50"
            >
              Cancel
            </button>
          </div>
        </div>
      );
    }

    // Button row by intent
    const rejectBtn = (label = 'Reject') => btnSecondary(label, () => setShowReject(true), 'hover:border-red-200 hover:text-red-600');

    switch (pat) {
      case 'refund':
        return (
          <div className="flex gap-2">
            {btnPrimary(`Full refund ${fmt(refundableAmt)}`, 'full-refund')}
            {btnSecondary('Partial refund', () => setShowPartial(true))}
            {btnSecondary('Exchange offer', () => handleAction('replacement'))}
            {btnSecondary('Wait for return', () => handleAction('return-label'))}
          </div>
        );
      case 'return':
        return (
          <div className="flex gap-2">
            {btnPrimary('Approve Return', 'return-label')}
            {btnSecondary('Partial refund', () => setShowPartial(true))}
            {btnSecondary('Exchange offer', () => handleAction('replacement'))}
            {rejectBtn()}
          </div>
        );
      case 'replace':
        return (
          <div className="flex gap-2">
            {btnPrimary('Send Replacement', 'replacement')}
            {btnSecondary('Partial refund', () => setShowPartial(true))}
            {btnSecondary('Exchange offer', () => handleAction('replacement'))}
            {rejectBtn()}
          </div>
        );
      case 'cancel':
        return (
          <div className="flex gap-2">
            {btnPrimary('Confirm Cancellation', 'cancel')}
            {rejectBtn('Reject Cancel')}
          </div>
        );
      default:
        return (
          <div className="flex gap-2">
            {btnPrimary('Approve Request', 'full-refund')}
            {rejectBtn()}
          </div>
        );
    }
  }

  // ── Loading skeleton ──────────────────────────────────────────────────────
  if (detailsLoading) {
    return (
      <div className="mb-4 rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden animate-pulse">
        <div className="h-10 bg-gray-100 border-b border-gray-200" />
        <div className="grid grid-cols-4 divide-x border-b">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="p-4 space-y-2">
              <div className="h-2 w-16 bg-gray-100 rounded" />
              <div className="h-5 w-20 bg-gray-200 rounded" />
            </div>
          ))}
        </div>
        <div className="p-4 space-y-2">
          {[...Array(5)].map((_, i) => <div key={i} className="h-4 bg-gray-100 rounded w-full" />)}
        </div>
      </div>
    );
  }

  // ── No order ID case ──────────────────────────────────────────────────────
  if (!hasOrderId) {
    return (
      <div className="mb-4 rounded-xl border border-amber-200 bg-amber-50 p-4">
        <p className="text-sm font-semibold text-amber-700 mb-1">No Shopify order linked</p>
        <p className="text-xs text-amber-600">
          This ticket does not have a Shopify order ID. Admin actions cannot be executed until the order is linked.
        </p>
        <div className="mt-3 border-t border-amber-200 pt-3">
          {renderActionButtons()}
          {actionError && <p className="text-xs text-red-600 mt-2">{actionError}</p>}
        </div>
      </div>
    );
  }

  // ── GraphQL error case ────────────────────────────────────────────────────
  if (detailsError) {
    return (
      <div className="mb-4 rounded-xl border border-red-200 bg-red-50 p-4">
        <div className="flex items-center gap-2 text-red-600 mb-2">
          <AlertTriangle size={15} />
          <span className="text-sm font-semibold">Could not load Shopify order</span>
        </div>
        <p className="text-xs text-red-500 mb-3">{detailsError}</p>
        <div className="flex gap-2">
          <button onClick={loadDetails} className="text-xs text-red-600 hover:underline flex items-center gap-1">
            <RefreshCw size={12} /> Retry
          </button>
        </div>
      </div>
    );
  }

  const { order, tracking, inventory, policy } = details || {};

  // ── Full panel render ─────────────────────────────────────────────────────
  return (
    <div className="mb-4 rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden text-sm">

      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-gray-100 bg-white">
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400 font-medium">
            Ticket #{ticket?.id?.slice(-6)?.toUpperCase()} ·
          </span>
          <span className="text-xs font-semibold text-gray-700 capitalize">
            {pat ? `${pat} Request` : 'Request'}
          </span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs font-medium text-gray-700">
            {ticket?.customer_name} · #{orderNum}
          </span>
          {isAutoChannel && (
            <span className="flex items-center gap-1 text-xs text-green-600 font-medium">
              <span className="w-1.5 h-1.5 rounded-full bg-green-500 inline-block" />
              Autonomous
            </span>
          )}
          <button
            onClick={loadDetails}
            className="text-xs text-gray-400 hover:text-gray-600 flex items-center gap-0.5"
          >
            <RefreshCw size={11} />
          </button>
        </div>
      </div>

      {/* ── Stats row ───────────────────────────────────────────────────── */}
      <div className="grid grid-cols-4 divide-x divide-gray-100 border-b border-gray-100">
        <div className="px-4 py-3">
          <p className="text-xs text-gray-400 mb-0.5">Order value</p>
          <p className="text-lg font-semibold text-gray-900">{fmt(order?.total_price)}</p>
        </div>
        <div className="px-4 py-3">
          <p className="text-xs text-gray-400 mb-0.5">Order date</p>
          <p className="text-lg font-semibold text-gray-900">{order?.formatted_date || '—'}</p>
        </div>
        <div className="px-4 py-3">
          <p className="text-xs text-gray-400 mb-0.5">Refund window</p>
          <p className={clsx('text-base font-semibold', details?.refund_window_days_left > 0 ? 'text-amber-500' : 'text-red-500')}>
            {details?.refund_window_days_left > 0
              ? `${details.refund_window_days_left} days left`
              : 'Expired'}
          </p>
        </div>
        <div className="px-4 py-3">
          <p className="text-xs text-gray-400 mb-0.5">Orders (customer)</p>
          <p className="text-lg font-semibold text-gray-900">{details?.customer_order_count ?? '—'}</p>
        </div>
      </div>

      {/* ── Tracking + Inventory ────────────────────────────────────────── */}
      <div className="grid grid-cols-2 divide-x divide-gray-100 border-b border-gray-100">
        {/* Order tracking */}
        <div className="px-4 py-3">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2.5">
            Order Tracking
          </p>
          <div className="space-y-2">
            {(tracking || []).map((step, i) => (
              <div key={i} className="flex items-center gap-2.5">
                <TrackingDot done={step.done} />
                <span className={clsx('flex-1', step.done ? 'text-gray-700' : 'text-gray-300')}>
                  {step.label}
                </span>
                {step.date && (
                  <span className="text-xs text-gray-400 shrink-0">{step.date}</span>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Inventory */}
        <div className="px-4 py-3">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2.5">
            Inventory Status
          </p>
          {(inventory || []).length === 0 ? (
            <p className="text-xs text-gray-400">No line items found.</p>
          ) : (
            <div className="space-y-3">
              {inventory.map((item, i) => (
                <div key={i} className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <p className="text-gray-800 font-medium leading-snug truncate">{item.title}</p>
                    {item.variant_title && (
                      <p className="text-xs text-gray-400">{item.variant_title}</p>
                    )}
                    <div className="flex items-center gap-3 mt-1">
                      <span className="text-xs text-gray-500">Stock</span>
                      <span className={clsx(
                        'text-xs font-medium',
                        item.available > 0 ? 'text-green-600' : 'text-red-500',
                      )}>
                        {item.stock_label}
                      </span>
                    </div>
                  </div>
                  <div className="text-right shrink-0">
                    <p className="text-xs text-gray-500">×{item.quantity}</p>
                    <p className="text-sm font-semibold text-gray-800">{fmt(item.price)}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── Policy eligibility checks ────────────────────────────────────── */}
      <div className="px-4 py-3 border-b border-gray-100">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
          Policy Eligibility Checks
        </p>
        {policy ? (
          <div>
            <PolicyRow label={`Within refund window (${_REFUND_WINDOW_DAYS} days)`}
              value={policy.refund_window?.label}  color={policy.refund_window?.color} />
            <PolicyRow label={`Reason — ${(ticket?.pending_action_issue || 'other').replace(/_/g, ' ')}`}
              value={policy.reason?.label}          color={policy.reason?.color} />
            <PolicyRow label="Return pickup initiated"
              value={policy.pickup?.label}          color={policy.pickup?.color} />
            <PolicyRow label="Payment status"
              value={policy.payment_status?.label}  color={policy.payment_status?.color} />
            <PolicyRow label="Refund eligible"
              value={policy.refund_eligible?.label} color={policy.refund_eligible?.color} />
            <PolicyRow label="Cancel eligible"
              value={policy.cancel_eligible?.label} color={policy.cancel_eligible?.color} />
            <PolicyRow label="Customer refund history"
              value={policy.refund_history?.label}  color={policy.refund_history?.color} />
            <PolicyRow label="24h messaging window"
              value={policy.messaging_window?.label} color={policy.messaging_window?.color} />
          </div>
        ) : (
          <p className="text-xs text-gray-400">Policy data unavailable.</p>
        )}
      </div>

      {/* ── Action buttons ───────────────────────────────────────────────── */}
      <div className="px-4 py-3">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2.5">
          {pat === 'cancel' ? 'Cancel Actions' : 'Refund / Return Actions'}
        </p>
        {renderActionButtons()}
        {actionError && (
          <div className="mt-2 flex items-start gap-1.5 text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
            <AlertTriangle size={12} className="shrink-0 mt-0.5" />
            <span>{actionError}</span>
            <button onClick={() => setActionE(null)} className="ml-auto shrink-0 text-red-400 hover:text-red-600">
              ✕
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
