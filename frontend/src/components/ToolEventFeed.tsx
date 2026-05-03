'use client'
import type { ToolEvent, ToolName } from '@/types'

const TOOL_ICONS: Record<ToolName, string> = {
  identify_user: '👤',
  fetch_slots: '📅',
  book_appointment: '✅',
  retrieve_appointments: '📋',
  cancel_appointment: '🚫',
  modify_appointment: '✏️',
  end_conversation: '👋',
}

interface ToolEventFeedProps {
  events: ToolEvent[]
}

export function ToolEventFeed({ events }: ToolEventFeedProps) {
  if (events.length === 0) return null

  return (
    <div className="flex flex-col gap-2">
      <p className="text-xs font-mono uppercase tracking-widest" style={{ color: 'var(--color-text-faint)' }}>
        Agent Actions
      </p>
      <div className="flex flex-col gap-2 max-h-56 overflow-y-auto">
        {events.map((event, idx) => (
          <div
            key={event.id}
            className="glass rounded-lg px-3 py-2 flex items-center gap-3 slide-up"
            style={{
              opacity: idx === 0 ? 1 : Math.max(0.4, 1 - idx * 0.15),
              borderColor:
                event.status === 'success'
                  ? 'rgba(74, 222, 128, 0.25)'
                  : event.status === 'error'
                  ? 'rgba(248, 113, 113, 0.25)'
                  : 'rgba(251, 191, 36, 0.25)',
            }}
          >
            <span className="text-base">{TOOL_ICONS[event.tool]}</span>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate" style={{ color: 'var(--color-text)' }}>
                {event.label}
              </p>
              <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                {event.timestamp.toLocaleTimeString()}
              </p>
            </div>
            <span
              className="text-xs font-mono px-2 py-0.5 rounded-full"
              style={{
                background:
                  event.status === 'success'
                    ? 'rgba(74, 222, 128, 0.1)'
                    : event.status === 'error'
                    ? 'rgba(248, 113, 113, 0.1)'
                    : 'rgba(251, 191, 36, 0.1)',
                color:
                  event.status === 'success'
                    ? '#4ade80'
                    : event.status === 'error'
                    ? '#f87171'
                    : '#fbbf24',
              }}
            >
              {event.status === 'pending' ? '⏳' : event.status === 'success' ? '✓' : '✗'}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
