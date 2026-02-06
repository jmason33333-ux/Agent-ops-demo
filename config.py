"""
Configuration for the AI Support Ops Team demo.

All thresholds, pricing, and model settings live here so they're
easy to find and tweak without digging through agent code.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ---------------------------------------------------------------------------
# API Configuration
# ---------------------------------------------------------------------------
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"
ANTHROPIC_MAX_TOKENS: int = 1024

# ---------------------------------------------------------------------------
# Cost Tracking (USD per million tokens) — Claude Sonnet pricing as of 2025
# ---------------------------------------------------------------------------
INPUT_TOKEN_COST_PER_MILLION: float = 3.00
OUTPUT_TOKEN_COST_PER_MILLION: float = 15.00

# ---------------------------------------------------------------------------
# Routing Thresholds
# ---------------------------------------------------------------------------
# Minimum drafter confidence to allow auto-send
AUTO_SEND_CONFIDENCE_THRESHOLD: float = 0.8

# Minimum quality score (from QA agent) to allow auto-send
AUTO_SEND_MIN_QUALITY_SCORE: float = 0.7

# Annual spend above this marks a customer as "high-value"
HIGH_VALUE_ANNUAL_SPEND_THRESHOLD: float = 10_000.0

# ---------------------------------------------------------------------------
# Slack Configuration
# ---------------------------------------------------------------------------
# Set via .env — if empty, escalations fall back to console output
SLACK_WEBHOOK_URL: str | None = os.getenv("SLACK_WEBHOOK_URL") or None

# ---------------------------------------------------------------------------
# Knowledge Base
# ---------------------------------------------------------------------------
# Number of KB articles to retrieve per ticket
KB_TOP_RESULTS: int = 3

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DATA_DIR: str = os.path.join(os.path.dirname(__file__), "data")
OUTPUT_DIR: str = os.path.join(os.path.dirname(__file__), "output")
