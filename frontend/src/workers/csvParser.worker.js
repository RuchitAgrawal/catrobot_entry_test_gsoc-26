/**
 * csvParser.worker.js
 *
 * Web Worker: parses and validates the CSV off the main thread so the UI
 * stays responsive while processing large files.
 *
 * Message protocol:
 *   IN  { type: 'PARSE', csvText: string }
 *   OUT { type: 'DONE',  events: EcosystemEvent[] }
 *       { type: 'ERROR', message: string }
 */
import Papa from 'papaparse'

const REQUIRED_COLUMNS = [
  'timestamp',
  'sensor_zone',
  'soil_moisture_pct',
  'drone_active',
  'crop_health_index',
  'irrigation_triggered',
  'temperature_celsius',
]

self.onmessage = (e) => {
  const { type, csvText } = e.data

  if (type !== 'PARSE') return

  try {
    const result = Papa.parse(csvText.trim(), {
      header: true,
      skipEmptyLines: true,
      dynamicTyping: false, // we do explicit typing below for safety
    })

    if (result.errors.length > 0) {
      const critical = result.errors.filter((err) => err.type === 'Delimiter' || err.type === 'Quotes')
      if (critical.length > 0) {
        throw new Error(`CSV parse error: ${critical[0].message}`)
      }
    }

    // Validate required columns
    const cols = result.meta.fields || []
    const missing = REQUIRED_COLUMNS.filter((c) => !cols.includes(c))
    if (missing.length > 0) {
      throw new Error(`Missing required columns: ${missing.join(', ')}`)
    }

    // Type-cast and sanitize each row → EcosystemEvent-compatible object
    const events = result.data
      .map((row, idx) => {
        const moisture = parseFloat(row.soil_moisture_pct)
        const health = parseFloat(row.crop_health_index)
        const temp = parseFloat(row.temperature_celsius)
        const rainfall = parseFloat(row.rainfall_mm ?? '0')

        if (isNaN(moisture) || moisture < 0 || moisture > 100) {
          throw new Error(`Row ${idx + 2}: soil_moisture_pct="${row.soil_moisture_pct}" is invalid`)
        }
        if (isNaN(health) || health < 0 || health > 10) {
          throw new Error(`Row ${idx + 2}: crop_health_index="${row.crop_health_index}" is invalid`)
        }

        return {
          timestamp: row.timestamp,
          sensor_zone: row.sensor_zone.trim(),
          soil_moisture_pct: moisture,
          drone_active: row.drone_active.trim().toLowerCase() === 'true',
          crop_health_index: health,
          irrigation_triggered: row.irrigation_triggered.trim().toLowerCase() === 'true',
          temperature_celsius: isNaN(temp) ? 25.0 : temp,
          rainfall_mm: isNaN(rainfall) ? 0.0 : rainfall,
        }
      })

    // Derive zones for a quick summary before sending
    const zones = [...new Set(events.map((e) => e.sensor_zone))].sort()

    self.postMessage({ type: 'DONE', events, zones, rowCount: events.length })
  } catch (err) {
    self.postMessage({ type: 'ERROR', message: err.message })
  }
}
