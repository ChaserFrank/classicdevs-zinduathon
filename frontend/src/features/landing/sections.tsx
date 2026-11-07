import { BellRing, Check, GitBranch, Lock, Search, ShieldCheck, Sparkles, X } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { GlassCard, GlassPanel, GlassPill } from "@/components/glass/Glass";
import { TierBadge } from "@/components/ui/Badge";

function Section({
  id,
  eyebrow,
  title,
  intro,
  children,
}: {
  id: string;
  eyebrow: string;
  title: string;
  intro?: string;
  children: ReactNode;
}) {
  return (
    <section
      id={id}
      aria-labelledby={`${id}-title`}
      className="mx-auto max-w-6xl scroll-mt-24 px-4 py-20 sm:py-28"
    >
      <GlassPill className="text-mist">{eyebrow}</GlassPill>
      <h2 id={`${id}-title`} className="mt-5 max-w-2xl text-[clamp(1.9rem,4vw,3rem)]">
        {title}
      </h2>
      {intro && <p className="mt-4 max-w-2xl text-lg text-mist">{intro}</p>}
      <div className="mt-12">{children}</div>
    </section>
  );
}

/** CV claim (noise) vs SkillProof evidence (signal), side by side. */
export function DemoPanel() {
  return (
    <div className="mx-auto max-w-5xl px-4">
      <GlassPanel glow className="grid gap-6 p-6 sm:p-8 md:grid-cols-[1fr_1.4fr]">
        <GlassCard className="p-5">
          <p className="text-sm text-mist">On a CV</p>
          <p className="mt-3 text-2xl font-bold text-mist line-through decoration-bad/80 decoration-2">
            Expert in React
          </p>
          <p className="mt-3 text-sm text-mist">No dates, no code, no way to check.</p>
        </GlassCard>
        <GlassCard className="p-5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm text-mist">On SkillProof</p>
            <TierBadge tier="Strong" />
          </div>
          <p className="mt-3 text-2xl font-bold">React</p>
          <ul className="mt-4 space-y-2 text-sm">
            {[
              ["shop-app", "44 commits · Jan–Oct 2026 · tests · CI"],
              ["portfolio-site", "16 commits · Aug–Oct 2026 · tests"],
            ].map(([repo, detail]) => (
              <li
                key={repo}
                className="flex flex-wrap items-baseline justify-between gap-2 rounded-xl bg-white/[0.03] px-3 py-2"
              >
                <span className="font-medium text-ink">{repo}</span>
                <span className="text-mist">{detail}</span>
              </li>
            ))}
          </ul>
          <p className="mt-4 text-sm text-mist">
            Evidence 2.0 from two sustained projects. Every number links to the repos behind it.
          </p>
        </GlassCard>
      </GlassPanel>
    </div>
  );
}

export function HowItWorks() {
  const steps = [
    {
      icon: GitBranch,
      title: "Connect GitHub",
      body: "Sign in with GitHub. We read public repositories you own; never private code.",
    },
    {
      icon: Sparkles,
      title: "We read the evidence",
      body: "Commits over time, tests, CI, dependencies and who wrote the code become skills with confidence labels.",
    },
    {
      icon: ShieldCheck,
      title: "Share your card",
      body: "One link with your Signal Score, proven skills and the repos behind each one. You control who can find it.",
    },
  ];
  return (
    <Section id="how" eyebrow="How it works" title="From commits to a card in about a minute.">
      <ol className="grid gap-4 md:grid-cols-3">
        {steps.map(({ icon: Icon, title, body }, i) => (
          <li key={title}>
            <GlassCard className="h-full p-6">
              <div className="flex items-center gap-3">
                <span className="grid h-10 w-10 place-items-center rounded-xl bg-flare/15 text-flare-hot">
                  <Icon aria-hidden className="h-5 w-5" />
                </span>
                <span className="tabular text-sm text-mist">Step {i + 1}</span>
              </div>
              <h3 className="mt-5 text-xl">{title}</h3>
              <p className="mt-2 text-mist">{body}</p>
            </GlassCard>
          </li>
        ))}
      </ol>
    </Section>
  );
}

