#!/usr/bin/env python3
"""DeWebSearch 索引器：从 tapeout.link 目录抓取站点，产出结构化 index.json。
数据源：先用手头已抓的官网快照（playwright snapshot），后续可替换成实时爬虫。"""
import json, re, sys

SNAP = r"C:\Users\CF\.claude\projects\C--Users-CF-Desktop-okx-sentinel\247c1451-7620-417b-b4ff-3f123f9aa0b0\tool-results\mcp-playwright-browser_snapshot-1793332624136.txt"

# 分类关键词 → category
CATS = [
    ("game", ["游戏", "射击", "五子棋", "扑克", "大逃杀", "坦克", "roguelite", "arcade", "闯关", "像素", "弹幕", "Boss", "竞技"]),
    ("chat",  ["聊天", "消息", "Chat", "即时消息", "端到端", "私聊", "会话", "加好友"]),
    ("social",["社交", "相册", "社区", "论坛", "名人榜", "贡献"]),
    ("music", ["音乐", "音频", "曲目", "版税", "唱片"]),
    ("defi",  ["交易", "兑换", "流动性", "DeFi", "PT / YT", "发射", "矿币", "市场", "OTC", "挂单", "质押", "底池", "代币"]),
    ("ai",    ["AI", "agent", "神经网络", "推理", "ZK", "协处理器"]),
    ("mining",["挖矿", "矿机", "算力", "晶体管", "PoD", "流片", "配机", "组装", "租赁"]),
    ("tool",  ["发布", "上传", "网关", "浏览器", "工作台", "仿真", "优化器", "等价", "索引", "看板", "目录", "白皮书", "导入"]),
]

def categorize(text):
    for cat, kws in CATS:
        for kw in kws:
            if kw in text:
                return cat
    return "other"

def extract_chain(text):
    if "X Layer" in text: return "X Layer"
    if "BNB" in text or "BSC" in text or "BEM" in text: return "BNB"
    if "Base" in text: return "Base"
    return "multi"

def main():
    raw = open(SNAP, encoding="utf-8").read()
    # 匹配  link "名称 描述..."  形式
    entries = re.findall(r'link "([^"]+)"', raw)
    sites = []
    seen = set()
    for e in entries:
        e = e.strip()
        if not e or e in seen or e in ("更多", "跳到主要内容", "查看全网 DeWEB 网站 210 个链上站点 · web.tapeout.link"):
            continue
        seen.add(e)
        # 名字取第一个词（空格或换行分隔）；描述取剩余
        parts = re.split(r'\s+', e, maxsplit=1)
        name = parts[0].strip()
        desc = parts[1].strip() if len(parts) > 1 else ""
        # 提取 tape:// 地址
        tape = re.search(r'tape://([0-9.#@a-zA-Z]+)', e)
        sites.append({
            "name": name,
            "desc": desc,
            "category": categorize(e),
            "chain": extract_chain(e),
            "tape": tape.group(0) if tape else None,
        })
    out = {"count": len(sites), "generated": "2026-10-30", "sites": sites}
    with open(r"C:\Users\CF\Desktop\okx-sentinel\deweb-search\index.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"OK: {len(sites)} sites indexed -> index.json")
    # 打印分类统计
    from collections import Counter
    print(Counter(s["category"] for s in sites))

if __name__ == "__main__":
    main()
