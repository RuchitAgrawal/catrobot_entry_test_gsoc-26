"""
cli.py - Rich-powered CLI for Ecosystem Narrator.

Flags:
  --data PATH               Run pipeline on a CSV file
  --generate-scenario TYPE  Procedurally generate scenario data (no CSV needed)
  --watch                   Re-narrate whenever the CSV file changes
  --export-report PATH      Export a standalone HTML report with SVG charts
  --mock                    Force mock mode
  --output PATH             Save narration JSON to a file
  --no-table                Skip printing the raw data table

Scenario types: normal | drought | crisis | recovery
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
import time
from pathlib import Path

from rich import box
from rich.columns import Columns
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from .models import EcosystemDataset, ZoneAnalysis
from .narrator import EcosystemNarrator, MockClient, load_csv
from .scenario_generator import (
    SCENARIO_DESCRIPTIONS,
    ScenarioType,
    generate_scenario,
    scenario_to_csv,
)

console = Console()

TONE_DISPLAY = {
    "routine":   ("✅ Routine Monitoring Log",    "green"),
    "advisory":  ("⚠  Field Advisory",           "yellow"),
    "emergency": ("🚨 Emergency Situation Report", "bold red"),
}


# Rendering helpers

def render_header() -> None:
    console.print()
    console.print(
        Panel(
            "[bold green]🌾  Agricultural Ecosystem Narrator[/bold green]\n"
            "[dim]Gemini-Powered Sensor Grid Analysis[/dim]",
            border_style="green",
            padding=(1, 4),
        )
    )
    console.print()


def render_dataset_table(dataset: EcosystemDataset) -> None:
    table = Table(
        title="📊 Ecosystem Sensor Data",
        box=box.ROUNDED,
        border_style="bright_blue",
        header_style="bold cyan",
        show_lines=True,
        expand=True,
    )

    table.add_column("Timestamp", style="dim", width=18)
    table.add_column("Zone", style="bold white", width=8)
    table.add_column("Moisture %", justify="right")
    table.add_column("Health", justify="right")
    table.add_column("Drone", justify="center")
    table.add_column("Irrigation", justify="center")
    table.add_column("Temp °C", justify="right")

    events = sorted(dataset.events, key=lambda e: (e.sensor_zone, e.timestamp))
    for e in events:
        moisture_style = (
            "bold red" if e.soil_moisture_pct < 55
            else "yellow" if e.soil_moisture_pct < 65
            else "green"
        )
        health_style = (
            "red" if e.crop_health_index < 7
            else "yellow" if e.crop_health_index < 8
            else "green"
        )
        table.add_row(
            e.timestamp.strftime("%m-%d %H:%M"),
            e.sensor_zone,
            Text(f"{e.soil_moisture_pct:.1f}%", style=moisture_style),
            Text(f"{e.crop_health_index:.1f}", style=health_style),
            "[bold yellow]✈ YES[/bold yellow]" if e.drone_active else "[dim]—[/dim]",
            "[bold cyan]💧 YES[/bold cyan]" if e.irrigation_triggered else "[dim]—[/dim]",
            f"{e.temperature_celsius:.1f}",
        )

    console.print(table)
    console.print()


def render_insights(zone_analyses: list[ZoneAnalysis], global_anomalies: list[str],
                    severity_score: float, tone_register: str) -> None:
    tone_label, tone_style = TONE_DISPLAY.get(tone_register, ("Monitoring", "dim"))
    console.print(Rule(f"[{tone_style}]{tone_label}[/{tone_style}]  ·  "
                       f"[dim]severity={severity_score:.2f}[/dim]"))
    console.print()

    panels = []
    for za in zone_analyses:
        delta_style = (
            "red" if za.moisture_delta_pct < -5
            else "yellow" if za.moisture_delta_pct < 0
            else "green"
        )
        content = (
            f"[bold]Moisture:[/bold] {za.moisture_start_pct:.1f}% → {za.moisture_end_pct:.1f}% "
            f"([{delta_style}]{za.moisture_delta_pct:+.1f}%[/{delta_style}])\n"
            f"[bold]Min/Max:[/bold] {za.min_moisture_pct:.1f}% / {za.max_moisture_pct:.1f}%\n"
            f"[bold]Drop Rate:[/bold] {za.moisture_drop_rate_per_hour:.2f}%/h\n"
            f"[bold]Health:[/bold] {za.crop_health_mean:.2f}/10 (Δ{za.crop_health_delta:+.1f})\n"
            f"[bold]Drones:[/bold] {za.drone_deployments} deployments\n"
            f"[bold]Irrigation:[/bold] {za.irrigation_events} event(s)\n"
            f"[bold]Peak Temp:[/bold] {za.peak_temperature_celsius}°C"
        )

        if za.anomaly_flags:
            content += "\n\n[bold red]⚠ Anomalies:[/bold red]"
            for flag in za.anomaly_flags:
                content += f"\n  • {flag}"

        border = (
            "red" if za.min_moisture_pct < 55
            else "yellow" if za.min_moisture_pct < 65
            else "green"
        )
        panels.append(
            Panel(content, title=f"[bold]{za.zone}[/bold]", border_style=border, expand=True)
        )

    console.print(Columns(panels, equal=True))
    console.print()

    if global_anomalies:
        console.print(Rule("[bold red]⚠  Global Anomalies Detected[/bold red]"))
        for anomaly in global_anomalies:
            console.print(f"  [red]•[/red] {anomaly}")
        console.print()


def render_narration(output, elapsed: float) -> None:
    console.print(Rule("[bold green]🌿 Ecosystem Narration[/bold green]"))
    console.print()

    narration_md = Markdown(f"*{output.narration}*")
    console.print(
        Panel(
            narration_md,
            title="[bold green]AI Narration[/bold green]",
            border_style="bright_green",
            padding=(1, 3),
        )
    )
    console.print()

    conf_color = (
        "green" if output.confidence >= 0.8
        else "yellow" if output.confidence >= 0.6
        else "red"
    )
    meta_table = Table(box=box.SIMPLE, show_header=False)
    meta_table.add_column("Key", style="dim")
    meta_table.add_column("Value", style="bold")
    meta_table.add_row("Sentences", str(output.sentence_count))
    meta_table.add_row("Confidence", Text(f"{output.confidence:.0%}", style=conf_color))
    meta_table.add_row("Generated in", f"{elapsed:.2f}s")
    meta_table.add_row("Anomalies covered", str(len(output.anomalies_detected)))
    console.print(meta_table)

    if output.anomalies_detected:
        console.print()
        console.print("[bold]Anomalies covered in narration:[/bold]")
        for a in output.anomalies_detected:
            console.print(f"  [cyan]→[/cyan] {a}")

    console.print()


# Pipeline runner (used by both single-shot and watch mode)

def run_pipeline(
    dataset: EcosystemDataset,
    narrator: EcosystemNarrator,
    show_table: bool = True,
    export_report: Path | None = None,
    output_path: Path | None = None,
    is_watch: bool = False,
) -> None:
    if show_table and not is_watch:
        render_dataset_table(dataset)

    start = time.perf_counter()
    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
        console=console, transient=True,
    ) as progress:
        progress.add_task(
            "[cyan]Running statistical analysis and generating narration...[/cyan]",
            total=None,
        )
        output, insights = narrator.narrate(dataset)
    elapsed = time.perf_counter() - start

    render_insights(
        insights.zone_analyses,
        insights.global_anomalies,
        insights.severity_score,
        insights.tone_register,
    )
    render_narration(output, elapsed)

    if export_report:
        from .report_generator import save_report
        saved = save_report(
            output, insights, export_report,
            is_mock=isinstance(narrator.client, MockClient),
            source_file=dataset.source_file,
        )
        console.print(f"[green]✓[/green] HTML report saved to [bold]{saved}[/bold]")
        console.print()

    if output_path:
        result_data = {
            "narration_output": output.model_dump(mode="json"),
            "analysis_insights": insights.model_dump(mode="json"),
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(result_data, indent=2, default=str), encoding="utf-8"
        )
        console.print(f"[green]✓[/green] Output saved to [bold]{output_path}[/bold]")
        console.print()


# Watch mode

async def _watch_async(
    data_path: Path,
    narrator: EcosystemNarrator,
    export_report: Path | None,
    output_path: Path | None,
) -> None:
    """Poll the CSV file for changes and re-run the pipeline on each change."""
    try:
        from watchfiles import awatch
    except ImportError:
        console.print("[bold red]Error:[/bold red] watchfiles not installed. Run: uv add watchfiles")
        return

    console.print(
        Panel(
            f"[bold cyan]👁  Watch Mode Active[/bold cyan]\n"
            f"[dim]Monitoring: {data_path}\n"
            f"Re-narrating automatically on file change.\n"
            f"Press Ctrl+C to stop.[/dim]",
            border_style="cyan",
            padding=(1, 3),
        )
    )

    last_hash = None
    try:
        dataset = load_csv(data_path)
        last_hash = _file_hash(data_path)
        console.print(Rule("[cyan]Initial Narration[/cyan]"))
        run_pipeline(dataset, narrator, show_table=False,
                     export_report=export_report, output_path=output_path, is_watch=True)
    except Exception as e:
        console.print(f"[red]Initial load error:[/red] {e}")

    async for changes in awatch(data_path):
        current_hash = _file_hash(data_path)
        if current_hash == last_hash:
            continue  # spurious event
        last_hash = current_hash

        console.print()
        console.print(Rule(f"[cyan]📡 File Changed — Re-Narrating[/cyan]  [dim]{time.strftime('%H:%M:%S')}[/dim]"))
        try:
            dataset = load_csv(data_path)
            run_pipeline(
                dataset, narrator, show_table=False,
                export_report=export_report, output_path=output_path, is_watch=True,
            )
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")


def _file_hash(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


# CLI entry point

def app() -> None:
    parser = argparse.ArgumentParser(
        prog="ecosystem-narrator",
        description="Gemini-Powered Agricultural Ecosystem Narration System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  ecosystem-narrator --data data/agro_ecosystem_sample.csv\n"
            "  ecosystem-narrator --generate-scenario drought\n"
            "  ecosystem-narrator --data data/agro_ecosystem_sample.csv --watch\n"
            "  ecosystem-narrator --data data/agro_ecosystem_sample.csv --export-report report.html\n"
            "  ecosystem-narrator --generate-scenario crisis --mock\n"
        ),
    )
    parser.add_argument("--data", "-d", type=Path, default=None,
                        help="Path to CSV ecosystem data file")
    parser.add_argument(
        "--generate-scenario", "-g",
        choices=["normal", "drought", "crisis", "recovery"],
        metavar="SCENARIO",
        default=None,
        help="Procedurally generate scenario data: normal | drought | crisis | recovery",
    )
    parser.add_argument("--watch", "-w", action="store_true",
                        help="Re-narrate whenever the CSV file changes (requires --data)")
    parser.add_argument("--export-report", "-r", type=Path, default=None, metavar="PATH",
                        help="Export a self-contained HTML report with SVG charts")
    parser.add_argument("--mock", "-m", action="store_true",
                        help="Force mock mode (skip Gemini API call)")
    parser.add_argument("--output", "-o", type=Path, default=None,
                        help="Save narration output to a JSON file")
    parser.add_argument("--no-table", action="store_true",
                        help="Skip printing the raw data table")

    args = parser.parse_args()

    if args.data is None and args.generate_scenario is None:
        parser.error("Provide either --data PATH or --generate-scenario SCENARIO")

    if args.watch and args.data is None:
        parser.error("--watch requires --data to specify which file to monitor")

    render_header()

    # Load or generate dataset
    if args.generate_scenario:
        scenario: ScenarioType = args.generate_scenario  # type: ignore[assignment]
        console.print(
            Panel(
                f"[bold cyan]🔬 Generating Scenario: [white]{scenario.upper()}[/white][/bold cyan]\n"
                f"[dim]{SCENARIO_DESCRIPTIONS[scenario]}[/dim]",
                border_style="cyan",
                padding=(1, 3),
            )
        )
        csv_path = Path(f"data/generated_{scenario}.csv")
        scenario_to_csv(scenario, output_path=csv_path)
        console.print(f"[green]✓[/green] Generated CSV saved to [bold]{csv_path}[/bold]\n")

        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                      console=console, transient=True) as progress:
            task = progress.add_task("Building dataset from scenario...", total=None)
            dataset = generate_scenario(scenario)
            progress.update(task, completed=True)
    else:
        if not args.data.exists():
            console.print(f"[bold red]Error:[/bold red] File not found: {args.data}")
            sys.exit(1)
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                      console=console, transient=True) as progress:
            task = progress.add_task("Loading and validating ecosystem data...", total=None)
            dataset = load_csv(args.data)
            progress.update(task, completed=True)

    console.print(
        f"[green]✓[/green] Loaded [bold]{len(dataset.events)}[/bold] events "
        f"from [bold]{len(dataset.zones)}[/bold] zones "
        f"across [bold]{dataset.time_range_hours:.1f}h[/bold] window\n"
    )

    client = MockClient() if args.mock else None
    narrator = EcosystemNarrator(client=client)

    if args.watch:
        try:
            asyncio.run(
                _watch_async(args.data, narrator, args.export_report, args.output)
            )
        except KeyboardInterrupt:
            console.print("\n[dim]Watch mode stopped.[/dim]")
        return

    if not args.no_table:
        render_dataset_table(dataset)

    run_pipeline(
        dataset=dataset,
        narrator=narrator,
        show_table=False,
        export_report=args.export_report,
        output_path=args.output,
    )

    console.print(Rule("[dim]Ecosystem Narrator Complete[/dim]"))


if __name__ == "__main__":
    app()
