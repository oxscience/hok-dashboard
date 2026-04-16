"""
PubMed E-utilities Service
===========================
Primary search API. Uses PubMed publication type filters to narrow down
to RCTs, systematic reviews, and meta-analyses.

Docs: https://www.ncbi.nlm.nih.gov/books/NBK25497/
Rate limit: 3 req/s without key, 10 req/s with key.
"""

import requests
from datetime import datetime, timedelta
from urllib.parse import urlencode

BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
USER_AGENT = "HoK-Dashboard/1.0 (contact: pat@outoftheb-ox.de)"
DEFAULT_TIMEOUT = 15


def search_recent(query, days=30, max_results=20, study_types=None):
    """
    Search PubMed for recent studies matching the query.

    Args:
        query: Search term (Fachgebiet). English recommended.
        days: Days back from today (publication date).
        max_results: Max PMIDs to return.
        study_types: List like ["rct", "review", "meta"]. None = all.

    Returns:
        List of PMIDs (strings).
    """
    # Build publication type filter
    pt_filters = []
    if study_types is None:
        study_types = ["rct", "review", "meta"]
    type_map = {
        "rct": '"randomized controlled trial"[pt]',
        "review": '"systematic review"[pt]',
        "meta": '"meta-analysis"[pt]',
        "trial": '"clinical trial"[pt]',
        "guideline": '"practice guideline"[pt] OR "guideline"[pt]',
    }
    for st in study_types:
        if st in type_map:
            pt_filters.append(type_map[st])

    if pt_filters:
        term = f"({query}) AND ({' OR '.join(pt_filters)})"
    else:
        term = query

    # Date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    params = {
        "db": "pubmed",
        "term": term,
        "datetype": "pdat",
        "mindate": start_date.strftime("%Y/%m/%d"),
        "maxdate": end_date.strftime("%Y/%m/%d"),
        "retmode": "json",
        "retmax": max_results,
        "sort": "relevance",
    }

    url = f"{BASE_URL}/esearch.fcgi"
    headers = {"User-Agent": USER_AGENT}

    try:
        response = requests.get(url, params=params, headers=headers, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        pmids = data.get("esearchresult", {}).get("idlist", [])
        return pmids
    except requests.RequestException as e:
        print(f"[pubmed] Search failed: {e}")
        return []


def fetch_summaries(pmids):
    """
    Fetch metadata for a list of PMIDs via ESummary.

    Returns:
        Dict mapping PMID -> { title, authors, journal, pubdate, doi, pubtypes }
    """
    if not pmids:
        return {}

    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "json",
    }

    url = f"{BASE_URL}/esummary.fcgi"
    headers = {"User-Agent": USER_AGENT}

    try:
        response = requests.get(url, params=params, headers=headers, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        result = data.get("result", {})

        summaries = {}
        for pmid in pmids:
            entry = result.get(pmid)
            if not entry:
                continue

            # Extract DOI from articleids
            doi = None
            for aid in entry.get("articleids", []):
                if aid.get("idtype") == "doi":
                    doi = aid.get("value")
                    break

            # Authors
            authors = entry.get("authors", [])
            author_names = [a.get("name", "") for a in authors[:3]]
            if len(authors) > 3:
                author_names.append("et al.")

            summaries[pmid] = {
                "pmid": pmid,
                "title": entry.get("title", "").rstrip("."),
                "authors": author_names,
                "journal": entry.get("fulljournalname") or entry.get("source", ""),
                "pubdate": entry.get("pubdate", ""),
                "doi": doi,
                "pubtypes": entry.get("pubtype", []),
                "source": "pubmed",
            }
        return summaries
    except requests.RequestException as e:
        print(f"[pubmed] Summary fetch failed: {e}")
        return {}


def search_and_fetch(query, days=30, max_results=15, study_types=None):
    """One-shot: search + fetch summaries."""
    pmids = search_recent(query, days=days, max_results=max_results, study_types=study_types)
    if not pmids:
        return []
    summaries = fetch_summaries(pmids)
    # Return in original order
    return [summaries[pmid] for pmid in pmids if pmid in summaries]
