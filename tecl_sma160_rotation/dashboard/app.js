(function () {
  "use strict";

  function $(selector) {
    return document.querySelector(selector);
  }

  function fmt(value, digits) {
    if (digits === undefined) digits = 2;
    if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
    return Number(value).toLocaleString("en-US", {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    });
  }

  function pct(value, digits) {
    if (digits === undefined) digits = 2;
    if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
    return fmt(Number(value) * 100, digits) + "%";
  }

  function readPayload() {
    const node = $("#__positionEmbed");
    if (!node) return null;
    try {
      return JSON.parse(node.textContent || "{}");
    } catch (error) {
      return { error: error.message };
    }
  }

  function requestedStart() {
    const params = new URLSearchParams(window.location.search || "");
    const fromUrl = params.get("start");
    if (fromUrl === "2005" || fromUrl === "2010" || fromUrl === "1991") return fromUrl;
    const stored = window.localStorage && window.localStorage.getItem("canonicalStart");
    return stored === "2010" ? "2010" : stored === "1991" ? "1991" : "2005";
  }

function selectVariant(sitePayload, start) {
    if (sitePayload && sitePayload.variants) {
      return sitePayload.variants[start] || sitePayload.variants[sitePayload.selected_variant] || sitePayload.variants["2005"];
    }
    return sitePayload;
  }

  function metricValue(selector, value) {
    const node = $(selector);
    if (node) node.textContent = value;
  }

  function rowsToDl(rows) {
    return rows.map(([key, value]) => "<dt>" + key + "</dt><dd>" + (value ?? "-") + "</dd>").join("");
  }

  function renderSummary(payload) {
    const decision = payload.decision || {};
    const summary = payload.summary || {};
    const source = payload.source || {};
    const checks = decision.exit_checks || {};
    const trigger = checks.gspc_profit_trigger;
    const triggerText = trigger == null ? "" : " / GSPC profit trigger " + fmt(trigger, 2);
    const sourceTime = source.source_time_jst || "-";
    const generatedAt = source.generated_at_jst ? " / generated " + source.generated_at_jst : "";
    $("#decisionSummary").innerHTML = [
      '<div class="summary-topline">',
      '<p class="summary-label">最新カノニカル判定</p>',
      '<span class="rule-badge">' + (summary.transition_policy || "one_open_transition_per_day") + "</span>",
      "</div>",
      '<div class="summary-main">' + (decision.headline || "-") + "</div>",
      '<div class="summary-position">最終ポジション: <strong>' + (decision.position || "-") + "</strong></div>",
      '<div class="summary-sub">データソース: ' +
        (source.label || payload.generated_from || "-") +
        " / " +
        sourceTime +
        generatedAt +
        " / " +
        (source.market_time_et || "-") +
        " / " +
        (source.market_phase || "-") +
        triggerText +
        "</div>",
    ].join("");
  }

  function renderMetrics(payload) {
    const latest = payload.decision_input || payload.latest || {};
    const source = payload.source || {};
    const decision = payload.decision || {};
    metricValue("#metricDate", source.source_time_jst || source.generated_at_jst || latest.date || "-");
    metricValue("#metricPosition", decision.position || latest.selected_leg || "-");
    metricValue("#metricSource", source.label || "-");
    metricValue("#metricRsi", fmt(latest.rsi, 2));
    metricValue("#metricBbz", fmt(latest.bb20_z, 2));
    metricValue("#metricGspc", fmt(latest.gspc_open, 2));
    metricValue("#metricTqqq", fmt(latest.tqqq_open, 2));
    metricValue("#metricEquity", fmt(latest.strategy_equity, 2));
  }

  function renderReasons(payload) {
    const reasons = ((payload.decision && payload.decision.reasons) || []).concat(
      (payload.source && payload.source.notes) || [],
    );
    $("#reasonList").innerHTML = reasons.length
      ? reasons.map((reason) => "<li>" + reason + "</li>").join("")
      : "<li>No reason text.</li>";
  }

  function renderEntry(payload) {
    const entry = payload.active_entry;
    if (!entry) {
      $("#entryList").innerHTML = rowsToDl([["状態", "高RSI UVIX最優先 / 低RSI TQQQ最優先の進行中ポジションはありません"]]);
      return;
    }
    $("#entryList").innerHTML = rowsToDl([
      ["発動日", entry.date],
      ["発動ポジション", entry.selected_leg],
      ["発動アクション", entry.action || "-"],
      ["発動時 Implied RSI (14)", fmt(entry.rsi, 2)],
      ["発動時 BB20 Z", fmt(entry.bb20_z, 2)],
      ["発動時 GSPC始値", fmt(entry.gspc_open, 2)],
      ["発動時 TQQQ始値", fmt(entry.tqqq_open, 2)],
    ]);
  }

  function renderRules(payload) {
    const rules = payload.rules || {};
    $("#ruleList").innerHTML = Object.entries(rules)
      .map(([key, value]) => "<li><strong>" + key + "</strong>: " + value + "</li>")
      .join("");
  }

  // ── Chart instances (Chart.js) ────────────────────────────────────────────
  var bbChartInst = null;
  var rsiChartInst = null;

  function renderBBChart(payload) {
    if (typeof Chart === "undefined") return;
    var canvas = document.getElementById("bbChart");
    if (!canvas) return;
    var history = payload.chart_history || [];
    var current = payload.chart_current || null;
    var all = current ? history.concat([current]) : history.slice();
    if (all.length < 2) return;

    var timeEl = document.getElementById("chartSourceTime");
    if (timeEl) {
      var t = (payload.source && payload.source.source_time_jst) || (current && current.source_time_jst) || "";
      timeEl.textContent = t ? "推定値取得: " + t : "";
    }

    var n = all.length;
    var hasCurrent = !!current;
    var labels = all.map(function (p) { return p.date || ""; });
    var gspcData = all.map(function (p) { return p.gspc_open; });
    var bb20Data = all.map(function (p) { return p.bb20_upper; });

    var currColor = "#9ca3af";
    if (hasCurrent && current.gspc_open != null && current.bb20_upper != null) {
      currColor = current.gspc_open >= current.bb20_upper ? "#047857" : "#dc2626";
    }
    var gspcPtRadius = gspcData.map(function (_, i) { return i === n - 1 && hasCurrent ? 5 : 0; });
    var gspcPtBg = gspcData.map(function (_, i) { return i === n - 1 && hasCurrent ? currColor : "transparent"; });

    if (bbChartInst) { bbChartInst.destroy(); bbChartInst = null; }
    bbChartInst = new Chart(canvas, {
      type: "line",
      data: {
        labels: labels,
        datasets: [
          {
            label: "GSPC open",
            data: gspcData,
            borderColor: "#2563eb",
            borderWidth: 2,
            pointRadius: gspcPtRadius,
            pointHoverRadius: 4,
            pointBackgroundColor: gspcPtBg,
            tension: 0,
            fill: false,
            segment: hasCurrent ? {
              borderDash: function (ctx) { return ctx.p1DataIndex === n - 1 ? [4, 4] : undefined; },
            } : undefined,
          },
          {
            label: "BB20 +1.6σ (close)",
            data: bb20Data,
            borderColor: "#d97706",
            borderWidth: 1.5,
            pointRadius: 0,
            pointHoverRadius: 4,
            tension: 0,
            fill: false,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { position: "top", labels: { boxWidth: 16, padding: 12, font: { size: 11 } } },
          tooltip: {
            callbacks: {
              title: function (items) { var p = all[items[0].dataIndex]; return p.source_time_jst || p.date || ""; },
              label: function (ctx) {
                var v = ctx.parsed.y;
                var str = ctx.dataset.label + ": " + (v != null ? v.toFixed(0) : "-");
                if (hasCurrent && ctx.dataIndex === n - 1 && ctx.datasetIndex === 0) str += " (推定)";
                return str;
              },
            },
          },
          zoom: {
            zoom: { wheel: { enabled: true }, pinch: { enabled: true }, mode: "x" },
            pan: { enabled: true, mode: "x" },
          },
        },
        scales: {
          x: {
            ticks: {
              maxRotation: 0,
              maxTicksLimit: 8,
              font: { size: 10 },
              callback: function (val, idx) { return labels[idx] ? labels[idx].slice(5) : ""; },
            },
          },
          y: {
            ticks: { font: { size: 11 }, callback: function (v) { return v.toFixed(0); } },
          },
        },
      },
    });
    canvas.ondblclick = function () { if (bbChartInst) bbChartInst.resetZoom(); };
  }

  function renderRSIChart(payload) {
    if (typeof Chart === "undefined") return;
    var canvas = document.getElementById("rsiChart");
    if (!canvas) return;
    var history = payload.chart_history || [];
    var current = payload.chart_current || null;
    var all = current ? history.concat([current]) : history.slice();
    if (all.length < 2) return;

    var n = all.length;
    var hasCurrent = !!current;
    var ENTRY_RSI = 67.5, EXIT_RSI = 66.0;
    var labels = all.map(function (p) { return p.date || ""; });
    var rsiData = all.map(function (p) { return p.rsi14; });
    var entryLine = rsiData.map(function () { return ENTRY_RSI; });
    var exitLine = rsiData.map(function () { return EXIT_RSI; });

    var currColor = "#9ca3af";
    if (hasCurrent && current.rsi14 != null) {
      currColor = current.rsi14 >= ENTRY_RSI ? "#047857" : current.rsi14 >= EXIT_RSI ? "#d97706" : "#dc2626";
    }
    var rsiPtRadius = rsiData.map(function (_, i) { return i === n - 1 && hasCurrent ? 5 : 0; });
    var rsiPtBg = rsiData.map(function (_, i) { return i === n - 1 && hasCurrent ? currColor : "transparent"; });

    if (rsiChartInst) { rsiChartInst.destroy(); rsiChartInst = null; }
    rsiChartInst = new Chart(canvas, {
      type: "line",
      data: {
        labels: labels,
        datasets: [
          {
            label: "RSI14",
            data: rsiData,
            borderColor: "#2563eb",
            borderWidth: 2,
            pointRadius: rsiPtRadius,
            pointHoverRadius: 4,
            pointBackgroundColor: rsiPtBg,
            tension: 0,
            fill: false,
            order: 1,
            segment: hasCurrent ? {
              borderDash: function (ctx) { return ctx.p1DataIndex === n - 1 ? [4, 4] : undefined; },
            } : undefined,
          },
          {
            label: "entry 67.5",
            data: entryLine,
            borderColor: "#047857",
            borderWidth: 1,
            borderDash: [6, 3],
            pointRadius: 0,
            pointHoverRadius: 0,
            tension: 0,
            fill: false,
            order: 2,
          },
          {
            label: "exit 66.0",
            data: exitLine,
            borderColor: "#d97706",
            borderWidth: 1,
            borderDash: [6, 3],
            pointRadius: 0,
            pointHoverRadius: 0,
            tension: 0,
            fill: false,
            order: 2,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { position: "top", labels: { boxWidth: 16, padding: 12, font: { size: 11 } } },
          tooltip: {
            filter: function (item) { return item.dataset.label === "RSI14"; },
            callbacks: {
              title: function (items) { var p = all[items[0].dataIndex]; return p.source_time_jst || p.date || ""; },
              label: function (ctx) {
                var v = ctx.parsed.y;
                var str = "RSI14: " + (v != null ? v.toFixed(1) : "-");
                if (hasCurrent && ctx.dataIndex === n - 1) str += " (推定)";
                return str;
              },
            },
          },
          zoom: {
            zoom: { wheel: { enabled: true }, pinch: { enabled: true }, mode: "x" },
            pan: { enabled: true, mode: "x" },
          },
        },
        scales: {
          x: {
            ticks: {
              maxRotation: 0,
              maxTicksLimit: 8,
              font: { size: 10 },
              callback: function (val, idx) { return labels[idx] ? labels[idx].slice(5) : ""; },
            },
          },
          y: { ticks: { font: { size: 11 } } },
        },
      },
    });
    canvas.ondblclick = function () { if (rsiChartInst) rsiChartInst.resetZoom(); };
  }

  function renderError(message) {
    $("#decisionSummary").innerHTML =
      '<div class="summary-main">Dashboard error</div><div class="summary-sub">' + message + "</div>";
  }

  function setRefreshStatus(message, isError) {
    const node = $("#refreshStatus");
    if (!node) return;
    node.textContent = message || "";
    node.classList.toggle("error", !!isError);
  }

  function renderModeButtons(payload) {
    const modes = payload.modes || {};
    const selected = modes.selected || (payload.source && payload.source.selected_mode) || "latest";
    const availability = modes.availability || {};
    const sel = document.getElementById("modeSelect");
    if (!sel) return;
    Array.from(sel.options).forEach(function (opt) {
      opt.disabled = availability[opt.value] === false;
    });
    sel.value = selected;
  }

function render(payload) {
    renderSummary(payload);
    renderMetrics(payload);
    renderReasons(payload);
    renderEntry(payload);
    renderRules(payload);
    renderModeButtons(payload);
    renderBBChart(payload);
    renderRSIChart(payload);
  }

  function apiUrl(mode, start) {
    const query =
      "?mode=" + encodeURIComponent(mode || "latest") + "&start=" + encodeURIComponent(start || currentStart || "2005");
    if (window.location.protocol === "file:") {
      return "http://127.0.0.1:8765/api/position" + query;
    }
    return "/api/position" + query;
  }

  function setRefreshBusy(busy) {
    const modeSelEl = document.getElementById("modeSelect");
    const refreshBtn = document.getElementById("refreshBtn");
    if (modeSelEl) modeSelEl.disabled = busy;
    if (refreshBtn) refreshBtn.disabled = busy;
  }

  async function refreshMode(mode) {
    setRefreshStatus("更新中...");
    setRefreshBusy(true);
    try {
      const response = await fetch(apiUrl(mode, currentStart), { cache: "no-store" });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "API error");
      currentPayload = payload;
      render(payload);
      const source = payload.source || {};
      setRefreshStatus((source.source_time_jst || source.generated_at_jst || "") + " 更新", false);
    } catch (error) {
      renderModeButtons(currentPayload || {});
      setRefreshStatus("更新失敗: ローカルサーバ http://127.0.0.1:8765 を起動してください", true);
    } finally {
      setRefreshBusy(false);
    }
  }

  const modeSelEl = document.getElementById("modeSelect");
  if (modeSelEl) {
    modeSelEl.addEventListener("change", function () { refreshMode(modeSelEl.value); });
  }

  const refreshBtn = document.getElementById("refreshBtn");
  if (refreshBtn) {
    refreshBtn.addEventListener("click", function () {
      const mode = (modeSelEl && modeSelEl.value) || "latest";
      refreshMode(mode);
    });
  }


  const sitePayload = readPayload();
  let currentStart = requestedStart();
  let currentPayload = selectVariant(sitePayload, currentStart);
  if (!currentPayload || currentPayload.error) {
    renderError((currentPayload && currentPayload.error) || "Missing embedded dashboard data.");
    return;
  }
  render(currentPayload);
})();
