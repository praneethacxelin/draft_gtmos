import { useState } from "react";
import { Link, useLocation } from "wouter";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/PageHeader";
import { StatusPill } from "@/components/Pills";
import { useCreateStrategy, useStrategies } from "@/hooks/useStrategies";
import { useActiveStrategy } from "@/hooks/useActiveStrategy";
import { Compass, ArrowRight, Plus, Sparkles } from "lucide-react";

export function StrategyList() {
  const { data: strategies } = useStrategies();
  const create = useCreateStrategy();
  const { setActiveId } = useActiveStrategy();
  const [, navigate] = useLocation();
  const [productName, setProductName] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const created = await create.mutateAsync({
      product_name: productName,
      description: "",
    });
    setActiveId(created.id);
    navigate(`/strategy/${created.id}`);
  }

  return (
    <>
      <PageHeader
        eyebrow="Stage 1"
        title="Product Profile"
        subtitle="Create a product profile, then complete the discovery questionnaire to generate an ICP, persona matrix, problem map, NAICS segmentation, stakeholder graph, and use-case library."
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
        <Card className="lg:col-span-2 border-card-border bg-card p-5">
          <div className="mb-4 flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <Plus className="h-4 w-4" />
            </div>
            <div className="text-sm font-semibold">New Product Profile</div>
          </div>
          <p className="text-xs text-muted-foreground mb-4">
            Enter your product or service name to get started. You'll answer a quick discovery questionnaire next to tailor the AI generation.
          </p>
          <form className="space-y-3" onSubmit={submit}>
            <div>
              <Label className="text-xs">Product / Service Name</Label>
              <Input
                value={productName}
                onChange={(e) => setProductName(e.target.value)}
                required
                data-testid="input-product-name"
                placeholder="e.g., Acme Sales Intelligence"
                className="mt-1"
              />
            </div>
            <Button
              type="submit"
              disabled={create.isPending || !productName.trim()}
              data-testid="button-create-strategy"
              className="w-full gap-2"
            >
              {create.isPending ? (
                "Creating…"
              ) : (
                <>
                  <Sparkles className="h-4 w-4" />
                  Create & Start Discovery
                  <ArrowRight className="h-4 w-4" />
                </>
              )}
            </Button>
          </form>
        </Card>

        <div className="lg:col-span-3">
          <div className="mb-3 text-xs font-medium uppercase tracking-widest text-muted-foreground">
            Existing Profiles
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
                        {s.description ||
                          (typeof s.discovery_data?.product_description === "string"
                            ? s.discovery_data.product_description
                            : "") ||
                          "No description yet — complete the discovery questionnaire"}
                      </div>
                    </div>
                    <StatusPill status={s.status} />
                  </div>
                </Card>
              </Link>
            ))}
            {strategies && strategies.length === 0 && (
              <div className="rounded border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
                No product profiles yet. Create one to start the pipeline.
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
