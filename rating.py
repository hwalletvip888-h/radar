#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""海豚Radar · 电路/矿机安全评级引擎（V3）。

评分模型（0-100，越高越安全，权重可配置）：
  撤销 Revoked   → 0  分  F 永久失格（反例举证成立）
  被夺最优 Demoted → 75 分  B 失去设计溢价，基础挖矿继续
  停挖 Stopped   → 60 分  C 活跃度风险（仅能映射到 circuitId 的那部分）
  被加反例 Counterexample → 70 分 C 被举证过但未撤销（风险偏低）
  正常/健康     → 100 分  A

数据源：
  - real_chain_data.json（全量事件：Revoked/Demoted/Stopped/CounterexampleAdded）
  - graph_onchain.json（电路富化信息：name/debtBEM/tx/challenger）

产出 ratings.json。数据模型见 DATA_MODEL.md。

用法：python rating.py
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

# ── 评分模型（可配置）──────────────────────────────
MODEL = {
    "version": "v3",
    "score_range": "0-100（越高越安全）",
    "weights": {
        "revoked": 0,      # 撤销 → 0 分
        "demoted": 75,     # 被夺最优 → 75 分
        "stopped": 60,     # 停挖 → 60 分
        "counterexample": 70,  # 被加反例（未撤销）→ 70 分
        "healthy": 100,    # 正常 → 100 分
    },
    "grades": [(90, "A"), (75, "B"), (60, "C"), (40, "D"), (0, "F")],
}

PROCESSORS = {
    "0x1f5cb4aeae1807bf60c3b9c0d8adbcc14e91f12c": "Behemoth",
    "0xb1024b89886b9a34aa4ff5f31c411d708b20a14c": "TapeOut",
    "0xf4412c52ec3dd7fca5f518b6662f77b02bde28e": "RefBench",
}


def grade(score):
    for bound, g in MODEL["grades"]:
        if score >= bound:
            return g
    return "F"


def proc_name(addr):
    return PROCESSORS.get(addr.lower(), (addr or "?")[:10])


def main():
    rc = json.load(open(EVENTS_FILE, encoding="utf-8"))
    g = json.load(open(GRAPH_FILE, encoding="utf-8"))

    events = rc.get("events", [])
    miners = rc.get("miners", {})
    weights = MODEL["weights"]

    # 1) 撤销电路：miners 字典（key→circuitId）+ graph 富化
    revoked = {}
    rev_keys = {e["key"] for e in events if e.get("event") == "Revoked"}
    graph_revoked = {n.get("num"): n for n in g["nodes"]
                     if n.get("type") == "circuit" and n.get("status") == "revoked"}
    for key in rev_keys:
        m = miners.get(key, {})
        cid = m.get("circuitId")
        if cid is not None:
            en = graph_revoked.get(cid, {})
            revoked[cid] = {
                "circuitId": cid,
                "processor": en.get("processor") or proc_name(m.get("circuits")),
                "taskId": en.get("taskId") or m.get("taskId"),
                "gateCount": en.get("gateCount"),
                "debtBEM": en.get("debtBEM"),
                "tx": en.get("tx"),
                "challenger": en.get("challenger"),
                "registrant": en.get("registrant") or m.get("registrant"),
            }

    # 2) 被夺最优电路：Demoted 事件带 circuitId（去重），同时建 key→circuitId 映射
    demoted = {}
    key2cid = {}
    for e in events:
        if e.get("event") == "Demoted" and e.get("circuitId") is not None:
            cid = int(e["circuitId"])
            addr = "0x" + e.get("circuits", "0x")[-40:]
            key2cid[e.get("key")] = (cid, addr)
            if cid not in revoked:
                demoted[cid] = {
                    "circuitId": cid,
                    "processor": proc_name(addr),
                    "processorAddr": addr,
                    "taskId": e.get("taskId"),
                }

    # 3) 停挖电路：Stopped 事件只带 key，用 Demoted 的 key→circuitId 映射（能映射到的那部分）
    stopped = {}
    stopped_keys = {e["key"] for e in events if e.get("event") == "Stopped" and "key" in e}
    stopped_unmapped = 0
    for k in stopped_keys:
        if k in key2cid:
            cid, addr = key2cid[k]
            if cid in revoked or cid in demoted:
                continue  # 已撤销/已夺最优的优先
            stopped[cid] = {
                "circuitId": cid,
                "processor": proc_name(addr),
                "processorAddr": addr,
            }
        else:
            stopped_unmapped += 1

    # 4) 被加反例电路（graph 里 status 不是 revoked 的电路，即「被举证过但未撤销」）
    counterexample = {}
    for n in g["nodes"]:
        if n.get("type") == "circuit" and n.get("status") != "revoked" and n.get("num") is not None:
            cid = n["num"]
            if cid in revoked or cid in demoted or cid in stopped:
                continue
            counterexample[cid] = {
                "circuitId": cid,
                "processor": n.get("processor"),
                "taskId": n.get("taskId"),
                "gateCount": n.get("gateCount"),
            }

    # 组装评级
    ratings = []
    for cid, info in revoked.items():
        ratings.append({**info, "score": weights["revoked"], "grade": grade(weights["revoked"]),
                        "status": "revoked", "risk": ["被撤销（反例举证成立，永久失格）"]})
    for cid, info in demoted.items():
        ratings.append({**info, "score": weights["demoted"], "grade": grade(weights["demoted"]),
                        "status": "demoted", "risk": ["被夺最优（设计溢价被收回）"]})
    for cid, info in stopped.items():
        ratings.append({**info, "score": weights["stopped"], "grade": grade(weights["stopped"]),
                        "status": "stopped", "risk": ["停挖（活跃度风险）"]})
    for cid, info in counterexample.items():
        ratings.append({**info, "score": weights["counterexample"], "grade": grade(weights["counterexample"]),
                        "status": "counterexample", "risk": ["被加反例（被举证但未撤销）"]})

    ratings.sort(key=lambda r: (r["score"], r["circuitId"]))

    # 汇总
    by_status = Counter(r["status"] for r in ratings)
    healthy_estimate = max(0, MINER_COUNT - len(revoked) - len(demoted) - stopped_unmapped)

    summary = {
        "revoked": len(revoked),
        "demoted": len(demoted),
        "stopped_rated": len(stopped),
        "stopped_unmapped": stopped_unmapped,
        "counterexample": len(counterexample),
        "healthy_estimate": healthy_estimate,
        "by_status": dict(by_status),
        "by_grade": Counter(r["grade"] for r in ratings),
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
    print(f"[rating] V3 评级 {len(ratings)} 个电路")
    print(f"[rating] 撤销 {len(revoked)} · 夺最优 {len(demoted)} · 停挖 {len(stopped)}(+{stopped_unmapped}未映射) · 被加反例 {len(counterexample)}")
    print(f"[rating] 健康估算 ~{healthy_estimate}")
    print(f"[rating] 等级: {dict(summary['by_grade'])}")


if __name__ == "__main__":
    main()
