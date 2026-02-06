"""
run.py — Single Ticket Processor

Process one support ticket through the full 3-agent pipeline.

Usage:
    python run.py --ticket ticket_001       # Process a sample ticket by ID
    python run.py --interactive             # Enter a ticket interactively
    python run.py --file path/to/ticket.json  # Process from a JSON file
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any

import anthropic
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

import config
from agents.drafter import DrafterAgent
from agents.quality_router import QualityRouterAgent
from agents.triage import TriageAgent
from tools.cost_tracker import CostTracker
from tools.crm import lookup_customer
from tools.knowledge_base import search_articles
from tools.slack_notifier import send_to_slack

console = Console()


# ---------------------------------------------------------------------------
# Core pipeline — shared by run.py and demo.py
# ---------------------------------------------------------------------------

def process_ticket(
    ticket: dict[str, Any], client: anthropic.Anthropic
) -> dict[str, Any]:
    """
    Run a single ticket through the full 3-agent pipeline.

    This is the core orchestration function used by both run.py and demo.py.

    Args:
        ticket: Ticket dict with id, from_email, subject, body, received_at.
        client: An initialized Anthropic client.

    Returns:
        A dict containing all results: triage, draft, quality, cost_summary.
    """
    ticket_id = ticket["id"]
    cost_tracker = CostTracker(ticket_id=ticket_id)

    # ---- Step 1: CRM Lookup ----
    console.print()
    console.print("[bold cyan]  Looking up customer in CRM...[/bold cyan]")
    customer = lookup_customer(ticket["from_email"])
    if customer:
        console.print(
            f"  Found: [bold]{customer['first_name']} {customer['last_name']}[/bold] "
            f"at {customer['company']} ({customer['plan']} plan)"
        )
    else:
        console.print("[yellow]  Customer not found in CRM.[/yellow]")

    # ---- Step 2: Triage Agent ----
    console.print()
    console.print("[bold magenta]  Triage Agent processing...[/bold magenta]")
    triage_agent = TriageAgent(client, cost_tracker)
    triage_result = triage_agent.process(ticket, customer)

    _print_triage_result(triage_result)

    # ---- Step 3: Knowledge Base Search ----
    console.print()
    console.print("[bold cyan]  Searching knowledge base...[/bold cyan]")
    # Extract keywords from the ticket subject and body for KB search
    keywords = ticket["subject"].lower().split() + ticket["body"].lower().split()[:20]
    kb_articles = search_articles(
        category=triage_result["category"],
        keywords=keywords,
    )
    console.print(f"  Found {len(kb_articles)} relevant article(s)")
    for article in kb_articles:
        console.print(f"  - [{article['id']}] {article['title']}")

    # ---- Step 4: Response Drafter Agent ----
    console.print()
    console.print("[bold magenta]  Response Drafter working...[/bold magenta]")
    drafter_agent = DrafterAgent(client, cost_tracker)
    draft_result = drafter_agent.process(ticket, triage_result, kb_articles)

    _print_draft_result(draft_result)

    # ---- Step 5: Quality & Routing Agent ----
    console.print()
    console.print("[bold magenta]  Quality & Routing reviewing...[/bold magenta]")
    qa_agent = QualityRouterAgent(client, cost_tracker)
    quality_result = qa_agent.process(ticket, triage_result, draft_result)

    _print_quality_result(quality_result)

    # ---- Step 6: Execute Routing Decision ----
    routing = quality_result.get("routing_decision", "human_review")
    _print_routing_banner(routing, ticket, triage_result, draft_result, quality_result)

    # ---- Step 7: Cost Summary ----
    cost_summary = cost_tracker.get_summary()
    _print_cost_summary(cost_summary)

    # ---- Save output to file ----
    output = {
        "ticket": ticket,
        "customer": customer,
        "triage": triage_result,
        "draft": draft_result,
        "quality": quality_result,
        "cost_summary": cost_summary,
    }
    _save_output(ticket_id, output)

    return output


# ---------------------------------------------------------------------------
# Display helpers — all use rich for polished terminal output
# ---------------------------------------------------------------------------

def _print_triage_result(result: dict[str, Any]) -> None:
    """Display triage results in a formatted table."""
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Field", style="bold")
    table.add_column("Value")

    table.add_row("Category", result.get("category", ""))
    table.add_row("Urgency", _colorize_urgency(result.get("urgency", "")))
    table.add_row("Sentiment", _colorize_sentiment(result.get("sentiment", "")))
    table.add_row("Core Issue", result.get("core_issue", ""))
    table.add_row("High-Value", str(result.get("high_value_flag", False)))
    table.add_row("Routing Rec.", result.get("recommended_routing", ""))

    console.print(Panel(table, title="[bold]Triage Assessment[/bold]", border_style="magenta"))


def _print_draft_result(result: dict[str, Any]) -> None:
    """Display the draft response and metadata."""
    # Draft response in a panel
    console.print(
        Panel(
            result.get("draft_response", ""),
            title="[bold]Draft Response[/bold]",
            border_style="blue",
            padding=(1, 2),
        )
    )

    # Metadata
    confidence = result.get("confidence_score", 0)
    confidence_color = "green" if confidence >= 0.8 else "yellow" if confidence >= 0.5 else "red"
    console.print(
        f"  Confidence: [{confidence_color}]{confidence:.0%}[/{confidence_color}]"
        f"  |  KB Articles: {', '.join(result.get('kb_articles_used', []))}"
    )
    if result.get("notes_for_reviewer"):
        console.print(f"  [yellow]Reviewer Note: {result['notes_for_reviewer']}[/yellow]")


def _print_quality_result(result: dict[str, Any]) -> None:
    """Display quality scores in a formatted table."""
    scores = result.get("quality_scores", {})
    table = Table(title="Quality Scores", show_header=True, header_style="bold")
    table.add_column("Dimension")
    table.add_column("Score", justify="center")

    for dimension in ["accuracy", "tone", "completeness", "safety"]:
        score = scores.get(dimension, 0)
        color = "green" if score >= 0.8 else "yellow" if score >= 0.6 else "red"
        table.add_row(dimension.capitalize(), f"[{color}]{score:.0%}[/{color}]")

    overall = result.get("overall_quality", 0)
    overall_color = "green" if overall >= 0.8 else "yellow" if overall >= 0.6 else "red"
    table.add_row(
        "[bold]Overall[/bold]",
        f"[bold {overall_color}]{overall:.0%}[/bold {overall_color}]",
    )

    console.print(table)


def _print_routing_banner(
    routing: str,
    ticket: dict[str, Any],
    triage_result: dict[str, Any],
    draft_result: dict[str, Any],
    quality_result: dict[str, Any],
) -> None:
    """Print the routing decision as a prominent banner and trigger notifications."""
    console.print()

    if routing == "auto_send":
        console.print(
            Panel(
                "[bold green]AUTO-SEND[/bold green] — Response approved for automatic delivery.",
                title="Routing Decision",
                border_style="green",
            )
        )
    elif routing == "human_review":
        console.print(
            Panel(
                "[bold yellow]HUMAN REVIEW[/bold yellow] — Response queued for human agent review.\n"
                f"Reason: {quality_result.get('routing_reasoning', 'N/A')}",
                title="Routing Decision",
                border_style="yellow",
            )
        )
        # Send to Slack
        slack_msg = (
            f"*Ticket:* {ticket['id']} — {ticket['subject']}\n"
            f"*From:* {ticket['from_email']}\n"
            f"*Category:* {triage_result['category']} | *Urgency:* {triage_result['urgency']}\n"
            f"*Reason:* {quality_result.get('routing_reasoning', 'N/A')}\n"
            f"*Draft Response:*\n>{draft_result.get('draft_response', '')}"
        )
        send_to_slack(slack_msg, title="Human Review Needed")

    elif routing == "urgent_escalation":
        console.print(
            Panel(
                "[bold red]URGENT ESCALATION[/bold red] — Immediate human attention required!\n"
                f"Reason: {quality_result.get('routing_reasoning', 'N/A')}",
                title="Routing Decision",
                border_style="red",
            )
        )
        # Send to Slack with urgency
        slack_msg = (
            f"*URGENT ESCALATION*\n"
            f"*Ticket:* {ticket['id']} — {ticket['subject']}\n"
            f"*From:* {ticket['from_email']}\n"
            f"*Category:* {triage_result['category']} | *Urgency:* {triage_result['urgency']}\n"
            f"*Sentiment:* {triage_result['sentiment']}\n"
            f"*High-Value:* {triage_result['high_value_flag']}\n"
            f"*Reason:* {quality_result.get('routing_reasoning', 'N/A')}"
        )
        send_to_slack(slack_msg, title="URGENT ESCALATION")


def _print_cost_summary(summary: dict[str, Any]) -> None:
    """Display cost breakdown in a table."""
    console.print()
    table = Table(title="Cost Summary", show_header=True, header_style="bold")
    table.add_column("Agent")
    table.add_column("Input Tokens", justify="right")
    table.add_column("Output Tokens", justify="right")
    table.add_column("Cost (USD)", justify="right")

    for agent_name, data in summary["agents"].items():
        table.add_row(
            agent_name,
            f"{data['input_tokens']:,}",
            f"{data['output_tokens']:,}",
            f"${data['cost_usd']:.4f}",
        )

    table.add_row(
        "[bold]Total[/bold]",
        f"[bold]{summary['total_tokens']:,}[/bold]",
        "",
        f"[bold]${summary['total_cost_usd']:.4f}[/bold]",
    )

    console.print(table)
    console.print(
        f"  Processing time: {summary['processing_time_seconds']:.1f}s"
    )


def _colorize_urgency(urgency: str) -> str:
    """Return urgency text with appropriate color markup."""
    colors = {
        "low": "green",
        "medium": "yellow",
        "high": "bold yellow",
        "critical": "bold red",
    }
    color = colors.get(urgency, "white")
    return f"[{color}]{urgency}[/{color}]"


def _colorize_sentiment(sentiment: str) -> str:
    """Return sentiment text with appropriate color markup."""
    colors = {
        "positive": "green",
        "neutral": "white",
        "frustrated": "yellow",
        "angry": "bold red",
    }
    color = colors.get(sentiment, "white")
    return f"[{color}]{sentiment}[/{color}]"


def _save_output(ticket_id: str, output: dict[str, Any]) -> None:
    """Save the full processing output to a JSON file."""
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    filepath = os.path.join(config.OUTPUT_DIR, f"{ticket_id}_result.json")
    with open(filepath, "w") as f:
        json.dump(output, f, indent=2, default=str)
    console.print(f"\n  [dim]Results saved to {filepath}[/dim]")


# ---------------------------------------------------------------------------
# CLI entry points
# ---------------------------------------------------------------------------

def _load_sample_ticket(ticket_id: str) -> dict[str, Any]:
    """Load a ticket from sample_tickets.json by ID."""
    filepath = os.path.join(config.DATA_DIR, "sample_tickets.json")
    with open(filepath, "r") as f:
        tickets = json.load(f)
    for ticket in tickets:
        if ticket["id"] == ticket_id:
            return ticket
    console.print(f"[bold red]Ticket '{ticket_id}' not found in sample data.[/bold red]")
    console.print("Available tickets:")
    for t in tickets:
        console.print(f"  - {t['id']}: {t['subject']}")
    sys.exit(1)


def _interactive_ticket() -> dict[str, Any]:
    """Prompt the user to enter a ticket interactively."""
    console.print(Panel("[bold]Enter a support ticket[/bold]", border_style="cyan"))
    from_email = console.input("[bold]Customer email:[/bold] ")
    subject = console.input("[bold]Subject:[/bold] ")
    console.print("[bold]Body[/bold] (enter a blank line to finish):")

    body_lines = []
    while True:
        line = console.input("")
        if line == "":
            break
        body_lines.append(line)

    return {
        "id": f"custom_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
        "from_email": from_email,
        "subject": subject,
        "body": "\n".join(body_lines),
        "received_at": datetime.now(timezone.utc).isoformat(),
    }


def _load_file_ticket(filepath: str) -> dict[str, Any]:
    """Load a ticket from a JSON file."""
    with open(filepath, "r") as f:
        return json.load(f)


def main() -> None:
    """Main entry point for single-ticket processing."""
    parser = argparse.ArgumentParser(description="Process a support ticket through the AI ops pipeline")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--ticket", help="Sample ticket ID (e.g. ticket_001)")
    group.add_argument("--interactive", action="store_true", help="Enter a ticket interactively")
    group.add_argument("--file", help="Path to a ticket JSON file")
    args = parser.parse_args()

    # Validate API key
    if not config.ANTHROPIC_API_KEY:
        console.print(
            "[bold red]Error: ANTHROPIC_API_KEY is not set.[/bold red]\n"
            "Copy .env.example to .env and add your API key."
        )
        sys.exit(1)

    # Load the ticket
    if args.ticket:
        ticket = _load_sample_ticket(args.ticket)
    elif args.interactive:
        ticket = _interactive_ticket()
    else:
        ticket = _load_file_ticket(args.file)

    # Print ticket header
    console.print()
    console.print(
        Panel(
            f"[bold]{ticket['subject']}[/bold]\n"
            f"From: {ticket['from_email']}\n"
            f"Received: {ticket.get('received_at', 'N/A')}",
            title=f"[bold]Ticket: {ticket['id']}[/bold]",
            border_style="cyan",
        )
    )

    # Initialize Anthropic client and process
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    process_ticket(ticket, client)

    console.print()
    console.print("[bold green]Done.[/bold green]")


if __name__ == "__main__":
    main()
