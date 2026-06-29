import { useEffect } from "react";
import { Switch, Route, Redirect, Router as WouterRouter } from "wouter";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "@/components/ui/toaster";
import { Toaster as SonnerToaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AppShell } from "@/components/layout/AppShell";
import { Dashboard } from "@/pages/Dashboard";
import { StrategyList } from "@/pages/StrategyList";
import { StrategyDetail } from "@/pages/StrategyDetail";
import { Prospects } from "@/pages/Prospects";
import { Outreach } from "@/pages/Outreach";
import { Intelligence } from "@/pages/Intelligence";
import { Settings } from "@/pages/Settings";
import { Help } from "@/pages/Help";
import NotFound from "@/pages/not-found";
import { AdminPage } from "@/pages/Admin";
import { Audit } from "@/pages/Audit";
import { Analytics } from "@/pages/Analytics";
import { Learnings } from "@/pages/Learnings";
import { Login } from "@/pages/Login";
import { AuthProvider, useAuth } from "@/hooks/useAuth";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 5_000, refetchOnWindowFocus: false },
  },
});

const basePath = import.meta.env.BASE_URL.replace(/\/$/, "");

/**
 * Gate that bounces to /login only when the server enforces auth
 * (AUTH_REQUIRED) and a request came back 401. In the default optional-auth
 * mode anonymous users keep full access.
 */
function RequireAuth({ children }: { children: React.ReactNode }) {
  const { loading, requiresLogin, isAuthenticated } = useAuth();
  if (loading) return null;
  if (requiresLogin && !isAuthenticated) {
    return <Redirect to="/login" />;
  }
  return <>{children}</>;
}

function AppRoutes() {
  return (
    <AppShell>
      <Switch>
        <Route path="/" component={Dashboard} />
        <Route path="/strategy" component={StrategyList} />
        <Route path="/strategy/:id" component={StrategyDetail} />
        <Route path="/prospects" component={Prospects} />
        <Route path="/outreach" component={Outreach} />
        <Route path="/intelligence" component={Intelligence} />
        <Route path="/learnings" component={Learnings} />
        <Route path="/help" component={Help} />
        <Route path="/settings" component={Settings} />
        <Route path="/audit" component={Audit} />
        <Route path="/analytics" component={Analytics} />
        <Route component={NotFound} />
      </Switch>
    </AppShell>
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

  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <WouterRouter base={basePath}>
          <AuthProvider>
            <Switch>
              <Route path="/login" component={Login} />
              <Route path="/admin/*?" component={AdminPage} />
              <Route>
                <RequireAuth>
                  <AppRoutes />
                </RequireAuth>
              </Route>
            </Switch>
          </AuthProvider>
        </WouterRouter>
        <Toaster />
        <SonnerToaster />
      </TooltipProvider>
    </QueryClientProvider>
  );
}

export default App;
