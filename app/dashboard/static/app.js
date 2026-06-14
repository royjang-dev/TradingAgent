const $ = (s) => document.querySelector(s);
const fmt = (n) => (typeof n === "number" ? n.toLocaleString(undefined, { maximumFractionDigits: 2 }) : n);
const cls = (n) => (n > 0 ? "up" : n < 0 ? "dn" : "");
const sign = (n) => (n > 0 ? "+" : "");
let view = "dashboard";
let chart = null;
let cfg = null;
let recFilter = "전체";

async function getJSON(url) {
  try { const r = await fetch(url); return await r.json(); } catch { return null; }
}

document.querySelectorAll(".nav").forEach((el) => {
  el.onclick = () => {
    document.querySelectorAll(".nav").forEach((n) => n.classList.remove("on"));
    el.classList.add("on");
    view = el.dataset.view;
    document.querySelectorAll("main section").forEach((s) => s.classList.add("hide"));
    $("#" + view).classList.remove("hide");
    refresh();
  };
});

$("#startstop").onclick = async () => {
  const go = $("#startstop").classList.contains("go");
  await fetch(go ? "/api/start" : "/api/stop", { method: "POST" });
  refresh();
};

function kpi(lab, val, sub, valColor, icon, iconColor) {
  return `<div class="card"><div style="display:flex;justify-content:space-between;align-items:flex-start"><span class="lab">${lab}</span><i class="ti ti-${icon}" style="color:${iconColor};font-size:17px" aria-hidden="true"></i></div><div class="val" style="color:${valColor}">${val}</div><div class="sub">${sub}</div></div>`;
}

async function renderDashboard() {
  const s = await getJSON("/api/status");
  if (!s) return;
  $("#modepill").textContent = s.mode;
  const ss = $("#startstop");
  ss.textContent = s.running ? "STOP" : "START";
  ss.classList.toggle("go", !s.running);
  $("#conn").innerHTML = `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${s.running ? "#34d399" : "#f3647a"};margin-right:5px"></span>${s.running ? "Running" : "Stopped"} · ${s.mode}`;
  const initial = s.balance - s.total_pnl;
  const realPnl = (s.equity != null ? s.equity : s.balance) - initial; // realized + unrealized
  const unreal = s.unrealized_pnl != null ? s.unrealized_pnl : 0;
  $("#kpis").innerHTML =
    kpi("진짜 자산", "$" + fmt(s.equity != null ? s.equity : s.balance), "실손익 " + sign(realPnl) + "$" + fmt(Math.abs(realPnl)), realPnl >= 0 ? "#34d399" : "#f3647a", "scale", "#d8a72e") +
    kpi("잔고 (실현)", "$" + fmt(s.balance), "가용 $" + fmt(s.available), "#eef0f5", "wallet", "#d8a72e") +
    kpi("미실현 손익", sign(unreal) + "$" + fmt(unreal), "보유 " + s.position_count + "개 (가방)", unreal >= 0 ? "#34d399" : "#f3647a", "alert-triangle", unreal < 0 ? "#f3647a" : "#34d399") +
    kpi("누적 수익금 (실현)", sign(s.total_pnl) + "$" + fmt(s.total_pnl), "총 " + s.trade_count + " 거래", s.total_pnl >= 0 ? "#34d399" : "#f3647a", "trending-up", "#34d399") +
    kpi("누적 수익률", sign(s.total_roe) + fmt(s.total_roe) + "%", "승률 " + s.win_rate + "%", s.total_roe >= 0 ? "#34d399" : "#f3647a", "percentage", "#5b8def") +
    kpi("포지션", s.position_count, "주문 " + s.order_count, "#eef0f5", "layers-intersect", "#d8a72e");
  const d = await getJSON("/api/daily");
  if (d) drawDaily(d);
  const m = await getJSON("/api/market");
  drawMarket(m && m.total ? m : null);
}

