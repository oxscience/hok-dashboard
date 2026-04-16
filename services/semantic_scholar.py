"""
Semantic Scholar Service
========================
Returns AI-generated tldr (one-line summary) and influential citation count.

Docs: https://api.semanticscholar.org/graph/v1/
Rate limit: 1 req/s with free key, shared pool without.
"""

import requests
import time

BASE_URL = "https://api.semanticscholar.org/graph/v1"
DEFAULT_TIMEOUT = 15
FIELDS = "tldr,citationCount,influentialCitationCount,openAccessPdf"


def enrich_by_dois(dois):
    """
    Enrich studies with Semantic Scholar data via DOI batch endpoint.

    Args:
        dois: List of DOIs (strings, no doi.org prefix).

    Returns:
        Dict mapping DOI (lowercase) -> { tldr, citations, influential, oa_pdf }
    """
    if not dois:
        return {}

    # S2 batch endpoint: POST /paper/batch
    url = f"{BASE_URL}/paper/batch"
    params = {"fields": FIELDS}
    # Format IDs as DOI:xxx
    payload = {"ids": [f"DOI:{doi}" for doi in dois if doi]}

    if not payload["ids"]:
        return {}

    try:
        response = requests.post(
            url,
            params=params,
            json=payload,
            timeout=DEFAULT_TIMEOUT,
            headers={"User-Agent": "HoK-Dashboard/1.0"},
        )
        # S2 may return 429 under load — retry once
        if response.status_code == 429:
            time.sleep(1.2)
            response = requests.post(url, params=params, json=payload, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        data = response.json()

        results = {}
        for idx, paper in enumerate(data):
            if paper is None:
                continue
            doi_input = dois[idx].lower() if idx < len(dois) else None
            if not doi_input:
                continue

            tldr_obj = paper.get("tldr") or {}
            oa_pdf = paper.get("openAccessPdf") or {}

            results[doi_input] = {
                "tldr": tldr_obj.get("text"),
                "citations": paper.get("citationCount", 0),
                "influential": paper.get("influentialCitationCount", 0),
                "oa_pdf_url": oa_pdf.get("url"),
            }
        return results
    except requests.RequestException as e:
        print(f"[s2] Enrichment failed: {e}")
        return {}
