"""
report_generator.py — Self-Contained HTML Report with Embedded SVG Charts.

Generates a standalone .html file (open in any browser, no server needed):
  - Soil moisture trend line chart (SVG, no external libraries)
  - Drone & irrigation activity bar chart (SVG)
  - AI narration card with severity badge
  - Per-zone statistical breakdown table
  - Global anomaly list

Architectural note: HTML is built via string concatenation, NOT f-string
templates, to avoid nested quote/backslash complexity inside HTML attributes.
"""

from __future__ import annotations

import html as _html_mod
from datetime import datetime
from pathlib import Path

from .models import AnalysisInsights, NarrationOutput

# ─────────────────────────────────────────────────────────────────────────────
#  Color palette
# ─────────────────────────────────────────────────────────────────────────────

ZONE_COLORS = {
    "Zone-A": "#a78bfa",
    "Zone-B": "#38bdf8",
    "Zone-C": "#34d399",
    "Zone-D": "#fb923c",
    "Zone-E": "#f472b6",
}

SEVERITY_CFG = {
    "routine":   {"bg": "#052e16", "border": "#166534", "text": "#4ade80",  "label": "Routine Monitoring"},
    "advisory":  {"bg": "#422006", "border": "#92400e", "text": "#fbbf24",  "label": "Field Advisory"},
    "emergency": {"bg": "#450a0a", "border": "#991b1b", "text": "#f87171",  "label": "Emergency Report"},
}


# ─────────────────────────────────────────────────────────────────────────────
#  SVG: moisture trend line chart
# ─────────────────────────────────────────────────────────────────────────────

def _moisture_svg(insights: AnalysisInsights) -> str:
    W, H = 680, 260
    PL, PR, PT, PB = 55, 60, 20, 45
    pw = W - PL - PR
    ph = H - PT - PB

    def xp(i: int, n: int) -> float:
        return PL + (i / max(n - 1, 1)) * pw

    def yp(v: float) -> float:
        return PT + ph - (min(max(v, 0), 100) / 100.0) * ph

    parts = ['<svg viewBox="0 0 680 260" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:680px">']
    parts.append('<defs><style>.al{font:11px Inter,sans-serif;fill:#6b7280}.zl{font:11px Inter,sans-serif;font-weight:600}</style></defs>')

    # Grid lines
    grid = [
        (20, "#1f2937", "", ""),
        (40, "#1f2937", "", ""),
        (55, "#ef4444", "4,3", "#ef4444"),
        (65, "#f59e0b", "4,3", ""),
        (80, "#1f2937", "", ""),
        (100, "#1f2937", "", ""),
    ]
    for pct, color, dash, lcolor in grid:
        y = yp(pct)
        sa = f' stroke-dasharray="{dash}"' if dash else ""
        parts.append(f'<line x1="{PL}" y1="{y:.1f}" x2="{W-PR}" y2="{y:.1f}" stroke="{color}" stroke-width="1"{sa} opacity="0.6"/>')
        fc = lcolor if lcolor else "#6b7280"
        if pct in (20, 40, 65, 80, 100):
            parts.append(f'<text x="{PL-5}" y="{y+4:.1f}" text-anchor="end" class="al" fill="{fc}">{pct}%</text>')
        elif pct == 55:
            parts.append(f'<text x="{PL-5}" y="{y+4:.1f}" text-anchor="end" class="al" fill="#ef4444">55%</text>')

    # Zone lines
    for za in insights.zone_analyses:
        color = ZONE_COLORS.get(za.zone, "#94a3b8")
        n = 10
        ms = _approx_series(za.moisture_start_pct, za.moisture_end_pct, za.min_moisture_pct, za.irrigation_events, n)
        pts = " ".join(f"{xp(i,n):.1f},{yp(m):.1f}" for i, m in enumerate(ms))
        parts.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>')
        lx = xp(n - 1, n) + 5
        ly = yp(ms[-1]) + 4
        parts.append(f'<text x="{lx:.1f}" y="{ly:.1f}" fill="{color}" class="zl">{_html_mod.escape(za.zone)}</text>')

    # X-axis time labels
    for i in range(6):
        idx = int(i * 9 / 5)
        x = xp(idx, 10)
        hour = 6 + idx * 0.5
        h, m = int(hour), ("30" if hour % 1 else "00")
        parts.append(f'<text x="{x:.1f}" y="{H-8}" text-anchor="middle" class="al">{h:02d}:{m}</text>')

    # Axes
    parts.append(f'<line x1="{PL}" y1="{PT}" x2="{PL}" y2="{H-PB}" stroke="#374151" stroke-width="1"/>')
    parts.append(f'<line x1="{PL}" y1="{H-PB}" x2="{W-PR}" y2="{H-PB}" stroke="#374151" stroke-width="1"/>')
    parts.append('</svg>')
    return "".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
