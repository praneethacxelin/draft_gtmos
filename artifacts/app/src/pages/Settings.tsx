import { useState, useEffect } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/PageHeader";
import {
  useIntegrations,
  useUpdateIntegration,
  useTestIntegration,
  useFetchLimits,
  useUpdateFetchLimits,
  Integration,
} from "@/hooks/useSettings";
import { Plug, Check, AlertCircle, KeyRound, UserRound, Gauge, Wifi, WifiOff } from "lucide-react";

export function Settings() {
  const { data: integrations } = useIntegrations();

  return (
    <>
      <PageHeader
        eyebrow="Configuration"
        title="Integrations"
        subtitle="Plug in optional tools to upgrade GTM Factory from AI demo data to real signals and outreach. Keys are encrypted in the database."
      />

      <AccountCard />

      <FetchLimitsCard />

      <Card className="mb-6 border-card-border bg-card p-4">
        <div className="flex items-start gap-3">
          <Plug className="mt-0.5 h-4 w-4 text-primary" />
          <div className="text-xs text-muted-foreground">
            <strong className="text-foreground">No keys required.</strong> The
            app works end-to-end without any of these — every stage falls back
            to AI-generated demo data clearly badged as such. Add keys to graduate
            from simulation to live signals, real lead enrichment, and live
            email orchestration.
          </div>
        </div>
      </Card>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {integrations?.map((it) => (
          <IntegrationCard key={it.name} integration={it} />
        ))}
      </div>
    </>
  );
}

function AccountCard() {
  return (
    <Card className="mb-6 border-card-border bg-card p-5" data-testid="card-account">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/15 text-primary">
          <UserRound className="h-5 w-5" />
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-widest text-muted-foreground">
            Mode
          </div>
          <div className="text-sm font-semibold" data-testid="text-account-name">
            Public — no sign-in required
          </div>
          <div className="text-xs text-muted-foreground">
            Authentication has been disabled. All visitors share the same
            workspace and see all strategies.
          </div>
        </div>
      </div>
    </Card>
  );
}

function FetchLimitsCard() {
  const { data } = useFetchLimits();
  const update = useUpdateFetchLimits();
  const [draft, setDraft] = useState<{ leads_per_run: number; signals_per_account: number; market_sizing_results: number } | null>(null);

  useEffect(() => {
    if (data && !draft) setDraft(data.limits);
  }, [data, draft]);

  if (!data || !draft) return null;
  const fields: { key: keyof typeof draft; label: string; help: string }[] = [
    { key: "leads_per_run", label: "Leads per run", help: "How many contacts a Discover-leads click pulls (Apollo or AI demo)." },
    { key: "signals_per_account", label: "Signals per account", help: "Hard cap on SerpAPI signals persisted per account per run (split across funding + hiring queries)." },
    { key: "market_sizing_results", label: "Market sizing results", help: "How many SerpAPI snippets feed the TAM/SAM/SOM prompt." },
  ];

  return (
    <Card className="mb-6 border-card-border bg-card p-5" data-testid="card-fetch-limits">
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/15 text-primary">
          <Gauge className="h-5 w-5" />
        </div>
        <div className="flex-1">
          <div className="text-[10px] uppercase tracking-widest text-muted-foreground">Fetch caps</div>
          <div className="text-sm font-semibold">Per-deployment fetch limits</div>
          <div className="text-xs text-muted-foreground">
            Soft caps that protect your free-tier API quotas. Each agent run can also be overridden per click.
          </div>
        </div>
      </div>
      <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-3">
        {fields.map((f) => (
          <div key={f.key}>
            <Label className="text-xs">
              {f.label}
              <span className="ml-1 text-muted-foreground">
                (1–{data.maximums[f.key]})
              </span>
            </Label>
            <div className="flex items-center gap-3" data-testid={`slider-fetch-${f.key}`}>
              <Slider
                min={1}
                max={data.maximums[f.key]}
                step={1}
                value={[draft[f.key]]}
                onValueChange={(v) =>
                  setDraft({ ...draft, [f.key]: Math.max(1, Math.min(data.maximums[f.key], v[0] ?? 1)) })
                }
                className="flex-1"
              />
              <span className="w-10 text-right font-mono text-sm tabular-nums">{draft[f.key]}</span>
            </div>
            <div className="mt-1 text-[11px] text-muted-foreground">{f.help}</div>
          </div>
        ))}
      </div>
      <div className="mt-3 flex items-center justify-end gap-2">
        <Button
          size="sm"
          variant="secondary"
          onClick={() => setDraft(data.defaults)}
          data-testid="button-fetch-defaults"
        >
          Reset defaults
        </Button>
        <Button
          size="sm"
          disabled={update.isPending}
          onClick={() => update.mutate(draft)}
          data-testid="button-fetch-save"
        >
          {update.isPending ? "Saving…" : "Save limits"}
        </Button>
      </div>
    </Card>
  );
}

