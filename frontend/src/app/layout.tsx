import type { Metadata } from 'next'
import './globals.css'
import '@livekit/components-styles'

export const metadata: Metadata = {
  title: 'Mykare Health — AI Voice Assistant',
  description: 'Book and manage your healthcare appointments with Aria, our AI voice assistant.',
  icons: { icon: '/favicon.ico' },
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="relative min-h-screen">
        <div className="relative z-10">{children}</div>
      </body>
    </html>
  )
}
