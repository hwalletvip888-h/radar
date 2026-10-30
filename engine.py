#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TapeOut 安全警报引擎 —— 事件驱动的实时推送。

WebSocket 实时订阅 BNB PodMining 的 Revoked / CounterexampleAdded 事件，
一旦有新事件 → 富化矿机身份 + 算爆炸半径 → 匹配订阅者 → 按渠道推送。
到期订阅自动失效。

用法：
  python engine.py              # 挂 WebSocket 实时监听
  python engine.py --replay     # demo 模式：重放最近一次撤销事件，演示「检测→推送」全流程
  python engine.py --once       # 只重放一次，不挂 WebSocket

订阅：subscriptions.json（免费/Pro/企业三套餐，带 expiry 到期时间）。
推送：Telegram / Webhook（token 读 .bot_token 或环境变量 TELEGRAM_BOT_TOKEN）。
共享工具在 common.py（匹配/推送/读 token 等）。
"""
import asyncio
import json
import os
import sys
import time
import urllib.request

from web3 import AsyncWeb3
from web3.providers import WebSocketProvider

from common import PROCESSORS, load_token, load_subs, active_subscribers, push_alert

BASE = os.path.dirname(os.path.abspath(__file__))

POD = "0x7E2E0DC66a3bD9103E69b766afA62d9f7b697b46"
BNB_WS = "wss://bsc.publicnode.com"
BNB_HTTP = "https://bsc-dataseed.bnbchain.org/"
GETMINER_SEL = "0x0527edc2"

# 事件 topic0
REVOKED_T0 = "0xe52b422ce6b3cd73243c813dcbc499543bb477dd997c5d177b52c03562347ce5"
CE_T0 = "0x46ff8dc9a41ea4f2cc01bb124e2fc899797dbfa40dca6f4310aa69e9cfd2f3a2"


def http_rpc(method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(BNB_HTTP, data=body,
                                 headers={"Content-Type": "application/json", "User-Agent": "tapeout-engine/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        j = json.loads(r.read().decode())
    if "error" in j:
        raise RuntimeError(str(j["error"]))
    return j["result"]


def get_miner(key):
    """读矿机身份（getMiner(bytes32)）"""
    data = GETMINER_SEL + key[2:]
    res = http_rpc("eth_call", [{"to": POD, "data": data}, "latest"])
    if not res or res == "0x":
        return {}
    h = res[2:]
    w = [h[i:i + 64] for i in range(0, len(h), 64)]
    if len(w) < 22:
        return {}
    return {
        "circuits": "0x" + w[0][-40:],
        "circuitId": int(w[1], 16),
        "taskId": int(w[2], 16),
        "gateCount": int(w[3], 16),
        "status": int(w[9], 16),
        "registrant": "0x" + w[10][-40:],
        "debt": int(w[21], 16),
    }


def build_alert(event, log):
    """把一条链上事件变成一条分级告警。event: 'Revoked' / 'CounterexampleAdded'"""
    topics = log["topics"]
    data = log.get("data", "0x")[2:]
    words = [data[i:i + 64] for i in range(0, len(data), 64)]

    if event == "Revoked":
        key = topics[1]
        challenger = "0x" + topics[2][-40:]
        vector_index = int(words[0], 16) if words else None
        m = get_miner(key)
        proc = PROCESSORS.get((m.get("circuits") or "").lower(), (m.get("circuits") or "?")[:10])
        debt_bem = round(m.get("debt", 0) / 1e8, 4)
        tier = "high" if debt_bem > 100 else ("mid" if debt_bem > 1 else "low")
        return {
            "ts": int(time.time() * 1000),
            "type": "revoked",
            "tier": tier,
            "title": f"🚨 矿机被撤销：{proc} #{m.get('circuitId', '?')}",
            "detail": f"题 #{m.get('taskId', '?')} · {m.get('gateCount', '?')} 门 · 向量 #{vector_index}",
            "impact": f"冻结未领 {debt_bem} BEM",
            "challenger": challenger,
            "owner": m.get("registrant"),
            "tx": log["transactionHash"],
            "block": int(log["blockNumber"], 16),
        }
    # CounterexampleAdded
    task_id = int(topics[1], 16)
    circuits = "0x" + topics[2][-40:]
    circuit_id = int(topics[3], 16)
    proc = PROCESSORS.get(circuits.lower(), circuits[:10])
    return {
        "ts": int(time.time() * 1000),
        "type": "counterexample",
        "tier": "mid",
        "title": f"⚠️ 新反例登记：{proc} #{circuit_id}",
        "detail": f"题 #{task_id} 被补入新反例向量",
        "impact": "参考实现被加固",
        "tx": log["transactionHash"],
        "block": int(log["blockNumber"], 16),
    }


def replay_alert():
    """demo 用：用已扫出的历史 Revoked 事件重放一次"""
    rc = json.load(open(os.path.join(BASE, "real_chain_data.json"), encoding="utf-8"))
    revs = [e for e in rc.get("events", []) if e["event"] == "Revoked"]
    miners = rc.get("miners", {})
    if not revs:
        return None
    d = revs[-1]
    m = miners.get(d.get("key"), {})
    proc = PROCESSORS.get((m.get("circuits") or "").lower(), (m.get("circuits") or "?")[:10])
    debt_bem = round(m.get("debt", 0) / 1e8, 4)
    return {
        "ts": int(time.time() * 1000), "replay": True,
        "type": "revoked", "tier": "high" if debt_bem > 100 else ("mid" if debt_bem > 1 else "low"),
        "title": f"🚨 矿机被撤销：{proc} #{m.get('circuitId', '?')}",
        "detail": f"题 #{m.get('taskId', '?')} · {m.get('gateCount', '?')} 门 · 向量 #{d.get('vectorIndex')}",
        "impact": f"冻结未领 {debt_bem} BEM",
        "challenger": d.get("challenger"), "owner": m.get("registrant"),
        "tx": d.get("tx"), "block": d.get("block"),
    }


async def listen_real_time(tg_token):
    """挂 WebSocket 实时监听 BNB 的 Revoked / CounterexampleAdded"""
    w3 = await AsyncWeb3(WebSocketProvider(BNB_WS))
    if not await w3.is_connected():
        print("[engine] WebSocket 连接失败")
        return
    print("[engine] WebSocket 已连接，实时监听 BNB PodMining…")

    sub = await w3.eth.subscribe("logs", {
        "address": POD,
        "topics": [[REVOKED_T0, CE_T0]],
    })
    print("[engine] 已订阅日志（Revoked / CounterexampleAdded），等新事件…")

    async for payload in sub:
        log = payload.get("result", payload)
        t0 = log.get("topics", [""])[0]
        event = "Revoked" if t0.lower() == REVOKED_T0 else "CounterexampleAdded"
        try:
            alert = build_alert(event, log)
        except Exception as e:
            print(f"[engine] 解码失败: {e}")
            continue
        print(f"\n[engine] 🔔 检测到新事件：{alert['title']}")
        subs = active_subscribers(load_subs())
        n = push_alert(alert, subs, tg_token)
        print(f"[engine] 已推 {n} 次")
        # 追加到 alerts.json
        alerts = []
        if os.path.exists(os.path.join(BASE, "alerts.json")):
            alerts = json.load(open(os.path.join(BASE, "alerts.json"), encoding="utf-8"))
        alerts.insert(0, alert)
        json.dump(alerts[:100], open(os.path.join(BASE, "alerts.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


async def main():
    tg_token = load_token()
    subs = load_subs()
    active = active_subscribers(subs)
    print(f"[engine] 活跃订阅者 {len(active)} 个（免费/Pro/企业 到期时间已在 subscriptions.json）")

    if "--replay" in sys.argv:
        alert = replay_alert()
        if alert:
            print(f"\n[engine] ▶ 重放最近一次撤销：{alert['title']} · {alert['impact']}")
            n = push_alert(alert, active, tg_token)
            print(f"[engine] 已推 {n} 次")
        else:
            print("[engine] 没有可重放的历史事件")

    if "--once" in sys.argv:
        return

    # 挂 WebSocket 实时监听
    try:
        await listen_real_time(tg_token)
    except KeyboardInterrupt:
        print("\n[engine] 停止")


if __name__ == "__main__":
    asyncio.run(main())
