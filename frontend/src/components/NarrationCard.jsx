/**
 * NarrationCard.jsx
 * Animated card displaying the AI-generated ecosystem narration,
 * anomalies, confidence score, and sentence count metadata.
 */
import { CheckCircle, AlertTriangle, Sparkles, Clock } from 'lucide-react'

function ConfidenceBadge({ confidence }) {
  const pct = Math.round(confidence * 100)
  const color =
    confidence >= 0.8
      ? 'bg-green-500/20 text-green-400 border-green-500/30'
      : confidence >= 0.6
      ? 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30'
      : 'bg-red-500/20 text-red-400 border-red-500/30'

  return (
    <span className={`badge border ${color}`}>
      {pct}% confidence
    </span>
  )
}

export default function NarrationCard({ narration, isMock, elapsed }) {
  if (!narration) return null

  const { narration: text, sentence_count, anomalies_detected, confidence } = narration

  return (
    <div className="narration-reveal space-y-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 text-green-400">
          <Sparkles className="w-5 h-5" />
          <h2 className="text-lg font-semibold">Ecosystem Narration</h2>
        </div>
        <div className="flex items-center gap-2 ml-auto flex-wrap justify-end gap-y-2">
          {isMock && (
            <span className="badge border bg-red-500/20 text-red-400 border-red-500/30">
              ⚠ Mock Mode
            </span>
          )}
          <ConfidenceBadge confidence={confidence} />
          <span className="badge border bg-blue-500/20 text-blue-400 border-blue-500/30">
            {sentence_count} sentence{sentence_count !== 1 ? 's' : ''}
          </span>
          {elapsed && (
            <span className="flex items-center gap-1 badge border bg-white/5 text-gray-400 border-white/10">
              <Clock className="w-3 h-3" />
              {elapsed.toFixed(2)}s
            </span>
          )}
        </div>
      </div>

      {/* Narration text */}
      <div className="glass-card rounded-2xl p-6 relative overflow-hidden">
        {/* Decorative gradient orb */}
        <div
          className="absolute -top-16 -right-16 w-48 h-48 rounded-full opacity-10 blur-3xl pointer-events-none"
          style={{ background: 'radial-gradient(circle, #22c55e, transparent)' }}
        />
        <p className="text-gray-100 text-base leading-8 font-light relative z-10 italic">
          &ldquo;{text}&rdquo;
        </p>
      </div>

      {/* Anomalies */}
      {anomalies_detected && anomalies_detected.length > 0 && (
        <div className="glass-card rounded-2xl p-4">
          <div className="flex items-center gap-2 mb-3 text-yellow-400">
            <AlertTriangle className="w-4 h-4" />
            <span className="text-sm font-semibold">Anomalies Covered in Narration</span>
          </div>
          <ul className="space-y-2">
            {anomalies_detected.map((a, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-gray-300">
                <CheckCircle className="w-4 h-4 text-green-500 mt-0.5 flex-shrink-0" />
                {a}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
