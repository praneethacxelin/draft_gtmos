export default function CallToAction() {
  return (
    <div className="w-screen h-screen overflow-hidden relative bg-bg text-text">
      <div className="absolute inset-0 grid-bg opacity-50" />
      <div className="absolute inset-0 bg-gradient-to-tr from-primary/15 via-transparent to-violet/15" />
      <div className="absolute -left-[15vw] -bottom-[20vh] w-[60vw] h-[60vw] rounded-full bg-primary/10 blur-[8vw]" />

      <div className="absolute top-[5vh] left-[5vw] right-[5vw] flex items-center justify-between">
        <div className="flex items-center gap-[1vw]">
          <div className="w-[2.4vw] h-[2.4vw] rounded-[0.5vw] bg-primary flex items-center justify-center">
            <div className="w-[1.2vw] h-[1.2vw] rounded-[0.2vw] bg-bg" />
          </div>
          <div className="font-mono text-[1.2vw] tracking-tight text-text">GTM Factory</div>
        </div>
        <div className="flex items-center gap-[1vw]">
          <div className="w-[0.8vw] h-[0.8vw] rounded-full bg-primary animate-pulse" />
          <div className="font-mono text-[1.1vw] text-text">READY TO SHIP</div>
        </div>
      </div>

      <div className="absolute left-[5vw] top-[26vh] right-[5vw]">
        <div className="font-mono text-[1.2vw] text-primary tracking-[0.3em] uppercase mb-[2vh]">Spin up your first strategy in minutes</div>
        <h1 className="font-display font-black text-[7.5vw] leading-[0.9] tracking-tighter text-text" style={{ textWrap: "balance" }}>
          Run your GTM
          <span className="block text-primary">like a system, not a checklist.</span>
        </h1>
      </div>

      <div className="absolute left-[5vw] right-[5vw] bottom-[8vh] grid grid-cols-3 gap-[1.5vw]">
        <div className="bg-panel border border-primary/30 rounded-[0.8vw] p-[1.8vw]">
          <div className="font-mono text-[0.9vw] text-primary tracking-[0.2em] uppercase mb-[1vh]">Try the product</div>
          <div className="font-display font-bold text-[1.8vw] text-text leading-tight">gtmfactory.app</div>
          <div className="text-[1.15vw] text-muted leading-snug mt-[0.8vh]">Sign in, paste a one-line brief, watch the S1 pipeline run live.</div>
        </div>
        <div className="bg-panel border border-amber/30 rounded-[0.8vw] p-[1.8vw]">
          <div className="font-mono text-[0.9vw] text-amber tracking-[0.2em] uppercase mb-[1vh]">Book a walkthrough</div>
          <div className="font-display font-bold text-[1.8vw] text-text leading-tight">30 minutes</div>
          <div className="text-[1.15vw] text-muted leading-snug mt-[0.8vh]">Bring a real account list — leave with a scored, sequenced campaign.</div>
        </div>
        <div className="bg-panel border border-violet/30 rounded-[0.8vw] p-[1.8vw]">
          <div className="font-mono text-[0.9vw] text-violet tracking-[0.2em] uppercase mb-[1vh]">Talk to the team</div>
          <div className="font-display font-bold text-[1.8vw] text-text leading-tight">hello@gtmfactory.app</div>
          <div className="text-[1.15vw] text-muted leading-snug mt-[0.8vh]">Design partners and pilots welcome — we ship weekly.</div>
        </div>
      </div>
    </div>
  );
}
