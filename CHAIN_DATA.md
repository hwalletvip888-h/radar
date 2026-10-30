# TapeOut 链上数据模型与合约（逆向实测）

> 本文件是我直接从 BNB Chain 上逆向 + 官网 dApp 前端 JS bundle 里扒出来的**真实**数据模型、合约地址与 ABI。
> 所有地址已用 `cast` 实测验证。数据日期 2026-10-30。

## 一、核心合约地址（全部已验证）

| 名称 | 地址 | 说明 |
|---|---|---|
| **BEM 代币** | `0x5ce033B2bFCa3Af30b3e8C8457DeaF776A8b695a` | ERC-20，8 位小数，上限 2100 万 |
| **PodMining（挖矿）** | `0x7E2E0DC66a3bD9103E69b766afA62d9f7b697b46` | EIP-1967 代理；impl `0xa3dbe873da37cd4e4a13c7cef23a7db6ca60f898` |
| **lens（数据读取器）** | `0xdD20B9537b9f5DB9d2A23E6B11Ad863cF81930d8` | 只读聚合 |
| **lensNext** | `0x2243Eaf4Dd308AeA7E243C06d7b95265a90b0134` | 新版只读聚合 |
| **factory（处理器工厂）** | `0x68224F668083c29e9800Be2a646d42d18cedF7e2` | 创建处理器 |
| **SiteRegistry（网站仓库）** | `0xd006ffdd5Ae313B17729621A00999cDc7C1CE5e6` | 存链上网站文件 |
| **DomainBinding** | `0x861EE183de2BBE4a6ecf9D158...`（待补全） | 名字开通/付费 |
| **BEM/USDT 池 (PancakeSwap V3)** | `0x2f5e…ea38`（待补全） | DEX |

### 处理器（CPU，电路 NFT 所在合约）

| 处理器 | 地址 | 挖矿系数 P | 说明 |
|---|---|---|---|
| Genesis CPU（#0） | `0x50A994E71615474b55559fF4F500928fbc339DD9` | — | 演示/初始处理器 |
| **Behemoth（#1）** | `0x1F5Cb4aeaE1807Bf60c3b9C0D8aDBCC14e91f12C` | **6** | 可挖矿 |
| **TapeOut（#30）** | `0xb1024b89886B9a34Aa4ff5F31C411D708b20a14C` | **1** | 可挖矿 |
| RefBench | `0xF4412C52ec3DDf7CAf5f518B6662F77B02Bde28E` | 1 | 参考基准 |

## 二、数据模型（术语 → 链上形态）

```
NAND/LATCH 晶体管  = ERC-1155（每台处理器一套，可铸可交易）
处理器 processor    = 工厂创建的合约（自带一套晶体管 + 一套电路编号）
电路 circuit       = ERC-721 NFT（流片=销毁元件+铸 NFT，网表在链上）
矿机 miner         = 参与 PoD 挖矿的电路 NFT（俗称）
容器 container     = ERC-6551 账户，绑在电路上（无死钥，控制权随 NFT）
tape:// 网站        = 挂在容器上的 DeWEB 站点（SiteRegistry 存文件）
BEM                = PoD 产出的 ERC-20，唯一铸币者是 PodMining
```

**`.tape` 名字**：`<电路#ID>.<处理器编号>.tape`，例 `4246.0.tape` = 0 号处理器上第 4246 枚电路。
电路编号**每台处理器单独从 1 起算**，所以「#12」必须带处理器号才唯一。

## 三、PodMining ABI（从官网 JS bundle 扒出，实测验证）

### 关键只读函数

| 签名 | selector | 说明 |
|---|---|---|
| `minerCount() view returns (uint256)` | `0x6d1da431` | 矿机总数 = 20567 |
| `verifMinerCount() view returns (uint256)` | `0xcb29bf7d` | 已验证池矿机数 = 19919 |
| `totalVerifWeight()` | `0xef6aff46` | 全网已验证算力 = 1584450 |
| `totalUnverWeight()` | `0x63967742` | 全网未验证算力 = 41297 |
| `totalMined()` | `0x5556db65` | 已产 BEM = 45056489564391（/1e8 = 450564.9 枚） |
| `totalForgone()` | `0xcf6f282c` | 放弃产出 |
| `currentRate()` | `0xf9f8bdb7` | 当前速率 = 8333333 |
| `dailyEmission()` | `0xa335fd36` | 日产出 |
| `minerKey(address,uint256) pure returns (bytes32)` | `0x10eafa00` | 计算矿机 key |
| `getMiner(bytes32) view returns (tuple)` | `0x0527edc2` | 完整矿机状态 |
| `pending(bytes32)` | `0x1808eeb8` | 待领奖励 |
| `bestSlot(uint32,address)` | `0x11d5a55c` | 最优首创 |
| `ceCount(uint32,address)` | `0x2060b9db` | 反例数 |
| `processorMultiplier(address)` | `0x0f03daba` | 处理器系数 |
| `owner()` | `0x8da5cb5b` | = 0x0（已封印） |
| `paused()` | `0x5c975abb` | |
| `TAPEOUT_FEE()` | `0xadfb2b69` | 流片费 |

