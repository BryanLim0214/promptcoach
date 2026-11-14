"""The statistics that produced numbers now printed in the thesis.

Chapter 11 reports ICC(2,2), weighted kappa, a rank-based AUC and bootstrap
intervals computed by `eval/benchmark.py`. Those functions had no tests when
their output was written into the manuscript, which is the wrong order. These
check them against cases with known answers.

A wrong ICC here does not produce an error. It produces a plausible number in a
thesis, which is worse.
"""

from __future__ import annotations

import math
import statistics

import pytest

from eval.benchmark import (
    auc_mann_whitney,
    clustered_bootstrap_ci,
    icc_2_2,
    weighted_kappa,
)

pytestmark = pytest.mark.statistics


# --- ICC(2,2) -------------------------------------------------------------


def test_icc_is_one_for_identical_raters():
    pairs = [(1.0, 1.0), (2.0, 2.0), (3.0, 3.0), (4.0, 4.0), (2.5, 2.5)]
    assert icc_2_2(pairs) == pytest.approx(1.0, abs=1e-9)


def test_icc_is_below_one_for_a_constant_offset():
    """A rater who is always half a point high agrees on ordering but never on
    value.

    This is the test that caught the original implementation: it computed the
    consistency form and returned exactly 1.0 here, which would report perfect
    agreement between two graders that never once produced the same number.
    Absolute agreement must penalise the offset.
    """
    base = [1.0, 2.0, 3.0, 4.0, 2.0, 3.0]
    pairs = [(v, v + 0.5) for v in base]
    icc = icc_2_2(pairs)
    assert icc is not None
    assert 0.80 < icc < 1.0, icc


def test_absolute_agreement_is_lower_than_consistency_under_offset():
    """A sanity check on the direction of the correction."""
    base = [1.0, 2.0, 3.0, 4.0, 2.0, 3.0, 1.0, 4.0]
    unbiased = icc_2_2([(v, v) for v in base])
    offset = icc_2_2([(v, v + 0.5) for v in base])
    assert unbiased is not None and offset is not None
    assert offset < unbiased


def test_icc_collapses_when_the_second_rater_is_unrelated():
    pairs = [(1.0, 4.0), (2.0, 1.0), (3.0, 4.0), (4.0, 1.0), (1.0, 3.0), (4.0, 2.0)]
    icc = icc_2_2(pairs)
    assert icc is not None
    assert icc < 0.5


def test_icc_is_none_when_there_is_no_between_item_variance():
    """Every item scored the same by both raters. Perfect agreement and no
    variance to attribute it to - reporting 1.0 would be a lie."""
    assert icc_2_2([(3.0, 3.0)] * 6) is None


def test_icc_needs_at_least_three_pairs():
    assert icc_2_2([(1.0, 1.0), (2.0, 2.0)]) is None


# --- weighted kappa -------------------------------------------------------


def test_weighted_kappa_is_one_for_perfect_agreement():
    a = [1, 2, 3, 4, 1, 2, 3, 4]
    assert weighted_kappa(a, list(a)) == pytest.approx(1.0)


def test_weighted_kappa_is_zero_at_chance():
    """Every (i, j) cell filled exactly once, so the observed table *is* the
    table expected under independence. Kappa must come out at 0."""
    a = [i for i in (1, 2, 3, 4) for _ in range(4)]
    b = [j for _ in range(4) for j in (1, 2, 3, 4)]
    k = weighted_kappa(a, b)
    assert k is not None
    assert k == pytest.approx(0.0, abs=1e-9)


def test_weighted_kappa_goes_negative_when_agreement_is_worse_than_chance():
    a = [1, 1, 1, 1, 4, 4, 4, 4]
    b = [4, 4, 4, 4, 1, 1, 1, 1]
    k = weighted_kappa(a, b)
    assert k is not None
    assert k < 0


def test_weighted_kappa_penalises_distance_not_just_mismatch():
    """Linear weighting is the point: being off by three must cost more than
    being off by one, or the coefficient says nothing the exact-match rate does
    not already say."""
    truth = [1, 2, 3, 4] * 4
    near = [2, 3, 4, 3] * 4  # off by one
    far = [4, 4, 1, 1] * 4  # off by up to three
    k_near = weighted_kappa(truth, near)
    k_far = weighted_kappa(truth, far)
    assert k_near is not None and k_far is not None
    assert k_near > k_far


def test_weighted_kappa_rejects_out_of_range_values():
    assert weighted_kappa([1, 2, 9], [1, 2, 3]) is None


