import { useEffect } from "react";
import { Switch, Route, Router as WouterRouter } from "wouter";
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

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 5_000, refetchOnWindowFocus: false },
  },
});

const basePath = import.meta.env.BASE_URL.replace(/\/$/, "");

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
          <Switch>
            <Route path="/admin/*?" component={AdminPage} />
            <Route component={AppRoutes} />
          </Switch>
        </WouterRouter>
        <Toaster />
        <SonnerToaster />
      </TooltipProvider>
    </QueryClientProvider>
  );
}

export default App;
