#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""海豚Radar · 风险引擎（Phase 1.1）。

从「报事件」升级到「判风险」：给每个电路算「风险分 0-100」+「作弊嫌疑」标签。

信号（诚实边界：无官方作弊名单，全是链上特征推断，标「疑似」而非「实锤」）：
  实锤 Revoked                         → 反例举证成立，永久撤销         risk 100
  高嫌疑 Demoted + Counterexample      → 被夺最优 且 被加过反例         risk 80
  中高嫌疑 Demoted（反例活跃题）        → 被夺最优 且 该题被加过反例     risk 70
  中嫌疑 Demoted（仅被夺最优）          → 被夺最优（作弊 kick 代理信号）risk 60
  低风险 Stopped                       → 停挖（活跃度风险）            risk 25
  健康                                  → 无安全信号                    risk 0

数据源：events + miners 表。产出 risk.json + risks 表。
"""
import json
import os
import time

from service.config import MODEL, MINER_COUNT, PROCESSORS, ROOT

OUT_FILE = os.path.join(ROOT, "risk.json")


RISK_LEVELS = [
    (80, "高危"),
    (60, "中危"),
    (25, "低危"),
    (0, "健康"),
]


def proc_name(addr):
    return PROCESSORS.get((addr or "").lower(), (addr or "?")[:10])


def risk_all(conn):
    """计算全部电路的风险分 + 作弊嫌疑。返回 summary。"""

    # ── 1) 实锤：Revoked（从 miners 富化拿 circuitId）──
    revoked = {}   # circuitId -> info
    rev_keys = {r["key"] for r in conn.execute("SELECT key FROM events WHERE event='Revoked'").fetchall()}
    for key in rev_keys:
        m = conn.execute("SELECT * FROM miners WHERE key=?", (key,)).fetchone()
        if m is None or m["circuit_id"] is None:
            continue
        cid = m["circuit_id"]
        revoked[cid] = {
            "circuitId": cid,
            "processor": proc_name(m["circuits"]),
            "taskId": m["task_id"],
            "gateCount": m["gate_count"],
            "debtBEM": round((m["debt"] or 0) / 1e8, 4),
        }

    # ── 2) 被夺最优（Demoted）+ 被加反例（CounterexampleAdded）──
    demoted = {}      # circuitId -> info
    ce_circuits = set()   # 被加过反例的 circuitId
    ce_tasks = set()      # 被加过反例的 taskId
    dem_tasks = set()     # Demoted 涉及的 taskId

    for e in conn.execute("SELECT * FROM events WHERE event='Demoted' AND circuit_id IS NOT NULL").fetchall():
        cid = e["circuit_id"]
        dem_tasks.add(e["task_id"])
        if cid not in demoted and cid not in revoked:
            demoted[cid] = {
                "circuitId": cid,
                "processor": proc_name(e["circuits"]),
                "taskId": e["task_id"],
            }

    for e in conn.execute("SELECT * FROM events WHERE event='CounterexampleAdded'").fetchall():
        if e["circuit_id"] is not None:
            ce_circuits.add(e["circuit_id"])
        if e["task_id"] is not None:
            ce_tasks.add(e["task_id"])

    # ── 3) 停挖（Stopped，用 Demoted 的 key→circuitId 映射，同 rating.py）──
    stopped = {}
    key2cid = {}
    for e in conn.execute("SELECT * FROM events WHERE event='Demoted' AND key IS NOT NULL AND circuit_id IS NOT NULL").fetchall():
        key2cid[e["key"]] = e["circuit_id"]
    for e in conn.execute("SELECT key FROM events WHERE event='Stopped'").fetchall():
        k = e["key"]
        if k in key2cid:
            cid = key2cid[k]
            if cid not in revoked and cid not in demoted:
                stopped[cid] = {"circuitId": cid}

    # ── 4) 组装风险 ──
    risks = []
    for cid, info in revoked.items():
        risks.append({**info, "risk": 100, "level": "高危", "status": "revoked",
                      "labels": ["实锤作弊（反例举证成立，永久撤销）"], "suspect": "confirmed"})
    for cid, info in demoted.items():
        # 精确重叠：同一台电路被加过反例
        if cid in ce_circuits:
            risk, lvl, lab = 80, "高危", "高嫌疑（被夺最优 + 被加过反例）"
            suspect = "high"
        elif info.get("taskId") in ce_tasks:
            risk, lvl, lab = 70, "中危", "中高嫌疑（被夺最优 + 该题被加过反例）"
            suspect = "mid_high"
        else:
            risk, lvl, lab = 60, "中危", "中嫌疑（被夺最优，作弊 kick 代理信号）"
            suspect = "mid"
        risks.append({**info, "risk": risk, "level": lvl, "status": "demoted",
                      "labels": [lab], "suspect": suspect})
    for cid, info in stopped.items():
        risks.append({**info, "risk": 25, "level": "低危", "status": "stopped",
                      "labels": ["停挖（活跃度风险）"], "suspect": "none"})

    risks.sort(key=lambda r: (-r["risk"], r["circuitId"]))

    # ── 5) 写 risks 表（幂等 upsert）+ risk.json ──
    now = int(time.time())
    for r in risks:
        conn.execute(
            """INSERT INTO risks(circuit_id, processor, task_id, risk, level, status, labels, suspect, updated_at)
               VALUES(?,?,?,?,?,?,?,?,?)
               ON CONFLICT(circuit_id) DO UPDATE SET
                 processor=excluded.processor, task_id=excluded.task_id, risk=excluded.risk,
                 level=excluded.level, status=excluded.status, labels=excluded.labels,
                 suspect=excluded.suspect, updated_at=excluded.updated_at""",
            (r["circuitId"], r.get("processor"), r.get("taskId"), r["risk"], r["level"],
             r["status"], json.dumps(r["labels"], ensure_ascii=False), r["suspect"], now),
        )
    conn.commit()

    # 汇总
    summary = {
        "confirmed": len(revoked),
        "high_suspect": sum(1 for r in risks if r["suspect"] == "high"),
        "mid_high_suspect": sum(1 for r in risks if r["suspect"] == "mid_high"),
        "mid_suspect": sum(1 for r in risks if r["suspect"] == "mid"),
        "stopped": len(stopped),
        "total_risky": len(risks),
    }

    out = {
        "generated_at": now,
        "model": {"version": "risk-v1", "note": "链上特征推断，疑似≠实锤"},
        "summary": summary,
        "risks": risks,
    }
    json.dump(out, open(OUT_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return summary


if __name__ == "__main__":
    from service import db
    c = db.connect()
    s = risk_all(c)
    print(json.dumps(s, ensure_ascii=False, indent=1))
