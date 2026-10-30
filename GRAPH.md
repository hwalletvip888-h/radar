# TapeOut 安全警报系统 · 图数据模型

> 对象 = 节点，关系 = 边。数据来自 BNB Chain 真实链上事件（详见 CHAIN_DATA.md）。

## 一、节点类型（对象）

| type | 含义 | 关键属性 |
|---|---|---|
| **processor** | 处理器（电路 NFT 所在合约） | num, address, multiplier(P) |
| **circuit** | 电路 = 矿机（ERC-721，网表在链上） | num, processor, taskId, gateCount, status, debtBEM, challenger, tx |
| **token** | BEM 代币 | symbol, decimals, cap |
| **person** | 举证者 / 矿主（地址） | address, role |

其中 `circuit.status` 是核心安全信号：

| status | 含义 | 链上来源 |
|---|---|---|
| `revoked` | 被反例证伪 → 永久撤销 | `Revoked` 事件 |
| `counterexample` | 被加反例（发现 bug，参考实现被加固） | `CounterexampleAdded` 事件 |
| `demoted` | 被夺最优首创 | `Demoted` 事件（仅统计，不建节点） |
| `stopped` | 主动停挖 | `Stopped` 事件 |

## 二、边类型（关系）

| edge | from → to | 含义 |
|---|---|---|
| `taped_on` | circuit → processor | 电路流片在这台处理器上 |
| `mines` | circuit → token(BEM) | 电路（矿机）挖出 BEM |
| `revealed` | person → circuit | 举证者证伪了这台电路 |
| `operated_by` | circuit → person | 矿主（失去这台矿机的地址） |

## 三、爆炸半径查询（核心）

对一台被撤销电路（status=revoked），反向追溯：

```
1. 直接损失：circuit 本身（停止算力）+ debtBEM（冻结未领 BEM）
2. 矿主：operated_by → person（谁失去了这台矿机）
3. 下游：mines → BEM → Claimed 事件 → 谁领走了这台矿机挖的币
4. 举证审计：revealed → person（谁证伪的）+ tx（交易哈希）
```

## 四、真实数据规模（2026-10-30）

- 处理器：全生态 1456 台（只有 Behemoth P=6 / TapeOut P=1 能挖矿）
- 矿机：20567 台在挖（已验证池 19919 台）
- 被撤销：12 台，冻结 4676 BEM
- 反例举证：136 次

## 五、交付物

1. `chain_extract.py` → `real_chain_data.json` —— 链上事件提取
2. `blast_radius.py` → `blast_radius.json` —— 下游 BEM 流向
3. `graph_onchain.py` → `graph_onchain.json` —— 真实对象图
4. `graph.html` —— 主界面（对象搜索 / 关系图 / 影响追溯 / 告警广播）
