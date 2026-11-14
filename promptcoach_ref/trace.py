"""Per-cycle provenance, for the Trace view.

Every layer's input, output, evidence grade and thesis citation, captured as the
cycle runs. This is what makes "show how it follows the design" checkable rather
than asserted: the reader opens a layer in the UI and sees the contract sentence
from Chapter 10 beside the value the code actually produced.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .framework import grades
from .framework.contracts import (
    CalibrateOutput,
    DiagnoseOutput,
    ElicitOutput,
    MeasureOutput,
    RespondOutput,
)

#: Which graded component each layer's central claim rests on.
LAYER_COMPONENT: dict[str, str] = {
    "elicit": "intent_artifact_gap_diagnostic",
    "measure": "six_dimension_rubric",
    "diagnose": "seven_category_taxonomy",
    "respond": "graduated_ladder",
    "calibrate": "five_band_progression",
}

LAYER_CONTRACT: dict[str, str | None] = {
    "elicit": ElicitOutput.REQUIREMENT_PASSED_DOWNSTREAM,
    "measure": MeasureOutput.REQUIREMENT_PASSED_DOWNSTREAM,
    "diagnose": DiagnoseOutput.REQUIREMENT_PASSED_DOWNSTREAM,
    "respond": RespondOutput.REQUIREMENT_PASSED_DOWNSTREAM,
    "calibrate": CalibrateOutput.REQUIREMENT_PASSED_DOWNSTREAM,
}

LAYER_CITE: dict[str, str] = {
    "elicit": "sec:elicit",
    "measure": "sec:measure",
    "diagnose": "sec:diagnose",
    "respond": "sec:respond",
    "calibrate": "sec:calibrate (no downstream requirement is stated for Layer 5)",
}


@dataclass
class Step:
    layer: str
    output: Any
    contract: str | None
    contract_is_from_thesis: bool
    cite: str
    component_id: str
    grade: str
    grade_basis: str
    grade_limit: str


@dataclass
class Trace:
    steps: list[Step] = field(default_factory=list)

    def record(self, layer: str, output: Any) -> None:
        component = grades.BY_ID[LAYER_COMPONENT[layer]]
        contract = LAYER_CONTRACT[layer]
        self.steps.append(
            Step(
                layer=layer,
                output=output,
                contract=contract,
                contract_is_from_thesis=contract is not None,
                cite=LAYER_CITE[layer],
                component_id=component.id,
                grade=component.grade.value,
                grade_basis=component.basis,
                grade_limit=component.limit,
            )
        )

    def to_json(self) -> list[dict]:
        from dataclasses import asdict, is_dataclass

        out = []
        for s in self.steps:
            out.append(
                {
                    "layer": s.layer,
                    "contract": s.contract,
                    "contract_is_from_thesis": s.contract_is_from_thesis,
                    "cite": s.cite,
                    "component": s.component_id,
                    "grade": s.grade,
                    "grade_basis": s.grade_basis,
                    "grade_limit": s.grade_limit,
                    "output": asdict(s.output) if is_dataclass(s.output) else str(s.output),
                }
            )
        return out
