#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""海豚Radar · 服务配置（唯一真相源）。

合约地址、RPC、事件 topic0、处理器名、评分模型权重，全部集中在这里，
其他模块（db/ingest/rate/alert/api）都从这 import，不再各自硬编码。
"""
import os

BASE = os.path.dirname(os.path.abspath(__file__))   # service/
ROOT = os.path.dirname(BASE)                        # deweb-search/
DATA_DIR = os.path.join(ROOT, "data")
DB_PATH = os.path.join(DATA_DIR, "radar.db")

# ── 链上 ──────────────────────────────────────────
POD = "0x7E2E0DC66a3bD9103E69b766afA62d9f7b697b46"   # PodMining 挖矿合约（BNB Chain）
FROM_BLOCK = 117234441                              # PodMining 部署块
GETMINER_SEL = "0x0527edc2"                         # getMiner(bytes32)

RPCS = [
    "https://bsc.publicnode.com",
    "https://1rpc.io/bnb",
    "https://bsc-dataseed.bnbchain.org/",
    "https://bsc-dataseed.binance.org/",
    "https://tapeout.net/rpc",   # 殿后：只允许 0-50 块区间
]

# 事件 topic0（已用 cast keccak 实测）
TOPICS = {
    "0xe52b422ce6b3cd73243c813dcbc499543bb477dd997c5d177b52c03562347ce5": "Revoked",
    "0x46ff8dc9a41ea4f2cc01bb124e2fc899797dbfa40dca6f4310aa69e9cfd2f3a2": "CounterexampleAdded",
    "0xc167316d53fbdff5ab2c8e45514426acd104c84efb1e239fe4b517ebb32ba88e": "Stopped",
    "0x687eb3f2eb7f9e2f33de282fee110bc0bcadb9c0dc5ffd2f7e27d440952e1549": "Demoted",
}

# 处理器合约地址 → 显示名
PROCESSORS = {
    "0x1f5cb4aeae1807bf60c3b9c0d8adbcc14e91f12c": "Behemoth",
    "0xb1024b89886b9a34aa4ff5f31c411d708b20a14c": "TapeOut",
    "0xf4412c52ec3dd7fca5f518b6662f77b02bde28e": "RefBench",
}

# ── 评分模型（V3，与旧 rating.py 对齐）────────────
MINER_COUNT = 20567  # PodMining minerCount()，全网矿机总数
MODEL = {
    "version": "v3",
    "score_range": "0-100（越高越安全）",
    "weights": {
        "revoked": 0,       # 撤销 → 0 分
        "demoted": 75,      # 被夺最优 → 75 分
        "stopped": 60,      # 停挖 → 60 分
        "healthy": 100,     # 正常 → 100 分
    },
    "grades": [(90, "A"), (75, "B"), (60, "C"), (40, "D"), (0, "F")],
}

# ── 调度 ──────────────────────────────────────────
POLL_INTERVAL = 120   # 增量扫链间隔（秒）
API_HOST = "127.0.0.1"
API_PORT = 8900

# ── 扫链 chunk ────────────────────────────────────
CHUNK = 5000         # 首选块区间（公共 RPC 普遍支持）
CHUNK_MIN = 50       # 下限（tapeout.net 只允许 0-50 块）
