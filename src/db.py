"""SQLite storage so you only see each job once and can track what you applied to."""
import json
import sqlite3
from datetime import datetime

from . import settings
from .models import Job

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    uid TEXT PRIMARY KEY,
    dedupe_key TEXT,
    source TEXT, title TEXT, company TEXT, location TEXT, url TEXT,
    description TEXT, posted_at TEXT, salary TEXT,
    score INTEGER, verdict TEXT, reason TEXT,
    matching_skills TEXT, missing_skills TEXT, resume_version TEXT,
    status TEXT DEFAULT 'new',          -- new | saved | applied | skipped | filtered
    found_at TEXT, notified INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_dedupe ON jobs(dedupe_key);
"""


def connect() -> sqlite3.Connection:
    settings.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(settings.DB_PATH)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def is_known(con, job: Job) -> bool:
    row = con.execute("SELECT 1 FROM jobs WHERE uid=? OR dedupe_key=?", (job.uid, job.dedupe_key)).fetchone()
    return row is not None


def save(con, job: Job, status: str = "new") -> None:
    con.execute(
        """INSERT OR IGNORE INTO jobs (uid, dedupe_key, source, title, company, location, url, description,
           posted_at, salary, score, verdict, reason, matching_skills, missing_skills, resume_version, found_at, status)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (job.uid, job.dedupe_key, job.source, job.title, job.company, job.location, job.url, job.description,
         job.posted_at, job.salary, job.score, job.verdict, job.reason, json.dumps(job.matching_skills),
         json.dumps(job.missing_skills), job.resume_version, datetime.now().isoformat(timespec="seconds"), status),
    )
    con.commit()


def set_status(con, uid: str, status: str) -> None:
    con.execute("UPDATE jobs SET status=? WHERE uid=?", (status, uid))
    con.commit()


def mark_notified(con, uids: list[str]) -> None:
    con.executemany("UPDATE jobs SET notified=1 WHERE uid=?", [(u,) for u in uids])
    con.commit()


def all_jobs(con) -> list[dict]:
    rows = con.execute("SELECT * FROM jobs WHERE status != 'filtered' ORDER BY score DESC, found_at DESC").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["matching_skills"] = json.loads(d["matching_skills"] or "[]")
        d["missing_skills"] = json.loads(d["missing_skills"] or "[]")
        out.append(d)
    return out


def delete_demo_jobs(con) -> int:
    n = con.execute("DELETE FROM jobs WHERE source='demo'").rowcount
    con.commit()
    return n


def filtered_jobs(con) -> list[dict]:
    return [dict(r) for r in con.execute(
        "SELECT title, company, location, reason, url FROM jobs WHERE status='filtered' ORDER BY found_at DESC")]