def test_weighted_kappa_rejects_mismatched_lengths():
    assert weighted_kappa([1, 2], [1]) is None


# --- AUC ------------------------------------------------------------------


def test_auc_is_one_for_perfect_separation():
    assert auc_mann_whitney([0.8, 0.9, 1.0], [0.1, 0.2, 0.3]) == pytest.approx(1.0)


def test_auc_is_zero_for_perfect_inversion():
    assert auc_mann_whitney([0.1, 0.2], [0.8, 0.9]) == pytest.approx(0.0)


def test_auc_is_half_when_the_classes_are_identical():
    """Ties count a half, which is what makes this come out at chance rather
    than at zero."""
    assert auc_mann_whitney([0.5] * 4, [0.5] * 4) == pytest.approx(0.5)


def test_auc_handles_partial_overlap():
    # 0.4 beats only 0.1; 0.6 beats 0.1 and 0.5; 0.9 beats all three.
    auc = auc_mann_whitney([0.4, 0.6, 0.9], [0.1, 0.5, 0.7])
    assert auc == pytest.approx((1 + 2 + 3) / 9)


def test_auc_is_none_for_an_empty_class():
    assert auc_mann_whitney([], [0.1]) is None
    assert auc_mann_whitney([0.1], []) is None


# --- clustered bootstrap --------------------------------------------------


def test_bootstrap_interval_brackets_the_point_estimate():
    clusters = {f"i{i}": [float(i % 5)] for i in range(30)}
    values = [v for vs in clusters.values() for v in vs]
    ci = clustered_bootstrap_ci(clusters, statistics.fmean)
    assert ci is not None
    assert ci[0] <= statistics.fmean(values) <= ci[1]


def test_bootstrap_interval_is_wider_with_fewer_clusters():
    """The whole reason for clustering: rerunning the same items must not buy a
    narrower interval."""
    many = {f"i{i}": [float(i % 7)] for i in range(40)}
    few = {f"i{i}": [float(i % 7)] * 3 for i in range(14)}
    wide = clustered_bootstrap_ci(few, statistics.fmean)
    narrow = clustered_bootstrap_ci(many, statistics.fmean)
    assert wide is not None and narrow is not None
    assert (wide[1] - wide[0]) > (narrow[1] - narrow[0])


def test_repeating_every_cluster_does_not_narrow_the_interval():
    """Three identical runs of the same items carry the same information as one.
    This is the property that made the first reported intervals too tight."""
    once = {f"i{i}": [float(i % 5)] for i in range(30)}
    thrice = {f"i{i}": [float(i % 5)] * 3 for i in range(30)}
    a = clustered_bootstrap_ci(once, statistics.fmean)
    b = clustered_bootstrap_ci(thrice, statistics.fmean)
    assert a is not None and b is not None
    width_a = a[1] - a[0]
    width_b = b[1] - b[0]
    assert math.isclose(width_a, width_b, rel_tol=0.05)


def test_bootstrap_is_deterministic():
    """A seeded bootstrap so a reported interval can be reproduced exactly."""
    clusters = {f"i{i}": [float(i % 6)] for i in range(25)}
    assert clustered_bootstrap_ci(clusters, statistics.fmean) == clustered_bootstrap_ci(
        clusters, statistics.fmean
    )


def test_bootstrap_declines_on_too_few_clusters():
    assert clustered_bootstrap_ci({"a": [1.0], "b": [2.0]}, statistics.fmean) is None


def test_bootstrap_survives_a_statistic_that_returns_none():
    """icc_2_2 returns None on degenerate resamples. Those are dropped, not
    counted as zero."""
    clusters = {f"i{i}": [(float(i % 4), float(i % 4))] for i in range(20)}
    ci = clustered_bootstrap_ci(clusters, icc_2_2)
    assert ci is None or (0.0 <= ci[0] <= ci[1] <= 1.0001)


# --- the reported numbers are internally consistent -----------------------


def test_percentage_of_span_uses_three_not_four():
    """sec:method records that the published paper
    divided by 4 in two places. 0.134 is 4.5% of the three-point span, not 3.4%
    of the scale maximum."""
    from promptcoach_ref.framework import rubric

    assert rubric.RUBRIC_SPAN == 3
    pct = 100 * rubric.PARAPHRASE_MEAN_ABSOLUTE_SHIFT / rubric.RUBRIC_SPAN
    assert pct == pytest.approx(4.5, abs=0.05)
    gap_pct = 100 * rubric.MEAN_GRADER_GAP_POINTS / rubric.RUBRIC_SPAN
    assert gap_pct == pytest.approx(8.7, abs=0.05)
