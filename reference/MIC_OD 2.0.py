import pandas as pd
import os
import glob
import re

# ================================
# USER INPUT
# ================================
folder_path = r"/Users/chaoliadmin/Desktop/MIC_OD"

# ================================
# SAFE CSV READER
# ================================
def safe_read_csv(file, skiprows=None):
    df = pd.read_csv(
        file,
        skiprows=skiprows,
        encoding="latin1",
        engine="python",
        sep=None,
        on_bad_lines="skip"
    )
    df = df.loc[:, ~df.columns.astype(str).str.contains("^Unnamed")]
    return df

# ================================
# DETECT OD TABLE
# ================================
def detect_od_table(file):
    with open(file, "r", encoding="latin1", errors="ignore") as f:
        lines = f.readlines()

    start = None
    for i, line in enumerate(lines):
        if line.startswith("Time") and "A1" in line:
            start = i
            break

    if start is None:
        raise Exception(f"OD table not found in {file}")

    df = safe_read_csv(file, skiprows=start)
    drop_cols = [c for c in df.columns if "600" in str(c)]
    df = df.drop(columns=drop_cols, errors="ignore")
    df["A1_numeric"] = pd.to_numeric(df["A1"], errors="coerce")
    df = df[df["A1_numeric"].notna()]
    df = df.drop(columns=["A1_numeric"])
    return df

# ================================
# SPLIT OD SUBPLATES
# ================================
def split_subplates_od(df):
    sub1_cols = ["Time"]
    sub2_cols = ["Time"]
    for col in range(1, 13):
        sub1_cols += [f"A{col}", f"B{col}", f"C{col}", f"D{col}"]
        sub2_cols += [f"E{col}", f"F{col}", f"G{col}", f"H{col}"]
    sub1 = df[sub1_cols]
    sub2 = df[sub2_cols]
    return sub1, sub2

# ================================
# DETECT RESULTS TABLE (ROBUST)
# ================================
def detect_results_table(file):
    with open(file, "r", encoding="latin1", errors="ignore") as f:
        lines = f.readlines()

    rows = list("ABCDEFGH")
    maxV = {}
    lag = {}
    current_row = None

    for line in lines:
        parts = re.split(r"[,\t]", line.strip())
        if len(parts) < 2:
            continue
        if parts[0].strip() in rows:
            current_row = parts[0].strip()
        if current_row is None:
            continue
        if len(parts) > 1 and parts[-1].strip() == "Max V [Read 2:600]":
            maxV[current_row] = parts[1:13]
        if len(parts) > 1 and parts[-1].strip() == "Lagtime [Read 2:600]":
            lag[current_row] = parts[1:13]

    if maxV:
        maxV_df = pd.DataFrame.from_dict(maxV, orient="index")
        maxV_df.columns = [str(i) for i in range(1, 13)]
    else:
        maxV_df = pd.DataFrame(columns=[str(i) for i in range(1, 13)])

    if lag:
        lag_df = pd.DataFrame.from_dict(lag, orient="index")
        lag_df.columns = [str(i) for i in range(1, 13)]
    else:
        lag_df = pd.DataFrame(columns=[str(i) for i in range(1, 13)])

    return maxV_df, lag_df

# ================================
# SPLIT RESULTS SUBPLATES
# ================================
def split_subplates_results(df):
    sub1 = df.loc[df.index.intersection(["A", "B", "C", "D"])]
    sub2 = df.loc[df.index.intersection(["E", "F", "G", "H"])]
    return sub1, sub2

# ================================
# FIND CSV FILES
# ================================
csv_files = glob.glob(os.path.join(folder_path, "*.csv"))
plates = {1: [], 2: [], 3: [], 4: []}
for file in csv_files:
    name = os.path.basename(file)
    for p in range(1, 5):
        if f"_P{p}" in name:
            plates[p].append(file)

# ================================
# PROCESS OD TABLES
# ================================
print("\nProcessing OD tables...")
od_output = os.path.join(folder_path, "MIC_OD_Prism.xlsx")  # UPDATED FILE NAME
with pd.ExcelWriter(od_output, engine="xlsxwriter") as od_writer:
    for plate in plates:
        dfs = []
        for file in sorted(plates[plate]):
            df = detect_od_table(file)
            name = os.path.basename(file)
            if "0-24h" in name:
                df = df.iloc[:25].copy()
                df["Time"] = list(range(25))
            elif "48h" in name:
                df = df.iloc[:1].copy()
                df["Time"] = [48]
            elif "72h" in name:
                df = df.iloc[:1].copy()
                df["Time"] = [72]
            dfs.append(df)
        if not dfs:
            continue
        combined = pd.concat(dfs, ignore_index=True)
        sub1, sub2 = split_subplates_od(combined)
        sub1.to_excel(od_writer, sheet_name=f"P{plate}-1", index=False)
        sub2.to_excel(od_writer, sheet_name=f"P{plate}-2", index=False)
        print(f"Plate P{plate} OD exported")

print("\nMIC_OD_Prism.xlsx generated successfully.")

# ================================
# PROCESS RESULTS TABLES (0-24h ONLY, TRANSPOSED)
# ================================
print("\nProcessing Results tables (0-24h only, transposed)...")
results_output = os.path.join(folder_path, "MIC_OD_Results_Prism.xlsx")
with pd.ExcelWriter(results_output, engine="xlsxwriter") as writer:
    for plate in plates:
        for file in plates[plate]:
            name = os.path.basename(file)
            if "0-24h" not in name:
                continue
            maxV, lag = detect_results_table(file)
            max1, max2 = split_subplates_results(maxV)
            lag1, lag2 = split_subplates_results(lag)
            # TRANSPOSE before saving
            max1.T.to_excel(writer, sheet_name=f"P{plate}-1_MaxV")
            max2.T.to_excel(writer, sheet_name=f"P{plate}-2_MaxV")
            lag1.T.to_excel(writer, sheet_name=f"P{plate}-1_Lag")
            lag2.T.to_excel(writer, sheet_name=f"P{plate}-2_Lag")
            print(f"Plate P{plate} Results exported from {name} (transposed)")

print("\nMIC_OD_Results_Prism.xlsx generated successfully (transposed).")