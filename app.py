"""
Head of Knowledge Dashboard
============================
5-Modul Briefing-Dashboard für Health Professionals.
Pullt Daten von freien APIs + RSS, interpretiert via Ollama/Qwen (wenn verfügbar).

Module:
  1. Studien-Update    — PubMed + OpenAlex + S2
  2. Leitlinien-Check  — Medizin-RSS (AWMF-nahe Quellen)
  3. KI-Tools          — Hacker News Algolia
  4. Patienten-Themen  — Gesundheits-News RSS
  5. Datenschutz-Alert — Security + Datenschutz RSS

Flask + HTMX + SQLite.
"""

import json
import os
from datetime import datetime

from flask import Flask, render_template, request, abort

from database import get_db, init_db, close_db
from services import studies, hackernews, rss, llm


# ── Config ──────────────────────────────────────────────

TOPIC_MAP = {
    "physiotherapie": "physiotherapy",
    "orthopädie": "orthopedics",
    "allgemeinmedizin": "general practice",
    "hausarztmedizin": "family medicine",
    "pädiatrie": "pediatrics",
    "kardiologie": "cardiology",
    "neurologie": "neurology",
    "ergotherapie": "occupational therapy",
    "sportmedizin": "sports medicine",
    "innere medizin": "internal medicine",
    "gynäkologie": "gynecology",
    "dermatologie": "dermatology",
}

DAYS_MAP = {"7 Tage": 7, "14 Tage": 14, "30 Tage": 30, "90 Tage": 90}

# RSS Feed-Konfigurationen pro Modul
FEEDS_PATIENTEN = [
    {"url": "https://www.spiegel.de/gesundheit/index.rss", "label": "Spiegel Gesundheit"},
    {"url": "https://rss.sueddeutsche.de/rss/Gesundheit", "label": "SZ Gesundheit"},
    {"url": "https://www.apotheke-adhoc.de/rss.xml", "label": "apotheke adhoc"},
]

FEEDS_DATENSCHUTZ = [
    {"url": "https://www.heise.de/security/rss/news-atom.xml", "label": "heise Security"},
    {"url": "https://www.dr-datenschutz.de/feed/", "label": "Dr. Datenschutz"},
]


def translate_query(fachgebiet):
    if not fachgebiet:
        return fachgebiet
    return TOPIC_MAP.get(fachgebiet.lower().strip(), fachgebiet)


def timeago(iso_str):
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(iso_str.replace("T", " ").split(".")[0])
    except (ValueError, AttributeError):
        return iso_str
    delta = datetime.utcnow() - dt
    seconds = int(delta.total_seconds())
    if seconds < 0:
        return "gerade eben"
    if seconds < 60:
        return "gerade eben"
    if seconds < 3600:
        return f"vor {seconds // 60} Min"
    if seconds < 86400:
        return f"vor {seconds // 3600} Std"
    days = seconds // 86400
    return f"vor {days} Tag" if days == 1 else f"vor {days} Tagen"


def get_latest_result(db, module_id):
    row = db.execute(
        """SELECT result_json, created_at FROM briefing_results
           WHERE module_id = ? ORDER BY created_at DESC LIMIT 1""",
        (module_id,),
    ).fetchone()
    if not row:
        return None
    try:
        data = json.loads(row["result_json"])
        data["_fetched_at"] = row["created_at"]
        data["_timeago"] = timeago(row["created_at"])
        return data
    except (json.JSONDecodeError, TypeError):
        return None


def load_modules_with_data(db):
    modules = get_all_modules()
    for m in modules:
        m["latest"] = get_latest_result(db, m["id"])
    return modules


# ── App Factory ──────────────────────────────────────────────

