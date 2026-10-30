#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TapeOut 安全警报推送引擎（轮询分发）。

读 watcher.py 产出的 alerts.json，按 subscriptions.json 里的订阅配置，
把告警分发给订阅者的渠道（Telegram / Webhook）。到期订阅自动失效。

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
        "expiry": 1750000000,
        "filters": {"processors": [], "tasks": [], "types": []}   // 空 = 全部
      }
    ]
  }

Telegram bot token 通过环境变量 TELEGRAM_BOT_TOKEN 或 .bot_token 提供。
状态存 notifier_state.json（记住哪些告警已推过，避免重复）。
共享工具在 common.py。
"""
import os
import sys
import time

from common import (BASE, SUBS_FILE, load_token, load_json, save_json,
                    active_subscribers, push_alert)

ALERTS_FILE = os.path.join(BASE, "alerts.json")
STATE_FILE = os.path.join(BASE, "notifier_state.json")


def main():
    loop = int(sys.argv[sys.argv.index("--loop") + 1]) if "--loop" in sys.argv else None
    tg_token = load_token()

    while True:
        cfg = load_json(SUBS_FILE, {"subscribers": []})
        alerts = load_json(ALERTS_FILE, [])
        state = load_json(STATE_FILE, {"sent": []})
        sent = set(state.get("sent", []))

        subscribers = active_subscribers(cfg)  # 过滤过期订阅
        total_pushed = 0
        for alert in alerts:
            key = alert.get("tx") or (alert.get("title") + str(alert.get("ts")))
            if key in sent:
                continue
            total_pushed += push_alert(alert, subscribers, tg_token)
            sent.add(key)

        state["sent"] = sorted(sent)[-5000:]
        save_json(STATE_FILE, state)
        print(f"[notifier] 本轮处理 {len(alerts)} 条告警，活跃订阅 {len(subscribers)} 个，新推送 {total_pushed} 次")

        if loop is None:
            break
        time.sleep(loop)


if __name__ == "__main__":
    main()
