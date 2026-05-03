'use client'
import { useState, useCallback, useRef } from 'react'
import { api } from '@/lib/api'
import type { TokenResponse, TavusSession, CallStatus, AgentStatus, ToolEvent, ToolName } from '@/types'

const TOOL_LABELS: Record<ToolName, string> = {
  identify_user: 'Verifying identity…',
  fetch_slots: 'Fetching available slots…',
  book_appointment: 'Booking appointment…',
  retrieve_appointments: 'Loading appointments…',
  cancel_appointment: 'Cancelling appointment…',
  modify_appointment: 'Updating appointment…',
  end_conversation: 'Wrapping up call…',
}

const TOOL_SUCCESS_LABELS: Record<ToolName, string> = {
  identify_user: 'Identity verified ✓',
  fetch_slots: 'Slots loaded ✓',
  book_appointment: 'Appointment booked ✓',
  retrieve_appointments: 'Appointments loaded ✓',
  cancel_appointment: 'Appointment cancelled ✓',
  modify_appointment: 'Appointment updated ✓',
  end_conversation: 'Call ended ✓',
}

export function useCallSession() {
  const [callStatus, setCallStatus] = useState<CallStatus>('idle')
  const [agentStatus, setAgentStatus] = useState<AgentStatus>('idle')
  const [token, setToken] = useState<TokenResponse | null>(null)
  const [tavusSession, setTavusSession] = useState<TavusSession | null>(null)
  const [toolEvents, setToolEvents] = useState<ToolEvent[]>([])
  const [callSummary, setCallSummary] = useState<string | null>(null)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const startTimeRef = useRef<Date | null>(null)

  const startCall = useCallback(async (participantName?: string) => {
    try {
      setCallStatus('connecting')
      setError(null)
      setToolEvents([])
      setCallSummary(null)

      const tokenData = await api.getToken(undefined, participantName || 'Patient')
      setToken(tokenData)
      setSessionId(tokenData.session_id)
      startTimeRef.current = new Date()

      // Try to create Tavus session
      try {
        const tavus = await api.createTavusSession(tokenData.room_name, tokenData.session_id)
        setTavusSession(tavus)
      } catch {
        // Tavus optional
        console.log('Tavus not available, audio-only mode')
      }

      setCallStatus('connected')
    } catch (err: any) {
      setError(err.message || 'Failed to connect')
      setCallStatus('idle')
    }
  }, [])

  const endCall = useCallback(async () => {
    if (tavusSession?.conversation_id) {
      try {
        await api.endTavusSession(tavusSession.conversation_id)
      } catch { }
    }

    if (sessionId) {
      try {
        const session = await api.getSession(sessionId)
        if (session?.summary) setCallSummary(session.summary)
      } catch { }
    }

    setCallStatus('ended')
    setAgentStatus('idle')
  }, [tavusSession, sessionId])

  const addToolEvent = useCallback((tool: ToolName, status: 'pending' | 'success' | 'error', result?: string) => {
    const event: ToolEvent = {
      id: typeof window !== 'undefined' ? `${Date.now()}-${Math.random().toString(36).slice(2)}` : Math.random().toString(36).slice(2),
      tool,
      label: status === 'pending' ? TOOL_LABELS[tool] : TOOL_SUCCESS_LABELS[tool],
      status,
      timestamp: new Date(),
      result,
    }
    setToolEvents(prev => [event, ...prev].slice(0, 10))

    if (tool === 'end_conversation' && status === 'success') {
      setTimeout(endCall, 2000)
    }
  }, [endCall])

  const resetCall = useCallback(() => {
    setCallStatus('idle')
    setAgentStatus('idle')
    setToken(null)
    setTavusSession(null)
    setToolEvents([])
    setCallSummary(null)
    setSessionId(null)
    setError(null)
    startTimeRef.current = null
  }, [])

  return {
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
  }
}