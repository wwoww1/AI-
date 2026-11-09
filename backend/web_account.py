"""为成员名单中的学生或教师生成或轮换网页登录码。"""
import argparse
import secrets

from .access import digest
from .members import roster
from .store import db, initialize


def provision(uid):
    key = secrets.token_urlsafe(32)
    with db() as conn:
        conn.execute("""INSERT INTO web_accounts(uid,key_digest) VALUES (?,?)
            ON CONFLICT(uid) DO UPDATE SET key_digest=excluded.key_digest""", (uid, digest(key)))
        conn.execute("DELETE FROM sessions WHERE uid=?", (uid,))
    return key


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--member", required=True, help="成员名单中的键，如学生或教师的 OpenID")
    args = parser.parse_args()
    member = roster().get(args.member)
    if not member:
        parser.error("成员名单中没有此人")
    initialize()
    print(provision(member["uid"]))


if __name__ == "__main__":
    main()
