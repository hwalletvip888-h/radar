#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""海豚Radar · 电路/矿机安全评级（V1）。

评分模型（0-100，越高越安全）：
  - 被撤销（Revoked）→ 0 分，F 级（永久失格）
  - 被夺最优（Demoted）→ 75 分，B 级（失去设计溢价，基础挖矿继续）
  - 正常 → 100 分，A 级

等级：
  A ≥90   B 75-89   C 60-74   D 40-59   F <40

数据源：
  - graph_onchain.json（109 个安全相关电路 + 撤销标记）
  - real_chain_data.json（Demoted 事件 → 被夺最优的电路）

产出 ratings.json。未来扩展：停挖、背答案作弊（官方 80 电路）、假冒代币标记。

用法：python rating.py
"""
import json
import os
import time

BASE = os.path.dirname(os.path.abspath(__file__))
GRAPH_FILE = os.path.join(BASE, "graph_onchain.json")
EVENTS_FILE = os.path.join(BASE, "real_chain_data.json")
OUT_FILE = os.path.join(BASE, "ratings.json")

# 评分模型 V1
MODEL = {
    "version": "v1",
    "score_range": "0-100（越高越安全）",
    "weights": {
        "revoked": -100,   # 被撤销 → 直接 0 分
        "demoted": -25,    # 被夺最优 → 扣 25 分
    },
}

GRADE_BOUNDS = [(90, "A"), (75, "B"), (60, "C"), (40, "D"), (0, "F")]


def grade(score):
    for bound, g in GRADE_BOUNDS:
        if score >= bound:
            return g
    return "F"


def main():
    g = json.load(open(GRAPH_FILE, encoding="utf-8"))
    rc = json.load(open(EVENTS_FILE, encoding="utf-8"))

    circuits = [n for n in g["nodes"] if n.get("type") == "circuit"]

    # 被夺最优的电路 ID 集合（Demoted 事件带 circuitId）
    demoted_ids = set()
    for e in rc.get("events", []):
        if e.get("event") == "Demoted" and e.get("circuitId") is not None:
            demoted_ids.add(int(e["circuitId"]))

    ratings = []
    for c in circuits:
        num = c.get("num")
        is_revoked = c.get("status") == "revoked" or c.get("state") == "revoked"
        is_demoted = num in demoted_ids

        if is_revoked:
            score = 0
        elif is_demoted:
            score = 75
        else:
            score = 100

        risks = []
        if is_revoked:
            risks.append("被撤销（反例举证成立，永久失格）")
        if is_demoted:
            risks.append("被夺最优（设计溢价被收回）")

        ratings.append({
            "circuitId": num,
            "name": c.get("name"),
            "processor": c.get("processor"),
            "taskId": c.get("taskId"),
            "gateCount": c.get("gateCount"),
            "score": score,
            "grade": grade(score),
            "status": "revoked" if is_revoked else ("demoted" if is_demoted else "ok"),
            "risk": risks,
            "debtBEM": c.get("debtBEM"),
            "registrant": c.get("registrant"),
            "tx": c.get("tx"),
        })

    # 排序：低分（危险）在前
    ratings.sort(key=lambda r: (r["score"], r["circuitId"]))

    # 汇总
    from collections import Counter
    summary = Counter(r["grade"] for r in ratings)
    revoked_count = sum(1 for r in ratings if r["status"] == "revoked")
    demoted_count = sum(1 for r in ratings if r["status"] == "demoted")

    out = {
        "generated_at": int(time.time()),
        "model": MODEL,
        "total_circuits": len(ratings),
        "summary": {
            "revoked": revoked_count,
            "demoted": demoted_count,
            "ok": len(ratings) - revoked_count - demoted_count,
            "by_grade": {g: summary.get(g, 0) for g in ["A", "B", "C", "D", "F"]},
        },
        "ratings": ratings,
    }

    json.dump(out, open(OUT_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[rating] 已评级 {len(ratings)} 个电路 → {OUT_FILE}")
    print(f"[rating] 撤销 {revoked_count} · 夺最优 {demoted_count} · 正常 {len(ratings)-revoked_count-demoted_count}")
    print(f"[rating] 等级分布: {dict(summary)}")


if __name__ == "__main__":
    main()
