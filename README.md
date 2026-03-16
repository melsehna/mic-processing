# Bulk Cytation5 MIC Analysis

## Overview

`micprocessing` parses OD600 and biomass CSV files exported from BioTek Cytation plate readers, maps wells to strains using a Plate ID spreadsheet, and determines MIC values across antibiotic dilution series.

### Features

- **Auto-discovery** of plate reader output files (flat CSV or nested Drawer/Plate directory layouts)
- **OD600 and biomass** time-course parsing
- **Plate ID mapping** from an Excel file to assign strain names to well groups (auto-detected)
- **MIC determination** using a growth-threshold method with consecutive-well confirmation
- **Full timecourse MIC** analysis at every hourly read, not just the endpoint
- **Status tracking**: distinguishes between `mic`, `no_growth`, `completeGrowth`, and `indeterminate` outcomes
- **Per-plate and master output** CSVs organized by drawer/plate directory structure

## Installation

```bash
pip install -e .
```

## Usage

```bash
python -m micprocessing /path/to/data/directory -o /path/to/output
```

### Options

| Flag | Description |
|---|---|
| `-o`, `--outputDir` | Output directory (default: `<dataDir>/results`) |
| `--plateId` | Path to Plate ID `.xlsx` (auto-detected from data dir, parent, cwd, or cwd/reference) |
| `--ax1Conc` | Starting antibiotic concentration in ug/mL for column 1 |
| `--threshold` | MIC threshold as percent of growth range (default: 10) |
| `--config` | Path to YAML config file (auto-detected from data dir, parent, cwd, or cwd/reference) |
| `--genConfig` | Generate a template config file from discovered plates and exit |

### Example

```bash
python -m micprocessing ./raw_data -o ./output --ax1Conc 1000
```

### Using a config file

Generate a template from your data, fill it in, then run:

```bash
python -m micprocessing ./raw_data --genConfig
# Edit mic_config.yaml with strain names and concentrations
python -m micprocessing ./raw_data --config mic_config.yaml
```

If a file matching `*config*.yaml` is found in the data directory, its parent, cwd, or `cwd/reference/`, it is loaded automatically (no `--config` flag needed). When a config is present, the Plate ID xlsx is not auto-detected (but can still be passed explicitly with `--plateId`).

## Config file format

A YAML file that assigns strain names, antibiotics, and concentrations per plate. The `defaults` section sets values inherited by all plates unless overridden.

```yaml
defaults:
  threshold: 10
  ax1Conc: null        # starting concentration, ug/mL
  antibiotic: null

plates:
  1:
    strainUpper: 'BS168'
    strainLower: 'BS920'
    ax1Conc: 1000
    antibiotic: 'Spectinomycin'
  2:
    strainUpper: 'BS168'
    strainLower: 'JW1234'
    ax1Conc: 500
    antibiotic: 'Kanamycin'
```

| Field | Scope | Description |
|---|---|---|
| `threshold` | defaults | MIC threshold (default 10) |
| `ax1Conc` | defaults / plate | Starting antibiotic concentration in column 1 |
| `antibiotic` | defaults / plate | Antibiotic name (included in output) |
| `strainUpper` | plate | Strain name for rows A-D |
| `strainLower` | plate | Strain name for rows E-H |

Per-plate values override defaults. CLI `--ax1Conc` and `--threshold` flags are used as fallbacks when not set in the config.

## Output structure

Results are organized per-plate using the original drawer/plate directory names, plus master CSVs combining all plates:

```
<outputDir>/
  micResults.csv
  micTimecourse.csv
  endpointSummary.csv
  plateIndex.csv
  <drawerDir>/
    <plateDir>/
      micResults.csv
      micTimecourse.csv
      endpointSummary.csv
      plateIndex.csv
```

### micResults.csv

One row per strain/measurement/timepoint. Endpoint MIC using the final read.

| Column | Description |
|---|---|
| strain | Strain name from Plate ID (or fallback like P1-1) |
| posId | Plate position ID (e.g. P1-1, P2-2) |
| plate | Plate number |
| drawerName | Parent drawer directory name |
| plateName | Plate subdirectory name |
| rows | Replicate rows used (e.g. A,B,C,D) |
| measurement | `od` or `biomass` |
| timepoint | e.g. `0-24h`, `72h` |
| micCol | Column number where growth is inhibited (NaN if none) |
| micConc | Concentration label at MIC column |
| status | `mic`, `no_growth`, `completeGrowth`, or `indeterminate` |
| posCtrlMean | Growth control mean at endpoint |
| negCtrlMean | Media control mean at endpoint |
| threshold | Computed growth threshold |

### micTimecourse.csv

MIC evaluated at every hourly read across the full time-course.

Same columns as micResults, except `timepoint` is replaced by `hour` (0, 1, 2, ... 24, 72).

### endpointSummary.csv

Per-well mean and SD at the final timepoint for each strain/measurement/column.

### plateIndex.csv

Maps every well to its strain, file paths, and antibiotic concentration.

## Plate layout

Each 96-well plate is split into two strains:

- **Rows A-D** (upper): strain 1
- **Rows E-H** (lower): strain 2
- **Columns 1-10**: antibiotic dilution series (2-fold from column 1)
- **Column 11**: growth control (bacteria only)
- **Column 12**: media control (media only)

## MIC determination

1. Compute threshold: `negCtrlMean + (threshPct / 100) * (posCtrlMean - negCtrlMean)`
2. Classify each concentration column as growing (mean >= threshold) or inhibited
3. MIC = lowest concentration column that is inhibited, confirmed by two consecutive growing wells at lower concentrations
4. Minimum growth delta of 0.1 OD required between controls before calling MIC (suppresses noise at early timepoints)

### Status values

| Status | Meaning |
|---|---|
| `mic` | MIC determined at the reported column |
| `no_growth` | Growth control has not separated from media control |
| `completeGrowth` | All concentration wells are growing, no inhibition found |
| `indeterminate` | Growth detected but consecutive-well confirmation not met |

## Input formats

### Flat CSVs

Files named with a `_P<n>.csv` suffix (e.g. `OD_0-24h_P1.csv`, `biomass_24h_P2.csv`). Biomass files must contain "biomass" in the filename.

### Nested directories (Cytation export)

Each drawer directory contains one OD CSV at the top level and a Plate subdirectory with biomass data:

```
<experiment>/
  <drawer_dir>/
    <name>.csv                          <- OD time-course
    <plate_subdir>/
      Numerical data/
        4x_BF_biomass.csv              <- biomass time-course
```

Plate number is inferred from the Drawer number. Multi-plate endpoint directories (e.g. 72h) with `Plate 1`, `Plate 2`, etc. subdirs and `_P1`, `_P2` CSVs are also supported.

## Plate ID file

An Excel file with one sheet per plate (named `P1`, `P2`, etc.). Each sheet has two columns: well ID (e.g. `A1`) and strain name. Rows A-D map to the upper strain, E-H to the lower strain. Auto-detected from the data directory, its parent, cwd, or `cwd/reference/`.

## Reference scripts

The `reference/` directory contains earlier standalone analysis scripts and the Plate ID spreadsheet used during development.