#  SVG: drone & irrigation bar chart
# ─────────────────────────────────────────────────────────────────────────────

def _drone_svg(insights: AnalysisInsights) -> str:
    zones = insights.zone_analyses
    W, H = 440, 160
    PL, PR, PT, PB = 50, 20, 15, 40
    pw = W - PL - PR
    ph = H - PT - PB
    n = len(zones)
    mx = max(max((z.drone_deployments for z in zones), default=0),
             max((z.irrigation_events for z in zones), default=0), 1)

    parts = ['<svg viewBox="0 0 440 160" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:440px">']
    parts.append('<defs><style>.al{font:11px Inter,sans-serif;fill:#6b7280}.bv{font:10px Inter,sans-serif;fill:#9ca3af}</style></defs>')

    bw = (pw / n) * 0.28

    for tick in range(0, mx + 2, max(1, (mx + 1) // 4)):
        y = PT + ph - (tick / (mx + 1)) * ph
        parts.append(f'<line x1="{PL}" y1="{y:.1f}" x2="{W-PR}" y2="{y:.1f}" stroke="#1f2937" stroke-width="1"/>')
        parts.append(f'<text x="{PL-5}" y="{y+4:.1f}" text-anchor="end" class="al">{tick}</text>')

    for i, za in enumerate(zones):
        color = ZONE_COLORS.get(za.zone, "#94a3b8")
        gx = PL + i * (pw / n) + (pw / n) * 0.1

        # drone bar
        dh = (za.drone_deployments / (mx + 1)) * ph
        dy = PT + ph - dh
        parts.append(f'<rect x="{gx:.1f}" y="{dy:.1f}" width="{bw:.1f}" height="{dh:.1f}" fill="{color}" rx="3" opacity="0.85"/>')
        parts.append(f'<text x="{gx+bw/2:.1f}" y="{dy-4:.1f}" text-anchor="middle" class="bv">{za.drone_deployments}</text>')

        # irrigation bar
        ih = (za.irrigation_events / (mx + 1)) * ph
        iy = PT + ph - ih
        ix = gx + bw + 4
        parts.append(f'<rect x="{ix:.1f}" y="{iy:.1f}" width="{bw:.1f}" height="{ih:.1f}" fill="#38bdf8" rx="3" opacity="0.5"/>')
        parts.append(f'<text x="{ix+bw/2:.1f}" y="{iy-4:.1f}" text-anchor="middle" class="bv">{za.irrigation_events}</text>')

        lx = gx + bw
        parts.append(f'<text x="{lx:.1f}" y="{H-8}" text-anchor="middle" class="al" fill="{color}">{_html_mod.escape(za.zone)}</text>')

    # Axes + legend
    parts.append(f'<line x1="{PL}" y1="{PT}" x2="{PL}" y2="{H-PB}" stroke="#374151" stroke-width="1"/>')
    parts.append(f'<line x1="{PL}" y1="{H-PB}" x2="{W-PR}" y2="{H-PB}" stroke="#374151" stroke-width="1"/>')
    parts.append(f'<rect x="{W-140}" y="10" width="12" height="12" fill="#a78bfa" rx="2" opacity="0.85"/>')
    parts.append(f'<text x="{W-124}" y="21" class="al">Drone events</text>')
    parts.append(f'<rect x="{W-140}" y="28" width="12" height="12" fill="#38bdf8" rx="2" opacity="0.5"/>')
    parts.append(f'<text x="{W-124}" y="39" class="al">Irrigation events</text>')
    parts.append('</svg>')
    return "".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _approx_series(start: float, end: float, mn: float, irrig: int, n: int) -> list[float]:
    result = []
    for i in range(n):
        t = i / max(n - 1, 1)
        val = start + (end - start) * t
        if irrig > 0 and t > 0.65:
            val = min(val + irrig * 1.5 * (t - 0.65), 100.0)
        if round(t * (n - 1)) == n // 2:
            val = min(val, mn + 1.5)
        result.append(round(max(val, 0.0), 1))
    return result


def _e(s: str) -> str:
    """HTML-escape a string."""
    return _html_mod.escape(str(s))


# ─────────────────────────────────────────────────────────────────────────────
#  HTML assembler
# ─────────────────────────────────────────────────────────────────────────────

def generate_html_report(
    output: NarrationOutput,
    insights: AnalysisInsights,
    is_mock: bool = False,
    source_file: str = "",
) -> str:
    sev = getattr(insights, "tone_register", "routine")
    cfg = SEVERITY_CFG.get(sev, SEVERITY_CFG["routine"])
    sev_score = getattr(insights, "severity_score", 0.0)
    conf_pct = round(output.confidence * 100)
    conf_color = "#4ade80" if output.confidence >= 0.8 else "#fbbf24" if output.confidence >= 0.6 else "#f87171"
    generated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    crit_color = "#ef4444" if insights.critical_zones else "#4ade80"

    moisture_svg = _moisture_svg(insights)
    drone_svg = _drone_svg(insights)

    p: list[str] = []

    # ── document head ─────────────────────────────────────────────────────────
    p.append("<!DOCTYPE html>\n<html lang='en'>\n<head>")
    p.append("<meta charset='UTF-8'/>")
    p.append("<meta name='viewport' content='width=device-width,initial-scale=1'/>")
    p.append("<title>Ecosystem Report — " + _e(generated_at) + "</title>")
    p.append("<meta name='description' content='Gemini-powered agricultural ecosystem narration report'/>")
    p.append("""<link rel='preconnect' href='https://fonts.googleapis.com'>
<link href='https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap' rel='stylesheet'>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{background:#030712;color:#f1f5f9;font-family:'Inter',system-ui,sans-serif;line-height:1.6;min-height:100vh}
h1{font-size:1.6rem;font-weight:700}
h2{font-size:1rem;font-weight:600;color:#94a3b8;text-transform:uppercase;letter-spacing:.06em;margin-bottom:12px}
.wrap{max-width:960px;margin:0 auto;padding:32px 20px}
header{border-bottom:1px solid #1f2937;padding-bottom:20px;margin-bottom:32px;display:flex;align-items:center;gap:16px}
.logo{width:44px;height:44px;border-radius:12px;background:#052e16;border:1px solid #166534;display:flex;align-items:center;justify-content:center;font-size:22px;flex-shrink:0}
.card{background:linear-gradient(145deg,rgba(255,255,255,.04),rgba(255,255,255,.01));border:1px solid rgba(255,255,255,.08);border-radius:16px;padding:24px;margin-bottom:24px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-bottom:24px}
.stat{background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);border-radius:12px;padding:16px}
.sv{font-size:1.6rem;font-weight:700;font-family:'JetBrains Mono',monospace}
.sl{font-size:.7rem;color:#6b7280;text-transform:uppercase;letter-spacing:.05em;margin-top:4px}
.narr{font-size:1.05rem;line-height:1.85;font-style:italic;color:#e2e8f0;border-left:3px solid #4ade80;padding-left:18px}
table{width:100%;border-collapse:collapse;font-size:13px}
th{background:rgba(255,255,255,.04);color:#6b7280;font-weight:600;text-transform:uppercase;font-size:.7rem;letter-spacing:.05em;padding:10px 12px;border-bottom:1px solid rgba(255,255,255,.08);text-align:left}
td{padding:10px 12px;border-bottom:1px solid rgba(255,255,255,.05);font-family:'JetBrains Mono',monospace;font-size:12px}
tr:last-child td{border-bottom:none}
tr:hover td{background:rgba(255,255,255,.02)}
.badge{display:inline-flex;align-items:center;gap:4px;padding:3px 10px;border-radius:99px;font-size:.7rem;font-weight:600;letter-spacing:.04em;text-transform:uppercase}
.two-col{display:grid;grid-template-columns:1fr 1fr;gap:24px;align-items:start}
footer{border-top:1px solid #1f2937;padding-top:20px;margin-top:40px;font-size:12px;color:#4b5563;text-align:center}
</style>""")
    p.append("</head>\n<body>\n<div class='wrap'>")

    # ── header ────────────────────────────────────────────────────────────────
    badge_style = (
        "background:" + cfg["bg"] + ";border:1px solid " + cfg["border"] +
        ";color:" + cfg["text"]
    )
    p.append("<header>")
    p.append("<div class='logo'>🌾</div>")
    p.append("<div><h1>Ecosystem Narrator Report</h1>")
    p.append("<div style='color:#6b7280;font-size:13px;margin-top:2px'>Generated " +
             _e(generated_at) + " · " + _e(source_file or "unknown source") + "</div></div>")
    p.append("<div style='margin-left:auto'>")
    p.append("<span class='badge' style='" + badge_style + "'>" + _e(cfg["label"]) + "</span>")
    p.append("</div></header>")

    # ── mock banner ───────────────────────────────────────────────────────────
    if is_mock:
        p.append(
            "<div style='background:#450a0a;border:1px solid #991b1b;border-radius:8px;"
            "padding:10px 16px;color:#f87171;font-size:13px;margin-bottom:16px'>"
            "<strong>MOCK MODE:</strong> Set GEMINI_API_KEY for live narration.</div>"
        )

    # ── stat grid ─────────────────────────────────────────────────────────────
    p.append("<div class='grid'>")
    stats = [
        (insights.overall_moisture_trend.title(), cfg["text"], "Moisture Trend"),
        (str(insights.total_drone_deployments), "#fbbf24", "Drone Deployments"),
        (str(insights.total_irrigation_events), "#38bdf8", "Irrigation Events"),
        (str(len(insights.critical_zones or [])), crit_color, "Critical Zones"),
        (str(conf_pct) + "%", conf_color, "AI Confidence"),
        (str(round(sev_score * 100)) + "%", "#a78bfa", "Severity Score"),
    ]
    for val, color, label in stats:
        p.append("<div class='stat'>")
        p.append("<div class='sv' style='color:" + color + "'>" + _e(val) + "</div>")
        p.append("<div class='sl'>" + _e(label) + "</div>")
        p.append("</div>")
    p.append("</div>")

    # ── narration card ────────────────────────────────────────────────────────
    p.append("<div class='card'>")
    p.append("<h2>AI Narration <span style='font-size:.75rem;color:#6b7280;text-transform:none;letter-spacing:0'>(" +
             str(output.sentence_count) + " sentences · " + str(conf_pct) + "% confidence)</span></h2>")
    p.append('<p class="narr">"' + _e(output.narration) + '"</p>')
    if output.anomalies_detected:
        p.append("<ul style='margin-top:16px;padding-left:0;list-style:none'>")
        for a in output.anomalies_detected:
            p.append("<li style='margin:4px 0;color:#fca5a5'>⚠ " + _e(a) + "</li>")
        p.append("</ul>")
    p.append("</div>")

    # ── moisture chart ────────────────────────────────────────────────────────
    p.append("<div class='card'>")
    p.append("<h2>Soil Moisture Trend by Zone</h2>")
    p.append("<div style='overflow-x:auto'>" + moisture_svg + "</div>")
    p.append("<div style='display:flex;gap:16px;margin-top:12px;flex-wrap:wrap'>")
    for za in insights.zone_analyses:
        zc = ZONE_COLORS.get(za.zone, "#94a3b8")
        p.append(
            "<span style='display:flex;align-items:center;gap:6px;font-size:12px'>"
            "<span style='width:16px;height:3px;background:" + zc + ";border-radius:2px;display:inline-block'></span>"
            + _e(za.zone) + "</span>"
        )
    p.append(
        "<span style='display:flex;align-items:center;gap:6px;font-size:12px;color:#ef4444'>"
        "<span style='width:16px;height:1px;background:#ef4444;border-bottom:1px dashed #ef4444;display:inline-block'></span>"
        "55% critical</span>"
    )
    p.append(
        "<span style='display:flex;align-items:center;gap:6px;font-size:12px;color:#f59e0b'>"
        "<span style='width:16px;height:1px;background:#f59e0b;border-bottom:1px dashed #f59e0b;display:inline-block'></span>"
        "65% warning</span>"
    )
    p.append("</div></div>")

    # ── zone stats table ──────────────────────────────────────────────────────
    p.append("<div class='card'>")
    p.append("<h2>Per-Zone Statistical Summary (" + str(round(insights.analysis_window_hours, 1)) + "h window)</h2>")
    p.append("<div style='overflow-x:auto'><table>")
    p.append("<thead><tr><th>Zone</th><th>Start %</th><th>End %</th><th>Delta</th>"
             "<th>Min %</th><th>Health</th><th>Drones</th><th>Irrigation</th><th>Peak Temp</th></tr></thead>")
    p.append("<tbody>")
    for za in insights.zone_analyses:
        zc = ZONE_COLORS.get(za.zone, "#94a3b8")
        dsign = "+" if za.moisture_delta_pct > 0 else ""
        dc = "#ef4444" if za.moisture_delta_pct < -5 else "#f59e0b" if za.moisture_delta_pct < 0 else "#4ade80"
        crit_label = " <span style='color:#ef4444;font-weight:600'>Critical</span>" if za.min_moisture_pct < 55 else ""
        p.append("<tr>")
        p.append("<td style='color:" + zc + ";font-weight:600'>" + _e(za.zone) + crit_label + "</td>")
        p.append("<td>" + str(round(za.moisture_start_pct, 1)) + "%</td>")
        p.append("<td>" + str(round(za.moisture_end_pct, 1)) + "%</td>")
        p.append("<td style='color:" + dc + "'>" + dsign + str(round(za.moisture_delta_pct, 1)) + "%</td>")
        p.append("<td>" + str(round(za.min_moisture_pct, 1)) + "%</td>")
        p.append("<td>" + str(round(za.crop_health_mean, 2)) + "/10</td>")
        p.append("<td>" + str(za.drone_deployments) + "</td>")
        p.append("<td>" + str(za.irrigation_events) + "</td>")
        p.append("<td>" + str(za.peak_temperature_celsius) + "°C</td>")
        p.append("</tr>")
    p.append("</tbody></table></div></div>")

    # ── drone chart + anomalies ───────────────────────────────────────────────
    p.append("<div class='card'><div class='two-col'>")
    p.append("<div><h2>Drone &amp; Irrigation Activity</h2>")
    p.append("<div style='overflow-x:auto'>" + drone_svg + "</div></div>")
    p.append("<div><h2>Global Anomalies</h2><ul style='list-style:none;padding:0'>")
    if insights.global_anomalies:
        for a in insights.global_anomalies:
            p.append("<li style='margin:6px 0;color:#fca5a5;font-size:13px'>" + _e(a) + "</li>")
    else:
        p.append("<li style='color:#4ade80;font-size:13px'>No critical anomalies detected.</li>")
    p.append("</ul></div></div></div>")

    # ── footer ────────────────────────────────────────────────────────────────
    p.append("<footer>")
    p.append("<p>Ecosystem Narrator v0.1.0 · GSoC '26 Entry Task · CatRobot Organization</p>")
    mock_note = " (Mock)" if is_mock else ""
    p.append("<p style='margin-top:4px'>Pre-processed by <code>analyzer.py</code> · Narrated via Gemini" + mock_note + "</p>")
    p.append("</footer>")
    p.append("</div>\n</body>\n</html>")

    return "\n".join(p)


def save_report(
    output: NarrationOutput,
    insights: AnalysisInsights,
    path: Path,
    is_mock: bool = False,
    source_file: str = "",
) -> Path:
    """Write the HTML report to disk. Return the output path."""
    content = generate_html_report(output, insights, is_mock, source_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path
