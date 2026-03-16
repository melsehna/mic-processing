import argparse
from pathlib import Path

from .analysis import loadExp, genResults, genTimecourseResults, genEndpointSummary, genIndex
from .config import loadConfig, findConfig, generateTemplate


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
    parser.add_argument('--config', default=None, help='Path to YAML config file')
    parser.add_argument('--genConfig', action='store_true', help='Generate a template config file and exit')

    args = parser.parse_args()
    dataDir = Path(args.dataDir)
    outputDir = Path(args.outputDir) if args.outputDir else dataDir / 'results'

    # --genConfig: generate template and exit
    if args.genConfig:
        outPath = generateTemplate(dataDir, args.config)
        print(f'Generated config template: {outPath}')
        return

    outputDir.mkdir(parents=True, exist_ok=True)

    # Load config
    config = None
    configPath = args.config
    if configPath:
        config = loadConfig(configPath)
        print(f'Loaded config: {configPath}')
    else:
        detected = findConfig(dataDir)
        if detected:
            config = loadConfig(detected)
            print(f'Auto-detected config: {detected}')

    # Config threshold/ax1Conc serve as defaults; CLI flags override
    threshold = args.threshold
    if threshold == 10 and config and config.threshold != 10:
        threshold = config.threshold

    ax1Conc = args.ax1Conc
    if ax1Conc is None and config and config.ax1Conc is not None:
        ax1Conc = config.ax1Conc

    # plateId: config overrides xlsx, but xlsx still works as fallback
    plateIdPath = args.plateId
    if plateIdPath is None and config is None:
        searchDirs = [
            dataDir,
            dataDir.parent,
            Path.cwd(),
            Path.cwd() / 'reference',
        ]
        for d in searchDirs:
            if not d.is_dir():
                continue
            for candidate in d.glob('*Plate*ID*.xlsx'):
                plateIdPath = candidate
                print(f'Auto-detected plate ID file: {candidate}')
                break
            if plateIdPath:
                break

    print(f'Data directory: {dataDir}')
    print(f'Output directory: {outputDir}')

    exp = loadExp(dataDir, plateIdPath=plateIdPath, config=config)
    print(f'Loaded {len(exp)} strain positions:')

    for posId in sorted(exp.keys()):
        e = exp[posId]
        print(f'  {e["strain"]} [{posId}] (Plate {e["plate"]}): OD={list(e["od"].keys())}, Biomass={list(e["biomass"].keys())}')

    plateInfo = {}
    for posId, entry in exp.items():
        pn = entry['plate']
        if pn not in plateInfo:
            plateInfo[pn] = {
                'strains': [],
                'posIds': [],
                'drawerName': entry.get('drawerName'),
                'plateName': entry.get('plateName'),
            }
        plateInfo[pn]['strains'].append(entry['strain'])
        plateInfo[pn]['posIds'].append(posId)

    indexDf = genIndex(dataDir, plateIdPath=plateIdPath, ax1Conc=ax1Conc, config=config)
    micDf = genResults(exp, threshPct=threshold, ax1Conc=ax1Conc)
    tcDf = genTimecourseResults(exp, threshPct=threshold, ax1Conc=ax1Conc)
    summaryDf = genEndpointSummary(exp, ax1Conc=ax1Conc)

    for plateNo in sorted(plateInfo.keys()):
        info = plateInfo[plateNo]
        if info['drawerName'] and info['plateName']:
            plateDir = outputDir / info['drawerName'] / info['plateName']
        else:
            plateDir = outputDir / f'plate{plateNo}'
        plateDir.mkdir(parents=True, exist_ok=True)
        strains = info['strains']
        tag = '_'.join(sorted(strains))
        print(f'\nPlate {plateNo} ({", ".join(sorted(strains))}):')
        print(f'  -> {plateDir}')

        if not indexDf.empty:
            plateDf = indexDf[indexDf['plateNo'] == plateNo]
            if not plateDf.empty:
                plateDf.to_csv(plateDir / f'plateIndex_{tag}.csv', index=False)
                print(f'  plateIndex_{tag}.csv ({len(plateDf)} wells)')

        if not micDf.empty:
            plateMic = micDf[micDf['plate'] == plateNo]
            if not plateMic.empty:
                plateMic.to_csv(plateDir / f'micResults_{tag}.csv', index=False)
                print(f'  micResults_{tag}.csv')
                print(plateMic.to_string(index=False))

        if not tcDf.empty:
            plateTc = tcDf[tcDf['plate'] == plateNo]
            if not plateTc.empty:
                plateTc.to_csv(plateDir / f'micTimecourse_{tag}.csv', index=False)
                print(f'  micTimecourse_{tag}.csv ({plateTc["hour"].nunique()} timepoints)')

        if not summaryDf.empty:
            plateSummary = summaryDf[summaryDf['plate'] == plateNo]
            if not plateSummary.empty:
                plateSummary.to_csv(plateDir / f'endpointSummary_{tag}.csv', index=False)
                print(f'  endpointSummary_{tag}.csv')

    # Master CSVs across all plates
    if not indexDf.empty:
        indexDf.to_csv(outputDir / 'full_plateIndex.csv', index=False)
    if not micDf.empty:
        micDf.to_csv(outputDir / 'full_micResults.csv', index=False)
    if not tcDf.empty:
        tcDf.to_csv(outputDir / 'full_micTimecourse.csv', index=False)
    if not summaryDf.empty:
        summaryDf.to_csv(outputDir / 'full_endpointSummary.csv', index=False)
    print(f'\nMaster CSVs saved to {outputDir}')
    print('Done.')


if __name__ == '__main__':
    main()
