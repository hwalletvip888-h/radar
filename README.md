# 海豚Radar（DolphinRadar）

> **TapeOut 生态安全警报系统** —— 矿机的电路一旦被链上反例审查证伪、永久撤销，第一时间追溯波及范围、分级告警、实时推送。

**🔗 已上线**：`https://11-2-4.tapekit.org/`（链上 `tape://11.2.4.tape`，运行在 X Layer DeWEB）

**📜 订阅合约已部署 + 已验证**：`0x7c57f97d593c4AFcFA2F7a7E7Cc61CDa1B3E7652`（[OKLink 查看源码](https://www.oklink.com/xlayer/address/0x7c57f97d593c4AFcFA2F7a7E7Cc61CDa1B3E7652/contract)）

## 能做什么

1. **实时监控** —— 链上矿机被撤销、电路被证伪，第一时间发现
2. **依赖图谱** —— 把「电路 → 矿机 → BEM → 下游」的依赖关系画成图，一眼看清谁依赖谁
3. **追溯波及** —— 谁被波及、冻结了多少 BEM、坏币流向了哪个资金池
4. **分级告警** —— 按高 / 中 / 低风险，推送到订阅者的 Telegram
5. **地址体检** —— 连接钱包，自动查你的地址是否在被撤销矿主、BEM 领取方或举证者名单里
6. **链上订阅合约** —— AlertSubscription 已部署 X Layer 并开源验证，订阅 / 续费 / 升级 / 取消全走合约，BEM 收款、到期自动失效

## 真实链上数据（2026-10-30 实测）

扫了 PodMining 挖矿合约从部署至今的 **1340 万区块**，读出的真实安全事件：

| 事件 | 数量 | 含义 |
|---|---|---|
| **Revoked（被撤销）** | **12** | 矿机被反例证伪 → 永久撤销 |
| CounterexampleAdded | 136 | 反例举证（验证的验证） |
| Demoted（被夺最优） | 1978 | 最优首创被更小设计夺走 |
| Stopped（停挖） | 2871 | 主动停挖 |

12 台被撤销矿机冻结 **4676 BEM** 未领奖励，最大的一台 Behemoth #1965 单独冻结 3384 BEM。

## 完整闭环

```
验证（challenge 反例举证 → Revoked 事件，链上永久撤销）
  → 追溯（电路 → 矿机 → BEM → 下游，算出爆炸半径 + 冻结金额）
  → 分级告警（🔴 矿主 / 🟡 BEM 下游 / ⚪ 举证审计归档）
  → 状态收敛（revoked → 下游迁移 → BEM 标记）
```

## 实时订阅 + 付费

连钱包订阅（上链）→ 引擎监听链上事件 → 命中订阅者 → 自动推送到 Telegram / Webhook。

| 套餐 | 价格 | 权益 |
|---|---|---|
| 免费 Free | 0（只付 gas） | 全局告警 + 周报 |
| Pro | 0.2 BEM/月 | 实时推送 + 体检 |
| 企业 Enterprise | 定制（owner 定价） | API + 批量 |

- **链上订阅记录 = 平台用户量凭证**（每个订阅者都有可验证的链上记录）
- 合约 `contracts/AlertSubscription.sol`：订阅 / 续费 / 升级补差价 / 取消退款，X Layer 桥接 BEM 收款（已部署 + OKLink 验证，地址见顶部）
- 实时引擎 `engine.py`：WebSocket 订阅 BNB PodMining 的 Revoked / CounterexampleAdded，推送给有效订阅者
- Telegram 绑定 bot `bot.py`：订阅页生成深链 → 用户点 Start → 自动绑定「钱包 ↔ Telegram」

## 文件结构

```
deweb-search/
├── CHAIN_DATA.md        逆向实测：全部合约地址 + ABI + 数据模型 + 安全机制
├── chain_extract.py     链上提取器：扫 1340 万区块读真实安全事件
├── blast_radius.py      爆炸半径：谁从被撤销矿机领走了 BEM
├── bem_flow.py          BEM 二级流转污染追踪（见「诚实的边界」）
├── real_chain_data.json 原始链上事件（Revoked/Counterexample/Stopped/Demoted）
├── graph_onchain.py     真实图谱构建器 → graph_onchain.json
├── graph_onchain.json   真实对象图（109 电路 / 4 处理器 / 12 被撤销 / 233 关系）
├── contracts/           三套餐付费订阅合约 AlertSubscription.sol（Free/Pro/Enterprise）
├── engine.py            实时告警引擎（WebSocket 事件订阅 → 富化 → 分级 → 推送）
├── common.py            告警管线共享工具（推送 / 匹配 / 读 token / 过滤过期）
├── bot.py               Telegram 订阅绑定 bot（/start 深链 → 写 subscriptions.json）
├── notifier.py / watcher.py   轮询分发 / 扫链监听（与 engine 互补）
├── deploy/              X Layer DeWEB 部署包（index.html + subscribe.html + brand/ + 数据）
├── brand/               海豚珍珠品牌资产（logo / favicon / 头像）
├── DEMO.md / DEMO_VIDEO_BRIEF.md / DEMO_STORYBOARD.md   演示脚本 + 视频简报
├── ROADMAP.md           长期路线图（定位：TapeOut 链上安全数据层）
├── service/             常驻服务（SQLite + 增量扫链 + 评级 + REST API，见 SERVICE.md）
├── SERVICE.md           服务架构文档
└── vendor/              本地化的 vis-network（离线/上链也能跑）
```

## 运行

**常驻服务（推荐，7×24 自动）** —— 见 [SERVICE.md](SERVICE.md)：

```bash
cd deweb-search
python -m service.run    # 建库 + seed + 增量扫链 + 评级 + REST API（http://127.0.0.1:8900）
```

**离线重扫（原型脚本，可选）**：

```bash
cd deweb-search
python chain_extract.py    # 重新扫链（可选，~几分钟）
python blast_radius.py     # 重新扫下游 BEM（可选）
python graph_onchain.py    # 重建 graph_onchain.json
python -m http.server 8899 # 起本地服务
# 浏览器打开 http://localhost:8899/graph.html
```

实时告警引擎（依赖 web3 + websockets，token 读 `.bot_token` 或环境变量 `TELEGRAM_BOT_TOKEN`）：

```bash
python engine.py --replay   # demo：重放最近一次撤销，演示「检测→推送」全流程
python engine.py            # 常驻：WebSocket 实时监听并推送
python bot.py               # 常驻：Telegram 订阅绑定 bot（/start 深链）
```

## 诚实的边界

- 下游爆炸半径已接两层：**一级**（谁从被撤销矿机领走 BEM，`blast_radius.json`）+ **二级**（这些地址转给谁、进了哪个 DEX 池，`bem_flow.json`，实测 728 BEM 进了 PancakeSwap BEM/USDT 池）。但这是「从 9 个源地址出发的流出」，不是精确的逐币 taint 追踪（9 个地址还有其它合法矿机的 BEM，坏币被稀释了）。
- 意图解析是关键词启发式，非真 NLP。
- 12 台撤销在数量上只占全网约 2 万台矿机的 0.06%，但它们是「真实发生过、且事后无人追溯」的样本——产品价值在补上追溯盲区，不在撤销数量。
