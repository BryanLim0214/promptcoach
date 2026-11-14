import type { Level } from "../types";
import { GradeMark } from "./GradeMark";
import "./ladder.css";

/**
 * The four-level response ladder.
 *
 * Rungs above the current one are shown, not hidden, with what they would give
 * and what they would still leave her to do. Escalation should read as a
 * decision with a cost, not as a door that opens by itself.
 *
 * Level 4 carries its own grade. The ladder as a whole is Transferred from Build
 * 3; the worked contrast that replaces Build 3's worked solution is Argued, and
 * the thesis calls it "the framework's most exposed single claim". The interface
 * says so on the rung rather than in a footnote.
 */
export function Ladder({
  levels,
  issued,
  current,
}: {
  levels: Level[];
  issued: number[];
  current: number | null;
}) {
  return (
    <ol className="ladder" aria-label="Response ladder">
      {levels.map((lv) => {
        const done = issued.includes(lv.level);
        const active = current === lv.level;
        const state = active ? "active" : done ? "done" : "locked";
        return (
          <li key={lv.level} className={`rung is-${state}`} aria-current={active}>
            <div className="rung-mark" aria-hidden="true">
              <span className="rung-num">{lv.level}</span>
            </div>
            <div className="rung-body">
              <div className="rung-head">
                <p className="rung-gives">{lv.gives}</p>
                {lv.grade === "argued" && <GradeMark grade={lv.grade} />}
              </div>
              <p className="small quiet">
                <span className="label" style={{ display: "inline" }}>
                  she still
                </span>{" "}
                {lv.student_still_does}
              </p>
            </div>
            <span className="rung-state label">
              {active ? "issued" : done ? "used" : "not reached"}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
