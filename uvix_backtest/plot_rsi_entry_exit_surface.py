from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent

DEFAULT_INPUT = Path(
    BASE_DIR / "output" /
    "stitched_uvix_longvol_2x_full_grid_from_20110101_entrystep_0p1_exitstep_0p1.csv"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help="Path to a full_grid CSV produced by rsi_entry_exit_optimize.py.",
    )
    parser.add_argument(
        "--title",
        default=None,
        help="Optional chart title prefix.",
    )
    return parser.parse_args()


def load_grid(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    required = {
        "entry",
        "exit",
        "cagr",
        "start_date",
        "end_date",
    }
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Missing required columns in {path}: {sorted(missing)}")
    return frame


def derive_label(path: Path, explicit_title: str | None) -> str:
    if explicit_title:
        return explicit_title
    stem = path.stem
    dataset = stem.split("_full_grid")[0].replace("_", " ")
    return dataset


def build_title(frame: pd.DataFrame, label: str) -> str:
    start_date = frame["start_date"].iloc[0]
    end_date = frame["end_date"].iloc[0]
    return f"{label} | {start_date} to {end_date}"


def build_surface_matrix(frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    pivot = frame.pivot(index="exit", columns="entry", values="cagr").sort_index().sort_index(axis=1)
    x = pivot.columns.to_numpy(dtype=float)
    y = pivot.index.to_numpy(dtype=float)
    z = pivot.to_numpy(dtype=float) * 100.0
    return x, y, z


def build_heatmap_matrix(frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    x, y, z = build_surface_matrix(frame)
    z = np.ma.masked_invalid(z)
    return x, y, z


def to_jsonable_2d(values: np.ndarray) -> list[list[float | None]]:
    rows: list[list[float | None]] = []
    for row in values:
        rows.append([None if np.isnan(value) else float(value) for value in row])
    return rows


def save_3d_surface(frame: pd.DataFrame, title: str, output_path: Path) -> None:
    best = frame.loc[frame["cagr"].idxmax()]
    z_pct = frame["cagr"].to_numpy(dtype=float) * 100.0
    x = frame["entry"].to_numpy(dtype=float)
    y = frame["exit"].to_numpy(dtype=float)
    best_z = float(best["cagr"] * 100.0)
    z_offset = max(1.5, (np.nanmax(z_pct) - np.nanmin(z_pct)) * 0.04)

    fig = plt.figure(figsize=(14, 10), constrained_layout=True)
    ax = fig.add_subplot(111, projection="3d")
    surface = ax.plot_trisurf(x, y, z_pct, cmap="viridis", linewidth=0.15, antialiased=True)
    ax.scatter(
        [best["entry"]],
        [best["exit"]],
        [best_z],
        color="red",
        s=90,
        depthshade=False,
        label="Best CAGR",
    )
    ax.text(
        float(best["entry"]),
        float(best["exit"]),
        best_z + z_offset,
        f"Best\nentry={best['entry']:.1f}\nexit={best['exit']:.1f}\nCAGR={best_z:.2f}%",
        color="red",
        fontsize=10,
        ha="left",
        va="bottom",
    )
    ax.set_xlabel("RSI Entry")
    ax.set_ylabel("RSI Exit")
    ax.set_zlabel("CAGR (%)")
    ax.set_title(f"RSI Entry/Exit CAGR Surface\n{title}")
    ax.view_init(elev=28, azim=-132)
    ax.legend(loc="upper left")
    colorbar = fig.colorbar(surface, ax=ax, shrink=0.7, pad=0.08)
    colorbar.set_label("CAGR (%)")
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_interactive_3d_surface_html(frame: pd.DataFrame, title: str, output_path: Path) -> None:
    best = frame.loc[frame["cagr"].idxmax()]
    x, y, z = build_surface_matrix(frame)

    payload = {
        "x": x.tolist(),
        "y": y.tolist(),
        "z": to_jsonable_2d(z),
        "title": title,
        "best_entry": float(best["entry"]),
        "best_exit": float(best["exit"]),
        "best_cagr": float(best["cagr"] * 100.0),
    }

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>RSI Entry/Exit Interactive 3D Surface</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f6f7fb;
      --panel: #ffffff;
      --text: #1b1f24;
      --muted: #5d6674;
      --accent: #d92d20;
      --border: #dde3ea;
    }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: linear-gradient(180deg, #f8fafc 0%, #eef2f7 100%);
      color: var(--text);
    }}
    .wrap {{
      max-width: 1400px;
      margin: 0 auto;
      padding: 24px;
    }}
    .meta {{
      background: rgba(255, 255, 255, 0.92);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 16px 18px;
      box-shadow: 0 10px 28px rgba(31, 41, 55, 0.08);
      margin-bottom: 16px;
    }}
    .meta h1 {{
      margin: 0 0 8px 0;
      font-size: 22px;
      line-height: 1.25;
    }}
    .meta p {{
      margin: 4px 0;
      color: var(--muted);
    }}
    .best {{
      color: var(--accent);
      font-weight: 700;
    }}
    #plot {{
      width: 100%;
      height: 80vh;
      min-height: 720px;
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 16px;
      box-shadow: 0 14px 40px rgba(31, 41, 55, 0.1);
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="meta">
      <h1>RSI Entry/Exit Interactive 3D Surface</h1>
      <p>{payload["title"]}</p>
      <p class="best">Best CAGR: entry={payload["best_entry"]:.1f}, exit={payload["best_exit"]:.1f}, CAGR={payload["best_cagr"]:.2f}%</p>
      <p>Rotate with drag. Zoom with trackpad or scroll. Pan with right-drag.</p>
    </div>
    <div id="plot"></div>
  </div>
  <script>
    const payload = {json.dumps(payload, ensure_ascii=False)};
    const surface = {{
      type: 'surface',
      x: payload.x,
      y: payload.y,
      z: payload.z,
      colorscale: 'Viridis',
      colorbar: {{ title: 'CAGR (%)' }},
      hovertemplate: 'RSI Entry=%{{x:.1f}}<br>RSI Exit=%{{y:.1f}}<br>CAGR=%{{z:.2f}}%<extra></extra>'
    }};
    const bestPoint = {{
      type: 'scatter3d',
      mode: 'markers+text',
      x: [payload.best_entry],
      y: [payload.best_exit],
      z: [payload.best_cagr],
      marker: {{
        color: '#d92d20',
        size: 7,
        line: {{ color: '#ffffff', width: 2 }}
      }},
      text: ['Best'],
      textposition: 'top center',
      textfont: {{ color: '#d92d20', size: 12 }},
      hovertemplate: 'Best<br>RSI Entry=%{{x:.1f}}<br>RSI Exit=%{{y:.1f}}<br>CAGR=%{{z:.2f}}%<extra></extra>',
      showlegend: false
    }};
    const layout = {{
      title: {{
        text: payload.title,
        x: 0.03,
        xanchor: 'left'
      }},
      margin: {{ l: 0, r: 0, t: 60, b: 0 }},
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      scene: {{
        xaxis: {{ title: 'RSI Entry', backgroundcolor: '#f8fafc', gridcolor: '#d7dde6', zerolinecolor: '#d7dde6' }},
        yaxis: {{ title: 'RSI Exit', backgroundcolor: '#f8fafc', gridcolor: '#d7dde6', zerolinecolor: '#d7dde6' }},
        zaxis: {{ title: 'CAGR (%)', backgroundcolor: '#f8fafc', gridcolor: '#d7dde6', zerolinecolor: '#d7dde6' }},
        camera: {{
          eye: {{ x: 1.55, y: -1.8, z: 0.95 }}
        }}
      }}
    }};
    const config = {{
      responsive: true,
      displaylogo: false,
      toImageButtonOptions: {{
        format: 'png',
        filename: 'rsi_entry_exit_interactive_surface',
        scale: 2
      }}
    }};
    Plotly.newPlot('plot', [surface, bestPoint], layout, config);
  </script>
</body>
</html>
"""
    output_path.write_text(html, encoding="utf-8")


def save_2d_heatmap(frame: pd.DataFrame, title: str, output_path: Path) -> None:
    x, y, z = build_heatmap_matrix(frame)
    best = frame.loc[frame["cagr"].idxmax()]
    best_x = float(best["entry"])
    best_y = float(best["exit"])
    best_z = float(best["cagr"] * 100.0)
    finite_z = z.compressed()
    contour_floor = max(float(finite_z.min()), np.floor(max(best_z - 50.0, 0.0) / 10.0) * 10.0)
    contour_ceiling = np.floor(best_z / 10.0) * 10.0
    contour_levels = np.arange(contour_floor, contour_ceiling + 0.1, 10.0)
    highlighted_z = np.ma.masked_less(z, contour_floor)

    fig, ax = plt.subplots(figsize=(13, 9), constrained_layout=True)
    mesh = ax.pcolormesh(x, y, z, shading="nearest", cmap="viridis")
    contours = ax.contour(
        x,
        y,
        highlighted_z,
        levels=contour_levels,
        colors="#d92d20",
        linewidths=1.6,
        alpha=0.95,
    )
    contour_labels = ax.clabel(contours, inline=True, fontsize=9, fmt="%.0f%%", colors="#d92d20")
    for label in contour_labels:
        label.set_bbox(
            {
                "boxstyle": "round,pad=0.18",
                "fc": "white",
                "ec": "#d92d20",
                "alpha": 0.92,
            }
        )
    ax.scatter(
        [best_x],
        [best_y],
        color="red",
        s=130,
        edgecolors="white",
        linewidths=0.9,
        zorder=3,
    )
    ax.annotate(
        f"Best ({best_x:.1f}, {best_y:.1f})\nCAGR {best_z:.2f}%",
        xy=(best_x, best_y),
        xytext=(best_x + 1.1, best_y + 1.2),
        color="red",
        fontsize=10,
        arrowprops={"arrowstyle": "->", "color": "red", "lw": 1.5},
        bbox={"boxstyle": "round,pad=0.3", "fc": "white", "ec": "red", "alpha": 0.95},
    )
    ax.set_xlabel("RSI Entry")
    ax.set_ylabel("RSI Exit")
    ax.set_title(f"RSI Entry/Exit CAGR Heatmap\n{title}")
    ax.set_facecolor("#f4f4f4")
    colorbar = fig.colorbar(mesh, ax=ax)
    colorbar.set_label("CAGR (%)")
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    args = parse_args()
    frame = load_grid(args.input)
    label = derive_label(args.input, args.title)
    title = build_title(frame, label)
    output_dir = args.input.parent
    output_prefix = args.input.stem
    surface_path = output_dir / f"{output_prefix}_3d_surface.png"
    interactive_surface_path = output_dir / f"{output_prefix}_3d_surface_interactive.html"
    heatmap_path = output_dir / f"{output_prefix}_2d_heatmap.png"

    save_3d_surface(frame, title, surface_path)
    save_interactive_3d_surface_html(frame, title, interactive_surface_path)
    save_2d_heatmap(frame, title, heatmap_path)

    print(surface_path)
    print(interactive_surface_path)
    print(heatmap_path)


if __name__ == "__main__":
    main()
