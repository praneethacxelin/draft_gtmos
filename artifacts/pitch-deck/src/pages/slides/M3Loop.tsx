export default function M3Loop() {
  return (
    <div className="w-screen h-screen overflow-hidden relative bg-bg text-text">
      <div className="absolute inset-0 grid-bg opacity-50" />
      <div className="absolute -right-[10vw] top-[10vh] w-[40vw] h-[40vw] rounded-full bg-violet/10 blur-[7vw]" />

      <div className="absolute top-[5vh] left-[5vw] right-[5vw] flex items-center justify-between">
        <div className="font-mono text-[1.1vw] text-violet tracking-[0.3em] uppercase">M3 · Intelligence Loop</div>
        <div className="font-mono text-[1.1vw] text-muted">/ THE COMPOUNDING ENGINE</div>
      </div>

      <div className="absolute left-[5vw] top-[12vh] w-[40vw]">
        <h2 className="font-display font-black text-[4.4vw] leading-[0.95] tracking-tight text-text" style={{ textWrap: "balance" }}>
          Every reply, click, and close
          <span className="text-violet"> sharpens the next campaign.</span>
        </h2>
        <p className="mt-[3vh] text-[1.5vw] text-muted leading-snug" style={{ textWrap: "pretty" }}>
          M3 captures engagement events, classifies intent, extracts feedback themes, attributes revenue, and proposes ICP loop-back changes — applied with one click.
        </p>

        <div className="mt-[4vh] grid grid-cols-2 gap-[1vw]">
          <div className="bg-panel border border-border rounded-[0.6vw] p-[1.2vw]">
            <div className="font-mono text-[0.85vw] text-primary tracking-[0.2em] uppercase">Engagement</div>
            <div className="text-[1.15vw] text-text mt-[0.4vh] leading-snug">Clicks, opens, replies, demo bookings.</div>
          </div>
          <div className="bg-panel border border-border rounded-[0.6vw] p-[1.2vw]">
            <div className="font-mono text-[0.85vw] text-amber tracking-[0.2em] uppercase">Intent</div>
            <div className="text-[1.15vw] text-text mt-[0.4vh] leading-snug">Recomputed scoring per account.</div>
          </div>
          <div className="bg-panel border border-border rounded-[0.6vw] p-[1.2vw]">
            <div className="font-mono text-[0.85vw] text-sky tracking-[0.2em] uppercase">Feedback</div>
            <div className="text-[1.15vw] text-text mt-[0.4vh] leading-snug">Sentiment + themes from replies.</div>
          </div>
          <div className="bg-panel border border-border rounded-[0.6vw] p-[1.2vw]">
            <div className="font-mono text-[0.85vw] text-rose tracking-[0.2em] uppercase">Attribution</div>
            <div className="text-[1.15vw] text-text mt-[0.4vh] leading-snug">Revenue tied back to touchpoint.</div>
          </div>
        </div>
      </div>

      <div className="absolute right-[5vw] top-[12vh] w-[45vw] h-[78vh] bg-panel border border-violet/40 rounded-[0.8vw] overflow-hidden">
        <div className="h-[3vh] bg-bg/60 border-b border-border flex items-center px-[1vw] gap-[0.5vw]">
          <div className="w-[0.7vw] h-[0.7vw] rounded-full bg-rose/70" />
          <div className="w-[0.7vw] h-[0.7vw] rounded-full bg-amber/70" />
          <div className="w-[0.7vw] h-[0.7vw] rounded-full bg-primary/70" />
          <div className="ml-[1vw] font-mono text-[0.85vw] text-muted">gtm-factory · /intelligence/loop-back</div>
        </div>
        <div className="p-[1.5vw]">
          <div className="font-mono text-[0.85vw] text-violet tracking-[0.2em] uppercase">M3 · Loop-back proposal</div>
          <div className="font-display font-bold text-[1.7vw] text-text leading-tight mt-[0.5vh]">3 ICP refinements ready to apply</div>
          <div className="text-[1vw] text-muted">Generated from 1,284 engagement events · 72 replies · 14 closed-won</div>

          <div className="mt-[2vh] space-y-[1.2vh]">
            <div className="bg-bg/40 border-l-2 border-primary rounded-r-[0.4vw] p-[1vw]">
              <div className="flex items-center justify-between mb-[0.4vh]">
                <span className="font-mono text-[0.9vw] text-primary">+ ADD</span>
                <span className="font-mono text-[0.85vw] text-muted">confidence · 0.92</span>
              </div>
              <div className="text-[1.15vw] text-text leading-snug">Tighten ICP to companies with a recent ops-leader hire — 4.2× reply rate vs. baseline.</div>
            </div>
            <div className="bg-bg/40 border-l-2 border-amber rounded-r-[0.4vw] p-[1vw]">
              <div className="flex items-center justify-between mb-[0.4vh]">
                <span className="font-mono text-[0.9vw] text-amber">~ REFINE</span>
                <span className="font-mono text-[0.85vw] text-muted">confidence · 0.81</span>
              </div>
              <div className="text-[1.15vw] text-text leading-snug">Move CFO from "champion" to "economic buyer" tier — only closes when looped in by Day 7.</div>
            </div>
            <div className="bg-bg/40 border-l-2 border-rose rounded-r-[0.4vw] p-[1vw]">
              <div className="flex items-center justify-between mb-[0.4vh]">
                <span className="font-mono text-[0.9vw] text-rose">− DROP</span>
                <span className="font-mono text-[0.85vw] text-muted">confidence · 0.74</span>
              </div>
              <div className="text-[1.15vw] text-text leading-snug">Deprioritize sub-200 employee logistics segment — 0.6% conversion across last 4 weeks.</div>
            </div>
          </div>

          <div className="mt-[2vh] bg-bg/40 border border-border rounded-[0.5vw] p-[1vw] flex items-center justify-between">
            <div>
              <div className="font-mono text-[0.85vw] text-muted">QUALIFICATION ROLLUP</div>
              <div className="flex items-center gap-[0.6vw] mt-[0.4vh]">
                <span className="font-mono text-[1vw] px-[0.6vw] py-[0.2vh] rounded-[0.3vw] bg-primary/15 text-primary">SQL · 18</span>
                <span className="font-mono text-[1vw] px-[0.6vw] py-[0.2vh] rounded-[0.3vw] bg-amber/15 text-amber">MQL · 47</span>
                <span className="font-mono text-[1vw] px-[0.6vw] py-[0.2vh] rounded-[0.3vw] bg-violet/15 text-violet">Nurture · 91</span>
              </div>
            </div>
            <div className="font-mono text-[1vw] px-[0.9vw] py-[0.5vh] rounded-[0.4vw] bg-violet/20 text-violet">apply all →</div>
          </div>
        </div>
      </div>
    </div>
  );
}
