'use client'
import { useState, useCallback, useEffect } from 'react'
import dynamic from 'next/dynamic'
import { useCallSession } from '@/hooks/useCallSession'
import { AvatarPanel } from '@/components/AvatarPanel'
import { ToolEventFeed } from '@/components/ToolEventFeed'
import { CallSummary } from '@/components/CallSummary'
import { AudioWave } from '@/components/AudioWave'
import type { AgentStatus, ToolName, Appointment } from '@/types'
import { api } from '@/lib/api'

// Dynamically import LiveKit to avoid SSR issues
const LiveKitSession = dynamic(
  () => import('@/components/LiveKitSession').then(m => m.LiveKitSession),
  { ssr: false }
)

export default function HomePage() {
  const {
    callStatus,
    agentStatus,
    setAgentStatus,
    token,
    tavusSession,
    toolEvents,
    callSummary,
    sessionId,
    error,
    startCall,
    endCall,
    resetCall,
    addToolEvent,
  } = useCallSession()

  const [participantName, setParticipantName] = useState('Patient')
  const [appointments, setAppointments] = useState<Appointment[]>([])
  const [backendOk, setBackendOk] = useState<boolean | null>(null)

  // Check backend health
  useEffect(() => {
    api.health().then(() => setBackendOk(true)).catch(() => setBackendOk(false))
  }, [])

  // Fetch appointments when tool calls indicate booking
  useEffect(() => {
    const bookEvent = toolEvents.find(e => e.tool === 'book_appointment' && e.status === 'success')
    if (bookEvent) {
      // Try to refresh appointments from summary data
      setAppointments(prev => [...prev])
    }
  }, [toolEvents])

  const handleAgentStatusChange = useCallback((status: AgentStatus) => {
    setAgentStatus(status)
  }, [setAgentStatus])

  const handleToolCall = useCallback((tool: ToolName, status: 'pending' | 'success' | 'error', result?: string) => {
    addToolEvent(tool, status, result)
  }, [addToolEvent])

  const handleDisconnect = useCallback(() => {
    endCall()
  }, [endCall])

  const handleStartCall = async () => {
    await startCall(participantName)
  }

  const livekitUrl = process.env.NEXT_PUBLIC_LIVEKIT_URL || token?.livekit_url || ''

  return (
    <main
      className="min-h-screen flex flex-col"
      style={{ fontFamily: 'var(--font-body)' }}
    >
      {/* ── Header ── */}
      <header
        className="relative z-20 flex items-center justify-between px-6 py-4"
        style={{ borderBottom: '1px solid var(--color-border)' }}
      >
        <div className="flex items-center gap-3">
          <div
            className="w-9 h-9 rounded-xl flex items-center justify-center text-lg"
            style={{ background: 'var(--color-accent-soft)', border: '1px solid var(--color-border)' }}
          >
            🩺
          </div>
          <div>
            <h1
              className="text-lg font-semibold leading-none"
              style={{ fontFamily: 'var(--font-display)', color: 'var(--color-text)' }}
            >
              Mykare Health
            </h1>
            <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
              AI Voice Receptionist
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span
            className="w-2 h-2 rounded-full"
            style={{
              backgroundColor: backendOk === null ? '#fbbf24' : backendOk ? '#4ade80' : '#f87171',
              animation: backendOk === true ? 'blink 2s infinite' : 'none',
            }}
          />
          <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
            {backendOk === null ? 'Checking…' : backendOk ? 'System Online' : 'Backend Offline'}
          </span>
        </div>
      </header>

      {/* ── Main content ── */}
      <div className="relative z-10 flex-1 flex items-center justify-center px-4 py-8">
        {callStatus === 'ended' ? (
          /* ── Call ended: show summary ── */
          <CallSummary
            summary={callSummary}
            appointments={appointments}
            sessionId={sessionId}
            onNewCall={resetCall}
          />
        ) : (
          <div className="w-full max-w-5xl grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">

            {/* ── Left panel: avatar + controls ── */}
            <div className="lg:col-span-1 flex flex-col items-center gap-6">
              <AvatarPanel
                agentStatus={agentStatus}
                tavusSession={tavusSession}
                callStatus={callStatus}
              />

              {/* ── Call controls ── */}
              {callStatus === 'idle' && (
                <div className="w-full max-w-xs flex flex-col gap-4 slide-up">
                  <div className="flex flex-col gap-2">
                    <label className="text-xs font-mono" style={{ color: 'var(--color-text-muted)' }}>
                      Your Name (optional)
                    </label>
                    <input
                      value={participantName}
                      onChange={e => setParticipantName(e.target.value)}
                      placeholder="Patient"
                      className="w-full px-4 py-2.5 rounded-xl text-sm outline-none transition-all"
                      style={{
                        background: 'var(--color-surface)',
                        border: '1px solid var(--color-border)',
                        color: 'var(--color-text)',
                      }}
                      onFocus={e => (e.currentTarget.style.borderColor = 'var(--color-accent)')}
                      onBlur={e => (e.currentTarget.style.borderColor = 'var(--color-border)')}
                    />
                  </div>

                  <button
                    onClick={handleStartCall}
                    disabled={!backendOk}
                    className="w-full py-3.5 rounded-xl font-semibold text-sm transition-all duration-200 relative overflow-hidden"
                    style={{
                      background: backendOk
                        ? 'linear-gradient(135deg, var(--color-accent) 0%, #0d9488 100%)'
                        : 'var(--color-surface)',
                      color: '#fff',
                      border: 'none',
                      cursor: backendOk ? 'pointer' : 'not-allowed',
                      boxShadow: backendOk ? '0 4px 24px var(--color-accent-glow)' : 'none',
                    }}
                    onMouseEnter={e => { if (backendOk) e.currentTarget.style.transform = 'translateY(-1px)' }}
                    onMouseLeave={e => { e.currentTarget.style.transform = 'translateY(0)' }}
                  >
                    📞 Start Voice Call
                  </button>

                  {error && (
                    <p className="text-xs text-center" style={{ color: 'var(--color-danger)' }}>
                      {error}
                    </p>
                  )}
                </div>
              )}

              {callStatus === 'connecting' && (
                <div className="flex flex-col items-center gap-3 slide-up">
                  <div className="w-8 h-8 rounded-full border-2 border-t-transparent animate-spin"
                    style={{ borderColor: 'var(--color-accent)', borderTopColor: 'transparent' }} />
                  <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>Connecting…</p>
                </div>
              )}

              {callStatus === 'connected' && token && (
                <div className="w-full max-w-xs slide-up">
                  <LiveKitSession
                    token={token.token}
                    livekitUrl={livekitUrl}
                    onAgentStatusChange={handleAgentStatusChange}
                    onToolCall={handleToolCall}
                    onDisconnect={handleDisconnect}
                  />
                </div>
              )}
            </div>

            {/* ── Center + Right: info panels ── */}
            <div className="lg:col-span-2 flex flex-col gap-6">

              {/* Welcome / active session info */}
              {callStatus === 'idle' && (
                <div className="glass rounded-2xl p-6 slide-up">
                  <h2
                    className="text-2xl font-semibold mb-2"
                    style={{ fontFamily: 'var(--font-display)', color: 'var(--color-text)' }}
                  >
                    Meet Aria, your health AI assistant
                  </h2>
                  <p className="text-sm mb-5" style={{ color: 'var(--color-text-muted)', lineHeight: 1.7 }}>
                    Aria can help you book appointments, check availability, and manage your healthcare schedule — all through natural voice conversation.
                  </p>

                  <div className="grid grid-cols-2 gap-3">
                    {[
                      { icon: '🎤', title: 'Natural Speech', desc: 'Just talk — no buttons or forms needed' },
                      { icon: '📅', title: 'Instant Booking', desc: 'Book, modify or cancel appointments in seconds' },
                      { icon: '🔒', title: 'Verified Identity', desc: 'Secure phone-based patient identification' },
                      { icon: '📋', title: 'Smart Summary', desc: 'Detailed call summary generated automatically' },
                    ].map(item => (
                      <div
                        key={item.title}
                        className="rounded-xl p-4"
                        style={{ background: 'var(--color-surface-2)', border: '1px solid var(--color-border)' }}
                      >
                        <div className="text-xl mb-2">{item.icon}</div>
                        <p className="text-sm font-medium mb-1" style={{ color: 'var(--color-text)' }}>{item.title}</p>
                        <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>{item.desc}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Active call panel */}
              {callStatus === 'connected' && (
                <div className="glass rounded-2xl p-6 slide-up">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full bg-green-400 status-dot" />
                      <span className="text-sm font-medium" style={{ color: 'var(--color-text)' }}>
                        Call in Progress
                      </span>
                    </div>
                    <AudioWave status={agentStatus} size="sm" />
                  </div>

                  <ToolEventFeed events={toolEvents} />

                  {toolEvents.length === 0 && (
                    <div className="flex flex-col items-center justify-center py-8 gap-3">
                      <div style={{ color: 'var(--color-text-faint)', fontSize: 40 }}>🎙️</div>
                      <p className="text-sm text-center" style={{ color: 'var(--color-text-muted)' }}>
                        Aria is ready. Say hello to get started!
                      </p>
                    </div>
                  )}
                </div>
              )}

              {/* How to use */}
              {callStatus === 'idle' && (
                <div className="glass rounded-2xl p-5">
                  <p className="text-xs font-mono uppercase tracking-widest mb-4" style={{ color: 'var(--color-text-faint)' }}>
                    Try saying
                  </p>
                  <div className="flex flex-col gap-2">
                    {[
                      '"I\'d like to book an appointment for tomorrow"',
                      '"What slots are available this week?"',
                      '"Can you show me my upcoming appointments?"',
                      '"I need to cancel my appointment on Friday"',
                    ].map(phrase => (
                      <div
                        key={phrase}
                        className="px-4 py-2.5 rounded-lg text-sm"
                        style={{
                          background: 'var(--color-accent-soft)',
                          border: '1px solid var(--color-border)',
                          color: 'var(--color-accent)',
                          fontStyle: 'italic',
                        }}
                      >
                        {phrase}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* ── Footer ── */}
      <footer
        className="relative z-20 px-6 py-3 flex items-center justify-between"
        style={{ borderTop: '1px solid var(--color-border)' }}
      >
        <p className="text-xs" style={{ color: 'var(--color-text-faint)' }}>
          Powered by LiveKit · Deepgram · Cartesia · Gemini
        </p>
        <p className="text-xs" style={{ color: 'var(--color-text-faint)' }}>
          Mykare Health © 2024
        </p>
      </footer>
    </main>
  )
}
