import re
from pathlib import Path

upperRows = list('ABCD')
lowerRows = list('EFGH')
allRows = upperRows + lowerRows
numCols = 12
concCols = list(range(1, 11))
mediaCtrl = 11
growthCtrl = 12


def discoverData(dataDir):
    dataDir = Path(dataDir)
    if not dataDir.is_dir():
        raise FileNotFoundError(f'Data directory not found: {dataDir}')

    result = _tryFlat(dataDir)
    if not result:
        result = _tryNested(dataDir)
    if not result:
        raise FileNotFoundError(
            f'No recognized Cytation output files found in {dataDir}. '
            'Expected flat CSVs with _P1/_P2/etc suffixes, or nested '
            'Drawer/Plate directories.'
        )
    return result


def _tryFlat(dataDir):
    plateRe = re.compile(r'_P(\d+)\.csv$', re.IGNORECASE)
    tpRe = re.compile(r'(0-24h|24h|\d+h)', re.IGNORECASE)

    result = {}
    for csvPath in sorted(dataDir.glob('*.csv')):
        plateMatch = plateRe.search(csvPath.name)
        if not plateMatch:
            continue

        plateNo = int(plateMatch.group(1))
        tpMatch = tpRe.search(csvPath.name)
        tp = tpMatch.group(1) if tpMatch else '0-24h'

        if plateNo not in result:
            result[plateNo] = {'od': [], 'biomass': []}

        if 'biomass' in csvPath.name.lower():
            result[plateNo]['biomass'].append((tp, csvPath))
        else:
            result[plateNo]['od'].append((tp, csvPath))

    return result if result else None


def _tryNested(dataDir):
    result = {}

    for drawerDir in sorted(dataDir.iterdir()):
        if not drawerDir.is_dir():
            continue

        plateNo = None
        plateSubdir = None
        for child in drawerDir.iterdir():
            if child.is_dir():
                m = re.search(r'Plate\s*(\d+)', child.name, re.IGNORECASE)
                if m:
                    plateNo = int(m.group(1))
                    plateSubdir = child
                    break
        if plateNo is None:
            m = re.search(r'Drawer\s*(\d+)', drawerDir.name, re.IGNORECASE)
            if m:
                plateNo = int(m.group(1))
            else:
                continue

        if plateNo not in result:
            result[plateNo] = {
                'od': [], 'biomass': [],
                'drawerName': drawerDir.name,
                'plateName': plateSubdir.name if plateSubdir else None,
            }

        tp = _inferTimepoint(drawerDir, dataDir)

        for csvPath in sorted(drawerDir.glob('*.csv')):
            if csvPath.is_file():
                result[plateNo]['od'].append((tp, csvPath))
                break

        if plateSubdir is not None:
            biomassPath = plateSubdir / 'Numerical data' / '4x_BF_biomass.csv'
            if biomassPath.exists():
                result[plateNo]['biomass'].append((tp, biomassPath))

    return result if result else None


def _inferPlateNo(fpath, baseDir):
    relStr = str(fpath.relative_to(baseDir))
    m = re.search(r'Plate\s*(\d+)', relStr, re.IGNORECASE)
    if m:
        return int(m.group(1))
    m = re.search(r'Drawer\s*(\d+)', relStr, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


def _inferTimepoint(fpath, baseDir):
    relStr = str(fpath.relative_to(baseDir))
    m = re.search(r'(\d+)h\b', relStr, re.IGNORECASE)
    return f'{m.group(1)}h' if m else '0-24h'
