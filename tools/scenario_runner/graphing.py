"""Graph rendering helpers for scenario outputs."""

from __future__ import annotations

from pathlib import Path


def render_rows_svg(*, rows: list[dict[str, object]], path: Path, title: str) -> None:
    """Render a simple SVG line chart for grid/load/solar series."""
    if not rows:
        path.write_text("<svg xmlns='http://www.w3.org/2000/svg' width='800' height='240'></svg>\n")
        return

    width = 1000
    height = 320
    margin = 40
    plot_w = width - 2 * margin
    plot_h = height - 2 * margin

    def values(key: str) -> list[float]:
        return [float(row.get(key, 0.0)) for row in rows]

    grid_vals = values("grid")
    load_vals = values("load")
    solar_vals = values("solar")
    all_vals = grid_vals + load_vals + solar_vals
    min_v = min(all_vals)
    max_v = max(all_vals)
    value_span = (max_v - min_v) if max_v != min_v else 1.0

    def point(idx: int, val: float) -> tuple[float, float]:
        x = margin + (idx / max(len(rows) - 1, 1)) * plot_w
        y = margin + (1.0 - ((val - min_v) / value_span)) * plot_h
        return x, y

    def polyline(key: str, color: str) -> str:
        pts = " ".join(f"{x:.2f},{y:.2f}" for x, y in (point(i, v) for i, v in enumerate(values(key))))
        return f"<polyline fill='none' stroke='{color}' stroke-width='2' points='{pts}' />"

    svg = "\n".join(
        [
            f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}'>",
            f"<rect x='0' y='0' width='{width}' height='{height}' fill='white' />",
            f"<text x='{margin}' y='24' font-size='16' font-family='Arial'>{title}</text>",
            f"<line x1='{margin}' y1='{margin}' x2='{margin}' y2='{height - margin}' stroke='#888' />",
            f"<line x1='{margin}' y1='{height - margin}' x2='{width - margin}' y2='{height - margin}' stroke='#888' />",
            polyline("grid", "#1f77b4"),
            polyline("load", "#ff7f0e"),
            polyline("solar", "#2ca02c"),
            f"<text x='{width - 260}' y='{margin}' font-size='12'>blue=grid orange=load green=solar</text>",
            "</svg>",
            "",
        ]
    )
    path.write_text(svg)
