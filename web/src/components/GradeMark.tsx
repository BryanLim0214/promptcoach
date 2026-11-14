import type { Grade } from "../types";

const LABEL: Record<Grade, string> = {
  direct: "Direct",
  transferred: "Transferred",
  argued: "Argued",
};

/**
 * Evidence grade, carried by rule weight rather than colour.
 *
 * Solid holds on its own. Dashed was established somewhere else and is assumed
 * to carry. Dotted has never been tested at all. The three grades are ordinal,
 * and a line that gets less continuous is the honest way to show an ordinal
 * scale - it survives greyscale printing and colour blindness, which a red /
 * amber / green pill row does not.
 */
export function GradeMark({
  grade,
  showLabel = true,
}: {
  grade: Grade;
  showLabel?: boolean;
}) {
  return (
    <span
      className={`grade-${grade}`}
      style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
    >
      <hr className="grade-rule" aria-hidden="true" />
      {showLabel && (
        <span
          className="label"
          style={{ color: "currentColor", display: "inline" }}
        >
          {LABEL[grade]}
        </span>
      )}
      <span style={{ position: "absolute", left: -9999 }}>
        evidence grade: {LABEL[grade]}
      </span>
    </span>
  );
}
