import { Popover } from "radix-ui";
import type { ReactNode } from "react";
import { GradeMark } from "./GradeMark";
import type { Grade } from "../types";

/**
 * A citation into the manuscript, or a marker that a value is ours.
 *
 * Every number this interface renders is one of two things: transcribed from the
 * thesis, or chosen by this implementation because the thesis leaves it open.
 * Those look different here on purpose - `source="thesis"` shows a chapter
 * reference and a grade, `source="policy"` shows the passage proving the thesis
 * left the value open, where the number came from, and the caveat that goes with
 * relying on it.
 */
export function Cite({
  label,
  source,
  cite,
  grade,
  children,
}: {
  label: string;
  source: "thesis" | "policy";
  cite?: string;
  grade?: Grade;
  children: ReactNode;
}) {
  return (
    <Popover.Root>
      <Popover.Trigger asChild>
        <button
          className="cite-btn"
          aria-label={`${
            source === "thesis" ? "Thesis citation" : "Implementation choice"
          }: ${label}`}
        >
          {source === "thesis" ? cite ?? label : "implementation choice"}
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          className="popover"
          sideOffset={6}
          collisionPadding={16}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "baseline",
              gap: 12,
              marginBottom: 8,
            }}
          >
            <span className="label">
              {source === "thesis" ? "From the thesis" : "Not in the thesis"}
            </span>
            {grade && <GradeMark grade={grade} />}
          </div>
          {children}
          {cite && source === "thesis" && (
            <p
              className="small faint"
              style={{ marginTop: 10, fontFamily: "var(--face-artifact)" }}
            >
              {cite}
            </p>
          )}
          <Popover.Arrow style={{ fill: "var(--rule-strong)" }} />
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