function LiveBadge({ integration }: { integration: Integration }) {
  if (!integration.is_connected) {
    return (
      <span className="inline-flex items-center gap-1 rounded bg-muted px-1.5 py-0.5 text-[10px] uppercase tracking-widest text-muted-foreground">
        <WifiOff className="h-2.5 w-2.5" /> Not configured
      </span>
    );
  }
  if (integration.is_enabled) {
    return (
      <span className="inline-flex items-center gap-1 rounded bg-primary/15 px-1.5 py-0.5 text-[10px] uppercase tracking-widest text-primary">
        <Wifi className="h-2.5 w-2.5" /> Live
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded bg-amber-500/15 px-1.5 py-0.5 text-[10px] uppercase tracking-widest text-amber-400">
      <WifiOff className="h-2.5 w-2.5" /> Disabled
    </span>
  );
}

function IntegrationCard({ integration }: { integration: Integration }) {
  const [key, setKey] = useState("");
  const [enabled, setEnabled] = useState(integration.is_enabled);
  const update = useUpdateIntegration();
  const test = useTestIntegration();

  useEffect(() => {
    setEnabled(integration.is_enabled);
  }, [integration.is_enabled]);

  return (
    <Card
      className="border-card-border bg-card p-5"
      data-testid={`integration-${integration.name}`}
    >
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <KeyRound className="h-4 w-4 text-primary" />
            <div className="text-sm font-semibold">{integration.display_name}</div>
            <LiveBadge integration={integration} />
          </div>
          <div className="mt-1 max-w-md text-xs text-muted-foreground">
            {integration.description}
          </div>
          {integration.is_connected && integration.key_last_four && (
            <div className="mt-1.5 flex items-center gap-1.5">
              <span className="font-mono text-[11px] text-muted-foreground tracking-widest">
                ••••••••{integration.key_last_four}
              </span>
              <span className="text-[10px] text-muted-foreground/60">saved key</span>
            </div>
          )}
        </div>
        <Switch
          checked={enabled}
          onCheckedChange={(v) => {
            setEnabled(v);
            update.mutate({
              name: integration.name,
              api_key: undefined,
              is_enabled: v,
            });
          }}
          data-testid={`switch-${integration.name}`}
        />
      </div>

      <div className="mt-4 space-y-2">
        <Label className="text-xs">{integration.key_label}</Label>
        <Input
          type="password"
          placeholder={
            integration.is_connected ? "•••••••• (saved — type to replace)" : "Paste API key"
          }
          value={key}
          onChange={(e) => setKey(e.target.value)}
          data-testid={`input-key-${integration.name}`}
        />
      </div>

      <div className="mt-3 flex items-center justify-between gap-2">
        <div className="text-xs text-muted-foreground">
          {integration.test_status === "ok" && (
            <span className="inline-flex items-center gap-1 text-primary">
              <Check className="h-3 w-3" /> {integration.test_message}
            </span>
          )}
          {integration.test_status === "failed" && (
            <span className="inline-flex items-center gap-1 text-destructive">
              <AlertCircle className="h-3 w-3" /> {integration.test_message}
            </span>
          )}
        </div>
        <div className="flex gap-2">
          <Button
            size="sm"
            variant="secondary"
            disabled={!integration.is_connected || test.isPending}
            onClick={() => test.mutate(integration.name)}
            data-testid={`button-test-${integration.name}`}
          >
            {test.isPending ? "Testing…" : "Test"}
          </Button>
          <Button
            size="sm"
            disabled={update.isPending}
            onClick={async () => {
              await update.mutateAsync({
                name: integration.name,
                api_key: key || undefined,
                is_enabled: enabled,
              });
              setKey("");
            }}
            data-testid={`button-save-${integration.name}`}
          >
            {update.isPending ? "Saving…" : "Save"}
          </Button>
        </div>
      </div>
    </Card>
  );
}
