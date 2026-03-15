import re
import numpy as np
import pandas as pd
from pathlib import Path

from .discover import (
    discoverData, upperRows, lowerRows, allRows, concCols,
    mediaCtrl, growthCtrl,
)
from .parsers import parseBiomassCsv, parseOdCsv


def loadPlateId(plateIdPath):
    plateIdPath = Path(plateIdPath)
    if not plateIdPath.exists():
        return None

    xl = pd.ExcelFile(plateIdPath)
    strainMap = {}
    for sheet in xl.sheet_names:
        m = re.search(r'P(\d+)', sheet)
        if not m:
            continue
        plateNo = int(m.group(1))
        df = pd.read_excel(xl, sheet, header=None)
        upper, lower = set(), set()
        for _, row in df.iterrows():
            well = str(row.iloc[0]).strip()
            strain = str(row.iloc[1]).strip()
            if well and well[0] in 'ABCD':
                upper.add(strain)
            elif well and well[0] in 'EFGH':
                lower.add(strain)
        strainMap[plateNo] = {
            'upper': upper.pop() if len(upper) == 1 else f'P{plateNo}-1',
            'lower': lower.pop() if len(lower) == 1 else f'P{plateNo}-2',
        }
    return strainMap


def loadExp(dataDir, plateIdPath=None):
    fileMap = discoverData(dataDir)
    strainMap = loadPlateId(plateIdPath) if plateIdPath else None

    exp = {}
    for plateNo in sorted(fileMap.keys()):
        plateData = fileMap[plateNo]

        for group, rows in [('upper', upperRows), ('lower', lowerRows)]:
            if strainMap and plateNo in strainMap:
                name = strainMap[plateNo][group]
            else:
                name = f'P{plateNo}-{"1" if group == "upper" else "2"}'

            posId = f'P{plateNo}-{"1" if group == "upper" else "2"}'

            entry = {
                'plate': plateNo, 'posId': posId,
                'rows': rows, 'od': {}, 'biomass': {},
                'drawerName': plateData.get('drawerName'),
                'plateName': plateData.get('plateName'),
            }

            for tp, fpath in plateData.get('od', []):
                entry['od'][tp] = _extractByCols(parseOdCsv(fpath), rows)
            for tp, fpath in plateData.get('biomass', []):
                entry['biomass'][tp] = _extractByCols(parseBiomassCsv(fpath), rows)

            exp[name] = entry

    return exp


def _extractByCols(wellData, rows):
    result = {}
    for col in range(1, 13):
        reps = [wellData[f'{r}{col}'] for r in rows if f'{r}{col}' in wellData and len(wellData[f'{r}{col}']) > 0]
        if not reps:
            continue
        maxLen = max(len(r) for r in reps)
        padded = [np.pad(r, (0, maxLen - len(r)), constant_values=np.nan) if len(r) < maxLen else r for r in reps]
        result[col] = np.array(padded)
    return result


MIN_GROWTH_DELTA = 0.1


def determineMic(colData, threshPct=10, tIdx=-1):
    if not colData:
        return None
    posVals = colData.get(growthCtrl)
    if posVals is None or tIdx >= posVals.shape[1]:
        return None
    posEnd = np.nanmean(posVals[:, tIdx])

    negVals = colData.get(mediaCtrl)
    if negVals is not None and tIdx < negVals.shape[1]:
        negEnd = np.nanmean(negVals[:, tIdx])
    else:
        negEnd = 0.0

    growthDelta = posEnd - negEnd
    if growthDelta < MIN_GROWTH_DELTA:
        if posEnd >= MIN_GROWTH_DELTA:
            # growth ctrl grew but all wells are near media ctrl level
            return {'micCol': 1, 'status': 'belowRange',
                    'posCtrlMean': round(posEnd, 4),
                    'negCtrlMean': round(negEnd, 4), 'threshold': None}
        return {'micCol': None, 'status': 'noGrowth',
                'posCtrlMean': round(posEnd, 4),
                'negCtrlMean': round(negEnd, 4), 'threshold': None}

    thresh = negEnd + (threshPct / 100) * growthDelta

    growing = {}
    for col in concCols:
        if col in colData and tIdx < colData[col].shape[1]:
            growing[col] = np.nanmean(colData[col][:, tIdx]) >= thresh

    micCol = None
    for col in range(max(concCols), 0, -1):
        if col not in growing:
            continue
        if not growing[col]:
            nextGrows = growing.get(col + 1, False)
            nextNextGrows = growing.get(col + 2, False)
            if nextGrows and nextNextGrows:
                micCol = col
            elif col + 1 > max(concCols) and nextGrows:
                micCol = col

    if micCol is not None:
        status = 'mic'
    elif all(growing.get(c, False) for c in concCols if c in growing):
        status = 'completeGrowth'
    else:
        status = 'indeterminate'

    return {'micCol': micCol, 'status': status,
            'posCtrlMean': round(posEnd, 4),
            'negCtrlMean': round(negEnd, 4), 'threshold': round(thresh, 4)}


