"""
Agent 2: Response Drafter

Writes a professional, empathetic customer support response based on
the triage assessment and relevant knowledge base articles.
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
DRAFTER_SYSTEM_PROMPT = """You are a senior support response writer. Your job is to draft a professional, empathetic customer support response based on the triage assessment and relevant knowledge base articles.

You will receive:
1. The original ticket content
2. The triage assessment (category, urgency, sentiment, core issue)
3. Relevant knowledge base articles

Guidelines:
- Match tone to customer sentiment: frustrated customers need empathy first, neutral customers need efficiency
- Reference specific solutions from the knowledge base when applicable
- Keep responses concise: 3-5 sentences for simple issues, up to 8 sentences for complex ones
- Never make promises about timelines unless specified in the KB article
- Always end with a clear next step for the customer
- Use a warm but professional tone
- Address the customer by first name

Respond ONLY with valid JSON in this exact format:
{
  "draft_response": "string",
  "kb_articles_used": ["article_id_1", "article_id_2"],
  "confidence_score": float between 0.0 and 1.0,
  "notes_for_reviewer": "string or null"
}

Confidence scoring guide:
- Above 0.8: The knowledge base directly addresses this issue with clear steps
- 0.5 to 0.8: The KB is partially relevant but doesn't fully cover the specific question
- Below 0.5: The KB doesn't cover this well; flag for human review"""


def _parse_json_response(text: str) -> dict[str, Any]:
    """
    Parse JSON from an LLM response, stripping markdown code fences if present.
    """
    cleaned = re.sub(r"^```(?:json)?\s*\n?", "", text.strip())
    cleaned = re.sub(r"\n?```\s*$", "", cleaned)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        console.print(f"[bold red]  Failed to parse drafter agent JSON: {e}[/bold red]")
        console.print(f"[dim]  Raw response: {text[:500]}[/dim]")
        raise


class DrafterAgent:
    """
    Drafts a customer-facing support response.

    Uses the triage assessment to understand the issue and tone,
    and pulls from the knowledge base for factual content.
    """

    def __init__(self, client: anthropic.Anthropic, cost_tracker: CostTracker) -> None:
        self.client = client
        self.cost_tracker = cost_tracker

    def process(
        self,
        ticket: dict[str, Any],
        triage_result: dict[str, Any],
        kb_articles: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Draft a response for the support ticket.

        Args:
            ticket: The original ticket dict.
            triage_result: Output from the Triage Agent.
            kb_articles: Relevant knowledge base articles.

        Returns:
            Dict with draft_response, confidence_score, kb_articles_used, notes.
        """
        # Build context for the drafter
        kb_section = self._format_kb_articles(kb_articles)
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
- **Customer Context:** {triage_result['customer_context']}
- **High-Value Customer:** {triage_result['high_value_flag']}

## Knowledge Base Articles

{kb_section}"""

        # Call Claude
        response = self.client.messages.create(
            model=config.ANTHROPIC_MODEL,
            max_tokens=config.ANTHROPIC_MAX_TOKENS,
            system=DRAFTER_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        # Track token usage
        self.cost_tracker.record("drafter", response.usage)

        # Parse the response
        raw_text = response.content[0].text
        result = _parse_json_response(raw_text)

        return result

    def _format_kb_articles(self, articles: list[dict[str, Any]]) -> str:
        """Format KB articles for inclusion in the prompt."""
        if not articles:
            return (
                "No relevant knowledge base articles found for this category.\n"
                "Set confidence_score below 0.5 and note this in notes_for_reviewer."
            )

        sections = []
        for article in articles:
            sections.append(
                f"### [{article['id']}] {article['title']}\n"
                f"**Category:** {article['category']} | "
                f"**Last Updated:** {article['last_updated']}\n\n"
                f"{article['content']}"
            )
        return "\n\n---\n\n".join(sections)
