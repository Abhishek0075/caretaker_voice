'use client'
import { useState } from 'react'
import type { AgentStatus, TavusSession } from '@/types'
import { AudioWave } from './AudioWave'

interface AvatarPanelProps {
  agentStatus: AgentStatus
  tavusSession: TavusSession | null
  callStatus: string
}

function AgentStatusBadge({ status }: { status: AgentStatus }) {
  const config = {
    idle: { label: 'Standby', color: 'var(--color-text-faint)', dot: '#3d6b6b' },
    listening: { label: 'Listening', color: '#60a5fa', dot: '#60a5fa' },
    thinking: { label: 'Thinking', color: '#fbbf24', dot: '#fbbf24' },
    speaking: { label: 'Speaking', color: 'var(--color-accent)', dot: 'var(--color-accent)' },
  }[status]

  return (
    <div className="flex items-center gap-2 px-3 py-1 rounded-full glass">
      <span
        className="w-2 h-2 rounded-full status-dot"
        style={{ backgroundColor: config.dot }}
      />
      <span className="text-xs font-medium" style={{ color: config.color }}>
        {config.label}
      </span>
    </div>
  )
}

export function AvatarPanel({ agentStatus, tavusSession, callStatus }: AvatarPanelProps) {
  const hasTavus = tavusSession?.conversation_url && tavusSession.status === 'created'

  return (
    <div className="flex flex-col items-center gap-4">
      {/* Avatar display */}
      <div className="relative">
        {hasTavus ? (
          // Tavus iframe avatar
          <div
            className="rounded-2xl overflow-hidden glass"
            style={{
              width: 280,
              height: 320,
              border: '1px solid var(--color-border)',
            }}
          >
            <iframe
              src={tavusSession!.conversation_url!}
              allow="camera; microphone; autoplay"
              className="w-full h-full"
              style={{ border: 'none' }}
              title="Aria - AI Avatar"
            />
          </div>
        ) : (
          // Animated fallback avatar
          <div
            className="relative rounded-2xl overflow-hidden flex items-center justify-center"
            style={{
              width: 280,
              height: 280,
              background: 'linear-gradient(135deg, var(--color-surface) 0%, var(--color-surface-2) 100%)',
              border: '1px solid var(--color-border)',
            }}
          >
            {/* Glow ring when speaking */}
            {agentStatus === 'speaking' && (
              <div
                className="absolute inset-0 rounded-2xl"
                style={{
                  boxShadow: '0 0 0 2px var(--color-accent), 0 0 40px var(--color-accent-glow)',
                  animation: 'pulse-ring 2s ease-in-out infinite',
                }}
              />
            )}

            {/* Ambient orbs */}
            <div
              style={{
                position: 'absolute',
                width: 200,
                height: 200,
                borderRadius: '50%',
                background: 'radial-gradient(circle, rgba(20,184,166,0.12) 0%, transparent 70%)',
                top: '50%',
                left: '50%',
                transform: 'translate(-50%, -50%)',
                animation: agentStatus !== 'idle' ? 'pulse-ring 3s ease-in-out infinite' : 'none',
              }}
            />

            {/* Avatar icon */}
            <div className="relative flex flex-col items-center gap-3">
              <div
                className="rounded-full flex items-center justify-center"
                style={{
                  width: 96,
                  height: 96,
                  background: 'linear-gradient(135deg, rgba(20,184,166,0.2) 0%, rgba(20,184,166,0.05) 100%)',
                  border: '2px solid var(--color-border)',
                  fontSize: 42,
                }}
              >
                🩺
              </div>
              <div>
                <p className="text-center font-semibold" style={{ color: 'var(--color-text)', fontFamily: 'var(--font-display)' }}>
                  Aria
                </p>
                <p className="text-center text-xs" style={{ color: 'var(--color-text-muted)' }}>
                  Mykare Health AI
                </p>
              </div>
              {callStatus === 'connected' && (
                <AudioWave status={agentStatus} size="md" />
              )}
            </div>
          </div>
        )}

        {/* Status badge overlay */}
        {callStatus === 'connected' && (
          <div className="absolute -bottom-3 left-1/2 -translate-x-1/2">
            <AgentStatusBadge status={agentStatus} />
          </div>
        )}
      </div>
    </div>
  )
}
