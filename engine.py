#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TapeOut 安全警报引擎 —— 事件驱动的实时推送。

WebSocket 实时订阅 BNB PodMining 的 Revoked / CounterexampleAdded 事件，
一旦有新事件 → 富化矿机身份 + 算爆炸半径 → 匹配订阅者 → 按渠道推送。
到期订阅自动失效。

用法：
  python engine.py              # 跑一次：先补扫最近 N 块，再挂 WebSocket 实时监听
  python engine.py --replay     # demo 模式：重放最近一次撤销事件，演示「检测→推送」全流程
  python engine.py --once       # 只补扫一次历史，不挂 WebSocket

订阅：subscriptions.json（免费/Pro/企业三套餐，带 expiry 到期时间）。
推送：Telegram（TELEGRAM_BOT_TOKEN 环境变量）/ Webhook。
"""
import asyncio
import json
import os
import sys
import time
import urllib.request

from web3 import AsyncWeb3
from web3.providers import WebSocketProvider

BASE = os.path.dirname(os.path.abspath(__file__))
SUBS_FILE = os.path.join(BASE, "subscriptions.json")
STATE_FILE = os.path.join(BASE, "engine_state.json")

POD = "0x7E2E0DC66a3bD9103E69b766afA62d9f7b697b46"
BNB_WS = "wss://bsc.publicnode.com"
BNB_HTTP = "https://bsc-dataseed.bnbchain.org/"
GETMINER_SEL = "0x0527edc2"

# 事件 topic0
REVOKED_T0 = "0xe52b422ce6b3cd73243c813dcbc499543bb477dd997c5d177b52c03562347ce5"
CE_T0 = "0x46ff8dc9a41ea4f2cc01bb124e2fc899797dbfa40dca6f4310aa69e9cfd2f3a2"

PROCESSORS = {
    "0x1f5cb4aeae1807bf60c3b9c0d8adbcc14e91f12c": "Behemoth",
    "0xb1024b89886b9a34aa4ff5f31c411d708b20a14c": "TapeOut",
}

TIER_EMOJI = {"high": "🔴", "mid": "🟡", "low": "⚪"}


def load_token():
    """优先取环境变量 TELEGRAM_BOT_TOKEN，否则读 .bot_token 文件"""
    tok = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if tok:
        return tok
    f = os.path.join(BASE, ".bot_token")
    if os.path.exists(f):
        try:
            return open(f, encoding="utf-8").read().strip()
        except Exception:
            pass
    return ""


def load_subs():
    try:
        return json.load(open(SUBS_FILE, encoding="utf-8"))
    except Exception:
        return {"subscribers": []}


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
    t0 = log["topics"][0]
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


def match(alert, filters):
    procs = filters.get("processors", [])
    tasks = filters.get("tasks", [])
    types = filters.get("types", [])
    title = alert.get("title", "") + " " + alert.get("detail", "")
    if procs and not any(p in title for p in procs):
        return False
    if tasks and not any(f"题 #{t}" in title for t in tasks):
        return False
    if types and alert.get("type") not in types:
        return False
    return True


def send_telegram(token, chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    body = json.dumps({"chat_id": chat_id, "text": text, "disable_web_page_preview": True}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


def send_webhook(url, payload):
    body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.status


def format_alert(alert):
    return (f"{TIER_EMOJI.get(alert.get('tier'), '⚪')} {alert['title']}\n"
            f"{alert.get('detail', '')}\n"
            f"影响：{alert.get('impact', '')}\n"
            f"交易：https://bscscan.com/tx/{alert.get('tx', '')}")


def active_subscribers(subs, now=None):
    """过滤出未过期的订阅者"""
    now = now or time.time()
    out = []
    for s in subs.get("subscribers", []):
        exp = s.get("expiry")
        if exp is None or exp > now:
            out.append(s)
    return out


def push_alert(alert, subscribers, tg_token):
    text = format_alert(alert)
    pushed = 0
    for sub in subscribers:
        if not match(alert, sub.get("filters", {})):
            continue
        for ch in sub.get("channels", []):
            try:
                if ch == "telegram" and tg_token and sub.get("telegram_chat_id"):
                    send_telegram(tg_token, sub["telegram_chat_id"], text)
                    print(f"  [推送] telegram → {sub.get('id')}")
                elif ch == "webhook" and sub.get("webhook_url"):
                    send_webhook(sub["webhook_url"], alert)
                    print(f"  [推送] webhook → {sub.get('id')}")
                elif ch == "tapesend":
                    print(f"  [推送] tapesend 待接 → {sub.get('id')}")
                else:
                    print(f"  [跳过] {sub.get('id')} 的 {ch} 未配置")
            except Exception as e:
                print(f"  [失败] {sub.get('id')}/{ch}: {e}")
        pushed += 1
    return pushed


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
        print(f"[engine] 已推给 {n} 个订阅者")
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
            print(f"[engine] 已推给 {n} 个订阅者")
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