function dailySeries(d) {
  const keys = ["values", "profit", "loss", "profit_roe", "loss_roe"];
  const maps = {};
  keys.forEach((k) => { maps[k] = {}; (d.labels || []).forEach((lab, i) => { maps[k][lab] = (d[k] || [])[i] || 0; }); });
  const DAY = 864e5, todayMs = Date.now();
  let startMs = d.labels && d.labels.length ? Date.parse(d.labels[0]) : todayMs;
  startMs = Math.min(startMs, todayMs - 13 * DAY); // always show at least ~14 days of date axis
  const out = { labels: [] };
  keys.forEach((k) => (out[k] = []));
  for (let t = startMs; t <= todayMs + 1000; t += DAY) {
    const iso = new Date(t).toISOString().slice(0, 10);
    out.labels.push(iso.slice(5)); // MM-DD
    keys.forEach((k) => out[k].push(maps[k][iso] || 0));
  }
  return out;
}

function drawDaily(d) {
  const s = dailySeries(d);
  const colors = s.values.map((v) => (v >= 0 ? "#2fd4bf" : "#f3647a"));
  const data = { labels: s.labels, datasets: [{ type: "bar", label: "일별 순수익 ($)", data: s.values, backgroundColor: colors, borderRadius: 3 }] };
  const opts = {
    responsive: true, maintainAspectRatio: false, animation: false, // animation off -> no flicker on the 5s refresh
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (ctx) => {
            const i = ctx.dataIndex, loss = s.loss[i], net = s.values[i];
            return [
              `일별 수익금액: +$${fmt(s.profit[i])}`,
              `손실금액: ${loss < 0 ? "-$" + fmt(-loss) : "$0"}`,
              `일일 수익율: +${s.profit_roe[i]}%`,
              `일일 손실율: ${s.loss_roe[i]}%`,
              `순손익: ${net >= 0 ? "+$" + fmt(net) : "-$" + fmt(-net)}`,
            ];
          },
        },
      },
    },
    scales: {
      x: { ticks: { color: "#7c7e8a", font: { size: 9 }, maxRotation: 0, autoSkip: true, maxTicksLimit: 16 }, grid: { display: false } },
      y: { title: { display: true, text: "수익금액 ($)", color: "#6b6d78", font: { size: 9 } }, ticks: { color: "#7c7e8a", font: { size: 9 }, callback: (v) => "$" + v }, grid: { color: "#1c1e26" } },
    },
  };
  if (chart) { chart.data = data; chart.options = opts; chart.update("none"); return; }
  chart = new Chart($("#daily"), { data, options: opts });
}

function mp(icon, ic, title, rows) {
  return `<div class="mp"><div class="h"><i class="ti ti-${icon}" style="color:${ic}" aria-hidden="true"></i> ${title}</div>${rows}</div>`;
}
function row(a, b, bc) { return `<div class="row"><span style="color:#cdd0d8">${a}</span><span class="${bc || ""}">${b}</span></div>`; }

function abbr(n) { return n >= 1e9 ? "$" + (n / 1e9).toFixed(1) + "B" : n >= 1e6 ? "$" + (n / 1e6).toFixed(1) + "M" : "$" + fmt(n); }
function noUsdt(s) { return (s || "").replace(/USDT$/, ""); }

