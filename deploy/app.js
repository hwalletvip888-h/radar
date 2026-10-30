
(() => {
'use strict';

/* ---------- 工具 ---------- */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const num = (n, d = 2) => (n == null || n === '' || isNaN(n)) ? '—' : Number(n).toLocaleString('en-US', { maximumFractionDigits: d });
const short = (a, h = 6, t = 4) => !a ? '' : a.length <= h + t + 1 ? a : `${a.slice(0, h)}…${a.slice(-t)}`;
const isAddr = s => /^0x[0-9a-fA-F]{40}$/.test(s || '');
const rgba = (hex, a) => { const n = parseInt(hex.slice(1), 16); return `rgba(${n >> 16 & 255},${n >> 8 & 255},${n & 255},${a})`; };
const hash = s => { let h = 2166136261; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; };
const pad2 = n => String(n).padStart(2, '0');
const fmtTime = iso => { const d = new Date(iso); return isNaN(d) ? String(iso ?? '—') : `${d.getUTCFullYear()}-${pad2(d.getUTCMonth() + 1)}-${pad2(d.getUTCDate())} ${pad2(d.getUTCHours())}:${pad2(d.getUTCMinutes())} UTC`; };
const fmtBal = (b, sym) => b == null ? `… ${sym}` : b === 0 ? `0 ${sym}` : b < 0.0001 ? `<0.0001 ${sym}` : `${b.toLocaleString('en-US', { maximumFractionDigits: b < 1 ? 4 : b < 1000 ? 3 : 0 })} ${sym}`;
const scrollToEl = sel => { const el = $(sel); if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' }); };
const store = {
  get: k => { try { return localStorage.getItem('dolphinRadar.' + k); } catch (e) { return null; } },
  set: (k, v) => { try { v == null ? localStorage.removeItem('dolphinRadar.' + k) : localStorage.setItem('dolphinRadar.' + k, v); } catch (e) { /* 隐私模式下忽略 */ } },
};

const ICON = {
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
  wallet: '<path d="M19 7V5.5A1.5 1.5 0 0 0 17.5 4h-12A2.5 2.5 0 0 0 3 6.5v11A2.5 2.5 0 0 0 5.5 20h13a1.5 1.5 0 0 0 1.5-1.5V17"/><path d="M21 9h-5a3 3 0 0 0 0 6h5z"/><path d="M16 12h.01"/>',
  copy: '<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V6a2 2 0 0 1 2-2h8"/>',
  ext: '<path d="M14 4h6v6"/><path d="M20 4 11 13"/><path d="M19 14v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h4"/>',
  power: '<path d="M12 3v8"/><path d="M6.3 6.3a8 8 0 1 0 11.4 0"/>',
  shield: '<path d="M12 3 5 6v5.5c0 4.3 2.9 8 7 9.5 4.1-1.5 7-5.2 7-9.5V6z"/><path d="m9 12 2 2 4-4"/>',
  alert: '<path d="M10.3 4.3 2.6 18a2 2 0 0 0 1.7 3h15.4a2 2 0 0 0 1.7-3L13.7 4.3a2 2 0 0 0-3.4 0z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
  chev: '<path d="m6 9 6 6 6-6"/>',
  check: '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
  x: '<path d="M6 6l12 12M18 6 6 18"/>',
  grid: '<rect x="3.5" y="3.5" width="7" height="7" rx="1.5"/><rect x="13.5" y="3.5" width="7" height="7" rx="1.5"/><rect x="3.5" y="13.5" width="7" height="7" rx="1.5"/><rect x="13.5" y="13.5" width="7" height="7" rx="1.5"/>',
  graph: '<circle cx="5.5" cy="6" r="2.5"/><circle cx="18.5" cy="6" r="2.5"/><circle cx="12" cy="18" r="2.5"/><path d="M8 6h8M7 8.2l3.8 7.6M17 8.2l-3.8 7.6"/>',
  route: '<circle cx="6" cy="18" r="2.5"/><circle cx="18" cy="6" r="2.5"/><path d="M8.5 18H16a3.5 3.5 0 0 0 0-7H8a3.5 3.5 0 0 1 0-7h7.5"/>',
  bell: '<path d="M6 8a6 6 0 1 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>',
  cpu: '<rect x="6" y="6" width="12" height="12" rx="2"/><rect x="9.5" y="9.5" width="5" height="5" rx="1"/><path d="M9 2.5V6M15 2.5V6M9 18v3.5M15 18v3.5M2.5 9H6M2.5 15H6M18 9h3.5M18 15h3.5"/>',
  snow: '<path d="M12 2v20M3.3 7l17.4 10M3.3 17 20.7 7"/><path d="m9 4 3 2 3-2M9 20l3-2 3 2"/>',
  coin: '<circle cx="12" cy="12" r="9"/><path d="M14.8 9.2A3 3 0 0 0 12.3 8H11a2 2 0 0 0 0 4h2a2 2 0 0 1 0 4h-1.3a3 3 0 0 1-2.5-1.2M12 6.5V8M12 16v1.5"/>',
  lock: '<rect x="4.5" y="10.5" width="15" height="10" rx="2"/><path d="M8 10.5V7a4 4 0 0 1 8 0v3.5"/>',
  unlock: '<rect x="4.5" y="10.5" width="15" height="10" rx="2"/><path d="M8 10.5V7a4 4 0 0 1 7.6-1.7"/>',
  radar: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><path d="M12 12 18.4 5.6"/><circle cx="12" cy="12" r="1" fill="currentColor"/>',
  cube: '<path d="m12 2.8 8 4.6v9.2l-8 4.6-8-4.6V7.4z"/><path d="m4 7.4 8 4.6 8-4.6M12 12v9.2"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  fit: '<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/>',
  refresh: '<path d="M20 11a8 8 0 1 0-2.3 5.7"/><path d="M20 4.5V11h-6.5"/>',
  compare: '<path d="M12 3v18"/><rect x="3" y="6" width="6" height="12" rx="1.5"/><rect x="15" y="6" width="6" height="12" rx="1.5"/>',
  doc: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M9 13h6M9 17h4"/>',
};
const ic = (n, cls) => `<svg class="ico${cls ? ' ' + cls : ''}" viewBox="0 0 24 24" aria-hidden="true" focusable="false">${ICON[n] || ''}</svg>`;
// 链标识为简化绘制（非官方 Logo），仅用于网络识别
const CHAIN_ICON = {
  bnb: '<svg class="chain-ico" viewBox="0 0 24 24" aria-hidden="true"><path fill="#F0B90B" d="M5.631 3.676 12.001 0l6.367 3.676-2.34 1.358L12 2.716 7.972 5.034l-2.34-1.358Zm12.737 4.636-2.34-1.358L12 9.272 7.972 6.954l-2.34 1.358v2.716l4.026 2.318v4.636L12 19.341l2.341-1.359v-4.636l4.027-2.318V8.312Zm0 7.352v-2.716l-2.34 1.358v2.716l2.34-1.358Zm1.663.96-4.027 2.318v2.717l6.368-3.677V10.63l-2.34 1.358v4.636Zm-2.34-10.63 2.34 1.358v2.716l2.341-1.358V5.994l-2.34-1.358-2.342 1.358ZM9.657 19.926v2.716L12 24l2.341-1.358v-2.716l-2.34 1.358-2.343-1.358Zm-4.027-4.262 2.341 1.358v-2.716l-2.34-1.358v2.716Zm4.027-9.67L12 7.352l2.341-1.358-2.34-1.358-2.343 1.358Zm-5.69 1.358L6.31 5.994 3.968 4.636l-2.34 1.358V8.71l2.34 1.358V7.352Zm0 4.636-2.34-1.358v7.352l6.368 3.677v-2.717l-4.028-2.318v-4.636Z"/></svg>',
  xlayer: '<svg class="chain-ico" viewBox="0 0 24 24" aria-hidden="true"><path fill="#fff" fill-opacity=".5" d="M17.82 14.342v4.672h1.275c.172 0 .312-.14.312-.311v-4.05a.31.31 0 0 0-.312-.312zm0-9.356v4.673h1.275c.172 0 .312-.14.312-.312v-4.05a.31.31 0 0 0-.312-.311z"/><path fill="#fff" fill-opacity=".3" d="M20.209 4.986v4.673h.477c.172 0 .311-.14.311-.312v-4.05a.31.31 0 0 0-.311-.311zm.002 9.356v4.672h.477c.172 0 .312-.14.312-.311v-4.05a.31.31 0 0 0-.312-.312z"/><path fill="#fff" d="M12.026 9.67h-4.03a.31.31 0 0 0-.31.307v4.002c0 .17.138.308.31.308h4.03a.31.31 0 0 0 .31-.308V9.977a.31.31 0 0 0-.31-.308M7.361 4.986h-4.05A.31.31 0 0 0 3 5.297v4.05c0 .172.14.312.312.312h4.05c.171 0 .31-.14.31-.312v-4.05a.31.31 0 0 0-.31-.311m9.343 0h-4.05a.31.31 0 0 0-.311.311v4.05c0 .172.14.312.311.312h4.05c.172 0 .312-.14.312-.312v-4.05a.31.31 0 0 0-.312-.311M7.361 14.33h-4.05a.31.31 0 0 0-.311.313v4.05c0 .171.14.31.312.31h4.05a.31.31 0 0 0 .31-.31v-4.05a.31.31 0 0 0-.31-.312m9.343-.001h-4.05a.31.31 0 0 0-.311.313v4.05c0 .171.14.31.311.31h4.05a.31.31 0 0 0 .312-.31v-4.05a.31.31 0 0 0-.312-.312"/></svg>',
};

/* ---------- 配置 ---------- */
const SITE_TAPE = 'tape://11.2.4.tape';
const CHAINS = {
  xlayer: {
    key: 'xlayer', id: 196, hex: '0xc4', name: 'X Layer', layer: 'DeWEB 层', symbol: 'OKB',
    explorer: 'https://www.oklink.com/xlayer', explorerName: 'OKLink',
    add: { chainId: '0xc4', chainName: 'X Layer Mainnet', nativeCurrency: { name: 'OKB', symbol: 'OKB', decimals: 18 }, rpcUrls: ['https://rpc.xlayer.tech'], blockExplorerUrls: ['https://www.oklink.com/xlayer'] },
  },
  bnb: {
    key: 'bnb', id: 56, hex: '0x38', name: 'BNB Chain', layer: '挖矿层', symbol: 'BNB',
    explorer: 'https://bscscan.com', explorerName: 'BscScan',
    add: { chainId: '0x38', chainName: 'BNB Smart Chain Mainnet', nativeCurrency: { name: 'BNB', symbol: 'BNB', decimals: 18 }, rpcUrls: ['https://bsc-dataseed.bnbchain.org'], blockExplorerUrls: ['https://bscscan.com'] },
  },
};
const chainById = id => Object.values(CHAINS).find(c => c.id === id) || null;
const addrUrl = (k, a) => `${CHAINS[k].explorer}/address/${a}`;
const txUrl = (k, h) => `${CHAINS[k].explorer}/tx/${h}`;

const TYPE = {
  circuit: { label: '电路', color: '#A08CD3', size: 11 },
  processor: { label: '处理器', color: '#8FD3EE', size: 18 },
  token: { label: '代币', color: '#FBF2D3', size: 22 },
  person: { label: '地址', color: '#F0BDD8', size: 10 },
  site: { label: '资金池', color: '#74E2BF', size: 16 },
  miner: { label: '矿机', color: '#F6C66F', size: 12 },
  agent: { label: 'Agent', color: '#8FD3EE', size: 12 },
  container: { label: '容器', color: '#968EAE', size: 12 },
};
const REL = { mines: '挖出', taped_on: '流片于', revealed: '反例举证', operated_by: '矿主', paid_bem_to: '已领走', pooled_into: '流入', depends_on: '依赖', on_chain: '链', challenged: '挑战' };
const STATE = { revoked: '已被反例撤销 · 永久', mining: '挖矿中', stopped: '已停挖', demoted: '被夺最优首创', counterexample: '发现反例', verified: '已验证' };
const ROLE = { challenger: '举证者', miner_owner: '矿主', bem_holder: 'BEM 领取方' };
const CONTRACT_META = {
  factory: { label: '工厂合约', chain: 'xlayer' },
  opener: { label: 'Opener 合约', chain: 'xlayer' },
  accountImpl: { label: '账户实现合约', chain: 'xlayer' },
  bem: { label: 'BEM 代币', chain: 'xlayer' },
  bnbLock: { label: 'BEM 锁仓（BNB Chain）', chain: 'bnb' },
};
const C_REVOKED = '#FF7389', C_CE = '#F6C66F';
const CANVAS_FONT = '-apple-system, "PingFang SC", "Microsoft YaHei", "Segoe UI", sans-serif';
const SWEEP = 6; // 雷达扫描周期（秒），与 CSS 的 sweep/blip 动画一致

const nodeColor = n => n.status === 'revoked' ? C_REVOKED : n.status === 'counterexample' ? C_CE : (TYPE[n.type] ? TYPE[n.type].color : '#968EAE');
const typeLabel = t => (TYPE[t] && TYPE[t].label) || t;
const nodeLabel = n => n.type === 'person' ? short(n.address || n.name) : n.type === 'circuit' ? String(n.name).replace(/^Circuit\s+/, '') : n.name;

const S = {
  chain: 'xlayer', view: 'card',
  G: null, XL: null, PS: null, byId: new Map(), adj: new Map(),
  searched: false, hits: [], groups: {}, traceId: null,
  wallets: new Map(), wallet: null, connecting: null, switching: false, afterConnect: null, scanAddr: '',
  network: null, graphKey: '', drawToken: 0, pendingFocus: null, lastFocus: null,
};

/* ---------- 启动 ---------- */
function init() {
  $$('[data-ic]').forEach(el => { el.outerHTML = ic(el.dataset.ic); });
  $$('[data-chain-ic]').forEach(el => { el.outerHTML = CHAIN_ICON[el.dataset.chainIc]; });
  const saved = store.get('chain');
  if (CHAINS[saved]) S.chain = saved;
  bindEvents();
  discoverWallets();
  setChain(S.chain);
  setView('card');
  loadData();
}

async function loadData() {
  const get = async u => { const r = await fetch(u, { cache: 'no-cache' }); if (!r.ok) throw new Error(`${u} → ${r.status}`); return r.json(); };
  const [g, x, p] = await Promise.allSettled([get('graph_onchain.json'), get('xlayer_data.json'), get('pod-stats.json')]);
  if (g.status === 'fulfilled' && Array.isArray(g.value && g.value.nodes)) {
    S.G = g.value;
    S.byId = new Map(S.G.nodes.map(n => [n.id, n]));
    for (const e of S.G.edges) {
      if (!S.adj.has(e.from)) S.adj.set(e.from, []);
      if (!S.adj.has(e.to)) S.adj.set(e.to, []);
      S.adj.get(e.from).push(e);
      if (e.to !== e.from) S.adj.get(e.to).push(e);
    }
  }
  if (x.status === 'fulfilled') S.XL = x.value;
  if (p.status === 'fulfilled') S.PS = p.value;
  renderHero(); renderRadar(); renderLayerHead(); renderXlayer(); renderBnb(); renderFooter(); renderWallet();
  if (S.view !== 'card') setView(S.view);
  restoreWallet();
}

/* ---------- 首屏 ---------- */
function renderHero() {
  const m = (S.G && S.G.meta) || {}, sec = (S.XL && S.XL.security) || {};
  if (S.G) {
    $('#heroLead').innerHTML = `海豚Radar 运行于 X Layer DeWEB，持续扫描 BNB 挖矿层的反例审查：已有 <b>${num(m.revoked_circuits, 0)} 台电路</b>被永久撤销，<b>${num(m.total_frozen_bem)} BEM</b> 冻结未领。连接钱包，看看你的地址是否在告警名单上。`;
    $('#hcBnb').innerHTML = `<b class="t-danger">${num(m.revoked_circuits, 0)}</b> 台被撤销 · <b>${num(m.total_frozen_bem)}</b> BEM 冻结`;
  } else $('#hcBnb').textContent = '数据未加载';
  $('#hcXl').innerHTML = S.XL ? `<b class="t-warn">${(sec.findings || []).length}</b> 项安全发现 · ${sec.factorySealed ? '工厂已封印' : '工厂未封印'}` : '数据未加载';
}

function renderRadar() {
  if (!S.G) return;
  const nodes = S.G.nodes, pts = [];
  const add = (n, color, size, rMin, rMax) => {
    const h = hash(n.id), ang = (h % 3600) / 10, r = rMin + ((h >>> 12) % 1000) / 1000 * (rMax - rMin), rad = ang * Math.PI / 180;
    const x = 50 + Math.sin(rad) * r * 50, y = 50 - Math.cos(rad) * r * 50;
    // 光点在扫描线经过的那一刻点亮：负延迟让第一圈就对齐
    pts.push(`<i class="blip" style="left:${x.toFixed(2)}%;top:${y.toFixed(2)}%;--c:${color};--s:${size}px;animation-delay:${(ang / 360 * SWEEP - SWEEP).toFixed(2)}s"></i>`);
  };
  const ce = nodes.filter(n => n.status === 'counterexample'), rev = nodes.filter(n => n.status === 'revoked'), procs = nodes.filter(n => n.type === 'processor');
  ce.slice(0, 42).forEach(n => add(n, C_CE, 4, .5, .96));
  procs.forEach(n => add(n, TYPE.processor.color, 7, .5, .72));
  rev.forEach(n => add(n, C_REVOKED, 9, .52, .92));
  $('#radarBlips').innerHTML = pts.join('');
  $('#radarLegend').innerHTML = `<span><i style="--c:${C_REVOKED}"></i>已撤销 <b>${rev.length}</b></span><span><i style="--c:${C_CE}"></i>发现反例 <b>${ce.length}</b></span><span><i style="--c:${TYPE.processor.color}"></i>处理器 <b>${procs.length}</b></span>`;
}

/* ---------- 网络切换（视图 + 钱包） ---------- */
function setChain(key) {
  if (!CHAINS[key]) return;
  S.chain = key;
  store.set('chain', key);
  const sw = $('#chainSwitch');
  sw.dataset.active = key;
  $$('.cs-opt', sw).forEach(b => { const on = b.dataset.chain === key; b.setAttribute('aria-checked', String(on)); b.tabIndex = on ? 0 : -1; });
  $$('.hc').forEach(b => b.classList.toggle('is-active', b.dataset.chain === key));
  $('#viewXlayer').hidden = key !== 'xlayer';
  $('#viewBnb').hidden = key !== 'bnb';
  renderLayerHead();
  renderWallet();
  if (key === 'bnb' && S.view === 'graph') requestAnimationFrame(() => drawGraph());
}

// 用户主动切换：视图立即切换，已连接钱包时同步请求钱包切换网络
async function selectChain(key, opts = {}) {
  setChain(key);
  // 已滚过网络区顶部时回到区头，避免停在新视图的中段
  if (opts.scroll || $('#layer').getBoundingClientRect().top < 0) scrollToEl('#layer');
  const w = S.wallet;
  if (w && w.chainId !== CHAINS[key].id) await ensureWalletChain(CHAINS[key]);
}

function renderLayerHead() {
  const c = CHAINS[S.chain], chips = [`<span class="chip">Chain ID ${c.id}</span>`];
  let sub = '';
  if (c.key === 'bnb') {
    const sealed = S.PS ? /^0x0{40}$/i.test(S.PS.owner || '') : !!(S.XL && S.XL.comparison && S.XL.comparison.bnb && S.XL.comparison.bnb.sealed);
    sub = `存量安全 · PoD 挖矿合约${sealed ? '已封印（owner = 0x0）' : ''}`;
    const blk = (S.G && S.G.meta && S.G.meta.latestBlock) || (S.PS && S.PS.block);
    if (blk) chips.push(`<span class="chip">${ic('cube')}区块 #${num(blk, 0)}</span>`);
    if (S.PS && S.PS.generatedAt) chips.push(`<span class="chip">${ic('clock')}快照 ${fmtTime(S.PS.generatedAt)}</span>`);
    if (sealed) chips.push(`<span class="chip ok">${ic('lock')}已封印</span>`);
  } else {
    const sec = (S.XL && S.XL.security) || {};
    sub = `增量基建 · 海豚Radar 本身就部署在这条链上（${SITE_TAPE}）`;
    if (S.XL && S.XL.updatedAt) chips.push(`<span class="chip">${ic('clock')}更新于 ${esc(S.XL.updatedAt)}</span>`);
    if (S.XL) chips.push(sec.factorySealed ? `<span class="chip ok">${ic('lock')}工厂已封印</span>` : `<span class="chip warn">${ic('unlock')}工厂未封印</span>`);
  }
  $('#lhBadge').innerHTML = CHAIN_ICON[c.key];
  $('#lhTitle').textContent = `${c.name} · ${c.layer}`;
  $('#lhSub').textContent = sub;
  $('#lhMeta').innerHTML = chips.join('');
}

const kpi = (v, icon, label, value, foot) => `<div class="kpi k-${v}"><div class="kpi-top">${ic(icon)}<span>${label}</span></div><div class="kpi-val">${value}</div>${foot ? `<div class="kpi-foot">${foot}</div>` : ''}</div>`;
const emptyHTML = (icon, title, sub) => `<div class="empty">${ic(icon)}<b>${title}</b>${sub ? `<span>${sub}</span>` : ''}</div>`;

/* ---------- X Layer · DeWEB 层 ---------- */
function renderXlayer() {
  const el = $('#viewXlayer');
  if (!S.XL) { el.innerHTML = emptyHTML('radar', 'X Layer 数据未加载', '请确认 xlayer_data.json 与页面在同一目录'); return; }
  const XL = S.XL, sec = XL.security || {}, ct = XL.contracts || {}, cmp = XL.comparison || {}, b = cmp.bnb || {}, x = cmp.xlayer || {};
  const kpis = [
    kpi(sec.factorySealed ? 'ok' : 'warn', sec.factorySealed ? 'lock' : 'unlock', '工厂合约', sec.factorySealed ? '已封印' : '未封印', sec.factoryOwner ? `owner ${short(sec.factoryOwner)} · ${sec.factorySealed ? '不可升级' : '可升级'}` : ''),
    kpi('lav', 'coin', 'BEM 跨链流通', num(ct.bem && ct.bem.circulating), ct.bnbLock && ct.bnbLock.locked != null ? `BNB Chain 1:1 锁仓 ${num(ct.bnbLock.locked)}` : ''),
    kpi(sec.mining ? 'ok' : 'muted', 'cpu', 'PoD 挖矿', sec.mining ? '有' : '无', sec.mining ? '' : 'DeWEB 层暂无矿机'),
    kpi(sec.challengeMechanism ? 'ok' : 'muted', 'shield', '反例审查', sec.challengeMechanism ? '有' : '无', 'challenge / Revoked 机制'),
  ];
  const yn = v => v ? `<span class="tag ok">${ic('check')}有</span>` : `<span class="tag muted">${ic('x')}无</span>`;
  const sealTag = (v, okTxt, badTxt) => v ? `<span class="tag ok">${ic('lock')}${okTxt}</span>` : `<span class="tag bad">${ic('unlock')}${badTxt}</span>`;
  const cnt = (v, d) => `<span class="mono${v ? ' t-danger' : ''}">${num(v || 0, d)}</span>`;
  const rows = [
    ['挖矿合约封印', sealTag(b.sealed, '已封印 · owner=0x0', '未封印'), sealTag(x.sealed, '已封印', '未封印 · 3/5 多签可升级')],
    ['PoD 挖矿', yn(b.mining), yn(x.mining)],
    ['反例审查（challenge / Revoked）', yn(b.challenge), yn(x.challenge)],
    ['在挖矿机', `<span class="mono">${num(b.minerCount || 0, 0)}</span>`, `<span class="mono">${num(x.minerCount || 0, 0)}</span>`],
    ['被撤销矿机', cnt(b.revoked, 0), cnt(x.revoked, 0)],
    ['冻结未领 BEM', cnt(b.frozenBem, 2), cnt(x.frozenBem, 2)],
  ];
  const finding = (f, i) => {
    const m = String(f).match(/^(.{2,40}?)(：|——|:)(.+)$/);
    return `<li><span class="f-idx">${pad2(i + 1)}</span><div>${m ? `<b>${esc(m[1])}</b><p>${esc(m[3])}</p>` : `<p>${esc(f)}</p>`}</div></li>`;
  };
  const contract = ([key, v]) => {
    const meta = CONTRACT_META[key] || { label: key, chain: 'xlayer' }, a = v.address || '';
    const extra = [];
    if (v.owner) extra.push(`<span>owner <b>${short(v.owner)}</b></span>`);
    if (v.impl) extra.push(`<span>impl <b>${short(v.impl)}</b></span>`);
    if (v.circulating != null) extra.push(`<span>流通 <b>${num(v.circulating)}</b> BEM</span>`);
    if (v.locked != null) extra.push(`<span>锁仓 <b>${num(v.locked)}</b> BEM</span>`);
    extra.push(`<span>${CHAINS[meta.chain].name}</span>`);
    const seal = v.sealed === false ? `<span class="chip sm warn">${ic('unlock')}未封印</span>` : v.sealed ? `<span class="chip sm ok">${ic('lock')}已封印</span>` : '';
    return `<div class="contract"><div class="ct-head"><h4>${esc(meta.label)}</h4><code class="ct-key">${esc(key)}</code>${seal}</div>
      <div class="addr-line"><code title="${esc(a)}">${esc(short(a, 10, 8))}</code><button class="icon-btn" type="button" data-copy="${esc(a)}" aria-label="复制地址">${ic('copy')}</button><a class="icon-btn" href="${addrUrl(meta.chain, a)}" target="_blank" rel="noopener" aria-label="在 ${CHAINS[meta.chain].explorerName} 查看">${ic('ext')}</a></div>
      <div class="ct-meta">${extra.join('')}</div></div>`;
  };
  const revoked = (S.G && S.G.meta && S.G.meta.revoked_circuits) || b.revoked || 0;
  el.innerHTML = `<div class="view">
    <div class="banner">${ic('radar')}<p><b>海豚Radar 双链安全警报系统</b> · 本站就运行在 X Layer DeWEB 上（<code>${SITE_TAPE}</code>）。它同时监控两条链：<b>BNB 挖矿层</b>（存量安全）与 <b>X Layer DeWEB 层</b>（增量基建）。X Layer 目前几乎空白，正是卡位期。</p></div>
    <div class="kpis">${kpis.join('')}</div>
    <div class="xl-grid">
      <section class="box pad"><div class="sec-title"><h3>${ic('compare')}双链安全态势对比</h3></div>
        <div class="cmp-wrap"><table class="cmp"><thead><tr><th>维度</th><th><span class="th-chain">${CHAIN_ICON.bnb}${esc(b.label || 'BNB Chain · 挖矿层')}</span></th><th class="col-on"><span class="th-chain">${CHAIN_ICON.xlayer}${esc(x.label || 'X Layer · DeWEB 层')}</span></th></tr></thead>
        <tbody>${rows.map(r => `<tr><td>${r[0]}</td><td>${r[1]}</td><td class="col-on">${r[2]}</td></tr>`).join('')}</tbody></table></div>
      </section>
      <section class="box pad"><div class="sec-title"><h3>${ic('alert')}X Layer 安全发现</h3><span class="chip sm">链上实测</span></div>
        <ol class="findings">${(sec.findings || []).map(finding).join('') || '<li><p>暂无发现</p></li>'}</ol>
      </section>
    </div>
    <section style="margin-top:16px"><div class="sec-title"><h3>${ic('doc')}X Layer 关键合约</h3><span class="note">可复制地址 · 在区块浏览器中查看</span></div>
      <div class="contracts">${Object.entries(ct).map(contract).join('')}</div>
    </section>
    <button class="jump" type="button" data-chain="bnb">${CHAIN_ICON.bnb}<span><b>切换到 BNB Chain · 挖矿层</b><small>查看 ${num(revoked, 0)} 条撤销告警、关系图与影响追溯</small></span>${ic('arrow')}</button>
  </div>`;
}

/* ---------- BNB Chain · 挖矿层 ---------- */
function renderBnb() {
  if (!S.G) {
    $('#bnbKpis').innerHTML = '';
    $('#panel-card').innerHTML = emptyHTML('radar', '暂未读取到链上图谱', '请先运行 graph_onchain.py 生成 graph_onchain.json，并与页面放在同一目录');
    return;
  }
  const m = S.G.meta || {}, ev = m.eventCounts || {}, PS = S.PS || {};
  $('#bnbKpis').innerHTML = [
    kpi('danger', 'alert', '被撤销电路', num(m.revoked_circuits, 0), '链上终局 · 永久撤销'),
    kpi('danger', 'snow', '冻结未领 BEM', num(m.total_frozen_bem), '撤销后奖励不可领取'),
    kpi('lav', 'shield', '反例举证', num(ev.CounterexampleAdded, 0), '验证的验证'),
    kpi('ok', 'cpu', '全网在挖矿机', num(PS.minerCount, 0), PS.verifMinerCount != null ? `其中 ${num(PS.verifMinerCount, 0)} 台已验证` : ''),
  ].join('');
  const sub = [];
  if (PS.taskCount != null) sub.push(`题库 <b>${num(PS.taskCount, 0)}</b> 题${PS.tasksFrozen ? '（已冻结）' : ''}`);
  if (ev.Stopped != null) sub.push(`已停挖 <b>${num(ev.Stopped, 0)}</b>`);
  if (ev.Demoted != null) sub.push(`被夺最优首创 <b>${num(ev.Demoted, 0)}</b>`);
  if (PS.mining) sub.push(`挖矿合约 <a class="ext" href="${addrUrl('bnb', PS.mining)}" target="_blank" rel="noopener">${short(PS.mining)}${ic('ext')}</a>`);
  $('#bnbSub').innerHTML = sub.map(s => `<span>${s}</span>`).join('');
  $('#tabAlertCount').textContent = m.revoked_circuits || '';
  renderAddrRadar();
  runSearch($('#q').value);
}

/* ---------- 对象搜索（意图解析） ---------- */
const STOP = /的|了|吗|呢|吧|能|什么|有|想|找|搜索|搜|看看|看|一下|帮我|给我|哪些|哪个|所有|全部|列出|显示/g;
function parseQuery(raw) {
  let q = ` ${raw.trim().toLowerCase()} `;
  const f = { types: new Set(), parts: [], kws: [] };
  const take = (re, fn) => { const m = q.match(re); if (m) { q = q.replace(new RegExp(re.source, 'gi'), ' '); fn(m); } };
  take(/0x[0-9a-f]{4,40}/, m => { f.address = m[0]; f.parts.push(`地址 <b>${esc(short(m[0], 8, 6))}</b>`); });
  take(/(?:题|task|任务)\s*#?\s*(\d+)/, m => { f.taskId = +m[1]; f.parts.push(`题号 <b>#${f.taskId}</b>`); });
  take(/#\s*(\d{2,6})/, m => { f.num = +m[1]; f.parts.push(`编号 <b>#${f.num}</b>`); });
  take(/被?撤销|revoked?|吊销/, () => { f.status = 'revoked'; f.parts.push('状态 <b>已撤销</b>'); });
  take(/举证者|举证人|挑战者|challenger/, () => { f.role = 'challenger'; f.parts.push('角色 <b>举证者</b>'); });
  take(/矿主|registrant/, () => { f.role = 'miner_owner'; f.parts.push('角色 <b>矿主</b>'); });
  if (!f.status) take(/反例|counterexample/, () => { f.status = 'counterexample'; f.parts.push('状态 <b>发现反例</b>'); });
  take(/代币|token/, () => { f.types.add('token'); f.parts.push('找 <b>代币</b>'); });
  take(/电路|circuit|网表|nand|矿机|算力/, () => { f.types.add('circuit'); f.parts.push('找 <b>电路</b>'); });
  take(/处理器|processor/, () => { f.types.add('processor'); f.parts.push('找 <b>处理器</b>'); });
  take(/pancakeswap|pancake|资金池|池子|流动性|dex/, () => { f.types.add('site'); f.parts.push('找 <b>资金池</b>'); });
  for (const p of S.G.nodes.filter(n => n.type === 'processor')) {
    const name = p.name.toLowerCase();
    if (q.includes(name)) { f.processor = p.name; q = q.split(name).join(' '); f.parts.push(`处理器 <b>${esc(p.name)}</b>`); }
  }
  take(/x\s*layer/, () => f.parts.push('在 <b>X Layer</b>'));
  take(/\bbnb\b|\bbsc\b/, () => f.parts.push('在 <b>BNB</b>'));
  f.kws = q.replace(STOP, ' ').split(/[\s,，、/|]+/).filter(s => s && !/^[#·.。+]+$/.test(s));
  f.kws.forEach(k => f.parts.unshift(`关键词 <b>${esc(k)}</b>`));
  return f;
}
function scoreNode(n, f) {
  const hay = [n.name, n.symbol, n.id, n.address, n.processor, n.status, n.status && STATE[n.status], n.reason, n.challenger, n.registrant, n.role && ROLE[n.role], n.category].filter(Boolean).join(' ').toLowerCase();
  let s = 0, need = 0, got = 0;
  const hit = (cond, w) => { need++; if (cond) { s += w; got++; } };
  if (f.address) hit(hay.includes(f.address), 6);
  if (f.taskId != null) hit(n.taskId === f.taskId, 4);
  if (f.num != null) hit(n.num === f.num, 4);
  if (f.status) hit(n.status === f.status, 3);
  if (f.role) hit(n.role === f.role, 3);
  if (f.processor) hit(n.processor === f.processor || (n.type === 'processor' && n.name === f.processor), 3);
  if (f.types.size) hit(f.types.has(n.type), 2);
  for (const k of f.kws) hit(hay.includes(k), 2);
  return { s, need, got };
}
const rank = n => (n.status === 'revoked' ? 1000 : n.status === 'counterexample' ? 100 : 0) + (n.debtBEM || 0) / 10;
// 先要求所有条件同时满足；没有完全命中时退回到命中条件最多的对象
function matchNodes(f) {
  const scored = S.G.nodes.map(n => Object.assign({ n }, scoreNode(n, f)));
  if (!scored.length || !scored[0].need) return S.G.nodes.map(n => ({ n, s: 1 }));
  const any = scored.filter(x => x.got > 0);
  if (!any.length) return [];
  const full = any.filter(x => x.got === x.need);
  const top = Math.max(...any.map(x => x.got));
  return (full.length ? full : any.filter(x => x.got === top)).sort((a, b) => b.s - a.s || rank(b.n) - rank(a.n));
}
function runSearch(raw) {
  if (!S.G) return;
  const q = String(raw || '').trim();
  let hits;
  if (!q) {
    hits = S.G.nodes.filter(n => n.status === 'revoked').sort((a, b) => rank(b) - rank(a)).map(n => ({ n, s: 1 }));
    S.searched = false; S.hits = [];
    $('#intent').innerHTML = `默认视图：<b>被撤销电路</b> · ${hits.length} 个对象 · 试试上面的推荐查询`;
  } else {
    const f = parseQuery(q);
    hits = matchNodes(f);
    S.searched = true; S.hits = hits;
    $('#intent').innerHTML = `理解成：${f.parts.length ? f.parts.join(' + ') : '<b>探索全部对象</b>'} · 找到 <b>${hits.length}</b> 个对象 <button class="link-btn" type="button" data-act="clear-search">清除</button>`;
  }
  renderCards(hits);
  if (S.view === 'graph' && S.chain === 'bnb') drawGraph();
}

const ORDER = ['circuit', 'person', 'processor', 'token', 'site', 'miner', 'agent', 'container'];
function renderCards(hits) {
  const el = $('#panel-card');
  if (!hits.length) { el.innerHTML = emptyHTML('search', '没找到匹配的对象', '换个关键词，或试试：被撤销的 / Behemoth / 题 260 / 0x 地址'); return; }
  const by = {};
  for (const h of hits) (by[h.n.type] = by[h.n.type] || []).push(h.n);
  S.groups = by;
  const types = ORDER.concat(Object.keys(by).filter(t => !ORDER.includes(t))).filter(t => by[t]);
  el.innerHTML = `<div class="view">${types.map(t => {
    const list = by[t], LIMIT = 12, color = (TYPE[t] && TYPE[t].color) || '#968EAE';
    return `<section class="group" data-type="${esc(t)}"><div class="group-head"><i style="--c:${color}"></i>${typeLabel(t)}<span>${list.length}</span></div>
      <div class="cards">${list.slice(0, LIMIT).map(cardHTML).join('')}</div>
      ${list.length > LIMIT ? `<button class="btn btn-ghost btn-sm more" type="button" data-more="${esc(t)}">显示全部 ${list.length} 个</button>` : ''}</section>`;
  }).join('')}</div>`;
}
function expandGroup(t) {
  const sec = $(`#panel-card .group[data-type="${t}"]`), list = S.groups[t];
  if (!sec || !list) return;
  $('.cards', sec).innerHTML = list.map(cardHTML).join('');
  const more = $('.more', sec);
  if (more) more.remove();
}
function relsHTML(n) {
  const groups = new Map();
  for (const e of S.adj.get(n.id) || []) {
    const out = e.from === n.id, k = e.type + (out ? '>' : '<');
    if (!groups.has(k)) groups.set(k, { type: e.type, out, ids: [] });
    groups.get(k).ids.push(out ? e.to : e.from);
  }
  if (!groups.size) return '';
  const label = id => { const o = S.byId.get(id); return o ? nodeLabel(o) : id.split(':').slice(1).join(':') || id; };
  const items = [...groups.values()].slice(0, 5).map(g => {
    const first = S.byId.get(g.ids[0]);
    const names = g.ids.length > 2 ? `${g.ids.length} 个${first ? typeLabel(first.type) : '对象'}` : g.ids.map(id => esc(label(id))).join('、');
    return `<span><b>${REL[g.type] || esc(g.type)}</b>${g.out ? '→' : '←'} ${names}</span>`;
  });
  return `<div class="oc-rels">${items.join('')}</div>`;
}
function cardHTML(n) {
  const rev = n.status === 'revoked', person = n.type === 'person';
  const chips = [`<span class="chip sm type" style="--c:${nodeColor(n)}">${typeLabel(n.type)}</span>`];
  if (n.status) chips.push(`<span class="chip sm ${rev ? 'danger' : n.status === 'counterexample' ? 'warn' : ''}">${STATE[n.status] || esc(n.status)}</span>`);
  if (n.processor) chips.push(`<span class="chip sm">${esc(n.processor)}</span>`);
  if (n.taskId != null) chips.push(`<span class="chip sm">题 #${esc(n.taskId)}</span>`);
  if (n.gateCount != null) chips.push(`<span class="chip sm">${esc(n.gateCount)} 门</span>`);
  if (n.role) chips.push(`<span class="chip sm lav">${ROLE[n.role] || esc(n.role)}</span>`);
  if (n.multiplier != null) chips.push(`<span class="chip sm">倍率 ×${esc(n.multiplier)}</span>`);
  if (n.cap != null) chips.push(`<span class="chip sm">上限 ${num(n.cap, 0)}</span>`);
  let desc = '';
  if (n.reason) desc = esc(n.reason);
  else if (n.receivedBEM != null) desc = `已流入 <b>${num(n.receivedBEM)}</b> BEM`;
  else if (n.address && !person) desc = `<span class="mono">${esc(short(n.address, 10, 8))}</span>`;
  if (rev) desc += `<br>冻结未领 <b class="t-danger">${num(n.debtBEM, 4)} BEM</b> · 已领走 <b>${num(n.claimedBEM, 4)} BEM</b>`;
  const acts = [];
  if (n.type === 'circuit') acts.push(`<button class="link-btn" type="button" data-trace="${esc(n.id)}">${ic('route')}追溯影响</button>`);
  if (person) acts.push(`<button class="link-btn" type="button" data-addr="${esc(n.address)}">${ic('shield')}地址雷达</button>`);
  const a = n.address || n.processorAddr;
  if (a) acts.push(`<a class="link-btn" href="${addrUrl('bnb', a)}" target="_blank" rel="noopener">${ic('ext')}BscScan</a>`);
  if (n.tx) acts.push(`<a class="link-btn" href="${txUrl('bnb', n.tx)}" target="_blank" rel="noopener">${ic('ext')}撤销交易</a>`);
  const title = person ? `<span class="mono">${esc(short(n.address || n.name, 8, 6))}</span><button class="icon-btn" type="button" data-copy="${esc(n.address || n.name)}" aria-label="复制地址">${ic('copy')}</button>` : esc(n.name);
  return `<article class="ocard${rev ? ' is-revoked' : ''}"><div class="oc-title"><h4>${title}</h4></div>
    <div class="oc-chips">${chips.join('')}</div>${desc ? `<p class="oc-desc">${desc}</p>` : ''}${relsHTML(n)}
    ${acts.length ? `<div class="oc-actions">${acts.join('')}</div>` : ''}</article>`;
}

/* ---------- 关系图（vis-network 按需加载） ---------- */
let visPromise = null;
function loadVis() {
  if (window.vis && window.vis.Network) return Promise.resolve();
  if (!visPromise) visPromise = new Promise((res, rej) => {
    const s = document.createElement('script');
    s.src = 'vendor/vis-network.min.js';
    s.onload = () => (window.vis && window.vis.Network ? res() : rej(new Error('vis missing')));
    s.onerror = () => { visPromise = null; rej(new Error('load failed')); };
    document.head.appendChild(s);
  });
  return visPromise;
}
function graphIds() {
  const ids = new Set(), addNeighbors = base => base.forEach(id => { ids.add(id); for (const e of S.adj.get(id) || []) { ids.add(e.from); ids.add(e.to); } });
  if (S.searched && S.hits.length) {
    const base = S.hits.slice(0, 40).map(h => h.n.id);
    if (base.length <= 8) addNeighbors(base); else base.forEach(id => ids.add(id));
  } else {
    addNeighbors(S.G.nodes.filter(n => n.status === 'revoked').map(n => n.id));
    for (const e of S.G.edges) if (e.type === 'pooled_into' && ids.has(e.from)) ids.add(e.to);
  }
  return ids;
}
function visNode(n) {
  const c = nodeColor(n), rev = n.status === 'revoked';
  const title = [n.type === 'person' ? (n.address || n.name) : n.name, typeLabel(n.type) + (n.status ? ' · ' + (STATE[n.status] || n.status) : '') + (n.role ? ' · ' + (ROLE[n.role] || n.role) : '')];
  if (rev) title.push(`冻结未领 ${num(n.debtBEM, 4)} BEM`);
  return {
    id: n.id, label: nodeLabel(n), title: title.join('\n'),
    size: rev ? 15 : ((TYPE[n.type] && TYPE[n.type].size) || 10),
    color: { background: rgba(c, rev ? .38 : .2), border: c, highlight: { background: rgba(c, .55), border: '#F7F5FB' }, hover: { background: rgba(c, .45), border: c } },
    font: { size: rev ? 13 : n.type === 'person' ? 11 : 12, color: rev ? '#FFD7DE' : '#E9E4F5' },
    shadow: { enabled: true, color: rgba(c, rev ? .65 : .25), size: rev ? 22 : 10, x: 0, y: 0 },
  };
}
function visOptions() {
  return {
    autoResize: true, width: '100%', height: '100%',
    physics: { stabilization: { iterations: 220 }, barnesHut: { gravitationalConstant: -6500, springLength: 130, springConstant: 0.03, damping: 0.25 } },
    interaction: { hover: true, tooltipDelay: 120 },
    nodes: { shape: 'dot', borderWidth: 2, font: { face: CANVAS_FONT, strokeWidth: 4, strokeColor: '#100d18' } },
    edges: {
      width: 1, selectionWidth: 1.5, arrows: { to: { enabled: true, scaleFactor: 0.45 } }, smooth: { type: 'continuous', roundness: 0.2 },
      color: { color: 'rgba(160,140,211,.34)', highlight: '#C3B4F0', hover: '#C3B4F0' },
      font: { face: CANVAS_FONT, color: '#8E86A6', size: 10, strokeWidth: 0, align: 'middle' },
    },
  };
}
async function drawGraph(force) {
  const el = $('#graph');
  if (!S.G) { el.innerHTML = `<div class="g-loading">${ic('radar')}暂未读取到链上图谱</div>`; return; }
  const ids = graphIds(), key = [...ids].sort().join('|');
  if (!force && S.network && S.graphKey === key) { S.network.redraw(); applyFocus(); return; }
  const token = ++S.drawToken;
  if (!(window.vis && window.vis.Network)) {
    el.innerHTML = '<div class="g-loading"><span class="spin"></span>正在加载关系图组件…</div>';
    try { await loadVis(); } catch (e) {
      if (token === S.drawToken) el.innerHTML = `<div class="g-loading">${ic('alert')}关系图组件加载失败：未找到 vendor/vis-network.min.js</div>`;
      return;
    }
    if (token !== S.drawToken) return;
  }
  if (S.network) { S.network.destroy(); S.network = null; }
  el.innerHTML = '';
  const nodes = [...ids].map(id => S.byId.get(id)).filter(Boolean);
  // 同一对节点之间的多条关系合并成一条边
  const pairs = new Map();
  for (const e of S.G.edges) {
    if (!ids.has(e.from) || !ids.has(e.to)) continue;
    const k = e.from + '>' + e.to, label = REL[e.type] || e.type;
    if (pairs.has(k)) pairs.get(k).label += ' · ' + label; else pairs.set(k, { from: e.from, to: e.to, label });
  }
  S.graphKey = key;
  const net = S.network = new vis.Network(el, { nodes: new vis.DataSet(nodes.map(visNode)), edges: new vis.DataSet([...pairs.values()]) }, visOptions());
  net.on('click', p => showNodeInfo(p.nodes[0]));
  net.on('hoverNode', () => { el.style.cursor = 'pointer'; });
  net.on('blurNode', () => { el.style.cursor = ''; });
  net.once('stabilizationIterationsDone', () => { if (S.pendingFocus) applyFocus(); else net.fit({ animation: { duration: 600, easingFunction: 'easeInOutQuad' } }); });
  const present = new Map();
  for (const n of nodes) { const k = n.status === 'revoked' || n.status === 'counterexample' ? n.status : n.type; present.set(k, (present.get(k) || 0) + 1); }
  const legendName = { revoked: '已撤销电路', counterexample: '发现反例' };
  $('#gLegend').innerHTML = [...present].map(([k, c]) => `<span><i style="--c:${k === 'revoked' ? C_REVOKED : k === 'counterexample' ? C_CE : ((TYPE[k] && TYPE[k].color) || '#968EAE')}"></i>${legendName[k] || typeLabel(k)} ${c}</span>`).join('');
  const rev = S.G.nodes.filter(n => n.status === 'revoked').length;
  $('#gHint').textContent = S.searched ? `搜索结果 · ${nodes.length} 个节点 · 点击节点查看详情` : `默认：${rev} 台被撤销电路 + 一跳邻居 · 点击节点查看详情`;
  $('#gInfo').hidden = true;
}
function applyFocus() {
  const id = S.pendingFocus, net = S.network;
  if (!id || !net) return;
  S.pendingFocus = null;
  try { net.selectNodes([id]); net.focus(id, { scale: 1.15, animation: { duration: 600, easingFunction: 'easeInOutQuad' } }); showNodeInfo(id); } catch (e) { /* 节点不在当前图中 */ }
}
function showNodeInfo(id) {
  const box = $('#gInfo');
  const n = id && S.byId.get(id);
  if (!n) { box.hidden = true; return; }
  const rows = [], add = (k, v) => { if (v != null && v !== '') rows.push(`<dt>${k}</dt><dd>${v}</dd>`); };
  add('类型', typeLabel(n.type));
  add('状态', n.status ? (STATE[n.status] || esc(n.status)) : '');
  add('角色', n.role ? (ROLE[n.role] || esc(n.role)) : '');
  add('处理器', esc(n.processor));
  add('题号', n.taskId != null ? '#' + esc(n.taskId) : '');
  add('门数', esc(n.gateCount));
  add('冻结未领', n.debtBEM != null ? `${num(n.debtBEM, 4)} BEM` : '');
  add('已领走', n.claimedBEM != null ? `${num(n.claimedBEM, 4)} BEM` : '');
  add('举证者', n.challenger ? short(n.challenger) : '');
  add('矿主', n.registrant ? short(n.registrant) : '');
  add('地址', n.address ? short(n.address, 8, 6) : '');
  add('倍率', n.multiplier != null ? '×' + esc(n.multiplier) : '');
  add('流入', n.receivedBEM != null ? `${num(n.receivedBEM)} BEM` : '');
  const acts = [];
  if (n.type === 'circuit') acts.push(`<button class="btn btn-ghost btn-sm" type="button" data-trace="${esc(n.id)}">${ic('route')}追溯影响</button>`);
  if (n.type === 'person') acts.push(`<button class="btn btn-ghost btn-sm" type="button" data-addr="${esc(n.address)}">${ic('shield')}地址雷达</button>`);
  const a = n.address || n.processorAddr;
  if (a) acts.push(`<a class="btn btn-ghost btn-sm" href="${addrUrl('bnb', a)}" target="_blank" rel="noopener">${ic('ext')}BscScan</a>`);
  if (n.tx) acts.push(`<a class="btn btn-ghost btn-sm" href="${txUrl('bnb', n.tx)}" target="_blank" rel="noopener">${ic('ext')}撤销交易</a>`);
  box.innerHTML = `<div class="gi-head"><span class="dot" style="--c:${nodeColor(n)}"></span><h4>${esc(n.type === 'person' ? short(n.address || n.name, 8, 6) : n.name)}</h4><button class="icon-btn" type="button" data-act="close-info" aria-label="关闭">${ic('x')}</button></div>
    <dl class="kv">${rows.join('')}</dl>${acts.length ? `<div class="gi-acts">${acts.join('')}</div>` : ''}`;
  box.hidden = false;
}

/* ---------- 影响追溯：电路 → 矿机 → BEM → 下游 ---------- */
function renderTrace() {
  const el = $('#panel-trace');
  if (!S.G) { el.innerHTML = ''; return; }
  const circuits = S.G.nodes.filter(n => n.type === 'circuit');
  if (!circuits.length) { el.innerHTML = emptyHTML('route', '图里还没有电路节点', ''); return; }
  const rev = circuits.filter(n => n.status === 'revoked').sort((a, b) => (b.debtBEM || 0) - (a.debtBEM || 0));
  const ce = circuits.filter(n => n.status === 'counterexample').sort((a, b) => a.name.localeCompare(b.name, 'en', { numeric: true }));
  const rest = circuits.filter(n => n.status !== 'revoked' && n.status !== 'counterexample');
  const opt = n => `<option value="${esc(n.id)}">${esc(n.name)}${n.debtBEM != null ? ` · 冻结 ${num(n.debtBEM)} BEM` : ''}</option>`;
  const og = (label, list) => list.length ? `<optgroup label="${label}（${list.length}）">${list.map(opt).join('')}</optgroup>` : '';
  const sel = S.byId.has(S.traceId) ? S.traceId : (rev[0] || circuits[0]).id;
  el.innerHTML = `<div class="view"><div class="trace-bar"><label for="circuitSel">选择电路</label><div class="select"><select id="circuitSel">${og('已被反例撤销', rev)}${og('发现反例', ce)}${og('其他电路', rest)}</select>${ic('chev')}</div></div><div id="traceOut"></div></div>`;
  $('#circuitSel').value = sel;
  traceImpact(sel);
}
function traceImpact(cid) {
  const c = S.byId.get(cid), out = $('#traceOut');
  if (!c || !out) return;
  S.traceId = cid;
  const adj = S.adj.get(cid) || [];
  const pick = (dir, type) => adj.filter(e => (dir === 'out' ? e.from === cid : e.to === cid) && e.type === type).map(e => S.byId.get(dir === 'out' ? e.to : e.from)).filter(Boolean);
  const bem = pick('out', 'mines'), procs = pick('out', 'taped_on'), holders = pick('out', 'paid_bem_to'), challengers = pick('in', 'revealed');
  const bad = c.status === 'revoked', state = STATE[c.status] || STATE.verified;
  const sameProc = p => S.G.nodes.filter(n => n.type === 'circuit' && n.processor === p.name && n.id !== cid).length;
  const pill = (name, act) => `<div class="pill"><span class="mono">${esc(name)}</span><span class="act">→ ${act}</span></div>`;
  const none = '<div class="pill none">无</div>';
  const node = (cls, small, big) => `<div class="fl-node ${cls}"><small>${small}</small><b>${esc(big)}</b></div>`;
  const edge = label => `<div class="fl-edge"><span>${label}</span></div>`;
  const flow = bem.length
    ? node('n-danger', '电路', nodeLabel(c)) + edge('挖出') + node('n-gold', '代币', bem[0].name) + edge('已领走') + node('n-pink', '领取地址', `${holders.length} 个`)
    : node(c.status === 'counterexample' ? 'n-lav' : 'n-lav', '电路', nodeLabel(c)) + edge('流片于') + node('n-ice', '处理器', procs.map(p => p.name).join('、') || '—');
  out.innerHTML = `
    <div class="th ${bad ? 'is-danger' : c.status === 'counterexample' ? 'is-warn' : ''}">
      <div class="th-top"><h3>${esc(c.name)}</h3><span class="chip ${bad ? 'danger' : c.status === 'counterexample' ? 'warn' : 'ok'}">${state}</span>${c.processor ? `<span class="chip">${esc(c.processor)}</span>` : ''}${c.taskId != null ? `<span class="chip">题 #${esc(c.taskId)}</span>` : ''}${c.gateCount != null ? `<span class="chip">${esc(c.gateCount)} 门</span>` : ''}</div>
      <p>${c.reason ? esc(c.reason) : bad ? '' : `该电路${c.status === 'counterexample' ? '有反例记录，但' : ''}尚未被撤销，不涉及冻结奖励。`}</p>
      ${bad ? `<div class="th-stats">
        <div class="ts"><small>冻结未领</small><b class="t-danger">${num(c.debtBEM, 4)} BEM</b></div>
        <div class="ts"><small>已领走</small><b>${num(c.claimedBEM, 4)} BEM</b></div>
        <div class="ts"><small>举证者 · 向量</small><b title="${esc(c.challenger)}">${short(c.challenger)} · #${esc(c.vectorIndex)}</b></div>
        <div class="ts"><small>撤销区块</small><b>#${num(c.block, 0)}</b></div></div>` : ''}
      ${c.tx ? `<a class="ext" href="${txUrl('bnb', c.tx)}" target="_blank" rel="noopener">在 BscScan 查看撤销交易 ${ic('ext')}</a>` : ''}
    </div>
    <div class="flow">${flow}</div>
    <div class="lanes">
      <div class="lane l-high"><div class="lane-head"><i></i>高优先级 · 本电路矿机</div><div class="lane-sub">${bem.length ? '在挖 BEM' : '未挖矿'}</div>${bem.map(b => pill(b.name, '停止计入算力 / 冻结未领 BEM')).join('') || none}</div>
      <div class="lane l-mid"><div class="lane-head"><i></i>中优先级 · 同处理器与领取方</div><div class="lane-sub">${procs.length} 个处理器 · ${holders.length} 个领取地址</div>${procs.map(p => pill(`${p.name} · 另有 ${sameProc(p)} 个电路`, '核查同处理器其它电路')).join('')}${holders.map(h => pill(short(h.address), '标记来源电路已撤销')).join('')}${procs.length || holders.length ? '' : none}</div>
      <div class="lane l-low"><div class="lane-head"><i></i>低优先级 · 举证者与审计</div><div class="lane-sub">仅归档，不推送</div>${challengers.map(p => pill(short(p.address), '归档举证记录')).join('') || none}</div>
    </div>`;
}

/* ---------- 告警广播 ---------- */
function renderBroadcast() {
  const el = $('#panel-broadcast');
  if (!S.G) { el.innerHTML = ''; return; }
  const bad = S.G.nodes.filter(n => n.type === 'circuit' && n.status === 'revoked').sort((a, b) => (b.block || 0) - (a.block || 0));
  if (!bad.length) { el.innerHTML = emptyHTML('bell', '暂无被反例撤销的电路', '雷达持续监听中'); return; }
  const flow = (S.G.meta && S.G.meta.bem_flow) || {};
  const pct = flow.total_traced_bem ? Math.min(100, flow.pool_bem / flow.total_traced_bem * 100) : 0;
  const alertHTML = c => {
    const adj = S.adj.get(c.id) || [];
    const mines = adj.some(e => e.from === c.id && e.type === 'mines');
    const holders = adj.filter(e => e.from === c.id && e.type === 'paid_bem_to').map(e => S.byId.get(e.to)).filter(Boolean);
    return `<article class="alert"><div class="al-rail"><span class="al-dot"></span></div><div class="al-card">
      <header class="al-head"><span class="sev">${ic('alert')}严重</span><h4>${esc(c.name)}</h4><span class="chip sm danger">${STATE.revoked}</span><span class="al-time">区块 #${num(c.block, 0)}</span></header>
      <p class="al-reason">${esc(c.reason || '')}</p>
      <dl class="al-grid">
        <div><dt>处理器</dt><dd>${esc(c.processor || '?')}</dd></div>
        <div><dt>题号</dt><dd>#${esc(c.taskId ?? '?')}</dd></div>
        <div><dt>门数</dt><dd>${esc(c.gateCount ?? '?')}</dd></div>
        <div><dt>测试向量</dt><dd>#${esc(c.vectorIndex ?? '?')}</dd></div>
        <div><dt>举证者</dt><dd title="${esc(c.challenger)}">${c.challenger ? short(c.challenger) : '未知'}</dd></div>
        <div><dt>矿主</dt><dd title="${esc(c.registrant)}">${c.registrant ? short(c.registrant) : '—'}</dd></div>
      </dl>
      <ul class="al-prio">
        <li style="--c:var(--danger)"><i></i><span><b>高</b> · 本电路矿机：${mines ? '在挖 BEM，已停止计入算力' : '未挖矿'}</span></li>
        <li style="--c:var(--warn)"><i></i><span><b>中</b> · 已领走该矿机 BEM 的地址：${holders.length} 个</span>${holders.slice(0, 3).map(h => `<button class="addr-chip" type="button" data-addr="${esc(h.address)}" title="用地址雷达扫描">${short(h.address)}</button>`).join('')}</li>
        <li style="--c:var(--muted)"><i></i><span><b>低</b> · 举证者与审计记录：仅归档，不推送</span></li>
      </ul>
      <footer class="al-foot"><div class="al-money"><span>冻结未领 <b class="t-danger">${num(c.debtBEM, 4)} BEM</b></span><span>已领走 <b>${num(c.claimedBEM, 4)} BEM</b></span></div>
        <div class="al-links"><button class="link-btn" type="button" data-trace="${esc(c.id)}">${ic('route')}追溯影响</button>${c.tx ? `<a class="ext" href="${txUrl('bnb', c.tx)}" target="_blank" rel="noopener">撤销交易 ${ic('ext')}</a>` : ''}</div></footer>
    </div></article>`;
  };
  el.innerHTML = `<div class="view">
    <div class="bc-top">
      <div class="box pad"><h3>${ic('bell')}定向告警 · 分级推送</h3><p>以下 ${bad.length} 台电路已被链上反例审查永久撤销。海豚Radar 按优先级把告警广播给受影响方，状态收敛才是终点。</p>
        <div class="prio-legend"><span><i style="--c:var(--danger)"></i>高 · 本电路矿机</span><span><i style="--c:var(--warn)"></i>中 · 已领走 BEM 的地址</span><span><i style="--c:var(--muted)"></i>低 · 举证与审计（仅归档）</span></div></div>
      ${flow.total_traced_bem ? `<div class="box pad"><h3>${ic('route')}坏币二级流转</h3>
        <div class="bf-num"><b>${num(flow.total_traced_bem)}</b><span>BEM 已从矿主流出 → ${num(flow.recipient_count, 0)} 个地址</span></div>
        <div class="bf-bar"><i style="width:${pct.toFixed(1)}%"></i></div>
        <div class="bf-legend"><span><i style="--c:var(--danger)"></i><b>${num(flow.pool_bem)} BEM</b>（${pct.toFixed(1)}%）进入 PancakeSwap BEM/USDT 池，已混入全网流动性</span><span><i style="--c:rgba(195,180,240,.45)"></i>其余 <b>${num(flow.total_traced_bem - flow.pool_bem)} BEM</b> 流向其他地址</span></div></div>` : ''}
    </div>
    <div class="feed">${bad.map(alertHTML).join('')}</div></div>`;
}

/* ---------- 地址雷达 ---------- */
function scanAddress(addr) {
  const a = String(addr).toLowerCase(), pid = 'person:' + a;
  const person = S.G.nodes.find(n => n.type === 'person' && String(n.address || '').toLowerCase() === a) || null;
  const owner = new Set(), holder = new Set(), challenged = new Set();
  for (const e of S.G.edges) {
    if (e.to.toLowerCase() === pid && e.type === 'operated_by') owner.add(S.byId.get(e.from));
    if (e.to.toLowerCase() === pid && e.type === 'paid_bem_to') holder.add(S.byId.get(e.from));
    if (e.from.toLowerCase() === pid && e.type === 'revealed') challenged.add(S.byId.get(e.to));
  }
  for (const n of S.G.nodes) {
    if (n.type !== 'circuit') continue;
    if (String(n.registrant || '').toLowerCase() === a) owner.add(n);
    if (String(n.challenger || '').toLowerCase() === a) challenged.add(n);
  }
  const clean = s => [...s].filter(Boolean);
  const own = clean(owner), ownIds = new Set(own.map(n => n.id));
  return { person, owner: own, holder: clean(holder).filter(n => !ownIds.has(n.id)), challenged: clean(challenged) };
}
const scanLevel = r => r.owner.length ? 'high' : r.holder.length ? 'mid' : r.challenged.length ? 'info' : 'clean';
function sampleAddrs() {
  const rev = S.G.nodes.filter(n => n.status === 'revoked').sort((a, b) => (b.debtBEM || 0) - (a.debtBEM || 0));
  const counts = {};
  for (const e of S.G.edges) if (e.type === 'revealed') counts[e.from] = (counts[e.from] || 0) + 1;
  const top = Object.entries(counts).sort((a, b) => b[1] - a[1])[0];
  const ch = top && S.byId.get(top[0]);
  return [rev[0] && rev[0].registrant && { label: '示例 · 矿主', addr: rev[0].registrant }, ch && ch.address && { label: '示例 · 举证者', addr: ch.address }].filter(Boolean);
}
function renderAddrRadar() {
  const el = $('#addrRadar');
  if (!S.G) { el.hidden = true; return; }
  el.hidden = false;
  const w = S.wallet, addr = S.scanAddr || (w && w.address) || '';
  const mine = !!(w && addr && addr.toLowerCase() === w.address.toLowerCase());
  let out;
  if (!addr) out = `<div class="ar-out"><div class="ar-res-head">${ic('radar')}<b>等待扫描</b></div><p>连接钱包后会自动扫描你的地址；也可以粘贴任意 BNB Chain 地址。</p></div>`;
  else if (!isAddr(addr)) out = `<div class="ar-out lv-mid"><div class="ar-res-head">${ic('alert')}<b class="t-warn">地址格式不正确</b></div><p>需要 0x 开头、40 位十六进制字符的地址。</p></div>`;
  else {
    const r = scanAddress(addr), lv = scanLevel(r), who = mine ? '你的地址' : '该地址';
    const head = { high: ['t-danger', '高风险 · 被撤销电路的矿主'], mid: ['t-warn', '需关注 · 领取过被撤销电路的 BEM'], info: ['t-lav', '举证者 · 参与了反例审查'], clean: ['t-ok', '未发现关联告警'] }[lv];
    const items = [];
    r.owner.forEach(c => items.push(`<li><span class="chip sm danger">矿主</span><span><b>${esc(c.name)}</b> ${STATE[c.status] || ''}${c.debtBEM != null ? ` · 冻结未领 <b class="t-danger mono">${num(c.debtBEM, 4)} BEM</b>` : ''}</span></li>`));
    r.holder.forEach(c => items.push(`<li><span class="chip sm warn">领取方</span><span>领取过 <b>${esc(c.name)}</b> 挖出的 BEM（该电路合计已领走 ${num(c.claimedBEM, 4)} BEM）</span></li>`));
    if (r.challenged.length) {
      const rv = r.challenged.filter(c => c.status === 'revoked').length;
      items.push(`<li><span class="chip sm lav">举证者</span><span>共举证 <b>${r.challenged.length}</b> 个电路${rv ? `，其中 <b>${rv}</b> 个已被撤销` : ''}，记录已归档</span></li>`);
    }
    out = `<div class="ar-out lv-${lv}"><div class="ar-res-head"><span class="avatar" style="${avatarStyle(addr)}"></span><div><b class="${head[0]}">${head[1]}</b><div class="mono ar-addr">${esc(short(addr, 10, 8))}${mine ? ' · 已连接钱包' : ''}</div></div></div>
      ${items.length ? `<ul class="ar-items">${items.join('')}</ul>` : `<p>${who}不在 ${num(S.G.meta && S.G.meta.revoked_circuits, 0)} 台被撤销电路的矿主、BEM 领取方或举证者名单中。</p>`}
      <div class="ar-links"><a class="ext" href="${addrUrl('bnb', addr)}" target="_blank" rel="noopener">在 BscScan 查看 ${ic('ext')}</a>${r.person ? `<button class="link-btn" type="button" data-graph-node="${esc(r.person.id)}">${ic('graph')}在关系图中定位</button>` : ''}</div></div>`;
  }
  el.innerHTML = `<div class="ar-left">
      <div class="ar-intro"><span class="ar-ico">${ic('shield')}</span><div><h3>地址雷达</h3><p>检查地址是否出现在被撤销电路的矿主、BEM 领取方或举证记录中</p></div></div>
      <form class="ar-form" id="arForm"><input class="field mono" id="arInput" value="${esc(addr)}" placeholder="0x…  粘贴 BNB Chain 地址" spellcheck="false" autocomplete="off" aria-label="要扫描的地址"><button class="btn btn-ghost" type="submit">${ic('radar')}扫描</button></form>
      <div class="ar-samples">${w ? `<button class="link-btn" type="button" data-addr="${esc(w.address)}">我的地址</button>` : `<button class="link-btn" type="button" data-act="connect">${ic('wallet')}连接钱包</button>`}${sampleAddrs().map(s => `<button class="link-btn" type="button" data-addr="${esc(s.addr)}">${s.label}</button>`).join('')}</div>
    </div>${out}`;
}
function goScan(addr) {
  S.scanAddr = addr || '';
  if (S.chain !== 'bnb') setChain('bnb');
  renderAddrRadar();
  scrollToEl('#addrRadar');
}
function goTrace(id) {
  S.traceId = id;
  if (S.chain !== 'bnb') setChain('bnb');
  setView('trace');
  scrollToEl('#tabs');
}
function goGraphNode(id) {
  const n = S.byId.get(id);
  if (!n) return;
  const q = n.address || n.name;
  $('#q').value = q;
  if (S.chain !== 'bnb') setChain('bnb');
  S.pendingFocus = id;
  runSearch(q);
  setView('graph');
  scrollToEl('#tabs');
}

/* ---------- 标签页 ---------- */
function setView(v) {
  S.view = v;
  $$('#tabs [role="tab"]').forEach(b => { const on = b.dataset.view === v; b.setAttribute('aria-selected', String(on)); b.tabIndex = on ? 0 : -1; });
  ['card', 'graph', 'trace', 'broadcast'].forEach(k => { $('#panel-' + k).hidden = k !== v; });
  if (!S.G) return;
  if (v === 'graph' && S.chain === 'bnb') drawGraph();
  if (v === 'trace') renderTrace();
  if (v === 'broadcast' && !$('#panel-broadcast').childElementCount) renderBroadcast();
}

/* ---------- 钱包：EIP-6963 多钱包发现 + EIP-1193 ---------- */
function discoverWallets() {
  window.addEventListener('eip6963:announceProvider', e => {
    const d = e.detail;
    if (!d || !d.info || !d.provider) return;
    const id = d.info.rdns || d.info.uuid || d.info.name;
    if (S.wallets.has(id)) return;
    S.wallets.set(id, { id, info: d.info, provider: d.provider });
    if (!$('#walletModal').hidden) renderWalletList();
  });
  window.dispatchEvent(new Event('eip6963:requestProvider'));
}
function legacyWallet() {
  const eth = window.okxwallet || window.ethereum;
  if (!eth || typeof eth.request !== 'function') return null;
  const name = window.okxwallet ? 'OKX Wallet' : eth.isRabby ? 'Rabby' : (eth.isBinance || eth.isBinanceChain) ? 'Binance Wallet' : (eth.isTrust || eth.isTrustWallet) ? 'Trust Wallet' : eth.isCoinbaseWallet ? 'Coinbase Wallet' : eth.isMetaMask ? 'MetaMask' : '浏览器钱包';
  return { id: 'injected', info: { name, icon: '', rdns: 'injected' }, provider: eth };
}
function walletEntries() {
  const list = [...S.wallets.values()];
  if (!list.length) { const l = legacyWallet(); if (l) list.push(l); }
  const pref = S.chain === 'xlayer' ? /okx|okex/i : /binance/i, isPref = e => pref.test(`${e.info.rdns || ''} ${e.info.name || ''}`);
  return list.sort((a, b) => Number(isPref(b)) - Number(isPref(a)));
}
const avatarStyle = addr => {
  const h = parseInt(String(addr).slice(2, 10), 16) || 0, a = h % 360, x = 22 + (h >>> 9) % 56, y = 22 + (h >>> 17) % 56;
  return `background:radial-gradient(circle at ${x}% ${y}%,rgba(255,255,255,.85),rgba(255,255,255,0) 42%),conic-gradient(from ${a}deg,#F0BDD8,#A08CD3,#C4E8F5,#FBF2D3,#F0BDD8)`;
};
const errCode = e => (e && (e.code ?? (e.data && e.data.originalError && e.data.originalError.code))) ?? null;
function walletError(e, action) {
  const code = errCode(e);
  if (code === 4001) return `你在钱包中取消了${action}`;
  if (code === -32002) return '钱包里已有待确认的请求，请先打开钱包处理';
  return `${action}失败：${(e && e.message) || e}`;
}

function openModal(opts) {
  S.afterConnect = opts && opts.thenScan ? 'scan' : null;
  window.dispatchEvent(new Event('eip6963:requestProvider'));
  renderWalletList();
  S.lastFocus = document.activeElement;
  $('#walletModal').hidden = false;
  document.body.classList.add('modal-open');
  requestAnimationFrame(() => { const f = $('#wmList .wm-item') || $('#wmClose'); if (f) f.focus(); });
}
function closeModal() {
  const m = $('#walletModal');
  if (m.hidden) return;
  m.hidden = true;
  document.body.classList.remove('modal-open');
  if (S.lastFocus && S.lastFocus.focus) S.lastFocus.focus();
}
function renderWalletList() {
  const want = CHAINS[S.chain], box = $('#wmList');
  $('#wmChain').innerHTML = `${CHAIN_ICON[want.key]}${want.name}`;
  const list = walletEntries();
  if (!list.length) {
    const here = location.href, touch = window.matchMedia && matchMedia('(pointer:coarse)').matches;
    const okxApp = 'https://www.okx.com/download?deeplink=' + encodeURIComponent('okx://wallet/dapp/url?dappUrl=' + encodeURIComponent(here));
    const mmApp = 'https://metamask.app.link/dapp/' + here.replace(/^https?:\/\//, '');
    const link = (href, name, sub) => `<a class="wm-item" href="${esc(href)}" target="_blank" rel="noopener"><span class="wm-icon">${esc(name[0])}</span><span class="wm-name">${esc(name)}<small>${sub}</small></span>${ic('ext')}</a>`;
    box.innerHTML = `<div class="wm-empty"><div class="wm-empty-head">${ic('wallet')}<div><b>未检测到浏览器钱包</b><p>安装支持 X Layer 与 BNB Chain 的钱包扩展后刷新页面${touch ? '，或直接在钱包 App 中打开本站' : ''}。</p></div></div>
      ${touch ? link(okxApp, 'OKX Wallet', '在 App 中打开本站') + link(mmApp, 'MetaMask', '在 App 中打开本站') : ''}
      ${link('https://web3.okx.com/download', 'OKX Wallet', '安装浏览器扩展')}${link('https://metamask.io/download/', 'MetaMask', '安装浏览器扩展')}</div>`;
    return;
  }
  box.innerHTML = list.map(e => {
    const busy = S.connecting === e.id, tag = `${e.info.rdns || ''} ${e.info.name || ''}`;
    const rec = (S.chain === 'xlayer' && /okx|okex/i.test(tag)) || (S.chain === 'bnb' && /binance/i.test(tag));
    return `<button class="wm-item" type="button" data-wallet="${esc(e.id)}"${S.connecting ? ' disabled' : ''}>
      <span class="wm-icon">${e.info.icon ? `<img src="${esc(e.info.icon)}" alt="">` : esc((e.info.name || '?')[0])}</span>
      <span class="wm-name">${esc(e.info.name || '未知钱包')}${rec ? '<span class="wm-tag">推荐</span>' : ''}<small class="${busy ? '' : 'ok'}">${busy ? '请在钱包弹窗中确认…' : '已检测到'}</small></span>
      ${busy ? '<span class="spin"></span>' : ic('arrow')}</button>`;
  }).join('');
  $$('img', box).forEach(img => img.addEventListener('error', () => { const n = img.closest('.wm-item').querySelector('.wm-name'); img.parentElement.textContent = (n.textContent.trim()[0]) || '?'; }, { once: true }));
}

async function connect(entry) {
  if (S.connecting) return;
  S.connecting = entry.id;
  renderWalletList(); renderWallet();
  try {
    const accounts = await entry.provider.request({ method: 'eth_requestAccounts' });
    if (!accounts || !accounts.length) throw new Error('钱包没有返回账户');
    const chainId = Number(await entry.provider.request({ method: 'eth_chainId' }));
    setWallet(entry, accounts[0], chainId);
    store.set('wallet', entry.id);
    S.connecting = null;
    closeModal();
    toast(`已连接 ${entry.info.name}`, 'ok');
    const want = CHAINS[S.chain];
    // 切换成功时由 chainChanged 刷新余额；未切换（同链 / 用户拒绝）则按当前链读取
    if (chainId === want.id || !(await ensureWalletChain(want))) refreshBalance();
    if (S.afterConnect === 'scan') goScan(S.wallet.address);
    announceScan();
  } catch (e) {
    toast(walletError(e, '连接'), errCode(e) === 4001 ? 'warn' : 'danger');
  } finally {
    S.connecting = null; S.afterConnect = null;
    renderWalletList(); renderWallet();
  }
}
const handlers = {
  accountsChanged: accts => {
    if (!S.wallet) return;
    if (!accts || !accts.length) { disconnect(true); return; }
    if (String(accts[0]).toLowerCase() === S.wallet.address.toLowerCase()) return;
    S.wallet.address = accts[0]; S.wallet.balance = null; S.scanAddr = '';
    renderWallet(); renderAddrRadar(); refreshBalance(); announceScan();
  },
  chainChanged: hex => onChainChanged(Number(hex)),
};
function setWallet(entry, address, chainId) {
  if (S.wallet && S.wallet.provider !== entry.provider) detachProvider(S.wallet.provider);
  S.wallet = { entry, provider: entry.provider, address, chainId, balance: null };
  if (entry.provider.on) for (const k in handlers) entry.provider.on(k, handlers[k]);
  renderWallet(); renderAddrRadar();
}
function detachProvider(p) { if (p && p.removeListener) for (const k in handlers) p.removeListener(k, handlers[k]); }
function onChainChanged(id) {
  const w = S.wallet;
  if (!w || !id) return;
  const changed = w.chainId !== id;
  w.chainId = id;
  const c = chainById(id);
  if (c && c.key !== S.chain) setChain(c.key); // 钱包里切到受支持的链时，页面跟随
  if (changed) { w.balance = null; refreshBalance(); }
  renderWallet();
}
async function ensureWalletChain(c) {
  const w = S.wallet;
  if (!w || S.switching) return false;
  if (w.chainId === c.id) return true;
  S.switching = true; renderWallet();
  try {
    try {
      await w.provider.request({ method: 'wallet_switchEthereumChain', params: [{ chainId: c.hex }] });
    } catch (e) {
      // 4902：钱包里还没有这条链，先添加（添加后多数钱包会自动切过去）
      if (errCode(e) === 4902 || /unrecognized|not been added|unknown chain|not added/i.test((e && e.message) || '')) {
        await w.provider.request({ method: 'wallet_addEthereumChain', params: [c.add] });
      } else throw e;
    }
    const id = Number(await w.provider.request({ method: 'eth_chainId' }));
    S.switching = false;
    onChainChanged(id);
    if (id === c.id) toast(`钱包已切换到 ${c.name}`, 'ok');
    return id === c.id;
  } catch (e) {
    toast(walletError(e, '切换网络'), 'warn');
    return false;
  } finally {
    S.switching = false; renderWallet();
  }
}
async function refreshBalance() {
  const w = S.wallet;
  if (!w) return;
  const c = chainById(w.chainId);
  if (!c) { w.balance = null; renderWallet(); return; }
  const addr = w.address;
  try {
    const hex = await w.provider.request({ method: 'eth_getBalance', params: [addr, 'latest'] });
    if (S.wallet === w && w.chainId === c.id && w.address === addr) w.balance = Number(BigInt(hex)) / 1e18;
  } catch (e) { w.balance = null; }
  renderWallet();
}
async function restoreWallet() {
  const id = store.get('wallet');
  if (!id || S.wallet) return;
  await new Promise(r => setTimeout(r, 400)); // 给 EIP-6963 公告留一点时间
  const entry = S.wallets.get(id) || (id === 'injected' ? legacyWallet() : null);
  if (!entry) return;
  try {
    const accts = await entry.provider.request({ method: 'eth_accounts' }); // 不弹窗
    if (!accts || !accts.length) { store.set('wallet', null); return; }
    const chainId = Number(await entry.provider.request({ method: 'eth_chainId' }));
    setWallet(entry, accts[0], chainId);
    const c = chainById(chainId);
    if (c && c.key !== S.chain) setChain(c.key);
    refreshBalance();
  } catch (e) { /* 静默恢复失败就保持未连接 */ }
}
async function disconnect(silent) {
  const w = S.wallet;
  if (!w) return;
  detachProvider(w.provider);
  S.wallet = null; S.scanAddr = '';
  store.set('wallet', null);
  closeMenu(); renderWallet(); renderAddrRadar();
  try { await w.provider.request({ method: 'wallet_revokePermissions', params: [{ eth_accounts: {} }] }); } catch (e) { /* 部分钱包不支持 */ }
  if (!silent) toast('已断开钱包连接', 'info');
}
function announceScan() {
  if (!S.G || !S.wallet) return;
  const lv = scanLevel(scanAddress(S.wallet.address));
  if (lv === 'high') toast('地址雷达：你的地址是被撤销电路的矿主，点头像查看', 'danger');
  else if (lv === 'mid') toast('地址雷达：你领取过被撤销电路挖出的 BEM', 'warn');
}

function renderWallet() {
  const w = S.wallet, cb = $('#connectBtn');
  cb.hidden = !!w;
  cb.disabled = !!S.connecting;
  $('#walletGroup').hidden = !w;
  $('#heroConnectLbl').textContent = w ? '查看我的地址雷达' : '连接钱包 · 检查我的地址';
  if (!w) { closeMenu(); return; }
  const c = chainById(w.chainId), want = CHAINS[S.chain], mismatch = !c || c.id !== want.id;
  const net = $('#netBtn');
  net.classList.toggle('is-warn', mismatch && !S.switching);
  net.innerHTML = S.switching ? '<span class="spin"></span><span class="wg-txt">切换中…</span>'
    : mismatch ? `${ic('alert')}<span class="wg-txt">${c ? `切换到 ${want.name}` : '不支持的网络'}</span>`
    : `${CHAIN_ICON[c.key]}<span class="wg-txt mono">${fmtBal(w.balance, c.symbol)}</span>`;
  net.title = mismatch ? `钱包当前在 ${c ? c.name : 'Chain ' + w.chainId}，点击切换到 ${want.name}` : `${c.name} 余额`;
  net.setAttribute('aria-label', net.title);
  const lv = S.G ? scanLevel(scanAddress(w.address)) : 'clean';
  $('#acctBtn').innerHTML = `<span class="avatar" style="${avatarStyle(w.address)}">${lv === 'high' || lv === 'mid' ? '<i class="avatar-dot"></i>' : ''}</span><span class="wg-txt mono">${short(w.address)}</span>${ic('chev')}`;
  if (!$('#walletMenu').hidden) renderMenu();
}
function renderMenu() {
  const w = S.wallet;
  if (!w) return;
  const c = chainById(w.chainId), want = CHAINS[S.chain], mismatch = !c || c.id !== want.id;
  const lv = S.G ? scanLevel(scanAddress(w.address)) : null;
  const lvChip = { high: ['danger', '高风险'], mid: ['warn', '需关注'], info: ['lav', '举证者'], clean: ['ok', '无关联告警'] }[lv] || ['', '—'];
  const ek = c ? c.key : want.key;
  $('#walletMenu').innerHTML = `
    <div class="menu-head"><span class="avatar lg" style="${avatarStyle(w.address)}"></span><div><div class="mh-addr mono">${short(w.address)}<button class="icon-btn" type="button" data-act="copy-addr" aria-label="复制地址">${ic('copy')}</button></div><div class="mh-sub">${esc(w.entry.info.name)} · 已连接</div></div></div>
    <div class="menu-rows">
      <div class="mr"><span>钱包网络</span><span class="val${mismatch ? ' t-warn' : ''}">${c ? CHAIN_ICON[c.key] + c.name : `不支持（Chain ${esc(w.chainId)}）`}</span></div>
      <div class="mr"><span>余额</span><span class="val mono">${c ? fmtBal(w.balance, c.symbol) : '—'}</span></div>
      <div class="mr"><span>地址雷达</span><span class="val"><span class="chip sm ${lvChip[0]}">${lvChip[1]}</span></span></div>
    </div>
    ${mismatch ? `<button class="btn btn-holo btn-block" type="button" data-act="switch">${CHAIN_ICON[want.key]}切换钱包到 ${want.name}</button>` : ''}
    <div class="menu-actions">
      <button class="ma" type="button" data-act="scan-me">${ic('shield')}查看地址雷达</button>
      <a class="ma" href="${addrUrl(ek, w.address)}" target="_blank" rel="noopener">${ic('ext')}在 ${CHAINS[ek].explorerName} 查看</a>
      <button class="ma danger" type="button" data-act="disconnect">${ic('power')}断开连接</button>
    </div>`;
}
function toggleMenu() {
  const m = $('#walletMenu');
  if (!m.hidden) { closeMenu(); return; }
  renderMenu();
  m.hidden = false;
  $('#acctBtn').setAttribute('aria-expanded', 'true');
}
function closeMenu() {
  $('#walletMenu').hidden = true;
  $('#acctBtn').setAttribute('aria-expanded', 'false');
}

/* ---------- 交互 ---------- */
function toast(msg, kind) {
  const k = kind || 'info', el = document.createElement('div');
  el.className = `toast t-${k}`;
  el.setAttribute('role', 'status');
  el.innerHTML = `${ic(k === 'ok' ? 'check' : k === 'info' ? 'radar' : 'alert')}<span>${esc(msg)}</span>`;
  $('#toasts').appendChild(el);
  requestAnimationFrame(() => el.classList.add('in'));
  setTimeout(() => { el.classList.remove('in'); setTimeout(() => el.remove(), 300); }, 3600);
}
async function copyText(t) {
  try { await navigator.clipboard.writeText(t); }
  catch (e) {
    const ta = document.createElement('textarea');
    ta.value = t; ta.style.cssText = 'position:fixed;opacity:0';
    document.body.appendChild(ta); ta.select();
    try { document.execCommand('copy'); } catch (err) { /* 无剪贴板权限 */ }
    ta.remove();
  }
  toast(`已复制 ${short(t, 8, 6)}`, 'ok');
}

function onClick(e) {
  if (!$('#walletMenu').hidden && !e.target.closest('#walletMenu,#acctBtn,#netBtn')) closeMenu();
  const t = e.target.closest('[data-chain],[data-view],[data-act],[data-wallet],[data-addr],[data-trace],[data-q],[data-copy],[data-more],[data-graph-node],[data-close]');
  if (!t) return;
  const d = t.dataset;
  if (d.chain) { selectChain(d.chain, { scroll: t.matches('.hc,.jump') }); return; }
  if (d.view) { setView(d.view); return; }
  if (d.close != null) { closeModal(); return; }
  if (d.wallet) { const entry = walletEntries().find(x => x.id === d.wallet); if (entry) connect(entry); return; }
  if (d.addr) { goScan(d.addr); return; }
  if (d.trace) { goTrace(d.trace); return; }
  if (d.q != null) { $('#q').value = d.q; runSearch(d.q); return; }
  if (d.copy) { copyText(d.copy); return; }
  if (d.more) { expandGroup(d.more); return; }
  if (d.graphNode) { goGraphNode(d.graphNode); return; }
  switch (d.act) {
    case 'connect': if (S.wallet) goScan(S.wallet.address); else openModal(); break;
    case 'hero-connect': if (S.wallet) goScan(S.wallet.address); else openModal({ thenScan: true }); break;
    case 'alerts': if (S.chain !== 'bnb') setChain('bnb'); setView('broadcast'); scrollToEl('#tabs'); break;
    case 'menu': toggleMenu(); break;
    case 'net': {
      const w = S.wallet, c = w && chainById(w.chainId);
      if (w && (!c || c.key !== S.chain)) { closeMenu(); ensureWalletChain(CHAINS[S.chain]); } else toggleMenu();
      break;
    }
    case 'switch': closeMenu(); ensureWalletChain(CHAINS[S.chain]); break;
    case 'disconnect': disconnect(); break;
    case 'copy-addr': if (S.wallet) copyText(S.wallet.address); break;
    case 'scan-me': closeMenu(); if (S.wallet) goScan(S.wallet.address); break;
    case 'close-info': $('#gInfo').hidden = true; if (S.network) S.network.unselectAll(); break;
    case 'fit': if (S.network) S.network.fit({ animation: { duration: 500 } }); break;
    case 'relayout': drawGraph(true); break;
    case 'clear-search': $('#q').value = ''; runSearch(''); break;
  }
}
function onKey(e) {
  const modalOpen = !$('#walletModal').hidden;
  if (e.key === 'Escape') { if (modalOpen) closeModal(); else closeMenu(); return; }
  if (modalOpen && e.key === 'Tab') {
    const f = $$('#walletModal button:not([disabled]), #walletModal a[href]');
    if (!f.length) return;
    if (e.shiftKey && document.activeElement === f[0]) { e.preventDefault(); f[f.length - 1].focus(); }
    else if (!e.shiftKey && document.activeElement === f[f.length - 1]) { e.preventDefault(); f[0].focus(); }
    return;
  }
  const typing = /^(INPUT|TEXTAREA|SELECT)$/.test((document.activeElement || {}).tagName || '');
  if (e.key === '/' && !typing && S.chain === 'bnb') { e.preventDefault(); $('#q').focus(); return; }
  if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
  if (e.target.closest('#chainSwitch')) {
    e.preventDefault();
    const next = S.chain === 'xlayer' ? 'bnb' : 'xlayer';
    selectChain(next);
    $(`#chainSwitch [data-chain="${next}"]`).focus();
  } else if (e.target.closest('#tabs')) {
    e.preventDefault();
    const tabs = $$('#tabs [role="tab"]'), i = tabs.findIndex(t => t.dataset.view === S.view);
    const n = tabs[(i + (e.key === 'ArrowRight' ? 1 : tabs.length - 1)) % tabs.length];
    setView(n.dataset.view); n.focus();
  }
}
function bindEvents() {
  document.addEventListener('click', onClick);
  document.addEventListener('keydown', onKey);
  $('#searchForm').addEventListener('submit', e => { e.preventDefault(); runSearch($('#q').value); });
  document.addEventListener('submit', e => {
    if (e.target.id !== 'arForm') return;
    e.preventDefault();
    S.scanAddr = $('#arInput').value.trim();
    renderAddrRadar();
  });
  document.addEventListener('change', e => { if (e.target.id === 'circuitSel') traceImpact(e.target.value); });
}

function renderFooter() {
  const parts = [];
  if (S.G && S.G.meta && S.G.meta.latestBlock) parts.push(`BNB 区块 #${num(S.G.meta.latestBlock, 0)}`);
  if (S.PS && S.PS.generatedAt) parts.push(`快照 ${fmtTime(S.PS.generatedAt)}`);
  if (S.XL && S.XL.updatedAt) parts.push(`X Layer 更新 ${esc(S.XL.updatedAt)}`);
  $('#footMeta').innerHTML = parts.join(' · ');
}

init();
})();
