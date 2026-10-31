#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""海豚Radar · 告警生成 + 推送。

读 events 表里「告警游标之后」的新事件，生成分级告警，存 alerts 表，
并推送给 subscriptions 表里未过期的订阅者（复用 common.push_alert 排版）。

历史事件（bootstrap 之前的）不告警——游标由 run.py 在首轮扫完后一次性拉平，
避免服务一启动就把几千条历史事件全推给订阅者。
"""
import json
import os
import sys
import time

# 让 `import common`（deweb-search 根目录）可用
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import common
from service import db
from service.config import PROCESSORS


def build_alert(e, m=None):
    """把一条事件 dict 变成告警 dict。m = miners 行（可选富化）。"""
    name = e["event"]
    if name == "Revoked":
        proc = PROCESSORS.get((m["circuits"] or "").lower(), (m["circuits"] or "?")[:10]) if m else "?"
        debt_bem = round((m["debt"] or 0) / 1e8, 4) if m else 0
        tier = "high" if debt_bem > 100 else ("mid" if debt_bem > 1 else "low")
        return {
            "ts": int(time.time() * 1000), "type": "revoked", "tier": tier,
            "title": f"🚨 矿机被撤销：{proc} #{m['circuit_id'] if m else '?'}",
            "detail": f"题 #{m['task_id'] if m else '?'} · 向量 #{e.get('vectorIndex')}",
            "impact": f"冻结未领 {debt_bem} BEM",
            "challenger": e.get("challenger"), "owner": m["registrant"] if m else None,
            "tx": e["tx"], "block": e["block"],
        }
    if name == "Demoted":
        proc = PROCESSORS.get((e.get("circuits") or "").lower(), (e.get("circuits") or "?")[:10])
        return {
            "ts": int(time.time() * 1000), "type": "demoted", "tier": "mid",
            "title": f"🟡 电路被夺最优：{proc} #{e.get('circuitId')}",
            "detail": f"题 #{e.get('taskId')} 的最优设计被更小电路取代",
            "impact": "设计溢价被收回",
            "tx": e["tx"], "block": e["block"],
        }
    if name == "Stopped":
        proc = PROCESSORS.get((m["circuits"] or "").lower(), (m["circuits"] or "?")[:10]) if m else "?"
        return {
            "ts": int(time.time() * 1000), "type": "stopped", "tier": "low",
            "title": f"⏹️ 矿机停挖：{proc} #{m['circuit_id'] if m else '?'}",
            "detail": f"矿主主动停挖（by {e.get('by', '?')}）",
            "impact": "算力退出，BEM 停止产出",
            "tx": e["tx"], "block": e["block"],
        }
    if name == "CounterexampleAdded":
        proc = PROCESSORS.get((e.get("circuits") or "").lower(), (e.get("circuits") or "?")[:10])
        return {
            "ts": int(time.time() * 1000), "type": "counterexample", "tier": "mid",
            "title": f"⚠️ 新反例登记：{proc} #{e.get('circuitId')}",
            "detail": f"题 #{e.get('taskId')} 被补入新反例向量",
            "impact": "参考实现被加固",
            "tx": e["tx"], "block": e["block"],
        }
    return None


def load_subscribers(conn):
    out = []
    for s in conn.execute("SELECT * FROM subscriptions").fetchall():
        sub = {
            "id": s["id"], "tier": s["tier"],
            "channels": json.loads(s["channels"] or "[]"),
            "telegram_chat_id": s["telegram_chat_id"],
            "webhook_url": s["webhook_url"],
            "expiry": s["expiry"],
            "filters": json.loads(s["filters"] or "{}"),
        }
        if sub["expiry"] is None or sub["expiry"] > time.time():
            out.append(sub)
    return out


def process_new_alerts(conn):
    """把游标之后的新事件生成告警 + 推送。返回新增告警数。"""
    cursor = int(db.get_meta(conn, "alertCursor") or 0)
    tg_token = common.load_token()
    subs = load_subscribers(conn)

    rows = conn.execute(
        """SELECT e.* FROM events e
           WHERE e.event IN ('Revoked','Demoted','Stopped','CounterexampleAdded')
             AND e.block > ?
           ORDER BY e.block, e.log_index""",
        (cursor,),
    ).fetchall()

    new_count = 0
    max_block = cursor
    for e in rows:
        alert_id = f"{e['tx']}:{e['log_index']}"
        m = conn.execute("SELECT * FROM miners WHERE key=?", (e["key"],)).fetchone() if e["key"] else None
        alert = build_alert(e, m)
        if not alert:
            continue
        alert["id"] = alert_id
        conn.execute(
            """INSERT OR IGNORE INTO alerts(id, type, tier, title, detail, impact, tx, block, ts, payload)
               VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (alert_id, alert["type"], alert["tier"], alert["title"], alert["detail"],
             alert["impact"], alert["tx"], alert["block"], alert["ts"],
             json.dumps(alert, ensure_ascii=False)),
        )
        max_block = max(max_block, e["block"])
        new_count += 1
        try:
            common.push_alert(alert, subs, tg_token)
        except Exception as ex:
            print(f"[alert] 推送失败: {ex}")

    if max_block > cursor:
        db.set_meta(conn, "alertCursor", max_block)
    conn.commit()
    return new_count


if __name__ == "__main__":
    from service import db
    c = db.connect()
    print("[alert] 新告警数:", process_new_alerts(c))
