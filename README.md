# micprocessing

Automated MIC (Minimum Inhibitory Concentration) analysis for Cytation plate reader output.

## Overview

`micprocessing` parses OD600 and biomass CSV files exported from BioTek Cytation plate readers, maps wells to strains using a Plate ID spreadsheet, and determines MIC values across antibiotic dilution series.

### Features

- **Auto-discovery** of plate reader output files (flat CSV or nested Drawer/Plate directory layouts)
- **OD600 and biomass** time-course parsing
- **Plate ID mapping** from an Excel file to assign strain names to well groups
- **MIC determination** using a configurable growth-threshold method
- **Plate index generation** linking wells to file paths, strains, and concentrations
- **Endpoint summary** tables with per-well mean and SD at the final timepoint

## Installation

```bash
pip install .
```

Or in development mode:

```bash
pip install -e .
```

## Usage

```bash
micprocessing /path/to/data/directory
```

### Options

| Flag | Description |
|---|---|
| `-o`, `--outputDir` | Output directory (default: `<dataDir>/results`) |
| `--plateId` | Path to Plate ID `.xlsx` (auto-detected if not given) |
| `--ax1Conc` | Starting antibiotic concentration in ug/mL for column 1 |
| `--threshold` | MIC threshold as percent of growth range (default: 10) |

### Example

```bash
micprocessing ./raw_data --ax1Conc 1000 --threshold 10
```

This reads plate reader CSVs from `./raw_data`, auto-detects a Plate ID file, and writes `micResults.csv`, `endpointSummary.csv`, and `plateIndex.csv` to `./raw_data/results/`.

## Plate layout

Each 96-well plate is split into two strains:

- **Rows A-D** (upper): strain 1
- **Rows E-H** (lower): strain 2
- **Columns 1-10**: antibiotic dilution series (2-fold from column 1)
- **Column 11**: media-only negative control
- **Column 12**: growth-only positive control

## Input formats

### Flat CSVs

Files named with a `_P<n>.csv` suffix (e.g., `OD_0-24h_P1.csv`, `biomass_24h_P2.csv`). Biomass files must contain "biomass" in the filename.

### Nested directories

Cytation export folders containing `OD600.csv` and/or `Numerical data/4x_BF_biomass.csv` inside Drawer/Plate subdirectories.

## Reference scripts

The `reference/` directory contains earlier standalone analysis scripts and the Plate ID spreadsheet used during development.
