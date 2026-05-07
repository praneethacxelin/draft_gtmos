export default function Problem() {
  return (
    <div className="w-screen h-screen overflow-hidden relative bg-bg text-text">
      <div className="absolute inset-0 dot-bg opacity-50" />

      <div className="absolute top-[5vh] left-[5vw] right-[5vw] flex items-center justify-between">
        <div className="font-mono text-[1.1vw] text-primary tracking-[0.3em] uppercase">01 · Problem</div>
        <div className="font-mono text-[1.1vw] text-muted">/ THE STATUS QUO</div>
      </div>

      <div className="absolute left-[5vw] top-[14vh] right-[5vw]">
        <h2 className="font-display font-black text-[5.5vw] leading-[0.95] tracking-tight text-text" style={{ textWrap: "balance" }}>
          Modern GTM is a stack of disconnected tools
          <span className="text-muted"> — and humans paying the integration tax.</span>
        </h2>
      </div>

      <div className="absolute left-[5vw] right-[5vw] bottom-[8vh] grid grid-cols-4 gap-[1.5vw]">
        <div className="bg-panel border border-border rounded-[0.8vw] p-[2vw]">
          <div className="font-mono text-[0.9vw] text-rose tracking-[0.2em] uppercase mb-[1.5vh]">Strategy</div>
          <div className="font-display font-bold text-[2vw] leading-tight text-text mb-[1vh]">Slide decks &amp; spreadsheets</div>
          <div className="text-[1.3vw] text-muted leading-snug">ICPs, personas, problem maps — written once, never refreshed.</div>
        </div>
        <div className="bg-panel border border-border rounded-[0.8vw] p-[2vw]">
          <div className="font-mono text-[0.9vw] text-amber tracking-[0.2em] uppercase mb-[1.5vh]">Research</div>
          <div className="font-display font-bold text-[2vw] leading-tight text-text mb-[1vh]">Five SaaS subscriptions</div>
          <div className="text-[1.3vw] text-muted leading-snug">TAM, competitors, intent signals — siloed across vendor dashboards.</div>
        </div>
        <div className="bg-panel border border-border rounded-[0.8vw] p-[2vw]">
          <div className="font-mono text-[0.9vw] text-sky tracking-[0.2em] uppercase mb-[1.5vh]">Outreach</div>
          <div className="font-display font-bold text-[2vw] leading-tight text-text mb-[1vh]">Generic sequences</div>
          <div className="text-[1.3vw] text-muted leading-snug">Email blasts that ignore persona, channel fit, and live intent.</div>
        </div>
        <div className="bg-panel border border-border rounded-[0.8vw] p-[2vw]">
          <div className="font-mono text-[0.9vw] text-violet tracking-[0.2em] uppercase mb-[1.5vh]">Learning</div>
          <div className="font-display font-bold text-[2vw] leading-tight text-text mb-[1vh]">Quarterly retros</div>
          <div className="text-[1.3vw] text-muted leading-snug">Engagement and win/loss data never makes it back into the ICP.</div>
        </div>
      </div>
    </div>
  );
}
