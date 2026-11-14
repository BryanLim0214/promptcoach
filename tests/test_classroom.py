"""The classroom aggregates are pinned, and non-comparable items never become change.

Two sources and nothing else: the raw Promptemon re-analysis
(`analysis/promptemon_aggregates.json`) and the PicPrompt rows of
`evidence/NUMBERS.md`. Where those files are on disk, the transcription is
checked against them; where they are not, the pinned values below still hold.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from promptcoach_ref.framework import classroom, grades
from promptcoach_ref.framework.classroom import NotComparable

pytestmark = pytest.mark.classroom

THESIS = Path(__file__).resolve().parents[2] / "UTPB_Thesis_Lim_Final"
RAW = THESIS / "analysis" / "promptemon_aggregates.json"
NUMBERS = THESIS / "evidence" / "NUMBERS.md"


# --- pinned values ----------------------------------------------------------


PINNED_AGGREGATES = {
    "promptemon.n_pre": 60,
    "promptemon.n_post": 60,
    "promptemon.matched_pairs": 53,
    "promptemon.attrition": {"pre_only": 6, "post_only": 5, "duplicate_name_keys": 1},
    "promptemon.grade_agree": 53,
    "promptemon.confidence_direction": {"up": 26, "down": 8, "same": 19},
    "promptemon.confidence_sign_test": {"p": 0.0029, "holm": 0.0058},
    "promptemon.feedback_helped": {"agreed": 44, "of": 60},
    "promptemon.combo_motivation": {"agreed": 28, "of": 60},
    "picprompt.n": 22,
    "picprompt.in_target_band": {"n": 4, "of": 22},
    "picprompt.post_confidence": {"mean": 2.91, "of": 4},
    "picprompt.fun": {"mean": 3.95, "of": 5, "lowest_rating": 3},
    "picprompt.recommend": {"n": 17, "of": 22},
    "picprompt.helped_most_theme": {"n": 6, "of_usable": 12},
    "picprompt.skill_task_lost": {"n": 14, "of": 22},
}

PINNED_COMPARABLE = {
    "promptemon.confidence": True,
    "promptemon.best_way": True,
    "promptemon.let_ai_decide": True,
    "promptemon.persona": False,
    "picprompt.prompt_knowledge": False,
    "picprompt.lowest_anchor": False,
    "picprompt.ai_knowledge": False,
    "picprompt.specificity_strategy": False,
    "picprompt.wrong_image_response": False,
    "picprompt.bedroom_prompt": False,
}


def test_aggregates_are_pinned():
    assert {k: a.value for k, a in classroom.AGGREGATES.items()} == PINNED_AGGREGATES


def test_every_pair_has_a_comparable_flag_and_it_is_pinned():
    assert classroom.COMPARABLE == PINNED_COMPARABLE
    for pair in classroom.ITEM_PAIRS.values():
        assert isinstance(pair.comparable, bool)
        assert pair.why.strip(), pair.id


def test_only_two_studies_supply_numbers():
    studies = {a.study for a in classroom.AGGREGATES.values()}
    studies |= {p.study for p in classroom.ITEM_PAIRS.values()}
    assert studies == {"promptemon", "picprompt"}


def test_each_number_cites_its_chapter_by_section_label():
    for a in classroom.AGGREGATES.values():
        assert a.cite.label in grades.SECTION_LABELS
        expected = "5" if a.study == "promptemon" else "4"
        assert a.cite.chapter == expected, a.id
        assert re.fullmatch(r"P[MP]-\d\d", a.numbers_id), a.id
    for p in classroom.ITEM_PAIRS.values():
        assert p.cite.chapter == ("5" if p.study == "promptemon" else "4"), p.id


def test_the_two_studies_total_eighty_two():
    assert classroom.STUDENTS_ACROSS_BOTH_STUDIES == 82
    assert (
        classroom.AGGREGATES["promptemon.n_pre"].value
        + classroom.AGGREGATES["picprompt.n"].value
        == 82
    )


# --- comparability ----------------------------------------------------------


@pytest.mark.parametrize(
    "pair_id", [k for k, v in PINNED_COMPARABLE.items() if not v]
)
def test_a_non_comparable_pair_can_never_be_presented_as_change(pair_id):
    with pytest.raises(NotComparable):
        classroom.present_change(pair_id)
    shown = classroom.present(pair_id)
    # Both values are available, side by side, with no difference and no
    # "pre"/"post" keys a caller could subtract by habit.
    assert shown["comparable"] is False
    assert "pre" not in shown and "post" not in shown
    assert "change" not in shown and "difference" not in shown
    assert shown["note"]


@pytest.mark.parametrize("pair_id", [k for k, v in PINNED_COMPARABLE.items() if v])
def test_a_comparable_pair_is_presented_with_its_caveat(pair_id):
    shown = classroom.present_change(pair_id)
    assert {"pre", "post", "note", "cite"} <= set(shown)


def test_the_persona_items_are_not_a_change():
    """Belief before, gained understanding after. NUMBERS: do not print as a
    change."""
    with pytest.raises(NotComparable):
        classroom.present_change("promptemon.persona")


def test_the_picprompt_wrong_image_item_is_not_a_decline():
    """R3 rests partly on it, and the thesis prints it with its caveat: the two
    items were worded differently. It is never a measured decline."""
    with pytest.raises(NotComparable):
        classroom.present_change("picprompt.wrong_image_response")
    assert "would do" in classroom.ITEM_PAIRS["picprompt.wrong_image_response"].why


def test_the_best_way_result_is_no_improvement_not_a_decline():
    pair = classroom.present_change("promptemon.best_way")
    assert pair["test"]["p"] == 0.2188


def test_self_report_is_marked():
    assert "never evidence" in classroom.SELF_REPORT_RULE
    assert classroom.AGGREGATES["promptemon.confidence_direction"].self_report is True
    assert classroom.AGGREGATES["picprompt.skill_task_lost"].self_report is False


def test_promptemon_students_are_never_said_to_have_written_prompts():
    assert "did not type" in classroom.PROMPTEMON_STUDENTS_DID_NOT_TYPE
    assert "not pre-registered" in classroom.PROMPTEMON_LABEL


# --- against the source files, when they are on disk -------------------------


def _dig(data, keys):
    for key in keys:
        data = data[key]
    return data


@pytest.mark.skipif(not RAW.exists(), reason="raw aggregates not on this machine")
def test_promptemon_values_match_the_raw_aggregates():
    raw = json.loads(RAW.read_text(encoding="utf-8"))

    assert raw["n_pre"] == classroom.AGGREGATES["promptemon.n_pre"].value
    assert raw["n_post"] == classroom.AGGREGATES["promptemon.n_post"].value
    assert raw["paired_n"] == classroom.AGGREGATES["promptemon.matched_pairs"].value
    att = raw["attrition"]
    assert classroom.AGGREGATES["promptemon.attrition"].value == {
        "pre_only": att["pre_without_post_match"],
        "post_only": att["post_without_pre_match"],
        "duplicate_name_keys": att["duplicate_name_keys"],
    }
    assert (
        raw["matched_pairs_grade_agree"]
        == classroom.AGGREGATES["promptemon.grade_agree"].value
    )
    cp = raw["confidence_paired"]
    assert classroom.AGGREGATES["promptemon.confidence_direction"].value == {
        "up": cp["up"],
        "down": cp["down"],
        "same": cp["same"],
    }
    assert classroom.AGGREGATES["promptemon.confidence_sign_test"].value == {
        "p": cp["sign_test_p"],
        "holm": raw["holm_adjusted"]["confidence_sign_test"],
    }
    fb = raw["feedback_helped"]
    assert classroom.AGGREGATES["promptemon.feedback_helped"].value == {
        "agreed": fb["4"] + fb["5"],
        "of": sum(fb.values()),
    }
    cm = raw["combo_motivation"]
    assert classroom.AGGREGATES["promptemon.combo_motivation"].value == {
        "agreed": cm["4"] + cm["5"],
        "of": sum(cm.values()),
    }

    for pair in classroom.ITEM_PAIRS.values():
        if pair.study != "promptemon":
            continue
        assert pair.raw_keys, pair.id
        pre_key, post_key = pair.raw_keys
        assert list(pair.pre.values())[0] == _dig(raw, pre_key), pair.id
        assert list(pair.post.values())[0] == _dig(raw, post_key), pair.id
    assert raw["best_way_pairs_with_both_answers"] == 52
    assert raw["best_way_paired"]["mcnemar_exact_p"] == 0.2188


@pytest.mark.skipif(not NUMBERS.exists(), reason="NUMBERS.md not on this machine")
def test_picprompt_values_appear_in_their_numbers_rows():
    rows = {}
    for line in NUMBERS.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\|\s*(PP-\d\d)\s*\|", line)
        if m:
            rows[m.group(1)] = line

    def printed(value) -> list[str]:
        if isinstance(value, dict):
            return [_fmt(v) for v in value.values()]
        return [_fmt(value)]

    for a in classroom.AGGREGATES.values():
        if a.study != "picprompt":
            continue
        row = rows[a.numbers_id]
        for token in printed(a.value):
            assert token in row, f"{a.id}: {token} not in {a.numbers_id}"
    for p in classroom.ITEM_PAIRS.values():
        if p.study != "picprompt":
            continue
        row = rows[p.numbers_id]
        for token in printed(p.pre) + printed(p.post):
            assert token in row, f"{p.id}: {token} not in {p.numbers_id}"


def _fmt(v) -> str:
    return str(v) if not isinstance(v, float) else f"{v:.2f}".rstrip("0").rstrip(".")


@pytest.mark.skipif(not NUMBERS.exists(), reason="NUMBERS.md not on this machine")
def test_the_withdrawn_list_matches_numbers_md():
    text = NUMBERS.read_text(encoding="utf-8")
    withdrawn = text[text.index("## 10. WITHDRAWN") :]
    for figure in ("40 of 51", "31.7", "46.7", "5 to 52"):
        assert figure in withdrawn
    assert "78%" in withdrawn
