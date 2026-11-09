import json
import re
import time
from fractions import Fraction
from math import lcm
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, StrictInt, StringConstraints

from .access import User, require
from .model import teaching_response
from .questions import BANK, Stage, assess, questions
from .store import db

router = APIRouter(prefix="/api/study")
RequestId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=8, max_length=100)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


def student(user: User):
    require(user, "student")
    return user["uid"], user["class_id"]


Student = Annotated[tuple, Depends(student)]


class Ask(BaseModel):
    request_id: RequestId
    question: ShortText
    after: int = Field(ge=0)


def demo_answer(question, turns):
    expression = question.replace("／", "/").replace("＋", "+").replace("−", "-").strip()
    addition = re.fullmatch(r"(?:请计算|计算|请问)?\s*(-?\d{1,4})\s*/\s*([1-9]\d{0,3})\s*\+\s*"
                            r"(-?\d{1,4})\s*/\s*([1-9]\d{0,3})\s*(?:等于多少|是多少|=)?[？?。]?", expression)
    if addition:
        a, b, c, d = map(int, addition.groups())
        denominator = lcm(b, d)
        x, y = a * (denominator // b), c * (denominator // d)
        return (f"先把两项写成分母为 {denominator} 的分数：{x}/{denominator} 和 {y}/{denominator}。"
                f"把分子相加可得 {Fraction(x+y, denominator)}。你能说明为什么分母保持不变吗？")
    if any(word in question for word in ("举例", "例子", "再讲", "不明白", "不懂")) and turns:
        return "拿两个同样大的圆，一个分成 2 份，一个分成 3 份。把每个圆都重新分成 6 份，半个圆占 3 份，三分之一个圆占几份？"
    if any(word in question for word in ("通分", "分母", "分数", "分子")):
        return "分母表示把整体平均分成多少份。每份大小相同时，份数才能直接相加。试着把 1/2 和 1/3 都改写成分母为 6 的分数，各有几份？"
    if turns and question.strip() in {"2", "2份", "2 份", "2/6", "六分之二"} and "三分之一个圆占几份" in turns[-1]["answer"]:
        return "对，三分之一个圆是 2/6。加上半个圆的 3/6，一共是多少？"
    return "本地示例可以讲解通分或演算分数加法。可以问“为什么要通分”，也可以输入一道题，例如 1/4 + 1/6。"


def saved_turn(conn, scope, data):
    row = conn.execute("""SELECT id,question,answer,source FROM study_turns
        WHERE uid=? AND class_id=? AND request_id=?""", (*scope, data.request_id)).fetchone()
    if row and row["question"] != data.question:
        raise HTTPException(409, "请求编号已用于其他提问")
    return dict(row) if row else None


def recent_turns(conn, scope, limit):
    rows = conn.execute("""SELECT id,question,answer,source FROM study_turns WHERE uid=? AND class_id=?
        ORDER BY id DESC LIMIT ?""", (*scope, limit)).fetchall()
    return [dict(row) for row in reversed(rows)]


@router.get("/chat")
def history(scope: Student):
    with db() as conn:
        return recent_turns(conn, scope, 50)


@router.post("/chat")
def ask(data: Ask, scope: Student):
    with db() as conn:
        cached = saved_turn(conn, scope, data)
        if cached:
            return cached
        turns = recent_turns(conn, scope, 8)
    if (turns[-1]["id"] if turns else 0) != data.after:
        raise HTTPException(409, "对话已有更新，请重新发送")
    messages = []
    for turn in turns:
        messages.extend([{"role": "user", "content": turn["question"]},
                         {"role": "assistant", "content": turn["answer"]}])
    messages.append({"role": "user", "content": data.question})
    answer, source = teaching_response("你是学生的中文 AI 老师。结合上文解答当前学习问题，给出简短解释，并用一道追问检查理解。", messages, demo_answer(data.question, turns))
    with db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        cached = saved_turn(conn, scope, data)
        if cached:
            return cached
        latest = conn.execute("SELECT COALESCE(MAX(id),0) FROM study_turns WHERE uid=? AND class_id=?", scope).fetchone()[0]
        if latest != data.after:
            raise HTTPException(409, "对话已有更新，请重新发送")
        conn.execute("""INSERT INTO study_turns(uid,class_id,request_id,question,answer,source)
            VALUES (?,?,?,?,?,?)""", (*scope, data.request_id, data.question, answer, source))
        return saved_turn(conn, scope, data)


class Answers(BaseModel):
    request_id: RequestId
    answers: dict[str, StrictInt]


@router.get("/checks/{stage}")
def check_sheet(stage: Stage, scope: Student):
    with db() as conn:
        rows = conn.execute("""SELECT id,result,created FROM study_checks WHERE uid=? AND class_id=?
            AND stage=? ORDER BY id DESC LIMIT 20""", (*scope, stage)).fetchall()
    return {"topic": "异分母分数加法", "questions": questions(stage),
            "history": [dict(json.loads(r["result"]), id=r["id"], created=r["created"]) for r in rows]}


@router.post("/checks/{stage}")
def submit_check(stage: Stage, data: Answers, scope: Student):
    if set(data.answers) != {q[0] for q in BANK[stage]}:
        raise HTTPException(422, "请完成本次检测的全部题目")
    try:
        result = assess(stage, data.answers)
    except ValueError:
        raise HTTPException(422, "选项无效") from None
    choices = json.dumps(data.answers, sort_keys=True)
    with db() as conn:
        conn.execute("""INSERT INTO study_checks(uid,class_id,stage,request_id,choices,result,created)
            VALUES (?,?,?,?,?,?,?) ON CONFLICT(uid,class_id,request_id) DO NOTHING""",
            (*scope, stage, data.request_id, choices, json.dumps(result, ensure_ascii=False), int(time.time())))
        row = conn.execute("SELECT * FROM study_checks WHERE uid=? AND class_id=? AND request_id=?",
                           (*scope, data.request_id)).fetchone()
        if row["stage"] != stage or row["choices"] != choices:
            raise HTTPException(409, "检测编号已用于其他作答")
        return dict(json.loads(row["result"]), id=row["id"], created=row["created"])


class StartFocus(BaseModel):
    goal: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
    minutes: int = Field(ge=1, le=120)
    request_id: RequestId


def focus_view(row):
    elapsed = row["elapsed"]
    if row["state"] == "running":
        elapsed += max(0, int(time.time())-row["started"])
    return {"id": row["id"], "goal": row["goal"], "minutes": row["minutes"], "state": row["state"],
            "remaining": max(0, row["minutes"] * 60 - elapsed)}


@router.get("/focus")
def current_focus(scope: Student):
    with db() as conn:
        row = conn.execute("SELECT * FROM focus_sessions WHERE uid=? AND class_id=? ORDER BY id DESC LIMIT 1", scope).fetchone()
    return focus_view(row) if row else None


@router.post("/focus")
def start_focus(data: StartFocus, scope: Student):
    with db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        old = conn.execute("SELECT * FROM focus_sessions WHERE uid=? AND class_id=? AND request_id=?",
                           (*scope, data.request_id)).fetchone()
        if old:
            if old["goal"] != data.goal or old["minutes"] != data.minutes:
                raise HTTPException(409, "请求编号已用于其他目标")
            return focus_view(old)
        active = conn.execute("SELECT id FROM focus_sessions WHERE uid=? AND class_id=? AND state!='done'", scope).fetchone()
        if active:
            raise HTTPException(409, "已有进行中的目标，请先完成")
        row = conn.execute("""INSERT INTO focus_sessions(uid,class_id,request_id,goal,minutes,state,started)
            VALUES (?,?,?,?,?,'running',?) RETURNING *""", (*scope, data.request_id, data.goal, data.minutes, int(time.time()))).fetchone()
        return focus_view(row)


class ChangeFocus(BaseModel):
    state: Literal["paused", "running", "done"]
    expected: Literal["paused", "running"]


def owned_focus(conn, scope, fid):
    row = conn.execute("SELECT * FROM focus_sessions WHERE uid=? AND class_id=? AND id=?", (*scope, fid)).fetchone()
    if not row:
        raise HTTPException(404, "找不到学习目标")
    return row


@router.post("/focus/{fid}/state")
def change_focus(fid: int, data: ChangeFocus, scope: Student):
    with db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = owned_focus(conn, scope, fid)
        if row["state"] == data.state:
            return focus_view(row)
        if row["state"] != data.expected:
            raise HTTPException(409, "目标状态已更新，请刷新")
        now = int(time.time())
        elapsed = row["elapsed"] + (max(0, now-row["started"]) if row["state"] == "running" else 0)
        conn.execute("UPDATE focus_sessions SET state=?, elapsed=?, started=? WHERE id=?", (data.state, elapsed, now, fid))
        return focus_view(owned_focus(conn, scope, fid))


@router.post("/focus/{fid}/advice")
def coach(fid: int, scope: Student):
    with db() as conn:
        focus = focus_view(owned_focus(conn, scope, fid))
        row = conn.execute("SELECT result FROM study_checks WHERE uid=? AND class_id=? ORDER BY id DESC LIMIT 1", scope).fetchone()
    weak = [i["skill"] for i in json.loads(row["result"])["items"] if not i["ok"]] if row else []
    next_step = f"上次检测可以再练“{weak[0]}”。" if weak else "选一道与目标相关的题，独立完成后解释每一步。"
    cue = "用一句话总结这次学会的内容。" if focus["remaining"] == 0 or focus["state"] == "done" else "先写下你准备完成的第一步。"
    reply, source = teaching_response("你是中文学习督导。根据学生自己设置的目标、剩余时间及最近检测的薄弱点，给出一个具体的下一步。不能推断学生是否在专心。",
        [{"role": "user", "content": json.dumps({"目标": focus, "上次检测薄弱点": weak}, ensure_ascii=False)}],
        f"围绕“{focus['goal']}”，{cue}{next_step}")
    return {"text": reply, "source": source}
