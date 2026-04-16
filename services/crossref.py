"""
CrossRef Service (Fallback)
===========================
Used for DOI metadata enrichment when other sources fail.
Provides citation counts and journal info.

Docs: https://api.crossref.org/
Rate limit: 10 req/s (polite pool with mailto).
"""

import requests

BASE_URL = "https://api.crossref.org"
MAILTO = "pat@outoftheb-ox.de"
DEFAULT_TIMEOUT = 15


def fetch_by_doi(doi):
    """Fetch single DOI metadata from CrossRef."""
    if not doi:
        return None

    url = f"{BASE_URL}/works/{doi}"
    params = {"mailto": MAILTO}

    try:
        response = requests.get(url, params=params, timeout=DEFAULT_TIMEOUT)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        data = response.json().get("message", {})

        return {
            "doi": doi,
            "title": (data.get("title") or [""])[0],
            "journal": (data.get("container-title") or [""])[0],
            "cited_by_count": data.get("is-referenced-by-count", 0),
            "publisher": data.get("publisher"),
            "url": data.get("URL"),
        }
    except requests.RequestException as e:
        print(f"[crossref] Fetch failed for {doi}: {e}")
        return None
