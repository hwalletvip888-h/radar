# 海豚Radar · 常驻服务（核心骨架）

> 把原来的「一堆要人手动跑的脚本」升级成「一台 7×24 自动转的机器」。
> 一次启动后：定时增量扫链 → 落 SQLite → 重算评级 → 推送告警 → REST API 供前端/第三方读。

---

## 为什么重做

原来的 `chain_extract.py` / `watcher.py` / `notifier.py` / `engine.py` / `rating.py` 是原型：
- 数据一次性扫完就静止，`rating.py` 要人手动跑
- 三套脚本干同一件事（检测→告警），状态文件各存各的
- 全是散 JSON，没有库、没有历史，前端只能读静态文件

新服务把「扫链 → 富化 → 评级 → 告警 → 服务」串成一条自动管线，数据进 SQLite，历史可追溯。

---

## 架构

```
deweb-search/service/
├── config.py   配置唯一真相源（合约地址 / RPC / topic0 / 评分模型 / 调度间隔）
├── db.py       SQLite 建库 + 连接 + meta 读写（幂等，重跑不重复）
├── ingest.py   增量扫链（只扫新块，自适应 chunk）+ bootstrap（从旧 JSON seed）
├── rate.py     评级引擎（从 DB 读事件 → 写 ratings + 历史 + 快照）
├── alert.py    告警生成 + 推送（复用 common.py 排版，游标去重）
├── api.py      FastAPI REST（events / ratings / alerts / snapshots / stats）
└── run.py      入口：建库 → seed → 补扫 → 首轮评级 → API + 调度线程
```

数据流：

```
real_chain_data.json ──bootstrap──▶ SQLite(data/radar.db)
                                        ▲
                        增量扫链(每120s) ┤  只扫新块，绕开 RPC 限流
                                        │
                        rate.py ────────▶ ratings / rating_history / snapshots
                        alert.py ───────▶ alerts + Telegram/webhook 推送
                        api.py  ────────▶ REST（前端/第三方读）
```

---

## 启动

```bash
cd deweb-search
python -m service.run
```

- 首次启动：从 `real_chain_data.json` seed 历史（幂等，4997 事件 + 12 矿机），补扫到最新块，跑首轮评级。
- API 默认 `http://127.0.0.1:8900`，`/docs` 有自动生成的交互文档。
- 调度线程每 `POLL_INTERVAL`（120s）扫一次新块，重算评级，推送新告警。
- 关掉窗口服务就停；要长期跑可以挂 `nssm` / 计划任务（见「部署」）。

---

## API

| 端点 | 说明 |
|---|---|
| `GET /health` | 健康检查（last_block / events / ratings 数） |
| `GET /api/stats` | 汇总：最新快照 + 按状态/等级分布 |
| `GET /api/ratings` | 电路评级列表（`?status=` `?grade=` `?q=` `?limit=` `?offset=`） |
| `GET /api/ratings/{cid}` | 单电路：评级 + 等级变化历史 + 事件时间线 |
| `GET /api/alerts` | 最近告警 |
| `GET /api/events` | 最近链上事件（`?event=` 过滤） |
| `GET /api/snapshots` | 全局统计历史（趋势用） |

CORS 全开，DeWeb 静态站可直接跨域读。示例：

```bash
curl "http://127.0.0.1:8900/api/ratings?status=revoked&limit=5"
curl "http://127.0.0.1:8900/api/ratings/1965"
```

---

## 评分模型（与旧 rating.py V3 对齐）

| 状态 | 分数 | 等级 |
|---|---|---|
| 撤销 Revoked | 0 | F |
| 被夺最优 Demoted | 75 | B |
| 停挖 Stopped（已映射） | 60 | C |
| 健康（估算） | 100 | A |

当前实测：**12 撤销 F + 1787 夺最优 B = 1799 电路**（与旧 ratings.json 一致）。

---

## 诚实边界（没变）

- **健康电路是估算值**：`miner_count - 撤销 - 夺最优 - 未映射停挖`，不是逐台扫出来的。
- **停挖维度不完整**：`Stopped` 事件只带 key、缺 circuitId，历史 2871 条里只能映射到「与 Demoted 重叠」的那部分（当前 0 条落在非撤销/非夺最优电路上）；**新的停挖事件**由增量摄取逐台 `getMiner` 补齐。
- **撤销事件的 circuit_id 是 NULL**：`Revoked` 只带 key，靠 `miners.key → circuit_id` 关联回电路（详情端点已处理）。
- **「背答案作弊」无公开名单**：`Demoted` 是它的链上代理信号，见 DATA_MODEL.md。

---

## 部署（后面做）

- 开发期先跑 Windows 本机后台。
- 正式：搬到 `radar.hvip.one`（已有 Caddy），Docker 或 systemd 常驻；DeWeb 前端指向它的 API。
- 升级路径：SQLite → Postgres（等用户量起来再换）。
