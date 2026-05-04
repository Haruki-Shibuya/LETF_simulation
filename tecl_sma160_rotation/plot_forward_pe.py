import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
import numpy as np
import os

CSV = os.path.join(os.path.dirname(__file__), "output", "valuation_forward_pe_2005_sim_monthly.csv")
OUT = os.path.join(os.path.dirname(__file__), "output", "forward_pe_gspc_qqq_2005.png")

df = pd.read_csv(CSV, parse_dates=["date"])
df = df.sort_values("date").set_index("date")
sp = df["sp500_forward_pe"].astype(float)
qqq = df["qqq_forward_pe"].astype(float)

fig, ax = plt.subplots(figsize=(14, 6))
fig.patch.set_facecolor("#0d1117")
ax.set_facecolor("#0d1117")

# Shaded recession / crash bands
bands = [
    ("2007-12-01", "2009-06-30", "GFC", 0.12),
    ("2020-02-01", "2020-04-30", "COVID\ncrash", 0.12),
    ("2022-01-01", "2022-12-31", "Rate-hike\nbear", 0.08),
]
for start, end, label, alpha in bands:
    ax.axvspan(pd.Timestamp(start), pd.Timestamp(end),
               color="#ffffff", alpha=alpha, zorder=0)
    mid = pd.Timestamp(start) + (pd.Timestamp(end) - pd.Timestamp(start)) / 2
    ax.text(mid, ax.get_ylim()[1] if ax.get_ylim()[1] > 10 else 45,
            label, ha="center", va="top", fontsize=7, color="#888888")

# Lines
ax.plot(sp.index, sp.values, color="#4e9af1", linewidth=2, label="S&P 500 (GSPC) Forward P/E", zorder=3)
ax.plot(qqq.index, qqq.values, color="#f97316", linewidth=2, label="NASDAQ-100 / QQQ Forward P/E", zorder=3)

# Horizontal averages
sp_mean = sp.mean()
qqq_mean = qqq.mean()
ax.axhline(sp_mean, color="#4e9af1", linewidth=0.8, linestyle="--", alpha=0.5)
ax.axhline(qqq_mean, color="#f97316", linewidth=0.8, linestyle="--", alpha=0.5)

# Current value annotations
for series, color, name in [(sp, "#4e9af1", "GSPC"), (qqq, "#f97316", "QQQ")]:
    last_val = series.dropna().iloc[-1]
    last_date = series.dropna().index[-1]
    ax.scatter([last_date], [last_val], color=color, s=40, zorder=5)
    ax.annotate(f"{name}: {last_val:.1f}x",
                xy=(last_date, last_val),
                xytext=(8, 0), textcoords="offset points",
                fontsize=8.5, color=color, va="center")

# Axes styling
ax.set_xlim(df.index.min(), df.index.max() + pd.DateOffset(months=6))
ax.set_ylim(0, max(qqq.max(), sp.max()) * 1.12)
ax.xaxis.set_major_locator(mdates.YearLocator(2))
ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.0fx"))
ax.tick_params(colors="#aaaaaa", labelsize=9)
for spine in ax.spines.values():
    spine.set_edgecolor("#333333")
ax.grid(axis="y", color="#333333", linewidth=0.5, alpha=0.7)
ax.grid(axis="x", color="#222222", linewidth=0.4, alpha=0.5)

# Legend and title
legend = ax.legend(loc="upper left", framealpha=0.15, edgecolor="#444444",
                   fontsize=9, labelcolor="linecolor")
ax.set_title("S&P 500 vs NASDAQ-100 / QQQ — Forward P/E Ratio (2005–2026)",
             color="#dddddd", fontsize=13, pad=12)
ax.set_ylabel("Forward P/E (NTM)", color="#aaaaaa", fontsize=10)

# Source annotation
ax.text(0.01, 0.01, "Sources: Doinoff (GSPC 2005–2025), Trendonify (GSPC 2026, NASDAQ-100 full), FactSet EPS Insight (cross-check)",
        transform=ax.transAxes, fontsize=6.5, color="#666666", va="bottom")

plt.tight_layout()
plt.savefig(OUT, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
print(f"Saved: {OUT}")
plt.show()
