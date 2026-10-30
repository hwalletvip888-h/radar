#!/usr/bin/env python3
"""构建 TapeOut 关系追溯图 graph.json。
核心依赖链：Circuit → 站点 → 矿机 → BEM → DeWEB 应用。
关系：used_by(电路→站点) / operates(站点→矿机) / mines(矿机→BEM) /
      depends_on(站点→BEM) / hosts(容器→站点) / created_by(站点→人) / on_chain / category。
电路带 verification 状态（verified / compromised），供「漏洞影响传播」追溯。"""
import json, re

SRC = r"C:\Users\CF\Desktop\okx-sentinel\deweb-search\sites.json"
OUT = r"C:\Users\CF\Desktop\okx-sentinel\deweb-search\graph.json"

# TapeOut 自己的代币（才生成 depends_on 依赖边）；BNB/USDT/ETH 等外部计价币不算依赖
TAPE_TOKENS = ["BEM", "TAP", "TF"]
PEOPLE = {"Blonskr": "TapeOut 创始人", "TapeOut Labs": "官方团队"}

# 种子：已确认被攻破的电路 + 修复状态生命周期
# state: compromised(已确认坏) / fixing(修复中) / reverified(已修复重新验证) / migrated(下游已迁移)
COMPROMISED = {
    "279": {"reason": "真值表对拍不一致：存在一个隐藏输入组合，输出偏离参考实现",
            "state": "compromised"},
    "281": {"reason": "疑似后门：特定输入下可覆盖正常输出，绕过风控逻辑",
            "state": "reverified"},
}

def main():
    d = json.load(open(SRC, encoding="utf-8"))
    nodes, edges = {}, []
    def add_node(type_, name, **props):
        key = f"{type_}:{name}"
        if key not in nodes:
            nodes[key] = {"id": key, "type": type_, "name": name, **props}
        return key
    def add_edge(frm, to, typ):
        edges.append({"from": frm, "to": to, "type": typ})

    for s in d["sites"]:
        name, desc, chain = s["name"], s["desc"], s["chain"]
        site = add_node("site", name, desc=desc, chain=chain, category=s["category"], tape=s["tape"])
        add_edge(site, f"chain:{chain}", "on_chain")
        add_edge(site, f"cat:{s['category']}", "category")

        # 代币依赖（只算 TapeOut 自己的代币）
        for t in TAPE_TOKENS:
            if re.search(rf'\b{re.escape(t)}\b', desc):
                add_edge(site, add_node("token", t, symbol=t), "depends_on")
        # 电路：站点「使用」电路（依赖链上游）
        for m in re.finditer(r'(?:Circuit|电路)\s*#?\s*(\d+)', desc, re.I):
            cid = m.group(1)
            ver = "compromised" if cid in COMPROMISED else "verified"
            reason = COMPROMISED[cid]["reason"] if cid in COMPROMISED else None
            state = COMPROMISED[cid]["state"] if cid in COMPROMISED else "verified"
            circuit = add_node("circuit", f"Circuit #{cid}", num=cid, verification=ver, reason=reason, state=state)
            add_edge(circuit, site, "used_by")  # 电路 → 站点（站点用它）
        # 处理器
        for m in re.finditer(r'(?:Behemoth|处理器)\s*#?\s*(\d+)', desc, re.I):
            add_edge(site, add_node("processor", f"Processor #{m.group(1)}", num=m.group(1)), "mentions")
        # Agent
        if re.search(r'(AI\s*agent|agent\b|检察官|智能体)', desc, re.I):
            add_edge(site, add_node("agent", name), "mentions")
        # 容器 hosts
        for m in re.finditer(r'tape://([0-9.#]+)', desc):
            container = add_node("container", f"容器 {m.group(1)}", address=m.group(1))
            add_edge(container, site, "hosts")
        # 人 created_by
        for p, bio in PEOPLE.items():
            if p in desc:
                add_edge(site, add_node("person", p, bio=bio), "created_by")
        # 矿机：挖矿类站点 → 矿机节点，站点 operates 矿机，矿机 mines BEM
        if s["category"] == "mining" or re.search(r'(矿机|挖矿|算力|PoD|矿工)', desc):
            miner = add_node("miner", f"矿机·{name}", site_of=name)
            add_edge(site, miner, "operates")   # 站点 → 矿机
            add_edge(miner, add_node("token", "BEM", symbol="BEM"), "mines")  # 矿机 → BEM

    # 补 chain/category 节点 + 显式加入人
    for e in list(edges):
        if e["to"].startswith("chain:") or e["to"].startswith("cat:"):
            if e["to"] not in nodes:
                t, nm = e["to"].split(":", 1)
                nodes[e["to"]] = {"id": e["to"], "type": t, "name": nm}
    for p, bio in PEOPLE.items():
        add_node("person", p, bio=bio)

    out = {
        "nodes": list(nodes.values()),
        "edges": edges,
        "stats": {t: sum(1 for n in nodes.values() if n["type"] == t) for t in
                  ["site", "token", "circuit", "agent", "processor", "container", "person", "miner"]},
    }
    out["stats"]["edges"] = len(edges)
    out["stats"]["compromised_circuits"] = sum(1 for n in nodes.values() if n["type"] == "circuit" and n.get("verification") == "compromised")
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("graph.json written:")
    for k, v in out["stats"].items():
        print(f"  {k}: {v}")

if __name__ == "__main__":
    main()
