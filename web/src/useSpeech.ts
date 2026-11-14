import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Speech capture, with the typed path always available beside it.
 *
 * Layer 1's diagnostic value comes from a spoken plan sitting next to a typed
 * prompt. But 7:323 makes the fallback a commitment, not a courtesy: "a student
 * who declines audio capture must retain a usable path through the system", and
 * 3:195 adds that the fallback "degrades the diagnosis rather than blocking it".
 *
 * So `supported` being false is not an error state. It changes the modality on
 * the record - which Layer 3 reads and reports - and nothing else.
 *
 * The audio itself is never retained. The browser produces a transcript and the
 * transcript is the artifact; there is no MediaRecorder here and nothing is
 * uploaded. 3:195 - "the transcript and not the audio is the artifact, audio
 * should be discarded once transcribed".
 */

interface SpeechRecognitionLike extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start(): void;
  stop(): void;
  onresult: ((event: any) => void) | null;
  onerror: ((event: any) => void) | null;
  onend: (() => void) | null;
}

function constructor(): (new () => SpeechRecognitionLike) | null {
  const w = window as any;
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export function useSpeech(onTranscript: (text: string) => void) {
  const [listening, setListening] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const ref = useRef<SpeechRecognitionLike | null>(null);
  const supported = constructor() !== null;

  const stop = useCallback(() => {
    ref.current?.stop();
    setListening(false);
  }, []);

  const start = useCallback(() => {
    const Ctor = constructor();
    if (!Ctor) {
      setError("This browser cannot capture speech. Type it instead.");
      return;
    }
    setError(null);
    const rec = new Ctor();
    rec.continuous = true;
    rec.interimResults = true;
    rec.lang = navigator.language || "en-US";

    let final = "";
    rec.onresult = (event: any) => {
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const chunk = event.results[i][0].transcript;
        if (event.results[i].isFinal) final += chunk;
        else interim += chunk;
      }
      onTranscript((final + interim).trim());
    };
    rec.onerror = (event: any) => {
      setError(
        event?.error === "not-allowed"
          ? "The microphone was declined. Type what you were trying to do instead — the loop still works."
          : "Speech capture stopped. Type it instead.",
      );
      setListening(false);
    };
    rec.onend = () => setListening(false);

    ref.current = rec;
    rec.start();
    setListening(true);
  }, [onTranscript]);

  useEffect(() => () => ref.current?.stop(), []);

  return { supported, listening, error, start, stop };
}
