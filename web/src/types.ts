export type Grade = "direct" | "transferred" | "argued";
export type NeedBasis = "students" | "builds" | "argument";

export interface Dimension {
  id: string;
  name: string;
  measures: string;
  one_against_four: string;
  kind: "planning" | "evaluative";
  weighted_kappa: number;
  within_one_pct: number;
  cite: string;
}

export interface Category {
  id: string;
  name: string;
  student_did: string;
  derived_from: string;
  response_implied: string;
  detectable_from: "prompt_text" | "paired_spoken_record" | "session_history";
  paired_dimension: string;
  grade: Grade;
  cite: string;
}

export interface Level {
  level: number;
  gives: string;
  student_still_does: string;
  grade: Grade;
  cite: string;
}

export interface Band {
  band: number;
  axis: string;
  requires: string;
  example: string;
  dimensions_named_in_task: boolean | null;
  grade: Grade;
  cite: string;
}

export interface GradedComponent {
  id: string;
  name: string;
  grade: Grade;
  need: NeedBasis;
  /** Display text for `need` ("User studies", "Builds", "Argument"). */
  need_label: string;
  requirement: string;
  basis: string;
  limit: string;
  cite: string;
}

export interface Framework {
  dimensions: Dimension[];
  scale: { min: number; max: number; span: number };
  reliability: {
    overall_icc: number;
    overall_weighted_kappa: number | null;
    paraphrase_shift: number;
    mean_grader_gap: number;
    latency_mean_s: number;
    latency_p95_s: number;
    caveat: string;
    third_bar: string;
    shared_prior: string;
    expires: string;
  };
  taxonomy: Category[];
  taxonomy_notes: Record<string, string>;
  ladder: Level[];
  ladder_notes: Record<string, string>;
  bands: Band[];
  band_notes: {
    axis_join: number[];
    not_commensurable: string;
    band_1_argument: string;
    why_4_and_5: string;
  };
  sentinel: {
    signals: {
      id: string;
      name: string;
      detects: string;
      derives_category: string;
    }[];
    auc: number;
    cross_model_agreement: number;
    one_signal: string;
    thin_basis: string;
    routing_rule: string;
  };
  commitments: {
    id: string;
    name: string;
    text: string;
    grade: Grade;
    cite: string;
  }[];
  prohibitions: Record<string, string>;
  non_transfers: Record<string, string>;
  grades: {
    definitions: Record<Grade, string>;
    need_definitions: Record<NeedBasis, string>;
    need_labels: Record<NeedBasis, string>;
    counts: Record<Grade, number>;
    need_counts: Record<NeedBasis, number>;
    components: GradedComponent[];
    originals: string[];
    removed: Record<string, { why: string; cite: string }>;
  };
}

export interface Choice {
  id: string;
  value: unknown;
  thesis_says: string;
  borrowed_from: string;
  caveat: string;
}

export interface PolicyPayload {
  choices: Choice[];
  unspecified: { id: string; note: string }[];
  closed_by_removal: { id: string; note: string }[];
}

export interface Task {
  id: string;
  band: number;
  topic?: string;
  scenario: string;
  protected_judgment: string;
  named_dimensions: string[];
  provided_model_output: string;
  reading_load?: string;
  from_thesis: boolean;
}

export interface DimensionScore {
  dimension_id: string;
  value: number | null;
  confidence: number;
  evidence_span: string | null;
  unable_to_score: boolean;
  span_verified: boolean;
  evaluative: boolean;
}

export interface Agreement {
  scorer_a: string;
  scorer_b: string;
  different_organisations: boolean;
  per_dimension_gap: Record<string, number>;
  mean_gap: number;
  caveat: string;
}

export interface Assignment {
  category: string;
  rank: number;
  confidence: number;
  trigger: string;
  overlaps_with: string[];
}