export function ScoringRules() {
  const rules = [
    ["Consistency", "Active weeks in the last year. Steady work beats a weekend sprint."],
    ["Iteration", "Small, frequent commits and projects that keep going."],
    ["Quality", "Tests, CI, a real README, Docker or an .env example."],
    ["Breadth", "How many skills reach Strong or Moderate evidence."],
    ["Ownership", "Projects where you wrote most of the code."],
  ];
  return (
    <Section
      id="scoring"
      eyebrow="Scoring"
      title="Rules set every score. AI only writes the summary."
      intro="The Signal Score is five sub-scores of 0–20, each with a plain-language reason. The AI writes three sentences about the result and is checked against it: it can't invent a skill or a number."
    >
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {rules.map(([name, body]) => (
          <GlassCard key={name} className="p-5">
            <p className="tabular text-sm text-flare-hot">0–20</p>
            <h3 className="mt-2 text-lg">{name}</h3>
            <p className="mt-2 text-sm text-mist">{body}</p>
          </GlassCard>
        ))}
      </div>
    </Section>
  );
}

export function ForRecruiters() {
  const points = [
    {
      icon: Search,
      title: "Search by proven skill",
      body: "Filter by skills at Strong or Moderate, minimum score and open to work.",
    },
    {
      icon: Check,
      title: "Shortlist and match",
      body: "Post a job with weighted skills and see candidates ranked by match.",
    },
    {
      icon: BellRing,
      title: "Feedback they actually get",
      body: "Your feedback reaches candidates in-app, by email and by SMS.",
    },
  ];
  return (
    <Section id="recruiters" eyebrow="For recruiters" title="Stop guessing from keywords.">
      <div className="grid gap-4 md:grid-cols-3">
        {points.map(({ icon: Icon, title, body }) => (
          <GlassCard key={title} className="p-6">
            <Icon aria-hidden className="h-5 w-5 text-flare-hot" />
            <h3 className="mt-4 text-lg">{title}</h3>
            <p className="mt-2 text-mist">{body}</p>
          </GlassCard>
        ))}
      </div>
      <div className="mt-10">
        <Link
          to="/register?role=recruiter"
          className="glass-pill inline-flex h-12 items-center rounded-full px-6 font-semibold text-ink hover:bg-white/10"
        >
          Create a recruiter account
        </Link>
      </div>
    </Section>
  );
}

export function PrivacyNote() {
  const items = [
    "Public repositories only",
    "You decide if recruiters can find your card",
    "Download or delete your data any time",
    "Built to the Kenya Data Protection Act, 2019",
  ];
  return (
    <Section id="privacy" eyebrow="Privacy" title="Your evidence, your call.">
      <GlassPanel className="grid gap-6 p-6 sm:p-8 md:grid-cols-[auto_1fr] md:items-center">
        <span className="grid h-14 w-14 place-items-center rounded-2xl bg-white/5 text-flare-hot">
          <Lock aria-hidden className="h-6 w-6" />
        </span>
        <ul className="grid gap-3 sm:grid-cols-2">
          {items.map((item) => (
            <li key={item} className="flex items-start gap-2">
              <Check aria-hidden className="mt-0.5 h-4 w-4 shrink-0 text-ok" />
              {item}
            </li>
          ))}
        </ul>
      </GlassPanel>
      <p className="mt-6 text-sm text-mist">
        Recruiters never see your email or phone. <X aria-hidden className="inline h-3.5 w-3.5" /> No selling
        of data.{" "}
        <Link to="/privacy" className="text-flare-hot hover:underline">
          Read the privacy policy
        </Link>
      </p>
    </Section>
  );
}
