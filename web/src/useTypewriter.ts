import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Type a string into a setter, character by character.
 *
 * Two things it has to get right.
 *
 * It writes into the same state the real textarea reads, so the field being
 * filled is the field a student would fill. Nothing is faked into a display-only
 * element.
 *
 * It honours `prefers-reduced-motion` by filling instantly, and it can be
 * skipped mid-run. Watching a machine type is charming once and tiresome the
 * second time, and a viewer who has seen it should never have to sit through it
 * again.
 */
export function useTypewriter(setter: (value: string) => void) {
  const [typing, setTyping] = useState(false);
  const timer = useRef<number | null>(null);
  const target = useRef("");
  const done = useRef<(() => void) | null>(null);

  const clear = () => {
    if (timer.current !== null) {
      window.clearTimeout(timer.current);
      timer.current = null;
    }
  };

  const finish = useCallback(() => {
    clear();
    setter(target.current);
    setTyping(false);
    done.current?.();
    done.current = null;
  }, [setter]);

  const type = useCallback(
    (text: string, onDone?: () => void) => {
      clear();
      target.current = text;
      done.current = onDone ?? null;

      const reduced = window.matchMedia(
        "(prefers-reduced-motion: reduce)",
      ).matches;
      if (reduced) {
        finish();
        return;
      }

      setTyping(true);
      let i = 0;
      const tick = () => {
        i += 1;
        setter(text.slice(0, i));
        if (i >= text.length) {
          setTyping(false);
          done.current?.();
          done.current = null;
          return;
        }
        // Slightly uneven, and slower after punctuation. Perfectly even typing
        // reads as a progress bar rather than as someone writing.
        const ch = text[i - 1];
        const delay = ch === "," || ch === "." ? 160 : 14 + Math.random() * 18;
        timer.current = window.setTimeout(tick, delay);
      };
      timer.current = window.setTimeout(tick, 120);
    },
    [setter, finish],
  );

  useEffect(() => clear, []);

  return { type, skip: finish, typing };
}
