export default function StageS1() {
  return (
    <div className="w-screen h-screen overflow-hidden relative bg-bg text-text">
      <div className="absolute inset-0 dot-bg opacity-40" />

      <div className="absolute top-[5vh] left-[5vw] right-[5vw] flex items-center justify-between">
        <div className="font-mono text-[1.1vw] text-primary tracking-[0.3em] uppercase">Stage 1 · Strategy</div>
        <div className="font-mono text-[1.1vw] text-muted">/ S1 · DISCOVERY</div>
      </div>

      <div className="absolute left-[5vw] top-[12vh] w-[40vw]">
        <h2 className="font-display font-black text-[4.4vw] leading-[0.95] tracking-tight text-text" style={{ textWrap: "balance" }}>
          From a one-line brief to a full GTM strategy.
        </h2>
        <p className="mt-[3vh] text-[1.5vw] text-muted leading-snug" style={{ textWrap: "pretty" }}>
          One prompt generates an ICP, persona matrix, problem map, NAICS segments, stakeholder graph, and a use-case library — streamed live as agents run.
        </p>

        <div className="mt-[4vh] space-y-[1.5vh]">
          <div className="flex items-center gap-[1vw]">
            <div className="w-[0.6vw] h-[0.6vw] rounded-full bg-primary" />
            <div className="text-[1.4vw] text-text">ICP and persona matrix</div>
          </div>
          <div className="flex items-center gap-[1vw]">
            <div className="w-[0.6vw] h-[0.6vw] rounded-full bg-primary" />
            <div className="text-[1.4vw] text-text">Problem map and use-case library</div>
          </div>
          <div className="flex items-center gap-[1vw]">
            <div className="w-[0.6vw] h-[0.6vw] rounded-full bg-primary" />
            <div className="text-[1.4vw] text-text">Stakeholder graph with tier coloring</div>
          </div>
          <div className="flex items-center gap-[1vw]">
            <div className="w-[0.6vw] h-[0.6vw] rounded-full bg-primary" />
            <div className="text-[1.4vw] text-text">NAICS segmentation and territory cuts</div>
          </div>
        </div>
      </div>

      <div className="absolute right-[5vw] top-[12vh] w-[45vw] h-[78vh] bg-panel border border-border rounded-[0.8vw] overflow-hidden">
        <div className="h-[3vh] bg-bg/60 border-b border-border flex items-center px-[1vw] gap-[0.5vw]">
          <div className="w-[0.7vw] h-[0.7vw] rounded-full bg-rose/70" />
          <div className="w-[0.7vw] h-[0.7vw] rounded-full bg-amber/70" />
          <div className="w-[0.7vw] h-[0.7vw] rounded-full bg-primary/70" />
          <div className="ml-[1vw] font-mono text-[0.85vw] text-muted">gtm-factory · /strategy/acme-cloud-erp</div>
        </div>
        <div className="p-[1.5vw]">
          <div className="font-mono text-[0.85vw] text-primary tracking-[0.2em] uppercase">Stage 1 · Strategy</div>
          <div className="font-display font-bold text-[1.8vw] text-text leading-tight mt-[0.5vh]">Acme Cloud ERP — North America Mid-Market</div>
          <div className="text-[1vw] text-muted mt-[0.5vh]">Generated 2 minutes ago · 6 agents · 14 artifacts</div>

          <div className="mt-[2.5vh] bg-bg/40 border border-border rounded-[0.5vw] p-[1vw]">
            <div className="font-mono text-[0.85vw] text-muted mb-[1vh]">LIVE AGENT PIPELINE</div>
            <div className="space-y-[0.8vh]">
              <div className="flex items-center justify-between font-mono text-[1vw]">
                <div className="flex items-center gap-[0.6vw]">
                  <div className="w-[0.5vw] h-[0.5vw] rounded-full bg-primary" />
                  <span className="text-text">icp_synthesis</span>
                </div>
                <span className="text-primary">done · 1.2s</span>
              </div>
              <div className="flex items-center justify-between font-mono text-[1vw]">
                <div className="flex items-center gap-[0.6vw]">
                  <div className="w-[0.5vw] h-[0.5vw] rounded-full bg-primary" />
                  <span className="text-text">persona_matrix</span>
                </div>
                <span className="text-primary">done · 2.4s</span>
              </div>
              <div className="flex items-center justify-between font-mono text-[1vw]">
                <div className="flex items-center gap-[0.6vw]">
                  <div className="w-[0.5vw] h-[0.5vw] rounded-full bg-primary" />
                  <span className="text-text">problem_map</span>
                </div>
                <span className="text-primary">done · 1.8s</span>
              </div>
              <div className="flex items-center justify-between font-mono text-[1vw]">
                <div className="flex items-center gap-[0.6vw]">
                  <div className="w-[0.5vw] h-[0.5vw] rounded-full bg-amber animate-pulse" />
                  <span className="text-text">stakeholder_graph</span>
                </div>
                <span className="text-amber">running…</span>
              </div>
              <div className="flex items-center justify-between font-mono text-[1vw]">
                <div className="flex items-center gap-[0.6vw]">
                  <div className="w-[0.5vw] h-[0.5vw] rounded-full bg-muted" />
                  <span className="text-muted">naics_segmentation</span>
                </div>
                <span className="text-muted">queued</span>
              </div>
              <div className="flex items-center justify-between font-mono text-[1vw]">
                <div className="flex items-center gap-[0.6vw]">
                  <div className="w-[0.5vw] h-[0.5vw] rounded-full bg-muted" />
                  <span className="text-muted">use_case_library</span>
                </div>
                <span className="text-muted">queued</span>
              </div>
            </div>
          </div>

          <div className="mt-[2vh] grid grid-cols-2 gap-[1vw]">
            <div className="bg-bg/40 border border-border rounded-[0.5vw] p-[1vw]">
              <div className="font-mono text-[0.8vw] text-muted">ICP FIT — TARGET COMPANIES</div>
              <div className="font-display font-black text-[2.6vw] text-primary leading-tight">1,284</div>
              <div className="text-[0.95vw] text-muted">200–2,000 employees · ERP modernization</div>
            </div>
            <div className="bg-bg/40 border border-border rounded-[0.5vw] p-[1vw]">
              <div className="font-mono text-[0.8vw] text-muted">STAKEHOLDER TIERS</div>
              <div className="flex items-center gap-[0.4vw] mt-[0.5vh]">
                <span className="text-[0.95vw] px-[0.6vw] py-[0.2vh] rounded-[0.3vw] bg-primary/15 text-primary font-mono">champion</span>
                <span className="text-[0.95vw] px-[0.6vw] py-[0.2vh] rounded-[0.3vw] bg-amber/15 text-amber font-mono">econ</span>
                <span className="text-[0.95vw] px-[0.6vw] py-[0.2vh] rounded-[0.3vw] bg-violet/15 text-violet font-mono">infl</span>
                <span className="text-[0.95vw] px-[0.6vw] py-[0.2vh] rounded-[0.3vw] bg-rose/15 text-rose font-mono">block</span>
              </div>
              <div className="text-[0.95vw] text-muted mt-[0.5vh]">4-tier graph rendered with ReactFlow</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
