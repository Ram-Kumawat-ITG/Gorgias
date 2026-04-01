// SLA dashboard — compliance metrics, sortable ticket table, per-ticket history timeline
import { useState, useEffect, useMemo } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell,
} from 'recharts'
import { Shield, ChevronUp, ChevronDown, X, Clock, CheckCircle, AlertTriangle, AlertCircle } from 'lucide-react'
import api from '../api/client'
import SLATimeline from '../components/SLATimeline'
import clsx from 'clsx'

// ─── Constants ───────────────────────────────────────────────────────────────

const SLA_BADGE = {
  ok:       'bg-green-100 text-green-700',
  warning:  'bg-yellow-100 text-yellow-700',
  breached: 'bg-red-100 text-red-700',
}

const CHANNEL_LABEL = {
  email:     'Email',
  whatsapp:  'WhatsApp',
  instagram: 'Instagram',
  manual:    'Manual',
  shopify:   'Shopify',
  twitter:   'Twitter',
}

const COMPLIANCE_COLORS = {
  ok:       '#16a34a',
  warning:  '#f59e0b',
  breached: '#ef4444',
}

// ─── Sub-components ──────────────────────────────────────────────────────────

function SLAStatusBadge({ status }) {
  if (!status) return <span className="badge bg-gray-100 text-gray-400">—</span>
  return (
    <span className={clsx('badge', SLA_BADGE[status] ?? 'bg-gray-100 text-gray-500')}>
      {status}
    </span>
  )
}

function StatCard({ title, value, hint, valueClass = 'text-gray-900', icon: Icon, iconClass }) {
  return (
    <div className="card p-4 flex items-start gap-3">
      {Icon && (
        <div className={clsx('p-2 rounded-lg', iconClass)}>
          <Icon size={18} />
        </div>
      )}
      <div>
        <p className="text-sm text-gray-500">{title}</p>
        <p className={clsx('text-2xl font-semibold', valueClass)}>
          {value}
          {hint && <span className="text-sm text-gray-400 ml-1">{hint}</span>}
        </p>
      </div>
    </div>
  )
}

