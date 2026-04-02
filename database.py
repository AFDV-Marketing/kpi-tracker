"""KPI Tracker Database — SQLite backend for staff performance management."""
import sqlite3
from datetime import date, datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "kpi_tracker.db"


def get_db():
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    return db


def init_db():
    DB_PATH.parent.mkdir(exist_ok=True)
    db = get_db()

    db.executescript("""
    CREATE TABLE IF NOT EXISTS staff (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        role TEXT NOT NULL,
        email TEXT,
        rate REAL,
        start_date TEXT,
        active INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS kpis (
        id INTEGER PRIMARY KEY,
        staff_id INTEGER NOT NULL REFERENCES staff(id),
        name TEXT NOT NULL,
        description TEXT,
        category TEXT NOT NULL CHECK(category IN ('lead', 'lag')),
        frequency TEXT NOT NULL CHECK(frequency IN ('weekly', 'monthly', 'quarterly')),
        green_threshold TEXT,
        yellow_threshold TEXT,
        red_threshold TEXT,
        sort_order INTEGER DEFAULT 0,
        active INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS scores (
        id INTEGER PRIMARY KEY,
        kpi_id INTEGER NOT NULL REFERENCES kpis(id),
        staff_id INTEGER NOT NULL REFERENCES staff(id),
        period_start TEXT NOT NULL,
        period_end TEXT NOT NULL,
        score TEXT NOT NULL CHECK(score IN ('green', 'yellow', 'red', 'na')),
        value TEXT,
        notes TEXT,
        logged_at TEXT DEFAULT (datetime('now')),
        UNIQUE(kpi_id, period_start)
    );

    CREATE TABLE IF NOT EXISTS goals (
        id INTEGER PRIMARY KEY,
        staff_id INTEGER NOT NULL REFERENCES staff(id),
        title TEXT NOT NULL,
        description TEXT,
        target_date TEXT,
        status TEXT DEFAULT 'not_started' CHECK(status IN ('not_started', 'in_progress', 'completed', 'overdue', 'cancelled')),
        progress INTEGER DEFAULT 0,
        outcome TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY,
        staff_id INTEGER NOT NULL REFERENCES staff(id),
        review_type TEXT NOT NULL CHECK(review_type IN ('weekly', 'monthly', 'quarterly')),
        period_label TEXT NOT NULL,
        summary TEXT,
        strengths TEXT,
        concerns TEXT,
        action_items TEXT,
        overall_grade TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS wigs (
        id INTEGER PRIMARY KEY,
        title TEXT NOT NULL,
        description TEXT,
        metric_from TEXT,
        metric_to TEXT,
        target_date TEXT,
        status TEXT DEFAULT 'active',
        created_at TEXT DEFAULT (datetime('now'))
    );
    """)

    db.commit()
    db.close()


