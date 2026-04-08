// AiBanner.jsx — unified AI analysis dashboard panel
// Design matches reference HTML files: header, summary, metrics, timeline, inventory, policy, actions
import { useState, useEffect, useRef, useCallback } from 'react'
import clsx from 'clsx'
import { ordersApi, shopifyApi, returnsApi, ticketsApi } from '../api/client'

// ── ProductSelectorInput (exported — used in action forms) ────────────────────
export function ProductSelectorInput({ value, onTextChange, onSelect }) {
  const [query, setQuery] = useState(value || '')
  const [results, setResults] = useState([])
  const [searchLoading, setSearchLoading] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [hasMore, setHasMore] = useState(false)
  const [lastProductId, setLastProductId] = useState(null)
  const [open, setOpen] = useState(false)
  const searchRef = useRef(null)
  const dropdownRef = useRef(null)

  async function fetchProducts(q = '', sinceId = '') {
    if (sinceId) setLoadingMore(true)
    else setSearchLoading(true)
    try {
      const res = await ordersApi.searchProducts(q, 250, sinceId)
      const data = res.data
      if (sinceId) setResults(prev => [...prev, ...(data.products || [])])
      else setResults(data.products || [])
      setHasMore(data.has_more || false)
      setLastProductId(data.last_product_id || null)
      setOpen(true)
    } catch {
      if (!sinceId) setResults([])
    } finally {
      setSearchLoading(false)
      setLoadingMore(false)
    }
  }

  useEffect(() => { fetchProducts('') }, [])
  useEffect(() => { setQuery(value || '') }, [value])
  useEffect(() => {
    const t = setTimeout(() => { setLastProductId(null); fetchProducts(query) }, 300)
    return () => clearTimeout(t)
  }, [query])
  useEffect(() => {
    function handle(e) {
      if (searchRef.current && !searchRef.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', handle)
    return () => document.removeEventListener('mousedown', handle)
  }, [])

  const handleDropdownScroll = useCallback(() => {
    const el = dropdownRef.current
    if (!el || loadingMore || !hasMore) return
    if (el.scrollTop + el.clientHeight >= el.scrollHeight - 40) fetchProducts(query, lastProductId)
  }, [loadingMore, hasMore, lastProductId, query])

  return (
    <div className="relative flex-1" ref={searchRef}>
      <div className="relative">
        <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-4.35-4.35M17 11A6 6 0 1 1 5 11a6 6 0 0 1 12 0z" />
        </svg>
        <input type="text" value={query}
          onChange={e => { setQuery(e.target.value); onTextChange(e.target.value) }}
          onFocus={() => setOpen(true)}
          placeholder="Search products to add..."
          className="w-full pl-10 pr-4 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
        {searchLoading && <div className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 border-2 border-gray-200 border-t-brand-600 rounded-full animate-spin" />}
      </div>
      {open && (
        <div ref={dropdownRef} onScroll={handleDropdownScroll}
          className="absolute left-0 right-0 top-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-50 max-h-72 overflow-y-auto">
          {searchLoading && results.length === 0 ? (
            <div className="flex items-center justify-center py-4">
              <div className="w-5 h-5 border-2 border-gray-200 border-t-brand-600 rounded-full animate-spin" />
            </div>
          ) : results.length === 0 ? (
            <p className="px-4 py-3 text-sm text-gray-400">No products found</p>
          ) : (
            <>
              {results.map(p => (
                <button key={p.variant_id} type="button" onMouseDown={e => e.preventDefault()}
                  onClick={() => { setQuery(p.title); onTextChange(p.title); onSelect(p); setOpen(false) }}
                  className="w-full text-left flex items-center gap-3 px-4 py-2.5 hover:bg-gray-50 border-b border-gray-50 last:border-0 transition-colors">
                  <div className="w-10 h-10 rounded bg-gray-100 shrink-0 overflow-hidden">
                    {p.image ? <img src={p.image} alt="" className="w-full h-full object-cover" /> : <div className="w-full h-full flex items-center justify-center text-gray-300 text-xs">N/A</div>}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900 truncate">{p.title}</p>
                    <p className="text-xs text-gray-500">
                      ${p.price}<span className="mx-1">·</span>
                      <span className={p.inventory_quantity > 0 ? 'text-green-600' : 'text-red-500'}>
                        {p.inventory_quantity > 0 ? `${p.inventory_quantity} in stock` : 'Out of stock'}
                      </span>
                      {p.sku && <span className="ml-1 text-gray-400">· {p.sku}</span>}
                    </p>
                  </div>
                </button>
              ))}
              {loadingMore && <p className="px-4 py-2 text-xs text-gray-400 text-center">Loading more...</p>}
              {hasMore && !loadingMore && <p className="px-4 py-2 text-xs text-gray-300 text-center">Scroll for more</p>}
            </>
          )}
        </div>
      )}
    </div>
  )
}

// ── Constants ─────────────────────────────────────────────────────────────────
const ACTION_ICONS = {
  CANCEL_ORDER: '🚫', CREATE_ORDER: '🛒', UPDATE_ORDER: '✏️', DELETE_ORDER: '🗑️',
  UPDATE_CUSTOMER_ADDRESS: '📍', TRACK_ORDER: '📦', REFUND_ORDER: '💰',
  UPDATE_CUSTOMER_DETAILS: '👤',
  cancel_order: '🚫', create_order: '🛒', update_order: '✏️', delete_order: '🗑️',
  change_address: '📍', track_order: '📦', refund_order: '💰', contact_support: '📞',
}

const TICKET_TYPE_LABEL = {
  refund: 'Refund Request',
  return: 'Return Request',
  replace: 'Replacement Request',
  cancel: 'Cancellation Request',
  cancel_requested: 'Cancellation Request',
  shipping: 'Shipping Issue',
  order_status: 'Order Status',
  billing: 'Billing Issue',
  product_inquiry: 'Product Inquiry',
  technical: 'Technical Issue',
  general: 'General Inquiry',
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function computePolicies(shopifyOrder, selectedTicket, returnPolicyData = null) {
  if (!shopifyOrder) return []
  const isCancelled = !!shopifyOrder.cancelled_at
  const isPaid = shopifyOrder.financial_status === 'paid'
  const isRefunded = ['refunded', 'partially_refunded'].includes(shopifyOrder.financial_status)
  const isUnfulfilled = !shopifyOrder.fulfillment_status || shopifyOrder.fulfillment_status === 'unfulfilled'

  const policies = []

  // ── Window check — label adapts to ticket type ──
  const ticketType = selectedTicket?.ticket_type || selectedTicket?.pending_action_type
  const windowLabel = ticketType === 'replace' || ticketType === 'replacement'
    ? 'Replacement window'
    : ticketType === 'refund'
      ? 'Refund window'
      : 'Return window'

  if (returnPolicyData?.return_window) {
    const rw = returnPolicyData.return_window
    const daysRemaining = Math.max(0, rw.days - (rw.days_since_baseline ?? rw.days))
    policies.push({
      label: `Within ${windowLabel.toLowerCase()} (${rw.days} days)`,
      pass: rw.pass === true,
      warn: false,
      detail: rw.pass === null ? 'N/A'
        : rw.pass ? `${daysRemaining} day${daysRemaining !== 1 ? 's' : ''} left`
        : 'Expired',
    })
  } else {
    // Fallback only while backend data is loading — no hardcoded window
    policies.push({
      label: windowLabel,
      pass: false,
      warn: true,
      detail: 'Loading policy…',
    })
  }

  // ── Reason eligibility (backend only — shown for return tickets) ──
  if (returnPolicyData?.reason_eligibility) {
    const re = returnPolicyData.reason_eligibility
    policies.push({
      label: `Reason — ${(re.reason || '').replace(/_/g, ' ')}`,
      pass: re.status === 'eligible',
      warn: re.status === 'review',
      detail: re.label || re.status,
    })
  }

  // ── Return pickup initiated (backend only) ──
  if (returnPolicyData?.pickup_initiated) {
    const pi = returnPolicyData.pickup_initiated
    policies.push({
      label: 'Return pickup initiated',
      pass: pi.pass,
      warn: !pi.pass,
      detail: pi.current_status || (pi.pass ? 'Yes' : 'Pending'),
    })
  }

  // ── Order-level checks (always shown) ──
  policies.push(
    {
      label: isPaid ? 'Payment confirmed' : 'Payment status',
      pass: isPaid,
      warn: shopifyOrder.financial_status === 'pending',
      detail: shopifyOrder.financial_status === 'refunded'
        ? 'Already refunded'
        : shopifyOrder.financial_status === 'partially_refunded'
        ? 'Partially refunded'
        : shopifyOrder.financial_status === 'voided'
        ? 'Payment voided'
        : isPaid ? 'Paid' : `Status: ${shopifyOrder.financial_status}`,
    },
    {
      label: 'Refund eligible',
      pass: isPaid && !isCancelled && !isRefunded,
      warn: false,
      detail: isRefunded ? 'Already refunded' : isCancelled ? 'Order cancelled' : isPaid ? 'Eligible' : 'Not paid',
    },
    {
      label: 'Cancel eligible',
      pass: !isCancelled && isUnfulfilled,
      warn: !isCancelled && !isUnfulfilled,
      detail: isCancelled ? 'Already cancelled' : isUnfulfilled ? 'Unfulfilled — can cancel' : 'Fulfilled — cannot cancel',
    },
  )

  // ── Customer history — show relevant count based on ticket type ──
  const isReplace = ticketType === 'replace' || ticketType === 'replacement'
  const isRefund = ticketType === 'refund'
  const isReturn = ticketType === 'return'

  if (isReplace && returnPolicyData?.prior_replacements != null) {
    const count = returnPolicyData.prior_replacements.count
    policies.push({
      label: 'Customer replacement history',
      pass: count === 0,
      warn: count > 0 && count <= 2,
      detail: count === 0 ? 'No prior replacements' : `${count} prior replacement${count !== 1 ? 's' : ''}`,
    })
  } else if (isRefund && returnPolicyData?.prior_refunds != null) {
    const count = returnPolicyData.prior_refunds.count
    policies.push({
      label: 'Customer refund history',
      pass: count === 0,
      warn: count > 0 && count <= 2,
      detail: count === 0 ? 'No prior refunds' : `${count} prior refund${count !== 1 ? 's' : ''}`,
    })
  } else if (isReturn && (returnPolicyData?.prior_returns_tickets != null || returnPolicyData?.prior_returns != null)) {
    const count = returnPolicyData.prior_returns_tickets?.count ?? returnPolicyData.prior_returns?.count ?? 0
    policies.push({
      label: 'Customer return history',
      pass: count === 0,
      warn: count > 0 && count <= 2,
      detail: count === 0 ? 'No prior returns' : `${count} prior return${count !== 1 ? 's' : ''}`,
    })
  } else if (returnPolicyData?.prior_returns != null) {
    // Fallback for other ticket types — show general return history
    const count = returnPolicyData.prior_returns.count
    policies.push({
      label: 'Customer return history',
      pass: count === 0,
      warn: count > 0 && count <= 2,
      detail: count === 0 ? 'No prior returns' : `${count} prior return${count !== 1 ? 's' : ''}`,
    })
  }

  // ── WhatsApp 24h window ──
  if (selectedTicket?.channel === 'whatsapp' && selectedTicket?.whatsapp_last_customer_msg_at) {
    const hoursAgo = (Date.now() - new Date(selectedTicket.whatsapp_last_customer_msg_at).getTime()) / (1000 * 60 * 60)
    const within = hoursAgo < 24
    policies.push({
      label: '24h messaging window',
      pass: within,
      warn: !within,
      detail: within ? `Active — ${hoursAgo.toFixed(1)}h since last msg` : `Expired — ${Math.round(hoursAgo)}h ago (templates only)`,
    })
  }

  return policies
}

function buildTimeline(shopifyOrder) {
  if (!shopifyOrder) return []
  const isPaid = ['paid', 'partially_refunded', 'refunded', 'partially_paid'].includes(shopifyOrder.financial_status)
  const isPending = shopifyOrder.financial_status === 'pending'
  const isCancelled = !!shopifyOrder.cancelled_at
  const isFulfilled = shopifyOrder.fulfillment_status === 'fulfilled'
  const isPartial = shopifyOrder.fulfillment_status === 'partial'
  const isUnfulfilled = !shopifyOrder.fulfillment_status || shopifyOrder.fulfillment_status === 'unfulfilled'
  const latestFulfillment = shopifyOrder.fulfillments?.[shopifyOrder.fulfillments.length - 1]
  const isDelivered = isFulfilled && latestFulfillment?.status === 'success'

  const fmt = (d) => d ? new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : null

  if (isCancelled) {
    return [
      { label: 'Order placed', date: fmt(shopifyOrder.created_at), status: 'done' },
      { label: 'Order cancelled', date: fmt(shopifyOrder.cancelled_at), status: 'fail' },
    ]
  }

  return [
    { label: 'Order placed', date: fmt(shopifyOrder.created_at), status: 'done' },
    { label: 'Payment confirmed', date: isPaid ? fmt(shopifyOrder.processed_at || shopifyOrder.created_at) : null, status: isPaid ? 'done' : isPending ? 'active' : 'pending' },
    { label: 'Processing', date: null, status: (isPaid && !isUnfulfilled) || isFulfilled || isPartial ? 'done' : isPaid ? 'active' : 'pending' },
    {
      label: isPartial ? 'Partially shipped' : isFulfilled ? 'Shipped' : 'Awaiting shipment',
      date: latestFulfillment ? fmt(latestFulfillment.created_at) : null,
      status: isFulfilled || isPartial ? 'done' : isPaid && !isUnfulfilled ? 'active' : 'pending',
    },
    {
      label: isDelivered ? 'Delivered' : 'Delivery',
      date: null,
      status: isDelivered ? 'done' : isFulfilled ? 'active' : 'pending',
    },
  ]
}

// ── Status badge ──────────────────────────────────────────────────────────────
function PolicyBadge({ pass, warn, detail }) {
  if (pass) return <span className="text-xs font-medium px-2.5 py-0.5 rounded-full bg-green-50 text-green-700">{detail}</span>
  if (warn) return <span className="text-xs font-medium px-2.5 py-0.5 rounded-full bg-yellow-50 text-yellow-700">{detail}</span>
  return <span className="text-xs font-medium px-2.5 py-0.5 rounded-full bg-red-50 text-red-600">{detail}</span>
}

// ── Timeline dot ──────────────────────────────────────────────────────────────
function TimelineDot({ status }) {
  return (
    <span className={clsx(
      'w-2 h-2 rounded-full shrink-0 mt-1',
      status === 'done' && 'bg-green-500',
      status === 'active' && 'bg-orange-400',
      status === 'fail' && 'bg-red-400',
      status === 'pending' && 'bg-gray-200',
    )} />
  )
}

// ── Card wrapper ──────────────────────────────────────────────────────────────
function Card({ title, children, className = '' }) {
  return (
    <div className={clsx('bg-white border border-gray-100 rounded-xl p-4', className)}>
      {title && <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">{title}</p>}
      {children}
    </div>
  )
}

// ── Action confirmation panel ─────────────────────────────────────────────────
function ActionPanel({ action, index, actionResult, executeAction, getFieldValue, handleFieldChange, onClose }) {
  const result = actionResult[index]
  return (
    <div className="mt-3 bg-gray-50 border border-gray-200 rounded-xl p-4 space-y-3">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-semibold text-gray-900">{action.label}</p>
          {action.description && <p className="text-xs text-gray-500 mt-0.5">{action.description}</p>}
        </div>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600 ml-2 shrink-0">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {action.extracted_data && Object.keys(action.extracted_data).length > 0 && (
        <div className="space-y-2 border-t border-gray-100 pt-3">
          <p className="text-xs text-gray-400">Confirm or fill details before executing</p>
          {Object.entries(action.extracted_data).map(([field, aiValue]) => {
            const isProductField = action.type === 'CREATE_ORDER' && field === 'product_name'
            return (
              <div key={field} className={isProductField ? 'space-y-1' : 'flex items-center gap-3'}>
                <label className="text-xs text-gray-500 w-36 shrink-0 capitalize">{field.replace(/_/g, ' ')}</label>
                {isProductField ? (
                  <ProductSelectorInput
                    value={getFieldValue(index, field, aiValue)}
                    onTextChange={val => handleFieldChange(index, field, val)}
                    onSelect={p => {
                      handleFieldChange(index, 'product_name', p.title)
                      handleFieldChange(index, 'price', p.price)
                      handleFieldChange(index, 'variant_id', p.variant_id)
                    }}
                  />
                ) : (
                  <input type="text"
                    value={getFieldValue(index, field, aiValue)}
                    onChange={e => handleFieldChange(index, field, e.target.value)}
                    placeholder={aiValue == null ? 'not found — enter manually' : ''}
                    className="flex-1 text-xs border border-gray-200 rounded-md px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-purple-400 bg-white placeholder-gray-300" />
                )}
              </div>
            )
          })}
        </div>
      )}

      {result?.trackingData && (
        <div className="rounded-lg border border-blue-200 bg-blue-50 p-3 space-y-2">
          <p className="text-xs font-semibold text-blue-700">Shipment Tracking</p>
          <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
            {result.trackingData.company && <><span className="text-gray-500">Carrier</span><span className="font-medium">{result.trackingData.company}</span></>}
            <span className="text-gray-500">Tracking #</span><span className="font-mono font-medium break-all">{result.trackingData.number}</span>
            {result.trackingData.status && <><span className="text-gray-500">Status</span><span className="font-medium capitalize">{result.trackingData.status}</span></>}
          </div>
          {result.trackingData.url && (
            <a href={result.trackingData.url} target="_blank" rel="noopener noreferrer"
              className="flex items-center justify-center gap-1.5 w-full py-1.5 rounded-lg bg-blue-600 text-white text-xs font-semibold hover:bg-blue-700 transition-colors">
              Track Shipment →
            </a>
          )}
        </div>
      )}

      {result?.success && !result.trackingData && (
        <div className="flex items-center gap-2 text-xs text-green-700 bg-green-50 border border-green-200 rounded-lg px-3 py-2">
          <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
          {result.success}
        </div>
      )}

      {result?.error && (
        <div className="rounded-lg bg-red-50 border border-red-200 px-3 py-2 space-y-1.5">
          <p className="text-xs text-red-700">{result.error}</p>
          <button onClick={() => executeAction(action, index)} className="text-xs text-red-600 underline">Retry</button>
        </div>
      )}

      {!result?.success && (
        <button onClick={() => executeAction(action, index)} disabled={result?.loading}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-purple-600 hover:bg-purple-700 text-white text-sm font-medium disabled:opacity-60 transition-colors">
          {result?.loading ? (
            <><div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />Executing…</>
          ) : (
            <><span>{ACTION_ICONS[action.type] || '⚡'}</span>Execute: {action.label}</>
          )}
        </button>
      )}
    </div>
  )
}

// ── Quick action configs ───────────────────────────────────────────────────────
function getQuickActions(selectedTicket, shopifyOrder) {
  const isPaymentPending = shopifyOrder?.financial_status === 'pending'
  const ticketType = selectedTicket?.ticket_type
  const pendingType = selectedTicket?.pending_action_type
  const id = selectedTicket?.id?.slice(-6).toUpperCase() || '—'
  const currency = shopifyOrder?.currency === 'INR' ? '₹' : '$'
  const amount = shopifyOrder?.total_price || '0'
  const itemName = shopifyOrder?.line_items?.[0]?.title || 'item'
  const subject = (selectedTicket?.subject || '').toLowerCase()

  // Subject-based detection takes priority over ticket_type (AI classification can be wrong)
  const subjectIsReplace = subject.includes('replacement') || subject.includes('replace')
  const subjectIsRefund = !subjectIsReplace && subject.includes('refund')
  const subjectIsReturn = !subjectIsReplace && subject.includes('return')

  const isReplace = ticketType === 'replace' || pendingType === 'replace' || subjectIsReplace

  const isRefundReturn = !isReplace && (
    ['return', 'refund', 'cancel_requested', 'cancel'].includes(ticketType)
    || subjectIsRefund || subjectIsReturn
  )
  
  if (isReplace) {
    return {
      type: 'replace',
      enabled: true,
      buttons: [
        { id: 'approve',       label: 'Approve replacement', variant: 'primary-blue',  action: 'approve', prompt: `Ticket #${id} ke liye replacement approve karo — ${itemName}` },
        { id: 'refund_instead',label: 'Refund instead',      variant: 'secondary',     prompt: `Ticket #${id} ke liye full refund process karo instead of replacement` },
        { id: 'escalate_qc',   label: 'Escalate to QC',      variant: 'secondary',     prompt: `Ticket #${id} ke liye QC team ko inspect karne bhejo` },
        { id: 'wait_pickup',   label: 'Wait for pickup',     variant: 'amber',         prompt: `Ticket #${id} ke liye pickup confirm hone ke baad replacement dispatch karo` },
      ],
    }
  }

  if (isRefundReturn) {
    return {
      type: 'refund',
      enabled: true,
      paymentPending: isPaymentPending,
      currency,
      amount,
      buttons: [
        { id: 'full_refund',   label: `Full refund ${currency}${amount}`, variant: 'primary-green', prompt: `Ticket #${id} ke liye full refund ${currency}${amount} process karo` },
        { id: 'partial_refund',label: 'Partial refund',                   variant: 'secondary',     prompt: `Ticket #${id} ke liye partial refund options suggest karo` },
        { id: 'exchange',      label: 'Exchange offer',                   variant: 'secondary',     prompt: `Ticket #${id} ke liye exchange option create karo` },
        { id: 'wait_return',   label: 'Wait for return',                  variant: 'amber',         prompt: `Ticket #${id} ke liye return aane tak hold pe rakho` },
      ],
    }
  }

  // No recognised request type — return placeholder set in disabled state
  if (process.env.NODE_ENV !== 'production') {
    console.warn('[AiBanner] Request type not determined for ticket type:', ticketType, pendingType)
  }
  return {
    type: 'pending',
    enabled: false,
    buttons: [
      { id: 'full_refund',    label: 'Full refund',    variant: 'primary-green' },
      { id: 'partial_refund', label: 'Partial refund', variant: 'secondary' },
      { id: 'exchange',       label: 'Exchange offer',  variant: 'secondary' },
      { id: 'wait_return',    label: 'Wait for return', variant: 'amber' },
    ],
  }
}

// ── Main component ─────────────────────────────────────────────────────────────
export default function AiBanner({
  aiResult,
  aiLoading,
  aiError,
  aiProcessResult,
  selectedTicket,
  shopifyOrder,
  shopifyCustomer,
  actionResult,
  activeActionIndex,
  setActiveActionIndex,
  executeAction,
  handleAnalyze,
  handleProcessTicket,
  getFieldValue,
  handleFieldChange,
  inventory,
  inventoryLoading,
  inventoryError,
  onRetryInventory,
  sendPrompt,
  approveAction,
  onClear,
}) {
  // ── Backend return policy state (must be declared before use in computePolicies) ──
  const [returnPolicyData, setReturnPolicyData] = useState(null)
  const [returnPolicyLoading, setReturnPolicyLoading] = useState(false)

  const isWhatsApp = selectedTicket?.channel === 'whatsapp'
  const policies = computePolicies(shopifyOrder, selectedTicket, returnPolicyData)
  const timeline = buildTimeline(shopifyOrder)

  // ── Quick-action local state ──────────────────────────────────────────────
  const [refundLoading, setRefundLoading] = useState(false)
  const [refundSuccess, setRefundSuccess] = useState(null)
  const [refundError, setRefundError] = useState(null)

  // Partial refund modal
  const [showPartialModal, setShowPartialModal] = useState(false)
  const [partialAmount, setPartialAmount] = useState('')
  const [partialReason, setPartialReason] = useState('')
  const [partialLoading, setPartialLoading] = useState(false)
  const [partialError, setPartialError] = useState(null)
  const [partialSuccess, setPartialSuccess] = useState(null)

  // Exchange panel
  const [showExchangePanel, setShowExchangePanel] = useState(false)
  const [exchangeVariants, setExchangeVariants] = useState([])
  const [exchangeVariantsLoading, setExchangeVariantsLoading] = useState(false)
  const [exchangeVariantsError, setExchangeVariantsError] = useState(null)
  const [selectedExchangeVariant, setSelectedExchangeVariant] = useState(null)
  const [exchangeLoading, setExchangeLoading] = useState(false)
  const [exchangeSuccess, setExchangeSuccess] = useState(null)
  const [exchangeError, setExchangeError] = useState(null)

  // Replacement approval
  const [replacementLoading, setReplacementLoading] = useState(false)
  const [replacementSuccess, setReplacementSuccess] = useState(null)   // new order name e.g. "#1749"
  const [replacementError, setReplacementError] = useState(null)

  useEffect(() => {
    const RETURN_TICKET_TYPES = ['return', 'refund', 'replacement', 'replace', 'cancel', 'cancel_requested']
    if (!shopifyOrder?.id || !RETURN_TICKET_TYPES.includes(selectedTicket?.ticket_type)) {
      setReturnPolicyData(null)
      return
    }
    let cancelled = false
    setReturnPolicyLoading(true)
    returnsApi.listByOrder(shopifyOrder.id)
      .then(async res => {
        const returns = res.data || []
        if (cancelled) return
        if (returns.length) {
          // Full policy check when a return record exists
          const policyRes = await returnsApi.policyCheck(returns[0].id)
          if (!cancelled) setReturnPolicyData(policyRes.data)
        } else {
          // Order-level policy check (return/replacement/refund window + payment status)
          const policyRes = await returnsApi.orderPolicyCheck(shopifyOrder.id, {
            ticket_type: selectedTicket?.ticket_type || undefined,
            customer_email: selectedTicket?.customer_email || undefined,
          })
          if (!cancelled) setReturnPolicyData(policyRes.data)
        }
      })
      .catch(() => { if (!cancelled) setReturnPolicyData(null) })
      .finally(() => { if (!cancelled) setReturnPolicyLoading(false) })
    return () => { cancelled = true }
  }, [selectedTicket?.id, shopifyOrder?.id])

  // ── Auto-resolve ticket after successful action ───────────────────────────
  async function resolveTicket() {
    if (!selectedTicket?.id) return
    try {
      await ticketsApi.update(selectedTicket.id, { status: 'resolved' })
    } catch (err) {
      console.error('[AiBanner] Failed to resolve ticket:', err)
    }
  }

  // Prevent body scroll when modal is open
  useEffect(() => {
    document.body.style.overflow = showPartialModal ? 'hidden' : ''
    return () => { document.body.style.overflow = '' }
  }, [showPartialModal])

  // ── Approve replacement handler ──────────────────────────────────────────
  async function handleApproveReplacement(qa) {
    if (!shopifyOrder?.id || replacementLoading || replacementSuccess) return
    if (!shopifyOrder.customer_id) {
      setReplacementError('Cannot create replacement — customer ID missing from order.')
      return
    }
    setReplacementLoading(true)
    setReplacementError(null)
    try {
      const lineItems = (shopifyOrder.line_items || []).map(li => ({
        title: li.title || 'Item',
        quantity: li.quantity || 1,
        price: '0.00',                          // free replacement — customer pays nothing
        variant_id: li.variant_id || null,
      }))
      const originalOrderName = shopifyOrder.name || `#${shopifyOrder.order_number}`
      const res = await ordersApi.create({
        customer_id: shopifyOrder.customer_id,
        line_items: lineItems,
        note: `Replacement for ${originalOrderName} — approved by agent`,
        tags: 'replacement',
        financial_status: 'paid',               // marked paid so no customer payment needed
        merchant_id: selectedTicket?.merchant_id || null,
      })
      const newOrderName = res.data?.name || res.data?.order_number ? `#${res.data.order_number}` : 'created'
      setReplacementSuccess(`Replacement order ${newOrderName} created — ready to fulfill`)
      await resolveTicket()
      if (sendPrompt && qa?.buttons?.find(b => b.id === 'approve')?.prompt) {
        sendPrompt(qa.buttons.find(b => b.id === 'approve').prompt)
      }
    } catch (err) {
      const msg = err?.response?.data?.detail || 'Failed to create replacement order'
      setReplacementError(msg)
    } finally {
      setReplacementLoading(false)
    }
  }

  // ── Full refund handler ───────────────────────────────────────────────────
  async function handleFullRefund(qa) {
    if (!shopifyOrder?.id || refundLoading || refundSuccess) return
    if (shopifyOrder.financial_status === 'pending') { setRefundError('Cannot refund — payment is still pending'); return }
    setRefundLoading(true)
    setRefundError(null)
    try {
      await ordersApi.refund(shopifyOrder.id, {
        line_items: (shopifyOrder.line_items || []).map(li => ({
          line_item_id: li.id,
          quantity: li.quantity,
          restock: true,
        })),
        shipping_full_refund: true,
        notify: true,
      })
      setRefundSuccess(`Refund of ${qa.currency}${qa.amount} processed successfully`)
      await resolveTicket()
      if (sendPrompt) sendPrompt(`Ticket #${selectedTicket?.id?.slice(-6).toUpperCase()} ke liye full refund ${qa.currency}${qa.amount} process ho gaya hai`)
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Refund failed'
      setRefundError(typeof msg === 'object' ? JSON.stringify(msg) : String(msg))
    } finally {
      setRefundLoading(false)
    }
  }

  // ── Partial refund handler ────────────────────────────────────────────────
  async function handlePartialRefund(qa) {
    const amt = parseFloat(partialAmount)
    const max = parseFloat(qa?.amount || '0')
    if (!amt || amt <= 0 || amt > max) { setPartialError(`Enter an amount between ${qa?.currency}1 and ${qa?.currency}${max}`); return }
    if (!shopifyOrder?.id) { setPartialError('Order not loaded'); return }
    if (shopifyOrder.financial_status === 'pending') { setPartialError('Cannot refund — payment is still pending'); return }
    setPartialLoading(true)
    setPartialError(null)
    try {
      await ordersApi.refund(shopifyOrder.id, {
        custom_amount: partialAmount,
        note: partialReason || undefined,
        notify: true,
      })
      setPartialSuccess(`Partial refund of ${qa?.currency}${partialAmount} processed`)
      await resolveTicket()
      if (sendPrompt) sendPrompt(`Ticket #${selectedTicket?.id?.slice(-6).toUpperCase()} ke liye partial refund ${qa?.currency}${partialAmount} process ho gaya hai`)
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Refund failed'
      setPartialError(typeof msg === 'object' ? JSON.stringify(msg) : String(msg))
    } finally {
      setPartialLoading(false)
    }
  }

  // ── Exchange: fetch variants for first line item's product ────────────────
  async function openExchangePanel() {
    const productId = shopifyOrder?.line_items?.[0]?.product_id
    setShowExchangePanel(true)
    setSelectedExchangeVariant(null)
    setExchangeSuccess(null)
    setExchangeError(null)
    if (!productId) {
      setExchangeVariants([])
      setExchangeVariantsError('Product ID not available — connect Shopify Product API for live variants')
      return
    }
    setExchangeVariantsLoading(true)
    setExchangeVariantsError(null)
    try {
      const res = await shopifyApi.getProductVariants(productId, selectedTicket?.merchant_id || null)
      setExchangeVariants(res.data.variants || [])
    } catch (err) {
      setExchangeVariantsError('Could not load product variants')
    } finally {
      setExchangeVariantsLoading(false)
    }
  }

  // ── Exchange: confirm (initiate return + create draft for new variant) ────
  async function handleConfirmExchange() {
    if (!selectedExchangeVariant || !shopifyOrder?.id) return
    setExchangeLoading(true)
    setExchangeError(null)
    try {
      const originalItem = shopifyOrder.line_items?.[0]
      const oldVariantTitle = originalItem?.variant_title || originalItem?.title || 'item'
      const newVariantTitle = selectedExchangeVariant.title

      // Step 1: cancel/return the original order line (cancel the order, restock)
      // Using ordersApi.cancel as a proxy for return initiation (full return flow requires
      // POST /returns which uses internal DB — use that if returns are tracked in your DB)
      // TODO: Replace with returnsApi.create() when the returns router is wired to frontend
      await ordersApi.refund(shopifyOrder.id, {
        line_items: [{ line_item_id: originalItem.id, quantity: originalItem.quantity, restock: true }],
        notify: true,
      })

      // Step 2: Create a draft order for the replacement variant
      await ordersApi.create({
        customer_id: shopifyOrder.customer_id || '',
        line_items: [{ variant_id: selectedExchangeVariant.id, quantity: 1, price: selectedExchangeVariant.price || '0.00', title: selectedExchangeVariant.title }],
        note: `Exchange from ticket #${selectedTicket?.id?.slice(-6).toUpperCase()} — ${oldVariantTitle} → ${newVariantTitle}`,
        tags: 'exchange',
      })

      setExchangeSuccess(`Exchange initiated: ${oldVariantTitle} → ${newVariantTitle}`)
      await resolveTicket()
      if (sendPrompt) sendPrompt(`Ticket #${selectedTicket?.id?.slice(-6).toUpperCase()} ke liye exchange process ho raha hai — ${oldVariantTitle} se ${newVariantTitle}`)
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Exchange failed'
      setExchangeError(typeof msg === 'object' ? JSON.stringify(msg) : String(msg))
    } finally {
      setExchangeLoading(false)
    }
  }
  // Dynamic return window from backend policy data
  const rw = returnPolicyData?.return_window
  const daysLeft = rw ? Math.max(0, rw.days - (rw.days_since_baseline ?? rw.days)) : null
  const topConfidence = aiResult?.actions?.length
    ? Math.max(...aiResult.actions.map(a => a.confidence || 0))
    : null

  const ticketTypeLabel = TICKET_TYPE_LABEL[selectedTicket?.ticket_type] || selectedTicket?.ticket_type || 'Support Request'
  const orderNumber = shopifyOrder?.name || (selectedTicket?.shopify_order_number ? `#${selectedTicket.shopify_order_number}` : null)
  const customerName = selectedTicket?.customer_name || selectedTicket?.customer_email || '—'

  return (
    <div className="mb-6 space-y-3">

      {/* ── WhatsApp process result ─────────────────────────────────────────── */}
      {aiProcessResult?.status === 'success' && (
        <div className={clsx('rounded-xl border px-4 py-3 space-y-2',
          aiProcessResult.reply_sent ? 'border-green-200 bg-green-50' : 'border-orange-200 bg-orange-50')}>
          <div className="flex items-center gap-2">
            <span className={clsx('text-xs font-semibold', aiProcessResult.reply_sent ? 'text-green-800' : 'text-orange-800')}>
              {aiProcessResult.reply_sent ? '✓ AI replied to customer via WhatsApp' : '⚠ AI reply generated — delivery failed'}
            </span>
          </div>
          {aiProcessResult.send_error && (
            <div className="bg-orange-100 border border-orange-200 rounded-lg px-3 py-2">
              <p className="text-xs font-medium text-orange-700 mb-0.5">Meta API error:</p>
              <p className="text-xs text-orange-800 font-mono break-all">{aiProcessResult.send_error}</p>
            </div>
          )}
          <div className="bg-white border border-gray-100 rounded-lg px-3 py-2">
            <p className="text-xs text-gray-500 mb-1">{aiProcessResult.reply_sent ? 'Sent:' : 'Generated (not delivered):'}</p>
            <p className="text-sm text-gray-800 whitespace-pre-wrap">{aiProcessResult.ai_reply}</p>
          </div>
          <button onClick={handleProcessTicket} disabled={aiLoading} className="text-xs text-gray-500 hover:text-gray-700 underline">Run again</button>
        </div>
      )}

      {/* ── AI error ─────────────────────────────────────────────────────────── */}
      {aiError && (
        <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 flex items-start gap-3">
          <svg className="w-4 h-4 text-red-500 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <div className="flex-1">
            <p className="text-sm font-medium text-red-700">AI analysis failed</p>
            <p className="text-xs text-red-600 mt-0.5">{aiError}</p>
          </div>
          <button onClick={handleAnalyze} className="text-xs text-red-600 hover:text-red-800 font-medium underline shrink-0">Retry</button>
        </div>
      )}

      {/* ── Main dashboard card ───────────────────────────────────────────────── */}
      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">

        {/* Header row */}
        <div className="flex items-start justify-between px-5 pt-5 pb-4 border-b border-gray-100">
          <div>
            <p className="text-xs text-gray-400 mb-1">
              {selectedTicket?.id ? `Ticket #${selectedTicket.id.slice(-6).toUpperCase()}` : 'Ticket'} · {ticketTypeLabel}
            </p>
            <p className="text-base font-semibold text-gray-900">
              {customerName}{orderNumber ? <span className="font-normal text-gray-500"> · {orderNumber}</span> : ''}
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0 ml-4">
            {aiResult ? (
              <>
                <span className="text-xs px-2.5 py-1 rounded-full bg-green-50 text-green-700 font-medium">AI Analysis Ready</span>
                <button onClick={onClear} className="text-xs text-gray-400 hover:text-gray-600 underline">Clear</button>
              </>
            ) : (
              isWhatsApp ? (
                <div className="flex items-center gap-2">
                  <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-green-50 border border-green-200 text-green-700 text-xs font-medium">
                    <span className="relative flex h-1.5 w-1.5">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
                      <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-green-500" />
                    </span>
                    Autonomous
                  </div>
                  {aiLoading ? (
                    <div className="w-3.5 h-3.5 border-2 border-gray-200 border-t-gray-600 rounded-full animate-spin" />
                  ) : (
                    <button onClick={handleProcessTicket} className="text-xs text-gray-400 hover:text-gray-600 underline">Run</button>
                  )}
                </div>
              ) : (
                <button onClick={handleAnalyze} disabled={aiLoading}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-purple-600 text-white text-xs font-medium hover:bg-purple-700 disabled:opacity-60 transition-colors">
                  {aiLoading ? (
                    <><div className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />Analyzing…</>
                  ) : (
                    <>
                      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                      </svg>
                      Analyze with AI
                    </>
                  )}
                </button>
              )
            )}
          </div>
        </div>

        <div className="p-5 space-y-4">

          {/* ── AI summary ─────────────────────────────────────────────────────── */}
          {aiResult?.summary && (
            <div className="bg-blue-50 border border-blue-100 rounded-lg px-4 py-3">
              <p className="text-xs font-semibold text-blue-600 mb-1">AI Agent Summary</p>
              <p className="text-sm text-gray-800 leading-relaxed">{aiResult.summary}</p>
              {aiResult.intent && (
                <div className="mt-2 flex items-center gap-1.5">
                  <span className="text-xs text-blue-500">Intent:</span>
                  <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-blue-100 text-blue-700">
                    {aiResult.intent?.primary || aiResult.intent}
                  </span>
                </div>
              )}
            </div>
          )}

          {/* ── Metrics row ─────────────────────────────────────────────────────── */}
          {shopifyOrder && (
            <div className="grid grid-cols-4 gap-2.5">
              <div className="bg-gray-50 rounded-lg p-3">
                <p className="text-xs text-gray-500 mb-1">Order value</p>
                <p className="text-lg font-semibold text-gray-900">
                  {shopifyOrder.currency === 'INR' ? '₹' : '$'}{shopifyOrder.total_price}
                </p>
              </div>
              <div className="bg-gray-50 rounded-lg p-3">
                <p className="text-xs text-gray-500 mb-1">Order date</p>
                <p className="text-sm font-semibold text-gray-900 mt-0.5">
                  {shopifyOrder.created_at
                    ? new Date(shopifyOrder.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
                    : '—'}
                </p>
              </div>
              <div className="bg-gray-50 rounded-lg p-3">
                <p className="text-xs text-gray-500 mb-1">
                  {selectedTicket?.ticket_type === 'replace' || selectedTicket?.pending_action_type === 'replace'
                    ? 'Replacement window'
                    : selectedTicket?.ticket_type === 'refund'
                      ? 'Refund window'
                      : 'Return window'}
                </p>
                <p className={clsx('text-sm font-semibold mt-0.5',
                  daysLeft === null ? 'text-gray-400' :
                    daysLeft > 7 ? 'text-green-600' :
                      daysLeft > 0 ? 'text-yellow-600' : 'text-red-500')}>
                  {daysLeft === null ? '—' : daysLeft > 0 ? `${daysLeft} days left` : 'Expired'}
                </p>
              </div>
              <div className="bg-gray-50 rounded-lg p-3">
                <p className="text-xs text-gray-500 mb-1">Orders (customer)</p>
                <p className="text-lg font-semibold text-gray-900">
                  {shopifyCustomer?.orders_count ?? '—'}
                </p>
              </div>
            </div>
          )}

          {/* ── Two-column: tracking timeline + inventory ──────────────────────── */}
          {shopifyOrder && (
            <div className="grid grid-cols-2 gap-3">

              {/* Order tracking timeline */}
              <Card title="Order tracking">
                <div className="space-y-2.5">
                  {timeline.map((step, i) => (
                    <div key={i} className="flex items-start gap-2.5">
                      <TimelineDot status={step.status} />
                      <div className="flex-1 flex items-center justify-between min-w-0">
                        <span className={clsx('text-xs leading-snug',
                          step.status === 'done' ? 'text-gray-700' :
                            step.status === 'active' ? 'text-orange-700 font-medium' :
                              step.status === 'fail' ? 'text-red-600 font-medium' :
                                'text-gray-400')}>
                          {step.label}
                        </span>
                        {step.date && <span className="text-xs text-gray-400 ml-2 shrink-0">{step.date}</span>}
                      </div>
                    </div>
                  ))}
                  {shopifyOrder.fulfillments?.[shopifyOrder.fulfillments.length - 1]?.tracking_number && (
                    <div className="mt-2 pt-2 border-t border-gray-100">
                      <p className="text-xs text-gray-500 mb-1">Tracking</p>
                      <p className="text-xs font-mono text-gray-700 break-all">
                        {shopifyOrder.fulfillments[shopifyOrder.fulfillments.length - 1].tracking_number}
                      </p>
                      {shopifyOrder.fulfillments[shopifyOrder.fulfillments.length - 1].tracking_url && (
                        <a href={shopifyOrder.fulfillments[shopifyOrder.fulfillments.length - 1].tracking_url}
                          target="_blank" rel="noopener noreferrer"
                          className="text-xs text-blue-600 hover:underline mt-0.5 block">
                          Track shipment →
                        </a>
                      )}
                    </div>
                  )}
                </div>
              </Card>

              {/* Inventory */}
              <Card title="Inventory status">
                {inventoryLoading ? (
                  <div className="flex items-center gap-2 text-xs text-gray-400">
                    <div className="w-3.5 h-3.5 border-2 border-gray-200 border-t-gray-400 rounded-full animate-spin" />
                    Fetching stock…
                  </div>
                ) : inventoryError ? (
                  <div className="space-y-2">
                    <p className="text-xs text-red-500">Failed to load inventory</p>
                    {onRetryInventory && (
                      <button onClick={onRetryInventory}
                        className="text-xs text-brand-600 underline hover:text-brand-800">
                        Retry
                      </button>
                    )}
                  </div>
                ) : shopifyOrder.line_items?.length > 0 ? (
                  <div className="space-y-2.5">
                    {shopifyOrder.line_items.map((li, idx) => {
                      const variantId = li.variant_id ? String(li.variant_id) : null
                      const inv = variantId ? inventory?.find(v => v.variant_id === variantId) : null
                      const qty = inv?.inventory_quantity  // null = not tracked, number = actual stock
                      const tracked = inv?.tracked !== false && inv !== undefined
                      return (
                        <div key={idx} className="border-b border-gray-50 pb-2.5 last:border-0 last:pb-0">
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex-1 min-w-0">
                              <p className="text-xs font-medium text-gray-800 leading-snug truncate">{li.title}</p>
                              {li.variant_title && li.variant_title !== 'Default Title' && (
                                <p className="text-xs text-gray-400">{li.variant_title}</p>
                              )}
                              {inv?.sku && <p className="text-xs text-gray-400 font-mono">SKU: {inv.sku}</p>}
                            </div>
                            <div className="shrink-0 text-right">
                              <p className="text-xs text-gray-500">×{li.quantity}</p>
                              <p className="text-xs font-semibold text-gray-800">${li.price}</p>
                            </div>
                          </div>
                          <div className="mt-1.5 flex items-center justify-between text-xs">
                            <span className="text-gray-400">Stock</span>
                            {inv === undefined || inv === null ? (
                              <span className="text-gray-400">—</span>
                            ) : qty === null || qty === undefined ? (
                              <span className="text-gray-400 italic">Not tracked</span>
                            ) : qty > 10 ? (
                              <span className="font-medium text-green-600">{qty} available</span>
                            ) : qty > 0 ? (
                              <span className="font-medium text-yellow-600">{qty} left (low)</span>
                            ) : (
                              <span className="font-medium text-red-500">Out of stock</span>
                            )}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                ) : (
                  <p className="text-xs text-gray-400">No line items on order</p>
                )}
              </Card>
            </div>
          )}

          {/* ── Policy eligibility checks ───────────────────────────────────────── */}
          {(policies.length > 0 || returnPolicyLoading) && (
            <Card title="Policy eligibility checks">
              {returnPolicyLoading ? (
                <div className="flex items-center gap-2 text-xs text-gray-400 py-1">
                  <div className="w-3.5 h-3.5 border-2 border-gray-200 border-t-gray-400 rounded-full animate-spin" />
                  Loading policy from server…
                </div>
              ) : (
                <div className="space-y-0 divide-y divide-gray-50">
                  {policies.map((p, i) => (
                    <div key={i} className="flex items-center justify-between py-2 first:pt-0 last:pb-0">
                      <span className="text-xs text-gray-700">{p.label}</span>
                      <PolicyBadge pass={p.pass} warn={p.warn} detail={
                        p.pass ? (p.detail || 'Pass') : p.warn ? (p.detail || 'Warning') : (p.detail || 'Fail')
                      } />
                    </div>
                  ))}
                </div>
              )}
            </Card>
          )}

          {/* ── Quick actions ───────────────────────────────────────────────────── */}
          {shopifyOrder && (() => {
            const qa = getQuickActions(selectedTicket, shopifyOrder)
            const cardTitle = qa.type === 'replace' ? 'Replacement actions' : 'Refund / return actions'
            const isDisabled = !qa.enabled || aiLoading

            function handleButtonClick(btn) {
              if (!qa.enabled) return
              if (qa.paymentPending && ['full_refund', 'partial_refund'].includes(btn.id)) return
              if (btn.id === 'full_refund') { handleFullRefund(qa); return }
              if (btn.id === 'partial_refund') { setPartialAmount(''); setPartialReason(''); setPartialError(null); setPartialSuccess(null); setShowPartialModal(true); return }
              if (btn.id === 'exchange') { openExchangePanel(); return }
              if (btn.id === 'approve') { handleApproveReplacement(qa); return }
              // wait, escalate, refund_instead → sendPrompt only
              if (sendPrompt && btn.prompt) sendPrompt(btn.prompt)
            }

            return (
              <Card title={cardTitle}>
                {/* Disabled hint */}
                {!qa.enabled && (
                  <p className="text-xs text-gray-400 mb-3 italic">Awaiting request classification — run AI analysis to enable actions</p>
                )}
                {qa.paymentPending && (
                  <div className="mb-3 flex items-center gap-2 rounded-lg bg-amber-50 border border-amber-200 px-3 py-2 text-xs text-amber-700">
                    <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                    Payment pending — Refund &amp; Partial Refund are disabled until payment is completed
                  </div>
                )}

                {/* Replacement success/error banners */}
                {replacementSuccess && (
                  <div className="mb-3 flex items-center gap-2 rounded-lg bg-blue-50 border border-blue-200 px-3 py-2 text-xs text-blue-700">
                    <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                    {replacementSuccess}
                  </div>
                )}
                {replacementError && (
                  <div className="mb-3 flex items-center justify-between gap-2 rounded-lg bg-red-50 border border-red-200 px-3 py-2 text-xs text-red-700">
                    <span>{replacementError}</span>
                    <button onClick={() => setReplacementError(null)} className="underline shrink-0">Retry</button>
                  </div>
                )}

                {/* Full-refund success/error banners */}
                {refundSuccess && (
                  <div className="mb-3 flex items-center gap-2 rounded-lg bg-green-50 border border-green-200 px-3 py-2 text-xs text-green-700">
                    <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                    {refundSuccess}
                  </div>
                )}
                {refundError && (
                  <div className="mb-3 flex items-center justify-between gap-2 rounded-lg bg-red-50 border border-red-200 px-3 py-2 text-xs text-red-700">
                    <span>{refundError}</span>
                    <button onClick={() => setRefundError(null)} className="underline shrink-0">Retry</button>
                  </div>
                )}

                <div className="grid grid-cols-4 gap-2">
                  {qa.buttons.map((btn) => {
                    const isFullRefund = btn.id === 'full_refund'
                    const isApprove = btn.id === 'approve'
                    const btnDisabled = isDisabled
                      || (['full_refund', 'partial_refund'].includes(btn.id) && qa.paymentPending)
                      || (isFullRefund && (refundLoading || !!refundSuccess))
                      || (isApprove && (replacementLoading || !!replacementSuccess))
                      
                    return (
                      <button
                        key={btn.id}
                        disabled={btnDisabled}
                        onClick={() => handleButtonClick(btn)}
                        className={clsx(
                          'flex items-center justify-center gap-1.5 px-3 py-2.5 rounded-lg border text-xs font-medium transition-colors text-center disabled:opacity-40 disabled:cursor-not-allowed',
                          btn.variant === 'primary-green' && 'bg-green-600 text-white border-green-600 hover:bg-green-700',
                          btn.variant === 'primary-blue' && 'bg-blue-600 text-white border-blue-600 hover:bg-blue-700',
                          btn.variant === 'amber' && 'bg-amber-50 text-amber-700 border-amber-200 hover:bg-amber-100',
                          btn.variant === 'secondary' && 'bg-white text-gray-700 border-gray-200 hover:bg-gray-50',
                        )}
                      >
                        {isFullRefund && refundLoading
                          ? <><div className="w-3 h-3 border-2 border-white/40 border-t-white rounded-full animate-spin" />Processing…</>
                          : isApprove && replacementLoading
                          ? <><div className="w-3 h-3 border-2 border-white/40 border-t-white rounded-full animate-spin" />Creating order…</>
                          : btn.label}
                      </button>
                    )
                  })}
                </div>

                {/* ── Exchange inline panel ──────────────────────────────────────── */}
                {showExchangePanel && qa.type === 'refund' && (
                  <div className="mt-4 border border-gray-200 rounded-xl p-4 space-y-3 bg-gray-50">
                    <div className="flex items-center justify-between">
                      <p className="text-xs font-semibold text-gray-700">Exchange offer</p>
                      <button onClick={() => setShowExchangePanel(false)} className="text-gray-400 hover:text-gray-600">
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                      </button>
                    </div>

                    {shopifyOrder?.line_items?.[0] && (
                      <div className="flex items-center gap-2 text-xs text-gray-600 bg-white border border-gray-100 rounded-lg px-3 py-2">
                        <span className="text-gray-400">Current item:</span>
                        <span className="font-medium">{shopifyOrder.line_items[0].title}</span>
                        {shopifyOrder.line_items[0].variant_title && shopifyOrder.line_items[0].variant_title !== 'Default Title' && (
                          <span className="text-gray-500">— {shopifyOrder.line_items[0].variant_title}</span>
                        )}
                      </div>
                    )}

                    {exchangeVariantsLoading && (
                      <div className="flex items-center gap-2 text-xs text-gray-400">
                        <div className="w-3.5 h-3.5 border-2 border-gray-200 border-t-gray-500 rounded-full animate-spin" />
                        Loading variants…
                      </div>
                    )}
                    {exchangeVariantsError && (
                      <p className="text-xs text-amber-600 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">{exchangeVariantsError}</p>
                    )}

                    {exchangeVariants.length > 0 && (
                      <div className="space-y-2">
                        <p className="text-xs text-gray-500">Select replacement variant:</p>
                        <div className="flex flex-wrap gap-2">
                          {exchangeVariants.map(v => {
                            const inStock = v.available && v.inventory_quantity > 0
                            const isSelected = selectedExchangeVariant?.id === v.id
                            return (
                              <button
                                key={v.id}
                                disabled={!inStock}
                                onClick={() => setSelectedExchangeVariant(v)}
                                className={clsx(
                                  'px-3 py-1.5 rounded-lg border text-xs font-medium transition-colors',
                                  !inStock && 'opacity-40 cursor-not-allowed border-gray-200 text-gray-400',
                                  inStock && isSelected && 'border-blue-500 bg-blue-50 text-blue-700',
                                  inStock && !isSelected && 'border-gray-200 bg-white text-gray-700 hover:border-gray-300',
                                )}
                              >
                                {v.title}
                                <span className={clsx('ml-1.5', inStock ? 'text-green-600' : 'text-red-400')}>
                                  {inStock ? `${v.inventory_quantity} in stock` : '✗ OOS'}
                                </span>
                              </button>
                            )
                          })}
                        </div>
                      </div>
                    )}

                    {exchangeSuccess && (
                      <div className="flex items-center gap-2 text-xs text-green-700 bg-green-50 border border-green-200 rounded-lg px-3 py-2">
                        <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                        {exchangeSuccess}
                      </div>
                    )}
                    {exchangeError && (
                      <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">{exchangeError}</p>
                    )}

                    {!exchangeSuccess && (
                      <button
                        onClick={handleConfirmExchange}
                        disabled={!selectedExchangeVariant || exchangeLoading}
                        className="flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 text-white text-xs font-semibold hover:bg-blue-700 disabled:opacity-50 transition-colors"
                      >
                        {exchangeLoading
                          ? <><div className="w-3 h-3 border-2 border-white/40 border-t-white rounded-full animate-spin" />Processing exchange…</>
                          : 'Confirm exchange →'}
                      </button>
                    )}
                  </div>
                )}
              </Card>
            )
          })()}

          {/* ── AI recommended actions (disabled) ──────────────────────────────── */}
          {false && aiResult?.actions?.length > 0 && (
            <Card title="AI recommended actions">
              <div className={clsx(
                'grid gap-2',
                aiResult.actions.length === 1 ? 'grid-cols-1' :
                  aiResult.actions.length === 2 ? 'grid-cols-2' :
                    aiResult.actions.length === 3 ? 'grid-cols-3' :
                      'grid-cols-2 sm:grid-cols-4'
              )}>
                {aiResult.actions.map((action, i) => (
                  <button key={i}
                    onClick={() => setActiveActionIndex(activeActionIndex === i ? null : i)}
                    className={clsx(
                      'border rounded-lg px-3 py-2.5 text-xs font-medium text-left transition-colors',
                      i === 0
                        ? activeActionIndex === i
                          ? 'border-purple-400 bg-purple-100 text-purple-800'
                          : 'border-purple-300 bg-purple-50 text-purple-700 hover:bg-purple-100'
                        : activeActionIndex === i
                          ? 'border-gray-300 bg-gray-100 text-gray-800'
                          : 'border-gray-200 bg-white text-gray-700 hover:bg-gray-50'
                    )}>
                    <span className="block truncate">{action.label} →</span>
                    <span className={clsx('block text-xs mt-0.5',
                      action.confidence >= 0.8 ? 'text-green-600' :
                        action.confidence >= 0.5 ? 'text-yellow-600' : 'text-gray-400')}>
                      {Math.round(action.confidence * 100)}% confident
                    </span>
                  </button>
                ))}
              </div>
              {activeActionIndex !== null && aiResult.actions[activeActionIndex] && (
                <ActionPanel
                  action={aiResult.actions[activeActionIndex]}
                  index={activeActionIndex}
                  actionResult={actionResult}
                  executeAction={executeAction}
                  getFieldValue={getFieldValue}
                  handleFieldChange={handleFieldChange}
                  onClose={() => setActiveActionIndex(null)}
                />
              )}
            </Card>
          )}

          {/* ── AI confidence ───────────────────────────────────────────────────── */}
          {topConfidence !== null && (
            <div className="text-center">
              <p className="text-xs text-gray-400">
                AI confidence: {Math.round(topConfidence * 100)}% · based on order data, tracking, inventory + policy rules
              </p>
              <div className="w-48 mx-auto mt-1.5 h-1 bg-gray-100 rounded-full overflow-hidden">
                <div className="h-full bg-purple-500 rounded-full transition-all" style={{ width: `${topConfidence * 100}%` }} />
              </div>
            </div>
          )}

        </div>
      </div>

      {/* ── Partial refund modal ───────────────────────────────────────────────── */}
      {showPartialModal && (() => {
        const qa = getQuickActions(selectedTicket, shopifyOrder)
        const max = parseFloat(qa?.amount || '0')
        const amt = parseFloat(partialAmount) || 0
        const keeps = max - amt

        return (
          <div
            className="fixed inset-0 z-50 flex items-center justify-center p-4"
            style={{ backdropFilter: 'blur(4px)', backgroundColor: 'rgba(0,0,0,0.4)' }}
            onClick={e => { if (e.target === e.currentTarget) setShowPartialModal(false) }}
          >
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm p-6 space-y-4" onClick={e => e.stopPropagation()}>
              {/* Title */}
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-base font-semibold text-gray-900">Partial Refund</p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    Ticket #{selectedTicket?.id?.slice(-6).toUpperCase()} · Order total: {qa?.currency}{qa?.amount}
                  </p>
                </div>
                <button onClick={() => setShowPartialModal(false)} className="text-gray-400 hover:text-gray-600">
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                </button>
              </div>

              {/* Amount input */}
              <div>
                <label className="text-xs font-medium text-gray-700 mb-1.5 block">Refund amount</label>
                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-gray-500">{qa?.currency}</span>
                  <input
                    type="number"
                    min="1"
                    max={max}
                    step="0.01"
                    value={partialAmount}
                    onChange={e => setPartialAmount(e.target.value)}
                    placeholder={`1 – ${max}`}
                    className="w-full pl-7 pr-4 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
                  />
                </div>
                <p className="text-xs text-gray-400 mt-1">Enter amount between {qa?.currency}1 and {qa?.currency}{max}</p>
              </div>

              {/* Reason */}
              <div>
                <label className="text-xs font-medium text-gray-700 mb-1.5 block">Reason (optional)</label>
                <select
                  value={partialReason}
                  onChange={e => setPartialReason(e.target.value)}
                  className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-green-400 text-gray-700"
                >
                  <option value="">Select reason…</option>
                  <option value="Damaged item">Damaged item</option>
                  <option value="Partial order issue">Partial order issue</option>
                  <option value="Customer goodwill">Customer goodwill</option>
                  <option value="Other">Other</option>
                </select>
              </div>

              {/* Live summary */}
              {amt > 0 && amt <= max && (
                <div className="bg-gray-50 border border-gray-100 rounded-lg px-4 py-2.5 text-xs space-y-1">
                  <div className="flex justify-between text-gray-600">
                    <span>Refund</span>
                    <span className="font-semibold text-green-700">{qa?.currency}{amt.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between text-gray-600">
                    <span>Customer keeps</span>
                    <span className="font-medium">{qa?.currency}{Math.max(0, keeps).toFixed(2)}</span>
                  </div>
                </div>
              )}

              {/* Success */}
              {partialSuccess && (
                <div className="flex items-center gap-2 text-xs text-green-700 bg-green-50 border border-green-200 rounded-lg px-3 py-2">
                  <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                  {partialSuccess}
                </div>
              )}

              {/* Error */}
              {partialError && (
                <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">{partialError}</p>
              )}

              {/* Actions */}
              <div className="flex gap-3 pt-1">
                <button
                  onClick={() => setShowPartialModal(false)}
                  className="flex-1 py-2.5 rounded-lg border border-gray-200 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={() => handlePartialRefund(qa)}
                  disabled={partialLoading || !!partialSuccess || !partialAmount || amt <= 0 || amt > max}
                  className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg bg-green-600 text-white text-sm font-medium hover:bg-green-700 disabled:opacity-50 transition-colors"
                >
                  {partialLoading
                    ? <><div className="w-3.5 h-3.5 border-2 border-white/40 border-t-white rounded-full animate-spin" />Processing…</>
                    : `Process Refund${amt > 0 && amt <= max ? ` — ${qa?.currency}${amt.toFixed(2)}` : ''}`}
                </button>
              </div>
            </div>
          </div>
        )
      })()}
    </div>
  )
}
