"""Whether she sees her own calibration gap.

sec:calibrate, component 22, records her predicted rating beside the measured
score. "Whether to show the gap to the student is a policy setting tested by
F8." F8 (sec:falsify): showing the gap does not narrow it over a session, or it
lowers the number of revisions.

So the display is a switch with two arms. Where the gap may go is not a switch:
it is hers, and the teacher view never carries it, aggregate or otherwise
(`framework.commitments.CALIBRATION_STAYS_WITH_STUDENT`).
"""

from __future__ import annotations

from .base import Choice, register

SHOW_GAP_TO_STUDENT = register(
    Choice(
        id="calibration.show_gap_to_student",
        value=True,
        thesis_says=(
            "sec:calibrate leaves whether to show the gap to the student as a "
            "policy setting, tested by F8."
        ),
        borrowed_from="none",
        caveat=(
            "Shown by default. The gap is a model score minus her guess, so the "
            "shared-priors threat applies to it, and confidence and prompt score "
            "are different constructs. Showing it may teach her to predict the "
            "scorer rather than to judge her prompt; F8 is the test of whether "
            "showing it helps at all. Off is the F8 control arm: the rating and "
            "the gap are still recorded, and the student is shown neither."
        ),
    )
)

TEACHER_VIEW = register(
    Choice(
        id="calibration.teacher_view",
        value="never",
        thesis_says=(
            "sec:commitments: diagnostics belong to the student and teacher views "
            "are aggregate unless she chooses to share."
        ),
        borrowed_from="none",
        caveat=(
            "Not a toggle. The policy choice is to exclude calibration from even "
            "the aggregate teacher view, which is stricter than the commitment "
            "requires: a class-average gap is cheap to compute and invites ranking "
            "students by how well they guess a model's score."
        ),
    )
)
