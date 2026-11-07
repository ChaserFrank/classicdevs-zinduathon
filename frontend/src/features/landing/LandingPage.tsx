import { motion, useReducedMotion, useScroll, useTransform } from "framer-motion";
import { useCallback, useState } from "react";
import { Link } from "react-router-dom";

import { GlassPill } from "@/components/glass/Glass";
import { SignalPlanet } from "@/components/space/SignalPlanet";

import { DemoPanel, ForRecruiters, HowItWorks, PrivacyNote, ScoringRules } from "./sections";

const HEADLINE = "Your commits already tell the story.";
const INTRO_KEY = "skillproof.introSeen";

function introSeen(): boolean {
  try {
    return window.sessionStorage.getItem(INTRO_KEY) === "1";
  } catch {
    return false;
  }
}

/** Landing: hero with the Signal Planet, then the demo, how it works, scoring, recruiters, privacy. */
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

  // Scroll: over the first 600px the planet rises and grows a little, then fades behind content.
  const { scrollY } = useScroll();
  const planetY = useTransform(scrollY, [0, 600], [0, reduce ? 0 : -120]);
  const planetScale = useTransform(scrollY, [0, 600], [1, reduce ? 1 : 1.08]);
  const planetOpacity = useTransform(scrollY, [300, 900], [1, 0.15]);

  const words = HEADLINE.split(" ");
  return (
    <>
      <section className="relative isolate flex min-h-[100svh] flex-col items-center overflow-hidden px-4 pt-36 text-center sm:pt-40">
        <motion.div
          aria-hidden
          className="absolute inset-0 -z-10"
          style={{ y: planetY, scale: planetScale, opacity: planetOpacity }}
        >
          <SignalPlanet intro={playIntro} onIntroDone={onIntroDone} />
        </motion.div>
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
      <div className="relative -mt-24 pb-8">
        <DemoPanel />
      </div>
      <HowItWorks />
      <ScoringRules />
      <ForRecruiters />
      <PrivacyNote />
    </>
  );
}
