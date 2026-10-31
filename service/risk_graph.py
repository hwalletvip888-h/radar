#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""海豚Radar · 风险关联分析（Phase 1.2）。

把逐电路的「风险分」聚合成「关联视角」：
  1. 作弊高发题（task hotspots）—— 哪些题被夺最优最多、被加反例最多、被撤销（作弊高发区）
  2. 处理器风险 —— Behemoth vs TapeOut 谁的风险更集中
  3. 实锤作弊链 —— 撤销电路 → 矿主 → 冻结 BEM（风险传染的源头）

数据源：events + miners 表。产出 risk_graph.json。
"""
import json
import os
import time
from collections import Counter, defaultdict

from service.config import PROCESSORS, ROOT

OUT_FILE = os.path.join(ROOT, "risk_graph.json")


def proc_name(addr):
    return PROCESSORS.get((addr or "").lower(), (addr or "?")[:10])


def risk_graph(conn):
    # ── 1) 每道题的风险信号 ──
    task_signal = defaultdict(lambda: {"demoted": 0, "counterexample": 0, "revoked": 0})
    for e in conn.execute(
        "SELECT event, task_id FROM events WHERE task_id IS NOT NULL"
    ).fetchall():
        if e["event"] == "Demoted":
            task_signal[e["task_id"]]["demoted"] += 1
        elif e["event"] == "CounterexampleAdded":
            task_signal[e["task_id"]]["counterexample"] += 1
    # 撤销电路的题（从 miners 富化）
    for m in conn.execute(
        "SELECT task_id FROM miners WHERE circuit_id IS NOT NULL AND task_id IS NOT NULL"
    ).fetchall():
        task_signal[m["task_id"]]["revoked"] += 1

    # 题的风险分：撤销权重最高，反例次之，夺最优最低
    hotspots = []
    for tid, sig in task_signal.items():
        score = sig["demoted"] * 1 + sig["counterexample"] * 3 + sig["revoked"] * 10
        if score > 0:
            hotspots.append({
                "taskId": tid,
                "demoted": sig["demoted"],
                "counterexample": sig["counterexample"],
                "revoked": sig["revoked"],
                "score": score,
            })
    hotspots.sort(key=lambda x: -x["score"])

    # ── 2) 处理器风险分布 ──
    proc_risk = Counter()
    for r in conn.execute("SELECT processor, risk, suspect FROM risks").fetchall():
        proc_risk[r["processor"]] += 1

    # ── 3) 实锤作弊链（撤销 → 矿主 → 冻结 BEM）──
    chains = []
    for m in conn.execute(
        "SELECT circuit_id, circuits, task_id, registrant, debt FROM miners WHERE circuit_id IS NOT NULL"
    ).fetchall():
        chains.append({
            "circuitId": m["circuit_id"],
            "processor": proc_name(m["circuits"]),
            "taskId": m["task_id"],
            "registrant": m["registrant"],
            "frozenBEM": round((m["debt"] or 0) / 1e8, 4),
        })
    chains.sort(key=lambda x: -x["frozenBEM"])

    out = {
        "generated_at": int(time.time()),
        "hotspots": hotspots,
        "processor_risk": {k: v for k, v in sorted(proc_risk.items(), key=lambda x: -x[1])},
        "confirmed_chains": chains,
    }
    json.dump(out, open(OUT_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return out


if __name__ == "__main__":
    from service import db
    c = db.connect()
    out = risk_graph(c)
    print("=== 作弊高发题（前 12）===")
    for h in out["hotspots"][:12]:
        print(f"  题 #{h['taskId']}: 夺最优{h['demoted']} 反例{h['counterexample']} 撤销{h['revoked']} 分{h['score']}")
    print("=== 处理器风险 ===")
    print(" ", out["processor_risk"])
    print("=== 实锤作弊链（冻结 BEM 前 5）===")
    for c in out["confirmed_chains"][:5]:
        print(f"  #{c['circuitId']} {c['processor']} 矿主 {c['registrant'][:10]}… 冻结 {c['frozenBEM']} BEM")
