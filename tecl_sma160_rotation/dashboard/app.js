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

  function writeStart(start) {
    if (window.localStorage) window.localStorage.setItem("canonicalStart", start);
    const url = new URL(window.location.href);
    url.searchParams.set("start", start);
    window.history.replaceState(null, "", url.pathname + url.search + url.hash);
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

  function renderBBChart(payload) {
    var canvas = document.getElementById("bbChart");
    if (!canvas) return;
    var history = payload.chart_history || [];
    var current = payload.chart_current || null;
    var all = current ? history.concat([current]) : history.slice();
    if (all.length < 2) return;

    var dpr = window.devicePixelRatio || 1;
    var W = canvas.offsetWidth || 640;
    var H = canvas.offsetHeight || 220;
    canvas.width = Math.round(W * dpr);
    canvas.height = Math.round(H * dpr);
    var ctx = canvas.getContext("2d");
    ctx.scale(dpr, dpr);

    var P = { top: 20, right: 20, bottom: 30, left: 68 };
    var iW = W - P.left - P.right;
    var iH = H - P.top - P.bottom;
    var n = all.length;

    var vals = [];
    all.forEach(function (p) {
      if (p.gspc_open != null) vals.push(p.gspc_open);
      if (p.gspc_close != null) vals.push(p.gspc_close);
      if (p.bb20_upper != null) vals.push(p.bb20_upper);
    });
    if (!vals.length) return;
    var yMin = Math.min.apply(null, vals) * 0.996;
    var yMax = Math.max.apply(null, vals) * 1.004;

    function xOf(i) { return P.left + (n > 1 ? (i / (n - 1)) * iW : iW / 2); }
    function yOf(v) { return P.top + (1 - (v - yMin) / (yMax - yMin)) * iH; }

    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, W, H);

    var GRID_N = 4;
    for (var g = 0; g <= GRID_N; g++) {
      var gv = yMin + (yMax - yMin) * (g / GRID_N);
      var gy = yOf(gv);
      ctx.strokeStyle = "#e5e7eb";
      ctx.lineWidth = 0.5;
      ctx.beginPath(); ctx.moveTo(P.left, gy); ctx.lineTo(W - P.right, gy); ctx.stroke();
      ctx.fillStyle = "#9ca3af";
      ctx.font = "11px ui-monospace,monospace";
      ctx.textAlign = "right";
      ctx.fillText(gv >= 1000 ? gv.toFixed(0) : gv.toFixed(1), P.left - 5, gy + 4);
    }

    ctx.beginPath();
    ctx.strokeStyle = "#d97706";
    ctx.lineWidth = 1.5;
    ctx.setLineDash([6, 3]);
    var started = false;
    all.forEach(function (p, i) {
      if (p.bb20_upper == null) return;
      if (!started) { ctx.moveTo(xOf(i), yOf(p.bb20_upper)); started = true; }
      else ctx.lineTo(xOf(i), yOf(p.bb20_upper));
    });
    ctx.stroke();
    ctx.setLineDash([]);

    ctx.beginPath();
    ctx.strokeStyle = "#2563eb";
    ctx.lineWidth = 2;
    started = false;
    all.forEach(function (p, i) {
      var price = p.gspc_open != null ? p.gspc_open : p.gspc_close;
      if (price == null) return;
      if (!started) { ctx.moveTo(xOf(i), yOf(price)); started = true; }
      else ctx.lineTo(xOf(i), yOf(price));
    });
    ctx.stroke();

    if (current) {
      var ci = all.length - 1;
      var cprice = current.gspc_open;
      if (cprice != null) {
        var cx = xOf(ci), cy = yOf(cprice);
        var above = current.bb20_upper != null && cprice >= current.bb20_upper;
        ctx.beginPath(); ctx.arc(cx, cy, 5, 0, Math.PI * 2);
        ctx.fillStyle = above ? "#047857" : "#dc2626";
        ctx.fill();
        ctx.fillStyle = above ? "#047857" : "#dc2626";
        ctx.font = "bold 11px ui-monospace,monospace";
        ctx.textAlign = "center";
        ctx.fillText(cprice.toFixed(0), cx, cy - 9);
      }
    }

    ctx.fillStyle = "#9ca3af";
    ctx.font = "10px ui-monospace,monospace";
    ctx.textAlign = "center";
    var step = Math.max(1, Math.round(n / 6));
    all.forEach(function (p, i) {
      if (i % step === 0 || i === n - 1) {
        ctx.fillText((p.date || "").slice(5), xOf(i), H - P.bottom + 14);
      }
    });

    ctx.font = "11px ui-sans-serif,sans-serif";
    ctx.textAlign = "left";
    ctx.fillStyle = "#2563eb";
    ctx.beginPath(); ctx.arc(P.left + 8, P.top + 8, 4, 0, Math.PI * 2); ctx.fill();
    ctx.fillText("GSPC open", P.left + 16, P.top + 12);
    ctx.strokeStyle = "#d97706"; ctx.lineWidth = 1.5; ctx.setLineDash([5, 3]);
    ctx.beginPath(); ctx.moveTo(P.left + 112, P.top + 8); ctx.lineTo(P.left + 126, P.top + 8); ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = "#d97706";
    ctx.fillText("BB20 +1.6σ", P.left + 130, P.top + 12);
  }

  function renderRSIChart(payload) {
    var canvas = document.getElementById("rsiChart");
    if (!canvas) return;
    var history = payload.chart_history || [];
    var current = payload.chart_current || null;
    var all = current ? history.concat([current]) : history.slice();
    if (all.length < 2) return;

    var dpr = window.devicePixelRatio || 1;
    var W = canvas.offsetWidth || 640;
    var H = canvas.offsetHeight || 160;
    canvas.width = Math.round(W * dpr);
    canvas.height = Math.round(H * dpr);
    var ctx = canvas.getContext("2d");
    ctx.scale(dpr, dpr);

    var P = { top: 20, right: 20, bottom: 30, left: 44 };
    var iW = W - P.left - P.right;
    var iH = H - P.top - P.bottom;
    var n = all.length;

    var rsiVals = all.map(function (p) { return p.rsi14; }).filter(function (v) { return v != null; });
    if (!rsiVals.length) return;
    var yMin = Math.min(Math.min.apply(null, rsiVals) - 2, 60);
    var yMax = Math.max(Math.max.apply(null, rsiVals) + 2, 75);

    function xOf(i) { return P.left + (n > 1 ? (i / (n - 1)) * iW : iW / 2); }
    function yOf(v) { return P.top + (1 - (v - yMin) / (yMax - yMin)) * iH; }

    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, W, H);

    var GRID_N = 4;
    for (var g = 0; g <= GRID_N; g++) {
      var gv = yMin + (yMax - yMin) * (g / GRID_N);
      var gy = yOf(gv);
      ctx.strokeStyle = "#e5e7eb";
      ctx.lineWidth = 0.5;
      ctx.beginPath(); ctx.moveTo(P.left, gy); ctx.lineTo(W - P.right, gy); ctx.stroke();
      ctx.fillStyle = "#9ca3af";
      ctx.font = "11px ui-monospace,monospace";
      ctx.textAlign = "right";
      ctx.fillText(gv.toFixed(0), P.left - 5, gy + 4);
    }

    var ENTRY_RSI = 67.5, EXIT_RSI = 66.0;
    ctx.lineWidth = 1;
    ctx.setLineDash([6, 3]);
    ctx.strokeStyle = "#047857";
    ctx.beginPath(); ctx.moveTo(P.left, yOf(ENTRY_RSI)); ctx.lineTo(W - P.right, yOf(ENTRY_RSI)); ctx.stroke();
    ctx.strokeStyle = "#d97706";
    ctx.beginPath(); ctx.moveTo(P.left, yOf(EXIT_RSI)); ctx.lineTo(W - P.right, yOf(EXIT_RSI)); ctx.stroke();
    ctx.setLineDash([]);
    ctx.font = "10px ui-monospace,monospace";
    ctx.textAlign = "right";
    ctx.fillStyle = "#047857";
    ctx.fillText("67.5", W - P.right - 4, yOf(ENTRY_RSI) - 3);
    ctx.fillStyle = "#d97706";
    ctx.fillText("66.0", W - P.right - 4, yOf(EXIT_RSI) + 11);

    ctx.beginPath();
    ctx.strokeStyle = "#2563eb";
    ctx.lineWidth = 2;
    var started = false;
    all.forEach(function (p, i) {
      if (p.rsi14 == null) return;
      if (!started) { ctx.moveTo(xOf(i), yOf(p.rsi14)); started = true; }
      else ctx.lineTo(xOf(i), yOf(p.rsi14));
    });
    ctx.stroke();

    if (current && current.rsi14 != null) {
      var ci = all.length - 1;
      var cx = xOf(ci), cy = yOf(current.rsi14);
      var rcolor = current.rsi14 >= ENTRY_RSI ? "#047857" : current.rsi14 >= EXIT_RSI ? "#d97706" : "#dc2626";
      ctx.beginPath(); ctx.arc(cx, cy, 5, 0, Math.PI * 2);
      ctx.fillStyle = rcolor;
      ctx.fill();
      ctx.fillStyle = rcolor;
      ctx.font = "bold 11px ui-monospace,monospace";
      ctx.textAlign = "center";
      ctx.fillText(current.rsi14.toFixed(1), cx, cy - 9);
    }

    ctx.fillStyle = "#9ca3af";
    ctx.font = "10px ui-monospace,monospace";
    ctx.textAlign = "center";
    var step = Math.max(1, Math.round(n / 6));
    all.forEach(function (p, i) {
      if (i % step === 0 || i === n - 1) {
        ctx.fillText((p.date || "").slice(5), xOf(i), H - P.bottom + 14);
      }
    });

    ctx.font = "11px ui-sans-serif,sans-serif";
    ctx.textAlign = "left";
    ctx.fillStyle = "#2563eb";
    ctx.beginPath(); ctx.arc(P.left + 8, P.top + 8, 4, 0, Math.PI * 2); ctx.fill();
    ctx.fillText("RSI14", P.left + 16, P.top + 12);
    ctx.strokeStyle = "#047857"; ctx.lineWidth = 1; ctx.setLineDash([5, 3]);
    ctx.beginPath(); ctx.moveTo(P.left + 68, P.top + 8); ctx.lineTo(P.left + 82, P.top + 8); ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = "#047857";
    ctx.fillText("entry 67.5", P.left + 86, P.top + 12);
    ctx.strokeStyle = "#d97706"; ctx.lineWidth = 1; ctx.setLineDash([5, 3]);
    ctx.beginPath(); ctx.moveTo(P.left + 168, P.top + 8); ctx.lineTo(P.left + 182, P.top + 8); ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = "#d97706";
    ctx.fillText("exit 66.0", P.left + 186, P.top + 12);
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
    document.querySelectorAll(".mode-button").forEach((button) => {
      const mode = button.dataset.mode;
      const enabled = availability[mode] !== false;
      button.disabled = !enabled;
      button.classList.toggle("active", mode === selected);
    });
  }

  function renderStartButtons(payload) {
    const selected = (payload && payload.variant) || currentStart || "2005";
    document.querySelectorAll(".start-button").forEach((button) => {
      button.classList.toggle("active", button.dataset.start === selected);
    });
  }

  function render(payload) {
    renderSummary(payload);
    renderMetrics(payload);
    renderReasons(payload);
    renderEntry(payload);
    renderRules(payload);
    renderModeButtons(payload);
    renderStartButtons(payload);
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

  async function refreshMode(mode) {
    setRefreshStatus("更新中...");
    document.querySelectorAll(".mode-button").forEach((button) => {
      button.disabled = true;
    });
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
    }
  }

  document.querySelectorAll(".mode-button").forEach((button) => {
    button.addEventListener("click", () => refreshMode(button.dataset.mode));
  });

  document.querySelectorAll(".start-button").forEach((button) => {
    button.addEventListener("click", () => {
      currentStart = button.dataset.start || "2005";
      writeStart(currentStart);
      const nextPayload = selectVariant(sitePayload, currentStart);
      if (nextPayload) {
        currentPayload = nextPayload;
        render(currentPayload);
      }
      if (window.location.protocol !== "file:") {
        const mode = (currentPayload && currentPayload.modes && currentPayload.modes.selected) || "latest";
        refreshMode(mode);
      }
    });
  });

  const sitePayload = readPayload();
  let currentStart = requestedStart();
  let currentPayload = selectVariant(sitePayload, currentStart);
  if (!currentPayload || currentPayload.error) {
    renderError((currentPayload && currentPayload.error) || "Missing embedded dashboard data.");
    return;
  }
  render(currentPayload);
})();
