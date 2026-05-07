export default function StageS2() {
  return (
    <div className="w-screen h-screen overflow-hidden relative bg-bg text-text">
      <div className="absolute inset-0 dot-bg opacity-40" />

      <div className="absolute top-[5vh] left-[5vw] right-[5vw] flex items-center justify-between">
        <div className="font-mono text-[1.1vw] text-amber tracking-[0.3em] uppercase">Stage 2 · Intelligence</div>
        <div className="font-mono text-[1.1vw] text-muted">/ S2 · MARKET + SCORING</div>
      </div>

      <div className="absolute left-[5vw] top-[12vh] w-[40vw]">
        <h2 className="font-display font-black text-[4.4vw] leading-[0.95] tracking-tight text-text" style={{ textWrap: "balance" }}>
          Sized markets, real signals, ranked accounts.
        </h2>
        <p className="mt-[3vh] text-[1.5vw] text-muted leading-snug" style={{ textWrap: "pretty" }}>
          TAM/SAM/SOM, live competitor research, lead discovery via Apollo, and intent signals via SerpAPI — composited into a single account score.
        </p>

        <div className="mt-[4vh] bg-panel border border-border rounded-[0.8vw] p-[1.8vw]">
          <div className="font-mono text-[0.9vw] text-muted tracking-[0.2em] uppercase mb-[1vh]">Composite Score</div>
          <div className="font-mono text-[1.6vw] text-text leading-snug">
            <span className="text-primary">0.30</span>
            <span className="text-muted"> × ICP fit + </span>
            <span className="text-amber">0.40</span>
            <span className="text-muted"> × signals + </span>
            <span className="text-sky">0.30</span>
            <span className="text-muted"> × engagement</span>
          </div>
          <div className="mt-[1.2vh] text-[1.1vw] text-muted">+ pattern boost when learned clusters exist for the strategy</div>
        </div>
      </div>

      <div className="absolute right-[5vw] top-[12vh] w-[45vw] h-[78vh] bg-panel border border-border rounded-[0.8vw] overflow-hidden">
        <div className="h-[3vh] bg-bg/60 border-b border-border flex items-center px-[1vw] gap-[0.5vw]">
          <div className="w-[0.7vw] h-[0.7vw] rounded-full bg-rose/70" />
          <div className="w-[0.7vw] h-[0.7vw] rounded-full bg-amber/70" />
          <div className="w-[0.7vw] h-[0.7vw] rounded-full bg-primary/70" />
          <div className="ml-[1vw] font-mono text-[0.85vw] text-muted">gtm-factory · /strategy/acme-cloud-erp/market</div>
        </div>
        <div className="p-[1.5vw]">
          <div className="grid grid-cols-3 gap-[1vw]">
            <div className="bg-bg/40 border border-border rounded-[0.5vw] p-[1vw]">
              <div className="font-mono text-[0.8vw] text-muted">TAM</div>
              <div className="font-display font-black text-[2.4vw] text-text leading-tight">$48.2B</div>
              <div className="text-[0.9vw] text-primary">+12.4% YoY</div>
            </div>
            <div className="bg-bg/40 border border-border rounded-[0.5vw] p-[1vw]">
              <div className="font-mono text-[0.8vw] text-muted">SAM</div>
              <div className="font-display font-black text-[2.4vw] text-text leading-tight">$11.6B</div>
              <div className="text-[0.9vw] text-amber">NA mid-market</div>
            </div>
            <div className="bg-bg/40 border border-border rounded-[0.5vw] p-[1vw]">
              <div className="font-mono text-[0.8vw] text-muted">SOM · YR1</div>
              <div className="font-display font-black text-[2.4vw] text-primary leading-tight">$84M</div>
              <div className="text-[0.9vw] text-muted">2.4% capture</div>
            </div>
          </div>

          <div className="mt-[2.5vh] bg-bg/40 border border-border rounded-[0.5vw] p-[1vw]">
            <div className="flex items-center justify-between mb-[1vh]">
              <div className="font-mono text-[0.85vw] text-muted">RANKED ACCOUNTS — TOP SIGNALS</div>
              <div className="font-mono text-[0.85vw] text-primary">scoring · live</div>
            </div>
            <div className="space-y-[1vh]">
              <div className="flex items-center justify-between font-mono text-[1.05vw]">
                <div className="flex items-center gap-[0.8vw]">
                  <span className="text-muted w-[1.6vw]">01</span>
                  <span className="text-text">Northwind Logistics</span>
                  <span className="text-[0.85vw] px-[0.5vw] py-[0.1vh] rounded-[0.3vw] bg-primary/15 text-primary">hiring · ERP lead</span>
                </div>
                <span className="text-primary font-bold">0.94</span>
              </div>
              <div className="flex items-center justify-between font-mono text-[1.05vw]">
                <div className="flex items-center gap-[0.8vw]">
                  <span className="text-muted w-[1.6vw]">02</span>
                  <span className="text-text">Helix Manufacturing</span>
                  <span className="text-[0.85vw] px-[0.5vw] py-[0.1vh] rounded-[0.3vw] bg-amber/15 text-amber">funding · Series C</span>
                </div>
                <span className="text-primary font-bold">0.91</span>
              </div>
              <div className="flex items-center justify-between font-mono text-[1.05vw]">
                <div className="flex items-center gap-[0.8vw]">
                  <span className="text-muted w-[1.6vw]">03</span>
                  <span className="text-text">Civic Health Group</span>
                  <span className="text-[0.85vw] px-[0.5vw] py-[0.1vh] rounded-[0.3vw] bg-sky/15 text-sky">tech · SAP migration</span>
                </div>
                <span className="text-primary font-bold">0.88</span>
              </div>
              <div className="flex items-center justify-between font-mono text-[1.05vw]">
                <div className="flex items-center gap-[0.8vw]">
                  <span className="text-muted w-[1.6vw]">04</span>
                  <span className="text-text">Brightline Foods</span>
                  <span className="text-[0.85vw] px-[0.5vw] py-[0.1vh] rounded-[0.3vw] bg-violet/15 text-violet">job posting · CFO</span>
                </div>
                <span className="text-amber font-bold">0.81</span>
              </div>
              <div className="flex items-center justify-between font-mono text-[1.05vw]">
                <div className="flex items-center gap-[0.8vw]">
                  <span className="text-muted w-[1.6vw]">05</span>
                  <span className="text-text">Pacific Rim Retail</span>
                  <span className="text-[0.85vw] px-[0.5vw] py-[0.1vh] rounded-[0.3vw] bg-primary/15 text-primary">G2 review surge</span>
                </div>
                <span className="text-amber font-bold">0.77</span>
              </div>
            </div>
          </div>

          <div className="mt-[2vh] bg-bg/40 border border-border rounded-[0.5vw] p-[1vw]">
            <div className="font-mono text-[0.85vw] text-muted mb-[1vh]">PATTERN CLUSTERS · LEARNED FROM WINS</div>
            <div className="flex flex-wrap gap-[0.5vw]">
              <span className="text-[0.95vw] px-[0.7vw] py-[0.3vh] rounded-[0.3vw] bg-primary/15 text-primary font-mono">cluster_07 · ops-led buying</span>
              <span className="text-[0.95vw] px-[0.7vw] py-[0.3vh] rounded-[0.3vw] bg-amber/15 text-amber font-mono">cluster_12 · post-merger ERP</span>
              <span className="text-[0.95vw] px-[0.7vw] py-[0.3vh] rounded-[0.3vw] bg-violet/15 text-violet font-mono">cluster_19 · CFO-driven</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
