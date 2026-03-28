/**
 * Dashboard.jsx
 * Main dashboard component: shows zone stats panels derived from AnalysisInsights.
 */
import { TrendingDown, TrendingUp, Minus, Cpu, Droplets, Leaf } from 'lucide-react'

function StatCard({ title, value, sub, icon: Icon, color = 'green', trend }) {
  const colorMap = {
    green: 'text-green-400 bg-green-500/10 border-green-500/20',
    yellow: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/20',
    red: 'text-red-400 bg-red-500/10 border-red-500/20',
    blue: 'text-blue-400 bg-blue-500/10 border-blue-500/20',
  }
  return (
    <div className={`glass-card rounded-xl p-4 border ${colorMap[color]}`}>
      <div className="flex items-start justify-between mb-3">
        <Icon className={`w-5 h-5 ${colorMap[color].split(' ')[0]}`} />
        {trend === 'down' && <TrendingDown className="w-4 h-4 text-red-400" />}
        {trend === 'up' && <TrendingUp className="w-4 h-4 text-green-400" />}
        {trend === 'stable' && <Minus className="w-4 h-4 text-gray-500" />}
      </div>
      <div className={`text-2xl font-bold font-mono ${colorMap[color].split(' ')[0]}`}>{value}</div>
      <div className="text-xs font-semibold text-gray-400 mt-1">{title}</div>
      {sub && <div className="text-xs text-gray-600 mt-0.5">{sub}</div>}
    </div>
  )
}

function ZonePanel({ za }) {
  const isCritical = za.min_moisture_pct < 55
  const borderColor = isCritical
    ? 'border-red-500/30'
    : za.min_moisture_pct < 65
    ? 'border-yellow-500/30'
    : 'border-green-500/30'

  const TrendIcon =
    za.moisture_delta_pct < -5
      ? TrendingDown
      : za.moisture_delta_pct > 2
      ? TrendingUp
      : Minus

  const trendColor =
    za.moisture_delta_pct < -5
      ? 'text-red-400'
      : za.moisture_delta_pct > 2
      ? 'text-green-400'
      : 'text-gray-500'

  return (
    <div className={`glass-card rounded-xl p-4 border ${borderColor} space-y-3`}>
      <div className="flex items-center justify-between">
        <span className="font-semibold text-sm">{za.zone}</span>
        {isCritical && (
          <span className="badge bg-red-500/20 text-red-400 border border-red-500/30">
            ⚠ Critical
          </span>
        )}
      </div>

      {/* Moisture bar */}
      <div>
        <div className="flex justify-between text-xs text-gray-500 mb-1">
          <span>Moisture</span>
          <span className="flex items-center gap-1">
            <TrendIcon className={`w-3 h-3 ${trendColor}`} />
            <span className={trendColor}>{za.moisture_delta_pct > 0 ? '+' : ''}{za.moisture_delta_pct.toFixed(1)}%</span>
          </span>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex-1 bg-white/5 rounded-full h-2 overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-1000 ${
                za.moisture_end_pct < 55
                  ? 'bg-gradient-to-r from-red-600 to-red-400'
                  : za.moisture_end_pct < 65
                  ? 'bg-gradient-to-r from-yellow-600 to-yellow-400'
                  : 'bg-gradient-to-r from-green-600 to-green-400'
              }`}
              style={{ width: `${za.moisture_end_pct}%` }}
            />
          </div>
          <span className="text-xs font-mono text-gray-400 w-10 text-right">
            {za.moisture_end_pct.toFixed(1)}%
          </span>
        </div>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-3 gap-2 text-xs">
        <div className="text-center">
          <div className="text-gray-500 mb-0.5">Health</div>
          <div className={`font-mono font-semibold ${za.crop_health_mean < 7 ? 'text-red-400' : za.crop_health_mean < 8 ? 'text-yellow-400' : 'text-green-400'}`}>
            {za.crop_health_mean.toFixed(1)}
          </div>
        </div>
        <div className="text-center">
          <div className="text-gray-500 mb-0.5">Drones</div>
          <div className={`font-mono font-semibold ${za.drone_deployments > 0 ? 'text-yellow-400' : 'text-gray-500'}`}>
            {za.drone_deployments}
          </div>
        </div>
        <div className="text-center">
          <div className="text-gray-500 mb-0.5">Irrigation</div>
          <div className={`font-mono font-semibold ${za.irrigation_events > 0 ? 'text-blue-400' : 'text-gray-500'}`}>
            {za.irrigation_events}
          </div>
        </div>
      </div>

      {/* Anomaly flags */}
      {za.anomaly_flags && za.anomaly_flags.length > 0 && (
        <div className="border-t border-white/5 pt-2 space-y-1">
          {za.anomaly_flags.slice(0, 2).map((flag, i) => (
            <div key={i} className="text-xs text-red-400/80 flex items-start gap-1">
              <span className="mt-0.5 flex-shrink-0">•</span>
              <span>{flag}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default function Dashboard({ insights }) {
  if (!insights) return null

  const { zone_analyses, total_drone_deployments, total_irrigation_events,
          overall_moisture_trend, analysis_window_hours, global_anomalies } = insights

  const trendColor =
    overall_moisture_trend === 'declining'
      ? 'red'
      : overall_moisture_trend === 'recovering'
      ? 'green'
      : 'yellow'

  return (
    <div className="space-y-6">
      {/* Global stats */}
      <div>
        <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">
          Global Statistics — {analysis_window_hours.toFixed(1)}h Window
        </h2>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <StatCard
            title="Moisture Trend"
            value={overall_moisture_trend.charAt(0).toUpperCase() + overall_moisture_trend.slice(1)}
            icon={TrendingDown}
            color={trendColor}
            trend={overall_moisture_trend === 'declining' ? 'down' : overall_moisture_trend === 'recovering' ? 'up' : 'stable'}
          />
          <StatCard
            title="Drone Deployments"
            value={total_drone_deployments}
            sub="across all zones"
            icon={Cpu}
            color={total_drone_deployments > 5 ? 'yellow' : 'blue'}
          />
          <StatCard
            title="Irrigation Events"
            value={total_irrigation_events}
            sub="automated triggers"
            icon={Droplets}
            color={total_irrigation_events > 0 ? 'blue' : 'green'}
          />
          <StatCard
            title="Zones Monitored"
            value={zone_analyses.length}
            sub={`${insights.critical_zones?.length || 0} critical`}
            icon={Leaf}
            color={insights.critical_zones?.length > 0 ? 'red' : 'green'}
          />
        </div>
      </div>

      {/* Zone panels */}
      <div>
        <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">
          Per-Zone Analysis
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {zone_analyses.map((za) => (
            <ZonePanel key={za.zone} za={za} />
          ))}
        </div>
      </div>

      {/* Global anomalies */}
      {global_anomalies && global_anomalies.length > 0 && (
        <div className="glass-card rounded-xl p-4 border border-red-500/20">
          <h3 className="text-sm font-semibold text-red-400 mb-3">⚠ Global Anomalies Detected</h3>
          <ul className="space-y-2">
            {global_anomalies.map((a, i) => (
              <li key={i} className="text-sm text-gray-300 flex items-start gap-2">
                <span className="text-red-400 mt-0.5">→</span>
                {a}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
