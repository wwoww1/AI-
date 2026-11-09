import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from .access import current
from .main import WebLogin, WeChatLogin, web_login, wechat
from .members import roster
from .store import initialize
from .web_account import provision


class SharedIdentity(unittest.TestCase):
    def test_both_roles_share_sessions_with_wechat_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            members = {"legacy-student": {"role": "student", "name": "学生", "class_id": "a"},
                       "teacher-openid": {"account_id":"t1", "role":"teacher", "name":"教师", "class_id":"a"}}
            source = root / "members.json"
            source.write_text(json.dumps(members), encoding="utf-8")
            with patch.dict(os.environ, DATABASE_PATH=str(root/"test.sqlite3"), MEMBERS_FILE=str(source),
                            DEMO_MODE="0", WX_APP_ID="mock", WX_APP_SECRET="mock"):
                initialize()
                for openid, uid in [("legacy-student","wx:legacy-student"), ("teacher-openid","member:t1")]:
                    key = provision(uid)
                    web = web_login(WebLogin(access_key=key))
                    with patch("backend.main.urlopen", return_value=io.BytesIO(json.dumps({"openid":openid}).encode())):
                        mini = wechat(WeChatLogin(code="test"))
                    for s in [web,mini]:
                        user=current("Bearer "+s["token"])
                        self.assertEqual((user["uid"],user["class_id"],user["role"]),
                                         (uid,"a",members[openid]["role"]))
                    provision(uid)
                    for check in [lambda: web_login(WebLogin(access_key=key)), lambda: current("Bearer "+web["token"])]:
                        with self.assertRaises(HTTPException) as denied:
                            check()
                        self.assertEqual(denied.exception.status_code,401)
                members["another"] = dict(members["teacher-openid"])
                source.write_text(json.dumps(members),encoding="utf-8")
                with self.assertRaises(HTTPException):
                    roster()
