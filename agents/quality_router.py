"""
Agent 3: Quality & Routing Agent

Evaluates draft responses for quality and decides whether to
auto-send, route to human review, or urgently escalate.
"""

import json
import re
from typing import Any

import anthropic
from rich.console import Console

import config
from tools.cost_tracker import CostTracker

console = Console()

# ---------------------------------------------------------------------------
# System prompt — defined here as a constant so it's easy to find and tweak
# ---------------------------------------------------------------------------
QUALITY_ROUTER_SYSTEM_PROMPT = """You are a support quality assurance specialist. Your job is to evaluate a draft support response and decide whether it should be auto-sent to the customer or routed to a human reviewer.

You will receive:
1. The original ticket
2. The triage assessment
3. The draft response
4. The drafter's confidence score

Evaluate the draft on these criteria:
- Accuracy: Does the response address the actual issue raised in the ticket?
- Tone: Is the tone appropriate for the customer's sentiment?
- Completeness: Does the response include a clear next step?
- Safety: Does the response make any inappropriate promises or contain potentially incorrect information?

Routing rules:
- AUTO_SEND: All criteria pass AND confidence >= 0.8 AND urgency is low/medium AND sentiment is not angry
- HUMAN_REVIEW: Any criteria fails OR confidence < 0.8 OR urgency is high OR sentiment is angry
- URGENT_ESCALATION: Customer is high-value AND (urgency is critical OR sentiment is angry)

Respond ONLY with valid JSON in this exact format:
{
  "quality_scores": {
    "accuracy": float 0-1,
    "tone": float 0-1,
    "completeness": float 0-1,
    "safety": float 0-1
  },
  "overall_quality": float 0-1,
  "routing_decision": "auto_send | human_review | urgent_escalation",
  "routing_reasoning": "string",
  "suggested_edits": "string or null"
}"""


def _parse_json_response(text: str) -> dict[str, Any]:
    """
    Parse JSON from an LLM response, stripping markdown code fences if present.
    """
    cleaned = re.sub(r"^```(?:json)?\s*\n?", "", text.strip())
    cleaned = re.sub(r"\n?```\s*$", "", cleaned)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        console.print(
            f"[bold red]  Failed to parse quality router JSON: {e}[/bold red]"
        )
        console.print(f"[dim]  Raw response: {text[:500]}[/dim]")
        raise


class QualityRouterAgent:
    """
    Evaluates draft responses and makes routing decisions.

    Scores the draft on accuracy, tone, completeness, and safety,
    then applies routing rules to decide next steps.
    """

    def __init__(self, client: anthropic.Anthropic, cost_tracker: CostTracker) -> None:
        self.client = client
        self.cost_tracker = cost_tracker

    def process(
        self,
        ticket: dict[str, Any],
        triage_result: dict[str, Any],
        draft_result: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Evaluate the draft response and decide on routing.

        Args:
            ticket: The original ticket dict.
            triage_result: Output from the Triage Agent.
            draft_result: Output from the Drafter Agent.

        Returns:
            Dict with quality_scores, routing_decision, reasoning, suggested_edits.
        """
        user_message = f"""## Original Ticket

**Subject:** {ticket['subject']}
**From:** {ticket['from_email']}
**Body:**
{ticket['body']}

## Triage Assessment

- **Category:** {triage_result['category']}
- **Urgency:** {triage_result['urgency']}
- **Sentiment:** {triage_result['sentiment']}
- **Core Issue:** {triage_result['core_issue']}
- **High-Value Customer:** {triage_result['high_value_flag']}
- **Triage Routing Recommendation:** {triage_result['recommended_routing']}

## Draft Response

{draft_result['draft_response']}

## Drafter Metadata

- **Confidence Score:** {draft_result['confidence_score']}
- **KB Articles Used:** {', '.join(draft_result.get('kb_articles_used', []))}
- **Drafter Notes:** {draft_result.get('notes_for_reviewer') or 'None'}"""

        # Call Claude
        response = self.client.messages.create(
            model=config.ANTHROPIC_MODEL,
            max_tokens=config.ANTHROPIC_MAX_TOKENS,
            system=QUALITY_ROUTER_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        # Track token usage
        self.cost_tracker.record("quality_router", response.usage)

        # Parse the response
        raw_text = response.content[0].text
        result = _parse_json_response(raw_text)

        return result
