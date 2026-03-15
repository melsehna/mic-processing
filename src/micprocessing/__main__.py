import argparse
from pathlib import Path

from .analysis import loadExp, genResults, genEndpointSummary, genIndex


def main():
    parser = argparse.ArgumentParser(
        prog='micProcessing',
        description='Analyze MIC data from Cytation plate reader output.',
    )
    parser.add_argument('dataDir', help='Directory containing plate reader output')
    parser.add_argument('-o', '--outputDir', default=None, help='Output directory (default: dataDir/results)')
    parser.add_argument('--plateId', default=None, help='Path to Plate ID xlsx for strain names')
    parser.add_argument('--ax1Conc', type=float, default=None, help='Starting antibiotic concentration (ug/mL) in column 1')
    parser.add_argument('--threshold', type=float, default=10, help='MIC threshold as pct of growth range (default: 10)')

    args = parser.parse_args()
    dataDir = Path(args.dataDir)
    outputDir = Path(args.outputDir) if args.outputDir else dataDir / 'results'
    outputDir.mkdir(parents=True, exist_ok=True)

    plateIdPath = args.plateId
    if plateIdPath is None:
        for candidate in list(dataDir.glob('*Plate*ID*.xlsx')) + list(dataDir.parent.glob('*Plate*ID*.xlsx')):
            plateIdPath = candidate
            print(f'Auto-detected plate ID file: {candidate.name}')
            break

    print(f'Data directory: {dataDir}')
    print(f'Output directory: {outputDir}')

    exp = loadExp(dataDir, plateIdPath=plateIdPath)
    print(f'Loaded {len(exp)} strains: {", ".join(sorted(exp.keys()))}')

    for strain in sorted(exp.keys()):
        e = exp[strain]
        print(f'  {strain} (Plate {e["plate"]}): OD={list(e["od"].keys())}, Biomass={list(e["biomass"].keys())}')

    plateInfo = {}
    for strain, entry in exp.items():
        pn = entry['plate']
        if pn not in plateInfo:
            plateInfo[pn] = {
                'strains': [],
                'drawerName': entry.get('drawerName'),
                'plateName': entry.get('plateName'),
            }
        plateInfo[pn]['strains'].append(strain)

    indexDf = genIndex(dataDir, plateIdPath=plateIdPath, ax1Conc=args.ax1Conc)
    micDf = genResults(exp, threshPct=args.threshold, ax1Conc=args.ax1Conc)
    summaryDf = genEndpointSummary(exp, ax1Conc=args.ax1Conc)

    for plateNo in sorted(plateInfo.keys()):
        info = plateInfo[plateNo]
        if info['drawerName'] and info['plateName']:
            plateDir = outputDir / info['drawerName'] / info['plateName']
        else:
            plateDir = outputDir / f'plate{plateNo}'
        plateDir.mkdir(parents=True, exist_ok=True)
        strains = info['strains']
        print(f'\nPlate {plateNo} ({", ".join(sorted(strains))}):')
        print(f'  -> {plateDir}')

        if not indexDf.empty:
            plateDf = indexDf[indexDf['plateNo'] == plateNo]
            if not plateDf.empty:
                plateDf.to_csv(plateDir / 'plateIndex.csv', index=False)
                print(f'  plateIndex.csv ({len(plateDf)} wells)')

        if not micDf.empty:
            plateMic = micDf[micDf['plate'] == plateNo]
            if not plateMic.empty:
                plateMic.to_csv(plateDir / 'micResults.csv', index=False)
                print(f'  micResults.csv')
                print(plateMic.to_string(index=False))

        if not summaryDf.empty:
            plateSummary = summaryDf[summaryDf['plate'] == plateNo]
            if not plateSummary.empty:
                plateSummary.to_csv(plateDir / 'endpointSummary.csv', index=False)
                print(f'  endpointSummary.csv')

    print('\nDone.')


if __name__ == '__main__':
    main()
