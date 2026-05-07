import { useEffect, useState } from "react";
import { Switch, Route, Router as WouterRouter, useLocation } from "wouter";
import { QueryClient, QueryClientProvider, useQueryClient } from "@tanstack/react-query";
import {
  ClerkProvider,
  SignIn,
  SignUp,
  Show,
  RedirectToSignIn,
  useAuth,
  useClerk,
} from "@clerk/react";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AppShell } from "@/components/layout/AppShell";
import { Dashboard } from "@/pages/Dashboard";
import { StrategyList } from "@/pages/StrategyList";
import { StrategyDetail } from "@/pages/StrategyDetail";
import { Prospects } from "@/pages/Prospects";
import { Outreach } from "@/pages/Outreach";
import { Intelligence } from "@/pages/Intelligence";
import { Settings } from "@/pages/Settings";
import NotFound from "@/pages/not-found";
import { setAuthTokenGetter } from "@/lib/api";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 5_000, refetchOnWindowFocus: false },
  },
});

const clerkPubKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY as
  | string
  | undefined;

// For pk_live_ keys Clerk uses a satellite custom domain
// (e.g. clerk.gtmos.replit.app) which is not provisioned by Replit. We
// must route all Clerk traffic through our FastAPI proxy at /api/__clerk
// instead. Use an absolute URL (Clerk prefers this).
// pk_test_ keys hit the public *.clerk.accounts.dev FAPI directly and
// don't need (or want) a proxy in dev.
const clerkProxyUrl = clerkPubKey?.startsWith("pk_live_")
  ? `${typeof window !== "undefined" ? window.location.origin : ""}/api/__clerk`
  : undefined;

const basePath = import.meta.env.BASE_URL.replace(/\/$/, "");

function stripBase(p: string): string {
  return basePath && p.startsWith(basePath)
    ? p.slice(basePath.length) || "/"
    : p;
}

function ProtectedShell() {
  return (
    <>
      <Show when="signed-in">
        <AppShell>
          <Switch>
            <Route path="/" component={Dashboard} />
            <Route path="/strategy" component={StrategyList} />
            <Route path="/strategy/:id" component={StrategyDetail} />
            <Route path="/prospects" component={Prospects} />
            <Route path="/outreach" component={Outreach} />
            <Route path="/intelligence" component={Intelligence} />
            <Route path="/settings" component={Settings} />
            <Route component={NotFound} />
          </Switch>
        </AppShell>
      </Show>
      <Show when="signed-out">
        <RedirectToSignIn />
      </Show>
    </>
  );
}

function SignInPage() {
  return (
    <div className="flex min-h-[100dvh] items-center justify-center bg-background px-4 py-10">
      <SignIn
        routing="path"
        path={`${basePath}/sign-in`}
        signUpUrl={`${basePath}/sign-up`}
        afterSignInUrl={basePath || "/"}
        afterSignUpUrl={basePath || "/"}
      />
    </div>
  );
}

function SignUpPage() {
  return (
    <div className="flex min-h-[100dvh] items-center justify-center bg-background px-4 py-10">
      <SignUp
        routing="path"
        path={`${basePath}/sign-up`}
        signInUrl={`${basePath}/sign-in`}
        afterSignInUrl={basePath || "/"}
        afterSignUpUrl={basePath || "/"}
      />
    </div>
  );
}

function DebugBanner() {
  const { loaded } = useClerk();
  const { isLoaded, isSignedIn, userId } = useAuth();
  const [time, setTime] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setTime((x) => x + 1), 1000);
    return () => clearInterval(t);
  }, []);
  if (!new URLSearchParams(window.location.search).has("debug")) return null;
  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        background: "#000",
        color: "#0f0",
        padding: "8px 12px",
        font: "12px/1.4 monospace",
        zIndex: 99999,
        whiteSpace: "pre",
        borderBottom: "2px solid #0f0",
      }}
    >
      {`React: OK | t=${time}s | clerkLoaded=${loaded} | authLoaded=${isLoaded} | signedIn=${isSignedIn} | userId=${userId ?? "-"} | pubKey=${clerkPubKey?.slice(0, 16)}... | proxyUrl=${clerkProxyUrl ?? "(none)"} | path=${window.location.pathname}`}
    </div>
  );
}

function AuthBridge() {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  const qc = useQueryClient();

  useEffect(() => {
    setAuthTokenGetter(() => getToken());
    return () => setAuthTokenGetter(null);
  }, [getToken]);

  useEffect(() => {
    if (!isLoaded) return;
    if (isSignedIn) qc.invalidateQueries();
    else qc.clear();
  }, [isLoaded, isSignedIn, qc]);

  return null;
}

function ClerkRoutes() {
  const [, setLocation] = useLocation();
  return (
    <ClerkProvider
      publishableKey={clerkPubKey || ""}
      proxyUrl={clerkProxyUrl}
      signInUrl={`${basePath}/sign-in`}
      signUpUrl={`${basePath}/sign-up`}
      routerPush={(to) => setLocation(stripBase(to))}
      routerReplace={(to) => setLocation(stripBase(to), { replace: true })}
    >
      <QueryClientProvider client={queryClient}>
        <DebugBanner />
        <AuthBridge />
        <TooltipProvider>
          <Switch>
            <Route path="/sign-in/*?" component={SignInPage} />
            <Route path="/sign-up/*?" component={SignUpPage} />
            <Route component={ProtectedShell} />
          </Switch>
        </TooltipProvider>
        <Toaster />
      </QueryClientProvider>
    </ClerkProvider>
  );
}

function App() {
  useEffect(() => {
    if (!localStorage.getItem("gtm.theme")) {
      document.documentElement.classList.add("dark");
    } else if (localStorage.getItem("gtm.theme") === "dark") {
      document.documentElement.classList.add("dark");
    }
  }, []);

  if (!clerkPubKey) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background p-8 text-foreground">
        <div className="max-w-md rounded-lg border border-border p-6 text-sm">
          <div className="mb-2 font-semibold">Authentication not configured</div>
          <div className="text-muted-foreground">
            Missing <code>VITE_CLERK_PUBLISHABLE_KEY</code>. Set it in the
            environment to enable sign-in.
          </div>
        </div>
      </div>
    );
  }

  return (
    <WouterRouter base={basePath}>
      <ClerkRoutes />
    </WouterRouter>
  );
}

export default App;
