import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    import yaml
except ImportError:
    yaml = None

from .discover import (
    discoverData, upperRows, lowerRows, concCols as defaultConcCols,
    growthCtrl as defaultGrowthCtrl, mediaCtrl as defaultMediaCtrl,
)


@dataclass
class PlateConfig:
    strainUpper: Optional[str] = None
    strainLower: Optional[str] = None
    ax1Conc: Optional[float] = None
    antibiotic: Optional[str] = None


@dataclass
class ExperimentConfig:
    threshold: float = 10
    ax1Conc: Optional[float] = None
    antibiotic: Optional[str] = None
    upperRows: list = field(default_factory=lambda: list('ABCD'))
    lowerRows: list = field(default_factory=lambda: list('EFGH'))
    growthCtrl: int = 11
    mediaCtrl: int = 12
    concCols: list = field(default_factory=lambda: list(range(1, 11)))
    dilutionFactor: int = 2
    plates: dict = field(default_factory=dict)  # plateNo -> PlateConfig

    def plateConfig(self, plateNo):
        return self.plates.get(plateNo, PlateConfig())


def _requireYaml():
    if yaml is None:
        raise ImportError(
            'pyyaml is required for config file support. '
            'Install it with: pip install pyyaml'
        )


def loadConfig(path):
    _requireYaml()
    path = Path(path)
    with open(path) as f:
        raw = yaml.safe_load(f)
    if raw is None:
        raw = {}

    defaults = raw.get('defaults', {})
    cfg = ExperimentConfig(
        threshold=defaults.get('threshold', 10),
        ax1Conc=defaults.get('ax1Conc'),
        antibiotic=defaults.get('antibiotic'),
        upperRows=defaults.get('upperRows', list('ABCD')),
        lowerRows=defaults.get('lowerRows', list('EFGH')),
        growthCtrl=defaults.get('growthCtrl', 11),
        mediaCtrl=defaults.get('mediaCtrl', 12),
        concCols=defaults.get('concCols', list(range(1, 11))),
        dilutionFactor=defaults.get('dilutionFactor', 2),
    )

    for plateKey, plateRaw in raw.get('plates', {}).items():
        plateNo = int(plateKey)
        cfg.plates[plateNo] = PlateConfig(
            strainUpper=plateRaw.get('strainUpper'),
            strainLower=plateRaw.get('strainLower'),
            ax1Conc=plateRaw.get('ax1Conc'),
            antibiotic=plateRaw.get('antibiotic'),
        )

    return cfg


def findConfig(dataDir):
    dataDir = Path(dataDir)
    searchDirs = [
        dataDir,
        dataDir.parent,
        Path.cwd(),
        Path.cwd() / 'reference',
    ]
    for d in searchDirs:
        if not d.is_dir():
            continue
        for candidate in sorted(d.glob('*config*.yaml')) + sorted(d.glob('*config*.yml')):
            return candidate
    return None


def generateTemplate(dataDir, outputPath=None):
    _requireYaml()
    dataDir = Path(dataDir)
    if outputPath is None:
        outputPath = dataDir / 'mic_config.yaml'
    else:
        outputPath = Path(outputPath)

    fileMap = discoverData(dataDir)

    plates = {}
    for plateNo in sorted(fileMap.keys()):
        plates[plateNo] = {
            'strainUpper': f'P{plateNo}-1',
            'strainLower': f'P{plateNo}-2',
            'ax1Conc': None,
            'antibiotic': None,
        }

    template = {
        'defaults': {
            'threshold': 10,
            'ax1Conc': None,
            'antibiotic': None,
        },
        'plates': plates,
    }

    with open(outputPath, 'w') as f:
        yaml.dump(template, f, default_flow_style=False, sort_keys=False)

    return outputPath
