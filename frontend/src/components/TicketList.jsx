import { formatDistanceToNow } from 'date-fns'

const PRIORITY_COLORS = {
  low: 'bg-gray-100 text-gray-500',
  normal: 'bg-blue-50 text-blue-600',
  high: 'bg-orange-50 text-orange-600',
  urgent: 'bg-red-50 text-red-600',
}
const STATUS_COLORS = {
  open: 'bg-green-50 text-green-700',
  pending: 'bg-yellow-50 text-yellow-700',
  resolved: 'bg-gray-100 text-gray-500',
  closed: 'bg-gray-200 text-gray-400',
}
const SOURCE_ICONS = {
  email: '✉️',
  manual: '✏️',
  shopify: '🛍️',
}

function TicketSkeleton() {
  return (
    <div className="card p-4 animate-pulse">
      <div className="flex items-start gap-3">
        <div className="w-8 h-8 rounded-full bg-gray-200 flex-shrink-0" />
        <div className="flex-1 space-y-2">
          <div className="h-4 bg-gray-200 rounded w-3/4" />
          <div className="h-3 bg-gray-100 rounded w-1/2" />
          <div className="flex gap-2 mt-2">
            <div className="h-5 w-16 bg-gray-100 rounded-full" />
            <div className="h-5 w-12 bg-gray-100 rounded-full" />
          </div>
        </div>
      </div>
    </div>
  )
}

export default function TicketList({ tickets, loading, onSelect }) {
  if (loading) {
    return (
      <div className="space-y-2">
        {[1, 2, 3, 4, 5].map((i) => <TicketSkeleton key={i} />)}
      </div>
    )
  }

  if (tickets.length === 0) {
    return (
      <div className="card p-12 text-center">
        <div className="w-12 h-12 mx-auto mb-4 rounded-full bg-gray-100 flex items-center justify-center">
          <svg className="w-6 h-6 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
          </svg>
        </div>
        <p className="text-gray-500 font-medium">No tickets found</p>
        <p className="text-gray-400 text-sm mt-1">Try adjusting your filters</p>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {tickets.map((ticket) => (
        <button
          key={ticket.id}
          onClick={() => onSelect(ticket.id)}
          className="card w-full p-4 text-left hover:border-brand-300 hover:shadow-md transition-all group"
        >
          <div className="flex items-start gap-3">
            {/* Avatar */}
            <div className="w-9 h-9 rounded-full bg-brand-100 flex items-center justify-center text-brand-700 font-semibold text-sm flex-shrink-0">
              {(ticket.customer_name?.[0] || ticket.customer_email?.[0] || '?').toUpperCase()}
            </div>

            <div className="flex-1 min-w-0">
              <div className="flex items-start justify-between gap-2">
                <p className="font-semibold text-gray-900 truncate group-hover:text-brand-700 transition-colors">
                  {ticket.subject}
                </p>
                <span className="text-xs text-gray-400 flex-shrink-0 mt-0.5">
                  {formatDistanceToNow(new Date(ticket.updated_at), { addSuffix: true })}
                </span>
              </div>

              <p className="text-sm text-gray-500 truncate mt-0.5">
                {SOURCE_ICONS[ticket.source]} {ticket.customer_name || ticket.customer_email}
                {ticket.customer_name && (
                  <span className="text-gray-400"> · {ticket.customer_email}</span>
                )}
              </p>

              <div className="flex flex-wrap items-center gap-1.5 mt-2">
                <span className={`badge ${STATUS_COLORS[ticket.status]}`}>{ticket.status}</span>
                <span className={`badge ${PRIORITY_COLORS[ticket.priority]}`}>{ticket.priority}</span>
                {ticket.assignee_name && (
                  <span className="badge bg-purple-50 text-purple-600">
                    {ticket.assignee_name}
                  </span>
                )}
                {ticket.tags?.slice(0, 2).map((tag) => (
                  <span key={tag} className="badge bg-gray-100 text-gray-500">{tag}</span>
                ))}
                <span className="ml-auto text-xs text-gray-400">
                  {ticket.message_count} {ticket.message_count === 1 ? 'msg' : 'msgs'}
                </span>
              </div>
            </div>
          </div>
        </button>
      ))}
    </div>
  )
}
