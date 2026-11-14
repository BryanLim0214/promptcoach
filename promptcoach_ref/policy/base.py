"""The shape every implementation choice must take.

The thesis specifies output contracts for Layers 1-4 and twenty-four other
things not at all. An implementation has to choose values anyway. This module makes
each choice declare itself.

Four fields are mandatory on every choice:

    thesis_says    - the passage proving the thesis leaves this open
    borrowed_from  - where the number came from, or "none" if invented here
    caveat         - what the thesis says about relying on it
    status         - always IMPLEMENTATION_CHOICE

A test asserts that every Choice instance in this package has all four
non-empty. The UI badges anything carrying a Choice differently from anything
carrying a framework Cite, so a reader is never left guessing which is which.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class Status(str, Enum):
    IMPLEMENTATION_CHOICE = "implementation_choice"


IMPLEMENTATION_CHOICE = Status.IMPLEMENTATION_CHOICE


@dataclass(frozen=True)
class Choice:
    """One value the thesis does not specify."""

    id: str
    #: What was chosen. Kept as a plain value so the traceability generator can
    #: render it without knowing the type.
    value: Any
    thesis_says: str
    borrowed_from: str
    caveat: str
    status: Status = IMPLEMENTATION_CHOICE

    def __post_init__(self) -> None:
        for name in ("thesis_says", "borrowed_from", "caveat"):
            if not str(getattr(self, name)).strip():
                raise ValueError(
                    f"{self.id}: implementation choices must state {name!r}. "
                    "A value the thesis does not specify, presented without its "
                    "provenance, is indistinguishable from a value the thesis does "
                    "specify. That is the failure this class exists to prevent."
                )


_REGISTRY: dict[str, Choice] = {}


def register(choice: Choice) -> Choice:
    if choice.id in _REGISTRY:
        raise ValueError(f"duplicate implementation choice id: {choice.id}")
    _REGISTRY[choice.id] = choice
    return choice


def all_choices() -> tuple[Choice, ...]:
    return tuple(_REGISTRY[k] for k in sorted(_REGISTRY))


#: The twenty-four things the framework leaves open, enumerated so the traceability
#: report can show which are covered by a Choice and which are simply not
#: implemented. Keeping the list here means a gap cannot be closed by silence.
UNSPECIFIED_BY_THESIS: tuple[tuple[str, str], ...] = (
    ("per_layer_inputs", "Only 'Requirement passed downstream' (output) is stated."),
    ("layer_5_output", "Layers 1-4 have a downstream requirement; Layer 5 has none."),
    ("state_machine", "No named states exist; only 'the escalation state' and 'the difficulty state'."),
    ("confidence_formula", "No formula, threshold, or scale for per-dimension confidence."),
    ("sentinel_aggregation", "How four 0-1 signals combine into one score."),
    ("sentinel_threshold", "AUC is reported precisely to avoid committing to a threshold."),
    ("classifier_algorithm", "Layer 3's algorithm, features, and tie-breaking."),
    ("ranked_list_length", "How many categories the ranked list should contain."),
    ("escalation_thresholds", "Build 3's triggers were set for a task with a correct answer."),
    ("de_escalation", "Whether the level resets between attempts, tasks, or sessions."),
    ("stop_condition", "What happens after level 4 fails to land."),
    ("gating_values", "Rate, streak, and window for prompting bands."),
    ("decomposition_rules", "Build 3's numbers are Python values."),
    ("task_bank", "No prompting tasks per band exist beyond the illustrative examples."),
    ("band_placement", "Band 1 'needs a placement pretest' to be set by data."),
    ("response_templates", "Templates per failure category are listed as unbuilt."),
    ("worked_contrast_generator", "Listed as unbuilt."),
    ("reason_min_length", "A revision needs 'a short stated reason'; no minimum length is given."),
    ("revision_gate_exit", "A new task is held 'unless policy exit applies'; the exit is not stated."),
    ("gap_display", "Whether to show the calibration gap to the student is a policy setting tested by F8."),
    ("generator_model", "The judge must be independent of the generating model; no generator is named."),
    # Added after the second review round (FINDINGS_LOG_R2 D03, D04).
    ("evaluative_escalation", "Help does not rise on the evaluative scores alone; what counts as an unchanged prompt is not stated."),
    ("gating_success", "What counts as a success for the rate and streak, and whether the streak counts attempts or distinct tasks."),
    ("help_cycle_scope", "What one cycle of help covers (one task, one top-ranked failure, across revisions) and when it closes."),
)

#: Gaps that closed because the framework dropped the component. Kept so the
#: change is visible rather than silent.
CLOSED_BY_REMOVAL: tuple[tuple[str, str], ...] = (
    ("affect_thresholds", "Affective state inference was removed from the framework (sec:not-adopted)."),
)
