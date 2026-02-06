"""
Mock Knowledge Base Search Tool

Loads support articles from data/knowledge_base.json and provides
search by category and keyword relevance. In production, this would
query Airtable, a vector database, or a search API.
"""

import json
import os
from typing import Any

import config

# ---------------------------------------------------------------------------
# PRODUCTION NOTE:
# To swap this for Airtable, replace `search_articles()` with:
#
#   from pyairtable import Api
#   api = Api(os.getenv("AIRTABLE_API_KEY"))
#   table = api.table("appXXXXXX", "Knowledge Base")
#   records = table.all(formula=f"{{Category}} = '{category}'")
#
# For a vector DB (e.g., Pinecone, Weaviate), you'd embed the query
# and do a similarity search instead of keyword matching.
# ---------------------------------------------------------------------------

# Cache loaded KB data
_articles: list[dict[str, Any]] | None = None


def _load_articles() -> list[dict[str, Any]]:
    """Load knowledge base articles from the JSON file (cached)."""
    global _articles
    if _articles is not None:
        return _articles

    filepath = os.path.join(config.DATA_DIR, "knowledge_base.json")
    with open(filepath, "r") as f:
        _articles = json.load(f)
    return _articles


def _keyword_score(article: dict[str, Any], keywords: list[str]) -> int:
    """
    Score an article by how many of the search keywords appear in its
    keywords list or title. Higher score = more relevant.
    """
    score = 0
    article_keywords = [kw.lower() for kw in article.get("keywords", [])]
    article_title = article.get("title", "").lower()

    for keyword in keywords:
        kw_lower = keyword.lower()
        # Check keyword list
        if kw_lower in article_keywords:
            score += 2  # Direct keyword match is worth more
        # Check title
        if kw_lower in article_title:
            score += 1

    return score


def search_articles(
    category: str,
    keywords: list[str] | None = None,
    top_k: int | None = None,
) -> list[dict[str, Any]]:
    """
    Search the knowledge base by category, then rank by keyword relevance.

    Args:
        category: The ticket category (e.g. "billing", "technical").
        keywords: Optional list of keywords to rank results by relevance.
        top_k: Number of results to return. Defaults to config.KB_TOP_RESULTS.

    Returns:
        List of matching articles, sorted by relevance (best first).
    """
    if top_k is None:
        top_k = config.KB_TOP_RESULTS

    articles = _load_articles()

    # Step 1: Filter by category
    category_matches = [
        a for a in articles if a["category"].lower() == category.lower()
    ]

    # Step 2: If we have keywords, score and sort by relevance
    if keywords:
        scored = [(a, _keyword_score(a, keywords)) for a in category_matches]
        scored.sort(key=lambda x: x[1], reverse=True)
        results = [a for a, _ in scored[:top_k]]
    else:
        results = category_matches[:top_k]

    # Step 3: If we didn't get enough results from the category, pad with
    # keyword matches from other categories
    if len(results) < top_k and keywords:
        other_articles = [a for a in articles if a not in results]
        scored_others = [(a, _keyword_score(a, keywords)) for a in other_articles]
        scored_others.sort(key=lambda x: x[1], reverse=True)
        for article, score in scored_others:
            if score > 0 and len(results) < top_k:
                results.append(article)

    return results
