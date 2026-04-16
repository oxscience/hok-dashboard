import sqlite3
from flask import g

DATABASE = "hok_dashboard.db"


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS profile (
            id INTEGER PRIMARY KEY,
            fachgebiet TEXT DEFAULT '',
            praxistyp TEXT DEFAULT '',
            teamgroesse TEXT DEFAULT '',
            zeitraum TEXT DEFAULT '30 Tage'
        );

        CREATE TABLE IF NOT EXISTS briefing_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_id INTEGER NOT NULL,
            module_name TEXT NOT NULL,
            prompt_text TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Cached briefing results (actual data pulled from APIs)
        CREATE TABLE IF NOT EXISTS briefing_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_id INTEGER NOT NULL,
            query TEXT NOT NULL,
            result_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_briefing_results_module
            ON briefing_results(module_id, created_at DESC);

        -- Seed default profile if empty
        INSERT OR IGNORE INTO profile (id, fachgebiet, praxistyp, teamgroesse, zeitraum)
        VALUES (1, '', '', '', '30 Tage');
    """)
    db.commit()
