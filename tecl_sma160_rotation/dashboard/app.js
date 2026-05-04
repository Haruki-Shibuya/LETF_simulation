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
    if (fromUrl === "2005" || fromUrl === "2010") return fromUrl;
    const stored = window.localStorage && window.localStorage.getItem("canonicalStart");
    return stored === "2010" ? "2010" : "2005";
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
