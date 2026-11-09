import json
import os
import secrets
import sqlite3
import threading
import time
from contextlib import asynccontextmanager
from typing import Literal
from urllib.parse import urlencode
from urllib.request import urlopen

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .grading import QUESTION, grade
from .access import User, digest, require
from .members import roster
from .learning import router as learning_router
from .lessons import router as lesson_router
from .store import class_summary, db, initialize, process_next


def run_worker(stop):
    while not stop.is_set():
        try:
            busy = process_next(grade)
        except sqlite3.OperationalError:
            busy = False
        stop.wait(0.05 if busy else 0.5)


@asynccontextmanager
async def lifespan(app):
    initialize()
    stop = threading.Event()
    worker = threading.Thread(target=run_worker, args=(stop,), daemon=True)
    worker.start()
    try:
        yield
    finally:
        stop.set()
        worker.join(timeout=2)


app = FastAPI(title="教学智能体平台", lifespan=lifespan)
web_origins = [url.strip().rstrip("/") for url in os.getenv("WEB_ORIGINS", "").split(",") if url.strip()]
if "*" in web_origins:
    raise ValueError("WEB_ORIGINS 需要填写具体网页来源")
if web_origins:
    app.add_middleware(CORSMiddleware, allow_origins=web_origins,
                       allow_methods=["GET", "POST"], allow_headers=["Authorization", "Content-Type"])
app.include_router(learning_router)
app.include_router(lesson_router)
Role = Literal["student", "teacher"]


class DemoLogin(BaseModel):
    role: Role


class WeChatLogin(BaseModel):
    code: str = Field(min_length=1, max_length=256)


class WebLogin(BaseModel):
    access_key: str = Field(min_length=1, max_length=256)


class Submission(BaseModel):
    request_id: str = Field(min_length=8, max_length=100)
    answer: str = Field(min_length=1, max_length=2000)


class Review(BaseModel):
    verdict: Literal["correct", "incorrect"]
    feedback: str = Field(min_length=1, max_length=1000)
    tag: str = Field(default="", max_length=80)


def save_session(conn, uid, role, class_id, name):
    token = secrets.token_urlsafe(32)
    conn.execute("DELETE FROM sessions WHERE expires<=?", (int(time.time()),))
    conn.execute("INSERT INTO sessions VALUES (?,?,?,?,?,?)",
                 (digest(token), uid, role, class_id, name, int(time.time())+86400))
    return {"token": token, "role": role, "name": name, "class_id": class_id}


def issue(uid, role, class_id, name):
    with db() as conn:
        return save_session(conn, uid, role, class_id, name)


@app.get("/api/login/options")
def login_options():
    return {"demo": os.getenv("DEMO_MODE") == "1"}


@app.post("/api/login/web")
def web_login(data: WebLogin):
    if os.getenv("DEMO_MODE") == "1":
        raise HTTPException(403, "演示服务不接受正式教师账号")
    with db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        account = conn.execute("SELECT uid FROM web_accounts WHERE key_digest=?",
                              (digest(data.access_key.strip()),)).fetchone()
        if not account:
            raise HTTPException(401, "登录码无效")
        member = next((m for m in roster().values() if m["uid"] == account["uid"]), None)
        if not member:
            raise HTTPException(403, "该账号已不在成员名单中")
        return save_session(conn, member["uid"], member["role"], member["class_id"], member["name"])


@app.post("/api/logout")
def logout(user: User):
    with db() as conn:
        conn.execute("DELETE FROM sessions WHERE digest=?", (user["digest"],))
    return {"ok": True}


@app.post("/api/login/demo")
def demo(data: DemoLogin):
    if os.getenv("DEMO_MODE") != "1":
        raise HTTPException(404, "演示登录未启用")
    return issue("demo:"+data.role, data.role, "demo", "示例学生" if data.role=="student" else "示例教师")


