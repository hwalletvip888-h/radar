#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""海豚Radar · 链上数据摄取（增量）。

两个入口：
  bootstrap(conn)        —— 从旧 real_chain_data.json 一次性 seed 历史数据（幂等）
  scan_incremental(conn) —— 增量扫链：只扫 lastBlock 之后的新块，写事件 + 富化矿机

增量是关键：轮询只扫最近几百块，RPC 压力极小，绕开之前的全量扫描限流。
纯 stdlib（urllib），无第三方依赖。
"""
import json
import os
import time
import urllib.request

from service.config import POD, FROM_BLOCK, GETMINER_SEL, RPCS, TOPICS, ROOT, CHUNK, CHUNK_MIN


def rpc_call(method, params, rpc_url):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(rpc_url, data=body,
                                 headers={"Content-Type": "application/json", "User-Agent": "dolphinradar/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def rpc_rotating(method, params):
    """多个 RPC 轮转 + 重试，避免单点限流。"""
    err = None
    for rpc_url in RPCS:
        for attempt in range(3):
            try:
                res = rpc_call(method, params, rpc_url)
                if "error" in res:
                    raise RuntimeError(str(res["error"]))
                return res["result"]
            except Exception as e:
                err = e
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"all RPCs failed: {err}")


def latest_block():
    return int(rpc_rotating("eth_blockNumber", []), 16)


def abi_words(data):
    if not data or data == "0x":
        return []
    h = data[2:] if data.startswith("0x") else data
    return [h[i:i + 64] for i in range(0, len(h), 64)]


def decode_addr(topic):
    return "0x" + topic[-40:]


def decode_uint(word):
    return int(word, 16)


def decode_raw_log(log):
    """把 RPC 返回的原始 log 解码成事件 dict（与 real_chain_data.json 同 schema）。"""
    t0 = log["topics"][0].lower()
    name = TOPICS.get(t0, "Unknown")
    out = {"event": name, "block": int(log["blockNumber"], 16),
           "tx": log["transactionHash"], "logIndex": int(log["logIndex"], 16)}
    topics = log["topics"]
    data = abi_words(log.get("data", "0x"))

    if name == "Revoked":
        out["key"] = topics[1]
        out["challenger"] = decode_addr(topics[2])
        out["vectorIndex"] = decode_uint(data[0]) if data else None
    elif name == "CounterexampleAdded":
        out["taskId"] = decode_uint(topics[1])
        out["circuits"] = decode_addr(topics[2])
        out["circuitId"] = decode_uint(topics[3])
        out["by"] = decode_addr(data[0]) if data else None
        out["added"] = bool(decode_uint(data[1])) if len(data) > 1 else None
    elif name == "Stopped":
        out["key"] = topics[1]
        out["by"] = decode_addr(topics[2])
    elif name == "Demoted":
        out["key"] = topics[1]
        out["circuits"] = decode_addr(topics[2])
        out["circuitId"] = decode_uint(data[0]) if data else None
        out["taskId"] = decode_uint(data[1]) if len(data) > 1 else None
    return out


def get_miner(key):
    """调用 getMiner(bytes32) 并手动解码关键字段。"""
    data = GETMINER_SEL + key[2:]
    res = rpc_rotating("eth_call", [{"to": POD, "data": data}, "latest"])
    if not res or res == "0x":
        return None
    w = abi_words(res)
    if len(w) < 22:
        return None
    return {
        "circuits": "0x" + w[0][-40:],
        "circuitId": decode_uint(w[1]),
        "taskId": decode_uint(w[2]),
        "gateCount": decode_uint(w[3]),
        "status": decode_uint(w[9]),
        "registrant": "0x" + w[10][-40:],
        "debt": decode_uint(w[21]),
    }


def insert_event(conn, d):
    conn.execute(
        """INSERT OR IGNORE INTO events
           (tx, log_index, event, block, key, circuits, circuit_id, task_id,
            challenger, vector_index, by, raw)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
        (d["tx"], d.get("logIndex"), d["event"], d["block"], d.get("key"), d.get("circuits"),
         d.get("circuitId"), d.get("taskId"), d.get("challenger"), d.get("vectorIndex"),
         d.get("by"), json.dumps(d, ensure_ascii=False)),
    )


