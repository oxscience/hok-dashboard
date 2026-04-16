"""
Hacker News Algolia API
=======================
Fetches recent "Show HN" posts matching AI keywords. Frei, kein Auth.

Docs: https://hn.algolia.com/api
"""

import requests
from datetime import datetime, timedelta
from urllib.parse import urlparse

BASE_URL = "https://hn.algolia.com/api/v1/search"
DEFAULT_TIMEOUT = 15


def _domain(url):
    try:
        d = urlparse(url).netloc
        return d.replace("www.", "") if d else ""
    except Exception:
        return ""


def _timeago(created_at_i):
    if not created_at_i:
        return ""
    delta = datetime.now() - datetime.fromtimestamp(created_at_i)
    days = delta.days
    if days == 0:
        return "heute"
    if days == 1:
        return "gestern"
    if days < 7:
        return f"vor {days} Tagen"
    if days < 30:
        return f"vor {days // 7} Woche" if days // 7 == 1 else f"vor {days // 7} Wochen"
    return f"vor {days // 30} Mon"


def fetch_ai_tools(days=30, min_points=15, limit=10, extra_query=None):
    """
    Fetch recent Show HN posts about AI tools.

    Args:
        days: Lookback window in days.
        min_points: Minimum HN points to filter noise.
        limit: Max results.
        extra_query: Additional keyword to narrow (e.g. "health", "medical").

    Returns:
        Dict with 'items' (normalized tool objects) and 'meta'.
    """
    cutoff = int((datetime.now() - timedelta(days=days)).timestamp())
    query = "AI OR LLM OR GPT OR agent"
    if extra_query:
        query = f"({query}) {extra_query}"

    params = {
        "query": query,
        "tags": "show_hn",
        "numericFilters": f"created_at_i>{cutoff},points>{min_points}",
        "hitsPerPage": min(limit * 2, 40),  # fetch extra, filter later
    }

    try:
        response = requests.get(BASE_URL, params=params, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        return {
            "items": [],
            "meta": {"error": str(e), "sources_used": []},
        }

    items = []
    for hit in data.get("hits", []):
        title = hit.get("title") or hit.get("story_title") or ""
        # Strip "Show HN: " prefix for cleaner display
        clean_title = title
        if clean_title.lower().startswith("show hn:"):
            clean_title = clean_title[8:].strip()

        url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"

        items.append({
            "title": clean_title,
            "hn_title": title,
            "tool_url": url,
            "domain": _domain(url),
            "points": hit.get("points", 0),
            "comments": hit.get("num_comments", 0),
            "author": hit.get("author", ""),
            "created_at": hit.get("created_at", ""),
            "timeago": _timeago(hit.get("created_at_i")),
            "hn_url": f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
            "source": "Show HN",
        })

    # Sort by points desc, trim
    items.sort(key=lambda x: x["points"], reverse=True)
    top = items[:limit]

    return {
        "tools": top,
        "meta": {
            "total_found": data.get("nbHits", 0),
            "returned": len(top),
            "sources_used": ["Hacker News"],
            "query_used": query,
            "days": days,
        },
    }
