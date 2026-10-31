#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""海豚Radar · 服务入口。

一次性：建库 → seed 历史数据（幂等）→ 补扫到最新块 → 首轮评级 → 起 API + 后台调度线程。

启动（在 deweb-search 目录下）：
  python -m service.run

后台调度线程每 POLL_INTERVAL 秒：增量扫链 → 评级 → 告警推送。
API 默认监听 127.0.0.1:8900（config.API_HOST/API_PORT）。
"""
import os
import sys
import threading
import time

# 让 `import service.*` 和 `import common` 都可用（从任意 cwd 启动）
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import uvicorn

from service import db, ingest, rate, alert, api
from service.config import POLL_INTERVAL, API_HOST, API_PORT


def run_pipeline():
    """调度线程主循环：seed → 补扫 → 首轮评级 → 循环（扫链→评级→告警）。"""
    c = db.connect()

    # 启动各步骤失败都不致命：保证线程总能进到循环里，下一轮自动重试
    try:
        ingest.bootstrap(c)         # 从旧 JSON seed 历史事件 + 矿机（幂等）
    except Exception as e:
        print(f"[run] seed 失败: {e}")
    try:
        ingest.migrate_subscriptions(c)  # 旧 subscriptions.json → 表（幂等）
    except Exception as e:
        print(f"[run] 订阅迁移失败: {e}")
    try:
        ingest.scan_incremental(c)  # lastBlock → 当前最新块（补上 seed 之后的 gap）
    except Exception as e:
        print(f"[run] 首轮扫链失败（进循环后重试）: {e}")

    # 历史 + 补扫的 gap 都不告警：把告警游标一次性拉到当前块
    if db.get_meta(c, "alertCursor") is None:
        db.set_meta(c, "alertCursor", db.get_meta(c, "lastBlock") or 0)
        c.commit()

    try:
        s = rate.rate_all(c)
        print(f"[run] 初始评级完成：撤销 {s['revoked']} / 夺最优 {s['demoted']} "
              f"/ 停挖 {s['stopped_rated']}(+{s['stopped_unmapped']}未映射) / 健康估算 ~{s['healthy_estimate']}")
    except Exception as e:
        print(f"[run] 初始评级失败: {e}")

    while True:
        time.sleep(POLL_INTERVAL)
        try:
            n = ingest.scan_incremental(c)
            if n:
                print(f"[run] 新增 {n} 条事件")
        except Exception as e:
            print(f"[run] 扫链失败（下轮重试）: {e}")
        try:
            rate.rate_all(c)
        except Exception as e:
            print(f"[run] 评级失败: {e}")
        try:
            k = alert.process_new_alerts(c)
            if k:
                print(f"[run] 新告警 {k} 条")
        except Exception as e:
            print(f"[run] 告警失败: {e}")


def main():
    db.init_db()
    t = threading.Thread(target=run_pipeline, daemon=True)
    t.start()
    uvicorn.run(api.app, host=API_HOST, port=API_PORT, log_level="info")


if __name__ == "__main__":
    main()
