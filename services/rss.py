"""
RSS Feed Service
================
Generischer Feed-Parser für deutsche Gesundheits-Quellen.
Nutzt feedparser (Pure Python, kein Auth nötig).

Unterstützt: AWMF, KBV, BfDI, heise, Ärzteblatt, Tagesschau, etc.
"""

import feedparser
import requests
from datetime import datetime
from time import mktime

DEFAULT_TIMEOUT = 15
USER_AGENT = "HoK-Dashboard/1.0 (contact: pat@outoftheb-ox.de)"


def _parse_date(entry):
    """Extract a datetime from a feedparser entry."""
    for field in ("published_parsed", "updated_parsed"):
        parsed = entry.get(field)
        if parsed:
            try:
                return datetime.fromtimestamp(mktime(parsed))
            except (TypeError, OverflowError, ValueError):
                continue
    # Fallback: raw string
    return entry.get("published") or entry.get("updated") or ""


def _timeago(dt):
    if not isinstance(dt, datetime):
        return str(dt) if dt else ""
    delta = datetime.now() - dt
    days = delta.days
    if days == 0:
        hours = delta.seconds // 3600
        if hours == 0:
            return "gerade eben"
        return f"vor {hours} Std"
    if days == 1:
        return "gestern"
    if days < 7:
        return f"vor {days} Tagen"
    if days < 30:
        weeks = days // 7
        return f"vor {weeks} Woche" if weeks == 1 else f"vor {weeks} Wochen"
    months = days // 30
    return f"vor {months} Mon"


def fetch_feed(url, limit=10, days_back=None):
    """
    Fetch + parse a single RSS/Atom feed.

    Args:
        url: Feed URL.
        limit: Max entries.
        days_back: Only include entries from last N days (None = all).

    Returns:
        List of dicts: { title, summary, url, source, published, timeago }
    """
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)
    except Exception as e:
        print(f"[rss] Failed to fetch {url}: {e}")
        return []

    cutoff = None
    if days_back:
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(days=days_back)

    feed_title = feed.feed.get("title", "")
    items = []

    for entry in feed.entries:
        dt = _parse_date(entry)

        if cutoff and isinstance(dt, datetime) and dt < cutoff:
            continue

        # Clean summary (strip HTML tags simply)
        raw_summary = entry.get("summary") or entry.get("description") or ""
        import re
        clean_summary = re.sub(r"<[^>]+>", "", raw_summary).strip()
        # Truncate
        if len(clean_summary) > 300:
            clean_summary = clean_summary[:297] + "..."

        items.append({
            "title": entry.get("title", "").strip(),
            "summary": clean_summary,
            "url": entry.get("link", ""),
            "source": feed_title,
            "published": dt.strftime("%d.%m.%Y") if isinstance(dt, datetime) else str(dt),
            "published_dt": dt if isinstance(dt, datetime) else None,
            "timeago": _timeago(dt),
        })

        if len(items) >= limit:
            break

    return items


def fetch_multi(feed_configs, limit_per_feed=5, total_limit=10, days_back=None):
    """
    Fetch multiple feeds, merge + sort by date.

    Args:
        feed_configs: List of { url, label } dicts.
        limit_per_feed: Max entries per feed.
        total_limit: Max entries total.
        days_back: Only recent N days.

    Returns:
        Dict with 'entries' and 'meta'.
    """
    all_items = []
    sources_used = []

    for config in feed_configs:
        url = config["url"]
        label = config.get("label", "")
        entries = fetch_feed(url, limit=limit_per_feed, days_back=days_back)
        if entries:
            sources_used.append(label or entries[0].get("source", url))
            for e in entries:
                e["feed_label"] = label
            all_items.extend(entries)

    # Sort by date (newest first)
    all_items.sort(
        key=lambda x: x["published_dt"] or datetime.min,
        reverse=True,
    )

    top = all_items[:total_limit]

    return {
        "entries": top,
        "meta": {
            "total_found": len(all_items),
            "returned": len(top),
            "sources_used": sources_used,
            "days": days_back,
        },
    }
