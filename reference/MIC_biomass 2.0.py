import pandas as pd
from pathlib import Path

# --------------------------------
# Folder containing the CSV files
# --------------------------------
data_folder = Path("/Users/chaoliadmin/Desktop/MIC_biomass")

# --------------------------------
# Plate identifiers
# --------------------------------
plate_ids = ["P1", "P2", "P3", "P4"]

# --------------------------------
# Time points (0-24h always, 48h and 72h optional)
# --------------------------------
time_points = ["0-24h", "48h", "72h"]

# --------------------------------
# Rows and columns
# --------------------------------
rows = list("ABCDEFGH")
cols = range(1, 13)

desired_order = [f"Plate 1: {row}{col}" for col in cols for row in rows]

# Row groups for sub-plates
group_1_rows = set("ABCD")
group_2_rows = set("EFGH")

# Output Excel file
output_file = data_folder / "MIC_biomass_Prism.xlsx"

# --------------------------------
# Helper functions
# --------------------------------
def columnize(df, old_label, new_label, suffix):
    out = {}
    for col in range(1, 13):
        wells = [
            f"{old_label}: {r}{col}"
            for r in rows
            if f"{old_label}: {r}{col}" in df.columns
        ]
        if wells:
            out[f"{new_label}: Col{col}_{suffix}"] = df[wells].values.flatten()
    return pd.DataFrame(out)


def combine_max_end(df_max, df_end):
    combined = []
    for col in df_max.columns:
        base = col.replace("_Max", "")
        combined.append(df_max[col])
        combined.append(df_end[f"{base}_End"])
    return pd.concat(combined, axis=1)

# --------------------------------
# Collect available CSV files
# --------------------------------
available_files = {}
for tp in time_points:
    for pid in plate_ids:
        file_name = f"4x_BF_biomass_{tp}_{pid}.csv"
        file_path = data_folder / file_name
        if file_path.exists():
            available_files.setdefault(pid, []).append((tp, file_path))

# --------------------------------
# Process plates and write Excel
# --------------------------------
with pd.ExcelWriter(output_file, engine="xlsxwriter") as writer:
    sheets = {}

    for pid in plate_ids:
        # Collect all available time points for this plate
        dfs = []
        time_vector = []
        for tp, path in sorted(available_files.get(pid, []), key=lambda x: x[0]):
            df = pd.read_csv(path)
            dfs.append(df)
            # Generate time column for this block
            if tp == "0-24h":
                time_vector.extend(list(range(df.shape[0])))
            elif tp == "48h":
                time_vector.extend([48] * df.shape[0])
            elif tp == "72h":
                time_vector.extend([72] * df.shape[0])

        if not dfs:
            continue

        # Concatenate vertically
        df_full = pd.concat(dfs, ignore_index=True)

        # Reorder columns
        existing_columns = [c for c in desired_order if c in df_full.columns]
        df_full = df_full[existing_columns]

        # Split sub-plates
        df_1 = df_full[[c for c in df_full.columns if c.split(":")[1].strip()[0] in group_1_rows]]
        df_2 = df_full[[c for c in df_full.columns if c.split(":")[1].strip()[0] in group_2_rows]]

        # Add Time column
        df_1.insert(0, "Time", time_vector)
        df_2.insert(0, "Time", time_vector)

        sheet_1 = f"{pid}-1"
        sheet_2 = f"{pid}-2"

        # Rename raw well columns
        df_1.columns = ["Time"] + [c.replace("Plate 1", sheet_1) for c in df_1.columns[1:]]
        df_2.columns = ["Time"] + [c.replace("Plate 1", sheet_2) for c in df_2.columns[1:]]

        sheets[sheet_1] = df_1
        sheets[sheet_2] = df_2

        # ---- Max and End (raw) ----
        max_1 = df_1.drop(columns="Time").max().to_frame().T
        max_2 = df_2.drop(columns="Time").max().to_frame().T
        end_1 = df_1.drop(columns="Time").iloc[[-1]]
        end_2 = df_2.drop(columns="Time").iloc[[-1]]

        # ---- Columnized ----
        max_1_c = columnize(max_1, sheet_1, sheet_1, "Max")
        end_1_c = columnize(end_1, sheet_1, sheet_1, "End")
        max_2_c = columnize(max_2, sheet_2, sheet_2, "Max")
        end_2_c = columnize(end_2, sheet_2, sheet_2, "End")

        sheets[f"{sheet_1}-Max"] = max_1_c
        sheets[f"{sheet_1}-End"] = end_1_c
        sheets[f"{sheet_2}-Max"] = max_2_c
        sheets[f"{sheet_2}-End"] = end_2_c

        # ---- Combined Max + End ----
        sheets[f"{sheet_1}-Max+End"] = combine_max_end(max_1_c, end_1_c)
        sheets[f"{sheet_2}-Max+End"] = combine_max_end(max_2_c, end_2_c)

    # --------------------------------
    # Final sheet order
    # --------------------------------
    ordered_sheets = []

    for p in plate_ids:
        ordered_sheets += [f"{p}-1", f"{p}-2"]

    for p in plate_ids:
        ordered_sheets += [f"{p}-1-Max+End", f"{p}-2-Max+End"]

    for p in plate_ids:
        ordered_sheets += [f"{p}-1-Max", f"{p}-2-Max"]

    for p in plate_ids:
        ordered_sheets += [f"{p}-1-End", f"{p}-2-End"]

    # Write in order
    for name in ordered_sheets:
        if name in sheets:
            sheets[name].to_excel(writer, sheet_name=name, index=False)

print(f"Reorganized plates with Max/End saved to: {output_file}")