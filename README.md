# AI Support Ops Team

A self-contained 3-agent AI support operations pipeline that processes incoming support tickets end-to-end — from triage to draft response to quality review and routing. Built as a demo for managed AI agent operations engagements.

## Architecture

```
[Incoming Ticket]           (CLI input or sample data)
       |
       v
+----------------+
|  TRIAGE AGENT  |---- Looks up customer in CRM
|                |---- Classifies: category, urgency, sentiment
|                |---- Output: structured triage summary
+-------+--------+
        |
        v
+------------------+
| RESPONSE DRAFTER |---- Pulls from knowledge base
|                  |---- Drafts customer-facing response
|                  |---- Output: draft reply + confidence score
+-------+----------+
        |
        v
+---------------------+
| QUALITY & ROUTING   |---- Evaluates: accuracy, tone, completeness, safety
|                     |---- Routes: auto-send OR human review OR escalation
|                     |---- Notifies via Slack (or console fallback)
+-------+-------------+
        |
        v
+----------------+
|  COST TRACKER  |---- Tallies tokens across all 3 agents
|                |---- Calculates per-ticket API cost
+----------------+
```

## Prerequisites

- **Python 3.11+**
- **Anthropic API key** — get one at [console.anthropic.com](https://console.anthropic.com)
- (Optional) **Slack incoming webhook URL** for escalation notifications

## Setup

```bash
# 1. Clone the repo
git clone <repo-url>
cd ai-support-ops-team

# 2. Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

## Running the Demo

Process all 5 sample tickets with polished terminal output (great for Loom recordings):

```bash
python demo.py
```

This runs each ticket through the full pipeline and displays:
- Triage assessment (category, urgency, sentiment)
- Draft response with confidence score
- Quality scores and routing decision
- Cost breakdown per agent
- Summary dashboard with totals and projections

## Processing a Single Ticket

```bash
# Process a sample ticket by ID
python run.py --ticket ticket_001

# Enter a ticket interactively
python run.py --interactive

# Process from a JSON file
python run.py --file path/to/ticket.json
```

## Sample Tickets

The demo includes 5 tickets designed to show different routing outcomes:

| Ticket | Scenario | Expected Routing |
|--------|----------|-----------------|
| ticket_001 | Simple billing question, neutral customer | Auto-send |
| ticket_002 | Obscure technical issue, not in KB | Human review (low confidence) |
| ticket_003 | Angry customer, repeated billing errors | Human review (sentiment) |
| ticket_004 | Enterprise customer, platform down | Urgent escalation |
| ticket_005 | New customer, ambiguous question | Human review (clarity) |

## Connecting to Production Systems

The demo uses mock data for CRM and knowledge base. Here's how to swap in real systems:

### CRM (HubSpot)
See `tools/crm.py` — replace `lookup_customer()` with HubSpot Contacts API calls. The downstream code expects the same dict shape as `data/customers.json`.

### Knowledge Base (Airtable / Vector DB)
See `tools/knowledge_base.py` — replace `search_articles()` with Airtable queries or vector similarity search. For better relevance, embed queries and articles with an embedding model.

### Slack Notifications
Set `SLACK_WEBHOOK_URL` in your `.env` file. The system automatically sends escalations to Slack when configured.

## Cost Estimates

Based on Claude Sonnet pricing ($3/M input tokens, $15/M output tokens):

| Volume | Estimated Cost |
|--------|---------------|
| 1 ticket | ~$0.01–0.05 |
| 100 tickets/day | ~$2–5/day |
| 3,000 tickets/month | ~$60–150/month |

Actual costs depend on ticket complexity and response length. The cost tracker provides exact per-ticket breakdowns.

## Project Structure

```
├── README.md                    # This file
├── CLAUDE.md                    # Project rules for AI-assisted development
├── .env.example                 # Environment variable template
├── requirements.txt             # Python dependencies
├── config.py                    # All configuration and thresholds
├── run.py                       # Single ticket processor + shared pipeline
├── demo.py                      # 5-ticket demo runner
├── agents/
│   ├── triage.py                # Agent 1: Triage & classification
│   ├── drafter.py               # Agent 2: Response drafting
│   └── quality_router.py        # Agent 3: QA & routing
├── tools/
│   ├── crm.py                   # Mock CRM lookup
│   ├── knowledge_base.py        # Mock KB search
│   ├── slack_notifier.py        # Slack webhook / console fallback
│   └── cost_tracker.py          # Token & cost tracking
├── data/
│   ├── customers.json           # 18 mock customer records
│   ├── knowledge_base.json      # 18 mock KB articles
│   └── sample_tickets.json      # 5 sample tickets for demo
└── output/
    └── (processing results saved here)
```
