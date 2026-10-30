#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从真实链上数据构建 TapeOut 安全图谱。

读 chain_extract.py 产出的 real_chain_data.json（真实 Revoked / Started /
CounterexampleAdded / Claimed 事件 + getMiner 富化），构建与 graph.json 同 schema
的真实对象图，输出 graph_onchain.json。

真实安全机制：challenge(反例举证) → Revoked(永久撤销)，就是「电路被攻破」的链上信号。
"""
import json

SRC = r"C:\Users\CF\Desktop\okx-sentinel\deweb-search\real_chain_data.json"
OUT = r"C:\Users\CF\Desktop\okx-sentinel\deweb-search\graph_onchain.json"

# 处理器：地址 -> (编号, 名字, 挖矿系数)
PROCESSORS = {
    "0x1F5Cb4aeaE1807Bf60c3b9C0D8aDBCC14e91f12C": ("1", "Behemoth", 6),
    "0xb1024b89886B9a34Aa4ff5F31C411D708b20a14C": ("30", "TapeOut", 1),
    "0xF4412C52ec3DDf7CAf5f518B6662F77B02Bde28E": ("ref", "RefBench", 1),
    "0x50A994E71615474b55559fF4F500928fbc339DD9": ("0", "Genesis CPU", 0),
}
ADDR_TO_PROC = {a.lower(): v for a, v in PROCESSORS.items()}

def proc_name(addr):
    if not addr:
        return None
    a = addr.lower()
    if a in ADDR_TO_PROC:
        return ADDR_TO_PROC[a]
    return (None, addr[:10] + "…", None)

def main():
    d = json.load(open(SRC, encoding="utf-8"))
    events = d.get("events", [])
    miners = d.get("miners", {})

    nodes, edges = {}, []
    def add_node(type_, name, **props):
        key = f"{type_}:{name}"
        if key not in nodes:
            nodes[key] = {"id": key, "type": type_, "name": name, **props}
        return key
    def add_edge(frm, to, typ):
        e = {"from": frm, "to": to, "type": typ}
        if e not in edges:
            edges.append(e)

    # 处理器 + BEM 固定节点
    for addr, (num, name, mult) in PROCESSORS.items():
        add_node("processor", name, num=num, address=addr, multiplier=mult)
    bem = add_node("token", "BEM", symbol="BEM", decimals=8, cap=21_000_000)

    # 事件分类
    revoked = [e for e in events if e["event"] == "Revoked"]
    cex = [e for e in events if e["event"] == "CounterexampleAdded"]
    started = [e for e in events if e["event"] == "Started"]
    stopped = [e for e in events if e["event"] == "Stopped"]
    claimed = [e for e in events if e["event"] == "Claimed"]
    demoted = [e for e in events if e["event"] == "Demoted"]

    # 已撤销电路（核心安全信号）
    revoked_circuits = []
    for r in revoked:
        m = miners.get(r["key"])
        circ_id = m["circuitId"] if m else None
        proc = proc_name(m["circuits"]) if m else (None, None, None)
        cnum = f"#{proc[1]}·{circ_id}" if proc and circ_id is not None else r["key"][:10]
        cname = f"Circuit {proc[1]} #{circ_id}" if circ_id is not None else f"Circuit {r['key'][:8]}…"
        debt = (m or {}).get("debt", 0)
        cnode = add_node(
            "circuit", cname,
            num=circ_id, processor=proc[1], processorAddr=(m or {}).get("circuits"),
            taskId=(m or {}).get("taskId"), gateCount=(m or {}).get("gateCount"),
            status="revoked", verification="compromised", state="revoked",
            reason=f"链上反例举证成立：第 {r['vectorIndex']} 号测试向量算出错，永久撤销",
            challenger=r["challenger"], vectorIndex=r["vectorIndex"],
            block=r["block"], tx=r["tx"],
            debt=debt, debtBEM=round(debt / 1e8, 4),
            registrant=(m or {}).get("registrant"), bstar=(m or {}).get("bstar"),
            verifWeight=(m or {}).get("verifWeight"),
        )
        revoked_circuits.append(cnode)
        # 电路 → 处理器
        if proc[1]:
            add_edge(cnode, add_node("processor", proc[1], num=proc[0], multiplier=proc[2]), "taped_on")
        # 电路 → BEM（曾是矿机，挖矿产 BEM）
        add_edge(cnode, bem, "mines")
        # 挑战者（安全研究员）
        challenger = add_node("person", r["challenger"], address=r["challenger"], role="challenger")
        add_edge(challenger, cnode, "revealed")
        # 矿主（失去这台矿机的地址）
        if (m or {}).get("registrant"):
            owner = add_node("person", m["registrant"], address=m["registrant"], role="miner_owner")
            add_edge(cnode, owner, "operated_by")

    # 反例登记（挑战者给题目补新反例向量）
    for c in cex:
        proc = proc_name(c.get("circuits"))
        if proc[1]:
            add_node("processor", proc[1], num=proc[0], multiplier=proc[2])
        cname = f"Circuit {proc[1] if proc[1] else '?'} #{c.get('circuitId')}"
        cnode = add_node("circuit", cname, num=c.get("circuitId"), processor=proc[1],
                         taskId=c.get("taskId"), status="counterexample", verification="verified")
        if proc[1]:
            add_edge(cnode, add_node("processor", proc[1], num=proc[0], multiplier=proc[2]), "taped_on")
        add_edge(add_node("person", c.get("by"), address=c.get("by"), role="challenger"), cnode, "revealed")

    # 挖矿中/停挖的电路（矿机）
    mining_keys = {}
    for s in started:
        proc = proc_name(s.get("circuits"))
        cname = f"Circuit {proc[1] if proc[1] else '?'} #{s.get('circuitId')}"
        cnode = add_node("circuit", cname, num=s.get("circuitId"), processor=proc[1],
                         taskId=s.get("taskId"), status="mining", verification="verified",
                         verifWeight=s.get("verifWeight"), bstar=s.get("bstar"),
                         registrant=s.get("registrant"), block=s["block"])
        if proc[1]:
            add_edge(cnode, add_node("processor", proc[1], num=proc[0], multiplier=proc[2]), "taped_on")
        add_edge(cnode, bem, "mines")
        mining_keys[s.get("key")] = cnode

    for s in stopped:
        m = miners.get(s.get("key"))
        if not m:
            continue
        proc = proc_name(m.get("circuits"))
        cname = f"Circuit {proc[1] if proc[1] else '?'} #{m.get('circuitId')}"
        add_node("circuit", cname, num=m.get("circuitId"), processor=proc[1],
                 taskId=m.get("taskId"), status="stopped")

    # Demoted（被夺最优首创）只是挖矿生命周期事件，不是安全事件；
    # 保留统计计数即可，不逐个建节点，避免图谱被稀释。
    demoted_count = len(demoted)

    # BEM 领取（矿机 → BEM 流转）
    claim_addrs = {}
    for cl in claimed:
        claim_addrs[cl["to"]] = claim_addrs.get(cl["to"], 0) + cl.get("amount", 0)

    # 爆炸半径：加载 blast_radius.json，把「已领走 BEM 的下游地址」接进图
    try:
        br = json.load(open(r"C:\Users\CF\Desktop\okx-sentinel\deweb-search\blast_radius.json", encoding="utf-8"))
        br_by_id = {(c["circuits"].lower(), c["circuitId"]): c for c in br.get("circuits", [])}
        total_claimed = 0.0
        for n in list(nodes.values()):
            if n["type"] == "circuit" and n.get("status") == "revoked":
                key = ((n.get("processorAddr") or "").lower(), n.get("num"))
                brc = br_by_id.get(key)
                if not brc:
                    continue
                n["claimedBEM"] = brc.get("total_claimed_bem", 0)
                total_claimed += n["claimedBEM"]
                for addr, amt in (brc.get("claimed_bem") or {}).items():
                    if amt <= 0:
                        continue
                    holder = add_node("person", addr, address=addr, role="bem_holder")
                    add_edge(n["id"], holder, "paid_bem_to")
    except Exception as e:
        print(f"  (blast_radius.json not integrated: {e})")

    # BEM 二级流转：加载 bem_flow.json，把 DEX 池 + 流向接进图
    POOL = "0x2f5ec19ab0583d3fcd9bcbcd9ab416d2858eea38"  # PancakeSwap BEM/USDT V3 池（0x2f5e…ea38）
    try:
        bf = json.load(open(r"C:\Users\CF\Desktop\okx-sentinel\deweb-search\bem_flow.json", encoding="utf-8"))
        flow_total = bf.get("total_traced_bem", 0)
        pool_amt = 0.0
        top_recipients = []
        for r in bf.get("recipients", []):
            top_recipients.append({"address": r["address"], "bem": r["bem"]})
            if r["address"].lower() == POOL:
                pool_amt = r["bem"]
        # DEX 池节点：BEM 流入的「公共池」，坏币在此混入全网
        pool_node = add_node("site", "PancakeSwap BEM/USDT 池", address=POOL, category="dex",
                             receivedBEM=round(pool_amt, 2))
        add_edge(bem, pool_node, "pooled_into")
    except Exception as e:
        flow_total, pool_amt, top_recipients, pool_node = 0.0, 0.0, [], None
        print(f"  (bem_flow.json not integrated: {e})")

    out = {
        "nodes": list(nodes.values()),
        "edges": edges,
        "meta": {
            "latestBlock": d.get("latestBlock"),
            "eventCounts": d.get("counts"),
            "revoked_circuits": len(revoked_circuits),
            "demoted_count": demoted_count,
            "total_frozen_bem": round(sum(n.get("debt", 0) for n in nodes.values()
                                            if n["type"] == "circuit" and n.get("status") == "revoked") / 1e8, 2),
            "bem_flow": {
                "total_traced_bem": round(flow_total, 2),
                "pool_bem": round(pool_amt, 2),
                "recipient_count": len(top_recipients),
            },
            "revoked_details": [{
                "circuit": n["name"], "processor": n.get("processor"),
                "taskId": n.get("taskId"), "gateCount": n.get("gateCount"),
                "vectorIndex": n.get("vectorIndex"), "challenger": n.get("challenger"),
                "tx": n.get("tx"),
            } for n in nodes.values() if n["type"] == "circuit" and n.get("status") == "revoked"],
        },
    }
    out["stats"] = {t: sum(1 for n in nodes.values() if n["type"] == t)
                    for t in ["processor", "circuit", "token", "person", "miner", "site"]}
    out["stats"]["edges"] = len(edges)
    out["stats"]["revoked_circuits"] = len(revoked_circuits)

    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("graph_onchain.json written")
    for k, v in out["stats"].items():
        print(f"  {k}: {v}")
    print("  revoked circuits:")
    for rd in out["meta"]["revoked_details"]:
        print(f"    - {rd['circuit']} (task {rd['taskId']}, {rd['gateCount']} gates) vector #{rd['vectorIndex']} by {rd['challenger'][:10]}…")

if __name__ == "__main__":
    main()
