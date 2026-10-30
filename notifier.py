#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TapeOut 安全警报推送引擎。

读 watcher.py 产出的 alerts.json，按 subscriptions.json 里的订阅配置，
把告警分发给订阅者的渠道（Telegram / Webhook）。

用法：
  python notifier.py            # 把「未推送」的告警推一遍
  python notifier.py --loop 60  # 常驻，每 60 秒检查新告警并推送

订阅配置 subscriptions.json：
  {
    "subscribers": [
      {
        "id": "alice",
        "channels": ["telegram"],
        "telegram_chat_id": "123456789",
        "filters": {"processors": [], "tasks": [], "types": []}   // 空 = 全部
      }
    ]
  }

Telegram bot token 通过环境变量 TELEGRAM_BOT_TOKEN 提供。
状态存 notifier_state.json（记住哪些告警已推过，避免重复）。
"""
import json, os, time, sys, urllib.request

BASE = r"C:\Users\CF\Desktop\okx-sentinel\deweb-search"
SUBS_FILE = os.path.join(BASE, "subscriptions.json")
ALERTS_FILE = os.path.join(BASE, "alerts.json")
STATE_FILE = os.path.join(BASE, "notifier_state.json")

TIER_EMOJI = {"high": "🔴", "mid": "🟡", "low": "⚪"}
TYPE_LABEL = {"revoked": "矿机被撤销", "counterexample": "新反例登记"}


def load_json(path, default):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return default


def save_json(path, obj):
    json.dump(obj, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def match(alert, filters):
    """判断一条告警是否命中订阅者的过滤条件。空过滤 = 全部命中。"""
    procs = filters.get("processors", [])
    tasks = filters.get("tasks", [])
    types = filters.get("types", [])
    title = alert.get("title", "") + " " + alert.get("detail", "")
    # 处理器/题目从标题+详情里做关键词匹配（简单版）
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
    t = alert.get("type", "")
    title = alert.get("title", "")
    return (f"{TIER_EMOJI.get(alert.get('tier'), '⚪')} {title}\n"
            f"{alert.get('detail', '')}\n"
            f"影响：{alert.get('impact', '')}\n"
            f"交易：https://bscscan.com/tx/{alert.get('tx', '')}")


def main():
    loop = int(sys.argv[sys.argv.index("--loop") + 1]) if "--loop" in sys.argv else None
    tg_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")

    while True:
        cfg = load_json(SUBS_FILE, {"subscribers": []})
        alerts = load_json(ALERTS_FILE, [])
        state = load_json(STATE_FILE, {"sent": []})
        sent = set(state.get("sent", []))

        pushed = 0
        for alert in alerts:
            key = alert.get("tx") or (alert.get("title") + str(alert.get("ts")))
            if key in sent:
                continue
            text = format_alert(alert)
            for sub in cfg.get("subscribers", []):
                if not match(alert, sub.get("filters", {})):
                    continue
                for ch in sub.get("channels", []):
                    try:
                        if ch == "telegram" and tg_token and sub.get("telegram_chat_id"):
                            send_telegram(tg_token, sub["telegram_chat_id"], text)
                            print(f"[notifier] → telegram 推给 {sub['id']}: {alert['title']}")
                        elif ch == "webhook" and sub.get("webhook_url"):
                            send_webhook(sub["webhook_url"], alert)
                            print(f"[notifier] → webhook 推给 {sub['id']}")
                        elif ch == "tapesend":
                            print(f"[notifier] ⚠ tapesend 渠道待接（发到容器端点）: {sub['id']}")
                        else:
                            print(f"[notifier] 跳过 {sub['id']} 的渠道 {ch}（未配置 token/url）")
                    except Exception as e:
                        print(f"[notifier] 推送失败 {sub['id']}/{ch}: {e}")
                pushed += 1
            sent.add(key)

        state["sent"] = sorted(sent)[-5000:]
        save_json(STATE_FILE, state)
        print(f"[notifier] 本轮处理 {len(alerts)} 条告警，新推送 {pushed} 次")

        if loop is None:
            break
        time.sleep(loop)


if __name__ == "__main__":
    main()
