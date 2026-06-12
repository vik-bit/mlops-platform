'use client'

import { ReactNode } from 'react'
import { TrendingDown, TrendingUp } from 'lucide-react'

interface StatCardProps {
  title: string
  value: string | number
  change: string
  icon: ReactNode
  trend?: 'up' | 'down' | 'stable'
  color?: 'blue' | 'green' | 'cyan' | 'orange' | 'purple'
}

const colorClasses = {
  blue: 'bg-blue-100 text-blue-600',
  green: 'bg-green-100 text-green-600',
  cyan: 'bg-cyan-100 text-cyan-600',
  orange: 'bg-orange-100 text-orange-600',
  purple: 'bg-purple-100 text-purple-600',
}

const StatCard = ({ title, value, change, icon, trend = 'stable', color = 'blue' }: StatCardProps) => {
  return (
    <div className="bg-white border border-border rounded-xl p-6 hover:border-primary/50 transition-all group">
      <div className="flex items-start justify-between mb-4">
        <div className={`p-3 rounded-lg ${colorClasses[color]}`}>
          {icon}
        </div>
        {trend !== 'stable' && (
          <div className={`flex items-center gap-1 text-xs font-semibold ${trend === 'up' ? 'text-green-600' : 'text-red-600'}`}>
            {trend === 'up' ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
            {trend === 'up' ? 'Up' : 'Down'}
          </div>
        )}
      </div>
      <h3 className="text-muted-foreground text-sm font-medium mb-2">{title}</h3>
      <div className="flex items-baseline gap-2 mb-2">
        <p className="text-3xl font-bold text-foreground">{value}</p>
      </div>
      <p className="text-xs text-muted-foreground">{change}</p>
    </div>
  )
}

export default StatCard
