"""试点单元题库。题目顺序和选项以稳定标识保存，答案仅用于服务端评分。"""
from typing import Literal

Stage = Literal["preview", "review"]
BANK = {
    "preview": [
        ("unit", "认识分数单位", "1/3 与 1/4 的分数单位相同吗？", ["相同", "不同"], 1,
         "同样大的整体分别平均分成 3 份和 4 份，每一份大小不同。"),
        ("equiv", "理解等值分数", "哪个分数和 1/3 相等？", ["1/6", "2/6", "3/6"], 1,
         "分子和分母同时乘 2，分数的大小不变。"),
        ("why", "理解通分", "为什么要先通分再相加？", ["统一每一份的大小", "让分子都等于 1", "直接相加分母"], 0,
         "通分统一了计数单位，这样才能把份数相加。"),
    ],
    "review": [
        ("sum", "计算异分母加法", "1/2 + 1/3 等于多少？", ["2/5", "1/6", "5/6"], 2,
         "1/2 = 3/6，1/3 = 2/6，所以结果为 5/6。"),
        ("diagnose", "辨认错误步骤", "小明写 1/4 + 1/6 = 2/10。哪一步要改？", ["只把分子改成 1", "先通分，再把分子相加", "先把两个分母相乘就完成了"], 1,
         "1/4 = 3/12，1/6 = 2/12，相加得 5/12。"),
        ("apply", "运用到情境", "同一个水壶先装了容量的 1/4，又装了容量的 1/2。一共装了多少？", ["3/4", "2/6", "1/8"], 0,
         "两次都以同一个壶为整体，1/4 + 2/4 = 3/4。"),
    ],
}


def questions(stage):
    return [{"id": qid, "skill": skill, "prompt": prompt, "options": options}
            for qid, skill, prompt, options, _, _ in BANK[stage]]


def assess(stage, answers):
    details = []
    for qid, skill, prompt, options, correct, why in BANK[stage]:
        choice = answers[qid]
        if not 0 <= choice < len(options):
            raise ValueError("选项无效")
        details.append({"id": qid, "skill": skill, "prompt": prompt, "chosen": options[choice],
                        "expected": options[correct], "ok": choice == correct, "reason": why})
    return {"stage": stage, "score": sum(item["ok"] for item in details), "total": len(details), "items": details}
