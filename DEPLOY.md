# 部署到 X Layer DeWEB（上链成 tape:// 网站）

> 黑客松硬要求：**在 X Layer 的 DeWEB 中运行**。这一步把 `graph.html` 变成真正的 `tape://` 链上网站。
> 需要：OKX Web3 钱包 + X Layer 上的少量 OKB（容器费 0.08 OKB + gas）。

## 已准备好的文件（deploy/ 目录）

```
deploy/
├── index.html           前端（双链版：BNB 挖矿层 + X Layer DeWEB 层）
├── graph_onchain.json   BNB 链上真实数据（12 台撤销 / 4676 BEM 冻结）
├── xlayer_data.json     X Layer 安全态势数据
├── pod-stats.json       实时挖矿统计
└── vendor/              vis-network 本地化（无 CDN 依赖，上链能跑）
```

全部静态文件 + 相对路径，符合 DeWEB 要求（单个文件最大 8.4MB，这些都在 700KB 以内）。

## 部署流程（两步）

### 第 1 步：开一个容器（拿到 .tape 名字）

1. 打开容器工厂：**https://id.tapeout.link/**
2. 钱包切到 **X Layer** 网络（chainId 196）
3. 点「一键开容器」→ 选号 → 铸造 → 流片（**用 1 个 NAND 流片，成本最低**）→ 开通容器
4. 记住你的 `.tape` 名字，格式 `<电路#ID>.<处理器编号>.tape`（X Layer 区号 2）

> 成本：流片协议费 + gas + 容器开通费 **0.08 OKB**（X Layer 价）。

### 第 2 步：把文件传上去（HashPort 托管）

1. 打开 **https://hashport.ai/**
2. 钱包同样切到 **X Layer**
3. 选你刚开容器的那个电路
4. 把 `deploy/` 文件夹**整个拖进去**
5. 确认两次钱包签名（HashPort 用临时钱包代签其余几十笔上传交易）

完成后，你的网站就是 `tape://<你的.tape名字>/`，浏览器通过官方网关打开。**注意：网关网址把名字里的 `.` 全部换成 `-`**（否则 SSL 报错），例如名字 `11.2.4.tape` → `https://11-2-4.tapekit.org/`。

## 提交时填什么（Google 表单）

- **访问链接**：`tape://xxx.x.tape/` 或 `https://xxx-x.tapekit.org/`
- **处理器合约地址 + 电路 ID**：容器工厂里能看到
- **使用了哪些 TapeOut 生态能力**：DeWEB（网站托管）、电路（1 NAND 流片）、容器（ERC-6551）

## 验证清单（提交前）

- [ ] 网站能在官方网关正常打开（`https://xxx-x.tapekit.org/`）
- [ ] 双链切换正常（BNB Chain 挖矿层 ↔ X Layer DeWEB 层）
- [ ] 12 台被撤销电路能显示，交易链接能跳到 bscscan
- [ ] X Layer 安全态势表正常显示

## 常见坑

- **容器工厂默认 BNB Chain**：一定要切到 X Layer（钱包 + 页面都要切）
- **OKB 不够**：X Layer 容器费 0.08 OKB，gas 另算，先备 ~0.1 OKB
- **文件名英文**：deploy/ 里已经是英文文件名，别改中文
- **上链后改数据**：graph_onchain.json 是快照，改数据要重新上传（每次改动都写链）
