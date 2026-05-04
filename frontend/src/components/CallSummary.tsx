'use client'
import type { Appointment } from '@/types'

interface CallSummaryProps {
  summary: string | null
  appointments: Appointment[]
  sessionId: string | null
  onNewCall: () => void
}

export function CallSummary({ summary, appointments, sessionId, onNewCall }: CallSummaryProps) {
  const timestamp = new Date().toLocaleString()

  return (
    <div className="glass rounded-2xl p-6 flex flex-col gap-5 slide-up max-w-lg w-full mx-auto">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div
          className="w-10 h-10 rounded-xl flex items-center justify-center text-xl"
          style={{ background: 'rgba(74,222,128,0.1)', border: '1px solid rgba(74,222,128,0.2)' }}
        >
          📋
        </div>
        <div>
          <h3 className="font-semibold" style={{ fontFamily: 'var(--font-display)', color: 'var(--color-text)' }}>
            Call Summary
          </h3>
          <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>{timestamp}</p>
        </div>
        {sessionId && (
          <span
            className="ml-auto text-xs font-mono px-2 py-1 rounded"
            style={{ background: 'rgba(20,184,166,0.1)', color: 'var(--color-accent)' }}
          >
            #{sessionId.slice(-8)}
          </span>
        )}
      </div>

      {/* Summary text */}
      {summary && (
        <div className="rounded-xl p-4" style={{ background: 'var(--color-surface-2)' }}>
          <p className="text-sm leading-relaxed" style={{ color: 'var(--color-text)' }}>
            {summary}
          </p>
        </div>
      )}

      {/* Appointments booked */}
      {appointments.length > 0 && (
        <div className="flex flex-col gap-2">
          <p className="text-xs font-mono uppercase tracking-widest" style={{ color: 'var(--color-text-faint)' }}>
            Appointments
          </p>
          {appointments.map(appt => (
            <div
              key={appt.id}
              className="flex items-center gap-3 p-3 rounded-xl"
              style={{ background: 'rgba(74,222,128,0.06)', border: '1px solid rgba(74,222,128,0.15)' }}
            >
              <span className="text-lg">🗓</span>
              <div className="flex-1">
                <p className="text-sm font-medium" style={{ color: 'var(--color-text)' }}>
                  {appt.date} at {appt.time}
                </p>
                <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                  {appt.doctor} · {appt.department} · ID #{appt.id}
                </p>
              </div>
              <span
                className="text-xs px-2 py-0.5 rounded-full"
                style={{ background: 'rgba(74,222,128,0.1)', color: '#4ade80' }}
              >
                ✓ Confirmed
              </span>
            </div>
          ))}
        </div>
      )}

      {/* No appointments */}
      {appointments.length === 0 && (
        <p className="text-sm text-center" style={{ color: 'var(--color-text-muted)' }}>
          No appointments booked in this session.
        </p>
      )}

      {/* Download PDF */}
      {sessionId && (
        <button
          onClick={() => {
            const link = document.createElement('a')
            link.href = `${process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'}/api/sessions/${sessionId}/pdf`
            link.download = `call_summary_${sessionId}.pdf`
            link.click()
          }}
          className="w-full py-3 rounded-xl font-medium text-sm transition-all duration-200 mb-2"
          style={{
            background: 'rgba(74,222,128,0.1)',
            color: '#4ade80',
            border: '1px solid rgba(74,222,128,0.2)',
            cursor: 'pointer',
          }}
          onMouseEnter={e => (e.currentTarget.style.opacity = '0.85')}
          onMouseLeave={e => (e.currentTarget.style.opacity = '1')}
        >
          📄 Download Summary PDF
        </button>
      )}

      {/* CTA */}
      <button
        onClick={onNewCall}
        className="w-full py-3 rounded-xl font-medium text-sm transition-all duration-200"
        style={{
          background: 'linear-gradient(135deg, var(--color-accent) 0%, #0d9488 100%)',
          color: '#fff',
          border: 'none',
          cursor: 'pointer',
        }}
        onMouseEnter={e => (e.currentTarget.style.opacity = '0.85')}
        onMouseLeave={e => (e.currentTarget.style.opacity = '1')}
      >
        Start New Call
      </button>
    </div>
  )
}
