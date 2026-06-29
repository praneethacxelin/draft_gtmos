import { useState, type FormEvent } from "react";
import { useLocation } from "wouter";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/hooks/useAuth";

export function Login() {
  const { login, register } = useAuth();
  const [, navigate] = useLocation();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      if (mode === "login") {
        await login(email.trim(), password);
      } else {
        await register(email.trim(), password);
      }
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <Card className="w-full max-w-sm p-6">
        <h1 className="mb-1 text-xl font-semibold">
          {mode === "login" ? "Sign in" : "Create account"}
        </h1>
        <p className="mb-6 text-sm text-muted-foreground">
          {mode === "login"
            ? "Sign in to access your GTM workspace."
            : "Create an account to keep your strategies private."}
        </p>
        <form onSubmit={onSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              data-testid="input-auth-email"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              data-testid="input-auth-password"
            />
            {mode === "register" && (
              <p className="text-xs text-muted-foreground">
                At least 8 characters.
              </p>
            )}
          </div>
          {error && (
            <p className="text-sm text-destructive" data-testid="text-auth-error">
              {error}
            </p>
          )}
          <Button
            type="submit"
            className="w-full"
            disabled={submitting}
            data-testid="button-auth-submit"
          >
            {submitting
              ? "Please wait…"
              : mode === "login"
                ? "Sign in"
                : "Create account"}
          </Button>
        </form>
        <div className="mt-4 text-center text-sm text-muted-foreground">
          {mode === "login" ? (
            <>
              No account?{" "}
              <button
                type="button"
                className="text-primary hover:underline"
                onClick={() => {
                  setMode("register");
                  setError(null);
                }}
                data-testid="button-auth-switch-register"
              >
                Create one
              </button>
            </>
          ) : (
            <>
              Already have an account?{" "}
              <button
                type="button"
                className="text-primary hover:underline"
                onClick={() => {
                  setMode("login");
                  setError(null);
                }}
                data-testid="button-auth-switch-login"
              >
                Sign in
              </button>
            </>
          )}
        </div>
      </Card>
    </div>
  );
}
