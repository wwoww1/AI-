import hashlib
import json
import os
import sqlite3
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from fastapi import HTTPException

from .model import teaching_response
from .test_flow import ApiCase


class LearningFlow(ApiCase):
    def member(self, role, class_id, name):
        token = "extra-" + hashlib.sha256(name.encode()).hexdigest()
        with sqlite3.connect(self.database) as conn:
            conn.execute("INSERT INTO sessions VALUES (?,?,?,?,?,?)", (
                hashlib.sha256(token.encode()).hexdigest(), "demo:"+name, role, class_id, name, int(time.time())+300))
        return token

    def rejected(self, code, path, data, token):
        with self.assertRaises(HTTPError) as caught:
            self.call(path, data, token)
        self.assertEqual(caught.exception.code, code)

    def test_chat_history_retry_and_ownership(self):
        path = "/study/chat"
        first = {"question": "1/4 + 1/6", "request_id": "first-turn", "after": 0}
        turn = self.call(path, first, self.student)
        self.assertIn("5/12", turn["answer"])
        self.assertEqual(self.call(path, first, self.student), turn)
        self.rejected(409, path, dict(first, question="其他问题"), self.student)
        second = dict(first, request_id="next-turn", question="再举个例子")
        self.rejected(409, path, second, self.student)
        next_turn = self.call(path, dict(second, after=turn["id"]), self.student)
        self.assertIn("圆", next_turn["answer"])
        self.assertEqual(self.call(path, token=self.student), [turn, next_turn])
        self.assertEqual(self.call(path, token=self.member("student", "demo", "peer")), [])
        self.rejected(403, path, None, self.teacher)

    def test_preview_and_review_report(self):
        for stage, choices, score in [
            ("preview", {"unit": 1, "equiv": 0, "why": 0}, 2),
            ("review", {"sum": 2, "diagnose": 1, "apply": 0}, 3),
        ]:
            path = "/study/checks/" + stage
            sheet = self.call(path, token=self.student)
            self.assertEqual(sheet["history"], [])
            self.assertEqual(set(sheet["questions"][0]), {"id","prompt","skill","options"})
            payload = {"answers": choices, "request_id": "test-"+stage}
            self.rejected(422, path, dict(payload, answers={}), self.student)
            bad = {**choices, next(iter(choices)): -4}
            self.rejected(422, path, dict(payload, answers=bad), self.student)
            report = self.call(path, payload, self.student)
            self.assertEqual(report["score"], score)
            self.assertEqual(report["total"], 3)
            self.assertEqual(self.call(path, payload, self.student), report)
            self.assertEqual(self.call(path, token=self.student)["history"], [report])
            self.assertEqual(report["stage"], stage)
            self.assertTrue(all(item["reason"] for item in report["items"]))
            self.rejected(403, path, payload, self.teacher)
        self.assertEqual(self.call("/study/checks/preview", token=self.member("student","demo","peer"))["history"], [])

    def test_optional_focus_and_pause_resume(self):
        data = {"goal": "独立完成通分", "minutes": 1, "request_id": "first-focus"}
        focus = self.call("/study/focus", data, self.student)
        fid = focus["id"]
        state = f"/study/focus/{fid}/state"
        self.assertEqual(self.call("/study/focus", data, self.student)["id"], fid)
        self.rejected(409, "/study/focus", dict(data, request_id="other-focus"), self.student)
        # 模拟经过 15 秒，再验证暂停期间不扣减剩余时间。
        with sqlite3.connect(self.database) as conn:
            conn.execute("UPDATE focus_sessions SET started=started-15 WHERE id=?", (fid,))
        pause = {"state": "paused", "expected": "running"}
        paused = self.call(state, pause, self.student)
        with sqlite3.connect(self.database) as conn:
            conn.execute("UPDATE focus_sessions SET started=started-30 WHERE id=?", (fid,))
        self.assertEqual(self.call("/study/focus", token=self.student), paused)
        self.assertLessEqual(paused["remaining"], 45)
        self.assertEqual(self.call(state, pause, self.student), paused)
        self.call(state, {"state": "running", "expected": "paused"}, self.student)
        with sqlite3.connect(self.database) as conn:
            conn.execute("UPDATE focus_sessions SET started=started-60 WHERE id=?", (fid,))
        self.assertEqual(self.call("/study/focus", token=self.student)["remaining"], 0)
        self.call("/study/checks/preview", {"request_id":"coach-test","answers":{"unit":0,"equiv":1,"why":0}}, self.student)
        advice = self.call(f"/study/focus/{fid}/advice", {}, self.student)
        self.assertIn("认识分数单位", advice["text"])
        self.rejected(404, state, pause, self.member("student", "demo", "peer"))
        self.rejected(403, "/study/focus", None, self.teacher)
        done = self.call(state, {"state": "done", "expected": "running"}, self.student)
        self.assertEqual(done["state"], "done")
        self.rejected(409, state, pause, self.student)
        self.assertNotEqual(self.call("/study/focus", dict(data, request_id="next-focus"), self.student)["id"], fid)

    def test_prepare_edit_plan_reopen_isolated(self):
        with sqlite3.connect(self.database) as conn:
            for group, tag in [("demo","本班错因"), ("other","外班错因")]:
                conn.execute("""INSERT INTO submissions(uid,class_id,name,request_id,answer,state,review,created)
                    VALUES (?,?,?,?,?,'reviewed',?,?)""", (group, group, "样例", "test", "错答",
                    json.dumps({"verdict":"incorrect","tag":tag}), int(time.time())))
        data = {"request_id":"prep-001","topic":"分数加法","audience":"小学五年级","goal":"会解释通分","minutes":40,"include_errors":True}
        self.rejected(403, "/lessons", data, self.student)
        lesson = self.call("/lessons", data, self.teacher)
        path = "/lessons/" + str(lesson["id"])
        self.assertIn("本班错因", lesson["prep"])
        self.assertNotIn("外班错因", lesson["prep"])
        self.assertEqual(self.call("/lessons", data, self.teacher), lesson)
        self.rejected(409, "/lessons", dict(data, topic="其他"), self.teacher)
        draft = {"prep":"用纸条折出六分之一","revision":1}
        plan = self.call(path+"/plan", draft, self.teacher)
        self.assertIn(draft["prep"], plan["plan"])
        self.assertEqual(self.call(path+"/plan", draft, self.teacher), plan)
        changes = {**draft, "plan":"教师修订的教案"}
        self.rejected(409, path+"/save", changes, self.teacher)
        saved = self.call(path+"/save", dict(changes, revision=plan["revision"]), self.teacher)
        self.assertEqual(saved, self.call(path, token=self.teacher))
        self.assertEqual(saved["plan"], changes["plan"])
        peer = self.member("teacher","demo","同班其他教师")
        self.rejected(404, path, None, peer)
        self.assertEqual(self.call("/lessons", token=peer), [])
        self.rejected(403, path, None, self.student)


class TeachingModel(unittest.TestCase):
    @patch.dict(os.environ, TEACHING_MODE="model")
    @patch("backend.model.completion", return_value="根据上文，下一步应该先画图。")
    def test_model_response_and_visible_source(self, complete):
        messages = [{"role":"user","content":"为什么要通分？"}]
        answer, source = teaching_response("教学任务", messages, "本地")
        complete.assert_called_once_with([{"role":"system","content":"教学任务"}, *messages])
        self.assertIn("画图", answer)
        self.assertEqual(source, "AI 生成")

    @patch.dict(os.environ, TEACHING_MODE="model")
    @patch("backend.model.completion", side_effect=TimeoutError)
    def test_failure_does_not_impersonate_ai(self, _):
        with self.assertRaises(HTTPException) as failure:
            teaching_response("教学任务", [], "本地")
        self.assertEqual(failure.exception.status_code, 503)