function drawMarket(m) {
  if (!m) { $("#mtop").innerHTML = `<div class="mp muted">시장 데이터 수집 중…</div>`; $("#mbot").innerHTML = ""; return; }
  const nm = (t) => `<span style="color:#cdd0d8">${t}</span>`;
  const lvl = m.avg_volatility >= 8 ? "높음" : m.avg_volatility >= 4 ? "보통" : "낮음";
  const coin = (x, n) => (x ? `<div class="row">${nm(n + " $" + fmt(x.last))}<span class="${cls(x.change)}">${sign(x.change)}${x.change}%</span></div><div class="row" style="margin:0"><span class="muted" style="font-size:10px">$${fmt(x.low)} ~ $${fmt(x.high)}</span></div>` : "");
  $("#mtop").innerHTML =
    mp("currency-bitcoin", "#e6b948", "BTC / ETH", coin(m.btc, "BTC") + coin(m.eth, "ETH")) +
    mp("mood-smile", "#5b8def", "시장 심리", `<div style="display:flex;height:7px;border-radius:4px;overflow:hidden;margin:2px 0 7px"><div style="width:${m.up_ratio}%;background:#2fd4bf"></div><div style="flex:1;background:#f15668"></div></div><div class="row"><span class="up">${m.up} 상승</span><span class="dn">${m.down} 하락</span></div><div class="row muted">전체 ${m.total}개 (${m.up_ratio}% 상승)</div><div class="row"><span class="muted">평균 변동</span><span class="${cls(m.avg_change)}">${sign(m.avg_change)}${m.avg_change}%</span></div>`) +
    mp("activity", "#e6b948", "시장 변동성", `<div style="display:flex;height:7px;border-radius:4px;overflow:hidden;margin:2px 0 7px;background:#2a2c36"><div style="width:${Math.min(m.avg_volatility / 15 * 100, 100)}%;background:linear-gradient(90deg,#e6b948,#f15668)"></div></div><div class="row"><span style="color:#e6b948">${lvl}</span><span style="color:#e6b948">avg [${m.avg_volatility.toFixed(2)}%]</span></div><div class="row"><span class="muted">일일 변동폭</span><span style="color:#cdd0d8">${m.daily_range}%</span></div>`) +
    mp("coin", "#35d6a4", "펀딩비", `<div class="row"><span class="muted">평균</span><span class="${cls(m.avg_funding)}">${m.avg_funding}%</span></div>` + (m.funding_high ? `<div class="row"><span class="muted">최고 ${noUsdt(m.funding_high.symbol)}</span><span class="up">${m.funding_high.pct}%</span></div>` : "") + (m.funding_low ? `<div class="row"><span class="muted">최저 ${noUsdt(m.funding_low.symbol)}</span><span class="dn">${m.funding_low.pct}%</span></div>` : ""));
  const lst = (a) => (a || []).map((c) => `<div class="row">${nm(noUsdt(c.symbol))}<span class="${cls(c.pct)}">${sign(c.pct)}${c.pct}%</span></div>`).join("");
  $("#mbot").innerHTML =
    mp("arrow-up-right", "#35d6a4", "Top 상승", lst(m.top_gainers)) +
    mp("arrow-down-right", "#f3647a", "Top 하락", lst(m.top_losers)) +
    mp("chart-candle", "#5b8def", "Top 거래량", (m.top_volume || []).map((c) => `<div class="row">${nm(noUsdt(c.symbol))}<span><span class="muted">${abbr(c.vol)}</span> <span class="${cls(c.pct)}">${sign(c.pct)}${c.pct}%</span></span></div>`).join(""));
}

async function renderPositions() {
  const p = await getJSON("/api/positions");
  $("#margin").textContent = (p || []).length + " 보유";
  const head = "<tr><th class='l'>심볼</th><th class='l'>전략</th><th class='l'>방향</th><th>수량</th><th>진입가</th><th>현재가</th><th>손익</th><th>수익률</th><th>배율</th><th>분할</th><th>TF</th><th class='l'>진입 시간</th></tr>";
  const rows = (p || []).map((w) =>
    `<tr><td class='l' style='color:#eef0f5'>${w.symbol}</td><td class='l'>${w.strategy}</td><td class='l'><span class='bs ${w.side}'>${w.side.toUpperCase()}</span></td><td>${fmt(w.qty)}</td><td>${w.entry_price}</td><td>${w.current_price}</td><td class='${cls(w.pnl)}'>${sign(w.pnl)}$${fmt(w.pnl)}</td><td class='${cls(w.roe)}'>${sign(w.roe)}${fmt(w.roe)}%</td><td>${w.leverage}x</td><td>${w.split}</td><td>${w.tf}</td><td class='l muted'>${w.entry_time || ""}</td></tr>`
  ).join("");
  $("#postable").innerHTML = head + rows;
}

const REASON_KO = { TrailingStop: "트레일링", Profit: "익절", StopLoss: "손절", ReverseExit: "역추세", Manual: "수동", Rebalance: "리밸런싱", RiskGuard: "리스크가드" };
function dur(entry, close) {
  if (!entry || !close) return "";
  const a = Date.parse(entry.replace(" ", "T")), b = Date.parse(close.replace(" ", "T"));
  if (isNaN(a) || isNaN(b)) return "";
  let s = Math.max(0, Math.round((b - a) / 1000));
  const d = Math.floor(s / 86400); s %= 86400;
  const h = Math.floor(s / 3600); s %= 3600;
  const m = Math.floor(s / 60);
  return d > 0 ? `${d}일 ${h}시간` : h > 0 ? `${h}시간 ${m}분` : `${m}분`;
}

