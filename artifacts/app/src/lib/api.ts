const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");

const TOKEN_KEY = "gtm.auth.token";
let authToken: string | null =
  typeof localStorage !== "undefined" ? localStorage.getItem(TOKEN_KEY) : null;
let unauthorizedHandler: (() => void) | null = null;

/** Store (or clear) the bearer token used for authenticated requests. */
export function setAuthToken(token: string | null) {
  authToken = token;
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* ignore storage errors (private mode, etc.) */
  }
}

export function getAuthToken(): string | null {
  return authToken;
}

/** Register a callback invoked when the API returns 401 (e.g. to log out). */
export function setUnauthorizedHandler(fn: (() => void) | null) {
  unauthorizedHandler = fn;
}

function authHeaders(): Record<string, string> {
  return authToken ? { Authorization: `Bearer ${authToken}` } : {};
}

/**
 * Backwards-compatible no-op kept for older imports. Prefer
 * {@link setAuthToken}.
 */
export function setAuthTokenGetter(
  _fn: (() => Promise<string | null>) | null,
) {
  // no-op
}

export function apiUrl(path: string): string {
  return `${BASE}${path.startsWith("/") ? path : `/${path}`}`;
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const url = apiUrl(path);
  const res = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...(init?.headers || {}),
    },
  });
  if (!res.ok) {
    if (res.status === 401) {
      unauthorizedHandler?.();
    }
    const text = await res.text();
    let msg = text;
    let parsed: { detail?: string; message?: string; integration?: string; retry_after_seconds?: number } = {};
    try {
      parsed = JSON.parse(text);
      msg = parsed.detail || parsed.message || text;
    } catch {}
    if (res.status === 429) {
      const integ = parsed.integration ? ` (${parsed.integration})` : "";
      const retry = parsed.retry_after_seconds ? ` Retry in ~${parsed.retry_after_seconds}s.` : "";
      const friendly = `Free-tier rate limit hit${integ}.${retry}`;
      try {
        const { toast } = await import("sonner");
        toast.error(friendly);
      } catch {}
      throw new Error(friendly);
    }
    throw new Error(msg || res.statusText);
  }
  if (res.status === 204) return null as T;
  return res.json() as Promise<T>;
}

/**
 * POST to an SSE endpoint and resolve when the server emits the
 * `complete` event (or rejects on `error`). The final `stage_complete`
 * payload's `result` field is returned when present.
 */
export function streamSse<T = unknown>(
  path: string,
  onStage?: (stage: string, status: "start" | "complete") => void,
  body?: unknown,
): Promise<T | null> {
  return new Promise((resolve, reject) => {
    const url = apiUrl(path);
    fetch(url, {
      method: "POST",
      headers: {
        ...authHeaders(),
        ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
      },
      ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
    })
      .then(async (res) => {
        if (!res.ok || !res.body) {
          if (res.status === 401) {
            unauthorizedHandler?.();
          }
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
          let parsed: {
            stage?: string;
            result?: T;
            message?: string;
            status?: number;
            integration?: string;
            retry_after_seconds?: number;
          } = {};
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
            if (parsed.status === 429) {
              const integ = parsed.integration ? ` (${parsed.integration})` : "";
              const retry = parsed.retry_after_seconds
                ? ` Retry in ~${parsed.retry_after_seconds}s.`
                : "";
              const friendly = `Free-tier rate limit hit${integ}.${retry}`;
              import("sonner").then(({ toast }) => toast.error(friendly)).catch(() => {});
              reject(new Error(friendly));
            } else {
              reject(new Error(parsed.message || "Stream error"));
            }
          }
        };

        while (true) {
          const { value, done } = await reader.read();
          if (done) {
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
