"""
OpenAlex Service
================
Enrichment via PMID. Returns citation counts, FWCI (Field-Weighted Citation
Impact), open access info, and reconstructed abstract.

Docs: https://docs.openalex.org/
Rate limit: ~10 req/s polite pool. $1/day free = ~1000 searches.
"""

import requests

BASE_URL = "https://api.openalex.org/works"
MAILTO = "pat@outoftheb-ox.de"  # Polite pool
DEFAULT_TIMEOUT = 15


def reconstruct_abstract(inverted_index):
    """OpenAlex returns abstracts as inverted index. Reconstruct to string."""
    if not inverted_index:
        return ""
    positions = {}
    for word, indices in inverted_index.items():
        for idx in indices:
            positions[idx] = word
    return " ".join(positions[i] for i in sorted(positions.keys()))


def enrich_by_pmids(pmids):
    """
    Batch fetch OpenAlex data for a list of PMIDs.

    Returns:
        Dict mapping PMID -> enrichment data.
    """
    if not pmids:
        return {}

    # OpenAlex accepts filter with multiple IDs (pipe-separated)
    # Correct format: filter=pmid:12345|67890
    pmid_filter = "|".join(pmids)

    params = {
        "filter": f"pmid:{pmid_filter}",
        "per_page": min(len(pmids), 50),
        "select": "id,doi,ids,title,abstract_inverted_index,cited_by_count,fwci,citation_normalized_percentile,open_access,primary_location,publication_date",
        "mailto": MAILTO,
    }

    try:
        response = requests.get(BASE_URL, params=params, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        data = response.json()

        results = {}
        for work in data.get("results", []):
            # Extract PMID from ids
            pmid = None
            ids = work.get("ids", {})
            if "pmid" in ids:
                # Format: "https://pubmed.ncbi.nlm.nih.gov/12345"
                pmid = ids["pmid"].rstrip("/").split("/")[-1]

            if not pmid:
                continue

            oa = work.get("open_access") or {}

            results[pmid] = {
                "openalex_id": work.get("id"),
                "abstract": reconstruct_abstract(work.get("abstract_inverted_index")),
                "cited_by_count": work.get("cited_by_count", 0),
                "fwci": work.get("fwci"),  # Field-Weighted Citation Impact
                "citation_percentile": (work.get("citation_normalized_percentile") or {}).get("value"),
                "is_oa": oa.get("is_oa", False),
                "oa_status": oa.get("oa_status"),  # gold/green/hybrid/bronze/closed
                "oa_url": oa.get("oa_url"),
            }
        return results
    except requests.RequestException as e:
        print(f"[openalex] Enrichment failed: {e}")
        return {}
