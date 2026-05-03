export interface TokenResponse {
  token: string
  room_name: string
  livekit_url: string
  session_id: string
}

export interface Appointment {
  id: number
  user_id: number
  phone_number: string
  patient_name: string
  date: string
  time: string
  doctor: string
  department: string
  status: 'confirmed' | 'cancelled'
  notes: string
  created_at: string
}

export interface AvailableSlot {
  date: string
  day: string
  available_times: string[]
}

export interface CallSession {
  id: number
  session_id: string
  phone_number: string
  patient_name: string
  room_name: string
  summary: string
  appointments_booked: string
  started_at: string
  ended_at: string
  duration_seconds: number
}

export interface TavusSession {
  conversation_id: string
  conversation_url: string | null
  status: string
  message?: string
}

export type ToolName =
  | 'identify_user'
  | 'fetch_slots'
  | 'book_appointment'
  | 'retrieve_appointments'
  | 'cancel_appointment'
  | 'modify_appointment'
  | 'end_conversation'

export interface ToolEvent {
  id: string
  tool: ToolName
  label: string
  status: 'pending' | 'success' | 'error'
  timestamp: Date
  result?: string
}

export type CallStatus = 'idle' | 'connecting' | 'connected' | 'ended'
export type AgentStatus = 'idle' | 'listening' | 'thinking' | 'speaking'