def seed_data():
    """Seed initial staff, KPIs, goals, and WIG from the Q2 scorecards."""
    db = get_db()

    if db.execute("SELECT COUNT(*) FROM staff").fetchone()[0] > 0:
        db.close()
        return

    # Staff
    db.execute("INSERT INTO staff (id, name, role, email, rate, start_date) VALUES (1, 'Jessie L.', 'Digital Marketing Specialist', 'jessie@my.afdvmarketing.com', 10.00, '2025-10-24')")
    db.execute("INSERT INTO staff (id, name, role, email, rate, start_date) VALUES (2, 'Mariam G.', 'Account Manager / Project Manager', 'mariam@my.afdvmarketing.com', 12.00, '2025-10-09')")

    # WIG
    db.execute("INSERT INTO wigs (title, description, metric_from, metric_to, target_date) VALUES ('Grow Recurring Revenue', 'From $4,000/mo to $6,000/mo recurring revenue', '$4,000/mo', '$6,000/mo', '2026-06-30')")

    # Jessie KPIs — Lead
    jessie_leads = [
        ("Content pieces delivered", "Social posts + blog articles shipped per week", "lead", "weekly", "3+/week", "2/week", "0-1/week", 1),
        ("On-time delivery", "% delivered by due date from tracking sheet", "lead", "weekly", "100%", "1 late", "2+ late", 2),
        ("Tracked hours with specific memos", "Upwork diary — task-level descriptions", "lead", "weekly", "All specific", "1-2 vague", "Catch-all returns", 3),
        ("CRM task updates", "Perfex CRM logins + task status changes", "lead", "weekly", "2+ logins/week", "1 login/week", "0 logins", 4),
    ]
    for name, desc, cat, freq, g, y, r, sort in jessie_leads:
        db.execute("INSERT INTO kpis (staff_id, name, description, category, frequency, green_threshold, yellow_threshold, red_threshold, sort_order) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)",
                   (name, desc, cat, freq, g, y, r, sort))

    # Jessie KPIs — Lag
    jessie_lags = [
        ("Social engagement rate", "FB/IG avg engagement from Business Manager", "lag", "monthly", "2%+ avg", "1-2%", "<1%", 5),
        ("Blog posts published", "WordPress + HD content tracker count", "lag", "monthly", "4/month", "2-3/month", "0-1/month", 6),
        ("Client satisfaction (HD)", "Sue feedback in Chat + monthly check-in", "lag", "monthly", "Positive", "Minor issue", "Complaint/escalation", 7),
    ]
    for name, desc, cat, freq, g, y, r, sort in jessie_lags:
        db.execute("INSERT INTO kpis (staff_id, name, description, category, frequency, green_threshold, yellow_threshold, red_threshold, sort_order) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)",
                   (name, desc, cat, freq, g, y, r, sort))

    # Mariam KPIs — Lead
    mariam_leads = [
        ("Client check-ins sent", "Emails to clients per week (Gmail delegation)", "lead", "weekly", "2+/week", "1/week", "0/week", 1),
        ("Delivery tracking updated", "Google Sheet last-modified frequency", "lead", "weekly", "2+/week", "1/week", "Stale", 2),
        ("LinkedIn outreach (RCIC)", "Connection requests + messages sent", "lead", "weekly", "5+/week", "2-4/week", "0-1/week", 3),
        ("CRM task management", "Perfex login frequency + task updates", "lead", "weekly", "3+ logins/week", "1-2/week", "0/week", 4),
    ]
    for name, desc, cat, freq, g, y, r, sort in mariam_leads:
        db.execute("INSERT INTO kpis (staff_id, name, description, category, frequency, green_threshold, yellow_threshold, red_threshold, sort_order) VALUES (2, ?, ?, ?, ?, ?, ?, ?, ?)",
                   (name, desc, cat, freq, g, y, r, sort))

    # Mariam KPIs — Lag
    mariam_lags = [
        ("Deliverables on-time rate", "Tracking sheet: delivered by due date", "lag", "monthly", "90%+", "75-89%", "<75%", 5),
        ("Client retention", "Active clients maintained (no churn)", "lag", "monthly", "0 lost", "1 at-risk", "Client lost", 6),
        ("Meetings held", "Google Calendar events with Meet links", "lag", "monthly", "3+/week avg", "2/week avg", "0-1/week avg", 7),
        ("New business pipeline", "LinkedIn responses + discovery calls booked", "lag", "monthly", "1+ lead/month", "Outreach, no leads", "No outreach", 8),
    ]
    for name, desc, cat, freq, g, y, r, sort in mariam_lags:
        db.execute("INSERT INTO kpis (staff_id, name, description, category, frequency, green_threshold, yellow_threshold, red_threshold, sort_order) VALUES (2, ?, ?, ?, ?, ?, ?, ?, ?)",
                   (name, desc, cat, freq, g, y, r, sort))

    # Jessie Goals
    jessie_goals = [
        ("Social media analytics certification", "Complete Meta Blueprint, HubSpot, or Google certification", "2026-06-30", "not_started", 0),
        ("HD content workflow documentation", "Create repeatable workflow doc for HD content (anyone could follow it)", "2026-05-15", "not_started", 0),
        ("AFDV Gateway proficiency", "Learn to use gateway for content scheduling/research — 10+ tool calls", "2026-05-31", "not_started", 0),
    ]
    for title, desc, target, status, progress in jessie_goals:
        db.execute("INSERT INTO goals (staff_id, title, description, target_date, status, progress) VALUES (1, ?, ?, ?, ?, ?)",
                   (title, desc, target, status, progress))

    # Mariam Goals
    mariam_goals = [
        ("PM Course (Coursera)", "Complete project management certification", "2026-06-30", "in_progress", 25),
        ("WordPress proficiency", "Build or edit 1 WordPress page independently", "2026-04-30", "in_progress", 40),
        ("Lead a discovery call", "Conduct call independently + send follow-up without Ali", "2026-06-30", "not_started", 0),
        ("AFDV Gateway proficiency", "20+ gateway tool calls logged in audit", "2026-05-31", "not_started", 0),
    ]
    for title, desc, target, status, progress in mariam_goals:
        db.execute("INSERT INTO goals (staff_id, title, description, target_date, status, progress) VALUES (2, ?, ?, ?, ?, ?)",
                   (title, desc, target, status, progress))

    db.commit()
    db.close()
