#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""海豚Radar · 评级引擎（DB 版）。

从 SQLite 的 events/miners 表读真实事件，算出每个电路的健康分 + 等级，
写 ratings 表（当前态）+ rating_history（只记变化，不重复堆叠）+ snapshots（全局历史）。

评分模型与旧 rating.py V3 对齐（见 config.MODEL）：
  撤销 Revoked → 0 分 F；被夺最优 Demoted → 75 分 B；停挖 Stopped → 60 分 C；健康 → 100 分 A。

诚实边界：停挖事件只带 key、缺 circuitId，只能映射到「与 Demoted 事件重叠」的那部分；
其余停挖是历史欠账（stopped_unmapped），新的停挖事件由增量摄取逐台 getMiner 补齐。
"""
import json
import time

from service.config import MODEL, MINER_COUNT, PROCESSORS


def grade(score):
    for bound, g in MODEL["grades"]:
        if score >= bound:
            return g
    return "F"


def proc_name(addr):
    return PROCESSORS.get((addr or "").lower(), (addr or "?")[:10])


def rate_all(conn):
    weights = MODEL["weights"]

    # ── 1) 撤销电路（Revoked 事件 + miners 富化）──
    revoked = {}
    for e in conn.execute("SELECT * FROM events WHERE event='Revoked'").fetchall():
        m = conn.execute("SELECT * FROM miners WHERE key=?", (e["key"],)).fetchone()
        if m is None or m["circuit_id"] is None:
            continue
        cid = m["circuit_id"]
        revoked[cid] = {
            "circuitId": cid,
            "processor": proc_name(m["circuits"]),
            "taskId": m["task_id"],
            "gateCount": m["gate_count"],
            "debtBEM": round((m["debt"] or 0) / 1e8, 4),
            "challenger": e["challenger"],
            "registrant": m["registrant"],
            "tx": e["tx"],
            "block": e["block"],
        }

    # ── 2) 被夺最优电路（Demoted 事件带 circuitId，去重）+ key→circuitId 映射 ──
    demoted = {}
    key2cid = {}
    for e in conn.execute("SELECT * FROM events WHERE event='Demoted' AND circuit_id IS NOT NULL").fetchall():
        cid = e["circuit_id"]
        addr = e["circuits"]
        if e["key"]:
            key2cid[e["key"]] = (cid, addr)
        if cid not in revoked:
            demoted[cid] = {
                "circuitId": cid,
                "processor": proc_name(addr),
                "processorAddr": addr,
                "taskId": e["task_id"],
            }

    # ── 3) 停挖电路（Stopped 只带 key，用 key→circuitId 映射；映射不到的是历史欠账）──
    stopped = {}
    stopped_unmapped = 0
    for e in conn.execute("SELECT * FROM events WHERE event='Stopped'").fetchall():
        k = e["key"]
        if k in key2cid:
            cid, addr = key2cid[k]
            if cid not in revoked and cid not in demoted:
                stopped[cid] = {"circuitId": cid, "processor": proc_name(addr), "processorAddr": addr}
        else:
            stopped_unmapped += 1

    # ── 4) 组装评级 ──
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
    ratings.sort(key=lambda r: (r["score"], r["circuitId"]))

    # ── 5) 写 ratings（当前态）+ history（只在等级/状态变化时记）──
    now = int(time.time())
    for r in ratings:
        cur = conn.execute("SELECT score, grade, status FROM ratings WHERE circuit_id=?",
                           (r["circuitId"],)).fetchone()
        conn.execute(
            """INSERT INTO ratings(circuit_id, processor, task_id, gate_count, score, grade, status, risk, debt_bem,
                                   challenger, registrant, tx, block, updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(circuit_id) DO UPDATE SET
                 processor=excluded.processor, task_id=excluded.task_id, gate_count=excluded.gate_count,
                 score=excluded.score, grade=excluded.grade, status=excluded.status, risk=excluded.risk,
                 debt_bem=excluded.debt_bem, challenger=excluded.challenger, registrant=excluded.registrant,
                 tx=excluded.tx, block=excluded.block, updated_at=excluded.updated_at""",
            (r["circuitId"], r.get("processor"), r.get("taskId"), r.get("gateCount"), r["score"], r["grade"],
             r["status"], json.dumps(r["risk"], ensure_ascii=False), r.get("debtBEM"), r.get("challenger"),
             r.get("registrant"), r.get("tx"), r.get("block"), now),
        )
        if cur is None or cur["score"] != r["score"] or cur["grade"] != r["grade"] or cur["status"] != r["status"]:
            conn.execute("INSERT INTO rating_history(circuit_id, score, grade, status, at) VALUES(?,?,?,?,?)",
                         (r["circuitId"], r["score"], r["grade"], r["status"], now))

    # ── 6) 汇总 + 快照 ──
    ce_count = conn.execute("SELECT COUNT(*) c FROM events WHERE event='CounterexampleAdded'").fetchone()["c"]
    summary = {
        "revoked": len(revoked),
        "demoted": len(demoted),
        "stopped_rated": len(stopped),
        "stopped_unmapped": stopped_unmapped,
        "counterexample_events": ce_count,
        "healthy_estimate": max(0, MINER_COUNT - len(revoked) - len(demoted) - stopped_unmapped),
        "rated_circuits": len(ratings),
    }
    # 快照只在指标变化时插入，避免每轮轮询堆一行冗余数据
    last_snap = conn.execute(
        "SELECT revoked, demoted, stopped, counterexample FROM snapshots ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if (last_snap is None or last_snap["revoked"] != len(revoked) or last_snap["demoted"] != len(demoted)
            or last_snap["stopped"] != len(stopped) or last_snap["counterexample"] != ce_count):
        conn.execute(
            "INSERT INTO snapshots(at, total_miners, revoked, demoted, stopped, counterexample) VALUES(?,?,?,?,?,?)",
            (now, MINER_COUNT, len(revoked), len(demoted), len(stopped), ce_count),
        )
    conn.commit()
    return summary


if __name__ == "__main__":
    from service import db
    c = db.connect()
    s = rate_all(c)
    print(json.dumps(s, ensure_ascii=False, indent=1))
