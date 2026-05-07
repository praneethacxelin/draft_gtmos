const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");

let tokenGetter: (() => Promise<string | null>) | null = null;

/**
 * Register the auth-token getter so apiFetch / streamSse attach a
 * Bearer token to every request. Called from the App once Clerk is
 * loaded.
 */
export function setAuthTokenGetter(fn: (() => Promise<string | null>) | null) {
  tokenGetter = fn;
}

async function authHeaders(): Promise<Record<string, string>> {
  if (!tokenGetter) return {};
  try {
    const token = await tokenGetter();
    return token ? { Authorization: `Bearer ${token}` } : {};
  } catch {
    return {};
  }
}

export function apiUrl(path: string): string {
  return `${BASE}${path.startsWith("/") ? path : `/${path}`}`;
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const url = apiUrl(path);
  const auth = await authHeaders();
  const res = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...auth,
      ...(init?.headers || {}),
    },
  });
  if (!res.ok) {
    const text = await res.text();
    let msg = text;
    try {
      const parsed = JSON.parse(text);
      msg = parsed.detail || parsed.message || text;
    } catch {}
    throw new Error(msg || res.statusText);
  }
  if (res.status === 204) return null as T;
  return res.json() as Promise<T>;
}

/**
 * POST to an SSE endpoint and resolve when the server emits the
 * `complete` event (or rejects on `error`). The final `stage_complete`
 * payload's `result` field is returned when present so callers can
 * still surface a value.
 */
export function streamSse<T = unknown>(
  path: string,
  onStage?: (stage: string, status: "start" | "complete") => void,
): Promise<T | null> {
  return new Promise((resolve, reject) => {
    const url = apiUrl(path);
    authHeaders()
      .then((auth) => fetch(url, { method: "POST", headers: { ...auth } }))
      .then(async (res) => {
        if (!res.ok || !res.body) {
          const text = await res.text().catch(() => "");
          reject(new Error(text || res.statusText));
          return;
        }
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buf = "";
        let lastResult: T | null = null;
        let currentEvent = "message";
        let dataLines: string[] = [];

        const flush = () => {
          if (!dataLines.length) return;
          const dataStr = dataLines.join("\n");
          dataLines = [];
          let parsed: { stage?: string; result?: T; message?: string } = {};
          try {
            parsed = JSON.parse(dataStr);
          } catch {}
          if (currentEvent === "stage_start" && parsed.stage) {
            onStage?.(parsed.stage, "start");
          } else if (currentEvent === "stage_complete") {
            if (parsed.stage) onStage?.(parsed.stage, "complete");
            if (parsed.result !== undefined) lastResult = parsed.result;
          } else if (currentEvent === "complete") {
            resolve(lastResult);
          } else if (currentEvent === "error") {
            reject(new Error(parsed.message || "Stream error"));
          }
        };

        while (true) {
          const { value, done } = await reader.read();
          if (done) {
            // Flush trailing event then resolve if we never saw "complete".
            flush();
            resolve(lastResult);
            return;
          }
          buf += decoder.decode(value, { stream: true });
          let nl: number;
          while ((nl = buf.indexOf("\n")) !== -1) {
            const line = buf.slice(0, nl).replace(/\r$/, "");
            buf = buf.slice(nl + 1);
            if (line === "") {
              flush();
              currentEvent = "message";
            } else if (line.startsWith("event:")) {
              currentEvent = line.slice(6).trim();
            } else if (line.startsWith("data:")) {
              dataLines.push(line.slice(5).trim());
            }
          }
        }
      })
      .catch(reject);
  });
}
