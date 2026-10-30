# 海豚Radar（DolphinRadar）

> **TapeOut 生态安全警报系统**——图谱是底层结构，广播是产品形态。
> 当 TapeOut 生态里一台矿机被链上反例审查证伪、永久撤销，沿「电路 → 矿机 → BEM → 下游」依赖链追溯波及方，按依赖优先级分级广播告警，并追踪状态直到收敛。
> **数据全部来自 BNB Chain 真实链上状态，不是演示数据。**

## 一句话

TapeOut 上 2 万台矿机在挖 BEM，协议内建「反例审查」能永久撤销算错的矿机。但撤销之后谁被波及、冻结了多少币、下游谁拿了它挖的币——这套系统把「验证 → 追溯 → 分级告警 → 状态收敛」串成闭环。

## 真实链上数据（2026-10-30 实测）

扫了 PodMining 挖矿合约从部署至今的 **1340 万区块**，读出的真实安全事件：

| 事件 | 数量 | 含义 |
|---|---|---|
| **Revoked（被撤销）** | **12** | 矿机被反例证伪 → 永久撤销 |
| CounterexampleAdded | 136 | 反例举证（验证的验证） |
| Demoted（被夺最优） | 1978 | 最优首创被更小设计夺走 |
| Stopped（停挖） | 2871 | 主动停挖 |

12 台被撤销矿机冻结 **4676 BEM** 未领奖励。最大的一台 Behemoth #1965 单独冻结 3384 BEM。

## 完整闭环

```
验证（challenge 反例举证 → Revoked 事件，链上永久撤销）
  → 追溯（电路 → 矿机 → BEM → 下游，算出爆炸半径 + 冻结金额）
  → 分级告警（🔴 矿主 / 🟡 BEM 下游 / ⚪ 举证审计归档）
  → 状态收敛（revoked → 下游迁移 → BEM 标记）
```

## 三层告警架构（产品核心）

| 层 | 内容 |
|---|---|
| **L1 影响清单** | 每个受影响对象 + 可执行动作（停止算力/冻结未领 BEM/核查下游） |
| **L2 分级广播** | 🔴 高（矿主，直接损失）→ 🟡 中（依赖 BEM 的下游）→ ⚪ 低（仅归档） |
| **L3 状态追踪** | 广播后生命周期：撤销（终局）→ 下游迁移 → 坏币标记 |

## 实时订阅 + 付费（产品闭环）

连钱包订阅（上链）→ 引擎监听链上事件 → 命中订阅者 → 自动推送到 Telegram / Webhook。

| 套餐 | 价格 | 权益 |
|---|---|---|
| 免费 Free | 0（只付 gas） | 全局告警 + 周报 |
| Pro | 0.2 BEM/月 | 实时推送 + 体检 |
| 企业 Enterprise | 定制（owner 定价） | API + 批量 |

- **链上订阅记录 = 平台用户量凭证**（每个订阅者都有可验证的链上记录）
- 合约 `contracts/AlertSubscription.sol`：订阅 / 续费 / 升级补差价 / 取消退款，X Layer 桥接 BEM 收款
- 实时引擎 `engine.py`：WebSocket 订阅 BNB PodMining 的 Revoked / CounterexampleAdded，推送给有效订阅者
- Telegram 绑定 bot `bot.py`：订阅页生成深链 → 用户点 Start → 自动绑定「钱包 ↔ Telegram」

## 文件结构

```
deweb-search/
├── CHAIN_DATA.md        逆向实测：全部合约地址 + ABI + 数据模型 + 安全机制
├── chain_extract.py     链上提取器：扫 1340 万区块读真实安全事件
├── blast_radius.py      爆炸半径：谁从被撤销矿机领走了 BEM
├── bem_flow.py          BEM 二级流转污染追踪（需 RPC 冷却后再跑，见「诚实边界」）
├── real_chain_data.json 原始链上事件（Revoked/Counterexample/Stopped/Demoted）
├── blast_radius.json    下游 BEM 流向
├── graph_onchain.py     真实图谱构建器 → graph_onchain.json
├── graph_onchain.json   真实对象图（109 电路 / 4 处理器 / 12 被撤销 / 233 关系）
├── graph.html           主界面：对象搜索 / 关系图 / 影响追溯 / 告警广播 / 实时告警
├── subscribe.html       订阅页（连钱包 → 选套餐 → 绑定 Telegram）
├── deploy.html          订阅合约部署页（含已编译字节码）
├── contracts/           三套餐付费订阅合约 AlertSubscription.sol（Free/Pro/Enterprise）
├── engine.py            实时告警引擎（WebSocket 事件订阅 → 富化 → 分级 → 推送）
├── common.py            告警管线共享工具（推送 / 匹配 / 读 token / 过滤过期）
├── bot.py               Telegram 订阅绑定 bot（/start 深链 → 写 subscriptions.json）
├── notifier.py          轮询分发（读 alerts.json 推送，与 engine 二选一）
├── watcher.py           链上事件监听（扫链写 alerts.json）
├── brand/               海豚珍珠品牌资产（logo / favicon / 头像）
├── deploy/              X Layer DeWEB 部署包
├── main-processors.json 官网 processor 全表（1456 台）
├── pod-*.json           官网挖矿配置/统计/题库/测试向量
├── graph.py / sites.json / graph.json  旧版（描述文本种子数据，已弃用）
├── DESIGN.md / GRAPH.md / DEPLOY.md / DEMO.md  设计与演示文档
└── vendor/              本地化的 vis-network（离线/上链也能跑）
```

## 运行

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

## 真实对象图

- **processor** 处理器 4（Behemoth P=6 / TapeOut P=1 / RefBench / Genesis，共 1456 台里只有前两台可挖矿）
- **circuit** 电路 109（12 被撤销 + 97 被加反例）
- **person** 人 20（举证者 + 矿主）
- **token** BEM
- 关系：`taped_on`（电路→处理器）/ `mines`（电路→BEM）/ `revealed`（举证者→电路）/ `operated_by`（电路→矿主）

## 诚实的边界

- 下游爆炸半径已接两层：**一级**（谁从被撤销矿机领走 BEM，`blast_radius.json`）+ **二级**（这些地址转给谁、进了哪个 DEX 池，`bem_flow.json`，实测 728 BEM 进了 PancakeSwap BEM/USDT 池）。但这是「从 9 个源地址出发的流出」，不是精确的逐币 taint 追踪（9 个地址还有其它合法矿机的 BEM，坏币被稀释了）。
- 电路 → 容器 → tape:// 网站的映射还没接（需要 ERC-6551 容器派生 + SiteRegistry），这 12 台矿机大概率不托管网站，所以不是当前重点。
- 意图解析是关键词启发式，非真 NLP。
- 前端已部署到 X Layer DeWEB：`tape://11.2.4.tape`，官方网关 **https://11-2-4.tapekit.org/**（注意名字里的点换成横线，否则 SSL 报错）。本地预览用 `python -m http.server`。
