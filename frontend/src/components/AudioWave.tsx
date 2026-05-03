'use client'
import type { AgentStatus } from '@/types'

interface AudioWaveProps {
  status: AgentStatus
  size?: 'sm' | 'md' | 'lg'
}

const BAR_COUNTS = { sm: 5, md: 7, lg: 11 }
const HEIGHTS = {
  sm: [12, 18, 24, 18, 12],
  md: [10, 16, 24, 30, 24, 16, 10],
  lg: [8, 14, 20, 26, 32, 36, 32, 26, 20, 14, 8],
}

export function AudioWave({ status, size = 'md' }: AudioWaveProps) {
  const count = BAR_COUNTS[size]
  const heights = HEIGHTS[size]
  const isActive = status === 'speaking' || status === 'listening'
  const color = status === 'speaking' ? '#14b8a6' : status === 'listening' ? '#60a5fa' : '#3d6b6b'

  const barW = size === 'sm' ? 3 : size === 'md' ? 4 : 3
  const gap = size === 'sm' ? 3 : 4

  return (
    <div
      className="flex items-center justify-center"
      style={{ gap: `${gap}px`, height: `${Math.max(...heights) + 4}px` }}
      role="img"
      aria-label={`Agent is ${status}`}
    >
      {heights.map((h, i) => (
        <div
          key={i}
          className={isActive ? 'wave-bar' : ''}
          style={{
            width: `${barW}px`,
            height: `${isActive ? h : Math.floor(h * 0.3)}px`,
            backgroundColor: color,
            borderRadius: '99px',
            transition: 'height 0.3s ease, background-color 0.3s ease',
            animationDelay: isActive ? `${i * 0.08}s` : '0s',
          }}
        />
      ))}
    </div>
  )
}