### `getMiner(bytes32)` 返回 tuple 字段（顺序）

```
(address circuits,      // 处理器地址
 uint64 circuitId,      // 电路 ID
 uint32 taskId,         // 题目 ID
 uint32 gateCount,      // 门数
 uint32 stateCount,     // 锁存器数
 uint32 depth,          // 深度
 uint64 area,           // 面积
 uint32 mult,           // 处理器系数 P
 uint64 since,          // 开挖时间
 uint8  status,         // ★状态：1=挖矿中，其它=已停/被撤销
 address registrant,    // 注册人
 uint32 nandBurn, uint32 latchBurn,
 uint64 bstar, uint64 bonus, bool optimal,
 uint64 commitBlock, uint64 firstUnusedId, uint64 stopBlock,
 uint128 verifWeight,   // 已验证算力
 uint128 unverWeight,   // 未验证算力
 uint256 debt)          // 待领 BEM
```

### 事件（= 安全信号源）

| 事件 | topic0 | 含义 |
|---|---|---|
| **`Revoked(bytes32 key, address challenger, uint32 vectorIndex)`** | `0xe52b422c...` | ★矿机被反例举证 → 永久撤销 |
| `CounterexampleAdded(uint32 taskId, address circuits, uint256 circuitId, address by, bool added, bytes input)` | `0x46ff8dc9...` | 新反例登记 |
| `Started(bytes32 key, address circuits, uint256 circuitId, uint32 taskId, ...)` | `0x7c9c1f2b...` | 矿机开挖 |
| `Stopped(bytes32 key, address by)` | `0xc167316d...` | 停挖 |
| `Claimed(bytes32 key, address to, uint256 amount)` | `0x0508a8b4...` | 领取 BEM |
| `Demoted(bytes32 key, address circuits, uint256 circuitId, uint32 taskId)` | `0x687eb3f2...` | 被夺最优首创 |
| `TapedOut(uint256 circuitId, address owner, uint32 gateCount, uint32 nState)` | `0xc11215e4...` | 电路流片 |
| `TaskAdded(...)` | — | 出题 |

### 写函数（安全闭环的核心）

- `challenge(bytes32,uint32,bytes,bytes,bytes32[])` — 提交反例（input + 错误输出 + merkle 证明），成立即 `Revoked`
- `registerCounterexample(uint32,address,bytes)` — 给题目登记新反例向量
- `kick(uint32,address)` — 只夺最优首创，不停挖
- `arm(address,uint256)` / `start(...)` / `stop(bytes32)` / `claim(bytes32)` / `claimMany(bytes32[])` / `reclaim(bytes32)`

## 四、处理器（电路 NFT）合约 ABI

| 签名 | 说明 |
|---|---|
| `eval(uint256,bytes) view returns (bytes)` | 求值电路（核心） |
| `netlist(uint256) view returns (bytes)` | 网表数据（在链上） |
| `circuitInfo(uint256) view returns (uint32,uint32,uint32,uint32)` | 电路信息 |
| `tapeout(bytes nl,uint32 nIn,uint32 nOut) payable returns (uint256)` | 流片铸 NFT |
| `cachedDepth(address,uint256)` | 深度（缓存） |
| `balanceOf(address,uint256)` / `ownerOf(uint256)` / `tokenURI(uint256)` | ERC-721/1155 |
| `name()` / `symbol()` / `transistors()` / `supportsInterface(bytes4)` | 元数据 |
| ENS 解析：`resolve` / `resolver` / `name(bytes32)` / `text` / `contenthash` / `addr` | **`.tape` 名字 → 电路的解析** |

## 五、安全闭环（真实机制，不是演示文案）

TapeOut 协议**内建**了「反例审查」机制，正好是供应链安全告警的核心：

1. **验证**：任何人（无需质押）提交 `challenge(key, vectorIndex, input, wrongOutput, merkleProof)`，合约当场逐位核对
2. **成立**：emit `Revoked(key, challenger, vectorIndex)` → 该矿机**永久撤销**，不能再领 BEM
3. **追溯**：`Revoked` 的 key → `minerKey(processor, circuitId)` → 定位电路 NFT → 它的容器 → tape:// 网站 → 下游
4. **告警**：沿依赖链广播
5. **收敛**：状态生命周期（compromised → revoked → 下游迁移）

`CounterexampleAdded` 是「验证的验证」：把新发现的反例补进题目标准向量，让参考实现也变硬。

## 六、官方数据接口（可读，非私有）

官网 dApp 直接暴露 JSON + RPC：

- `https://tapeout.net/pod/pod-mainnet.json` — 全部合约地址 + 处理器 + 示例电路 + 267 题
- `https://tapeout.net/pod/pod-stats.json` — 实时挖矿统计
- `https://tapeout.net/pod/pod-taskbank.json` — 题库（306 题，267 上链）
- `https://tapeout.net/pod/pod-probe.json` — 测试向量（输入→标准答案，反例验证的数据）
- `https://tapeout.net/pod/assets/main-<hash>.js` — 前端 bundle（含全部 ABI）
- `https://tapeout.net/processors.json` — **全部 1456 台处理器**（地址/晶体管合约/名字/creator/电路数）
- `https://tapeout.net/protocol-stats.json` — 协议活动统计（交易量/笔数/地址数）
- `https://tapeout.net/cpu-stats.json` — 每台 CPU 的铸币者/持有者/数量
- `https://tapeout.net/rpc` — JSON-RPC 代理（eth_call/eth_getLogs，单次最多 50000 块，**不限频**，含归档）

