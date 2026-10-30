#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""海豚Radar · 电路/矿机安全评级（V2 · 全量事件版）。

评分模型（0-100，越高越安全）：
  - 被撤销（Revoked）→ 0 分，F 级（永久失格）
  - 被夺最优（Demoted）→ 75 分，B 级（失去设计溢价，基础挖矿继续）
  - 停挖（Stopped）→ 单独统计（事件只带 key，无 circuitId，不逐电路评级）
  - 正常 → 100 分，A 级（= 矿机总数 - 撤销 - 夺最优）

数据源：
  - real_chain_data.json（全量事件：Revoked/Demoted/Stopped/CounterexampleAdded）
  - graph_onchain.json（撤销电路的名字/债务/交易哈希等富化信息）

产出 ratings.json。相比 V1（只 109 个电路），V2 覆盖全量「有安全信号的电路」。
"""
import json
import os
import time
from collections import Counter

BASE = os.path.dirname(os.path.abspath(__file__))
EVENTS_FILE = os.path.join(BASE, "real_chain_data.json")
GRAPH_FILE = os.path.join(BASE, "graph_onchain.json")
OUT_FILE = os.path.join(BASE, "ratings.json")

MINER_COUNT = 20567  # PodMining minerCount()，全网矿机总数

MODEL = {
    "version": "v2",
    "score_range": "0-100（越高越安全）",
    "weights": {
        "revoked": -100,   # 被撤销 → 0 分
        "demoted": -25,    # 被夺最优 → 75 分
    },
}

GRADE_BOUNDS = [(90, "A"), (75, "B"), (60, "C"), (40, "D"), (0, "F")]

PROCESSORS = {
    "0x1f5cb4aeae1807bf60c3b9c0d8adbcc14e91f12c": "Behemoth",
    "0xb1024b89886b9a34aa4ff5f31c411d708b20a14c": "TapeOut",
    "0xf4412c52ec3dd7fca5f518b6662f77b02bde28e": "RefBench",
}


def proc_name(addr):
    return PROCESSORS.get(addr.lower(), (addr or "?")[:10])


def grade(score):
    for bound, g in GRADE_BOUNDS:
        if score >= bound:
            return g
    return "F"


def main():
    rc = json.load(open(EVENTS_FILE, encoding="utf-8"))
    g = json.load(open(GRAPH_FILE, encoding="utf-8"))

    events = rc.get("events", [])
    miners = rc.get("miners", {})

    # 1) 被撤销的电路：从 miners 字典（key → circuitId）+ graph 富化
    revoked = {}
    rev_keys = {e["key"] for e in events if e.get("event") == "Revoked"}
    # graph 里撤销电路的富化信息（name/debtBEM/tx/challenger）
    graph_revoked = {n.get("num"): n for n in g["nodes"] if n.get("type") == "circuit" and n.get("status") == "revoked"}
    for key in rev_keys:
        m = miners.get(key, {})
        cid = m.get("circuitId")
        if cid is not None:
            enriched = graph_revoked.get(cid, {})
            revoked[cid] = {
                "circuitId": cid,
                "processor": enriched.get("processor") or ("0x" + m.get("circuits", "0x")[-40:]),
                "taskId": enriched.get("taskId") or m.get("taskId"),
                "gateCount": enriched.get("gateCount"),
                "debtBEM": enriched.get("debtBEM"),
                "tx": enriched.get("tx"),
                "challenger": enriched.get("challenger"),
                "registrant": enriched.get("registrant") or m.get("registrant"),
            }

    # 2) 被夺最优的电路：Demoted 事件直接带 circuitId（去重）
    demoted = {}
    for e in events:
        if e.get("event") == "Demoted" and e.get("circuitId") is not None:
            cid = int(e["circuitId"])
            if cid in revoked:
                continue  # 已撤销的优先记撤销
            demoted[cid] = {
                "circuitId": cid,
                "processor": proc_name("0x" + e.get("circuits", "0x")[-40:]),
                "processorAddr": "0x" + e.get("circuits", "0x")[-40:],
                "taskId": e.get("taskId"),
            }

    # 3) 停挖：Stopped 事件只带 key，无 circuitId，单独统计
    stopped_keys = {e["key"] for e in events if e.get("event") == "Stopped"}
    stopped_count = len(stopped_keys)

    # 组装评级
    ratings = []
    for cid, info in revoked.items():
        ratings.append({
            **info,
            "score": 0, "grade": "F", "status": "revoked",
            "risk": ["被撤销（反例举证成立，永久失格）"],
        })
    for cid, info in demoted.items():
        ratings.append({
            **info,
            "score": 75, "grade": "B", "status": "demoted",
            "risk": ["被夺最优（设计溢价被收回）"],
        })

    ratings.sort(key=lambda r: (r["score"], r["circuitId"]))

    revoked_count = len(revoked)
    demoted_count = len(demoted)
    # 健康矿机估算 = 全网矿机 - 撤销 - 夺最优 - 停挖（粗略，可能有重叠）
    healthy_estimate = max(0, MINER_COUNT - revoked_count - demoted_count)

    summary = {
        "revoked": revoked_count,
        "demoted": demoted_count,
        "stopped_events": stopped_count,
        "healthy_estimate": healthy_estimate,
        "by_grade": {
            "A": healthy_estimate, "B": demoted_count, "F": revoked_count,
            "C": 0, "D": 0,
        },
    }

    out = {
        "generated_at": int(time.time()),
        "model": MODEL,
        "rated_circuits": len(ratings),
        "total_miners": MINER_COUNT,
        "summary": summary,
        "ratings": ratings,
    }

    json.dump(out, open(OUT_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[rating] V2 全量事件版：评级 {len(ratings)} 个电路（撤销 {revoked_count} + 夺最优 {demoted_count}）")
    print(f"[rating] 停挖事件 {stopped_count} 条（无 circuitId，仅统计）")
    print(f"[rating] 健康矿机估算 ~{healthy_estimate}（{MINER_COUNT} - 撤销 - 夺最优）")
    print(f"[rating] 等级分布: A~{healthy_estimate} / B {demoted_count} / F {revoked_count}")


if __name__ == "__main__":
    main()
