'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Sidebar from '@/components/sidebar'
import Dashboard from '@/components/dashboard'
import TrainingView from '@/components/training-view'
import DeploymentsView from '@/components/deployments-view'
import MonitoringView from '@/components/monitoring-view'
import DatasetsView from '@/components/datasets-view'
import { getToken } from '@/lib/api'

export default function Home() {
  const router = useRouter()
  const [currentView, setCurrentView] = useState('dashboard')
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    if (!getToken()) {
      router.push('/login')
      return
    }
    setIsLoading(false)
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
