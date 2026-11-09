import json
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def db():
    path = Path(os.getenv("DATABASE_PATH", "learning.sqlite3"))
    conn = sqlite3.connect(path, timeout=8)
    conn.row_factory = sqlite3.Row
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def initialize():
    with db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                digest TEXT PRIMARY KEY, uid TEXT NOT NULL, role TEXT NOT NULL,
                class_id TEXT NOT NULL, name TEXT NOT NULL, expires INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS web_accounts (
                uid TEXT PRIMARY KEY, key_digest TEXT NOT NULL UNIQUE
            );
            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY, uid TEXT NOT NULL, class_id TEXT NOT NULL, name TEXT NOT NULL,
                request_id TEXT NOT NULL, answer TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'queued',
                attempts INTEGER NOT NULL DEFAULT 0, claim TEXT, lease_until INTEGER DEFAULT 0,
                draft TEXT, review TEXT, created INTEGER NOT NULL,
                UNIQUE(uid, request_id)
            );
            CREATE INDEX IF NOT EXISTS submission_class ON submissions(class_id, id);
            CREATE TABLE IF NOT EXISTS study_turns (
                id INTEGER PRIMARY KEY, uid TEXT NOT NULL, class_id TEXT NOT NULL,
                request_id TEXT NOT NULL, question TEXT NOT NULL, answer TEXT NOT NULL, source TEXT NOT NULL,
                UNIQUE(uid, class_id, request_id)
            );
            CREATE TABLE IF NOT EXISTS study_checks (
                id INTEGER PRIMARY KEY, uid TEXT NOT NULL, class_id TEXT NOT NULL,
                request_id TEXT NOT NULL, stage TEXT NOT NULL, choices TEXT NOT NULL, result TEXT NOT NULL,
                created INTEGER NOT NULL, UNIQUE(uid, class_id, request_id)
            );
            CREATE TABLE IF NOT EXISTS focus_sessions (
                id INTEGER PRIMARY KEY, uid TEXT NOT NULL, class_id TEXT NOT NULL,
                request_id TEXT NOT NULL, goal TEXT NOT NULL, minutes INTEGER NOT NULL,
                state TEXT NOT NULL, elapsed INTEGER NOT NULL DEFAULT 0, started INTEGER NOT NULL,
                UNIQUE(uid,class_id,request_id)
            );
            CREATE UNIQUE INDEX IF NOT EXISTS focus_open ON focus_sessions(uid,class_id)
                WHERE state IN ('running','paused');
            CREATE TABLE IF NOT EXISTS lessons (
                id INTEGER PRIMARY KEY, uid TEXT NOT NULL, class_id TEXT NOT NULL,
                request_id TEXT NOT NULL, inputs TEXT NOT NULL, prep TEXT NOT NULL, prep_source TEXT NOT NULL,
                plan TEXT NOT NULL DEFAULT '', plan_source TEXT NOT NULL DEFAULT '',
                revision INTEGER NOT NULL DEFAULT 1, UNIQUE(uid,class_id,request_id)
            );
        """)


def class_summary(class_id):
    with db() as conn:
        rows = conn.execute("""SELECT review FROM submissions WHERE class_id=? AND state='reviewed'""",
                            (class_id,)).fetchall()
    counts = {}
    for row in rows:
        review = json.loads(row["review"])
        if review["verdict"] == "incorrect":
            tag = review["tag"]
            counts[tag] = counts.get(tag, 0) + 1
    return {"reviewed": len(rows), "errors": [{"tag": k, "count": v} for k,v in
            sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))]}


def process_next(grade):
    now, claim = int(time.time()), uuid.uuid4().hex
    with db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("""
            SELECT * FROM submissions WHERE state='queued' OR
            (state='grading' AND lease_until < ?) ORDER BY id LIMIT 1
        """, (now,)).fetchone()
        if not row:
            return False
        conn.execute("""UPDATE submissions SET state='grading', attempts=attempts+1,
                     claim=?, lease_until=? WHERE id=?""", (claim, now+90, row["id"]))
    try:
        result = json.dumps(grade(row["answer"]), ensure_ascii=False)
        state = "draft"
    except Exception:
        # 超时和模型格式错误可重试；耗尽次数后允许教师手动批改。
        result = None
        state = "queued" if row["attempts"] < 2 else "failed"
    with db() as conn:
        conn.execute("""UPDATE submissions SET state=?, draft=?, claim=NULL, lease_until=0
                     WHERE id=? AND claim=?""", (state, result, row["id"], claim))
    return True
