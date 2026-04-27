const button = document.querySelector("#refreshButton");
const statusEl = document.querySelector("#status");
const decisionSummary = document.querySelector("#decisionSummary");
const currentPosition = document.querySelector("#currentPosition");
const uvixEntryTqqqOpen = document.querySelector("#uvixEntryTqqqOpen");
const stateList = document.querySelector("#stateList");
const ruleList = document.querySelector("#ruleList");
const scenarioList = document.querySelector("#scenarioList");

function fmt(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  return Number(value).toLocaleString("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function pct(value) {
  return `${fmt(value, 2)}%`;
}

function setStatus(message, isError = false) {
  statusEl.textContent = message;
  statusEl.classList.toggle("error", isError);
}

function renderState(payload) {
  const state = payload.detected_state;
  const rows = [
    ["State as of", state.as_of],
    ["Current leg", state.selected_leg],
    ["Active UVIX", state.active_uvix ? "Yes" : "No"],
    ["Active low-RSI override", state.active_low_rsi_override ? "Yes" : "No"],
    ["UVIX entry TQQQ Open", fmt(state.uvix_entry_tqqq_open)],
    ["TQQQ peak Open", fmt(state.tqqq_peak_open)],
    ["NY time", payload.ny_time],
    ["Market open", payload.market_is_open ? "Yes" : "No"],
  ];
  stateList.innerHTML = rows
    .map(([key, value]) => `<dt>${key}</dt><dd>${value ?? "-"}</dd>`)
    .join("");

  ruleList.innerHTML = Object.entries(payload.strategy.rules)
    .map(([key, value]) => `<li><strong>${key}</strong>: ${value}</li>`)
    .join("");
}

function metric(label, value) {
  return `<div class="metric"><span>${label}</span><strong>${value}</strong></div>`;
}

function pickPrimaryScenario(payload) {
  const order = ["市場Open後の実Open", "SPY premarket/last示唆", "S&P futures示唆", "前日Close据え置き"];
  for (const name of order) {
    const match = payload.scenarios.find((scenario) => scenario.name === name);
    if (match) return match;
  }
  return payload.scenarios[0];
}

function actionText(scenario, currentLeg) {
  if (!scenario) return "判断なし";
  if (scenario.action === "enter_uvix") return "TQQQ等を売って UVIX を買う";
  if (scenario.action === "hold_uvix") return "UVIX を継続保有";
  if (scenario.action === "exit_uvix") return `UVIX を売って ${scenario.position} に戻す`;
  if (scenario.action === "enter_low_rsi_tqqq_override") return "待機ポジションを売って TQQQ を買う";
  if (scenario.action === "hold_low_rsi_tqqq_override") return "TQQQ を継続保有";
  if (scenario.action === "exit_low_rsi_tqqq_override") return `TQQQ を売って ${scenario.position} に戻す`;
  if (scenario.position === currentLeg) return `${scenario.position} を継続保有`;
  return `${currentLeg} から ${scenario.position} へ切り替え`;
}

function renderSummary(payload) {
  const scenario = pickPrimaryScenario(payload);
  if (!scenario) return;
  const currentLeg = payload.detected_state.selected_leg;
  const reasons = scenario.reasons.slice(0, 2).join(" / ");
  decisionSummary.innerHTML = `
    <div class="summary-topline">
      <p class="summary-label">結論: ${scenario.name}</p>
      <span class="rule-badge">${scenario.applied_rule}</span>
    </div>
    <div class="summary-main">${actionText(scenario, currentLeg)}</div>
    <div class="summary-position">最終ポジション: <strong>${scenario.position}</strong></div>
    <div class="summary-sub">${reasons}</div>
    <div class="summary-metrics">
      ${metric("Open-implied RSI14", fmt(scenario.values.gspc_open_implied_rsi14))}
      ${metric("GSPC Open input", fmt(scenario.values.gspc_open))}
      ${metric("TQQQ Open input", fmt(scenario.values.tqqq_open))}
      ${metric("TQQQ drawdown", pct(scenario.values.tqqq_drawdown_pct))}
    </div>
  `;
}

function renderScenario(item) {
  const values = item.values;
  return `
    <article class="scenario">
      <div>
        <h3>${item.name}</h3>
        <p class="subtitle">${item.description}</p>
        <span class="rule-badge">${item.applied_rule}</span>
      </div>
      <div>
        <div class="position">${item.position}</div>
        <ul class="reason-list">
          ${item.reasons.map((reason) => `<li>${reason}</li>`).join("")}
        </ul>
        <ul class="note-list">
          ${item.data_notes.map((note) => `<li>${note}</li>`).join("")}
        </ul>
      </div>
      <div class="metrics">
        ${metric("GSPC Open input", fmt(values.gspc_open))}
        ${metric("TQQQ Open input", fmt(values.tqqq_open))}
        ${metric("Open-implied RSI14", fmt(values.gspc_open_implied_rsi14))}
        ${metric("GSPC SMA160", fmt(values.gspc_sma160))}
        ${metric("TQQQ drawdown", pct(values.tqqq_drawdown_pct))}
        ${metric("UVIX entry TQQQ Open", fmt(values.uvix_entry_tqqq_open))}
      </div>
    </article>
  `;
}

function render(payload) {
  renderSummary(payload);
  renderState(payload);
  scenarioList.innerHTML = payload.scenarios.map(renderScenario).join("");
  setStatus(`取得完了: ${payload.fetched_at}`);
}

async function refresh() {
  button.disabled = true;
  setStatus("最新データを取得中です。yfinanceの応答に数十秒かかる場合があります。");
  try {
    const params = new URLSearchParams({ current_position: currentPosition.value });
    if (uvixEntryTqqqOpen.value) {
      params.set("uvix_entry_tqqq_open", uvixEntryTqqqOpen.value);
    }
    const response = await fetch(`/api/decision?${params.toString()}`, { cache: "no-store" });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "API error");
    render(payload);
  } catch (error) {
    setStatus(`取得に失敗しました: ${error.message}`, true);
  } finally {
    button.disabled = false;
  }
}

button.addEventListener("click", refresh);
refresh();
