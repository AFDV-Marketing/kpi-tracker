"""AFDV KPI Tracker — Staff Performance Management Dashboard."""
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from database import get_db, init_db, seed_data

app = FastAPI(title="AFDV KPI Tracker")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@app.on_event("startup")
def startup():
    init_db()
    seed_data()


def get_week_range(d=None):
    """Return Monday-Sunday range for the week containing date d."""
    if d is None:
        d = date.today()
    monday = d - timedelta(days=d.weekday())
    sunday = monday + timedelta(days=6)
    return monday.isoformat(), sunday.isoformat()


def get_month_range(d=None):
    if d is None:
        d = date.today()
    first = d.replace(day=1)
    if d.month == 12:
        last = d.replace(year=d.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        last = d.replace(month=d.month + 1, day=1) - timedelta(days=1)
    return first.isoformat(), last.isoformat()


# ── Dashboard ──────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    db = get_db()
    staff = db.execute("SELECT * FROM staff WHERE active=1").fetchall()
    wig = db.execute("SELECT * FROM wigs WHERE status='active' ORDER BY id DESC LIMIT 1").fetchone()

    week_start, week_end = get_week_range()
    month_start, month_end = get_month_range()

    scorecards = []
    for s in staff:
        kpis = db.execute("SELECT * FROM kpis WHERE staff_id=? AND active=1 ORDER BY sort_order", (s["id"],)).fetchall()

        scored_kpis = []
        for kpi in kpis:
            period = (week_start, week_end) if kpi["frequency"] == "weekly" else (month_start, month_end)
            score = db.execute(
                "SELECT * FROM scores WHERE kpi_id=? AND period_start=? ORDER BY logged_at DESC LIMIT 1",
                (kpi["id"], period[0])
            ).fetchone()
            scored_kpis.append({"kpi": kpi, "score": score})

        goals = db.execute("SELECT * FROM goals WHERE staff_id=? ORDER BY target_date", (s["id"],)).fetchall()

        total = len(scored_kpis)
        greens = sum(1 for sk in scored_kpis if sk["score"] and sk["score"]["score"] == "green")
        yellows = sum(1 for sk in scored_kpis if sk["score"] and sk["score"]["score"] == "yellow")
        reds = sum(1 for sk in scored_kpis if sk["score"] and sk["score"]["score"] == "red")
        unscored = total - greens - yellows - reds

        scorecards.append({
            "staff": s,
            "kpis": scored_kpis,
            "goals": goals,
            "summary": {"total": total, "green": greens, "yellow": yellows, "red": reds, "unscored": unscored},
        })

    recent_reviews = db.execute("SELECT r.*, s.name as staff_name FROM reviews r JOIN staff s ON r.staff_id=s.id ORDER BY r.created_at DESC LIMIT 5").fetchall()

    db.close()
    return templates.TemplateResponse(request, "dashboard.html", {
        "scorecards": scorecards,
        "wig": wig,
        "week_start": week_start,
        "week_end": week_end,
        "month_label": date.today().strftime("%B %Y"),
        "recent_reviews": recent_reviews,
    })


# ── Scorecard Detail ───────────────────────────────────────
@app.get("/scorecard/{staff_id}", response_class=HTMLResponse)
async def scorecard(request: Request, staff_id: int):
    db = get_db()
    staff = db.execute("SELECT * FROM staff WHERE id=?", (staff_id,)).fetchone()
    kpis = db.execute("SELECT * FROM kpis WHERE staff_id=? AND active=1 ORDER BY sort_order", (staff_id,)).fetchall()
    goals = db.execute("SELECT * FROM goals WHERE staff_id=? ORDER BY target_date", (staff_id,)).fetchall()

    week_start, week_end = get_week_range()
    month_start, month_end = get_month_range()

    scored_kpis = []
    for kpi in kpis:
        period = (week_start, week_end) if kpi["frequency"] == "weekly" else (month_start, month_end)
        score = db.execute(
            "SELECT * FROM scores WHERE kpi_id=? AND period_start=? ORDER BY logged_at DESC LIMIT 1",
            (kpi["id"], period[0])
        ).fetchone()

        # History (last 8 periods)
        history = db.execute(
            "SELECT * FROM scores WHERE kpi_id=? ORDER BY period_start DESC LIMIT 8",
            (kpi["id"],)
        ).fetchall()

        scored_kpis.append({"kpi": kpi, "score": score, "history": list(reversed(history))})

    reviews = db.execute("SELECT * FROM reviews WHERE staff_id=? ORDER BY created_at DESC LIMIT 10", (staff_id,)).fetchall()

    db.close()
    return templates.TemplateResponse(request, "scorecard.html", {
        "staff": staff,
        "kpis": scored_kpis,
        "goals": goals,
        "reviews": reviews,
        "week_start": week_start,
        "week_end": week_end,
        "month_label": date.today().strftime("%B %Y"),
    })


# ── Log Scores ─────────────────────────────────────────────
@app.get("/log/{staff_id}", response_class=HTMLResponse)
async def log_form(request: Request, staff_id: int, period: str = "weekly"):
    db = get_db()
    staff = db.execute("SELECT * FROM staff WHERE id=?", (staff_id,)).fetchone()

    if period == "weekly":
        kpis = db.execute("SELECT * FROM kpis WHERE staff_id=? AND frequency='weekly' AND active=1 ORDER BY sort_order", (staff_id,)).fetchall()
        period_start, period_end = get_week_range()
    else:
        kpis = db.execute("SELECT * FROM kpis WHERE staff_id=? AND frequency='monthly' AND active=1 ORDER BY sort_order", (staff_id,)).fetchall()
        period_start, period_end = get_month_range()

    existing = {}
    for kpi in kpis:
        score = db.execute("SELECT * FROM scores WHERE kpi_id=? AND period_start=?", (kpi["id"], period_start)).fetchone()
        if score:
            existing[kpi["id"]] = score

    db.close()
    return templates.TemplateResponse(request, "log_scores.html", {
        "staff": staff,
        "kpis": kpis,
        "existing": existing,
        "period": period,
        "period_start": period_start,
        "period_end": period_end,
    })


@app.post("/log/{staff_id}")
async def log_scores(request: Request, staff_id: int):
    form = await request.form()
    db = get_db()

    period_start = form.get("period_start")
    period_end = form.get("period_end")

    for key, value in form.items():
        if key.startswith("score_"):
            kpi_id = int(key.replace("score_", ""))
            score = value
            notes = form.get(f"notes_{kpi_id}", "")
            val = form.get(f"value_{kpi_id}", "")

            db.execute("""
                INSERT INTO scores (kpi_id, staff_id, period_start, period_end, score, value, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(kpi_id, period_start) DO UPDATE SET
                    score=excluded.score, value=excluded.value, notes=excluded.notes, logged_at=datetime('now')
            """, (kpi_id, staff_id, period_start, period_end, score, val, notes))

    db.commit()
    db.close()
    return RedirectResponse(f"/scorecard/{staff_id}", status_code=303)


# ── Goals ──────────────────────────────────────────────────
@app.post("/goals/{goal_id}/update")
async def update_goal(request: Request, goal_id: int):
    form = await request.form()
    db = get_db()
    goal = db.execute("SELECT * FROM goals WHERE id=?", (goal_id,)).fetchone()

    status = form.get("status", goal["status"])
    progress = int(form.get("progress", goal["progress"]))
    outcome = form.get("outcome", goal["outcome"] or "")

    db.execute("UPDATE goals SET status=?, progress=?, outcome=?, updated_at=datetime('now') WHERE id=?",
               (status, progress, outcome, goal_id))
    db.commit()

    staff_id = goal["staff_id"]
    db.close()
    return RedirectResponse(f"/scorecard/{staff_id}", status_code=303)


# ── Reviews ────────────────────────────────────────────────
@app.get("/review/{staff_id}/new", response_class=HTMLResponse)
async def new_review(request: Request, staff_id: int, review_type: str = "weekly"):
    db = get_db()
    staff = db.execute("SELECT * FROM staff WHERE id=?", (staff_id,)).fetchone()
    db.close()

    if review_type == "weekly":
        period_label = f"Week of {get_week_range()[0]}"
    elif review_type == "monthly":
        period_label = date.today().strftime("%B %Y")
    else:
        q = (date.today().month - 1) // 3 + 1
        period_label = f"Q{q} {date.today().year}"

    return templates.TemplateResponse(request, "review_form.html", {
        "staff": staff,
        "review_type": review_type,
        "period_label": period_label,
    })


@app.post("/review/{staff_id}")
async def save_review(request: Request, staff_id: int):
    form = await request.form()
    db = get_db()

    db.execute("""
        INSERT INTO reviews (staff_id, review_type, period_label, summary, strengths, concerns, action_items, overall_grade)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (staff_id, form.get("review_type"), form.get("period_label"),
          form.get("summary"), form.get("strengths"), form.get("concerns"),
          form.get("action_items"), form.get("overall_grade")))

    db.commit()
    db.close()
    return RedirectResponse(f"/scorecard/{staff_id}", status_code=303)


# ── API for gateway integration ────────────────────────────
@app.get("/api/scorecards")
async def api_scorecards():
    db = get_db()
    staff = db.execute("SELECT * FROM staff WHERE active=1").fetchall()
    week_start, _ = get_week_range()
    month_start, _ = get_month_range()

    result = []
    for s in staff:
        kpis = db.execute("SELECT * FROM kpis WHERE staff_id=? AND active=1", (s["id"],)).fetchall()
        scores_out = []
        for kpi in kpis:
            period = week_start if kpi["frequency"] == "weekly" else month_start
            score = db.execute("SELECT score, value, notes FROM scores WHERE kpi_id=? AND period_start=?", (kpi["id"], period)).fetchone()
            scores_out.append({
                "kpi": kpi["name"],
                "category": kpi["category"],
                "score": dict(score) if score else None,
            })
        result.append({"staff": dict(s), "scores": scores_out})

    db.close()
    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8300)
