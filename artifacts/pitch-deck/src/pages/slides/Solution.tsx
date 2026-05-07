export default function Solution() {
  return (
    <div className="w-screen h-screen overflow-hidden relative bg-bg text-text">
      <div className="absolute inset-0 grid-bg opacity-50" />
      <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-primary/5" />

      <div className="absolute top-[5vh] left-[5vw] right-[5vw] flex items-center justify-between">
        <div className="font-mono text-[1.1vw] text-primary tracking-[0.3em] uppercase">02 · Solution</div>
        <div className="font-mono text-[1.1vw] text-muted">/ ONE OPERATING SYSTEM</div>
      </div>

      <div className="absolute left-[5vw] top-[14vh] right-[5vw]">
        <h2 className="font-display font-black text-[5vw] leading-[0.95] tracking-tight text-text" style={{ textWrap: "balance" }}>
          Three stages. One agent loop.
          <span className="block text-primary">Continuous compounding intelligence.</span>
        </h2>
      </div>

      <div className="absolute left-[5vw] right-[5vw] top-[44vh] grid grid-cols-3 gap-[1.5vw]">
        <div className="bg-panel border border-primary/30 rounded-[0.8vw] p-[1.8vw] relative">
          <div className="absolute top-[1.5vw] right-[1.5vw] font-mono text-[0.95vw] text-primary">S1</div>
          <div className="font-display font-bold text-[2.2vw] leading-tight text-text mb-[1vh]">Strategy</div>
          <div className="text-[1.3vw] text-muted leading-snug mb-[1.5vh]">ICP, personas, problem map, NAICS segments, stakeholder graph.</div>
          <div className="font-mono text-[0.95vw] text-primary">→ live SSE pipeline</div>
        </div>
        <div className="bg-panel border border-amber/30 rounded-[0.8vw] p-[1.8vw] relative">
          <div className="absolute top-[1.5vw] right-[1.5vw] font-mono text-[0.95vw] text-amber">S2</div>
          <div className="font-display font-bold text-[2.2vw] leading-tight text-text mb-[1vh]">Intelligence</div>
          <div className="text-[1.3vw] text-muted leading-snug mb-[1.5vh]">TAM/SAM/SOM, competitors, lead discovery, buying signals, scoring.</div>
          <div className="font-mono text-[0.95vw] text-amber">→ composite scoring</div>
        </div>
        <div className="bg-panel border border-sky/30 rounded-[0.8vw] p-[1.8vw] relative">
          <div className="absolute top-[1.5vw] right-[1.5vw] font-mono text-[0.95vw] text-sky">S3</div>
          <div className="font-display font-bold text-[2.2vw] leading-tight text-text mb-[1vh]">Outreach</div>
          <div className="text-[1.3vw] text-muted leading-snug mb-[1.5vh]">Persona-aware sequences across email, LinkedIn, and call.</div>
          <div className="font-mono text-[0.95vw] text-sky">→ deliverability + launch</div>
        </div>
      </div>

      <div className="absolute left-[5vw] right-[5vw] bottom-[5vh] bg-panel border border-violet/40 rounded-[0.8vw] p-[1.5vw] flex items-center justify-between">
        <div className="flex items-center gap-[1.5vw]">
          <div className="w-[3vw] h-[3vw] rounded-full border-2 border-violet flex items-center justify-center">
            <div className="font-mono text-[1.1vw] text-violet font-bold">M3</div>
          </div>
          <div>
            <div className="font-display font-bold text-[1.7vw] text-text leading-tight">Intelligence loop</div>
            <div className="text-[1.15vw] text-muted leading-snug">Engagement → intent → feedback → attribution → ICP loop-back.</div>
          </div>
        </div>
        <div className="font-mono text-[1vw] text-violet tracking-[0.2em] uppercase">feeds S1 · S2 · S3</div>
      </div>
    </div>
  );
}
