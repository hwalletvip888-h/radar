#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""被撤销电路的爆炸半径：谁从这些电路领走了 BEM。

读 real_chain_data.json 里 12 台被撤销矿机的 key，扫 PodMining 的 Claimed 事件
（topic1 = key），聚合出「每个地址从被攻破电路领走了多少 BEM」。

纯 stdlib。输出写文件，避免 GBK 控制台问题。
"""
import json, time, urllib.request

POD = "0x7E2E0DC66a3bD9103E69b766afA62d9f7b697b46"
FROM_BLOCK = 117234441
CLAIMED_T0 = "0x0508a8b4117d9a7b3d8f5895f6413e61b4f9a2df35afbfb41e78d0ecfff1843f"
RPCS = ["https://tapeout.net/rpc", "https://bsc-dataseed.bnbchain.org/", "https://bsc-dataseed.binance.org/"]
CHUNK = 50000
PROGRESS = r"C:\Users\CF\Desktop\okx-sentinel\deweb-search\blast_progress.txt"


def p(msg):
    with open(PROGRESS, "a", encoding="utf-8") as f:
        f.write(msg + "\n")
    print(msg, flush=True)


def rpc(method, params):
    err = None
    for rpc_url in RPCS:
        for a in range(3):
            try:
                body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
                req = urllib.request.Request(rpc_url, data=body,
                                             headers={"Content-Type": "application/json", "User-Agent": "tapeout-sentinel/1.0"})
                with urllib.request.urlopen(req, timeout=60) as r:
                    j = json.loads(r.read().decode())
                if "error" in j:
                    raise RuntimeError(str(j["error"]))
                return j["result"]
            except Exception as e:
                err = e
                time.sleep(1.5 * (a + 1))
    raise RuntimeError(err)


def main():
    import os
    if os.path.exists(PROGRESS):
        os.remove(PROGRESS)
    d = json.load(open(r"real_chain_data.json", encoding="utf-8"))
    miners = d["miners"]
    keys = sorted(miners.keys())
    p(f"querying Claimed for {len(keys)} revoked keys")

    latest = int(rpc("eth_blockNumber", []), 16)
    all_logs = []
    cur = FROM_BLOCK
    while cur <= latest:
        to_b = min(cur + CHUNK - 1, latest)
        try:
            logs = rpc("eth_getLogs", [{
                "address": POD, "fromBlock": hex(cur), "toBlock": hex(to_b),
                "topics": [CLAIMED_T0, keys],
            }])
            all_logs.extend(logs)
        except Exception as e:
            p(f"  chunk {cur}-{to_b} failed: {e}")
            time.sleep(2)
            continue
        if (cur - FROM_BLOCK) % 4000000 < CHUNK:
            p(f"  scanned to {to_b} ({len(all_logs)} claimed logs)")
        cur = to_b + 1

    p(f"total claimed logs: {len(all_logs)}")

    # 聚合：key -> {address -> amount}
    # Claimed(bytes32 indexed key, address indexed to, uint256 amount)
    #   topic1 = key, topic2 = to, data[0] = amount
    def addr(t):
        return "0x" + t[-40:]
    by_key = {}
    for l in all_logs:
        topics = l["topics"]
        key = topics[1]
        to = addr(topics[2]) if len(topics) > 2 else None
        data = l["data"][2:] if l["data"].startswith("0x") else l["data"]
        words = [data[i:i+64] for i in range(0, len(data), 64)]
        amount = int(words[0], 16) if words else 0
        by_key.setdefault(key, {})
        by_key[key][to] = by_key[key].get(to, 0) + amount

    # 与矿机身份合并
    out = {"total_frozen_bem": sum(m["debt"] for m in miners.values()) / 1e8,
           "circuits": []}
    for key in keys:
        m = miners[key]
        claims = {a: amt / 1e8 for a, amt in by_key.get(key, {}).items()}
        out["circuits"].append({
            "circuits": m["circuits"], "circuitId": m["circuitId"], "taskId": m["taskId"],
            "gateCount": m["gateCount"], "debt_bem": m["debt"] / 1e8,
            "registrant": m["registrant"], "claimed_bem": claims,
            "total_claimed_bem": round(sum(claims.values()), 4),
        })

    json.dump(out, open("blast_radius.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    p(f"done. frozen={out['total_frozen_bem']} BEM, circuits={len(out['circuits'])}")
    for c in out["circuits"]:
        p(f"  #{c['circuitId']} debt={c['debt_bem']:.2f} claimed={c['total_claimed_bem']:.2f} to {len(c['claimed_bem'])} addrs")


if __name__ == "__main__":
    main()
