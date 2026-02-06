"""
Slack Notification Tool

Sends messages to a Slack channel via incoming webhook.
Falls back to rich console output if no webhook URL is configured.
"""

import json

import requests
from rich.console import Console
from rich.panel import Panel

import config

console = Console()


def send_to_slack(message: str, title: str = "Support Escalation") -> bool:
    """
    Send a notification to Slack via incoming webhook.

    If SLACK_WEBHOOK_URL is not configured, prints the message to the
    console as a fallback so the demo still looks good in a Loom recording.

    Args:
        message: The message body to send.
        title: A short title for the notification.

    Returns:
        True if the message was sent (or printed as fallback), False on error.
    """
    # ----- Slack webhook path (production) -----
    if config.SLACK_WEBHOOK_URL:
        try:
            payload = {
                "text": f"*{title}*\n{message}",
            }
            response = requests.post(
                config.SLACK_WEBHOOK_URL,
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            if response.status_code == 200:
                console.print(
                    "[bold green]  Slack notification sent successfully.[/bold green]"
                )
                return True
            else:
                console.print(
                    f"[bold red]  Slack webhook returned status {response.status_code}[/bold red]"
                )
                return False
        except requests.RequestException as e:
            console.print(f"[bold red]  Slack webhook failed: {e}[/bold red]")
            return False

    # ----- Console fallback (no Slack configured) -----
    console.print()
    console.print(
        Panel(
            message,
            title=f"[bold yellow]SLACK FALLBACK[/bold yellow] — {title}",
            border_style="yellow",
            padding=(1, 2),
        )
    )
    return True