### 处理器实测（processors.json 摘录）

| 处理器 | 地址 | 晶体管(ERC-1155) | 电路数 |
|---|---|---|---|
| Genesis CPU (#0) | `0x50A994E71615474b55559fF4F500928fbc339DD9` | `0x1d23Bf70ec6bAAD95f396Ea38f8A8415119dFDE6` | 12912 |
| Blonskr_No1 = Behemoth (#1) | `0x1F5Cb4aeaE1807Bf60c3b9C0D8aDBCC14e91f12C` | `0xE2DfD802081C7a05341E20b6582b04b908e8550c` | 2737 |
| picasso | `0xc1aE0d87cDE4f93bcaE38c6D62A269c76D5d3215` | `0xc1685B9cEFA8C5E5D50a98B3Cdf68B3C70d35081` | 226 |
| （共 1456 台） | … | … | … |

注意：只有 **Behemoth(#1) + TapeOut(#30)** 能挖矿（P=6 / P=1）。其它 1454 台处理器只能流片/建站，不产 BEM。

## 六·五、X Layer（DeWEB 层）—— 第二战场

> 黑客松要求：**必须用 X Layer 上的 TapeOut 电路/合约/链上数据，或在 X Layer 的 DeWEB 中运行。**
> X Layer = chainId 196，区号 2。**不产 BEM（PoD 挖矿只在 BNB Chain）**，跑的是 DeWEB 层。

### 关键合约地址（全部实测验证）

| 名称 | 地址 | 说明 |
|---|---|---|
| **factory（处理器工厂）** | `0x1f09daefa827f02cbb40967cc91b259763760761` | impl `0xb41c1e7602eb5734be2430b72178ccb814a5293d` |
| **opener（开容器）** | `0x536add8f30f03b69f6fbf29d425a816a0dc50106` | 5210 字节 |
| **accountImpl（ERC-6551 实现）** | `0xac4f791353ee9f06e2c50ae4c34680d28ea52a57` | 1204 字节 |
| **BEM（跨链铸造）** | `0x60e62Efa9405d6873C5deaBD4E6CC91c25363952` | 流通 13,446.9 BEM |
| BNB 侧跨链锁仓 | `0xa84B8D3893De6e9922f2B29bE1e1b115845F5E72` | 1:1 锁定 |
| rigVoucher / usdt0 / wokb | `0x9cfc…` / `0x779D…` / `0xe538…` | 生态代币 |

RPC：`https://rpc.xlayer.tech`（日志范围 100 块）、`https://tapeout.net/rpc-xlayer`（1000 块）、`https://xlayerrpc.okx.com`（100 块）。

### 安全发现（与 BNB 对比）

1. **工厂未封印**：X Layer factory `owner()` = `0xB3D85b42A045c1A88D800CAD0F55d2566a4D3138`（3/5 多签，官网法律声明明说「工厂合约目前保持可升级」）。而 BNB 的 PodMining 已封印 `owner()=0x0`。→ X Layer 的工厂规则仍可被管理员改。
2. **BEM 桥**：13,446.9 BEM 从 BNB 1:1 锁定后跨到 X Layer，走 LayerZero（LayerZero Labs + Nethermind 两验证者 + Horizen/Canary 至少一个），源链确认 20 块后开始验证。
3. **无挖矿/无反例审查**：X Layer 没有 PoD，也就没有 `challenge`/`Revoked` 机制——DeWEB 层没有「矿机被撤销」这种安全信号。

### X Layer 的安全角度（DeWEB 供应链）

```
电路（ERC-721，控制权可转让）
  → 容器（ERC-6551，控制权跟随电路 NFT）
    → tape:// 网站（SiteRegistry 存文件）
      → 用户
```

安全信号（DeWEB 版）：**电路所有权转移**（网站换手）、**容器冻结**（挂单期间）、**网站内容变更**（哈希变了）。这是「谁控制了你的链上网站」这个问题的供应链追踪。

### 待补

- 工厂的处理器枚举函数名没对出来（`processors(uint256)`/`processorCount()` 都 revert，函数名不同）
- SiteRegistry 地址在 TapeKit 网关（tapekit.org），不在主站 bundle 里
- 部署到 X Layer DeWEB 需要钱包 + OKB（见 DEPLOY.md）



- `bsc-dataseed.binance.org` / `bsc-dataseed1` / `1rpc.io/bnb` / `bsc.publicnode.com` 可用
- eth_getLogs 单次最多 50000 块；全历史需分页（~14.6M 块 / 50000 ≈ 292 次）
- publicnode 老块要 archive token；dataseed 有频率限制
