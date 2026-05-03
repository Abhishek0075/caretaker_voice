import type { TokenResponse, Appointment, AvailableSlot, TavusSession, CallSession } from '@/types'

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BACKEND}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(err || `HTTP ${res.status}`)
  }
  return res.json()
}

export const api = {
  // LiveKit token
  getToken: (roomName?: string, participantName?: string) =>
    apiFetch<TokenResponse>('/api/token', {
      method: 'POST',
      body: JSON.stringify({ room_name: roomName, participant_name: participantName }),
    }),

  // Tavus avatar
  createTavusSession: (roomName: string, sessionId: string) =>
    apiFetch<TavusSession>('/api/tavus/session', {
      method: 'POST',
      body: JSON.stringify({ room_name: roomName, session_id: sessionId }),
    }),

  endTavusSession: (conversationId: string) =>
    apiFetch(`/api/tavus/session/${conversationId}`, { method: 'DELETE' }),

  // Appointments
  getSlots: (date?: string) =>
    apiFetch<{ slots: AvailableSlot[] }>(`/api/slots${date ? `?date=${date}` : ''}`),

  getAppointments: (phone: string) =>
    apiFetch<{ appointments: Appointment[] }>(`/api/appointments/${phone}`),

  // Call sessions
  getSession: (sessionId: string) =>
    apiFetch<CallSession>(`/api/sessions/${sessionId}`),

  health: () => apiFetch<{ status: string }>('/api/health'),
}
