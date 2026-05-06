import { useState } from "react";
import { Link, useLocation } from "wouter";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/PageHeader";
import { StatusPill } from "@/components/Pills";
import { useCreateStrategy, useStrategies } from "@/hooks/useStrategies";
import { useActiveStrategy } from "@/hooks/useActiveStrategy";
import { Compass } from "lucide-react";

export function StrategyList() {
  const { data: strategies } = useStrategies();
  const create = useCreateStrategy();
  const { setActiveId } = useActiveStrategy();
  const [, navigate] = useLocation();
  const [form, setForm] = useState({
    product_name: "",
    description: "",
    target_market: "",
    pain_points_raw: "",
  });

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const created = await create.mutateAsync(form);
    setActiveId(created.id);
    navigate(`/strategy/${created.id}`);
  }

  return (
    <>
      <PageHeader
        eyebrow="Stage 1"
        title="Strategy & Discovery"
        subtitle="Define a product, then run the agent pipeline to generate an ICP, persona matrix, problem map, NAICS segmentation, stakeholder graph, and use-case library."
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
        <Card className="lg:col-span-2 border-card-border bg-card p-5">
          <div className="mb-4 flex items-center gap-2">
            <Compass className="h-4 w-4 text-primary" />
            <div className="text-sm font-semibold">New strategy</div>
          </div>
          <form className="space-y-3" onSubmit={submit}>
            <div>
              <Label className="text-xs">Product name</Label>
              <Input
                value={form.product_name}
                onChange={(e) =>
                  setForm({ ...form, product_name: e.target.value })
                }
                required
                data-testid="input-product-name"
                placeholder="Acme Sales Intelligence"
              />
            </div>
            <div>
              <Label className="text-xs">Description</Label>
              <Textarea
                value={form.description}
                onChange={(e) =>
                  setForm({ ...form, description: e.target.value })
                }
                rows={3}
                required
                data-testid="input-description"
                placeholder="What it does, who it's for, what problem it solves."
              />
            </div>
            <div>
              <Label className="text-xs">Target market</Label>
              <Input
                value={form.target_market}
                onChange={(e) =>
                  setForm({ ...form, target_market: e.target.value })
                }
                data-testid="input-target-market"
                placeholder="Series B/C SaaS, 100-500 employees, North America"
              />
            </div>
            <div>
              <Label className="text-xs">Known pain points</Label>
              <Textarea
                value={form.pain_points_raw}
                onChange={(e) =>
                  setForm({ ...form, pain_points_raw: e.target.value })
                }
                rows={3}
                data-testid="input-pain-points"
                placeholder="What hurts today for the buyer?"
              />
            </div>
            <Button
              type="submit"
              disabled={create.isPending}
              data-testid="button-create-strategy"
            >
              {create.isPending ? "Creating…" : "Create & continue"}
            </Button>
          </form>
        </Card>

        <div className="lg:col-span-3">
          <div className="mb-3 text-xs font-medium uppercase tracking-widest text-muted-foreground">
            Existing strategies
          </div>
          <div className="space-y-2">
            {strategies?.map((s) => (
              <Link key={s.id} href={`/strategy/${s.id}`}>
                <Card
                  className="cursor-pointer border-card-border bg-card p-4 hover-elevate"
                  data-testid={`row-strategy-${s.id}`}
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-sm font-medium">{s.product_name}</div>
                      <div className="mt-0.5 line-clamp-1 text-xs text-muted-foreground">
                        {s.description}
                      </div>
                    </div>
                    <StatusPill status={s.status} />
                  </div>
                </Card>
              </Link>
            ))}
            {strategies && strategies.length === 0 && (
              <div className="rounded border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
                No strategies yet. Create one to start the pipeline.
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