def create_app():
    app = Flask(__name__)
    app.secret_key = "hok-dashboard-dev-key"
    app.teardown_appcontext(close_db)

    with app.app_context():
        init_db()

    @app.context_processor
    def inject_globals():
        return {
            "now": datetime.now(),
            "llm_available": llm.is_available(),
        }

    # ── Routes ──────────────────────────────────────────────

    @app.route("/")
    def dashboard():
        db = get_db()
        profile = db.execute("SELECT * FROM profile WHERE id = 1").fetchone()
        modules = load_modules_with_data(db)
        return render_template("dashboard.html", profile=profile, modules=modules)

    @app.route("/profile", methods=["POST"])
    def update_profile():
        db = get_db()
        fachgebiet = request.form.get("fachgebiet", "").strip()
        praxistyp = request.form.get("praxistyp", "").strip()
        teamgroesse = request.form.get("teamgroesse", "").strip()
        zeitraum = request.form.get("zeitraum", "30 Tage")

        db.execute(
            """INSERT OR REPLACE INTO profile (id, fachgebiet, praxistyp, teamgroesse, zeitraum)
               VALUES (1, ?, ?, ?, ?)""",
            (fachgebiet, praxistyp, teamgroesse, zeitraum),
        )
        db.commit()

        profile = db.execute("SELECT * FROM profile WHERE id = 1").fetchone()
        modules = load_modules_with_data(db)
        return render_template("partials/briefing_body.html", profile=profile, modules=modules)

    @app.route("/pull/<int:module_id>")
    def pull_data(module_id):
        db = get_db()
        profile = db.execute("SELECT * FROM profile WHERE id = 1").fetchone()
        modules = get_all_modules()
        module = next((m for m in modules if m["id"] == module_id), None)

        if not module:
            abort(404)

        if not profile or not profile["fachgebiet"]:
            module["latest"] = None
            module["error"] = "Bitte zuerst dein Profil ausfüllen."
            return render_template("partials/briefing_section.html", module=module, profile=profile)

        days = DAYS_MAP.get(profile["zeitraum"], 30)
        query_en = translate_query(profile["fachgebiet"])

        result = None
        error = None

        try:
            if module_id == 1:
                # Studien-Update
                result = studies.fetch_studies(
                    query_en, days=days, max_results=15, top_n=5, mode="new"
                )
            elif module_id == 2:
                # Leitlinien-Check — PubMed Practice Guidelines
                result = studies.fetch_studies(
                    query_en,
                    days=max(days, 90),
                    max_results=20,
                    top_n=5,
                    study_types=["guideline"],
                    mode="new",
                )
            elif module_id == 5:
                # KI-Tools — Hacker News
                result = hackernews.fetch_ai_tools(
                    days=max(days, 60), min_points=10, limit=10
                )
            elif module_id == 6:
                # Patienten-Themen — News RSS
                result = rss.fetch_multi(
                    FEEDS_PATIENTEN, limit_per_feed=5, total_limit=8, days_back=days
                )
            elif module_id == 9:
                # Datenschutz-Alert — Security RSS
                result = rss.fetch_multi(
                    FEEDS_DATENSCHUTZ, limit_per_feed=5, total_limit=8, days_back=days
                )
            else:
                error = "Modul nicht konfiguriert"
        except Exception as e:
            error = f"Fehler: {e}"

        if error:
            module["error"] = error
            return render_template("partials/briefing_section.html", module=module, profile=profile)

        # Cache
        db.execute(
            "INSERT INTO briefing_results (module_id, query, result_json) VALUES (?, ?, ?)",
            (module_id, query_en, json.dumps(result, ensure_ascii=False, default=str)),
        )
        db.commit()

        module["latest"] = get_latest_result(db, module_id)
        return render_template("partials/briefing_section.html", module=module, profile=profile)

    @app.route("/view/<int:module_id>")
    def view_detail(module_id):
        db = get_db()
        profile = db.execute("SELECT * FROM profile WHERE id = 1").fetchone()
        modules = get_all_modules()
        module = next((m for m in modules if m["id"] == module_id), None)
        if not module:
            abort(404)
        latest = get_latest_result(db, module_id)
        return render_template(
            "detail.html", module=module, profile=profile, result=latest,
        )

    return app


# ── Die 5 Module ──────────────────────────────────────────

def get_all_modules():
    return [
        {
            "id": 1,
            "name": "Studien-Update",
            "icon": "📑",
            "category": "Forschung",
            "cadence": "Wöchentlich",
            "accent": "indigo",
            "description": "Neue RCTs, Reviews & Meta-Analysen zum Fachgebiet.",
            "data_type": "studies",
            "data_sources": ["PubMed", "OpenAlex", "Semantic Scholar"],
            "layout": "hero",
        },
        {
            "id": 2,
            "name": "Leitlinien-Check",
            "icon": "📋",
            "category": "Compliance",
            "cadence": "Quartalsweise",
            "accent": "blue",
            "description": "Practice Guidelines der letzten 90 Tage zum Fachgebiet.",
            "data_type": "studies",
            "data_sources": ["PubMed", "OpenAlex", "Semantic Scholar"],
        },
        {
            "id": 5,
            "name": "KI-Tools",
            "icon": "🤖",
            "category": "Technologie",
            "cadence": "Alle 2 Wochen",
            "accent": "orange",
            "description": "Top-AI-Launches von Show HN.",
            "data_type": "tools",
            "data_sources": ["Hacker News"],
        },
        {
            "id": 6,
            "name": "Patienten-Themen",
            "icon": "💬",
            "category": "Kommunikation",
            "cadence": "Wöchentlich",
            "accent": "green",
            "description": "Gesundheitsthemen aus den Medien.",
            "data_type": "feed",
            "data_sources": ["Spiegel", "SZ", "Zeit"],
        },
        {
            "id": 9,
            "name": "Datenschutz-Alert",
            "icon": "🔒",
            "category": "Compliance",
            "cadence": "Monatlich",
            "accent": "red",
            "description": "DSGVO-News und Security-Meldungen.",
            "data_type": "feed",
            "data_sources": ["heise Security", "Dr. Datenschutz"],
        },
    ]


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, port=5020)
