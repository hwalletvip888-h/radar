# 断线恢复 · 当前进度（2026-10-31）

> 断线回来接着干，先读这个。完整立项见 PROJECT_CHARTER.md，架构见 SERVICE.md。

---

## 一句话状态

**海豚Radar 已从「黑客松项目」升级为「TapeOut 安全 Agent」，Phase 1 风险引擎 5 模块全部上线。**

---

## 已完成（Phase 1 风险引擎）

| 模块 | 文件 | 产出 |
|---|---|---|
| 作弊识别 + 风险评分 | `service/risk.py` | 12 实锤 + 97 高嫌疑 + 816 中高 + 874 中 |
| 风险关联 | `service/risk_graph.py` | 247 作弊高发题 + 8 重复作弊者 |
| 地址风险评分 | 同上 | /api/risks 逐电路风险分 |
| 假币标记 | `service/config.py` | /api/tokens 官方 BEM vs 假币 |
| 权限监控 | `service/perm_watch.py` | 盯 X Layer 工厂 owner 变化 |

---

## 关键地址 / 命令

| 项 | 值 |
|---|---|
| 服务器 | `64.83.48.164`（RainYun，Ubuntu 24.04） |
| SSH | `ssh radar`（key `~/.ssh/radar_deploy_ed25519`） |
| 服务 | `systemctl restart dolphinradar`（代码在 `/root/dolphinradar/`） |
| 公网 API | `https://api.radar.hvip.one`（Caddy + Let's Encrypt） |
| 链上前端 | `https://11-2-4.tapekit.org/`（tape://11.2.4.tape） |
| GitHub | `hwalletvip888-h/radar`（gh 已切到 hwalletvip888-h） |
| 本地项目 | `C:\Users\CF\Desktop\okx-sentinel\deweb-search\` |

**部署命令**（改完代码后）：
```bash
cd deweb-search
tar czf - service | ssh radar 'cd /root/dolphinradar && tar xzf - && systemctl restart dolphinradar'
```

---

## 下一步（Phase 2 产品化）

1. **吃狗粮**：跨点 BEM 到 X Layer，用测试钱包订阅一次，跑通真实付费闭环
2. **主动预警**：把「97 高嫌疑 + 8 重复作弊者」主动推给订阅者（现在要等着查，改成主动推）
3. **需求验证**：拿这些发现进 TapeOut 社区，验证矿主付不付费（立项书成功标准：1 个真实矿主订阅）

---

## 前端页面（链上实时）

- 首页：心跳条 + 三入口
- 📊 安全评级 `ratings-live.html`（12 F + 1787 B）
- 🚨 风险榜 `risk.html`（四层风险）
- 🧭 风险地图 `risk-graph.html`（作弊高发题 + 重复作弊者）
- 🔔 订阅推送 `subscribe.html`

⚠️ DeWeb 坑：非首页文件同名不可覆盖，改文件要改名（如 ratings.html→ratings-live.html）。
