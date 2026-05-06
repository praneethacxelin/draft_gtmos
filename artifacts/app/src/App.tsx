import { useEffect } from "react";
import { Switch, Route, Router as WouterRouter } from "wouter";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
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

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 5_000, refetchOnWindowFocus: false },
  },
});

function Router() {
  return (
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
  );
}

function App() {
  useEffect(() => {
    // Default to dark mode on first load if user hasn't chosen
    if (!localStorage.getItem("gtm.theme")) {
      document.documentElement.classList.add("dark");
    } else if (localStorage.getItem("gtm.theme") === "dark") {
      document.documentElement.classList.add("dark");
    }
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <WouterRouter base={import.meta.env.BASE_URL.replace(/\/$/, "")}>
          <AppShell>
            <Router />
          </AppShell>
        </WouterRouter>
        <Toaster />
      </TooltipProvider>
    </QueryClientProvider>
  );
}

export default App;
