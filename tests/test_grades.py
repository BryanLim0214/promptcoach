"""Tier 4 - no component reports a grade stronger than the framework assigns.

These are the tests that fail if someone quietly promotes a proposition to a
finding. The taxonomy, the progression, the reasoned revision and the
calibration gap are the thesis's own contributions and are all Argued; a later
contributor who "fixes" their grade because the code now works would be making
exactly the claim the manuscript refuses to make.

Two columns are pinned: the mechanism grade (4 Direct, 10 Transferred, 10 Argued)
and the need basis (4 User studies, 18 Builds, 2 Argument). The enum
member for the first is still `NeedBasis.STUDENTS`; its label is "Classroom
studies".
"""

from __future__ import annotations

import inspect

import pytest

from promptcoach_ref import policy
from promptcoach_ref.framework import (
    classroom,
    commitments,
    grades,
    ladder,
    progression,
    revision,
    rubric,
    sentinel,
    taxonomy,
)
from promptcoach_ref.framework.grades import Cite, Grade, NeedBasis

pytestmark = pytest.mark.grade


def test_there_are_twenty_four_components():
    assert len(grades.GRADED_COMPONENTS) == grades.EXPECTED_COMPONENT_COUNT == 24
    assert len(grades.BY_ID) == 24, "component ids must be unique"


def test_mechanism_grade_counts_match_the_framework():
    """sec:framework - "Mechanism: 4 Direct, 10 Transferred, 10 Argued." """
    assert grades.counts() == grades.EXPECTED_GRADE_COUNTS
    assert grades.EXPECTED_GRADE_COUNTS == {
        Grade.DIRECT: 4,
        Grade.TRANSFERRED: 10,
        Grade.ARGUED: 10,
    }


def test_need_basis_counts_match_the_framework():
    """sec:evidence - "By need basis, 4 rest on the user studies, 18 on the
    builds, and 2 on argument." """
    assert grades.need_counts() == grades.EXPECTED_NEED_COUNTS
    assert grades.EXPECTED_NEED_COUNTS == {
        NeedBasis.STUDENTS: 4,
        NeedBasis.BUILDS: 18,
        NeedBasis.ARGUMENT: 2,
    }


def test_every_component_has_a_need_basis():
    for c in grades.GRADED_COMPONENTS:
        assert isinstance(c.need, NeedBasis), c.id


def test_the_need_basis_is_required_on_construction():
    with pytest.raises(TypeError):
        grades.GradedComponent(  # type: ignore[call-arg]
            id="x",
            name="x",
            grade=Grade.ARGUED,
            basis="b",
            limit="l",
            cite=Cite("sec:framework"),
        )


def test_the_four_student_rows_are_the_new_ones():
    students = {c.id for c in grades.GRADED_COMPONENTS if c.need is NeedBasis.STUDENTS}
    assert students == {
        "visible_consequence_before_coaching",
        "same_task_revision_with_reason",
        "predicted_rating_beside_score",
        "selecting_is_not_composing",
    }


def test_the_two_argument_rows():
    argument = {c.id for c in grades.GRADED_COMPONENTS if c.need is NeedBasis.ARGUMENT}
    assert argument == {
        "judge_independent_of_generator",
        "diagnostics_belong_to_student",
    }


def test_the_five_new_rows_carry_their_specified_grades():
    expected = {
        "visible_consequence_before_coaching": (Grade.ARGUED, NeedBasis.STUDENTS),
        "same_task_revision_with_reason": (Grade.ARGUED, NeedBasis.STUDENTS),
        "predicted_rating_beside_score": (Grade.ARGUED, NeedBasis.STUDENTS),
        "judge_independent_of_generator": (Grade.TRANSFERRED, NeedBasis.ARGUMENT),
        "selecting_is_not_composing": (Grade.ARGUED, NeedBasis.STUDENTS),
    }
    for cid, (grade, need) in expected.items():
        c = grades.BY_ID[cid]
        assert (c.grade, c.need) == (grade, need), cid


def test_the_new_rows_name_the_requirement_they_answer():
    assert grades.BY_ID["visible_consequence_before_coaching"].requirement == "R1"
    assert grades.BY_ID["predicted_rating_beside_score"].requirement == "R2"
    assert grades.BY_ID["same_task_revision_with_reason"].requirement == "R3"
    assert grades.BY_ID["judge_independent_of_generator"].requirement == "R4"
    assert grades.BY_ID["selecting_is_not_composing"].requirement == "R5"


def test_visible_consequence_is_argued_because_the_order_was_never_varied():
    """Row 20 was Direct on acceptance self-report. No evaluation of the
    mechanism took place (R2_COMMITTEE M7), so it is Argued."""
    c = grades.VISIBLE_CONSEQUENCE_BEFORE_COACHING
    assert c.grade is Grade.ARGUED
    assert "never varied" in c.basis
    assert "untested" in c.basis
    assert "self-report" in c.basis.lower()


