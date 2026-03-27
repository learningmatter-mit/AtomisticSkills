import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.graph_objects as go

def create_refinement_plot(data_dir, output_path=None, diff_offset=False):
    data_dir = Path(data_dir)
    stem = data_dir.name # e.g. "digitized_plot"
    
    curve_csv = data_dir / f"{stem}_curve_data.csv"
    peak_csv = data_dir / f"{stem}_peak_data.csv"
    json_path = data_dir / "refinement_result.json"
    
    if not curve_csv.exists() or not json_path.exists():
        # Fallback to single file lookup if directory mapping is non-standard
        curve_csvs = list(data_dir.glob("*_curve_data.csv"))
        if curve_csvs:
            curve_csv = curve_csvs[0]
            stem = curve_csv.stem.replace("_curve_data", "")
            peak_csv = data_dir / f"{stem}_peak_data.csv"
        else:
            raise FileNotFoundError(f"Could not find curve data in {data_dir}. You MUST run refine.py first to export this.")

    curve_data = pd.read_csv(curve_csv)
    
    with open(json_path, "r") as f:
        res_json = json.load(f)
        
    peak_data = None
    if peak_csv.exists():
        peak_data = pd.read_csv(peak_csv)

    rwp = res_json.get("rwp", 0.0)
    phases = res_json.get("phases", [])
    
    weight_fractions = {}
    total_w = sum(p.get("gewicht", [0])[0] if isinstance(p.get("gewicht"), list) else (p.get("gewicht", 0) or 0) for p in phases)
    for p in phases:
        w = p.get("gewicht", [0])[0] if isinstance(p.get("gewicht"), list) else (p.get("gewicht", 0) or 0)
        weight_fractions[p["name"]] = w / total_w if total_w > 0 else 0

    colormap = [
        "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
        "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf"
    ]

    fig = go.Figure()

    # Observed
    fig.add_trace(go.Scatter(
        x=curve_data["x"], y=curve_data["y_obs"],
        mode="markers", marker=dict(color="blue", size=3, symbol="cross-thin-open"),
        name="Observed"
    ))

    # Calculated
    fig.add_trace(go.Scatter(
        x=curve_data["x"], y=curve_data["y_calc"],
        mode="lines", line=dict(color="green", width=2),
        name="Calculated"
    ))

    # Background
    fig.add_trace(go.Scatter(
        x=curve_data["x"], y=curve_data["y_bkg"],
        mode="lines", line=dict(color="#FF7F7F", width=2),
        name="Background", opacity=0.5
    ))

    # Difference
    diff = curve_data["y_obs"] - curve_data["y_calc"]
    diff_offset_val = 1.1 * diff.max() if diff_offset else 0
    fig.add_trace(go.Scatter(
        x=curve_data["x"], y=diff - diff_offset_val,
        mode="lines", line=dict(color="#808080", width=1),
        name="Difference", opacity=0.7, hoverinfo="skip"
    ))

    max_y = (curve_data["y_obs"] + curve_data["y_bkg"]).max()
    min_y_diff = diff.min()

    # Individual Phases
    struct_cols = [c for c in curve_data.columns if c.startswith("struct_")]
    for i, col in enumerate(struct_cols):
        phase_name = col.replace("struct_", "")
        color_idx = i % len(colormap)
        
        name = f"{phase_name} ({weight_fractions.get(phase_name, 0)*100:.2f} %)" if len(struct_cols) > 1 else phase_name
        
        # Transparent baseline for phase area filling
        fig.add_trace(go.Scatter(
            x=curve_data["x"], y=curve_data["y_bkg"],
            mode="lines", line=dict(color=colormap[color_idx], width=0),
            fill=None, showlegend=False, hoverinfo="skip", legendgroup=phase_name
        ))
        
        # Phase area filled
        fig.add_trace(go.Scatter(
            x=curve_data["x"], y=curve_data[col] + curve_data["y_bkg"],
            mode="lines", line=dict(color=colormap[color_idx], width=1.5),
            fill="tonexty", name=name, visible="legendonly", legendgroup=phase_name
        ))
        
        if peak_data is not None:
            phase_peaks = peak_data[peak_data["phase"] == phase_name]
            if not phase_peaks.empty:
                refl = phase_peaks["2theta"]
                intensity = phase_peaks["intensity"]
                fig.add_trace(go.Scatter(
                    x=refl, y=np.ones(len(refl)) * (i + 1) * -max_y * 0.1 + min_y_diff,
                    mode="markers", marker=dict(symbol=142, size=5, color=colormap[color_idx]),
                    name=name, legendgroup=phase_name, showlegend=False, visible="legendonly",
                    text=[f"{x:.2f}, {y:.2f}" for x, y in zip(refl, intensity)], hovertemplate="%{text}"
                ))

    # -------------------------------------------------------------------------
    # Apply Standard Formatting (plot-standards.md)
    # The user can edit these values below independently of the heavy DARA search
    # -------------------------------------------------------------------------
    title = f"{stem} (Rwp={rwp:.2f}%)"
    fig.update_layout(
        title=title,
        width=600,
        height=400,
        font=dict(size=14, color="black", family="Arial, sans-serif"),
        legend=dict(
            x=0.99, y=0.99, xanchor="right", yanchor="top",
            bgcolor="rgba(255, 255, 255, 0.8)",
            bordercolor="black", borderwidth=1,
            tracegroupgap=1
        ),
        margin=dict(l=60, r=20, t=40, b=60),
        xaxis=dict(
            range=[curve_data["x"].min(), curve_data["x"].max()],
            showline=True, linewidth=1, linecolor="black", mirror=True,
            ticks="outside", tickwidth=1, tickcolor="black", ticklen=10
        ),
        yaxis=dict(
            showline=True, linewidth=1, linecolor="black", mirror=True,
            ticks="outside", tickwidth=1, tickcolor="black", ticklen=10
        ),
        plot_bgcolor="white"
    )

    fig.update_xaxes(title_text="<b>2θ [°]</b>", title_font=dict(size=14, color="black"))
    fig.update_yaxes(title_text="<b>Intensity</b>", title_font=dict(size=14, color="black"))
    fig.add_hline(y=0, line_width=1)

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        html_out = out.with_suffix(".html")
        png_out = out.with_suffix(".png")
        svg_out = out.with_suffix(".svg")
        
        fig.write_html(str(html_out))
        try:
            fig.write_image(str(png_out), scale=2)
            fig.write_image(str(svg_out))
            print(f"Saved plots to {out.parent}")
        except Exception as e:
            print(f"Warning: Could not save image, ensure kaleido is installed. {e}")
    
    return fig

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Standalone plotter for XRD refinement results.")
    parser.add_argument("--data_dir", type=str, required=True, help="Directory containing refinement_result.json and *_curve_data.csv")
    parser.add_argument("--output", type=str, required=True, help="Path for the output plot files (without extension)")
    parser.add_argument("--diff_offset", action="store_true", help="Offset the difference curve")
    
    args = parser.parse_args()
    create_refinement_plot(args.data_dir, args.output, args.diff_offset)