def upsert_miner(conn, key, m):
    conn.execute(
        """INSERT INTO miners(key, circuits, circuit_id, task_id, gate_count, status, registrant, debt, updated_at)
           VALUES(?,?,?,?,?,?,?,?,?)
           ON CONFLICT(key) DO UPDATE SET
             circuits=excluded.circuits, circuit_id=excluded.circuit_id, task_id=excluded.task_id,
             gate_count=excluded.gate_count, status=excluded.status, registrant=excluded.registrant,
             debt=excluded.debt, updated_at=excluded.updated_at""",
        (key, m.get("circuits"), m.get("circuitId"), m.get("taskId"), m.get("gateCount"),
         m.get("status"), m.get("registrant"), m.get("debt"), int(time.time())),
    )


def bootstrap(conn):
    """从 real_chain_data.json 一次性 seed 历史数据。幂等：已存在的事件/矿机跳过。"""
    path = os.path.join(ROOT, "real_chain_data.json")
    if not os.path.exists(path):
        print("[ingest] real_chain_data.json 不存在，跳过 seed")
        return False

    rc = json.load(open(path, encoding="utf-8"))
    for d in rc.get("events", []):
        if not d.get("event") or d["event"] == "Unknown":
            continue
        insert_event(conn, d)
    for key, m in rc.get("miners", {}).items():
        upsert_miner(conn, key, m)
    conn.commit()

    from service import db
    # 记录历史扫描边界（增量扫链从这里继续；只在第一次 seed 时设置）
    last = rc.get("latestBlock")
    if last and db.get_meta(conn, "lastBlock") is None:
        db.set_meta(conn, "lastBlock", last)
        conn.commit()
    print(f"[ingest] seed 完成：events={len(rc.get('events', []))} miners={len(rc.get('miners', {}))}")
    return True


def migrate_subscriptions(conn):
    """把旧 subscriptions.json 迁到 subscriptions 表。幂等（按 id upsert）。"""
    path = os.path.join(ROOT, "subscriptions.json")
    if not os.path.exists(path):
        return False
    cfg = json.load(open(path, encoding="utf-8"))
    subs = cfg.get("subscribers", [])
    for s in subs:
        conn.execute(
            """INSERT INTO subscriptions(id, address, tier, channels, telegram_chat_id, webhook_url, expiry, filters)
               VALUES(?,?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET
                 address=excluded.address, tier=excluded.tier, channels=excluded.channels,
                 telegram_chat_id=excluded.telegram_chat_id, webhook_url=excluded.webhook_url,
                 expiry=excluded.expiry, filters=excluded.filters""",
            (s.get("id"), s.get("address"), s.get("tier"),
             json.dumps(s.get("channels", [])), s.get("telegram_chat_id"),
             s.get("webhook_url"), s.get("expiry"), json.dumps(s.get("filters", {}))),
        )
    conn.commit()
    print(f"[ingest] 订阅迁移 {len(subs)} 条")
    return True


def fetch_logs(from_b, to_b):
    """拉取 [from_b, to_b] 的日志。遇到「块区间超限」自动缩小 chunk 重试（5000→500→50）。"""
    logs = []
    cur = from_b
    chunk = CHUNK
    while cur <= to_b:
        cb = min(cur + chunk - 1, to_b)
        try:
            got = rpc_rotating("eth_getLogs", [{
                "address": POD, "fromBlock": hex(cur), "toBlock": hex(cb),
                "topics": [list(TOPICS.keys())],
            }])
            logs.extend(got)
            cur = cb + 1
        except Exception as e:
            msg = str(e).lower()
            if chunk > CHUNK_MIN and ("limit" in msg or "range" in msg):
                chunk = max(CHUNK_MIN, chunk // 10)
                continue
            raise
    return logs


def scan_incremental(conn):
    """增量扫链：从 lastBlock+1 扫到 latest，新事件落库 + 富化矿机。返回新事件数。"""
    from service import db

    last = db.get_meta(conn, "lastBlock")
    last = int(last) if last is not None else FROM_BLOCK - 1
    latest = latest_block()
    if latest <= last:
        return 0

    new_count = 0
    for log in fetch_logs(last + 1, latest):
        d = decode_raw_log(log)
        if d["event"] == "Unknown":
            continue
        insert_event(conn, d)
        new_count += 1
        # 富化：带 key 且未缓存的矿机，读 getMiner
        if d.get("key"):
            cached = conn.execute("SELECT 1 FROM miners WHERE key=?", (d["key"],)).fetchone()
            if not cached:
                try:
                    m = get_miner(d["key"])
                    if m:
                        upsert_miner(conn, d["key"], m)
                except Exception as e:
                    print(f"[ingest] getMiner {d['key'][:18]}… 失败: {e}")

    db.set_meta(conn, "lastBlock", latest)
    conn.commit()
    return new_count