def test_the_direct_rows_are_exactly_the_four_build_one_measurement_rows():
    direct = {c.id for c in grades.GRADED_COMPONENTS if c.grade is Grade.DIRECT}
    assert direct == {
        "six_dimension_rubric",
        "lower_confidence_on_evaluative",
        "content_over_fluency",
        "over_reliance_separable",
    }
    assert all(grades.BY_ID[i].need is NeedBasis.BUILDS for i in direct)
    assert "classroom-based Direct" not in grades.GRADE_DEFINITION[Grade.DIRECT]


def test_affective_state_inference_is_removed():
    """Removed after implementation (sec:not-adopted). It must not come back as a
    graded component, and its removal must stay visible."""
    assert "affective_state_inference" not in grades.BY_ID
    assert not hasattr(grades, "AFFECTIVE_STATE_INFERENCE")
    why, cite = grades.REMOVED_COMPONENTS["affective_state_inference"]
    assert "planning" in why
    assert cite.label == "sec:not-adopted"


def test_escalation_no_longer_names_inactivity_as_a_trigger():
    basis = grades.ESCALATION_ON_OBSERVABLE_CONDITIONS.basis.lower()
    assert "repeated failed attempts" in basis
    assert "explicit" in basis
    assert "inactivity is dropped" in basis


def test_the_corrected_citations_hold():
    """Row 15 cites Hattie and Timperley and Shute, not Demszky; row 19 does not
    cite the disability-access source for consent; row 23 leads with
    Panickssery."""
    single = grades.SINGLE_TARGET_RESPONSE.basis
    assert "Hattie" in single and "Shute" in single
    assert "Demszky" not in single
    assert "ladner" not in grades.CONSENT_SEPARABLE_FROM_USE.basis.lower()
    judge = grades.JUDGE_INDEPENDENT_OF_GENERATOR.basis
    assert judge.index("Panickssery") < judge.index("Zheng")
    assert "raised the possibility" in judge


def test_the_wording_updates_are_in():
    """Row 2 names both grader pairs; row 3 gives the matched-pairs test; row 4
    prints both AUCs, never as an improvement, plus the beyond-the-score test."""
    assert "depends on the grader pair" in grades.LOWER_CONFIDENCE_ON_EVALUATIVE.basis
    fluency = grades.CONTENT_OVER_FLUENCY.basis
    assert "12 matched pairs" in fluency and "0.139" in fluency
    assert "0.046 to 0.245" in fluency
    assert "benchmark wide" not in fluency
    auc = grades.OVER_RELIANCE_SEPARABLE.basis
    assert "0.81" in auc and "0.882" in auc and "0.825" in auc and "0.929" in auc
    assert "Not an improvement" in auc
    assert "0.720" in auc and "0.905" in auc and ".0045" in auc
    assert "offline keyword rules were tested only on the authors' items" in grades.OVER_RELIANCE_SEPARABLE.limit


def test_every_graded_component_states_its_limit():
    """A limit for every row, including the direct ones. "Direct does not mean
    strong." """
    for c in grades.GRADED_COMPONENTS:
        assert c.limit.strip(), c.id
        assert c.basis.strip(), c.id
        assert c.cite.label.startswith("sec:"), c.id


def test_taxonomy_is_argued():
    assert grades.SEVEN_CATEGORY_TAXONOMY.grade is Grade.ARGUED
    for category in taxonomy.CATEGORIES:
        assert category.grade is Grade.ARGUED


def test_progression_is_argued():
    assert grades.FIVE_BAND_PROGRESSION.grade is Grade.ARGUED
    for band in progression.BANDS:
        assert band.grade is Grade.ARGUED


def test_the_originals_are_the_four_the_thesis_names_and_all_argued():
    """sec:framework - "Original to this thesis: taxonomy, progression, 22, 23
    (all Argued)." """
    assert set(grades.ORIGINAL_CONTRIBUTIONS) == {
        "seven_category_taxonomy",
        "five_band_progression",
        "same_task_revision_with_reason",
        "predicted_rating_beside_score",
    }
    for component_id in grades.ORIGINAL_CONTRIBUTIONS:
        assert grades.BY_ID[component_id].grade is Grade.ARGUED


def test_terminal_ladder_level_is_argued_even_though_the_ladder_is_transferred():
    assert grades.GRADUATED_LADDER.grade is Grade.TRANSFERRED
    assert ladder.LEVEL_4.grade is Grade.ARGUED
    for level in ladder.LEVELS[:-1]:
        assert level.grade is Grade.TRANSFERRED


def test_the_build_measurements_stay_direct():
    assert grades.SIX_DIMENSION_RUBRIC.grade is Grade.DIRECT
    assert grades.LOWER_CONFIDENCE_ON_EVALUATIVE.grade is Grade.DIRECT
    assert grades.OVER_RELIANCE_SEPARABLE.grade is Grade.DIRECT
    assert grades.CONTENT_OVER_FLUENCY.grade is Grade.DIRECT


def test_no_overall_weighted_kappa_is_invented():
    assert rubric.OVERALL_WEIGHTED_KAPPA is None


