'use client'

import { LayoutDashboard, Database, Brain, Zap, BarChart3, LogOut, Sparkles } from 'lucide-react'
import { useRouter } from 'next/navigation'
import { clearToken } from '@/lib/api'

interface SidebarProps {
  currentView: string
  onViewChange: (view: string) => void
}

export default function Sidebar({ currentView, onViewChange }: SidebarProps) {
  const router = useRouter()

  const menuItems = [
    { id: 'dashboard',   label: 'Dashboard',     icon: LayoutDashboard },
    { id: 'datasets',    label: 'Datasets',       icon: Database },
    { id: 'training',    label: 'Training Jobs',  icon: Brain },
    { id: 'deployments', label: 'Deployments',    icon: Zap },
    { id: 'monitoring',  label: 'Monitoring',     icon: BarChart3 },
    { id: 'copilot',     label: 'AI Copilot',     icon: Sparkles },
  ]

  const handleLogout = () => {
    clearToken()
    router.push('/login')
  }

  return (
    <aside className="w-64 border-r border-border bg-white flex flex-col shadow-sm">
      {/* Header */}
      <div className="p-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-primary flex items-center justify-center">
            <Brain className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-foreground">MLOps</h1>
            <p className="text-xs text-muted-foreground">Platform</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-4 space-y-1">
        {menuItems.map((item) => {
          const Icon = item.icon
          const isActive = currentView === item.id
          return (
            <button
              key={item.id}
              onClick={() => onViewChange(item.id)}
              className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-lg transition-all font-medium text-sm ${
                isActive
                  ? 'bg-primary text-white'
                  : 'text-foreground hover:bg-secondary'
              }`}
            >
              <Icon className="w-5 h-5 flex-shrink-0" />
              <span>{item.label}</span>
            </button>
          )
        })}
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-border">
        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-3 px-4 py-2.5 rounded-lg text-destructive hover:bg-destructive/10 transition-all font-medium text-sm"
        >
          <LogOut className="w-5 h-5 flex-shrink-0" />
          <span>Logout</span>
        </button>
      </div>
    </aside>
  )
}
