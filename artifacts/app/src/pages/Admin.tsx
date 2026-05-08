import { useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiUrl } from "@/lib/api";

const TOKEN_KEY = "gtm.adminToken";

type StrategyRow = {
  id: string;
  product_name: string;
  description: string;
  target_market: string | null;
  status: string;
  created_at: string | null;
  owner: { user_id: string | null; email: string | null; is_admin: boolean };
};

async function adminFetch<T>(
  path: string,
  token: string,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(apiUrl(path), {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-Admin-Token": token,
      ...(init?.headers || {}),
    },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json() as Promise<T>;
}

function LoginForm({ onLogin }: { onLogin: (token: string) => void }) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(apiUrl("/admin/login"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });
      if (!res.ok) {
        const t = await res.text();
        throw new Error(t || res.statusText);
      }
      const { token } = (await res.json()) as { token: string };
      localStorage.setItem(TOKEN_KEY, token);
      onLogin(token);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-[100dvh] items-center justify-center bg-background px-4">
      <Card className="w-full max-w-sm border-card-border bg-card p-6">
        <div className="mb-4">
          <div className="text-xs uppercase tracking-widest text-muted-foreground">
            Internal
          </div>
          <h1 className="text-lg font-semibold">Admin sign-in</h1>
          <p className="mt-1 text-xs text-muted-foreground">
            View every strategy across every user.
          </p>
        </div>
        <form className="space-y-3" onSubmit={submit}>
          <div>
            <Label className="text-xs">Admin password</Label>
            <Input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoFocus
              data-testid="input-admin-password"
            />
          </div>
          {error && (
            <div className="rounded border border-destructive/50 bg-destructive/10 p-2 text-xs text-destructive">
              {error}
            </div>
          )}
          <Button
            type="submit"
            disabled={busy}
            className="w-full"
            data-testid="button-admin-login"
          >
            {busy ? "Signing in…" : "Sign in"}
          </Button>
        </form>
      </Card>
    </div>
  );
}

function AdminConsole({
  token,
  onLogout,
}: {
  token: string;
  onLogout: () => void;
}) {
  const [rows, setRows] = useState<StrategyRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    adminFetch<StrategyRow[]>("/admin/strategies", token)
      .then((data) => {
        if (!cancelled) setRows(data);
      })
      .catch((err) => {
        if (cancelled) return;
        const msg = err instanceof Error ? err.message : String(err);
        setError(msg);
        if (msg.toLowerCase().includes("token")) {
          localStorage.removeItem(TOKEN_KEY);
          onLogout();
        }
      });
    return () => {
      cancelled = true;
    };
  }, [token, onLogout]);

  return (
    <div className="min-h-[100dvh] bg-background p-6">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <div className="text-xs uppercase tracking-widest text-muted-foreground">
            Admin console
          </div>
          <h1 className="text-xl font-semibold">All strategies</h1>
          <p className="mt-1 text-xs text-muted-foreground">
            Read-only view across every user. {rows ? `${rows.length} total.` : ""}
          </p>
        </div>
        <Button
          variant="outline"
          onClick={() => {
            localStorage.removeItem(TOKEN_KEY);
            onLogout();
          }}
          data-testid="button-admin-logout"
        >
          Sign out
        </Button>
      </div>

      {error && (
        <Card className="border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </Card>
      )}

      {!rows && !error && (
        <div className="text-sm text-muted-foreground">Loading…</div>
      )}

      {rows && rows.length === 0 && (
        <div className="rounded border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
          No strategies in the database yet.
        </div>
      )}

      <div className="space-y-2">
        {rows?.map((r) => (
          <Card
            key={r.id}
            className="border-card-border bg-card p-4"
            data-testid={`row-admin-strategy-${r.id}`}
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0 flex-1">
                <div className="text-sm font-semibold">{r.product_name}</div>
                <div className="mt-1 line-clamp-2 text-xs text-muted-foreground">
                  {r.description}
                </div>
                {r.target_market && (
                  <div className="mt-2 text-xs">
                    <span className="text-muted-foreground">Target:</span>{" "}
                    {r.target_market}
                  </div>
                )}
              </div>
              <div className="text-right text-xs">
                <div className="font-mono text-muted-foreground">{r.status}</div>
                <div className="mt-1">
                  {r.owner.email || r.owner.user_id || "—"}
                  {r.owner.is_admin && (
                    <span className="ml-1 rounded bg-primary/20 px-1 py-0.5 text-[10px] uppercase text-primary">
                      admin
                    </span>
                  )}
                </div>
                {r.created_at && (
                  <div className="mt-1 text-muted-foreground">
                    {new Date(r.created_at).toLocaleString()}
                  </div>
                )}
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}

export function AdminPage() {
  const [token, setToken] = useState<string | null>(() =>
    typeof window !== "undefined" ? localStorage.getItem(TOKEN_KEY) : null,
  );

  if (!token) return <LoginForm onLogin={setToken} />;
  return <AdminConsole token={token} onLogout={() => setToken(null)} />;
}