def genResults(exp, threshPct=10, ax1Conc=None):
    rows = []
    for strain in sorted(exp.keys()):
        entry = exp[strain]
        for measType in ['od', 'biomass']:
            for tp, colData in entry.get(measType, {}).items():
                mic = determineMic(colData, threshPct)
                if mic is None:
                    continue
                micCol = mic['micCol']
                rows.append({
                    'strain': strain, 'posId': entry['posId'],
                    'plate': entry['plate'],
                    'drawerName': entry.get('drawerName', ''),
                    'plateName': entry.get('plateName', ''),
                    'rows': ','.join(entry['rows']),
                    'measurement': measType, 'timepoint': tp,
                    'micCol': micCol,
                    'micConc': _concLabel(int(micCol), ax1Conc) if micCol is not None and not np.isnan(micCol) else '',
                    'status': mic['status'],
                    'posCtrlMean': mic['posCtrlMean'],
                    'negCtrlMean': mic['negCtrlMean'],
                    'threshold': mic['threshold'],
                })
    return pd.DataFrame(rows)


def genTimecourseResults(exp, threshPct=10, ax1Conc=None):
    rows = []
    for strain in sorted(exp.keys()):
        entry = exp[strain]
        for measType in ['od', 'biomass']:
            for tp, colData in entry.get(measType, {}).items():
                nTimepoints = min(v.shape[1] for v in colData.values())
                # compute cumulative hour offset from timepoint label
                baseHour = _tpBaseHour(tp)
                for tIdx in range(nTimepoints):
                    mic = determineMic(colData, threshPct, tIdx=tIdx)
                    if mic is None:
                        continue
                    micCol = mic['micCol']
                    rows.append({
                        'strain': strain, 'plate': entry['plate'],
                        'drawerName': entry.get('drawerName', ''),
                        'plateName': entry.get('plateName', ''),
                        'rows': ','.join(entry['rows']),
                        'measurement': measType,
                        'hour': baseHour + tIdx,
                        'micCol': micCol,
                        'micConc': _concLabel(int(micCol), ax1Conc) if micCol is not None and not np.isnan(micCol) else '',
                        'status': mic['status'],
                        'posCtrlMean': mic['posCtrlMean'],
                        'negCtrlMean': mic['negCtrlMean'],
                        'threshold': mic['threshold'],
                    })
    return pd.DataFrame(rows)


def _tpBaseHour(tp):
    m = re.match(r'^(\d+)-(\d+)h$', tp)
    if m:
        return int(m.group(1))
    m = re.match(r'^(\d+)h$', tp)
    if m:
        return int(m.group(1))
    return 0


def genEndpointSummary(exp, ax1Conc=None):
    rows = []
    for strain in sorted(exp.keys()):
        entry = exp[strain]
        for measType in ['od', 'biomass']:
            for tp, colData in entry.get(measType, {}).items():
                for colNum in sorted(colData.keys()):
                    vals = colData[colNum][:, -1]
                    vals = vals[~np.isnan(vals)]
                    rows.append({
                        'strain': strain, 'plate': entry['plate'],
                        'drawerName': entry.get('drawerName', ''),
                        'plateName': entry.get('plateName', ''),
                        'rows': ','.join(entry['rows']),
                        'measurement': measType, 'timepoint': tp,
                        'column': colNum, 'condition': _concLabel(colNum, ax1Conc),
                        'mean': round(np.mean(vals), 4),
                        'sd': round(np.std(vals), 4), 'n': len(vals),
                    })
    return pd.DataFrame(rows)


def genIndex(dataDir, plateIdPath=None, ax1Conc=None):
    dataDir = Path(dataDir)
    fileMap = discoverData(dataDir)
    strainMap = loadPlateId(plateIdPath) if plateIdPath else None

    rows = []
    for plateNo in sorted(fileMap.keys()):
        plateData = fileMap[plateNo]
        odPath = _pickTsPath(plateData.get('od', []))
        biomassPath = _pickTsPath(plateData.get('biomass', []))

        for rowLetter in allRows:
            if strainMap and plateNo in strainMap:
                group = 'upper' if rowLetter in upperRows else 'lower'
                plateId = strainMap[plateNo][group]
            else:
                group = '1' if rowLetter in upperRows else '2'
                plateId = f'P{plateNo}-{group}'

            for colNum in range(1, 13):
                if colNum == mediaCtrl:
                    conc = 'media_ctrl'
                elif colNum == growthCtrl:
                    conc = 'growth_ctrl'
                elif ax1Conc is not None:
                    conc = ax1Conc / (2 ** (colNum - 1))
                else:
                    conc = f'Ax1/{2 ** (colNum - 1)}' if colNum > 1 else 'Ax1'

                rows.append({
                    'plateId': plateId, 'wellId': f'{rowLetter}{colNum}',
                    'plateNo': plateNo, 'biomassPath': biomassPath,
                    'odPath': odPath, 'axConc': conc,
                })

    return pd.DataFrame(rows)


def _pickTsPath(fileList):
    if not fileList:
        return ''
    for tp, fpath in fileList:
        if '0-24' in tp or '24' in tp:
            return str(fpath)
    return str(fileList[0][1])


def _concLabel(colNum, ax1Conc=None):
    if colNum == mediaCtrl:
        return 'Media ctrl'
    elif colNum == growthCtrl:
        return 'Growth ctrl'
    elif ax1Conc is not None:
        return f'{ax1Conc / (2 ** (colNum - 1)):g} ug/mL'
    else:
        return 'Ax1' if colNum == 1 else f'Ax1/{2 ** (colNum - 1)}'