export interface CycleResult {
  stopped_at: "elicit" | "measure" | "diagnose" | "respond" | "calibrate";
  clarification: string | null;
  elicit: {
    record: {
      attempt_id: string;
      stated_intent: string;
      prompt_text: string;
      intent_modality: string;
      predicted_rating: number | null;
      revision_reason: string | null;
      inserted_spans: { start: number; end: number }[];
    } | null;
    clarification_required: string | null;
  };
  measure: {
    scores: Record<string, DimensionScore>;
    overall: number | null;
    agreement: Agreement | null;
    failure_reason: string | null;
    routing: string;
    judge_model: string;
    generator_model: string;
    judge_independent_of_generator: boolean;
    excluded_inserted_chars: number;
  } | null;
  diagnose: {
    assignments: Assignment[];
    target: string | null;
    insufficient_evidence: boolean;
    reason_trace: string[];
  } | null;
  respond: {
    level: number;
    target: string;
    text: string;
    expected_action: string;
    used_template_floor: boolean;
    selection_reason: string;
  } | null;
  calibrate: {
    band: number;
    band_changed: boolean;
    crossed_axis_join: boolean;
    reason: string;
    paired_delta: number | null;
    unpaired_deltas: Record<string, number>;
    pairing_strictness: string;
    sentinel: Record<string, number>;
    /** Which detector produced `sentinel`: the model-based one (live), the
     * offline keyword stand-in (never benchmarked), or none and why. */
    sentinel_source: string;
    next_task_id: string | null;
    calibration_gap: number | null;
    predicted_rating: number | null;
    measured_overall: number | null;
    revision_pending: boolean;
  } | null;
  /** Hers only; the teacher route never carries it. */
  calibration: {
    predicted_rating: number | null;
    measured_overall: number | null;
    gap: number | null;
    visible: boolean;
  };
  revision_pending: boolean;
  /** What happened to the help cycle on this attempt (opened, still open,
   * closed and why), or null. */
  help_cycle: string | null;
  /** What her prompt actually produced. */
  answer: Answer | null;
  /** The answer the prompt before this one produced, for side-by-side. */
  previous_answer: Answer | null;
  previous_prompt: string | null;
  trace: TraceStep[];
  state: SessionState;
}

export interface Answer {
  text: string;
  source: string;
  /** True when assembled locally rather than generated by a model. */
  scripted: boolean;
  latency_ms: number;
}

export interface TraceStep {
  layer: string;
  contract: string | null;
  contract_is_from_thesis: boolean;
  cite: string;
  component: string;
  grade: Grade;
  grade_basis: string;
  grade_limit: string;
  output: unknown;
}

export interface SessionState {
  session_id: string;
  band: number;
  task_id: string;
  task: Task;
  levels_issued: number[];
  attempts: number;
  revision_pending: boolean;
  require_reason: boolean;
  show_gap: boolean;
  generator: string | null;
  consent: {
    platform_use: boolean;
    research_participation: boolean;
    audio_retention: boolean;
  };
}

export interface AboutPayload {
  title: string;
  thesis_statement: Passage;
  requirements: { id: string; requirement: string; strength: string }[];
  research_questions: string[];
  scope: Passage;
  why_the_boundary: Passage;
  why_input_side: Passage;
  where_the_rubric_comes_from: Passage;
  threats: Passage[];
  remaining: string[];
  conclusion: Passage;
  shows: string;
  does_not_show: string;
}

export interface Passage {
  chapter: string;
  label: string;
  heading: string;
  text: string;
}

export interface TierStat {
  n: number;
  n_items?: number;
  mean: number | null;
  ci: [number, number] | null;
}

export interface Telemetry {
  reported: {
    source: string;
    overall_icc: number;
    mean_grader_gap: number;
    paraphrase_shift: number;
    sentinel_auc: number;
    sentinel_agreement: number;
    latency_mean_s: number;
    latency_p95_s: number;
    dimensions: {
      id: string;
      name: string;
      kappa: number;
      within_one: number;
      kind: string;
    }[];
    tiers: Record<string, number>;
    caveat: string;
  };
  measured: {
    source: string;
    not_cross_vendor: string;
    n_items: number;
    n_runs: number;
    overall_icc: number | null;
    overall_icc_ci: [number, number] | null;
    mean_grader_gap: number | null;
    mean_grader_gap_ci: [number, number] | null;
    paraphrase_shift: number | null;
    paraphrase_shift_ci: [number, number] | null;
    sentinel: {
      n_high: number;
      n_low: number;
      high_mean: number | null;
      low_mean: number | null;
      auc: number | null;
      per_signal: Record<
        string,
        { name: string; fired_on_high_risk: number; of: number }
      >;
    } | null;
    tiers: Record<string, TierStat>;
    stability: Record<
      string,
      { min: number | null; max: number | null; range: number | null }
    >;
    per_run: { run: number; icc: number | null; paraphrase: number | null; auc: number | null }[];
    ensemble_spread: number | null;
    dimensions: {
      id: string;
      name: string;
      kappa: number | null;
      exact: number | null;
      within_one: number | null;
      kind: string;
    }[];
  } | null;
  live: {
    engine: string;
    organisation: string;
    calls: number;
    errors: Record<string, number>;
    input_tokens: number;
    output_tokens: number;
    latency_mean_ms: number | null;
    latency_p95_ms: number | null;
    latency_max_ms: number | null;
    latency_median_ms?: number;
    latencies_ms: number[];
  };
  budget: {
    pipeline_mean_s: number;
    pipeline_p95_s: number;
    reference_s: number;
    note: string;
  };
  landis_koch: { from: number; to: number; label: string }[];
}

export interface Health {
  engine: string;
  organisation: string;
  comparator: string | null;
  generator: string;
  judge_independent_of_generator: boolean;
  cross_model: boolean;
  offline: boolean;
  no_students: string;
}
