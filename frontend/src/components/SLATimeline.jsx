// SLA event timeline — color-coded dots by event type, with vertical connecting line
import clsx from 'clsx'

// Map event name → dot color + label color
function eventStyle(eventName = '') {
  const name = eventName.toLowerCase()
  if (name.includes('breach'))  return { dot: 'bg-red-400',    ring: 'ring-red-100',    text: 'text-red-700' }
  if (name.includes('warning')) return { dot: 'bg-yellow-400', ring: 'ring-yellow-100', text: 'text-yellow-700' }
  if (name.includes('ok') || name.includes('resolved') || name.includes('created'))
                                 return { dot: 'bg-green-400',  ring: 'ring-green-100',  text: 'text-green-700' }
  return                                { dot: 'bg-gray-300',   ring: 'ring-gray-100',   text: 'text-gray-600' }
}

function EventRow({ e, isLast }) {
  const time = e.created_at ? new Date(e.created_at).toLocaleString() : ''
  const style = eventStyle(e.event)

  return (
    <div className="flex items-start gap-3 relative">
      {/* Dot + vertical line */}
      <div className="flex flex-col items-center flex-shrink-0" style={{ width: 18 }}>
        <span className={clsx(
          'w-2.5 h-2.5 rounded-full ring-4 flex-shrink-0 mt-1',
          style.dot, style.ring,
        )} />
        {!isLast && <div className="w-px flex-1 bg-gray-200 mt-1 min-h-[1.5rem]" />}
      </div>

      {/* Content */}
      <div className="flex-1 pb-4">
        <div className={clsx('text-xs font-semibold uppercase tracking-wide', style.text)}>
          {e.event || 'Event'}
        </div>
        {e.description && (
          <div className="text-xs text-gray-600 mt-0.5 leading-snug">{e.description}</div>
        )}
        <div className="text-xs text-gray-400 mt-1">{time}</div>
      </div>
    </div>
  )
}

export default function SLATimeline({ events = [] }) {
  if (!events || events.length === 0) {
    return (
      <div className="py-4 text-center">
        <p className="text-xs text-gray-400">No history events found</p>
      </div>
    )
  }

  return (
    <div>
      {events.map((e, i) => (
        <EventRow
          key={e._id || `${e.event}-${e.created_at}-${i}`}
          e={e}
          isLast={i === events.length - 1}
        />
      ))}
    </div>
  )
}
