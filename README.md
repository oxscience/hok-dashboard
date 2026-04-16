# OX Briefing

Morning briefing dashboard for health professionals. Pulls from free academic APIs and RSS feeds, zero API keys required.

![OX Briefing Screenshot](docs/screenshot.png)

## What It Does

Single-column briefing with five modules, each pulling from public data sources:

| # | Module | What it covers | Sources |
|---|--------|----------------|---------|
| 1 | **Studies** | New RCTs, systematic reviews, meta-analyses for your specialty | PubMed + OpenAlex + Semantic Scholar |
| 2 | **Guidelines** | Practice guidelines from the past 90 days | PubMed (publication type filter) |
| 3 | **AI Tools** | Top AI launches from Show HN | Hacker News Algolia API |
| 4 | **Patient Topics** | Health news patients are reading | RSS: Spiegel Gesundheit, SZ Gesundheit |
| 5 | **Privacy Alerts** | GDPR news and security advisories | RSS: heise Security, Dr. Datenschutz |

Users set their medical specialty (e.g. physiotherapy, cardiology, sports medicine) and a time window. Each module pulls on demand via HTMX. Results are cached in SQLite. The UI is a briefing-style layout with a floating table of contents.

## Live Demo

**[briefing.outoftheb-ox.de](https://briefing.outoftheb-ox.de)**

## Tech Stack

- **Backend:** Flask 3 with Application Factory pattern
- **Frontend:** HTMX (no framework), dark mode
- **Database:** SQLite (WAL mode)
- **RSS:** feedparser
- **HTTP:** requests
- **Production:** Gunicorn

## Quick Start

```bash
git clone https://github.com/oxscience/hok-dashboard.git
cd hok-dashboard
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

Open [http://localhost:5020](http://localhost:5020).

## Data Sources

All APIs are free and require no authentication or API keys.

| Source | API | Used for | Docs |
|--------|-----|----------|------|
| PubMed | E-utilities (esearch + esummary) | Study search, guideline search | [ncbi.nlm.nih.gov](https://www.ncbi.nlm.nih.gov/books/NBK25497/) |
| OpenAlex | REST API | Citation counts, FWCI, open access status, abstracts | [docs.openalex.org](https://docs.openalex.org/) |
| Semantic Scholar | Graph API v1 (batch endpoint) | AI-generated TLDR, influential citation count | [api.semanticscholar.org](https://api.semanticscholar.org/graph/v1/) |
| Hacker News | Algolia Search API | AI tool launches (Show HN) | [hn.algolia.com/api](https://hn.algolia.com/api) |
| Spiegel, SZ | RSS/Atom feeds | Patient-facing health news | Standard RSS |
| heise, Dr. Datenschutz | RSS/Atom feeds | Privacy and security alerts | Standard RSS |

## Optional: LLM Integration

`services/llm.py` connects to a local Ollama instance (default model: `qwen3:8b`) via the OpenAI-compatible API. When available, it provides:

- Study summaries with clinical relevance
- Guideline change explanations
- Privacy alert relevance assessment
- Patient-friendly topic explanations

Not yet wired into the UI. The dashboard works fully without it.

```bash
# To enable (optional):
export OLLAMA_URL=http://localhost:11434
export OLLAMA_MODEL=qwen3:8b
```

## License

MIT

## By

[Out Of The Box Science](https://outoftheb-ox.de)
