export default function WhyItWins() {
  return (
    <div className="w-screen h-screen overflow-hidden relative bg-bg text-text">
      <div className="absolute inset-0 dot-bg opacity-50" />

      <div className="absolute top-[5vh] left-[5vw] right-[5vw] flex items-center justify-between">
        <div className="font-mono text-[1.1vw] text-primary tracking-[0.3em] uppercase">04 · Differentiation</div>
        <div className="font-mono text-[1.1vw] text-muted">/ WHY IT WINS</div>
      </div>

      <div className="absolute left-[5vw] top-[14vh] right-[5vw]">
        <h2 className="font-display font-black text-[5vw] leading-[0.95] tracking-tight text-text" style={{ textWrap: "balance" }}>
          Not another GPT wrapper.
          <span className="block text-primary">A closed-loop revenue system.</span>
        </h2>
      </div>

      <div className="absolute left-[5vw] right-[5vw] bottom-[7vh] grid grid-cols-3 gap-[1.5vw]">
        <div className="bg-panel border border-border rounded-[0.8vw] p-[2vw]">
          <div className="font-display font-black text-[3.2vw] text-primary leading-none">01</div>
          <div className="font-display font-bold text-[1.8vw] text-text leading-tight mt-[1.2vh]">One schema, every stage</div>
          <div className="text-[1.2vw] text-muted leading-snug mt-[1vh]">Strategy artifacts, accounts, signals, events, and feedback live in the same Postgres + pgvector schema — so the loop can actually close.</div>
        </div>
        <div className="bg-panel border border-border rounded-[0.8vw] p-[2vw]">
          <div className="font-display font-black text-[3.2vw] text-amber leading-none">02</div>
          <div className="font-display font-bold text-[1.8vw] text-text leading-tight mt-[1.2vh]">Demo-safe by default</div>
          <div className="text-[1.2vw] text-muted leading-snug mt-[1vh]">Every external integration is optional. No keys? Agents emit clearly-labelled AI demo data so the product is never empty.</div>
        </div>
        <div className="bg-panel border border-border rounded-[0.8vw] p-[2vw]">
          <div className="font-display font-black text-[3.2vw] text-violet leading-none">03</div>
          <div className="font-display font-bold text-[1.8vw] text-text leading-tight mt-[1.2vh]">ICP that learns</div>
          <div className="text-[1.2vw] text-muted leading-snug mt-[1vh]">The M3 loop turns engagement and attribution into one-click ICP refinements — every campaign sharpens the next.</div>
        </div>
      </div>
    </div>
  );
}
