/**
 * App.jsx — Root application component.
 *
 * Flow:
 *  1. User uploads CSV → Web Worker parses off main thread (non-blocking)
 *  2. Parsed events displayed in DataTable
 *  3. "Generate Narration" → POST /api/narrate → NarrationOutput
 *  4. Dashboard shows AnalysisInsights, NarrationCard shows narration
 */
import { useState, useRef, useCallback } from 'react'
import { Upload, Zap, Leaf, Github, FileText } from 'lucide-react'
import Dashboard from './components/Dashboard.jsx'
import DataTable from './components/DataTable.jsx'
import NarrationCard from './components/NarrationCard.jsx'

// ─── Tabs ────────────────────────────────────────────────────────────────────
const TABS = ['Overview', 'Raw Data', 'Narration']

// ─── Loading Skeleton ──────────────────────────────────────────────────────
function Skeleton({ className = '' }) {
  return <div className={`shimmer rounded-lg ${className}`} />
}

function LoadingSkeleton() {
  return (
    <div className="space-y-4 animate-pulse">
      <div className="grid grid-cols-4 gap-3">
        {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-24" />)}
      </div>
      <div className="grid grid-cols-3 gap-3">
        {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-40" />)}
      </div>
    </div>
  )
}

// ─── Upload Zone ──────────────────────────────────────────────────────────
function UploadZone({ onFile, isParsingWorker }) {
  const inputRef = useRef(null)
  const [dragging, setDragging] = useState(false)

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files?.[0]
    if (file) onFile(file)
  }, [onFile])

  return (
    <div
      id="upload-zone"
      className={`drop-zone border-2 border-dashed border-white/15 rounded-2xl p-12 text-center flex flex-col items-center gap-4 ${dragging ? 'drag-over' : ''}`}
      onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      onClick={() => inputRef.current?.click()}
    >
      {isParsingWorker ? (
        <>
          <div className="w-12 h-12 rounded-full border-2 border-green-500/40 border-t-green-400 animate-spin" />
          <div className="text-sm text-gray-400">
            <p className="font-semibold text-gray-300">Parsing CSV in Web Worker…</p>
            <p className="text-xs mt-1 text-gray-600">Off-thread — UI stays responsive</p>
          </div>
        </>
      ) : (
        <>
          <div className="w-16 h-16 rounded-2xl bg-green-500/10 flex items-center justify-center border border-green-500/20">
            <Upload className="w-7 h-7 text-green-400" />
          </div>
          <div>
            <p className="text-gray-300 font-medium">Drop your CSV here or click to browse</p>
            <p className="text-xs text-gray-600 mt-1">
              Required columns: timestamp, sensor_zone, soil_moisture_pct, drone_active,
              crop_health_index, irrigation_triggered, temperature_celsius
            </p>
          </div>
          <span className="badge border bg-white/5 text-gray-500 border-white/10">
            .csv files only
          </span>
        </>
      )}
      <input
        ref={inputRef}
        type="file"
        accept=".csv"
        className="hidden"
        onChange={(e) => { const f = e.target.files?.[0]; if (f) onFile(f) }}
      />
    </div>
  )
}

