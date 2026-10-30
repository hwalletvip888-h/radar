#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TapeOut 链上安全数据提取器。

从 PodMining 合约读取真实事件（Revoked / CounterexampleAdded / Stopped /
Demoted / Claimed），解码后 enriched 矿机身份，输出真实链上数据。

纯 stdlib，无第三方依赖。输出写 JSON 文件（避免 Windows GBK 控制台问题）。
"""
import json
import time
import urllib.request
import urllib.error

POD = "0x7E2E0DC66a3bD9103E69b766afA62d9f7b697b46"
FROM_BLOCK = 117234441  # PodMining 部署块（pod-mainnet.json fromBlock）

# 事件 topic0（已用 cast keccak 实测）
# 只扫安全相关事件（Revoked/CounterexampleAdded/Stopped/Demoted），
# Started/Claimed 数量庞大（~20567 条），用聚合统计 + getMiner 采样替代。
TOPICS = {
    "0xe52b422ce6b3cd73243c813dcbc499543bb477dd997c5d177b52c03562347ce5": "Revoked",
    "0x46ff8dc9a41ea4f2cc01bb124e2fc899797dbfa40dca6f4310aa69e9cfd2f3a2": "CounterexampleAdded",
    "0xc167316d53fbdff5ab2c8e45514426acd104c84efb1e239fe4b517ebb32ba88e": "Stopped",
    "0x687eb3f2eb7f9e2f33de282fee110bc0bcadb9c0dc5ffd2f7e27d440952e1549": "Demoted",
}

RPCS = [
    "https://tapeout.net/rpc",
    "https://bsc-dataseed.bnbchain.org/",
    "https://bsc-dataseed.binance.org/",
    "https://bsc.publicnode.com",
    "https://1rpc.io/bnb",
]

PROGRESS_FILE = r"C:\Users\CF\Desktop\okx-sentinel\deweb-search\extract_progress.txt"


def progress(msg):
    with open(PROGRESS_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")
    print(msg, flush=True)

CHUNK = 50000
GETMINER_SEL = "0x0527edc2"  # getMiner(bytes32)


def rpc_call(method, params, rpc):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(
        rpc, data=body, headers={"Content-Type": "application/json", "User-Agent": "tapeout-sentinel/1.0"}
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def rpc_call_rotating(method, params):
    err = None
    for rpc in RPCS:
        for attempt in range(3):
            try:
                res = rpc_call(method, params, rpc)
                if "error" in res:
                    raise RuntimeError(str(res["error"]))
                return res["result"]
            except Exception as e:
                err = e
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"all RPCs failed: {err}")


def get_logs(from_b, to_b):
    params = [{
        "address": POD,
        "fromBlock": hex(from_b),
        "toBlock": hex(to_b),
        "topics": [list(TOPICS.keys())],
    }]
    return rpc_call_rotating("eth_getLogs", params)


def get_latest_block():
    return int(rpc_call_rotating("eth_blockNumber", []), 16)


def decode_address(topic):
    """topic 是 32 字节 hex，取低 20 字节为地址。"""
    return "0x" + topic[-40:]


def decode_uint(word):
    return int(word, 16)


def abi_words(data):
    """把 ABI data hex 切成 32 字节 word 列表。"""
    if not data or data == "0x":
        return []
    h = data[2:] if data.startswith("0x") else data
    return [h[i:i + 64] for i in range(0, len(h), 64)]


def decode_log(log):
    t0 = log["topics"][0]
    name = TOPICS.get(t0, "Unknown")
    out = {"event": name, "block": int(log["blockNumber"], 16),
           "tx": log["transactionHash"], "logIndex": int(log["logIndex"], 16)}
    topics = log["topics"]
    data = abi_words(log.get("data", "0x"))

    if name == "Revoked":
        out["key"] = topics[1]
        out["challenger"] = decode_address(topics[2])
        out["vectorIndex"] = decode_uint(data[0]) if data else None
    elif name == "CounterexampleAdded":
        out["taskId"] = decode_uint(topics[1])
        out["circuits"] = decode_address(topics[2])
        out["circuitId"] = decode_uint(topics[3])
        out["by"] = decode_address(data[0]) if data else None
        out["added"] = bool(decode_uint(data[1])) if len(data) > 1 else None
    elif name == "Stopped":
        out["key"] = topics[1]
        out["by"] = decode_address(topics[2])
    elif name == "Demoted":
        out["key"] = topics[1]
        out["circuits"] = decode_address(topics[2])
        out["circuitId"] = decode_uint(data[0]) if data else None
        out["taskId"] = decode_uint(data[1]) if len(data) > 1 else None
    elif name == "Claimed":
        out["key"] = topics[1]
        out["to"] = decode_address(topics[2])
        out["amount"] = decode_uint(data[0]) if data else None
    elif name == "Started":
        out["key"] = topics[1]
        out["circuits"] = decode_address(topics[2])
        out["circuitId"] = decode_uint(topics[3])
        if data:
            out["taskId"] = decode_uint(data[0])
            out["registrant"] = decode_address(data[1])
            out["bstar"] = decode_uint(data[2])
            out["bonus"] = decode_uint(data[3])
            out["optimal"] = bool(decode_uint(data[4]))
            out["verifWeight"] = decode_uint(data[5])
            out["unverWeight"] = decode_uint(data[6])
    return out


def get_miner(key):
    """调用 getMiner(bytes32) 并手动解码 22 字段 tuple。"""
    data = GETMINER_SEL + key[2:]
    res = rpc_call_rotating("eth_call", [{"to": POD, "data": data}, "latest"])
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
        "stateCount": decode_uint(w[4]),
        "depth": decode_uint(w[5]),
        "area": decode_uint(w[6]),
        "mult": decode_uint(w[7]),
        "since": decode_uint(w[8]),
        "status": decode_uint(w[9]),
        "registrant": "0x" + w[10][-40:],
        "nandBurn": decode_uint(w[11]),
        "latchBurn": decode_uint(w[12]),
        "bstar": decode_uint(w[13]),
        "bonus": decode_uint(w[14]),
        "optimal": bool(decode_uint(w[15])),
        "commitBlock": decode_uint(w[16]),
        "firstUnusedId": decode_uint(w[17]),
        "stopBlock": decode_uint(w[18]),
        "verifWeight": decode_uint(w[19]),
        "unverWeight": decode_uint(w[20]),
        "debt": decode_uint(w[21]),
    }


def main():
    try:
        import os
        if os.path.exists(PROGRESS_FILE):
            os.remove(PROGRESS_FILE)
    except Exception:
        pass
    latest = get_latest_block()
    progress(f"latest block: {latest}")

    all_logs = []
    cur = FROM_BLOCK
    while cur <= latest:
        to_b = min(cur + CHUNK - 1, latest)
        try:
            logs = get_logs(cur, to_b)
            all_logs.extend(logs)
        except Exception as e:
            progress(f"  chunk {cur}-{to_b} failed: {e}, retrying...")
            time.sleep(2)
            continue
        if (cur - FROM_BLOCK) % 2000000 < CHUNK:
            progress(f"  scanned to {to_b} ({len(all_logs)} logs so far)")
        cur = to_b + 1

    progress(f"total logs: {len(all_logs)}")
    decoded = [decode_log(l) for l in all_logs]

    # 按事件分类
    by_event = {}
    for d in decoded:
        by_event.setdefault(d["event"], []).append(d)

    result = {"latestBlock": latest, "counts": {k: len(v) for k, v in by_event.items()}, "events": decoded, "miners": {}}

    # 先把扫描结果落盘（避免 enrichment 阶段丢失扫描成果）
    with open("real_chain_data.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    progress(f"scanned done, saved. events: {result['counts']}")

    # 只对 Revoked 的 key 做 getMiner 富化（关键安全信号；Stopped/Demoted 已在事件里带 circuitId）
    miner_cache = {}
    rev_keys = {d["key"] for d in decoded if d["event"] == "Revoked" and "key" in d}
    progress(f"enriching {len(rev_keys)} revoked keys...")
    for i, key in enumerate(sorted(rev_keys)):
        try:
            m = get_miner(key)
            if m:
                miner_cache[key] = m
        except Exception as e:
            progress(f"  getMiner {key[:18]}... failed: {e}")
        if (i + 1) % 20 == 0:
            progress(f"  enriched {i+1}/{len(rev_keys)}")
    result["miners"] = miner_cache

    with open("real_chain_data.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)

    # 摘要
    progress("== summary ==")
    for k, v in result["counts"].items():
        progress(f"  {k}: {v}")
    progress(f"  enriched revoked miners: {len(miner_cache)}")
    revs = by_event.get("Revoked", [])
    progress(f"  sample Revoked keys: {[r['key'][:18]+'...' for r in revs[:5]]}")


if __name__ == "__main__":
    main()
