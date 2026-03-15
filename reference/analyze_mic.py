#!/usr/bin/env python3
"""
Analysis script for MIC Test 03 - S. pneumoniae (Spectinomycin)
Reads OD600 and biomass CSVs from plate reader output, generates growth curves
and determines MIC values.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# ── Configuration ──────────────────────────────────────────────────────────────

BASE_DIR = Path("/mnt/bridgeslab/Chao/Raw Data/2026-03-06 MIC Test 03 S pneumo")

# Drawer directories (24h time-course data)
DRAWER_DIRS = {
    1: "260306_130019_4x_Discontinuous_IMB_37_Drawer1 06-Mar-2026 12-56-45",
    2: "260306_130727_4x_Discontinuous_IMB_37_Drawer2 06-Mar-2026 12-57-35",
    3: "260306_131432_4x_Discontinuous_IMB_37_Drawer3 06-Mar-2026 12-58-59",
    4: "260306_132141_4x_Discontinuous_IMB_37_Drawer4 06-Mar-2026 12-59-31",
}

# 72h endpoint directory
DIR_72H = "260309_113437_4x_Discontinuous_IMB_37_72h 09-Mar-2026"

# Plate subdirectories within each drawer
PLATE_SUBDIRS = {
    1: "260306_130019_Plate 1",
    2: "260306_130727_Plate 1",
    3: "260306_131432_Plate 1",
    4: "260306_132141_Plate 1",
}

# 72h plate subdirectories
PLATE_72H_SUBDIRS = {
    1: "260309_113437_Plate 1",
    2: "260309_114124_Plate 2",
    3: "260309_114720_Plate 3",
    4: "260309_115321_Plate 4",
}

# Strain assignments: plate -> {row_group: strain_name}
# Update these with actual strain names
STRAIN_MAP = {
    1: {"upper": "BS1", "lower": "BS2"},
    2: {"upper": "BS3", "lower": "BS4"},
    3: {"upper": "BS5", "lower": "BS6"},
    4: {"upper": "BS7", "lower": "BS8"},
}

UPPER_ROWS = ["A", "B", "C", "D"]
LOWER_ROWS = ["E", "F", "G", "H"]

# Column layout
# Columns 1-10: antibiotic concentrations (2-fold dilutions from Ax1)
# Column 11: media only (negative control)
# Column 12: bacteria only (positive control)
NUM_CONC_COLUMNS = 10
NEGATIVE_CTRL_COL = 11
POSITIVE_CTRL_COL = 12

# Time setup: 25 reads over 24h at 1h intervals
NUM_READS_24H = 25
TIME_HOURS = np.arange(NUM_READS_24H)  # 0, 1, 2, ..., 24

# Set this to the starting antibiotic concentration (µg/mL) if known
# e.g., AX1_CONC = 1000 means col1=1000, col2=500, col3=250, ...
AX1_CONC = None  # Set to actual value, e.g. 1000


# ── Helper functions ───────────────────────────────────────────────────────────

def parse_od600(csv_path):
    """Parse OD600 CSV. Columns are wells (A1,B1,...,H12), rows are timepoints."""
    df = pd.read_csv(csv_path)
    well_data = {}
    for col in df.columns:
        well_data[col.strip()] = df[col].values.astype(float)
    return well_data


def parse_biomass(csv_path):
    """Parse biomass CSV. Columns are 'Plate 1: A10' format, rows are timepoints."""
    df = pd.read_csv(csv_path)
    well_data = {}
    for col in df.columns:
        well_name = col.strip()
        if ": " in well_name:
            well_name = well_name.split(": ", 1)[1]
        well_data[well_name] = df[col].values.astype(float)
    return well_data


def get_well_name(row_letter, col_num):
    return f"{row_letter}{col_num}"


def extract_strain_data(well_data, rows):
    """
    Extract data for a strain (set of rows) organized by column.
    Returns dict: col_num -> array of shape (n_replicates, n_timepoints)
    """
    result = {}
    for col in range(1, 13):
        replicate_data = []
        for row in rows:
            well = get_well_name(row, col)
            if well in well_data:
                replicate_data.append(well_data[well])
        if replicate_data:
            result[col] = np.array(replicate_data)
    return result


def concentration_label(col_num, ax1_conc=None):
    if col_num == NEGATIVE_CTRL_COL:
        return "Media ctrl"
    elif col_num == POSITIVE_CTRL_COL:
        return "Growth ctrl"
    else:
        if ax1_conc is not None:
            conc = ax1_conc / (2 ** (col_num - 1))
            if conc >= 1:
                return f"{conc:g} µg/mL"
            else:
                return f"{conc:.2g} µg/mL"
        else:
            if col_num == 1:
                return "Ax1"
            else:
                fold = 2 ** (col_num - 1)
                return f"Ax1/{fold}"


# ── Data loading ───────────────────────────────────────────────────────────────

def load_all_data():
    """Load all 24h time-course and 72h endpoint data."""
    data = {}

    for plate_num in range(1, 5):
        drawer_dir = BASE_DIR / DRAWER_DIRS[plate_num]
        plate_subdir = PLATE_SUBDIRS[plate_num]

        # Biomass (available for all plates)
        biomass_path = drawer_dir / plate_subdir / "Numerical data" / "4x_BF_biomass.csv"
        biomass_data = parse_biomass(biomass_path) if biomass_path.exists() else None

        # OD600 (not available for Drawer 1)
        od_path = drawer_dir / plate_subdir / "OD600.csv"
        od_data = parse_od600(od_path) if od_path.exists() else None

        # 72h endpoint
        dir_72h = BASE_DIR / DIR_72H / PLATE_72H_SUBDIRS[plate_num]
        biomass_72h_path = dir_72h / "Numerical data" / "4x_BF_biomass.csv"
        od_72h_path = dir_72h / "OD600.csv"
        biomass_72h = parse_biomass(biomass_72h_path) if biomass_72h_path.exists() else None
        od_72h = parse_od600(od_72h_path) if od_72h_path.exists() else None

        for group, rows in [("upper", UPPER_ROWS), ("lower", LOWER_ROWS)]:
            strain = STRAIN_MAP[plate_num][group]
            strain_entry = {"plate": plate_num, "rows": rows}

            if od_data:
                strain_entry["od_24h"] = extract_strain_data(od_data, rows)
            if biomass_data:
                strain_entry["biomass_24h"] = extract_strain_data(biomass_data, rows)
            if od_72h:
                strain_entry["od_72h"] = extract_strain_data(od_72h, rows)
            if biomass_72h:
                strain_entry["biomass_72h"] = extract_strain_data(biomass_72h, rows)

            data[strain] = strain_entry

    return data


# ── Plotting ───────────────────────────────────────────────────────────────────

CONC_COLORS = [
    "#e6194b", "#f58231", "#ffe119", "#bfef45", "#3cb44b",
    "#42d4f4", "#4363d8", "#911eb4", "#f032e6", "#a9a9a9",
]


def plot_growth_curves(data, measurement="od_24h", title_suffix="OD600",
                       ylabel="OD$_{600}$", ax1_conc=None, figsize=(20, 12)):
    """Plot growth curves for all strains."""
    strains = sorted(data.keys())
    strains_with_data = [s for s in strains if measurement in data[s]]

    if not strains_with_data:
        print(f"  No {measurement} data available for any strain.")
        return None

    n_strains = len(strains_with_data)
    ncols = min(4, n_strains)
    nrows = (n_strains + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=figsize, squeeze=False)

    for idx, strain in enumerate(strains_with_data):
        ax = axes[idx // ncols][idx % ncols]
        strain_data = data[strain][measurement]

        for col in range(1, 13):
            if col not in strain_data:
                continue
            replicates = strain_data[col]
            mean = replicates.mean(axis=0)
            std = replicates.std(axis=0)

            label = concentration_label(col, ax1_conc)
            if col == NEGATIVE_CTRL_COL:
                color, marker, ls = "gray", "s", "--"
            elif col == POSITIVE_CTRL_COL:
                color, marker, ls = "black", "o", "-"
            else:
                color, marker, ls = CONC_COLORS[col - 1], "o", "-"

            ax.errorbar(TIME_HOURS[:len(mean)], mean, yerr=std,
                        color=color, marker=marker, markersize=3,
                        linewidth=1.2, linestyle=ls, label=label,
                        capsize=2, capthick=0.8, elinewidth=0.8)

        ax.set_title(strain, fontsize=12, fontweight="bold")
        ax.set_xlabel("Time from Inoculation (h)")
        ax.set_ylabel(ylabel)
        ax.set_xlim(-0.5, 24.5)
        if "od" in measurement:
            ax.set_ylim(0, None)

    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="center right", fontsize=8,
               title="[Spectinomycin]", title_fontsize=9,
               bbox_to_anchor=(1.0, 0.5))

    for idx in range(n_strains, nrows * ncols):
        axes[idx // ncols][idx % ncols].set_visible(False)

    fig.suptitle(f"S. pneumoniae MIC - {title_suffix} (24h Time Course)",
                 fontsize=14, fontweight="bold", y=1.01)
    fig.tight_layout()
    return fig


def plot_endpoint_comparison(data, timepoint="72h", measurement_type="od",
                             ax1_conc=None, figsize=(16, 8)):
    """Plot endpoint OD or biomass as bar charts for all strains."""
    key = f"{measurement_type}_{timepoint}"
    strains = sorted([s for s in data if key in data[s]])

    if not strains:
        print(f"  No {key} data available.")
        return None

    n_strains = len(strains)
    ncols = min(4, n_strains)
    nrows = (n_strains + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=figsize, squeeze=False)

    for idx, strain in enumerate(strains):
        ax = axes[idx // ncols][idx % ncols]
        strain_data = data[strain][key]

        cols = sorted(strain_data.keys())
        means, stds, xlabels, colors = [], [], [], []

        for col in cols:
            vals = strain_data[col].flatten()
            means.append(vals.mean())
            stds.append(vals.std())
            xlabels.append(concentration_label(col, ax1_conc))
            if col == NEGATIVE_CTRL_COL:
                colors.append("lightgray")
            elif col == POSITIVE_CTRL_COL:
                colors.append("black")
            else:
                colors.append(CONC_COLORS[col - 1])

        x = np.arange(len(cols))
        ax.bar(x, means, yerr=stds, color=colors, edgecolor="black",
               linewidth=0.5, capsize=3)
        ax.set_xticks(x)
        ax.set_xticklabels(xlabels, rotation=45, ha="right", fontsize=7)
        ax.set_title(strain, fontsize=11, fontweight="bold")
        ylabel = "OD$_{600}$" if measurement_type == "od" else "Biomass (a.u.)"
        ax.set_ylabel(ylabel)

    for idx in range(n_strains, nrows * ncols):
        axes[idx // ncols][idx % ncols].set_visible(False)

    title_meas = "OD600" if measurement_type == "od" else "Biomass"
    fig.suptitle(f"S. pneumoniae MIC - {title_meas} at {timepoint}",
                 fontsize=14, fontweight="bold")
    fig.tight_layout()
    return fig


# ── MIC Determination ─────────────────────────────────────────────────────────

def determine_mic(data, measurement_key, ax1_conc=None, threshold_factor=0.1):
    """
    Determine MIC for each strain.
    MIC = lowest concentration where final OD/biomass is below
    (negative_ctrl + threshold_factor * (positive_ctrl - negative_ctrl))
    """
    results = []

    for strain in sorted(data.keys()):
        if measurement_key not in data[strain]:
            continue

        strain_data = data[strain][measurement_key]

        if POSITIVE_CTRL_COL not in strain_data:
            continue
        pos_vals = strain_data[POSITIVE_CTRL_COL]
        pos_mean = pos_vals[:, -1].mean() if pos_vals.ndim > 1 and pos_vals.shape[1] > 1 else pos_vals.flatten().mean()

        neg_vals = strain_data.get(NEGATIVE_CTRL_COL)
        if neg_vals is not None:
            neg_mean = neg_vals[:, -1].mean() if neg_vals.ndim > 1 and neg_vals.shape[1] > 1 else neg_vals.flatten().mean()
        else:
            neg_mean = 0

        threshold = neg_mean + threshold_factor * (pos_mean - neg_mean)

        mic_col = None
        for col in range(NUM_CONC_COLUMNS, 0, -1):
            if col not in strain_data:
                continue
            vals = strain_data[col]
            final_mean = vals[:, -1].mean() if vals.ndim > 1 and vals.shape[1] > 1 else vals.flatten().mean()
            if final_mean < threshold:
                mic_col = col
            else:
                break

        mic_conc = ax1_conc / (2 ** (mic_col - 1)) if (ax1_conc and mic_col) else None

        results.append({
            "Strain": strain,
            "MIC_column": mic_col if mic_col else ">col10 (below lowest conc)",
            "MIC_conc_ugmL": f"{mic_conc:g}" if mic_conc else "N/A",
            "Pos_ctrl_mean": round(pos_mean, 4),
            "Neg_ctrl_mean": round(neg_mean, 4),
            "Threshold_10pct": round(threshold, 4),
        })

    return pd.DataFrame(results)


# ── Summary table ──────────────────────────────────────────────────────────────

def endpoint_summary_table(data, measurement_key, ax1_conc=None):
    """Summary table of mean ± SD at final timepoint for each strain x concentration."""
    rows = []
    for strain in sorted(data.keys()):
        if measurement_key not in data[strain]:
            continue
        strain_data = data[strain][measurement_key]
        for col in range(1, 13):
            if col not in strain_data:
                continue
            vals = strain_data[col]
            final_vals = vals[:, -1] if vals.ndim > 1 and vals.shape[1] > 1 else vals.flatten()
            rows.append({
                "Strain": strain,
                "Column": col,
                "Condition": concentration_label(col, ax1_conc),
                "Mean": round(final_vals.mean(), 4),
                "SD": round(final_vals.std(), 4),
                "N": len(final_vals),
            })
    return pd.DataFrame(rows)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("Loading data...")
    data = load_all_data()
    print(f"Loaded data for {len(data)} strains: {sorted(data.keys())}")

    for strain in sorted(data.keys()):
        available = [k for k in data[strain] if k not in ("plate", "rows")]
        print(f"  {strain} (Plate {data[strain]['plate']}, rows {data[strain]['rows']}): {', '.join(available)}")

    output_dir = Path("/home/smellick/mic_analysis_output")
    output_dir.mkdir(exist_ok=True)

    # ── 24h Growth Curves ──
    print("\nPlotting 24h OD600 growth curves...")
    fig_od = plot_growth_curves(data, measurement="od_24h",
                                title_suffix="OD600", ylabel="OD$_{600}$",
                                ax1_conc=AX1_CONC)
    if fig_od:
        fig_od.savefig(output_dir / "growth_curves_OD600_24h.png",
                       dpi=200, bbox_inches="tight")
        print(f"  Saved: growth_curves_OD600_24h.png")
        plt.close(fig_od)

    print("Plotting 24h biomass growth curves...")
    fig_bm = plot_growth_curves(data, measurement="biomass_24h",
                                title_suffix="Biomass (BF)",
                                ylabel="Biomass (a.u.)",
                                ax1_conc=AX1_CONC)
    if fig_bm:
        fig_bm.savefig(output_dir / "growth_curves_biomass_24h.png",
                       dpi=200, bbox_inches="tight")
        print(f"  Saved: growth_curves_biomass_24h.png")
        plt.close(fig_bm)

    # ── 72h Endpoint Bar Charts ──
    print("\nPlotting 72h endpoint data...")
    fig_72_od = plot_endpoint_comparison(data, timepoint="72h",
                                         measurement_type="od",
                                         ax1_conc=AX1_CONC)
    if fig_72_od:
        fig_72_od.savefig(output_dir / "endpoint_OD600_72h.png",
                          dpi=200, bbox_inches="tight")
        print(f"  Saved: endpoint_OD600_72h.png")
        plt.close(fig_72_od)

    fig_72_bm = plot_endpoint_comparison(data, timepoint="72h",
                                          measurement_type="biomass",
                                          ax1_conc=AX1_CONC)
    if fig_72_bm:
        fig_72_bm.savefig(output_dir / "endpoint_biomass_72h.png",
                          dpi=200, bbox_inches="tight")
        print(f"  Saved: endpoint_biomass_72h.png")
        plt.close(fig_72_bm)

    # ── MIC Determination ──
    print("\n" + "="*60)
    print("MIC DETERMINATION (10% growth threshold)")
    print("="*60)
    for key, label in [("od_24h", "OD600 @ 24h"), ("biomass_24h", "Biomass @ 24h"),
                       ("od_72h", "OD600 @ 72h"), ("biomass_72h", "Biomass @ 72h")]:
        mic_df = determine_mic(data, key, ax1_conc=AX1_CONC)
        if not mic_df.empty:
            print(f"\n{label}:")
            print(mic_df.to_string(index=False))
            mic_df.to_csv(output_dir / f"MIC_{key}.csv", index=False)

    # ── Summary Tables ──
    print("\n\nGenerating summary tables...")
    for key, label in [("od_24h", "OD600_24h_endpoint"),
                       ("biomass_24h", "Biomass_24h_endpoint"),
                       ("od_72h", "OD600_72h"), ("biomass_72h", "Biomass_72h")]:
        summary = endpoint_summary_table(data, key, ax1_conc=AX1_CONC)
        if not summary.empty:
            outpath = output_dir / f"summary_{label}.csv"
            summary.to_csv(outpath, index=False)
            print(f"  Saved: {outpath.name}")

    print(f"\nAll outputs saved to: {output_dir}")
    if AX1_CONC is None:
        print("\nNOTE: AX1_CONC not set - showing column numbers instead of µg/mL.")
        print("      Edit the AX1_CONC variable at the top of the script.")
    print("NOTE: Strain names are placeholders (BS1-BS8). Update STRAIN_MAP as needed.")


if __name__ == "__main__":
    main()
