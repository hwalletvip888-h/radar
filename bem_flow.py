#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BEM 二级流转污染追踪。

从 9 个「领走过坏矿机 BEM」的地址出发，扫 BEM 的 Transfer 事件（from ∈ 这些地址），
看这些「坏币」流向了哪里（DEX 池 / 其他持有者 / 黑洞地址）。

纯 stdlib。输出写文件。
"""
import json, time, urllib.request

BEM = "0x5ce033B2bFCa3Af30b3e8C8457DeaF776A8b695a"
FROM_BLOCK = 118000000  # 最早的 Revoked 块（118122256）之前，转账只发生在领币之后
TRANSFER_T0 = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"  # Transfer(address,address,uint256)
RPCS = ["https://tapeout.net/rpc", "https://bsc-dataseed.bnbchain.org/", "https://bsc-dataseed.binance.org/"]
CHUNK = 50000
PROGRESS = r"C:\Users\CF\Desktop\okx-sentinel\deweb-search\bem_flow_progress.txt"

# 已知地址标签
KNOWN = {
    "0x000000000000000000000000000000000000dead": "黑洞地址(销毁)",
    "0x5ce033b2bfca3af30b3e8c8457deaf776a8b695a": "BEM 合约",
    "0x7e2e0dc66a3bd9103e69b766afa62d9f7b697b46": "PodMining",
}


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
                time.sleep(6 * (a + 1))
    raise RuntimeError(err)


def main():
    import os
    if os.path.exists(PROGRESS):
        os.remove(PROGRESS)
    br = json.load(open(r"blast_radius.json", encoding="utf-8"))
    sources = set()
    for c in br["circuits"]:
        for addr, amt in c["claimed_bem"].items():
            if amt > 0:
                # topic 必须是 32 字节，地址要零填充到 64 hex
                sources.add("0x" + "0" * 24 + addr[2:].lower())
    p(f"tracing BEM outflow from {len(sources)} source addresses")

    latest = int(rpc("eth_blockNumber", []), 16)
    all_logs = []
    cur = FROM_BLOCK
    while cur <= latest:
        to_b = min(cur + CHUNK - 1, latest)
        try:
            logs = rpc("eth_getLogs", [{
                "address": BEM, "fromBlock": hex(cur), "toBlock": hex(to_b),
                "topics": [TRANSFER_T0, list(sources)],
            }])
            all_logs.extend(logs)
        except Exception as e:
            p(f"  chunk {cur}-{to_b} failed: {e}")
            time.sleep(15)
            continue
        if (cur - FROM_BLOCK) % 4000000 < CHUNK:
            p(f"  scanned to {to_b} ({len(all_logs)} transfers)")
        cur = to_b + 1

    p(f"total outflow transfers: {len(all_logs)}")

    def addr(t):
        return "0x" + t[-40:]

    # 聚合：from -> to -> amount
    flow = {}
    for l in all_logs:
        topics = l["topics"]
        frm = addr(topics[1])
        to = addr(topics[2])
        data = l["data"][2:] if l["data"].startswith("0x") else l["data"]
        amount = int(data, 16) if data else 0
        flow.setdefault(frm, {})
        flow[frm][to] = flow[frm].get(to, 0) + amount

    # 汇总每个 recipient 收到的坏币总量
    recipients = {}
    for frm, tos in flow.items():
        for to, amt in tos.items():
            recipients[to] = recipients.get(to, 0) + amt

    out = {
        "sources": sorted(sources),
        "total_traced_bem": sum(recipients.values()) / 1e8,
        "recipients": [],
    }
    for to, amt in sorted(recipients.items(), key=lambda x: -x[1]):
        label = KNOWN.get(to, "")
        out["recipients"].append({
            "address": to, "bem": amt / 1e8, "label": label,
            "is_dead": to.endswith("dead"), "is_pool": "pool" in label.lower(),
        })

    json.dump(out, open("bem_flow.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    p(f"done. traced={out['total_traced_bem']:.4f} BEM to {len(recipients)} recipients")
    for r in out["recipients"][:15]:
        p(f"  {r['address'][:12]}..  {r['bem']:.4f} BEM  {r['label']}")


if __name__ == "__main__":
    main()
