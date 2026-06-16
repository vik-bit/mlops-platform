import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'MLOps Platform',
  description: 'Enterprise ML management platform',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="antialiased bg-background font-sans">{children}</body>
    </html>
  )
}
