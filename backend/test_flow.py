"""使用实际 HTTP 接口检查单班试点的提交、复核与权限边界。"""
import json
import os
import shutil
import socket
import sqlite3
import hashlib
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ApiCase(unittest.TestCase):
    def setUp(self):
        directory = Path(tempfile.mkdtemp(prefix="learning-test-"))
        self.database = directory / "test.sqlite3"
        self.addCleanup(shutil.rmtree, directory, True)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        self.url = f"http://127.0.0.1:{port}/api"
        env = dict(os.environ, DEMO_MODE="1", GRADER_MODE="rules", TEACHING_MODE="rules", DATABASE_PATH=str(self.database))
        self.server = subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.main:app",
                                        "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"], env=env)
        self.addCleanup(self.stop_server)
        last_error = None
        for _ in range(100):
            try:
                self.student = self.call("/login/demo", {"role": "student"})["token"]
                break
            except URLError as error:
                last_error = error
                time.sleep(.1)
        else:
            self.fail(f"未能连接本机测试服务: {last_error}")
        self.teacher = self.call("/login/demo", {"role": "teacher"})["token"]

    def stop_server(self):
        self.server.terminate()
        self.server.wait(timeout=10)

    def call(self, path, data=None, token=""):
        body = None if data is None else json.dumps(data).encode()
        req = Request(self.url + path, data=body, headers={"Content-Type": "application/json", "Authorization": "Bearer "+token})
        with urlopen(req, timeout=5) as res:
            return json.load(res)

class ReviewFlow(ApiCase):
    def test_submission_review_summary(self):
        sample = {"request_id": "sample-001", "answer": "2/7"}
        sid = self.call("/submissions", sample, self.student)["id"]
        self.assertEqual(self.call("/submissions", sample, self.student)["id"], sid)
        with self.assertRaises(HTTPError) as conflict:
            self.call("/submissions", dict(sample, answer="7/12"), self.student)
        self.assertEqual(conflict.exception.code, 409)
        for _ in range(60):
            row = self.call("/submissions", token=self.teacher)[0]
            if row["state"] == "draft":
                break
            time.sleep(.1)
        self.assertEqual(row["draft"]["verdict"], "incorrect")
        self.assertEqual(row["draft"]["source"], "规则演示")
        self.assertEqual(len(self.call("/submissions", token=self.teacher)), 1)
        student_row = self.call("/submissions", token=self.student)[0]
        self.assertNotIn("draft", student_row)
        self.assertIsNone(student_row["review"])
        self.assertEqual(self.call("/summary", token=self.teacher)["reviewed"], 0)

        url = f"/submissions/{sid}/review"
        result = {"verdict": "incorrect", "feedback": "请写出通分步骤，再算一次。", "tag": "通分需复查"}
        with self.assertRaises(HTTPError) as forbidden:
            self.call(url, result, self.student)
        self.assertEqual(forbidden.exception.code, 403)
        for _ in range(2):
            self.assertEqual(self.call(url, result, self.teacher)["state"], "reviewed")
        self.assertEqual(self.call("/submissions", token=self.student)[0]["review"], result)
        self.assertEqual(self.call("/summary", token=self.teacher),
                         {"reviewed": 1, "errors": [{"tag": result["tag"], "count": 1}]})

    def test_auth_and_validation(self):
        for path, token, status in [("/summary", self.student, 403), ("/submissions", "", 401)]:
            with self.assertRaises(HTTPError) as rejected:
                self.call(path, token=token)
            self.assertEqual(rejected.exception.code, status)
        with self.assertRaises(HTTPError) as rejected:
            self.call("/submissions", {"request_id": "invalid-001", "answer": "   "}, self.student)
        self.assertEqual(rejected.exception.code, 422)

    def test_peer_and_other_class_cannot_access_submission(self):
        sid = self.call("/submissions", {"request_id": "scope-001", "answer": "7/12"}, self.student)["id"]
        members = [("peer", "student", "demo"), ("other-teacher", "teacher", "other")]
        with sqlite3.connect(self.database) as conn:
            for token, role, class_id in members:
                conn.execute("INSERT INTO sessions VALUES (?,?,?,?,?,?)", (
                    hashlib.sha256(token.encode()).hexdigest(), "demo:"+token, role,
                    class_id, token, int(time.time())+60))
        for token, _, _ in members:
            self.assertEqual(self.call("/submissions", token=token), [])
        with self.assertRaises(HTTPError) as denied:
            self.call(f"/submissions/{sid}/review", {"verdict":"correct","feedback":"通过"}, "other-teacher")
        self.assertEqual(denied.exception.code, 404)
        self.assertEqual(self.call("/summary", token="other-teacher")["reviewed"], 0)


if __name__ == "__main__":
    unittest.main()
