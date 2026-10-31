#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""海豚Radar · 权限监控（Phase 1.3）。

盯 X Layer 工厂合约的 owner()，一旦权限变化（换管理员/升级/封印）就标记 + 告警。

这是「安全 Agent」的「主动预警」能力：不等用户问，自己盯着关键合约权限。
"""
import json
import time
import urllib.request

from service import db

# X Layer 工厂合约（DeWEB 层的关键合约）
FACTORY = "0x1f09daefa827f02cbb40967cc91b259763760761"
BASELINE_OWNER = "0xB3D85b42A045c1A88D800CAD0F55d2566a4D3138"  # 3/5 多签
XLAYER_RPC = "https://rpc.xlayer.tech"
OWNER_SEL = "0x8da5cb5b"  # owner()


def rpc_call(method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(XLAYER_RPC, data=body,
                                 headers={"Content-Type": "application/json", "User-Agent": "dolphinradar/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


def get_owner():
    res = rpc_call("eth_call", [{"to": FACTORY, "data": OWNER_SEL}, "latest"])
    h = res.get("result", "")
    if not h or h == "0x":
        return None
    return "0x" + h[-40:]


def check_factory_owner(conn):
    """查询工厂 owner，若变化则记录高危告警。返回状态 dict。"""
    try:
        owner = get_owner()
    except Exception as e:
        return {"status": "rpc_error", "factory": FACTORY, "error": str(e)}

    now = int(time.time())
    baseline = db.get_meta(conn, "factoryOwnerBaseline") or BASELINE_OWNER
    changed = bool(owner and owner.lower() != baseline.lower())

    db.set_meta(conn, "factoryOwner", owner or "")
    db.set_meta(conn, "factoryOwnerCheckedAt", now)
    conn.commit()

    result = {
        "status": "changed" if changed else "ok",
        "factory": FACTORY,
        "owner": owner,
        "baseline": baseline,
        "changed": changed,
        "checkedAt": now,
    }

    if changed:
        alert = {
            "ts": int(time.time() * 1000),
            "type": "permission_change",
            "tier": "high",
            "title": "🔴 X Layer 工厂 owner 已变更",
            "detail": f"旧 {(baseline or '')[:10]}… → 新 {(owner or '')[:10]}…",
            "impact": "工厂规则可能被管理员修改（可升级）",
            "tx": "", "block": None,
        }
        alert_id = f"perm:{now}"
        conn.execute(
            "INSERT OR IGNORE INTO alerts(id, type, tier, title, detail, impact, tx, block, ts, payload) "
            "VALUES(?,?,?,?,?,?,?,?,?,?)",
            (alert_id, alert["type"], alert["tier"], alert["title"], alert["detail"],
             alert["impact"], "", None, alert["ts"], json.dumps(alert, ensure_ascii=False)),
        )
        conn.commit()

    return result


if __name__ == "__main__":
    from service import db
    c = db.connect()
    print(json.dumps(check_factory_owner(c), ensure_ascii=False, indent=1))
