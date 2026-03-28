/**
 * DataTable.jsx
 * Color-coded table of ecosystem sensor events with moisture/health indicators.
 */
import { useState } from 'react'
import { ChevronUp, ChevronDown } from 'lucide-react'

function MoistureBar({ value }) {
  const color =
    value < 55 ? 'bg-red-500' : value < 65 ? 'bg-yellow-500' : 'bg-green-500'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-white/5 rounded-full h-1.5 overflow-hidden">
        <div
          className={`moisture-bar ${color}`}
          style={{ width: `${Math.min(value, 100)}%` }}
        />
      </div>
      <span
        className={`text-xs font-mono font-medium w-12 text-right ${
          value < 55 ? 'text-red-400' : value < 65 ? 'text-yellow-400' : 'text-green-400'
        }`}
      >
        {value.toFixed(1)}%
      </span>
    </div>
  )
}

function HealthDot({ value }) {
  const color =
    value < 7 ? 'bg-red-400' : value < 8 ? 'bg-yellow-400' : 'bg-green-400'
  return (
    <div className="flex items-center gap-2">
      <div className={`w-2 h-2 rounded-full ${color}`} />
      <span className="text-xs font-mono">{value.toFixed(1)}</span>
    </div>
  )
}

function ZoneBadge({ zone }) {
  const colorMap = {
    'Zone-A': 'bg-purple-500/20 text-purple-300',
    'Zone-B': 'bg-blue-500/20 text-blue-300',
    'Zone-C': 'bg-cyan-500/20 text-cyan-300',
    'Zone-D': 'bg-orange-500/20 text-orange-300',
  }
  const cls = colorMap[zone] || 'bg-white/10 text-gray-300'
  return <span className={`badge ${cls}`}>{zone}</span>
}

export default function DataTable({ events }) {
  const [sortKey, setSortKey] = useState('timestamp')
  const [sortAsc, setSortAsc] = useState(true)
  const [activeZone, setActiveZone] = useState('All')

  const zones = ['All', ...new Set(events.map((e) => e.sensor_zone)).values()].sort()

  const filtered = activeZone === 'All' ? events : events.filter((e) => e.sensor_zone === activeZone)

  const sorted = [...filtered].sort((a, b) => {
    let av = a[sortKey], bv = b[sortKey]
    if (typeof av === 'string') av = av.toLowerCase(), bv = bv.toLowerCase()
    if (av < bv) return sortAsc ? -1 : 1
    if (av > bv) return sortAsc ? 1 : -1
    return 0
  })

  function toggleSort(key) {
    if (sortKey === key) setSortAsc(!sortAsc)
    else { setSortKey(key); setSortAsc(true) }
  }

  const SortIcon = ({ col }) => {
    if (sortKey !== col) return <ChevronUp className="w-3 h-3 opacity-20" />
    return sortAsc
      ? <ChevronUp className="w-3 h-3 text-green-400" />
      : <ChevronDown className="w-3 h-3 text-green-400" />
  }

  const TH = ({ col, label, className = '' }) => (
    <th
      className={`px-3 py-3 text-left text-xs font-semibold text-gray-400 uppercase tracking-wider cursor-pointer select-none hover:text-gray-200 transition-colors ${className}`}
      onClick={() => toggleSort(col)}
    >
      <span className="flex items-center gap-1">
        {label} <SortIcon col={col} />
      </span>
    </th>
  )

  return (
    <div className="space-y-3">
      {/* Zone filter tabs */}
      <div className="flex gap-2 flex-wrap">
        {zones.map((z) => (
          <button
            key={z}
            onClick={() => setActiveZone(z)}
            className={`px-3 py-1 rounded-full text-xs font-semibold transition-all duration-200 ${
              activeZone === z
                ? 'bg-green-500/30 text-green-300 border border-green-500/40'
                : 'bg-white/5 text-gray-400 border border-white/10 hover:border-white/20'
            }`}
          >
            {z}
          </button>
        ))}
        <span className="ml-auto text-xs text-gray-500 self-center">
          {sorted.length} events
        </span>
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-xl border border-white/8">
        <table className="w-full text-sm">
          <thead className="bg-white/3 border-b border-white/8">
            <tr>
              <TH col="timestamp" label="Time" />
              <TH col="sensor_zone" label="Zone" />
              <TH col="soil_moisture_pct" label="Moisture" className="w-40" />
              <TH col="crop_health_index" label="Health" />
              <TH col="drone_active" label="Drone" />
              <TH col="irrigation_triggered" label="Irrigation" />
              <TH col="temperature_celsius" label="Temp °C" />
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {sorted.map((e, i) => (
              <tr key={i} className="data-row">
                <td className="px-3 py-2.5 font-mono text-xs text-gray-400">
                  {new Date(e.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </td>
                <td className="px-3 py-2.5">
                  <ZoneBadge zone={e.sensor_zone} />
                </td>
                <td className="px-3 py-2.5 min-w-[140px]">
                  <MoistureBar value={e.soil_moisture_pct} />
                </td>
                <td className="px-3 py-2.5">
                  <HealthDot value={e.crop_health_index} />
                </td>
                <td className="px-3 py-2.5">
                  {e.drone_active ? (
                    <span className="badge bg-yellow-500/20 text-yellow-400">✈ Active</span>
                  ) : (
                    <span className="text-xs text-gray-600">—</span>
                  )}
                </td>
                <td className="px-3 py-2.5">
                  {e.irrigation_triggered ? (
                    <span className="badge bg-blue-500/20 text-blue-400">💧 Yes</span>
                  ) : (
                    <span className="text-xs text-gray-600">—</span>
                  )}
                </td>
                <td className="px-3 py-2.5 font-mono text-xs text-gray-400">
                  {e.temperature_celsius.toFixed(1)}°
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