@app.post("/api/login/wechat")
def wechat(data: WeChatLogin):
    if os.getenv("DEMO_MODE") == "1":
        raise HTTPException(403, "演示服务不接受真实微信登录")
    try:
        members = roster()
        params = urlencode({"appid": os.environ["WX_APP_ID"], "secret": os.environ["WX_APP_SECRET"],
                            "js_code": data.code, "grant_type": "authorization_code"})
    except (KeyError, OSError, ValueError):
        raise HTTPException(503, "微信登录尚未配置") from None
    try:
        with urlopen("https://api.weixin.qq.com/sns/jscode2session?" + params, timeout=8) as response:
            identity = json.load(response)
    except (OSError, ValueError):
        raise HTTPException(502, "微信登录暂时不可用") from None
    openid = identity.get("openid")
    if not openid:
        raise HTTPException(401, "登录凭证已失效，请重试")
    member = members.get(openid)
    if not member or member.get("role") not in ("student", "teacher") or not member.get("class_id") or not member.get("name"):
        raise HTTPException(403, "该账号尚未分配班级和身份")
    return issue(member["uid"], member["role"], member["class_id"], member["name"])


@app.get("/api/assignment")
def assignment(user: User):
    return QUESTION


@app.post("/api/submissions")
def submit(data: Submission, user: User):
    require(user, "student")
    answer = data.answer.strip()
    if not answer:
        raise HTTPException(422, "请填写作答")
    with db() as conn:
        conn.execute("""INSERT INTO submissions(uid,class_id,name,request_id,answer,created)
            VALUES (?,?,?,?,?,?) ON CONFLICT(uid,request_id) DO NOTHING""",
            (user["uid"], user["class_id"], user["name"], data.request_id, answer, int(time.time())))
        row = conn.execute("SELECT id,answer FROM submissions WHERE uid=? AND request_id=?",
                           (user["uid"], data.request_id)).fetchone()
        if row["answer"] != answer:
            raise HTTPException(409, "此提交编号已用于其他作答")
    return {"id": row["id"]}


@app.get("/api/submissions")
def submissions(user: User):
    with db() as conn:
        rows = conn.execute("""SELECT * FROM submissions WHERE class_id=?
            AND (?='teacher' OR uid=?) ORDER BY id DESC""", (user["class_id"], user["role"], user["uid"])).fetchall()
    result = []
    for row in rows:
        entry = {key: row[key] for key in ("id", "name", "answer", "state", "created")}
        if user["role"] == "teacher":
            entry["draft"] = json.loads(row["draft"]) if row["draft"] else None
        elif row["state"] != "reviewed":
            entry["state"] = "submitted"
        entry["review"] = json.loads(row["review"]) if row["review"] else None
        result.append(entry)
    return result


@app.post("/api/submissions/{sid}/review")
def review(sid: int, data: Review, user: User):
    require(user, "teacher")
    result = {"verdict": data.verdict, "feedback": data.feedback.strip(),
              "tag": data.tag.strip() if data.verdict=="incorrect" else ""}
    if not result["feedback"] or (data.verdict=="incorrect" and not result["tag"]):
        raise HTTPException(422, "请填写反馈及相应错因")
    with db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM submissions WHERE id=? AND class_id=?", (sid, user["class_id"])).fetchone()
        if not row:
            raise HTTPException(404, "找不到这份作业")
        if row["state"] == "reviewed" and json.loads(row["review"]) == result:
            return {"state": "reviewed"}
        if row["state"] not in ("draft", "failed"):
            raise HTTPException(409, "该作业已处理或仍在批改，请刷新")
        conn.execute("UPDATE submissions SET review=?, state='reviewed' WHERE id=?",
                     (json.dumps(result, ensure_ascii=False), sid))
    return {"state": "reviewed"}


@app.get("/api/summary")
def summary(user: User):
    require(user, "teacher")
    return class_summary(user["class_id"])
