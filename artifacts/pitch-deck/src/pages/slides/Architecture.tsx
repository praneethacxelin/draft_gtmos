export default function Architecture() {
  return (
    <div className="w-screen h-screen overflow-hidden relative bg-bg text-text">
      <div className="absolute inset-0 grid-bg opacity-40" />

      <div className="absolute top-[5vh] left-[5vw] right-[5vw] flex items-center justify-between">
        <div className="font-mono text-[1.1vw] text-primary tracking-[0.3em] uppercase">03 · Architecture</div>
        <div className="font-mono text-[1.1vw] text-muted">/ AI-FIRST BY DESIGN</div>
      </div>

      <div className="absolute left-[5vw] top-[12vh] right-[5vw]">
        <h2 className="font-display font-black text-[5vw] leading-[0.95] tracking-tight text-text" style={{ textWrap: "balance" }}>
          Agents at every layer.
          <span className="block text-muted">Optional integrations. Streaming everywhere.</span>
        </h2>
      </div>

      <div className="absolute left-[5vw] right-[5vw] top-[42vh]">
        <div className="grid grid-cols-4 gap-[1.2vw]">
          <div className="bg-panel border border-border rounded-[0.6vw] p-[1.4vw]">
            <div className="font-mono text-[0.9vw] text-primary tracking-[0.2em] uppercase mb-[1vh]">Agents</div>
            <div className="font-display font-bold text-[1.6vw] text-text leading-tight">Per-stage LLM workers</div>
            <div className="text-[1.05vw] text-muted mt-[0.6vh] leading-snug">Replit OpenAI proxy · structured outputs · SSE streaming.</div>
          </div>
          <div className="bg-panel border border-border rounded-[0.6vw] p-[1.4vw]">
            <div className="font-mono text-[0.9vw] text-amber tracking-[0.2em] uppercase mb-[1vh]">Embeddings</div>
            <div className="font-display font-bold text-[1.6vw] text-text leading-tight">Deterministic 1536-dim</div>
            <div className="text-[1.05vw] text-muted mt-[0.6vh] leading-snug">Hash-based, normalized, pgvector-compatible — swap to a real model anytime.</div>
          </div>
          <div className="bg-panel border border-border rounded-[0.6vw] p-[1.4vw]">
            <div className="font-mono text-[0.9vw] text-sky tracking-[0.2em] uppercase mb-[1vh]">Integrations</div>
            <div className="font-display font-bold text-[1.6vw] text-text leading-tight">Optional, demo-safe</div>
            <div className="text-[1.05vw] text-muted mt-[0.6vh] leading-snug">Apollo, SerpAPI, Instantly. No key? Agents fall back to AI-generated demo data.</div>
          </div>
          <div className="bg-panel border border-border rounded-[0.6vw] p-[1.4vw]">
            <div className="font-mono text-[0.9vw] text-violet tracking-[0.2em] uppercase mb-[1vh]">Storage</div>
            <div className="font-display font-bold text-[1.6vw] text-text leading-tight">Postgres + pgvector</div>
            <div className="text-[1.05vw] text-muted mt-[0.6vh] leading-snug">Strategies, accounts, signals, events, and pattern clusters in one schema.</div>
          </div>
        </div>

        <div className="mt-[3vh] bg-panel border border-border rounded-[0.6vw] p-[1.5vw]">
          <div className="font-mono text-[0.9vw] text-muted tracking-[0.2em] uppercase mb-[1.5vh]">Request flow</div>
          <div className="flex items-center gap-[1vw] font-mono text-[1.15vw]">
            <span className="px-[0.8vw] py-[0.5vh] rounded-[0.3vw] bg-primary/15 text-primary">React + Vite</span>
            <span className="text-muted">→</span>
            <span className="px-[0.8vw] py-[0.5vh] rounded-[0.3vw] bg-amber/15 text-amber">FastAPI</span>
            <span className="text-muted">→</span>
            <span className="px-[0.8vw] py-[0.5vh] rounded-[0.3vw] bg-sky/15 text-sky">SSE stage runner</span>
            <span className="text-muted">→</span>
            <span className="px-[0.8vw] py-[0.5vh] rounded-[0.3vw] bg-violet/15 text-violet">LLM agents</span>
            <span className="text-muted">→</span>
            <span className="px-[0.8vw] py-[0.5vh] rounded-[0.3vw] bg-rose/15 text-rose">pgvector</span>
            <span className="text-muted">→</span>
            <span className="px-[0.8vw] py-[0.5vh] rounded-[0.3vw] bg-primary/15 text-primary">M3 loop</span>
          </div>
          <div className="text-[1.1vw] text-muted mt-[1.5vh] leading-snug">Every stage emits typed events. The frontend renders a live agent pipeline; the backend writes artifacts into the same schema the M3 loop reads from.</div>
        </div>
      </div>
    </div>
  );
}
