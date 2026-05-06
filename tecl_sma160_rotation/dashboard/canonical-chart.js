(function () {
  const el = document.getElementById("chart");
  const errEl = document.getElementById("chartError");
  const toolbar = document.getElementById("episodeToolbar");
  const btnPrev = document.getElementById("epPrev");
  const btnNext = document.getElementById("epNext");
  const slider = document.getElementById("epSlider");
  const lblEp = document.getElementById("epLabel");
  const rngEp = document.getElementById("epRange");
  const metricDays = document.getElementById("metricDays");
  const metricEntryRsi = document.getElementById("metricEntryRsi");
  const metricExitRsi = document.getElementById("metricExitRsi");
  const metricGspcReturn = document.getElementById("metricGspcReturn");
  const metricUvixReturn = document.getElementById("metricUvixReturn");
  const metricEntryReason = document.getElementById("metricEntryReason");
  const metricExitReason = document.getElementById("metricExitReason");
  const metricEpisode = document.getElementById("metricEpisode");
  const ruleLine = document.getElementById("ruleLine");
  const scatterGspcUvix = document.getElementById("scatterGspcUvix");
  const scatterRsiUvix = document.getElementById("scatterRsiUvix");
  const scatterGspcMeta = document.getElementById("scatterGspcMeta");
  const scatterRsiMeta = document.getElementById("scatterRsiMeta");

  let fullData = null;
  let sitePayload = null;
  let currentStart = "2005";
  let episodeIndex = 0;
  let plotInitialized = false;
  let scatterInitialized = false;
  let __hashSyncFromJs = false;
  let navBound = false;

  function parseEmbedded() {
    var n = document.getElementById("__canonicalEmbed");
    if (!n) return null;
    var t = n.textContent.replace(/^\s+|\s+$/g, "");
    if (!t || t === "{}") return null;
    try {
      var o = JSON.parse(t);
      if (o && o.variants) return o;
      if (o && Array.isArray(o.dates) && o.dates.length > 0) return o;
    } catch (e) {}
    return null;
  }

  function requestedStart() {
    var params = new URLSearchParams(window.location.search || "");
    var fromUrl = params.get("start");
    if (fromUrl === "2005" || fromUrl === "2010") return fromUrl;
    var stored = window.localStorage && window.localStorage.getItem("canonicalStart");
    return stored === "2010" ? "2010" : "2005";
  }

  function writeStart(start) {
    if (window.localStorage) window.localStorage.setItem("canonicalStart", start);
    var url = new URL(window.location.href);
    url.searchParams.set("start", start);
    window.history.replaceState(null, "", url.pathname + url.search + url.hash);
  }

  function selectVariant(payload, start) {
    if (payload && payload.variants) {
      return payload.variants[start] || payload.variants[payload.selected_variant] || payload.variants["2005"];
    }
    return payload;
  }

  function syncStartButtons(data) {
    var selected = (data && data.variant) || currentStart || "2005";
    var sel = document.getElementById("startSelect");
    if (sel) sel.value = selected;
  }

  function sliceArray(arr, i0, i1) {
    if (!arr || !Array.isArray(arr)) return arr;
    return arr.slice(i0, i1 + 1);
  }

  function slicePayload(data, i0, i1) {
    return {
      dates: sliceArray(data.dates, i0, i1),
      gspc_price: sliceArray(data.gspc_price || data.gspc_close, i0, i1),
      uvix_price: sliceArray(data.uvix_price || data.uvix_close, i0, i1),
      rsi: sliceArray(data.rsi, i0, i1),
      bb20_z: data.bb20_z ? sliceArray(data.bb20_z, i0, i1) : null,
      uvix_hold: sliceArray(data.uvix_hold, i0, i1),
      spans: [],
      title: data.title,
      subtitle: data.subtitle,
      meta: data.meta,
    };
  }

  function spanIndices(dates, start, end) {
    let i0 = dates.indexOf(start);
    let i1 = dates.indexOf(end);
    if (i0 < 0) {
      for (var i = 0; i < dates.length; i++) {
        if (dates[i] >= start) {
          i0 = i;
          break;
        }
      }
    }
    if (i1 < 0) {
      for (var j = dates.length - 1; j >= 0; j--) {
        if (dates[j] <= end) {
          i1 = j;
          break;
        }
      }
    }
    if (i0 < 0 || i1 < 0 || i0 > i1) return null;
    return { i0: i0, i1: i1 };
  }

  function chartHeightPx() {
    var tb = toolbar && !toolbar.hidden ? toolbar.offsetHeight : 0;
    var head = document.getElementById("canonicalPlotHeading");
    var hh = head && !head.hidden ? head.offsetHeight + 8 : 0;
    var reserve = window.innerWidth < 700 ? 330 : 285;
    return Math.max(470, window.innerHeight - tb - hh - reserve);
  }

  function fmtNum(value, digits) {
    if (value == null || Number(value) !== Number(value)) return "-";
    return Number(value).toLocaleString("en-US", {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    });
  }

  function fmtPct(value) {
    if (value == null || Number(value) !== Number(value)) return "-";
    var signed = Number(value);
    return (signed > 0 ? "+" : "") + (signed * 100).toFixed(2) + "%";
  }

  function isFiniteNumber(value) {
    return value != null && Number(value) === Number(value) && Number(value) !== Infinity && Number(value) !== -Infinity;
  }

  function pearson(points) {
    var n = points.length;
    if (n < 2) return null;
    var sx = 0;
    var sy = 0;
    for (var i = 0; i < n; i++) {
      sx += points[i].x;
      sy += points[i].y;
    }
    var mx = sx / n;
    var my = sy / n;
    var sxx = 0;
    var syy = 0;
    var sxy = 0;
    for (var j = 0; j < n; j++) {
      var dx = points[j].x - mx;
      var dy = points[j].y - my;
      sxx += dx * dx;
      syy += dy * dy;
      sxy += dx * dy;
    }
    if (sxx <= 0 || syy <= 0) return null;
    return sxy / Math.sqrt(sxx * syy);
  }

  function linearFit(points) {
    var n = points.length;
    if (n < 2) return null;
    var sx = 0;
    var sy = 0;
    for (var i = 0; i < n; i++) {
      sx += points[i].x;
      sy += points[i].y;
    }
    var mx = sx / n;
    var my = sy / n;
    var denom = 0;
    var numer = 0;
    var minX = points[0].x;
    var maxX = points[0].x;
    for (var j = 0; j < n; j++) {
      var x = points[j].x;
      var y = points[j].y;
      numer += (x - mx) * (y - my);
      denom += (x - mx) * (x - mx);
      if (x < minX) minX = x;
      if (x > maxX) maxX = x;
    }
    if (denom <= 0 || minX === maxX) return null;
    var slope = numer / denom;
    var intercept = my - slope * mx;
    return {
      slope: slope,
      intercept: intercept,
      x: [minX, maxX],
      y: [intercept + slope * minX, intercept + slope * maxX],
    };
  }

  function episodeScatterPoints(data, xGetter) {
    var spans = (data && data.spans) || [];
    var out = [];
    for (var i = 0; i < spans.length; i++) {
      var sp = spans[i] || {};
      var x = xGetter(sp);
      var y = isFiniteNumber(sp.uvix_return) ? Number(sp.uvix_return) * 100 : null;
      if (!isFiniteNumber(x) || !isFiniteNumber(y)) continue;
      out.push({
        x: Number(x),
        y: y,
        episode: i + 1,
        start: sp.start || "",
        end: sp.end || "",
        exitReason: sp.exit_reason || "-",
        entryReason: sp.entry_reason || "-",
        entryRsi: sp.entry_rsi,
        exitRsi: sp.exit_rsi,
      });
    }
    return out;
  }

  function scatterLayout(title, xTitle) {
    return {
      height: 360,
      autosize: true,
      paper_bgcolor: "#ffffff",
      plot_bgcolor: "#ffffff",
      font: { family: "Inter, ui-sans-serif, system-ui, sans-serif", color: "#111827" },
      margin: { l: 64, r: 22, t: 18, b: 58 },
      hovermode: "closest",
      showlegend: false,
      title: { text: "" },
      xaxis: {
        title: { text: xTitle, font: { size: 12 } },
        automargin: true,
        zeroline: true,
        zerolinecolor: "#98a2b3",
        gridcolor: "#edf0f4",
        tickfont: { size: 10, color: "#667085" },
      },
      yaxis: {
        title: { text: "UVIX return (%)", font: { size: 12 } },
        automargin: true,
        zeroline: true,
        zerolinecolor: "#98a2b3",
        gridcolor: "#edf0f4",
        tickfont: { size: 10, color: "#667085" },
      },
      annotations: [
        {
          xref: "paper",
          yref: "paper",
          x: 0,
          y: 1.06,
          xanchor: "left",
          yanchor: "bottom",
          text: "<b>" + title + "</b>",
          showarrow: false,
          font: { size: 13, color: "#111827" },
        },
      ],
    };
  }

  function drawOneScatter(node, metaNode, points, title, xTitle) {
    if (!node) return;
    var r = pearson(points);
    var fit = linearFit(points);
    if (metaNode) {
      metaNode.textContent =
        "Pearson r=" +
        (r == null ? "-" : r.toFixed(3)) +
        " · n=" +
        points.length +
        (fit ? " · fit slope=" + fit.slope.toFixed(2) : "");
    }
    var markerTrace = {
      type: "scatter",
      mode: "markers",
      name: "episode",
      x: points.map(function (p) {
        return p.x;
      }),
      y: points.map(function (p) {
        return p.y;
      }),
      customdata: points.map(function (p) {
        return [p.episode, p.start, p.end, p.exitReason, p.entryRsi, p.exitRsi, p.entryReason];
      }),
      marker: {
        color: "#2563eb",
        size: 7,
        opacity: 0.78,
        line: { color: "#ffffff", width: 0.8 },
      },
      hovertemplate:
        "Episode %{customdata[0]}<br>" +
        "%{customdata[1]} — %{customdata[2]}<br>" +
        xTitle +
        ": %{x:.2f}<br>" +
        "UVIX return: %{y:.2f}%<br>" +
        "Entry RSI: %{customdata[4]:.2f}<br>" +
        "Exit RSI: %{customdata[5]:.2f}<br>" +
        "Entry: %{customdata[6]}<br>" +
        "%{customdata[3]}<extra></extra>",
    };
    var traces = [markerTrace];
    if (fit) {
      traces.push({
        type: "scatter",
        mode: "lines",
        name: "linear fit",
        x: fit.x,
        y: fit.y,
        line: { color: "#101828", width: 2, dash: "dash" },
        hoverinfo: "skip",
      });
    }
    var config = { responsive: true, displayModeBar: false };
    Plotly.react(node, traces, scatterLayout(title, xTitle), config);
  }

  function drawScatterCharts(data) {
    if (!scatterGspcUvix && !scatterRsiUvix) return;
    var gspcPoints = episodeScatterPoints(data, function (sp) {
      return isFiniteNumber(sp.gspc_return) ? Number(sp.gspc_return) * 100 : null;
    });
    var rsiPoints = episodeScatterPoints(data, function (sp) {
      if (!isFiniteNumber(sp.entry_rsi) || !isFiniteNumber(sp.exit_rsi)) return null;
      return Number(sp.exit_rsi) - Number(sp.entry_rsi);
    });
    drawOneScatter(
      scatterGspcUvix,
      scatterGspcMeta,
      gspcPoints,
      "GSPC episode return vs UVIX episode return",
      "GSPC return (%)"
    );
    drawOneScatter(
      scatterRsiUvix,
      scatterRsiMeta,
      rsiPoints,
      "RSI move vs UVIX episode return",
      "Exit RSI - Entry RSI"
    );
    scatterInitialized = true;
  }

  function setReturnMetric(node, value) {
    if (!node) return;
    node.textContent = fmtPct(value);
    node.classList.remove("positive", "negative");
    if (value > 0) node.classList.add("positive");
    if (value < 0) node.classList.add("negative");
  }

  function syncRuleLine(data) {
    if (!ruleLine) return;
    var meta = (data && data.meta) || {};
    var entryRsi = meta.entry_rsi || meta.uvix_entry_rsi || 69.5;
    var exitRsi = meta.exit_rsi || meta.uvix_exit_rsi || 68.5;
    var bbz = meta.uvix_entry_min_bb_z;
    var dropPct = meta.uvix_tqqq_drop_exit_pct;
    var gspcProfitPct = meta.uvix_gspc_profit_exit_pct;
    var chips = [
      "Entry: RSI >= " + fmtNum(entryRsi, 1) + (bbz != null ? " & BB20Z >= " + fmtNum(bbz, 1) : ""),
      "Exit: RSI <= " + fmtNum(exitRsi, 1),
    ];
    if (dropPct != null) {
      chips.push("Exit: TQQQ open <= entry" + (Number(dropPct) ? " - " + fmtNum(dropPct, 1) + "%" : ""));
    }
    if (gspcProfitPct != null) {
      chips.push("Exit: GSPC open <= entry + " + fmtNum(gspcProfitPct, 1) + "%");
    }
    ruleLine.innerHTML = chips
      .map(function (txt) {
        return '<span class="rule-chip">' + txt + "</span>";
      })
      .join("");
  }

  function isoToJpLong(iso) {
    var p = String(iso || "").split("-");
    if (p.length !== 3) return String(iso || "");
    var y = parseInt(p[0], 10);
    var m = parseInt(p[1], 10);
    var d = parseInt(p[2], 10);
    return y + "年" + m + "月" + d + "日";
  }

  function syncPlotHeading(sliced, ctx) {
    var shell = document.getElementById("canonicalPlotHeading");
    var linesWrap = document.getElementById("canonicalPlotHeadingLines");
    var perEl = document.getElementById("canonicalPlotPeriod");
    var ex = document.getElementById("canonicalPlotExplain");
    if (!shell || !linesWrap || !perEl) return;
    shell.hidden = false;
    linesWrap.innerHTML = "";
    var raw = String(ctx.baseTitle || "").trim();
    var parts = raw
      .split("|")
      .map(function (s) {
        return s.trim();
      })
      .filter(function (s) {
        return s.length > 0;
      });
    parts.forEach(function (p) {
      var div = document.createElement("div");
      div.className = "canonical-plot-heading-line";
      div.textContent = p;
      linesWrap.appendChild(div);
    });
    var nd = sliced.dates ? sliced.dates.length : 0;
    perEl.textContent =
      isoToJpLong(ctx.span.start || "") +
      " — " +
      isoToJpLong(ctx.span.end || "") +
      " · " +
      nd +
      "営業日" +
      (nd === 1 ? " · 単一営業日（同日の2点を結んで線表示）" : "");
    if (ex) {
      if (nd === 1) {
        ex.hidden = false;
        ex.textContent =
          "日次バックテストで UVIX レッグがこの1営業日だけのケースです。横軸は同じ暦日の2時刻を結ぶため、必ず短い線分として表示されます。";
      } else {
        ex.hidden = true;
        ex.textContent = "";
      }
    }
  }

  /** 日足1行：同一暦日内の2ミリ秒（UTC）で必ず線分が出る */
  function widenXForSingleBarGraph(xDates) {
    if (!xDates || xDates.length !== 1) return null;
    var p = xDates[0].split("-");
    if (p.length !== 3) return null;
    var y = parseInt(p[0], 10);
    var m = parseInt(p[1], 10) - 1;
    var d = parseInt(p[2], 10);
    var t0 = Date.UTC(y, m, d, 14, 0, 0);
    var t1 = Date.UTC(y, m, d, 20, 0, 0);
    if (t0 !== t0 || t1 !== t1) return null;
    return [t0, t1];
  }

  function duplicateYForWideX(yArr, origLen, singlePad) {
    if (!singlePad || !yArr || yArr.length !== origLen || origLen !== 1) return yArr;
    var v = yArr[0];
    if (v != null && Number(v) === Number(v)) return [v, v];
    return [null, null];
  }

  function paddedXAxisRangeForPlotly(dates) {
    if (!dates || dates.length !== 1) return undefined;
    var t = new Date(dates[0] + "T12:00:00").getTime();
    if (t !== t) return undefined;
    var pad = 3 * 86400000;
    return [new Date(t - pad), new Date(t + pad)];
  }

  function buildLayout(sliced, ctx) {
    var dayMs = 86400000;
    var entryThr = (sliced.meta && sliced.meta.entry_rsi) || 69.5;
    var exitThr = (sliced.meta && sliced.meta.exit_rsi) || 68.5;

    var d1 = [0.72, 0.988];
    var d2 = [0.405, 0.688];
    var d3 = [0.055, 0.362];
    function mid(a) {
      return (a[0] + a[1]) / 2;
    }

    var paneLabels = [
      { y: mid(d1), text: "GSPC" },
      { y: mid(d2), text: "UVIX" },
      { y: mid(d3), text: "RSI14" },
    ];
    var labelAnn = paneLabels.map(function (pl) {
      return {
        xref: "paper",
        yref: "paper",
        x: 0.025,
        xanchor: "left",
        y: pl.y,
        yanchor: "middle",
        text: "<b>" + pl.text + "</b>",
        showarrow: false,
        font: { size: 11, color: "#475467" },
      };
    });

    var thresholdShapes = [
      {
        type: "line",
        xref: "paper",
        yref: "y",
        x0: 0,
        x1: 1,
        y0: 1,
        y1: 1,
        line: { color: "#98a2b3", width: 1, dash: "dot" },
        layer: "below",
      },
      {
        type: "line",
        xref: "paper",
        yref: "y2",
        x0: 0,
        x1: 1,
        y0: 1,
        y1: 1,
        line: { color: "#98a2b3", width: 1, dash: "dot" },
        layer: "below",
      },
      {
        type: "line",
        xref: "paper",
        yref: "y3",
        x0: 0,
        x1: 1,
        y0: entryThr,
        y1: entryThr,
        line: { color: "#475467", width: 1, dash: "dash" },
        layer: "below",
      },
      {
        type: "line",
        xref: "paper",
        yref: "y3",
        x0: 0,
        x1: 1,
        y0: exitThr,
        y1: exitThr,
        line: { color: "#667085", width: 1, dash: "dot" },
        layer: "below",
      },
    ];

    return {
      height: chartHeightPx(),
      dragmode: "zoom",
      paper_bgcolor: "#ffffff",
      plot_bgcolor: "#ffffff",
      font: { family: "Inter, ui-sans-serif, system-ui, sans-serif", color: "#111827" },
      margin: { l: 78, r: 22, t: 22, b: 92 },
      hovermode: "x unified",
      showlegend: true,
      title: { text: "" },
      annotations: labelAnn,
      legend: {
        orientation: "h",
        xref: "paper",
        yref: "paper",
        x: 0.12,
        y: -0.12,
        xanchor: "left",
        yanchor: "top",
        bgcolor: "rgba(255,255,255,0)",
        borderwidth: 0,
        font: { size: 11 },
        itemsizing: "constant",
        traceorder: "normal",
      },
      autosize: true,
      uirevision: "ep-" + ctx.episodeNum,
      xaxis: {
        title: { text: "日付（営業日・年付き）", font: { size: 11 } },
        type: "date",
        domain: [0.12, 0.985],
        anchor: "y3",
        automargin: true,
        showgrid: true,
        gridcolor: "#edf0f4",
        zeroline: false,
        showspikes: true,
        spikemode: "across",
        spikesnap: "cursor",
        spikethickness: 1,
        spikecolor: "#90a4ae",
        rangeslider: { visible: false },
        tickformat: "%Y-%m-%d",
        dtick: dayMs,
        tickangle: -45,
        tickfont: { size: 10, color: "#667085" },
        range: paddedXAxisRangeForPlotly(sliced.dates),
      },
      yaxis: {
        title: { text: "" },
        tickfont: { size: 10, color: "#667085" },
        domain: d1,
        anchor: "x",
        automargin: false,
        showgrid: true,
        gridcolor: "#edf0f4",
        zeroline: false,
      },
      yaxis2: {
        title: { text: "" },
        tickfont: { size: 10, color: "#667085" },
        domain: d2,
        anchor: "x",
        automargin: false,
        showgrid: true,
        gridcolor: "#edf0f4",
        zeroline: false,
      },
      yaxis3: {
        title: { text: "" },
        tickfont: { size: 10, color: "#667085" },
        domain: d3,
        anchor: "x",
        automargin: false,
        showgrid: true,
        gridcolor: "#edf0f4",
        zeroline: false,
      },
      shapes: thresholdShapes,
    };
  }

  function episodeRel(values, uvixHold) {
    const out = [];
    let entryValue = null;
    for (let i = 0; i < uvixHold.length; i++) {
      const hold = !!uvixHold[i];
      if (!hold) {
        out.push(null);
        entryValue = null;
        continue;
      }
      const prevHold = i > 0 && !!uvixHold[i - 1];
      var v = values[i];
      if (!prevHold) {
        entryValue = v != null ? Number(v) : null;
        if (entryValue != null && entryValue > 1e-15) {
          out.push(1);
        } else {
          out.push(null);
        }
        continue;
      }
      if (entryValue != null && entryValue > 1e-15 && v != null && Number(v) === Number(v)) {
        out.push(Number(v) / entryValue);
      } else {
        out.push(null);
      }
    }
    return out;
  }

  function scatterTrace(base) {
    var m = base._marker;
    delete base._marker;
    if (m !== undefined) base.marker = m;
    return base;
  }

  function tracesFromData(data) {
    const x = data.dates || [];
    const nx = x.length;
    const xWide = widenXForSingleBarGraph(x);
    const singlePad = !!xWide;
    const xPlot = singlePad ? xWide : x;
    const uvixHold = data.uvix_hold || [];

    var gspcValues = data.gspc_price || data.gspc_close || [];
    var uvixValues = data.uvix_price || data.uvix_close || [];
    var allInEpisode = new Array(nx).fill(true);

    var gspcY = gspcValues.length === nx ? episodeRel(gspcValues, allInEpisode) : gspcValues.slice();

    var uvixY;
    if (uvixValues.length === nx) {
      uvixY = episodeRel(uvixValues, allInEpisode);
    } else {
      uvixY = [];
    }

    var rsiY = data.rsi ? data.rsi.slice() : [];

    gspcY = duplicateYForWideX(gspcY, nx, singlePad);
    uvixY = duplicateYForWideX(uvixY, nx, singlePad);
    rsiY = duplicateYForWideX(rsiY, nx, singlePad);

    var modeLines;
    var lineW;
    var mkCol;
    if (nx <= 0) {
      modeLines = "lines";
      lineW = 1.3;
      mkCol = function () {
        return undefined;
      };
    } else if (singlePad) {
      modeLines = "lines";
      lineW = 2.9;
      mkCol = function () {
        return undefined;
      };
    } else if (nx <= 8) {
      modeLines = "lines+markers";
      lineW = 1.3;
      mkCol = function (stroke) {
        return { size: 5, line: { width: 0 } };
      };
    } else {
      modeLines = "lines";
      lineW = 1.3;
      mkCol = function () {
        return undefined;
      };
    }

    return [
      scatterTrace({
        type: "scatter",
        mode: modeLines,
        name: "GSPC open（エントリー=1）",
        x: xPlot,
        y: gspcY,
        connectgaps: false,
        line: { color: "#2563eb", width: lineW },
        _marker: mkCol("#0d47a1"),
        yaxis: "y",
        xaxis: "x",
        hovertemplate: "%{x}<br>GSPC open rel: %{y:.4f}<extra></extra>",
      }),
      scatterTrace({
        type: "scatter",
        mode: modeLines,
        name: "UVIX open（エントリー=1）",
        x: xPlot,
        y: uvixY,
        connectgaps: false,
        line: { color: "#16a34a", width: lineW },
        _marker: mkCol("#1b5e20"),
        yaxis: "y2",
        xaxis: "x",
        hovertemplate: "%{x}<br>UVIX open rel: %{y:.4f}<extra></extra>",
      }),
      scatterTrace({
        type: "scatter",
        mode: modeLines,
        name: "RSI(14)",
        x: xPlot,
        y: rsiY,
        line: { color: "#f97316", width: lineW },
        _marker: mkCol("#e65100"),
        yaxis: "y3",
        xaxis: "x",
      }),
    ];
  }

  function drawChart(sliced, ctx) {
    errEl.textContent = "";
    syncPlotHeading(sliced, ctx);
    try {
      var layout = buildLayout(sliced, ctx);
      var traces = tracesFromData(sliced);
      var config = {
        responsive: true,
        displayModeBar: true,
        modeBarButtonsToRemove: ["lasso2d", "select2d"],
        scrollZoom: true,
        doubleClick: "reset",
      };
      if (!plotInitialized) {
        Plotly.newPlot(el, traces, layout, config);
        plotInitialized = true;
      } else {
        Plotly.react(el, traces, layout, config);
      }
    } catch (err) {
      errEl.textContent = "Plot error: " + String(err.message || err);
    }
  }

  function updateToolbar(epIdx, epCount, span) {
    if (!toolbar) return;
    toolbar.hidden = false;
    lblEp.textContent = "エピソード " + (epIdx + 1) + " / " + epCount;
    rngEp.textContent = isoToJpLong(span.start || "") + " — " + isoToJpLong(span.end || "");
    slider.min = "0";
    slider.max = String(Math.max(0, epCount - 1));
    slider.step = "1";
    slider.value = String(epIdx);
    btnPrev.disabled = epIdx <= 0;
    btnNext.disabled = epIdx >= epCount - 1;
    if (metricDays) metricDays.textContent = (span.days || 0) + "営業日";
    if (metricEntryRsi) metricEntryRsi.textContent = fmtNum(span.entry_rsi, 2);
    if (metricExitRsi) metricExitRsi.textContent = fmtNum(span.exit_rsi, 2);
    if (metricEntryReason) metricEntryReason.textContent = span.entry_reason || "-";
    if (metricExitReason) metricExitReason.textContent = span.exit_reason || "-";
    if (metricEpisode) metricEpisode.textContent = (epIdx + 1) + " / " + epCount;
    setReturnMetric(metricGspcReturn, span.gspc_return);
    setReturnMetric(metricUvixReturn, span.uvix_return);
  }

  function renderEpisode(idx, opts) {
    opts = opts || {};
    if (!fullData) return;
    const spans = fullData.spans || [];
    const n = spans.length;
    episodeIndex = Math.max(0, Math.min(n - 1, idx));
    if (!opts.skipHashWrite) {
      var wantHash = "#e" + (episodeIndex + 1);
      if (window.location.hash !== wantHash) {
        __hashSyncFromJs = true;
        window.location.hash = wantHash;
        window.setTimeout(function () {
          __hashSyncFromJs = false;
        }, 80);
      }
    }
    var sp = spans[episodeIndex];
    var ix = spanIndices(fullData.dates, sp.start, sp.end);
    if (!ix) {
      errEl.textContent = "エピソードの日付範囲をデータに結びつけられません。";
      return;
    }
    var sliced = slicePayload(fullData, ix.i0, ix.i1);
    updateToolbar(episodeIndex, n, sp);
    drawChart(sliced, {
      baseTitle: fullData.title || "",
      baseSubtitle: fullData.subtitle || "",
      span: sp,
      episodeNum: episodeIndex + 1,
      episodeCount: n,
    });
  }

  window.addEventListener("hashchange", function () {
    if (__hashSyncFromJs || !fullData) return;
    var hb = hashToEpisodeOneBased();
    if (!hb || hb < 1) return;
    var nsp = (fullData.spans || []).length;
    var nextIdx = Math.max(0, Math.min(nsp - 1, hb - 1));
    if (nextIdx === episodeIndex) return;
    renderEpisode(nextIdx);
  });

  function bindNav() {
    if (navBound) return;
    navBound = true;
    if (!btnPrev) return;
    btnPrev.onclick = function () {
      renderEpisode(episodeIndex - 1);
    };
    btnNext.onclick = function () {
      renderEpisode(episodeIndex + 1);
    };
    slider.oninput = function () {
      renderEpisode(parseInt(slider.value, 10));
    };

    document.addEventListener(
      "keydown",
      function (ev) {
        var tn = ev.target && ev.target.tagName ? String(ev.target.tagName).toLowerCase() : "";
        if (tn === "input" || tn === "textarea" || tn === "select") return;
        if (!fullData || !(fullData.spans || []).length) return;
        if (ev.key === "ArrowRight") {
          renderEpisode(episodeIndex + 1);
          ev.preventDefault();
        } else if (ev.key === "ArrowLeft") {
          renderEpisode(episodeIndex - 1);
          ev.preventDefault();
        }
      },
      false
    );

    window.addEventListener(
      "resize",
      function () {
        if (!fullData || !(fullData.spans || []).length) return;
        renderEpisode(episodeIndex, { skipHashWrite: true });
        if (scatterInitialized) drawScatterCharts(fullData);
      },
      false
    );
  }

  function hashToEpisodeOneBased() {
    var h = (window.location.hash || "").replace(/^#/, "");
    var m = /^e(\d+)$/.exec(h);
    if (!m) return null;
    return parseInt(m[1], 10);
  }

  function startApp(data) {
    fullData = data;
    plotInitialized = false;
    scatterInitialized = false;
    currentStart = (data && data.variant) || currentStart || "2005";
    syncStartButtons(data);
    syncRuleLine(data);
    drawScatterCharts(data);
    const spans = data.spans || [];
    const n = spans.length;
    if (n === 0) {
      errEl.textContent = "UVIX ホールドのエピソード（スパン）がありません。";
      if (toolbar) toolbar.hidden = true;
      return;
    }
    bindNav();
    var fromHash = hashToEpisodeOneBased();
    var idx = 0;
    if (fromHash != null && fromHash >= 1) {
      idx = Math.min(n - 1, fromHash - 1);
    }
    episodeIndex = idx;
    renderEpisode(idx);
  }

  var startSelEl = document.getElementById("startSelect");
  if (startSelEl) {
    startSelEl.addEventListener("change", function () {
      currentStart = startSelEl.value || "2005";
      writeStart(currentStart);
      var nextData = selectVariant(sitePayload, currentStart);
      if (nextData) {
        startApp(nextData);
        return;
      }
      if (window.location.protocol !== "file:") {
        fetch("/api/canonical_chart?start=" + encodeURIComponent(currentStart), { cache: "no-store" })
          .then(function (r) {
            if (!r.ok) throw new Error("HTTP " + r.status);
            return r.json();
          })
          .then(function (data) {
            startApp(data);
          })
          .catch(function (e) {
            errEl.textContent = "開始日データの読み込みに失敗しました: " + String(e.message || e);
          });
      }
    });
  }

  var embedded = parseEmbedded();
  if (embedded) {
    sitePayload = embedded;
    currentStart = requestedStart();
    startApp(selectVariant(embedded, currentStart));
  } else if (window.location.protocol === "file:") {
    errEl.innerHTML =
      "<strong>データ未埋め込み</strong> <code>file://</code> で開いていますが、JSON が空です。<br />" +
      "プロジェクト根で <code>python3 build_canonical_chart_html_embedded.py</code> を実行して再試行してください。" +
      "<br />または <code>python3 dashboard_server.py</code> で http 経由を開いて <code>/api/canonical_chart</code> から取得してください。";
  } else {
    currentStart = requestedStart();
    fetch("/api/canonical_chart?start=" + encodeURIComponent(currentStart))
      .then(function (r) {
        if (!r.ok) {
          return r.text().then(function (txt) {
            throw new Error("HTTP " + r.status + (txt ? " — " + txt.slice(0, 120) : ""));
          });
        }
        return r.json();
      })
      .then(function (data) {
        startApp(data);
      })
      .catch(function (e) {
        var m = String(e.message || e);
        var hint =
          "\n\n（サーバー起動後 http で開いていますか？or 埋め込み用 <code>python3 build_canonical_chart_html_embedded.py</code>）";
        if (m.indexOf("404") >= 0) {
          hint += "\n\n404: URL は <code>/canonical-chart.html</code> （<code>python3 dashboard_server.py</code> 表示のまま）";
        }
        errEl.innerHTML =
          "読み込みに失敗しました。<code>/api/canonical_chart</code><br/><pre style='margin:0.5rem 0;white-space:pre-wrap'>" +
          m.replace(/</g, "&lt;") +
          "</pre>" +
          hint;
      });
  }
})();
