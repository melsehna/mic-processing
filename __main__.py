import argparse
from pathlib import Path

from .analysis import loadExp, genResults, genEndpointSummary, genIndex


def main():
    parser = argparse.ArgumentParser(
        prog="micProcessing",
        description="Analyze MIC data from Cytation plate reader output.",
    )
    parser.add_argument("dataDir", help="Directory containing plate reader output")
    parser.add_argument("-o", "--outputDir", default=None, help="Output directory (default: dataDir/results)")
    parser.add_argument("--plateId", default=None, help="Path to Plate ID xlsx for strain names")
    parser.add_argument("--ax1Conc", type=float, default=None, help="Starting antibiotic concentration (ug/mL) in column 1")
    parser.add_argument("--threshold", type=float, default=10, help="MIC threshold as pct of growth range (default: 10)")

    args = parser.parse_args()
    dataDir = Path(args.dataDir)
    outputDir = Path(args.outputDir) if args.outputDir else dataDir / "results"
    outputDir.mkdir(parents=True, exist_ok=True)

    plateIdPath = args.plateId
    if plateIdPath is None: # auto-detect
        for candidate in list(dataDir.glob("*Plate*ID*.xlsx")) + list(dataDir.parent.glob("*Plate*ID*.xlsx")):
            plateIdPath = candidate
            print(f"Auto-detected plate ID file: {candidate.name}")
            break

    print(f"Data directory: {dataDir}")
    print(f"Output directory: {outputDir}")

    exp = loadExp(dataDir, plateIdPath=plateIdPath)
    print(f"Loaded {len(exp)} strains: {', '.join(sorted(exp.keys()))}")

    for strain in sorted(exp.keys()):
        e = exp[strain]
        print(f"  {strain} (Plate {e['plate']}): OD={list(e['od'].keys())}, Biomass={list(e['biomass'].keys())}")

    indexDf = genIndex(dataDir, plateIdPath=plateIdPath, ax1Conc=args.ax1Conc)
    if not indexDf.empty:
        indexPath = outputDir / "plateIndex.csv"
        indexDf.to_csv(indexPath, index=False)
        print(f"\nPlate index saved to: {indexPath} ({indexDf['plateNo'].nunique()} plates, {len(indexDf)} wells)")

    micDf = genResults(exp, threshPct=args.threshold, ax1Conc=args.ax1Conc)
    if not micDf.empty:
        micPath = outputDir / "micResults.csv"
        micDf.to_csv(micPath, index=False)
        print(f"\nMIC results saved to: {micPath}")
        print(micDf.to_string(index=False))
    else:
        print("\nNo MIC results generated (no data found).")

    summaryDf = genEndpointSummary(exp, ax1Conc=args.ax1Conc)
    if not summaryDf.empty:
        summaryPath = outputDir / "endpointSummary.csv"
        summaryDf.to_csv(summaryPath, index=False)
        print(f"\nEndpoint summary saved to: {summaryPath}")

    print("\nDone.")


if __name__ == "__main__":
    main()