// ─── Main App ─────────────────────────────────────────────────────────────
export default function App() {
  const [events, setEvents] = useState(null)
  const [fileName, setFileName] = useState('')
  const [workerState, setWorkerState] = useState('idle') // idle | parsing | done | error
  const [workerError, setWorkerError] = useState(null)

  const [apiState, setApiState] = useState('idle') // idle | loading | done | error
  const [narrationData, setNarrationData] = useState(null)
  const [apiError, setApiError] = useState(null)
  const [elapsed, setElapsed] = useState(null)

  const [activeTab, setActiveTab] = useState('Overview')
  const [forceMock, setForceMock] = useState(false)

  // ── Scenario loader (no file upload needed) ──────────────────────────────
  const SCENARIOS = [
    { type: 'normal',   label: '☀️ Normal Day',       color: 'bg-green-500/10 border-green-500/20 text-green-400 hover:bg-green-500/20' },
    { type: 'drought',  label: '🌵 Drought Event',    color: 'bg-yellow-500/10 border-yellow-500/20 text-yellow-400 hover:bg-yellow-500/20' },
    { type: 'crisis',   label: '🚨 Crisis Mode',      color: 'bg-red-500/10 border-red-500/20 text-red-400 hover:bg-red-500/20' },
    { type: 'recovery', label: '💧 Recovery Phase',   color: 'bg-blue-500/10 border-blue-500/20 text-blue-400 hover:bg-blue-500/20' },
  ]

  const loadScenario = useCallback(async (scenarioType) => {
    setFileName(`scenario: ${scenarioType}`)
    setWorkerState('parsing')
    setWorkerError(null)
    setEvents(null)
    setNarrationData(null)
    setApiState('loading')

    const _applyData = (data) => {
      setEvents(data.insights.zone_analyses.map((za, i) => ({
        id: i,
        sensor_zone: za.zone,
        soil_moisture_pct: za.moisture_end_pct,
        drone_active: za.drone_deployments > 0,
        crop_health_index: za.crop_health_mean,
        irrigation_triggered: za.irrigation_events > 0,
        temperature_celsius: za.peak_temperature_celsius,
        timestamp: new Date().toISOString(),
      })))
      setNarrationData(data)
      setWorkerState('done')
      setApiState('done')
      setElapsed(null)
      setActiveTab('Narration')
    }

    try {
      // First try with real Gemini API
      let res = await fetch(`/api/scenario/${scenarioType}`)
      if (res.status === 429 || res.status === 500) {
        // Rate-limited or server error → auto-fallback to mock
        console.warn(`Gemini rate limit hit (${res.status}), retrying with mock mode…`)
        res = await fetch(`/api/scenario/${scenarioType}?force_mock=true`)
      }
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail || `HTTP ${res.status}`)
      }
      const data = await res.json()
      _applyData(data)
    } catch (err) {
      // Network error — try mock as last resort
      try {
        const res = await fetch(`/api/scenario/${scenarioType}?force_mock=true`)
        if (res.ok) {
          const data = await res.json()
          _applyData(data)
          return
        }
      } catch (_) { /* ignore */ }
      setWorkerError(`Cannot reach API: ${err.message}. Make sure the backend is running.`)
      setWorkerState('error')
      setApiState('idle')
    }
  }, [])

  // ── Web Worker CSV parse ─────────────────────────────────────────────────
  const handleFile = useCallback((file) => {
    setFileName(file.name)
    setWorkerState('parsing')
    setWorkerError(null)
    setEvents(null)
    setNarrationData(null)
    setApiState('idle')

    const worker = new Worker(
      new URL('./workers/csvParser.worker.js', import.meta.url),
      { type: 'module' }
    )

    const reader = new FileReader()
    reader.onload = (e) => {
      worker.postMessage({ type: 'PARSE', csvText: e.target.result })
    }
    reader.readAsText(file)

    worker.onmessage = (e) => {
      const { type, events: parsed, message } = e.data
      if (type === 'DONE') {
        setEvents(parsed)
        setWorkerState('done')
        setActiveTab('Overview')
      } else if (type === 'ERROR') {
        setWorkerError(message)
        setWorkerState('error')
      }
      worker.terminate()
    }

    worker.onerror = (err) => {
      setWorkerError(err.message)
      setWorkerState('error')
      worker.terminate()
    }
  }, [])

  // ── API call ─────────────────────────────────────────────────────────────
  const generateNarration = useCallback(async () => {
    if (!events) return
    setApiState('loading')
    setApiError(null)
    setNarrationData(null)

    const start = performance.now()
    const _post = (body) => fetch('/api/narrate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })

    try {
      let res = await _post({ events, source_file: fileName, force_mock: forceMock })

      // Auto-fallback on Gemini rate limit (429) or server error (500)
      if ((res.status === 429 || res.status === 500) && !forceMock) {
        console.warn('Gemini rate limit hit — falling back to mock mode')
        res = await _post({ events, source_file: fileName, force_mock: true })
      }

      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || `HTTP ${res.status}`)
      }
      const data = await res.json()
      setNarrationData(data)
      setApiState('done')
      setElapsed((performance.now() - start) / 1000)
      setActiveTab('Narration')
    } catch (err) {
      setApiError(err.message)
      setApiState('error')
    }
  }, [events, fileName, forceMock])

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-[#030712] text-gray-100">
      {/* Animated background */}
      <div className="fixed inset-0 pointer-events-none">
        <div
          className="absolute top-0 left-1/4 w-96 h-96 rounded-full opacity-5 blur-3xl"
          style={{ background: 'radial-gradient(circle, #22c55e, transparent)' }}
        />
        <div
          className="absolute bottom-0 right-1/4 w-96 h-96 rounded-full opacity-5 blur-3xl"
          style={{ background: 'radial-gradient(circle, #3b82f6, transparent)' }}
        />
      </div>

      {/* Header */}
      <header className="relative border-b border-white/8 bg-black/30 backdrop-blur-xl sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-green-500/20 border border-green-500/30 flex items-center justify-center">
            <Leaf className="w-4 h-4 text-green-400" />
          </div>
          <div>
            <h1 className="text-sm font-bold text-white leading-none">Ecosystem Narrator</h1>
            <p className="text-xs text-gray-500 leading-none mt-0.5">Gemini-Powered Agricultural Analysis</p>
          </div>
          <div className="ml-auto flex items-center gap-3">
            <a
              href="https://github.com"
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-300 transition-colors"
            >
              <Github className="w-4 h-4" />
              <span className="hidden sm:inline">GSoC '26 Entry Task</span>
            </a>
          </div>
        </div>
      </header>

      <main className="relative max-w-7xl mx-auto px-4 sm:px-6 py-8 space-y-8">

        {/* Upload section */}
        {!events && (
          <section>
            <div className="max-w-2xl mx-auto space-y-6">
              <div className="text-center space-y-2">
                <div className="inline-flex items-center gap-2 badge border bg-green-500/10 text-green-400 border-green-500/20 text-xs py-1 px-3 mb-2">
                  <div className="w-1.5 h-1.5 rounded-full bg-green-400 pulse-dot" />
                  Agricultural Ecosystem Monitor
                </div>
                <h2 className="text-3xl font-bold text-white">
                  Upload Sensor Data
                </h2>
                <p className="text-gray-500 text-sm max-w-md mx-auto">
                  Drop a CSV of your sensor grid readings. CSV parsing runs off the main
                  thread via a <strong className="text-gray-400">Web Worker</strong> — the UI
                  stays completely non-blocking.
                </p>
              </div>
              <UploadZone onFile={handleFile} isParsingWorker={workerState === 'parsing'} />
              {workerState === 'error' && (
                <div className="glass-card border border-red-500/30 rounded-xl p-4 text-red-400 text-sm">
                  <strong>Parse error:</strong> {workerError}
                </div>
              )}
              <div className="text-center">
                <p className="text-xs text-gray-600">
                  Or use the sample:{' '}
                  <code className="bg-white/5 px-1.5 py-0.5 rounded text-gray-400">
                    data/agro_ecosystem_sample.csv
                  </code>
                </p>
              </div>

              {/* ── Scenario presets: one-click demo, no file upload needed ── */}
              <div className="border-t border-white/8 pt-5 space-y-3">
                <p className="text-xs text-center text-gray-500 font-medium tracking-wide uppercase">
                  ⚡ Or try a procedural scenario instantly
                </p>
                <div className="grid grid-cols-2 gap-2">
                  {SCENARIOS.map((s) => (
                    <button
                      key={s.type}
                      id={`scenario-${s.type}-btn`}
                      onClick={() => loadScenario(s.type)}
                      disabled={workerState === 'parsing' || apiState === 'loading'}
                      className={`border rounded-xl px-4 py-3 text-sm font-medium transition-all duration-200 disabled:opacity-40 disabled:cursor-not-allowed ${s.color}`}
                    >
                      {s.label}
                    </button>
                  ))}
                </div>
                <p className="text-xs text-center text-gray-700">
                  Physics-consistent procedural data · Gemini API narration
                </p>
              </div>
            </div>
          </section>
        )}

        {/* Dashboard loaded */}
        {events && (
          <>
            {/* File info bar */}
            <div className="flex items-center gap-3 glass-card rounded-xl px-4 py-3 border border-white/8">
              <FileText className="w-4 h-4 text-green-400" />
              <span className="text-sm text-gray-300">{fileName}</span>
              <span className="badge bg-green-500/10 text-green-400 border border-green-500/20">
                {events.length} events
              </span>
              <button
                onClick={() => { setEvents(null); setNarrationData(null); setWorkerState('idle'); setApiState('idle') }}
                className="ml-auto text-xs text-gray-600 hover:text-gray-400 transition-colors"
              >
                ✕ Clear
              </button>
            </div>

            {/* Generate button */}
            <div className="flex flex-wrap items-center gap-3">
              <button
                id="generate-narration-btn"
                onClick={generateNarration}
                disabled={apiState === 'loading'}
                className="flex items-center gap-2 px-6 py-3 bg-green-500 hover:bg-green-400 disabled:opacity-50 disabled:cursor-not-allowed text-black font-semibold rounded-xl transition-all duration-200 hover:shadow-lg hover:shadow-green-500/25 active:scale-95"
              >
                {apiState === 'loading' ? (
                  <>
                    <div className="w-4 h-4 border-2 border-black/30 border-t-black rounded-full animate-spin" />
                    Generating narration…
                  </>
                ) : (
                  <>
                    <Zap className="w-4 h-4" />
                    Generate Narration
                  </>
                )}
              </button>

              <label className="flex items-center gap-2 text-xs text-gray-500 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={forceMock}
                  onChange={(e) => setForceMock(e.target.checked)}
                  className="rounded"
                />
                Force mock mode
              </label>

              {apiState === 'error' && (
                <span className="text-sm text-red-400">
                  Error: {apiError}
                </span>
              )}
            </div>

            {/* Tab bar */}
            <div className="flex gap-1 border-b border-white/8">
              {TABS.map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`px-4 py-2.5 text-sm font-medium transition-all duration-200 border-b-2 -mb-px ${
                    activeTab === tab
                      ? 'border-green-400 text-green-400'
                      : 'border-transparent text-gray-500 hover:text-gray-300'
                  }`}
                >
                  {tab}
                </button>
              ))}
            </div>

            {/* Tab content */}
            <div className="min-h-[400px]">
              {activeTab === 'Overview' && (
                apiState === 'loading' ? (
                  <LoadingSkeleton />
                ) : narrationData ? (
                  <Dashboard insights={narrationData.insights} />
                ) : (
                  <div className="text-center py-20 text-gray-600 text-sm">
                    Click <strong className="text-gray-400">Generate Narration</strong> to run the analysis pipeline.
                  </div>
                )
              )}

              {activeTab === 'Raw Data' && (
                <DataTable events={events} />
              )}

              {activeTab === 'Narration' && (
                apiState === 'loading' ? (
                  <div className="space-y-4">
                    <Skeleton className="h-8 w-48" />
                    <Skeleton className="h-32" />
                    <Skeleton className="h-24" />
                  </div>
                ) : narrationData ? (
                  <NarrationCard
                    narration={narrationData.narration}
                    isMock={narrationData.mock_mode}
                    elapsed={elapsed}
                  />
                ) : (
                  <div className="text-center py-20 text-gray-600 text-sm">
                    Narration will appear here after generation.
                  </div>
                )
              )}
            </div>
          </>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-white/5 mt-16 py-6 text-center text-xs text-gray-700">
        GSoC '26 Entry Task — Gemini-Powered Ecosystem Narration ·{' '}
        <span className="text-gray-600">CatRobot Organization</span>
      </footer>
    </div>
  )
}
