"""
Mock CRM Lookup Tool

Loads customer records from data/customers.json and provides
lookup by email. In production, this would call the HubSpot API.
"""

import json
import os
from typing import Any

from rich.console import Console

import config

console = Console()

# ---------------------------------------------------------------------------
# PRODUCTION NOTE:
# To swap this for a real HubSpot integration, replace `lookup_customer()`
# with a call to the HubSpot Contacts API:
#
#   import hubspot
#   client = hubspot.Client.create(access_token=os.getenv("HUBSPOT_API_KEY"))
#   response = client.crm.contacts.basic_api.get_by_id(
#       contact_id, properties=["email", "firstname", "company", ...]
#   )
#
# Everything downstream expects the same dict shape, so just map the
# HubSpot response fields to match the schema in customers.json.
# ---------------------------------------------------------------------------

# Cache loaded customer data so we only read the file once
_customers: list[dict[str, Any]] | None = None


def _load_customers() -> list[dict[str, Any]]:
    """Load customer records from the JSON file (cached after first call)."""
    global _customers
    if _customers is not None:
        return _customers

    filepath = os.path.join(config.DATA_DIR, "customers.json")
    with open(filepath, "r") as f:
        _customers = json.load(f)
    return _customers


def lookup_customer(email: str) -> dict[str, Any] | None:
    """
    Look up a customer by email address.

    Returns the customer record dict if found, or None if no match.
    """
    customers = _load_customers()
    for customer in customers:
        if customer["email"].lower() == email.lower():
            return customer
    return None


def is_high_value(customer: dict[str, Any]) -> bool:
    """Check if a customer qualifies as high-value based on spend threshold."""
    return (
        customer.get("plan") == "enterprise"
        or customer.get("annual_spend", 0) >= config.HIGH_VALUE_ANNUAL_SPEND_THRESHOLD
    )
