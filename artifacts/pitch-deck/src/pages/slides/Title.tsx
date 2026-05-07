export default function Title() {
  return (
    <div className="w-screen h-screen overflow-hidden relative bg-bg text-text">
      <div className="absolute inset-0 grid-bg opacity-60" />
      <div className="absolute inset-0 bg-gradient-to-br from-primary/10 via-transparent to-violet/10" />
      <div className="absolute -left-[10vw] -top-[20vh] w-[60vw] h-[60vw] rounded-full bg-primary/10 blur-[8vw]" />
      <div className="absolute -right-[15vw] -bottom-[20vh] w-[50vw] h-[50vw] rounded-full bg-violet/10 blur-[8vw]" />

      <div className="absolute top-[5vh] left-[5vw] right-[5vw] flex items-center justify-between">
        <div className="flex items-center gap-[1vw]">
          <div className="w-[2.4vw] h-[2.4vw] rounded-[0.5vw] bg-primary flex items-center justify-center">
            <div className="w-[1.2vw] h-[1.2vw] rounded-[0.2vw] bg-bg" />
          </div>
          <div className="font-mono text-[1.2vw] tracking-tight text-text">GTM Factory</div>
        </div>
        <div className="font-mono text-[1.1vw] text-muted">v1.0 · Operating Console</div>
      </div>

      <div className="absolute left-[5vw] top-[28vh] right-[5vw]">
        <div className="font-mono text-[1.2vw] text-primary tracking-[0.3em] uppercase mb-[2vh]">
          Agentic GTM · S1 · S2 · S3 · M3
        </div>
        <h1 className="font-display font-black text-[7.2vw] leading-[0.9] tracking-tighter text-text" style={{ textWrap: "balance" }}>
          The operating console
          <span className="block text-primary">for AI-native GTM.</span>
        </h1>
        <p className="mt-[3vh] text-[2vw] text-muted max-w-[60vw] font-light leading-snug" style={{ textWrap: "pretty" }}>
          Strategy, market intelligence, and multichannel outreach — generated, scored, and continuously improved by agents.
        </p>
      </div>

      <div className="absolute bottom-[5vh] left-[5vw] right-[5vw] flex items-end justify-between">
        <div className="font-mono text-[1.1vw] text-muted">PITCH · 2026</div>
        <div className="flex items-center gap-[1.5vw]">
          <div className="w-[0.8vw] h-[0.8vw] rounded-full bg-primary animate-pulse" />
          <div className="font-mono text-[1.1vw] text-text">SYSTEM ONLINE</div>
        </div>
      </div>
    </div>
  );
}
