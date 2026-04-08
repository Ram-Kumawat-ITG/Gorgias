import { useState, useEffect, Component, useRef, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { aiApi, ordersApi, customersApi, channelsApi, ticketsApi, shopifyApi } from '../api/client'
import AiBanner from '../components/AiBanner'
import clsx from 'clsx'

// ── Error Boundary — prevents blank page on any render-time throw ─────────────
class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }
  componentDidCatch(error, info) {
    console.error('[RequestPage] Render error:', error, info)
  }
  render() {  
    if (this.state.hasError) {
      return (
        <div className="p-8 rounded-xl bg-red-50 border border-red-200 text-center space-y-3">
          <p className="text-red-700 font-semibold">Something went wrong rendering this page.</p>
          <p className="text-red-500 text-sm font-mono">{this.state.error?.message}</p>
          <button
            onClick={() => this.setState({ hasError: false, error: null })}
            className="px-4 py-2 rounded-lg bg-red-600 text-white text-sm font-medium hover:bg-red-700"
          >
            Try again
          </button>
        </div>
      )
    }
    return this.props.children
  }
}

// ── Channel icon lookup — maps icon string from API to SVG JSX ───────────────
const CHANNEL_ICON_MAP = {
  all: (
    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
    </svg>
  ),
  shopify: (
    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 11V7a4 4 0 00-8 0v4M5 9h14l1 12H4L5 9z" />
    </svg>
  ),
  email: (
    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
    </svg>
  ),
  manual: (
    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
    </svg>
  ),
  whatsapp: (
    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
    </svg>
  ),
  chat: (
    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8h2a2 2 0 012 2v6a2 2 0 01-2 2h-2v4l-4-4H9a1.994 1.994 0 01-1.414-.586m0 0L11 14h4a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2v4l.586-.586z" />
    </svg>
  ),
  instagram: (
    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4h16v16H4V4zm4 8a4 4 0 108 0 4 4 0 00-8 0zm9-4.5a.5.5 0 110-1 .5.5 0 010 1z" />
    </svg>
  ),
  telegram: (
    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
    </svg>
  ),
}

// Fallback icon for unknown channels
const DEFAULT_CHANNEL_ICON = (
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 20l4-16m2 16l4-16M6 9h14M4 15h14" />
  </svg>
)

// Convert an API channel object to the tab shape used by the template
function toTabChannel(ch) {
  return {
    label: ch.name,
    value: ch.value,
    icon: CHANNEL_ICON_MAP[ch.icon] || CHANNEL_ICON_MAP[ch.value] || DEFAULT_CHANNEL_ICON,
  }
}


const PRIORITY_COLORS = {
  low: 'bg-gray-100 text-gray-700',
  normal: 'bg-blue-100 text-blue-700',
  high: 'bg-orange-100 text-orange-700',
  urgent: 'bg-red-100 text-red-700',
}

const STATUS_COLORS = {
  open: 'bg-green-100 text-green-700',
  pending: 'bg-yellow-100 text-yellow-700',
  pending_admin_action: 'bg-orange-100 text-orange-700',
  resolved: 'bg-blue-100 text-blue-700',
  closed: 'bg-gray-100 text-gray-600',
}

const FINANCIAL_COLORS = {
  paid: 'bg-green-100 text-green-700',
  pending: 'bg-yellow-100 text-yellow-700',
  refunded: 'bg-red-100 text-red-700',
  voided: 'bg-gray-100 text-gray-600',
}

const FULFILLMENT_COLORS = {
  fulfilled: 'bg-green-100 text-green-700',
  partial: 'bg-yellow-100 text-yellow-700',
  unfulfilled: 'bg-orange-100 text-orange-700',
}

// ── Normalize a raw API message to the shape used by the detail view ─────────
function normalizeMsg(m) {
  return {
    id: m.id,
    sender: m.sender_type,
    message: m.body,
    time: m.created_at,
    whatsapp_media_id: m.whatsapp_media_id || null,
    whatsapp_media_url: m.whatsapp_media_url || null,
    whatsapp_media_type: m.whatsapp_media_type || null,
    instagram_media_url: m.instagram_media_url || null,
    instagram_media_type: m.instagram_media_type || null,
  }
}

const MSG_COLORS = {
  customer: 'bg-gray-50',
  agent: 'bg-blue-50',
}



