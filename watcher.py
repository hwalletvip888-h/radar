#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TapeOut 实时安全监听器。

盯 BNB PodMining 合约的 Revoked / CounterexampleAdded / Stopped 事件，
发现新事件 → 富化矿机身份 → 算爆炸半径 + 分级 → 写 alerts.json（可选 Telegram 推送）。

用法：
  python watcher.py            # 跑一轮（扫描最近 N 块，检测新事件）
  python watcher.py --loop 60  # 每 60 秒轮询一轮（常驻监听）
  python watcher.py --replay   # 重放最近一次 Revoked 事件（demo 用，演示检测+告警流程）

纯 stdlib。状态存 watcher_state.json（记住扫到哪、见过哪些事件）。
"""
import json, time, sys, urllib.request, os

from common import PROCESSORS

POD = "0x7E2E0DC66a3bD9103E69b766afA62d9f7b697b46"
RPCS = ["https://tapeout.net/rpc", "https://bsc-dataseed.bnbchain.org/", "https://bsc-dataseed.binance.org/"]
CHUNK = 50000
BASE = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BASE, "watcher_state.json")
ALERTS_FILE = os.path.join(BASE, "alerts.json")
GETMINER_SEL = "0x0527edc2"

EVENTS = {
    "0xe52b422ce6b3cd73243c813dcbc499543bb477dd997c5d177b52c03562347ce5": "Revoked",
    "0x46ff8dc9a41ea4f2cc01bb124e2fc899797dbfa40dca6f4310aa69e9cfd2f3a2": "CounterexampleAdded",
    "0xc167316d53fbdff5ab2c8e45514426acd104c84efb1e239fe4b517ebb32ba88e": "Stopped",
}


def rpc(method, params):
    err = None
    for rpc_url in RPCS:
        for a in range(3):
            try:
                body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
                req = urllib.request.Request(rpc_url, data=body,
                                             headers={"Content-Type": "application/json", "User-Agent": "tapeout-watcher/1.0"})
                with urllib.request.urlopen(req, timeout=60) as r:
                    j = json.loads(r.read().decode())
                if "error" in j:
                    raise RuntimeError(str(j["error"]))
                return j["result"]
            except Exception as e:
                err = e
                time.sleep(2 * (a + 1))
    raise RuntimeError(err)


def get_miner(key):
    data = GETMINER_SEL + key[2:]
    res = rpc("eth_call", [{"to": POD, "data": data}, "latest"])
    if not res or res == "0x":
        return None
    h = res[2:]
    w = [h[i:i + 64] for i in range(0, len(h), 64)]
    if len(w) < 22:
        return None
    return {
        "circuits": "0x" + w[0][-40:],
        "circuitId": int(w[1], 16),
        "taskId": int(w[2], 16),
        "gateCount": int(w[3], 16),
        "status": int(w[9], 16),
        "registrant": "0x" + w[10][-40:],
        "bstar": int(w[13], 16),
        "debt": int(w[21], 16),
    }


def decode_log(log):
    t0 = log["topics"][0]
    name = EVENTS.get(t0, "Unknown")
    topics = log["topics"]
    data = log.get("data", "0x")[2:]
    words = [data[i:i + 64] for i in range(0, len(data), 64)]
    out = {"event": name, "tx": log["transactionHash"], "block": int(log["blockNumber"], 16)}
    if name == "Revoked":
        out["key"] = topics[1]
        out["challenger"] = "0x" + topics[2][-40:]
        out["vectorIndex"] = int(words[0], 16) if words else None
    elif name == "CounterexampleAdded":
        out["taskId"] = int(topics[1], 16)
        out["circuits"] = "0x" + topics[2][-40:]
        out["circuitId"] = int(topics[3], 16)
    elif name == "Stopped":
        out["key"] = topics[1]
        out["by"] = "0x" + topics[2][-40:]
    return out


def build_alert(d):
    """把一条事件变成一条分级告警。"""
    name = d["event"]
    if name == "Revoked":
        m = get_miner(d["key"]) or {}
        proc = PROCESSORS.get((m.get("circuits") or "").lower(), (m.get("circuits") or "?")[:10])
        debt_bem = round(m.get("debt", 0) / 1e8, 4)
        tier = "high" if debt_bem > 100 else ("mid" if debt_bem > 1 else "low")
        return {
            "ts": int(time.time() * 1000),
            "type": "revoked",
            "tier": tier,
            "title": f"🚨 矿机被撤销：{proc} #{m.get('circuitId', '?')}",
            "detail": f"题 #{m.get('taskId', '?')} · {m.get('gateCount', '?')} 门 · 向量 #{d.get('vectorIndex')}",
            "impact": f"冻结未领 {debt_bem} BEM",
            "challenger": d.get("challenger"),
            "owner": m.get("registrant"),
            "tx": d["tx"],
            "block": d["block"],
        }
    if name == "CounterexampleAdded":
        proc = PROCESSORS.get((d.get("circuits") or "").lower(), (d.get("circuits") or "?")[:10])
        return {
            "ts": int(time.time() * 1000),
            "type": "counterexample",
            "tier": "mid",
            "title": f"⚠️ 新反例登记：{proc} #{d.get('circuitId')}",
            "detail": f"题 #{d.get('taskId')} 被补入新反例向量",
            "impact": "参考实现被加固",
            "tx": d["tx"],
            "block": d["block"],
        }
    if name == "Stopped":
        m = get_miner(d.get("key")) or {}
        proc = PROCESSORS.get((m.get("circuits") or "").lower(), (m.get("circuits") or "?")[:10])
        return {
            "ts": int(time.time() * 1000),
            "type": "stopped",
            "tier": "low",
            "title": f"⏹️ 矿机停挖：{proc} #{m.get('circuitId', '?')}",
            "detail": f"矿主主动停挖（by {d.get('by', '?')}）",
            "impact": "算力退出，BEM 停止产出",
            "tx": d["tx"],
            "block": d["block"],
        }
    return None


def main():
    replay = "--replay" in sys.argv
    loop = None
    if "--loop" in sys.argv:
        loop = int(sys.argv[sys.argv.index("--loop") + 1])

    state = {}
    if os.path.exists(STATE_FILE):
        state = json.load(open(STATE_FILE, encoding="utf-8"))
    seen = set(state.get("seen", []))

    while True:
        latest = int(rpc("eth_blockNumber", []), 16)
        from_b = state.get("lastBlock", latest - 200)
        if from_b >= latest:
            from_b = latest - 200
        to_b = latest

        new_alerts = []
        # 分块扫（每次最多 50000 块，但轮询通常只要几百块）
        cur = from_b
        while cur <= to_b:
            cb = min(cur + CHUNK - 1, to_b)
            try:
                logs = rpc("eth_getLogs", [{
                    "address": POD, "fromBlock": hex(cur), "toBlock": hex(cb),
                    "topics": [list(EVENTS.keys())],
                }])
            except Exception as e:
                print(f"[watcher] 块 {cur}-{cb} 失败: {e}")
                time.sleep(5)
                continue
            for log in logs:
                tx = log["transactionHash"]
                if tx in seen:
                    continue
                seen.add(tx)
                d = decode_log(log)
                alert = build_alert(d)
                if alert:
                    new_alerts.append(alert)
                    print(f"[watcher] 🔔 {alert['title']} · {alert['impact']}")
            cur = cb + 1

        # replay：demo 用，用已扫出的历史 Revoked 事件（real_chain_data.json）演示「检测+告警」
        if replay and not new_alerts:
            try:
                rc = json.load(open(os.path.join(BASE, "real_chain_data.json"), encoding="utf-8"))
                revs = [e for e in rc.get("events", []) if e["event"] == "Revoked"]
                miners = rc.get("miners", {})
                if revs:
                    d = revs[-1]  # 最近一次
                    m = miners.get(d.get("key"), {})
                    proc = PROCESSORS.get((m.get("circuits") or "").lower(), (m.get("circuits") or "?")[:10])
                    debt_bem = round(m.get("debt", 0) / 1e8, 4)
                    tier = "high" if debt_bem > 100 else ("mid" if debt_bem > 1 else "low")
                    alert = {
                        "ts": int(time.time() * 1000), "replay": True,
                        "type": "revoked", "tier": tier,
                        "title": f"🚨 矿机被撤销：{proc} #{m.get('circuitId', '?')}",
                        "detail": f"题 #{m.get('taskId', '?')} · {m.get('gateCount', '?')} 门 · 向量 #{d.get('vectorIndex')}",
                        "impact": f"冻结未领 {debt_bem} BEM",
                        "challenger": d.get("challenger"), "owner": m.get("registrant"),
                        "tx": d.get("tx"), "block": d.get("block"),
                    }
                    new_alerts.append(alert)
                    print(f"[watcher] 重放最近一次撤销：{alert['title']} · {alert['impact']}")
            except Exception as e:
                print(f"[watcher] replay failed: {e}")

        # 写状态 + 告警
        state["lastBlock"] = latest
        state["seen"] = sorted(seen)[-5000:]
        json.dump(state, open(STATE_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

        if new_alerts:
            alerts = []
            if os.path.exists(ALERTS_FILE):
                alerts = json.load(open(ALERTS_FILE, encoding="utf-8"))
            alerts = new_alerts + alerts  # 新的在前
            json.dump(alerts[:100], open(ALERTS_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

        print(f"[watcher] 已扫描到块 {latest}，本轮新事件 {len(new_alerts)} 条")

        if loop is None:
            break
        time.sleep(loop)


if __name__ == "__main__":
    main()
