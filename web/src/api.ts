import type {
  AboutPayload,
  CycleResult,
  Framework,
  Health,
  PolicyPayload,
  SessionState,
  Task,
  Telemetry,
} from "./types";

async function get<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`${response.status} ${path}`);
  return response.json() as Promise<T>;
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
  });
  if (!response.ok) {
    // The server's own sentence, when it gave one - the reasoned-revision hold
    // (409) says what to do next, and that is what she should read.
    let detail = "";
    try {
      detail = (await response.json())?.detail ?? "";
    } catch {
      detail = "";
    }
    throw new ApiError(response.status, detail || `${response.status} ${path}`);
  }
  return response.json() as Promise<T>;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export const api = {
  framework: () => get<Framework>("/api/framework"),
  policy: () => get<PolicyPayload>("/api/policy"),
  about: () => get<AboutPayload>("/api/about"),
  tasks: () => get<Task[]>("/api/tasks"),
  health: () => get<Health>("/api/health"),
  telemetry: () => get<Telemetry>("/api/telemetry"),

  createSession: (body: {
    platform_use: boolean;
    research_participation: boolean;
    audio_retention: boolean;
    task_id?: string;
    require_reason?: boolean;
    show_gap?: boolean;
  }) => post<SessionState>("/api/session", body),

  setTask: (sid: string, taskId: string) =>
    post<SessionState>(`/api/session/${sid}/task/${taskId}`),

  submit: (
    sid: string,
    body: {
      stated_intent: string;
      prompt_text: string;
      intent_modality: string;
      transcript_reviewed: boolean;
      student_ms: number;
      parent_attempt_id?: string | null;
      asked_for_help?: boolean;
      /** 1 to 4, before she sees the output. Optional. */
      predicted_rating?: number | null;
      /** Why she changed it, on a revision of the same task. */
      revision_reason?: string | null;
      /** Ranges of prompt_text the interface inserted. */
      inserted_spans?: { start: number; end: number }[];
    },
  ) => post<CycleResult>(`/api/session/${sid}/submit`, body),
};
