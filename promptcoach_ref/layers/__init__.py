"""The five layers.

Each implements the Protocol of the same name in `framework.contracts`, takes
only its declared input, and returns only its declared output.

`READS` on each class records which upstream outputs it may see. Layer 3 reads
Layer 1 as well as Layer 2, which is the DAG edge sec:framework
requires: four of the seven categories are invisible in the prompt text Layer 2
scores. A contract test walks these declarations.
"""

from .calibrate import CalibrateLayer
from .diagnose import DiagnoseLayer
from .elicit import Consent, ElicitLayer
from .measure import MeasureLayer
from .respond import RespondLayer, validate

__all__ = [
    "CalibrateLayer",
    "Consent",
    "DiagnoseLayer",
    "ElicitLayer",
    "MeasureLayer",
    "RespondLayer",
    "validate",
]
