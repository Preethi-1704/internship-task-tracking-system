import hashlib, hmac, secrets, re, sqlite3, shutil
from datetime import date, timedelta, datetime
from pathlib import Path
from database.connection import connect
from config.settings import DB, WINDOW


def hash_password(p):
    s = secrets.token_hex(16)
    d = hashlib.pbkdf2_hmac("sha256", p.encode(), s.encode(), 310000).hex()
    return f"pbkdf2${s}${d}"


def verify_password(p, h):
    try:
        _, s, d = h.split("$")
        return hmac.compare_digest(
            hashlib.pbkdf2_hmac("sha256", p.encode(), s.encode(), 310000).hex(),
            d
        )
    except Exception:
        return False


def audit(user, op, typ="", rid="", outcome="success", details=""):
    with connect() as c:
        c.execute(
            """INSERT INTO audit_logs
               (username, operation, entity_type, entity_id, outcome, details)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user, op, typ, str(rid), outcome, details[:300])
        )


def authenticate(u, p):
    with connect() as c:
        r = c.execute(
            "SELECT * FROM users WHERE username=? AND active=1", (u,)
        ).fetchone()

    if r and verify_password(p, r["password_hash"]):
        audit(u, "login", "user", u)
        return {k: r[k] for k in ("username", "role", "intern_id", "team_id")}

    audit(u or "unknown", "login_failed", "user", u, "failure")
    return None


def allowed(user, team_id=None, intern_id=None):
    if user["role"] == "admin":
        return True
    if user["role"] == "team_lead":
        return (
            (team_id is None or team_id == user["team_id"])
            and (intern_id is None or intern_in_team(intern_id, user["team_id"]))
        )
    return intern_id is None or intern_id == user["intern_id"]


def intern_in_team(i, t):
    with connect() as c:
        r = c.execute(
            "SELECT 1 FROM interns WHERE intern_id=? AND team_id=?", (i, t)
        ).fetchone()
    return bool(r)


def save_intern(d, actor):
    if not d["intern_id"].strip() or not d["full_name"].strip():
        raise ValueError("Intern ID and name required")
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", d["email"]):
        raise ValueError("Invalid email")
    if d["end_date"] < d["start_date"]:
        raise ValueError("End date must not precede start date")

    with connect() as c:
        if not c.execute(
            "SELECT 1 FROM teams WHERE team_id=? AND active=1", (d["team_id"],)
        ).fetchone():
            raise ValueError("Invalid or inactive team")

        c.execute(
            """INSERT INTO interns
               (intern_id, full_name, email, phone, team_id, start_date, end_date)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(intern_id) DO UPDATE SET
               full_name=excluded.full_name, email=excluded.email,
               phone=excluded.phone, team_id=excluded.team_id,
               start_date=excluded.start_date, end_date=excluded.end_date,
               active=1""",
            (
                d["intern_id"].upper(), d["full_name"], d["email"].lower(),
                d.get("phone", ""), d["team_id"], d["start_date"], d["end_date"]
            )
        )
    audit(actor, "save_intern", "intern", d["intern_id"])


def tasks(user):
    q = "SELECT t.*, i.full_name FROM tasks t JOIN interns i ON i.intern_id=t.intern_id"
    args = []
    if user["role"] == "team_lead":
        q += " WHERE t.team_id=?"
        args = [user["team_id"]]
    elif user["role"] == "intern":
        q += " WHERE t.intern_id=?"
        args = [user["intern_id"]]

    with connect() as c:
        return [dict(x) for x in c.execute(q + " ORDER BY due_date", args)]


def save_task(d, actor):
    if d["due_date"] < d["assigned_date"]:
        raise ValueError("Due date must be on or after assignment date")
    if d.get("submission_date") and d["submission_date"] < d["assigned_date"]:
        raise ValueError("Submission cannot precede assignment")
    if d["status"] not in ["Not Started", "In Progress", "Submitted", "Reviewed"]:
        raise ValueError("Invalid status")
    if d["assessment_status"] == "Passed" and d["status"] != "Reviewed":
        raise ValueError("Passed tasks must be reviewed")
    if d["status"] == "Reviewed" and d["assessment_status"] == "Pending":
        raise ValueError("Reviewed tasks need an assessment result")

    with connect() as c:
        i = c.execute(
            "SELECT team_id, active FROM interns WHERE intern_id=?", (d["intern_id"],)
        ).fetchone()
        if not i or not i["active"]:
            raise ValueError("Invalid or inactive intern")
        if i["team_id"] != d["team_id"]:
            raise ValueError("Task team must match intern team")

        c.execute(
            """INSERT INTO tasks
               (task_id, title, description, intern_id, team_id, assigned_date,
                due_date, submission_date, status, assessment_status, priority,
                reviewer_comments, assigned_by, reviewed_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(task_id) DO UPDATE SET
               title=excluded.title, description=excluded.description,
               intern_id=excluded.intern_id, team_id=excluded.team_id,
               assigned_date=excluded.assigned_date, due_date=excluded.due_date,
               submission_date=excluded.submission_date, status=excluded.status,
               assessment_status=excluded.assessment_status, priority=excluded.priority,
               reviewer_comments=excluded.reviewer_comments,
               reviewed_by=excluded.reviewed_by""",
            (
                d["task_id"], d["title"], d.get("description", ""), d["intern_id"],
                d["team_id"], d["assigned_date"], d["due_date"],
                d.get("submission_date"), d["status"], d["assessment_status"],
                d["priority"], d.get("reviewer_comments", ""), actor,
                d.get("reviewed_by")
            )
        )
        if d["status"] == "Reviewed":
            c.execute(
                """INSERT INTO reviews
                   (task_id, reviewer, assessment_status, comments)
                   VALUES (?, ?, ?, ?)""",
                (
                    d["task_id"], d.get("reviewed_by") or actor,
                    d["assessment_status"], d.get("reviewer_comments", "")
                )
            )
    audit(actor, "save_task", "task", d["task_id"])


def deadlines(user):
    today = date.today()
    out = {
        "overdue": [], "due_today": [], "upcoming": [],
        "review_pending": [], "revision": []
    }

    for t in tasks(user):
        due = date.fromisoformat(t["due_date"])
        submitted = bool(t["submission_date"]) or t["status"] == "Reviewed"
        t["days_overdue"] = max(0, (today - due).days) if due < today and not submitted else 0

        if due < today and not submitted:
            out["overdue"].append(t)
        elif due == today and not submitted:
            out["due_today"].append(t)
        elif today < due <= today + timedelta(days=WINDOW) and not submitted:
            out["upcoming"].append(t)

        if t["status"] == "Submitted" and t["assessment_status"] == "Pending":
            out["review_pending"].append(t)
        if t["assessment_status"] in ("Need Revision", "Needs Revision"):
            out["revision"].append(t)

    return out


def seed():
    with connect() as c:
        if c.execute("SELECT COUNT(*) FROM interns").fetchone()[0]:
            return

        for tid, name, lead in [
            ("TEAM-A", "Automation", "lead_a"),
            ("TEAM-D", "Data Analytics", "lead_d"),
            ("TEAM-W", "Web Operations", "lead_w"),
            ("TEAM-Q", "Quality Assurance", "lead_q")
        ]:
            c.execute("INSERT INTO teams VALUES(?,?,?,1)", (tid, name, lead))
            c.execute(
                "INSERT INTO users VALUES(?,?,?,?,?,1)",
                (lead, hash_password("DemoLead!234"), "team_lead", None, tid)
            )

        for i in range(1, 21):
            tid = ["TEAM-A", "TEAM-D", "TEAM-W", "TEAM-Q"][(i - 1) % 4]
            iid = f"DIT-I{i:03d}"
            c.execute(
                """INSERT INTO interns
                   (intern_id, full_name, email, team_id, start_date, end_date, demo_record)
                   VALUES (?, ?, ?, ?, ?, ?, 1)""",
                (
                    iid, f"Intern {i:02d}", f"intern{i:02d}@example.test", tid,
                    (date.today() - timedelta(days=20)).isoformat(),
                    (date.today() + timedelta(days=30)).isoformat()
                )
            )
            c.execute(
                "INSERT INTO users VALUES(?,?,?,?,?,1)",
                (iid.lower(), hash_password("DemoIntern!234"), "intern", iid, tid)
            )

        for i in range(1, 49):
            iid = f"DIT-I{((i - 1) % 20) + 1:03d}"
            tid = ["TEAM-A", "TEAM-D", "TEAM-W", "TEAM-Q"][((i - 1) % 20) % 4]
            status = ["Not Started", "In Progress", "Submitted", "Reviewed"][(i - 1) % 4]
            due = (
                date.today() + timedelta(days=[-4, -1, 0, 1, 2, 5][i % 6])
            ).isoformat()
            sub = (
                (date.today() - timedelta(days=1)).isoformat()
                if status in ("Submitted", "Reviewed") else None
            )
            assess = (
                "Passed" if i % 5 == 0
                else "Needs Revision" if i % 7 == 0
                else "Pending"
            ) if status == "Reviewed" else "Pending"

            c.execute(
                """INSERT INTO tasks
                   (task_id, title, description, intern_id, team_id, assigned_date,
                    due_date, submission_date, status, assessment_status, priority,
                    assigned_by, demo_record)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
                (
                    f"TASK-{i:03d}", f"Deliverable {i:02d}", "Synthetic demo task",
                    iid, tid, (date.today() - timedelta(days=10)).isoformat(),
                    due, sub, status, assess,
                    ["Low", "Medium", "High", "Critical"][i % 4], "admin"
                )
            )


def backup():
    p = DB.parent.parent / "backups" / f"backup_{datetime.now():%Y%m%d_%H%M%S}.db"
    p.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB) as a, sqlite3.connect(p) as b:
        a.backup(b)

    with sqlite3.connect(p) as c:
        if c.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("Backup integrity check failed")

    return p


def reset_workspace():
    """
    Permanently clear workspace data while preserving admin user accounts.
    Take a backup before calling this function.
    """
    db_path = str(DB)
    conn = sqlite3.connect(db_path)

    try:
        # Disable FK enforcement before beginning the transaction.
        conn.execute("PRAGMA foreign_keys = OFF")

        tables = [
            row[0]
            for row in conn.execute("""
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                  AND name NOT LIKE 'sqlite_%'
            """).fetchall()
        ]

        if "users" not in tables:
            raise RuntimeError("Database users table was not found.")

        conn.execute("BEGIN")

        for table in tables:
            if table == "users":
                continue
            safe_table = '"' + table.replace('"', '""') + '"'
            conn.execute(f"DELETE FROM {safe_table}")

        conn.execute("""
            DELETE FROM users
            WHERE role IS NULL OR role != 'admin'
        """)

        has_sequence = conn.execute("""
            SELECT 1 FROM sqlite_master
            WHERE type = 'table' AND name = 'sqlite_sequence'
        """).fetchone()

        if has_sequence:
            conn.execute("DELETE FROM sqlite_sequence")

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()