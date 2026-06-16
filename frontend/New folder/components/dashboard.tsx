
'use client'

import { CheckCircle, Brain, Zap, Database, Package } from 'lucide-react'
import StatCard from '@/components/stat-card'
import { useDashboard } from '@/lib/hooks'

const Dashboard = () => {
  const { jobs, deployments, loading, stats } = useDashboard()

  const avgAccuracyDisplay = stats.avgAccuracy != null
    ? `${Math.round(stats.avgAccuracy * 100)}%`
    : '—'

  return (
    <div className="flex-1 overflow-auto bg-white">
      {/* Header */}
      <div className="border-b border-border bg-white sticky top-0 z-10">
        <div className="px-8 py-6">
          <h1 className="text-3xl font-bold text-foreground">Dashboard</h1>
          <p className="text-muted-foreground mt-1">Your ML pipeline at a glance</p>
        </div>
      </div>

      <div className="p-8">
        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <StatCard
            title="Training Jobs"
            value={loading ? '…' : stats.totalJobs}
            change={`${stats.runningJobs} running`}
            icon={<Brain className="w-6 h-6" />}
            trend="up"
            color="blue"
          />
          <StatCard
            title="Completed"
            value={loading ? '…' : stats.completedJobs}
            change={stats.avgAccuracy != null ? `${Math.round(stats.avgAccuracy * 100)}% avg accuracy` : 'No accuracy data'}
            icon={<CheckCircle className="w-6 h-6" />}
            trend="up"
            color="green"
          />
          <StatCard
            title="Active Deployments"
            value={loading ? '…' : stats.activeDeployments}
            change={stats.activeDeployments > 0 ? 'Serving predictions' : 'None deployed'}
            icon={<Zap className="w-6 h-6" />}
            trend="stable"
            color="cyan"
          />
          <StatCard
            title="Avg Accuracy"
            value={loading ? '…' : avgAccuracyDisplay}
            change="Across completed jobs"
            icon={<Package className="w-6 h-6" />}
            trend="up"
            color="orange"
          />
        </div>

        {/* Recent Activity */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Recent Training Jobs */}
          <div className="bg-white border border-border rounded-xl p-6">
            <h2 className="text-lg font-semibold text-foreground mb-6">Recent Training Jobs</h2>
            {loading ? (
              <div className="space-y-3">
                {[1,2,3].map(i => <div key={i} className="h-14 bg-secondary rounded-lg animate-pulse" />)}
              </div>
            ) : jobs.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-8">No training jobs yet</p>
            ) : (
              <div className="space-y-3">
                {jobs.slice(0, 5).map((job) => (
                  <div key={job.id} className="flex items-center justify-between p-3 bg-secondary rounded-lg hover:bg-secondary/80 transition">
                    <div className="flex items-center gap-3">
                      <div className={`w-2 h-2 rounded-full flex-shrink-0 ${
                        job.status === 'running'   ? 'bg-amber-500 animate-pulse' :
                        job.status === 'completed' ? 'bg-green-500' :
                        job.status === 'failed'    ? 'bg-red-500' : 'bg-blue-500'
                      }`} />
                      <div>
                        <p className="font-medium text-foreground text-sm">
                          {job.model_type} · Dataset #{job.dataset_id}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {new Date(job.created_at).toLocaleDateString()}
                        </p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="text-sm font-medium text-foreground capitalize">{job.status}</p>
                      {job.accuracy != null && (
                        <p className="text-xs text-blue-500">
                          {(parseFloat(job.accuracy) * 100).toFixed(1)}% acc
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Active Deployments */}
          <div className="bg-white border border-border rounded-xl p-6">
            <h2 className="text-lg font-semibold text-foreground mb-6">Active Deployments</h2>
            {loading ? (
              <div className="space-y-3">
                {[1,2,3].map(i => <div key={i} className="h-14 bg-secondary rounded-lg animate-pulse" />)}
              </div>
            ) : deployments.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-8">No deployments yet</p>
            ) : (
              <div className="space-y-3">
                {deployments.slice(0, 5).map((dep) => (
                  <div key={dep.id} className="flex items-center justify-between p-3 bg-secondary rounded-lg hover:bg-secondary/80 transition">
                    <div className="flex items-center gap-3">
                      <CheckCircle className={`w-4 h-4 flex-shrink-0 ${dep.status === 'active' ? 'text-green-500' : 'text-muted-foreground'}`} />
                      <div>
                        <p className="font-medium text-foreground text-sm">Model #{dep.model_id}</p>
                        <p className="text-xs text-muted-foreground font-mono truncate max-w-[180px]">{dep.endpoint}</p>
                      </div>
                    </div>
                    <span className={`text-xs font-semibold px-2 py-1 rounded-full ${
                      dep.status === 'active' ? 'text-green-600 bg-green-100' : 'text-gray-400 bg-gray-100'
                    }`}>
                      {dep.status}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default Dashboard
