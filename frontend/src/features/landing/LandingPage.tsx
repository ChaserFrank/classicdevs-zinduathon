import { motion, useReducedMotion } from "framer-motion";
import { useCallback, useState } from "react";
import { Link } from "react-router-dom";

import { GlassPill } from "@/components/glass/Glass";
import { SignalPlanet } from "@/components/space/SignalPlanet";

const HEADLINE = "Your commits already tell the story.";
const INTRO_KEY = "skillproof.introSeen";

function introSeen(): boolean {
  try {
    return window.sessionStorage.getItem(INTRO_KEY) === "1";
  } catch {
    return false;
  }
}

/** Landing hero (Phase 1: hero only; the sections below the fold arrive in Phase 2). */
export function LandingPage() {
  const reduce = useReducedMotion();
  const [playIntro] = useState(() => !reduce && !introSeen());
  const [revealed, setRevealed] = useState(!playIntro);
  const onIntroDone = useCallback(() => {
    setRevealed(true);
    try {
      window.sessionStorage.setItem(INTRO_KEY, "1");
    } catch {
      /* the intro just plays again next time */
    }
  }, []);

  const words = HEADLINE.split(" ");
  return (
    <section className="relative isolate flex min-h-[100svh] flex-col items-center overflow-hidden px-4 pt-36 text-center sm:pt-40">
      <SignalPlanet className="-z-10" intro={playIntro} onIntroDone={onIntroDone} />
      {/* Readability scrim behind the type, where the planet's rim can rise into it. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-[55%] bg-gradient-to-b from-void via-void/80 to-transparent"
      />
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={revealed ? { opacity: 1, y: 0 } : {}}
        transition={{ duration: 0.4 }}
      >
        <GlassPill className="text-ink">
          <span
            aria-hidden
            className="h-1.5 w-1.5 rounded-full bg-flare shadow-[0_0_8px_rgb(var(--flare))]"
          />
          Proof of skill for the AI era
        </GlassPill>
      </motion.div>
      <h1 className="mt-6 max-w-3xl text-[clamp(2.4rem,6vw,4.5rem)]" aria-label={HEADLINE}>
        {words.map((word, i) => (
          <motion.span
            key={i}
            aria-hidden
            className="inline-block whitespace-pre"
            initial={{ opacity: 0, y: 14, filter: "blur(6px)" }}
            animate={revealed ? { opacity: 1, y: 0, filter: "blur(0px)" } : {}}
            transition={{ duration: 0.5, delay: 0.1 + i * 0.04, ease: [0.22, 1, 0.36, 1] }}
          >
            {word}
            {i < words.length - 1 ? " " : ""}
          </motion.span>
        ))}
      </h1>
      <motion.p
        className="mt-5 max-w-xl text-lg text-mist"
        initial={{ opacity: 0, y: 10 }}
        animate={revealed ? { opacity: 1, y: 0 } : {}}
        transition={{ duration: 0.5, delay: 0.45 }}
      >
        SkillProof reads your public GitHub work and shows recruiters the evidence behind every skill.
      </motion.p>
      <motion.div
        className="mt-8 flex flex-wrap justify-center gap-3"
        initial={{ opacity: 0, y: 10 }}
        animate={revealed ? { opacity: 1, y: 0 } : {}}
        transition={{ duration: 0.5, delay: 0.6 }}
      >
        <Link
          to="/register?role=job_seeker"
          className="inline-flex h-12 items-center rounded-full bg-ink px-6 font-semibold text-black transition hover:bg-white"
        >
          Get your skill card
        </Link>
        <Link
          to="/register?role=recruiter"
          className="glass-pill inline-flex h-12 items-center rounded-full px-6 font-semibold text-ink transition hover:bg-white/10"
        >
          I'm hiring
        </Link>
      </motion.div>
    </section>
  );
}
