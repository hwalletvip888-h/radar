/* 海豚Radar · 实时心跳条
   独立于 app.js：只读 API，更新页面上的实时数据条，不碰复杂的主渲染逻辑。
   数据源：https://api.radar.hvip.one（CORS 已开），30 秒轮询一次。 */
(function () {
  var API = 'https://api.radar.hvip.one';
  var bar = document.getElementById('liveBar');
  var dot = document.getElementById('lbDot');
  var txt = document.getElementById('lbText');
  if (!bar) return;

  function esc(s) { return String(s == null ? '' : s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

  function tick() {
    Promise.all([
      fetch(API + '/api/stats', { cache: 'no-cache' }).then(function (r) { return r.json(); }),
      fetch(API + '/api/ratings?status=revoked&limit=50', { cache: 'no-cache' }).then(function (r) { return r.json(); }),
    ]).then(function (res) {
      var st = res[0], rev = res[1];
      var latest = st.latest || {};
      var frozen = 0;
      (rev.items || []).forEach(function (x) { frozen += (x.debt_bem || 0); });
      dot.style.background = '#74E2BF';
      dot.style.boxShadow = '0 0 8px #74E2BF';
      txt.innerHTML =
        '<b>实时</b> · 区块 #' + (st.last_block || '—') +
        ' · 撤销 <b class="t-danger">' + (latest.revoked || 0) + '</b> 台' +
        ' · 冻结 ' + frozen.toFixed(1) + ' BEM' +
        ' · 夺最优 ' + (latest.demoted || 0) + ' 台';
    }).catch(function () {
      dot.style.background = '#968EAE';
      dot.style.boxShadow = 'none';
      txt.textContent = '实时数据暂不可用（API 未连接）';
    });
  }

  tick();
  setInterval(tick, 30000);
})();
