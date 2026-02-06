"""
Cost Tracker

Tracks token usage and calculates API costs across all agent calls
for a single ticket processing run. Uses pricing from config.py.
"""

import time
from typing import Any

import config


class CostTracker:
    """
    Accumulates token usage across multiple agent calls and calculates costs.

    Usage:
        tracker = CostTracker(ticket_id="ticket_001")
        tracker.record("triage", usage_from_api_response)
        tracker.record("drafter", usage_from_api_response)
        tracker.record("quality_router", usage_from_api_response)
        summary = tracker.get_summary()
    """

    def __init__(self, ticket_id: str) -> None:
        self.ticket_id = ticket_id
        self._start_time = time.time()
        self._agents: dict[str, dict[str, Any]] = {}

    def record(self, agent_name: str, usage: Any) -> None:
        """
        Record token usage from an Anthropic API response.

        Args:
            agent_name: Which agent made the call (e.g. "triage", "drafter").
            usage: The `usage` object from the Anthropic API response.
                   Expected to have `input_tokens` and `output_tokens` attributes.
        """
        input_tokens = getattr(usage, "input_tokens", 0)
        output_tokens = getattr(usage, "output_tokens", 0)

        # Calculate cost for this call
        input_cost = (input_tokens / 1_000_000) * config.INPUT_TOKEN_COST_PER_MILLION
        output_cost = (output_tokens / 1_000_000) * config.OUTPUT_TOKEN_COST_PER_MILLION
        total_cost = input_cost + output_cost

        self._agents[agent_name] = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": round(total_cost, 6),
        }

    def get_total_cost(self) -> float:
        """Return the total cost across all agents in USD."""
        return sum(a["cost_usd"] for a in self._agents.values())

    def get_total_tokens(self) -> int:
        """Return total tokens (input + output) across all agents."""
        return sum(
            a["input_tokens"] + a["output_tokens"] for a in self._agents.values()
        )

    def get_processing_time(self) -> float:
        """Return elapsed time since tracker was created, in seconds."""
        return round(time.time() - self._start_time, 2)

    def get_summary(self) -> dict[str, Any]:
        """
        Return a complete cost summary for this ticket.

        Returns a dict matching the spec:
        {
            "ticket_id": str,
            "agents": { agent_name: { input_tokens, output_tokens, cost_usd } },
            "total_tokens": int,
            "total_cost_usd": float,
            "processing_time_seconds": float,
        }
        """
        return {
            "ticket_id": self.ticket_id,
            "agents": dict(self._agents),
            "total_tokens": self.get_total_tokens(),
            "total_cost_usd": round(self.get_total_cost(), 6),
            "processing_time_seconds": self.get_processing_time(),
        }
