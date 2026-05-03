'use client'
import { useEffect, useRef, useCallback } from 'react'
import {
  LiveKitRoom,
  useVoiceAssistant,
  BarVisualizer,
  VoiceAssistantControlBar,
  useRoomContext,
} from '@livekit/components-react'
import type { AgentStatus, ToolEvent, ToolName } from '@/types'

// ─── Inner component that uses LiveKit hooks ───
function VoiceSessionInner({
  onAgentStatusChange,
  onToolCall,
  onDisconnect,
}: {
  onAgentStatusChange: (status: AgentStatus) => void
  onToolCall: (tool: ToolName, status: 'pending' | 'success' | 'error', result?: string) => void
  onDisconnect: () => void
}) {
  const { state: agentState, audioTrack } = useVoiceAssistant()
  const room = useRoomContext()

  // Map LiveKit agent state to our AgentStatus
  useEffect(() => {
    const map: Record<string, AgentStatus> = {
      disconnected: 'idle',
      connecting: 'idle',
      initializing: 'idle',
      listening: 'listening',
      thinking: 'thinking',
      speaking: 'speaking',
    }
    onAgentStatusChange(map[agentState] || 'idle')
  }, [agentState, onAgentStatusChange])

  // Listen for data messages from the agent (tool call events)
  useEffect(() => {
    if (!room) return

    const handler = (payload: Uint8Array) => {
      try {
        const text = new TextDecoder().decode(payload)
        const data = JSON.parse(text)
        if (data.type === 'tool_call') {
          onToolCall(data.tool as ToolName, data.status, data.result)
        }
      } catch { }
    }

    room.on('dataReceived', handler)
    return () => { room.off('dataReceived', handler) }
  }, [room, onToolCall])

  return (
    <div className="flex flex-col items-center gap-4 w-full">
      {/* Audio visualizer */}
      <div
        className="w-full rounded-xl overflow-hidden"
        style={{
          height: 60,
          background: 'var(--color-surface-2)',
          border: '1px solid var(--color-border)',
        }}
      >
        <BarVisualizer
          state={agentState}
          barCount={32}
          trackRef={audioTrack}
          style={{ width: '100%', height: '100%' }}
          options={{ minHeight: 2 }}
        />
      </div>

      {/* Control bar (mute/unmute, disconnect) */}
      <VoiceAssistantControlBar
        onDisconnectClick={onDisconnect}
        style={{ background: 'transparent' } as React.CSSProperties}
      />
    </div>
  )
}

// ─── Outer component with LiveKitRoom provider ───
interface LiveKitSessionProps {
  token: string
  livekitUrl: string
  onAgentStatusChange: (status: AgentStatus) => void
  onToolCall: (tool: ToolName, status: 'pending' | 'success' | 'error', result?: string) => void
  onDisconnect: () => void
}

export function LiveKitSession({
  token,
  livekitUrl,
  onAgentStatusChange,
  onToolCall,
  onDisconnect,
}: LiveKitSessionProps) {
  return (
    <LiveKitRoom
      token={token}
      serverUrl={livekitUrl}
      connect={true}
      audio={true}
      video={false}
      onDisconnected={onDisconnect}
      style={{ background: 'transparent' }}
    >
      <VoiceSessionInner
        onAgentStatusChange={onAgentStatusChange}
        onToolCall={onToolCall}
        onDisconnect={onDisconnect}
      />
    </LiveKitRoom>
  )
}
