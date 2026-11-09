import json
import os
from pathlib import Path

from fastapi import HTTPException


def roster():
    try:
        data = json.loads(Path(os.environ["MEMBERS_FILE"]).read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict):
            raise ValueError
        result = {}
        seen = set()
        for key, member in data.items():
            if not isinstance(member, dict) or member.get("role") not in ("student", "teacher"):
                raise ValueError
            if not all(isinstance(member.get(field), str) and member[field].strip() for field in ("name", "class_id")):
                raise ValueError
            account = member.get("account_id")
            if account is not None and (not isinstance(account, str) or not account.strip()):
                raise ValueError
            uid = "member:" + account if account else "wx:" + key
            if uid in seen:
                raise ValueError
            seen.add(uid)
            result[key] = {**member, "uid": uid}
        return result
    except (KeyError, OSError, ValueError):
        raise HTTPException(503, "成员名单未配置或内容无效") from None
