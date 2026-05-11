import { ReactNode } from "react";
import { Link, useLocation } from "wouter";
import {
  LayoutDashboard,
  Compass,
  Users,
  Send,
  Activity,
  BarChart2,
  BookOpen,
  Settings as SettingsIcon,
  ClipboardList,
  Sun,
  Moon,
  CircleDot,
} from "lucide-react";
import { useActiveStrategy } from "@/hooks/useActiveStrategy";
import { useTheme } from "@/hooks/useTheme";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/strategy", label: "Strategy", icon: Compass },
  { href: "/prospects", label: "Prospects", icon: Users },
  { href: "/outreach", label: "Outreach", icon: Send },
  { href: "/intelligence", label: "Intelligence", icon: Activity },
  { href: "/analytics", label: "Analytics", icon: BarChart2 },
  { href: "/help", label: "Help", icon: BookOpen },
  { href: "/settings", label: "Settings", icon: SettingsIcon },
  { href: "/audit", label: "Audit", icon: ClipboardList },
];

export function AppShell({ children }: { children: ReactNode }) {
  const [location] = useLocation();
  const { activeId, setActiveId, strategies } = useActiveStrategy();
  const { theme, toggle } = useTheme();

  return (
    <div className="flex min-h-screen w-full bg-background text-foreground">
      <aside className="flex w-64 shrink-0 flex-col border-r border-border bg-sidebar">
        <div className="flex items-center gap-2 px-5 pt-5 pb-4">
          <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
            <CircleDot className="h-4 w-4" />
          </div>
          <div>
            <div className="text-sm font-semibold tracking-tight">GTM Factory</div>
            <div className="text-[11px] uppercase tracking-widest text-muted-foreground">
              Operating Console
            </div>
          </div>
        </div>

        <div className="px-3 pb-3">
          <div className="mb-1 px-2 text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
            Active Strategy
          </div>
          <Select
            value={activeId ?? undefined}
            onValueChange={(v) => setActiveId(v)}
          >
            <SelectTrigger
              className="h-9 w-full bg-card text-xs"
              data-testid="select-active-strategy"
            >
              <SelectValue placeholder="No strategy selected" />
            </SelectTrigger>
            <SelectContent>
              {strategies.length === 0 ? (
                <div className="px-3 py-2 text-xs text-muted-foreground">
                  No strategies yet
                </div>
              ) : (
                strategies.map((s) => (
                  <SelectItem key={s.id} value={s.id}>
                    <span className="truncate">{s.product_name}</span>
                    <span className="ml-2 text-[10px] uppercase tracking-wide text-muted-foreground">
                      {s.status}
                    </span>
                  </SelectItem>
                ))
              )}
            </SelectContent>
          </Select>
        </div>

        <nav className="flex-1 space-y-0.5 px-3">
          {NAV.map((item) => {
            const active =
              item.href === "/"
                ? location === "/"
                : location.startsWith(item.href);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors hover-elevate",
                  active
                    ? "bg-sidebar-accent text-foreground"
                    : "text-muted-foreground hover:text-foreground",
                )}
                data-testid={`link-${item.label.toLowerCase()}`}
              >
                <Icon className="h-4 w-4" />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="border-t border-border p-3">
          <button
            onClick={toggle}
            className="flex w-full items-center justify-between rounded-md px-3 py-2 text-xs text-muted-foreground hover-elevate"
            data-testid="button-theme-toggle"
          >
            <span className="uppercase tracking-widest">
              {theme === "dark" ? "Dark" : "Light"} mode
            </span>
            {theme === "dark" ? (
              <Moon className="h-4 w-4" />
            ) : (
              <Sun className="h-4 w-4" />
            )}
          </button>
        </div>
      </aside>

      <main className="flex-1 overflow-x-hidden">
        <div className="mx-auto w-full max-w-[1400px] px-8 py-8">{children}</div>
      </main>
    </div>
  );
}