async function renderRecords() {
  const r = (await getJSON("/api/records")) || [];
  const s = await getJSON("/api/status");
  const today = new Date().toISOString().slice(0, 10);
  const todayRecs = r.filter((x) => (x.close_time || "").slice(0, 10) === today);
  const todayPnl = todayRecs.reduce((a, x) => a + x.pnl, 0);
  const roes = r.map((x) => x.roe);
  const maxRoe = roes.length ? Math.max(...roes) : 0;
  const minRoe = roes.length ? Math.min(...roes) : 0;
  if (s) $("#reckpis").innerHTML =
    kpi("총 손익", sign(s.total_pnl) + "$" + fmt(s.total_pnl), s.trade_count + " trades", s.total_pnl >= 0 ? "#34d399" : "#f3647a", "currency-dollar", "#d8a72e") +
    kpi("오늘 손익", sign(todayPnl) + "$" + fmt(todayPnl), todayRecs.length + " trades today", todayPnl > 0 ? "#34d399" : todayPnl < 0 ? "#f3647a" : "#eef0f5", "calendar", "#35d6a4") +
    kpi("승률", s.win_rate + "%", "W:" + s.win + " / L:" + s.loss, "#5fa8ef", "percentage", "#5b8def") +
    kpi("평균 수익률", sign(s.avg_roe) + fmt(s.avg_roe) + "%", "Max: " + sign(maxRoe) + maxRoe.toFixed(2) + "% / " + minRoe.toFixed(2) + "%", "#34d399", "chart-line", "#d8a72e");
  const types = ["전체", "MeanRevert", "Breakout", "UprichAgrt"];
  $("#rechead").innerHTML = `<i class="ti ti-history" style="color:#5b8def" aria-hidden="true"></i> 거래 내역 <span class="muted" style="margin-left:6px">필터:</span> <select id="recfilter" class="fv" style="padding:3px 10px">${types.map((t) => `<option ${recFilter === t ? "selected" : ""}>${t}</option>`).join("")}</select> <span class="btn" style="margin-left:auto;border-color:#f1566840;color:#f47082">선택 삭제</span>`;
  $("#recfilter").onchange = (e) => { recFilter = e.target.value; renderRecords(); };
  const shown = recFilter === "전체" ? r : r.filter((x) => x.type === recFilter);
  const head = "<tr><th class='l'>심볼</th><th class='l'>방향</th><th>진입가</th><th>청산가</th><th>수량</th><th>손익</th><th>수익률</th><th>분할</th><th class='l'>타입</th><th class='l'>청산사유</th><th>TF</th><th class='l'>진입 시간</th><th class='l'>청산 시간</th><th class='l'>보유</th></tr>";
  const rows = shown.slice().reverse().map((x) =>
    `<tr><td class='l' style='color:#eef0f5'>${x.symbol}</td><td class='l'><span class='bs ${x.side}'>${x.side}</span></td><td>${x.entry_price}</td><td>${x.close_price}</td><td>${fmt(x.qty)}</td><td class='${cls(x.pnl)}'>${sign(x.pnl)}$${fmt(x.pnl)}</td><td class='${cls(x.roe)}'>${sign(x.roe)}${fmt(x.roe)}%</td><td>${x.split}</td><td class='l'>${x.type}</td><td class='l'>${REASON_KO[x.reason] || x.reason || "-"}</td><td>${x.tf}</td><td class='l muted'>${x.entry_time || ""}</td><td class='l muted'>${x.close_time || ""}</td><td class='l muted'>${dur(x.entry_time, x.close_time)}</td></tr>`
  ).join("");
  $("#rectable").innerHTML = head + rows;
}

async function renderLogs() {
  const d = await getJSON("/api/logs");
  $("#logcount").textContent = d ? "(" + d.total + ")" : "";
  const head = "<tr><th class='l'>시간</th><th class='l'>카테고리</th><th class='l'>메시지</th></tr>";
  const rows = (d ? d.items : []).map((x) =>
    `<tr><td class='l muted'>${x.time}</td><td class='l'><span class='tag ${x.category}'>${x.category}</span></td><td class='l'>${x.message}</td></tr>`
  ).join("");
  $("#logtable").innerHTML = head + rows;
}

