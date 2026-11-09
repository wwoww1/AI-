import hashlib
import os
import time
from typing import Annotated

from fastapi import Depends, Header, HTTPException

from .store import db


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def current(authorization: Annotated[str, Header()] = ""):
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "请先登录")
    with db() as conn:
        user = conn.execute("SELECT * FROM sessions WHERE digest=? AND expires>?",
                            (digest(authorization[7:]), int(time.time()))).fetchone()
    if not user or (user["uid"].startswith("demo:") != (os.getenv("DEMO_MODE") == "1")):
        raise HTTPException(401, "登录已过期")
    return dict(user)


def require(user, role):
    if user["role"] != role:
        raise HTTPException(403, "身份无权执行此操作")


User = Annotated[dict, Depends(current)]
