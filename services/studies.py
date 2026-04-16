"""
Studies Pipeline
================
Orchestrates PubMed + OpenAlex + Semantic Scholar + CrossRef to produce
a ranked list of studies. Two ranking modes:

- mode="new"     → recency bias + study type (Module 1: Studien-Update)
- mode="impact"  → heavy citation impact focus (Module 7: Evidenz-Check)
"""

import math

from . import pubmed, openalex, semantic_scholar, crossref


# Study type relevance weights (higher = more clinically useful)
STUDY_TYPE_WEIGHTS = {
    "Meta-Analysis": 5,
    "Systematic Review": 4,
    "Randomized Controlled Trial": 3,
    "Clinical Trial": 2,
    "Review": 1,
    "Journal Article": 0,
}


def rank_by_recency(study):
    """
    Module 1 style ranking: what's new AND good.
    Weighs study type heavily; citation metrics help but don't dominate
    (new papers haven't accumulated citations yet).
    """
    score = 0.0

    # Study type weight
    for ptype in study.get("pubtypes", []):
        score += STUDY_TYPE_WEIGHTS.get(ptype, 0)

    # Citation percentile (if available)
    percentile = study.get("citation_percentile")
    if percentile is not None:
        score += float(percentile) * 3

    # Raw citations (log-scaled)
    citations = study.get("cited_by_count", 0)
    if citations > 0:
        score += math.log(citations + 1) * 0.5

    if study.get("is_oa"):
        score += 0.3
    if study.get("tldr"):
        score += 0.2

    return score


def rank_by_impact(study):
    """
    Module 7 style ranking: established evidence.
    Citations and FWCI dominate; study type is secondary since we already
    filter for Reviews + Meta-Analyses at query time.
    """
    score = 0.0

    # FWCI (Field-Weighted Citation Impact) — strongest signal for actual impact
    fwci = study.get("fwci")
    if fwci is not None and fwci > 0:
        score += math.log(float(fwci) + 1) * 4  # strong weight

    # Citation percentile in field
    percentile = study.get("citation_percentile")
    if percentile is not None:
        score += float(percentile) * 6

    # Raw citations (log scaled, heavy)
    citations = study.get("cited_by_count", 0)
    if citations > 0:
        score += math.log(citations + 1) * 2

    # Influential citations (S2)
    inf = study.get("influential_citations", 0)
    if inf > 0:
        score += math.log(inf + 1) * 1.5

    # Study type — still prefer Meta-Analysis over Review
    for ptype in study.get("pubtypes", []):
        score += STUDY_TYPE_WEIGHTS.get(ptype, 0) * 0.3

    if study.get("is_oa"):
        score += 0.3
    if study.get("tldr"):
        score += 0.2

    return score


def compute_rank_score(study, mode="new"):
    return rank_by_impact(study) if mode == "impact" else rank_by_recency(study)


def best_study_type(pubtypes):
    """Pick the most specific/relevant pubtype label."""
    for preferred in ["Meta-Analysis", "Systematic Review", "Randomized Controlled Trial", "Clinical Trial"]:
        if preferred in pubtypes:
            return preferred
    if "Review" in pubtypes:
        return "Review"
    return pubtypes[0] if pubtypes else "Article"


def fetch_studies(query, days=30, max_results=15, top_n=5, study_types=None, mode="new"):
    """
    Full pipeline: search + enrich + rank.

    Args:
        mode: "new" (recency bias, for Studien-Update) or
              "impact" (citation focus, for Evidenz-Check)

    Returns:
        Dict with:
            'studies': list of enriched + ranked studies
            'meta': { total_found, sources_used, query_used, mode }
    """
    sources_used = []

    # Step 1: PubMed search + summaries
    pubmed_results = pubmed.search_and_fetch(
        query, days=days, max_results=max_results, study_types=study_types
    )
    if pubmed_results:
        sources_used.append("PubMed")

    if not pubmed_results:
        return {
            "studies": [],
            "meta": {
                "total_found": 0,
                "sources_used": [],
                "query_used": query,
                "error": "Keine Treffer bei PubMed. Versuche englische Suchbegriffe.",
            },
        }

    pmids = [s["pmid"] for s in pubmed_results]
    dois = [s["doi"] for s in pubmed_results if s.get("doi")]

    # Step 2: OpenAlex enrichment
    oa_data = openalex.enrich_by_pmids(pmids)
    if oa_data:
        sources_used.append("OpenAlex")

    # Step 3: Semantic Scholar tldr
    s2_data = semantic_scholar.enrich_by_dois(dois)
    if s2_data:
        sources_used.append("Semantic Scholar")

    # Step 4: Merge everything
    studies = []
    default_enrichment = {
        "abstract": "",
        "cited_by_count": 0,
        "fwci": None,
        "citation_percentile": None,
        "is_oa": False,
        "oa_status": None,
        "oa_url": None,
        "tldr": None,
        "influential_citations": 0,
    }
    for pm in pubmed_results:
        pmid = pm["pmid"]
        doi = (pm.get("doi") or "").lower()

        enriched = dict(default_enrichment)
        enriched.update(pm)
        enriched.update(oa_data.get(pmid, {}))

        if doi and doi in s2_data:
            s2 = s2_data[doi]
            enriched["tldr"] = s2.get("tldr")
            # Use S2 citation count if OpenAlex missing
            if not enriched.get("cited_by_count"):
                enriched["cited_by_count"] = s2.get("citations", 0)
            enriched["influential_citations"] = s2.get("influential", 0)
            if not enriched.get("oa_url"):
                enriched["oa_url"] = s2.get("oa_pdf_url")

        # Fallback: CrossRef if journal name is missing
        if not enriched.get("journal") and doi:
            cr = crossref.fetch_by_doi(doi)
            if cr:
                enriched["journal"] = cr.get("journal", "")
                if not sources_used or "CrossRef" not in sources_used:
                    sources_used.append("CrossRef")

        enriched["best_type"] = best_study_type(enriched.get("pubtypes", []))
        enriched["rank_score"] = compute_rank_score(enriched, mode=mode)

        # Build URLs
        enriched["pubmed_url"] = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        if doi:
            enriched["doi_url"] = f"https://doi.org/{doi}"

        studies.append(enriched)

    # Step 5: Rank + trim
    studies.sort(key=lambda s: s["rank_score"], reverse=True)
    top = studies[:top_n]

    return {
        "studies": top,
        "meta": {
            "total_found": len(pubmed_results),
            "returned": len(top),
            "sources_used": sources_used,
            "query_used": query,
            "days": days,
            "mode": mode,
        },
    }
