'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Sidebar from '@/components/sidebar'
import Dashboard from '@/components/dashboard'
import TrainingView from '@/components/training-view'
import DeploymentsView from '@/components/deployments-view'
import MonitoringView from '@/components/monitoring-view'
import DatasetsView from '@/components/datasets-view'
import CopilotPage from '@/app/copilot/page'
import HowToUseView from '@/components/how-to-use-view'
import { auth, getToken, clearToken } from '@/lib/api'

export default function Home() {
  const router = useRouter()
  const [currentView, setCurrentView] = useState('dashboard')
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    let cancelled = false

    async function verifySession() {
      const token = getToken()

      // No token at all — straight to login, no network call needed.
      if (!token) {
        router.push('/login')
        return
      }

      // A token exists in localStorage, but that only proves a PAST login —
      // it doesn't prove the token is still valid (expired, backend restarted,
      // user deleted, secret rotated, etc.). Verify it against the backend
      // before trusting it.
      try {
        await auth.me()
        if (!cancelled) setIsLoading(false)
      } catch {
        // 401 (or any failure) means the token is stale/invalid.
        // auth.me()'s underlying request() already clears the token and
        // redirects on a 401, but we clear + redirect here too as a
        // belt-and-suspenders fallback for non-401 failures (e.g. network
        // error while the gateway is restarting).
        if (!cancelled) {
          clearToken()
          router.push('/login')
        }
      }
    }

    verifySession()

    return () => {
      cancelled = true
    }
  }, [router])

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  const renderView = () => {
    switch (currentView) {
      case 'datasets':    return <DatasetsView />
      case 'training':    return <TrainingView />
      case 'deployments': return <DeploymentsView />
      case 'monitoring':  return <MonitoringView />
      case 'copilot':     return <CopilotPage />
      case 'how-to-use':  return <HowToUseView onNavigate={setCurrentView} />
      default:            return <Dashboard />
    }
  }

  return (
    <div className="flex h-screen bg-background">
      <Sidebar currentView={currentView} onViewChange={setCurrentView} />
      <main className="flex-1 overflow-auto">{renderView()}</main>
    </div>
  )
}