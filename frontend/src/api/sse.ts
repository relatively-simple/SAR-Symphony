import type { ProgressEvent } from "./types";

export interface ExploreHandlers {
  onProgress: (ev: ProgressEvent) => void;
  onDone: (sessionId: string) => void;
  onError: (message: string, code?: string) => void;
}

export function startExploreSse(
  ra: string,
  dec: string,
  fov: number,
  preset: string | null | undefined,
  handlers: ExploreHandlers
): () => void {
  const params = new URLSearchParams({ ra, dec, fov: String(fov) });
  if (preset) params.set("preset", preset);

  const es = new EventSource(`/api/explore?${params.toString()}`);
  let finished = false;

  const stages = ["resolve", "query", "plan", "fetch", "process"] as const;
  for (const stage of stages) {
    es.addEventListener(stage, (evt) => {
      try {
        const data = JSON.parse((evt as MessageEvent).data) as ProgressEvent;
        handlers.onProgress(data);
      } catch {
        // ignore parse glitch
      }
    });
  }

  es.addEventListener("done", (evt) => {
    finished = true;
    es.close();
    const data = JSON.parse((evt as MessageEvent).data) as ProgressEvent;
    handlers.onProgress(data);
    if (data.session_id) {
      handlers.onDone(data.session_id);
    } else {
      handlers.onError("Missing session identifier from server.");
    }
  });

  es.addEventListener("error", (evt) => {
    if (finished) return;
    finished = true;
    es.close();
    try {
      const msgEvt = evt as MessageEvent;
      if (msgEvt.data) {
        const data = JSON.parse(msgEvt.data) as ProgressEvent;
        handlers.onError(data.message, data.error_code ?? undefined);
        return;
      }
    } catch {
      // network error fallback
    }
    handlers.onError("Connection to SAR Symphony server interrupted. Please retry.");
  });

  return () => {
    finished = true;
    es.close();
  };
}
