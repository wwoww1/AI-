import json
import os
from urllib.request import Request, urlopen

from fastapi import HTTPException


def completion(messages):
    url = os.environ["MODEL_ENDPOINT"]
    if not url.startswith("https://"):
        raise ValueError("模型接口需使用 HTTPS")
    body = {"model": os.environ["MODEL_NAME"], "messages": messages}
    req = Request(url, data=json.dumps(body).encode(), headers={
        "Content-Type": "application/json", "Authorization": "Bearer " + os.environ["MODEL_API_KEY"],
    })
    with urlopen(req, timeout=30) as response:
        payload = json.load(response)
    text = payload["choices"][0]["message"]["content"]
    if not isinstance(text, str) or not text.strip():
        raise ValueError("模型未返回文字")
    return text.strip()


def teaching_response(instruction, messages, local_text):
    mode = os.getenv("TEACHING_MODE", os.getenv("GRADER_MODE", "rules"))
    if mode == "rules":
        return local_text, "本地示例"
    if mode != "model":
        raise HTTPException(503, "教学助手模式配置无效")
    try:
        reply = completion([{"role": "system", "content": instruction}, *messages])
        if len(reply) > 10000:
            raise ValueError("响应过长")
        return reply, "AI 生成"
    except (OSError, ValueError, KeyError, TypeError, IndexError):
        raise HTTPException(503, "教学模型暂不可用，请稍后重试") from None
