import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, StringConstraints

from .access import User, require
from .model import teaching_response
from .store import class_summary, db

router = APIRouter(prefix="/api/lessons")
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10000)]


def teacher(user: User):
    require(user, "teacher")
    return user["uid"], user["class_id"]


Teacher = Annotated[tuple, Depends(teacher)]


class Brief(BaseModel):
    request_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=8, max_length=100)]
    topic: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    audience: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
    goal: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=800)]
    minutes: int = Field(ge=5, le=180)
    include_errors: bool = False


class SaveLesson(BaseModel):
    revision: int = Field(ge=1)
    prep: Text
    plan: Annotated[str, StringConstraints(strip_whitespace=True, max_length=10000)]


class PlanRequest(BaseModel):
    revision: int = Field(ge=1)
    prep: Text


def lesson_view(row):
    return {"id": row["id"], **json.loads(row["inputs"]), **{k: row[k] for k in
            ("prep", "plan", "revision", "prep_source", "plan_source")}}


def owned(conn, scope, lid):
    row = conn.execute("SELECT * FROM lessons WHERE id=? AND uid=? AND class_id=?", (lid, *scope)).fetchone()
    if not row:
        raise HTTPException(404, "找不到这份备课")
    return row


@router.get("")
def collection(scope: Teacher):
    with db() as conn:
        rows = conn.execute("SELECT id,inputs,plan FROM lessons WHERE uid=? AND class_id=? ORDER BY id DESC", scope)
        return [{"id": r["id"], "topic": json.loads(r["inputs"])["topic"], "has_plan": bool(r["plan"])} for r in rows]


@router.get("/{lid}")
def one(lid: int, scope: Teacher):
    with db() as conn:
        return lesson_view(owned(conn, scope, lid))


@router.post("")
def prepare(data: Brief, scope: Teacher):
    inputs = data.model_dump(exclude={"request_id"})
    with db() as conn:
        previous = conn.execute("SELECT * FROM lessons WHERE uid=? AND class_id=? AND request_id=?",
                                (*scope, data.request_id)).fetchone()
    if previous:
        if {k: json.loads(previous["inputs"])[k] for k in inputs} != inputs:
            raise HTTPException(409, "请求编号已用于其他课题")
        return lesson_view(previous)
    tags = class_summary(scope[1])["errors"][:5] if data.include_errors else []
    inputs["errors"] = tags
    emphasis = "用两张等大的分数纸条演示为什么必须先通分，再请学生解释每一份表示什么。" if "分数" in data.topic or "通分" in data.topic else f"围绕“{data.topic}”选一组正例和反例，让学生说出区分两者的依据。"
    local = (f"教学目标\n面向{data.audience}，本课要达成：{data.goal}。\n\n"
             f"讲解重点\n{emphasis}\n\n准备材料与提问\n准备一份例题和一份独立练习。"
             f"请学生先解释自己的做法，再用新例子检验能否达成目标。")
    if tags:
        local += "\n\n本班已确认错因\n" + "、".join(t["tag"] for t in tags) + "。选一份同类匿名例题，请学生指出出错的步骤。"
    prep, source = teaching_response("你是教师的中文备课助手。根据课题、学段、目标和课时写出具体的教学重点、材料、提问和检验方法。仅在给出的已确认错因与课题相关时采用。",
        [{"role": "user", "content": json.dumps(inputs, ensure_ascii=False)}], local)
    with db() as conn:
        conn.execute("""INSERT INTO lessons(uid,class_id,request_id,inputs,prep,prep_source) VALUES (?,?,?,?,?,?)
            ON CONFLICT(uid,class_id,request_id) DO NOTHING""",
            (*scope, data.request_id, json.dumps(inputs, ensure_ascii=False), prep, source))
        row = conn.execute("SELECT * FROM lessons WHERE uid=? AND class_id=? AND request_id=?", (*scope, data.request_id)).fetchone()
        if any(json.loads(row["inputs"])[k] != v for k, v in data.model_dump(exclude={"request_id"}).items()):
            raise HTTPException(409, "请求编号已用于其他课题")
        return lesson_view(row)


@router.post("/{lid}/save")
def save(lid: int, data: SaveLesson, scope: Teacher):
    with db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = owned(conn, scope, lid)
        if row["prep"] == data.prep and row["plan"] == data.plan:
            return lesson_view(row)
        if row["revision"] != data.revision:
            raise HTTPException(409, "备课已在其他页面修改，请重新打开")
        conn.execute("""UPDATE lessons SET prep=?,plan=?,revision=revision+1,
            prep_source=?,plan_source=? WHERE id=?""", (data.prep, data.plan,
            row["prep_source"] if row["prep"] == data.prep else "教师编辑",
            row["plan_source"] if row["plan"] == data.plan else "教师编辑", lid))
        return lesson_view(owned(conn, scope, lid))


@router.post("/{lid}/plan")
def make_plan(lid: int, data: PlanRequest, scope: Teacher):
    with db() as conn:
        row = owned(conn, scope, lid)
    if row["plan"] and row["prep"] == data.prep:
        return lesson_view(row)
    if row["revision"] != data.revision or row["plan"]:
        raise HTTPException(409, "备课已有更新或已有教案，请重新打开")
    brief = json.loads(row["inputs"])
    total = brief["minutes"]
    intro = max(1, total // 8)
    explain = max(1, total * 2 // 5)
    closing = max(1, total // 8)
    practice = total - intro - explain - closing
    local = (f"{brief['topic']} · {brief['audience']} · {total} 分钟\n\n"
             f"学习目标\n{brief['goal']}\n\n教学依据\n{data.prep[:5000]}\n\n"
             f"导入（{intro} 分钟）\n围绕课题提问，请学生说说已有认识。\n\n"
             f"示范与讨论（{explain} 分钟）\n依照上面的讲解重点演示一个例子，请学生复述关键步骤。\n\n"
             f"独立练习（{practice} 分钟）\n给出一个新例子，请学生独立作答，并和同伴说明理由。\n\n"
             f"课堂评价（{closing} 分钟）\n按学习目标检查一次独立作答，记录下一课需重讲的内容。")
    plan, source = teaching_response("根据教师编辑后的备课内容写一份可执行的中文教案。包含目标、材料、师生活动、分环节用时及课堂评价。环节时长合计等于给定分钟数。",
        [{"role": "user", "content": json.dumps({**brief, "备课内容": data.prep}, ensure_ascii=False)}], local)
    with db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        latest = owned(conn, scope, lid)
        if latest["revision"] != data.revision:
            if latest["plan"] and latest["prep"] == data.prep:
                return lesson_view(latest)
            raise HTTPException(409, "生成期间备课已修改，请重新打开")
        conn.execute("UPDATE lessons SET prep=?,prep_source=?,plan=?,plan_source=?,revision=revision+1 WHERE id=?",
                     (data.prep, row["prep_source"] if data.prep == row["prep"] else "教师编辑", plan, source, lid))
        return lesson_view(owned(conn, scope, lid))