def test_every_policy_choice_declares_its_provenance():
    choices = policy.all_choices()
    assert choices, "policy modules must register their choices"
    for choice in choices:
        assert choice.thesis_says.strip(), choice.id
        assert choice.borrowed_from.strip(), choice.id
        assert choice.caveat.strip(), choice.id
        assert choice.status is policy.base.IMPLEMENTATION_CHOICE


def test_the_twenty_three_gaps_are_enumerated():
    """Eighteen before the redesign, minus the affect thresholds (the component
    was removed), plus four new ones: reason length, gate exit, gap display,
    generator model; plus two from the second review round: what counts as an
    unchanged prompt for evaluative escalation (D03), and what counts as a
    success for gating (D04)."""
    keys = [k for k, _ in policy.UNSPECIFIED_BY_THESIS]
    assert len(keys) == 24
    assert len(set(keys)) == 24
    assert "evaluative_escalation" in keys and "gating_success" in keys
    assert "affect_thresholds" not in keys
    for new in ("reason_min_length", "revision_gate_exit", "gap_display", "generator_model"):
        assert new in keys
    assert ("affect_thresholds" in dict(policy.base.CLOSED_BY_REMOVAL))


def test_each_new_gap_has_a_choice():
    ids = {c.id for c in policy.all_choices()}
    assert "revision.min_reason_chars" in ids
    assert "revision.gate_exit" in ids
    assert "calibration.show_gap_to_student" in ids
    assert "generator.model" in ids


def test_framework_never_imports_policy():
    """The transcription of the thesis must be readable without the choices
    mixed into it. The dependency runs one way."""
    import promptcoach_ref.framework as fw

    for name, module in vars(fw).items():
        if not inspect.ismodule(module):
            continue
        source = inspect.getsource(module)
        assert "from ..policy" not in source, name
        assert "import policy" not in source, name


def test_every_framework_constant_carries_a_section_label():
    """Citations point at section labels of the thesis, never at file:line."""
    cites = []
    cites += [c.cite for c in taxonomy.CATEGORIES]
    cites += [lv.cite for lv in ladder.LEVELS]
    cites += [b.cite for b in progression.BANDS]
    cites += [s.cite for s in sentinel.SIGNALS]
    cites += [c.cite for c in commitments.COMMITMENTS]
    cites += [c.cite for c in grades.GRADED_COMPONENTS]
    cites += [a.cite for a in classroom.AGGREGATES.values()]
    cites += [p.cite for p in classroom.ITEM_PAIRS.values()]
    cites += [rubric.CITE, revision.CITE]
    for cite in cites:
        assert cite.label in grades.SECTION_LABELS
        assert ".tex" not in str(cite)


def test_a_citation_cannot_name_a_file_or_an_unknown_label():
    with pytest.raises(ValueError):
        Cite("7_the_framework.tex", "264")
    with pytest.raises(ValueError):
        Cite("sec:does-not-exist")


def test_the_chapter_map_has_thirteen_chapters():
    assert sorted(set(grades.SECTION_LABELS.values()), key=int) == [
        str(n) for n in range(1, 14)
    ]


def test_layer_five_output_is_marked_as_not_from_the_thesis():
    from promptcoach_ref.framework import contracts

    assert contracts.ElicitOutput.THESIS_SPECIFIED is True
    assert contracts.MeasureOutput.THESIS_SPECIFIED is True
    assert contracts.DiagnoseOutput.THESIS_SPECIFIED is True
    assert contracts.RespondOutput.THESIS_SPECIFIED is True
    assert contracts.CalibrateOutput.THESIS_SPECIFIED is False
    assert contracts.CalibrateOutput.REQUIREMENT_PASSED_DOWNSTREAM is None


def test_no_layer_input_claims_to_be_specified():
    from promptcoach_ref.framework import contracts

    for cls in (
        contracts.ElicitInput,
        contracts.MeasureInput,
        contracts.DiagnoseInput,
        contracts.RespondInput,
        contracts.CalibrateInput,
    ):
        assert cls.THESIS_SPECIFIED is False, cls.__name__


def test_every_cited_label_exists_in_the_chapter_sources_when_present():
    """Checked against thesis/sections_v2/*.tex if that folder exists; skipped,
    and reported as skipped in TRACEABILITY.md, otherwise."""
    from promptcoach_ref import traceability

    status, missing = traceability.check_labels()
    if not traceability.SECTIONS_V2.is_dir():
        assert status == "skipped"
        pytest.skip("thesis/sections_v2 is not on disk")
    assert status == "checked"
    assert missing == [], f"labels cited but not defined: {missing}"


def test_the_label_check_finds_a_missing_label(tmp_path):
    from promptcoach_ref import traceability

    labels = sorted(traceability.cited_labels())
    (tmp_path / "all.tex").write_text(
        "".join(f"\\section{{x}}\\label{{{l}}}\n" for l in labels[1:]),
        encoding="utf-8",
    )
    status, missing = traceability.check_labels(tmp_path)
    assert status == "checked"
    assert missing == [labels[0]]