export default function RequestPage() {
  const [searchParams] = useSearchParams()

  // ── Channels ──────────────────────────────────────────────────────────────
  const [channels, setChannels] = useState([])
  const [channelsLoading, setChannelsLoading] = useState(true)
  const [channelsError, setChannelsError] = useState('')
  const [activeChannel, setActiveChannel] = useState(searchParams.get('channel') || '')

  // ── Ticket list ───────────────────────────────────────────────────────────
  const [tickets, setTickets] = useState([])
  const [ticketsLoading, setTicketsLoading] = useState(false)
  const [ticketsError, setTicketsError] = useState('')
  const [totalTickets, setTotalTickets] = useState(0)
  const [currentPage, setCurrentPage] = useState(1)
  const [activeStatus, setActiveStatus] = useState('active') // 'active'|'open'|'pending'|'resolved'|'closed'|''
  const LIMIT = 20

  // ── Search ────────────────────────────────────────────────────────────────
  const [searchInput, setSearchInput] = useState('')
  const [search, setSearch] = useState('')

  // ── Selected ticket + messages ────────────────────────────────────────────
  const [selectedId, setSelectedId] = useState(null)
  const [selectedTicket, setSelectedTicket] = useState(null)
  const [messages, setMessages] = useState([])
  const [messagesLoading, setMessagesLoading] = useState(false)

  // ── Live Shopify data for the selected ticket ─────────────────────────────
  const [shopifyOrder, setShopifyOrder] = useState(null)
  const [shopifyOrderLoading, setShopifyOrderLoading] = useState(false)
  const [shopifyCustomer, setShopifyCustomer] = useState(null)
  const [sidebarActionLoading, setSidebarActionLoading] = useState(null) // 'fulfill' | 'markPaid' | null
  const [sidebarActionError, setSidebarActionError] = useState('')

  // ── AI analysis ───────────────────────────────────────────────────────────
  const [aiResult, setAiResult] = useState(null)
  const [aiLoading, setAiLoading] = useState(false)
  const [aiError, setAiError] = useState('')
  const [aiProcessResult, setAiProcessResult] = useState(null)  // result from autonomous process
  const [editableData, setEditableData] = useState({})
  const [activeActionIndex, setActiveActionIndex] = useState(null)
  const [actionResult, setActionResult] = useState({})

  // ── Inventory levels (fetched when shopifyOrder loads) ────────────────────
  const [inventory, setInventory] = useState([])
  const [inventoryLoading, setInventoryLoading] = useState(false)
  const [inventoryError, setInventoryError] = useState(false)

  // ── Order identification state ─────────────────────────────────────────────
  // True when no order number could be identified from ticket data or messages
  const [orderNotIdentified, setOrderNotIdentified] = useState(false)
  // Mismatch warning when a found order doesn't belong to this customer
  const [orderMismatchWarning, setOrderMismatchWarning] = useState(null)
  // Last 5 customer orders for manual selection when order can't be identified
  const [candidateOrders, setCandidateOrders] = useState([])
  // Tracks which ticketId we've already attempted message-based extraction for
  const orderExtractionAttemptedRef = useRef(null)

  // ── Pending action approve/reject ────────────────────────────────────────
  const [actionLoading, setActionLoading] = useState(false)
  const [showRejectInput, setShowRejectInput] = useState(false)
  const [rejectReason, setRejectReason] = useState('')

  async function approveAction() {
    if (!selectedTicket) return
    setActionLoading(true)
    try {
      await aiApi.approveAction(selectedTicket.id)
      const res = await ticketsApi.get(selectedTicket.id)
      if (res.data) setSelectedTicket(res.data)
    } catch (err) {
      console.error('Approve action failed:', err)
    } finally {
      setActionLoading(false)
    }
  }

  async function rejectAction() {
    if (!selectedTicket) return
    setActionLoading(true)
    try {
      await aiApi.rejectAction(selectedTicket.id, { rejection_reason: rejectReason })
      setShowRejectInput(false)
      setRejectReason('')
      const res = await ticketsApi.get(selectedTicket.id)
      if (res.data) setSelectedTicket(res.data)
    } catch (err) {
      console.error('Reject action failed:', err)
    } finally {
      setActionLoading(false)
    }
  }

  // Track which ticket has been auto-analyzed + previous message count for change detection
  const autoAnalyzedForRef = useRef(null)
  const prevMsgCountRef = useRef(0)

  // Load channels on mount
  useEffect(() => {
    channelsApi.list()
      .then(res => {
        const mapped = res.data.channels
          .filter(ch => ch.value !== 'shopify' && ch.value !== 'instagram')
          .map(toTabChannel)
        if (mapped.length > 0) setChannels(mapped)
      })
      .catch(() => setChannelsError('Could not load channels'))
      .finally(() => setChannelsLoading(false))
  }, [])

  // Debounce search input → apply after 400 ms idle
  useEffect(() => {
    const t = setTimeout(() => { setSearch(searchInput); setCurrentPage(1) }, 400)
    return () => clearTimeout(t)
  }, [searchInput])

  // Reset to page 1 when channel tab or status filter changes
  useEffect(() => { setCurrentPage(1) }, [activeChannel, activeStatus])

  // Fetch tickets from real API whenever channel / status / page / search changes
  useEffect(() => {
    setTicketsLoading(true)
    setTicketsError('')
    const params = { page: currentPage, limit: LIMIT }
    if (activeChannel) params.channel = activeChannel
    if (activeStatus) params.status = activeStatus
    if (search) params.search = search
    ticketsApi.list(params)
      .then(res => {
        setTickets(res.data.tickets || [])
        setTotalTickets(res.data.total || 0)
      })
      .catch(err => setTicketsError(err.response?.data?.detail || 'Failed to load requests'))
      .finally(() => setTicketsLoading(false))
  }, [activeChannel, activeStatus, currentPage, search])

  // Load messages for the selected ticket
  useEffect(() => {
    if (!selectedId) { setMessages([]); return }
    setMessagesLoading(true)
    ticketsApi.messages(selectedId)
      .then(res => setMessages((res.data || []).map(normalizeMsg)))
      .catch(() => setMessages([]))
      .finally(() => setMessagesLoading(false))
  }, [selectedId])

  // Silent background poll — refresh messages every 4 s while a ticket is open
  useEffect(() => {
    if (!selectedId) return
    const interval = setInterval(() => {
      ticketsApi.messages(selectedId)
        .then(res => setMessages((res.data || []).map(normalizeMsg)))
        .catch(() => {})
    }, 4000)
    return () => clearInterval(interval)
  }, [selectedId])

  // Autonomous AI processing:
  //   • WhatsApp tickets → call processTicket (executes Shopify + sends WA reply + saves to DB)
  //   • Other channels  → call analyze (suggestions only, no auto-send)
  //   Triggers on first load and whenever a new customer message arrives
  // AI processing — ONLY runs when a NEW customer message arrives while viewing
  // Does NOT auto-run on ticket open (prevents unnecessary API calls)
  useEffect(() => {
    if (!selectedTicket || !messages.length || aiLoading) return

    const lastMsg = messages[messages.length - 1]
    const isNewCustomerMsg =
      messages.length > prevMsgCountRef.current && lastMsg?.sender === 'customer'

    prevMsgCountRef.current = messages.length

    if (!isNewCustomerMsg) return

    if (selectedTicket.channel === 'whatsapp') {
      handleProcessTicket()
    } else {
      handleAnalyze()
    }
  }, [messages])

  // ── Order number extraction from free text ──────────────────────────────
  function extractOrderNumber(text) {
    if (!text) return null
    const patterns = [
      // "Order #1741", "order no. 1741", "order number 1741", "order: 1741"
      /order\s*(?:#|no\.?|number|:)\s*(\d{3,})/i,
      // "ORD-1741", "#ORD-1741"
      /(?:#?ORD[-\s]?)(\d{3,})/i,
      // Standalone "#1741" (at least 3 digits, not part of a longer word)
      /(?<![\/\d])#(\d{3,})(?!\d)/,
    ]
    for (const p of patterns) {
      const m = text.match(p)
      if (m?.[1]) return m[1]
    }
    return null
  }

  // ── Fetch order by number, verify customer ownership ─────────────────────
  async function findAndVerifyOrderByNumber(orderNumber, customerEmail, merchantId = null) {
    const numStr = String(orderNumber).replace(/^#/, '')
    const res = await ordersApi.searchByNumber(numStr, merchantId)
    const orders = res.data?.orders || []
    if (!orders.length) return { order: null, warning: `Order #${numStr} not found in Shopify` }
    const order = orders[0]
    const orderEmail = (order.email || '').toLowerCase().trim()
    const ticketEmail = (customerEmail || '').toLowerCase().trim()
    if (orderEmail && ticketEmail && orderEmail !== ticketEmail) {
      return { order, warning: `Order #${numStr} belongs to ${order.email} — does not match this ticket's customer (${customerEmail})` }
    }
    return { order, warning: null }
  }

  // Fetch live Shopify order + customer when a ticket is opened
  // Priority order:
  //   1. selectedTicket.shopify_order_id  → direct GET /orders/{id}
  //   2. selectedTicket.shopify_order_number → search by name
  //   3. message-based extraction → separate effect below (needs messages to load first)
  useEffect(() => {
    if (!selectedTicket) {
      setShopifyOrder(null)
      setShopifyCustomer(null)
      setOrderNotIdentified(false)
      setOrderMismatchWarning(null)
      setCandidateOrders([])
      orderExtractionAttemptedRef.current = null
      return
    }

    async function loadOrderP1P2() {
      setShopifyOrderLoading(true)
      setOrderNotIdentified(false)
      setOrderMismatchWarning(null)
      setCandidateOrders([])
      try {
        const mid = selectedTicket.merchant_id || null
        // Priority 1 — ticket already has a direct Shopify order ID (Shopify-synced tickets)
        if (selectedTicket.shopify_order_id) {
          const res = await ordersApi.get(selectedTicket.shopify_order_id, mid)
          setShopifyOrder(res.data)
          return
        }
        // Priority 2 — ticket has order number stored (email/manual tickets after AI processing)
        if (selectedTicket.shopify_order_number) {
          const { order, warning } = await findAndVerifyOrderByNumber(
            selectedTicket.shopify_order_number, selectedTicket.customer_email, mid
          )
          if (order) { setShopifyOrder(order); if (warning) setOrderMismatchWarning(warning); return }
        }
        // No order found in ticket metadata — message extraction happens in the next effect
        setShopifyOrder(null)
      } catch (err) {
        console.warn('[shopifyOrder] P1/P2 fetch failed:', err)
        setShopifyOrder(null)
      } finally {
        setShopifyOrderLoading(false)
      }
    }

    loadOrderP1P2()

    // ── Customer profile (independent of order) ────────────────────────────
    if (selectedTicket.customer_email) {
      customersApi.search(selectedTicket.customer_email, 1, selectedTicket.merchant_id || null)
        .then(res => setShopifyCustomer((res.data?.customers || [])[0] || null))
        .catch(() => setShopifyCustomer(null))
    } else {
      setShopifyCustomer(null)
    }
  }, [selectedTicket])

  // Priority 3 & 4: once messages load, attempt order extraction from message text
  // Guard: only runs once per ticket (ref tracks attempt), only if order still not resolved
  useEffect(() => {
    if (!selectedTicket || shopifyOrder || shopifyOrderLoading) return
    if (!messages.length) return
    if (orderExtractionAttemptedRef.current === selectedTicket.id) return
    orderExtractionAttemptedRef.current = selectedTicket.id

    async function loadOrderP3P4() {
      setShopifyOrderLoading(true)
      try {
        // Priority 3 — extract order number from message text
        const text = messages.map(m => m.message || m.body || '').join(' ')
        const orderNumber = extractOrderNumber(text)

        if (orderNumber) {
          const { order, warning } = await findAndVerifyOrderByNumber(orderNumber, selectedTicket.customer_email, selectedTicket.merchant_id || null)
          if (order) {
            setShopifyOrder(order)
            if (warning) setOrderMismatchWarning(warning)
            return
          }
          // Extraction found a number but Shopify returned no match
          console.warn(`[shopifyOrder] Order #${orderNumber} mentioned in message but not found in Shopify`)
        }

        // Priority 4 — no extractable order number → fetch recent orders as candidates for manual selection
        if (selectedTicket.customer_email) {
          try {
            const cRes = await customersApi.search(selectedTicket.customer_email, 1, selectedTicket.merchant_id || null)
            const customers = cRes.data?.customers || []
            if (customers.length && customers[0].id) {
              const ordersRes = await ordersApi.listByCustomer(customers[0].id, selectedTicket.merchant_id || null)
              setCandidateOrders((ordersRes.data || []).slice(0, 5))
            }
          } catch { /* customer may not be in Shopify */ }
        }
        setOrderNotIdentified(true)
      } catch (err) {
        console.warn('[shopifyOrder] P3/P4 failed:', err)
        setOrderNotIdentified(true)
      } finally {
        setShopifyOrderLoading(false)
      }
    }

    loadOrderP3P4()
  }, [selectedTicket, messages, shopifyOrder, shopifyOrderLoading])

  // When an order with a valid customer_id is loaded, refresh customer data directly
  // (search-by-email can return stale orders_count / total_spent from Shopify's cache)
  useEffect(() => {
    if (!shopifyOrder?.customer_id) return
    customersApi.get(shopifyOrder.customer_id, selectedTicket?.merchant_id || null)
      .then(res => {
        if (res.data?.customer) {
          const c = res.data.customer
          // Override orders_count with the actual fetched count (Shopify's field is often stale/partial)
          setShopifyCustomer({ ...c, orders_count: res.data.orders?.length ?? c.orders_count })
        }
      })
      .catch(() => {})
  }, [shopifyOrder?.customer_id])

  // Fetch inventory levels when shopifyOrder loads
  const fetchInventory = useCallback((order) => {
    const src = order || shopifyOrder
    if (!src?.line_items?.length) { setInventory([]); return }
    const variantIds = src.line_items.map(li => li.variant_id).filter(Boolean).map(String)
    if (!variantIds.length) { setInventory([]); return }
    setInventoryLoading(true)
    setInventoryError(false)
    shopifyApi.getInventory(variantIds, selectedTicket?.merchant_id || null)
      .then(res => {
        if (res.data.error) {
          setInventory([]);
          setInventoryError(true);
        } else {
          setInventory(res.data.inventory || []);
          setInventoryError(false);
        }
      })
      .catch(() => { setInventory([]); setInventoryError(true) })
      .finally(() => setInventoryLoading(false))
  }, [shopifyOrder])

  useEffect(() => {
    fetchInventory(shopifyOrder)
  }, [shopifyOrder?.id])

  // Background poll every 30 s — only refreshes the list view
  useEffect(() => {
    const poll = setInterval(() => {
      if (selectedId) return
      const params = { page: currentPage, limit: LIMIT }
      if (activeChannel) params.channel = activeChannel
      if (search) params.search = search
      ticketsApi.list(params)
        .then(res => { setTickets(res.data.tickets || []); setTotalTickets(res.data.total || 0) })
        .catch(() => { })
    }, 30_000)
    return () => clearInterval(poll)
  }, [activeChannel, currentPage, search, selectedId])

  const activeChannelMeta = channels.find((c) => c.value === activeChannel)
  const totalPages = Math.max(1, Math.ceil(totalTickets / LIMIT))

  async function handleSelectTicket(id) {
    // Show the list-cached version instantly so the UI opens immediately
    const cached = tickets.find(t => t.id === id) || null
    setSelectedId(id)
    setSelectedTicket(cached)
    setAiResult(null)
    setAiError('')
    setAiProcessResult(null)
    setEditableData({})
    setActiveActionIndex(null)
    setActionResult({})
    setShowRejectInput(false)
    setRejectReason('')
    autoAnalyzedForRef.current = null
    prevMsgCountRef.current = 0

    // Then fetch the FULL ticket document from the DB so shopify_order_id
    // and every other stored field is guaranteed to be present
    try {
      const res = await ticketsApi.get(id)
      if (res.data) setSelectedTicket(res.data)
    } catch {
      // keep the cached version if the fetch fails
    }
  }

  function handleFieldChange(actionIndex, field, value) {
    setEditableData(prev => ({
      ...prev,
      [actionIndex]: { ...(prev[actionIndex] || {}), [field]: value },
    }))
  }

  function getFieldValue(actionIndex, field, aiValue) {
    // If agent has already typed something, use that
    if (editableData[actionIndex]?.[field] !== undefined) return editableData[actionIndex][field]
    // If AI extracted a non-null value, use it
    if (aiValue != null && aiValue !== '') return aiValue
    // Auto-fill from DB ticket fields + live Shopify sidebar data
    // order_id: ticket.shopify_order_id (from DB) → live shopifyOrder.id (already fetched for sidebar)
    if (field === 'order_id')
      return selectedTicket?.shopify_order_id || shopifyOrder?.id || ''
    if (field === 'order_number')
      return String(selectedTicket?.shopify_order_number || shopifyOrder?.order_number || '')
    if (field === 'customer_email') return selectedTicket?.customer_email || ''
    if (field === 'customer_name') return selectedTicket?.customer_name || ''
    return ''
  }

  async function executeAction(action, actionIndex) {
    const merged = {
      ...(action.extracted_data || {}),
      ...(editableData[actionIndex] || {}),
    }
    console.log('Executing action with merged data:', selectedTicket, shopifyOrder, merged)
    // Resolve order/customer IDs — prefer agent-typed / AI-extracted, fall back to ticket data
    console.log(selectedTicket, shopifyOrder)
    const ticketOrderId = selectedTicket?.shopify_order_id
    if (!merged.order_id && ticketOrderId) merged.order_id = ticketOrderId
    if (!merged.customer_email && selectedTicket?.customer_email) merged.customer_email = selectedTicket.customer_email

    setActionResult(prev => ({ ...prev, [actionIndex]: { loading: true, error: null, success: null } }))
    try {
      let successMsg = 'Action executed successfully.'
      let extraData = {}   // extra payload attached to the result (e.g. trackingData)

      const mid = selectedTicket?.merchant_id || null
      const resolveTicketId = selectedTicket?.id || null

      if (action.type === 'CANCEL_ORDER') {
        const id = merged.shopify_order_id || merged.order_id || ticketOrderId
        if (!id) throw new Error('Order ID is required. It has been auto-filled if available — check the field above.')
        await ordersApi.cancel(id, { reason: merged.reason || 'other', restock: true, email: false, merchant_id: mid, ticket_id: resolveTicketId })
        successMsg = `Order #${merged.order_number || id} cancelled successfully.`

      } else if (action.type === 'REFUND_ORDER') {
        const id = merged.shopify_order_id || merged.order_id || ticketOrderId
        if (!id) throw new Error('Order ID is required. It has been auto-filled if available — check the field above.')
        await ordersApi.refund(id, {
          custom_amount: merged.refund_amount || null,
          note: merged.reason || '',
          notify: true,
          merchant_id: mid,
          ticket_id: resolveTicketId,
        })
        successMsg = `Refund of $${merged.refund_amount || '(full)'} issued for order #${merged.order_number || id}.`

      } else if (action.type === 'TRACK_ORDER') {
        const id = merged.shopify_order_id || merged.order_id || ticketOrderId
        if (!id) throw new Error('Order ID is required. It has been auto-filled if available — check the field above.')
        const res = await ordersApi.get(id, mid)
        const order = res.data
        const ff = order.fulfillments?.[0]
        if (ff?.tracking_number) {
          extraData.trackingData = {
            orderName: order.name || `#${order.order_number}`,
            number: ff.tracking_number,
            company: ff.tracking_company || '',
            url: ff.tracking_url || '',
            status: ff.status || '',
            fulfillmentStatus: order.fulfillment_status,
          }
          successMsg = `Tracking #${ff.tracking_number} via ${ff.tracking_company || 'carrier'}`
        } else {
          successMsg = order.fulfillment_status === 'unfulfilled'
            ? 'This order has not been shipped yet.'
            : `Order status: ${order.financial_status} / ${order.fulfillment_status || 'unfulfilled'}`
        }

      } else if (action.type === 'UPDATE_ORDER') {
        const id = merged.order_id || ticketOrderId || merged.shopify_order_id
        if (!id) throw new Error('Order ID is required — enter the Shopify order ID above')
        const payload = {}
        if (merged.field_to_update === 'note') payload.note = merged.new_value
        else if (merged.field_to_update === 'tags') payload.tags = merged.new_value
        await ordersApi.update(id, payload)
        successMsg = `Order #${merged.order_number || id} updated.`

      } else if (action.type === 'CREATE_ORDER') {
        const email = merged.customer_email || selectedTicket?.customer_email
        if (!email) throw new Error('Customer email is required')
        // Look up Shopify customer_id by email
        const searchRes = await customersApi.search(email, 1, mid)
        const customers = searchRes.data?.customers || []
        if (!customers.length) throw new Error(`No Shopify customer found for: ${email}`)
        const customerId = customers[0].id
        const lineItem = {
          title: merged.product_name || 'Item',
          quantity: parseInt(merged.quantity || 1, 10),
          price: merged.price || '0.00',
          ...(merged.variant_id ? { variant_id: merged.variant_id } : {}),
        }
        const order = await ordersApi.create({ customer_id: customerId, line_items: [lineItem], merchant_id: mid })
        successMsg = `Order created for ${email} — Order #${order.data?.order_number || ''}.`

      } else if (action.type === 'DELETE_ORDER') {
        const id = merged.order_id || ticketOrderId || merged.shopify_order_id
        if (!id) throw new Error('Order ID is required — enter the Shopify order ID above')
        // Shopify does not allow deleting confirmed orders — cancel instead
        await ordersApi.cancel(id, { reason: 'other', restock: true, email: false, merchant_id: mid, ticket_id: resolveTicketId })
        successMsg = `Order #${merged.order_number || id} cancelled and restocked.`

      } else if (action.type === 'UPDATE_CUSTOMER_ADDRESS' || action.type === 'UPDATE_CUSTOMER_DETAILS') {
        const email = merged.customer_email || selectedTicket?.customer_email
        if (!email) throw new Error('Customer email is required')
        const searchRes = await customersApi.search(email, 1, mid)
        const customers = searchRes.data?.customers
        if (!customers?.length) throw new Error(`No customer found with email: ${email}`)
        const customerId = customers[0].id
        if (action.type === 'UPDATE_CUSTOMER_ADDRESS') {
          await customersApi.update(customerId, {
            address: merged.new_address || '',
            city: merged.city || '',
            zip: merged.zip || '',
            country_code: merged.country || 'US',
          })
          successMsg = `Address updated for ${email}.`
        } else {
          const payload = {}
          if (merged.field_to_update) payload[merged.field_to_update] = merged.new_value
          await customersApi.update(customerId, payload)
          successMsg = `Customer ${email} updated.`
        }

      } else {
        throw new Error(`Action type "${action.type}" is not yet connected to a real operation.`)
      }

      setActionResult(prev => ({ ...prev, [actionIndex]: { loading: false, error: null, success: successMsg, ...extraData } }))

      // Refresh ticket state for final actions so the status badge updates immediately
      const RESOLVE_ACTIONS = ['CANCEL_ORDER', 'REFUND_ORDER', 'DELETE_ORDER']
      if (RESOLVE_ACTIONS.includes(action.type) && selectedTicket?.id) {
        try {
          const res = await ticketsApi.get(selectedTicket.id)
          if (res.data) setSelectedTicket(res.data)
        } catch {
          // non-critical — status will reflect on next navigation
        }
      }
    } catch (err) {
      const raw = err.response?.data?.detail || err.message || 'Action failed'
      // Make Shopify API errors readable
      const msg = typeof raw === 'object' ? JSON.stringify(raw) : String(raw)
      setActionResult(prev => ({ ...prev, [actionIndex]: { loading: false, error: msg, success: null } }))
    }
  }

  // Fully autonomous — process + send WA reply + save to DB, then refresh messages
  async function handleProcessTicket() {
    if (!selectedTicket) return
    setAiLoading(true)
    setAiError('')
    setAiResult(null)
    setAiProcessResult(null)
    try {
      const res = await aiApi.processTicket(selectedTicket.id)
      const data = res.data

      if (data.status === 'success') {
        setAiProcessResult(data)
        // Refresh messages so the AI reply appears immediately in the thread
        ticketsApi.messages(selectedTicket.id)
          .then(r => setMessages((r.data || []).map(normalizeMsg)))
          .catch(() => {})
      } else if (data.status === 'analysis_only') {
        // Non-WhatsApp fallback — show suggestions panel
        setAiResult(data.analysis)
      } else {
        setAiError(data.reason || 'AI processing failed')
      }
    } catch (err) {
      setAiError(err.response?.data?.detail || err.message || 'AI processing failed')
    } finally {
      setAiLoading(false)
    }
  }

  async function handleAnalyze() {
    if (!selectedTicket) return
    setAiLoading(true)
    setAiError('')
    setAiResult(null)
    setAiProcessResult(null)
    try {
      const res = await aiApi.analyze({
        subject: selectedTicket.subject,
        customer_email: selectedTicket.customer_email,
        shopify_order_id: selectedTicket.shopify_order_id || shopifyOrder?.id || null,
        messages: messages.map((m) => ({ sender: m.sender, message: m.message })),
      })
      setAiResult(res.data)
    } catch (err) {
      setAiError(err.response?.data?.detail || err.message || 'AI analysis failed')
    } finally {
      setAiLoading(false)
    }
  }

  // Analyze with a custom prompt injected as an agent message — used by quick action buttons
  async function sendPrompt(promptText) {
    if (!selectedTicket) return
    setAiLoading(true)
    setAiError('')
    setAiResult(null)
    setAiProcessResult(null)
    try {
      const res = await aiApi.analyze({
        subject: selectedTicket.subject,
        customer_email: selectedTicket.customer_email,
        shopify_order_id: selectedTicket.shopify_order_id || shopifyOrder?.id || null,
        messages: [
          ...messages.map((m) => ({ sender: m.sender, message: m.message })),
          { sender: 'agent', message: promptText },
        ],
      })
      setAiResult(res.data)
    } catch (err) {
      setAiError(err.response?.data?.detail || err.message || 'AI analysis failed')
    } finally {
      setAiLoading(false)
    }
  }

  // ── Detail view ──────────────────────────────────────────────────────────
  if (selectedTicket) {
    return (
      <ErrorBoundary>
        <div>
          {/* Back button + header */}
          <button
            onClick={() => { setSelectedId(null); setSelectedTicket(null) }}
            className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-900 mb-4 transition-colors"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Back to Requests
          </button>

          <div className="flex gap-6">
            {/* Left — messages + AI panel */}
            <div className="flex-1 min-w-0">
              <div className="mb-4">
                <h1 className="text-xl font-semibold text-gray-900">{selectedTicket.subject}</h1>
                <div className="flex items-center gap-2 mt-1 flex-wrap">
                  <span className={clsx('badge capitalize', STATUS_COLORS[selectedTicket.status])}>
                    {selectedTicket.status}
                  </span>
                  <span className={clsx('badge', PRIORITY_COLORS[selectedTicket.priority])}>
                    {selectedTicket.priority}
                  </span>
                  <span className="badge bg-gray-50 text-gray-500 capitalize">{selectedTicket.channel}</span>
                  {selectedTicket.shopify_financial_status && (
                    <span className={clsx('badge', FINANCIAL_COLORS[selectedTicket.shopify_financial_status] || 'bg-gray-100 text-gray-600')}>
                      {selectedTicket.shopify_financial_status}
                    </span>
                  )}
                  {selectedTicket.shopify_fulfillment_status && (
                    <span className={clsx('badge', FULFILLMENT_COLORS[selectedTicket.shopify_fulfillment_status] || 'bg-gray-100 text-gray-600')}>
                      {selectedTicket.shopify_fulfillment_status}
                    </span>
                  )}
                  <span className="text-xs text-gray-400">
                    {new Date(selectedTicket.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })} · {new Date(selectedTicket.created_at).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}
                  </span>
                </div>
              </div>

              {/* Message thread */}
              <div className="space-y-3 mb-4">
                {messagesLoading && (
                  <div className="py-6 text-center text-sm text-gray-400">Loading messages…</div>
                )}
                {!messagesLoading && messages.length === 0 && (
                  <div className="py-6 text-center text-sm text-gray-400">No messages yet.</div>
                )}
                {messages.map((m, i) => (
                  <div
                    key={i}
                    className={clsx(
                      'rounded-lg p-4 text-sm',
                      MSG_COLORS[m.sender] || 'bg-gray-50'
                    )}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-medium text-gray-700 capitalize">{m.sender}</span>
                      <span className="text-xs text-gray-400">
                        {new Date(m.time).toLocaleString()}
                      </span>
                    </div>
                    {/* Hide placeholder body like "[image received]" when media is present */}
                    {(() => {
                      const hasMedia = (m.whatsapp_media_url || m.whatsapp_media_id) &&
                        ['image', 'video', 'image/', 'video/'].some(t => (m.whatsapp_media_type || '').startsWith(t));
                      const isPlaceholder = hasMedia && /^\[.* received\]$/.test((m.message || '').trim());
                      return !isPlaceholder && m.message
                        ? <p className="text-gray-800 whitespace-pre-wrap">{m.message}</p>
                        : null;
                    })()}
                    {/* WhatsApp media — image / video / file */}
                    {(m.whatsapp_media_url || m.whatsapp_media_id) && (() => {
                      const mediaType = m.whatsapp_media_type || '';
                      const src = `${import.meta.env.VITE_API_BASE_URL.replace(/\/$/, '')}/media/whatsapp/${m.id}`;

                      if (mediaType === 'image' || mediaType.startsWith('image/')) {
                        return <img src={src} alt="WhatsApp image" className="mt-2 max-w-xs rounded-lg cursor-pointer hover:opacity-90" onClick={() => window.open(src, '_blank')}
                          onError={e => {
                            e.currentTarget.style.display = 'none';
                            e.currentTarget.parentElement.innerHTML =
                              `<div class="mt-2 w-32 h-24 flex flex-col items-center justify-center bg-gray-100 rounded-lg border border-gray-200 gap-1 p-1">` +
                              `<svg xmlns="http://www.w3.org/2000/svg" class="w-7 h-7 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"/></svg>` +
                              `<span class="text-xs text-gray-400 text-center leading-tight">View image</span>` +
                              `</div>`;
                          }} />;
                      }
                      if (mediaType === 'video' || mediaType.startsWith('video/')) {
                        return <video src={src} controls className="mt-2 max-w-xs rounded-lg" />;
                      }
                      if (mediaType === 'document' || mediaType === 'audio') {
                        return (
                          <a href={src} target="_blank" rel="noopener noreferrer"
                             className="mt-2 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gray-100 text-gray-700 text-xs hover:bg-gray-200">
                            📎 View {mediaType}
                          </a>
                        );
                      }
                      return null;
                    })()}
                    {/* Instagram media */}
                    {m.instagram_media_url && (() => {
                      const rawUrl = m.instagram_media_url;
                      const url = typeof rawUrl === 'string' ? rawUrl : rawUrl?.url || rawUrl?.link || null;
                      if (!url) return null;
                      const mediaType = m.instagram_media_type || '';
                      if (mediaType === 'image' || mediaType.startsWith('image/')) {
                        return <img src={url} alt="Instagram image" className="mt-2 max-w-xs rounded-lg" />;
                      }
                      if (mediaType === 'video' || mediaType.startsWith('video/')) {
                        return <video src={url} controls className="mt-2 max-w-xs rounded-lg" />;
                      }
                      return (
                        <a href={url} target="_blank" rel="noopener noreferrer"
                           className="mt-2 inline-flex items-center gap-1.5 text-xs text-brand-600 hover:underline">
                          View {mediaType || 'media'}
                        </a>
                      );
                    })()}
                  </div>
                ))}
              </div>

              {/* Ticket-level image attachments */}
              {selectedTicket.images?.length > 0 && (
                <div className="mb-4">
                  <p className="text-xs font-medium text-gray-500 mb-2">Attachments ({selectedTicket.images.length})</p>
                  <div className="flex flex-wrap gap-2">
                    {selectedTicket.images.map((url, i) => (
                      <a key={i} href={url} target="_blank" rel="noopener noreferrer">
                        <img src={url} alt={`attachment ${i + 1}`} className="h-24 w-24 object-cover rounded-lg border border-gray-200 hover:opacity-80 transition-opacity"
                          onError={e => {
                            e.currentTarget.style.display = 'none';
                            e.currentTarget.parentElement.innerHTML =
                              `<div class="h-24 w-24 flex flex-col items-center justify-center bg-gray-100 rounded-lg border border-gray-200 gap-1 p-1">` +
                              `<svg xmlns="http://www.w3.org/2000/svg" class="w-7 h-7 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"/></svg>` +
                              `<span class="text-xs text-gray-400 text-center leading-tight">View image</span>` +
                              `</div>`;
                          }} />
                      </a>
                    ))}
                  </div>
                </div>
              )}

              {/* Pending Admin Action Banner */}
              {selectedTicket.status === 'pending_admin_action' && (
                <div className="mb-4 rounded-xl border border-orange-200 bg-orange-50 p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <span className="text-lg">⏳</span>
                    <span className="font-semibold text-orange-800 text-sm">Pending Admin Approval</span>
                    <span className={clsx(
                      'badge text-xs font-semibold uppercase',
                      selectedTicket.pending_action_type === 'refund'  && 'bg-red-100 text-red-700',
                      selectedTicket.pending_action_type === 'replace' && 'bg-blue-100 text-blue-700',
                      selectedTicket.pending_action_type === 'return'  && 'bg-purple-100 text-purple-700',
                      selectedTicket.pending_action_type === 'cancel'  && 'bg-gray-100 text-gray-700',
                      !['refund','replace','return','cancel'].includes(selectedTicket.pending_action_type) && 'bg-orange-100 text-orange-700',
                    )}>
                      {selectedTicket.pending_action_type || 'request'}
                    </span>
                    <span className="badge bg-gray-50 text-gray-500 capitalize text-xs">
                      {selectedTicket.channel || 'unknown'}
                    </span>
                  </div>

                  <div className="bg-white border border-orange-100 rounded-lg p-3 mb-3 space-y-1.5 text-sm">
                    {selectedTicket.pending_action_order_number && (
                      <div className="flex gap-2">
                        <span className="text-gray-500 w-24 shrink-0">Order</span>
                        <span className="font-semibold text-gray-900">#{selectedTicket.pending_action_order_number}</span>
                      </div>
                    )}
                    {selectedTicket.customer_name && (
                      <div className="flex gap-2">
                        <span className="text-gray-500 w-24 shrink-0">Name</span>
                        <span className="text-gray-800">{selectedTicket.customer_name}</span>
                      </div>
                    )}
                    {selectedTicket.pending_action_email && (
                      <div className="flex gap-2">
                        <span className="text-gray-500 w-24 shrink-0">Contact</span>
                        <span className="text-gray-800">{selectedTicket.pending_action_email}</span>
                      </div>
                    )}
                    {selectedTicket.pending_action_issue && (
                      <div className="flex gap-2">
                        <span className="text-gray-500 w-24 shrink-0">Issue</span>
                        <span className="text-gray-800 capitalize">{selectedTicket.pending_action_issue.replace(/_/g, ' ')}</span>
                      </div>
                    )}
                    {selectedTicket.pending_action_description && (
                      <div className="flex gap-2">
                        <span className="text-gray-500 w-24 shrink-0">Description</span>
                        <span className="text-gray-700">{selectedTicket.pending_action_description}</span>
                      </div>
                    )}
                    {selectedTicket.created_at && (
                      <div className="flex gap-2">
                        <span className="text-gray-500 w-24 shrink-0">Submitted</span>
                        <span className="text-gray-700">{new Date(selectedTicket.created_at).toLocaleString()}</span>
                      </div>
                    )}
                  </div>

                  {/* Proof / media thumbnails from message thread */}
                  {messages.some(m => m.whatsapp_media_url || m.instagram_media_url) && (
                    <div className="mb-3">
                      <p className="text-xs font-semibold text-gray-500 mb-1.5">📸 Proof Uploaded</p>
                      <div className="flex flex-wrap gap-2">
                        {messages.filter(m => m.sender === 'customer' && (m.whatsapp_media_url || m.whatsapp_media_id || m.instagram_media_url)).map((m, idx) => {
                          const mediaType = m.whatsapp_media_type || m.instagram_media_type || ''
                          const isImage = mediaType === 'image' || mediaType.startsWith('image/')
                          // Always proxy WhatsApp media (Meta URLs expire and need auth)
                          const isWhatsApp = !!(m.whatsapp_media_url || m.whatsapp_media_id)
                          const src = isWhatsApp
                            ? `${import.meta.env.VITE_API_BASE_URL.replace(/\/$/, '')}/media/whatsapp/${m.id || idx}`
                            : (() => {
                                const rawUrl = m.instagram_media_url
                                return typeof rawUrl === 'string' ? rawUrl : rawUrl?.url || rawUrl?.link || null
                              })()
                          return isImage ? (
                            <img key={idx} src={src} alt="Proof" className="w-16 h-16 rounded-lg object-cover border border-gray-200 cursor-pointer hover:opacity-80" onClick={() => window.open(src, '_blank')}
                              onError={e => {
                                e.currentTarget.style.display = 'none';
                                e.currentTarget.parentElement.innerHTML =
                                  `<div class="w-16 h-16 flex flex-col items-center justify-center bg-gray-100 rounded-lg border border-gray-200 gap-0.5">` +
                                  `<svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"/></svg>` +
                                  `<span class="text-xs text-gray-400 leading-tight">Image</span>` +
                                  `</div>`;
                              }} />
                          ) : (
                            <a key={idx} href={src} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 px-2 py-1 rounded-lg bg-gray-100 text-gray-600 text-xs hover:bg-gray-200">
                              📎 {mediaType || 'file'}
                            </a>
                          )
                        })}
                      </div>
                    </div>
                  )}

                  {!showRejectInput ? (
                    <div className="flex gap-2">
                      <button
                        onClick={approveAction}
                        disabled={actionLoading}
                        className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-green-600 text-white text-sm font-medium hover:bg-green-700 disabled:opacity-50 transition-colors"
                      >
                        {actionLoading ? (
                          <><div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" /> Processing…</>
                        ) : (
                          <><span>✅</span> Approve Request</>
                        )}
                      </button>
                      <button
                        onClick={() => setShowRejectInput(true)}
                        disabled={actionLoading}
                        className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-red-100 text-red-700 text-sm font-medium hover:bg-red-200 disabled:opacity-50 transition-colors"
                      >
                        <span>❌</span> Reject Request
                      </button>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <input
                        type="text"
                        value={rejectReason}
                        onChange={e => setRejectReason(e.target.value)}
                        placeholder="Rejection reason (optional — sent to customer)"
                        className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-400 bg-white"
                      />
                      <div className="flex gap-2">
                        <button
                          onClick={rejectAction}
                          disabled={actionLoading}
                          className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-red-600 text-white text-sm font-medium hover:bg-red-700 disabled:opacity-50 transition-colors"
                        >
                          {actionLoading ? (
                            <><div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" /> Rejecting…</>
                          ) : 'Confirm Reject'}
                        </button>
                        <button
                          onClick={() => { setShowRejectInput(false); setRejectReason('') }}
                          className="px-4 py-2 rounded-lg bg-gray-100 text-gray-600 text-sm font-medium hover:bg-gray-200 transition-colors"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* ── Order mismatch warning ────────────────────────────────────── */}
              {orderMismatchWarning && (
                <div className="mb-4 flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3">
                  <svg className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
                  </svg>
                  <div className="flex-1">
                    <p className="text-xs font-semibold text-amber-800">Order customer mismatch</p>
                    <p className="text-xs text-amber-700 mt-0.5">{orderMismatchWarning}</p>
                  </div>
                  <button onClick={() => setOrderMismatchWarning(null)} className="text-amber-400 hover:text-amber-600 shrink-0">
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                  </button>
                </div>
              )}

              {/* ── Order not identified — manual selector ─────────────────── */}
              {orderNotIdentified && !shopifyOrder && (
                <div className="mb-4 rounded-xl border border-gray-200 bg-white p-4 space-y-3">
                  <div className="flex items-start gap-3">
                    <svg className="w-4 h-4 text-gray-400 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                    </svg>
                    <div>
                      <p className="text-sm font-medium text-gray-800">Could not identify order number from customer message</p>
                      <p className="text-xs text-gray-500 mt-0.5">
                        {candidateOrders.length > 0
                          ? 'Select the correct order below, or ask the customer for the order number.'
                          : 'No orders found for this customer in Shopify.'}
                      </p>
                    </div>
                  </div>
                  {candidateOrders.length > 0 && (
                    <div className="space-y-2">
                      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Recent orders</p>
                      {candidateOrders.map(order => (
                        <button
                          key={order.id}
                          onClick={() => { setShopifyOrder(order); setOrderNotIdentified(false); setCandidateOrders([]) }}
                          className="w-full flex items-center justify-between gap-3 rounded-lg border border-gray-200 px-4 py-3 text-left hover:bg-gray-50 hover:border-gray-300 transition-colors"
                        >
                          <div>
                            <p className="text-sm font-medium text-gray-900">{order.name || `#${order.order_number}`}</p>
                            <p className="text-xs text-gray-500 mt-0.5">
                              {order.created_at ? new Date(order.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '—'}
                              {' · '}{order.financial_status}
                              {order.total_price ? ` · ${order.currency === 'INR' ? '₹' : '$'}${order.total_price}` : ''}
                            </p>
                          </div>
                          <span className="text-xs text-brand-600 font-medium shrink-0">Select →</span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* ── AiBanner: 7-section unified analysis panel ── */}
              <AiBanner
                aiResult={aiResult}
                aiLoading={aiLoading}
                aiError={aiError}
                aiProcessResult={aiProcessResult}
                selectedTicket={selectedTicket}
                shopifyOrder={shopifyOrder}
                shopifyCustomer={shopifyCustomer}
                actionResult={actionResult}
                activeActionIndex={activeActionIndex}
                setActiveActionIndex={setActiveActionIndex}
                executeAction={executeAction}
                handleAnalyze={handleAnalyze}
                handleProcessTicket={handleProcessTicket}
                getFieldValue={getFieldValue}
                handleFieldChange={handleFieldChange}
                inventory={inventory}
                inventoryLoading={inventoryLoading}
                inventoryError={inventoryError}
                onRetryInventory={() => fetchInventory(shopifyOrder)}
                sendPrompt={sendPrompt}
                approveAction={approveAction}
                onClear={() => { setAiResult(null); setActionResult({}); setActiveActionIndex(null) }}
              />

            </div>

            {/* Right — ticket info sidebar */}
            <div className="w-72 shrink-0 space-y-4">

              {/* Customer card */}
              <div className="card p-4">
                <h3 className="text-sm font-semibold text-gray-900 mb-3">Customer</h3>
                <div className="space-y-1.5 text-sm">
                  <p className="font-medium text-gray-800">{selectedTicket.customer_name || '—'}</p>
                  <p className="text-gray-500">{selectedTicket.customer_email}</p>
                  {shopifyCustomer && (
                    <>
                      <div className="border-t border-gray-100 my-2" />
                      <div className="flex justify-between text-xs text-gray-500">
                        <span>Orders</span>
                        <span className="font-medium text-gray-800">{shopifyCustomer.orders_count}</span>
                      </div>
                      <div className="flex justify-between text-xs text-gray-500">
                        <span>Total spent</span>
                        <span className="font-medium text-gray-800">${shopifyCustomer.total_spent}</span>
                      </div>
                      {shopifyCustomer.city && (
                        <div className="flex justify-between text-xs text-gray-500">
                          <span>Location</span>
                          <span className="font-medium text-gray-800">
                            {[shopifyCustomer.city, shopifyCustomer.country_code].filter(Boolean).join(', ')}
                          </span>
                        </div>
                      )}
                      {shopifyCustomer.tags && (
                        <p className="text-xs text-gray-400 mt-1">{shopifyCustomer.tags}</p>
                      )}
                    </>
                  )}
                </div>
              </div>

              {/* Tags */}
              {selectedTicket.tags?.length > 0 && (
                <div className="card p-4">
                  <h3 className="text-sm font-semibold text-gray-900 mb-3">Tags</h3>
                  <div className="flex flex-wrap gap-1">
                    {selectedTicket.tags.map((tag) => (
                      <span key={tag} className="badge bg-gray-100 text-gray-600">{tag}</span>
                    ))}
                  </div>
                </div>
              )}

              {/* ── Live Shopify Order Card ────────────────────────────────── */}
              {shopifyOrderLoading && (
                <div className="card p-4 flex items-center gap-2 text-xs text-gray-400">
                  <div className="w-3.5 h-3.5 border-2 border-gray-200 border-t-gray-400 rounded-full animate-spin" />
                  Fetching order from Shopify…
                </div>
              )}

              {shopifyOrder && !shopifyOrderLoading && (() => {
                const isPaid = shopifyOrder.financial_status === 'paid'
                const isPending = shopifyOrder.financial_status === 'pending'
                const isRefunded = ['refunded', 'partially_refunded'].includes(shopifyOrder.financial_status)
                const isVoided = shopifyOrder.financial_status === 'voided'
                const isCancelled = !!shopifyOrder.cancelled_at
                const isFulfilled = shopifyOrder.fulfillment_status === 'fulfilled'
                const isPartial = shopifyOrder.fulfillment_status === 'partial'
                const isUnfulfilled = !shopifyOrder.fulfillment_status || shopifyOrder.fulfillment_status === 'unfulfilled'
                const latestFulfillment = shopifyOrder.fulfillments?.[shopifyOrder.fulfillments.length - 1]
                const hasTracking = latestFulfillment?.tracking_number

                // Order timeline steps
                const steps = [
                  { key: 'placed', label: 'Order Placed', done: true },
                  { key: 'paid', label: 'Payment', done: isPaid || isRefunded, warn: isPending, fail: isVoided },
                  { key: 'processing', label: 'Processing', done: isPaid && !isUnfulfilled || isFulfilled || isPartial },
                  { key: 'shipped', label: 'Shipped', done: isFulfilled || isPartial },
                  { key: 'delivered', label: 'Delivered', done: isFulfilled && latestFulfillment?.status === 'success' },
                ]

                return (
                  <div className="card overflow-hidden">
                    {/* Header */}
                    <div className="px-4 pt-4 pb-3 border-b border-gray-100">
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <p className="text-sm font-semibold text-gray-900">
                            {shopifyOrder.name || `#${shopifyOrder.order_number}`}
                          </p>
                          <p className="text-xs text-gray-400 mt-0.5">
                            {shopifyOrder.created_at ? new Date(shopifyOrder.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : ''}
                          </p>
                        </div>
                        <div className="flex flex-col items-end gap-1">
                          {isCancelled ? (
                            <span className="badge bg-red-100 text-red-700 text-xs">Cancelled</span>
                          ) : (
                            <>
                              <span className={clsx('badge text-xs capitalize', FINANCIAL_COLORS[shopifyOrder.financial_status] || 'bg-gray-100 text-gray-600')}>
                                {shopifyOrder.financial_status?.replace(/_/g, ' ')}
                              </span>
                              <span className={clsx('badge text-xs capitalize', FULFILLMENT_COLORS[shopifyOrder.fulfillment_status] || 'bg-orange-100 text-orange-700')}>
                                {shopifyOrder.fulfillment_status?.replace(/_/g, ' ') || 'Unfulfilled'}
                              </span>
                            </>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Payment status banner */}
                    <div className={clsx(
                      'px-4 py-2.5 flex items-center gap-2.5 text-xs font-medium',
                      isPaid && 'bg-green-50 text-green-700',
                      isPending && 'bg-yellow-50 text-yellow-700',
                      isRefunded && 'bg-blue-50 text-blue-700',
                      isVoided && 'bg-gray-50 text-gray-500',
                      isCancelled && 'bg-red-50 text-red-600',
                      !isPaid && !isPending && !isRefunded && !isVoided && !isCancelled && 'bg-gray-50 text-gray-500',
                    )}>
                      {isPaid && (
                        <svg className="w-3.5 h-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                      )}
                      {isPending && (
                        <svg className="w-3.5 h-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                      )}
                      {isRefunded && (
                        <svg className="w-3.5 h-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6" />
                        </svg>
                      )}
                      {(isVoided || isCancelled) && (
                        <svg className="w-3.5 h-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                      )}
                      <span>
                        {isPaid && `Paid — $${shopifyOrder.total_price} ${shopifyOrder.currency}`}
                        {isPending && `Payment pending — $${shopifyOrder.total_price} ${shopifyOrder.currency}`}
                        {isRefunded && `${shopifyOrder.financial_status === 'refunded' ? 'Fully refunded' : 'Partially refunded'}`}
                        {isVoided && 'Payment voided'}
                        {isCancelled && `Cancelled${shopifyOrder.cancel_reason ? ` — ${shopifyOrder.cancel_reason}` : ''}`}
                        {!isPaid && !isPending && !isRefunded && !isVoided && !isCancelled && shopifyOrder.financial_status}
                      </span>
                    </div>

                    <div className="px-4 py-3 space-y-4">

                      {/* Order progress timeline */}
                      {!isCancelled && (
                        <div>
                          <div className="flex items-center justify-between relative">
                            {/* connecting line */}
                            <div className="absolute left-3 right-3 top-3 h-0.5 bg-gray-100 z-0" />
                            {steps.map((step, idx) => (
                              <div key={step.key} className="flex flex-col items-center gap-1 z-10" style={{ width: `${100 / steps.length}%` }}>
                                <div className={clsx(
                                  'w-6 h-6 rounded-full flex items-center justify-center border-2 text-xs font-bold transition-colors',
                                  step.done && !step.fail ? 'bg-green-500 border-green-500 text-white' :
                                    step.warn ? 'bg-yellow-400 border-yellow-400 text-white' :
                                      step.fail ? 'bg-red-400 border-red-400 text-white' :
                                        idx === steps.findIndex(s => !s.done && !s.warn && !s.fail) ? 'bg-white border-blue-400 text-blue-400' :
                                          'bg-white border-gray-200 text-gray-300'
                                )}>
                                  {step.done && !step.fail ? (
                                    <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                                    </svg>
                                  ) : step.warn ? '!' : step.fail ? '✕' : idx + 1}
                                </div>
                                <span className={clsx(
                                  'text-center leading-tight',
                                  'text-[9px]',
                                  step.done ? 'text-green-600 font-medium' :
                                    step.warn ? 'text-yellow-600 font-medium' :
                                      step.fail ? 'text-red-500' : 'text-gray-400'
                                )}>
                                  {step.label}
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Tracking card */}
                      {hasTracking && (
                        <div className="rounded-lg bg-blue-50 border border-blue-100 p-3 space-y-2">
                          <div className="flex items-center gap-1.5 text-blue-700 font-semibold text-xs">
                            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10" />
                            </svg>
                            Shipment Tracking
                          </div>
                          <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
                            {latestFulfillment.tracking_company && (
                              <>
                                <span className="text-gray-500">Carrier</span>
                                <span className="font-medium text-gray-800">{latestFulfillment.tracking_company}</span>
                              </>
                            )}
                            <span className="text-gray-500">Tracking #</span>
                            <span className="font-mono text-xs font-medium text-gray-800 break-all">{latestFulfillment.tracking_number}</span>
                            <span className="text-gray-500">Status</span>
                            <span className={clsx('font-medium capitalize',
                              latestFulfillment.status === 'success' ? 'text-green-600' :
                                latestFulfillment.status === 'failure' ? 'text-red-500' : 'text-blue-600'
                            )}>
                              {latestFulfillment.status || 'In transit'}
                            </span>
                          </div>
                          {latestFulfillment.tracking_url ? (
                            <a
                              href={latestFulfillment.tracking_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="flex items-center justify-center gap-1.5 w-full py-1.5 rounded-md bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold transition-colors"
                            >
                              Track Shipment
                              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                              </svg>
                            </a>
                          ) : (
                            <p className="text-xs text-blue-400">No tracking URL available</p>
                          )}
                        </div>
                      )}

                      {/* No tracking yet but order is placed */}
                      {!hasTracking && !isUnfulfilled && (
                        <div className="rounded-lg bg-gray-50 border border-dashed border-gray-200 p-3 text-center text-xs text-gray-400">
                          Tracking info not yet available
                        </div>
                      )}

                      {/* Line items */}
                      <div className="space-y-2">
                        {shopifyOrder.line_items?.map((li, i) => (
                          <div key={i} className="flex items-start justify-between gap-2 text-xs">
                            <div className="min-w-0 flex-1">
                              <p className="text-gray-700 font-medium leading-snug truncate">{li.title}</p>
                              {li.variant_title && li.variant_title !== 'Default Title' && (
                                <p className="text-gray-400">{li.variant_title}</p>
                              )}
                              {li.sku && <p className="text-gray-400 font-mono">SKU: {li.sku}</p>}
                            </div>
                            <div className="text-right shrink-0">
                              <p className="text-gray-500">×{li.quantity}</p>
                              <p className="font-semibold text-gray-800">${li.price}</p>
                            </div>
                          </div>
                        ))}
                      </div>

                      {/* Price summary */}
                      <div className="border-t border-gray-100 pt-2 space-y-1 text-xs">
                        {shopifyOrder.subtotal_price && shopifyOrder.subtotal_price !== shopifyOrder.total_price && (
                          <div className="flex justify-between text-gray-500">
                            <span>Subtotal</span>
                            <span>${shopifyOrder.subtotal_price}</span>
                          </div>
                        )}
                        {shopifyOrder.total_discounts && parseFloat(shopifyOrder.total_discounts) > 0 && (
                          <div className="flex justify-between text-green-600">
                            <span>Discount</span>
                            <span>−${shopifyOrder.total_discounts}</span>
                          </div>
                        )}
                        {shopifyOrder.total_tax && parseFloat(shopifyOrder.total_tax) > 0 && (
                          <div className="flex justify-between text-gray-500">
                            <span>Tax</span>
                            <span>${shopifyOrder.total_tax}</span>
                          </div>
                        )}
                        <div className="flex justify-between text-sm font-bold text-gray-900 pt-1.5 border-t border-gray-100">
                          <span>Total</span>
                          <span>${shopifyOrder.total_price} <span className="text-xs font-medium text-gray-400">{shopifyOrder.currency}</span></span>
                        </div>
                      </div>

                      {/* Shipping address */}
                      {shopifyOrder.shipping_address?.address1 && (
                        <div className="border-t border-gray-100 pt-3">
                          <p className="text-xs font-semibold text-gray-600 mb-1.5 flex items-center gap-1">
                            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                            </svg>
                            Ship to
                          </p>
                          <p className="text-xs text-gray-500 leading-relaxed">
                            {shopifyOrder.shipping_address.name}<br />
                            {shopifyOrder.shipping_address.address1}<br />
                            {[shopifyOrder.shipping_address.city, shopifyOrder.shipping_address.province, shopifyOrder.shipping_address.zip].filter(Boolean).join(', ')}<br />
                            {shopifyOrder.shipping_address.country}
                          </p>
                        </div>
                      )}

                      {/* Order note */}
                      {shopifyOrder.note && (
                        <div className="border-t border-gray-100 pt-2">
                          <p className="text-xs font-semibold text-gray-600 mb-1">Note</p>
                          <p className="text-xs text-gray-500 italic">{shopifyOrder.note}</p>
                        </div>
                      )}

                      {/* Quick action buttons */}
                      {sidebarActionError && (
                        <p className="text-xs text-red-500 bg-red-50 rounded-md px-2 py-1.5">{sidebarActionError}</p>
                      )}
                      <div className="border-t border-gray-100 pt-3 flex flex-wrap gap-2">
                        {isUnfulfilled && !isCancelled && (
                          <button
                            disabled={sidebarActionLoading === 'fulfill'}
                            onClick={async () => {
                              setSidebarActionError('')
                              setSidebarActionLoading('fulfill')
                              try {
                                await ordersApi.fulfill(shopifyOrder.id, { merchant_id: selectedTicket?.merchant_id || null })
                                const res = await ordersApi.get(shopifyOrder.id, selectedTicket?.merchant_id || null)
                                setShopifyOrder(res.data)
                              } catch (e) {
                                setSidebarActionError(e.response?.data?.detail || 'Fulfill failed')
                              } finally {
                                setSidebarActionLoading(null)
                              }
                            }}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-medium disabled:opacity-60 transition-colors"
                          >
                            {sidebarActionLoading === 'fulfill' ? (
                              <div className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                            ) : (
                              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4" />
                              </svg>
                            )}
                            Fulfill Order
                          </button>
                        )}
                        {isPending && !isCancelled && (
                          <button
                            disabled={sidebarActionLoading === 'markPaid'}
                            onClick={async () => {
                              setSidebarActionError('')
                              setSidebarActionLoading('markPaid')
                              try {
                                await ordersApi.markPaid(shopifyOrder.id, selectedTicket?.merchant_id || null)
                                const res = await ordersApi.get(shopifyOrder.id, selectedTicket?.merchant_id || null)
                                setShopifyOrder(res.data)
                              } catch (e) {
                                setSidebarActionError(e.response?.data?.detail || 'Mark as paid failed')
                              } finally {
                                setSidebarActionLoading(null)
                              }
                            }}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-green-600 hover:bg-green-700 text-white text-xs font-medium disabled:opacity-60 transition-colors"
                          >
                            {sidebarActionLoading === 'markPaid' ? (
                              <div className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                            ) : (
                              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" />
                              </svg>
                            )}
                            Mark as Paid
                          </button>
                        )}
                        {/* Refresh order data */}
                        <button
                          disabled={!!sidebarActionLoading}
                          onClick={async () => {
                            setSidebarActionLoading('refresh')
                            setSidebarActionError('')
                            try {
                              const res = await ordersApi.get(shopifyOrder.id, selectedTicket?.merchant_id || null)
                              setShopifyOrder(res.data)
                            } catch {
                              setSidebarActionError('Could not refresh order')
                            } finally {
                              setSidebarActionLoading(null)
                            }
                          }}
                          className="flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-gray-200 bg-white hover:bg-gray-50 text-gray-600 text-xs font-medium disabled:opacity-60 transition-colors"
                        >
                          {sidebarActionLoading === 'refresh' ? (
                            <div className="w-3 h-3 border-2 border-gray-300 border-t-gray-600 rounded-full animate-spin" />
                          ) : (
                            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                            </svg>
                          )}
                          Refresh
                        </button>
                      </div>
                    </div>
                  </div>
                )
              })()}

              {/* Fallback — show cached data when no live order loaded */}
              {!shopifyOrder && !shopifyOrderLoading && selectedTicket.shopify_line_items?.length > 0 && (
                <div className="card p-4">
                  <h3 className="text-sm font-semibold text-gray-900 mb-3">
                    Order #{selectedTicket.shopify_order_number}
                    <span className="ml-1 text-xs font-normal text-gray-400">(cached)</span>
                  </h3>
                  <div className="space-y-2">
                    {selectedTicket.shopify_line_items.map((li, i) => (
                      <div key={i} className="flex items-center justify-between text-xs">
                        <span className="text-gray-700">{li.title} x{li.quantity}</span>
                        <span className="font-medium">${li.price}</span>
                      </div>
                    ))}
                    <div className="border-t border-gray-100 pt-2 mt-2 flex items-center justify-between text-sm font-medium">
                      <span>Total</span>
                      <span>${selectedTicket.shopify_total_price} {selectedTicket.shopify_currency}</span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </ErrorBoundary>
    )
  }

  // ── List view ────────────────────────────────────────────────────────────
  return (
    <ErrorBoundary>
      <div>
        {/* Page header */}
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Requests</h1>
            <p className="text-sm text-gray-500 mt-0.5">
              {ticketsLoading ? 'Loading…' : `${totalTickets} ${totalTickets === 1 ? 'request' : 'requests'}${activeChannelMeta?.value ? ` via ${activeChannelMeta.label}` : ' across all channels'}`}
            </p>
          </div>

          {/* Search bar */}
          <div className="relative w-64">
            <svg className="absolute left-2.5 top-2.5 w-4 h-4 text-gray-400 pointer-events-none" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-4.35-4.35M17 11A6 6 0 1 1 5 11a6 6 0 0 1 12 0z" />
            </svg>
            <input
              type="text"
              value={searchInput}
              onChange={e => setSearchInput(e.target.value)}
              placeholder="Search subject, email…"
              className="w-full pl-8 pr-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-brand-400 bg-white"
            />
          </div>
        </div>

        {/* Sales channel tabs */}
        <div className="mb-3 overflow-x-auto">
          {channelsError && (
            <p className="text-xs text-red-500 mb-2">{channelsError}</p>
          )}
          <div className={clsx('flex gap-1 bg-white border border-gray-200 rounded-lg p-1 w-fit', channelsLoading && 'opacity-60')}>
            {channels.map((channel) => (
              <button
                key={channel.value}
                onClick={() => setActiveChannel(channel.value)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors whitespace-nowrap ${activeChannel === channel.value
                    ? 'bg-brand-600 text-white'
                    : 'text-gray-600 hover:bg-gray-100'
                  }`}
              >
                {channel.icon}
                {channel.label}
              </button>
            ))}
          </div>
        </div>

        {/* Status filter tabs */}
        <div className="mb-4 flex items-center gap-2">
          {[
            { value: 'active',   label: 'Active' },
            { value: 'open',     label: 'Open' },
            { value: 'pending',  label: 'Pending' },
            { value: 'resolved', label: 'Resolved' },
            { value: 'closed',   label: 'Closed' },
          ].map(({ value, label }) => (
            <button
              key={value}
              onClick={() => { setActiveStatus(value); setCurrentPage(1) }}
              className={clsx(
                'px-4 py-1.5 rounded-full text-sm font-semibold transition-all whitespace-nowrap',
                activeStatus === value
                  ? 'bg-green-500 text-white shadow-sm'
                  : 'bg-white text-gray-600 border border-gray-200 hover:bg-gray-50'
              )}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Error state */}
        {ticketsError && (
          <div className="mb-3 px-4 py-3 rounded-lg bg-red-50 text-red-700 border border-red-200 text-sm flex items-center justify-between">
            {ticketsError}
            <button
              onClick={() => { setTicketsError(''); setCurrentPage(p => p) }}
              className="text-xs underline ml-2"
            >Retry</button>
          </div>
        )}

        {/* Ticket list */}
        <div className="card divide-y divide-gray-100">
          {ticketsLoading ? (
            <div className="p-8 text-center text-gray-400 text-sm">Loading requests…</div>
          ) : tickets.length === 0 ? (
            <div className="p-8 text-center text-gray-400">
              {search
                ? `No results for "${search}"`
                : activeStatus === 'active'
                  ? 'No open or pending requests'
                  : activeStatus
                    ? `No ${activeStatus} requests`
                    : `No requests${activeChannelMeta?.value ? ` for ${activeChannelMeta.label}` : ''}`
              }
            </div>
          ) : (
            tickets.map((t) => (
              <div
                key={t.id}
                onClick={() => handleSelectTicket(t.id)}
                className="flex items-center justify-between px-4 py-3 hover:bg-gray-50 cursor-pointer transition-colors"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-medium text-gray-900 truncate">{t.subject}</p>
                    <span className={clsx('badge text-xs shrink-0', STATUS_COLORS[t.status])}>
                      {t.status}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 mt-0.5">
                    <p className="text-xs text-gray-500">{t.customer_name}</p>
                    <span className="text-xs text-gray-300">|</span>
                    <p className="text-xs text-gray-400">{t.customer_email}</p>
                    {t.channel === 'shopify' && t.shopify_total_price && (
                      <>
                        <span className="text-xs text-gray-300">|</span>
                        <span className="text-xs font-medium text-gray-700">
                          ${t.shopify_total_price} {t.shopify_currency}
                        </span>
                      </>
                    )}
                  </div>
                  {t.shopify_line_items?.length > 0 && (
                    <p className="text-xs text-gray-400 mt-0.5 truncate">
                      {t.shopify_line_items.map((li) => `${li.title} x${li.quantity}`).join(', ')}
                    </p>
                  )}
                  <p className="text-xs text-gray-400 mt-0.5">
                    {new Date(t.updated_at || t.created_at).toLocaleString()}
                  </p>
                </div>
                <div className="flex items-center gap-2 ml-4 shrink-0">
                  <span className="badge bg-gray-50 text-gray-500 capitalize text-xs">{t.channel}</span>
                  {t.shopify_financial_status && (
                    <span className={clsx('badge text-xs', FINANCIAL_COLORS[t.shopify_financial_status] || 'bg-gray-100 text-gray-600')}>
                      {t.shopify_financial_status}
                    </span>
                  )}
                  {t.shopify_fulfillment_status && (
                    <span className={clsx('badge text-xs', FULFILLMENT_COLORS[t.shopify_fulfillment_status] || 'bg-gray-100 text-gray-600')}>
                      {t.shopify_fulfillment_status}
                    </span>
                  )}
                  {!t.shopify_financial_status && t.tags?.slice(0, 2).map((tag) => (
                    <span key={tag} className="badge bg-gray-100 text-gray-600 text-xs">{tag}</span>
                  ))}
                  <span className={clsx('badge text-xs', PRIORITY_COLORS[t.priority])}>
                    {t.priority}
                  </span>
                  <span className="text-xs text-gray-400 whitespace-nowrap">
                    {new Date(t.created_at).toLocaleDateString()}
                  </span>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between mt-4 text-sm text-gray-600">
            <span>{totalTickets} total · page {currentPage} of {totalPages}</span>
            <div className="flex gap-1">
              <button
                disabled={currentPage <= 1}
                onClick={() => setCurrentPage(p => p - 1)}
                className="px-3 py-1.5 rounded border border-gray-200 bg-white hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
              >← Prev</button>
              <button
                disabled={currentPage >= totalPages}
                onClick={() => setCurrentPage(p => p + 1)}
                className="px-3 py-1.5 rounded border border-gray-200 bg-white hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
              >Next →</button>
            </div>
          </div>
        )}
      </div>
    </ErrorBoundary>
  )
}
