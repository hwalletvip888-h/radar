# 海豚Radar · 数据模型

> 底层数据层的字段定义。采数脚本、评级引擎、前端都按这份 schema 来。

---

## 数据管线（一条链）

```
链上（PodMining 合约）
   │  chain_extract.py 扫事件（13.4M 区块）
   ▼
real_chain_data.json  ← 原始事件 + 撤销矿机富化
   │  rating.py 评级引擎
   ▼
ratings.json          ← 电路健康分 + 等级 + 风险标签
   │  （前端看板 / API 消费）
   ▼
graph_onchain.json    ← 依赖图谱（前端关系图用）
```

---

## 1. real_chain_data.json（原始事件）

| 字段 | 类型 | 说明 |
|---|---|---|
| `latestBlock` | int | 扫描到的最高区块 |
| `counts` | dict | 各事件类型数量 |
| `events` | list | 全部安全事件（解码后） |
| `miners` | dict | 撤销矿机的 getMiner 富化（key → 22 字段） |

### 事件类型（events[].event）

| 事件 | 数量 | 关键字段 | 评级含义 |
|---|---|---|---|
| `Revoked` | 12 | key, challenger, vectorIndex | 撤销 → F |
| `Demoted` | 1978 | key, circuits, circuitId, taskId | 被夺最优 → B |
| `Stopped` | 2871 | key, by | 停挖（无 circuitId，需 getMiner 映射） |
| `CounterexampleAdded` | 136 | taskId, circuits, circuitId | 新反例登记 |

### getMiner 返回（miners[key] 的 22 字段）

circuits(处理器地址)、circuitId、taskId、gateCount、status、registrant(矿主)、bstar、optimal(是否最优)、debt(待领 BEM) 等。

---

## 2. ratings.json（评级输出）

| 字段 | 说明 |
|---|---|
| `model` | 评分模型版本 + 权重 + 等级区间 |
| `rated_circuits` | 已评级电路数 |
| `total_miners` | 全网矿机总数（minerCount()） |
| `summary` | 汇总：撤销/夺最优/停挖/健康估算 + 等级分布 |
| `ratings[]` | 每个电路的评级 |

### ratings[] 每个电路字段

| 字段 | 说明 |
|---|---|
| `circuitId` | 电路 ID |
| `processor` | 处理器名（Behemoth/TapeOut） |
| `taskId` | 认领的题号 |
| `score` | 健康分 0-100 |
| `grade` | 等级 A/B/C/D/F |
| `status` | revoked / demoted / stopped / counterexample |
| `risk` | 风险标签（中文） |
| `debtBEM` | 冻结未领的 BEM（仅撤销电路有） |
| `tx` / `challenger` | 撤销交易 / 举证者（仅撤销电路有） |

---

## 3. graph_onchain.json（依赖图谱）

| 字段 | 说明 |
|---|---|
| `nodes` | 节点（processor / circuit / person / token / site） |
| `edges` | 关系（taped_on / mines / revealed / operated_by） |
| `meta` | 统计 + 撤销详情 |
| `stats` | 各类节点/关系数量 |

---

## 评分模型（V3）

| 状态 | 分数 | 等级 | 依据 |
|---|---|---|---|
| 撤销 Revoked | 0 | F | 反例举证成立，永久失格 |
| 被夺最优 Demoted | 75 | B | 失去设计溢价，基础挖矿继续 |
| 停挖 Stopped | 60 | C | 活跃度风险 |
| 被加反例（未撤销） | 70 | C | 被举证但未成立 |
| 正常 | 100 | A | 无安全信号 |

> 停挖电路当前只能映射到「与 Demoted 重叠」的那部分（~98 个），其余 1758 个需 getMiner 逐台读（RPC 恢复后补）。

---

## 诚实边界

- **健康电路（A 级）是估算值**：`minerCount - 撤销 - 夺最优`，不是逐台扫出来的。
- **停挖维度不完整**：事件只带 key，缺 circuitId，需 getMiner。
- **「背答案作弊」无公开名单**：官方反例审查（2026-09-01）查出 80 个电路（13.99% 池子权重）「背答案」——针对公开测试向量修剪电路、通过 3~32 向量抽检但全输入不符。社区另有更激进说法（前 82 个最优电路 40% 过拟合、约 350 台 = 17.6% 算力未过全输入等价）。官方走「举报→撤销溢价」机制、不公示黑名单，因此**没有精确名单可查**；`Demoted` 事件（被夺最优/kick）是这一风险的链上代理信号，但无法区分「作弊被 kick」和「正常被夺最优」。
- **假冒代币**（TAPEOUTX 等）还没做标记。
