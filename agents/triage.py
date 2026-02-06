"""
Agent 1: Triage Agent

Classifies, prioritizes, and enriches incoming support tickets with
customer data from the CRM. Outputs a structured triage assessment
that downstream agents use for drafting and routing.
"""

import json
import re
from typing import Any

import anthropic
from rich.console import Console

import config
from tools.cost_tracker import CostTracker
from tools.crm import is_high_value

console = Console()

# ---------------------------------------------------------------------------
# System prompt — defined here as a constant so it's easy to find and tweak
# ---------------------------------------------------------------------------
TRIAGE_SYSTEM_PROMPT = """You are a Tier 1 Support Triage Specialist for a mid-size SaaS company. Your job is to analyze incoming support tickets and produce a structured triage assessment.

You will receive:
1. The raw ticket content (subject + body)
2. Customer profile data from our CRM

Your job:
- Classify the ticket into exactly one category: billing, account_access, technical, shipping, refund, general_inquiry
- Assess urgency: low, medium, high, critical
- Assess customer sentiment: positive, neutral, frustrated, angry
- Identify the core issue in one sentence
- Note any relevant customer context (plan tier, tenure, previous issues, account value)
- Flag if this customer is high-value (enterprise plan or >$10K annual spend)
- Recommend routing: auto_respond (simple, well-covered issues), human_review (complex or sensitive), urgent_escalation (critical + high-value)

Respond ONLY with valid JSON in this exact format:
{
  "category": "string",
  "urgency": "string",
  "sentiment": "string",
  "core_issue": "string",
  "customer_context": "string",
  "high_value_flag": boolean,
  "recommended_routing": "auto_respond | human_review | urgent_escalation",
  "reasoning": "string"
}"""


def _parse_json_response(text: str) -> dict[str, Any]:
    """
    Parse JSON from an LLM response, stripping markdown code fences if present.

    Claude sometimes wraps JSON in ```json ... ``` blocks. This handles that
    gracefully, plus a few other common quirks.
    """
    # Strip markdown code fences (```json ... ``` or ``` ... ```)
    cleaned = re.sub(r"^```(?:json)?\s*\n?", "", text.strip())
    cleaned = re.sub(r"\n?```\s*$", "", cleaned)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        console.print(f"[bold red]  Failed to parse triage agent JSON: {e}[/bold red]")
        console.print(f"[dim]  Raw response: {text[:500]}[/dim]")
        raise


class TriageAgent:
    """
    Classifies and prioritizes incoming support tickets.

    Takes a ticket dict and optional customer profile, calls Claude
    to produce a structured triage assessment.
    """

    def __init__(self, client: anthropic.Anthropic, cost_tracker: CostTracker) -> None:
        self.client = client
        self.cost_tracker = cost_tracker

    def process(
        self, ticket: dict[str, Any], customer: dict[str, Any] | None
    ) -> dict[str, Any]:
        """
        Run triage on a support ticket.

        Args:
            ticket: The ticket dict (id, from_email, subject, body, received_at).
            customer: The customer profile from CRM, or None if not found.

        Returns:
            Structured triage assessment dict.
        """
        # Build the user message with ticket + customer context
        customer_section = self._format_customer(customer)
        user_message = f"""## Incoming Support Ticket

**Ticket ID:** {ticket['id']}
**From:** {ticket['from_email']}
**Subject:** {ticket['subject']}
**Received:** {ticket['received_at']}

**Body:**
{ticket['body']}

## Customer Profile
{customer_section}"""

        # Call Claude
        response = self.client.messages.create(
            model=config.ANTHROPIC_MODEL,
            max_tokens=config.ANTHROPIC_MAX_TOKENS,
            system=TRIAGE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        # Track token usage
        self.cost_tracker.record("triage", response.usage)

        # Parse the JSON response
        raw_text = response.content[0].text
        result = _parse_json_response(raw_text)

        # Post-processing overrides based on business rules
        result = self._apply_business_rules(result, customer)

        return result

    def _format_customer(self, customer: dict[str, Any] | None) -> str:
        """Format customer data for the prompt, or note that they're unknown."""
        if customer is None:
            return (
                "**Customer not found in CRM.** This is an unknown customer.\n"
                "Recommend human_review for unknown customers."
            )

        return (
            f"**Name:** {customer['first_name']} {customer['last_name']}\n"
            f"**Company:** {customer['company']}\n"
            f"**Plan:** {customer['plan']}\n"
            f"**Annual Spend:** ${customer['annual_spend']:,.2f}\n"
            f"**Account Created:** {customer['account_created']}\n"
            f"**Previous Tickets:** {customer['previous_tickets']}\n"
            f"**Satisfaction Score:** {customer.get('satisfaction_score') or 'N/A'}\n"
            f"**Notes:** {customer.get('notes') or 'None'}"
        )

    def _apply_business_rules(
        self, result: dict[str, Any], customer: dict[str, Any] | None
    ) -> dict[str, Any]:
        """
        Apply hard business rules that override the LLM's judgment.

        Rules:
        - If customer is unknown → always recommend human_review
        - If sentiment is angry AND customer is high-value → force urgent_escalation
        """
        # Unknown customer → human review
        if customer is None:
            result["recommended_routing"] = "human_review"
            result["customer_context"] = (
                "Unknown customer — not found in CRM. " + result.get("customer_context", "")
            )

        # Angry + high-value → urgent escalation
        if (
            customer is not None
            and result.get("sentiment") == "angry"
            and is_high_value(customer)
        ):
            result["recommended_routing"] = "urgent_escalation"
            if "urgent_escalation" not in result.get("reasoning", ""):
                result["reasoning"] += (
                    " [OVERRIDE: Angry sentiment + high-value customer → urgent escalation]"
                )

        return result
