#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""海豚Radar 告警管线共享工具。

engine.py（WebSocket 实时）/ notifier.py（轮询分发）/ watcher.py（扫链）共用的
推送、匹配、分级、token/订阅读取 等纯函数，避免三处重复实现。

这些函数都是无副作用（除网络/文件 I/O）的，可安全被任意脚本 import。
"""
import json
import os
import time
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
SUBS_FILE = os.path.join(BASE, "subscriptions.json")

TIER_EMOJI = {"high": "🔴", "mid": "🟡", "low": "⚪"}
TYPE_LABEL = {"revoked": "矿机被撤销", "counterexample": "新反例登记", "stopped": "矿机停挖"}

# 处理器合约地址 → 显示名
PROCESSORS = {
    "0x1f5cb4aeae1807bf60c3b9c0d8adbcc14e91f12c": "Behemoth",
    "0xb1024b89886b9a34aa4ff5f31c411d708b20a14c": "TapeOut",
    "0xf4412c52ec3dd7fca5f518b6662f77b02bde28e": "RefBench",
}


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


def load_json(path, default):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return default


def save_json(path, obj):
    json.dump(obj, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def active_subscribers(subs, now=None):
    """过滤出未过期的订阅者（到期自动失效）"""
    now = now or time.time()
    out = []
    for s in subs.get("subscribers", []):
        exp = s.get("expiry")
        if exp is None or exp > now:
            out.append(s)
    return out


def match(alert, filters):
    """判断一条告警是否命中订阅者的过滤条件。空过滤 = 全部命中。"""
    procs = filters.get("processors", [])
    tasks = filters.get("tasks", [])
    types = filters.get("types", [])
    title = alert.get("title", "") + " " + alert.get("detail", "")
    if procs and not any(p in title for p in procs):
        return False
    if tasks and not any(f"题 #{t}" in title or f"task {t}" in title for t in tasks):
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
    return (f"{TIER_EMOJI.get(alert.get('tier'), '⚪')} {alert.get('title', '')}\n"
            f"{alert.get('detail', '')}\n"
            f"影响：{alert.get('impact', '')}\n"
            f"交易：https://bscscan.com/tx/{alert.get('tx', '')}")


def push_alert(alert, subscribers, tg_token):
    """把一条告警推给所有命中订阅者。返回「实际推送成功」的渠道数。"""
    text = format_alert(alert)
    pushed = 0
    for sub in subscribers:
        if not match(alert, sub.get("filters", {})):
            continue
        for ch in sub.get("channels", []):
            try:
                if ch == "telegram" and tg_token and sub.get("telegram_chat_id"):
                    send_telegram(tg_token, sub["telegram_chat_id"], text)
                    pushed += 1
                    print(f"  [推送] telegram → {sub.get('id')}")
                elif ch == "webhook" and sub.get("webhook_url"):
                    send_webhook(sub["webhook_url"], alert)
                    pushed += 1
                    print(f"  [推送] webhook → {sub.get('id')}")
                elif ch == "tapesend":
                    print(f"  [待接] tapesend 渠道 → {sub.get('id')}")
                else:
                    print(f"  [跳过] {sub.get('id')} 的渠道 {ch} 未配置")
            except Exception as e:
                print(f"  [失败] {sub.get('id')}/{ch}: {e}")
    return pushed