function SortHeader({ label, field, sort, onSort, className = '' }) {
  const active = sort.field === field
  return (
    <button
      onClick={() => onSort(field)}
      className={clsx(
        'flex items-center gap-1 text-xs font-medium text-gray-500 hover:text-gray-800 transition-colors select-none',
        className,
      )}
    >
      {label}
      <span className="flex flex-col leading-none">
        <ChevronUp
          size={10}
          className={active && sort.dir === 'asc' ? 'text-brand-600' : 'text-gray-300'}
        />
        <ChevronDown
          size={10}
          className={active && sort.dir === 'desc' ? 'text-brand-600' : 'text-gray-300'}
        />
      </span>
    </button>
  )
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function minsToHuman(mins) {
  if (mins === null || mins === undefined) return '—'
  const m = Math.round(Number(mins))
  if (m < 60) return `${m}m`
  const h = Math.floor(m / 60)
  const rem = m % 60
  return rem > 0 ? `${h}h ${rem}m` : `${h}h`
}

function firstResponseMins(ticket) {
  if (!ticket.first_response_at || !ticket.created_at) return null
  return (new Date(ticket.first_response_at) - new Date(ticket.created_at)) / 60000
}

function resolutionMins(ticket) {
  if (!ticket.resolved_at || !ticket.created_at) return null
  return (new Date(ticket.resolved_at) - new Date(ticket.created_at)) / 60000
}

function slaOrder(status) {
  return { breached: 0, warning: 1, ok: 2 }[status] ?? 3
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function SLAPage() {
  // Filter state
  const [days,      setDays]      = useState(30)
  const [channel,   setChannel]   = useState('')
  const [slaFilter, setSlaFilter] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate,   setEndDate]   = useState('')

  // Sort state: field + direction
  const [sort, setSort] = useState({ field: 'created_at', dir: 'desc' })

  // Data
  const [metrics,        setMetrics]        = useState(null)
  const [tickets,        setTickets]        = useState([])
  const [loading,        setLoading]        = useState(true)
  const [selectedTicket, setSelectedTicket] = useState(null)
  const [ticketHistory,  setTicketHistory]  = useState([])
  const [sidebarLoading, setSidebarLoading] = useState(false)

  // ── Data loading ────────────────────────────────────────────────────────────

  function loadOverview() {
    api.get('/analytics/overview', { params: { days } })
      .then(res => setMetrics(res.data))
      .catch(() => {})
  }

  function loadTickets() {
    setLoading(true)
    const params = { page: 1, limit: 100 }
    if (channel) params.channel = channel
    api.get('/tickets', { params })
      .then(res => {
        let list = res.data.tickets || []
        if (startDate) {
          const s = new Date(startDate)
          list = list.filter(t => new Date(t.created_at) >= s)
        }
        if (endDate) {
          const e = new Date(endDate)
          e.setHours(23, 59, 59, 999)
          list = list.filter(t => new Date(t.created_at) <= e)
        }
        setTickets(list)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  // Reload on channel/days change (and every 10 s)
  useEffect(() => {
    loadOverview()
    loadTickets()
    const iv = setInterval(() => { loadOverview(); loadTickets() }, 10000)
    return () => clearInterval(iv)
  }, [days, channel]) // eslint-disable-line react-hooks/exhaustive-deps

  // Reload on date filter change
  useEffect(() => { loadTickets() }, [startDate, endDate]) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Per-ticket sidebar ──────────────────────────────────────────────────────

  function openTicket(id) {
    if (selectedTicket?.id === id) return
    setSidebarLoading(true)
    setSelectedTicket(null)
    setTicketHistory([])
    Promise.all([
      api.get(`/tickets/${id}`),
      api.get(`/history/ticket/${id}`),
    ])
      .then(([tRes, hRes]) => {
        setSelectedTicket(tRes.data)
        // Keep all history events, prioritise SLA ones at top
        const all = hRes.data || []
        const slaEvents = all.filter(ev => ev.event?.toLowerCase().includes('sla'))
        const other     = all.filter(ev => !ev.event?.toLowerCase().includes('sla'))
        setTicketHistory([...slaEvents, ...other])
      })
      .catch(() => {})
      .finally(() => setSidebarLoading(false))
  }

  function closeTicket() {
    setSelectedTicket(null)
    setTicketHistory([])
  }

  // ── Sort toggle ─────────────────────────────────────────────────────────────

  function toggleSort(field) {
    setSort(prev =>
      prev.field === field
        ? { field, dir: prev.dir === 'asc' ? 'desc' : 'asc' }
        : { field, dir: 'asc' }
    )
  }

  // ── Derived data ────────────────────────────────────────────────────────────

  const filteredTickets = useMemo(() => {
    let list = tickets
    if (slaFilter) list = list.filter(t => t.sla_status === slaFilter)

    return [...list].sort((a, b) => {
      let av, bv
      switch (sort.field) {
        case 'sla_status':
          av = slaOrder(a.sla_status); bv = slaOrder(b.sla_status); break
        case 'channel':
          av = a.channel ?? ''; bv = b.channel ?? ''; break
        case 'first_response_at':
          av = a.first_response_at ? new Date(a.first_response_at).getTime() : Infinity
          bv = b.first_response_at ? new Date(b.first_response_at).getTime() : Infinity
          break
        case 'resolved_at':
          av = a.resolved_at ? new Date(a.resolved_at).getTime() : Infinity
          bv = b.resolved_at ? new Date(b.resolved_at).getTime() : Infinity
          break
        default: // created_at
          av = new Date(a.created_at).getTime()
          bv = new Date(b.created_at).getTime()
      }
      if (av < bv) return sort.dir === 'asc' ? -1 : 1
      if (av > bv) return sort.dir === 'asc' ? 1 : -1
      return 0
    })
  }, [tickets, slaFilter, sort])

  const total    = Object.values(metrics?.tickets_by_status || {}).reduce((a, b) => a + b, 0)
  const breaches = metrics?.sla_compliance?.breached ?? 0
  const warnings = metrics?.sla_compliance?.warning  ?? 0
  const okCount  = metrics?.sla_compliance?.ok       ?? 0
  const avgResp  = metrics?.avg_first_response_minutes ?? 0

  const complianceChartData = [
    { name: 'OK',      value: okCount,  fill: COMPLIANCE_COLORS.ok },
    { name: 'Warning', value: warnings, fill: COMPLIANCE_COLORS.warning },
    { name: 'Breached',value: breaches, fill: COMPLIANCE_COLORS.breached },
  ]

  const compliancePct = total > 0
    ? Math.round((okCount / total) * 100)
    : 0

  function clearFilters() {
    setStartDate('')
    setEndDate('')
    setSlaFilter('')
    setChannel('')
  }
  const hasActiveFilters = startDate || endDate || slaFilter || channel

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <div className="flex gap-6 min-h-0">

      {/* ── Main column ─────────────────────────────────────────────────────── */}
      <div className={clsx('flex-1 min-w-0 space-y-5', selectedTicket ? 'lg:max-w-[calc(100%-22rem)]' : '')}>

        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Shield size={22} className="text-brand-600" />
            <h1 className="text-2xl font-semibold text-gray-900">SLA</h1>
          </div>
          <div className="flex gap-2">
            <select
              value={days}
              onChange={e => setDays(Number(e.target.value))}
              className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            >
              <option value={7}>Last 7 days</option>
              <option value={30}>Last 30 days</option>
              <option value={90}>Last 90 days</option>
            </select>
          </div>
        </div>

        {/* Stat cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            title="Total Tickets"
            value={total}
            icon={Shield}
            iconClass="bg-gray-100 text-gray-500"
          />
          <StatCard
            title="SLA Breached"
            value={breaches}
            valueClass={breaches > 0 ? 'text-red-600' : 'text-gray-900'}
            icon={AlertCircle}
            iconClass="bg-red-50 text-red-500"
          />
          <StatCard
            title="SLA Warning"
            value={warnings}
            valueClass={warnings > 0 ? 'text-yellow-600' : 'text-gray-900'}
            icon={AlertTriangle}
            iconClass="bg-yellow-50 text-yellow-500"
          />
          <StatCard
            title="Avg. First Response"
            value={minsToHuman(avgResp)}
            icon={Clock}
            iconClass="bg-brand-50 text-brand-600"
          />
        </div>

        {/* SLA Compliance chart + compliance % */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="card p-4">
            <h3 className="text-sm font-medium text-gray-700 mb-4">SLA Compliance</h3>
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={complianceChartData} barCategoryGap="40%">
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" vertical={false} />
                <XAxis dataKey="name" tick={{ fontSize: 12 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip
                  formatter={(value, name) => [value, name]}
                  contentStyle={{ borderRadius: 8, border: '1px solid #e5e7eb', fontSize: 12 }}
                />
                <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                  {complianceChartData.map(entry => (
                    <Cell key={entry.name} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="card p-4 flex flex-col justify-between">
            <h3 className="text-sm font-medium text-gray-700 mb-4">Compliance Rate</h3>
            <div className="flex items-center justify-center flex-1">
              <div className="text-center">
                <div className={clsx(
                  'text-5xl font-bold',
                  compliancePct >= 80 ? 'text-green-600' : compliancePct >= 60 ? 'text-yellow-600' : 'text-red-600',
                )}>
                  {compliancePct}%
                </div>
                <div className="text-sm text-gray-500 mt-2">tickets within SLA</div>
              </div>
            </div>
            <div className="flex items-center gap-3 justify-center mt-4">
              <span className="flex items-center gap-1 text-xs text-gray-500">
                <span className="inline-block w-2.5 h-2.5 rounded-full bg-green-500" /> OK
              </span>
              <span className="flex items-center gap-1 text-xs text-gray-500">
                <span className="inline-block w-2.5 h-2.5 rounded-full bg-yellow-400" /> Warning
              </span>
              <span className="flex items-center gap-1 text-xs text-gray-500">
                <span className="inline-block w-2.5 h-2.5 rounded-full bg-red-500" /> Breached
              </span>
            </div>
          </div>
        </div>

        {/* Filters */}
        <div className="card p-4">
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-sm font-medium text-gray-600">Filters:</span>

            <select
              value={channel}
              onChange={e => setChannel(e.target.value)}
              className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            >
              <option value="">All Channels</option>
              <option value="whatsapp">WhatsApp</option>
              <option value="email">Email</option>
              <option value="instagram">Instagram</option>
            </select>

            <select
              value={slaFilter}
              onChange={e => setSlaFilter(e.target.value)}
              className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            >
              <option value="">All SLA Status</option>
              <option value="ok">OK</option>
              <option value="warning">Warning</option>
              <option value="breached">Breached</option>
            </select>

            <div className="flex items-center gap-2">
              <label className="text-sm text-gray-500">From</label>
              <input
                type="date"
                value={startDate}
                onChange={e => setStartDate(e.target.value)}
                className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
              <label className="text-sm text-gray-500">To</label>
              <input
                type="date"
                value={endDate}
                onChange={e => setEndDate(e.target.value)}
                className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
            </div>

            {hasActiveFilters && (
              <button onClick={clearFilters} className="btn-secondary flex items-center gap-1 text-xs py-1.5">
                <X size={13} /> Clear
              </button>
            )}

            <span className="ml-auto text-xs text-gray-400">
              {filteredTickets.length} ticket{filteredTickets.length !== 1 ? 's' : ''}
            </span>
          </div>
        </div>

        {/* Ticket table */}
        <div className="card overflow-hidden">
          {/* Table header */}
          <div className="hidden md:flex items-center px-4 py-3 border-b border-gray-100 bg-gray-50 gap-3">
            <div className="w-8 text-xs text-gray-400 font-medium">#</div>
            <div className="flex-1">
              <SortHeader label="Subject" field="created_at" sort={sort} onSort={toggleSort} />
            </div>
            <div className="w-36">
              <SortHeader label="Channel" field="channel" sort={sort} onSort={toggleSort} />
            </div>
            <div className="w-36">
              <SortHeader label="1st Response" field="first_response_at" sort={sort} onSort={toggleSort} />
            </div>
            <div className="w-36">
              <SortHeader label="Resolution" field="resolved_at" sort={sort} onSort={toggleSort} />
            </div>
            <div className="w-28 text-right">
              <SortHeader label="SLA Status" field="sla_status" sort={sort} onSort={toggleSort} className="justify-end" />
            </div>
          </div>

          <div className="divide-y divide-gray-100">
            {loading ? (
              <div className="flex items-center justify-center py-16">
                <div className="w-7 h-7 border-4 border-gray-200 border-t-brand-600 rounded-full animate-spin" />
              </div>
            ) : filteredTickets.length === 0 ? (
              <div className="py-16 text-center">
                <Shield size={32} className="text-gray-200 mx-auto mb-3" />
                <p className="text-sm text-gray-400">No tickets match the current filters</p>
              </div>
            ) : (
              filteredTickets.map((t, i) => {
                const isSelected = selectedTicket?.id === t.id
                const respMins = firstResponseMins(t)
                const resMins  = resolutionMins(t)
                return (
                  <div
                    key={t.id}
                    onClick={() => openTicket(t.id)}
                    className={clsx(
                      'flex items-center gap-3 px-4 py-3 cursor-pointer transition-colors',
                      isSelected ? 'bg-brand-50 border-l-2 border-brand-500' : 'hover:bg-gray-50',
                    )}
                  >
                    <div className="w-8 text-sm text-gray-400 flex-shrink-0">{i + 1}</div>

                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-gray-900 truncate">{t.subject}</div>
                      <div className="text-xs text-gray-400 truncate">{t.customer_email}</div>
                    </div>

                    <div className="w-36 hidden md:block">
                      <span className="badge bg-gray-100 text-gray-600 text-xs">
                        {CHANNEL_LABEL[t.channel] ?? t.channel}
                      </span>
                    </div>

                    <div className="w-36 hidden md:block text-sm text-gray-600">
                      {respMins !== null ? (
                        <span title={`First reply: ${new Date(t.first_response_at).toLocaleString()}`}>
                          {minsToHuman(respMins)}
                        </span>
                      ) : '—'}
                    </div>

                    <div className="w-36 hidden md:block text-sm text-gray-600">
                      {resMins !== null ? (
                        <span title={`Resolved: ${new Date(t.resolved_at).toLocaleString()}`}>
                          {minsToHuman(resMins)}
                        </span>
                      ) : '—'}
                    </div>

                    <div className="w-28 flex justify-end flex-shrink-0">
                      <SLAStatusBadge status={t.sla_status} />
                    </div>
                  </div>
                )
              })
            )}
          </div>
        </div>
      </div>

      {/* ── Sidebar ─────────────────────────────────────────────────────────── */}
      <aside className={clsx(
        'flex-shrink-0 space-y-4 transition-all duration-200',
        selectedTicket ? 'w-80 lg:w-96' : 'w-64',
      )}>

        {/* Ticket detail */}
        <div className="card p-4">
          {selectedTicket ? (
            <>
              <div className="flex items-start justify-between mb-3">
                <h3 className="text-sm font-medium text-gray-700">Ticket Detail</h3>
                <button onClick={closeTicket} className="text-gray-400 hover:text-gray-600">
                  <X size={14} />
                </button>
              </div>

              <div className="space-y-3">
                <div>
                  <div className="text-sm font-semibold text-gray-900 leading-snug">{selectedTicket.subject}</div>
                  <div className="text-xs text-gray-400 mt-0.5">{selectedTicket.customer_email}</div>
                </div>

                <div className="flex flex-wrap gap-2">
                  <SLAStatusBadge status={selectedTicket.sla_status} />
                  <span className="badge bg-gray-100 text-gray-600">
                    {CHANNEL_LABEL[selectedTicket.channel] ?? selectedTicket.channel}
                  </span>
                  <span className="badge bg-gray-100 text-gray-600">
                    {selectedTicket.status}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="bg-gray-50 rounded-lg p-2">
                    <div className="text-gray-400 mb-1">SLA Due</div>
                    <div className="font-medium text-gray-700">
                      {selectedTicket.sla_due_at
                        ? new Date(selectedTicket.sla_due_at).toLocaleString()
                        : '—'}
                    </div>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-2">
                    <div className="text-gray-400 mb-1">Created</div>
                    <div className="font-medium text-gray-700">
                      {new Date(selectedTicket.created_at).toLocaleDateString()}
                    </div>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-2">
                    <div className="text-gray-400 mb-1">1st Response</div>
                    <div className="font-medium text-gray-700">
                      {minsToHuman(firstResponseMins(selectedTicket))}
                    </div>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-2">
                    <div className="text-gray-400 mb-1">Resolution</div>
                    <div className="font-medium text-gray-700">
                      {minsToHuman(resolutionMins(selectedTicket))}
                    </div>
                  </div>
                </div>
              </div>

              <div className="mt-4 border-t border-gray-100 pt-4">
                <h4 className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-3">
                  SLA History
                </h4>
                {sidebarLoading ? (
                  <div className="flex items-center justify-center py-6">
                    <div className="w-5 h-5 border-3 border-gray-200 border-t-brand-600 rounded-full animate-spin" />
                  </div>
                ) : (
                  <SLATimeline events={ticketHistory} />
                )}
              </div>
            </>
          ) : (
            <div className="py-8 text-center">
              <Shield size={28} className="text-gray-200 mx-auto mb-2" />
              <p className="text-sm text-gray-400">Select a ticket to view SLA details</p>
            </div>
          )}
        </div>

        {/* Status legend */}
        <div className="card p-4">
          <h3 className="text-sm font-medium text-gray-700 mb-3">Status Legend</h3>
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="badge bg-green-100 text-green-700">ok</span>
              <span className="text-xs text-gray-500">Within SLA deadline</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="badge bg-yellow-100 text-yellow-700">warning</span>
              <span className="text-xs text-gray-500">Approaching deadline</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="badge bg-red-100 text-red-700">breached</span>
              <span className="text-xs text-gray-500">SLA deadline passed</span>
            </div>
          </div>
        </div>
      </aside>
    </div>
  )
}
