#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""海豚Radar · Telegram bot 处理器。

处理用户的 /start 深链，把「钱包地址 ↔ chat_id ↔ 套餐」自动记进 subscriptions.json。

深链格式：https://t.me/DR_xiaoxi_bot?start=<钱包地址>_<tier>
  tier: free / pro / enterprise

用法：python bot.py（长轮询，常驻）
"""
import json
import os
import sys
import time
import urllib.request

BASE = r"C:\Users\CF\Desktop\okx-sentinel\deweb-search"
TOKEN_FILE = os.path.join(BASE, ".bot_token")
SUBS_FILE = os.path.join(BASE, "subscriptions.json")
BIND_FILE = os.path.join(BASE, "telegram_bindings.json")

TIER_LABEL = {"free": "免费", "pro": "Pro", "enterprise": "企业"}


def tg(method, **params):
    token = open(TOKEN_FILE, encoding="utf-8").read().strip()
    url = f"https://api.telegram.org/bot{token}/{method}"
    body = json.dumps(params).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def load_subs():
    try:
        return json.load(open(SUBS_FILE, encoding="utf-8"))
    except Exception:
        return {"subscribers": []}


def save_subs(subs):
    json.dump(subs, open(SUBS_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def bind(address, tier, chat_id):
    """把 address + tier 绑定到 chat_id，写进 subscriptions.json"""
    subs = load_subs()
    # 移除同一 chat_id 的旧订阅
    subs["subscribers"] = [s for s in subs["subscribers"] if s.get("telegram_chat_id") != str(chat_id)]
    subs["subscribers"].append({
        "id": f"tg_{chat_id}",
        "address": address,
        "tier": tier,
        "channels": ["telegram"],
        "telegram_chat_id": str(chat_id),
        "expiry": int(time.time()) + 30 * 24 * 3600,  # 默认 30 天
        "filters": {"processors": [], "tasks": [], "types": ["revoked"]},
    })
    save_subs(subs)
    # 记录绑定历史
    binds = []
    if os.path.exists(BIND_FILE):
        binds = json.load(open(BIND_FILE, encoding="utf-8"))
    binds.append({"address": address, "tier": tier, "chat_id": str(chat_id), "ts": int(time.time())})
    json.dump(binds, open(BIND_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def main():
    offset = 0
    print("[bot] 海豚Radar bot 启动，长轮询 /start 深链…")
    while True:
        try:
            d = tg("getUpdates", offset=offset, timeout=30)
            for u in d.get("result", []):
                offset = u["update_id"] + 1
                msg = u.get("message", {})
                chat_id = msg.get("chat", {}).get("id")
                text = msg.get("text", "")
                if not chat_id or not text:
                    continue
                # /start <address>_<tier>
                if text.startswith("/start"):
                    parts = text.split()
                    payload = parts[1] if len(parts) > 1 else ""
                    if "_" in payload:
                        address, tier = payload.rsplit("_", 1)
                        if tier not in TIER_LABEL:
                            tier = "free"
                        bind(address.lower(), tier, chat_id)
                        tg("sendMessage", chat_id=chat_id,
                           text=f"✅ 已绑定海豚Radar订阅\n钱包：{address[:10]}…{address[-6:]}\n套餐：{TIER_LABEL[tier]}\n有效期：30 天\n\n之后有矿机被撤销/新反例，会第一时间推送到这里。")
                        print(f"[bot] 绑定 {address[:10]}… → chat {chat_id} ({TIER_LABEL[tier]})")
                    else:
                        tg("sendMessage", chat_id=chat_id,
                           text="👋 欢迎使用海豚Radar（DolphinRadar）\n\n请从我们的订阅页面点「绑定 Telegram」，会自动带上你的钱包地址完成绑定。\n直接发 /start 不带地址是没法绑定的哦。")
                else:
                    tg("sendMessage", chat_id=chat_id,
                       text="👋 我是海豚Radar的安全警报 bot。\n请从订阅页面点「绑定 Telegram」完成订阅绑定。")
        except KeyboardInterrupt:
            print("\n[bot] 停止")
            return
        except Exception as e:
            print(f"[bot] 错误: {e}")
            time.sleep(3)


if __name__ == "__main__":
    main()
