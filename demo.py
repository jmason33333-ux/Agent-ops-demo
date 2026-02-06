"""
demo.py — Demo Runner for Loom Recording

Processes all 5 sample tickets sequentially with polished rich console
output. Designed to look great in a screen recording.

Usage:
    python demo.py
"""

import json
import sys
import time

import anthropic
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

import config
from run import process_ticket

console = Console()


def main() -> None:
    """Run all sample tickets through the pipeline and show a summary dashboard."""

    # ---- Validate API key ----
    if not config.ANTHROPIC_API_KEY:
        console.print(
            "[bold red]Error: ANTHROPIC_API_KEY is not set.[/bold red]\n"
            "Copy .env.example to .env and add your API key."
        )
        sys.exit(1)

    # ---- Load sample tickets ----
    tickets_path = f"{config.DATA_DIR}/sample_tickets.json"
    with open(tickets_path, "r") as f:
        tickets = json.load(f)

    # ---- Print demo header ----
    console.print()
    console.print(
        Panel(
            "[bold]AI Support Ops Team[/bold]\n"
            "3-Agent Pipeline: Triage → Draft → Quality & Routing\n\n"
            f"Processing [bold]{len(tickets)}[/bold] sample tickets\n"
            f"Model: [cyan]{config.ANTHROPIC_MODEL}[/cyan]",
            title="[bold cyan]Demo Run[/bold cyan]",
            border_style="cyan",
            padding=(1, 2),
        )
    )
    console.print()

    # ---- Initialize Anthropic client ----
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    # ---- Process each ticket ----
    results = []
    total_start = time.time()

    for i, ticket in enumerate(tickets, 1):
        console.print(Rule(f"[bold]Ticket {i} of {len(tickets)}[/bold]", style="cyan"))
        console.print()
        console.print(
            Panel(
                f"[bold]{ticket['subject']}[/bold]\n"
                f"From: {ticket['from_email']}\n"
                f"Received: {ticket['received_at']}\n\n"
                f"[dim]{ticket['body']}[/dim]",
                title=f"[bold]Ticket: {ticket['id']}[/bold]",
                border_style="cyan",
                padding=(1, 2),
            )
        )

        try:
            output = process_ticket(ticket, client)
            results.append(output)
        except Exception as e:
            console.print(f"[bold red]  Error processing {ticket['id']}: {e}[/bold red]")
            results.append({"error": str(e), "ticket": ticket})

        console.print()

    total_elapsed = time.time() - total_start

    # ---- Summary Dashboard ----
    _print_summary_dashboard(results, total_elapsed)


def _print_summary_dashboard(
    results: list[dict], total_elapsed: float
) -> None:
    """Print a polished summary dashboard after all tickets are processed."""
    console.print()
    console.print(Rule("[bold]Summary Dashboard[/bold]", style="cyan"))
    console.print()

    # Count routing decisions
    routing_counts = {"auto_send": 0, "human_review": 0, "urgent_escalation": 0}
    total_cost = 0.0
    successful = 0

    for result in results:
        if "error" in result:
            continue
        successful += 1

        # Get routing decision from quality result
        routing = result.get("quality", {}).get("routing_decision", "unknown")
        if routing in routing_counts:
            routing_counts[routing] += 1

        # Accumulate cost
        total_cost += result.get("cost_summary", {}).get("total_cost_usd", 0)

    # ---- Ticket Overview Table ----
    overview = Table(title="Ticket Processing Overview", show_header=True, header_style="bold")
    overview.add_column("Ticket", style="bold")
    overview.add_column("Category")
    overview.add_column("Urgency")
    overview.add_column("Sentiment")
    overview.add_column("Routing", justify="center")
    overview.add_column("Cost", justify="right")

    for result in results:
        if "error" in result:
            overview.add_row(
                result["ticket"]["id"],
                "[red]ERROR[/red]",
                "", "", "", ""
            )
            continue

        ticket_id = result["ticket"]["id"]
        triage = result.get("triage", {})
        quality = result.get("quality", {})
        cost = result.get("cost_summary", {}).get("total_cost_usd", 0)
        routing = quality.get("routing_decision", "unknown")

        # Color-code routing
        routing_display = {
            "auto_send": "[bold green]AUTO-SEND[/bold green]",
            "human_review": "[bold yellow]HUMAN REVIEW[/bold yellow]",
            "urgent_escalation": "[bold red]URGENT ESCALATION[/bold red]",
        }.get(routing, routing)

        # Color-code urgency
        urgency = triage.get("urgency", "")
        urgency_colors = {"low": "green", "medium": "yellow", "high": "bold yellow", "critical": "bold red"}
        urgency_display = f"[{urgency_colors.get(urgency, 'white')}]{urgency}[/{urgency_colors.get(urgency, 'white')}]"

        overview.add_row(
            ticket_id,
            triage.get("category", ""),
            urgency_display,
            triage.get("sentiment", ""),
            routing_display,
            f"${cost:.4f}",
        )

    console.print(overview)
    console.print()

    # ---- Summary Stats ----
    stats = Table(title="Run Statistics", show_header=False, box=None, padding=(0, 3))
    stats.add_column("Metric", style="bold")
    stats.add_column("Value")

    stats.add_row("Total Tickets Processed", f"{successful}/{len(results)}")
    stats.add_row(
        "Routing Breakdown",
        f"[green]{routing_counts['auto_send']} auto-sent[/green] | "
        f"[yellow]{routing_counts['human_review']} human review[/yellow] | "
        f"[red]{routing_counts['urgent_escalation']} escalated[/red]",
    )
    stats.add_row("Total API Cost", f"[bold]${total_cost:.4f}[/bold]")

    avg_cost = total_cost / successful if successful > 0 else 0
    stats.add_row("Average Cost per Ticket", f"${avg_cost:.4f}")

    avg_time = total_elapsed / len(results) if results else 0
    stats.add_row("Total Processing Time", f"{total_elapsed:.1f}s")
    stats.add_row("Average Time per Ticket", f"{avg_time:.1f}s")

    # Cost projection
    daily_cost_100 = avg_cost * 100
    monthly_cost_100 = daily_cost_100 * 30
    stats.add_row(
        "Projected Cost (100 tickets/day)",
        f"${daily_cost_100:.2f}/day | ${monthly_cost_100:.2f}/month",
    )

    console.print(stats)
    console.print()
    console.print("[bold green]Demo complete.[/bold green]")
    console.print()


if __name__ == "__main__":
    main()
