export default function StageS3() {
  return (
    <div className="w-screen h-screen overflow-hidden relative bg-bg text-text">
      <div className="absolute inset-0 dot-bg opacity-40" />

      <div className="absolute top-[5vh] left-[5vw] right-[5vw] flex items-center justify-between">
        <div className="font-mono text-[1.1vw] text-sky tracking-[0.3em] uppercase">Stage 3 · Outreach</div>
        <div className="font-mono text-[1.1vw] text-muted">/ S3 · 3-CHANNEL SEQUENCER</div>
      </div>

      <div className="absolute left-[5vw] top-[12vh] w-[40vw]">
        <h2 className="font-display font-black text-[4.4vw] leading-[0.95] tracking-tight text-text" style={{ textWrap: "balance" }}>
          Persona-aware sequences across every channel.
        </h2>
        <p className="mt-[3vh] text-[1.5vw] text-muted leading-snug" style={{ textWrap: "pretty" }}>
          Email, LinkedIn, and phone — drafted per persona, deliverability-checked, then launched through Instantly or simulated for demo.
        </p>

        <div className="mt-[4vh] grid grid-cols-3 gap-[1vw]">
          <div className="bg-panel border border-primary/30 rounded-[0.6vw] p-[1.2vw]">
            <div className="font-mono text-[0.85vw] text-primary tracking-[0.2em] uppercase">Email</div>
            <div className="font-display font-bold text-[1.6vw] text-text leading-tight mt-[0.5vh]">3 touches</div>
            <div className="text-[1vw] text-muted">SPF · DKIM · DMARC verified</div>
          </div>
          <div className="bg-panel border border-sky/30 rounded-[0.6vw] p-[1.2vw]">
            <div className="font-mono text-[0.85vw] text-sky tracking-[0.2em] uppercase">LinkedIn</div>
            <div className="font-display font-bold text-[1.6vw] text-text leading-tight mt-[0.5vh]">2 touches</div>
            <div className="text-[1vw] text-muted">Connect + reply</div>
          </div>
          <div className="bg-panel border border-amber/30 rounded-[0.6vw] p-[1.2vw]">
            <div className="font-mono text-[0.85vw] text-amber tracking-[0.2em] uppercase">Call</div>
            <div className="font-display font-bold text-[1.6vw] text-text leading-tight mt-[0.5vh]">1 touch</div>
            <div className="text-[1vw] text-muted">Talk-track generated</div>
          </div>
        </div>
      </div>

      <div className="absolute right-[5vw] top-[12vh] w-[45vw] h-[78vh] bg-panel border border-border rounded-[0.8vw] overflow-hidden">
        <div className="h-[3vh] bg-bg/60 border-b border-border flex items-center px-[1vw] gap-[0.5vw]">
          <div className="w-[0.7vw] h-[0.7vw] rounded-full bg-rose/70" />
          <div className="w-[0.7vw] h-[0.7vw] rounded-full bg-amber/70" />
          <div className="w-[0.7vw] h-[0.7vw] rounded-full bg-primary/70" />
          <div className="ml-[1vw] font-mono text-[0.85vw] text-muted">gtm-factory · /strategy/acme-cloud-erp/outreach</div>
        </div>
        <div className="p-[1.5vw]">
          <div className="flex items-center justify-between mb-[1.5vh]">
            <div>
              <div className="font-mono text-[0.85vw] text-sky tracking-[0.2em] uppercase">Sequence · COO persona</div>
              <div className="font-display font-bold text-[1.7vw] text-text leading-tight">Northwind Logistics — 6 steps</div>
            </div>
            <div className="font-mono text-[0.95vw] px-[0.8vw] py-[0.4vh] rounded-[0.3vw] bg-primary/15 text-primary">deliverability OK</div>
          </div>

          <div className="bg-bg/40 border border-border rounded-[0.5vw] p-[1vw] mb-[1.2vh]">
            <div className="flex items-center justify-between mb-[0.6vh]">
              <div className="flex items-center gap-[0.6vw]">
                <div className="w-[1.4vw] h-[1.4vw] rounded-[0.3vw] bg-primary/20 text-primary flex items-center justify-center font-mono text-[0.85vw] font-bold">E1</div>
                <span className="font-mono text-[0.95vw] text-primary">Email · Day 0</span>
              </div>
              <span className="font-mono text-[0.85vw] text-muted">157 words</span>
            </div>
            <div className="text-[1.05vw] text-text leading-snug">"Saw Northwind opened a new ops hub in Memphis — most of the teams we work with hit ERP friction right at that scale. Worth a 15-min look at how Helix cut close cycle from 11 to 4 days?"</div>
          </div>

          <div className="bg-bg/40 border border-border rounded-[0.5vw] p-[1vw] mb-[1.2vh]">
            <div className="flex items-center justify-between mb-[0.6vh]">
              <div className="flex items-center gap-[0.6vw]">
                <div className="w-[1.4vw] h-[1.4vw] rounded-[0.3vw] bg-sky/20 text-sky flex items-center justify-center font-mono text-[0.85vw] font-bold">L1</div>
                <span className="font-mono text-[0.95vw] text-sky">LinkedIn · Day 2</span>
              </div>
              <span className="font-mono text-[0.85vw] text-muted">connect note</span>
            </div>
            <div className="text-[1.05vw] text-text leading-snug">"Following Northwind's Memphis launch — would love to compare notes on how mid-market 3PLs are scaling close cycle without a full SAP rip-and-replace."</div>
          </div>

          <div className="bg-bg/40 border border-border rounded-[0.5vw] p-[1vw] mb-[1.2vh]">
            <div className="flex items-center justify-between mb-[0.6vh]">
              <div className="flex items-center gap-[0.6vw]">
                <div className="w-[1.4vw] h-[1.4vw] rounded-[0.3vw] bg-amber/20 text-amber flex items-center justify-center font-mono text-[0.85vw] font-bold">C1</div>
                <span className="font-mono text-[0.95vw] text-amber">Call · Day 5</span>
              </div>
              <span className="font-mono text-[0.85vw] text-muted">talk-track · 90s</span>
            </div>
            <div className="text-[1.05vw] text-text leading-snug">Open with Memphis hub. Anchor on close-cycle pain. Reference Helix outcome. Ask: who owns ERP fit? Book the demo or capture champion.</div>
          </div>

          <div className="flex items-center justify-between mt-[1.5vh] font-mono text-[1vw]">
            <span className="text-muted">launch via Instantly</span>
            <span className="text-primary">→ ready</span>
          </div>
        </div>
      </div>
    </div>
  );
}