async function renderSymbols() {
  const d = await getJSON("/api/symbols");
  $("#symcount").textContent = d ? d.count + "개" : "";
  $("#symlist").innerHTML = (d && d.universe || []).map((s) => `<span class="bs" style="background:#15161c;border:1px solid #20222b;margin:3px;display:inline-block;color:#cdd0d8">${s}</span>`).join("") || "<span class='muted'>스캔 대기 중…</span>";
}

let activeStrat = "mr";
let activeRisk = "커스텀";
const SK = { mr: "mean_revert_target", bo: "breakout_target", ua: "uprich_agrt_target" };
const SN = { mr: "MeanRevert", bo: "Breakout", ua: "UprichAgrt" };

function refOf(o) { return o === "root" ? cfg : o === "rg" ? cfg.risk_guards : cfg[SK[o]]; }

function sinp(o, k, lab, w) {
  return `<div class="frow"><span class="muted">${lab}</span><input class="fv" type="number" step="any" data-o="${o}" data-k="${k}" value="${refOf(o)[k]}" style="width:${w || 96}px"></div>`;
}
function sw(o, k, lab) {
  const on = refOf(o)[k];
  return `<label class="tgl"><span class="sw ${on ? "on" : ""}"><input type="checkbox" data-o="${o}" data-k="${k}" data-repaint="1" ${on ? "checked" : ""} style="position:absolute;opacity:0;width:30px;height:16px;margin:0"><span class="kb"></span></span><span>${lab}</span></label>`;
}

function tradePanel() {
  const single = activeStrat === "bo";
  const col = (side, pre, color) => `<div style="flex:1"><div style="font-size:12px;margin-bottom:6px;color:${color}">${side}</div>${sinp(activeStrat, pre + "usdt", "테더(USDT)")}${sinp(activeStrat, pre + "leverage", "레버리지")}${sinp(activeStrat, pre + "split_cnt", "분할 횟수")}${sinp(activeStrat, pre + "split_gap", "분할 간격 %")}${sinp(activeStrat, pre + "split_add", "분할 추가 %")}${sinp(activeStrat, pre + "position_cnt", "최대 포지션")}${sinp(activeStrat, pre + "auto_input_ctrl", "자동투입금")}</div>`;
  const body = single ? col("숏", "short_", "#f3647a") : col("롱", "long_", "#35d6a4") + col("숏", "short_", "#f3647a");
  return `<div class="panel"><h3>${SN[activeStrat]} 매매 설정</h3><div style="display:flex;gap:16px">${body}</div></div>`;
}

function exitPanel() {
  const o = activeStrat;
  const sliders = [["profit", "익절 %"], ["stop_loss", "손절 %"], ["trailing_stop", "트레일링 %"], ["min_profit", "최소수익 %"]]
    .map(([k, l]) => `<div style="flex:1">${sinp(o, k, l, 80)}</div>`).join("");
  const tgls = [["profit_use", "익절"], ["stop_loss_use", "손절"], ["trailing_stop_use", "트레일링 스탑"], ["reverse_exit", "역추세 정산"], ["isolated_margin", "격리 마진 (OFF=교차)"], ["funding_fee_check_enabled", "펀딩비 손익"], ["rebalance_enabled", "리밸런싱"]]
    .map(([k, l]) => sw(o, k, l)).join("");
  return `<div class="panel"><h3>${SN[activeStrat]} 익절/손절 설정</h3><div style="display:flex;gap:14px;margin-bottom:12px">${sliders}</div><div style="display:flex;flex-wrap:wrap;gap:14px">${tgls}</div></div>`;
}

function splitPanel() {
  const o = activeStrat, t = cfg[SK[o]];
  const m = t.split_interval_multiplier, st = t.split_multiplier_start_at;
  const pv = (g) => [2, 3, 4, 5].map((n) => `${n}차:${Math.round(t.split_squared_enabled && n >= st ? g * m * n : g)}%`).join(", ");
  const small = (k) => `<input class="fv" type="number" step="any" data-o="${o}" data-k="${k}" data-repaint="1" value="${t[k]}" style="width:54px;margin:0 4px">`;
  return `<div class="panel"><h3>${SN[activeStrat]} 분할 간격 배율</h3>
    <div style="display:flex;align-items:center;gap:18px;font-size:11.5px;margin-bottom:8px">${sw(o, "split_squared_enabled", "분할 제곱")}<span class="muted">배율 ${small("split_interval_multiplier")}</span><span class="muted">시작 차수 ${small("split_multiplier_start_at")} 차</span></div>
    <div style="font-size:11px;margin:3px 0"><span style="color:#35d6a4">Long ▶</span> <span style="color:#cdd0d8">${pv(t.long_split_gap)}</span></div>
    <div style="font-size:11px;margin:3px 0"><span style="color:#f3647a">Short ▶</span> <span style="color:#cdd0d8">${pv(t.short_split_gap)}</span></div>
    <p style="font-size:10px;color:#7c7e8a;margin-top:8px">※ 지정한 차수부터 분할 간격이 배수로 증가합니다</p></div>`;
}

