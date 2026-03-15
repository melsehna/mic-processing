import re
import pandas as pd
import numpy as np


def parseBiomassCsv(csvPath):
    df = pd.read_csv(csvPath)
    wellData = {}
    for col in df.columns:
        name = col.strip()
        if ": " in name:
            name = name.split(": ", 1)[1].strip()
        if not re.match(r"^[A-H]\d{1,2}$", name):
            continue
        vals = pd.to_numeric(df[col], errors="coerce").values
        wellData[name] = vals[~np.isnan(vals)] if np.any(np.isnan(vals)) else vals
    return wellData


def parseOdCsv(csvPath):
    with open(csvPath, "r", encoding="latin1", errors="ignore") as f:
        lines = f.readlines()

    startRow = None
    for i, line in enumerate(lines):
        if line.startswith("Time") and "A1" in line:
            startRow = i
            break

    if startRow is not None:
        df = pd.read_csv(
            csvPath, skiprows=startRow, encoding="latin1",
            engine="python", sep=None, on_bad_lines="skip"
        )
        df = df.loc[:, ~df.columns.astype(str).str.contains("^Unnamed")]
        df = df.drop(columns=[c for c in df.columns if "600" in str(c)], errors="ignore")
        if "A1" in df.columns:
            df["_chk"] = pd.to_numeric(df["A1"], errors="coerce")
            df = df[df["_chk"].notna()].drop(columns=["_chk"])
    else:
        df = pd.read_csv(csvPath)

    wellData = {}
    for col in df.columns:
        name = col.strip()
        if not re.match(r"^[A-H]\d{1,2}$", name):
            continue
        vals = pd.to_numeric(df[col], errors="coerce").values
        wellData[name] = vals[~np.isnan(vals)] if np.any(np.isnan(vals)) else vals
    return wellData


def parseOdResults(csvPath):
    with open(csvPath, "r", encoding="latin1", errors="ignore") as f:
        lines = f.readlines()

    rowLetters = list("ABCDEFGH")
    maxV, lag = {}, {}
    curRow = None

    for line in lines:
        parts = re.split(r"[,\t]", line.strip())
        if len(parts) < 2:
            continue
        if parts[0].strip() in rowLetters:
            curRow = parts[0].strip()
        if curRow is None:
            continue
        if parts[-1].strip() == "Max V [Read 2:600]":
            maxV[curRow] = [pd.to_numeric(v, errors="coerce") for v in parts[1:13]]
        if parts[-1].strip() == "Lagtime [Read 2:600]":
            lag[curRow] = [pd.to_numeric(v, errors="coerce") for v in parts[1:13]]

    return (maxV or None, lag or None)