function paintSettings() {
  const risks = ["공격적", "일반적", "안정적", "커스텀"].map((r) => `<span class="seg-i ${activeRisk === r ? "on" : ""}" data-risk="${r}">${r}</span>`).join("");
  const tabs = Object.keys(SN).map((k) => `<span class="stab ${activeStrat === k ? "on" : ""}" data-tab="${k}">${SN[k]}</span>`).join("");
  const enables = `<div style="display:flex;justify-content:center;gap:24px;margin:10px 0">${sw("root", "mean_revert_enabled", "MeanRevert")}${sw("root", "breakout_enabled", "Breakout")}${sw("root", "uprich_agrt_enabled", "UprichAgrt")}</div><p style="text-align:center;font-size:10.5px;color:#7c7e8a;margin:0">여러 전략을 동시에 활성화하면 함께 실행됩니다.</p>`;
  $("#setbody").innerHTML =
    `<div class="frow" style="margin-bottom:10px"><span class="muted">실행 모드</span><select class="fv" data-o="root" data-k="execution_mode">${["paper", "testnet", "live"].map((m) => `<option ${cfg.execution_mode === m ? "selected" : ""}>${m}</option>`).join("")}</select></div>` +
    `<div class="panel"><h3>리스크 모드</h3><div class="seg">${risks}</div><div class="stabs">${tabs}</div>${enables}</div>` +
    tradePanel() + exitPanel() + splitPanel() +
    `<div class="panel"><h3 style="color:#f3647a">리스크 가드 (기본 OFF)</h3><div style="display:flex;align-items:center;gap:18px;flex-wrap:wrap">${sw("rg", "enabled", "활성")}${sinp("rg", "position_max_loss_roe", "포지션 손절 ROE%")}${sinp("rg", "daily_loss_limit_usdt", "일일 손실한도 USDT")}</div></div>` +
    `<div style="display:flex;justify-content:flex-end;align-items:center;gap:8px;margin-top:8px"><span id="savemsg" class="muted"></span><button class="btn" onclick="renderSettings()">Reset</button><button class="btn gold" onclick="saveSettings()">Save Settings</button></div>`;
  bindSettings();
}

function bindSettings() {
  document.querySelectorAll("#setbody [data-k]").forEach((el) => {
    el.onchange = () => {
      const r = refOf(el.dataset.o), k = el.dataset.k;
      if (el.type === "checkbox") r[k] = el.checked;
      else if (el.type === "number") r[k] = parseFloat(el.value);
      else r[k] = el.value;
      if (el.dataset.repaint) paintSettings();
    };
  });
  document.querySelectorAll("#setbody [data-tab]").forEach((el) => { el.onclick = () => { activeStrat = el.dataset.tab; paintSettings(); }; });
  document.querySelectorAll("#setbody [data-risk]").forEach((el) => { el.onclick = () => { activeRisk = el.dataset.risk; paintSettings(); }; });
}

async function renderSettings() {
  cfg = await getJSON("/api/config");
  if (cfg) paintSettings();
}

async function saveSettings() {
  const r = await fetch("/api/config", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(cfg) });
  const d = await r.json();
  const msg = $("#savemsg");
  if (msg) msg.textContent = r.ok ? `저장됨 (${(d.changes || []).length}건)` : "저장 실패";
}

function refresh() {
  if (view === "dashboard") renderDashboard();
  else if (view === "positions") renderPositions();
  else if (view === "records") renderRecords();
  else if (view === "logs") renderLogs();
  else if (view === "symbols") renderSymbols();
  else if (view === "settings") { if (!cfg) renderSettings(); }
}

refresh();
setInterval(refresh, 5000);
